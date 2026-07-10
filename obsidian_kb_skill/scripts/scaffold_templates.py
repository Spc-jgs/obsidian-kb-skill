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
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.resource_locator import ResourceError, template_dir

# Map note type -> (template filename used inside the vault, source file name
# in core/templates/). These are shipped starter files; users may edit the
# copies in {VAULT}/Templates/ freely.
TEMPLATE_MAP: list[tuple[str, str, str]] = [
    ("daily-note", "Daily Note.md", "daily-note.md"),
    ("meeting-note", "Meeting Note.md", "meeting-note.md"),
    ("learning-note", "Learning Note.md", "learning-note.md"),
    ("web-clip", "Web Clip.md", "web-clip.md"),
    ("insight-note", "Insight Note.md", "insight-note.md"),
    ("conversation-digest", "Digest Note.md", "digest-note.md"),
    ("project-note", "Project Note.md", "project-note.md"),
    ("person-note", "Person Note.md", "person-note.md"),
]


def main(argv: list[str] | None = None) -> int:
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
    args = p.parse_args(argv)

    vault = args.vault.expanduser().resolve()
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2

    try:
        src_dir = template_dir(skill_root=args.skill_root)
    except ResourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    templates_dir = vault / "Templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    wrote = 0
    for type_name, vault_fname, src_fname in TEMPLATE_MAP:
        src = src_dir / src_fname
        dest = templates_dir / vault_fname
        if not src.is_file():
            print(f"missing: shipped {src_fname} (skip)")
            continue
        if dest.exists() and not args.force:
            print(f"exists : {vault_fname} (skip; user template wins at runtime)")
            continue
        if not args.apply:
            print(f"would  : {vault_fname}")
            continue
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        wrote += 1
        print(f"wrote  : {vault_fname}")

    if args.apply:
        print(f"{wrote} template(s) written to {templates_dir}")
        print("Edit them inside Obsidian to customize — this script will not overwrite edits.")
    else:
        print("(dry run) pass --apply to write templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
