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
import re
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.conversation_digest_contract import (
    CONVERSATION_DIGEST_HEADING_VARIANTS,
)
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

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")


def _digest_section(index: int) -> tuple[str, ...]:
    """One digest section, in every locale the digest contract declares.

    Derived rather than restated. The digest's section names are already a
    contract, and a second copy here would be the hand-mirror shape that
    produced #91's installer paths and #103's peer lists — right up until the
    two drifted. The index is positional because the contract is an ordered
    tuple per locale; `test_digest_heading_variants_are_derived_not_copied`
    fails if that stops holding.
    """
    return tuple(
        headings[index].lower()
        for _, headings in CONVERSATION_DIGEST_HEADING_VARIANTS
    )


# Which headings answer each resume question, per note type. Extraction reads
# only these; a custom template without them yields `missing-section` rather
# than a guess assembled from arbitrary prose.
RESUME_SECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "goal": {
        # `overview` is what `core/templates/en/project-note.md` actually
        # writes; `project overview` is what the real Vault's oldest English
        # note uses. Both are observed. Until
        # `test_this_projects_own_templates_are_fully_readable_by_the_extractor`
        # was written, only the second was here, so every note written from this
        # project's own English template reported `goal` as missing.
        "project-note": ("项目概览", "overview", "project overview"),
        "conversation-digest": _digest_section(0),
    },
    "constraints": {
        "conversation-digest": _digest_section(1),
    },
    "decisions": {
        "project-note": ("决策记录", "decisions log", "decision log", "decisions"),
        "conversation-digest": _digest_section(2),
    },
    "evidence": {
        "conversation-digest": _digest_section(3),
    },
    "blockers": {
        "project-note": ("风险与阻塞", "risks and blockers", "risks & blockers"),
    },
    "next_actions": {
        # `后续行动` is observed, not invented: it is the heading in
        # `40-Projects/etianqu/2026-07-09 AI对话上下文与落库设计复盘.md` on the
        # reference Vault, and the note #115 was filed from. Every variant here
        # must come from a template or a real note — a guessed synonym makes the
        # vocabulary look complete while it still fails silently, which is the
        # defect itself rather than a fix for it.
        "project-note": ("下一步行动", "后续行动", "next actions", "next steps"),
        "conversation-digest": _digest_section(4),
    },
}

# Fields a project note is expected to answer on its own. Absence of the rest
# is not a gap in the project note — those live in its digests.
PROJECT_NOTE_FIELDS = tuple(
    field
    for field, sources in RESUME_SECTIONS.items()
    if "project-note" in sources
)

# Where a source came from. Only one origin exists today; the field is present
# from the start because the value is what tells a reader how much to trust the
# membership claim, and a later origin must not silently look like this one.
ORIGIN_INSTANCE_DIRECTORY = "instance-directory"

# Resuming needs the project's current state, so the newest output is the
# relevant output. The bound keeps the pack a known number of reads; the
# overflow is reported rather than dropped, because a pack that looks
# complete while the relevant note sits outside it is worse than a short one.
DEFAULT_MAX_SOURCES = 5


def _normalize_heading(text: str) -> str:
    """The single definition of "this heading is that heading".

    Both the matcher and the heading report call this. Two independent notions
    of equality would let the report claim a heading was recognized that the
    matcher never matched — the reader would then be told to stop looking.
    """
    return text.strip().lower()


def _heading_report(text: str, note_type: str) -> dict[str, list[str]]:
    """Split the note's headings into the ones this vocabulary knows and the rest.

    `missing_sections` alone cannot distinguish "the note never recorded this"
    from "the note recorded it under a name the vocabulary does not have", and
    those two readings lead a user in opposite directions (#115). The pack does
    not guess which unmatched heading holds what — #86 rules that out — it
    reports what it did not claim and lets the reader look.

    Recognition is by name only. A heading that is in the vocabulary but has an
    empty body appears here as matched while its field is still missing, which
    tells the reader the section exists and is empty.
    """
    known = {
        _normalize_heading(variant)
        for per_type in RESUME_SECTIONS.values()
        for variant in per_type.get(note_type, ())
    }
    matched: list[str] = []
    unmatched: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2).strip()
        target = matched if _normalize_heading(heading) in known else unmatched
        target.append(heading)
    return {"matched": matched, "unmatched": unmatched}


