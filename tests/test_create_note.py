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
    for field in ("source:", "author:", "published:", "capture_depth: standard"):
        assert field in rendered


@pytest.mark.parametrize(
    "placeholder",
    [
        "unknown",
        "未知",
        "N/A",
        "TODO",
        "待补充",
        "TODO: verify",
        "unknown author",
        "unknown作者",
        "unknown writer",
        "unknown (not provided)",
        "TODO待确认",
        "待补充作者",
        "none provided",
        "null value",
        "N/A pending",
        "ＴＯＤＯ：verify",
    ],
)
def test_web_clip_required_metadata_rejects_vague_placeholders(placeholder):
    metadata = {
        "source": "https://example.com/article",
        "author": placeholder,
        "published": "2026-07-27",
    }

    assert missing_required_metadata("web-clip", metadata) == ["author"]


@pytest.mark.parametrize(
    "author",
    [
        "Todor Zhivkov",
        "Nulla Rossi",
        "Jane TODO Smith",
        "Unknown Mortal Orchestra",
        "unknown@example.com",
    ],
)
def test_web_clip_required_metadata_accepts_nonplaceholder_substrings(author):
    metadata = {
        "source": "https://example.com/article",
        "author": author,
        "published": "2026-07-27",
    }

    assert missing_required_metadata("web-clip", metadata) == []


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
    (vault / "20-Learning").mkdir()
    complete_markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 张三\n"
        "published: 2026-07-13\n"
        "capture_depth: verified\n"
        "---\n"
        "# 中文文章\n\n"
        "## 来源与结论\n\n来源结论。\n\n"
        "## 问题、前提与适用边界\n\n"
        "### 适用边界\n\n仅适用于示例项目。\n\n"
        "### 反例\n\n职责无法稳定拆分时不应强行采用多智能体。\n\n"
        "## 核心知识与原理\n\n"
        "### 因果链\n\n多智能体通过明确分工协作。\n\n"
        "## 具体做法与示例\n\n"
        "### 应用方法\n\n先规划，再执行，最后验证。\n\n"
        "## 验证、风险与限制\n\n运行项目测试确认结果。\n\n"
        "## 理解与启发\n\n"
        "本文推导：职责隔离可以降低上下文干扰。\n\n"
        "## 关联笔记\n"
    )

    preflight = subprocess.run(
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
            "--preflight-json",
        ],
        input=complete_markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert preflight.returncode == 2
    initial = json.loads(preflight.stdout)
    assert initial["semantic_receipt"]["error"]["code"] == "missing-capture-receipt"
    receipt = {
        "schema_version": 1,
        "content_sha256": initial["content"]["sha256"],
        "profile": "conceptual-opinion",
        "source_access": "complete",
        "primary_sources": ["https://example.com/article"],
        "supplemental_sources": [],
        "material_items": [
            {
                "id": "boundary",
                "kind": "boundary",
                "source": "https://example.com/article",
                "note_anchor": "### 适用边界",
                "status": "resolved",
            },
            {
                "id": "causal-chain",
                "kind": "causal-claim",
                "source": "https://example.com/article",
                "note_anchor": "### 因果链",
                "status": "resolved",
            },
            {
                "id": "application-method",
                "kind": "application-method",
                "source": "https://example.com/article",
                "note_anchor": "### 应用方法",
                "status": "resolved",
            },
            {
                "id": "counterexample",
                "kind": "counterexample",
                "source": "https://example.com/article",
                "note_anchor": "### 反例",
                "status": "resolved",
            },
        ],
        "numeric_claims": [],
        "inferences": [
            {
                "note_excerpt": "本文推导：职责隔离可以降低上下文干扰。",
                "basis": "文中的多智能体职责分工",
                "label": "本文推导",
            }
        ],
        "practical_artifact": {
            "kind": "application-method",
            "note_anchor": "### 应用方法",
        },
        "unresolved_items": [],
    }
    accepted = subprocess.run(
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
            "--capture-receipt-json",
            json.dumps(receipt, ensure_ascii=False),
            "--preflight-json",
        ],
        input=complete_markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )
    assert accepted.returncode == 0, accepted.stdout
    receipt_sha256 = json.loads(accepted.stdout)["semantic_receipt"]["sha256"]
    missing_identity = subprocess.run(
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
            "--capture-receipt-json",
            json.dumps(receipt, ensure_ascii=False),
            "--apply",
            "--compact-json",
        ],
        input=complete_markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )
    assert missing_identity.returncode == 2
    assert (
        json.loads(missing_identity.stdout)["error"]["code"]
        == "missing-capture-receipt-sha256"
    )
    assert not list((vault / "20-Learning").glob("*中文文章.md"))
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
            "--capture-receipt-json",
            json.dumps(receipt, ensure_ascii=False),
            "--expect-capture-receipt-sha256",
            receipt_sha256,
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
    assert metadata["capture_depth"] == "verified"
    assert "多智能体通过明确分工协作" in body


