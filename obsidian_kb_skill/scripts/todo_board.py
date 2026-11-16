"""Write the one personal board. Listing lives in the retrieval skill."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.backup_policy import DEFAULT_KEEP_PER_NOTE, STAMP_RE
from obsidian_kb_skill.scripts.board_contract import (
    BOARD_PATH,
    BOARD_SECTIONS,
    OPEN_SECTIONS,
    Board,
    BoardMalformed,
    BoardRow,
    contains_due_marker,
    is_civil_date,
    is_clock,
    parse_board,
    render_board,
    spoken_section,
)
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.note_catalog import MAX_NOTE_BYTES
from obsidian_kb_skill.scripts.update_note import backup_note
from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


COMMAND = "todo-board"
FOLDER = "15-Daily"

_SIZE_MESSAGE = "待办.md 超过大小上限，我没有改。"
_SHAPE_MESSAGE = "待办.md 的格式不符合看板规则，我没有改。"
_DATE_MESSAGE = "日期或时间不对，我没有改。"
_TEXT_MESSAGE = "待办正文不对，我没有改。"
_AMBIGUOUS_MESSAGE = "有两条一样的待办，我没有改。"
_NO_MATCH_MESSAGE = "看板上没有这条待办，我没有改。"
_DUPLICATE_MESSAGE = "看板上已经有这条，我没有改。"
_FOLDER_MESSAGE = "15-Daily 还不是目录，我没有建。"


def _refuse(code: str, message: str, details: dict) -> int:
    print(
        json.dumps(
            {"error": {"code": code, "message": message, "details": details}},
            ensure_ascii=False,
        )
    )
    return 2


def _text_reason(text: str | None) -> str | None:
    """Reasons that do not need a valid date. Round-trip is separate."""
    if text is None:
        return "empty"
    if "\n" in text or "\r" in text:
        return "newline"
    if text == "":
        return "empty"
    if text != text.strip() or not text.strip():
        return "whitespace"
    if contains_due_marker(text):
        return "due-marker"
    return None


def _date_parameter(args: argparse.Namespace) -> str | None:
    """The first of ``--today``, ``--due``, ``--at`` that does not fit."""
    if args.today is None or not is_civil_date(args.today):
        return "--today"
    memo = args.operation == "capture" and args.kind == "memo"
    needs_due = args.operation == "reschedule"
    if memo and args.due is not None:
        return "--due"
    if needs_due and (args.due is None or not is_civil_date(args.due)):
        return "--due"
    if args.due is not None and not is_civil_date(args.due):
        return "--due"
    if memo and (args.at is None or not is_clock(args.at)):
        return "--at"
    if not memo and args.at is not None:
        return "--at"
    return None


def _open_line(text: str, due: str | None) -> str:
    if due is None:
        return f"- [ ] {text}"
    return f"- [ ] {text} 📅 {due}"


def _memo_line(today: str, at: str, text: str) -> str:
    return f"- {today} {at} {text}"


def _done_line(today: str, mark: str, text: str) -> str:
    return f"- {today} {mark}：{text}"


def _row_line(row: BoardRow) -> str:
    if row.at is not None:
        return f"- {row.at} {row.text}"
    if row.done_mark is not None:
        return f"- {row.due} {row.done_mark}：{row.text}"
    return _open_line(row.text, row.due)


def _new_line(args: argparse.Namespace) -> tuple[str, str, str | None]:
    """Return the line, the destination section, and the JSON due."""
    if args.operation == "capture" and args.kind == "memo":
        return _memo_line(args.today, args.at, args.text), "备忘", None
    if args.operation == "tick":
        return _done_line(args.today, "勾掉", args.text), "已完成", None
    if args.operation == "cancel":
        return _done_line(args.today, "取消", args.text), "已完成", None
    return _open_line(args.text, args.due), spoken_section(args.due, args.today), args.due


def _round_trips(args: argparse.Namespace) -> bool:
    line, section, _due = _new_line(args)
    try:
        board = parse_board(render_board(args.today, {section: [line]}))
    except BoardMalformed:
        return False
    rows = board.rows[section]
    if len(rows) != 1 or rows[0].text != args.text:
        return False
    row = rows[0]
    if section == "备忘":
        return row.at == f"{args.today} {args.at}"
    if section == "已完成":
        mark = "勾掉" if args.operation == "tick" else "取消"
        return row.due == args.today and row.done_mark == mark
    return row.due == args.due


def _open_matches(board: Board, text: str) -> list[BoardRow]:
    found: list[BoardRow] = []
    for name in OPEN_SECTIONS:
        for row in board.rows[name]:
            if row.text.strip() == text:
                found.append(row)
    return found


def _closed_matches(board: Board, text: str) -> list[BoardRow]:
    found: list[BoardRow] = []
    for name in ("备忘", "已完成"):
        for row in board.rows[name]:
            if row.text.strip() == text:
                found.append(row)
    return found


def _duplicate_details(row: BoardRow, kind: str) -> dict:
    details: dict = {
        "section": row.file_section,
        "line": row.line,
        "text": row.text,
    }
    if kind == "memo":
        details["at"] = row.at
    else:
        details["due"] = row.due
    return details


def _candidate(row: BoardRow) -> dict:
    return {
        "section": row.file_section,
        "line": row.line,
        "text": row.text,
        "due": row.due,
    }


def _match(board: Board | None, args: argparse.Namespace) -> BoardRow | None | int:
    """The named open row, None for capture, or a refusal exit code."""
    if board is None:
        if args.operation == "capture":
            return None
        return _refuse("board-no-match", _NO_MATCH_MESSAGE, {"text": args.text})
    if args.operation == "capture" and args.kind == "memo":
        stamp = f"{args.today} {args.at}"
        found = [
            row
            for row in board.rows["备忘"]
            if row.text.strip() == args.text and row.at == stamp
        ]
    elif args.operation == "capture":
        found = _open_matches(board, args.text)
    else:
        found = _open_matches(board, args.text)
        if not found:
            closed = _closed_matches(board, args.text)
            shown = closed[0].text if len(closed) == 1 else args.text
            return _refuse("board-no-match", _NO_MATCH_MESSAGE, {"text": shown})
        if len(found) > 1:
            return _refuse(
                "board-ambiguous",
                _AMBIGUOUS_MESSAGE,
                {"candidates": [_candidate(row) for row in found]},
            )
        return found[0]
    if len(found) == 1:
        return _refuse(
            "board-duplicate",
            _DUPLICATE_MESSAGE,
            _duplicate_details(found[0], args.kind),
        )
    if len(found) > 1:
        return _refuse(
            "board-ambiguous",
            _AMBIGUOUS_MESSAGE,
            {"candidates": [_candidate(row) for row in found]},
        )
    return None


def _plan(
    board: Board | None, args: argparse.Namespace, named: BoardRow | None
) -> tuple[str, list[dict], str, str | None, str, str | None]:
    rows = {name: [] for name in BOARD_SECTIONS}
    if board is not None:
        for name in BOARD_SECTIONS:
            rows[name] = list(board.rows[name])
    rebucketed: list[dict] = []
    placed: dict[str, list[str]] = {name: [] for name in OPEN_SECTIONS}
    for name in OPEN_SECTIONS:
        for row in rows[name]:
            if (
                named is not None
                and row.line == named.line
                and row.file_section == named.file_section
            ):
                continue
            dest = spoken_section(row.due, args.today)
            if dest != row.file_section:
                rebucketed.append(
                    {
                        "text": row.text,
                        "due": row.due,
                        "from": row.file_section,
                        "to": dest,
                    }
                )
            placed[dest].append(_row_line(row))
    line_text, section, due = _new_line(args)
    body = {
        "今天": placed["今天"],
        "之后": placed["之后"],
        "没定日子": placed["没定日子"],
        "备忘": [_row_line(row) for row in rows["备忘"]],
        "已完成": [_row_line(row) for row in rows["已完成"]],
    }
    body[section].append(line_text)
    frontmatter = None if board is None else board.frontmatter
    rendered = render_board(args.today, body, frontmatter=frontmatter)
    from_section = None if named is None else named.file_section
    return rendered, rebucketed, section, from_section, line_text, due


def _success(
    args: argparse.Namespace,
    *,
    applied: bool,
    existed_before: bool,
    section: str,
    from_section: str | None,
    line_text: str,
    due: str | None,
    rebucketed: list[dict],
    backup: str | None,
    backup_cleanup: dict | None,
) -> int:
    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "ok": True,
                "command": COMMAND,
                "operation": args.operation,
                "kind": args.kind,
                "applied": applied,
                "existed_before": existed_before,
                "path": BOARD_PATH,
                "today": args.today,
                "text": args.text,
                "due": due,
                "section": section,
                "from_section": from_section,
                "line_text": line_text,
                "rebucketed": rebucketed,
                "backup": backup,
                "backup_cleanup": backup_cleanup,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _backup_failed(exc: OSError, *, json_mode: bool) -> int:
    message = f"backup failed: {exc}"
    if json_mode:
        print(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "ok": False,
                    "command": COMMAND,
                    "error": {
                        "code": "BACKUP_FAILED",
                        "message": message,
                        "details": {},
                    },
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    return 3


def _cleanup_board_backups(vault: Path, protected: Path) -> dict:
    """Delete only this board's old timestamped backups. Never the new one."""
    result: dict = {
        "keep_per_note": DEFAULT_KEEP_PER_NOTE,
        "scanned": 0,
        "deleted": 0,
        "warnings": [],
    }
    root = vault / ".obsidian-kb-backups"
    try:
        if not os.path.lexists(root):
            return result
        info = root.lstat()
    except OSError as exc:
        result["warnings"].append(f"cannot inspect backup root: {exc}")
        return result
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        result["warnings"].append(
            "backup root is not a real directory; backup deletion stopped"
        )
        return result
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        result["warnings"].append(f"cannot scan backup root: {exc}")
        return result

    candidates: list[dict] = []
    for entry in entries:
        if not STAMP_RE.fullmatch(entry.name):
            continue
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError as exc:
            result["warnings"].append(f"cannot inspect backup item {entry.name}: {exc}")
            return result
        daily = Path(entry.path) / FOLDER
        board_file = Path(entry.path) / BOARD_PATH
        try:
            daily_info = daily.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            result["warnings"].append(f"cannot inspect backup file: {exc}")
            return result
        # A symlink directory is not a real column of this backup. Do not
        # resolve it: the link may leave the vault.
        if stat.S_ISLNK(daily_info.st_mode) or not stat.S_ISDIR(daily_info.st_mode):
            continue
        try:
            file_info = board_file.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            result["warnings"].append(f"cannot inspect backup file: {exc}")
            return result
        if stat.S_ISLNK(file_info.st_mode) or not stat.S_ISREG(file_info.st_mode):
            continue
        candidates.append(
            {
                "path": board_file,
                "stamp": entry.name,
                "mtime_ns": file_info.st_mtime_ns,
            }
        )

    result["scanned"] = len(candidates)
    try:
        protected_real = protected.resolve()
    except OSError as exc:
        result["warnings"].append(f"cannot verify protected backup: {exc}")
        return result
    match = None
    for candidate in candidates:
        try:
            if candidate["path"].resolve() == protected_real:
                match = candidate
                break
        except OSError as exc:
            result["warnings"].append(f"cannot verify protected backup: {exc}")
            return result
    if match is None:
        result["warnings"].append(
            "protected backup could not be verified; backup deletion stopped"
        )
        return result

    others = [candidate for candidate in candidates if candidate is not match]
    others.sort(
        key=lambda candidate: (
            candidate["mtime_ns"],
            candidate["stamp"],
            candidate["path"].as_posix(),
        ),
        reverse=True,
    )
    keep_extra = max(DEFAULT_KEEP_PER_NOTE - 1, 0)
    for candidate in others[keep_extra:]:
        try:
            candidate["path"].unlink()
        except OSError as exc:
            result["warnings"].append(f"cannot delete old backup: {exc}")
        else:
            result["deleted"] += 1
    return result


