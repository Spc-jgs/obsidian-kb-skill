"""Installed-payload diagnostics for the standard Skill."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts import doctor


ROOT = Path(__file__).resolve().parents[1]
STANDARD_SKILL = ROOT / "skills" / "obsidian-knowledge-base"


def installed_tree(tmp_path: Path) -> tuple[Path, Path]:
    skill = tmp_path / "skill"
    home = tmp_path / "home"
    shutil.copytree(STANDARD_SKILL, skill)
    support = home / ".obsidian-kb-skill"
    support.mkdir(parents=True)
    (support / "runtime.json").write_text(
        json.dumps({"schema_version": 1, "python": [sys.executable]}),
        encoding="utf-8",
    )
    return skill, home


def check_named(result: dict[str, object], name: str) -> dict[str, object]:
    return next(check for check in result["checks"] if check["name"] == name)


def tree_snapshot(*roots: Path) -> dict[str, bytes]:
    return {
        f"{index}/{path.relative_to(root).as_posix()}": path.read_bytes()
        for index, root in enumerate(roots)
        for path in root.rglob("*")
        if path.is_file()
    }


def test_doctor_accepts_complete_installed_skill(tmp_path):
    skill, home = installed_tree(tmp_path)

    result = doctor.inspect_installation(skill, home)

    assert result["ok"] is True
    assert result["version"] == "1.19.1"
    assert "create_category" in doctor.HELPER_MODULES
    assert {check["name"] for check in result["checks"]} == {
        "manifest",
        "payload",
        "runtime",
        "dependencies",
        "resources",
    }


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ("changed", "payload"),
        ("missing", "payload"),
        ("extra", "payload"),
        ("bad-manifest", "manifest"),
        ("escaping-manifest", "manifest"),
        ("bad-runtime", "runtime"),
        ("missing-runtime", "runtime"),
    ],
)
def test_doctor_reports_installed_drift(tmp_path, mutation, failed_check):
    skill, home = installed_tree(tmp_path)
    if mutation == "changed":
        (skill / "SKILL.md").write_text("changed", encoding="utf-8")
    elif mutation == "missing":
        (skill / "references" / "note-creation.md").unlink()
    elif mutation == "extra":
        (skill / "stale.md").write_text("stale", encoding="utf-8")
    elif mutation == "bad-manifest":
        (skill / "manifest.json").write_text("{", encoding="utf-8")
    elif mutation == "escaping-manifest":
        manifest = json.loads((skill / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"]["../outside.md"] = "0" * 64
        (skill / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif mutation == "bad-runtime":
        (home / ".obsidian-kb-skill" / "runtime.json").write_text(
            '{"python": []}', encoding="utf-8"
        )
    else:
        (home / ".obsidian-kb-skill" / "runtime.json").unlink()

    result = doctor.inspect_installation(skill, home)

    assert result["ok"] is False
    assert check_named(result, failed_check)["ok"] is False


def test_doctor_treats_payload_symlink_as_drift(tmp_path):
    skill, home = installed_tree(tmp_path)
    target = tmp_path / "external.md"
    target.write_text("external", encoding="utf-8")
    (skill / "SKILL.md").unlink()
    (skill / "SKILL.md").symlink_to(target)

    result = doctor.inspect_installation(skill, home)

    assert result["ok"] is False
    assert "SKILL.md" in check_named(result, "payload")["details"]["changed"]


def test_doctor_is_read_only(tmp_path):
    skill, home = installed_tree(tmp_path)
    before = tree_snapshot(skill, home)

    doctor.inspect_installation(skill, home)

    assert tree_snapshot(skill, home) == before


def test_doctor_json_is_one_parseable_object(tmp_path, monkeypatch, capsys):
    skill, home = installed_tree(tmp_path)
    (skill / "SKILL.md").write_text("changed", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    status = doctor.main(["--skill-root", str(skill), "--json"])

    assert status == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_doctor_rejects_python_310(tmp_path, monkeypatch):
    skill, home = installed_tree(tmp_path)
    real_run = doctor.subprocess.run

    def fake_run(command, **kwargs):
        if "sys.version_info" in command[-1]:
            return doctor.subprocess.CompletedProcess(command, 0, "3.10.14\n", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    result = doctor.inspect_installation(skill, home)

    assert result["ok"] is False
    assert check_named(result, "runtime")["ok"] is False


def test_doctor_reports_missing_pyyaml(tmp_path, monkeypatch):
    skill, home = installed_tree(tmp_path)

    def fake_run(command, **_kwargs):
        if "sys.version_info" in command[-1]:
            return doctor.subprocess.CompletedProcess(command, 0, "3.11.9\n", "")
        return doctor.subprocess.CompletedProcess(command, 1, "", "No module named yaml")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    result = doctor.inspect_installation(skill, home)

    assert result["ok"] is False
    dependency = check_named(result, "dependencies")
    assert dependency["ok"] is False
    assert "yaml" in dependency["details"]["error"]
