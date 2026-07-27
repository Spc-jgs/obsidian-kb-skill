"""Tests for the note creator (scripts/create_note.py)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.create_note import (
    build_note,
    missing_required_metadata,
    resolve_dest,
    sanitize_filename,
    split_frontmatter,
    write_new_note,
)
from obsidian_kb_skill.scripts.template_contract import template_sha256

ROOT = Path(__file__).resolve().parent.parent
ENV = {**__import__("os").environ, "PYTHONPATH": str(ROOT)}


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run the script as a module with the repo root importable."""
    return subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", *args],
        cwd=str(ROOT),
        env=ENV,
        capture_output=True,
        text=True,
    )


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def write_insight_template(
    vault: Path,
    body: str = "## Custom section\n\nTemplate guidance.\n",
) -> Path:
    template = vault / "Templates" / "Insight Note.md"
    template.write_text(
        "---\n"
        "type: insight-note\n"
        "tags: [insight]\n"
        "---\n"
        "# {{title}}\n\n"
        f"{body}",
        encoding="utf-8",
    )
    return template


def test_build_note_defaults_insight():
    folder, rendered = build_note(
        note_type="insight-note", title="T", date="2026-07-09", body="# hi\n"
    )
    assert folder == "30-Insights"
    assert "type: insight-note" in rendered
    assert "date:" in rendered and "2026-07-09" in rendered
    assert "tags:" in rendered and "- insight" in rendered
    assert "related: []" in rendered
    assert "source:" in rendered  # insight extra field


def test_build_note_web_clip_has_required_fields():
    _, rendered = build_note(
        note_type="web-clip", title="C", date="2026-07-09", body="x"
    )
    for field in ("source:", "author:", "published:"):
        assert field in rendered


@pytest.mark.parametrize("placeholder", ["unknown", "未知", "N/A", "TODO", "待补充"])
def test_web_clip_required_metadata_rejects_vague_placeholders(placeholder):
    metadata = {
        "source": "https://example.com/article",
        "author": placeholder,
        "published": "2026-07-27",
    }

    assert missing_required_metadata("web-clip", metadata) == ["author"]


def test_web_clip_required_metadata_accepts_explicit_source_absence():
    metadata = {
        "source": "https://example.com/article",
        "author": "原文未署名",
        "published": "原文未标明",
    }

    assert missing_required_metadata("web-clip", metadata) == []


def test_build_note_normalizes_yaml_date_scalars():
    _, rendered = build_note(
        note_type="web-clip",
        title="Dated",
        date="2026-07-13",
        body="# Clip\n",
        given_meta={
            "source": "https://example.com/article",
            "author": "张三",
            "published": datetime.date(2026, 7, 13),
            "nested": {"captured": datetime.datetime(2026, 7, 13, 9, 30)},
        },
    )

    metadata, _ = split_frontmatter(rendered)
    assert metadata["published"] == "2026-07-13"
    assert isinstance(metadata["published"], str)
    assert metadata["nested"]["captured"] == "2026-07-13T09:30:00"


def test_build_note_unknown_type_raises():
    with pytest.raises(ValueError):
        build_note(note_type="nope", title="T", date="2026-07-09", body="")


def test_split_frontmatter_merges():
    meta, body = split_frontmatter("---\nfoo: bar\n---\n# Body\n")
    assert meta.get("foo") == "bar"
    assert body.strip() == "# Body"


def test_split_frontmatter_rejects_invalid_yaml_with_full_input_location():
    malformed = (
        '---\nsource: "https://example.com"\n'
        'author: "用户（说明："登录后可见"）"\n'
        "published: 2026-07-14\n---\n# Body\n"
    )

    with pytest.raises(ValueError) as caught:
        split_frontmatter(malformed)

    error = caught.value
    assert error.code == "invalid-frontmatter"
    assert error.line == 3
    assert error.column == 17
    assert error.message == "expected <block end>, but found '<scalar>'"


def test_split_frontmatter_preserves_current_non_mapping_compatibility():
    source = "---\n- one\n- two\n---\n# Body\n"
    metadata, body = split_frontmatter(source)
    assert metadata == {}
    assert body == source


