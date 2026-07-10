"""Tests for the Link Suggestor (scripts/suggest_links.py)."""
from __future__ import annotations

from pathlib import Path

from obsidian_kb_skill.scripts.suggest_links import suggest_links


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "30-Insights").mkdir()
    (vault / "10-Work").mkdir()
    (vault / "20-Learning").mkdir()
    return vault


def test_suggests_shared_tag_notes_within_scope(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight, ai-agent]\n---\n# Target Note\n",
        encoding="utf-8",
    )
    (vault / "30-Insights" / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight, ai-agent]\n---\n# Alpha\n",
        encoding="utf-8",
    )
    (vault / "30-Insights" / "B.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Beta\n",
        encoding="utf-8",
    )
    # sibling folder in scope (10-Work is among the first two siblings)
    (vault / "10-Work" / "D.md").write_text(
        '---\ndate: "2026-07-07"\ntype: meeting-note\n'
        "tags: [insight]\n---\n# Delta\n",
        encoding="utf-8",
    )

    results = suggest_links(vault, vault / "30-Insights" / "Target.md", top_n=10)
    paths = [p.as_posix() for p, _, _ in results]

    assert (vault / "30-Insights" / "A.md").as_posix() in paths
    assert (vault / "10-Work" / "D.md").as_posix() in paths
    # no shared signal -> excluded
    assert (vault / "30-Insights" / "B.md").as_posix() not in paths
    # self excluded
    assert (vault / "30-Insights" / "Target.md").as_posix() not in paths


def test_excludes_existing_related(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        'tags: [insight]\nrelated: ["[[A]]"]\n---\n# Target Note\n',
        encoding="utf-8",
    )
    (vault / "30-Insights" / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Alpha\n",
        encoding="utf-8",
    )

    results = suggest_links(vault, vault / "30-Insights" / "Target.md")
    paths = [p.as_posix() for p, _, _ in results]

    assert (vault / "30-Insights" / "A.md").as_posix() not in paths


def test_respects_top_n(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Target Note\n",
        encoding="utf-8",
    )
    for i in range(5):
        (vault / "30-Insights" / f"N{i}.md").write_text(
            f'---\ndate: "2026-07-0{i + 1}"\ntype: insight-note\n'
            f"tags: [insight]\n---\n# N{i}\n",
            encoding="utf-8",
        )

    results = suggest_links(vault, vault / "30-Insights" / "Target.md", top_n=2)

    assert len(results) == 2


def test_is_read_only(tmp_path):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights" / "Target.md"
    target.write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Target Note\n",
        encoding="utf-8",
    )
    (vault / "30-Insights" / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Alpha\n",
        encoding="utf-8",
    )

    before = target.read_text(encoding="utf-8")
    suggest_links(vault, target)
    assert target.read_text(encoding="utf-8") == before
