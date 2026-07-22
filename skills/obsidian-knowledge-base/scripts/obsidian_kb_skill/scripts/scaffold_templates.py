#!/usr/bin/env python3
"""Bootstrap a vault's Templates/ folder from the skill's shipped starter templates.

The vault's {VAULT}/Templates/<Name>.md is the SINGLE SOURCE OF TRUTH at runtime
— create_note.py reads it, fills in {{date}}, and uses it as the note body. This
script only seeds the folder with sensible starter templates the first time; after
that the user is expected to edit them in their vault (Obsidian), and re-running
this script will NOT overwrite the user's edits (use --force if you really mean it).

The shipped templates are resolved by ``resource_locator`` (an installed wheel's
bundled copy by default, or ``--skill-root`` / ``OBSIDIAN_KB_SKILL_ROOT`` when set).
They also live at ``core/templates/`` in a source checkout, but at write time the
vault template wins.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.note_catalog import NOTE_TYPES
from obsidian_kb_skill.scripts.resource_locator import ResourceError, template_dir
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)

def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Bootstrap a vault's Templates/ from the skill's shipped starters."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--apply", action="store_true",
        help="Write missing templates (default is a dry run that only prints)",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite existing templates (DESTRUCTIVE: clobbers your edits)",
    )
    p.add_argument(
        "--skill-root", type=Path,
        help="Explicit skill root containing templates/ and references/ (advanced). "
             "If given but invalid, the command fails instead of falling back.",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit one machine-readable JSON result instead of text",
    )
    args = p.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        if args.json:
            print(json.dumps({"schema_version": "1.0", "ok": False,
                              "operation": "scaffold-templates",
                              "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (vault / ".obsidian").is_dir():
        if args.json:
            print(json.dumps({"schema_version": "1.0", "ok": False,
                              "operation": "scaffold-templates",
                              "error": f"not an Obsidian vault: {vault}"},
                             ensure_ascii=False))
        else:
            print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2

    try:
        src_dir = template_dir(skill_root=args.skill_root)
    except ResourceError as exc:
        if args.json:
            print(json.dumps({"schema_version": "1.0", "ok": False,
                              "operation": "scaffold-templates",
                              "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 3

    templates_dir = vault / "Templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []
    planned: list[str] = []
    for type_name, spec in NOTE_TYPES.items():
        vault_fname = spec.template_name
        src_fname = spec.template_asset
        if vault_fname is None or src_fname is None:
            continue
        src = src_dir / src_fname
        dest = templates_dir / vault_fname
        if not src.is_file():
            missing.append(src_fname)
            if not args.json:
                print(f"missing: shipped {src_fname} (skip)")
            continue
        if dest.exists() and not args.force:
            skipped.append(vault_fname)
            if not args.json:
                print(f"exists : {vault_fname} (skip; user template wins at runtime)")
            continue
        if not args.apply:
            planned.append(vault_fname)
            if not args.json:
                print(f"would  : {vault_fname}")
            continue
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(vault_fname)
        if not args.json:
            print(f"wrote  : {vault_fname}")

    result = {
        "schema_version": "1.0",
        "ok": not missing,
        "operation": "scaffold-templates",
        "apply": args.apply,
        "force": args.force,
        "written": written,
        "skipped": skipped,
        "missing": missing,
        "planned": planned,
        "templates_dir": str(templates_dir),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not missing else 3

    if args.apply:
        print(f"{len(written)} template(s) written to {templates_dir}")
        print("Edit them inside Obsidian to customize — this script will not overwrite edits.")
    else:
        print("(dry run) pass --apply to write templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