def test_standard_web_clip_applies_without_capture_receipt(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "20-Learning").mkdir()
    markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 示例作者\n"
        "published: 2026-07-31\n"
        "capture_depth: standard\n"
        "---\n"
        "# 普通沉淀\n\n"
        "## 来源与结论\n\n保留文章的核心结论。\n\n"
        "## 问题、前提与适用边界\n\n适用于普通阅读记录。\n\n"
        "## 核心知识与原理\n\n重构核心知识。\n\n"
        "## 具体做法与示例\n\n保留有价值的示例。\n\n"
        "## 验证、风险与限制\n\n作者主张尚未独立验证。\n\n"
        "## 理解与启发\n\n可迁移的启发。\n\n"
        "## 关联笔记\n"
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
            "普通沉淀",
            "--stdin",
            "--date",
            "2026-07-31",
            "--apply",
            "--compact-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "semantic_receipt" not in payload
    created = vault / "20-Learning" / "2026-07-31 普通沉淀.md"
    metadata, _ = split_frontmatter(created.read_text(encoding="utf-8"))
    assert metadata["capture_depth"] == "standard"


@pytest.mark.parametrize("capture_depth", ["deep", "research", "", "VERIFIED"])
def test_web_clip_rejects_invalid_capture_depth_before_write(
    tmp_path, capture_depth
):
    vault = make_vault(tmp_path)
    (vault / "20-Learning").mkdir()
    markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 示例作者\n"
        "published: 2026-07-31\n"
        f'capture_depth: "{capture_depth}"\n'
        "---\n"
        "# Invalid depth\n"
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
            "Invalid depth",
            "--stdin",
            "--date",
            "2026-07-31",
            "--apply",
            "--compact-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "invalid-capture-depth"
    assert not list((vault / "20-Learning").glob("*Invalid depth.md"))


