"""Tests for the reusable Obsidian vault auditor."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.audit_vault import (
    _frontmatter,
    audit_note,
    audit_note_text,
    audit_vault,
    build_link_index,
)


@pytest.mark.parametrize(
    ("source", "expected_error"),
    [
        (
            '---\na: one\nb: "broken: "value""\n---\n# Body\n',
            "while parsing a block mapping",
        ),
        (
            "---\ntype: insight-note\n# Body\n",
            "frontmatter opening fence has no closing fence",
        ),
        (
            "---\n- one\n- two\n---\n# Body\n",
            "frontmatter must be a YAML mapping",
        ),
    ],
)
def test_frontmatter_adapter_preserves_legacy_error_messages(
    source: str, expected_error: str
):
    assert _frontmatter(source) == (None, expected_error)


def codes(vault: Path) -> set[str]:
    return {finding.code for finding in audit_vault(vault)}


def configure_folder_index(
    vault: Path,
    *,
    user_specified: bool,
    index_filename: str = "INDEX",
    graph_overwrite: bool = True,
    excluded: list[str] | None = None,
) -> None:
    obsidian = vault / ".obsidian"
    plugin = obsidian / "plugins" / "obsidian-folder-index"
    plugin.mkdir(parents=True, exist_ok=True)
    (obsidian / "community-plugins.json").write_text(
        json.dumps(["obsidian-folder-index"]), encoding="utf-8"
    )
    (plugin / "data.json").write_text(
        json.dumps(
            {
                "graphOverwrite": graph_overwrite,
                "rootIndexFile": "INDEX.md",
                "indexFileUserSpecified": user_specified,
                "indexFilename": index_filename,
                "excludeFolders": excluded or [],
                "excludePatterns": [],
            }
        ),
        encoding="utf-8",
    )


def make_index(path: Path, note_type: str = "folder-index") -> None:
    path.write_text(
        f"---\ntype: {note_type}\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )


def write_note(path: Path) -> None:
    path.write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Note\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "rendered",
    [
        '---\ndate: "2026-07-14"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Valid\n\nActual content.\n",
        "# Missing metadata\n",
        '---\ndate: "2026-07-14"\ntype: insight-note\n'
        "tags: [Bad_Tag]\nrelated: [not-a-link]\n---\n"
        "# Invalid\n\n{{date}} [[No Such Note]]\n```\n",
        '---\ndate: "2026-07-14"\ntype: web-clip\n'
        "tags: [web-clip]\nsource: ''\nauthor: ''\npublished: ''\n---\n"
        "# Empty\n\n## Summary\n",
    ],
)
def test_audit_note_text_matches_written_note(tmp_path, rendered):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Templates").mkdir()
    candidate = tmp_path / "Candidate.md"

    prewrite = audit_note_text(tmp_path, candidate, rendered)
    candidate.write_text(rendered, encoding="utf-8")
    postwrite = audit_note(tmp_path, candidate)

    assert prewrite == postwrite


@pytest.mark.parametrize(
    "instruction",
    [
        "用 2–4 句话区分原文观点与自己的推论，不机械复述。",
        "说明原文解决什么问题、需要哪些版本和环境。",
        "Explain the problem, required versions, environment, and prior knowledge.",
        "State success criteria, verification, common failures, constraints, trade-offs, and open questions.",
        "Link only to existing Vault notes with a clear relationship.",
    ],
)
def test_reports_residual_template_instruction_comments(tmp_path, instruction):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Templates").mkdir()
    rendered = (
        '---\ndate: "2026-07-28"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Candidate\n\n"
        f"<!-- {instruction} -->\n\nActual content.\n"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Candidate.md", rendered)

    assert any(
        finding.code == "residual-template-instruction"
        and finding.path == "Candidate.md"
        for finding in findings
    )


@pytest.mark.parametrize(
    "example",
    [
        (
            "```markdown\n"
            "<!-- 说明原文解决什么问题、需要哪些版本和环境。 -->\n"
            "```\n"
        ),
        (
            "~~~markdown\n"
            "<!-- 说明原文解决什么问题、需要哪些版本和环境。 -->\n"
            "~~~\n"
        ),
        (
            "````markdown\n"
            "```markdown\n"
            "<!-- 说明原文解决什么问题、需要哪些版本和环境。 -->\n"
            "```\n"
            "````\n"
        ),
    ],
)
def test_allows_ordinary_html_comments_and_fenced_template_examples(
    tmp_path, example
):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Templates").mkdir()
    rendered = (
        '---\ndate: "2026-07-28"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Candidate\n\n"
        "<!-- diagram anchor: keep this comment -->\n\n"
        f"{example}"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Candidate.md", rendered)

    assert "residual-template-instruction" not in {
        finding.code for finding in findings
    }


def test_ignores_template_instruction_comments_inside_templates(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    template = templates / "Learning Note.md"
    template.write_text(
        '---\ndate: "{{date}}"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Template\n\n"
        "<!-- 说明原文解决什么问题、需要哪些版本和环境。 -->\n",
        encoding="utf-8",
    )

    assert "residual-template-instruction" not in codes(tmp_path)


def test_audit_note_text_checks_required_template_heading_order(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Learning Note.md").write_text(
        '---\ntype: learning-note\ntags: [learning]\n---\n'
        "# Template\n\n## First\n\n## Second\n",
        encoding="utf-8",
    )
    rendered = (
        '---\ndate: "2026-07-14"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "# Candidate\n\n## Second\nContent.\n\n## First\nMore.\n"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Candidate.md", rendered)

    assert [finding.code for finding in findings].count("missing-template-heading") == 1
    finding = next(
        finding for finding in findings if finding.code == "missing-template-heading"
    )
    assert "expected headings: First -> Second" in finding.message
    assert "actual headings: Second -> First" in finding.message
    assert "first mismatch: Second" in finding.message


def test_audit_vault_checks_versioned_deep_capture_heading_order(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Web Clip.md").write_text(
        '---\ntype: web-clip\ntags: [web-clip]\n---\n'
        "# Template\n\n"
        "## Source and Conclusion\n\n"
        "## Problem, Prerequisites, and Boundaries\n\n"
        "## Core Knowledge and Rationale\n\n"
        "## Procedure and Worked Example\n\n"
        "## Verification, Risks, and Limitations\n\n"
        "## Interpretation and Insights\n\n"
        "## Related Notes\n",
        encoding="utf-8",
    )
    (tmp_path / "Candidate.md").write_text(
        # Dated after the deep-capture contract shipped, so the historical
        # exemption does not apply and the ordering rule is still enforced.
        '---\ndate: "2026-08-01"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n"
        "## Source and Conclusion\n\nConclusion.\n\n"
        "## Problem, Prerequisites, and Boundaries\n\nBoundaries.\n\n"
        "## Procedure and Worked Example\n\nProcedure appears too early.\n\n"
        "## Core Knowledge and Rationale\n\nRationale.\n\n"
        "## Verification, Risks, and Limitations\n\nVerification.\n\n"
        "## Interpretation and Insights\n\nInsights.\n\n"
        "## Related Notes\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert any(
        finding.code == "missing-deep-capture-heading"
        and finding.path == "Candidate.md"
        for finding in findings
    )


def test_full_audit_uses_versioned_deep_capture_baseline_with_shallow_template(
    tmp_path,
):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Web Clip.md").write_text(
        '---\ntype: web-clip\ntags: [web-clip]\n---\n'
        "# Template\n\n## Source\n\n## Summary\n",
        encoding="utf-8",
    )
    (tmp_path / "Candidate.md").write_text(
        '---\ndate: "2026-07-27"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n## Source\n\nLink.\n\n## Summary\n\nShallow summary.\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert any(
        finding.code == "missing-deep-capture-heading"
        and finding.path == "Candidate.md"
        for finding in findings
    )
    assert any(
        finding.code == "outdated-deep-capture-template"
        and finding.path == "Templates/Web Clip.md"
        for finding in findings
    )
    assert not any(
        finding.code == "missing-template-heading"
        and finding.path == "Candidate.md"
        for finding in findings
    )


def test_full_audit_deep_baseline_is_independent_of_shallow_vault_template(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Web Clip.md").write_text(
        '---\ntype: web-clip\ntags: [web-clip]\n---\n'
        "# Template\n\n## Source\n\n## Summary\n",
        encoding="utf-8",
    )
    (tmp_path / "Candidate.md").write_text(
        '---\ndate: "2026-07-27"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n"
        "## 来源与结论\n\nConclusion.\n\n"
        "## 问题、前提与适用边界\n\nBoundaries.\n\n"
        "## 核心知识与原理\n\nRationale.\n\n"
        "## 具体做法与示例\n\nProcedure.\n\n"
        "## 验证、风险与限制\n\nVerification.\n\n"
        "## 理解与启发\n\nInsights.\n\n"
        "## 关联笔记\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert not any(
        finding.code in {"missing-deep-capture-heading", "missing-template-heading"}
        and finding.path == "Candidate.md"
        for finding in findings
    )
    assert any(
        finding.code == "outdated-deep-capture-template"
        and finding.path == "Templates/Web Clip.md"
        for finding in findings
    )


def test_full_audit_accepts_optional_atx_closing_markers(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    headings = (
        "Source and Conclusion",
        "Problem, Prerequisites, and Boundaries",
        "Core Knowledge and Rationale",
        "Procedure and Worked Example",
        "Verification, Risks, and Limitations",
        "Interpretation and Insights",
        "Related Notes",
    )
    body = "\n\n".join(f"## {heading} ##\n\nContent." for heading in headings)
    (templates / "Web Clip.md").write_text(
        '---\ntype: web-clip\ntags: [web-clip]\n---\n# Template\n\n' + body + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Candidate.md").write_text(
        '---\ndate: "2026-07-27"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n"
        + body
        + "\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert not any(
        finding.code
        in {"missing-deep-capture-heading", "outdated-deep-capture-template"}
        for finding in findings
    )


def test_full_audit_deep_baseline_does_not_require_a_vault_template(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Candidate.md").write_text(
        '---\ndate: "2026-07-27"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n## Summary\n\nShallow summary.\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert any(
        finding.code == "missing-deep-capture-heading"
        and finding.path == "Candidate.md"
        for finding in findings
    )


def test_note_level_audit_still_respects_a_custom_web_clip_template(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Web Clip.md").write_text(
        '---\ntype: web-clip\ntags: [web-clip]\n---\n'
        "# Template\n\n## Custom Evidence\n\n## Custom Action\n",
        encoding="utf-8",
    )
    rendered = (
        '---\ndate: "2026-07-27"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n'
        "# Candidate\n\n## Custom Evidence\n\nEvidence.\n\n"
        "## Custom Action\n\nAction.\n"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Candidate.md", rendered)

    assert "missing-template-heading" not in [finding.code for finding in findings]
    assert "missing-deep-capture-heading" not in [
        finding.code for finding in findings
    ]


def test_required_template_headings_ignore_frontmatter_and_fenced_examples(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Learning Note.md").write_text(
        "---\n## Internal note\ntype: learning-note\ntags: [learning]\n---\n"
        "# Template\n\n## First\n\n```markdown\n## Example\n```\n\n## Second\n",
        encoding="utf-8",
    )
    rendered = (
        '---\ndate: "2026-07-14"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "# Candidate\n\n## First\nContent.\n\n## Second\nMore.\n"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Candidate.md", rendered)

    assert "missing-template-heading" not in [finding.code for finding in findings]


def test_reports_missing_required_frontmatter(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text("# Note\n", encoding="utf-8")

    assert {
        "missing-frontmatter",
        "missing-date",
        "missing-type",
        "missing-tags",
    } <= codes(tmp_path)


def test_accepts_folder_index_without_date(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )

    assert codes(tmp_path) == set()


def test_ignores_hidden_agent_metadata_dirs(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    # Agent working memory without frontmatter must not be flagged.
    (tmp_path / ".workbuddy" / "memory").mkdir(parents=True)
    (tmp_path / ".workbuddy" / "memory" / "2026-07-09.md").write_text(
        "# Memory\nNo frontmatter here.\n", encoding="utf-8"
    )
    # Any other hidden tool-metadata dir is skipped too (general rule).
    (tmp_path / ".claude" / "notes").mkdir(parents=True)
    (tmp_path / ".claude" / "notes" / "foo.md").write_text(
        "No frontmatter either.\n", encoding="utf-8"
    )
    # A real note at the vault root is still audited.
    (tmp_path / "Real.md").write_text("# Real\n", encoding="utf-8")

    findings = audit_vault(tmp_path)
    assert not any(".workbuddy" in f.path for f in findings)
    assert not any(".claude" in f.path for f in findings)
    # Sanity: a real note without frontmatter is still caught.
    assert any(
        f.code == "missing-frontmatter" and f.path == "Real.md" for f in findings
    )


def test_ignores_top_level_hidden_dir_like_uploads(tmp_path):
    # A top-level hidden directory (e.g. Obsidian's ".uploads") sitting directly
    # under the vault root must be skipped as a whole -- including the
    # missing-folder-index check that Folder Index would otherwise raise.
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "community-plugins.json").write_text(
        '["obsidian-folder-index"]', encoding="utf-8"
    )
    (tmp_path / ".uploads").mkdir()
    (tmp_path / ".uploads" / "staged.md").write_text(
        "No frontmatter, but in a hidden dir.\n", encoding="utf-8"
    )
    (tmp_path / "Real.md").write_text("# Real\n", encoding="utf-8")

    findings = audit_vault(tmp_path)
    assert not any(".uploads" in f.path for f in findings)
    # Sanity: a real note without frontmatter is still caught.
    assert any(
        f.code == "missing-frontmatter" and f.path == "Real.md" for f in findings
    )


def test_reports_missing_folder_index_content_block(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n# Notes\n",
        encoding="utf-8",
    )

    assert "missing-folder-index-content" in codes(tmp_path)


def test_reports_duplicate_folder_index_content_blocks(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n"
        "## Manual navigation\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )

    assert "duplicate-folder-index-content" in codes(tmp_path)


def test_reports_unclosed_fence_and_broken_wikilink(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n[[Missing]]\n```dataview\nLIST\n",
        encoding="utf-8",
    )

    assert {"unclosed-fence", "broken-wikilink"} <= codes(tmp_path)


def test_reports_duplicate_index_owners(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    folder = tmp_path / "Topic"
    folder.mkdir()
    for name in ("INDEX.md", "Topic.md"):
        (folder / name).write_text(
            "---\ntype: folder-index\ntags: [moc]\n---\n"
            "```folder-index-content\n```\n",
            encoding="utf-8",
        )

    assert "duplicate-folder-index" in codes(tmp_path)


def test_reports_ambiguous_filename_only_wikilink(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    for folder_name in ("A", "B"):
        folder = tmp_path / folder_name
        folder.mkdir()
        (folder / "INDEX.md").write_text(
            "---\ntype: folder-index\ntags: [moc]\n---\n"
            "```folder-index-content\n```\n",
            encoding="utf-8",
        )
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: daily-note\n'
        "tags: [daily]\n---\n[[INDEX]]\n",
        encoding="utf-8",
    )

    assert "ambiguous-wikilink" in codes(tmp_path)


def test_resolves_path_link_alias_heading_and_attachment(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    topic = tmp_path / "Topic"
    topic.mkdir()
    (topic / "Existing.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Existing\n",
        encoding="utf-8",
    )
    attachments = tmp_path / "Attachments"
    attachments.mkdir()
    (attachments / "image.png").write_bytes(b"png")
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: daily-note\n'
        "tags: [daily]\n---\n"
        "[[Topic/Existing#Existing|Related]]\n![[image.png]]\n",
        encoding="utf-8",
    )

    assert "broken-wikilink" not in codes(tmp_path)
    assert "ambiguous-wikilink" not in codes(tmp_path)


def test_ignores_example_links_in_repository_documentation(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "README.md").write_text(
        "Use `[[Missing]]` as an example.\n",
        encoding="utf-8",
    )

    assert codes(tmp_path) == set()


def test_ignores_wikilinks_inside_inline_and_fenced_code(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "Use `[[Inline Example]]`.\n"
        "```markdown\n[[Fenced Example]]\n```\n",
        encoding="utf-8",
    )

    assert "broken-wikilink" not in codes(tmp_path)


def test_reports_invalid_and_excessive_tags(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning, Bad_Tag, three, four, five, six]\n---\n",
        encoding="utf-8",
    )

    assert {"invalid-tag", "too-many-tags"} <= codes(tmp_path)


def test_reports_graph_incompatible_uniform_custom_index_name(tmp_path):
    configure_folder_index(tmp_path, user_specified=True, index_filename="INDEX")
    make_index(tmp_path / "INDEX.md", note_type="moc")
    topic = tmp_path / "Topic"
    topic.mkdir()
    make_index(topic / "INDEX.md")

    assert "graph-incompatible-index-config" in codes(tmp_path)


def test_accepts_native_folder_named_graph_chain(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    topic = tmp_path / "Topic"
    topic.mkdir()
    make_index(topic / "Topic.md")
    write_note(topic / "2026-07-08 Note.md")

    assert not {
        "graph-incompatible-index-config",
        "missing-folder-index",
        "misnamed-folder-index",
        "broken-folder-graph-chain",
    } & codes(tmp_path)


def test_reports_missing_and_misnamed_native_folder_indexes(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    (tmp_path / "Missing").mkdir()
    legacy = tmp_path / "Legacy"
    legacy.mkdir()
    make_index(legacy / "INDEX.md")

    assert {"missing-folder-index", "misnamed-folder-index"} <= codes(tmp_path)


def test_excluded_folder_does_not_require_native_index(tmp_path):
    configure_folder_index(tmp_path, user_specified=False, excluded=["Templates"])
    make_index(tmp_path / "INDEX.md", note_type="moc")
    (tmp_path / "Templates").mkdir()

    assert "missing-folder-index" not in codes(tmp_path)


def test_reports_unresolved_template_placeholder(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "Leftover {{date}} in the body.\n",
        encoding="utf-8",
    )

    assert "unresolved-template-placeholder" in codes(tmp_path)


def test_ignores_placeholders_in_templates(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Daily Note.md").write_text(
        '---\ndate: "{{date}}"\ntype: daily-note\n'
        "tags: [daily]\n---\n# {{date}}\n\nPlan for {{date}}.\n",
        encoding="utf-8",
    )

    assert "unresolved-template-placeholder" not in codes(tmp_path)


def test_reports_invalid_related_entry(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        'tags: [learning]\nrelated: ["Just a title"]\n---\n# Note\n',
        encoding="utf-8",
    )

    assert "invalid-related-entry" in codes(tmp_path)


def test_reports_duplicate_related_entry(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# A\n",
        encoding="utf-8",
    )
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        'tags: [learning]\nrelated: ["[[A]]", "[[A|Alias]]"]\n---\n# Note\n',
        encoding="utf-8",
    )

    assert "duplicate-related-entry" in codes(tmp_path)


def test_accepts_valid_related(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    for name in ("Existing Note.md", "Other.md"):
        (tmp_path / name).write_text(
            '---\ndate: "2026-07-07"\ntype: learning-note\n'
            "tags: [learning]\n---\n# X\n",
            encoding="utf-8",
        )
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        'tags: [learning]\n'
        'related: ["[[Existing Note|Display]]", "[[Other]]"]\n---\n# Note\n',
        encoding="utf-8",
    )

    assert "invalid-related-entry" not in codes(tmp_path)
    assert "duplicate-related-entry" not in codes(tmp_path)


def test_reports_missing_web_clip_fields(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: ""\nauthor: ""\npublished: ""\n---\n# Clip\n',
        encoding="utf-8",
    )

    assert {
        "web-clip-missing-source",
        "web-clip-missing-author",
        "web-clip-missing-published",
    } <= codes(tmp_path)


def test_accepts_complete_web_clip(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n# Clip\n',
        encoding="utf-8",
    )
    found = codes(tmp_path)
    assert "web-clip-missing-source" not in found
    assert "web-clip-missing-author" not in found
    assert "web-clip-missing-published" not in found


def test_historical_web_clip_without_capture_depth_remains_compatible(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        'author: "Jane"\npublished: "2026-01-01"\n---\n# Clip\n',
        encoding="utf-8",
    )

    assert "web-clip-invalid-capture-depth" not in codes(tmp_path)


@pytest.mark.parametrize("capture_depth", ["deep", "VERIFIED", 1])
def test_audit_reports_invalid_present_capture_depth(tmp_path, capture_depth):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        f'author: "Jane"\npublished: "2026-01-01"\n'
        f"capture_depth: {capture_depth}\n---\n# Clip\n",
        encoding="utf-8",
    )

    assert "web-clip-invalid-capture-depth" in codes(tmp_path)


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
def test_rejects_vague_web_clip_metadata_placeholders(tmp_path, placeholder):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        f'author: "{placeholder}"\npublished: "2026-01-01"\n---\n# Clip\n',
        encoding="utf-8",
    )

    assert "web-clip-missing-author" in codes(tmp_path)


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
def test_accepts_meaningful_metadata_containing_placeholder_substrings(
    tmp_path, author
):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        f'author: "{author}"\npublished: "2026-01-01"\n---\n# Clip\n',
        encoding="utf-8",
    )

    assert "web-clip-missing-author" not in codes(tmp_path)


def test_accepts_explicit_web_clip_source_absence_markers(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: "https://example.com/a"\n'
        'author: "原文未署名"\npublished: "原文未标明"\n---\n# Clip\n',
        encoding="utf-8",
    )

    found = codes(tmp_path)
    assert "web-clip-missing-author" not in found
    assert "web-clip-missing-published" not in found


def test_ignores_web_clip_fields_for_other_types(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Note\n",
        encoding="utf-8",
    )

    assert "web-clip-missing-source" not in codes(tmp_path)


def test_reports_empty_template_note(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "# Title\n\n## Summary\n\n## Key Takeaways\n",
        encoding="utf-8",
    )

    assert "empty-template-note" in codes(tmp_path)


def test_accepts_filled_note(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n"
        "# Title\n\n## Summary\nKey insight here.\n",
        encoding="utf-8",
    )

    assert "empty-template-note" not in codes(tmp_path)


def test_ignores_note_without_headings(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\nsome prose without headings\n",
        encoding="utf-8",
    )

    assert "empty-template-note" not in codes(tmp_path)


def test_reports_near_duplicate_tags(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    for i, tag in enumerate(("ai-agent", "ai-agents", "ai_agent")):
        (tmp_path / f"Note{i}.md").write_text(
            f'---\ndate: "2026-07-0{i + 1}"\ntype: learning-note\n'
            f"tags: [{tag}]\n---\n# N\n",
            encoding="utf-8",
        )

    assert "near-duplicate-tags" in codes(tmp_path)


def test_reports_separator_only_tag_duplicates(tmp_path):
    """yaml-standards.md calls `frontend` and `front_end` one tag; so must the audit.

    Folding only case and underscores left `spring-boot` and `springboot` in
    separate buckets, so the duplicate the rule names went unreported.
    """
    (tmp_path / ".obsidian").mkdir()
    for i, tag in enumerate(("spring-boot", "springboot", "front_end", "frontend")):
        (tmp_path / f"Note{i}.md").write_text(
            f'---\ndate: "2026-07-0{i + 1}"\ntype: learning-note\n'
            f"tags: [{tag}]\n---\n# N\n",
            encoding="utf-8",
        )

    messages = [
        f.message
        for f in audit_vault(tmp_path)
        if f.code == "near-duplicate-tags"
    ]
    assert any("spring-boot" in m and "springboot" in m for m in messages)
    assert any("front_end" in m and "frontend" in m for m in messages)


def test_ignores_distinct_tags(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    for i, tag in enumerate(("python", "obsidian", "java")):
        (tmp_path / f"Note{i}.md").write_text(
            f'---\ndate: "2026-07-0{i + 1}"\ntype: learning-note\n'
            f"tags: [{tag}]\n---\n# N\n",
            encoding="utf-8",
        )

    assert "near-duplicate-tags" not in codes(tmp_path)


def test_ignores_lone_plural(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-01"\ntype: learning-note\n'
        "tags: [ai-agents]\n---\n# N\n",
        encoding="utf-8",
    )

    assert "near-duplicate-tags" not in codes(tmp_path)


def test_reports_duplicate_title(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Apollo Program\n",
        encoding="utf-8",
    )
    (tmp_path / "B.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Apollo Program\n",
        encoding="utf-8",
    )

    assert "duplicate-title" in codes(tmp_path)
    assert "similar-title" not in codes(tmp_path)


def test_reports_duplicate_title_from_filename_when_no_heading(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Apollo Program.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\nsome prose\n",
        encoding="utf-8",
    )
    (tmp_path / "2026-07-08 Apollo Program.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\nsome prose\n",
        encoding="utf-8",
    )

    assert "duplicate-title" in codes(tmp_path)


def test_reports_similar_title(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "A.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Apollo Launch Plan\n",
        encoding="utf-8",
    )
    (tmp_path / "B.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Apollo Launch Plan v2\n",
        encoding="utf-8",
    )

    assert "similar-title" in codes(tmp_path)
    assert "duplicate-title" not in codes(tmp_path)


def test_ignores_index_template_and_unique_titles(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n# Apollo Program\n",
        encoding="utf-8",
    )
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Insight.md").write_text(
        '---\ndate: "{{date}}"\ntype: insight-note\n'
        "tags: [insight]\n---\n# Apollo Program\n",
        encoding="utf-8",
    )
    (tmp_path / "Note.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Apollo Program\n",
        encoding="utf-8",
    )

    assert "duplicate-title" not in codes(tmp_path)
    assert "similar-title" not in codes(tmp_path)


def test_reports_orphan_note(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Lone.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Lone\nSome content.\n",
        encoding="utf-8",
    )

    assert "orphan-note" in codes(tmp_path)


def test_ignores_note_referenced_by_wikilink(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Target\nLinks back to [[Source]].\n",
        encoding="utf-8",
    )
    (tmp_path / "Source.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Source\nLinks to [[Target]].\n",
        encoding="utf-8",
    )

    assert "orphan-note" not in codes(tmp_path)


def test_related_field_counts_as_reference(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\nrelated: [\"[[Source]]\"]\n---\n# Target\nSome content.\n",
        encoding="utf-8",
    )
    (tmp_path / "Source.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\nrelated: [\"[[Target]]\"]\n---\n# Source\nSome content.\n",
        encoding="utf-8",
    )

    assert "orphan-note" not in codes(tmp_path)


def test_ignores_note_referenced_by_index(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    topic = tmp_path / "Topic"
    topic.mkdir()
    (topic / "Topic.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )
    (topic / "Child.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Child\nSome content.\n",
        encoding="utf-8",
    )

    assert "orphan-note" not in codes(tmp_path)


def _disconnected(tmp_path):
    return {
        finding.path
        for finding in audit_vault(tmp_path)
        if finding.code == "disconnected-note"
    }


def test_unreachable_note_is_only_an_orphan(tmp_path):
    """An unreachable note is an orphan, and the connectivity message would lie.

    `disconnected-note` states the note is reachable through its folder index.
    With no index in its folder that is false, and the note is already reported
    as `orphan-note`, so reporting both says two different things about one note.
    """
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Lone.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Lone\nSome content.\n",
        encoding="utf-8",
    )

    found = codes(tmp_path)
    assert "orphan-note" in found
    assert "disconnected-note" not in found


def test_link_to_own_source_archive_is_not_connectivity(tmp_path):
    """Archiving a source must not quietly clear the finding.

    `95-Sources/` is declared evidence rather than knowledge everywhere else --
    excluded from search, from note contracts, from folder-index requirements --
    so a note whose only link is to its own archive still touches nothing.
    """
    (tmp_path / ".obsidian").mkdir()
    topic = tmp_path / "Topic"
    topic.mkdir()
    (topic / "Topic.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )
    (topic / "Kafka.md").write_text(
        '---\ndate: "2026-08-01"\ntype: learning-note\n'
        'tags: [learning]\nsource_archive: "[[Kafka·原文]]"\n---\n'
        "# Kafka\n原文存档：[[Kafka·原文]]\n",
        encoding="utf-8",
    )
    archive = tmp_path / "95-Sources" / "2026-08"
    archive.mkdir(parents=True)
    (archive / "Kafka·原文.md").write_text(
        '---\ntype: source-archive\nnote: "[[Kafka]]"\n---\n原文正文。\n',
        encoding="utf-8",
    )

    assert "Topic/Kafka.md" in _disconnected(tmp_path)


def test_outbound_link_alone_is_connected(tmp_path):
    """One direction is enough. Only the intersection is reported."""
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Target\nNo links out.\n",
        encoding="utf-8",
    )
    (tmp_path / "Source.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Source\nLinks to [[Target]].\n",
        encoding="utf-8",
    )

    # Source has an outbound link and no inbound; Target the reverse.
    assert _disconnected(tmp_path) == set()


def test_reachable_through_folder_index_is_still_disconnected(tmp_path):
    """The whole point of the split: a folder index grants reachability only."""
    (tmp_path / ".obsidian").mkdir()
    topic = tmp_path / "Topic"
    topic.mkdir()
    (topic / "Topic.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )
    (topic / "Child.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Child\nSome content.\n",
        encoding="utf-8",
    )

    found = codes(tmp_path)
    assert "disconnected-note" in found
    assert "orphan-note" not in found


def test_inbound_link_through_alias_counts_as_connected(tmp_path):
    """Obsidian resolves [[alias]]; the audit must too, or #57 comes back."""
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Target.md").write_text(
        '---\ndate: "2026-07-07"\ntype: learning-note\n'
        'tags: [learning]\naliases: ["Nickname"]\n---\n# Target\nNo links out.\n',
        encoding="utf-8",
    )
    (tmp_path / "Source.md").write_text(
        '---\ndate: "2026-07-08"\ntype: learning-note\n'
        "tags: [learning]\n---\n# Source\nLinks to [[Nickname]].\n",
        encoding="utf-8",
    )

    assert "Target.md" not in _disconnected(tmp_path)


