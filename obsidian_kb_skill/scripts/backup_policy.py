#!/usr/bin/env python3
"""Load global backup retention and prune owned backups safely.

The updater calls this module after a note write has succeeded.  It deliberately
has no CLI: agents never enumerate or delete backup files themselves.
"""
from __future__ import annotations

import errno
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    resolve_existing_within_vault,
    validate_vault_root,
)

SETTINGS_NAME = ".obsidian-kb-settings.json"
BACKUP_ROOT_NAME = ".obsidian-kb-backups"
DEFAULT_KEEP_PER_NOTE = 1
MAX_KEEP_PER_NOTE = 1000
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}(?:-(?:[2-9]|[1-9]\d+))?$")


@dataclass(frozen=True)
class BackupPolicy:
    keep_per_note: int
    prune_enabled: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CleanupResult:
    keep_per_note: int
    scanned: int
    deleted: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Candidate:
    path: Path
    relative_note: Path
    stamp: str
    mtime_ns: int


def load_backup_policy(home: Path | None = None) -> BackupPolicy:
    """Read the global policy, disabling deletion on every invalid input."""
    settings = (home or Path.home()) / SETTINGS_NAME
    if not os.path.lexists(settings):
        return BackupPolicy(DEFAULT_KEEP_PER_NOTE, True)
    try:
        payload = json.loads(settings.read_text(encoding="utf-8"))
        schema = payload["schema_version"]
        value = payload["backup"]["keep_per_note"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return BackupPolicy(
            DEFAULT_KEEP_PER_NOTE,
            False,
            (f"invalid settings; backup deletion disabled: {exc}",),
        )
    valid = (
        isinstance(schema, int)
        and not isinstance(schema, bool)
        and schema == 1
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_KEEP_PER_NOTE
    )
    if not valid:
        return BackupPolicy(
            DEFAULT_KEEP_PER_NOTE,
            False,
            ("invalid backup retention settings; backup deletion disabled",),
        )
    return BackupPolicy(value, True)


def _walk_regular_files(
    directory: Path,
    *,
    directories: list[Path],
    warnings: list[str],
) -> Iterator[Path]:
    """Yield regular files beneath a real directory without following links."""
    try:
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
    except OSError as exc:
        warnings.append(f"cannot scan backup directory {directory.name}: {exc}")
        return
    for entry in entries:
        path = Path(entry.path)
        try:
            if entry.is_symlink():
                warnings.append(f"retained backup symlink: {path.name}")
            elif entry.is_dir(follow_symlinks=False):
                directories.append(path)
                yield from _walk_regular_files(
                    path,
                    directories=directories,
                    warnings=warnings,
                )
            elif entry.is_file(follow_symlinks=False):
                yield path
            else:
                warnings.append(f"retained non-regular backup item: {path.name}")
        except OSError as exc:
            warnings.append(f"cannot inspect backup item {path.name}: {exc}")


def _protected_path(vault: Path, protected: Path | None) -> Path | None:
    if protected is None or not os.path.lexists(protected) or protected.is_symlink():
        return None
    try:
        resolved = resolve_existing_within_vault(vault, protected, label="backup")
    except (OSError, VaultPathError):
        return None
    return resolved if resolved.is_file() else None


def _remove_empty_directories(directories: list[Path], warnings: list[str]) -> None:
    for directory in sorted(
        set(directories),
        key=lambda path: (len(path.parts), path.as_posix()),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError as exc:
            if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOENT):
                warnings.append(
                    f"cannot remove empty backup directory {directory.name}: {exc}"
                )


def prune_backups(
    vault: Path,
    policy: BackupPolicy,
    protected: Path | None = None,
) -> CleanupResult:
    """Apply per-note retention inside the verified backup tree.

    Invalid policy input is fail-closed: no directory scan and no deletion.
    Skipped or failed filesystem operations become warnings, never exceptions
    that could make an agent retry a note write that already committed.
    """
    warnings = list(policy.warnings)
    if not policy.prune_enabled:
        return CleanupResult(policy.keep_per_note, 0, 0, tuple(warnings))

    root = validate_vault_root(vault)
    backup_root = root / BACKUP_ROOT_NAME
    if not os.path.lexists(backup_root):
        return CleanupResult(policy.keep_per_note, 0, 0, tuple(warnings))
    if backup_root.is_symlink() or not backup_root.is_dir():
        warnings.append("backup root is not a real directory; backup deletion disabled")
        return CleanupResult(policy.keep_per_note, 0, 0, tuple(warnings))

    candidates: list[_Candidate] = []
    directories: list[Path] = []
    try:
        with os.scandir(backup_root) as iterator:
            top_entries = sorted(iterator, key=lambda entry: entry.name)
    except OSError as exc:
        warnings.append(f"cannot scan backup root: {exc}")
        return CleanupResult(policy.keep_per_note, 0, 0, tuple(warnings))

    for entry in top_entries:
        # Inbox transactions own a durable recovery namespace, not ordinary
        # timestamped note history. Retention must neither inspect nor warn for
        # this exact top-level name.
        if entry.name == "inbox":
            continue
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
            continue

        directories.append(stamp_path)
        for path in _walk_regular_files(
            stamp_path,
            directories=directories,
            warnings=warnings,
        ):
            try:
                resolved = resolve_existing_within_vault(root, path, label="backup")
                relative_note = path.relative_to(stamp_path)
                stat = resolved.stat()
            except (OSError, ValueError, VaultPathError) as exc:
                warnings.append(f"retained unverifiable backup file {path.name}: {exc}")
                continue
            if not resolved.is_file() or resolved.is_symlink():
                warnings.append(f"retained non-regular backup file: {path.name}")
                continue
            candidates.append(
                _Candidate(resolved, relative_note, entry.name, stat.st_mtime_ns)
            )

    protected_resolved = _protected_path(root, protected)
    if protected is not None and (
        protected_resolved is None
        or all(candidate.path != protected_resolved for candidate in candidates)
    ):
        warnings.append(
            "protected backup could not be verified in the backup scan; "
            "backup deletion disabled"
        )
        return CleanupResult(
            policy.keep_per_note,
            len(candidates),
            0,
            tuple(warnings),
        )

    groups: dict[Path, list[_Candidate]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.relative_note].append(candidate)

    deleted = 0
    for group in groups.values():
        ordered = sorted(
            group,
            key=lambda item: (
                item.path == protected_resolved,
                item.mtime_ns,
                item.stamp,
                item.path.as_posix(),
            ),
            reverse=True,
        )
        for candidate in ordered[policy.keep_per_note :]:
            try:
                candidate.path.unlink()
            except OSError as exc:
                warnings.append(
                    f"cannot delete old backup {candidate.path.name}: {exc}"
                )
            else:
                deleted += 1

    _remove_empty_directories(directories, warnings)
    return CleanupResult(
        policy.keep_per_note,
        len(candidates),
        deleted,
        tuple(warnings),
    )
