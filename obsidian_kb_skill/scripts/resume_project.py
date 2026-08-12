#!/usr/bin/env python3
"""Build a read-only resume pack for one project.

`review-projects` answers *which* project to pick up. This answers *how to
continue it*: the project's own note plus the output that belongs to it,
gathered without scanning the Vault and without inferring membership.

Membership comes from the entity-folder layout — a note inside the project's
instance directory belongs to that project because of where it is, not because
a frontmatter field or a wikilink says so. Those fields can be missing or stale;
the directory cannot be either.

Read-only: nothing here writes, moves, or repairs a note.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.note_catalog import (
    ENTITY_FOLDERS,
    ENTITY_INSTANCE_TYPE,
    EXEMPT_NAMES,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)

SCHEMA_VERSION = "1.0"
COMMAND = "resume-project"

# Where a source came from. Only one origin exists today; the field is present
# from the start because the value is what tells a reader how much to trust the
# membership claim, and a later origin must not silently look like this one.
ORIGIN_INSTANCE_DIRECTORY = "instance-directory"


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "command": COMMAND,
        "read_only": True,
        "error": {"code": code, "message": message},
    }


def _note_payload(relative: Path, metadata: dict[str, Any] | None) -> dict[str, Any]:
    meta = metadata or {}
    return {
        "path": relative.as_posix(),
        "type": meta.get("type"),
        "date": str(meta.get("date")) if meta.get("date") is not None else None,
        "status": meta.get("status"),
    }


def _read(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Return (metadata, error message). Unreadable frontmatter is reported."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    parsed = parse_frontmatter(text, source=path.as_posix())
    if parsed.issue is not None:
        return None, parsed.issue.message
    return parsed.metadata or {}, None


def _instance_sources(
    directory: Path, project: Path, vault: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every readable note in the instance directory except the project note.

    Index files are excluded: a folder index lists the directory's contents and
    would add nothing to a pack built from those same contents.
    """
    sources: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        if path == project or path.name in EXEMPT_NAMES:
            continue
        relative = path.relative_to(vault)
        metadata, error = _read(path)
        if error is not None:
            issues.append(
                {
                    "path": relative.as_posix(),
                    "code": "unreadable-frontmatter",
                    "message": error,
                }
            )
            continue
        entry = _note_payload(relative, metadata)
        entry["origin"] = ORIGIN_INSTANCE_DIRECTORY
        sources.append(entry)
    return sources, issues


def build(
    vault: Path, *, note: Path, as_of: datetime.date
) -> dict[str, Any]:
    """Assemble the resume pack for one project note."""
    vault = vault.resolve()
    project = (vault / note).resolve()
    if not project.is_file():
        return _error("missing-note", f"no such note: {note.as_posix()}")

    relative = project.relative_to(vault)
    metadata, error = _read(project)
    if error is not None:
        return _error("unreadable-frontmatter", error)

    entity_folder = relative.parts[0] if relative.parts else ""
    expected_type = ENTITY_INSTANCE_TYPE.get(entity_folder)
    if (metadata or {}).get("type") != expected_type:
        return _error(
            "not-a-project-note",
            f"{relative.as_posix()} is typed "
            f"{(metadata or {}).get('type')!r}, not {expected_type!r}",
        )

    # A project note directly at the entity root has no instance directory, so
    # it has no subordinate output to gather. That is a valid pre-existing
    # layout, not an error: #95 explicitly does not migrate it.
    in_instance_directory = (
        entity_folder in ENTITY_FOLDERS and len(relative.parts) >= 3
    )
    sources: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if in_instance_directory:
        sources, issues = _instance_sources(project.parent, project, vault)

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": COMMAND,
        "read_only": True,
        "as_of": as_of.isoformat(),
        "project": _note_payload(relative, metadata),
        "instance_directory": (
            project.parent.relative_to(vault).as_posix()
            if in_instance_directory
            else None
        ),
        "summary": {"sources": len(sources)},
        "sources": sources,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Build a read-only resume pack for one Obsidian project."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian Vault")
    parser.add_argument(
        "--note", required=True, help="Vault-relative path to the project note"
    )
    parser.add_argument(
        "--as-of", help="Reference date in ISO format (YYYY-MM-DD; default: today)"
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2

    try:
        resolve_target_within_vault(vault, args.note, label="--note")
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--note", json_mode=args.json)

    if args.as_of:
        try:
            as_of = datetime.date.fromisoformat(args.as_of)
        except ValueError:
            print(f"error: --as-of is not an ISO date: {args.as_of}", file=sys.stderr)
            return 2
    else:
        as_of = datetime.date.today()

    payload = build(vault, note=Path(args.note), as_of=as_of)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    if not payload["ok"]:
        print(f"error: {payload['error']['message']}", file=sys.stderr)
        return 1
    print(f"project: {payload['project']['path']}")
    print(f"status:  {payload['project'].get('status')}")
    print(f"sources: {payload['summary']['sources']}")
    for source in payload["sources"]:
        print(f"  {source['path']}  ({source['type']}, {source['date']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