@pytest.mark.parametrize("note_type", ["daily-report", "weekly-report"])
def test_periodic_reports_are_exempt_from_connectivity(tmp_path, note_type):
    """A log that links nothing is doing its job."""
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Report.md").write_text(
        f'---\ndate: "2026-07-07"\ntype: {note_type}\n'
        "tags: [daily]\n---\n# Report\nSome content.\n",
        encoding="utf-8",
    )

    assert "disconnected-note" not in codes(tmp_path)


def test_ignores_unlinked_daily_note(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "2026-07-07 Daily.md").write_text(
        '---\ndate: "2026-07-07"\ntype: daily-note\n'
        "tags: [daily]\n---\n# Daily\nSome content.\n",
        encoding="utf-8",
    )

    assert "orphan-note" not in codes(tmp_path)


def test_accepts_conversation_digest_type(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "Digest.md").write_text(
        '---\ndate: "2026-07-07"\ntype: conversation-digest\n'
        'tags: [insight]\nsource: "WorkBuddy"\nrelated: []\n---\n'
        "# Digest\n\n## Confirmed Conclusions\n\nKey decision made.\n",
        encoding="utf-8",
    )

    codes_found = codes(tmp_path)
    assert "invalid-type" not in codes_found
    assert "missing-type" not in codes_found


