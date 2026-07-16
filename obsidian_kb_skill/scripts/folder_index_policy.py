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


def expected_folder_index(
    folder: Path, vault: Path, config: FolderIndexConfig
) -> Path:
    if folder == vault:
        return vault / config.root_index_file
    if config.user_specified:
        return folder / f"{config.index_filename}.md"
    return folder / f"{folder.name}.md"


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
