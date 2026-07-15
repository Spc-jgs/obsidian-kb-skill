"""Tests for the Link Suggestor (scripts/suggest_links.py)."""
from __future__ import annotations

from pathlib import Path

from obsidian_kb_skill.scripts.suggest_links import _title_tokens, suggest_links


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
    assert (vault / "10-Work" / "D.md").as_posix() not in paths
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
        "tags: [insight]\n---\n# Ranking Target Note\n",
        encoding="utf-8",
    )
    for i in range(5):
        (vault / "30-Insights" / f"N{i}.md").write_text(
            f'---\ndate: "2026-07-0{i + 1}"\ntype: insight-note\n'
            f"tags: [insight]\n---\n# Ranking N{i}\n",
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


def test_suggests_chinese_title_overlap_without_tags(tmp_path):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights" / "Target.md"
    target.write_text("# 电子合同签章方案\n", encoding="utf-8")
    candidate = vault / "30-Insights" / "Candidate.md"
    candidate.write_text("# SpringBoot 电子签章实践\n", encoding="utf-8")

    results = suggest_links(vault, target)

    assert [path for path, _, _ in results] == [candidate]
    assert any("title overlap" in reason for reason in results[0][2])


def test_single_cjk_character_is_not_a_title_signal():
    assert _title_tokens("中") == set()


def test_suppresses_same_type_and_structural_tags_alone(tmp_path):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights" / "Target.md"
    target.write_text(
        "---\ntype: web-clip\ntags: [web-clip, java]\n---\n# 电子签章\n",
        encoding="utf-8",
    )
    (vault / "30-Insights" / "Unrelated.md").write_text(
        "---\ntype: web-clip\ntags: [web-clip, java]\n---\n# Import 注解源码解读\n",
        encoding="utf-8",
    )

    assert suggest_links(vault, target) == []


def test_common_tags_are_adaptively_ignored(tmp_path):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights" / "Target.md"
    target.write_text(
        "---\ntype: web-clip\ntags: [java, spring-boot]\n---\n# Contract signing\n",
        encoding="utf-8",
    )
    specific = vault / "30-Insights" / "Specific.md"
    specific.write_text(
        "---\ntype: learning-note\ntags: [java, spring-boot]\n---\n# Spring configuration\n",
        encoding="utf-8",
    )
    for name in ("Generic-A.md", "Generic-B.md"):
        (vault / "30-Insights" / name).write_text(
            "---\ntype: learning-note\ntags: [java]\n---\n# Unrelated topic\n",
            encoding="utf-8",
        )

    results = suggest_links(vault, target)

    assert [path for path, _, _ in results] == [specific]
    assert "spring-boot" in " ".join(results[0][2])
    assert "java" not in " ".join(results[0][2])


def test_only_relevant_sibling_folder_is_in_scope(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    current = vault / "Notes"
    current.mkdir()
    (vault / "00-Unrelated").mkdir()
    relevant_folder = vault / "Spring-Boot"
    relevant_folder.mkdir()
    target = current / "Target.md"
    target.write_text(
        "---\ntags: [spring-boot]\n---\n# Spring Boot contract\n",
        encoding="utf-8",
    )
    (vault / "00-Unrelated" / "Wrong.md").write_text(
        "---\ntags: [spring-boot]\n---\n# Wrong\n", encoding="utf-8"
    )
    relevant = relevant_folder / "Relevant.md"
    relevant.write_text(
        "---\ntags: [spring-boot]\n---\n# Relevant\n", encoding="utf-8"
    )

    results = suggest_links(vault, target)

    assert [path for path, _, _ in results] == [relevant]


def test_root_note_can_suggest_another_root_note(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    target = vault / "Target.md"
    target.write_text("---\ntags: [specific-topic]\n---\n# Target\n", encoding="utf-8")
    candidate = vault / "Candidate.md"
    candidate.write_text(
        "---\ntags: [specific-topic]\n---\n# Candidate\n", encoding="utf-8"
    )

    results = suggest_links(vault, target)

    assert [path for path, _, _ in results] == [candidate]


def test_reads_each_candidate_once(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights" / "Target.md"
    target.write_text("---\ntags: [specific-topic]\n---\n# Target\n", encoding="utf-8")
    candidate = vault / "30-Insights" / "Candidate.md"
    candidate.write_text(
        "---\ntags: [specific-topic]\n---\n# Candidate\n", encoding="utf-8"
    )
    original = Path.read_text
    reads = 0

    def counting_read_text(path, *args, **kwargs):
        nonlocal reads
        if path == candidate:
            reads += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    suggest_links(vault, target)

    assert reads == 1
