#!/usr/bin/env python3
"""Atomically append a todo or memo entry to a daily note or specified note section."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

from obsidian_kb_skill.scripts.action_heading_contract import (
    ACTION_HEADING_SYNONYMS,
)
from obsidian_kb_skill.scripts.backup_policy import load_backup_policy, prune_backups
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.resource_locator import template_dir
from obsidian_kb_skill.scripts.template_contract import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.update_note import backup_note
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    PathNotFoundError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


class AppendRejected(Exception):
    """The append was refused. The note is left unchanged."""


SCHEMA_VERSION = "1.0"
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_EMPTY_TODO = re.compile(r"^[ \t]*[-*+][ \t]+\[[ \t]\][ \t]*$")


def _resolve_daily_template(vault: Path, date_str: str) -> str:
    """Find and instantiate the daily note template for date_str."""
    vault_tmpl = vault / "Templates" / TYPE_TO_TEMPLATE.get("daily-note", "Daily Note.md")
    if vault_tmpl.is_file():
        try:
            raw = vault_tmpl.read_text(encoding="utf-8")
            return raw.replace("{{date}}", date_str)
        except (OSError, UnicodeError):
            pass

    try:
        bundled = template_dir() / "daily-note.md"
        if bundled.is_file():
            raw = bundled.read_text(encoding="utf-8")
            return raw.replace("{{date}}", date_str)
    except Exception:
        pass

    raise AppendRejected(
        f"daily note template for {date_str} is missing; refusing to invent a skeleton"
    )


def _format_entry(
    entry: str,
    *,
    is_todo: bool = False,
    timestamp: str | bool | None = None,
) -> str:
    text = entry.strip()
    if is_todo and not re.match(r"^[-*+][ \t]+\[[ \t]\]", text):
        text = f"- [ ] {text}"

    if timestamp:
        time_str = (
            datetime.now().strftime("%H:%M")
            if timestamp is True
            else str(timestamp).strip()
        )
        if text.startswith("- "):
            text = f"- {time_str} {text[2:].strip()}"
        elif not text.startswith("-"):
            text = f"- {time_str} {text}"

    return text


def _match_kind(heading_text: str, section_name: str) -> str | None:
    """Exact heading wins. A synonym matches only against the requested name.

    Two synonyms of the same canonical heading are not the same section. If
    both are present, the caller must name one of them.
    """
    if heading_text == section_name:
        return "exact"
    canonical_heading = ACTION_HEADING_SYNONYMS.get(heading_text)
    canonical_section = ACTION_HEADING_SYNONYMS.get(section_name)
    if canonical_heading == section_name or canonical_section == heading_text:
        return "synonym"
    return None


def _snapshot(vault: Path, note_path: Path) -> str:
    """Timestamped backup, then the same retention pass as update-note."""
    backup_path = backup_note(vault, note_path)
    try:
        prune_backups(vault, load_backup_policy(), protected=backup_path)
    except Exception:
        # The write already has a snapshot. Retention failure must not hide that.
        pass
    return backup_path.relative_to(vault).as_posix()


def append_entry(
    vault: Path | str,
    *,
    target: str = "daily",
    file: str | None = None,
    date: str | None = None,
    section: str | None = None,
    entry: str,
    is_todo: bool = False,
    timestamp: str | bool | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    vault = Path(vault).expanduser().resolve()
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    if target_date == "today":
        target_date = datetime.now().strftime("%Y-%m-%d")

    if file:
        requested = file.replace("\\", "/")
    elif target == "daily":
        requested = f"15-Daily/{target_date}.md"
    else:
        requested = target.replace("\\", "/")

    may_create = target == "daily" or requested.replace("\\", "/").lstrip("/").startswith("15-Daily/")
    try:
        note_path = resolve_existing_within_vault(vault, requested, label="target note")
        created_file = False
    except PathNotFoundError:
        if not may_create:
            raise
        note_path = resolve_target_within_vault(vault, requested, label="target note")
        created_file = True

    rel_path = note_path.relative_to(vault).as_posix()
    if created_file:
        text = _resolve_daily_template(vault, target_date)
    else:
        text = note_path.read_text(encoding="utf-8")

    section_name = (section or "").strip() or ("待办事项" if is_todo else "今日记录")
    formatted = _format_entry(entry, is_todo=is_todo, timestamp=timestamp)
    lines = text.splitlines()

    exact: list[tuple[int, int, str]] = []
    synonyms: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        match = _HEADING.match(line)
        if not match:
            continue
        heading_text = match.group(2).strip()
        kind = _match_kind(heading_text, section_name)
        found = (idx, len(match.group(1)), heading_text)
        if kind == "exact":
            exact.append(found)
        elif kind == "synonym":
            synonyms.append(found)

    chosen = exact or synonyms
    if not chosen:
        raise AppendRejected(f"section {section_name!r} does not exist in {rel_path}")
    if len(chosen) > 1:
        raise AppendRejected(f"section {section_name!r} is ambiguous in {rel_path}")

    target_idx, target_level, matched_heading = chosen[0]
    insert_at = len(lines)
    for idx in range(target_idx + 1, len(lines)):
        match = _HEADING.match(lines[idx])
        if match and len(match.group(1)) <= target_level:
            insert_at = idx
            break

    duplicate_at = next(
        (
            idx
            for idx in range(target_idx + 1, insert_at)
            if lines[idx].strip() == formatted.strip()
        ),
        None,
    )
    if duplicate_at is not None:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "command": "append-entry",
            "applied": False,
            "duplicate": True,
            "path": rel_path,
            "section": section_name,
            "matched_heading": matched_heading,
            "entry": formatted,
            "created_file": False,
            "line": duplicate_at + 1,
        }

    replaced = False
    inserted_line = 0
    for idx in range(target_idx + 1, insert_at):
        if _EMPTY_TODO.match(lines[idx]):
            lines[idx] = formatted
            inserted_line = idx + 1
            replaced = True
            break
    if not replaced:
        actual_insert = insert_at
        while actual_insert > target_idx + 1 and not lines[actual_insert - 1].strip():
            actual_insert -= 1
        lines.insert(actual_insert, formatted)
        inserted_line = actual_insert + 1

    new_text = "\n".join(lines) + "\n"
    backup = None
    if apply:
        if not created_file:
            backup = _snapshot(vault, note_path)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(new_text, encoding="utf-8")

    result = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "append-entry",
        "applied": apply,
        "duplicate": False,
        "path": rel_path,
        "section": section_name,
        "matched_heading": matched_heading,
        "entry": formatted,
        "created_file": created_file,
        "line": inserted_line,
    }
    if backup is not None:
        result["backup"] = backup
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically append a todo or memo entry to a note (daily note by default).",
    )
    parser.add_argument("vault", type=Path, help="Path to Obsidian vault")
    parser.add_argument(
        "--target",
        default="daily",
        help="Target note category or filename (default: daily)",
    )
    parser.add_argument(
        "--file",
        help="Explicit relative path to target note (overrides --target)",
    )
    parser.add_argument(
        "--date",
        help="Date for daily note YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--section",
        default=None,
        help="Section heading to append under (default: 待办事项 with --todo, otherwise 今日记录)",
    )
    parser.add_argument(
        "--entry",
        required=True,
        help="Entry text to append",
    )
    parser.add_argument(
        "--todo",
        action="store_true",
        dest="is_todo",
        help="Ensure entry is formatted as a todo item (- [ ])",
    )
    parser.add_argument(
        "--timestamp",
        nargs="?",
        const=True,
        default=None,
        help="Prepend timestamp HH:MM (defaults to current time if flag passed without value)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply modifications to disk (default is dry-run)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON result",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        if args.json:
            print(json.dumps({"error": {"code": "invalid-vault", "message": str(exc)}}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = append_entry(
            vault,
            target=args.target,
            file=args.file,
            date=args.date,
            section=args.section,
            entry=args.entry,
            is_todo=args.is_todo,
            timestamp=args.timestamp,
            apply=args.apply,
        )
    except VaultPathError as exc:
        return report_cli_violation(
            exc,
            param="--file" if args.file else "--target",
            json_mode=args.json,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": {"code": "append-failed", "message": str(exc)}}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "appended" if result["applied"] else "(dry-run) would append"
        print(f"{status} entry to {result['path']} under [{result['section']}] at line {result['line']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
