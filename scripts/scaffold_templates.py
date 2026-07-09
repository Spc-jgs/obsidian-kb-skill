#!/usr/bin/env python3
"""Scaffold a vault's Templates/ folder from the single-source note_spec.

Read-only by default (prints what it would create); pass --apply to write the
skeleton file for any template that does not already exist, or --force to
overwrite. Every file is generated from scripts/note_spec.py, so the templates
can never drift from the fields create_note.py writes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

try:
    from note_spec import NOTE_TYPES
except ImportError:  # allow `python -m scripts.scaffold_templates`
    from scripts.note_spec import NOTE_TYPES


def render(type_name: str, spec: dict) -> str:
    fm: dict = {"date": "{{date}}"}
    if spec.get("updated"):
        fm["updated"] = "{{date}}"
    fm["type"] = type_name
    fm["tags"] = spec["tags"]
    fm.update(spec["fields"])
    dump = yaml.safe_dump(
        fm, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    return f"---\n{dump}\n---\n{spec['body']}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scaffold a vault's Templates/ from note_spec.py."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--apply", action="store_true",
        help="Write missing templates (default is a dry run that only prints)",
    )
    p.add_argument(
        "--force", action="store_true", help="Overwrite existing templates too"
    )
    args = p.parse_args(argv)
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2

    templates_dir = vault / "Templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    wrote = 0
    for type_name, spec in NOTE_TYPES.items():
        fname = f"{spec['filename']}.md"
        dest = templates_dir / fname
        content = render(type_name, spec)
        if dest.exists() and not args.force:
            print(f"exists : {fname} (skip; use --force to overwrite)")
            continue
        if not args.apply:
            print(f"would  : {fname}")
            continue
        dest.write_text(content, encoding="utf-8")
        wrote += 1
        print(f"wrote  : {fname}")

    if args.apply:
        print(f"{wrote} template(s) written to {templates_dir}")
    else:
        print("(dry run) pass --apply to write templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
