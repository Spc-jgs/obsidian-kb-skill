"""Tests for vault_info.py — read-only cold-start context."""
from __future__ import annotations

from pathlib import Path

from obsidian_kb_skill.scripts import vault_info

collect = vault_info.collect


def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    for t in ("Daily Note.md", "Meeting Note.md", "Web Clip.md"):
        (vault / "Templates" / t).write_text(
            "---\ntype: daily-note\ndate: 2026-01-01\n---\n", encoding="utf-8"
        )
    for f in ("00-Inbox", "20-Learning", "30-Insights"):
        (vault / f).mkdir()
        (vault / f / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    return vault


def test_valid_vault_reports_true_with_templates(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    assert info["valid"] is True
    assert info["validation"] == {
        "exists": True,
        "is_obsidian": True,
        "has_templates": True,
    }
    assert info["templates"] == ["Daily Note", "Meeting Note", "Web Clip"]
    assert info["warnings"] == []


def test_standard_folders_reported_with_existence_and_index(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    folders = info["standard_folders"]
    # Present folders marked exists; missing folders (e.g. 40-Projects) not.
    assert folders["00-Inbox"]["exists"] is True
    assert folders["20-Learning"]["exists"] is True
    assert folders["40-Projects"]["exists"] is False
    # Note folders carry an index strategy; Templates/Attachments do not.
    assert folders["30-Insights"]["index"]["mode"] == "static"
    assert folders["30-Insights"]["index"]["can_append"] is True
    assert folders["Templates"]["index"] is None
    assert folders["Attachments"]["index"] is None


def test_invalid_vault_reports_false_with_warnings(tmp_path: Path):
    vault = tmp_path / "missing_vault"
    info = collect(vault)
    assert info["valid"] is False
    assert info["validation"]["exists"] is False
    assert any("does not exist" in w for w in info["warnings"])
    # No crash; templates empty and folders exist=False.
    assert info["templates"] == []
    assert info["standard_folders"]["00-Inbox"]["exists"] is False


def test_folder_index_global_present(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    g = info["folder_index_global"]
    assert set(g) == {"enabled", "graph_overwrite", "user_specified", "root_index_file"}
    assert g["root_index_file"] == "INDEX.md"


def test_custom_templates_reports_only_type_slugs(tmp_path: Path):
    vault = _make_vault(tmp_path)

    info = collect(vault)

    assert info["custom_templates"] == [
        "daily-note",
        "meeting-note",
        "web-clip",
    ]
    assert all(isinstance(item, str) for item in info["custom_templates"])


def test_collect_omits_template_shape_without_selected_type(tmp_path: Path):
    vault = _make_vault(tmp_path)

    info = collect(vault)

    assert "template_shape" not in info


def test_collect_returns_only_selected_template_shape(tmp_path: Path):
    vault = _make_vault(tmp_path)
    (vault / "Templates" / "Web Clip.md").write_text(
        "---\ntype: web-clip\n---\n# Clip\n\n## Source\n\nInstruction.\n## Summary\n",
        encoding="utf-8",
    )

    info = collect(vault, note_type="web-clip")

    assert info["template_shape"] == {
        "type": "web-clip",
        "path": "Templates/Web Clip.md",
        "headings": ["Source", "Summary"],
    }
    assert "Instruction." not in str(info["template_shape"])


def test_collect_returns_null_shape_for_missing_selected_template(tmp_path: Path):
    vault = _make_vault(tmp_path)
    (vault / "Templates" / "Web Clip.md").unlink()

    info = collect(vault, note_type="web-clip")

    assert info["template_shape"] is None


def test_compact_omits_note_lists_without_mutating_full_result(tmp_path: Path):
    vault = _make_vault(tmp_path)
    full = collect(vault)

    out = vault_info.compact(full)

    full_index = full["standard_folders"]["20-Learning"]["index"]
    compact_index = out["standard_folders"]["20-Learning"]["index"]
    assert "notes" in full_index
    assert "notes" not in compact_index
    assert compact_index["mode"] == "static"
    assert compact_index["index_file"] == "INDEX.md"
    assert compact_index["can_append"] is True


def test_crowded_folders_count_direct_notes_and_exclude_indexes(tmp_path: Path):
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    (topic / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    (topic / "AI-Agent.md").write_text("# Folder Index\n", encoding="utf-8")
    (topic / ".hidden.md").write_text("hidden\n", encoding="utf-8")
    for number in range(22):
        (topic / f"note-{number:02}.md").write_text("note\n", encoding="utf-8")
    nested = topic / "Skills"
    nested.mkdir()
    for number in range(7):
        (nested / f"skill-{number:02}.md").write_text("skill\n", encoding="utf-8")

    info = collect(vault)

    assert info["crowded_folders"] == [
        {
            "path": "20-Learning/AI-Agent",
            "direct_notes": 22,
            "threshold": 20,
            "child_folders": ["Skills"],
            "clusters": [{"term": "note", "kind": "title", "notes": 22}],
            "cluster_min_notes": 5,
        }
    ]


def test_crowded_folders_are_bounded_and_sorted(tmp_path: Path):
    vault = _make_vault(tmp_path)
    learning = vault / "20-Learning"
    for folder_number in range(25):
        topic = learning / f"Topic-{folder_number:02}"
        topic.mkdir()
        for note_number in range(20 + folder_number):
            (topic / f"note-{note_number:02}.md").write_text(
                "note\n", encoding="utf-8"
            )

    info = collect(vault)
    crowded = info["crowded_folders"]

    assert len(crowded) == 20
    assert crowded[0] == {
        "path": "20-Learning/Topic-24",
        "direct_notes": 44,
        "threshold": 20,
        "child_folders": [],
        "clusters": [{"term": "note", "kind": "title", "notes": 44}],
        "cluster_min_notes": 5,
    }
    assert crowded[-1]["direct_notes"] == 25


def test_crowded_folders_skip_directory_symlinks(tmp_path: Path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    for number in range(25):
        (outside / f"note-{number:02}.md").write_text("note\n", encoding="utf-8")
    alias = vault / "20-Learning" / "External"
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        import pytest

        pytest.skip(f"directory symlink creation unavailable: {exc}")

    info = collect(vault)

    assert all(item["path"] != "20-Learning/External" for item in info["crowded_folders"])


def _crowd(folder: Path, count: int, *, prefix: str, tags: str) -> None:
    for number in range(count):
        (folder / f"2026-07-{number + 1:02} {prefix} {number}.md").write_text(
            f"---\ntype: learning-note\ndate: 2026-07-01\ntags: {tags}\n---\n\n# t\n",
            encoding="utf-8",
        )


def test_clusters_answer_whether_a_child_category_is_justified(tmp_path: Path):
    """folder-routing.md needs five notes on one subject; report that directly.

    The rule was previously uncheckable at bounded cost: nothing in discovery
    said what the crowded folder was about, so the only way to apply it was to
    read every note.
    """
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 8, prefix="server", tags="[learning, mcp]")
    _crowd(topic, 4, prefix="rag pipeline", tags="[learning, rag]")
    for number in range(9):
        (topic / f"2026-06-{number + 1:02} misc {number}.md").write_text(
            "---\ntype: learning-note\ndate: 2026-06-01\ntags: [learning]\n---\n",
            encoding="utf-8",
        )

    crowded = collect(vault)["crowded_folders"][0]

    assert crowded["cluster_min_notes"] == 5
    clusters = {item["term"]: item for item in crowded["clusters"]}
    # A subject tag on enough notes is a cluster; four notes is not, and the
    # type-default tag every note carries is not a subject at all.
    assert clusters["mcp"] == {"term": "mcp", "kind": "tag", "notes": 8}
    assert "rag" not in clusters
    assert "learning" not in clusters


def test_clusters_report_a_readable_cjk_subject(tmp_path: Path):
    """Bigram tokens are rejoined so a Chinese subject reads as one term."""
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 21, prefix="记忆压缩", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]

    assert {"term": "记忆压缩", "kind": "title", "notes": 21} in clusters


def test_crowded_entry_lists_reusable_children(tmp_path: Path):
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    (topic / "Skills").mkdir()
    (topic / "Protocols").mkdir()
    _crowd(topic, 21, prefix="note", tags="[learning]")

    crowded = collect(vault)["crowded_folders"][0]

    assert crowded["child_folders"] == ["Protocols", "Skills"]


def test_required_references_name_the_whole_set_in_one_call(tmp_path: Path):
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 21, prefix="note", tags="[learning]")

    info = collect(vault, note_type="web-clip", folder="20-Learning/AI-Agent")

    assert [item["file"] for item in info["required_references"]] == [
        "note-creation.md",
        "web-capture.md",
        "custom-template.md",
        "folder-routing.md",
    ]
    reasons = {item["file"]: item["reason"] for item in info["required_references"]}
    assert "20-Learning/AI-Agent" in reasons["folder-routing.md"]


def test_required_references_stay_quiet_about_conditions_that_do_not_apply(
    tmp_path: Path,
):
    vault = _make_vault(tmp_path)

    info = collect(vault, note_type="web-clip")

    # The Web Clip template here is a stub rather than the shipped starter, so
    # it counts as customized; only the crowded-folder reference drops out.
    assert [item["file"] for item in info["required_references"]] == [
        "note-creation.md",
        "web-capture.md",
        "custom-template.md",
    ]


def test_an_invalid_vault_gets_no_reference_list(tmp_path: Path):
    info = collect(tmp_path / "missing")

    assert "required_references" not in info


def test_cluster_analysis_prefers_the_destination_over_the_crowd(tmp_path: Path):
    """Reading note heads is real I/O, so it runs under a whole-call budget.

    The folder the note is going into is the one the routing decision is about,
    so it is analyzed even when more crowded folders would have used the budget
    up first. Folders left unanalyzed omit `clusters` rather than reporting a
    sampled count that the five-note rule could not be applied to.
    """
    vault = _make_vault(tmp_path)
    for index in range(8):
        topic = vault / "20-Learning" / f"Topic-{index:02}"
        topic.mkdir()
        _crowd(topic, 190 - index, prefix=f"subject{index}", tags="[learning]")
    quiet = vault / "20-Learning" / "Chosen"
    quiet.mkdir()
    _crowd(quiet, 21, prefix="chosen subject", tags="[learning]")

    crowded = collect(
        vault, note_type="learning-note", folder="20-Learning/Chosen"
    )["crowded_folders"]

    analyzed = {item["path"] for item in crowded if "clusters" in item}
    assert "20-Learning/Chosen" in analyzed
    assert len(analyzed) < len(crowded)
    # Nothing is reported from a partial scan: an analyzed folder counted every
    # note it holds.
    chosen = next(item for item in crowded if item["path"] == "20-Learning/Chosen")
    assert {"term": "chosen", "kind": "title", "notes": 21} in chosen["clusters"]
