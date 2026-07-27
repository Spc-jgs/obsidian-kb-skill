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
        '---\ndate: "2026-07-14"\ntype: web-clip\n'
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
        "TODO待确认",
        "待补充作者",
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


@pytest.mark.parametrize("author", ["Todor Zhivkov", "Nulla Rossi", "Jane TODO Smith"])
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
