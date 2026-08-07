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
            # Every note here is titled the same, so the one term covers the
            # whole folder and cannot be split out of it.
            "clusters": [],
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
        "clusters": [],
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
    _crowd_from(folder, count, start=0, prefix=prefix, tags=tags)


def _crowd_from(
    folder: Path, count: int, *, start: int, prefix: str, tags: str
) -> None:
    """Write notes whose numbering starts past an existing batch.

    A cluster term has to leave a remainder to be splittable, so most fixtures
    need a second batch on a different subject alongside the first.
    """
    for number in range(start, start + count):
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
    # Leave a remainder, or the subject covers the folder and is not splittable.
    _crowd_from(topic, 6, start=22, prefix="其他", tags="[learning]")

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
    # Not named after the folder, and leaving a remainder, so the point of the
    # test stays the scan budget rather than the splittability rules.
    _crowd(quiet, 21, prefix="picked subject", tags="[learning]")
    _crowd_from(quiet, 6, start=22, prefix="其他", tags="[learning]")

    crowded = collect(
        vault, note_type="learning-note", folder="20-Learning/Chosen"
    )["crowded_folders"]

    analyzed = {item["path"] for item in crowded if "clusters" in item}
    assert "20-Learning/Chosen" in analyzed
    assert len(analyzed) < len(crowded)
    # Nothing is reported from a partial scan: an analyzed folder counted every
    # note it holds.
    chosen = next(item for item in crowded if item["path"] == "20-Learning/Chosen")
    assert {"term": "picked", "kind": "title", "notes": 21} in chosen["clusters"]


def test_a_long_frontmatter_block_still_yields_its_tags(tmp_path: Path):
    """A fixed character budget silently dropped a note from cluster counting.

    The reader used to stop at 4096 characters, so a note with a long `related`
    list parsed as "no frontmatter" and its subject tag vanished from the
    signal — no error, no warning, just a cluster reported one note short.
    """
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    filler = "\n".join(f'  - "[[占位关联笔记 {i}]]"' for i in range(300))
    for index in range(21):
        (topic / f"2026-07-{index + 1:02} 长头部 {index}.md").write_text(
            "---\ntype: learning-note\ndate: 2026-07-01\ntags: [learning, mcp]\n"
            f"related:\n{filler}\n---\n\n# t\n",
            encoding="utf-8",
        )
    # Leave a remainder, or `mcp` covers the folder and is not splittable.
    _crowd_from(topic, 6, start=22, prefix="其他", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]

    assert {"term": "mcp", "kind": "tag", "notes": 21} in clusters


def test_a_windows_style_route_still_matches_the_crowded_folder(tmp_path: Path):
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 21, prefix="note", tags="[learning]")

    info = collect(
        vault, note_type="learning-note", folder="20-Learning\\AI-Agent"
    )

    assert "folder-routing.md" in [
        item["file"] for item in info["required_references"]
    ]


def _template_tags(vault: Path, **defaults: str) -> None:
    for name, tag in defaults.items():
        (vault / "Templates" / f"{name}.md").write_text(
            f"---\ntype: {name.lower()}\ntags: [{tag}]\n---\n", encoding="utf-8"
        )


