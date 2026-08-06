"""Shared parsing primitives for leading YAML frontmatter blocks."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# A note's whole body is far more than a metadata reader needs, but a fixed
# character budget is the wrong bound: two callers used 4096 and silently
# returned "no frontmatter" for any note whose block ran longer — dropping its
# tags from cluster counts, and its aliases from link resolution, with no error
# anywhere. Read until the block closes instead, and cap only to stay bounded on
# a file that has no closing delimiter at all.
FRONTMATTER_SCAN_LIMIT = 256 * 1024
_SCAN_CHUNK = 8192


@dataclass(frozen=True)
class FrontmatterIssue:
    code: str
    source: str
    message: str
    line: int | None = None
    column: int | None = None
    context: str | None = None


@dataclass(frozen=True)
class FrontmatterResult:
    present: bool
    metadata: dict[str, Any] | None
    body: str
    normalized_text: str
    issue: FrontmatterIssue | None


def read_frontmatter_head(
    path: Path, *, limit: int = FRONTMATTER_SCAN_LIMIT
) -> str:
    """Return enough of a note's head to hold its complete frontmatter block.

    Returns an empty string when the file cannot be read, which every caller
    already treats as "no metadata".
    """
    collected: list[str] = []
    size = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            while size < limit:
                chunk = handle.read(_SCAN_CHUNK)
                if not chunk:
                    break
                collected.append(chunk)
                size += len(chunk)
                head = "".join(collected)
                normalized = _normalize_text(head)
                if not normalized.startswith("---\n"):
                    return head
                # Require the delimiter to be a complete line. A chunk boundary
                # can end mid-line, and `---` there is not a closing fence.
                if normalized.find("\n---\n", 4) != -1:
                    return head
    except OSError:
        return ""
    return "".join(collected)


def _normalize_text(text: str) -> str:
    return text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _closing_fence(normalized: str) -> tuple[int, int] | None:
    """Return the content end and body start for a closing frontmatter fence."""
    line_start = 4
    while line_start <= len(normalized):
        line_end = normalized.find("\n", line_start)
        if line_end == -1:
            line_end = len(normalized)
            body_start = line_end
        else:
            body_start = line_end + 1

        if normalized[line_start:line_end] == "---":
            content_end = line_start
            if content_end > 4 and normalized[content_end - 1] == "\n":
                content_end -= 1
            return content_end, body_start

        if line_end == len(normalized):
            return None
        line_start = body_start
    return None


def parse_frontmatter(text: str, *, source: str = "input") -> FrontmatterResult:
    """Parse a leading YAML frontmatter block without applying consumer policy."""
    normalized = _normalize_text(text)
    if not (normalized.startswith("---\n") or normalized == "---"):
        return FrontmatterResult(False, None, normalized, normalized, None)

    fence = _closing_fence(normalized) if normalized.startswith("---\n") else None
    if fence is None:
        issue = FrontmatterIssue(
            "unclosed-frontmatter",
            source,
            "frontmatter block is not closed",
            line=1,
            column=1,
        )
        return FrontmatterResult(True, None, normalized, normalized, issue)

    content_end, body_start = fence
    raw = normalized[4:content_end]
    try:
        node = yaml.compose(raw, Loader=yaml.SafeLoader)
        parsed = {} if node is None else yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        issue = FrontmatterIssue(
            "invalid-frontmatter",
            source,
            getattr(exc, "problem", None) or str(exc).splitlines()[0],
            line=mark.line + 2 if mark is not None else None,
            column=mark.column + 1 if mark is not None else None,
            context=getattr(exc, "context", None),
        )
        return FrontmatterResult(True, None, normalized, normalized, issue)

    if not isinstance(parsed, dict):
        mark = node.start_mark
        issue = FrontmatterIssue(
            "frontmatter-not-mapping",
            source,
            "frontmatter must be a YAML mapping",
            line=mark.line + 2,
            column=mark.column + 1,
        )
        return FrontmatterResult(True, None, normalized, normalized, issue)

    return FrontmatterResult(True, parsed, normalized[body_start:], normalized, None)


def portable_yaml_scalars(value: Any) -> Any:
    """Return a recursively copied value using portable YAML scalar types."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: portable_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable_yaml_scalars(item) for item in value]
    return value