def _write_digest_template(vault: Path) -> None:
    templates = vault / "Templates"
    templates.mkdir(exist_ok=True)
    (templates / "Digest Note.md").write_text(
        '---\ndate: "{{date}}"\ntype: conversation-digest\n'
        "tags: [insight]\nsource: ''\nproject: ''\nrelated: []\n---\n"
        "# Conversation\n\n"
        "## Resume Card\n\n"
        "- **Goal**:\n- **State**:\n- **Current conclusion**:\n"
        "- **Next step**:\n- **Key artifacts**:\n\n"
        "## Scope and Constraints\n\n"
        "## Decisions and Rationale\n\n"
        "## Evidence and Artifacts\n\n"
        "## Open Questions and Next Actions\n",
        encoding="utf-8",
    )


def _valid_digest() -> str:
    return (
        '---\ndate: "2026-07-29"\ntype: conversation-digest\n'
        'tags: [insight]\nsource: "Codex"\nproject: "obsidian-kb-skill"\n'
        "related: []\n---\n"
        "# Conversation context\n\n"
        "## Resume Card\n\n"
        "- **Goal**: Upgrade conversation context recovery.\n"
        "- **State**: Decided; implementation is in progress.\n"
        "- **Current conclusion**: Use a layered immutable digest.\n"
        "- **Next step**: Implement and validate the v2 contract.\n"
        "- **Key artifacts**: Design spec and focused tests.\n\n"
        "## Scope and Constraints\n\n"
        "Keep Task Memory authoritative for active task state.\n\n"
        "## Decisions and Rationale\n\n"
        "Use a short resume card plus details so scanning does not remove evidence.\n\n"
        "## Evidence and Artifacts\n\n"
        "The template, reference, preflight, and audit must agree.\n\n"
        "## Open Questions and Next Actions\n\n"
        "Run the complete regression suite after focused tests pass.\n"
    )


