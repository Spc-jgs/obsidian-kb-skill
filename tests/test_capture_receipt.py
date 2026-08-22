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
        "capture_depth: verified\n"
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


RESOURCE_A = "https://example.com/tool-a"
RESOURCE_B = "https://example.com/tool-b"


def resource_candidate() -> str:
    return (
        "---\n"
        f"source: {SOURCE}\n"
        "author: 示例作者\n"
        "published: 2026-07-28\n"
        "capture_depth: verified\n"
        "type: web-clip\n"
        "tags: [web-clip]\n"
        "---\n\n"
        "# Resource Survey\n\n"
        "## Resource Inventory\n\n"
        f"Tool A: {RESOURCE_A}\n\n"
        f"Tool B: {RESOURCE_B}\n\n"
        "## Evaluation\n\n"
        "Tool A supports the current LTS runtime and lacks offline mode.\n\n"
        "Tool B supports the previous LTS runtime and lacks Windows support.\n\n"
        "Choose by deployment environment. Start with the Tool A quickstart.\n"
    )


def valid_resource_receipt(rendered: str | None = None) -> dict[str, object]:
    text = rendered or resource_candidate()
    material = [
        ("tool-a-link", "canonical-link", "tool-a", RESOURCE_A),
        (
            "tool-a-compatibility",
            "compatibility",
            "tool-a",
            "Tool A supports the current LTS runtime",
        ),
        (
            "tool-a-limitation",
            "limitation",
            "tool-a",
            "lacks offline mode",
        ),
        ("tool-b-link", "canonical-link", "tool-b", RESOURCE_B),
        (
            "tool-b-compatibility",
            "compatibility",
            "tool-b",
            "Tool B supports the previous LTS runtime",
        ),
        (
            "tool-b-limitation",
            "limitation",
            "tool-b",
            "lacks Windows support",
        ),
    ]
    return {
        "schema_version": 1,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "profile": "resource-survey",
        "source_access": "complete",
        "primary_sources": [SOURCE],
        "supplemental_sources": [],
        "resources": [
            {"id": "tool-a", "name": "Tool A", "canonical_url": RESOURCE_A},
            {"id": "tool-b", "name": "Tool B", "canonical_url": RESOURCE_B},
        ],
        "material_items": [
            {
                "id": item_id,
                "kind": kind,
                "resource_id": resource_id,
                "source": SOURCE,
                "note_anchor": anchor,
                "status": "resolved",
            }
            for item_id, kind, resource_id, anchor in material
        ]
        + [
            {
                "id": "selection",
                "kind": "selection-criteria",
                "source": SOURCE,
                "note_anchor": "Choose by deployment environment",
                "status": "resolved",
            },
            {
                "id": "starting-example",
                "kind": "starting-example",
                "source": SOURCE,
                "note_anchor": "Start with the Tool A quickstart",
                "status": "resolved",
            },
        ],
        "numeric_claims": [],
        "inferences": [],
        "practical_artifact": {
            "kind": "selection-decision",
            "note_anchor": "Choose by deployment environment",
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
            "来源结论。发布于2026年；链接 https://example.com/2026/12；"
            "代码 `timeout=30s`；正文判断为 70/30。"
        ),
    )
    receipt = valid_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "uncovered-numeric-claim"
    assert caught.value.details["values"] == ["70/30"]


@pytest.mark.parametrize(
    ("measurement", "detected"),
    [
        ("3 months", "3 months"),
        ("2 years", "2 years"),
        ("1.2B users", "1.2B"),
        ("2 million users", "2 million"),
        ("覆盖3万用户", "3万"),
        ("处理2亿请求", "2亿"),
    ],
)
def test_common_duration_and_abbreviated_count_units_require_provenance(
    measurement, detected
):
    rendered = candidate().replace("来源结论。", f"来源结论。测量结果为 {measurement}。")
    receipt = valid_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "uncovered-numeric-claim"
    assert detected in caught.value.details["values"]


