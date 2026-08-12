"""Tests for the read-only project resume pack (scripts/resume_project.py)."""
from __future__ import annotations

import datetime
from pathlib import Path

from obsidian_kb_skill.scripts import resume_project


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "40-Projects").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def write_note(
    path: Path,
    note_type: str,
    *,
    date: str = "2026-08-01",
    status: str | None = None,
    body: str = "body\n",
    extra: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_line = f"status: {status}\n" if status else ""
    path.write_text(
        f"---\ntype: {note_type}\ndate: {date}\ntags: [project]\n"
        f"{status_line}{extra}---\n\n{body}",
        encoding="utf-8",
    )


AS_OF = datetime.date(2026, 8, 12)


def test_subordinate_output_in_the_instance_directory_is_a_source(tmp_path):
    """The entity folder makes membership readable from the layout itself.

    Every other route to "which notes belong to this project" depends on a
    frontmatter field or a wikilink being maintained. A note sitting in the
    project's own directory needs neither, so it is the most reliable source
    the pack has — and it did not exist before #95.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")
    write_note(instance / "Digest.md", "conversation-digest", date="2026-08-05")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert payload["project"]["path"] == "40-Projects/etianqu/Project.md"
    assert [source["path"] for source in payload["sources"]] == [
        "40-Projects/etianqu/Digest.md"
    ]
    assert payload["sources"][0]["origin"] == "instance-directory"


def test_the_project_note_is_not_listed_as_its_own_source(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["sources"] == []


def test_notes_outside_the_instance_directory_are_not_sources(tmp_path):
    """Membership comes from the directory, never from proximity or subject."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")
    write_note(
        vault / "40-Projects" / "other-project" / "Digest.md", "conversation-digest"
    )
    write_note(vault / "30-Insights" / "Unrelated.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["sources"] == []


def test_a_note_that_is_not_a_project_note_is_refused(tmp_path):
    """The pack resumes a project; pointing it at a digest is a caller error."""
    vault = make_vault(tmp_path)
    write_note(vault / "30-Insights" / "Note.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("30-Insights/Note.md"), as_of=AS_OF
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "not-a-project-note"