def test_accepts_complete_conversation_digest_v2(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)

    findings = audit_note_text(
        tmp_path,
        tmp_path / "Digest.md",
        _valid_digest(),
    )

    assert not {
        finding.code
        for finding in findings
        if finding.code.startswith("conversation-digest")
        or finding.code == "missing-conversation-digest-heading"
    }


def test_reports_outdated_conversation_digest_template_and_note(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Digest Note.md").write_text(
        '---\ntype: conversation-digest\ntags: [insight]\n---\n'
        "# Template\n\n## Context\n\n## Confirmed Conclusions\n",
        encoding="utf-8",
    )
    (tmp_path / "Digest.md").write_text(
        '---\ndate: "2026-07-29"\ntype: conversation-digest\n'
        'tags: [insight]\nsource: "Codex"\nrelated: []\n---\n'
        "# Digest\n\n## Context\n\nOld shape.\n\n"
        "## Confirmed Conclusions\n\nA conclusion.\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert any(
        finding.code == "outdated-conversation-digest-template"
        and finding.path == "Templates/Digest Note.md"
        for finding in findings
    )
    assert any(
        finding.code == "missing-conversation-digest-heading"
        and finding.path == "Digest.md"
        for finding in findings
    )


def test_reports_missing_resume_fields_and_overlong_resume_card(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)
    rendered = _valid_digest().replace(
        "- **Current conclusion**: Use a layered immutable digest.\n",
        "- **Current conclusion**:\n"
        + "".join(f"- Extra context line {index}.\n" for index in range(10)),
    )

    findings = audit_note_text(
        tmp_path,
        tmp_path / "Digest.md",
        rendered,
    )
    found_codes = {finding.code for finding in findings}

    assert "conversation-digest-missing-resume-field" in found_codes
    assert "conversation-digest-resume-card-too-long" in found_codes