def test_input_frontmatter_overrides_template_and_cli_fields_win(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\n"
        "source: template\n"
        "related: ['[[template-note]]']\n"
        "tags: [template]\n"
        "date: 2000-01-01\n"
        "type: template-type\n"
        "---\n"
        "# Template\n",
        encoding="utf-8",
    )

    _, rendered = build_note(
        note_type="insight-note",
        title="T",
        date="2026-07-11",
        body="# Body\n",
        given_meta={
            "source": "stdin",
            "related": ["[[stdin-note]]"],
            "tags": ["stdin"],
            "date": "1999-01-01",
            "type": "stdin-type",
        },
        tags=["cli"],
        vault=vault,
    )

    meta, _ = split_frontmatter(rendered)
    assert meta["source"] == "stdin"
    assert meta["related"] == ["[[stdin-note]]"]
    assert meta["tags"] == ["cli"]
    assert meta["type"] == "insight-note"
    assert meta["date"] == "2026-07-11"


def test_stdin_help_mentions_frontmatter_merge():
    result = _run("--help")
    normalized = " ".join(result.stdout.lower().split())

    assert result.returncode == 0
    assert "--stdin" in result.stdout
    assert "optional frontmatter is merged" in normalized


def test_sanitize_filename_strips_unsafe():
    assert "/" not in sanitize_filename('a/b:c*?"<>|')
    assert sanitize_filename("   ") == "untitled"


def test_resolve_dest_appends_suffix(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "2026-07-09 T.md").write_text("x", encoding="utf-8")
    dest = resolve_dest(vault, "30-Insights", "2026-07-09 T.md")
    assert dest.name == "2026-07-09 T-2.md"


def test_write_new_note_retries_when_another_writer_wins_race(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    original_open = Path.open
    raced = False

    def racing_open(path: Path, mode: str = "r", *args, **kwargs):
        nonlocal raced
        if mode == "xb" and not raced:
            raced = True
            with original_open(path, "wb") as handle:
                handle.write(b"other writer")
            raise FileExistsError(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    created = write_new_note(
        vault,
        "30-Insights",
        "2026-07-14 Race.md",
        b"our bytes",
    )

    first = vault / "30-Insights" / "2026-07-14 Race.md"
    assert first.read_bytes() == b"other writer"
    assert created.name == "2026-07-14 Race-2.md"
    assert created.read_bytes() == b"our bytes"


def test_concurrent_same_title_creates_two_complete_notes(tmp_path):
    vault = make_vault(tmp_path)
    command = [
        sys.executable,
        "-m",
        "obsidian_kb_skill.scripts.create_note",
        str(vault),
        "--type",
        "insight-note",
        "--title",
        "Concurrent",
        "--date",
        "2026-07-14",
        "--stdin",
        "--apply",
        "--compact-json",
    ]
    processes = [
        subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=ROOT,
            env=ENV,
        )
        for _ in range(2)
    ]
    results = [process.communicate("# Concurrent\n\nComplete body.\n") for process in processes]

    for process, (stdout, stderr) in zip(processes, results):
        assert process.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"
    created = sorted((vault / "30-Insights").glob("2026-07-14 Concurrent*.md"))
    assert [path.name for path in created] == [
        "2026-07-14 Concurrent-2.md",
        "2026-07-14 Concurrent.md",
    ]
    assert all("Complete body." in path.read_text(encoding="utf-8") for path in created)


def test_dry_run_writes_nothing(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Dry", "--stdin"],
        input="# dry\n", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0
    assert "dry run" in r.stdout
    assert not list((vault / "30-Insights").glob("*.md"))


def test_invalid_stdin_frontmatter_reports_location_and_writes_nothing(tmp_path):
    vault = make_vault(tmp_path)
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
            "--apply",
        ],
        input=malformed.encode("utf-8"),
        capture_output=True,
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    stderr = result.stderr.decode("utf-8")
    assert "invalid YAML frontmatter in stdin at line 3, column 17" in stderr
    assert "expected <block end>, but found '<scalar>'" in stderr
    assert not list(vault.rglob("*Malformed*.md"))


def test_apply_creates_note_and_updates_index(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Created", "--stdin", "--date", "2026-07-09", "--apply"],
        input="# body\n", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    created = vault / "30-Insights" / "2026-07-09 Created.md"
    assert created.is_file()
    text = created.read_text(encoding="utf-8")
    assert "type: insight-note" in text
    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    assert index_text == (
        "# Insights\n\n## Recent\n"
        "- [[30-Insights/2026-07-09 Created|Created]] (2026-07-09)\n"
    )


def test_web_clip_preflight_rejects_missing_metadata_without_mutation(tmp_path):
    vault = make_vault(tmp_path)
    learning = vault / "20-Learning"
    learning.mkdir()
    index = learning / "INDEX.md"
    original_index = "# Learning\n\n## Recent\n"
    index.write_text(original_index, encoding="utf-8")

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
            "--date",
            "2026-07-13",
            "--apply",
        ],
        input="# Incomplete\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    assert "source" in result.stderr
    assert "author" in result.stderr
    assert "published" in result.stderr
    assert not list(learning.glob("2026-07-13 Incomplete*.md"))
    assert index.read_text(encoding="utf-8") == original_index


def test_complete_web_clip_from_stdin_is_normalized_and_audited(tmp_path):
    vault = make_vault(tmp_path)
    complete_markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 张三\n"
        "published: 2026-07-13\n"
        "---\n"
        "# 中文文章\n\n"
        "多智能体协作。\n"
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
            "中文文章",
            "--stdin",
            "--date",
            "2026-07-13",
            "--apply",
        ],
        input=complete_markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 0, result.stderr
    assert "AUDIT: OK" in result.stdout
    created = vault / "20-Learning" / "2026-07-13 中文文章.md"
    metadata, body = split_frontmatter(created.read_text(encoding="utf-8"))
    assert metadata["published"] == "2026-07-13"
    assert isinstance(metadata["published"], str)
    assert metadata["author"] == "张三"
    assert "多智能体协作" in body


