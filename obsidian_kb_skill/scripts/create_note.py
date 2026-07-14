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
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.note_types import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.process_inbox import (
    TYPE_TO_FOLDER,
    _maybe_update_static_index,
)
from obsidian_kb_skill.scripts.audit_vault import Finding, audit_note, audit_note_text
from obsidian_kb_skill.scripts.suggest_links import suggest_links
from obsidian_kb_skill.scripts.vault_paths import (
    EXIT_PATH_VIOLATION,
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    structured_error,
    validate_vault_root,
)

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

def validate_vault(vault: Path, *, json_mode: bool = False) -> None:
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        exc = InvalidVaultRootError(f"not an Obsidian vault: {vault}")
        if json_mode:
            print(json.dumps(structured_error(exc, param="vault"), ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
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
    # Native Windows pipelines may prefix UTF-8 input with a BOM and preserve
    # CRLF line endings.  Normalize those transport details before looking for
    # Markdown's line-oriented frontmatter delimiters.
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
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


def normalize_yaml_scalars(value: Any) -> Any:
    """Return metadata using portable YAML scalar types.

    PyYAML resolves unquoted ISO dates to ``datetime.date`` objects. Obsidian
    properties and this skill's schema expect ISO strings, so normalize those
    values recursively before rendering the final frontmatter.
    """
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_yaml_scalars(item) for item in value]
    return value


def missing_required_metadata(note_type: str, metadata: dict[str, Any]) -> list[str]:
    """Return non-empty string fields required before a note may be written."""
    if note_type != "web-clip":
        return []
    return [
        field
        for field in ("source", "author", "published")
        if not isinstance(metadata.get(field), str) or not metadata[field].strip()
    ]


def report_invalid_utf8_input(source: str, *, json_mode: bool) -> int:
    """Report invalid Unicode input without leaking a Python traceback."""
    message = f"{source} must contain valid UTF-8"
    if json_mode:
        print(json.dumps({
            "error": {"code": "invalid-utf8-input", "message": message}
        }, ensure_ascii=False))
    else:
        print(f"error: {message}", file=sys.stderr)
    return 2


def finding_payload(findings: list[Finding]) -> dict[str, Any]:
    """Return the stable machine-readable shape for note-level findings."""
    return {
        "ok": not findings,
        "count": len(findings),
        "findings": [
            {"code": item.code, "path": item.path, "message": item.message}
            for item in findings
        ],
    }


def print_preview(vault: Path, folder: str, dest: Path, rendered: str) -> None:
    """Print the human-readable dry-run preview."""
    print(f"vault : {vault}")
    print(f"folder: {folder}")
    print(f"path  : {dest}")
    print("---- frontmatter + body (preview) ----")
    print(rendered)
    print("--------------------------------------")


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


def _render_template_body(text: str, *, date: str, title: str) -> str:
    """Fill template variables and bind its first H1 to the requested title."""
    heading = " ".join(title.splitlines()).strip() or "untitled"
    rendered = _substitute_date(text, date).replace("{{title}}", heading)
    lines = rendered.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"# {heading}{newline}"
            return "".join(lines)
    separator = "" if not rendered or rendered.startswith("\n") else "\n"
    return f"# {heading}\n{separator}{rendered}"


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

    Frontmatter resolution order: type defaults < user template frontmatter <
    given_meta (stdin/content-file) < explicit CLI overrides. This means a user
    adding fields to their template (e.g. a `mood:` field on Daily Note) will
    see them appear on every new note, while input frontmatter can fill those
    fields for one invocation.
    """
    target = folder or TYPE_TO_FOLDER.get(note_type)
    if not target:
        raise ValueError(
            f"unknown type '{note_type}' and no --folder given. "
            f"Known types: {', '.join(sorted(TYPE_TO_FOLDER))}"
        )

    user_template = _load_user_template(vault, note_type)
    user_tpl_meta, user_tpl_body = user_template if user_template else ({}, "")

    # Body: explicit body wins. A template body has date/title variables filled
    # and its first H1 is the requested note title; user-owned explicit content
    # is never rewritten.
    if body.strip():
        final_body = body
    elif user_tpl_body:
        final_body = _render_template_body(user_tpl_body, date=date, title=title)
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
    meta = normalize_yaml_scalars(meta)

    dump = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    rendered = f"---\n{dump}\n---\n"
    if final_body and not final_body.startswith("\n"):
        rendered += "\n"
    rendered += final_body
    return target, rendered


def destination_candidates(vault: Path, folder: str, filename: str) -> Iterator[Path]:
    """Yield the base destination followed by numeric-suffix alternatives."""
    dest_folder = vault / folder
    base = dest_folder / filename
    yield base
    index = 2
    while True:
        yield dest_folder / f"{base.stem}-{index}{base.suffix}"
        index += 1


def resolve_dest(vault: Path, folder: str, filename: str) -> Path:
    """Predict the first available destination for a dry-run preview."""
    return next(candidate for candidate in destination_candidates(vault, folder, filename)
                if not candidate.exists())


def write_new_note(
    vault: Path,
    folder: str,
    filename: str,
    rendered_bytes: bytes,
) -> Path:
    """Create one note exclusively, retrying suffixes when another writer wins."""
    dest_folder = vault / folder
    dest_folder.mkdir(parents=True, exist_ok=True)
    for candidate in destination_candidates(vault, folder, filename):
        try:
            with candidate.open("xb") as handle:
                handle.write(rendered_bytes)
            return candidate
        except FileExistsError:
            continue
    raise AssertionError("unreachable destination candidate loop")


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Create one Obsidian note with validated frontmatter (never overwrites)."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--type", required=True, help="Note type slug, e.g. insight-note")
    parser.add_argument("--title", required=True, help="Short note title (becomes filename)")
    parser.add_argument("--folder", help="Override the routed target folder")
    parser.add_argument(
        "--content-file", type=Path,
        help="Path to complete Markdown inside the Vault (frontmatter is merged, "
             "explicit values win)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read complete UTF-8 Markdown from standard input; optional frontmatter is merged",
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
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="With --apply, emit JSON without the rendered Markdown body",
    )
    parser.add_argument(
        "--preflight-json",
        action="store_true",
        help="Dry-run with final metadata, content identity, and validation "
             "without echoing the Markdown body",
    )
    args = parser.parse_args(argv)
    json_mode = args.json or args.compact_json or args.preflight_json

    if args.preflight_json and (args.apply or args.json or args.compact_json):
        print(json.dumps({
            "error": {
                "code": "invalid-output-mode",
                "message": (
                    "--preflight-json cannot be combined with --apply, --json, "
                    "or --compact-json"
                ),
            }
        }, ensure_ascii=False, indent=2))
        return 2

    if args.compact_json and not args.apply:
        print(json.dumps({
            "error": {
                "code": "compact-json-requires-apply",
                "message": "--compact-json requires --apply",
            }
        }, ensure_ascii=False, indent=2))
        return 2

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        if json_mode:
            print(json.dumps(structured_error(exc, param="vault"), ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    validate_vault(vault, json_mode=json_mode)

    # Enforce the Vault path boundary on every user-supplied path before any
    # read or write. Routing through vault_paths (never Path() + startswith)
    # is the single defense against ../ traversal, absolute escapes, symlink
    # redirects, and Windows drive/UNC spoofing.
    if args.folder:
        try:
            resolve_target_within_vault(vault, args.folder, label="--folder")
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--folder", json_mode=json_mode)
    content_path: Path | None = None
    if args.content_file:
        try:
            content_path = resolve_existing_within_vault(
                vault, args.content_file, label="--content-file"
            )
        except VaultPathError as exc:
            return report_cli_violation(
                exc, param="--content-file", json_mode=json_mode
            )

    date = args.date or datetime.date.today().isoformat()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    body_text = ""
    given_meta: dict[str, Any] = {}
    try:
        if content_path is not None:
            raw = content_path.read_text(encoding="utf-8")
            given_meta, body_text = split_frontmatter(raw)
        elif args.stdin:
            raw = sys.stdin.read()
            given_meta, body_text = split_frontmatter(raw)
    except UnicodeError:
        source = "stdin" if args.stdin else "--content-file"
        return report_invalid_utf8_input(source, json_mode=json_mode)

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
        if json_mode:
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

    try:
        rendered_bytes = rendered.encode("utf-8")
    except UnicodeError:
        source = "stdin" if args.stdin else "--content-file"
        return report_invalid_utf8_input(source, json_mode=json_mode)

    rendered_meta, rendered_body = split_frontmatter(rendered)
    missing_fields = missing_required_metadata(args.type, rendered_meta)
    if missing_fields and not args.preflight_json:
        error = {
            "code": "missing-required-metadata",
            "note_type": args.type,
            "fields": missing_fields,
        }
        if json_mode:
            payload = {**result, "error": error} if not args.apply else {"error": error}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if not args.apply:
                print_preview(vault, folder, dest, rendered)
            print(
                "error: web-clip requires non-empty metadata: "
                + ", ".join(missing_fields),
                file=sys.stderr,
            )
        return 2

    if args.preflight_json:
        findings = audit_note_text(vault, dest, rendered)
        payload = {
            "vault": str(vault),
            "folder": folder,
            "path": str(dest),
            "applied": False,
            "dry_run": True,
            "frontmatter": rendered_meta,
            "content": {
                "sha256": hashlib.sha256(rendered_bytes).hexdigest(),
                "utf8_bytes": len(rendered_bytes),
                "line_count": len(rendered.splitlines()),
            },
            "validation": finding_payload(findings),
            "suggested_links": None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not findings else 2

    if not args.apply:
        if json_mode:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_preview(vault, folder, dest, rendered)
            print("(dry run) pass --apply to write the file.")
        return 0

    if not rendered_body.strip() and not json_mode:
        print("warning: empty body; creating a frontmatter-only note.", file=sys.stderr)

    dest = write_new_note(vault, folder, filename, rendered_bytes)
    result["path"] = str(dest)
    result["applied"] = True

    # Update a static INDEX when applicable (Folder Index / Dataview owned
    # listings are left untouched, mirroring process_inbox).
    plan = {"path": dest, "target": folder, "title": args.title}
    _maybe_update_static_index(vault, plan, date)

    if not args.no_audit:
        findings = audit_note(vault, dest)
        result["audit"] = finding_payload(findings)
        if not json_mode:
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
        if not json_mode:
            if recs:
                print("SUGGESTED LINKS:")
                for path, score, reasons in recs:
                    print(f"  {score:>3}  {path.relative_to(vault).as_posix()}")
                    for reason in reasons:
                        print(f"        - {reason}")
            else:
                print("SUGGESTED LINKS: none")

    if json_mode:
        payload = (
            {key: value for key, value in result.items() if key != "rendered"}
            if args.compact_json
            else result
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"created: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
