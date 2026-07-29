"""Contracts and realistic routing fixtures for conversation workflows."""
from __future__ import annotations

import json
from pathlib import Path

from obsidian_kb_skill.scripts.conversation_digest_contract import (
    CONVERSATION_DIGEST_CONTRACT_VERSION,
    formatted_conversation_digest_variants,
    matches_conversation_digest_contract,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "core" / "references" / "conversation-digest.md"
HARVEST = ROOT / "core" / "references" / "conversation-harvest.md"
FIXTURES = ROOT / "tests" / "fixtures" / "conversation_workflow_eval_cases.json"


def load_cases() -> list[dict[str, object]]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_digest_contract_accepts_only_complete_localized_structure():
    zh = [
        "恢复卡片",
        "边界与约束",
        "决策与依据",
        "证据与产物",
        "未决事项与下一步",
    ]
    en = [
        "Resume Card",
        "Scope and Constraints",
        "Decisions and Rationale",
        "Evidence and Artifacts",
        "Open Questions and Next Actions",
    ]

    assert CONVERSATION_DIGEST_CONTRACT_VERSION == "2"
    assert matches_conversation_digest_contract(zh)
    assert matches_conversation_digest_contract(en)
    assert not matches_conversation_digest_contract(zh[:-1])
    assert "zh-CN: 恢复卡片 -> 边界与约束" in (
        formatted_conversation_digest_variants()
    )


def test_digest_reference_defines_layered_context_recovery():
    text = REFERENCE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "30-second Resume Card",
        "not a whole-note word limit",
        "Scope and Constraints",
        "Decisions and Rationale",
        "Evidence and Artifacts",
        "Open Questions and Next Actions",
        "verified",
        "inferred",
        "open",
        "Task Memory",
        "immutable snapshot",
    ):
        assert marker in normalized

    assert "250 words" not in text
    assert "Frontmatter carries the load" not in text


def test_harvest_reference_defines_value_gate_and_write_boundary():
    text = HARVEST.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "analysis and routing workflow",
        "not a note type",
        "Problem",
        "Reusable Knowledge",
        "Reflection",
        "Design",
        "verified",
        "inferred",
        "open",
        "skip",
        "at least two",
        "One high-value candidate",
        "Multiple independent candidates",
        "No durable candidate",
        "at most one note",
    ):
        assert marker in normalized


def test_eval_cases_cover_digest_task_memory_and_harvest_routes():
    cases = load_cases()

    assert {case["expected_route"] for case in cases} == {
        "conversation-digest",
        "task-memory",
        "conversation-harvest",
    }
    assert {case["id"] for case in cases} == {
        "architecture-discussion",
        "bug-investigation",
        "active-task-handoff",
        "knowledge-harvest",
    }
    for case in cases:
        assert str(case["intent"]).strip()
        assert len(list(case["required_context"])) >= 6


def test_routing_references_cover_every_eval_route():
    digest = REFERENCE.read_text(encoding="utf-8")
    harvest = HARVEST.read_text(encoding="utf-8")
    task_memory = (
        ROOT / "core" / "references" / "task-memory.md"
    ).read_text(encoding="utf-8")
    references = {
        "conversation-digest": digest,
        "conversation-harvest": harvest,
        "task-memory": task_memory,
    }

    for case in load_cases():
        assert str(case["expected_route"]) in references
        assert references[str(case["expected_route"])].strip()


def test_user_documentation_explains_design_and_usage_from_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "conversations.md").read_text(encoding="utf-8")

    for text in (readme, readme_en, docs_index):
        assert "docs/conversations.md" in text or "conversations.md" in text
    for marker in (
        "Conversation Digest v2",
        "Conversation Harvest",
        "Task Memory",
        "30 秒",
        "verified",
        "inferred",
        "open",
        "skip",
    ):
        assert marker in guide
