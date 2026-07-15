"""Tests for --json machine-readable output across every script that supports it.

A consistent JSON contract lets an agent (or another tool) drive every script
without parsing human text. This file verifies the contract: when --json is
passed, stdout is a single JSON document with predictable fields.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts import console

REPO = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, env_overrides: dict[str, str] | None = None) -> dict:
    env = {
        **__import__("os").environ,
        "PYTHONPATH": str(REPO),
        **(env_overrides or {}),
    }
    r = subprocess.run(
        [sys.executable] + args, capture_output=True, text=True, cwd=str(REPO), env=env
    )
    assert r.returncode == 0, f"stderr={r.stderr!r}\nstdout={r.stdout!r}"
    return json.loads(r.stdout)


def _make_vault(root: Path) -> Path:
    v = root / "vault"
    (v / ".obsidian").mkdir(parents=True)
    (v / "Templates").mkdir()
    (v / "30-Insights").mkdir()
    return v


# ---- audit_vault --------------------------------------------------------------

def test_audit_vault_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "Bad.md").write_text(
        "---\ndate: 2026-07-09\ntags: [a, b, c, d, e, f]\n---\n", encoding="utf-8"
    )
    out = _run(["-m", "obsidian_kb_skill.scripts.audit_vault", str(vault), "--json"])
    assert "count" in out and "findings" in out
    assert isinstance(out["findings"], list)
    # Each finding has code/path/message.
    for f in out["findings"]:
        assert {"code", "path", "message"} <= set(f)


# ---- suggest_links ------------------------------------------------------------

def test_suggest_links_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "Other.md").write_text(
        '---\ntype: insight-note\ndate: 2026-07-01\ntags: [insight]\n---\n# Other\nbody.\n',
        encoding="utf-8",
    )
    note = vault / "30-Insights" / "Target.md"
    note.write_text(
        '---\ntype: insight-note\ndate: 2026-07-09\ntags: [insight]\n---\n# Target\nbody.\n',
        encoding="utf-8",
    )
    out = _run([
        "-m", "obsidian_kb_skill.scripts.suggest_links", str(vault),
        "--note", str(note), "--json",
    ])
    assert isinstance(out, list)
    if out:
        item = out[0]
        assert {"path", "score", "reasons"} <= set(item)


# ---- detect_index -------------------------------------------------------------

def test_detect_index_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.detect_index", str(vault),
        "--folder", "30-Insights",
    ])
    # Already JSON by default; check the schema.
    assert out["mode"] == "static"
    assert "can_append" in out
    assert "index_file" in out
    assert "notes" in out


# ---- vault_info ---------------------------------------------------------------

def test_vault_info_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run(["-m", "obsidian_kb_skill.scripts.vault_info", str(vault)])
    assert out["valid"] is True
    assert "validation" in out
    assert "templates" in out
    assert "standard_folders" in out
    assert "folder_index_global" in out


def test_vault_info_compact_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run(
        [
            "-m",
            "obsidian_kb_skill.scripts.vault_info",
            str(vault),
            "--compact",
        ]
    )

    index = out["standard_folders"]["30-Insights"]["index"]
    assert "notes" not in index
    assert {"mode", "index_file", "can_append"} <= set(index)


# ---- process_inbox ------------------------------------------------------------

def test_process_inbox_plan_json(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    (vault / "00-Inbox").mkdir()
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )
    out = _run([
        "-m", "obsidian_kb_skill.scripts.process_inbox", str(vault), "--json",
    ])
    assert isinstance(out, list)
    assert out and out[0]["target"] == "30-Insights"


# ---- create_note --------------------------------------------------------------

def test_create_note_dry_run_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
        "--type", "insight-note", "--title", "Json", "--stdin", "--json",
    ])
    assert out["dry_run"] is True
    assert out["applied"] is False
    assert "rendered" in out
    assert out["path"].endswith("Json.md")
    assert out["audit"] is None  # dry run, no audit


@pytest.mark.parametrize(
    "mode_args",
    [
        ["--json"],
        ["--preflight-json"],
        ["--apply", "--compact-json"],
    ],
)
def test_create_note_invalid_frontmatter_is_structured_in_json_modes(
    tmp_path, mode_args
):
    vault = _make_vault(tmp_path)
    malformed = (
        '---\nsource: "https://example.com"\n'
        'author: "用户（说明："登录后可见"）"\n'
        "published: 2026-07-14\n---\n# Body\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--title",
            "Malformed",
            "--stdin",
            *mode_args,
        ],
        input=malformed.encode("utf-8"),
        capture_output=True,
        cwd=REPO,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout.decode("utf-8")) == {
        "error": {
            "code": "invalid-frontmatter",
            "source": "stdin",
            "line": 3,
            "column": 17,
            "message": "expected <block end>, but found '<scalar>'",
        }
    }
    assert not list(vault.rglob("*Malformed*.md"))


def test_create_note_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
        "--type", "insight-note", "--title", "Wrote", "--stdin",
        "--apply", "--no-audit", "--json",
    ])
    assert out["applied"] is True
    assert "rendered" in out
    # Audit was suppressed but the key still exists.
    assert out["audit"] is None


def test_create_note_apply_compact_json_omits_rendered(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "Compact",
            "--stdin",
            "--apply",
            "--compact-json",
        ],
        input="# Compact\n\nBody.\n",
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["applied"] is True
    assert payload["dry_run"] is False
    assert payload["audit"] == {"ok": True, "count": 0, "findings": []}
    assert "rendered" not in payload
    assert Path(payload["path"]).read_text(encoding="utf-8").endswith(
        "# Compact\n\nBody.\n"
    )


def test_create_note_compact_json_requires_apply(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "No Apply",
            "--stdin",
            "--compact-json",
        ],
        input="# No Apply\n",
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "error": {
            "code": "compact-json-requires-apply",
            "message": "--compact-json requires --apply",
        }
    }
    assert not list(vault.rglob("*No Apply*.md"))


def test_create_note_invalid_vault_compact_json_is_structured(tmp_path):
    not_vault = tmp_path / "not-vault"
    not_vault.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(not_vault),
            "--type",
            "insight-note",
            "--title",
            "Invalid Vault",
            "--apply",
            "--compact-json",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_VAULT_ROOT"
    assert payload["error"]["details"] == {"param": "vault"}


def _create_note_process(vault: Path, body: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "Structured Preview",
            "--date",
            "2026-07-14",
            "--stdin",
            *extra,
        ],
        input=body,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO,
    )


def test_create_note_preflight_json_returns_identity_without_body_or_mutation(tmp_path):
    vault = _make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    original_index = "# Insights\n\n## Recent\n"
    index.write_text(original_index, encoding="utf-8")
    body = "# Structured Preview\n\n机密正文不应被重复回显。\n"

    full_result = _create_note_process(vault, body, "--json")
    preflight_result = _create_note_process(vault, body, "--preflight-json")

    assert full_result.returncode == 0, full_result.stderr
    assert preflight_result.returncode == 0, preflight_result.stderr
    full = json.loads(full_result.stdout)
    payload = json.loads(preflight_result.stdout)
    rendered_bytes = full["rendered"].encode("utf-8")
    assert payload == {
        "vault": str(vault.resolve()),
        "folder": "30-Insights",
        "path": full["path"],
        "applied": False,
        "dry_run": True,
        "frontmatter": {
            "source": "",
            "related": [],
            "type": "insight-note",
            "date": "2026-07-14",
            "tags": ["insight"],
        },
        "content": {
            "sha256": hashlib.sha256(rendered_bytes).hexdigest(),
            "utf8_bytes": len(rendered_bytes),
            "line_count": len(full["rendered"].splitlines()),
        },
        "validation": {"ok": True, "count": 0, "findings": []},
        "suggested_links": None,
    }
    assert "rendered" not in payload
    assert body.strip() not in preflight_result.stdout
    assert not list((vault / "30-Insights").glob("*Structured Preview*.md"))
    assert index.read_text(encoding="utf-8") == original_index


def test_create_note_preflight_json_reports_findings_without_mutation(tmp_path):
    vault = _make_vault(tmp_path)
    result = _create_note_process(
        vault,
        "# Structured Preview\n\nSee [[No Such Note]].\n",
        "--preflight-json",
    )

    assert result.returncode == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["validation"]["ok"] is False
    assert payload["validation"]["count"] == 1
    assert payload["validation"]["findings"][0]["code"] == "broken-wikilink"
    assert not list((vault / "30-Insights").glob("*Structured Preview*.md"))


@pytest.mark.parametrize(
    "conflicting",
    [("--apply",), ("--json",), ("--compact-json",)],
)
def test_create_note_preflight_json_rejects_conflicting_modes(tmp_path, conflicting):
    vault = _make_vault(tmp_path)
    result = _create_note_process(
        vault,
        "# Structured Preview\n\nBody.\n",
        "--preflight-json",
        *conflicting,
    )

    assert result.returncode == 2
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "error": {
            "code": "invalid-output-mode",
            "message": (
                "--preflight-json cannot be combined with --apply, --json, "
                "or --compact-json"
            ),
        }
    }


def test_create_note_preflight_response_size_is_body_independent(tmp_path):
    vault = _make_vault(tmp_path)
    short_body = "# Structured Preview\n\nBody.\n"
    long_body = "# Structured Preview\n\n" + ("长正文内容。\n" * 10_000)

    short = _create_note_process(vault, short_body, "--preflight-json")
    long = _create_note_process(vault, long_body, "--preflight-json")
    full = _create_note_process(vault, long_body, "--json")

    assert short.returncode == long.returncode == full.returncode == 0
    assert len(long.stdout.encode("utf-8")) - len(short.stdout.encode("utf-8")) <= 512
    assert len(long.stdout.encode("utf-8")) < len(full.stdout.encode("utf-8")) * 0.2
    assert long_body.strip() not in long.stdout


def test_create_note_apply_with_audit_json(tmp_path):
    vault = _make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
         "--type", "insight-note", "--title", "Audited", "--stdin",
         "--apply", "--json"],
        input="# Insight\n\nReal body content here.\n",
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["audit"]["ok"] is True
    assert out["audit"]["count"] == 0


def test_create_note_web_clip_preflight_json_error(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--title",
            "Incomplete",
            "--stdin",
            "--apply",
            "--json",
        ],
        input="# Incomplete\n",
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "error": {
            "code": "missing-required-metadata",
            "note_type": "web-clip",
            "fields": ["source", "author", "published"],
        }
    }
    assert not list(vault.rglob("*Incomplete*.md"))


def test_create_note_web_clip_invalid_dry_run_keeps_preview_and_preflight(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--title",
            "Preview",
            "--stdin",
            "--json",
        ],
        input="# Preview\n",
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert "# Preview" in payload["rendered"]
    assert payload["error"] == {
        "code": "missing-required-metadata",
        "note_type": "web-clip",
        "fields": ["source", "author", "published"],
    }
    assert not list(vault.rglob("*Preview*.md"))


def test_create_note_invalid_utf8_stdin_returns_structured_error(tmp_path):
    vault = _make_vault(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "Invalid UTF-8",
            "--stdin",
            "--json",
        ],
        input=b"# invalid \xff\n",
        capture_output=True,
        cwd=REPO,
        env=env,
    )

    assert result.returncode == 2
    assert result.stderr == b""
    assert json.loads(result.stdout.decode("utf-8")) == {
        "error": {
            "code": "invalid-utf8-input",
            "message": "stdin must contain valid UTF-8",
        }
    }


def test_create_note_json_forces_utf8_when_console_default_cannot_encode_unicode(tmp_path):
    vault = _make_vault(tmp_path)
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\ntype: insight-note\ntags: [insight]\n---\n# 洞察标题\n\n中文正文\n",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "UTF-8",
            "--json",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(result.stdout.decode("utf-8"))
    assert "中文正文" in payload["rendered"]


def test_configure_utf8_stdio_includes_stdin(monkeypatch):
    class RecordingStream:
        def __init__(self):
            self.encodings: list[str] = []

        def reconfigure(self, *, encoding: str):
            self.encodings.append(encoding)

    stdin = RecordingStream()
    stdout = RecordingStream()
    stderr = RecordingStream()
    monkeypatch.setattr(console.sys, "stdin", stdin)
    monkeypatch.setattr(console.sys, "stdout", stdout)
    monkeypatch.setattr(console.sys, "stderr", stderr)

    console.configure_utf8_stdio()

    assert stdin.encodings == ["utf-8"]
    assert stdout.encodings == ["utf-8"]
    assert stderr.encodings == ["utf-8"]


def test_create_note_stdin_round_trips_utf8_when_default_is_legacy_encoding(tmp_path):
    vault = _make_vault(tmp_path)
    markdown = "# 中文输入 🧠\n\n多智能体协作。\n"
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "UTF-8 stdin",
            "--stdin",
            "--json",
        ],
        input=markdown.encode("utf-8"),
        capture_output=True,
        cwd=REPO,
        env=env,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(result.stdout.decode("utf-8"))
    assert markdown in payload["rendered"]


# ---- update_note --------------------------------------------------------------

def test_update_note_dry_run_json(tmp_path):
    vault = _make_vault(tmp_path)
    note = vault / "Tasks" / "foo" / "TASK.md"
    out = _run([
        "-m", "obsidian_kb_skill.scripts.update_note", str(vault),
        "--note", str(note.relative_to(vault)), "--json",
    ])
    assert out["dry_run"] is True
    assert out["action"] == "init"  # doesn't exist yet -> init
    assert out["backup_cleanup"] is None


def test_update_note_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.update_note", str(vault),
        "--note", "Tasks/foo/TASK.md", "--apply", "--no-audit", "--json",
    ])
    assert out["applied"] is True
    assert out["action"] == "init"


def test_update_note_apply_json_reports_backup_cleanup(tmp_path):
    vault = _make_vault(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "USERPROFILE": str(home)}
    base = [
        "-m",
        "obsidian_kb_skill.scripts.update_note",
        str(vault),
        "--note",
        "Tasks/foo/TASK.md",
        "--apply",
        "--no-audit",
        "--json",
    ]
    _run(base, env_overrides=env)
    _run(base + ["--add-open", "first"], env_overrides=env)
    out = _run(base + ["--add-open", "second"], env_overrides=env)

    assert out["backup_cleanup"] == {
        "keep_per_note": 1,
        "scanned": 2,
        "deleted": 1,
        "warnings": [],
    }
    backups = list(
        (vault / ".obsidian-kb-backups").glob("*/Tasks/foo/TASK.md")
    )
    assert len(backups) == 1


# ---- scaffold_templates ------------------------------------------------------

def test_scaffold_templates_apply_json(tmp_path):
    vault = _make_vault(tmp_path)
    out = _run([
        "-m", "obsidian_kb_skill.scripts.scaffold_templates", str(vault),
        "--apply", "--json",
    ])

    assert out["schema_version"] == "1.0"
    assert out["operation"] == "scaffold-templates"
    assert out["apply"] is True
    assert out["force"] is False
    assert out["written"]
    assert isinstance(out["skipped"], list)
    assert Path(out["templates_dir"]) == vault / "Templates"
