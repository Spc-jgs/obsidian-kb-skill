#!/usr/bin/env python3
"""Create a single Obsidian note with validated frontmatter and a safe write.

Constraint-based wrapper around the note-creation rules in core/OBSIDIAN_KB.md.
Agents without a native file-write tool should call THIS script instead of
writing their own one-off file-writing script.

Read-only by default: it prints the resolved path, the frontmatter that would be
written, and the body, but writes nothing. Pass --apply to actually create the
file. It never overwrites an existing file (a numeric suffix is appended).
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from process_inbox import TYPE_TO_FOLDER, _maybe_update_static_index
    from audit_vault import audit_note
    from suggest_links import suggest_links
except ImportError:  # allow `python -m scripts.create_note`
    from scripts.process_inbox import TYPE_TO_FOLDER, _maybe_update_static_index
    from scripts.audit_vault import audit_note
    from scripts.suggest_links import suggest_links

DEFAULT_TAG_BY_TYPE = {
    "daily-note": "daily",
    "meeting-note": "meeting",
    "learning-note": "learning",
    "web-clip": "web-clip",
    "insight-note": "insight",
    "conversation-digest": "insight",
    "project-note": "project",
    "person-note": "people",
    "task-memory": "task",
}

# Extra frontmatter fields written only when the user's template does NOT already
# define them. These are minimal placeholders so the file still parses as the
# expected type — users are expected to define their own fields in
# {VAULT}/Templates/<Name>.md. The vault template is the single source of truth;
# this dict is just a safety net for new notes whose template was never created.
EXTRA_FIELDS: dict[str, dict[str, Any]] = {
    "daily-note": {"related": []},
    "meeting-note": {"participants": [], "project": "", "related": []},
    "learning-note": {"source": "", "category": "", "related": []},
    "web-clip": {"source": "", "author": "", "published": "", "related": []},
    "insight-note": {"source": "", "related": []},
    "conversation-digest": {"source": "", "related": []},
    "project-note": {"status": "active", "related": []},
    "person-note": {"role": "", "organization": "", "related": []},
    "task-memory": {
        "status": "active", "task-memory": "enabled", "agents": [],
        "decisions": [], "constraints": [], "artifacts": [], "open": [],
    },
}

# Note type -> the conventional template filename inside {VAULT}/Templates/.
# Users can rename these, but the conventional names are what the shipped
# starter templates use, so the bootstrap script scaffolds them in this layout.
TYPE_TO_TEMPLATE: dict[str, str] = {
    "daily-note": "Daily Note.md",
    "meeting-note": "Meeting Note.md",
    "learning-note": "Learning Note.md",
    "web-clip": "Web Clip.md",
    "insight-note": "Insight Note.md",
    "conversation-digest": "Digest Note.md",
    "project-note": "Project Note.md",
    "person-note": "Person Note.md",
}


def validate_vault(vault: Path) -> None:
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        raise SystemExit(2)
    if not (vault / "Templates").is_dir():
        print(
            "warning: Templates/ folder not found; proceeding without template check.",
            file=sys.stderr,
        )


def sanitize_filename(name: str) -> str:
    # Drop characters that are unsafe in file names; keep unicode letters/spaces.
    unsafe = '/\\:*?"<>|'
    cleaned = "".join("_" if ch in unsafe else ch for ch in name).strip().strip(".")
    return cleaned or "untitled"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (metadata, body) splitting a leading YAML frontmatter block if present."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            raw_fm = text[4:end]
            body = text[end + 5:]
            try:
                meta = yaml.safe_load(raw_fm) or {}
            except yaml.YAMLError:
                meta = {}
            if isinstance(meta, dict):
                return meta, body
    return {}, text


def _load_user_template(vault: Path | None, note_type: str) -> tuple[dict[str, Any], str] | None:
    """Read {vault}/Templates/<Name>.md if it exists; return (frontmatter, body).

    Body has every `{{date}}` placeholder substituted with today's date string
    supplied by the caller is NOT done here — the caller already knows the date
    and we want to be explicit about substitution at the call site.

    Returns None when the vault has no Templates/ folder, the type has no
    conventional template name, or the template file is missing. Callers then
    fall back to a minimal body so the note is still usable.
    """
    if vault is None:
        return None
    fname = TYPE_TO_TEMPLATE.get(note_type)
    if not fname:
        return None
    path = vault / "Templates" / fname
    if not path.is_file():
        return None
    return split_frontmatter(path.read_text(encoding="utf-8"))


def _substitute_date(text: str, date: str) -> str:
    """Replace every {{date}} placeholder with the actual date string."""
    return text.replace("{{date}}", date)


def build_note(
    *,
    note_type: str,
    title: str,
    date: str,
    body: str,
    given_meta: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    folder: str | None = None,
    vault: Path | None = None,
) -> tuple[str, str]:
    """Return (folder, rendered_markdown) for the note.

    Body resolution order:
      1. Explicit `body` argument (from --content-file / --stdin) wins.
      2. Otherwise, the user's {vault}/Templates/<Name>.md is used as the body
         (its frontmatter is merged into the note's frontmatter, so the user's
         template can introduce extra fields and they'll be preserved on write).
      3. If no user template exists, a minimal `# title\\n\\n` body is used.

    Frontmatter resolution order: type defaults < given_meta < user template
    frontmatter < explicit CLI overrides. This means a user adding fields to
    their template (e.g. a `mood:` field on Daily Note) will see them appear on
    every new note, without code changes.
    """
    target = folder or TYPE_TO_FOLDER.get(note_type)
    if not target:
        raise ValueError(
            f"unknown type '{note_type}' and no --folder given. "
            f"Known types: {', '.join(sorted(TYPE_TO_FOLDER))}"
        )

    user_template = _load_user_template(vault, note_type)
    user_tpl_meta, user_tpl_body = user_template if user_template else ({}, "")

    # Body: explicit body wins, else user template body (with {{date}} filled).
    if body.strip():
        final_body = body
    elif user_tpl_body:
        final_body = _substitute_date(user_tpl_body, date)
    else:
        final_body = f"# {title}\n"

    # Frontmatter merge (lowest -> highest precedence).
    meta: dict[str, Any] = {}
    meta.update(EXTRA_FIELDS.get(note_type, {}))
    if user_tpl_meta:
        meta.update(user_tpl_meta)
    if given_meta:
        meta.update(given_meta)
    # Explicit CLI overrides always win.
    meta["type"] = note_type
    meta["date"] = date
    if tags is not None:
        meta["tags"] = tags
    if not meta.get("tags"):
        meta["tags"] = [DEFAULT_TAG_BY_TYPE.get(note_type, "note")]
    if "related" not in meta:
        meta["related"] = []

    dump = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    rendered = f"---\n{dump}\n---\n"
    if final_body and not final_body.startswith("\n"):
        rendered += "\n"
    rendered += final_body
    return target, rendered


def resolve_dest(vault: Path, folder: str, filename: str) -> Path:
    """Return a non-existing destination path, appending -2/-3 on conflict (never overwrite)."""
    dest_folder = vault / folder
    dest = dest_folder / filename
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        i = 2
        while (dest_folder / f"{stem}-{i}{suffix}").exists():
            i += 1
        dest = dest_folder / f"{stem}-{i}{suffix}"
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create one Obsidian note with validated frontmatter (never overwrites)."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--type", required=True, help="Note type slug, e.g. insight-note")
    parser.add_argument("--title", required=True, help="Short note title (becomes filename)")
    parser.add_argument("--folder", help="Override the routed target folder")
    parser.add_argument(
        "--content-file", type=Path,
        help="Path to a .md file with the note body (its frontmatter is merged, "
             "explicit values win)",
    )
    parser.add_argument(
        "--stdin", action="store_true", help="Read the note body from standard input"
    )
    parser.add_argument("--tags", help="Comma-separated tags overriding the type default")
    parser.add_argument("--date", help="Date (YYYY-MM-DD); defaults to today")
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write the file (default is a dry run that only prints)",
    )
    parser.add_argument(
        "--no-audit", action="store_true",
        help="Skip the automatic post-write audit (runs by default after --apply)",
    )
    parser.add_argument(
        "--suggest-links", action="store_true",
        help="After writing, print link suggestions reusing suggest_links.py "
             "(requires --apply; the note must exist on disk to score)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit a single JSON object instead of human-readable text",
    )
    args = parser.parse_args(argv)

    vault = args.vault.expanduser().resolve()
    validate_vault(vault)

    date = args.date or datetime.date.today().isoformat()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    body_text = ""
    given_meta: dict[str, Any] = {}
    if args.content_file:
        raw = args.content_file.read_text(encoding="utf-8")
        given_meta, body_text = split_frontmatter(raw)
    elif args.stdin:
        raw = sys.stdin.read()
        given_meta, body_text = split_frontmatter(raw)

    try:
        folder, rendered = build_note(
            note_type=args.type,
            title=args.title,
            date=date,
            body=body_text,
            given_meta=given_meta,
            tags=tags,
            folder=args.folder,
            vault=vault,
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2

    filename = f"{date} {sanitize_filename(args.title)}.md"
    dest = resolve_dest(vault, folder, filename)

    result: dict[str, Any] = {
        "vault": str(vault),
        "folder": folder,
        "path": str(dest),
        "rendered": rendered,
        "applied": False,
        "dry_run": not args.apply,
        "audit": None,
        "suggested_links": None,
    }

    if not args.apply:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"vault : {vault}")
            print(f"folder: {folder}")
            print(f"path  : {dest}")
            print("---- frontmatter + body (preview) ----")
            print(rendered)
            print("--------------------------------------")
            print("(dry run) pass --apply to write the file.")
        return 0

    if not body_text.strip() and not args.json:
        print("warning: empty body; creating a frontmatter-only note.", file=sys.stderr)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(rendered.encode("utf-8"))
    result["applied"] = True

    # Update a static INDEX when applicable (Folder Index / Dataview owned
    # listings are left untouched, mirroring process_inbox).
    plan = {"path": dest, "target": folder, "title": args.title}
    _maybe_update_static_index(vault, plan, date)

    if not args.no_audit:
        findings = audit_note(vault, dest)
        result["audit"] = {
            "ok": not findings,
            "count": len(findings),
            "findings": [
                {"code": f.code, "path": f.path, "message": f.message}
                for f in findings
            ],
        }
        if not args.json:
            rel = dest.relative_to(vault)
            if findings:
                print(f"AUDIT: {len(findings)} issue(s) found in {rel}:")
                for finding in findings:
                    print(f"  - {finding.code}: {finding.message}")
            else:
                print(f"AUDIT: OK — no issues in {rel}")

    if args.suggest_links:
        recs = suggest_links(vault, dest)
        result["suggested_links"] = [
            {"path": p.relative_to(vault).as_posix(), "score": s, "reasons": r}
            for p, s, r in recs
        ]
        if not args.json:
            if recs:
                print("SUGGESTED LINKS:")
                for path, score, reasons in recs:
                    print(f"  {score:>3}  {path.relative_to(vault).as_posix()}")
                    for reason in reasons:
                        print(f"        - {reason}")
            else:
                print("SUGGESTED LINKS: none")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"created: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
