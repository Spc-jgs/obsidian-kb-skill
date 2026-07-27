"""Mechanical metadata-quality checks shared by create and audit paths."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


PLACEHOLDER_VALUES = frozenset(
    {
        "unknown",
        "未知",
        "n/a",
        "na",
        "none",
        "null",
        "todo",
        "tbd",
        "待补充",
        "待确认",
    }
)

COMPOUND_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"unknown[\s:;,.!?\-_/\\()\[\]{}]+"
    r"(?:author|source|date|published|publication date|url|link|name|value)\b.*"
    r"|(?:todo|tbd)[\s:;,.!?\-_/\\()\[\]{}]+"
    r"(?:verify|confirm|check|fill|update|replace|add|complete|research|find|"
    r"pending|later)\b.*"
    r"|(?:none|null|n/a|na)[\s:;,.!?\-_/\\()\[\]{}]+"
    r"(?:provided|available|specified|known|given|found|pending|value)\b.*"
    r"|unknown(?:作者|来源|日期|发布日期|链接|网址|名称|值).*$"
    r"|(?:todo|tbd)(?:待确认|待补充|验证|核实|检查).*$"
    r"|(?:未知|待补充|待确认)"
    r"(?:作者|来源|日期|发布日期|链接|网址|字段|信息|内容|值).*$"
    r")$"
)


def is_meaningful_metadata(value: Any) -> bool:
    """Return whether a required metadata value is more than a vague placeholder."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().lower().split()
    )
    if not normalized or normalized in PLACEHOLDER_VALUES:
        return False
    return COMPOUND_PLACEHOLDER_RE.fullmatch(normalized) is None
