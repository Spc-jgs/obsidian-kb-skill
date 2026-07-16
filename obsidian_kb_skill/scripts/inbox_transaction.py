"""Durable recovery-store preparation for one Inbox operation.

This module deliberately stops after the immutable source/index pre-images,
manifest, and ``backup-ready`` journal event are durable.  Task 5 owns all
business-file mutation.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Protocol

from obsidian_kb_skill.scripts.inbox_plan import (
    InboxIssue,
    InboxPlanItem,
    sha256_bytes,
)
from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]

_BACKUP_ROOT = Path(".obsidian-kb-backups")
_INBOX_ROOT = _BACKUP_ROOT / "inbox"
_LOCK_ROOT = _INBOX_ROOT / ".locks"
_LOCK_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_RESTORE_ID_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{6}Z-[0-9a-f]{16}$"
)
_HELD_LOCK_IDENTITIES: dict[Path, tuple[int, int]] = {}


class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...


@dataclass(frozen=True)
class InboxApplyResult:
    source: Path
    destination: Path | None
    status: ApplyStatus
    applied: bool
    restore_id: str | None
    backup: Path | None
    issue: InboxIssue | None
    warnings: tuple[str, ...] = ()
    rollback_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedInboxOperation:
    vault: Path
    item: InboxPlanItem
    restore_id: str
    operation_root: Path
    manifest: Mapping[str, Any]
    held_locks: tuple[Path, ...]


class InboxPreparationError(OSError):
    """Stable fail-closed preparation error for Task 5 result mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class InboxLockBusyError(InboxPreparationError):
    """A resource lock is already owned by another recovery record."""

    def __init__(self, owner_restore_id: str) -> None:
        self.owner_restore_id = owner_restore_id
        super().__init__(
            "inbox-lock-busy",
            f"Inbox resource is locked by restore ID {owner_restore_id}",
        )


def _checkpoint(injector: InboxFailureInjector | None, name: str) -> None:
    if injector is not None:
        injector.checkpoint(name)


def _write_new_durable(path: Path, payload: bytes) -> None:
    """Create one new file exclusively, flush it, and fsync its exact bytes."""
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _json_line(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _append_event(
    operation: PreparedInboxOperation, phase: str, **data: Any
) -> None:
    """Append one complete, flushed, fsynced JSON Lines journal event."""
    relative = operation.operation_root.relative_to(operation.vault) / "events.jsonl"
    path = _resolved_target(operation.vault, relative, label="Inbox journal")
    lexical = operation.vault / relative
    if os.path.lexists(lexical) and (
        lexical.is_symlink() or not lexical.is_file() or path != lexical
    ):
        raise InboxPreparationError(
            "unsafe-inbox-journal", "Inbox journal is not a real contained file"
        )
    event: dict[str, Any] = {
        "phase": phase,
        "restore_id": operation.restore_id,
        "timestamp": _utc_timestamp(),
    }
    event.update(data)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        payload = _json_line(event)
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("could not append Inbox journal event")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _acquire_lock(vault: Path, key: str, restore_id: str) -> Path:
    """Create one hash-keyed, durable owner lock without stealing an old lock."""
    root = validate_vault_root(vault)
    if not _LOCK_KEY_RE.fullmatch(key):
        raise InboxPreparationError("unsafe-lock-key", "Inbox lock key is invalid")
    if not _RESTORE_ID_RE.fullmatch(restore_id):
        raise InboxPreparationError(
            "unsafe-restore-id", "Inbox restore ID is invalid"
        )
    _ensure_directory_chain(root, _LOCK_ROOT)
    relative = _LOCK_ROOT / f"{key}.lock"
    path = _resolved_target(root, relative, label="Inbox lock")
    try:
        _write_new_durable(path, _json_line({"restore_id": restore_id}))
    except FileExistsError:
        owner = _read_lock_owner(root, relative)
        raise InboxLockBusyError(owner) from None
    status = path.lstat()
    _HELD_LOCK_IDENTITIES[path] = (status.st_dev, status.st_ino)
    return path


def _release_locks(paths: Iterable[Path]) -> tuple[str, ...]:
    """Release only real lock files; retain unsafe replacements with warnings."""
    warnings: list[str] = []
    for path in reversed(tuple(paths)):
        expected = _HELD_LOCK_IDENTITIES.get(path)
        try:
            status = path.lstat()
            observed = (status.st_dev, status.st_ino)
            if (
                expected is None
                or observed != expected
                or not stat.S_ISREG(status.st_mode)
            ):
                warnings.append(f"retained unsafe Inbox lock: {path.name}")
                _HELD_LOCK_IDENTITIES.pop(path, None)
                continue
            path.unlink()
            _HELD_LOCK_IDENTITIES.pop(path, None)
        except FileNotFoundError:
            _HELD_LOCK_IDENTITIES.pop(path, None)
            continue
        except OSError as exc:
            warnings.append(f"could not release Inbox lock {path.name}: {exc}")
    return tuple(warnings)


def _utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d-%H%M%SZ"
    )


