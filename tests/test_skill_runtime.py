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
RETRIEVAL_SKILL = ROOT / "skills" / "obsidian-knowledge-retrieval"
HELPERS = (
    "audit-vault",
    "capture-receipt",
    "archive-source",
    "create-category",
    "create-note",
    "detect-index",
    "doctor",
    "process-inbox",
    "scaffold-templates",
    "suggest-links",
    "template-contract",
    "update-note",
    "vault-info",
)
RETRIEVAL_HELPERS = (
    "doctor",
    "explore-neighborhood",
    "resume-project",
    "review-captures",
    "review-projects",
    "run-retrieval-view",
    "search-vault",
    "suggest-directed-links",
    "vault-info",
)


def test_installed_runner_reads_one_custom_template_contract(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "00-Inbox").mkdir()
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\ntype: insight-note\ntags: [insight]\n---\n"
        "# {{title}}\n\n## Reflection\n\nExplain why this matters.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "template-contract",
            str(vault),
            "--type",
            "insight-note",
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["customized"] is True
    assert "Explain why this matters." in payload["body"]


def test_installed_runner_preflights_category_from_hostile_cwd(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-base"
    shutil.copytree(STANDARD_SKILL, skill)
    home = tmp_path / "home"
    work = tmp_path / "hostile-cwd"
    vault = tmp_path / "vault"
    home.mkdir()
    work.mkdir()
    (work / "obsidian_kb_skill").mkdir()
    (work / "obsidian_kb_skill" / "__init__.py").write_text(
        "raise RuntimeError('shadow package imported')\n", encoding="utf-8"
    )
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "20-Learning").mkdir()
    (vault / "20-Learning" / "INDEX.md").write_text(
        "---\ntype: moc\ntags: [moc]\n---\n# Learning\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(work)
    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "create-category",
            str(vault),
            "--folder",
            "20-Learning/Rust",
            "--preflight-json",
        ],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["folder"] == "20-Learning/Rust"
    assert payload["index"]["mode"] == "static"
    assert not (vault / "20-Learning/Rust").exists()


