"""Read the one personal board. This command never writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from obsidian_kb_skill.scripts.board_contract import (
    BOARD_PATH,
    OPEN_SECTIONS,
    Board,
    BoardMalformed,
    is_civil_date,
    parse_board,
    spoken_section,
)
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.note_catalog import MAX_NOTE_BYTES
from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


COMMAND = "list-board"


def _refuse(code: str, message: str, details: dict) -> int:
    print(
        json.dumps(
            {"error": {"code": code, "message": message, "details": details}},
            ensure_ascii=False,
        )
    )
    return 2


def _base(today: str, view: str, exists: bool) -> dict:
    return {
        "schema_version": "1.0",
        "ok": True,
        "command": COMMAND,
        "read_only": True,
        "path": BOARD_PATH,
        "today": today,
        "exists": exists,
        "view": view,
    }


def _todos(board: Board | None, today: str, exists: bool) -> dict:
    sections = {name: [] for name in OPEN_SECTIONS}
    misplaced: list[dict] = []
    if board is not None:
        for name in OPEN_SECTIONS:
            for row in board.rows[name]:
                spoken = spoken_section(row.due, today)
                item = {
                    "text": row.text,
                    "due": row.due,
                    "line": row.line,
                    "file_section": name,
                }
                sections[spoken].append(item)
                if row.due is not None and spoken != name:
                    misplaced.append({**item, "spoken_section": spoken})
    payload = _base(today, "todos", exists)
    payload["counts"] = {name: len(sections[name]) for name in OPEN_SECTIONS}
    payload["sections"] = sections
    payload["misplaced"] = misplaced
    return payload


def _memos(board: Board | None, today: str, exists: bool) -> dict:
    rows = [] if board is None else list(board.rows["备忘"])
    rows.sort(key=lambda row: (row.at or "", row.line), reverse=True)
    payload = _base(today, "memos", exists)
    payload["count"] = len(rows)
    payload["memos"] = [
        {"text": row.text, "at": row.at, "line": row.line} for row in rows
    ]
    return payload


def list_board(vault: Path, today: str, view: str) -> dict:
    """Return one view of the board. The file is not created or rewritten."""
    root = validate_vault_root(vault)
    candidate = root / BOARD_PATH
    if os.path.lexists(candidate):
        resolve_existing_within_vault(root, BOARD_PATH, label="path")
    else:
        resolve_target_within_vault(root, BOARD_PATH, label="path")
        return _todos(None, today, False) if view == "todos" else _memos(None, today, False)
    if candidate.stat().st_size > MAX_NOTE_BYTES:
        raise BoardMalformed("size")
    board = parse_board(candidate.read_text(encoding="utf-8"))
    if view == "todos":
        return _todos(board, today, True)
    return _memos(board, today, True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read the personal board.")
    parser.add_argument("vault", type=Path)
    parser.add_argument("--today", default=None)
    parser.add_argument("--view", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = _parser().parse_args(argv)
    if args.view not in {"todos", "memos"}:
        return _refuse(
            "board-invalid-view",
            "这不是列出待办或备忘，我没有读别的。",
            {"parameter": "--view"},
        )
    if args.today is None or not is_civil_date(args.today):
        return _refuse(
            "board-invalid-date",
            "日期或时间不对，我没有改。",
            {"parameter": "--today"},
        )
    try:
        payload = list_board(args.vault, args.today, args.view)
    except BoardMalformed as exc:
        message = (
            "待办.md 超过大小上限，我没有改。"
            if exc.reason == "size"
            else "待办.md 的格式不符合看板规则，我没有改。"
        )
        return _refuse("board-malformed", message, {"reason": exc.reason})
    except VaultPathError as exc:
        return report_cli_violation(exc, param="path", json_mode=args.json)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
