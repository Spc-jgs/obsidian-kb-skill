"""Versioned semantic gate inputs for the v1.30 reference-Agent evaluation."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_semantic_eval_has_twelve_balanced_cases_and_three_repeats():
    fixture = load_fixture()
    cases = fixture["cases"]

    assert fixture["schema_version"] == 1
    assert fixture["reference_agent"]["repeats"] == 3
    assert Counter(case["group"] for case in cases) == {
        "standard": 4,
        "verified": 4,
        "stop": 4,
    }
    assert len({case["id"] for case in cases}) == len(cases) == 12


def test_every_case_declares_hard_gate_inputs():
    for case in load_fixture()["cases"]:
        assert case["expected_outcome"] in {"write", "zero-write"}
        assert case["expected_depth"] in {"standard", "verified"}
        assert case["prompt"].strip()
        assert case["source_markdown"].strip()
        assert case["source_url"].startswith("https://")
        assert isinstance(case["required_facts"], list)
        assert isinstance(case["required_labels"], list)
        assert case["forbidden_claims"]
        if case["expected_outcome"] == "write":
            assert len(case["required_facts"]) >= 5
            assert "stop_reason" not in case
        else:
            assert case["stop_reason"]
            assert case["stop_evidence"]
            assert not case["required_facts"]


def test_verified_cases_require_receipts_and_stop_cases_require_zero_write():
    for case in load_fixture()["cases"]:
        if case["group"] == "verified":
            assert case["requires_receipt"] is True
        if case["group"] == "stop":
            assert case["expected_outcome"] == "zero-write"


def test_fixture_is_synthetic_and_contains_no_private_vault_material():
    serialized = FIXTURE.read_text(encoding="utf-8")

    for forbidden in (
        "/Users/",
        "my-knowledge-base",
        "shaopc",
        "Spc-jgs",
        "juejin.cn",
        "zhihu.com",
    ):
        assert forbidden not in serialized
    assert "REDACTED" in serialized
    assert all(
        ".invalid/" in case["source_url"]
        for case in load_fixture()["cases"]
    )


def test_material_image_case_reuses_a_checked_in_public_asset():
    case = next(
        case
        for case in load_fixture()["cases"]
        if case["id"] == "standard-material-diagram"
    )

    assert case["material_asset"] == "docs/assets/obsidian-kb-hero.webp"
    assert (ROOT / case["material_asset"]).is_file()
