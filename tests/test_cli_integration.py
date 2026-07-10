"""End-to-end CLI integration tests for the bundled scripts.

These exercise the real command-line entry points (argparse parsing, exit codes,
stdout) against throwaway temp vaults by invoking ``python -m scripts.<name>``.
That path also validates the import-fallback chain the installed console-script
entry points depend on (``from audit_vault import ... except ImportError: from
scripts.audit_vault import ...``).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(*args: str, vault: Path) -> subprocess.CompletedProcess:
    # Run so `obsidian_kb_skill` is importable as a package.
    env = {**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", *args, str(vault)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def _make_vault(
    tmp_path: Path,
    folders=("00-Inbox", "10-Work", "20-Learning", "30-Insights", "40-Projects", "50-People"),
) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    for folder in folders:
        (vault / folder).mkdir()
    return vault


def test_audit_vault_clean_vault_exits_zero(tmp_path):
    vault = _make_vault(tmp_path)
    result = _run("obsidian_kb_skill.scripts.audit_vault", vault=vault)
    assert result.returncode == 0, result.stderr
    assert "0 finding(s)" in result.stdout


def test_process_inbox_apply_moves_and_fills_note(tmp_path):
    vault = _make_vault(tmp_path)
    inbox_note = vault / "00-Inbox" / "idea.md"
    # keyword "analysis" routes to 30-Insights; no frontmatter yet.
    inbox_note.write_text("# A stray analysis idea\n\nSome insight worth keeping.\n", encoding="utf-8")

    result = _run("obsidian_kb_skill.scripts.process_inbox", "--apply", vault=vault)
    assert result.returncode == 0, result.stderr
    assert "moved:" in result.stdout
    assert "1 Inbox note(s) applied." in result.stdout

    moved = vault / "30-Insights" / "idea.md"
    assert moved.is_file()
    assert not inbox_note.exists()

    # Re-parse the filled frontmatter from the moved file.
    text = moved.read_text(encoding="utf-8")
    fm_text = text[4 : text.find("\n---\n", 4)]
    meta = yaml.safe_load(fm_text)
    assert meta["type"] == "insight-note"
    assert meta["tags"] == ["insight"]
    assert meta.get("date")


def test_process_inbox_apply_updates_static_index(tmp_path):
    vault = _make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    index.write_text("# 30-Insights\n\n## Manual Notes\n", encoding="utf-8")
    (vault / "00-Inbox" / "clip.md").write_text(
        "# An analysis worth keeping\n\nRead about something useful.\n", encoding="utf-8"
    )

    result = _run("obsidian_kb_skill.scripts.process_inbox", "--apply", vault=vault)
    assert result.returncode == 0, result.stderr

    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    assert "[[30-Insights/clip|" in index_text


def test_process_inbox_plan_is_read_only(tmp_path):
    vault = _make_vault(tmp_path)
    inbox_note = vault / "00-Inbox" / "thought.md"
    inbox_note.write_text("# Quick thought\n\nAn idea.\n", encoding="utf-8")

    result = _run("obsidian_kb_skill.scripts.process_inbox", "--plan", vault=vault)
    assert result.returncode == 0, result.stderr
    assert "FILE" in result.stdout
    # Nothing moved in plan mode.
    assert inbox_note.exists()
    assert not (vault / "30-Insights" / "thought.md").exists()


def test_suggest_links_finds_shared_tag_candidate(tmp_path):
    vault = _make_vault(tmp_path)
    alpha = vault / "30-Insights" / "Alpha.md"
    beta = vault / "30-Insights" / "Beta.md"
    alpha.write_text(
        "---\n"
        "type: insight-note\ndate: 2026-07-09\ntags: [insight, python]\n"
        "related: []\n---\n# Alpha\n\nAlpha body.\n",
        encoding="utf-8",
    )
    beta.write_text(
        "---\n"
        "type: insight-note\ndate: 2026-07-09\ntags: [insight, python]\n"
        "related: []\n---\n# Beta\n\nBeta body.\n",
        encoding="utf-8",
    )

    result = _run("obsidian_kb_skill.scripts.suggest_links", "--note", "30-Insights/Alpha.md", vault=vault)
    assert result.returncode == 0, result.stderr
    assert "Beta.md" in result.stdout
    assert "shared tags" in result.stdout
    assert "1 suggestion(s)" in result.stdout


def test_suggest_links_excludes_already_related(tmp_path):
    vault = _make_vault(tmp_path)
    alpha = vault / "30-Insights" / "Alpha.md"
    beta = vault / "30-Insights" / "Beta.md"
    alpha.write_text(
        "---\n"
        'type: insight-note\ndate: 2026-07-09\ntags: [insight, python]\n'
        'related: ["[[Beta]]"]\n---\n# Alpha\n\nAlpha body.\n',
        encoding="utf-8",
    )
    beta.write_text(
        "---\n"
        "type: insight-note\ndate: 2026-07-09\ntags: [insight, python]\n"
        "related: []\n---\n# Beta\n\nBeta body.\n",
        encoding="utf-8",
    )

    result = _run("obsidian_kb_skill.scripts.suggest_links", "--note", "30-Insights/Alpha.md", vault=vault)
    assert result.returncode == 0, result.stderr
    assert "0 suggestion(s)" in result.stdout


def test_cli_rejects_non_vault(tmp_path):
    not_a_vault = tmp_path / "notvault"
    not_a_vault.mkdir()
    result = _run("obsidian_kb_skill.scripts.audit_vault", vault=not_a_vault)
    assert result.returncode == 2
    assert "not an Obsidian vault" in result.stderr
