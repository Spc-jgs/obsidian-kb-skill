"""Tests for scripts/update_note.py — the handoff memory updater.

Covers: upsert init, field updates, Log append, Log TTL cap, list de-dup,
and dry-run safety.
"""
import pathlib
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import obsidian_kb_skill.scripts.update_note as update_note  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    return tmp_path


def _note(vault, rel="Tasks/foo/TASK.md"):
    return vault / rel


def test_init_creates_template_with_task_memory_enabled(vault):
    note = _note(vault)
    rc = update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    assert rc == 0
    assert note.exists()
    meta, _ = update_note.split_frontmatter(note.read_text(encoding="utf-8"))
    assert meta.get("type") == "task-memory"
    assert meta.get("task-memory") == "enabled"
    assert meta.get("status") == "active"


def test_dry_run_does_not_write(vault):
    note = _note(vault)
    rc = update_note.main([str(vault), "--note", "Tasks/foo/TASK.md"])
    assert rc == 0
    assert not note.exists()  # nothing written without --apply


def test_update_sets_step_and_appends_decision_and_log(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    rc = update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--status", "blocked", "--step", "data layer",
        "--add-decision", "Use Postgres",
        "--by", "WorkBuddy", "--log", "scaffold done", "--apply",
    ])
    assert rc == 0
    text = note.read_text(encoding="utf-8")
    meta, body = update_note.split_frontmatter(text)
    assert meta["status"] == "blocked"
    assert meta["step"] == "data layer"
    assert "Use Postgres" in meta["decisions"]
    assert "## Log" in body
    assert "[WorkBuddy] scaffold done" in body


def test_prose_sections_not_clobbered(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    # Agent writes some prose into the Decisions section.
    text = note.read_text(encoding="utf-8")
    text = text.replace(
        "## Decisions (crystallized)\n- ...",
        "## Decisions (crystallized)\n- existing human note",
    )
    note.write_text(text, encoding="utf-8")
    update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--add-open", "need API key", "--apply",
    ])
    new_text = note.read_text(encoding="utf-8")
    assert "existing human note" in new_text  # prose preserved
    meta, _ = update_note.split_frontmatter(new_text)
    assert "need API key" in meta["open"]


def test_list_fields_dedup(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--add-agent", "Codex", "--add-agent", "Codex", "--apply",
    ])
    text = note.read_text(encoding="utf-8")
    meta, _ = update_note.split_frontmatter(text)
    assert meta["agents"].count("Codex") == 1


def test_log_ttl_caps_to_last_30(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    for i in range(35):
        update_note.main([
            str(vault), "--note", "Tasks/foo/TASK.md",
            "--by", "A", "--log", f"entry {i}", "--apply",
        ])
    text = note.read_text(encoding="utf-8")
    # Count dash-lines inside the ## Log section only.
    lines = text.splitlines()
    log_start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Log")
    log_block = []
    for ln in lines[log_start + 1:]:
        if ln.startswith("## "):
            break
        if ln.startswith("- "):
            log_block.append(ln)
    assert len(log_block) == 30
    # Oldest entries dropped; newest present.
    assert any("entry 34" in ln for ln in log_block)
    assert not any("entry 0" in ln for ln in log_block)


def test_replace_decision_resolves_conflict(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--add-decision", "Use Mongo", "--apply",
    ])
    # Contradiction: switch to Postgres -> must REPLACE, not append a 2nd line.
    rc = update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--replace-decision", "Mongo::Use Postgres (scale)", "--apply",
    ])
    assert rc == 0
    meta, _ = update_note.split_frontmatter(note.read_text(encoding="utf-8"))
    assert meta["decisions"] == ["Use Postgres (scale)"]
    # No match -> appends as a new decision (upsert; never silently drops a fix).
    update_note.main([
        str(vault), "--note", "Tasks/foo/TASK.md",
        "--replace-decision", "no-such::Add rate limiter", "--apply",
    ])
    meta, _ = update_note.split_frontmatter(note.read_text(encoding="utf-8"))
    assert "Add rate limiter" in meta["decisions"]
    assert len(meta["decisions"]) == 2


def test_non_vault_returns_exit_2(tmp_path):
    # tmp_path has no .obsidian -> not a vault; validate_vault raises SystemExit(2)
    with pytest.raises(SystemExit) as exc:
        update_note.main([str(tmp_path), "--note", "Tasks/foo/TASK.md"])
    assert exc.value.code == 2


def test_apply_runs_automatic_audit_ok(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = update_note.main(
            [str(vault), "--note", "Tasks/foo/TASK.md", "--add-open", "x", "--apply"]
        )
    assert rc == 0
    assert "AUDIT: OK" in buf.getvalue()


def test_no_audit_suppresses_audit(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = update_note.main(
            [str(vault), "--note", "Tasks/foo/TASK.md",
             "--add-open", "y", "--apply", "--no-audit"]
        )
    assert rc == 0
    assert "AUDIT:" not in buf.getvalue()


def test_suggest_links_after_update(vault):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    (vault / "Tasks" / "foo" / "Related.md").write_text(
        '---\ntype: project-note\ndate: 2026-07-01\ntags: [task]\n---\n'
        "# Related\n\nContext.\n",
        encoding="utf-8",
    )
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = update_note.main(
            [str(vault), "--note", "Tasks/foo/TASK.md",
             "--add-open", "z", "--apply", "--suggest-links"]
        )
    assert rc == 0
    assert "SUGGESTED LINKS" in buf.getvalue()
    assert "Related" in buf.getvalue()
