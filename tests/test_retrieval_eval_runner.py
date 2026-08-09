"""Smoke the reproducible retrieval baseline runner."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run_retrieval_baseline.py"


def test_retrieval_runner_reports_the_versioned_baseline():
    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(completed.stdout)

    assert result["query_count"] == 40
    assert result["read_only"] is True
    assert result["groups"]["exact"]["recall_at_5"] == 1.0
    assert result["groups"]["alias"]["recall_at_5"] == 1.0
    assert result["groups"]["filtered"]["recall_at_5"] == 1.0
    assert result["groups"]["semantic"]["recall_at_5"] == 0.375
    assert result["groups"]["semantic"]["mrr"] == 0.3125
    assert result["groups"]["no-answer"]["false_positive_rate"] == 0.0
    assert result["latency_ms"]["p95"] > 0
