"""Smoke tests for configuration-aware installer index generation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.audit_vault import audit_vault


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _skip_bash_installer_tests_on_windows(request):
    """Bash lifecycle tests use POSIX path semantics and run in Linux CI."""
    if os.name == "nt" and request.node.name.startswith("test_bash_"):
        pytest.skip("Bash installer behavior is covered by the Linux jobs")


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
    env["OBSIDIAN_KB_PYTHON"] = sys.executable
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
    env["OBSIDIAN_KB_PYTHON"] = sys.executable
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


def _copy_release_tree(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    release.mkdir()
    shutil.copy2(ROOT / "install.sh", release / "install.sh")
    shutil.copytree(ROOT / "skills", release / "skills")
    shutil.copytree(ROOT / "platforms", release / "platforms")
    shutil.copytree(ROOT / "core", release / "core")
    return release


def _payload_files(root: Path) -> set[str]:
    excluded_parts = {".DS_Store", "__pycache__"}
    files = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative == Path("header.md"):
            continue
        if any(part in excluded_parts for part in relative.parts):
            continue
        if relative.suffix in {".pyc", ".pyo"}:
            continue
        files.add(relative.as_posix())
    return files


def _run_release_installer(
    release: Path,
    *,
    home: Path,
    vault: Path | str,
    platforms: str = "codex",
    extra_args: tuple[str, ...] = (),
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["OBSIDIAN_KB_PYTHON"] = sys.executable
    env["PYTHONPATH"] = ""
    return subprocess.run(
        [
            "bash",
            str(release / "install.sh"),
            "--vault",
            str(vault),
            "--platforms",
            platforms,
            *extra_args,
        ],
        cwd=cwd or release,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def _run_installed_helper(
    skill: Path,
    helper: str,
    *args: str,
    home: Path,
    cwd: Path,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = ""
    return subprocess.run(
        [sys.executable, str(skill / "scripts" / "run_helper.py"), helper, *args],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_bash_install_is_complete_and_survives_release_removal(tmp_path):
    release = _copy_release_tree(tmp_path)
    expected = _payload_files(release / "skills" / "obsidian-knowledge-base")
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)

    _run_release_installer(release, home=home, vault=vault, platforms="codex,qoderwork")
    shutil.rmtree(release)

    codex = home / ".agents" / "skills" / "obsidian-knowledge-base"
    qoder = home / ".qoderwork" / "skills" / "obsidian-knowledge-base"
    canonical = home / ".obsidian-kb-skill" / "skill"
    assert _payload_files(codex) == expected
    assert _payload_files(qoder) == expected
    assert _payload_files(canonical) == expected
    assert (codex / "references" / "note-creation.md").is_file()
    assert (vault / "Templates" / "Digest Note.md").is_file()

    neutral = tmp_path / "neutral"
    neutral.mkdir()
    result = _run_installed_helper(
        codex, "vault-info", str(vault), "--json", home=home, cwd=neutral
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_bash_upgrade_restores_payload_removes_stale_and_preserves_vault_template(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    _run_release_installer(release, home=home, vault=vault)
    installed = home / ".agents" / "skills" / "obsidian-knowledge-base"
    missing = installed / "references" / "note-creation.md"
    missing.unlink()
    stale = installed / "references" / "removed-in-upgrade.md"
    stale.write_text("stale", encoding="utf-8")
    template = vault / "Templates" / "Daily Note.md"
    template.write_text("user-owned", encoding="utf-8")

    _run_release_installer(release, home=home, vault=vault)

    assert missing.is_file()
    assert not stale.exists()
    assert template.read_text(encoding="utf-8") == "user-owned"


def test_bash_new_relative_vault_is_saved_as_absolute_path(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"

    _run_release_installer(
        release,
        home=home,
        vault="relative-vault",
        cwd=tmp_path,
    )

    configured = (home / ".obsidian-kb-config").read_text(encoding="utf-8").strip()
    assert Path(configured).is_absolute()
    assert Path(configured) == (tmp_path / "relative-vault").resolve()


def test_bash_unknown_platform_fails_before_install_mutation(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "new-vault"

    result = _run_release_installer(
        release,
        home=home,
        vault=vault,
        platforms="codex,unknown-agent",
        check=False,
    )

    assert result.returncode != 0
    assert "Unknown platform" in result.stdout + result.stderr
    assert not vault.exists()
    assert not (home / ".obsidian-kb-config").exists()


def test_bash_uninstall_preserves_config_and_explicit_purge_removes_it(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    _run_release_installer(release, home=home, vault=vault)
    config = home / ".obsidian-kb-config"

    _run_release_installer(
        release,
        home=home,
        vault=vault,
        extra_args=("--uninstall",),
    )

    assert config.is_file()
    assert vault.is_dir()
    assert not (home / ".obsidian-kb-skill").exists()

    _run_release_installer(release, home=home, vault=vault)
    _run_release_installer(
        release,
        home=home,
        vault=vault,
        extra_args=("--uninstall", "--purge-config"),
    )
    assert not config.exists()


def test_bash_settings_created_preserved_and_purged(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    settings = home / ".obsidian-kb-settings.json"

    _run_release_installer(release, home=home, vault=vault)
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "backup": {"keep_per_note": 1},
    }

    custom = '{"schema_version":1,"backup":{"keep_per_note":3}}\n'
    settings.write_text(custom, encoding="utf-8")
    _run_release_installer(release, home=home, vault=vault)
    assert settings.read_text(encoding="utf-8") == custom

    _run_release_installer(
        release,
        home=home,
        vault=vault,
        extra_args=("--uninstall",),
    )
    assert settings.read_text(encoding="utf-8") == custom

    _run_release_installer(release, home=home, vault=vault)
    _run_release_installer(
        release,
        home=home,
        vault=vault,
        extra_args=("--uninstall", "--purge-config"),
    )
    assert not settings.exists()


def test_bash_install_does_not_write_through_broken_settings_symlink(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    outside = tmp_path / "outside-settings.json"
    settings = home / ".obsidian-kb-settings.json"
    try:
        settings.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    _run_release_installer(release, home=home, vault=vault)

    assert settings.is_symlink()
    assert not outside.exists()


def test_powershell_installer_declares_global_backup_settings_contract():
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert ".obsidian-kb-settings.json" in script
    assert "keep_per_note" in script
    assert "PurgeConfig" in script


@pytest.mark.parametrize(
    "existing",
    [
        "user content\n<!-- BEGIN obsidian-kb-skill -->\norphaned\nkeep me\n",
        "user content\n<!-- END obsidian-kb-skill -->\nkeep me\n",
        (
            "user content\n<!-- END obsidian-kb-skill -->\n"
            "middle\n<!-- BEGIN obsidian-kb-skill -->\nkeep me\n"
        ),
        (
            "user content\n<!-- BEGIN obsidian-kb-skill -->\none\n"
            "<!-- END obsidian-kb-skill -->\n"
            "middle\n<!-- BEGIN obsidian-kb-skill -->\ntwo\n"
            "<!-- END obsidian-kb-skill -->\nkeep me\n"
        ),
    ],
    ids=("lone-begin", "lone-end", "reversed", "duplicate-blocks"),
)
def test_bash_malformed_marker_fails_without_modifying_shared_file(tmp_path, existing):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    shared = home / ".claude" / "CLAUDE.md"
    shared.parent.mkdir(parents=True)
    shared.write_text(existing, encoding="utf-8")
    before = shared.read_bytes()

    result = _run_release_installer(
        release,
        home=home,
        vault=vault,
        platforms="claude-code",
        check=False,
    )

    assert result.returncode != 0
    assert "malformed marker" in (result.stdout + result.stderr).lower()
    assert shared.read_bytes() == before


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


def test_bash_codex_install_replaces_destination_symlink_without_touching_source(tmp_path):
    vault = tmp_path / "vault"
    home = tmp_path / "home"
    target = home / ".agents/skills/obsidian-knowledge-base"
    target.parent.mkdir(parents=True)
    target.symlink_to(ROOT / "skills/obsidian-knowledge-base", target_is_directory=True)
    canonical = ROOT / "skills/obsidian-knowledge-base/SKILL.md"
    before = canonical.read_bytes()

    run_bash_installer(
        tmp_path,
        platforms="codex",
        vault=vault,
        home=home,
    )

    assert not target.is_symlink()
    assert _payload_files(target) == _payload_files(
        ROOT / "skills/obsidian-knowledge-base"
    )
    assert canonical.read_bytes() == before


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

    assert "skills\\obsidian-knowledge-base" in script
    assert ".agents\\skills\\obsidian-knowledge-base" in script
    assert "platforms\\qoderwork\\SKILL.md" not in script


def test_powershell_installer_declares_complete_runtime_lifecycle():
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    for marker in (
        "PurgeConfig",
        ".obsidian-kb-skill",
        "runtime.json",
        "run_helper.py",
        "OBSIDIAN_KB_PYTHON",
        "Copy-SkillPayload",
        "Post-install verification",
    ):
        assert marker in script


def test_ci_executes_windows_installer_smoke():
    workflow = (ROOT / ".github" / "workflows" / "check.yml").read_text(
        encoding="utf-8"
    )

    assert "windows-latest" in workflow
    assert "tests/windows_installer_smoke.ps1" in workflow
