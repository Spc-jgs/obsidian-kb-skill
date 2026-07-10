"""Tests for --json machine-readable output across every script that supports it.

A consistent JSON contract lets an agent (or another tool) drive every script
without parsing human text. This file verifies the contract: when --json is
passed, stdout is a single JSON document with predictable fields.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> dict:
    env = {**__import__("os").environ, "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable] + args, capture_output=True, text=True, cwd=str(REPO), env=env
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}\nstdout={r.stdout!r}"
    return json.loads(r.stdout)


def _make_vault(root: Path) -> Path:
    v = root / "vault"
    (v / ".obsidian").mkdir(parents=True)
    (v / "Templates").mkdir()
    (v / "30-Insights").mkdir()
    return v


# ---- audit_vault --------------------------------------------------------------

def test_audit_vault_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "Bad.md").write_text(
        "---\ndate: 2026-07-09\ntags: [a, b, c, d, e, f]\n---\n", encoding="utf-8"
    )
    out = _run(["-m", "obsidian_kb_skill.scripts.audit_vault", str(vault), "--json"])
    assert "count" in out and "findings" in out
    assert isinstance(out["findings"], list)
    # Each finding has code/path/message.
    for f in out["findings"]:
        assert {"code", "path", "message"} <= set(f)


# ---- suggest_links ------------------------------------------------------------

def test_suggest_links_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "Other.md").write_text(
        '---\ntype: insight-note\ndate: 2026-07-01\ntags: [insight]\n---\n# Other\nbody.\n',
        encoding="utf-8",
    )
    note = vault / "30-Insights" / "Target.md"
    note.write_text(
        '---\ntype: insight-note\ndate: 2026-07-09\ntags: [insight]\n---\n# Target\nbody.\n',
        encoding="utf-8",
    )
    out = _run([
        "-m", "obsidian_kb_skill.scripts.suggest_links", str(vault),
        "--note", str(note), "--json",
    ])
    assert isinstance(out, list)
    if out:
        item = out[0]
        assert {"path", "score", "reasons"} <= set(item)


# ---- detect_index -------------------------------------------------------------

def test_detect_index_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.detect_index", str(vault),
        "--folder", "30-Insights",
    ])
    # Already JSON by default; check the schema.
    assert out["mode"] == "static"
    assert "can_append" in out
    assert "index_file" in out
    assert "notes" in out


# ---- vault_info ---------------------------------------------------------------

def test_vault_info_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run(["-m", "obsidian_kb_skill.scripts.vault_info", str(vault)])
    assert out["valid"] is True
    assert "validation" in out
    assert "templates" in out
    assert "standard_folders" in out
    assert "folder_index_global" in out


# ---- process_inbox ------------------------------------------------------------

def test_process_inbox_plan_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    (vault / "00-Inbox").mkdir()
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )
    out = _run([
        "-m", "obsidian_kb_skill.scripts.process_inbox", str(vault), "--json",
    ])
    assert isinstance(out, list)
    assert out and out[0]["target"] == "30-Insights"


# ---- create_note --------------------------------------------------------------

def test_create_note_dry_run_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
        "--type", "insight-note", "--title", "Json", "--stdin", "--json",
    ])
    assert out["dry_run"] is True
    assert out["applied"] is False
    assert "rendered" in out
    assert out["path"].endswith("Json.md")
    assert out["audit"] is None  # dry run, no audit


def test_create_note_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
        "--type", "insight-note", "--title", "Wrote", "--stdin",
        "--apply", "--no-audit", "--json",
    ])
    assert out["applied"] is True
    assert "rendered" in out
    # Audit was suppressed but the key still exists.
    assert out["audit"] is None


def test_create_note_apply_with_audit_json(tmp_path):
    vault = _make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
         "--type", "insight-note", "--title", "Audited", "--stdin",
         "--apply", "--json"],
        input="# Insight\n\nReal body content here.\n",
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["audit"]["ok"] is True
    assert out["audit"]["count"] == 0


# ---- update_note --------------------------------------------------------------

def test_update_note_dry_run_json(tmp_path):
    vault = _make_vault(tmp_path)
    note = vault / "Tasks" / "foo" / "TASK.md"
    out = _run([
        "-m", "obsidian_kb_skill.scripts.update_note", str(vault),
        "--note", str(note.relative_to(vault)), "--json",
    ])
    assert out["dry_run"] is True
    assert out["action"] == "init"  # doesn't exist yet -> init


def test_update_note_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.update_note", str(vault),
        "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit", "--json",
    ])
    assert out["applied"] is True
    assert out["action"] == "init"


# ---- scaffold_templates ------------------------------------------------------

def test_scaffold_templates_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.scaffold_templates", str(vault),
        "--apply", "--json",
    ])

    assert out["schema_version"] == "1.0"
    assert out["operation"] == "scaffold-templates"
    assert out["apply"] is True
    assert out["force"] is False
    assert out["written"]
    assert isinstance(out["skipped"], list)
    assert Path(out["templates_dir"]) == vault / "Templates"
