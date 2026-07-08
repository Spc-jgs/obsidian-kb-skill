"""Smoke tests for configuration-aware installer index generation."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from scripts.audit_vault import audit_vault


ROOT = Path(__file__).resolve().parent.parent


def run_bash_installer(
    tmp_path: Path,
    settings: dict | None = None,
    platforms: str = "qoderwork",
    vault: Path | None = None,
    home: Path | None = None,
) -> tuple[Path, Path]:
    vault = vault or tmp_path / "vault"
    home = home or tmp_path / "home"
    vault.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
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
            platforms,
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return vault, home


def run_bash_uninstaller(vault: Path, home: Path) -> None:
    env = os.environ.copy()
    env["HOME"] = str(home)
    subprocess.run(
        [
            "bash",
            str(ROOT / "install.sh"),
            "--vault",
            str(vault),
            "--uninstall",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


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
    vault, _ = run_bash_installer(tmp_path, native_settings())

    index = vault / "20-Learning" / "20-Learning.md"
    assert index.is_file()
    assert not (vault / "20-Learning" / "INDEX.md").exists()
    assert "```folder-index-content" in index.read_text(encoding="utf-8")
    assert (vault / "90-Archive" / "90-Archive.md").is_file()
    root = (vault / "INDEX.md").read_text(encoding="utf-8")
    assert "[[20-Learning/20-Learning|Learning]]" in root
    assert audit_vault(vault) == []


def test_bash_installer_keeps_dataview_fallback_without_folder_index(tmp_path):
    vault, _ = run_bash_installer(tmp_path)

    index = vault / "20-Learning" / "INDEX.md"
    assert index.is_file()
    assert "```dataview" in index.read_text(encoding="utf-8")
    assert audit_vault(vault) == []


def test_powershell_installer_has_native_folder_index_parity():
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "indexFileUserSpecified" in script
    assert "rootIndexFile" in script
    assert "folder-index-content" in script


def test_bash_installer_uses_standard_skill_for_codex(tmp_path):
    _, home = run_bash_installer(tmp_path, platforms="codex")

    installed = home / ".agents/skills/obsidian-knowledge-base/SKILL.md"
    canonical = ROOT / "skills/obsidian-knowledge-base/SKILL.md"
    assert installed.read_bytes() == canonical.read_bytes()
    assert not (home / "AGENTS.md").exists()


def test_bash_installer_uses_standard_skill_for_qoderwork(tmp_path):
    _, home = run_bash_installer(tmp_path, platforms="qoderwork")

    installed = home / ".qoderwork/skills/obsidian-knowledge-base/SKILL.md"
    canonical = ROOT / "skills/obsidian-knowledge-base/SKILL.md"
    assert installed.read_bytes() == canonical.read_bytes()


def test_bash_codex_install_is_idempotent(tmp_path):
    vault, home = run_bash_installer(tmp_path, platforms="codex")
    installed = home / ".agents/skills/obsidian-knowledge-base/SKILL.md"
    first = installed.read_bytes()

    run_bash_installer(
        tmp_path,
        platforms="codex",
        vault=vault,
        home=home,
    )

    assert installed.read_bytes() == first
    assert list(installed.parent.glob("SKILL.md")) == [installed]


def test_bash_codex_install_accepts_symlink_to_canonical_skill(tmp_path):
    vault = tmp_path / "vault"
    home = tmp_path / "home"
    target = home / ".agents/skills/obsidian-knowledge-base"
    target.parent.mkdir(parents=True)
    target.symlink_to(ROOT / "skills/obsidian-knowledge-base", target_is_directory=True)

    run_bash_installer(
        tmp_path,
        platforms="codex",
        vault=vault,
        home=home,
    )

    assert target.is_symlink()
    assert (target / "SKILL.md").samefile(
        ROOT / "skills/obsidian-knowledge-base/SKILL.md"
    )


def test_bash_uninstall_preserves_sibling_agent_skill(tmp_path):
    vault, home = run_bash_installer(tmp_path, platforms="codex")
    sibling = home / ".agents/skills/keep-me/SKILL.md"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "---\nname: keep-me\ndescription: keep\n---\n",
        encoding="utf-8",
    )

    run_bash_uninstaller(vault, home)

    assert not (home / ".agents/skills/obsidian-knowledge-base").exists()
    assert sibling.is_file()


def test_powershell_installer_uses_standard_skill_for_codex_and_qoderwork():
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "skills\\obsidian-knowledge-base\\SKILL.md" in script
    assert ".agents\\skills\\obsidian-knowledge-base" in script
    assert "platforms\\qoderwork\\SKILL.md" not in script
