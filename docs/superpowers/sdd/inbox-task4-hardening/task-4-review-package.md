# Review package: 604b64a..1cef079

## Commits
1cef079 fix: harden inbox recovery preparation
6a0ac41 feat: add inbox transaction recovery store

## Files changed
 obsidian_kb_skill/scripts/backup_policy.py     |   5 +
 obsidian_kb_skill/scripts/inbox_transaction.py | 993 +++++++++++++++++++++++++
 tests/test_backup_policy.py                    |  38 +
 tests/test_inbox_transaction.py                | 644 ++++++++++++++++
 4 files changed, 1680 insertions(+)

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
index 0000000..202fa57
--- /dev/null
+++ b/obsidian_kb_skill/scripts/inbox_transaction.py
@@ -0,0 +1,993 @@
+"""Durable recovery-store preparation for one Inbox operation.
+
+This module deliberately stops after the immutable source/index pre-images,
+manifest, and ``backup-ready`` journal event are durable. Task 5 owns all
+business-file mutation.
+
+All recovery-store I/O is directory-fd relative and refuses platforms without
+the required no-follow primitives. Public lock names are released by an atomic
+rename into an inert namespace; the small tombstones are intentionally retained
+because portable POSIX has no unlink-by-fd operation that could delete an inode
+without reopening a pathname race.
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
+    SourceIdentity,
+    sha256_bytes,
+)
+from obsidian_kb_skill.scripts.vault_paths import (
+    VaultPathError,
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
+_RELEASED_LOCK_ROOT = _LOCK_ROOT / ".released"
+_LOCK_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
+_RESTORE_ID_RE = re.compile(
+    r"^\d{4}-\d{2}-\d{2}-\d{6}Z-[0-9a-f]{16}$"
+)
+_Identity = tuple[int, int]
+_HAS_SECURE_PRIMITIVES = (
+    hasattr(os, "O_DIRECTORY")
+    and hasattr(os, "O_NOFOLLOW")
+    and all(
+        function in os.supports_dir_fd
+        for function in (os.open, os.mkdir, os.stat, os.rename, os.link, os.unlink)
+    )
+)
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
+@dataclass
+class _OwnedLock:
+    fd: int
+    identity: _Identity
+    parent_identity: _Identity
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
+_HELD_LOCKS: dict[Path, _OwnedLock] = {}
+_OPERATION_IDENTITIES: dict[Path, _Identity] = {}
+
+
+def _checkpoint(injector: InboxFailureInjector | None, name: str) -> None:
+    if injector is not None:
+        injector.checkpoint(name)
+
+
+def _identity(status: os.stat_result) -> _Identity:
+    return status.st_dev, status.st_ino
+
+
+def _directory_flags() -> int:
+    return (
+        os.O_RDONLY
+        | getattr(os, "O_DIRECTORY", 0)
+        | getattr(os, "O_NOFOLLOW", 0)
+        | getattr(os, "O_CLOEXEC", 0)
+    )
+
+
+def _require_secure_primitives() -> None:
+    if not _HAS_SECURE_PRIMITIVES:
+        raise InboxPreparationError(
+            "unsupported-safe-filesystem",
+            "Inbox recovery requires directory-fd and no-follow filesystem support",
+        )
+
+
+def _fsync_directory(fd: int) -> None:
+    try:
+        os.fsync(fd)
+    except OSError as exc:
+        raise InboxPreparationError(
+            "unsupported-directory-fsync",
+            "Inbox recovery directory entries could not be made durable",
+        ) from exc
+
+
+def _write_all(fd: int, payload: bytes) -> None:
+    view = memoryview(payload)
+    while view:
+        written = os.write(fd, view)
+        if written <= 0:
+            raise OSError("could not write Inbox recovery bytes")
+        view = view[written:]
+
+
+def _write_new_at(
+    parent_fd: int,
+    name: str,
+    payload: bytes,
+    *,
+    created: dict[Path, _Identity] | None = None,
+    relative: Path | None = None,
+) -> _Identity:
+    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
+    flags |= getattr(os, "O_CLOEXEC", 0)
+    flags |= getattr(os, "O_NOFOLLOW", 0)
+    flags |= getattr(os, "O_BINARY", 0)
+    fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
+    identity = _identity(os.fstat(fd))
+    if created is not None and relative is not None:
+        created[relative] = identity
+    try:
+        _write_all(fd, payload)
+        os.fsync(fd)
+        _fsync_directory(parent_fd)
+    except BaseException:
+        os.close(fd)
+        raise
+    os.close(fd)
+    return identity
+
+
+def _write_new_durable(path: Path, payload: bytes) -> None:
+    """Create and fsync a file plus its new directory entry.
+
+    Security-sensitive Vault writes use ``_write_new_at`` after a no-follow
+    component traversal. This path wrapper remains for the documented internal
+    primitive and its standalone contract test.
+    """
+    _require_secure_primitives()
+    parent_fd = os.open(path.parent, _directory_flags())
+    try:
+        _write_new_at(parent_fd, path.name, payload)
+    finally:
+        os.close(parent_fd)
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
+def _open_directory_chain(
+    vault: Path,
+    relative: Path,
+    *,
+    create: bool = False,
+    created: dict[Path, _Identity] | None = None,
+    label: str = "Inbox recovery directory",
+) -> int:
+    _require_secure_primitives()
+    safe = _safe_relative(relative, label=label)
+    fd = os.open(vault, _directory_flags())
+    current = Path()
+    try:
+        for part in safe.parts:
+            current /= part
+            try:
+                child = os.open(part, _directory_flags(), dir_fd=fd)
+            except FileNotFoundError:
+                if not create:
+                    raise InboxPreparationError(
+                        "unsafe-inbox-path", f"{label} does not exist"
+                    ) from None
+                os.mkdir(part, 0o700, dir_fd=fd)
+                _fsync_directory(fd)
+                child = os.open(part, _directory_flags(), dir_fd=fd)
+                if created is not None:
+                    created[current] = _identity(os.fstat(child))
+            except OSError as exc:
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", f"{label} is not a real directory"
+                ) from exc
+            expected = created.get(current) if created is not None else None
+            if expected is not None and _identity(os.fstat(child)) != expected:
+                os.close(child)
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", f"{label} changed after creation"
+                )
+            os.close(fd)
+            fd = child
+        return fd
+    except BaseException:
+        os.close(fd)
+        raise
+
+
+def _ensure_directory_chain(vault: Path, relative: Path) -> Path:
+    fd = _open_directory_chain(vault, relative, create=True)
+    os.close(fd)
+    return vault / relative
+
+
+def _open_relative_directory(
+    base_fd: int,
+    parts: tuple[str, ...],
+    *,
+    operation_relative: Path,
+    created: dict[Path, _Identity],
+) -> int:
+    fd = os.dup(base_fd)
+    current = operation_relative
+    try:
+        for part in parts:
+            current /= part
+            try:
+                child = os.open(part, _directory_flags(), dir_fd=fd)
+            except FileNotFoundError:
+                os.mkdir(part, 0o700, dir_fd=fd)
+                _fsync_directory(fd)
+                child = os.open(part, _directory_flags(), dir_fd=fd)
+                created[current] = _identity(os.fstat(child))
+            except OSError as exc:
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", "Inbox backup ancestor is unsafe"
+                ) from exc
+            expected = created.get(current)
+            if expected is None or _identity(os.fstat(child)) != expected:
+                os.close(child)
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", "Inbox backup ancestor changed"
+                )
+            os.close(fd)
+            fd = child
+        return fd
+    except BaseException:
+        os.close(fd)
+        raise
+
+
+def _create_operation_directory(
+    vault: Path, relative: Path
+) -> tuple[Path, int, _Identity]:
+    parent_fd = _open_directory_chain(
+        vault, relative.parent, create=True, label="Inbox operation parent"
+    )
+    try:
+        os.mkdir(relative.name, 0o700, dir_fd=parent_fd)
+        _fsync_directory(parent_fd)
+        operation_fd = os.open(relative.name, _directory_flags(), dir_fd=parent_fd)
+    except FileExistsError:
+        raise FileExistsError("Inbox restore ID already exists") from None
+    finally:
+        os.close(parent_fd)
+    identity = _identity(os.fstat(operation_fd))
+    path = vault / relative
+    _OPERATION_IDENTITIES[path] = identity
+    return path, operation_fd, identity
+
+
+def _open_bound_operation(vault: Path, operation_root: Path) -> int:
+    expected = _OPERATION_IDENTITIES.get(operation_root)
+    if expected is None:
+        raise InboxPreparationError(
+            "unsafe-operation-root", "Inbox operation identity is unavailable"
+        )
+    relative = operation_root.relative_to(vault)
+    fd = _open_directory_chain(
+        vault, relative, label="Inbox operation directory"
+    )
+    if _identity(os.fstat(fd)) != expected:
+        os.close(fd)
+        raise InboxPreparationError(
+            "unsafe-operation-root", "Inbox operation directory changed"
+        )
+    return fd
+
+
+def _verify_operation_binding(vault: Path, operation_root: Path) -> None:
+    fd = _open_bound_operation(vault, operation_root)
+    os.close(fd)
+
+
+def _read_regular_at(
+    base_fd: int, relative: Path, *, label: str
+) -> tuple[bytes, os.stat_result]:
+    safe = _safe_relative(relative, label=label)
+    fd = os.dup(base_fd)
+    try:
+        for part in safe.parts[:-1]:
+            try:
+                child = os.open(part, _directory_flags(), dir_fd=fd)
+            except OSError as exc:
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", f"{label} ancestor is unsafe"
+                ) from exc
+            os.close(fd)
+            fd = child
+        flags = os.O_RDONLY
+        flags |= getattr(os, "O_CLOEXEC", 0)
+        flags |= getattr(os, "O_NOFOLLOW", 0)
+        flags |= getattr(os, "O_BINARY", 0)
+        try:
+            file_fd = os.open(safe.name, flags, dir_fd=fd)
+        except OSError as exc:
+            raise InboxPreparationError(
+                "unsafe-inbox-path", f"{label} is not a real regular file"
+            ) from exc
+        try:
+            status = os.fstat(file_fd)
+            if not stat.S_ISREG(status.st_mode):
+                raise InboxPreparationError(
+                    "unsafe-inbox-path", f"{label} is not a regular file"
+                )
+            chunks: list[bytes] = []
+            while True:
+                chunk = os.read(file_fd, 1024 * 1024)
+                if not chunk:
+                    break
+                chunks.append(chunk)
+            return b"".join(chunks), status
+        finally:
+            os.close(file_fd)
+    finally:
+        os.close(fd)
+
+
+def _read_regular_file(
+    vault: Path, relative: Path, *, label: str
+) -> tuple[bytes, os.stat_result]:
+    root_fd = os.open(vault, _directory_flags())
+    try:
+        return _read_regular_at(root_fd, relative, label=label)
+    finally:
+        os.close(root_fd)
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
+def _quarantine_unverified_lock(
+    root: Path, parent_fd: int, public_name: str
+) -> None:
+    """Remove an exclusively-created public lock name without deleting bytes.
+
+    This fallback is used only when the creation fd itself could not be
+    ``fstat``-ed. The entry is atomically moved to the inert namespace and is
+    never deleted or restored as an active lock because its identity is
+    intentionally unknown.
+    """
+    released_fd = _open_directory_chain(
+        root, _RELEASED_LOCK_ROOT, label="Inbox released-lock root"
+    )
+    try:
+        os.rename(
+            public_name,
+            f"{secrets.token_hex(16)}.unverified",
+            src_dir_fd=parent_fd,
+            dst_dir_fd=released_fd,
+        )
+        _fsync_directory(parent_fd)
+        _fsync_directory(released_fd)
+    finally:
+        os.close(released_fd)
+
+
+def _acquire_lock(vault: Path, key: str, restore_id: str) -> Path:
+    """Create one hash-keyed durable lock and retain its creation descriptor."""
+    root = validate_vault_root(vault)
+    if not _LOCK_KEY_RE.fullmatch(key):
+        raise InboxPreparationError("unsafe-lock-key", "Inbox lock key is invalid")
+    if not _RESTORE_ID_RE.fullmatch(restore_id):
+        raise InboxPreparationError(
+            "unsafe-restore-id", "Inbox restore ID is invalid"
+        )
+    _ensure_directory_chain(root, _RELEASED_LOCK_ROOT)
+    parent_fd = _open_directory_chain(root, _LOCK_ROOT, label="Inbox lock root")
+    parent_identity = _identity(os.fstat(parent_fd))
+    relative = _LOCK_ROOT / f"{key}.lock"
+    path = root / relative
+    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
+    flags |= getattr(os, "O_CLOEXEC", 0)
+    flags |= getattr(os, "O_NOFOLLOW", 0)
+    flags |= getattr(os, "O_BINARY", 0)
+    created_this_attempt = False
+    fd: int | None = None
+    try:
+        try:
+            fd = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
+        except FileExistsError:
+            owner = _read_lock_owner(root, relative)
+            raise InboxLockBusyError(owner) from None
+        created_this_attempt = True
+        owned = _OwnedLock(fd, _identity(os.fstat(fd)), parent_identity)
+        _HELD_LOCKS[path] = owned
+        _write_all(fd, _json_line({"restore_id": restore_id}))
+        os.fsync(fd)
+        _fsync_directory(parent_fd)
+        return path
+    except BaseException:
+        # The map is populated immediately after exclusive creation, before
+        # any fallible write or durability operation, so this cleanup never
+        # mistakes a pre-existing lock for this attempt's object.
+        if created_this_attempt:
+            if path in _HELD_LOCKS:
+                _release_locks((path,))
+            else:
+                try:
+                    _quarantine_unverified_lock(root, parent_fd, path.name)
+                finally:
+                    if fd is not None:
+                        os.close(fd)
+        raise
+    finally:
+        os.close(parent_fd)
+
+
+def _release_locks(paths: Iterable[Path]) -> tuple[str, ...]:
+    """Atomically remove public lock names without pathname-unlink races.
+
+    Released entries are retained below ``.locks/.released``. If an unknown
+    replacement was moved, it is hard-linked back without overwrite when safe;
+    otherwise both public and quarantined unknown entries are preserved.
+    """
+    warnings: list[str] = []
+    for path in reversed(tuple(paths)):
+        owned = _HELD_LOCKS.pop(path, None)
+        if owned is None:
+            warnings.append(f"retained unsafe Inbox lock: {path.name}")
+            continue
+        lock_fd: int | None = None
+        released_fd: int | None = None
+        try:
+            root = path.parents[len(_LOCK_ROOT.parts)]
+            lock_fd = _open_directory_chain(root, _LOCK_ROOT, label="Inbox lock root")
+            if _identity(os.fstat(lock_fd)) != owned.parent_identity:
+                warnings.append(f"retained unsafe Inbox lock: {path.name}")
+                continue
+            released_fd = _open_directory_chain(
+                root, _RELEASED_LOCK_ROOT, label="Inbox released-lock root"
+            )
+            tombstone = f"{secrets.token_hex(16)}.released"
+            try:
+                os.rename(
+                    path.name,
+                    tombstone,
+                    src_dir_fd=lock_fd,
+                    dst_dir_fd=released_fd,
+                )
+            except FileNotFoundError:
+                warnings.append(f"retained unsafe Inbox lock: {path.name}")
+                continue
+            _fsync_directory(lock_fd)
+            _fsync_directory(released_fd)
+            flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
+            moved_fd = os.open(tombstone, flags, dir_fd=released_fd)
+            try:
+                moved_identity = _identity(os.fstat(moved_fd))
+            finally:
+                os.close(moved_fd)
+            if moved_identity != owned.identity:
+                try:
+                    os.link(
+                        tombstone,
+                        path.name,
+                        src_dir_fd=released_fd,
+                        dst_dir_fd=lock_fd,
+                        follow_symlinks=False,
+                    )
+                    _fsync_directory(lock_fd)
+                except OSError as exc:
+                    warnings.append(
+                        f"retained unsafe Inbox lock {path.name} in released "
+                        f"namespace: {exc}"
+                    )
+                else:
+                    warnings.append(f"retained unsafe Inbox lock: {path.name}")
+        except OSError as exc:
+            warnings.append(f"could not release Inbox lock {path.name}: {exc}")
+        finally:
+            if released_fd is not None:
+                os.close(released_fd)
+            if lock_fd is not None:
+                os.close(lock_fd)
+            os.close(owned.fd)
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
+def _lock_key(relative: Path) -> str:
+    return hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
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
+def _source_identity_matches(status: os.stat_result, expected: SourceIdentity) -> bool:
+    return (
+        status.st_dev == expected.device
+        and status.st_ino == expected.inode
+        and status.st_size == expected.size
+        and status.st_mtime_ns == expected.mtime_ns
+    )
+
+
+def _backup_relative(operation_relative: Path, kind: str, original: Path) -> Path:
+    safe_original = _safe_relative(original, label=f"Inbox {kind} path")
+    return operation_relative / kind / safe_original
+
+
+def _write_backup(
+    vault: Path,
+    operation_root: Path,
+    operation_fd: int,
+    operation_relative: Path,
+    relative: Path,
+    payload: bytes,
+    *,
+    created_files: dict[Path, _Identity],
+    created_directories: dict[Path, _Identity],
+) -> Path:
+    _verify_operation_binding(vault, operation_root)
+    local = relative.relative_to(operation_relative)
+    parent_fd = _open_relative_directory(
+        operation_fd,
+        local.parent.parts,
+        operation_relative=operation_relative,
+        created=created_directories,
+    )
+    try:
+        _write_new_at(
+            parent_fd,
+            local.name,
+            payload,
+            created=created_files,
+            relative=relative,
+        )
+    finally:
+        os.close(parent_fd)
+    return vault / relative
+
+
+def _read_operation_file(
+    vault: Path,
+    operation_root: Path,
+    operation_fd: int,
+    operation_relative: Path,
+    relative: Path,
+    *,
+    label: str,
+) -> tuple[bytes, os.stat_result]:
+    _verify_operation_binding(vault, operation_root)
+    return _read_regular_at(
+        operation_fd, relative.relative_to(operation_relative), label=label
+    )
+
+
+def _remove_owned_file(
+    vault: Path, relative: Path, expected: _Identity, warnings: list[str]
+) -> None:
+    try:
+        parent_fd = _open_directory_chain(
+            vault, relative.parent, label="Inbox cleanup parent"
+        )
+        try:
+            observed = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
+            if not stat.S_ISREG(observed.st_mode) or _identity(observed) != expected:
+                warnings.append(f"retained unsafe recovery debris: {relative.name}")
+                return
+            os.unlink(relative.name, dir_fd=parent_fd)
+            _fsync_directory(parent_fd)
+        finally:
+            os.close(parent_fd)
+    except FileNotFoundError:
+        return
+    except OSError:
+        warnings.append(f"retained recovery debris: {relative.name}")
+
+
+def _remove_owned_directory(
+    vault: Path, relative: Path, expected: _Identity, warnings: list[str]
+) -> None:
+    try:
+        parent_fd = _open_directory_chain(
+            vault, relative.parent, label="Inbox cleanup parent"
+        )
+        try:
+            observed = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
+            if not stat.S_ISDIR(observed.st_mode) or _identity(observed) != expected:
+                warnings.append(f"retained unsafe recovery debris: {relative.name}")
+                return
+            os.rmdir(relative.name, dir_fd=parent_fd)
+            _fsync_directory(parent_fd)
+        finally:
+            os.close(parent_fd)
+    except FileNotFoundError:
+        return
+    except OSError:
+        warnings.append(f"retained recovery debris: {relative.name}")
+
+
+def _cleanup_unpersisted_operation(
+    vault: Path,
+    files: Mapping[Path, _Identity],
+    directories: Mapping[Path, _Identity],
+) -> tuple[str, ...]:
+    warnings: list[str] = []
+    for relative, expected in reversed(tuple(files.items())):
+        _remove_owned_file(vault, relative, expected, warnings)
+    for relative, expected in sorted(
+        directories.items(),
+        key=lambda item: (len(item[0].parts), item[0].as_posix()),
+        reverse=True,
+    ):
+        _remove_owned_directory(vault, relative, expected, warnings)
+        if relative.parent == _INBOX_ROOT:
+            _OPERATION_IDENTITIES.pop(vault / relative, None)
+    return tuple(warnings)
+
+
+def _append_event(
+    operation: PreparedInboxOperation, phase: str, **data: Any
+) -> None:
+    """Append one complete JSONL event through the bound operation directory."""
+    operation_fd = _open_bound_operation(operation.vault, operation.operation_root)
+    try:
+        event: dict[str, Any] = {
+            "phase": phase,
+            "restore_id": operation.restore_id,
+            "timestamp": _utc_timestamp(),
+        }
+        event.update(data)
+        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
+        if phase == "backup-ready":
+            flags |= os.O_EXCL
+        flags |= getattr(os, "O_CLOEXEC", 0)
+        flags |= getattr(os, "O_NOFOLLOW", 0)
+        flags |= getattr(os, "O_BINARY", 0)
+        fd = os.open("events.jsonl", flags, 0o600, dir_fd=operation_fd)
+        try:
+            status = os.fstat(fd)
+            if not stat.S_ISREG(status.st_mode):
+                raise InboxPreparationError(
+                    "unsafe-inbox-journal", "Inbox journal is not a regular file"
+                )
+            _write_all(fd, _json_line(event))
+            os.fsync(fd)
+        finally:
+            os.close(fd)
+        _fsync_directory(operation_fd)
+    finally:
+        os.close(operation_fd)
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
+    _require_secure_primitives()
+    _validate_item(item)
+    assert (
+        item.proposal is not None
+        and item.source_sha256 is not None
+        and item.identity is not None
+    )
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
+    created_files: dict[Path, _Identity] = {}
+    created_directories: dict[Path, _Identity] = {}
+    operation_fd: int | None = None
+    manifest_durable = False
+    try:
+        for key, kind in keyed_resources:
+            _checkpoint(injector, f"lock-{kind}")
+            held_locks.append(_acquire_lock(root, key, restore_id))
+
+        _checkpoint(injector, "backup-root")
+        operation_root, operation_fd, operation_identity = (
+            _create_operation_directory(root, operation_relative)
+        )
+        created_directories[operation_relative] = operation_identity
+
+        source_bytes, source_status = _read_regular_file(
+            root, source_relative, label="Inbox source"
+        )
+        if (
+            not _source_identity_matches(source_status, item.identity)
+            or sha256_bytes(source_bytes) != item.source_sha256
+        ):
+            raise InboxPreparationError(
+                "stale-inbox-source",
+                "Inbox source bytes or identity changed after planning",
+            )
+        source_backup_relative = _backup_relative(
+            operation_relative, "source", source_relative
+        )
+        _checkpoint(injector, "backup-source-write")
+        _write_backup(
+            root,
+            operation_root,
+            operation_fd,
+            operation_relative,
+            source_backup_relative,
+            source_bytes,
+            created_files=created_files,
+            created_directories=created_directories,
+        )
+        _checkpoint(injector, "backup-source-fsync")
+        verified_source, _source_backup_status = _read_operation_file(
+            root,
+            operation_root,
+            operation_fd,
+            operation_relative,
+            source_backup_relative,
+            label="Inbox source backup",
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
+                operation_root,
+                operation_fd,
+                operation_relative,
+                index_backup_relative,
+                index_bytes,
+                created_files=created_files,
+                created_directories=created_directories,
+            )
+            verified_index, _index_backup_status = _read_operation_file(
+                root,
+                operation_root,
+                operation_fd,
+                operation_relative,
+                index_backup_relative,
+                label="Inbox index backup",
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
+        _checkpoint(injector, "manifest-write")
+        _verify_operation_binding(root, operation_root)
+        _write_new_at(
+            operation_fd,
+            "manifest.json",
+            _json_line(manifest),
+            created=created_files,
+            relative=manifest_relative,
+        )
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
+        _verify_operation_binding(root, operation_root)
+        return operation
+    except Exception:
+        if not manifest_durable:
+            _cleanup_unpersisted_operation(
+                root, created_files, created_directories
+            )
+        _release_locks(held_locks)
+        raise
+    finally:
+        if operation_fd is not None:
+            os.close(operation_fd)
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
index 0000000..4051454
--- /dev/null
+++ b/tests/test_inbox_transaction.py
@@ -0,0 +1,644 @@
+from __future__ import annotations
+
+import json
+import os
+import stat
+from dataclasses import replace
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
+        path
+        for path in namespace.iterdir()
+        if path.name not in {".discarded", ".locks"}
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
+    assert not lock_root.exists() or list(lock_root.glob("*.lock")) == []
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
+@pytest.mark.parametrize("field", ["device", "inode", "size", "mtime_ns"])
+def test_preparation_rejects_every_changed_planned_identity_field(
+    tmp_path: Path, field: str
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    assert item.identity is not None
+    changed_identity = replace(
+        item.identity, **{field: getattr(item.identity, field) + 1}
+    )
+
+    with pytest.raises(InboxPreparationError) as caught:
+        prepare_inbox_operation(vault, replace(item, identity=changed_identity))
+
+    assert caught.value.code == "stale-inbox-source"
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+
+
+def test_preparation_rejects_same_byte_replacement_source(tmp_path: Path) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    moved = source.with_suffix(".planned")
+    source.rename(moved)
+    source.write_bytes(source_bytes)
+
+    with pytest.raises(InboxPreparationError) as caught:
+        prepare_inbox_operation(vault, item)
+
+    assert caught.value.code == "stale-inbox-source"
+    assert source.read_bytes() == source_bytes
+    assert moved.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+
+
+def test_operation_root_replacement_never_redirects_recovery_writes(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    redirect = vault / "redirect"
+    redirect.mkdir()
+
+    class ReplaceOperationRoot:
+        def checkpoint(self, name: str) -> None:
+            if name != "backup-source-write":
+                return
+            operation = operation_directories(vault)[0]
+            operation.rmdir()
+            operation.symlink_to(redirect, target_is_directory=True)
+
+    with pytest.raises(InboxPreparationError):
+        prepare_inbox_operation(vault, item, injector=ReplaceOperationRoot())
+
+    assert list(redirect.iterdir()) == []
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+
+
+def test_cleanup_preserves_regular_file_replacing_owned_backup(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    replacement = b"unknown concurrent recovery bytes\n"
+    replaced: list[Path] = []
+
+    class ReplaceBackup:
+        def checkpoint(self, name: str) -> None:
+            if name != "backup-source-fsync":
+                return
+            operation = operation_directories(vault)[0]
+            backup = operation / "source" / item.source
+            backup.unlink()
+            backup.write_bytes(replacement)
+            replaced.append(backup)
+
+    with pytest.raises(InboxPreparationError):
+        prepare_inbox_operation(vault, item, injector=ReplaceBackup())
+
+    assert replaced[0].read_bytes() == replacement
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+
+
+def test_backup_verification_rejects_in_vault_ancestor_symlink_swap(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    redirect = vault / "redirect"
+    redirect.mkdir()
+    redirected_backup = redirect / source.name
+    redirected_backup.write_bytes(source_bytes)
+    original_parent: list[Path] = []
+
+    class SwapBackupParent:
+        def checkpoint(self, name: str) -> None:
+            if name != "backup-source-fsync":
+                return
+            operation = operation_directories(vault)[0]
+            parent = operation / "source" / source.parent.relative_to(vault)
+            saved = parent.with_name(parent.name + "-original")
+            parent.rename(saved)
+            parent.symlink_to(redirect, target_is_directory=True)
+            original_parent.append(saved)
+
+    with pytest.raises(InboxPreparationError):
+        prepare_inbox_operation(vault, item, injector=SwapBackupParent())
+
+    assert redirected_backup.read_bytes() == source_bytes
+    assert (original_parent[0] / source.name).read_bytes() == source_bytes
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
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
+def test_lock_fsync_failure_leaves_no_public_orphan_lock(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    original_fsync = os.fsync
+    failed = False
+
+    def fail_first_regular_file_fsync(fd: int) -> None:
+        nonlocal failed
+        if not failed and stat.S_ISREG(os.fstat(fd).st_mode):
+            failed = True
+            raise OSError("injected lock fsync failure")
+        original_fsync(fd)
+
+    monkeypatch.setattr(os, "fsync", fail_first_regular_file_fsync)
+
+    with pytest.raises(OSError, match="injected lock fsync failure"):
+        prepare_inbox_operation(vault, item)
+
+    assert failed
+    lock_root = vault / ".obsidian-kb-backups" / "inbox" / ".locks"
+    assert not lock_root.exists() or list(lock_root.glob("*.lock")) == []
+
+
+def test_lock_identity_capture_failure_leaves_no_public_orphan_lock(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    original_fstat = os.fstat
+    failed = False
+
+    def fail_first_regular_file_fstat(fd: int) -> os.stat_result:
+        nonlocal failed
+        result = original_fstat(fd)
+        if not failed and stat.S_ISREG(result.st_mode):
+            failed = True
+            raise OSError("injected lock fstat failure")
+        return result
+
+    monkeypatch.setattr(os, "fstat", fail_first_regular_file_fstat)
+
+    with pytest.raises(OSError, match="injected lock fstat failure"):
+        prepare_inbox_operation(vault, item)
+
+    assert failed
+    lock_root = vault / ".obsidian-kb-backups" / "inbox" / ".locks"
+    assert not lock_root.exists() or list(lock_root.glob("*.lock")) == []
+
+
+def test_lock_release_preserves_replacement_created_after_identity_check(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    operation = prepare_inbox_operation(vault, item)
+    lock = operation.held_locks[0]
+    replacement = b"replacement during release\n"
+    original_path_unlink = Path.unlink
+    original_unlink = os.unlink
+    original_rename = os.rename
+    swapped = False
+
+    def swap_public_lock() -> None:
+        nonlocal swapped
+        if swapped:
+            return
+        swapped = True
+        original_unlink(lock)
+        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
+        try:
+            os.write(fd, replacement)
+        finally:
+            os.close(fd)
+
+    def swap_before_path_unlink(path: Path, *args: object, **kwargs: object) -> None:
+        if path == lock:
+            swap_public_lock()
+        original_path_unlink(path, *args, **kwargs)
+
+    def swap_before_atomic_rename(
+        src: object, dst: object, *args: object, **kwargs: object
+    ) -> None:
+        if Path(src).name == lock.name:
+            swap_public_lock()
+        original_rename(src, dst, *args, **kwargs)
+
+    monkeypatch.setattr(Path, "unlink", swap_before_path_unlink)
+    monkeypatch.setattr(os, "rename", swap_before_atomic_rename)
+
+    warnings = _release_locks((lock,))
+
+    assert swapped, warnings
+    assert lock.read_bytes() == replacement
+    assert any("unsafe Inbox lock" in warning for warning in warnings)
+    _release_locks(operation.held_locks[1:])
+
+
+def test_released_lock_tombstone_does_not_block_next_acquisition(
+    tmp_path: Path,
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    first = prepare_inbox_operation(vault, item)
+    assert _release_locks(first.held_locks) == ()
+
+    second = prepare_inbox_operation(vault, item)
+    try:
+        assert second.restore_id != first.restore_id
+        assert all(path.is_file() for path in second.held_locks)
+    finally:
+        assert _release_locks(second.held_locks) == ()
+
+
+def test_directory_entries_are_fsynced_after_each_durable_file(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault, item, *_rest = make_ready_item(tmp_path)
+    fsync_kinds: list[str] = []
+    original_fsync = os.fsync
+
+    def record_fsync(fd: int) -> None:
+        mode = os.fstat(fd).st_mode
+        fsync_kinds.append("directory" if stat.S_ISDIR(mode) else "file")
+        original_fsync(fd)
+
+    monkeypatch.setattr(os, "fsync", record_fsync)
+    operation = prepare_inbox_operation(vault, item)
+    try:
+        file_positions = [
+            index for index, kind in enumerate(fsync_kinds) if kind == "file"
+        ]
+        assert len(file_positions) >= 5
+        assert all(
+            position + 1 < len(fsync_kinds)
+            and fsync_kinds[position + 1] == "directory"
+            for position in file_positions
+        )
+    finally:
+        _release_locks(operation.held_locks)
+
+
+def test_initial_journal_never_appends_to_unknown_existing_file(
+    tmp_path: Path,
+) -> None:
+    vault, item, source, source_bytes, index, index_bytes, destination = (
+        make_ready_item(tmp_path)
+    )
+    unknown = b"unknown journal owner\n"
+    journal: list[Path] = []
+
+    class CreateUnknownJournal:
+        def checkpoint(self, name: str) -> None:
+            if name != "journal-backup-ready":
+                return
+            path = operation_directories(vault)[0] / "events.jsonl"
+            path.write_bytes(unknown)
+            journal.append(path)
+
+    with pytest.raises(FileExistsError):
+        prepare_inbox_operation(vault, item, injector=CreateUnknownJournal())
+
+    assert journal[0].read_bytes() == unknown
+    assert source.read_bytes() == source_bytes
+    assert index.read_bytes() == index_bytes
+    assert not os.path.lexists(destination)
+
+
+def test_shared_index_lock_serializes_different_sources(tmp_path: Path) -> None:
+    vault, first_item, *_rest = make_ready_item(tmp_path)
+    second_source = vault / "00-Inbox" / "Second Insight.md"
+    second_source.write_bytes(b"# Second Insight\nexact bytes\n")
+    plans = plan_inbox(vault, effective_date="2042-03-04").items
+    first_item = next(item for item in plans if item.source.name == "Insight.md")
+    second_item = next(
+        item for item in plans if item.source.name == "Second Insight.md"
+    )
+    assert first_item.proposal is not None and second_item.proposal is not None
+    assert first_item.source != second_item.source
+    assert first_item.proposal.index.index == second_item.proposal.index.index
+
+    first = prepare_inbox_operation(vault, first_item)
+    first_lock_names = {path.name for path in first.held_locks}
+    try:
+        with pytest.raises(InboxLockBusyError) as busy:
+            prepare_inbox_operation(vault, second_item)
+        assert busy.value.owner_restore_id == first.restore_id
+        public_locks = {
+            path.name
+            for path in (
+                vault / ".obsidian-kb-backups" / "inbox" / ".locks"
+            ).glob("*.lock")
+        }
+        assert public_locks == first_lock_names
+    finally:
+        assert _release_locks(first.held_locks) == ()
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
