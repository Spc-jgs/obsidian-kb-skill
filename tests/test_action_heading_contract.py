"""Tests for action heading contract and synonym resolution."""
from __future__ import annotations

import pytest

from obsidian_kb_skill.scripts.action_heading_contract import (
    ACTION_HEADINGS,
    ACTION_HEADING_SYNONYMS,
    is_action_heading,
    resolve_action_heading,
)


def test_canonical_headings_are_recognized():
    assert is_action_heading("待办事项")
    assert is_action_heading("Tasks")
    assert is_action_heading("下一步行动")
    assert resolve_action_heading("待办事项") == "待办事项"


def test_synonym_headings_are_recognized_and_resolved():
    for synonym in ("今日待办", "待办清单", "临时任务", "TODO", "Todo", "Todos", "备忘事项"):
        assert is_action_heading(synonym), f"{synonym} should be recognized as an action heading"
        assert resolve_action_heading(synonym) == "待办事项"


def test_unrelated_headings_are_rejected():
    assert not is_action_heading("可复用的项目落地检查表")
    assert not is_action_heading("今日记录")
    assert not is_action_heading("今日焦点")
    assert resolve_action_heading("今日记录") is None


def test_action_heading_synonyms_map_to_canonical_headings():
    """Consistency guard: Every synonym must resolve to a valid canonical template heading."""
    for synonym, canonical in ACTION_HEADING_SYNONYMS.items():
        assert canonical in ACTION_HEADINGS, f"Synonym '{synonym}' maps to '{canonical}', which is not in ACTION_HEADINGS"

