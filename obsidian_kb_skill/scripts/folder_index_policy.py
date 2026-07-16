#!/usr/bin/env python3
"""Folder Index ownership and static ``INDEX.md`` append policy."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from obsidian_kb_skill.scripts.vault_paths import (
    resolve_target_within_vault,
    validate_vault_root,
)


INVALID_FILENAME_CHARS = frozenset('/\\:*?"<>|')
WINDOWS_RESERVED_FILENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


class FolderIndexConfigError(ValueError):
    """A stable validation failure for a Folder Index filename setting."""

    code = "invalid-folder-index-config"

    def __init__(self, field: str) -> None:
        self.field = field
        self.message = f"{field} must be a portable visible basename"
        super().__init__(self.message)


class _StrictFolderIndexConfigError(ValueError):
    """Configuration uncertainty that legacy readers intentionally default."""


@dataclass(frozen=True)
class FolderIndexConfig:
    enabled: bool = False
    graph_overwrite: bool = False
    root_index_file: str = "INDEX.md"
    user_specified: bool = False
    index_filename: str = "INDEX"
    exclude_folders: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class StaticIndexEntry:
    note: Path
    title: str
    date: str


StaticIndexAction = Literal["append", "unchanged", "missing", "unmanaged"]


@dataclass(frozen=True)
class StaticIndexPlan:
    action: StaticIndexAction
    index: Path | None
    before: bytes | None
    after: bytes | None
    before_sha256: str | None
    after_sha256: str | None
    line: str | None


@dataclass(frozen=True)
class StaticIndexResult:
    status: str
    index: Path | None


IGNORED_PARTS = {
    ".git",
    ".obsidian",
    ".obsidian-kb-backups",
    ".venv",
    ".workbuddy",
}


def _is_ignored(relative: Path) -> bool:
    if any(part in IGNORED_PARTS for part in relative.parts):
        return True
    if any(part.startswith(".") for part in relative.parts):
        return True
    return relative.parts[:2] == ("docs", "superpowers")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def read_folder_index_config(vault: Path) -> FolderIndexConfig:
    obsidian = vault / ".obsidian"
    enabled = _read_json(obsidian / "community-plugins.json", [])
    if not isinstance(enabled, list) or "obsidian-folder-index" not in enabled:
        return FolderIndexConfig()
    settings = _read_json(
        obsidian / "plugins" / "obsidian-folder-index" / "data.json", {}
    )
    if not isinstance(settings, dict):
        settings = {}
    return FolderIndexConfig(
        enabled=True,
        graph_overwrite=bool(settings.get("graphOverwrite", False)),
        root_index_file=str(settings.get("rootIndexFile", "INDEX.md")),
        user_specified=bool(settings.get("indexFileUserSpecified", False)),
        index_filename=str(settings.get("indexFilename", "INDEX")),
        exclude_folders=tuple(
            str(item).strip("/")
            for item in settings.get("excludeFolders", [])
            if str(item)
        ),
        exclude_patterns=tuple(
            str(item) for item in settings.get("excludePatterns", []) if str(item)
        ),
    )


def _read_strict_json(path: Path, default: Any, *, label: str) -> Any:
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return default
    except OSError as exc:
        raise _StrictFolderIndexConfigError(
            f"{label} could not be read safely"
        ) from exc
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _StrictFolderIndexConfigError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc


def _strict_folder_index_config(vault: Path) -> FolderIndexConfig:
    """Read ownership configuration without converting uncertainty to defaults."""
    community_path = resolve_target_within_vault(
        vault,
        Path(".obsidian/community-plugins.json"),
        label="enabled plugin configuration",
    )
    enabled = _read_strict_json(
        community_path, [], label="enabled plugin configuration"
    )
    if not isinstance(enabled, list) or not all(
        isinstance(item, str) for item in enabled
    ):
        raise _StrictFolderIndexConfigError(
            "enabled plugin configuration must be a JSON list of names"
        )
    if "obsidian-folder-index" not in enabled:
        return FolderIndexConfig()

    settings_path = resolve_target_within_vault(
        vault,
        Path(".obsidian/plugins/obsidian-folder-index/data.json"),
        label="Folder Index configuration",
    )
    settings = _read_strict_json(
        settings_path, {}, label="Folder Index configuration"
    )
    if not isinstance(settings, dict):
        raise _StrictFolderIndexConfigError(
            "Folder Index configuration must be a JSON object"
        )
    for field in ("rootIndexFile", "indexFilename"):
        if field in settings and not isinstance(settings[field], str):
            raise _StrictFolderIndexConfigError(
                f"Folder Index configuration {field} must be text"
            )
    for field in ("graphOverwrite", "indexFileUserSpecified"):
        if field in settings and not isinstance(settings[field], bool):
            raise _StrictFolderIndexConfigError(
                f"Folder Index configuration {field} must be boolean"
            )
    for field in ("excludeFolders", "excludePatterns"):
        if field in settings and not (
            isinstance(settings[field], list)
            and all(isinstance(item, str) for item in settings[field])
        ):
            raise _StrictFolderIndexConfigError(
                f"Folder Index configuration {field} must be text list"
            )

    config = FolderIndexConfig(
        enabled=True,
        graph_overwrite=settings.get("graphOverwrite", False),
        root_index_file=settings.get("rootIndexFile", "INDEX.md"),
        user_specified=settings.get("indexFileUserSpecified", False),
        index_filename=settings.get("indexFilename", "INDEX"),
        exclude_folders=tuple(
            item.strip("/") for item in settings.get("excludeFolders", []) if item
        ),
        exclude_patterns=tuple(
            item for item in settings.get("excludePatterns", []) if item
        ),
    )
    _validate_index_basename(config.root_index_file, field="root_index_file")
    if config.user_specified:
        _validate_index_basename(config.index_filename, field="index_filename")
    return config


def is_folder_index_excluded(relative: Path, config: FolderIndexConfig) -> bool:
    if _is_ignored(relative):
        return True
    value = relative.as_posix()
    for excluded in config.exclude_folders:
        if value == excluded or value.startswith(f"{excluded}/"):
            return True
    return any(
        fnmatch.fnmatch(value, pattern) or fnmatch.fnmatch(relative.name, pattern)
        for pattern in config.exclude_patterns
    )


def _validate_index_basename(value: str, *, field: str) -> str:
    windows_stem = value.split(".", 1)[0].upper()
    if (
        not value
        or value != value.strip()
        or value in {".", ".."}
        or value.startswith(".")
        or value.endswith(".")
        or windows_stem in WINDOWS_RESERVED_FILENAMES
        or len(value.encode("utf-8")) > 255
        or any(
            ord(character) < 32 or character in INVALID_FILENAME_CHARS
            for character in value
        )
    ):
        raise FolderIndexConfigError(field)
    return value


def expected_folder_index(
    folder: Path, vault: Path, config: FolderIndexConfig
) -> Path:
    root = validate_vault_root(vault)
    target_folder = resolve_target_within_vault(root, folder, label="folder")
    if target_folder == root:
        name = _validate_index_basename(
            config.root_index_file, field="root_index_file"
        )
        return resolve_target_within_vault(root, root / name, label="root index")
    if config.user_specified:
        basename = _validate_index_basename(
            config.index_filename, field="index_filename"
        )
        name = f"{basename}.md"
    else:
        name = f"{target_folder.name}.md"
    return resolve_target_within_vault(
        root, target_folder / name, label="folder index"
    )


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _logical_note_path(vault: Path, root: Path, entry: StaticIndexEntry) -> Path:
    physical_note = resolve_target_within_vault(root, entry.note, label="note")
    logical_note = entry.note.expanduser()
    if logical_note.is_absolute():
        lexical_root = Path(vault).expanduser().absolute()
        try:
            logical_note = logical_note.relative_to(lexical_root)
        except ValueError:
            try:
                logical_note = logical_note.relative_to(root)
            except ValueError:
                logical_note = physical_note.relative_to(root)
    return logical_note


def _static_index_newline(before: bytes) -> bytes:
    newline_at = before.find(b"\n")
    if newline_at > 0 and before[newline_at - 1:newline_at] == b"\r":
        return b"\r\n"
    return b"\n"


def _unmanaged_plan(index: Path, before: bytes) -> StaticIndexPlan:
    digest = _sha256_bytes(before)
    return StaticIndexPlan(
        action="unmanaged",
        index=index,
        before=before,
        after=before,
        before_sha256=digest,
        after_sha256=digest,
        line=None,
    )


def _plan_static_index_entry_with_config(
    vault: Path,
    root: Path,
    entry: StaticIndexEntry,
    config: FolderIndexConfig,
) -> StaticIndexPlan:
    logical_note = _logical_note_path(vault, root, entry)
    if "\r" in entry.title or "\n" in entry.title:
        raise ValueError("static index title must not contain a line break")
    link = logical_note.with_suffix("").as_posix()
    if "\r" in link or "\n" in link or "\r" in entry.date or "\n" in entry.date:
        raise ValueError("static index entry must fit on one line")
    target = resolve_target_within_vault(
        root, logical_note.parent, label="target folder"
    )
    target_relative = target.relative_to(root)
    index = resolve_target_within_vault(
        root, target_relative / "INDEX.md", label="static index"
    )

    if config.enabled and not is_folder_index_excluded(
        logical_note.parent, config
    ):
        if index.is_file():
            before = index.read_bytes()
            return _unmanaged_plan(index.relative_to(root), before)
        return StaticIndexPlan("unmanaged", None, None, None, None, None, None)
    if not index.is_file():
        if os.path.lexists(index):
            raise ValueError("static index is not a regular file")
        return StaticIndexPlan("missing", None, None, None, None, None, None)

    before = index.read_bytes()
    relative_index = index.relative_to(root)
    if b"folder-index-content" in before or b"dataview" in before:
        return _unmanaged_plan(relative_index, before)

    newline = _static_index_newline(before)
    line_bytes = (
        f"- [[{link}|{entry.title}]] ({entry.date})".encode("utf-8") + newline
    )
    line = line_bytes.decode("utf-8")
    bare_line = line_bytes.removesuffix(newline)
    if bare_line in before.splitlines():
        digest = _sha256_bytes(before)
        return StaticIndexPlan(
            action="unchanged",
            index=relative_index,
            before=before,
            after=before,
            before_sha256=digest,
            after_sha256=digest,
            line=line,
        )

    separator = b"" if not before or before.endswith((b"\n", b"\r")) else newline
    after = before + separator + line_bytes
    return StaticIndexPlan(
        action="append",
        index=relative_index,
        before=before,
        after=after,
        before_sha256=_sha256_bytes(before),
        after_sha256=_sha256_bytes(after),
        line=line,
    )


def plan_static_index_entry(
    vault: Path, entry: StaticIndexEntry
) -> StaticIndexPlan:
    """Freeze one strict, read-only, byte-exact static index proposal."""
    root = validate_vault_root(vault)
    config = _strict_folder_index_config(root)
    return _plan_static_index_entry_with_config(vault, root, entry, config)


def append_static_index_entry(
    vault: Path, entry: StaticIndexEntry
) -> StaticIndexResult:
    root = validate_vault_root(vault)
    try:
        config = _strict_folder_index_config(root)
    except (_StrictFolderIndexConfigError, FolderIndexConfigError):
        config = read_folder_index_config(root)
    plan = _plan_static_index_entry_with_config(vault, root, entry, config)
    index = root / plan.index if plan.index is not None else None
    if plan.action != "append":
        return StaticIndexResult(plan.action, index)

    assert index is not None and plan.before is not None and plan.after is not None
    with index.open("ab") as handle:
        handle.write(plan.after[len(plan.before):])
    return StaticIndexResult("appended", index)
