#!/usr/bin/env python3
"""Detect a vault folder's index strategy and print it as JSON.

Single entry point for index-strategy detection so the agent never has to read
Obsidian's plugin config files and re-derive the mode by hand. Uses the shared
Folder Index policy and adds Dataview/static detection plus a note listing for
link candidates.

Output schema (JSON):
  {
    "vault": "...", "folder": "30-Insights",
    "mode": "folder-index" | "dataview" | "static",
    "index_file": "30-Insights.md" | "INDEX.md" | null,
    "can_append": true | false,        # safe to append a manual wikilink?
    "graph_compatible": true | false,
    "notes": ["a.md", "b.md"],         # note filenames in the folder
    "warnings": ["..."]
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.folder_index_policy import (
    FolderIndexConfigError,
    expected_folder_index,
    is_folder_index_excluded,
    read_folder_index_config,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)


def _index_file_in(folder: Path) -> Path | None:
    for name in (f"{folder.name}.md", "INDEX.md"):
        cand = folder / name
        if cand.is_file():
            return cand
    return None


def detect(vault: Path, folder: str) -> dict[str, Any]:
    v = vault / folder
    config = read_folder_index_config(vault)
    result: dict[str, Any] = {
        "vault": str(vault),
        "folder": folder,
        "warnings": [],
    }
    notes: list[str] = []
    if v.is_dir():
        for p in sorted(v.glob("*.md")):
            if not p.name.startswith("."):
                notes.append(p.name)
    result["notes"] = notes
    index_path = _index_file_in(v) if v.is_dir() else None

    # 1) Folder Index mode (plugin-owned; never append).
    if config.enabled and not is_folder_index_excluded(Path(folder), config):
        idx = expected_folder_index(v, vault, config)
        result["mode"] = "folder-index"
        result["index_file"] = idx.name
        result["can_append"] = False
        result["graph_compatible"] = bool(config.graph_overwrite) and (
            not config.user_specified
        )
        if not config.graph_overwrite:
            result["warnings"].append(
                "graphOverwrite is off: structural folder edges not enabled in Graph View."
            )
        elif config.user_specified:
            result["warnings"].append(
                "indexFileUserSpecified=true with graphOverwrite=true: structural graph "
                "incomplete; recommend a coordinated migration. Do not rename indexes silently."
            )
        return result

    # 2) Dataview mode (query-owned; never append).
    if index_path is not None:
        text = index_path.read_text(encoding="utf-8")
        if "```dataview" in text or "```dataviewjs" in text:
            result["mode"] = "dataview"
            result["index_file"] = index_path.name
            result["can_append"] = False
            return result

    # 3) Static mode (manual INDEX.md, append allowed).
    result["mode"] = "static"
    static = v / "INDEX.md"
    result["index_file"] = static.name if static.is_file() else None
    result["can_append"] = result["index_file"] is not None
    return result


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Detect a vault folder's index strategy (JSON)."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--folder", required=True,
        help="Target folder relative to the vault, e.g. 30-Insights",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON (this tool does so by default)",
    )
    args = p.parse_args(argv)
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        resolve_target_within_vault(vault, args.folder, label="--folder")
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--folder", json_mode=args.json)
    try:
        out = detect(vault, args.folder)
    except FolderIndexConfigError as exc:
        if args.json:
            print(json.dumps({"error": {
                "code": exc.code,
                "message": exc.message,
            }}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc.code}: {exc.message}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
