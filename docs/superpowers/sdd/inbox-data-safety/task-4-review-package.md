# Review package: 604b64a..6a0ac41

## Commits
6a0ac41 feat: add inbox transaction recovery store

## Files changed
 obsidian_kb_skill/scripts/backup_policy.py     |   5 +
 obsidian_kb_skill/scripts/inbox_transaction.py | 599 +++++++++++++++++++++++++
 tests/test_backup_policy.py                    |  38 ++
 tests/test_inbox_transaction.py                | 319 +++++++++++++
 4 files changed, 961 insertions(+)

## Diff
diff --git a/obsidian_kb_skill/scripts/backup_policy.py b/obsidian_kb_skill/scripts/backup_policy.py
index 021cac0..d907c60 100644
--- a/obsidian_kb_skill/scripts/backup_policy.py
+++ b/obsidian_kb_skill/scripts/backup_policy.py
@@ -167,20 +167,25 @@ def prune_backups(
     candidates: list[_Candidate] = []
     directories: list[Path] = []
     try:
         with os.scandir(backup_root) as iterator:
             top_entries = sorted(iterator, key=lambda entry: entry.name)
     except OSError as exc:
         warnings.append(f"cannot scan backup root: {exc}")
         return CleanupResult(policy.keep_per_note, 0, 0, tuple(warnings))
 
     for entry in top_entries:
+        # Inbox transactions own a durable recovery namespace, not ordinary
+        # timestamped note history. Retention must neither inspect nor warn for
+        # this exact top-level name.
+        if entry.name == "inbox":
+            continue
         stamp_path = Path(entry.path)
         try:
             is_real_directory = (
                 not entry.is_symlink() and entry.is_dir(follow_symlinks=False)
             )
         except OSError as exc:
             warnings.append(f"cannot inspect backup item {entry.name}: {exc}")
             continue
         if not is_real_directory or not STAMP_RE.fullmatch(entry.name):
             warnings.append(f"retained unknown backup item: {entry.name}")
diff --git a/obsidian_kb_skill/scripts/inbox_transaction.py b/obsidian_kb_skill/scripts/inbox_transaction.py
new file mode 100644
index 0000000..84a8b2e
--- /dev/null
+++ b/obsidian_kb_skill/scripts/inbox_transaction.py
@@ -0,0 +1,599 @@
+"""Durable recovery-store preparation for one Inbox operation.
+
+This module deliberately stops after the immutable source/index pre-images,
+manifest, and ``backup-ready`` journal event are durable.  Task 5 owns all
+business-file mutation.
+"""
+from __future__ import annotations
+
+import datetime
+import hashlib
+import json
+import os
+import re
+import secrets
+import stat
+from dataclasses import dataclass
+from pathlib import Path
+from typing import Any, Iterable, Literal, Mapping, Protocol
+
+from obsidian_kb_skill.scripts.inbox_plan import (
+    InboxIssue,
+    InboxPlanItem,
+    sha256_bytes,
+)
+from obsidian_kb_skill.scripts.vault_paths import (
+    VaultPathError,
+    resolve_existing_within_vault,
+    resolve_target_within_vault,
+    validate_vault_root,
+)
+
+
+ApplyStatus = Literal[
+    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
+]
+
+_BACKUP_ROOT = Path(".obsidian-kb-backups")
+_INBOX_ROOT = _BACKUP_ROOT / "inbox"
+_LOCK_ROOT = _INBOX_ROOT / ".locks"
+_LOCK_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
+_RESTORE_ID_RE = re.compile(
+    r"^\d{4}-\d{2}-\d{2}-\d{6}Z-[0-9a-f]{16}$"
+)
+_HELD_LOCK_IDENTITIES: dict[Path, tuple[int, int]] = {}
+
+
+class InboxFailureInjector(Protocol):
+    def checkpoint(self, name: str) -> None: ...
+
+
+@dataclass(frozen=True)
+class InboxApplyResult:
+    source: Path
+    destination: Path | None
+    status: ApplyStatus
+    applied: bool
+    restore_id: str | None
+    backup: Path | None
+    issue: InboxIssue | None
+    warnings: tuple[str, ...] = ()
+    rollback_actions: tuple[str, ...] = ()
+
+
+@dataclass(frozen=True)
+class PreparedInboxOperation:
+    vault: Path
+    item: InboxPlanItem
+    restore_id: str
+    operation_root: Path
+    manifest: Mapping[str, Any]
+    held_locks: tuple[Path, ...]
+
+
+class InboxPreparationError(OSError):
+    """Stable fail-closed preparation error for Task 5 result mapping."""
+
+    def __init__(self, code: str, message: str) -> None:
+        self.code = code
+        super().__init__(message)
+
+
+class InboxLockBusyError(InboxPreparationError):
+    """A resource lock is already owned by another recovery record."""
+
+    def __init__(self, owner_restore_id: str) -> None:
+        self.owner_restore_id = owner_restore_id
+        super().__init__(
+            "inbox-lock-busy",
+            f"Inbox resource is locked by restore ID {owner_restore_id}",
+        )
+
+
+def _checkpoint(injector: InboxFailureInjector | None, name: str) -> None:
+    if injector is not None:
+        injector.checkpoint(name)
+
+
+def _write_new_durable(path: Path, payload: bytes) -> None:
+    """Create one new file exclusively, flush it, and fsync its exact bytes."""
+    with path.open("xb") as handle:
+        handle.write(payload)
+        handle.flush()
+        os.fsync(handle.fileno())
+
+
+def _json_line(payload: Mapping[str, Any]) -> bytes:
+    return (
+        json.dumps(
+            payload,
+            ensure_ascii=True,
+            sort_keys=True,
+            separators=(",", ":"),
+        )
+        + "\n"
+    ).encode("utf-8")
+
+
+def _append_event(
+    operation: PreparedInboxOperation, phase: str, **data: Any
+) -> None:
+    """Append one complete, flushed, fsynced JSON Lines journal event."""
+    relative = operation.operation_root.relative_to(operation.vault) / "events.jsonl"
+    path = _resolved_target(operation.vault, relative, label="Inbox journal")
+    lexical = operation.vault / relative
+    if os.path.lexists(lexical) and (
+        lexical.is_symlink() or not lexical.is_file() or path != lexical
+    ):
+        raise InboxPreparationError(
+            "unsafe-inbox-journal", "Inbox journal is not a real contained file"
+        )
+    event: dict[str, Any] = {
+        "phase": phase,
+        "restore_id": operation.restore_id,
+        "timestamp": _utc_timestamp(),
+    }
+    event.update(data)
+    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
+    flags |= getattr(os, "O_CLOEXEC", 0)
+    flags |= getattr(os, "O_NOFOLLOW", 0)
+    flags |= getattr(os, "O_BINARY", 0)
+    fd = os.open(path, flags, 0o600)
+    try:
+        payload = _json_line(event)
+        view = memoryview(payload)
+        while view:
+            written = os.write(fd, view)
+            if written <= 0:
+                raise OSError("could not append Inbox journal event")
+            view = view[written:]
+        os.fsync(fd)
+    finally:
+        os.close(fd)
+
+
+def _acquire_lock(vault: Path, key: str, restore_id: str) -> Path:
+    """Create one hash-keyed, durable owner lock without stealing an old lock."""
+    root = validate_vault_root(vault)
+    if not _LOCK_KEY_RE.fullmatch(key):
+        raise InboxPreparationError("unsafe-lock-key", "Inbox lock key is invalid")
+    if not _RESTORE_ID_RE.fullmatch(restore_id):
+        raise InboxPreparationError(
+            "unsafe-restore-id", "Inbox restore ID is invalid"
+        )
+    _ensure_directory_chain(root, _LOCK_ROOT)
+    relative = _LOCK_ROOT / f"{key}.lock"
+    path = _resolved_target(root, relative, label="Inbox lock")
+    try:
+        _write_new_durable(path, _json_line({"restore_id": restore_id}))
+    except FileExistsError:
+        owner = _read_lock_owner(root, relative)
+        raise InboxLockBusyError(owner) from None
+    status = path.lstat()
+    _HELD_LOCK_IDENTITIES[path] = (status.st_dev, status.st_ino)
+    return path
+
+
+def _release_locks(paths: Iterable[Path]) -> tuple[str, ...]:
+    """Release only real lock files; retain unsafe replacements with warnings."""
+    warnings: list[str] = []
+    for path in reversed(tuple(paths)):
+        expected = _HELD_LOCK_IDENTITIES.get(path)
+        try:
+            status = path.lstat()
+            observed = (status.st_dev, status.st_ino)
+            if (
+                expected is None
+                or observed != expected
+                or not stat.S_ISREG(status.st_mode)
+            ):
+                warnings.append(f"retained unsafe Inbox lock: {path.name}")
+                _HELD_LOCK_IDENTITIES.pop(path, None)
+                continue
+            path.unlink()
+            _HELD_LOCK_IDENTITIES.pop(path, None)
+        except FileNotFoundError:
+            _HELD_LOCK_IDENTITIES.pop(path, None)
+            continue
+        except OSError as exc:
+            warnings.append(f"could not release Inbox lock {path.name}: {exc}")
+    return tuple(warnings)
+
+
+def _utc_timestamp() -> str:
+    return datetime.datetime.now(datetime.timezone.utc).strftime(
+        "%Y-%m-%d-%H%M%SZ"
+    )
+
+
+def _new_restore_id() -> str:
+    return f"{_utc_timestamp()}-{secrets.token_hex(8)}"
+
+
+def _safe_relative(path: Path, *, label: str) -> Path:
+    relative = Path(path)
+    if (
+        relative.is_absolute()
+        or not relative.parts
+        or any(part in ("", ".", "..") for part in relative.parts)
+    ):
+        raise InboxPreparationError(
+            "unsafe-inbox-path", f"{label} is not a safe Vault-relative path"
+        )
+    return relative
+
+
+def _resolved_target(vault: Path, relative: Path, *, label: str) -> Path:
+    safe = _safe_relative(relative, label=label)
+    try:
+        return resolve_target_within_vault(vault, safe, label=label)
+    except (OSError, VaultPathError) as exc:
+        raise InboxPreparationError(
+            "unsafe-inbox-path", f"{label} could not be resolved safely"
+        ) from exc
+
+
+def _ensure_real_directory(vault: Path, relative: Path) -> Path:
+    target = _resolved_target(vault, relative, label="Inbox recovery directory")
+    lexical = vault / relative
+    if os.path.lexists(lexical):
+        if lexical.is_symlink() or not lexical.is_dir() or target != lexical:
+            raise InboxPreparationError(
+                "unsafe-recovery-root",
+                "Inbox recovery directory is not a real contained directory",
+            )
+        return target
+    try:
+        target.mkdir(exist_ok=False)
+    except FileExistsError:
+        target = _resolved_target(
+            vault, relative, label="Inbox recovery directory"
+        )
+        if lexical.is_symlink() or not lexical.is_dir() or target != lexical:
+            raise InboxPreparationError(
+                "unsafe-recovery-root",
+                "Inbox recovery directory changed during creation",
+            ) from None
+    return target
+
+
+def _ensure_directory_chain(vault: Path, relative: Path) -> Path:
+    safe = _safe_relative(relative, label="Inbox recovery directory")
+    current = Path()
+    result = vault
+    for part in safe.parts:
+        current /= part
+        result = _ensure_real_directory(vault, current)
+    return result
+
+
+def _create_operation_directory(vault: Path, relative: Path) -> Path:
+    parent = _ensure_directory_chain(vault, relative.parent)
+    target = _resolved_target(vault, relative, label="Inbox operation directory")
+    lexical = vault / relative
+    if os.path.lexists(lexical):
+        raise FileExistsError("Inbox restore ID already exists")
+    if target.parent != parent:
+        raise InboxPreparationError(
+            "unsafe-operation-root", "Inbox operation parent changed"
+        )
+    target.mkdir(exist_ok=False)
+    return target
+
+
+def _read_lock_owner(vault: Path, relative: Path) -> str:
+    try:
+        raw, _status = _read_regular_file(vault, relative, label="Inbox lock")
+        payload = json.loads(raw.decode("utf-8"))
+        owner = payload.get("restore_id")
+        if isinstance(owner, str) and _RESTORE_ID_RE.fullmatch(owner):
+            return owner
+    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
+        pass
+    return "unknown"
+
+
+def _lock_key(relative: Path) -> str:
+    return hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
+
+
+def _read_regular_file(
+    vault: Path, relative: Path, *, label: str
+) -> tuple[bytes, os.stat_result]:
+    safe = _safe_relative(relative, label=label)
+    try:
+        path = resolve_existing_within_vault(vault, safe, label=label)
+    except (OSError, VaultPathError) as exc:
+        raise InboxPreparationError(
+            "unsafe-inbox-path", f"{label} could not be resolved safely"
+        ) from exc
+    lexical = vault / safe
+    if lexical.is_symlink() or not path.is_file():
+        raise InboxPreparationError(
+            "unsafe-inbox-path", f"{label} is not a real regular file"
+        )
+    flags = os.O_RDONLY
+    flags |= getattr(os, "O_CLOEXEC", 0)
+    flags |= getattr(os, "O_NOFOLLOW", 0)
+    flags |= getattr(os, "O_BINARY", 0)
+    fd = os.open(path, flags)
+    try:
+        status = os.fstat(fd)
+        if not stat.S_ISREG(status.st_mode):
+            raise InboxPreparationError(
+                "unsafe-inbox-path", f"{label} is not a regular file"
+            )
+        chunks: list[bytes] = []
+        while True:
+            chunk = os.read(fd, 1024 * 1024)
+            if not chunk:
+                break
+            chunks.append(chunk)
+        return b"".join(chunks), status
+    finally:
+        os.close(fd)
+
+
+def _metadata(status: os.stat_result) -> dict[str, int]:
+    return {
+        "atime_ns": status.st_atime_ns,
+        "mode": stat.S_IMODE(status.st_mode),
+        "mtime_ns": status.st_mtime_ns,
+        "size": status.st_size,
+    }
+
+
+def _backup_relative(operation_relative: Path, kind: str, original: Path) -> Path:
+    safe_original = _safe_relative(original, label=f"Inbox {kind} path")
+    return operation_relative / kind / safe_original
+
+
+def _write_backup(
+    vault: Path,
+    relative: Path,
+    payload: bytes,
+    *,
+    created_files: list[Path],
+    created_directories: list[Path],
+) -> Path:
+    operation_relative = _INBOX_ROOT / relative.parts[len(_INBOX_ROOT.parts)]
+    current = operation_relative
+    for part in relative.parts[len(operation_relative.parts) : -1]:
+        current /= part
+        _ensure_real_directory(vault, current)
+        created_directories.append(current)
+    path = _resolved_target(vault, relative, label="Inbox backup")
+    created_files.append(relative)
+    _write_new_durable(path, payload)
+    return path
+
+
+def _cleanup_unpersisted_operation(
+    vault: Path,
+    files: Iterable[Path],
+    directories: Iterable[Path],
+) -> tuple[str, ...]:
+    warnings: list[str] = []
+    for relative in reversed(tuple(files)):
+        lexical = vault / relative
+        try:
+            path = _resolved_target(vault, relative, label="Inbox cleanup file")
+            if not os.path.lexists(lexical):
+                continue
+            if lexical.is_symlink() or not lexical.is_file() or path != lexical:
+                warnings.append(f"retained unsafe recovery debris: {relative.name}")
+                continue
+            lexical.unlink()
+        except OSError:
+            warnings.append(f"retained recovery debris: {relative.name}")
+    for relative in sorted(
+        set(directories),
+        key=lambda item: (len(item.parts), item.as_posix()),
+        reverse=True,
+    ):
+        lexical = vault / relative
+        try:
+            path = _resolved_target(vault, relative, label="Inbox cleanup directory")
+            if not os.path.lexists(lexical):
+                continue
+            if lexical.is_symlink() or not lexical.is_dir() or path != lexical:
+                warnings.append(f"retained unsafe recovery debris: {relative.name}")
+                continue
+            lexical.rmdir()
+        except OSError:
+            warnings.append(f"retained recovery debris: {relative.name}")
+    return tuple(warnings)
+
+
+def _validate_item(item: InboxPlanItem) -> None:
+    if (
+        item.status != "ready"
+        or item.proposal is None
+        or item.source_sha256 is None
+        or item.identity is None
+    ):
+        raise InboxPreparationError(
+            "inbox-item-not-ready", "Inbox item is not ready for preparation"
+        )
+
+
+def prepare_inbox_operation(
+    vault: Path,
+    item: InboxPlanItem,
+    *,
+    injector: InboxFailureInjector | None = None,
+) -> PreparedInboxOperation:
+    """Persist verified pre-images and ``backup-ready`` while changing no note."""
+    root = validate_vault_root(vault)
+    _validate_item(item)
+    assert item.proposal is not None and item.source_sha256 is not None
+    proposal = item.proposal
+    source_relative = _safe_relative(item.source, label="Inbox source")
+    destination_relative = _safe_relative(
+        proposal.destination, label="Inbox destination"
+    )
+    destination = _resolved_target(
+        root, destination_relative, label="Inbox destination"
+    )
+    if os.path.lexists(root / destination_relative) or os.path.lexists(destination):
+        raise InboxPreparationError(
+            "destination-exists", "Inbox destination already exists"
+        )
+
+    index_plan = proposal.index
+    index_relative = (
+        _safe_relative(index_plan.index, label="Inbox index")
+        if index_plan.action == "append" and index_plan.index is not None
+        else None
+    )
+    resources = [("source", source_relative)]
+    if index_relative is not None:
+        resources.append(("index", index_relative))
+    keyed_resources = sorted(
+        ((_lock_key(relative), kind) for kind, relative in resources),
+        key=lambda value: value[0],
+    )
+
+    restore_id = _new_restore_id()
+    held_locks: list[Path] = []
+    operation_relative = _INBOX_ROOT / restore_id
+    created_files: list[Path] = []
+    created_directories: list[Path] = []
+    manifest_durable = False
+    try:
+        for key, kind in keyed_resources:
+            _checkpoint(injector, f"lock-{kind}")
+            held_locks.append(_acquire_lock(root, key, restore_id))
+
+        _checkpoint(injector, "backup-root")
+        operation_root = _create_operation_directory(root, operation_relative)
+        created_directories.append(operation_relative)
+
+        source_bytes, source_status = _read_regular_file(
+            root, source_relative, label="Inbox source"
+        )
+        if sha256_bytes(source_bytes) != item.source_sha256:
+            raise InboxPreparationError(
+                "stale-inbox-source", "Inbox source bytes changed after planning"
+            )
+        source_backup_relative = _backup_relative(
+            operation_relative, "source", source_relative
+        )
+        _checkpoint(injector, "backup-source-write")
+        _write_backup(
+            root,
+            source_backup_relative,
+            source_bytes,
+            created_files=created_files,
+            created_directories=created_directories,
+        )
+        _checkpoint(injector, "backup-source-fsync")
+        verified_source, _source_backup_status = _read_regular_file(
+            root, source_backup_relative, label="Inbox source backup"
+        )
+        if (
+            verified_source != source_bytes
+            or sha256_bytes(verified_source) != item.source_sha256
+        ):
+            raise InboxPreparationError(
+                "invalid-source-backup", "Inbox source backup verification failed"
+            )
+
+        index_manifest: dict[str, Any] | None = None
+        if index_relative is not None:
+            if (
+                index_plan.before is None
+                or index_plan.before_sha256 is None
+                or index_plan.after_sha256 is None
+            ):
+                raise InboxPreparationError(
+                    "invalid-index-plan", "Inbox index plan is incomplete"
+                )
+            index_bytes, index_status = _read_regular_file(
+                root, index_relative, label="Inbox index"
+            )
+            if (
+                index_bytes != index_plan.before
+                or sha256_bytes(index_bytes) != index_plan.before_sha256
+            ):
+                raise InboxPreparationError(
+                    "stale-inbox-index", "Inbox index bytes changed after planning"
+                )
+            index_backup_relative = _backup_relative(
+                operation_relative, "index", index_relative
+            )
+            _checkpoint(injector, "backup-index-write")
+            _write_backup(
+                root,
+                index_backup_relative,
+                index_bytes,
+                created_files=created_files,
+                created_directories=created_directories,
+            )
+            verified_index, _index_backup_status = _read_regular_file(
+                root, index_backup_relative, label="Inbox index backup"
+            )
+            if (
+                verified_index != index_bytes
+                or sha256_bytes(verified_index) != index_plan.before_sha256
+            ):
+                raise InboxPreparationError(
+                    "invalid-index-backup", "Inbox index backup verification failed"
+                )
+            index_manifest = {
+                "action": index_plan.action,
+                "after_sha256": index_plan.after_sha256,
+                "backup": index_backup_relative.relative_to(
+                    operation_relative
+                ).as_posix(),
+                "before_sha256": index_plan.before_sha256,
+                "metadata": _metadata(index_status),
+                "path": index_relative.as_posix(),
+            }
+
+        manifest: dict[str, Any] = {
+            "destination": {
+                "absent": True,
+                "path": destination_relative.as_posix(),
+                "rendered_sha256": proposal.rendered_sha256,
+            },
+            "index": index_manifest,
+            "restore_id": restore_id,
+            "schema_version": 1,
+            "source": {
+                "backup": source_backup_relative.relative_to(
+                    operation_relative
+                ).as_posix(),
+                "metadata": _metadata(source_status),
+                "path": source_relative.as_posix(),
+                "sha256": item.source_sha256,
+            },
+        }
+        manifest_relative = operation_relative / "manifest.json"
+        manifest_path = _resolved_target(
+            root, manifest_relative, label="Inbox manifest"
+        )
+        _checkpoint(injector, "manifest-write")
+        created_files.append(manifest_relative)
+        _write_new_durable(manifest_path, _json_line(manifest))
+        manifest_durable = True
+        _checkpoint(injector, "manifest-fsync")
+
+        operation = PreparedInboxOperation(
+            vault=root,
+            item=item,
+            restore_id=restore_id,
+            operation_root=operation_root,
+            manifest=manifest,
+            held_locks=tuple(held_locks),
+        )
+        _checkpoint(injector, "journal-backup-ready")
+        _append_event(operation, "backup-ready")
+        return operation
+    except Exception:
+        if not manifest_durable:
+            _cleanup_unpersisted_operation(
+                root, created_files, created_directories
+            )
+        _release_locks(held_locks)
+        raise
diff --git a/tests/test_backup_policy.py b/tests/test_backup_policy.py
index a4d2682..9096ee4 100644
--- a/tests/test_backup_policy.py
+++ b/tests/test_backup_policy.py
@@ -311,10 +311,48 @@ def test_rmdir_error_becomes_warning(tmp_path, monkeypatch):
 def test_regular_file_candidate_resolves_inside_vault(tmp_path):
     vault = make_vault(tmp_path)
     candidate = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "old")
     os.utime(candidate, ns=(1, 1))
     latest = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "new")
     os.utime(latest, ns=(2, 2))
     result = prune_backups(vault, BackupPolicy(1, True))
     assert not candidate.exists()
     assert latest.is_file()
     assert result.deleted == 1
