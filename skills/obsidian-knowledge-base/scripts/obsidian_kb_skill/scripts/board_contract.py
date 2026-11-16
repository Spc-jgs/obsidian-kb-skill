"""Grammar of the one personal board, shared by the reader and the writer.

This module does not touch the disk, the clock, or a refusal code. The helpers
that call it decide what an ill-formed board means to the person who asked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re


BOARD_PATH = "15-Daily/待办.md"
BOARD_TYPE = "todo-board"
BOARD_SECTIONS = ("今天", "之后", "没定日子", "备忘", "已完成")
OPEN_SECTIONS = ("今天", "之后", "没定日子")

_DUE_MARKER = re.compile(r" 📅 (\d{4}-\d{2}-\d{2})$")
_DUE_MARKER_ANY = re.compile(r" 📅 \d{4}-\d{2}-\d{2}")
_DATED_OPEN = re.compile(r"^- \[ \] (.*) 📅 (\d{4}-\d{2}-\d{2})$")
_UNDATED_OPEN = re.compile(r"^- \[ \] (.*)$")
_MEMO = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ([0-9]{2}):([0-9]{2}) (.*)$")
_DONE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (勾掉|取消)：(.*)$")
_FENCE = re.compile(r"^(```|~~~)")
_ATX = re.compile(r"^#{1,6}(?:\s|$)")


class BoardMalformed(Exception):
    """The file is not a board. ``reason`` is one of the closed set."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass
class BoardRow:
    file_section: str
    text: str
    line: int
    due: str | None = None
    at: str | None = None
    done_mark: str | None = None