def _section_text(
    text: str, headings: tuple[str, ...]
) -> tuple[str, int] | None:
    """Return (body, 1-indexed heading line) for the first matching section.

    The section ends at the next heading of the same or shallower level, so a
    subsection stays with its parent rather than truncating it.
    """
    lines = text.splitlines()
    wanted = {_normalize_heading(heading) for heading in headings}
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match or _normalize_heading(match.group(2)) not in wanted:
            continue
        level = len(match.group(1))
        end = len(lines)
        for following in range(index + 1, len(lines)):
            next_match = HEADING_RE.match(lines[following])
            if next_match and len(next_match.group(1)) <= level:
                end = following
                break
        body = "\n".join(lines[index + 1 : end]).strip()
        if body:
            return body, index + 1
    return None


def _extract(
    text: str, relative: Path, note_type: str, fields: tuple[str, ...]
) -> tuple[dict[str, Any], list[str]]:
    """Pull the resume fields this note type is expected to answer."""
    found: dict[str, Any] = {}
    missing: list[str] = []
    for field in fields:
        headings = RESUME_SECTIONS[field].get(note_type)
        if not headings:
            continue
        section = _section_text(text, headings)
        if section is None:
            found[field] = None
            missing.append(field)
            continue
        body, line = section
        found[field] = {
            "text": body,
            "path": relative.as_posix(),
            "line": line,
        }
    return found, missing


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
    directory: Path,
    project: Path,
    vault: Path,
    from_sources: dict[str, list[dict[str, Any]]],
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
        note_type = (metadata or {}).get("type")
        contributed, _ = _extract(
            path.read_text(encoding="utf-8"),
            relative,
            note_type,
            tuple(
                field
                for field, per_type in RESUME_SECTIONS.items()
                if note_type in per_type
            ),
        )
        entry["fields"] = sorted(
            field for field, value in contributed.items() if value is not None
        )
        for field, value in contributed.items():
            if value is not None:
                from_sources.setdefault(field, []).append(value)
        sources.append(entry)
    return sources, issues


def build(
    vault: Path,
    *,
    note: Path,
    as_of: datetime.date,
    max_sources: int = DEFAULT_MAX_SOURCES,
) -> dict[str, Any]:
    """Assemble the resume pack for one project note."""
    vault = vault.resolve()
    project = (vault / note).resolve()
    if not project.is_file():
        return _error("missing-note", f"no such note: {note.as_posix()}")

    relative = project.relative_to(vault)
    project_text = project.read_text(encoding="utf-8")
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
    from_sources: dict[str, list[dict[str, Any]]] = {}
    if in_instance_directory:
        sources, issues = _instance_sources(
            project.parent, project, vault, from_sources
        )
        # Newest first. A missing date sorts last rather than being dropped —
        # an undated note is still this project's output.
        sources.sort(key=lambda item: (item.get("date") or "", item["path"]), reverse=True)

    available = len(sources)
    bounded = sources[:max_sources] if max_sources is not None else sources
    if len(bounded) != available:
        # `from_sources` must describe the pack that was returned, not the one
        # that was gathered — otherwise a citation points at a note the reader
        # was never given.
        kept = {item["path"] for item in bounded}
        from_sources = {
            field: [entry for entry in entries if entry["path"] in kept]
            for field, entries in from_sources.items()
        }
        from_sources = {k: v for k, v in from_sources.items() if v}

    resume, missing = _extract(
        project_text, relative, expected_type, PROJECT_NOTE_FIELDS
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": COMMAND,
        "read_only": True,
        "as_of": as_of.isoformat(),
        "project": _note_payload(relative, metadata),
        "resume": resume,
        "from_sources": from_sources,
        # Answered by the project note *and* by a source. Not necessarily a
        # contradiction — a decision may simply be restated — but the pack must
        # not choose for the reader, so both are returned and named here.
        "contested": sorted(
            field
            for field, value in resume.items()
            if value is not None and field in from_sources
        ),
        "missing_sections": missing,
        # Read with `missing_sections`, never apart from it: a missing field
        # whose note has unmatched headings may well be recorded under one of
        # them. Both lists empty means the note has no headings at all, the one
        # case where missing does mean absent.
        "headings": _heading_report(project_text, expected_type),
        "instance_directory": (
            project.parent.relative_to(vault).as_posix()
            if in_instance_directory
            else None
        ),
        "summary": {
            "sources": len(bounded),
            "sources_available": available,
        },
        "sources": bounded,
        "truncated": available > len(bounded),
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
    parser.add_argument(
        "--max-sources",
        type=int,
        default=DEFAULT_MAX_SOURCES,
        help=f"Most recent sources to include (default: {DEFAULT_MAX_SOURCES})",
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

    payload = build(
        vault, note=Path(args.note), as_of=as_of, max_sources=args.max_sources
    )
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
