"""Structural checks for the v1.30 directional-link evaluation labels."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "directed_link_eval_cases.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_link_fixture_has_balanced_directional_labels():
    fixture = _load_fixture()
    positives = fixture["positive"]
    negatives = fixture["hard_negative"]

    assert fixture["schema_version"] == 1
    assert len(positives) == len(negatives) == 16
    assert len({case["id"] for case in positives + negatives}) == 32
    assert all(case["reader_learns"].strip() for case in positives)
    assert all(case["evidence"].strip() for case in positives)
    assert all(case["shared_topic"].strip() for case in negatives)
    assert all(case["why_not_related"].strip() for case in negatives)


def test_link_fixture_is_evaluation_only_and_synthetic():
    fixture = _load_fixture()
    serialized = FIXTURE.read_text(encoding="utf-8")

    assert "no scorer" in fixture["purpose"]
    for forbidden in (
        "/Users/",
        "my-knowledge-base",
        "shaopc",
        "Spc-jgs",
        "juejin.cn",
        "zhihu.com",
    ):
        assert forbidden not in serialized
