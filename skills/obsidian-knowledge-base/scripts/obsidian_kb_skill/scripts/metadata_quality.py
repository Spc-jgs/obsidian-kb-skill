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

LATIN_PLACEHOLDER_PREFIX_RE = re.compile(
    r"^(?:unknown|n/a|na|none|null|todo|tbd)"
    r"(?=$|[\s\W_\u3400-\u9fff])"
)
CJK_PLACEHOLDER_PREFIXES = ("未知", "待补充", "待确认")


def is_meaningful_metadata(value: Any) -> bool:
    """Return whether a required metadata value is more than a vague placeholder."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().lower().split()
    )
    if not normalized or normalized in PLACEHOLDER_VALUES:
        return False
    if LATIN_PLACEHOLDER_PREFIX_RE.match(normalized):
        return False
    return not normalized.startswith(CJK_PLACEHOLDER_PREFIXES)
