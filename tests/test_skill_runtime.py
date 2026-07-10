"""Black-box checks for the standard Skill's bundled helper runtime."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.resource_locator import locate_skill_resources


ROOT = Path(__file__).resolve().parent.parent
STANDARD_SKILL = ROOT / "skills" / "obsidian-knowledge-base"


def test_standard_skill_root_resolves_assets_and_references(tmp_path):
    skill = tmp_path / "obsidian-knowledge-base"
    (skill / "assets" / "templates").mkdir(parents=True)
    (skill / "references").mkdir()
    (skill / "assets" / "templates" / "daily-note.md").write_text(
        "template", encoding="utf-8"
    )
    (skill / "references" / "note-creation.md").write_text(
        "reference", encoding="utf-8"
    )

    resources = locate_skill_resources(skill_root=skill)

    assert resources.templates_dir == skill / "assets" / "templates"
    assert resources.references_dir == skill / "references"


def test_skill_runner_works_from_neutral_directory_without_repo_pythonpath(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    work = tmp_path / "neutral"
    vault = tmp_path / "vault"
    home.mkdir()
    work.mkdir()
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = ""
    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "vault-info",
            str(vault),
            "--json",
        ],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert Path(payload["vault"]) == vault.resolve()


def test_skill_runner_rejects_unknown_helper(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(STANDARD_SKILL / "scripts" / "run_helper.py"),
            "not-a-helper",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "invalid choice" in result.stderr
