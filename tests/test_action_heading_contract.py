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
    """Synonym values are canonical headings, and the scanner actually consults the table.

    An empty table must fail. A loop over ``items()`` does not: zero iterations
    is a passing test that is not looking at anything.
    """
    assert ACTION_HEADING_SYNONYMS, (
        "ACTION_HEADING_SYNONYMS is empty, so this guard is not watching the widening"
    )
    canonical = set(ACTION_HEADINGS)
    assert set(ACTION_HEADING_SYNONYMS.values()) <= canonical
    for synonym, resolved in ACTION_HEADING_SYNONYMS.items():
        assert is_action_heading(synonym), synonym
        assert resolve_action_heading(synonym) == resolved
        assert resolved in canonical

