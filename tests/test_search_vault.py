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
        # The helper forces UTF-8 on stdout, so the reader must use it too.
        # Windows would otherwise decode with the locale codec, where several
        # bytes of a CJK note title are simply undefined.
        encoding="utf-8",
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
    assert payload["scanned"] == {
        "files": 2, "indexed": 1, "skipped": 1, "excluded": 0,
    }
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


def test_scaffolding_files_are_not_indexed_as_knowledge(tmp_path: Path):
    """The write Skill already declares these are not notes; retrieval must agree.

    A Vault README is long and mentions every subject, which makes it a lexical
    magnet: on the reference Vault it took a top-five slot in half of twelve
    realistic questions, pushing real notes out.
    """
    vault = _vault(tmp_path)
    (vault / "README.md").write_text(
        "# Vault\n\nSpring AI MCP knowledge base overview.\n", encoding="utf-8"
    )
    (vault / "AGENTS.md").write_text(
        "# Governance\n\nSpring AI MCP routing rules.\n", encoding="utf-8"
    )
    (vault / "20-Learning" / "AGENTS.md").write_text(
        "# Nested governance\n\nSpring AI MCP.\n", encoding="utf-8"
    )
    _note(
        vault / "20-Learning" / "note.md",
        title="Spring AI MCP",
        body="Spring AI MCP integration notes.",
    )

    result = search_vault(vault, "Spring AI MCP", top_k=5)

    assert [item["path"] for item in result["results"]] == ["20-Learning/note.md"]
    assert result["scanned"]["excluded"] == 3
    assert result["scanned"]["indexed"] == 1
    # Scaffolding is not malformed; it must not be reported as a problem note.
    assert result["issues"] == []


def test_index_notes_stay_searchable(tmp_path: Path):
    """Navigational notes are knowledge: "how is this Vault organised" wants them."""
    vault = _vault(tmp_path)
    (vault / "INDEX.md").write_text(
        "---\ntype: folder-index\n---\n# Index\n\nVault organisation map.\n",
        encoding="utf-8",
    )

    result = search_vault(vault, "Vault organisation map", top_k=5)

    assert [item["path"] for item in result["results"]] == ["INDEX.md"]


def _dated(path: Path, *, title: str, note_type: str, date: str, tags: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: {note_type}\ndate: {date}\n"
        f"tags: {json.dumps(tags, ensure_ascii=False)}\n---\n# {title}\n\n"
        "共享正文关键词 needle\n",
        encoding="utf-8",
    )


def _filtered(tmp_path: Path):
    vault = _vault(tmp_path)
    _dated(vault / "15-Daily" / "d1.md", title="七月一日",
           note_type="daily-note", date="2026-07-01", tags=["work"])
    _dated(vault / "15-Daily" / "d2.md", title="七月二十日",
           note_type="daily-note", date="2026-07-20", tags=["work", "spring-boot"])
    _dated(vault / "20-Learning" / "l1.md", title="六月学习",
           note_type="learning-note", date="2026-06-15", tags=["llm"])
    _dated(vault / "20-Learning" / "l2.md", title="七月学习",
           note_type="learning-note", date="2026-07-25", tags=["llm"])
    (vault / "20-Learning" / "undated.md").write_text(
        "---\ntype: learning-note\ntags: [llm]\n---\n# 无日期\n\nneedle\n",
        encoding="utf-8",
    )
    return vault


def test_type_filter_removes_other_kinds_before_ranking(tmp_path: Path):
    vault = _filtered(tmp_path)

    payload = search_vault(vault, "needle", top_k=10, types=["daily-note"])

    assert {r["path"] for r in payload["results"]} == {
        "15-Daily/d1.md", "15-Daily/d2.md",
    }
    assert payload["filters"]["applied"] == {"type": ["daily-note"]}
    assert payload["filters"]["matched"] == 2
    assert payload["filters"]["excluded"]["type"] == 3


def test_date_range_is_inclusive_and_counts_undated_notes_apart(tmp_path: Path):
    """A note with no date is a governance problem, not a range mismatch."""
    vault = _filtered(tmp_path)

    payload = search_vault(
        vault, "needle", top_k=10, after="2026-07-01", before="2026-07-20"
    )

    assert {r["path"] for r in payload["results"]} == {
        "15-Daily/d1.md", "15-Daily/d2.md",
    }
    excluded = payload["filters"]["excluded"]
    assert excluded["missing-date"] == 1
    assert excluded["after"] + excluded["before"] == 2


def test_tag_filter_ignores_separator_and_plural_spelling(tmp_path: Path):
    """`--tag springboot` must find the Vault's `spring-boot`."""
    vault = _filtered(tmp_path)

    payload = search_vault(vault, "needle", top_k=10, tags=["springboot"])

    assert [r["path"] for r in payload["results"]] == ["15-Daily/d2.md"]


def test_repeats_within_a_dimension_are_or_across_dimensions_and(tmp_path: Path):
    vault = _filtered(tmp_path)

    either = search_vault(vault, "needle", top_k=10, tags=["work", "llm"])
    both = search_vault(
        vault, "needle", top_k=10, tags=["llm"], types=["learning-note"],
        after="2026-07-01",
    )

    assert len(either["results"]) == 5
    assert [r["path"] for r in both["results"]] == ["20-Learning/l2.md"]


