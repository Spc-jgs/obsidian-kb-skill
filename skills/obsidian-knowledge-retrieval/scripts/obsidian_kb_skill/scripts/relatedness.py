#!/usr/bin/env python3
"""Which notes does this note *depend on*, and what does it say it uses them for.

`explore-neighborhood` (#121) shows every declared link. This answers the
narrower question a reader actually has when following one: of the notes this
note points at, which ones does it lean on — and for what.

The judgement is **not similarity**. #75's evaluation set makes that explicit:
all sixteen of its hard negatives share a *word* with their source and nothing
else — `Release Quality Gate` against `Airport Departure Gates`, `Source Archive
Format` against `Museum Archive Visit`. A lexical scorer ranks every one of them
highly. What separates the sixteen positives is that the source note says, in
its own text, what it uses the target for: it *cites*, *names*, *delegates to*,
*imports*, *follows*, *is expressed as a multiple of*.

So a candidate needs two things at once, in one sentence of the source:

1. an explicit reference to the target, and
2. a phrase from `DEPENDENCY_MARKERS` saying what the reference is for.

A bare link is not a dependency, and a shared topic is not a reference. Both
halves must hold, which is why the negatives score nothing rather than merely
scoring low.

Directional by construction: A saying what it uses B for implies nothing about
B. The two directions are evaluated separately and never mirrored.

Read-only: nothing here writes, moves, or repairs a note, and it proposes rather
than applies — #75 rules out automatic linking outright.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.link_graph import (
    WIKILINK_RE,
    blank_code_examples,
    build_link_index,
    clean_link_target,
    candidate_paths,
)
from obsidian_kb_skill.scripts.note_catalog import (
    EXEMPT_NAMES,
    INDEX_TYPES,
    SOURCE_ARCHIVE_FOLDER,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)

SCHEMA_VERSION = "1.0"
COMMAND = "suggest-directed-links"

DEFAULT_MAX_CANDIDATES = 10

# What "this note leans on that one" sounds like when someone writes it down.
#
# Every entry is taken from an `evidence` line in the frozen v1.30 labels, which
# were written before any scorer existed. Nothing here is a synonym I supplied
# to widen recall: a marker with no label behind it would be a guess dressed as
# a vocabulary, and #75's own risk list rules that out. The English forms are
# what the labels use; the Chinese forms are their direct equivalents, marked as
# such, because this project's Vaults are bilingual and a table that only reads
# one language would silently score half a Vault at zero.
DEPENDENCY_MARKERS: tuple[str, ...] = (
    # pos-01, pos-10 — "cites"
    "cites", "citing", "引用自", "引自",
    # pos-02 — "names ... as"
    "names", "naming", "点名",
    # pos-03 — "delegates ... to"
    "delegates", "delegated", "委托给", "交由",
    # pos-04 — "traced to"
    "traced to", "traces to", "追溯到", "溯源自",
    # pos-05 — "adopted in response to"
    "in response to", "响应于", "因应",
    # pos-06 — "expressed as a multiple of"
    "expressed as", "measured in", "基于", "以…为基准",
    # pos-07 — "references"
    "references", "referencing", "参照", "参考自",
    # pos-08 — "links to ... **for its** verification stage". The dependency is
    # the role, not the link: "links to" alone is what a `See also` list does,
    # and admitting it would make every declared link a dependency, which is
    # `explore-neighborhood`'s job and not this one's.
    "for its", "as its", "作为其", "用作",
    # pos-09 — "selected from"
    "selected from", "选自", "取自",
    # pos-11 — "consumes"
    "consumes", "consuming", "消费自",
    # pos-12 — "imports"
    "imports", "importing", "沿用", "继承自",
    # pos-13 — "branches on"
    "branches on", "依据",
    # pos-14 — "proven with", "uses ... from"
    "proven with", "proven by", "verified by", "由…证明", "据以验证",
    # pos-15 — "follows"
    "follows", "following", "遵循",
    # pos-16 — "fails when"
    "fails when", "当…时失败",
    # Observed in the reference Vault rather than in the labels, and added on
    # the same terms `PROJECT_NOTE_NEXT_ACTION_HEADINGS` uses: a count, and a
    # note of where it was seen. "You need to understand X first" is a
    # dependency by any reading — 5 occurrences across 262 linking lines.
    "前置知识",  # observed ×3, e.g. 20-Learning/Python/…Python高级特性下-迭代器.md
    "前序知识",  # observed ×2, same series
    # Deliberately NOT added, measured in the same pass: `详见` (×4) and `参考`
    # (×2) are pointers, not dependencies — "for details see X" is `See also` in
    # Chinese, and admitting it would readmit every bare mention.
)

# Structural neighbours are not dependencies. An index lists its folder and an
# archive is the captured original — #121 and #133 settled both, and repeating
# the judgement here rather than sharing it would be a third definition.
EXCLUDED_INDEX_NOTE = "index-note"
EXCLUDED_SOURCE_ARCHIVE = "source-archive"

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。．.!?！？;；])\s+|\n")


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": False,
        "read_only": True,
        "error": {"code": code, "message": message},
    }


def _metadata(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_frontmatter(text, source=path.as_posix())
    return None if parsed.issue is not None else (parsed.metadata or {})


def _linkable(vault: Path) -> list[Path]:
    return [
        path
        for path in sorted(vault.rglob("*.md"))
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(vault).parts)
        and path.name not in EXEMPT_NAMES
    ]


def markers_in(text: str) -> list[str]:
    """Which dependency phrases this text uses, in the table's own order."""
    lowered = text.lower()
    return [marker for marker in DEPENDENCY_MARKERS if marker.lower() in lowered]