def test_split_frontmatter_accepts_utf8_bom_and_windows_newlines():
    metadata, body = split_frontmatter(
        "\ufeff---\r\n"
        "source: https://example.com/windows\r\n"
        "author: QoderWork\r\n"
        "published: 2026-07-13\r\n"
        "---\r\n"
        "# 中文输入 🧠\r\n"
    )

    assert metadata["source"] == "https://example.com/windows"
    assert metadata["author"] == "QoderWork"
    assert metadata["published"].isoformat() == "2026-07-13"
    assert body == "# 中文输入 🧠\n"


def test_apply_refuses_non_vault(tmp_path):
    not_vault = tmp_path / "notvault"
    not_vault.mkdir()
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(not_vault), "--type", "insight-note",
         "--title", "X", "--stdin", "--date", "2026-07-09", "--apply"],
        input="x", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 2
    assert not list(not_vault.glob("*.md"))


def test_apply_never_overwrites(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "2026-07-09 Dup.md").write_text("orig", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Dup", "--stdin", "--date", "2026-07-09", "--apply"],
        input="new", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0
    assert (vault / "30-Insights" / "2026-07-09 Dup-2.md").is_file()
    assert (vault / "30-Insights" / "2026-07-09 Dup.md").read_text(encoding="utf-8") == "orig"


def test_relative_content_file_reads_validated_vault_path_from_hostile_cwd(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "input.md").write_text("# INSIDE SAFE\n\nVault content.\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input.md").write_text("# OUTSIDE LEAK\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "insight-note",
            "--title",
            "Boundary",
            "--content-file",
            "input.md",
            "--date",
            "2026-07-14",
            "--apply",
            "--compact-json",
        ],
        capture_output=True,
        text=True,
        cwd=outside,
        env=ENV,
    )

    assert result.returncode == 0, result.stderr
    created = vault / "30-Insights" / "2026-07-14 Boundary.md"
    text = created.read_text(encoding="utf-8")
    assert "INSIDE SAFE" in text
    assert "OUTSIDE LEAK" not in text


