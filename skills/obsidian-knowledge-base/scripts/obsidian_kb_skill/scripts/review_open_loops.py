#!/usr/bin/env python3
"""Report the loops a Vault's author left open, without deciding what they mean.

Templates already ask for next actions; nothing ever collected them. `review-projects`
reads project instances only, and an insight note's follow-ups, a meeting's
action items and a capture's next steps stay wherever they were written. This
walks every note and returns the unticked boxes that sit under a heading a
template declared as holding action items.

**Deliberately not a task manager and deliberately not a classifier.** On the
reference Vault the 96 items it returns are visibly of mixed kinds: real next
actions, conditional advice, and open-ended intent with no finishable end
state. Two samples of the same corpus gave opposite impressions of that mix,
which is the reason no severity, no priority and no category is assigned here.
Every item carries its text, path, line, heading and note type so a reader
judges it; the type is reported because it is the one signal that is
mechanically true, not because it grades anything.

What is *not* collected is the other half of the honesty. `可复用的项目落地检查表`
holds fifteen unticked boxes on that Vault and is a reusable question list, not
work in progress — it is out because no template declares it, not because a
heuristic guessed. See `action_heading_contract`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from obsidian_kb_skill.scripts.action_heading_contract import is_action_heading
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.link_graph import blank_code_examples
from obsidian_kb_skill.scripts.note_catalog import MAX_NOTE_BYTES
from obsidian_kb_skill.scripts.search_vault import IGNORED_DIRECTORY_NAMES
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)


SCHEMA_VERSION = "1.0"

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_TYPE = re.compile(r"^type:\s*[\"']?([A-Za-z0-9_-]+)", re.M)
_DATE = re.compile(r"^date:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.M)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_UNTICKED = re.compile(r"^[ \t]*[-*+][ \t]+\[[ \t]\][ \t]*(.*)$")


@dataclass(frozen=True)
class OpenLoop:
    path: str
    note_type: str
    note_date: str | None
    heading: str
    line: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "type": self.note_type,
            "date": self.note_date,
            "heading": self.heading,
            "line": self.line,
            "text": self.text,
        }


def _markdown_files(vault: Path) -> Iterable[Path]:
    for path in sorted(vault.rglob("*.md")):
        relative = path.relative_to(vault)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if any(part in IGNORED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if path.is_file():
            yield path


def _loops_in(text: str) -> Iterable[tuple[int, str, str]]:
    """Yield `(line, heading, item)` for unticked boxes under action headings.

    Code is blanked line by line rather than dropped, so line numbers stay
    addressable — a `- [ ]` inside a fenced block is an example, and a reader
    sent to the wrong line would have to find that out themselves. The masker
    is `link_graph`'s, already used by the audit and by `explore-neighborhood`;
    a fourth hand-written fence scanner is the defect this project keeps
    finding.

    **Decide on the blanked copy, read from the original** — the pattern #189
    established. `blank_code_examples` also empties *inline* code, so taking
    the text from it turns `用 `/mcp` 命令验证 MCP 连接` into `用  命令验证 MCP
    连接`: a task stripped of the command it is about. One index addresses both
    copies, so the fence logic is still the only thing deciding what is code.
    """
    original = text.splitlines()
    blanked = blank_code_examples(text).splitlines()
    heading = ""
    for number, (masked, raw) in enumerate(zip(blanked, original), start=1):
        match = _HEADING.match(masked)
        if match:
            # The heading text also comes from the original, for the same
            # reason; a heading holding inline code would otherwise never
            # match the contract.
            raw_heading = _HEADING.match(raw)
            heading = (raw_heading or match).group(2).strip()
            continue
        if not _UNTICKED.match(masked):
            continue
        item = _UNTICKED.match(raw)
        if item and is_action_heading(heading):
            body = item.group(1).strip()
            if body:
                yield number, heading, body


def review_open_loops(
    vault: Path,
    *,
    note_types: tuple[str, ...] = (),
    top_k: int = 50,
) -> dict[str, Any]:
    vault = Path(vault).expanduser().resolve()
    loops: list[OpenLoop] = []
    by_type: dict[str, int] = {}
    scanned = 0
    unreadable: list[dict[str, str]] = []

    for path in _markdown_files(vault):
        relative = path.relative_to(vault).as_posix()
        try:
            if path.stat().st_size > MAX_NOTE_BYTES:
                raise ValueError(f"file exceeds {MAX_NOTE_BYTES} bytes")
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as exc:
            unreadable.append({"path": relative, "reason": str(exc)})
            continue
        scanned += 1
        head = _FRONTMATTER.search(text)
        metadata = head.group(1) if head else ""
        type_match = _TYPE.search(metadata)
        note_type = type_match.group(1) if type_match else "(untyped)"
        if note_types and note_type not in note_types:
            continue
        date_match = _DATE.search(metadata)
        for line, heading, body in _loops_in(text):
            loops.append(
                OpenLoop(
                    path=relative,
                    note_type=note_type,
                    note_date=date_match.group(1) if date_match else None,
                    heading=heading,
                    line=line,
                    text=body,
                )
            )
            by_type[note_type] = by_type.get(note_type, 0) + 1

    # Oldest first: a loop whose note is older has been open longer, and that
    # is the only ordering this can defend. Undated notes sort last rather
    # than being guessed a date, then path and line for determinism.
    loops.sort(key=lambda item: (item.note_date or "9999-99-99", item.path, item.line))

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "review-open-loops",
        "read_only": True,
        "scanned": scanned,
        "summary": {
            "open_loops": len(loops),
            "notes_with_loops": len({item.path for item in loops}),
            "by_type": dict(sorted(by_type.items())),
        },
        "items": [item.as_dict() for item in loops[:top_k]],
        "truncated": len(loops) > top_k,
        "unreadable": unreadable,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report unticked action items across a Vault (read-only).",
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument(
        "--type",
        dest="note_types",
        action="append",
        default=[],
        help="Restrict to a note type; repeatable.",
    )
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = _build_parser().parse_args(argv)
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = review_open_loops(
        vault,
        note_types=tuple(args.note_types),
        top_k=args.top_k,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    summary = report["summary"]
    print(
        f"{summary['open_loops']} open loops across "
        f"{summary['notes_with_loops']} notes ({report['scanned']} scanned)"
    )
    for note_type, count in summary["by_type"].items():
        print(f"  {note_type}\t{count}")
    if report["items"]:
        print()
    for item in report["items"]:
        print(f"{item['date'] or '(undated)'}\t{item['path']}:{item['line']}\t{item['text']}")
    if report["truncated"]:
        print(f"\n(truncated at {len(report['items'])}; pass --top-k for more)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