def test_hidden_frontmatter_and_comment_text_cannot_satisfy_anchors():
    rendered = candidate().replace(
        "### 因果链\n\n",
        "### 因果链\n\n<!-- hidden causal evidence -->\n\n",
    )
    receipt = valid_receipt(rendered)
    receipt["material_items"][0]["note_anchor"] = "hidden causal evidence"

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "missing-receipt-anchor"

    receipt = valid_receipt()
    receipt["material_items"][0]["note_anchor"] = SOURCE
    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, candidate(), candidate_source=SOURCE)
    assert caught.value.code == "missing-receipt-anchor"

    rendered = candidate().replace(
        "### 因果链\n\n",
        (
            "### 因果链\n\n"
            "<!-- hidden block starts\n"
            "```text\n"
            "hidden evidence across a fence-looking line\n"
            "```\n"
            "-->\n\n"
        ),
    )
    receipt = valid_receipt(rendered)
    receipt["material_items"][0]["note_anchor"] = (
        "hidden evidence across a fence-looking line"
    )
    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)
    assert caught.value.code == "missing-receipt-anchor"


def test_visible_fenced_code_can_satisfy_a_procedure_anchor():
    rendered = candidate().replace(
        "### 应用方法\n\n",
        "### 应用方法\n\n```bash\necho verify-visible-step\n```\n\n",
    )
    receipt = valid_receipt(rendered)
    receipt["material_items"][1]["note_anchor"] = "echo verify-visible-step"
    receipt["practical_artifact"]["note_anchor"] = "echo verify-visible-step"

    result = validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert result["ok"] is True


def test_inference_label_must_occur_inside_reader_facing_excerpt():
    receipt = valid_receipt()
    receipt["inferences"][0]["label"] = "Writer inference"

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, candidate(), candidate_source=SOURCE)

    assert caught.value.code == "unlabeled-inference"


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


def test_receipt_rejects_invalid_heredoc_first_skill_frontmatter():
    rendered = candidate().replace(
        "### 应用方法\n\n",
        (
            "### 应用方法\n\n"
            "```bash\n"
            "cat << 'EOF' > .claude/skills/reviewer/SKILL.md\n"
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

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(
            valid_receipt(rendered), rendered, candidate_source=SOURCE
        )

    assert caught.value.code == "invalid-copyable-skill-frontmatter"


def test_resource_survey_requires_evidence_for_every_concrete_resource():
    rendered = resource_candidate()
    receipt = valid_resource_receipt(rendered)

    result = validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)
    assert result["resource_count"] == 2

    receipt = valid_resource_receipt(rendered)
    receipt["material_items"] = [
        item
        for item in receipt["material_items"]
        if item["id"] != "tool-b-limitation"
    ]
    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)
    assert caught.value.code == "incomplete-resource-evidence"
    assert caught.value.details == {
        "resource_id": "tool-b",
        "missing_kinds": ["limitation"],
    }


def test_resource_survey_rejects_visible_resource_omitted_from_receipt():
    rendered = resource_candidate().replace(
        f"Tool B: {RESOURCE_B}\n\n",
        f"Tool B: {RESOURCE_B}\n\nTool C: https://tool-c.example/\n\n",
    )
    receipt = valid_resource_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "incomplete-resource-evidence"
    assert caught.value.details == {
        "undeclared_urls": ["https://tool-c.example/"],
        "unlisted_urls": [],
    }


def test_resource_survey_requires_explicit_reader_visible_inventory():
    rendered = resource_candidate().replace("## Resource Inventory\n\n", "")
    receipt = valid_resource_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "incomplete-resource-evidence"


def test_resource_survey_rejects_global_compatibility_without_resource_identity():
    rendered = resource_candidate()
    receipt = valid_resource_receipt(rendered)
    compatibility = next(
        item
        for item in receipt["material_items"]
        if item["id"] == "tool-b-compatibility"
    )
    compatibility.pop("resource_id")

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "incomplete-resource-evidence"


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
    ("note_type", "folder", "capture_depth", "expected"),
    [
        ("web-clip", "20-Learning/AI-Agent", "verified", True),
        ("web-clip", "20-Learning/AI-Agent", "standard", False),
        ("web-clip", "00-Inbox", "verified", False),
        ("web-clip", "00-Inbox/Unread", "standard", False),
        ("learning-note", "20-Learning", "verified", False),
    ],
)
def test_receipt_routing(note_type, folder, capture_depth, expected):
    assert requires_capture_receipt(note_type, folder, capture_depth) is expected


def test_receipt_rejects_standard_candidate_even_with_valid_evidence():
    rendered = candidate().replace(
        "capture_depth: verified", "capture_depth: standard"
    )
    receipt = valid_receipt(rendered)

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "capture-receipt-depth-mismatch"


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


