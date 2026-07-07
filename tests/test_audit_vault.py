"""Tests for the reusable Obsidian vault auditor."""
from pathlib import Path

from scripts.audit_vault import audit_vault


def codes(vault: Path) -> set[str]:
    return {finding.code for finding in audit_vault(vault)}


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