def test_resume_card_field_value_may_be_inline_code(tmp_path):
    """Inline code is a legitimate field value, not an empty one.

    `_without_code_examples` stripped fenced *and* inline code before the field
    regex ran, so `- **Key artifacts**: `src/app.py`` was reported missing.
    """
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)
    digest = _valid_digest().replace(
        "- **Key artifacts**: Design spec and focused tests.",
        "- **Key artifacts**: `src/app.py`",
    )

    findings = audit_note_text(tmp_path, tmp_path / "Digest.md", digest)

    assert not [
        finding
        for finding in findings
        if finding.code == "conversation-digest-missing-resume-field"
    ]


def test_resume_card_still_reports_a_genuinely_empty_field(tmp_path):
    """Guard: the fix must not make every field look populated."""
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)
    digest = _valid_digest().replace(
        "- **Key artifacts**: Design spec and focused tests.",
        "- **Key artifacts**:",
    )

    findings = audit_note_text(tmp_path, tmp_path / "Digest.md", digest)

    assert any(
        finding.code == "conversation-digest-missing-resume-field"
        and "Key artifacts" in finding.message
        for finding in findings
    )


def test_html_commented_structure_is_not_visible_structure(tmp_path):
    """A v2 structure the reader cannot see must not satisfy the baseline."""
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)
    hidden = (
        '---\ndate: "2026-07-29"\ntype: conversation-digest\n'
        'tags: [insight]\nsource: "Codex"\nrelated: []\n---\n'
        "# Digest\n\n"
        "<!--\n"
        "## Resume Card\n\n"
        "- **Goal**: hidden\n"
        "- **State**: hidden\n"
        "- **Current conclusion**: hidden\n"
        "- **Next step**: hidden\n"
        "- **Key artifacts**: hidden\n\n"
        "## Scope and Constraints\n\n"
        "## Decisions and Rationale\n\n"
        "## Evidence and Artifacts\n\n"
        "## Open Questions and Next Actions\n"
        "-->\n\n"
        "Nothing the reader can actually see.\n"
    )

    findings = audit_note_text(tmp_path, tmp_path / "Digest.md", hidden)

    assert any(
        finding.code == "missing-conversation-digest-heading"
        for finding in findings
    ), "hidden headings must not satisfy the v2 baseline"


