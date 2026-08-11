"""Versioned forty-query retrieval baseline with positive and no-answer cases."""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from obsidian_kb_skill.scripts.search_vault import search_vault


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_eval_cases.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _build_vault(tmp_path: Path, fixture: dict[str, object]) -> Path:
    vault = tmp_path / "vault"
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


def _run_cases(
    vault: Path, fixture: dict[str, object], *, expand: bool = True
) -> dict[str, list[float]]:
    metrics: dict[str, list[float]] = defaultdict(list)
    for case in fixture["queries"]:
        filters = case.get("filters", {})
        payload = search_vault(
            vault,
            case["query"],
            top_k=5,
            types=filters.get("types"),
            tags=filters.get("tags"),
            after=filters.get("after"),
            before=filters.get("before"),
            expand=expand,
        )
        paths = [item["path"] for item in payload["results"]]
        expected = set(case["expected"])
        if not expected:
            metrics[case["group"]].append(float(not paths))
            continue
        rank = next(
            (index for index, path in enumerate(paths, start=1) if path in expected),
            0,
        )
        metrics[case["group"]].append(1.0 / rank if rank else 0.0)
    return metrics


def test_retrieval_fixture_has_the_accepted_forty_query_shape():
    fixture = _load_fixture()
    queries = fixture["queries"]

    assert fixture["schema_version"] == 3
    assert Counter(case["group"] for case in queries) == {
        "exact": 10,
        "alias": 8,
        "filtered": 8,
        "semantic": 8,
        "semantic-holdout": 8,
        "no-answer": 6,
    }
    assert len({case["id"] for case in queries}) == len(queries) == 48
    assert all(case["expected"] for case in queries if case["group"] != "no-answer")
    assert all(not case["expected"] for case in queries if case["group"] == "no-answer")


def test_retrieval_fixture_is_synthetic_and_has_no_private_paths():
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


def test_lexical_baseline_quality_and_read_only_contract(tmp_path):
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)
    before = _snapshot(vault)

    metrics = _run_cases(vault, fixture)

    # Stable lexical strengths are release gates. The semantic result is
    # deliberately measured separately below rather than averaged into them.
    assert sum(metrics["exact"]) / len(metrics["exact"]) == 1.0
    assert sum(metrics["alias"]) / len(metrics["alias"]) == 1.0
    assert sum(metrics["filtered"]) / len(metrics["filtered"]) == 1.0
    assert sum(metrics["no-answer"]) / len(metrics["no-answer"]) == 1.0
    assert _snapshot(vault) == before


def test_no_expand_still_reproduces_the_recorded_pre_expansion_baseline(tmp_path):
    """`--no-expand` must remain a faithful reproduction of v1.29.2 retrieval.

    Kept as a live assertion rather than a paragraph in a report: the before
    number is what the after number means, and a comparison whose baseline
    silently drifted is not a comparison. It is also the flag a user reaches for
    when they want to know whether a surprising hit came from their own words.
    """
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    metrics = _run_cases(vault, fixture, expand=False)

    assert sum(score > 0 for score in metrics["semantic"]) == 3
    assert sum(metrics["semantic"]) / len(metrics["semantic"]) == 0.3125
    # Four of eight holdout queries already hit without expansion, all four
    # through a Chinese alias sharing a bigram with the query — the alias field
    # doing its job, not cross-lingual matching.
    assert sum(score > 0 for score in metrics["semantic-holdout"]) == 4
    assert sum(metrics["semantic-holdout"]) / len(metrics["semantic-holdout"]) == 0.5
    assert sum(metrics["exact"]) / len(metrics["exact"]) == 1.0
    assert sum(metrics["alias"]) / len(metrics["alias"]) == 1.0
    assert sum(metrics["no-answer"]) / len(metrics["no-answer"]) == 1.0


def test_query_expansion_clears_the_accepted_semantic_gate(tmp_path):
    """The gate #73 set: at least five of eight, nothing else regressing."""
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    metrics = _run_cases(vault, fixture)
    semantic = metrics["semantic"]

    assert sum(score > 0 for score in semantic) >= 5
    assert sum(score > 0 for score in semantic) > 3
    assert sum(semantic) / len(semantic) > 0.3125
    assert sum(metrics["exact"]) / len(metrics["exact"]) == 1.0
    assert sum(metrics["alias"]) / len(metrics["alias"]) == 1.0
    assert sum(metrics["filtered"]) / len(metrics["filtered"]) == 1.0
    assert sum(metrics["no-answer"]) / len(metrics["no-answer"]) == 1.0


def test_holdout_gain_is_reported_but_never_gated(tmp_path):
    """The holdout may only lose ground, never be tuned to win it.

    These eight queries were committed before any lexicon existed and are not a
    release gate: turning them into one would make the next author optimise
    against them, and the set would stop measuring generalisation the moment it
    started measuring compliance. The assertion is therefore one-sided — no
    regression below the frozen pre-expansion score.
    """
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    holdout = _run_cases(vault, fixture)["semantic-holdout"]

    assert sum(score > 0 for score in holdout) >= 4
    assert sum(holdout) / len(holdout) >= 0.5


def test_expansion_stays_inside_the_accepted_latency_budget(tmp_path):
    """#73 allows twice the lexical P95. Measured as a ratio, not a millisecond.

    An absolute threshold measures the CI runner, not the change. Both modes run
    in the same process against the same corpus, so the ratio between them is
    the only part that describes this code.
    """
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    def p95(expand: bool) -> float:
        samples: list[float] = []
        for case in fixture["queries"]:
            filters = case.get("filters", {})
            started = time.perf_counter()
            search_vault(
                vault,
                case["query"],
                top_k=5,
                types=filters.get("types"),
                tags=filters.get("tags"),
                after=filters.get("after"),
                before=filters.get("before"),
                expand=expand,
            )
            samples.append(time.perf_counter() - started)
        samples.sort()
        return samples[math.ceil(len(samples) * 0.95) - 1]

    baseline = p95(False)
    expanded = p95(True)

    assert expanded <= 2.0 * baseline
