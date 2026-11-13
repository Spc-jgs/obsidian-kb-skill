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
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.resource_locator import template_dir
from obsidian_kb_skill.scripts.template_contract import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)


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

    # Builtin fallback
    return (
        f"---\n"
        f"date: \"{date_str}\"\n"
        f"type: daily-note\n"
        f"tags: [daily]\n"
        f"related: []\n"
        f"---\n\n"
        f"# {date_str} 日记\n\n"
        f"## 今日焦点\n\n"
        f"## 今日记录\n\n"
        f"## 待办事项\n\n"
        f"- [ ] \n\n"
        f"## 今日复盘\n"
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


def _backup_file(vault: Path, rel_path: str, content_bytes: bytes) -> Path:
    """Save a snapshot of the file before mutating."""
    today = datetime.now().strftime("%Y-%m-%d")
    backup_path = vault / ".obsidian-kb-backups" / today / rel_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(content_bytes)
    return backup_path


def append_entry(
    vault: Path | str,
    *,
    target: str = "daily",
    file: str | None = None,
    date: str | None = None,
    section: str = "待办事项",
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
        rel_path = file.replace("\\", "/").lstrip("/")
    elif target == "daily":
        rel_path = f"15-Daily/{target_date}.md"
    else:
        rel_path = target.replace("\\", "/").lstrip("/")

    full_path = vault / rel_path
    created_file = False
    existing_bytes: bytes | None = None

    if full_path.is_file():
        existing_bytes = full_path.read_bytes()
        text = existing_bytes.decode("utf-8")
    else:
        if target == "daily" or rel_path.startswith("15-Daily/"):
            text = _resolve_daily_template(vault, target_date)
            created_file = True
        else:
            raise FileNotFoundError(f"target note {rel_path} does not exist in vault")

    formatted = _format_entry(entry, is_todo=is_todo, timestamp=timestamp)
    lines = text.splitlines()

    # Locate target section
    section_name = section.strip()
    target_idx: int | None = None
    target_level: int = 2

    for idx, line in enumerate(lines):
        m = _HEADING.match(line)
        if m:
            heading_text = m.group(2).strip()
            # Match directly or by resolved synonym
            syn_h = ACTION_HEADING_SYNONYMS.get(heading_text)
            syn_s = ACTION_HEADING_SYNONYMS.get(section_name)
            if (
                heading_text == section_name
                or (syn_h and syn_h == section_name)
                or (syn_s and syn_s == heading_text)
                or (syn_h and syn_s and syn_h == syn_s)
            ):
                target_idx = idx
                target_level = len(m.group(1))
                break

    inserted_line: int
    if target_idx is not None:
        # Scan forward to find the insertion point within this section
        insert_at = len(lines)
        for idx in range(target_idx + 1, len(lines)):
            m = _HEADING.match(lines[idx])
            if m and len(m.group(1)) <= target_level:
                insert_at = idx
                break

        # Check if there is an empty todo placeholder (e.g. `- [ ] `) in this section
        replaced = False
        for idx in range(target_idx + 1, insert_at):
            if _EMPTY_TODO.match(lines[idx]):
                lines[idx] = formatted
                inserted_line = idx + 1
                replaced = True
                break

        if not replaced:
            # Backtrack past trailing blank lines before next heading
            actual_insert = insert_at
            while actual_insert > target_idx + 1 and not lines[actual_insert - 1].strip():
                actual_insert -= 1
            lines.insert(actual_insert, formatted)
            inserted_line = actual_insert + 1
    else:
        # Section not found, append section and entry at bottom
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"## {section_name}")
        lines.append("")
        lines.append(formatted)
        inserted_line = len(lines)

    new_text = "\n".join(lines) + "\n"

    if apply:
        if existing_bytes is not None:
            _backup_file(vault, rel_path, existing_bytes)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(new_text, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "append-entry",
        "applied": apply,
        "path": rel_path,
        "section": section_name,
        "entry": formatted,
        "created_file": created_file,
        "line": inserted_line,
    }


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
        default="待办事项",
        help="Section heading to append under (default: 待办事项)",
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
