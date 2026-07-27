"""Mechanical metadata-quality checks shared by create and audit paths."""
from __future__ import annotations

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


def is_meaningful_metadata(value: Any) -> bool:
    """Return whether a required metadata value is more than a vague placeholder."""
    if not isinstance(value, str):
        return False
    normalized = " ".join(value.strip().lower().split())
    return bool(normalized) and normalized not in PLACEHOLDER_VALUES