def _tagged(folder: Path, name: str, tags: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text(
        f"---\ntype: learning-note\ndate: 2026-07-01\ntags: {tags}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_discovery_returns_the_vocabulary_the_reuse_rule_needs(tmp_path: Path):
    """Reusing an existing tag is only possible for tags the writer can see.

    The rule used to be checked against the five most recent notes in one
    folder, which names almost none of a Vault-wide vocabulary.
    """
    vault = _make_vault(tmp_path)
    _template_tags(vault, Learning="learning", Insight="insight")
    learning = vault / "20-Learning"
    for index in range(3):
        _tagged(learning, f"a{index}", "[learning, ai-agent]")
    _tagged(learning, "b", "[learning, mcp]")
    _tagged(vault / "30-Insights", "c", "[insight, mcp]")

    vocabulary = collect(vault)["tag_vocabulary"]

    assert vocabulary["tags"][0] == {"tag": "ai-agent", "notes": 3}
    assert {"tag": "mcp", "notes": 2} in vocabulary["tags"]
    assert vocabulary["distinct"] == 2
    # Every managed note is read, including the three folder INDEX.md files,
    # so `scanned` says how much of the Vault the vocabulary actually covers.
    assert vocabulary["scanned"] == 8


def test_vocabulary_drops_tags_the_template_already_supplies(tmp_path: Path):
    """A type default is not a subject choice, and it is read from this Vault.

    A hardcoded list both misses what a Vault renamed and discards real
    subjects that merely looked common elsewhere — and dropping a live subject
    invites the near-duplicate the vocabulary exists to prevent.
    """
    vault = _make_vault(tmp_path)
    _template_tags(vault, Person="people", Daily="daily")
    _tagged(vault / "20-Learning", "a", "[daily, people, java]")

    terms = [item["tag"] for item in collect(vault)["tag_vocabulary"]["tags"]]

    assert "daily" not in terms
    assert "people" not in terms
    assert "java" in terms


def test_vocabulary_ignores_index_notes(tmp_path: Path):
    vault = _make_vault(tmp_path)
    (vault / "20-Learning" / "20-Learning.md").write_text(
        "---\ntype: folder-index\ntags: [navigation]\n---\n# Index\n",
        encoding="utf-8",
    )
    _tagged(vault / "20-Learning", "a", "[mcp]")

    terms = [item["tag"] for item in collect(vault)["tag_vocabulary"]["tags"]]

    assert terms == ["mcp"]


def test_vocabulary_is_bounded_and_reports_what_it_left_out(tmp_path: Path):
    vault = _make_vault(tmp_path)
    for index in range(vault_info.MAX_VOCABULARY_TERMS + 5):
        _tagged(vault / "20-Learning", f"n{index}", f"[t{index:03}]")

    vocabulary = collect(vault)["tag_vocabulary"]

    assert len(vocabulary["tags"]) == vault_info.MAX_VOCABULARY_TERMS
    assert vocabulary["distinct"] == vault_info.MAX_VOCABULARY_TERMS + 5


def test_an_invalid_vault_gets_no_vocabulary(tmp_path: Path):
    assert "tag_vocabulary" not in collect(tmp_path / "missing")


def test_a_term_covering_the_folder_does_not_take_a_slot(tmp_path: Path):
    """The slots are the scarce resource, so an unsplittable term is removed.

    On the reference Vault the top four terms in `20-Learning/AI-Agent` were the
    folder's own name, both halves of it, and a generic word, which cut two real
    candidates off the end of the list.
    """
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    # `blanket` is on every note; `mcp` and `rag` are real sub-themes.
    _crowd(topic, 8, prefix="server", tags="[learning, blanket, mcp]")
    _crowd_from(topic, 7, start=9, prefix="pipeline", tags="[learning, blanket, rag]")
    _crowd_from(topic, 6, start=17, prefix="其他", tags="[learning, blanket]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]
    terms = {item["term"] for item in clusters}

    assert "blanket" not in terms
    assert {"mcp", "rag"} <= terms


def test_a_genuine_majority_cluster_is_still_reported(tmp_path: Path):
    """Large is not the same as unsplittable; only the remainder decides."""
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 13, prefix="server", tags="[learning, mcp]")
    _crowd_from(topic, 8, start=14, prefix="其他", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]

    # 13 of 21 is a clear majority, and the 8 left over could still be a folder.
    assert {"term": "mcp", "kind": "tag", "notes": 13} in clusters


def test_a_remainder_too_small_to_be_a_folder_is_not_a_split(tmp_path: Path):
    """Expressed as a remainder, not a percentage, so it scales with the folder."""
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 18, prefix="server", tags="[learning, mcp]")
    _crowd_from(topic, 4, start=19, prefix="其他", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]

    # Four left over cannot become a folder, so pulling `mcp` out is a rename.
    assert "mcp" not in {item["term"] for item in clusters}


def test_a_term_equal_to_the_folder_name_is_a_tautology(tmp_path: Path):
    """`20-Learning/AI-Agent/ai-agent/` renames the folder rather than splitting it.

    The remainder rule alone misses this: on the reference Vault `ai-agent`
    covers 25 of 34 notes and leaves 9 behind, which is a viable folder.
    """
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "AI-Agent"
    topic.mkdir()
    _crowd(topic, 15, prefix="server", tags="[learning, ai-agent]")
    _crowd_from(topic, 9, start=16, prefix="其他", tags="[learning, mcp]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]
    terms = {item["term"] for item in clusters}

    assert "ai-agent" not in terms
    assert "mcp" in terms


def test_a_title_token_that_is_part_of_a_tag_is_not_a_separate_subject(tmp_path: Path):
    """`ai` and `agent` are `ai-agent` seen twice.

    The existing guard only dropped a title token equal to a whole tag, so both
    halves of every hyphenated tag kept their own slot.
    """
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "Backend"
    topic.mkdir()
    _crowd(topic, 14, prefix="spring boot", tags="[learning, spring-boot]")
    _crowd_from(topic, 8, start=15, prefix="其他", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]
    terms = {item["term"] for item in clusters}

    assert "spring-boot" in terms
    assert "spring" not in terms
    assert "boot" not in terms


def test_a_title_token_merely_contained_in_a_tag_still_counts(tmp_path: Path):
    """Hyphen parts, not substrings: an unrelated token must not be swallowed."""
    vault = _make_vault(tmp_path)
    topic = vault / "20-Learning" / "Backend"
    topic.mkdir()
    # `kafka` is not a part of `spring-boot` and is nobody's tag, so it keeps
    # its own slot even though a hyphenated tag is being counted alongside it.
    _crowd(topic, 14, prefix="kafka streams", tags="[learning, spring-boot]")
    _crowd_from(topic, 8, start=15, prefix="其他", tags="[learning]")

    clusters = collect(vault)["crowded_folders"][0]["clusters"]
    terms = {item["term"] for item in clusters}

    assert "kafka" in terms
