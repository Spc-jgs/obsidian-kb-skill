"""Tool-neutral forward-evaluation contract for resilient webpage capture."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "web_capture_resilience_eval_cases.json"
WEB_CONTRACT = ROOT / "core" / "references" / "web-capture.md"
DEEP_CONTRACT = ROOT / "core" / "references" / "deep-capture.md"


def load_cases() -> list[dict[str, object]]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_fixture_set_covers_depths_outcomes_and_url_privacy():
    cases = load_cases()

    assert {case["expected_depth"] for case in cases} == {"standard", "verified"}
    assert "stop-zero-write" in {case["expected_outcome"] for case in cases}
    assert "receipt-required" in {case["expected_outcome"] for case in cases}
    assert "authenticated-private" in {case["url_class"] for case in cases}
    assert "material-unread" in {case["material_media"] for case in cases}
    assert len({case["id"] for case in cases}) == len(cases) == 8


def test_every_fixture_decision_is_reachable_from_lazy_contracts():
    contract = "\n".join(
        (
            WEB_CONTRACT.read_text(encoding="utf-8"),
            DEEP_CONTRACT.read_text(encoding="utf-8"),
        )
    )
    normalized = " ".join(contract.split())

    for case in load_cases():
        markers = [str(marker) for marker in case["contract_markers"]]
        assert markers, case["id"]
        for marker in markers:
            assert marker in normalized, f"{case['id']} missing contract marker {marker!r}"


def test_fixtures_remain_tool_neutral_and_do_not_prescribe_bypass():
    serialized = FIXTURES.read_text(encoding="utf-8")

    assert "Playwright" not in serialized
    assert "curl" not in serialized
    assert "bypass" not in serialized.lower()