def test_quick_inbox_web_clip_does_not_require_capture_receipt(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox").mkdir()
    markdown = (
        "---\n"
        "source: https://example.com/unread\n"
        "author: 示例作者\n"
        "published: 2026-07-28\n"
        "---\n"
        "# 稍后阅读\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--folder",
            "00-Inbox",
            "--title",
            "稍后阅读",
            "--stdin",
            "--date",
            "2026-07-28",
            "--apply",
            "--compact-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 0, result.stderr
    assert "semantic_receipt" not in json.loads(result.stdout)


def test_verified_web_clip_cannot_target_inbox(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox").mkdir()
    markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 示例作者\n"
        "published: 2026-07-31\n"
        "capture_depth: verified\n"
        "---\n"
        "# Wrong route\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--folder",
            "00-Inbox",
            "--title",
            "Wrong route",
            "--stdin",
            "--date",
            "2026-07-31",
            "--apply",
            "--compact-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    assert (
        json.loads(result.stdout)["error"]["code"]
        == "capture-depth-route-mismatch"
    )
    assert not list((vault / "00-Inbox").glob("*Wrong route.md"))


def test_standard_web_clip_rejects_capture_receipt(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "20-Learning").mkdir()
    markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 示例作者\n"
        "published: 2026-07-31\n"
        "capture_depth: standard\n"
        "---\n"
        "# Standard cannot carry verified evidence\n"
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
            "Standard receipt mismatch",
            "--stdin",
            "--date",
            "2026-07-31",
            "--capture-receipt-json",
            "{}",
            "--preflight-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    assert (
        json.loads(result.stdout)["semantic_receipt"]["error"]["code"]
        == "unexpected-capture-receipt"
    )
    assert not list((vault / "20-Learning").glob("*Standard receipt mismatch.md"))


@pytest.mark.parametrize("folder", ["00-Inbox/../20-Learning", "00-Inbox/Alias"])
def test_canonical_destination_cannot_bypass_capture_receipt(tmp_path, folder):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox").mkdir()
    (vault / "20-Learning").mkdir()
    if folder.endswith("/Alias"):
        try:
            (vault / "00-Inbox" / "Alias").symlink_to(
                vault / "20-Learning", target_is_directory=True
            )
        except OSError as exc:
            pytest.skip(f"directory symlink creation unavailable: {exc}")
    markdown = (
        "---\n"
        "source: https://example.com/article\n"
        "author: 示例作者\n"
        "published: 2026-07-28\n"
        "capture_depth: verified\n"
        "---\n"
        "# Finished article\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.create_note",
            str(vault),
            "--type",
            "web-clip",
            "--folder",
            folder,
            "--title",
            "Canonical Route",
            "--stdin",
            "--date",
            "2026-07-28",
            "--apply",
            "--compact-json",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=ENV,
    )

    assert result.returncode == 2
    assert (
        json.loads(result.stdout)["error"]["code"]
        == "missing-capture-receipt"
    )
    assert not list((vault / "20-Learning").glob("*Canonical Route.md"))


def test_create_note_rejects_missing_destination_folder(tmp_path):
    vault = make_vault(tmp_path)

    result = _run(
        str(vault),
        "--type",
        "insight-note",
        "--folder",
        "30-Insights/New",
        "--title",
        "No Silent Directory",
        "--preflight-json",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "missing-destination-folder"
    assert not (vault / "30-Insights" / "New").exists()


def test_task_memory_preflight_is_read_only_and_apply_initializes_operational_path(
    tmp_path,
):
    vault = make_vault(tmp_path)
    common = [
        sys.executable,
        "-m",
        "obsidian_kb_skill.scripts.create_note",
        str(vault),
        "--type",
        "task-memory",
        "--folder",
        "Tasks/demo",
        "--title",
        "TASK",
        "--date",
        "2026-07-28",
        "--stdin",
    ]
    preflight = subprocess.run(
        [*common, "--preflight-json"],
        input="# Task\n\nActive context.\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=ENV,
    )

    assert preflight.returncode == 0, preflight.stdout
    assert json.loads(preflight.stdout)["folder"] == "Tasks/demo"
    assert not (vault / "Tasks").exists()

    applied = subprocess.run(
        [*common, "--apply", "--compact-json"],
        input="# Task\n\nActive context.\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=ENV,
    )

    assert applied.returncode == 0, applied.stdout
    payload = json.loads(applied.stdout)
    assert payload["folder"] == "Tasks/demo"
    assert Path(payload["path"]).name == "TASK.md"
    assert (vault / "Tasks" / "demo" / "TASK.md").is_file()


@pytest.mark.parametrize(
    "folder",
    ["Tasks", "Tasks/Demo", "Tasks/demo/nested", "Tasks/../demo", "Other/demo"],
)
def test_task_memory_initialization_rejects_non_operational_paths(tmp_path, folder):
    vault = make_vault(tmp_path)

    result = _run(
        str(vault),
        "--type",
        "task-memory",
        "--folder",
        folder,
        "--title",
        "TASK",
        "--preflight-json",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "invalid-task-memory-folder"
    assert not (vault / "Tasks").exists()


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


def test_task_memory_refuses_a_symlinked_tasks_alias(tmp_path):
    """`Tasks/<slug>` must also be the resolved destination, not just the input.

    The shape rule was checked against the requested string only, so a symlink
    named `Tasks` filed operational notes outside the Tasks tree while still
    passing validation.
    """
    from obsidian_kb_skill.scripts.create_note import initialize_task_memory_folder

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "RealTasks").mkdir()
    try:
        (vault / "Tasks").symlink_to(vault / "RealTasks", target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ValueError) as error:
        initialize_task_memory_folder(vault, "Tasks/demo")

    assert "Tasks" in str(error.value)
    assert not (vault / "RealTasks" / "demo").exists()


def test_task_memory_still_initializes_a_real_tasks_folder(tmp_path):
    """Guard: the ordinary path must keep working."""
    from obsidian_kb_skill.scripts.create_note import initialize_task_memory_folder

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)

    initialize_task_memory_folder(vault, "Tasks/demo")

    assert (vault / "Tasks" / "demo").is_dir()


def _apply_with_body(vault: Path, body: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", str(vault),
         "--type", "insight-note", "--title", "Residue", "--stdin",
         "--date", "2026-07-09", "--apply", *extra],
        input=body, capture_output=True, text=True, cwd=ROOT, env=ENV,
    )