def load_runner(path: Path = STANDARD_SKILL / "scripts" / "run_helper.py"):
    spec = importlib.util.spec_from_file_location("standard_skill_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retrieval_runner_exposes_only_read_only_helpers():
    runner = load_runner(RETRIEVAL_SKILL / "scripts" / "run_helper.py")

    assert tuple(sorted(runner.HELPERS)) == RETRIEVAL_HELPERS
    assert not {
        "create-note",
        "update-note",
        "process-inbox",
        "scaffold-templates",
    } & set(runner.HELPERS)


def test_retrieval_runner_searches_from_hostile_cwd_without_mutation(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-retrieval"
    shutil.copytree(RETRIEVAL_SKILL, skill)
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
    (work / "obsidian_kb_skill" / "__init__.py").write_text(
        "raise RuntimeError('shadow package imported')\n",
        encoding="utf-8",
    )
    (vault / ".obsidian").mkdir(parents=True)
    note = vault / "retrieval.md"
    note.write_text("# Retrieval\n\n只读检索证据。\n", encoding="utf-8")
    before = note.read_bytes()
    skill_before = {
        path.relative_to(skill).as_posix(): path.read_bytes()
        for path in skill.rglob("*")
        if path.is_file()
    }

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "search-vault",
            str(vault),
            "--query",
            "只读检索",
            "--json",
        ],
        cwd=work,
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": str(work),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["results"][0]["path"] == "retrieval.md"
    assert note.read_bytes() == before
    assert {
        path.relative_to(skill).as_posix(): path.read_bytes()
        for path in skill.rglob("*")
        if path.is_file()
    } == skill_before


def test_retrieval_runner_reviews_projects_from_hostile_cwd_without_mutation(tmp_path):
    skill = tmp_path / "installed" / "obsidian-knowledge-retrieval"
    shutil.copytree(RETRIEVAL_SKILL, skill)
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
    (work / "obsidian_kb_skill" / "__init__.py").write_text(
        "raise RuntimeError('shadow package imported')\n",
        encoding="utf-8",
    )
    (vault / ".obsidian").mkdir(parents=True)
    note = vault / "project.md"
    note.write_text(
        "---\ndate: 2026-01-01\ntype: project-note\nstatus: active\n---\n"
        "# Project\n\n## Next Steps\n\n- [ ] Resume safely\n",
        encoding="utf-8",
    )
    before = note.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "review-projects",
            str(vault),
            "--as-of",
            "2026-08-10",
            "--json",
        ],
        cwd=work,
        env={
            **os.environ,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONPATH": str(work),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["items"][0]["path"] == "project.md"
    assert payload["items"][0]["next_action"] == "Resume safely"
    assert note.read_bytes() == before


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
    (vault / "00-Inbox").mkdir()
    markdown = (
        "\ufeff---\r\n"
        "source: https://example.com/runtime\r\n"
        "author: QoderWork\r\n"
        "published: 2026-07-13\r\n"
        "---\r\n"
        "# UTF-8\r\n\r\n中文输入 🧠\r\n\r\n"
        # The subject here is byte bridging; the body length is not. But a
        # web-clip under `WEB_CLIP_MIN_CONTENT_CHARS` is reported as having
        # captured nothing (#167), which would turn `audit.ok` false for a
        # reason that has nothing to do with encoding.
        "本文记录一次跨平台的字节桥接问题：Windows 侧以 UTF-16 写出标准输入，"
        "而 helper 期望 UTF-8，于是中文与 emoji 在传输途中变成了问号。"
        "修复的做法是在 run_helper 里显式声明编码，而不是依赖平台默认值，"
        "因为平台默认值在同一台机器上也会随终端设置变化，"
        "同一条命令在 PowerShell 与 Windows Terminal 里能得到不同结果。\r\n\r\n"
        "验证方式是让正文同时包含多字节汉字与四字节 emoji，"
        "并在写入后重新按 UTF-8 读回比对，两者都还原才算通过。"
        "此外还要覆盖带 BOM 的输入与 CRLF 换行，"
        "它们是这条路径上最容易被静默吞掉的两种字节："
        "BOM 会被当成正文的第一个字符，CRLF 会让按行比对的断言在末尾多出一个空白。\r\n"
        "\r\n更细的一层是标准输出侧：即便输入被正确解码，"
        "Windows 的控制台仍可能以 GBK 编码回写，"
        "于是 JSON 里的中文在被调用方解析时再次损坏。"
        "因此这条路径上需要同时固定输入与输出两端的编码，"
        "只修一端会得到一个看起来通过、实际只在开发者本机成立的结果。"
        "回归测试因此断言的是端到端的往返："
        "从字节写入，到文件按 UTF-8 读回，再到 JSON 载荷里的路径字段，"
        "三处都还原成同一串字符才算通过。\r\n"
    ).encode("utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "run_helper.py"),
            "create-note",
            str(vault),
            "--type",
            "web-clip",
            "--folder",
            "00-Inbox",
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


# --- Using the wrong Skill's runner must say so (#103) -----------------------
#
# The project ships two Skills with separate runners. A peer session looking for
# `review-projects` checked the write runner, did not find it, concluded the
# capability was missing, reported a phantom bug upstream, then bypassed the
# runner entirely and hit a missing-dependency error because vendor injection
# lives inside the runner it had just bypassed. The capability worked the whole
# time; only the signpost was absent.


@pytest.mark.parametrize("helper", ("review-projects", "review-captures"))
def test_write_runner_points_at_the_retrieval_skill_for_its_helpers(tmp_path, helper):
    result = subprocess.run(
        [
            sys.executable,
            str(STANDARD_SKILL / "scripts" / "run_helper.py"),
            helper,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "obsidian-knowledge-retrieval" in result.stderr, (
        "the helper exists in the other Skill; saying only 'invalid choice' "
        f"reads as 'this capability does not exist': {result.stderr!r}"
    )


def test_retrieval_runner_points_at_the_write_skill_for_its_helpers(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(RETRIEVAL_SKILL / "scripts" / "run_helper.py"),
            "create-note",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "obsidian-knowledge-base" in result.stderr, result.stderr


def test_a_name_neither_skill_provides_still_reports_invalid_choice(tmp_path):
    """The hint must not swallow the ordinary error for a genuine typo."""
    for runner in (
        STANDARD_SKILL / "scripts" / "run_helper.py",
        RETRIEVAL_SKILL / "scripts" / "run_helper.py",
    ):
        result = subprocess.run(
            [sys.executable, str(runner), "not-a-helper"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2, runner
        assert "invalid choice" in result.stderr, runner


def test_peer_helper_lists_cannot_drift_from_the_runners_they_mirror():
    """A hand-kept mirror rots. This is the only thing keeping the two in sync.

    `install.sh` already carries 20 hand-maintained copies of the same paths
    (#91); the lists added here are the same shape of duplication and need the
    assertion the installer never got.
    """
    write = load_runner(STANDARD_SKILL / "scripts" / "run_helper.py")
    retrieval = load_runner(RETRIEVAL_SKILL / "scripts" / "run_helper.py")

    # Only what the *other* runner has and this one lacks. `doctor` and
    # `vault-info` exist on both sides — the retrieval `vault-info` is a
    # separate, read-only implementation — so neither is a peer helper.
    assert set(write.PEER_HELPERS) == set(retrieval.HELPERS) - set(write.HELPERS), (
        "the write runner's peer list no longer matches the retrieval runner"
    )
    assert set(retrieval.PEER_HELPERS) == set(write.HELPERS) - set(retrieval.HELPERS), (
        "the retrieval runner's peer list no longer matches the write runner"
    )
    assert not (set(write.HELPERS) & set(write.PEER_HELPERS)), (
        "a helper cannot be both local and peer"
    )


@pytest.mark.parametrize("helper", RETRIEVAL_HELPERS)
def test_every_retrieval_helper_imports_from_the_installed_bundle(helper, tmp_path):
    """Being on the allowlist is not the same as being importable.

    The read-only bundle ships a hand-picked module list. A helper can be
    registered, have its own file copied, pass every unit test — which run from
    the repo root where all modules are visible — and still fail on the first
    real invocation because something it imports was never added to the list.
    `doctor` does not catch this: it verifies files are present, not that the
    import graph resolves.

    `--help` is enough: argparse runs after the module-level imports.
    """
    skill = tmp_path / "installed" / "obsidian-knowledge-retrieval"
    shutil.copytree(RETRIEVAL_SKILL, skill)

    result = subprocess.run(
        [sys.executable, str(skill / "scripts" / "run_helper.py"), helper, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"{helper} cannot start from the shipped bundle:\n{result.stderr}"
    )