@dataclass
class Board:
    frontmatter: str
    rows: dict[str, list[BoardRow]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in BOARD_SECTIONS:
            self.rows.setdefault(name, [])


def is_civil_date(value: str) -> bool:
    """True when ``value`` is a real ``YYYY-MM-DD`` calendar day."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def is_clock(value: str) -> bool:
    """True when ``value`` is ``HH:MM`` with hours 00–23 and minutes 00–59."""
    matched = re.fullmatch(r"(\d{2}):(\d{2})", value)
    if matched is None:
        return False
    hour = int(matched.group(1))
    minute = int(matched.group(2))
    return hour <= 23 and minute <= 59


def contains_due_marker(text: str) -> bool:
    """True when a date-shaped due marker occurs anywhere in ``text``."""
    return _DUE_MARKER_ANY.search(text) is not None


def comparison_key(text: str) -> str:
    """Drop one trailing due marker from a raw line, then strip.

    ``parse_board`` already stored that marker on ``BoardRow.due`` and left
    the rest in ``row.text``. Matching a parsed row with this function removes
    a second marker that is part of the body, so ``task`` would hit
    ``task 📅 2026-11-01``. Callers compare ``row.text.strip()`` instead.
    """
    return _DUE_MARKER.sub("", text).strip()


def spoken_section(due: str | None, today: str) -> str:
    """The column a dated open row is spoken in. The file is not consulted."""
    if due is None:
        return "没定日子"
    if due <= today:
        return "今天"
    return "之后"


def render_board(
    today: str,
    sections: dict[str, list[str]] | None = None,
    *,
    frontmatter: str | None = None,
) -> str:
    """Render one board. Each heading is followed by one blank line.

    Items in a column have no blank line between them. The file ends with one
    newline. ``frontmatter`` is pasted back unchanged when the caller has one.
    """
    lines_for = sections or {}
    parts = ["# 待办", ""]
    for name in BOARD_SECTIONS:
        parts.append(f"## {name}")
        parts.append("")
        parts.extend(lines_for.get(name, []))
    body = "\n".join(parts) + "\n"
    if frontmatter is None:
        frontmatter = (
            "---\n"
            f"date: {today}\n"
            f"type: {BOARD_TYPE}\n"
            "tags: [todo]\n"
            "related: []\n"
            "---\n\n"
        )
    elif frontmatter.endswith("\n") and not frontmatter.endswith("\n\n"):
        frontmatter = frontmatter + "\n"
    return frontmatter + body


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise BoardMalformed("frontmatter")
    closing = text.find("\n---\n", 3)
    if closing < 0:
        raise BoardMalformed("frontmatter")
    # Keep the closing marker and the single newline that ends it. The blank
    # line the skeleton puts before the title belongs to the body.
    end = closing + len("\n---\n")
    return text[:end], text[end:]


def _frontmatter_inner(frontmatter: str) -> str:
    return frontmatter[len("---\n") : -len("\n---\n")]


def _scalar(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def _mapping(inner: str) -> dict[str, object]:
    data: dict[str, object] = {}
    lines = inner.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line[:1].isspace() or ":" not in line:
            raise BoardMalformed("frontmatter")
        key, rest = line.split(":", 1)
        if not key or any(character.isspace() for character in key):
            raise BoardMalformed("frontmatter")
        if key in data:
            raise BoardMalformed("frontmatter")
        rest = rest.strip()
        if rest == "":
            items: list[str] = []
            index += 1
            while index < len(lines) and lines[index].startswith("  - "):
                items.append(_scalar(lines[index][4:].strip()))
                index += 1
            if not items:
                raise BoardMalformed("frontmatter")
            data[key] = items
            continue
        if rest.startswith("{") or rest.startswith("&") or rest.startswith("*"):
            raise BoardMalformed("frontmatter")
        if rest.startswith("[") and rest.endswith("]"):
            payload = rest[1:-1].strip()
            data[key] = (
                []
                if not payload
                else [_scalar(part.strip()) for part in payload.split(",")]
            )
        else:
            data[key] = _scalar(rest)
        index += 1
    return data


def _require_metadata(metadata: dict[str, object]) -> None:
    date_value = metadata.get("date")
    tags = metadata.get("tags")
    related = metadata.get("related")
    if (
        not isinstance(date_value, str)
        or not is_civil_date(date_value)
        or metadata.get("type") != BOARD_TYPE
        or not isinstance(tags, list)
        or "todo" not in tags
        or not isinstance(related, list)
    ):
        raise BoardMalformed("frontmatter")


def parse_board(text: str) -> Board:
    """Accept only a board. Anything else raises ``BoardMalformed``."""
    frontmatter, body = _split_frontmatter(text)
    metadata = _mapping(_frontmatter_inner(frontmatter))
    _require_metadata(metadata)
    # Body line 1 in the file is the line after the bytes consumed by the
    # frontmatter prefix. ``splitlines`` on the prefix counts those lines.
    offset = len(frontmatter.splitlines())
    rows = _parse_body(body, offset)
    return Board(frontmatter=frontmatter, rows=rows)


def _parse_body(body: str, offset: int) -> dict[str, list[BoardRow]]:
    rows: dict[str, list[BoardRow]] = {name: [] for name in BOARD_SECTIONS}
    title_seen = False
    expected = 0
    current: str | None = None
    for number, line in enumerate(body.splitlines(), start=offset + 1):
        if not line.strip():
            continue
        if _FENCE.match(line):
            raise BoardMalformed("fence")
        if line == "# 待办" and not title_seen:
            title_seen = True
            continue
        if _ATX.match(line):
            name = line[3:] if line.startswith("## ") else ""
            if (
                not title_seen
                or expected >= len(BOARD_SECTIONS)
                or name != BOARD_SECTIONS[expected]
            ):
                raise BoardMalformed("heading")
            current = name
            expected += 1
            continue
        if not title_seen or current is None:
            raise BoardMalformed("heading")
        rows[current].append(_row(current, line, number))
    if not title_seen or expected != len(BOARD_SECTIONS):
        raise BoardMalformed("heading")
    return rows


def _row(section: str, line: str, number: int) -> BoardRow:
    if section in {"今天", "之后"}:
        return _dated_open(section, line, number)
    if section == "没定日子":
        return _undated_open(section, line, number)
    if section == "备忘":
        return _memo(section, line, number)
    return _done(section, line, number)


def _nonempty(text: str) -> str:
    if not text.strip():
        raise BoardMalformed("pattern")
    return text


def _dated_open(section: str, line: str, number: int) -> BoardRow:
    matched = _DATED_OPEN.fullmatch(line)
    if matched is None or not is_civil_date(matched.group(2)):
        raise BoardMalformed("pattern")
    return BoardRow(
        file_section=section,
        text=_nonempty(matched.group(1)),
        due=matched.group(2),
        line=number,
    )


def _undated_open(section: str, line: str, number: int) -> BoardRow:
    if _DUE_MARKER.search(line) or _DATED_OPEN.fullmatch(line):
        raise BoardMalformed("pattern")
    matched = _UNDATED_OPEN.fullmatch(line)
    if matched is None:
        raise BoardMalformed("pattern")
    return BoardRow(
        file_section=section,
        text=_nonempty(matched.group(1)),
        line=number,
    )


def _memo(section: str, line: str, number: int) -> BoardRow:
    matched = _MEMO.fullmatch(line)
    if matched is None or not is_civil_date(matched.group(1)):
        raise BoardMalformed("pattern")
    hour = int(matched.group(2))
    minute = int(matched.group(3))
    if hour > 23 or minute > 59:
        raise BoardMalformed("pattern")
    text = _nonempty(matched.group(4))
    return BoardRow(
        file_section=section,
        text=text,
        at=f"{matched.group(1)} {matched.group(2)}:{matched.group(3)}",
        line=number,
    )


def _done(section: str, line: str, number: int) -> BoardRow:
    if "勾掉:" in line or "取消:" in line:
        raise BoardMalformed("pattern")
    matched = _DONE.fullmatch(line)
    if matched is None or not is_civil_date(matched.group(1)):
        raise BoardMalformed("pattern")
    return BoardRow(
        file_section=section,
        text=_nonempty(matched.group(3)),
        due=matched.group(1),
        done_mark=matched.group(2),
        line=number,
    )
