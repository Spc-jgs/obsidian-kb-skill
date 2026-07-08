"""Tests for the reusable Obsidian vault auditor."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_vault import audit_vault


def codes(vault: Path) -> set[str]:
    return {finding.code for finding in audit_vault(vault)}


def configure_folder_index(
    vault: Path,
    *,
    user_specified: bool,
    index_filename: str = "INDEX",
    graph_overwrite: bool = True,
    excluded: list[str] | None = None,
) -> None:
    obsidian = vault / ".obsidian"
    plugin = obsidian / "plugins" / "obsidian-folder-index"
    plugin.mkdir(parents=True, exist_ok=True)
    (obsidian / "community-plugins.json").write_text(
        json.dumps(["obsidian-folder-index"]), encoding="utf-8"
    )
    (plugin / "data.json").write_text(
        json.dumps(
            {
                "graphOverwrite": graph_overwrite,
                "rootIndexFile": "INDEX.md",
                "indexFileUserSpecified": user_specified,
                "indexFilename": index_filename,
                "excludeFolders": excluded or [],
                "excludePatterns": [],
            }
        ),
        encoding="utf-8",
    )


def make_index(path: Path, note_type: str = "folder-index") -> None:
    path.write_text(
        f"---\ntype: {note_type}\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )


def write_note(path: Path) -> None:
    path.write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Note\n",
        encoding="utf-8",
    )


def test_reports_missing_required_frontmatter(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text("# Note\n", encoding="utf-8")

    assert {
        "missing-frontmatter",
        "missing-date",
        "missing-type",
        "missing-tags",
    } <= codes(tmp_path)


def test_accepts_folder_index_without_date(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )

    assert codes(tmp_path) == set()


def test_reports_missing_folder_index_content_block(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n# Notes\n",
        encoding="utf-8",
    )

    assert "missing-folder-index-content" in codes(tmp_path)


def test_reports_duplicate_folder_index_content_blocks(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n"
        "## Manual navigation\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )

    assert "duplicate-folder-index-content" in codes(tmp_path)


def test_reports_unclosed_fence_and_broken_wikilink(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n[[Missing]]\n```dataview\nLIST\n",
        encoding="utf-8",
    )

    assert {"unclosed-fence", "broken-wikilink"} <= codes(tmp_path)


def test_reports_duplicate_index_owners(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    folder = tmp_path / "Topic"
    folder.mkdir()
    for name in ("INDEX.md", "Topic.md"):
        (folder / name).write_text(
            "---\ntype: folder-index\ntags: [moc]\n---\n"
            "```folder-index-content\n```\n",
            encoding="utf-8",
        )

    assert "duplicate-folder-index" in codes(tmp_path)


def test_reports_ambiguous_filename_only_wikilink(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    for folder_name in ("A", "B"):
        folder = tmp_path / folder_name
        folder.mkdir()
        (folder / "INDEX.md").write_text(
            "---\ntype: folder-index\ntags: [moc]\n---\n"
            "```folder-index-content\n```\n",
            encoding="utf-8",
        )
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: daily-note\n'
        "tags: [daily]\n---\n[[INDEX]]\n",
        encoding="utf-8",
    )

    assert "ambiguous-wikilink" in codes(tmp_path)


def test_resolves_path_link_alias_heading_and_attachment(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    topic = tmp_path / "Topic"
    topic.mkdir()
    (topic / "Existing.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Existing\n",
        encoding="utf-8",
    )
    attachments = tmp_path / "Attachments"
    attachments.mkdir()
    (attachments / "image.png").write_bytes(b"png")
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: daily-note\n'
        "tags: [daily]\n---\n"
        "[[Topic/Existing#Existing|Related]]\n![[image.png]]\n",
        encoding="utf-8",
    )

    assert "broken-wikilink" not in codes(tmp_path)
    assert "ambiguous-wikilink" not in codes(tmp_path)


def test_ignores_example_links_in_repository_documentation(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "README.md").write_text(
        "Use `[[Missing]]` as an example.\n",
        encoding="utf-8",
    )

    assert codes(tmp_path) == set()


def test_ignores_wikilinks_inside_inline_and_fenced_code(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "Use `[[Inline Example]]`.\n"
        "```markdown\n[[Fenced Example]]\n```\n",
        encoding="utf-8",
    )

    assert "broken-wikilink" not in codes(tmp_path)


def test_reports_invalid_and_excessive_tags(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning, Bad_Tag, three, four, five, six]\n---\n",
        encoding="utf-8",
    )

    assert {"invalid-tag", "too-many-tags"} <= codes(tmp_path)


def test_reports_graph_incompatible_uniform_custom_index_name(tmp_path):
    configure_folder_index(tmp_path, user_specified=True, index_filename="INDEX")
    make_index(tmp_path / "INDEX.md", note_type="moc")
    topic = tmp_path / "Topic"
    topic.mkdir()
    make_index(topic / "INDEX.md")

    assert "graph-incompatible-index-config" in codes(tmp_path)


def test_accepts_native_folder_named_graph_chain(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    topic = tmp_path / "Topic"
    topic.mkdir()
    make_index(topic / "Topic.md")
    write_note(topic / "2026-07-08 Note.md")

    assert not {
        "graph-incompatible-index-config",
        "missing-folder-index",
        "misnamed-folder-index",
        "broken-folder-graph-chain",
    } & codes(tmp_path)


def test_reports_missing_and_misnamed_native_folder_indexes(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    (tmp_path / "Missing").mkdir()
    legacy = tmp_path / "Legacy"
    legacy.mkdir()
    make_index(legacy / "INDEX.md")

    assert {"missing-folder-index", "misnamed-folder-index"} <= codes(tmp_path)


def test_excluded_folder_does_not_require_native_index(tmp_path):
    configure_folder_index(tmp_path, user_specified=False, excluded=["Templates"])
    make_index(tmp_path / "INDEX.md", note_type="moc")
    (tmp_path / "Templates").mkdir()

    assert "missing-folder-index" not in codes(tmp_path)
