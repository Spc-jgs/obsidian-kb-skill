"""Tests for the note creator (scripts/create_note.py)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.create_note import (
    build_note,
    resolve_dest,
    sanitize_filename,
    split_frontmatter,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "create_note.py"


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def test_build_note_defaults_insight():
    folder, rendered = build_note(
        note_type="insight-note", title="T", date="2026-07-09", body="# hi\n"
    )
    assert folder == "30-Insights"
    assert "type: insight-note" in rendered
    assert "date:" in rendered and "2026-07-09" in rendered
    assert "tags:" in rendered and "- insight" in rendered
    assert "related: []" in rendered
    assert "source:" in rendered  # insight extra field


def test_build_note_web_clip_has_required_fields():
    _, rendered = build_note(
        note_type="web-clip", title="C", date="2026-07-09", body="x"
    )
    for field in ("source:", "author:", "published:"):
        assert field in rendered


def test_build_note_unknown_type_raises():
    with pytest.raises(ValueError):
        build_note(note_type="nope", title="T", date="2026-07-09", body="")


def test_split_frontmatter_merges():
    meta, body = split_frontmatter("---\nfoo: bar\n---\n# Body\n")
    assert meta.get("foo") == "bar"
    assert body.strip() == "# Body"


def test_sanitize_filename_strips_unsafe():
    assert "/" not in sanitize_filename('a/b:c*?"<>|')
    assert sanitize_filename("   ") == "untitled"


def test_resolve_dest_appends_suffix(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "2026-07-09 T.md").write_text("x", encoding="utf-8")
    dest = resolve_dest(vault, "30-Insights", "2026-07-09 T.md")
    assert dest.name == "2026-07-09 T-2.md"


def test_dry_run_writes_nothing(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Dry", "--stdin"],
        input="# dry\n", capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0
    assert "dry run" in r.stdout
    assert not list((vault / "30-Insights").glob("*.md"))


def test_apply_creates_note_and_updates_index(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Created", "--stdin", "--apply"],
        input="# body\n", capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    created = vault / "30-Insights" / "2026-07-09 Created.md"
    assert created.is_file()
    text = created.read_text(encoding="utf-8")
    assert "type: insight-note" in text
    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    assert "[[" in index_text
    assert "Created" in index_text


def test_apply_refuses_non_vault(tmp_path):
    not_vault = tmp_path / "notvault"
    not_vault.mkdir()
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(not_vault), "--type", "insight-note",
         "--title", "X", "--stdin", "--apply"],
        input="x", capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 2
    assert not list(not_vault.glob("*.md"))


def test_apply_never_overwrites(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "2026-07-09 Dup.md").write_text("orig", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Dup", "--stdin", "--apply"],
        input="new", capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0
    assert (vault / "30-Insights" / "2026-07-09 Dup-2.md").is_file()
    assert (vault / "30-Insights" / "2026-07-09 Dup.md").read_text(encoding="utf-8") == "orig"


def test_apply_runs_automatic_audit_ok(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Audited", "--stdin", "--apply"],
        input="# Insight\n\nThis is the actual note content.\n",
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT: OK" in r.stdout


def test_apply_audit_flags_broken_wikilink(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Broken", "--stdin", "--apply"],
        input="see [[No Such Note]]\n", capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT:" in r.stdout
    assert "broken-wikilink" in r.stdout


def test_no_audit_suppresses_audit(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "Quiet", "--stdin", "--apply", "--no-audit"],
        input="# Insight\n\nThis is the actual note content.\n",
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT:" not in r.stdout
