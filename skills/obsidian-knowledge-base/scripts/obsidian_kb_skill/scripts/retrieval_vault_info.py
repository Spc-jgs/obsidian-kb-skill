#!/usr/bin/env python3
"""Minimal read-only Vault discovery for the retrieval Skill."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.search_vault import _ignored_directory, _markdown_files
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    report_cli_violation,
    validate_vault_root,
)


def retrieval_vault_info(vault: Path) -> dict[str, Any]:
    root = validate_vault_root(vault)
    is_obsidian = (root / ".obsidian").is_dir()
    searchable_folders = sorted(
        path.relative_to(root).as_posix()
        for path in root.iterdir()
        if path.is_dir() and not path.is_symlink() and not _ignored_directory(path)
    )
    markdown_files = sum(1 for _ in _markdown_files(root)) if is_obsidian else 0
    return {
        "schema_version": "1.0",
        "valid": is_obsidian,
        "searchable_folders": searchable_folders,
        "markdown_files": markdown_files,
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Inspect read-only Obsidian retrieval scope."
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = retrieval_vault_info(args.vault)
    except InvalidVaultRootError as exc:
        return report_cli_violation(exc, param="vault", json_mode=args.json)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"{payload['markdown_files']} searchable Markdown file(s) in "
            f"{len(payload['searchable_folders'])} folder(s)."
        )
    if not payload["valid"]:
        print("error: not an Obsidian Vault", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
