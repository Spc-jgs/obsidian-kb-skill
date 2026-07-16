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
import copy
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.detect_index import detect
from obsidian_kb_skill.scripts.audit_vault import _folder_index_config
from obsidian_kb_skill.scripts.note_catalog import MANAGED_NOTE_FOLDERS
from obsidian_kb_skill.scripts.note_types import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.template_contract import (
    custom_template_types,
    template_shape,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)


# Note-bearing folders that get an index strategy; Templates/Attachments are
# listed for existence only.
NOTE_FOLDERS: list[str] = list(MANAGED_NOTE_FOLDERS)
STANDARD_FOLDERS = NOTE_FOLDERS + ["Templates", "Attachments"]


def _templates(vault: Path) -> list[str]:
    templates_dir = vault / "Templates"
    if not templates_dir.is_dir():
        return []
    return sorted(
        p.stem for p in templates_dir.glob("*.md") if not p.name.startswith(".")
    )


def collect(vault: Path, note_type: str | None = None) -> dict[str, Any]:
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

    result = {
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
        "custom_templates": custom_template_types(vault) if exists else [],
        "warnings": warnings,
    }
    if note_type is not None:
        result["template_shape"] = template_shape(vault, note_type)
    return result


def compact(info: dict[str, Any]) -> dict[str, Any]:
    """Return discovery output without per-folder note filename arrays."""
    result = copy.deepcopy(info)
    for entry in result["standard_folders"].values():
        index = entry.get("index")
        if index is not None:
            index.pop("notes", None)
    return result


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Print a vault cold-start context summary as JSON."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--json", action="store_true", help="Emit JSON (this tool does so by default)"
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="Omit per-folder note filename arrays from discovery output",
    )
    p.add_argument(
        "--type",
        dest="note_type",
        help="Include only this conventional note type's ordered template headings",
    )
    args = p.parse_args(argv)
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.note_type is not None and args.note_type not in TYPE_TO_TEMPLATE:
        print(json.dumps({
            "error": {
                "code": "unsupported-template-type",
                "note_type": args.note_type,
                "supported": sorted(TYPE_TO_TEMPLATE),
            }
        }, ensure_ascii=False))
        return 2
    info = collect(vault, note_type=args.note_type)
    if args.compact:
        info = compact(info)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
