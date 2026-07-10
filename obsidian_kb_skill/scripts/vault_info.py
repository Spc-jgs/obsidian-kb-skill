#!/usr/bin/env python3
"""One-shot read-only vault cold-start context, emitted as JSON.

Replaces the several manual reads an agent would otherwise do on first
contact with a vault (vault discovery, the 3 validity checks, listing
Templates/, probing each folder's existence, and re-deriving the index
strategy per folder). A single call returns a compact JSON summary so the
agent spends tokens reading a summary, not raw directory listings.

Reuses `detect_index.detect` for index-strategy detection and
`audit_vault._folder_index_config` for the global Folder Index config, so
there is exactly one source of truth for those rules (no prose duplication).

Output schema (JSON):
  {
    "vault": "...", "valid": true,
    "validation": {"exists": true, "is_obsidian": true, "has_templates": true},
    "templates": ["Daily Note", "Meeting Note", ...],
    "standard_folders": {
      "00-Inbox": {"exists": true, "index": {<detect result>}},
      ...
      "Templates": {"exists": true, "index": null},
      "Attachments": {"exists": true, "index": null}
    },
    "folder_index_global": {
      "enabled": false, "graph_overwrite": false,
      "user_specified": false, "root_index_file": "INDEX.md"
    },
    "warnings": ["..."]
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.detect_index import detect
from obsidian_kb_skill.scripts.audit_vault import _folder_index_config


# Note-bearing folders that get an index strategy; Templates/Attachments are
# listed for existence only.
NOTE_FOLDERS = [
    "00-Inbox",
    "10-Work",
    "15-Daily",
    "20-Learning",
    "30-Insights",
    "40-Projects",
    "50-People",
    "90-Archive",
]
STANDARD_FOLDERS = NOTE_FOLDERS + ["Templates", "Attachments"]


def _templates(vault: Path) -> list[str]:
    templates_dir = vault / "Templates"
    if not templates_dir.is_dir():
        return []
    return sorted(
        p.stem for p in templates_dir.glob("*.md") if not p.name.startswith(".")
    )


def collect(vault: Path) -> dict[str, Any]:
    vault = vault.resolve()
    warnings: list[str] = []
    exists = vault.is_dir()
    is_obsidian = (vault / ".obsidian").is_dir()
    has_templates = (vault / "Templates").is_dir()
    valid = exists and is_obsidian and has_templates
    if not exists:
        warnings.append("vault path does not exist")
    if exists and not is_obsidian:
        warnings.append(".obsidian directory missing: not a real Obsidian vault")
    if exists and not has_templates:
        warnings.append("Templates/ directory missing")

    config = _folder_index_config(vault)
    standard_folders: dict[str, Any] = {}
    for name in STANDARD_FOLDERS:
        folder = vault / name
        entry: dict[str, Any] = {"exists": folder.is_dir()}
        if name in NOTE_FOLDERS:
            entry["index"] = detect(vault, name) if exists else None
        else:
            entry["index"] = None
        standard_folders[name] = entry

    return {
        "vault": str(vault),
        "valid": valid,
        "validation": {
            "exists": exists,
            "is_obsidian": is_obsidian,
            "has_templates": has_templates,
        },
        "templates": _templates(vault) if exists else [],
        "standard_folders": standard_folders,
        "folder_index_global": {
            "enabled": config.enabled,
            "graph_overwrite": config.graph_overwrite,
            "user_specified": config.user_specified,
            "root_index_file": config.root_index_file,
        },
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Print a vault cold-start context summary as JSON."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--json", action="store_true", help="Emit JSON (this tool does so by default)"
    )
    args = p.parse_args(argv)
    info = collect(args.vault.expanduser())
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
