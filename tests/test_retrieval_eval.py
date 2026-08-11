"""Versioned forty-query retrieval baseline with positive and no-answer cases."""
from __future__ import annotations

import hashlib
import json
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


def _run_cases(vault: Path, fixture: dict[str, object]) -> dict[str, list[float]]:
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


def test_semantic_baseline_is_versioned_before_query_expansion(tmp_path):
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    semantic = _run_cases(vault, fixture)["semantic"]

    # These values record the unmodified v1.29.2 lexical baseline. A candidate
    # must add at least two valid hits without weakening the stable groups.
    assert sum(score > 0 for score in semantic) == 3
    assert sum(semantic) / len(semantic) == 0.3125


def test_holdout_baseline_is_frozen_before_any_lexicon_exists(tmp_path):
    """Record the holdout set's score while no query expansion is implemented.

    The eight `semantic-holdout` queries are written against the same corpus but
    are never allowed to inform the lexicon: they exist to estimate how much of a
    later gain generalises past the eight queries the gate optimises. Freezing
    the number here, in the commit that adds the queries, is what makes that
    claim checkable afterwards rather than merely asserted.
    """
    fixture = _load_fixture()
    vault = _build_vault(tmp_path, fixture)

    holdout = _run_cases(vault, fixture)["semantic-holdout"]

    # Four of eight already hit without expansion, all four through a Chinese
    # alias sharing a bigram with the query — the alias field doing its job, not
    # cross-lingual matching. The other four have zero token overlap with their
    # English target.
    assert sum(score > 0 for score in holdout) == 4
    assert sum(holdout) / len(holdout) == 0.5
