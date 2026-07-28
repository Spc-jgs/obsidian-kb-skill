"""Content-bound semantic receipt validation."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.capture_receipt import (
    CaptureReceiptError,
    load_receipt_file,
    receipt_sha256,
    requires_capture_receipt,
    validate_capture_receipt,
)


SOURCE = "https://example.com/workflow"


def candidate() -> str:
    return (
        "---\n"
        f"source: {SOURCE}\n"
        "author: 示例作者\n"
        "published: 2026-07-28\n"
        "type: web-clip\n"
        "tags: [web-clip]\n"
        "---\n\n"
        "# 工作流\n\n"
        "## 来源与结论\n\n"
        "来源结论。\n\n"
        "## 问题、前提与适用边界\n\n"
        "### 适用边界\n\n"
        "仅适用于作者描述的个人项目。\n\n"
        "### 反例\n\n"
        "若任务每天都变，固定工具映射反而增加维护成本。\n\n"
        "## 核心知识与原理\n\n"
        "### 因果链\n\n"
        "稳定任务分工减少重复切换。\n\n"
        "## 具体做法与示例\n\n"
        "### 应用方法\n\n"
        "记录任务、匹配工具、定义验收，然后连续复盘。\n\n"
        "## 验证、风险与限制\n\n"
        "作者自述：交付周期从 12 天压缩至 5 天；原文未提供样本。\n\n"
        "## 理解与启发\n\n"
        "本文推导：流程设计比工具熟练度更可迁移。\n\n"
        "## 关联笔记\n"
    )


def valid_receipt(rendered: str | None = None) -> dict[str, object]:
    text = rendered or candidate()
    return {
        "schema_version": 1,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "profile": "conceptual-opinion",
        "source_access": "complete",
        "primary_sources": [SOURCE],
        "supplemental_sources": [],
        "material_items": [
            {
                "id": "causal-chain",
                "kind": "causal-claim",
                "source": SOURCE,
                "note_anchor": "### 因果链",
                "status": "resolved",
            },
            {
                "id": "application-method",
                "kind": "application-method",
                "source": SOURCE,
                "note_anchor": "### 应用方法",
                "status": "resolved",
            },
            {
                "id": "boundary",
                "kind": "boundary",
                "source": SOURCE,
                "note_anchor": "### 适用边界",
                "status": "resolved",
            },
            {
                "id": "counterexample",
                "kind": "counterexample",
                "source": SOURCE,
                "note_anchor": "### 反例",
                "status": "resolved",
            },
        ],
        "numeric_claims": [
            {
                "note_excerpt": (
                    "作者自述：交付周期从 12 天压缩至 5 天；原文未提供样本。"
                ),
                "provenance": "source-self-report",
                "source": SOURCE,
                "measurement_context": "作者自述；原文未提供样本和统计周期",
            }
        ],
        "inferences": [
            {
                "note_excerpt": "本文推导：流程设计比工具熟练度更可迁移。",
                "basis": "原文对比了稳定任务分工和频繁工具切换",
                "label": "本文推导",
            }
        ],
        "practical_artifact": {
            "kind": "application-method",
            "note_anchor": "### 应用方法",
        },
        "unresolved_items": [],
    }


def test_valid_receipt_is_bound_and_summarized():
    rendered = candidate()
    receipt = valid_receipt(rendered)

    result = validate_capture_receipt(
        receipt, rendered, candidate_source=SOURCE
    )

    assert result == {
        "ok": True,
        "schema_version": 1,
        "sha256": receipt_sha256(receipt),
        "content_sha256": receipt["content_sha256"],
        "profiles": ["conceptual-opinion"],
        "primary_source_count": 1,
        "supplemental_source_count": 0,
        "material_item_count": 4,
        "numeric_claim_count": 1,
        "inference_count": 1,
        "unresolved_item_count": 0,
    }


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda item: item.update(content_sha256="0" * 64),
            "capture-receipt-content-mismatch",
        ),
        (
            lambda item: item.update(source_access="partial"),
            "incomplete-source-access",
        ),
        (
            lambda item: item.update(unresolved_items=["measurement method"]),
            "unresolved-material-items",
        ),
        (
            lambda item: item["material_items"][0].update(note_anchor="missing"),
            "missing-receipt-anchor",
        ),
        (
            lambda item: item["numeric_claims"][0].update(
                measurement_context="TODO"
            ),
            "missing-measurement-context",
        ),
        (
            lambda item: item.update(numeric_claims=[]),
            "uncovered-numeric-claim",
        ),
        (
            lambda item: item["inferences"][0].update(label="TODO"),
            "unlabeled-inference",
        ),
        (
            lambda item: item.update(practical_artifact=None),
            "missing-practical-artifact",
        ),
    ],
)
def test_receipt_failures_are_stable(mutate, code):
    receipt = copy.deepcopy(valid_receipt())
    mutate(receipt)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(
            receipt, candidate(), candidate_source=SOURCE
        )

    assert caught.value.code == code


def test_metric_detection_ignores_dates_urls_and_code_but_covers_ratios():
    rendered = candidate().replace(
        "来源结论。",
        (
            "来源结论。链接 https://example.com/2026/12；"
            "代码 `timeout=30s`；正文判断为 70/30。"
        ),
    )
    receipt = valid_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "uncovered-numeric-claim"
    assert caught.value.details["values"] == ["70/30"]


def test_receipt_file_supports_long_or_shell_unsafe_json(tmp_path: Path):
    path = tmp_path / "receipt.json"
    expected = valid_receipt()
    path.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")

    assert load_receipt_file(path) == expected


def test_receipt_file_rejects_symlink(tmp_path: Path):
    target = tmp_path / "receipt.json"
    target.write_text(json.dumps(valid_receipt()), encoding="utf-8")
    link = tmp_path / "alias.json"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlink creation unavailable: {exc}")

    with pytest.raises(CaptureReceiptError) as caught:
        load_receipt_file(link)

    assert caught.value.code == "invalid-capture-receipt-file"


def test_receipt_rejects_invalid_copyable_skill_frontmatter():
    rendered = candidate().replace(
        "### 应用方法\n\n",
        (
            "### 应用方法\n\n"
            "```bash\n"
            "cat > .claude/skills/reviewer/SKILL.md << 'EOF'\n"
            "---\n"
            "name: reviewer\n"
            "description: Review Java code.\n"
            "Use when the user asks for review.\n"
            "---\n"
            "# Reviewer\n"
            "EOF\n"
            "```\n\n"
        ),
    )
    receipt = valid_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "invalid-copyable-skill-frontmatter"


def test_receipt_accepts_valid_copyable_skill_frontmatter():
    rendered = candidate().replace(
        "### 应用方法\n\n",
        (
            "### 应用方法\n\n"
            "```bash\n"
            "cat > .claude/skills/reviewer/SKILL.md << 'EOF'\n"
            "---\n"
            "name: reviewer\n"
            "description: >-\n"
            "  Review Java code. Use when the user asks for review.\n"
            "---\n"
            "# Reviewer\n"
            "EOF\n"
            "```\n\n"
        ),
    )

    result = validate_capture_receipt(
        valid_receipt(rendered), rendered, candidate_source=SOURCE
    )

    assert result["ok"] is True


def test_receipt_does_not_treat_a_skill_directory_tree_as_copyable_frontmatter():
    rendered = candidate().replace(
        "### 应用方法\n\n",
        (
            "### 应用方法\n\n"
            "```text\n"
            ".claude/skills/reviewer/\n"
            "└── SKILL.md\n"
            "```\n\n"
        ),
    )

    result = validate_capture_receipt(
        valid_receipt(rendered), rendered, candidate_source=SOURCE
    )

    assert result["ok"] is True


@pytest.mark.parametrize(
    ("note_type", "folder", "expected"),
    [
        ("web-clip", "20-Learning/AI-Agent", True),
        ("web-clip", "00-Inbox", False),
        ("web-clip", "00-Inbox/Unread", False),
        ("learning-note", "20-Learning", False),
    ],
)
def test_receipt_routing(note_type, folder, expected):
    assert requires_capture_receipt(note_type, folder) is expected


def test_standalone_helper_validates_in_vault_candidate(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "20-Learning").mkdir()
    note = vault / "20-Learning" / "candidate.md"
    note.write_text(candidate(), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.capture_receipt",
            str(vault),
            "--content-file",
            "20-Learning/candidate.md",
            "--receipt-json",
            json.dumps(valid_receipt(), ensure_ascii=False),
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_standalone_helper_rejects_outside_candidate(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text(candidate(), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.capture_receipt",
            str(vault),
            "--content-file",
            str(outside),
            "--receipt-json",
            json.dumps(valid_receipt(), ensure_ascii=False),
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "outside the vault" in result.stdout.lower()
