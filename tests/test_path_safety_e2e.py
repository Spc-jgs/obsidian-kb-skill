"""CLI-level Vault path-safety end-to-end tests (v1.10.1, Step 2).

These prove the boundary at the *command* layer, not just the module:

  * a high-risk command given an escaping path MUST fail (non-zero exit),
  * it MUST NOT leak a Python traceback or internal system paths to the user,
  * a sentinel file placed OUTSIDE the temp vault MUST be byte-for-byte
    unchanged afterwards (no silent write outside the boundary).

They are RED until the CLIs route every Vault path through
obsidian_kb_skill.scripts.vault_paths and reject escapes with exit code 3.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}

# Exit code agreed for path/security violations.
EXIT_PATH_VIOLATION = 3


def _run(module: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", f"obsidian_kb_skill.scripts.{module}", *args],
        cwd=str(ROOT),
        env=ENV,
        capture_output=True,
        text=True,
    )


def _no_traceback(proc: subprocess.CompletedProcess) -> None:
    combined = proc.stdout + proc.stderr
    assert "Traceback" not in combined, f"traceback leaked:\n{combined}"
    assert "vault_paths.py" not in combined, f"internal path leaked:\n{combined}"
    assert "File \"" not in combined, f"internal file path leaked:\n{combined}"


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    (vault / "00-Inbox").mkdir()
    return vault


# --- create_note: escaping --folder ------------------------------------------

def test_create_note_rejects_escaping_folder(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("SENTINEL-ORIGINAL", encoding="utf-8")

    proc = _run(
        "create_note",
        str(vault),
        "--type", "insight-note",
        "--title", "Escape",
        "--folder", "../outside",
        "--apply",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    _no_traceback(proc)
    # No new note was written into the outside directory.
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL-ORIGINAL"
    assert [p.name for p in outside.glob("*.md")] == ["sentinel.md"]


def test_create_note_rejects_absolute_outside_folder(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("SENTINEL-ORIGINAL", encoding="utf-8")

    proc = _run(
        "create_note",
        str(vault),
        "--type", "insight-note",
        "--title", "Escape",
        "--folder", str(outside),
        "--apply",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    _no_traceback(proc)
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL-ORIGINAL"


def test_create_note_accepts_inside_folder(tmp_path):
    vault = _make_vault(tmp_path)
    proc = _run(
        "create_note",
        str(vault),
        "--type", "insight-note",
        "--title", "Inside",
        "--folder", "30-Insights",
        "--apply",
    )
    assert proc.returncode == 0, proc.stderr
    assert list((vault / "30-Insights").glob("*.md"))


# --- update_note: external existing file (sentinel overwrite) ----------------

def test_update_note_rejects_external_existing_file(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("SENTINEL-ORIGINAL", encoding="utf-8")

    proc = _run(
        "update_note",
        str(vault),
        "--note", "../sentinel.md",
        "--status", "blocked",
        "--apply",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    _no_traceback(proc)
    # The external file must NOT have been touched.
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL-ORIGINAL"


# --- process_inbox: external inbox dir ---------------------------------------

def test_process_inbox_rejects_external_inbox(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    note = outside / "Stray.md"
    note.write_text("---\ntype: insight-note\n---\nbody\n", encoding="utf-8")

    proc = _run(
        "process_inbox",
        str(vault),
        "--inbox", "../outside",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    _no_traceback(proc)
    # The external note must stay put (must not be moved into the vault).
    assert note.exists()
    assert not list((vault / "30-Insights").glob("Stray.md"))


# --- JSON mode: structured error + security exit code ------------------------

def test_create_note_json_escape_returns_structured_error(tmp_path):
    import json as _json

    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("SENTINEL-ORIGINAL", encoding="utf-8")

    proc = _run(
        "create_note",
        str(vault),
        "--type", "insight-note",
        "--title", "Escape",
        "--folder", "../outside",
        "--apply",
        "--json",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    payload = _json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert payload["error"]["details"]["param"] == "--folder"
    # No internal path leakage in the message.
    assert "vault_paths.py" not in proc.stdout
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL-ORIGINAL"


def test_update_note_json_escape_returns_structured_error(tmp_path):
    import json as _json

    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("SENTINEL-ORIGINAL", encoding="utf-8")

    proc = _run(
        "update_note",
        str(vault),
        "--note", "../sentinel.md",
        "--status", "blocked",
        "--apply",
        "--json",
    )

    assert proc.returncode == EXIT_PATH_VIOLATION, proc.stderr
    payload = _json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert payload["error"]["details"]["param"] == "--note"
    assert sentinel.read_text(encoding="utf-8") == "SENTINEL-ORIGINAL"
