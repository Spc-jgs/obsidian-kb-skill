#!/usr/bin/env python3
"""Mutate open loop checkbox state: complete (tick), cancel, or postpone."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.backup_policy import load_backup_policy, prune_backups
from obsidian_kb_skill.scripts.update_note import backup_note
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    validate_vault_root,
)


SCHEMA_VERSION = "1.0"
_CHECKBOX = re.compile(r"^([ \t]*[-*+][ \t]+)\[([ xX\-/])\][ \t]*(.*)$")


def _snapshot(vault: Path, note_path: Path) -> str:
    backup_path = backup_note(vault, note_path)
    try:
        prune_backups(vault, load_backup_policy(), protected=backup_path)
    except Exception:
        pass
    return backup_path.relative_to(vault).as_posix()


def complete_loop(
    vault: Path | str,
    *,
    path: str,
    line: int,
    action: str = "tick",
    date: str | None = None,
    expected_text: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    vault = validate_vault_root(vault)
    note_path = resolve_existing_within_vault(vault, path, label="target note")
    rel_path = note_path.relative_to(vault).as_posix()
    text = note_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    line_idx = line - 1
    if not (0 <= line_idx < len(lines)):
        raise IndexError(f"line {line} out of range for {rel_path} ({len(lines)} lines)")

    old_line = lines[line_idx]
    m = _CHECKBOX.match(old_line)
    if not m:
        raise ValueError(f"line {line} in {rel_path} is not a checkbox item: '{old_line}'")

    prefix = m.group(1)
    body = m.group(3).strip()

    if expected_text and expected_text not in old_line:
        raise ValueError(f"line {line} does not match expected text '{expected_text}' (found: '{old_line}')")

    target_date = date or datetime.now().strftime("%Y-%m-%d")
    if target_date == "today":
        target_date = datetime.now().strftime("%Y-%m-%d")

    act = action.lower()
    if act in ("tick", "complete", "done"):
        cleaned_body = re.sub(r"[✅⛔]\s*\d{4}-\d{2}-\d{2}", "", body).strip()
        new_line = f"{prefix}[x] {cleaned_body} ✅ {target_date}"
    elif act in ("cancel", "drop"):
        cleaned_body = re.sub(r"[✅⛔]\s*\d{4}-\d{2}-\d{2}", "", body).strip()
        new_line = f"{prefix}[-] {cleaned_body} ⛔ {target_date}"
    elif act in ("postpone", "defer", "reschedule"):
        cleaned_body = re.sub(r"(?:📅|\[due::)\s*\d{4}-\d{2}-\d{2}\]?", "", body).strip()
        new_line = f"{prefix}[ ] {cleaned_body} 📅 {target_date}"
    else:
        raise ValueError(f"unknown action '{action}'; supported: tick, cancel, postpone")

    lines[line_idx] = new_line
    new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    backup = None
    if apply:
        backup = _snapshot(vault, note_path)
        note_path.write_text(new_text, encoding="utf-8")

    result = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "complete-loop",
        "applied": apply,
        "path": rel_path,
        "line": line,
        "action": act,
        "before": old_line,
        "after": new_line,
    }
    if backup is not None:
        result["backup"] = backup
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transition an open loop task state (tick, cancel, postpone).",
    )
    parser.add_argument("vault", type=Path, help="Path to Obsidian vault")
    parser.add_argument("--path", required=True, help="Relative path to target note")
    parser.add_argument("--line", required=True, type=int, help="1-indexed line number of the task")
    parser.add_argument(
        "--action",
        choices=["tick", "cancel", "postpone"],
        default="tick",
        help="Action to perform on the task (default: tick)",
    )
    parser.add_argument("--date", help="Date for completion stamp or postponed due date YYYY-MM-DD")
    parser.add_argument("--expected-text", help="Safety check: substring expected to be in the original line")
    parser.add_argument("--apply", action="store_true", help="Apply modifications to disk (default is dry-run)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON result")
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
        result = complete_loop(
            vault,
            path=args.path,
            line=args.line,
            action=args.action,
            date=args.date,
            expected_text=args.expected_text,
            apply=args.apply,
        )
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--path", json_mode=args.json)
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": {"code": "complete-loop-failed", "message": str(exc)}}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "applied" if result["applied"] else "(dry-run)"
        print(f"{status} [{result['action']}] on line {result['line']}:\n  before: {result['before']}\n   after: {result['after']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