def _new_restore_id() -> str:
    return f"{_utc_timestamp()}-{secrets.token_hex(8)}"


def _safe_relative(path: Path, *, label: str) -> Path:
    relative = Path(path)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        raise InboxPreparationError(
            "unsafe-inbox-path", f"{label} is not a safe Vault-relative path"
        )
    return relative


def _resolved_target(vault: Path, relative: Path, *, label: str) -> Path:
    safe = _safe_relative(relative, label=label)
    try:
        return resolve_target_within_vault(vault, safe, label=label)
    except (OSError, VaultPathError) as exc:
        raise InboxPreparationError(
            "unsafe-inbox-path", f"{label} could not be resolved safely"
        ) from exc


def _ensure_real_directory(vault: Path, relative: Path) -> Path:
    target = _resolved_target(vault, relative, label="Inbox recovery directory")
    lexical = vault / relative
    if os.path.lexists(lexical):
        if lexical.is_symlink() or not lexical.is_dir() or target != lexical:
            raise InboxPreparationError(
                "unsafe-recovery-root",
                "Inbox recovery directory is not a real contained directory",
            )
        return target
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError:
        target = _resolved_target(
            vault, relative, label="Inbox recovery directory"
        )
        if lexical.is_symlink() or not lexical.is_dir() or target != lexical:
            raise InboxPreparationError(
                "unsafe-recovery-root",
                "Inbox recovery directory changed during creation",
            ) from None
    return target


def _ensure_directory_chain(vault: Path, relative: Path) -> Path:
    safe = _safe_relative(relative, label="Inbox recovery directory")
    current = Path()
    result = vault
    for part in safe.parts:
        current /= part
        result = _ensure_real_directory(vault, current)
    return result


def _create_operation_directory(vault: Path, relative: Path) -> Path:
    parent = _ensure_directory_chain(vault, relative.parent)
    target = _resolved_target(vault, relative, label="Inbox operation directory")
    lexical = vault / relative
    if os.path.lexists(lexical):
        raise FileExistsError("Inbox restore ID already exists")
    if target.parent != parent:
        raise InboxPreparationError(
            "unsafe-operation-root", "Inbox operation parent changed"
        )
    target.mkdir(exist_ok=False)
    return target


def _read_lock_owner(vault: Path, relative: Path) -> str:
    try:
        raw, _status = _read_regular_file(vault, relative, label="Inbox lock")
        payload = json.loads(raw.decode("utf-8"))
        owner = payload.get("restore_id")
        if isinstance(owner, str) and _RESTORE_ID_RE.fullmatch(owner):
            return owner
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return "unknown"


def _lock_key(relative: Path) -> str:
    return hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()


def _read_regular_file(
    vault: Path, relative: Path, *, label: str
) -> tuple[bytes, os.stat_result]:
    safe = _safe_relative(relative, label=label)
    try:
        path = resolve_existing_within_vault(vault, safe, label=label)
    except (OSError, VaultPathError) as exc:
        raise InboxPreparationError(
            "unsafe-inbox-path", f"{label} could not be resolved safely"
        ) from exc
    lexical = vault / safe
    if lexical.is_symlink() or not path.is_file():
        raise InboxPreparationError(
            "unsafe-inbox-path", f"{label} is not a real regular file"
        )
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode):
            raise InboxPreparationError(
                "unsafe-inbox-path", f"{label} is not a regular file"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), status
    finally:
        os.close(fd)


