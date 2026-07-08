"""Smoke tests for configuration-aware installer index generation."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from scripts.audit_vault import audit_vault


ROOT = Path(__file__).resolve().parent.parent


def run_bash_installer(tmp_path: Path, settings: dict | None = None) -> Path:
    vault = tmp_path / "vault"
    home = tmp_path / "home"
    vault.mkdir()
    home.mkdir()
    if settings is not None:
        obsidian = vault / ".obsidian"
        plugin = obsidian / "plugins" / "obsidian-folder-index"
        plugin.mkdir(parents=True)
        (obsidian / "community-plugins.json").write_text(
            json.dumps(["obsidian-folder-index"]), encoding="utf-8"
        )
        (plugin / "data.json").write_text(json.dumps(settings), encoding="utf-8")
    env = os.environ.copy()
    env["HOME"] = str(home)
    subprocess.run(
        [
            "bash",
            str(ROOT / "install.sh"),
            "--vault",
            str(vault),
            "--platforms",
            "qoderwork",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return vault


def native_settings() -> dict:
    return {
        "graphOverwrite": True,
        "rootIndexFile": "INDEX.md",
        "indexFileUserSpecified": False,
        "indexFilename": "INDEX",
        "excludeFolders": ["Templates", "Attachments"],
        "excludePatterns": [],
    }


def test_bash_installer_uses_native_folder_named_indexes(tmp_path):
    vault = run_bash_installer(tmp_path, native_settings())

    index = vault / "20-Learning" / "20-Learning.md"
    assert index.is_file()
    assert not (vault / "20-Learning" / "INDEX.md").exists()
    assert "```folder-index-content" in index.read_text(encoding="utf-8")
    assert (vault / "90-Archive" / "90-Archive.md").is_file()
    root = (vault / "INDEX.md").read_text(encoding="utf-8")
    assert "[[20-Learning/20-Learning|Learning]]" in root
    assert audit_vault(vault) == []


def test_bash_installer_keeps_dataview_fallback_without_folder_index(tmp_path):
    vault = run_bash_installer(tmp_path)

    index = vault / "20-Learning" / "INDEX.md"
    assert index.is_file()
    assert "```dataview" in index.read_text(encoding="utf-8")
    assert audit_vault(vault) == []


def test_powershell_installer_has_native_folder_index_parity():
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "indexFileUserSpecified" in script
    assert "rootIndexFile" in script
    assert "folder-index-content" in script
