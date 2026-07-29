"""Small versioned retrieval quality gate for representative mixed-language queries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from obsidian_kb_skill.scripts.search_vault import search_vault


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_eval_cases.json"


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_retrieval_eval_hit_at_1_mrr_and_read_only(tmp_path):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for note in fixture["notes"]:
        path = vault / note["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"aliases: {json.dumps(note['aliases'], ensure_ascii=False)}\n"
            f"tags: {json.dumps(note['tags'], ensure_ascii=False)}\n"
            "---\n"
            f"# {note['title']}\n\n{note['body']}\n",
            encoding="utf-8",
        )
    before = _snapshot(vault)
    reciprocal_ranks: list[float] = []
    hit_at_1 = 0
    for case in fixture["queries"]:
        results = search_vault(vault, case["query"], top_k=5)["results"]
        paths = [item["path"] for item in results]
        rank = paths.index(case["expected"]) + 1 if case["expected"] in paths else 0
        hit_at_1 += int(rank == 1)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

    count = len(fixture["queries"])
    assert hit_at_1 / count == 1.0
    assert sum(reciprocal_ranks) / count == 1.0
    assert _snapshot(vault) == before