def _metadata(status: os.stat_result) -> dict[str, int]:
    return {
        "atime_ns": status.st_atime_ns,
        "mode": stat.S_IMODE(status.st_mode),
        "mtime_ns": status.st_mtime_ns,
        "size": status.st_size,
    }


def _backup_relative(operation_relative: Path, kind: str, original: Path) -> Path:
    safe_original = _safe_relative(original, label=f"Inbox {kind} path")
    return operation_relative / kind / safe_original


def _write_backup(
    vault: Path,
    relative: Path,
    payload: bytes,
    *,
    created_files: list[Path],
    created_directories: list[Path],
) -> Path:
    operation_relative = _INBOX_ROOT / relative.parts[len(_INBOX_ROOT.parts)]
    current = operation_relative
    for part in relative.parts[len(operation_relative.parts) : -1]:
        current /= part
        _ensure_real_directory(vault, current)
        created_directories.append(current)
    path = _resolved_target(vault, relative, label="Inbox backup")
    created_files.append(relative)
    _write_new_durable(path, payload)
    return path


def _cleanup_unpersisted_operation(
    vault: Path,
    files: Iterable[Path],
    directories: Iterable[Path],
) -> tuple[str, ...]:
    warnings: list[str] = []
    for relative in reversed(tuple(files)):
        lexical = vault / relative
        try:
            path = _resolved_target(vault, relative, label="Inbox cleanup file")
            if not os.path.lexists(lexical):
                continue
            if lexical.is_symlink() or not lexical.is_file() or path != lexical:
                warnings.append(f"retained unsafe recovery debris: {relative.name}")
                continue
            lexical.unlink()
        except OSError:
            warnings.append(f"retained recovery debris: {relative.name}")
    for relative in sorted(
        set(directories),
        key=lambda item: (len(item.parts), item.as_posix()),
        reverse=True,
    ):
        lexical = vault / relative
        try:
            path = _resolved_target(vault, relative, label="Inbox cleanup directory")
            if not os.path.lexists(lexical):
                continue
            if lexical.is_symlink() or not lexical.is_dir() or path != lexical:
                warnings.append(f"retained unsafe recovery debris: {relative.name}")
                continue
            lexical.rmdir()
        except OSError:
            warnings.append(f"retained recovery debris: {relative.name}")
    return tuple(warnings)


def _validate_item(item: InboxPlanItem) -> None:
    if (
        item.status != "ready"
        or item.proposal is None
        or item.source_sha256 is None
        or item.identity is None
    ):
        raise InboxPreparationError(
            "inbox-item-not-ready", "Inbox item is not ready for preparation"
        )