def _load(root: Path) -> tuple[Path, bool, bytes | None, Board | None]:
    candidate = root / BOARD_PATH
    if os.path.lexists(candidate):
        note = resolve_existing_within_vault(root, BOARD_PATH, label="path")
        if note.stat().st_size > MAX_NOTE_BYTES:
            raise BoardMalformed("size")
        original = note.read_bytes()
        return note, True, original, parse_board(original.decode("utf-8"))
    return (
        resolve_target_within_vault(root, BOARD_PATH, label="path"),
        False,
        None,
        None,
    )


def _real_folder(parent: Path) -> bool:
    try:
        info = parent.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)


def run(args: argparse.Namespace) -> int:
    root = validate_vault_root(args.vault)
    note, existed, original, board = _load(root)
    matched = _match(board, args)
    if isinstance(matched, int):
        return matched
    rendered, rebucketed, section, from_section, line_text, due = _plan(
        board, args, matched
    )
    encoded = rendered.encode("utf-8")
    if len(encoded) > MAX_NOTE_BYTES:
        raise BoardMalformed("size")
    if not args.apply:
        return _success(
            args,
            applied=False,
            existed_before=existed,
            section=section,
            from_section=from_section,
            line_text=line_text,
            due=due,
            rebucketed=rebucketed,
            backup=None,
            backup_cleanup=None,
        )
    if not existed:
        if not _real_folder(note.parent):
            return _refuse(
                "board-folder-missing",
                _FOLDER_MESSAGE,
                {"path": FOLDER},
            )
        note.write_text(rendered, encoding="utf-8", newline="\n")
        return _success(
            args,
            applied=True,
            existed_before=False,
            section=section,
            from_section=from_section,
            line_text=line_text,
            due=due,
            rebucketed=rebucketed,
            backup=None,
            backup_cleanup=None,
        )
    assert original is not None
    if encoded == original:
        return _success(
            args,
            applied=True,
            existed_before=True,
            section=section,
            from_section=from_section,
            line_text=line_text,
            due=due,
            rebucketed=rebucketed,
            backup=None,
            backup_cleanup=None,
        )
    try:
        # The resolved path can sit behind an in-vault symlink, so its
        # relative path is not BOARD_PATH. Backups and cleanup are keyed on
        # the board's own relative path. read_bytes follows the symlink.
        backup_path = backup_note(root, root / BOARD_PATH)
    except VaultPathError as exc:
        return report_cli_violation(exc, param="backup", json_mode=args.json)
    except OSError as exc:
        return _backup_failed(exc, json_mode=args.json)
    note.write_text(rendered, encoding="utf-8", newline="\n")
    cleanup = _cleanup_board_backups(root, backup_path)
    return _success(
        args,
        applied=True,
        existed_before=True,
        section=section,
        from_section=from_section,
        line_text=line_text,
        due=due,
        rebucketed=rebucketed,
        backup=backup_path.relative_to(root).as_posix(),
        backup_cleanup=cleanup,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write the personal board.")
    parser.add_argument("vault", type=Path)
    parser.set_defaults(kind=None, due=None, at=None)
    commands = parser.add_subparsers(dest="operation", required=True)

    def add_common(command: argparse.ArgumentParser) -> argparse.ArgumentParser:
        command.add_argument("--text", default=None)
        command.add_argument("--today", default=None)
        command.add_argument("--apply", action="store_true")
        command.add_argument("--json", action="store_true")
        return command

    capture = add_common(commands.add_parser("capture"))
    capture.add_argument("--kind", required=True, choices=("todo", "memo"))
    capture.add_argument("--due", default=None)
    capture.add_argument("--at", default=None)
    add_common(commands.add_parser("tick"))
    add_common(commands.add_parser("cancel"))
    reschedule = add_common(commands.add_parser("reschedule"))
    reschedule.add_argument("--due", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = _parser().parse_args(argv)
    reason = _text_reason(args.text)
    if reason is not None:
        return _refuse(
            "board-invalid-text",
            _TEXT_MESSAGE,
            {"parameter": "--text", "reason": reason},
        )
    parameter = _date_parameter(args)
    if parameter is not None:
        return _refuse(
            "board-invalid-date",
            _DATE_MESSAGE,
            {"parameter": parameter},
        )
    if not _round_trips(args):
        return _refuse(
            "board-invalid-text",
            _TEXT_MESSAGE,
            {"parameter": "--text", "reason": "round-trip"},
        )
    try:
        return run(args)
    except BoardMalformed as exc:
        message = _SIZE_MESSAGE if exc.reason == "size" else _SHAPE_MESSAGE
        return _refuse("board-malformed", message, {"reason": exc.reason})
    except VaultPathError as exc:
        return report_cli_violation(exc, param="path", json_mode=args.json)


if __name__ == "__main__":
    sys.exit(main())
