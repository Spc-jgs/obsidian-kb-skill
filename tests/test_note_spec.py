"""Tests for the note-type single source (note_spec.py) and scaffold_templates.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from scripts import note_spec
from scripts.note_spec import (
    DEFAULT_TAG_BY_TYPE,
    EXTRA_FIELDS,
    NOTE_TYPES,
    TASK_DEFAULT_BODY,
)

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "scaffold_templates.py"


def test_all_nine_types_present():
    assert set(NOTE_TYPES) == {
        "daily-note",
        "meeting-note",
        "learning-note",
        "web-clip",
        "insight-note",
        "conversation-digest",
        "project-note",
        "person-note",
        "task-memory",
    }


def test_web_clip_fields_match_spec():
    # The fields create_note writes must equal the spec's fields (no drift).
    assert EXTRA_FIELDS["web-clip"] == {
        "source": "",
        "author": "",
        "published": "",
        "related": [],
    }


def test_default_tag_matches_spec():
    assert DEFAULT_TAG_BY_TYPE["insight-note"] == "insight"
    assert DEFAULT_TAG_BY_TYPE["person-note"] == "people"


def test_task_default_body_is_the_spec_body():
    assert TASK_DEFAULT_BODY == NOTE_TYPES["task-memory"]["body"]
    assert "## Log" in TASK_DEFAULT_BODY


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def test_scaffold_dry_run_lists_all(tmp_path, capsys):
    vault = _make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault)],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, r.stderr
    assert "would  : Daily Note.md" in r.stdout
    assert "would  : TASK.md" in r.stdout
    assert not (vault / "Templates").exists() or not list((vault / "Templates").glob("*.md"))


def test_scaffold_apply_writes_templates(tmp_path):
    vault = _make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--apply"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, r.stderr
    templates = sorted(p.name for p in (vault / "Templates").glob("*.md"))
    assert "Daily Note.md" in templates
    assert "Web Clip.md" in templates
    assert "TASK.md" in templates
    # Generated template frontmatter matches the spec (type + tags).
    web = (vault / "Templates" / "Web Clip.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(web.split("---")[1])
    assert meta["type"] == "web-clip"
    assert meta["tags"] == ["web-clip"]
    assert meta["author"] == ""


def test_scaffold_skips_existing_without_force(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "Templates").mkdir()
    existing = vault / "Templates" / "Daily Note.md"
    existing.write_text("CUSTOM USER TEMPLATE\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--apply"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, r.stderr
    # Existing template preserved; others written.
    assert existing.read_text(encoding="utf-8") == "CUSTOM USER TEMPLATE\n"
    assert (vault / "Templates" / "Insight Note.md").is_file()
    assert "exists" in r.stdout


def test_scaffold_force_overwrites(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "Templates").mkdir()
    existing = vault / "Templates" / "Daily Note.md"
    existing.write_text("CUSTOM\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--apply", "--force"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, r.stderr
    text = existing.read_text(encoding="utf-8")
    assert "CUSTOM" not in text
    assert "type: daily-note" in text