TEMPLATE_RESIDUE = (
    "<!-- 用 2–4 句话区分原文观点与自己的推论 -->\n\n"
    "正文内容在这里，足够长以通过任何长度检查。\n"
)


def test_apply_refuses_a_body_that_still_holds_its_template_instructions(tmp_path):
    """The audit knew, in the same call, and the file was on disk anyway.

    On the reference Vault nine notes hold instructions addressed to the Agent —
    `<!-- 用 2–4 句话区分... -->` is guidance for whoever writes the note, and it
    shipped as part of the user's note. Every caller that judges by exit code was
    told the write succeeded.
    """
    vault = make_vault(tmp_path)

    r = _apply_with_body(vault, TEMPLATE_RESIDUE)

    assert r.returncode != 0, r.stdout
    assert not (vault / "30-Insights" / "2026-07-09 Residue.md").exists()


def test_a_clean_body_still_applies_and_exits_zero(tmp_path):
    vault = make_vault(tmp_path)

    r = _apply_with_body(vault, "正文内容在这里，足够长以通过任何长度检查。\n")

    assert r.returncode == 0, r.stderr
    assert (vault / "30-Insights" / "2026-07-09 Residue.md").is_file()


def test_no_audit_skips_the_report_but_not_the_refusal(tmp_path):
    """Skipping a report is a convenience; skipping the refusal writes a defect.

    `--no-audit` exists to save the post-write pass. Letting it also disable the
    refusal would make it the flag that writes a known-broken note.
    """
    vault = make_vault(tmp_path)

    r = _apply_with_body(vault, TEMPLATE_RESIDUE, "--no-audit")

    assert r.returncode != 0, r.stdout
    assert not (vault / "30-Insights" / "2026-07-09 Residue.md").exists()


def test_a_refusal_uses_the_error_envelope_and_a_write_carries_ok(tmp_path):
    """`audit.ok` was false while the exit code said success and `ok` was absent.

    #156 asked for a top-level `ok` on both paths. On the refusal path that
    would contradict the envelope `rules-and-errors.md` pins and
    `test_error_code_contract.py` enforces, so a refusal keeps the documented
    `{"error": {...}}` shape and exit 2, and `ok` is added to the success
    payload where nothing had reported the verdict at all.
    """
    vault = make_vault(tmp_path)

    bad = _apply_with_body(vault, TEMPLATE_RESIDUE, "--json")
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["error"]["code"] == "unfinished-template-body"

    good = _apply_with_body(vault, "正文足够长以通过任何长度检查。\n", "--json")
    assert json.loads(good.stdout)["ok"] is True
    assert good.returncode == 0


def test_linking_a_note_that_is_not_written_yet_does_not_block_creation(tmp_path):
    """`broken-wikilink` is a defect and must not join the refusal set.

    #159 settled that linking an unwritten note is standard Obsidian usage — the
    unresolved link is how the graph shows a concept worth its own note. Refusing
    every defect would make it impossible to create a note that points forward.
    """
    vault = make_vault(tmp_path)

    r = _apply_with_body(vault, "这篇讲的是 [[CQRS]]，那篇还没写。\n")

    assert r.returncode == 0, r.stdout
    assert (vault / "30-Insights" / "2026-07-09 Residue.md").is_file()


def test_every_refused_code_is_a_defect_the_author_can_fix_by_rewriting(tmp_path):
    """The refusal set must stay a subset of what the audit calls a defect.

    A code refused on write but graded `hygiene` by the audit would mean the two
    paths disagree about how bad it is, which is the shape this repo keeps
    finding. `broken-wikilink` is asserted out by name: it is a defect the audit
    reports and the writer must not refuse.
    """
    from obsidian_kb_skill.scripts.audit_vault import FINDING_SEVERITY
    from obsidian_kb_skill.scripts.create_note import REFUSED_ON_APPLY

    assert REFUSED_ON_APPLY
    for code in REFUSED_ON_APPLY:
        assert FINDING_SEVERITY[code] == "defect", code
    assert "broken-wikilink" not in REFUSED_ON_APPLY
