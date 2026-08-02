"""Versioned structural baseline for durable article captures."""
from __future__ import annotations

from collections.abc import Sequence


DEEP_CAPTURE_CONTRACT_VERSION = "1.20"
# The release that introduced this structural baseline (v1.20.1). A note
# written before it is not invalid merely because a later contract added
# sections; see the roadmap's template-upgrade boundary.
DEEP_CAPTURE_CONTRACT_EFFECTIVE_DATE = "2026-07-27"
DEEP_CAPTURE_HEADING_VARIANTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "zh-CN",
        (
            "来源与结论",
            "问题、前提与适用边界",
            "核心知识与原理",
            "具体做法与示例",
            "验证、风险与限制",
            "理解与启发",
            "关联笔记",
        ),
    ),
    (
        "en",
        (
            "Source and Conclusion",
            "Problem, Prerequisites, and Boundaries",
            "Core Knowledge and Rationale",
            "Procedure and Worked Example",
            "Verification, Risks, and Limitations",
            "Interpretation and Insights",
            "Related Notes",
        ),
    ),
)


def contains_ordered_headings(
    actual: Sequence[str],
    required: Sequence[str],
) -> bool:
    """Return whether every required heading occurs in order."""
    actual_index = 0
    for heading in required:
        while actual_index < len(actual) and actual[actual_index] != heading:
            actual_index += 1
        if actual_index == len(actual):
            return False
        actual_index += 1
    return True


def matches_deep_capture_contract(actual: Sequence[str]) -> bool:
    """Accept a complete Chinese or English v1.20 deep-capture structure."""
    return any(
        contains_ordered_headings(actual, required)
        for _, required in DEEP_CAPTURE_HEADING_VARIANTS
    )


def formatted_deep_capture_variants() -> str:
    """Return a stable reader-facing representation for audit diagnostics."""
    return " | ".join(
        f"{locale}: {' -> '.join(required)}"
        for locale, required in DEEP_CAPTURE_HEADING_VARIANTS
    )