+
+
+def test_exact_top_level_inbox_namespace_is_preserved_silently(tmp_path):
+    vault = make_vault(tmp_path)
+    transaction = (
+        vault / ".obsidian-kb-backups" / "inbox" / "restore-id" / "manifest.json"
+    )
+    transaction.parent.mkdir(parents=True)
+    transaction.write_text("recovery", encoding="utf-8")
+
+    result = prune_backups(vault, BackupPolicy(1, True))
+
+    assert transaction.read_text(encoding="utf-8") == "recovery"
+    assert result.scanned == 0
+    assert result.deleted == 0
+    assert result.warnings == ()
+
+
+def test_inbox_like_names_are_not_hidden_from_ordinary_retention(tmp_path):
+    vault = make_vault(tmp_path)
+    first = backup(
+        vault, "2026-07-10-100000", "inbox/Tasks/a/TASK.md", "old"
+    )
+    latest = backup(
+        vault, "2026-07-10-100001", "inbox/Tasks/a/TASK.md", "new"
+    )
+    near_name = vault / ".obsidian-kb-backups" / "inbox-copy"
+    near_name.mkdir(parents=True)
+    (near_name / "keep.md").write_text("keep", encoding="utf-8")
+
+    result = prune_backups(vault, BackupPolicy(1, True))
+
+    assert not first.exists()
+    assert latest.is_file()
+    assert (near_name / "keep.md").is_file()
+    assert result.scanned == 2
+    assert result.deleted == 1
+    assert result.warnings == ("retained unknown backup item: inbox-copy",)
diff --git a/tests/test_inbox_transaction.py b/tests/test_inbox_transaction.py
new file mode 100644
index 0000000..75188b2
--- /dev/null
+++ b/tests/test_inbox_transaction.py
@@ -0,0 +1,319 @@
+from __future__ import annotations
+
+import json
+import os
+from pathlib import Path
+
+import pytest
+
+from obsidian_kb_skill.scripts.inbox_plan import plan_inbox, sha256_bytes
+from obsidian_kb_skill.scripts.inbox_transaction import (
+    InboxLockBusyError,
+    InboxPreparationError,
+    _release_locks,
+    _write_new_durable,
+    prepare_inbox_operation,
+)
+
+
+class FailAt:
+    def __init__(self, checkpoint: str) -> None:
+        self.checkpoint_name = checkpoint
+        self.seen: list[str] = []
+
+    def checkpoint(self, name: str) -> None:
+        self.seen.append(name)
+        if name == self.checkpoint_name:
+            raise OSError(f"injected:{name}")
+
+
+def make_ready_item(tmp_path: Path):
+    vault = tmp_path / "vault"
+    (vault / ".obsidian").mkdir(parents=True)
+    (vault / "00-Inbox").mkdir()
+    target = vault / "30-Insights"
+    target.mkdir()
+    source = vault / "00-Inbox" / "Insight.md"
+    source_bytes = b"# Insight\nexact source bytes  \n"
+    source.write_bytes(source_bytes)
+    index = target / "INDEX.md"
+    index_bytes = b"\xef\xbb\xbf# Insights\r\n"
+    index.write_bytes(index_bytes)
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+    assert item.status == "ready"
+    assert item.proposal is not None
+    assert item.proposal.index.action == "append"
+    destination = vault / item.proposal.destination
+    return vault, item, source, source_bytes, index, index_bytes, destination
+
+
+def operation_directories(vault: Path) -> list[Path]:
+    namespace = vault / ".obsidian-kb-backups" / "inbox"
+    if not namespace.is_dir():
+        return []
+    return sorted(
+        path for path in namespace.iterdir() if path.name != ".locks"
+    )
+
+
+def assert_business_state_unchanged(
+    source: Path,
+    source_bytes: bytes,
+    index: Path,
+    index_bytes: bytes,
+    destination: Path,
+    outside: Path,
+) -> None:
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+    assert list(outside.iterdir()) == []
+
+
+@pytest.mark.parametrize(
+    "checkpoint",
+    [
+        "lock-source",
+        "lock-index",
+        "backup-root",
+        "backup-source-write",
+        "backup-source-fsync",
+        "backup-index-write",
+        "manifest-write",
+        "manifest-fsync",
+        "journal-backup-ready",
+    ],
+)
+def test_preparation_failure_never_mutates_business_files(
+    tmp_path: Path, checkpoint: str
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    injector = FailAt(checkpoint)
+
+    with pytest.raises(OSError, match=f"injected:{checkpoint}"):
+        prepare_inbox_operation(vault, item, injector=injector)
+
+    assert checkpoint in injector.seen
+    assert_business_state_unchanged(
+        source, source_bytes, index, index_bytes, destination, outside
+    )
+    lock_root = vault / ".obsidian-kb-backups" / "inbox" / ".locks"
+    assert not lock_root.exists() or list(lock_root.iterdir()) == []
+    durable_record = checkpoint in {"manifest-fsync", "journal-backup-ready"}
+    operations = operation_directories(vault)
+    if durable_record:
+        assert len(operations) == 1
+        manifest = operations[0] / "manifest.json"
+        assert manifest.is_file()
+        assert manifest.read_bytes().endswith(b"\n")
+    else:
+        assert operations == []
+
+
+def test_prepare_writes_exact_verified_backups_manifest_and_journal(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+
+    operation = prepare_inbox_operation(vault, item)
+    try:
+        assert operation.vault == vault.resolve()
+        assert operation.item is item
+        assert operation.operation_root == (
+            vault / ".obsidian-kb-backups" / "inbox" / operation.restore_id
+        )
+        assert operation.operation_root.is_dir()
+        assert operation.held_locks
+        assert [path.name for path in operation.held_locks] == sorted(
+            path.name for path in operation.held_locks
+        )
+
+        manifest_bytes = (operation.operation_root / "manifest.json").read_bytes()
+        assert manifest_bytes.endswith(b"\n")
+        manifest = json.loads(manifest_bytes)
+        assert manifest == operation.manifest
+        assert manifest_bytes == (
+            json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
+            + "\n"
+        ).encode("utf-8")
+        assert str(vault.resolve()).encode() not in manifest_bytes
+        assert manifest["restore_id"] == operation.restore_id
+        assert manifest["source"]["path"] == item.source.as_posix()
+        assert manifest["source"]["sha256"] == sha256_bytes(source_bytes)
+        assert manifest["destination"]["path"] == item.proposal.destination.as_posix()
+        assert manifest["destination"]["absent"] is True
+        assert manifest["index"]["path"] == item.proposal.index.index.as_posix()
+        assert manifest["index"]["before_sha256"] == sha256_bytes(index_bytes)
+
+        source_backup = operation.operation_root / manifest["source"]["backup"]
+        index_backup = operation.operation_root / manifest["index"]["backup"]
+        assert source_backup.read_bytes() == source_bytes
+        assert index_backup.read_bytes() == index_bytes
+        assert sha256_bytes(source_backup.read_bytes()) == manifest["source"]["sha256"]
+        assert sha256_bytes(index_backup.read_bytes()) == manifest["index"]["before_sha256"]
+
+        event_bytes = (operation.operation_root / "events.jsonl").read_bytes()
+        assert event_bytes.endswith(b"\n")
+        events = [json.loads(line) for line in event_bytes.splitlines()]
+        assert events[-1]["phase"] == "backup-ready"
+        assert events[-1]["restore_id"] == operation.restore_id
+        assert source.read_bytes() == source_bytes
+        assert index.read_bytes() == index_bytes
+        assert not os.path.lexists(destination)
+    finally:
+        assert _release_locks(operation.held_locks) == ()
+
+
+def test_write_new_durable_is_exclusive_and_fsyncs(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    path = tmp_path / "new.bin"
+    fsynced: list[int] = []
+    original_fsync = os.fsync
+
+    def record_fsync(fd: int) -> None:
+        fsynced.append(fd)
+        original_fsync(fd)
+
+    monkeypatch.setattr(os, "fsync", record_fsync)
+    _write_new_durable(path, b"first")
+
+    assert path.read_bytes() == b"first"
+    assert fsynced
+    with pytest.raises(FileExistsError):
+        _write_new_durable(path, b"second")
+    assert path.read_bytes() == b"first"
+
+
+def test_backup_verification_rejects_symlink_swap(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    outside_copy = outside / "copied-source.md"
+    outside_copy.write_bytes(source_bytes)
+
+    class SwapBackupAtVerification:
+        def checkpoint(self, name: str) -> None:
+            if name != "backup-source-fsync":
+                return
+            operation = operation_directories(vault)[0]
+            backup = operation / "source" / item.source
+            backup.unlink()
+            try:
+                backup.symlink_to(outside_copy)
+            except (OSError, NotImplementedError) as exc:
+                pytest.skip(f"symlinks unavailable: {exc}")
+
+    with pytest.raises(InboxPreparationError, match="backup"):
+        prepare_inbox_operation(
+            vault, item, injector=SwapBackupAtVerification()
+        )
+
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+    assert outside_copy.read_bytes() == source_bytes
+    assert list(outside.iterdir()) == [outside_copy]
+
+
+def test_second_preparation_reports_stable_owner_without_stealing_lock(
+    tmp_path: Path,
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    first = prepare_inbox_operation(vault, item)
+    lock_payloads = {path: path.read_bytes() for path in first.held_locks}
+    try:
+        with pytest.raises(InboxLockBusyError) as first_busy:
+            prepare_inbox_operation(vault, item)
+        with pytest.raises(InboxLockBusyError) as second_busy:
+            prepare_inbox_operation(vault, item)
+
+        assert first_busy.value.code == "inbox-lock-busy"
+        assert first_busy.value.owner_restore_id == first.restore_id
+        assert second_busy.value.owner_restore_id == first.restore_id
+        assert {path: path.read_bytes() for path in first.held_locks} == lock_payloads
+        assert all(path.is_file() for path in first.held_locks)
+    finally:
+        assert _release_locks(first.held_locks) == ()
+
+
+def test_lock_cleanup_retains_replaced_regular_file(tmp_path: Path) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    operation = prepare_inbox_operation(vault, item)
+    replaced = operation.held_locks[0]
+    replaced.unlink()
+    replacement = b"unrelated concurrent file\n"
+    replaced.write_bytes(replacement)
+
+    warnings = _release_locks(operation.held_locks)
+
+    assert replaced.read_bytes() == replacement
+    assert any("unsafe Inbox lock" in warning for warning in warnings)
+
+
+@pytest.mark.parametrize("unsafe_root", ["backup", "locks"])
+def test_symlinked_backup_or_lock_root_fails_closed(
+    tmp_path: Path, unsafe_root: str
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    backup_root = vault / ".obsidian-kb-backups"
+    if unsafe_root == "backup":
+        link = backup_root
+    else:
+        (backup_root / "inbox").mkdir(parents=True)
+        link = backup_root / "inbox" / ".locks"
+    try:
+        link.symlink_to(outside, target_is_directory=True)
+    except (OSError, NotImplementedError) as exc:
+        pytest.skip(f"symlinks unavailable: {exc}")
+
+    with pytest.raises(OSError):
+        prepare_inbox_operation(vault, item)
+
+    assert link.is_symlink()
+    assert_business_state_unchanged(
+        source, source_bytes, index, index_bytes, destination, outside
+    )
+
+
+@pytest.mark.parametrize("unsafe_root", ["backup", "locks"])
+def test_broken_backup_or_lock_root_fails_closed(
+    tmp_path: Path, unsafe_root: str
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    backup_root = vault / ".obsidian-kb-backups"
+    if unsafe_root == "backup":
+        link = backup_root
+    else:
+        (backup_root / "inbox").mkdir(parents=True)
+        link = backup_root / "inbox" / ".locks"
+    try:
+        link.symlink_to(tmp_path / "missing", target_is_directory=True)
+    except (OSError, NotImplementedError) as exc:
+        pytest.skip(f"symlinks unavailable: {exc}")
+
+    with pytest.raises(OSError):
+        prepare_inbox_operation(vault, item)
+
+    assert link.is_symlink()
+    assert_business_state_unchanged(
+        source, source_bytes, index, index_bytes, destination, outside
+    )
