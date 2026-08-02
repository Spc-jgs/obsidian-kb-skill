"""Versioned structural baseline for conversation context digests."""
from __future__ import annotations

from collections.abc import Sequence


CONVERSATION_DIGEST_CONTRACT_VERSION = "2"
# The release that introduced the v2 layered structure (v1.24.0). Digests
# written before it keep their original shape without becoming invalid.
CONVERSATION_DIGEST_CONTRACT_EFFECTIVE_DATE = "2026-07-29"
CONVERSATION_DIGEST_HEADING_VARIANTS: tuple[
    tuple[str, tuple[str, ...]], ...
] = (
    (
        "zh-CN",
        (
            "恢复卡片",
            "边界与约束",
            "决策与依据",
            "证据与产物",
            "未决事项与下一步",
        ),
    ),
    (
        "en",
        (
            "Resume Card",
            "Scope and Constraints",
            "Decisions and Rationale",
            "Evidence and Artifacts",
            "Open Questions and Next Actions",
        ),
    ),
)
CONVERSATION_DIGEST_RESUME_FIELD_VARIANTS: dict[str, tuple[str, ...]] = {
    "zh-CN": ("目标", "状态", "当前结论", "下一步", "关键产物"),
    "en": ("Goal", "State", "Current conclusion", "Next step", "Key artifacts"),
}


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


def conversation_digest_locale(actual: Sequence[str]) -> str | None:
    """Return the matching standard locale for a complete v2 structure."""
    for locale, required in CONVERSATION_DIGEST_HEADING_VARIANTS:
        if contains_ordered_headings(actual, required):
            return locale
    return None


def matches_conversation_digest_contract(actual: Sequence[str]) -> bool:
    """Accept a complete Chinese or English conversation-digest v2 structure."""
    return conversation_digest_locale(actual) is not None


def formatted_conversation_digest_variants() -> str:
    """Return stable reader-facing heading diagnostics."""
    return " | ".join(
        f"{locale}: {' -> '.join(required)}"
        for locale, required in CONVERSATION_DIGEST_HEADING_VARIANTS
    )