@pytest.mark.parametrize(
    "command",
    [
        'printf "%s" "$body" | tee ~/.claude/skills/x/SKILL.md',
        "$body | Set-Content -Path .\\skills\\x\\SKILL.md",
        "$body | Out-File skills/x/SKILL.md",
        'echo "$body" > skills/x/SKILL.md',
    ],
    ids=["printf-tee", "powershell-set-content", "out-file", "echo-redirect"],
)
def test_copyable_skill_detection_recognises_pipeline_forms(command):
    """The writing command need not start the line.

    The pattern was anchored with `^[ \\t]*`, so only a command in leading
    position matched. Every pipeline form wrote a SKILL.md without its
    frontmatter ever being validated.
    """
    from obsidian_kb_skill.scripts.capture_receipt import (
        _COPYABLE_SKILL_COMMAND_RE,
    )

    assert _COPYABLE_SKILL_COMMAND_RE.search(command) is not None


@pytest.mark.parametrize(
    "line",
    [
        "The tee command writes to SKILL.md conceptually.",
        "See skills/x/SKILL.md for the contract.",
    ],
    ids=["prose-mentioning-tee", "plain-reference"],
)
def test_copyable_skill_detection_ignores_prose(line):
    """Guard: prose that merely names SKILL.md is not a copyable example."""
    from obsidian_kb_skill.scripts.capture_receipt import (
        _COPYABLE_SKILL_COMMAND_RE,
    )

    assert _COPYABLE_SKILL_COMMAND_RE.search(line) is None


def test_reader_facing_body_keeps_comment_literals_inside_inline_code():
    """Inline code is visible; a comment literal in it is not a hidden comment."""
    from obsidian_kb_skill.scripts.capture_receipt import _reader_facing_body

    body = (
        "---\ntype: web-clip\n---\n\n"
        "The template uses `<!-- BEGIN block -->` as a marker.\n"
    )

    out = _reader_facing_body(body)

    assert "`<!-- BEGIN block -->`" in out


def test_reader_facing_body_still_masks_a_real_hidden_comment():
    """Guard: an actual comment outside code must still be masked."""
    from obsidian_kb_skill.scripts.capture_receipt import _reader_facing_body

    body = "---\ntype: web-clip\n---\n\nVisible. <!-- hidden claim --> More.\n"

    out = _reader_facing_body(body)

    assert "hidden claim" not in out
    assert "Visible." in out


FENCE_SAMPLES = (
    "plain text only\n",
    "before\n```\ncode {{ x }}\n```\nafter\n",
    "before\n~~~python\ncode {{ x }}\n~~~\nafter\n",
    "   ```js\n   nested {{ y }}\n   ```\n",
    "```` ```inside ````\nouter {{ z }}\n",
    "unclosed\n```\nstill inside {{ w }}\n",
    "```info`with`ticks\nnot a fence\n",
    "a\r\n```\r\nwindows {{ v }}\r\n```\r\nb\r\n",
)


def test_the_two_fence_maskers_agree():
    """Two implementations of "which bytes are inside a code fence".

    `capture_receipt` masks fences to keep a hidden HTML comment from passing as
    reader-facing text; `note_catalog` masks them so a note explaining Vue or
    Jinja2 is not read as carrying an unreplaced placeholder. Different reasons,
    same question — and a Markdown fence has enough corner cases (tildes,
    indentation, backticks in the info string, no closing fence) that two
    hand-written answers will not stay equal on their own.
    """
    from obsidian_kb_skill.scripts import capture_receipt, note_catalog

    for sample in FENCE_SAMPLES:
        assert note_catalog.mask_fenced_code(sample) == capture_receipt._mask_fenced_code(
            sample
        ), f"the two maskers disagree on {sample!r}"


def test_two_resources_named_the_same_number_are_still_duplicates():
    """The uniqueness check compares the raw value; the set stores `str(name)`.

    While `is_meaningful_metadata` rejected every non-`str`, those two could not
    disagree — a name that reached the set was already a string. #162 widened the
    predicate to accept scalars so an unquoted YAML date would stop being read as
    a placeholder, and that made `2026 in {"2026"}` reachable: two resources
    named the same number stopped colliding.
    """
    rendered = resource_candidate()
    receipt = copy.deepcopy(valid_resource_receipt(rendered))
    receipt["resources"][0]["name"] = "2026"
    receipt["resources"][1]["name"] = 2026

    with pytest.raises(CaptureReceiptError) as caught:
        validate_capture_receipt(receipt, rendered, candidate_source=SOURCE)

    assert caught.value.code == "invalid-capture-receipt"