def prepare_inbox_operation(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> PreparedInboxOperation:
    """Persist verified pre-images and ``backup-ready`` while changing no note."""
    root = validate_vault_root(vault)
    _validate_item(item)
    assert item.proposal is not None and item.source_sha256 is not None
    proposal = item.proposal
    source_relative = _safe_relative(item.source, label="Inbox source")
    destination_relative = _safe_relative(
        proposal.destination, label="Inbox destination"
    )
    destination = _resolved_target(
        root, destination_relative, label="Inbox destination"
    )
    if os.path.lexists(root / destination_relative) or os.path.lexists(destination):
        raise InboxPreparationError(
            "destination-exists", "Inbox destination already exists"
        )

    index_plan = proposal.index
    index_relative = (
        _safe_relative(index_plan.index, label="Inbox index")
        if index_plan.action == "append" and index_plan.index is not None
        else None
    )
    resources = [("source", source_relative)]
    if index_relative is not None:
        resources.append(("index", index_relative))
    keyed_resources = sorted(
        ((_lock_key(relative), kind) for kind, relative in resources),
        key=lambda value: value[0],
    )

    restore_id = _new_restore_id()
    held_locks: list[Path] = []
    operation_relative = _INBOX_ROOT / restore_id
    created_files: list[Path] = []
    created_directories: list[Path] = []
    manifest_durable = False
    try:
        for key, kind in keyed_resources:
            _checkpoint(injector, f"lock-{kind}")
            held_locks.append(_acquire_lock(root, key, restore_id))

        _checkpoint(injector, "backup-root")
        operation_root = _create_operation_directory(root, operation_relative)
        created_directories.append(operation_relative)

        source_bytes, source_status = _read_regular_file(
            root, source_relative, label="Inbox source"
        )
        if sha256_bytes(source_bytes) != item.source_sha256:
            raise InboxPreparationError(
                "stale-inbox-source", "Inbox source bytes changed after planning"
            )
        source_backup_relative = _backup_relative(
            operation_relative, "source", source_relative
        )
        _checkpoint(injector, "backup-source-write")
        _write_backup(
            root,
            source_backup_relative,
            source_bytes,
            created_files=created_files,
            created_directories=created_directories,
        )
        _checkpoint(injector, "backup-source-fsync")
        verified_source, _source_backup_status = _read_regular_file(
            root, source_backup_relative, label="Inbox source backup"
        )
        if (
            verified_source != source_bytes
            or sha256_bytes(verified_source) != item.source_sha256
        ):
            raise InboxPreparationError(
                "invalid-source-backup", "Inbox source backup verification failed"
            )

        index_manifest: dict[str, Any] | None = None
        if index_relative is not None:
            if (
                index_plan.before is None
                or index_plan.before_sha256 is None
                or index_plan.after_sha256 is None
            ):
                raise InboxPreparationError(
                    "invalid-index-plan", "Inbox index plan is incomplete"
                )
            index_bytes, index_status = _read_regular_file(
                root, index_relative, label="Inbox index"
            )
            if (
                index_bytes != index_plan.before
                or sha256_bytes(index_bytes) != index_plan.before_sha256
            ):
                raise InboxPreparationError(
                    "stale-inbox-index", "Inbox index bytes changed after planning"
                )
            index_backup_relative = _backup_relative(
                operation_relative, "index", index_relative
            )
            _checkpoint(injector, "backup-index-write")
            _write_backup(
                root,
                index_backup_relative,
                index_bytes,
                created_files=created_files,
                created_directories=created_directories,
            )
            verified_index, _index_backup_status = _read_regular_file(
                root, index_backup_relative, label="Inbox index backup"
            )
            if (
                verified_index != index_bytes
                or sha256_bytes(verified_index) != index_plan.before_sha256
            ):
                raise InboxPreparationError(
                    "invalid-index-backup", "Inbox index backup verification failed"
                )
            index_manifest = {
                "action": index_plan.action,
                "after_sha256": index_plan.after_sha256,
                "backup": index_backup_relative.relative_to(
                    operation_relative
                ).as_posix(),
                "before_sha256": index_plan.before_sha256,
                "metadata": _metadata(index_status),
                "path": index_relative.as_posix(),
            }

        manifest: dict[str, Any] = {
            "destination": {
                "absent": True,
                "path": destination_relative.as_posix(),
                "rendered_sha256": proposal.rendered_sha256,
            },
            "index": index_manifest,
            "restore_id": restore_id,
            "schema_version": 1,
            "source": {
                "backup": source_backup_relative.relative_to(
                    operation_relative
                ).as_posix(),
                "metadata": _metadata(source_status),
                "path": source_relative.as_posix(),
                "sha256": item.source_sha256,
            },
        }
        manifest_relative = operation_relative / "manifest.json"
        manifest_path = _resolved_target(
            root, manifest_relative, label="Inbox manifest"
        )
        _checkpoint(injector, "manifest-write")
        created_files.append(manifest_relative)
        _write_new_durable(manifest_path, _json_line(manifest))
        manifest_durable = True
        _checkpoint(injector, "manifest-fsync")

        operation = PreparedInboxOperation(
            vault=root,
            item=item,
            restore_id=restore_id,
            operation_root=operation_root,
            manifest=manifest,
            held_locks=tuple(held_locks),
        )
        _checkpoint(injector, "journal-backup-ready")
        _append_event(operation, "backup-ready")
        return operation
    except Exception:
        if not manifest_durable:
            _cleanup_unpersisted_operation(
                root, created_files, created_directories
            )
        _release_locks(held_locks)
        raise