def test_digest_template_missing_resume_labels_is_reported(tmp_path):
    """A template that passes audit but makes every note fail preflight.

    The template contract only checked the five headings, so dropping the
    Resume Card labels was accepted here and then rejected on every note
    created from it.
    """
    (tmp_path / ".obsidian").mkdir()
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "Digest Note.md").write_text(
        '---\ndate: "{{date}}"\ntype: conversation-digest\ntags: [insight]\n---\n'
        "# Template\n\n"
        "## Resume Card\n\n"
        "- **Goal**:\n\n"
        "## Scope and Constraints\n\n"
        "## Decisions and Rationale\n\n"
        "## Evidence and Artifacts\n\n"
        "## Open Questions and Next Actions\n",
        encoding="utf-8",
    )

    findings = audit_vault(tmp_path)

    assert any(
        finding.code == "outdated-conversation-digest-template"
        and finding.path == "Templates/Digest Note.md"
        for finding in findings
    )


def test_complete_digest_template_with_all_labels_is_accepted(tmp_path):
    """Guard: the label check must not reject the shipped template shape."""
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)

    findings = audit_vault(tmp_path)

    assert not [
        finding
        for finding in findings
        if finding.code == "outdated-conversation-digest-template"
    ]


def test_fence_looking_line_inside_an_html_comment_is_not_an_open_fence(tmp_path):
    """A commented-out fence is invisible, so it cannot be unclosed."""
    (tmp_path / ".obsidian").mkdir()

    findings = audit_note_text(
        tmp_path,
        tmp_path / "Note.md",
        "---\ntitle: T\ntype: insight-note\ndate: 2026-08-02\n"
        "tags: [insight]\n---\n\n# Body\n\n"
        "<!--\n```python\nx = 1\n-->\n\nStill fine.\n",
    )

    assert not [f for f in findings if f.code == "unclosed-fence"]


