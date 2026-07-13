"""Black-box checks for the standard Skill's bundled helper runtime."""
from __future__ import annotations

import json
import importlib.util
import io
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.resource_locator import locate_skill_resources


ROOT = Path(__file__).resolve().parent.parent
STANDARD_SKILL = ROOT / "skills" / "obsidian-knowledge-base"
HELPERS = (
    "audit-vault",
    "create-note",
    "detect-index",
    "doctor",
    "process-inbox",
    "scaffold-templates",
    "suggest-links",
    "update-note",
    "vault-info",
)


def load_runner(path: Path = STANDARD_SKILL / "scripts" / "run_helper.py"):
    spec = importlib.util.spec_from_file_location("standard_skill_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


@pytest.mark.parametrize(
    ("helper", "arguments", "healthy_field"),
    [
        ("doctor", ("--json",), "ok"),
        ("vault-info", ("{vault}", "--json"), "valid"),
    ],
)
def test_skill_runner_ignores_shadow_package_in_working_directory(
    tmp_path, helper, arguments, healthy_field
):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    work = tmp_path / "hostile-cwd"
    vault = tmp_path / "vault"
    home.mkdir()
    support = home / ".obsidian-kb-skill"
    support.mkdir()
    (support / "runtime.json").write_text(
        json.dumps({"schema_version": 1, "python": [sys.executable]}),
        encoding="utf-8",
    )
    (work / "obsidian_kb_skill" / "scripts").mkdir(parents=True)
    (work / "obsidian_kb_skill" / "__init__.py").write_text("", encoding="utf-8")
    (work / "obsidian_kb_skill" / "scripts" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()

    resolved_arguments = [
        str(vault) if argument == "{vault}" else argument for argument in arguments
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            helper,
            *resolved_arguments,
        ],
        cwd=work,
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": "",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[healthy_field] is True


def test_skill_runner_bridges_create_note_stdin_bytes(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    work = tmp_path / "neutral"
    vault = tmp_path / "vault"
    home.mkdir()
    work.mkdir()
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    markdown = (
        "\ufeff---\r\n"
        "source: https://example.com/runtime\r\n"
        "author: QoderWork\r\n"
        "published: 2026-07-13\r\n"
        "---\r\n"
        "# UTF-8\r\n\r\n中文输入 🧠\r\n"
    ).encode("utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "create-note",
            str(vault),
            "--type",
            "web-clip",
            "--title",
            "Runtime UTF-8",
            "--stdin",
            "--apply",
            "--json",
        ],
        input=markdown,
        cwd=work,
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": "",
        },
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["audit"]["ok"] is True
    assert "中文输入 🧠" in Path(payload["path"]).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("forwarded", "expected_input"),
    [
        (["vault", "--stdin"], b"frontmatter bytes"),
        (["vault", "--title=--stdin"], None),
    ],
)
def test_skill_runner_only_explicitly_bridges_exact_stdin_token(
    tmp_path, monkeypatch, forwarded, expected_input
):
    runner = load_runner()
    stdin = io.TextIOWrapper(io.BytesIO(b"frontmatter bytes"), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.sys, "stdin", stdin)
    monkeypatch.setattr(runner, "python_command", lambda: [sys.executable])
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main(["create-note", *forwarded]) == 0
    _, kwargs = calls[0]
    assert kwargs.get("input") == expected_input


def test_skill_runner_enforces_retention_from_installed_payload(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    work = tmp_path / "neutral"
    vault = tmp_path / "vault"
    home.mkdir()
    work.mkdir()
    (vault / ".obsidian").mkdir(parents=True)
    (home / ".obsidian-kb-settings.json").write_text(
        '{"schema_version":1,"backup":{"keep_per_note":1}}\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["PYTHONPATH"] = ""

    for index in range(4):
        result = subprocess.run(
            [
                sys.executable,
                str(skill / "scripts" / "run_helper.py"),
                "update-note",
                str(vault),
                "--note",
                "Tasks/demo/TASK.md",
                "--step",
                f"step-{index}",
                "--apply",
                "--no-audit",
                "--json",
            ],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload["backup_cleanup"]["keep_per_note"] == 1
    assert len(
        list((vault / ".obsidian-kb-backups").glob("*/Tasks/demo/TASK.md"))
    ) == 1

    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import pathlib,sys;"
                f"sys.path.insert(0,{str(skill / 'scripts')!r});"
                "import obsidian_kb_skill.scripts.backup_policy as module;"
                "print(pathlib.Path(module.__file__).resolve())"
            ),
        ],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    assert Path(probe.stdout.strip()).is_relative_to(skill.resolve())


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


@pytest.mark.parametrize("helper", HELPERS)
def test_skill_runner_forwards_helper_help(helper, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": "",
    }

    result = subprocess.run(
        [
            sys.executable,
            str(STANDARD_SKILL / "scripts" / "run_helper.py"),
            helper,
            "--help",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "Run a helper bundled" not in result.stdout


def test_skill_runner_keeps_top_level_help(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(STANDARD_SKILL / "scripts" / "run_helper.py"),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Run a helper bundled" in result.stdout


def test_skill_runner_keeps_double_dash_compatibility(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(STANDARD_SKILL / "scripts" / "run_helper.py"),
            "create-note",
            "--",
            "--help",
        ],
        cwd=tmp_path,
        env={**os.environ, "HOME": str(home), "PYTHONPATH": ""},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--type" in result.stdout
    assert "--title" in result.stdout
    assert "Run a helper bundled" not in result.stdout


def test_skill_runner_parse_dispatch_preserves_forwarded_arguments():
    runner = load_runner()

    assert runner.parse_dispatch(
        ["create-note", "vault", "--title", "A title", "--json"]
    ) == ("create-note", ["vault", "--title", "A title", "--json"])
    assert runner.parse_dispatch(["create-note", "--", "--help"]) == (
        "create-note",
        ["--help"],
    )


def test_skill_runner_environment_does_not_inherit_source_pythonpath(
    tmp_path, monkeypatch
):
    runner = load_runner()
    source = tmp_path / "source-checkout"
    monkeypatch.setenv("PYTHONPATH", str(source))

    env = runner.helper_environment(STANDARD_SKILL, home=tmp_path / "home")

    assert str(source) not in env["PYTHONPATH"].split(os.pathsep)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(
        STANDARD_SKILL / "scripts"
    )


def test_skill_runner_doctor_survives_invalid_runtime_record(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    support = home / ".obsidian-kb-skill"
    support.mkdir(parents=True)
    (support / "runtime.json").write_text("{", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": "",
    }

    doctor_result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "doctor",
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    normal_result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "vault-info",
            "--help",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert doctor_result.returncode == 1, doctor_result.stderr
    payload = json.loads(doctor_result.stdout)
    assert next(
        check for check in payload["checks"] if check["name"] == "runtime"
    )["ok"] is False
    assert normal_result.returncode == 3
    assert "invalid Skill runtime record" in normal_result.stderr