def test_template_body_does_not_emit_frontmatter_only_warning(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\ntype: insight-note\ntags: [insight]\n---\n"
        "# Template\n\nActual template body.\n",
        encoding="utf-8",
    )

    result = _run(
        str(vault),
        "--type",
        "insight-note",
        "--title",
        "Templated",
        "--date",
        "2026-07-14",
        "--apply",
    )

    assert result.returncode == 0, result.stderr
    assert "frontmatter-only" not in result.stderr
    created = vault / "30-Insights" / "2026-07-14 Templated.md"
    assert "Actual template body." in created.read_text(encoding="utf-8")


def test_apply_runs_automatic_audit_ok(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Audited", "--stdin", "--date", "2026-07-09", "--apply"],
        input="# Insight\n\nThis is the actual note content.\n",
        capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT: OK" in r.stdout


def test_apply_audit_flags_broken_wikilink(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Broken", "--stdin", "--date", "2026-07-09", "--apply"],
        input="see [[No Such Note]]\n", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT:" in r.stdout
    assert "broken-wikilink" in r.stdout


def test_no_audit_suppresses_audit(tmp_path):
    vault = make_vault(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "Quiet", "--stdin", "--date", "2026-07-09", "--apply", "--no-audit"],
        input="# Insight\n\nThis is the actual note content.\n",
        capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    assert "AUDIT:" not in r.stdout


def test_suggest_links_after_create(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Existing Topic.md").write_text(
        '---\ntype: insight-note\ndate: 2026-07-01\ntags: [insight]\n---\n'
        "# Existing Topic\n\nPrior art.\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault), "--type", "insight-note",
         "--title", "New Topic", "--stdin", "--date", "2026-07-09", "--apply", "--suggest-links"],
        input="# New Topic\n\nFresh content.\n", capture_output=True, text=True, cwd=ROOT,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    assert "SUGGESTED LINKS" in r.stdout
    assert "Existing Topic" in r.stdout


def test_preflight_rejects_stale_template_sha256_without_mutation(tmp_path):
    vault = make_vault(tmp_path)
    template = write_insight_template(vault)
    old_hash = template_sha256(template.read_text(encoding="utf-8"))
    template.write_text(
        template.read_text(encoding="utf-8") + "\nChanged after inspection.\n",
        encoding="utf-8",
    )

    result = _run(
        str(vault), "--type", "insight-note", "--title", "Stale",
        "--date", "2026-07-16", "--expect-template-sha256", old_hash,
        "--preflight-json",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "template-changed"
    assert payload["error"]["expected_sha256"] == old_hash
    assert payload["error"]["actual_sha256"] == template_sha256(
        template.read_text(encoding="utf-8")
    )
    assert not (vault / "30-Insights" / "2026-07-16 Stale.md").exists()


def test_apply_rejects_stale_template_sha256_without_mutation(tmp_path):
    vault = make_vault(tmp_path)
    template = write_insight_template(vault)
    old_hash = template_sha256(template.read_text(encoding="utf-8"))
    template.write_text(
        template.read_text(encoding="utf-8") + "\nChanged after inspection.\n",
        encoding="utf-8",
    )
    index = vault / "30-Insights" / "INDEX.md"
    index.write_text("# Insights\n", encoding="utf-8")

    result = _run(
        str(vault), "--type", "insight-note", "--title", "Stale",
        "--date", "2026-07-16", "--expect-template-sha256", old_hash,
        "--apply", "--compact-json",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "template-changed"
    assert index.read_text(encoding="utf-8") == "# Insights\n"
    assert not (vault / "30-Insights" / "2026-07-16 Stale.md").exists()


def test_preflight_accepts_current_template_sha256(tmp_path):
    vault = make_vault(tmp_path)
    template = write_insight_template(vault)
    current_hash = template_sha256(template.read_text(encoding="utf-8"))

    result = _run(
        str(vault), "--type", "insight-note", "--title", "Current",
        "--date", "2026-07-16", "--expect-template-sha256", current_hash,
        "--preflight-json",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["validation"]["ok"] is True


def test_rejects_invalid_expected_template_sha256(tmp_path):
    vault = make_vault(tmp_path)

    result = _run(
        str(vault), "--type", "insight-note", "--title", "Invalid hash",
        "--expect-template-sha256", "ABC123", "--preflight-json",
    )

    assert result.returncode == 2
    assert "64 lowercase hexadecimal" in result.stderr
