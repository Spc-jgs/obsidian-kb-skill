"""Tests for the user-template-driven create_note path.

The vault's {VAULT}/Templates/<Name>.md is the single source of truth at write
time. create_note.py must read it, fill {{date}} placeholders, merge its
frontmatter, and use its body as the scaffold. This file proves that contract
end-to-end so P5r (the rewrite) doesn't silently regress to hardcoded bodies.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from scripts.create_note import build_note

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "create_note.py"


def _vault_with_template(
    tmp_path: Path,
    *,
    type_name: str,
    tpl_filename: str,
    tpl_fm: dict,
    tpl_body: str,
) -> Path:
    """Build a minimal vault with a single user template inside Templates/."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    fm = yaml.safe_dump(
        tpl_fm, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    (vault / "Templates" / tpl_filename).write_text(
        f"---\n{fm}\n---\n{tpl_body}", encoding="utf-8"
    )
    return vault


def test_user_template_body_used_when_no_content(tmp_path):
    vault = _vault_with_template(
        tmp_path,
        type_name="insight-note",
        tpl_filename="Insight Note.md",
        tpl_fm={"type": "insight-note", "tags": ["insight"], "mood": "open"},
        tpl_body="## Custom Heading\n\nUser-defined body. {{date}} placeholder\n",
    )
    folder, rendered = build_note(
        note_type="insight-note",
        title="T",
        date="2026-07-09",
        body="",
        vault=vault,
    )
    # User's body must appear; {{date}} substituted with actual date.
    assert "Custom Heading" in rendered
    assert "2026-07-09" in rendered
    assert "{{date}}" not in rendered
    # User's custom field preserved.
    meta = yaml.safe_load(rendered.split("---")[1])
    assert meta["mood"] == "open"
    assert meta["type"] == "insight-note"
    # Built-in default 'source' field also present (from EXTRA_FIELDS safety net).
    assert "source" in meta


def test_explicit_body_overrides_user_template(tmp_path):
    vault = _vault_with_template(
        tmp_path,
        type_name="insight-note",
        tpl_filename="Insight Note.md",
        tpl_fm={"type": "insight-note", "tags": ["insight"]},
        tpl_body="TEMPLATE BODY - should not appear\n",
    )
    _, rendered = build_note(
        note_type="insight-note",
        title="T",
        date="2026-07-09",
        body="# Caller Override\n\nbody wins\n",
        vault=vault,
    )
    assert "Caller Override" in rendered
    assert "TEMPLATE BODY" not in rendered


def test_no_template_falls_back_to_minimal_body(tmp_path):
    # Vault with NO Templates/Insight Note.md.
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    folder, rendered = build_note(
        note_type="insight-note",
        title="Minimal",
        date="2026-07-09",
        body="",
        vault=vault,
    )
    # No template -> minimal fallback body "# Minimal".
    assert "# Minimal" in rendered
    # But frontmatter is still valid (date, type, tags, source, related).
    meta = yaml.safe_load(rendered.split("---")[1])
    assert meta["date"] == "2026-07-09"
    assert meta["type"] == "insight-note"


def test_vault_none_disables_template_lookup(tmp_path):
    # No vault arg -> no template lookup; uses the empty-body fallback.
    folder, rendered = build_note(
        note_type="insight-note",
        title="X",
        date="2026-07-09",
        body="",
    )
    assert "# X" in rendered
    assert "source" in rendered  # safety-net field still present


def test_user_template_field_overrides_safety_net_default(tmp_path):
    """If the user puts a non-empty `source` in the template, that value wins."""
    vault = _vault_with_template(
        tmp_path,
        type_name="insight-note",
        tpl_filename="Insight Note.md",
        tpl_fm={"type": "insight-note", "tags": ["insight"], "source": "user-given"},
        tpl_body="body\n",
    )
    _, rendered = build_note(
        note_type="insight-note", title="T", date="2026-07-09", body="", vault=vault
    )
    meta = yaml.safe_load(rendered.split("---")[1])
    assert meta["source"] == "user-given"


def test_cli_create_uses_user_template(tmp_path):
    """End-to-end: create_note.py --apply writes a note whose body comes from
    the user's template and whose {{date}} placeholder is substituted."""
    vault = _vault_with_template(
        tmp_path,
        type_name="insight-note",
        tpl_filename="Insight Note.md",
        tpl_fm={"type": "insight-note", "tags": ["insight"]},
        tpl_body="## Custom Section\n\nDate marker: {{date}}\n",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(vault), "--type", "insight-note",
         "--title", "FromTpl", "--apply", "--no-audit"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, r.stderr
    note = vault / "30-Insights" / "2026-07-09 FromTpl.md"
    assert note.is_file()
    text = note.read_text(encoding="utf-8")
    assert "Custom Section" in text
    assert "Date marker: 2026-07-09" in text
    assert "{{date}}" not in text
