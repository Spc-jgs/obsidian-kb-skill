#!/usr/bin/env python3
"""Measure the versioned synthetic retrieval corpus without mutating it."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from obsidian_kb_skill.scripts.search_vault import search_vault


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_eval_cases.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_vault(root: Path, fixture: dict[str, object]) -> Path:
    vault = root / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for note in fixture["notes"]:
        path = vault / note["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f'date: "{note["date"]}"\n'
            f'type: {note["type"]}\n'
            f"aliases: {json.dumps(note['aliases'], ensure_ascii=False)}\n"
            f"tags: {json.dumps(note['tags'], ensure_ascii=False)}\n"
            "---\n"
            f"# {note['title']}\n\n{note['body']}\n",
            encoding="utf-8",
        )
    return vault


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def evaluate(vault: Path, fixture: dict[str, object]) -> dict[str, object]:
    before = snapshot(vault)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    latencies: list[float] = []
    for case in fixture["queries"]:
        filters = case.get("filters", {})
        started = time.perf_counter()
        payload = search_vault(
            vault,
            case["query"],
            top_k=5,
            types=filters.get("types"),
            tags=filters.get("tags"),
            after=filters.get("after"),
            before=filters.get("before"),
        )
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        paths = [item["path"] for item in payload["results"]]
        expected = set(case["expected"])
        rank = next(
            (index for index, path in enumerate(paths, start=1) if path in expected),
            0,
        )
        grouped[case["group"]].append(
            {
                "recall_at_5": float(bool(rank)) if expected else None,
                "reciprocal_rank": 1.0 / rank if rank else 0.0,
                "false_positive": bool(paths) if not expected else None,
            }
        )

    groups = {}
    for name, rows in sorted(grouped.items()):
        recall = [row["recall_at_5"] for row in rows if row["recall_at_5"] is not None]
        false_positive = [row["false_positive"] for row in rows if row["false_positive"] is not None]
        groups[name] = {
            "count": len(rows),
            "recall_at_5": sum(recall) / len(recall) if recall else None,
            "mrr": sum(row["reciprocal_rank"] for row in rows) / len(rows),
            "false_positive_rate": (
                sum(false_positive) / len(false_positive) if false_positive else None
            ),
        }
    return {
        "schema_version": 1,
        "fixture_schema_version": fixture["schema_version"],
        "query_count": len(fixture["queries"]),
        "groups": groups,
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 4),
            "p95": round(percentile(latencies, 0.95), 4),
            "max": round(max(latencies), 4),
        },
        "read_only": snapshot(vault) == before,
    }


def main() -> int:
    args = parse_args()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="obsidian-retrieval-eval-") as raw:
        result = evaluate(build_vault(Path(raw), fixture), fixture)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
