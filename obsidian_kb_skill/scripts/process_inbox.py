#!/usr/bin/env python3
"""Propose or apply filing of Obsidian vault Inbox (quick-capture) notes.

Read-only by default (--plan). With --apply, each Inbox note is moved into the
folder inferred from its type or body keywords, missing `date`/`type`/`tags` are
filled, and a link is appended to the destination folder's static INDEX.md (only
when the Folder Index plugin is not enabled). Folder Index and Dataview listings
are never touched.

Reuses shared parsing and vault helpers instead of reimplementing them.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.audit_vault import _note_title
from obsidian_kb_skill.scripts.folder_index_policy import (
    StaticIndexEntry,
    append_static_index_entry,
)
from obsidian_kb_skill.scripts.frontmatter import FrontmatterIssue, parse_frontmatter
from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE,
    FOLDER_TO_DEFAULT_TYPE,
    TYPE_TO_FOLDER,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)

# Trigger keywords (lowercased substrings) -> target folder, used when the type
# is missing or unknown. First match wins.
KEYWORD_ROUTES = [
    (("meeting", "standup", "review", "sync"), "10-Work"),
    (("article", "learning", "book", "course", "tutorial"), "20-Learning"),
    (("web", "url", "blog", "clip"), "20-Learning"),
    (("analysis", "insight", "idea", "takeaway"), "30-Insights"),
    (("project", "milestone", "sprint"), "40-Projects"),
    (("person", "contact", "team"), "50-People"),
]

DEFAULT_TAG_BY_FOLDER = {
    folder: DEFAULT_TAG_BY_TYPE[note_type]
    for folder, note_type in FOLDER_TO_DEFAULT_TYPE.items()
}

INDEX_BASENAME = "INDEX.md"

# Skip code for a note whose frontmatter block exists but cannot be parsed.
UNREADABLE_FRONTMATTER = "unreadable-frontmatter"

# Skip code for an Inbox entry that is not a regular file (symlink, directory).
UNSAFE_INBOX_ENTRY = "unsafe-inbox-entry"


def scan_inbox(inbox: Path) -> tuple[list[Path], list[Path]]:
    """Return (regular notes, unsafe entries) without following symlinks.

    `glob()` and `is_file()` both resolve symlinks, so a link placed in the
    Inbox let an outside file be read and imported — exactly what this command
    states it refuses to do. Unsafe entries are reported rather than skipped
    silently, so the user learns why a file stayed put.
    """
    if not inbox.is_dir():
        return [], []
    safe: list[Path] = []
    unsafe: list[Path] = []
    with os.scandir(inbox) as entries:
        for entry in entries:
            if not entry.name.endswith(".md"):
                continue
            path = Path(entry.path)
            try:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    unsafe.append(path)
                else:
                    safe.append(path)
            except OSError:
                unsafe.append(path)
    return sorted(safe), sorted(unsafe)


def collect_inbox(inbox: Path) -> list[Path]:
    """Regular Inbox notes only. Kept for callers that ignore unsafe entries."""
    return scan_inbox(inbox)[0]


def infer_target(text: str, metadata: dict[str, Any] | None) -> str | None:
    note_type = metadata.get("type") if isinstance(metadata, dict) else None
    if note_type in TYPE_TO_FOLDER:
        return TYPE_TO_FOLDER[note_type]
    haystack = text.lower()
    for keywords, folder in KEYWORD_ROUTES:
        if any(kw in haystack for kw in keywords):
            return folder
    return None


def destination_index_name(vault: Path, target: str) -> str | None:
    folder = vault / target
    if not folder.is_dir():
        return None
    for name in (f"{target}.md", INDEX_BASENAME):
        if (folder / name).is_file():
            return name[:-3]
    return None


def _issue_payload(issue: FrontmatterIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "line": issue.line,
        "column": issue.column,
    }


def plan_note(path: Path, vault: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parsed = parse_frontmatter(text, source=path.as_posix())
    result: dict[str, Any] = {
        "path": path,
        "target": None,
        "title": _note_title(path, text),
    }
    # Fail closed: a frontmatter block we cannot read is not an empty one.
    # Filling defaults over it would discard the user's original keys, and the
    # move then deletes the only copy. Refuse the note and keep it in place.
    if parsed.issue is not None:
        result["skip"] = f"unreadable frontmatter: {parsed.issue.message}"
        result["skip_code"] = UNREADABLE_FRONTMATTER
        result["frontmatter_issue"] = _issue_payload(parsed.issue)
        return result

    metadata = parsed.metadata
    target = infer_target(text, metadata)
    result["target"] = target
    if target is None:
        result["skip"] = "could not infer a target folder"
        result["skip_code"] = "unknown-target"
        return result
    existing_tags = (metadata or {}).get("tags")
    if existing_tags:
        result["tags"] = (
            existing_tags if isinstance(existing_tags, list) else [existing_tags]
        )
    else:
        result["tags"] = [DEFAULT_TAG_BY_FOLDER.get(target, "note")]
    result["type"] = (metadata or {}).get("type") or FOLDER_TO_DEFAULT_TYPE.get(target)
    result["related_suggestion"] = destination_index_name(vault, target)
    return result


def _closing_fence_start(text: str) -> int | None:
    """Index where the closing `---` line of a frontmatter block starts."""
    if not text.startswith("---\n"):
        return None
    position = 4
    while position <= len(text):
        newline = text.find("\n", position)
        line_end = len(text) if newline == -1 else newline
        if text[position:line_end] == "---":
            return position
        if newline == -1:
            return None
        position = newline + 1
    return None


def _fill_frontmatter(text: str, updates: dict[str, Any]) -> str:
    """Insert the missing keys without rewriting the existing block.

    Re-dumping the whole mapping through yaml.safe_dump silently discarded
    comments and rewrote indentation and quoting, so a note lost content the
    user had written even when nothing was wrong with it.
    """
    if not updates:
        return text
    rendered = yaml.safe_dump(
        updates, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    fence = _closing_fence_start(text)
    if fence is None:
        return f"---\n{rendered}\n---\n{text}"
    return f"{text[:fence]}{rendered}\n{text[fence:]}"


def apply_plan(plan: dict[str, Any], vault: Path, silent: bool = False) -> bool:
    """Move one planned note. Return True only when the move committed."""
    if plan.get("skip"):
        if not silent:
            print(f"  skip: {plan['path'].as_posix()} — {plan['skip']}")
        return False
    source = plan["path"]
    dest_folder = vault / plan["target"]
    dest = dest_folder / source.name
    if dest.exists():
        print(f"  skip (target exists): {dest.as_posix()}", file=sys.stderr)
        return False
    text = source.read_text(encoding="utf-8")
    parsed = parse_frontmatter(text, source=source.as_posix())
    # Re-check at write time: the file may have changed since it was planned.
    if parsed.issue is not None:
        print(
            f"  skip (unreadable frontmatter): {source.as_posix()} — "
            f"{parsed.issue.message}",
            file=sys.stderr,
        )
        return False
    metadata = parsed.metadata

    dest_folder.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    updates: dict[str, Any] = {}
    if not (metadata and metadata.get("date")):
        updates["date"] = today
    if not (metadata and metadata.get("type")):
        updates["type"] = plan["type"]
    if not (metadata and metadata.get("tags")):
        updates["tags"] = plan["tags"]
    dest.write_bytes(_fill_frontmatter(text, updates).encode("utf-8"))
    try:
        source.unlink()
    except OSError as exc:
        # The copy is written but the original survives. Roll the copy back so
        # the note never exists in two places with divergent frontmatter.
        print(
            f"  skip (cannot remove source): {source.as_posix()} — {exc}",
            file=sys.stderr,
        )
        try:
            dest.unlink()
        except OSError as cleanup_exc:
            print(
                f"  warning: could not roll back {dest.as_posix()} — "
                f"{cleanup_exc}; remove it manually",
                file=sys.stderr,
            )
        return False
    append_static_index_entry(
        vault,
        StaticIndexEntry(
            note=dest.relative_to(vault),
            title=plan.get("title") or dest.stem,
            date=today,
        ),
    )
    if not silent:
        print(f"  moved: {source.as_posix()} -> {dest.as_posix()}")
    return True


def process_vault(
    vault: Path,
    apply: bool,
    inbox_name: str = "00-Inbox",
    silent: bool = False,
) -> list[dict[str, Any]]:
    vault = vault.resolve()
    inbox = vault / inbox_name
    sources, unsafe = scan_inbox(inbox)
    plans = [plan_note(path, vault) for path in sources]
    plans.extend(
        {
            "path": path,
            "target": None,
            "title": path.stem,
            "skip": "unsafe Inbox entry: not a regular file",
            "skip_code": UNSAFE_INBOX_ENTRY,
        }
        for path in unsafe
    )
    plans.sort(key=lambda plan: plan["path"].as_posix())
    if apply:
        for plan in plans:
            if plan.get("skip"):
                # Refusals must stay visible; --apply is where it matters most.
                if not silent:
                    print(
                        f"  skip: {plan['path'].as_posix()} — {plan['skip']}",
                        file=sys.stderr,
                    )
                plan["applied"] = False
                continue
            plan["applied"] = apply_plan(plan, vault, silent=silent)
    return plans


def _format_plan(plan: dict[str, Any]) -> str:
    if plan.get("skip"):
        return f"  SKIP  {plan['path'].as_posix()} — {plan['skip']}"
    tags = ", ".join(plan["tags"])
    related = plan.get("related_suggestion")
    rel_hint = f" related→[[{related}]]" if related else ""
    return (
        f"  FILE  {plan['path'].as_posix()}\n"
        f"        -> {plan['target']}/{plan['path'].name}\n"
        f"        type={plan['type']} tags=[{tags}]{rel_hint}"
    )


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Propose or apply filing of Obsidian vault Inbox notes."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--plan", action="store_true", help="Print the filing plan only (default)"
    )
    mode.add_argument(
        "--apply", action="store_true", help="Move and file notes (never overwrites)"
    )
    parser.add_argument("--inbox", default="00-Inbox", help="Inbox folder name")
    parser.add_argument(
        "--json", action="store_true", help="Emit the plan(s) as JSON instead of text"
    )
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2

    # The Inbox folder must live inside the Vault. Reading from an external
    # directory is rejected by default (no silent import of outside files).
    try:
        resolve_target_within_vault(vault, args.inbox, label="--inbox")
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--inbox", json_mode=args.json)

    plans = process_vault(vault, apply=args.apply, inbox_name=args.inbox, silent=args.json)
    if args.json:
        serial = [
            {k: (v.as_posix() if isinstance(v, Path) else v) for k, v in plan.items()}
            for plan in plans
        ]
        print(json.dumps(serial, ensure_ascii=False, indent=2))
        return 0
    if not args.apply:
        for plan in plans:
            print(_format_plan(plan))
        print(f"{len(plans)} Inbox note(s) planned.")
        return 0

    # Report what actually committed, not how many notes were examined.
    applied = sum(1 for plan in plans if plan.get("applied"))
    print(f"{applied} Inbox note(s) applied.")
    refused = len(plans) - applied
    if refused:
        print(f"{refused} Inbox note(s) left in place; see the messages above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
