"""Deterministic, read-only Vault retrieval contracts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.search_vault import search_vault, tokenize
from obsidian_kb_skill.scripts.vault_paths import PathOutsideVaultError


ROOT = Path(__file__).resolve().parent.parent


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for folder in (
        "20-Learning",
        "30-Insights",
        "90-Archive",
        "Templates",
        "Attachments",
    ):
        (vault / folder).mkdir()
    return vault


def _note(
    path: Path,
    *,
    title: str,
    body: str,
    aliases: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    metadata = [
        "---",
        "type: learning-note",
        "date: 2026-07-29",
        f"aliases: {json.dumps(aliases or [], ensure_ascii=False)}",
        f"tags: {json.dumps(tags or [], ensure_ascii=False)}",
        "---",
    ]
    path.write_text(
        "\n".join(metadata) + f"\n# {title}\n\n{body}\n",
        encoding="utf-8",
    )


def _hashes(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(vault.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.search_vault", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )


def test_tokenize_supports_english_chinese_and_mixed_queries():
    assert tokenize("Spring AI MCP") == ["spring", "ai", "mcp"]
    assert tokenize("知识库检索") == ["知识", "识库", "库检", "检索"]
    assert tokenize("Spring知识库 1.23") == [
        "spring",
        "知识",
        "识库",
        "1",
        "23",
    ]


def test_title_alias_tag_heading_and_body_matches_are_explainable(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault / "20-Learning" / "protocol.md",
        title="Model Context Protocol",
        aliases=["MCP 协议"],
        tags=["agent", "tool-protocol"],
        body=(
            "## 客户端配置\n\n"
            "Spring AI 通过 stdio 连接 MCP server。\n\n"
            "参见 [[Agent 工具设计|工具设计]]。"
        ),
    )

    payload = search_vault(vault, "Spring MCP 客户端", top_k=5)

    assert payload["results"][0]["path"] == "20-Learning/protocol.md"
    assert payload["results"][0]["heading"] == "客户端配置"
    assert payload["results"][0]["line"] > 1
    assert "Spring AI" in payload["results"][0]["snippet"]
    kinds = {signal["kind"] for signal in payload["results"][0]["signals"]}
    assert {"alias", "heading", "body"} <= kinds


def test_exact_title_outranks_repeated_body_mentions(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault / "20-Learning" / "title.md",
        title="Hybrid Search",
        body="A short implementation note.",
    )
    _note(
        vault / "20-Learning" / "body.md",
        title="Search Notes",
        body="Hybrid search hybrid search hybrid search hybrid search.",
    )

    payload = search_vault(vault, "Hybrid Search", top_k=5)

    assert [item["path"] for item in payload["results"][:2]] == [
        "20-Learning/title.md",
        "20-Learning/body.md",
    ]
    assert payload["results"][0]["signals"][0]["kind"] == "title-exact"


def test_fuzzy_alias_match_finds_typo(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault / "20-Learning" / "retrieval.md",
        title="Knowledge Retrieval",
        aliases=["Obsidian Retriever"],
        body="Local search implementation.",
    )

    payload = search_vault(vault, "Obsidian Retriver", top_k=5)

    assert payload["results"][0]["path"] == "20-Learning/retrieval.md"
    assert any(
        signal["kind"] == "alias-fuzzy"
        for signal in payload["results"][0]["signals"]
    )


def test_ties_are_ordered_by_relative_path(tmp_path):
    vault = _vault(tmp_path)
    _note(vault / "30-Insights" / "B.md", title="B", body="shared needle")
    _note(vault / "30-Insights" / "A.md", title="A", body="shared needle")

    payload = search_vault(vault, "needle", top_k=5)

    assert [result["path"] for result in payload["results"]] == [
        "30-Insights/A.md",
        "30-Insights/B.md",
    ]


def test_search_excludes_comments_hidden_templates_attachments_and_symlinks(tmp_path):
    vault = _vault(tmp_path)
    hidden = vault / ".private"
    hidden.mkdir()
    _note(hidden / "secret.md", title="Secret", body="private-needle")
    _note(
        vault / "Templates" / "Template.md",
        title="Template",
        body="private-needle",
    )
    _note(
        vault / "Attachments" / "Attachment.md",
        title="Attachment",
        body="private-needle",
    )
    visible = vault / "20-Learning" / "visible.md"
    _note(
        visible,
        title="Visible",
        body="<!-- private-needle -->\n\nreader-visible text",
    )
    outside = tmp_path / "outside.md"
    _note(outside, title="Outside", body="private-needle")
    try:
        (vault / "20-Learning" / "linked.md").symlink_to(outside)
        (vault / "20-Learning" / "linked-dir").symlink_to(
            hidden, target_is_directory=True
        )
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    payload = search_vault(vault, "private-needle", top_k=20)

    assert payload["results"] == []
    assert payload["scanned"]["files"] == 1


def test_malformed_frontmatter_is_bounded_issue_not_whole_search_failure(tmp_path):
    vault = _vault(tmp_path)
    (vault / "20-Learning" / "bad.md").write_text(
        "---\ntags: [broken\n---\n# Bad\nneedle\n",
        encoding="utf-8",
    )
    _note(vault / "20-Learning" / "good.md", title="Good", body="needle")

    payload = search_vault(vault, "needle", top_k=5)

    assert payload["results"][0]["path"] == "20-Learning/good.md"
    assert payload["scanned"] == {"files": 2, "indexed": 1, "skipped": 1}
    assert payload["issues"][0]["code"] == "invalid-frontmatter"
    assert payload["issues"][0]["path"] == "20-Learning/bad.md"


def test_no_results_is_successful_and_output_is_bounded(tmp_path):
    vault = _vault(tmp_path)
    _note(vault / "20-Learning" / "one.md", title="One", body="ordinary body")

    payload = search_vault(vault, "missing", top_k=5)

    assert payload["schema_version"] == "1.0"
    assert payload["mode"] == "lexical"
    assert payload["results"] == []
    assert payload["truncated"] is False
    assert len(json.dumps(payload, ensure_ascii=False)) < 16_384


def test_search_is_byte_for_byte_read_only(tmp_path):
    vault = _vault(tmp_path)
    _note(vault / "20-Learning" / "one.md", title="One", body="needle")
    before = _hashes(vault)

    search_vault(vault, "needle", top_k=5)

    assert _hashes(vault) == before


def test_direct_api_rejects_scope_outside_vault(tmp_path):
    vault = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(PathOutsideVaultError, match="outside the Vault"):
        search_vault(vault, "needle", scope=outside)


def test_cli_emits_structured_json(tmp_path):
    vault = _vault(tmp_path)
    _note(vault / "20-Learning" / "one.md", title="One", body="needle")

    result = _run(str(vault), "--query", "needle", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["results"][0]["path"] == "20-Learning/one.md"
    assert result.stderr == ""


def test_cli_rejects_scope_escape_without_traceback(tmp_path):
    vault = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    result = _run(
        str(vault),
        "--query",
        "needle",
        "--scope",
        "../outside",
        "--json",
    )

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert payload["error"]["details"]["param"] == "--scope"
    assert "Traceback" not in result.stderr + result.stdout


@pytest.mark.parametrize("top_k", [0, 21])
def test_cli_rejects_out_of_range_top_k(tmp_path, top_k):
    vault = _vault(tmp_path)

    result = _run(
        str(vault),
        "--query",
        "needle",
        "--top-k",
        str(top_k),
        "--json",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "invalid-top-k"
