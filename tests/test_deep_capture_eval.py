"""Deterministic fixtures for manual deep-capture forward evaluation."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "deep_capture_eval_cases.json"
FAILURE_FIXTURES = (
    ROOT / "tests" / "fixtures" / "deep_capture_failure_cases.json"
)
CONTRACT = ROOT / "core" / "references" / "deep-capture.md"


def load_cases() -> list[dict[str, object]]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def load_failure_cases() -> list[dict[str, object]]:
    return json.loads(FAILURE_FIXTURES.read_text(encoding="utf-8"))


def test_eval_fixture_set_covers_every_capture_profile():
    assert {case["profile"] for case in load_cases()} == {
        "Tutorial or Technical Procedure",
        "Resource Survey or Product Comparison",
        "Conceptual or Opinion Analysis",
        "Research, Data, News, or Evidence Report",
    }


def test_eval_material_anchors_are_source_backed_and_inventions_are_absent():
    for case in load_cases():
        source = str(case["source"])
        anchors = list(case["material_anchors"])
        inventions = list(case["forbidden_inventions"])

        assert len(anchors) >= 8, case["id"]
        assert all(str(anchor) in source for anchor in anchors), case["id"]
        assert all(str(item) not in source for item in inventions), case["id"]


def test_eval_profiles_and_acceptance_rules_are_reachable_from_contract():
    contract = CONTRACT.read_text(encoding="utf-8")

    for case in load_cases():
        assert str(case["profile"]) in contract
    for marker in (
        "Source Inventory and Coverage Ledger",
        "No unresolved material item",
        "unsupported factual claim",
        "Semantic Hard Failures",
        "Mechanical and Semantic Acceptance",
    ):
        assert marker in contract


def test_real_failure_shapes_require_receipt_level_rejection():
    cases = load_failure_cases()

    assert {case["id"] for case in cases} == {
        "opinion-unsupported-numbers",
        "resource-guide-overgeneralization",
    }
    for case in cases:
        source = str(case["source"])
        failures = [str(item) for item in case["candidate_failures"]]
        receipt_failures = [str(item) for item in case["required_receipt_failures"]]
        assert all(item not in source for item in failures)
        assert receipt_failures
        assert all(
            item
            in {
                "uncovered-numeric-claim",
                "missing-measurement-context",
                "incomplete-profile-evidence",
                "unlabeled-inference",
            }
            for item in receipt_failures
        )


def test_receipt_contract_names_the_real_failure_controls():
    contract = CONTRACT.read_text(encoding="utf-8")

    for marker in (
        "numeric_claims",
        "measurement_context",
        "source-self-report",
        "writer-derived conclusion",
        "explicit reader-facing label",
        "selection-criteria",
        "starting-example",
    ):
        assert marker in contract