def test_a_genuinely_unclosed_fence_is_still_reported(tmp_path):
    """Guard: the comment rule must not silence real unclosed fences."""
    (tmp_path / ".obsidian").mkdir()

    findings = audit_note_text(
        tmp_path,
        tmp_path / "Note.md",
        "---\ntitle: T\ntype: insight-note\ndate: 2026-08-02\n"
        "tags: [insight]\n---\n\n# Body\n\n```python\nx = 1\n",
    )

    assert [f for f in findings if f.code == "unclosed-fence"]


def _pre_contract_web_clip(date: str) -> str:
    """A finished Web Clip in the shape that predated the deep-capture contract."""
    return (
        f'---\ndate: "{date}"\ntype: web-clip\ntags: [web-clip]\n'
        'source: "https://example.com/a"\nauthor: "A"\npublished: "2026-01-01"\n'
        "---\n"
        "# Article\n\n## Summary\n\nOld shape, still a good note.\n"
    )


def test_note_predating_the_deep_capture_contract_is_not_invalid(tmp_path):
    """A later contract does not retroactively invalidate existing notes.

    The roadmap states that new templates apply to new notes and that existing
    notes "do not become invalid merely because a later template adds
    sections". The audit reported them anyway — 31 of them on the reference
    Vault, every one written before the contract shipped.
    """
    (tmp_path / ".obsidian").mkdir()

    (tmp_path / "20-Learning").mkdir()
    (tmp_path / "20-Learning" / "Old.md").write_text(
        _pre_contract_web_clip("2026-07-01"), encoding="utf-8"
    )

    findings = audit_vault(tmp_path)

    assert not [
        f for f in findings if f.code == "missing-deep-capture-heading"
    ]


def test_note_written_after_the_contract_is_still_checked(tmp_path):
    """Guard: the exemption must not disable the contract for new notes."""
    (tmp_path / ".obsidian").mkdir()

    (tmp_path / "20-Learning").mkdir()
    (tmp_path / "20-Learning" / "New.md").write_text(
        _pre_contract_web_clip("2026-08-02"), encoding="utf-8"
    )

    findings = audit_vault(tmp_path)

    assert [f for f in findings if f.code == "missing-deep-capture-heading"]


def test_note_without_a_usable_date_is_still_checked(tmp_path):
    """Guard: an undated note cannot claim the exemption."""
    (tmp_path / ".obsidian").mkdir()
    undated = _pre_contract_web_clip("2026-07-01").replace(
        'date: "2026-07-01"\n', ""
    )

    (tmp_path / "20-Learning").mkdir()
    (tmp_path / "20-Learning" / "X.md").write_text(undated, encoding="utf-8")

    findings = audit_vault(tmp_path)

    assert [f for f in findings if f.code == "missing-deep-capture-heading"]


def test_digest_predating_the_v2_contract_is_not_invalid(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    _write_digest_template(tmp_path)
    old = (
        '---\ndate: "2026-07-10"\ntype: conversation-digest\ntags: [insight]\n'
        'source: "x"\nrelated: []\n---\n'
        "# Digest\n\n## Context\n\nOld v1 shape.\n\n## Confirmed Conclusions\n\nA.\n"
    )

    (tmp_path / "Old.md").write_text(old, encoding="utf-8")

    findings = audit_vault(tmp_path)

    assert not [
        f
        for f in findings
        if f.code
        in {
            "missing-conversation-digest-heading",
            "conversation-digest-missing-resume-field",
        }
    ]


def test_template_residue_is_reported_regardless_of_age(tmp_path):
    """Guard: age exempts structure, never leftover template scaffolding."""
    (tmp_path / ".obsidian").mkdir()
    residue = _pre_contract_web_clip("2026-01-01").replace(
        "Old shape, still a good note.",
        "Body {{date}} left unresolved.",
    )

    (tmp_path / "20-Learning").mkdir()
    (tmp_path / "20-Learning" / "R.md").write_text(residue, encoding="utf-8")

    findings = audit_vault(tmp_path)

    assert [f for f in findings if f.code == "unresolved-template-placeholder"]


def _alias_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "20-Learning").mkdir()
    (vault / "20-Learning" / "2026-06-10 长标题的原始笔记.md").write_text(
        '---\ndate: "2026-06-10"\ntype: learning-note\ntags: [learning]\n'
        'aliases:\n  - "短别名"\n---\n\n# 原始笔记\n\n正文足够长，不是空模板。\n',
        encoding="utf-8",
    )
    return vault