def _structural(path: Path, vault: Path, metadata: dict[str, Any] | None) -> str | None:
    relative = path.relative_to(vault)
    if (metadata or {}).get("type") in INDEX_TYPES:
        return EXCLUDED_INDEX_NOTE
    if relative.parts[:1] == (SOURCE_ARCHIVE_FOLDER,):
        return EXCLUDED_SOURCE_ARCHIVE
    return None


def _resolve(target: str, source: Path, vault: Path, index) -> Path | None:
    """The one file this name means, or `None` when that is not decidable.

    Ambiguity is not resolved here any more than it is in `explore-neighborhood`:
    proposing a dependency on the wrong note of two with the same name would
    read as something the author declared.
    """
    if "/" in target:
        matches = [p for p in candidate_paths(source, target, vault) if p.is_file()]
    else:
        matches = [p for p in index.matches(target) if p.is_file()]
    unique = sorted({match.resolve() for match in matches})
    return unique[0] if len(unique) == 1 else None


def build(
    vault: Path,
    *,
    note: Path,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict[str, Any]:
    """Propose the notes this one declares a dependency on, with the sentence."""
    vault = vault.resolve()
    source = (vault / note).resolve()
    if not source.is_file():
        return _error("missing-note", f"no such note: {note.as_posix()}")

    index = build_link_index(_linkable(vault))
    text = source.read_text(encoding="utf-8")
    lines = blank_code_examples(text).splitlines()

    candidates: dict[str, dict[str, Any]] = {}
    excluded: dict[str, int] = {}
    linked_without_dependency = 0

    for number, line in enumerate(lines, start=1):
        links = list(WIKILINK_RE.finditer(line))
        if not links:
            continue
        # The dependency phrase has to be in the same sentence as the reference,
        # not merely somewhere in the note. A note whose opening paragraph says
        # "follows" and whose last line links something unrelated has declared
        # nothing about that link.
        for match in links:
            name = clean_link_target(match.group(1))
            if not name:
                continue
            sentence = _sentence_around(line, match.start())
            found = markers_in(sentence)
            if not found:
                linked_without_dependency += 1
                continue
            resolved = _resolve(name, source, vault, index)
            if resolved is None or resolved == source:
                continue
            reason = _structural(resolved, vault, _metadata(resolved))
            if reason is not None:
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            relative = resolved.relative_to(vault).as_posix()
            entry = candidates.get(relative)
            if entry is None or number < entry["line"]:
                candidates[relative] = {
                    "target": relative,
                    "name": name,
                    "line": number,
                    "markers": found,
                    "evidence": sentence.strip()[:400],
                }

    ordered = sorted(
        candidates.values(),
        key=lambda item: (item["line"], item["target"]),
    )
    kept = ordered[:max_candidates]
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": True,
        "read_only": True,
        "note": source.relative_to(vault).as_posix(),
        "candidates": kept,
        "excluded": excluded,
        "truncated": len(ordered) > len(kept),
        "summary": {
            "candidates_available": len(ordered),
            "links_without_a_dependency": linked_without_dependency,
        },
    }


def _sentence_around(line: str, position: int) -> str:
    """The sentence the reference sits in, within its line."""
    pieces = SENTENCE_SPLIT_RE.split(line)
    offset = 0
    for piece in pieces:
        start = line.find(piece, offset)
        if start == -1:
            continue
        if start <= position < start + len(piece):
            return piece
        offset = start + len(piece)
    return line


def _text_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"{payload['error']['code']}: {payload['error']['message']}"
    lines = [f"{payload['note']} — {len(payload['candidates'])} declared dependencies"]
    for item in payload["candidates"]:
        lines.append(f"  {item['target']}  :{item['line']}  ({', '.join(item['markers'])})")
        lines.append(f"      {item['evidence'][:110]}")
    if not payload["candidates"]:
        lines.append("  (none — links without a stated dependency are not proposed)")
    bare = payload["summary"]["links_without_a_dependency"]
    if bare:
        lines.append(f"  {bare} link(s) mentioned without saying what for")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Propose the notes a note declares a dependency on."
    )
    parser.add_argument("vault")
    parser.add_argument("--note", required=True)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.max_candidates < 1:
        parser.error("--max-candidates must be at least 1")

    try:
        root = validate_vault_root(Path(args.vault))
        resolve_target_within_vault(root, Path(args.note), label="note")
    except (InvalidVaultRootError, VaultPathError) as error:
        return report_cli_violation(error, command=COMMAND, as_json=args.json)

    payload = build(root, note=Path(args.note), max_candidates=args.max_candidates)
    print(
        json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json
        else _text_report(payload)
    )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
