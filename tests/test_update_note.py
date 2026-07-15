"""Tests for scripts/update_note.py — the handoff memory updater.

Covers: upsert init, field updates, Log append, Log TTL cap, list de-dup,
and dry-run safety.
"""
import json
import pathlib
import sys

import pytest
import yaml

from obsidian_kb_skill.scripts.backup_policy import CleanupResult
from obsidian_kb_skill.scripts.vault_paths import PathOutsideVaultError

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


def test_existing_note_is_backed_up_before_apply_and_reported_in_json(
    vault, monkeypatch, capsys
):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    original = note.read_bytes()
    capsys.readouterr()
    monkeypatch.setattr(
        update_note, "_backup_timestamp", lambda: "2026-07-10-123456"
    )

    rc = update_note.main(
        [
            str(vault),
            "--note",
            "Tasks/foo/TASK.md",
            "--add-open",
            "verify release",
            "--apply",
            "--no-audit",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backup"] == (
        ".obsidian-kb-backups/2026-07-10-123456/Tasks/foo/TASK.md"
    )
    backup = vault / payload["backup"]
    assert backup.read_bytes() == original
    assert note.read_bytes() != original


def test_existing_note_dry_run_creates_no_backup(vault, capsys):
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    capsys.readouterr()

    rc = update_note.main(
        [str(vault), "--note", "Tasks/foo/TASK.md", "--add-open", "preview"]
    )

    assert rc == 0
    assert not (vault / ".obsidian-kb-backups").exists()


def test_backup_note_never_overwrites_same_timestamp(vault):
    note = _note(vault)
    note.parent.mkdir(parents=True)
    note.write_bytes(b"first")

    first = update_note.backup_note(
        vault, note, timestamp="2026-07-10-123456"
    )
    note.write_bytes(b"second")
    second = update_note.backup_note(
        vault, note, timestamp="2026-07-10-123456"
    )

    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
    assert first != second
    assert second.parents[2].name == "2026-07-10-123456-2"


def test_backup_note_rejects_broken_symlink_target_without_writing_outside(vault):
    note = _note(vault)
    note.parent.mkdir(parents=True)
    note.write_bytes(b"original")
    outside = vault.parent / "outside" / "TASK.md"
    outside.parent.mkdir()
    link = (
        vault
        / ".obsidian-kb-backups"
        / "2026-07-10-123456"
        / "Tasks/foo/TASK.md"
    )
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(PathOutsideVaultError):
        update_note.backup_note(vault, note, timestamp="2026-07-10-123456")

    assert link.is_symlink()
    assert not outside.exists()


def test_backup_failure_aborts_without_modifying_note(vault, monkeypatch, capsys):
    note = _note(vault)
    update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
    original = note.read_bytes()
    capsys.readouterr()

    def fail_backup(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(update_note, "backup_note", fail_backup)
    rc = update_note.main(
        [
            str(vault),
            "--note",
            "Tasks/foo/TASK.md",
            "--add-open",
            "must not land",
            "--apply",
        ]
    )

    assert rc != 0
    assert "backup failed" in capsys.readouterr().err.lower()
    assert note.read_bytes() == original


def test_cleanup_runs_only_after_successful_write(vault, monkeypatch):
    note = _note(vault)
    assert update_note.main(
        [str(vault), "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit"]
    ) == 0
    calls = []
    original_write = pathlib.Path.write_bytes

    def tracked_write(path, data):
        if path == note:
            calls.append("write")
        return original_write(path, data)

    def tracked_prune(vault_arg, policy, protected=None):
        calls.append("prune")
        assert vault_arg == vault
        assert protected is not None and protected.is_file()
        return CleanupResult(policy.keep_per_note, scanned=2, deleted=1)

    monkeypatch.setattr(pathlib.Path, "write_bytes", tracked_write)
    monkeypatch.setattr(update_note, "prune_backups", tracked_prune)
    assert update_note.main(
        [
            str(vault),
            "--note",
            "Tasks/foo/TASK.md",
            "--add-open",
            "ordered",
            "--apply",
            "--no-audit",
        ]
    ) == 0
    assert calls == ["write", "prune"]


def test_note_write_failure_never_prunes(vault, monkeypatch):
    note = _note(vault)
    assert update_note.main(
        [str(vault), "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit"]
    ) == 0
    original_write = pathlib.Path.write_bytes

    def fail_note_write(path, data):
        if path == note:
            raise OSError("disk")
        return original_write(path, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", fail_note_write)
    monkeypatch.setattr(
        update_note,
        "prune_backups",
        lambda *_args, **_kwargs: pytest.fail("cleanup ran before failed write"),
    )
    with pytest.raises(OSError, match="disk"):
        update_note.main(
            [
                str(vault),
                "--note",
                "Tasks/foo/TASK.md",
                "--add-open",
                "must not land",
                "--apply",
                "--no-audit",
            ]
        )


def test_cleanup_warning_does_not_fail_committed_write(
    vault, monkeypatch, capsys
):
    note = _note(vault)
    assert update_note.main(
        [str(vault), "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit"]
    ) == 0
    capsys.readouterr()
    monkeypatch.setattr(
        update_note,
        "prune_backups",
        lambda *_args, **_kwargs: CleanupResult(
            keep_per_note=1,
            scanned=2,
            deleted=0,
            warnings=("cannot delete old backup",),
        ),
    )
    assert update_note.main(
        [
            str(vault),
            "--note",
            "Tasks/foo/TASK.md",
            "--add-open",
            "committed despite cleanup warning",
            "--apply",
            "--no-audit",
        ]
    ) == 0
    assert "committed despite cleanup warning" in note.read_text(encoding="utf-8")
    assert capsys.readouterr().err.count("cannot delete old backup") == 1


def test_cleanup_exception_does_not_fail_committed_write(
    vault, monkeypatch, capsys
):
    note = _note(vault)
    assert update_note.main(
        [str(vault), "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit"]
    ) == 0
    capsys.readouterr()

    def fail_cleanup(*_args, **_kwargs):
        raise OSError("cleanup disk error")

    monkeypatch.setattr(update_note, "prune_backups", fail_cleanup)
    assert update_note.main(
        [
            str(vault),
            "--note",
            "Tasks/foo/TASK.md",
            "--add-open",
            "write remains successful",
            "--apply",
            "--no-audit",
        ]
    ) == 0
    assert "write remains successful" in note.read_text(encoding="utf-8")
    assert "cleanup disk error" in capsys.readouterr().err


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
        '---\ntype: task-memory\ndate: 2026-07-01\ntags: [task]\n---\n'
        "# TASK Related\n\nContext.\n",
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
