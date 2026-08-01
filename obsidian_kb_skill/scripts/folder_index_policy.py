#!/usr/bin/env python3
"""Folder Index ownership and static ``INDEX.md`` append policy."""
from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    # A name the filesystem cannot even encode is a config error like any
    # other. Encoding inline in the length guard let it escape as an untyped
    # UnicodeEncodeError instead of the documented refusal.
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise FolderIndexConfigError(field) from None
    if (
        not value
        or value != value.strip()
        or value in {".", ".."}
        or value.startswith(".")
        or value.endswith(".")
        or windows_stem in WINDOWS_RESERVED_FILENAMES
        or len(encoded) > 255
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


def append_static_index_entry(
    vault: Path, entry: StaticIndexEntry
) -> StaticIndexResult:
    root = validate_vault_root(vault)
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
    target = resolve_target_within_vault(
        root, logical_note.parent, label="target folder"
    )
    target_relative = target.relative_to(root)
    index = resolve_target_within_vault(
        root, target_relative / "INDEX.md", label="static index"
    )

    config = read_folder_index_config(root)
    if config.enabled and not is_folder_index_excluded(logical_note.parent, config):
        return StaticIndexResult("unmanaged", index if index.is_file() else None)
    if not index.is_file():
        return StaticIndexResult("missing", None)
    index_text = index.read_text(encoding="utf-8")
    if "folder-index-content" in index_text or "dataview" in index_text:
        return StaticIndexResult("unmanaged", index)

    line = (
        f"- [[{logical_note.with_suffix('').as_posix()}|{entry.title}]] "
        f"({entry.date})\n"
    )
    with index.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return StaticIndexResult("appended", index)