def test_alias_link_is_not_reported_broken(tmp_path: Path):
    """Obsidian resolves `[[alias]]`; an audit that only knows filenames does not.

    `broken-wikilink` is the highest severity the audit has, so a false positive
    here is the most expensive kind: it sends the user to repair a link that
    already works.
    """
    vault = _alias_vault(tmp_path)
    (vault / "20-Learning" / "2026-06-11 引用方.md").write_text(
        '---\ndate: "2026-06-11"\ntype: learning-note\ntags: [learning]\n---\n\n'
        "# 引用方\n\n见 [[短别名]]。\n",
        encoding="utf-8",
    )

    codes = {finding.code for finding in audit_vault(vault)}

    assert "broken-wikilink" not in codes


def test_alias_link_counts_as_an_inbound_reference(tmp_path: Path):
    """The same gap made the linked note look like an orphan."""
    vault = _alias_vault(tmp_path)
    (vault / "20-Learning" / "2026-06-11 引用方.md").write_text(
        '---\ndate: "2026-06-11"\ntype: learning-note\ntags: [learning]\n---\n\n'
        "# 引用方\n\n见 [[短别名]]。\n",
        encoding="utf-8",
    )

    orphans = {
        finding.path
        for finding in audit_vault(vault)
        if finding.code == "orphan-note"
    }

    assert "20-Learning/2026-06-10 长标题的原始笔记.md" not in orphans


def test_an_alias_nobody_declared_is_still_broken(tmp_path: Path):
    """The fix must not turn every unresolved link into a pass."""
    vault = _alias_vault(tmp_path)
    (vault / "20-Learning" / "2026-06-11 引用方.md").write_text(
        '---\ndate: "2026-06-11"\ntype: learning-note\ntags: [learning]\n---\n\n'
        "# 引用方\n\n见 [[根本不存在的别名]]。\n",
        encoding="utf-8",
    )

    codes = {finding.code for finding in audit_vault(vault)}

    assert "broken-wikilink" in codes


def test_alias_map_is_built_only_when_a_link_fails_to_resolve(tmp_path: Path):
    """Reading every note's frontmatter is a whole-Vault pass.

    The per-note audit runs on every write, so a Vault whose links all resolve
    by filename must not pay for the alias map at all.
    """
    vault = _alias_vault(tmp_path)
    index = build_link_index(
        sorted((vault / "20-Learning").glob("*.md"))
    )

    assert index.matches("2026-06-10 长标题的原始笔记")
    assert index._aliases is None, "resolved by filename; the alias pass was wasted"

    assert index.matches("短别名")
    assert index._aliases is not None


def test_a_dot_in_the_title_does_not_break_link_resolution(tmp_path: Path):
    """`Path("Qwen3.6-27B").suffix` is `.6-27B` as far as pathlib is concerned.

    Gating the stem lookup on "the target looks extensionless" therefore skipped
    every note whose title contains a dot, and reported a link to a file that
    exists as the highest-severity finding the audit has. Found on a real Vault:
    four of its thirty-three `broken-wikilink` defects were this.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "20-Learning").mkdir()
    (vault / "20-Learning" / "2026-07-29 本地部署-Ollama+Qwen3.6-27B实战.md").write_text(
        '---\ndate: "2026-07-29"\ntype: learning-note\ntags: [learning]\n---\n\n'
        "# 部署\n\n正文足够长，不是空模板。\n",
        encoding="utf-8",
    )
    (vault / "20-Learning" / "2026-07-30 引用方.md").write_text(
        '---\ndate: "2026-07-30"\ntype: learning-note\ntags: [learning]\n---\n\n'
        "# 引用方\n\n见 [[2026-07-29 本地部署-Ollama+Qwen3.6-27B实战]]。\n",
        encoding="utf-8",
    )

    broken = [
        finding
        for finding in audit_vault(vault)
        if finding.code == "broken-wikilink"
    ]

    assert not broken, broken


def test_source_archives_are_not_held_to_note_contracts(tmp_path):
    """An archive is someone else's writing kept as evidence, not a note.

    Holding it to note contracts would flood the findings list with violations
    that describe the source's author rather than anything the user can fix.
    """
    (tmp_path / ".obsidian").mkdir()
    archive = tmp_path / "95-Sources" / "2026-08"
    archive.mkdir(parents=True)
    (archive / "violin.md").write_text(
        "---\ntype: source-archive\nsource: https://example.com/a\n---\n"
        "### 原文的三级标题\n\n{{这看起来像占位符}}\n\n```zig\nunclosed\n",
        encoding="utf-8",
    )
    (tmp_path / "20-Learning").mkdir()
    (tmp_path / "20-Learning" / "note.md").write_text(
        "# Ordinary\n", encoding="utf-8"
    )

    findings = audit_vault(tmp_path)

    assert not [f for f in findings if f.path.startswith("95-Sources/")]
    # The ordinary note still gets its contract enforced.
    assert any(f.path == "20-Learning/note.md" for f in findings)


def test_a_note_can_link_to_its_source_archive(tmp_path):
    """The link must resolve, and must break loudly if the archive is deleted."""
    (tmp_path / ".obsidian").mkdir()
    archive = tmp_path / "95-Sources" / "2026-08"
    archive.mkdir(parents=True)
    (archive / "violin-source.md").write_text(
        "---\ntype: source-archive\n---\n原文\n", encoding="utf-8"
    )
    (tmp_path / "20-Learning").mkdir()
    note = tmp_path / "20-Learning" / "violin.md"
    note.write_text(
        '---\ndate: "2026-08-06"\ntype: learning-note\ntags: [learning]\n---\n'
        "# Violin\n\n原文存档：[[violin-source]]\n",
        encoding="utf-8",
    )

    assert "broken-wikilink" not in codes(tmp_path)

    (archive / "violin-source.md").unlink()

    assert "broken-wikilink" in codes(tmp_path)