def test_a_filter_that_matches_nothing_explains_which_one(tmp_path: Path):
    """An empty result must never be mistaken for an empty Vault."""
    vault = _filtered(tmp_path)

    payload = search_vault(vault, "needle", top_k=10, types=["person-note"])

    assert payload["results"] == []
    assert payload["filters"]["candidates"] == 5
    assert payload["filters"]["matched"] == 0
    assert payload["filters"]["excluded"]["type"] == 5


def test_unfiltered_search_reports_no_filter_block(tmp_path: Path):
    vault = _filtered(tmp_path)

    assert "filters" not in search_vault(vault, "needle", top_k=10)


def test_results_carry_the_metadata_they_were_filtered_on(tmp_path: Path):
    vault = _filtered(tmp_path)

    payload = search_vault(vault, "needle", top_k=10, types=["daily-note"])

    assert payload["results"][0]["type"] == "daily-note"
    assert payload["results"][0]["date"] in {"2026-07-01", "2026-07-20"}


def test_cli_filters_narrow_the_result_set(tmp_path: Path):
    vault = _filtered(tmp_path)

    result = _run(
        str(vault), "--query", "needle", "--json",
        "--type", "daily-note", "--after", "2026-07-10",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [r["path"] for r in payload["results"]] == ["15-Daily/d2.md"]
    assert payload["filters"]["applied"]["after"] == "2026-07-10"


@pytest.mark.parametrize(
    "args, code",
    [
        (["--after", "07/01/2026"], "invalid-date"),
        (["--before", "2026-13-01"], "invalid-date"),
        (["--after", "2026-08-01", "--before", "2026-07-01"], "invalid-date-range"),
        (["--type", "not-a-type"], "invalid-type"),
        (["--tag", "   "], "invalid-tag"),
    ],
)
def test_cli_refuses_malformed_filters(tmp_path: Path, args: list[str], code: str):
    """A filter the helper cannot honour is refused, never silently ignored."""
    vault = _filtered(tmp_path)

    result = _run(str(vault), "--query", "needle", "--json", *args)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["error"]["code"] == code
    assert "results" not in payload


# The twelve questions that measured the problem on the reference Vault. Each
# one has a real answer among the notes below; the scaffolding files exist only
# to compete with them, which on the real Vault they won 11 of 60 top-five slots
# doing. Committed as a regression fixture so that cannot come back silently.
REFERENCE_QUERIES = (
    "我对知识库沉淀有什么洞察", "这个知识库怎么组织的", "obsidian skill 怎么用",
    "我最近在学什么", "AI Agent 的记忆机制", "项目复盘", "面试准备", "写作方法",
    "python 学习路线", "团队协作", "职场成长", "docker 部署",
)
_SUBJECTS = (
    ("30-Insights/insight.md", "知识库沉淀的洞察", "沉淀 洞察 知识库 组织"),
    ("20-Learning/skill.md", "Obsidian Skill 使用指南", "obsidian skill 使用 组织"),
    ("20-Learning/memory.md", "AI Agent 的记忆机制", "agent 记忆机制 最近 学习"),
    ("40-Projects/review.md", "项目复盘方法", "项目 复盘 团队协作 职场成长"),
    ("20-Learning/python.md", "Python 学习路线", "python 学习路线 写作方法"),
    ("20-Learning/docker.md", "Docker 部署实践", "docker 部署 面试准备"),
)


def test_scaffolding_does_not_crowd_out_real_notes(tmp_path: Path):
    vault = _vault(tmp_path)
    (vault / "40-Projects").mkdir(exist_ok=True)
    # A Vault README mentions every subject, which is exactly why it used to win.
    every_subject = " ".join(REFERENCE_QUERIES)
    for name in ("README.md", "AGENTS.md", "CLAUDE.md"):
        (vault / name).write_text(f"# {name}\n\n{every_subject}\n", encoding="utf-8")
    for relative, title, body in _SUBJECTS:
        _note(vault / relative, title=title, body=body)

    slots = 0
    scaffolding = 0
    for query in REFERENCE_QUERIES:
        for result in search_vault(vault, query, top_k=5)["results"]:
            slots += 1
            if result["path"] in {"README.md", "AGENTS.md", "CLAUDE.md"}:
                scaffolding += 1

    assert slots > 0
    assert scaffolding == 0


def test_archives_are_invisible_by_default_but_reachable_with_scope(tmp_path: Path):
    """Both halves of the requirement, pinned together so they cannot drift.

    Default exclusion comes from the walk applying the ignored set to child
    directories and never to the scope root — inherited behaviour this feature
    now depends on, so it is asserted rather than assumed.
    """
    vault = _vault(tmp_path)
    archive = vault / "95-Sources" / "2026-08"
    archive.mkdir(parents=True)
    (archive / "source.md").write_text(
        "---\ntype: source-archive\n---\n# 原文\n\nEventBus 回调 needle\n",
        encoding="utf-8",
    )
    _note(vault / "20-Learning" / "digest.md", title="摘要", body="unrelated text")

    everywhere = search_vault(vault, "EventBus 回调 needle", top_k=5)
    scoped = search_vault(
        vault, "EventBus 回调 needle", top_k=5, scope=vault / "95-Sources"
    )

    assert [r["path"] for r in everywhere["results"]] == []
    assert [r["path"] for r in scoped["results"]] == ["95-Sources/2026-08/source.md"]
