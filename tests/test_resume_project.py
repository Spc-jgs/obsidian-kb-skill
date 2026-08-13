"""Tests for the read-only project resume pack (scripts/resume_project.py)."""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from obsidian_kb_skill.scripts import resume_project


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "40-Projects").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def write_note(
    path: Path,
    note_type: str,
    *,
    date: str = "2026-08-01",
    status: str | None = None,
    body: str = "body\n",
    extra: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_line = f"status: {status}\n" if status else ""
    path.write_text(
        f"---\ntype: {note_type}\ndate: {date}\ntags: [project]\n"
        f"{status_line}{extra}---\n\n{body}",
        encoding="utf-8",
    )


AS_OF = datetime.date(2026, 8, 12)


def test_subordinate_output_in_the_instance_directory_is_a_source(tmp_path):
    """The entity folder makes membership readable from the layout itself.

    Every other route to "which notes belong to this project" depends on a
    frontmatter field or a wikilink being maintained. A note sitting in the
    project's own directory needs neither, so it is the most reliable source
    the pack has — and it did not exist before #95.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")
    write_note(instance / "Digest.md", "conversation-digest", date="2026-08-05")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert payload["project"]["path"] == "40-Projects/etianqu/Project.md"
    assert [source["path"] for source in payload["sources"]] == [
        "40-Projects/etianqu/Digest.md"
    ]
    assert payload["sources"][0]["origin"] == "instance-directory"


def test_the_project_note_is_not_listed_as_its_own_source(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["sources"] == []


def test_notes_outside_the_instance_directory_are_not_sources(tmp_path):
    """Membership comes from the directory, never from proximity or subject."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active")
    write_note(
        vault / "40-Projects" / "other-project" / "Digest.md", "conversation-digest"
    )
    write_note(vault / "30-Insights" / "Unrelated.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["sources"] == []


def test_a_note_that_is_not_a_project_note_is_refused(tmp_path):
    """The pack resumes a project; pointing it at a digest is a caller error."""
    vault = make_vault(tmp_path)
    write_note(vault / "30-Insights" / "Note.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("30-Insights/Note.md"), as_of=AS_OF
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "not-a-project-note"


# --- Extracting the resume fields (#86 second half) --------------------------


PROJECT_BODY_ZH = """# 鹅天渠

## 项目概览

从 0 到 1 接入 DashScope。

## 风险与阻塞

- 上下文注入链路未验证

## 决策记录

- 2026-07-09 选择直连而非代理

## 下一步行动

- [ ] 移除默认 MessageChatMemoryAdvisor
"""

PROJECT_BODY_EN = """# Project

## Project Overview

Ship the thing.

## Risks and Blockers

- unproven path

## Decisions Log

- picked direct calls

## Next Actions

- [ ] remove the advisor
"""


def test_extracts_resume_fields_from_a_chinese_project_note(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    fields = payload["resume"]
    assert "DashScope" in fields["goal"]["text"]
    assert "上下文注入链路未验证" in fields["blockers"]["text"]
    assert "选择直连而非代理" in fields["decisions"]["text"]
    assert "MessageChatMemoryAdvisor" in fields["next_actions"]["text"]
    assert fields["goal"]["path"] == "40-Projects/etianqu/Project.md"
    assert fields["goal"]["line"] > 0, "every claim carries the line it came from"


def test_extracts_the_same_fields_from_an_english_project_note(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "en-project"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_EN)

    payload = resume_project.build(
        vault, note=Path("40-Projects/en-project/Project.md"), as_of=AS_OF
    )

    fields = payload["resume"]
    assert "Ship the thing" in fields["goal"]["text"]
    assert "unproven path" in fields["blockers"]["text"]
    assert "remove the advisor" in fields["next_actions"]["text"]


def test_a_missing_section_is_reported_not_guessed(tmp_path):
    """A custom template may lack the standard sections.

    Reporting the gap keeps the pack honest; filling it from arbitrary prose
    would produce a confident answer the note never made.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "sparse"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body="# Sparse\n\nJust prose, no standard headings at all.\n",
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/sparse/Project.md"), as_of=AS_OF
    )

    for field in ("goal", "blockers", "decisions", "next_actions"):
        assert payload["resume"][field] is None, field
    assert set(payload["missing_sections"]) >= {
        "goal",
        "blockers",
        "decisions",
        "next_actions",
    }


# The structure of `40-Projects/etianqu/2026-07-09 AI对话上下文与落库设计复盘.md`
# on the reference Vault, trimmed to the headings that matter here. It is the
# note #115 was filed from: written from a conversation rather than from the
# template, it answers every resume question in prose the vocabulary cannot see.
PROJECT_BODY_FREEFORM = """# AI 对话上下文与落库设计复盘

## 项目概览

梳理对话上下文如何注入与落库。

## TL;DR

现状可用，1.0 走直连。

## 1.0 推荐方案

- 直连 DashScope，不经代理层

## Redis 优先级结论

- 先不引入 Redis，JVM 内存足够

## 后续行动

- [ ] 改造 Farui 上下文链路
"""


def test_unrecognized_headings_are_listed_so_missing_is_not_read_as_absent(
    tmp_path,
):
    """`missing` and `unrecognized` mean opposite things to a reader.

    #115: this note answers decisions under `1.0 推荐方案` and
    `Redis 优先级结论`. Reporting only `missing_sections: [decisions]` tells the
    reader the project never recorded a decision, and someone acting on that
    writes a document that already exists. The pack cannot judge whether those
    headings hold decisions — #86 rules that out — but it can say which headings
    it did not claim, and let the reader look.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body=PROJECT_BODY_FREEFORM,
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    unmatched = payload["headings"]["unmatched"]
    assert "1.0 推荐方案" in unmatched
    assert "Redis 优先级结论" in unmatched
    # The heading the pack did claim must not also be offered as unclaimed.
    assert "项目概览" in payload["headings"]["matched"]
    assert "项目概览" not in unmatched
    assert "decisions" in payload["missing_sections"]


def test_a_note_with_no_headings_at_all_is_distinguishable(tmp_path):
    """The one case where `missing` really does mean the content is absent.

    Both lists empty is the note saying nothing, not the vocabulary failing.
    Without this the reader cannot tell the two apart, which is #115.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "bare"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body="Just prose. No headings anywhere in this note.\n",
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/bare/Project.md"), as_of=AS_OF
    )

    assert payload["headings"] == {"matched": [], "unmatched": []}
    assert "decisions" in payload["missing_sections"]


def test_a_template_note_matches_every_field_and_leaves_nothing_unclaimed(
    tmp_path,
):
    """The control case: written to the template, nothing is missing."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "ai-bug-workflow"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body=PROJECT_BODY_ZH,
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/ai-bug-workflow/Project.md"), as_of=AS_OF
    )

    assert payload["missing_sections"] == []
    assert set(payload["headings"]["matched"]) == {
        "项目概览",
        "风险与阻塞",
        "决策记录",
        "下一步行动",
    }
    # Only the note's own title is left over.
    assert payload["headings"]["unmatched"] == ["鹅天渠"]


def test_reported_headings_cover_every_heading_the_matcher_could_have_read(
    tmp_path,
):
    """The report must describe the matcher's whole search space.

    `_section_text` scans headings at every level, so every level can match. A
    report that silently omitted one would send the reader looking for a section
    the pack claims does not exist — the same silent gap as #115, one level up.
    """
    body = "\n".join(
        f"{'#' * level} H{level}\n\ncontent {level}\n" for level in range(1, 7)
    )
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "deep"
    write_note(
        instance / "Project.md", "project-note", status="active", body=body
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/deep/Project.md"), as_of=AS_OF
    )

    reported = payload["headings"]["matched"] + payload["headings"]["unmatched"]
    assert sorted(reported) == [f"H{level}" for level in range(1, 7)]


def test_next_actions_accepts_the_variant_the_reference_vault_actually_uses(
    tmp_path,
):
    """`后续行动` is observed, not invented.

    Every variant in `RESUME_SECTIONS` must come from a template or a real note;
    this one is from `40-Projects/etianqu/...设计复盘.md`. Guessing at synonyms
    is what makes a vocabulary look complete while still failing silently.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body=PROJECT_BODY_FREEFORM,
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["resume"]["next_actions"] is not None
    assert "Farui" in payload["resume"]["next_actions"]["text"]
    assert "next_actions" not in payload["missing_sections"]


def test_every_known_variant_is_both_matchable_and_reported_as_matched():
    """The report's "recognized" must be the matcher's "matched", exactly.

    Two independent notions of heading equality would let the pack tell a
    reader a heading was recognized that the matcher never reads — the reader
    then stops looking, which is #115 with the arrow reversed. Both sides call
    `_normalize_heading`; this asserts the consequence rather than the call.
    """
    for note_type in ("project-note", "conversation-digest"):
        variants = [
            variant
            for per_type in resume_project.RESUME_SECTIONS.values()
            for variant in per_type.get(note_type, ())
        ]
        assert variants, f"{note_type} has no headings at all"
        for variant in variants:
            text = f"## {variant}\n\nbody\n"
            assert resume_project._section_text(text, (variant,)) is not None, (
                f"matcher cannot find its own variant: {variant!r}"
            )
            report = resume_project._heading_report(text, note_type)
            assert report["matched"] == [variant], (
                f"{variant!r} is matchable but reported as unclaimed: {report}"
            )


def test_a_recognized_but_empty_section_is_matched_and_still_missing(tmp_path):
    """Recognition is by name; content is a separate question.

    Calling an empty `决策记录` unmatched would send the reader hunting for a
    section that is right there and blank. The pair says exactly that: the
    heading was understood, and it holds nothing.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "empty-section"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        body="# P\n\n## 决策记录\n\n## 下一步行动\n\n- [ ] 继续\n",
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/empty-section/Project.md"), as_of=AS_OF
    )

    assert "决策记录" in payload["headings"]["matched"]
    assert "决策记录" not in payload["headings"]["unmatched"]
    assert "decisions" in payload["missing_sections"]


def test_this_projects_own_templates_are_fully_readable_by_the_extractor():
    """A note written from our template must not have unreadable fields.

    The project-note vocabulary is a hand-copy of the templates' headings, the
    same mirror shape row 15 guards on the digest side — and it had already
    drifted: `core/templates/en/project-note.md` says `## Overview` while the
    vocabulary only knew `project overview`, so every note written from this
    project's own English template reported `goal` as missing. Found by writing
    this assertion, not by a user, which is the whole point of having it.

    Asserted behaviourally, per locale, with no hand-kept mapping from heading
    to field: a second mapping would be one more thing to keep in step.
    """
    heading_re = re.compile(r"^#{1,6}[ \t]+(.+?)\s*$", re.M)
    templates = sorted(
        (Path("core") / "templates").glob("**/project-note.md")
    )
    assert len(templates) >= 2, f"expected both locales, found {templates}"

    for template in templates:
        headings = {
            match.group(1).strip().lower()
            for match in heading_re.finditer(
                template.read_text(encoding="utf-8")
            )
        }
        for field in resume_project.PROJECT_NOTE_FIELDS:
            variants = {
                variant.lower()
                for variant in resume_project.RESUME_SECTIONS[field][
                    "project-note"
                ]
            }
            assert variants & headings, (
                f"{template}: its heading for {field!r} is not in the "
                f"vocabulary, so this template's own notes report it missing"
            )


def test_digest_heading_variants_are_derived_not_copied():
    """A second copy of the digest headings would drift from the contract.

    The digest's section names already exist as a contract; restating them here
    is the hand-mirror shape that produced #91's installer paths and #103's peer
    lists. This asserts the resume contract reads from the same source.
    """
    from obsidian_kb_skill.scripts.conversation_digest_contract import (
        CONVERSATION_DIGEST_HEADING_VARIANTS,
    )

    declared = {
        heading.lower()
        for _, headings in CONVERSATION_DIGEST_HEADING_VARIANTS
        for heading in headings
    }
    used = {
        variant
        for field in resume_project.RESUME_SECTIONS.values()
        for variant in field.get("conversation-digest", ())
    }

    assert used, "the digest contributes no sections at all"
    assert used <= declared, f"headings not in the digest contract: {used - declared}"


DIGEST_BODY = """# 上下文方案讨论

## 恢复卡片

目标：接入 DashScope

## 边界与约束

- 不改动现有鉴权链路

## 决策与依据

- 走直连，因为代理层会吞掉 usage

## 证据与产物

- `src/main/java/.../DashScopeClient.java`

## 未决事项与下一步

- [ ] 压测并发上限
"""


def test_sources_contribute_the_fields_the_project_note_cannot_hold(tmp_path):
    """Constraints and evidence live in digests, never in the project note.

    The project note tracks state; a digest records what a working session
    established. Asking the project note for constraints would report a gap
    that is not one.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)
    write_note(instance / "Digest.md", "conversation-digest",
               date="2026-08-05", body=DIGEST_BODY)

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    contributed = payload["from_sources"]
    assert "不改动现有鉴权链路" in contributed["constraints"][0]["text"]
    assert "DashScopeClient" in contributed["evidence"][0]["text"]
    assert contributed["constraints"][0]["path"] == "40-Projects/etianqu/Digest.md"
    assert contributed["constraints"][0]["line"] > 0
    # A field the project note already answers is not reported as missing just
    # because a digest also speaks to it.
    assert "constraints" not in payload["missing_sections"]


def test_a_field_answered_by_both_is_reported_from_both(tmp_path):
    """Never silently pick one version. The pack shows both and cites each."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)
    write_note(instance / "Digest.md", "conversation-digest",
               date="2026-08-05", body=DIGEST_BODY)

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert "选择直连而非代理" in payload["resume"]["decisions"]["text"]
    assert "代理层会吞掉 usage" in payload["from_sources"]["decisions"][0]["text"]
    assert "decisions" in payload["contested"], (
        "both the project note and a source answer this; the reader decides"
    )


def test_a_source_without_standard_sections_contributes_nothing_quietly(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)
    write_note(instance / "Plain.md", "insight-note", body="# Plain\n\nprose only\n")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert payload["from_sources"] == {}
    assert payload["summary"]["sources"] == 1


def test_sources_are_bounded_and_the_truncation_is_reported(tmp_path):
    """A resume pack costs a known number of reads, or it is not a resume pack.

    Silently dropping the overflow would make the pack look complete while the
    most relevant note sits outside it.
    """
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "busy"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)
    for day in range(1, 9):
        write_note(
            instance / f"D{day:02d}.md",
            "conversation-digest",
            date=f"2026-08-{day:02d}",
            body=DIGEST_BODY,
        )

    payload = resume_project.build(
        vault, note=Path("40-Projects/busy/Project.md"), as_of=AS_OF, max_sources=3
    )

    assert len(payload["sources"]) == 3
    assert payload["truncated"] is True
    assert payload["summary"]["sources_available"] == 8
    # Most recent first: resuming needs the latest state, not the oldest.
    assert [source["date"] for source in payload["sources"]] == [
        "2026-08-08",
        "2026-08-07",
        "2026-08-06",
    ]


def test_an_unbounded_pack_reports_no_truncation(tmp_path):
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "small"
    write_note(instance / "Project.md", "project-note", status="active",
               body=PROJECT_BODY_ZH)
    write_note(instance / "D01.md", "conversation-digest", date="2026-08-01",
               body=DIGEST_BODY)

    payload = resume_project.build(
        vault, note=Path("40-Projects/small/Project.md"), as_of=AS_OF, max_sources=3
    )

    assert payload["truncated"] is False
    assert payload["summary"]["sources_available"] == 1


# --- Membership declared, not inferred, outside the directory (#110) ---------
#
# #86 named four kinds of source; PR #107/#108 shipped the first two and the
# issue closed, so the other two lost their tracker. The entity folder makes
# membership readable from a note's location, which is the most reliable route
# and rightly came first — but `40-Projects` root-level project notes have no
# instance directory at all, and #95 made migrating them a non-goal. For those,
# frontmatter `project` and the project note's own `related` are the *only*
# membership claims that exist.
#
# Both are weaker than location: a `project` field can name the wrong project of
# the same name, and a `related` link can resolve to a same-named note in
# another folder. Weaker is not the same as unusable — it means the origin has
# to say so.


def test_a_root_level_project_gains_sources_from_its_related_links(tmp_path):
    """The case #110 exists for, shaped like the reference Vault's own.

    A project note directly under `40-Projects` has no instance directory, so
    today its pack is the note and nothing else. Its `related` list is an
    explicit statement of membership, made by the project note itself.
    """
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "Summary.md",
        "project-note",
        status="active",
        extra='related:\n  - "[[Habits|四个工作习惯]]"\n',
        body=PROJECT_BODY_ZH,
    )
    write_note(vault / "20-Learning" / "Habits.md", "learning-note")

    payload = resume_project.build(
        vault, note=Path("40-Projects/Summary.md"), as_of=AS_OF
    )

    assert payload["instance_directory"] is None
    assert [source["path"] for source in payload["sources"]] == [
        "20-Learning/Habits.md"
    ]
    assert payload["sources"][0]["origin"] == "related-link"


def test_a_note_naming_this_project_in_frontmatter_is_a_source(tmp_path):
    """The third kind: the source note declares its own membership."""
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "Summary.md", "project-note", status="active"
    )
    write_note(
        vault / "30-Insights" / "Digest.md",
        "conversation-digest",
        extra="project: Summary\n",
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/Summary.md"), as_of=AS_OF
    )

    assert [source["path"] for source in payload["sources"]] == [
        "30-Insights/Digest.md"
    ]
    assert payload["sources"][0]["origin"] == "project-field"


def test_an_ambiguous_related_link_is_reported_and_not_resolved(tmp_path):
    """Hard negative from #110: two notes share a name, so nothing is chosen.

    Picking one would file another project's material into this pack, where it
    reads as this project's history. Saying "this link is ambiguous" costs the
    reader one sentence; guessing costs them a wrong conclusion.
    """
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "Summary.md",
        "project-note",
        status="active",
        extra='related:\n  - "[[Notes]]"\n',
    )
    write_note(vault / "20-Learning" / "Notes.md", "learning-note")
    write_note(vault / "30-Insights" / "Notes.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("40-Projects/Summary.md"), as_of=AS_OF
    )

    assert payload["sources"] == []
    codes = {issue["code"] for issue in payload["issues"]}
    assert "ambiguous-related-link" in codes
    ambiguous = next(
        issue for issue in payload["issues"] if issue["code"] == "ambiguous-related-link"
    )
    assert sorted(ambiguous["candidates"]) == [
        "20-Learning/Notes.md",
        "30-Insights/Notes.md",
    ]


def test_a_related_link_that_resolves_nowhere_is_reported(tmp_path):
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "Summary.md",
        "project-note",
        status="active",
        extra='related:\n  - "[[Nothing Here]]"\n',
    )

    payload = resume_project.build(
        vault, note=Path("40-Projects/Summary.md"), as_of=AS_OF
    )

    assert payload["sources"] == []
    assert {issue["code"] for issue in payload["issues"]} == {
        "unresolved-related-link"
    }


def test_one_note_reached_two_ways_appears_once_with_both_origins(tmp_path):
    """#110: report every route, but the note is one source, not two."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        extra='related:\n  - "[[Digest]]"\n',
    )
    write_note(instance / "Digest.md", "conversation-digest", date="2026-08-05")

    payload = resume_project.build(
        vault, note=Path("40-Projects/etianqu/Project.md"), as_of=AS_OF
    )

    assert [source["path"] for source in payload["sources"]] == [
        "40-Projects/etianqu/Digest.md"
    ]
    source = payload["sources"][0]
    # The strongest route names the entry; every route is still reported.
    assert source["origin"] == "instance-directory"
    assert sorted(source["origins"]) == ["instance-directory", "related-link"]


def test_directory_sources_are_never_crowded_out_by_weaker_ones(tmp_path):
    """The bound is layered: location beats declaration when space runs out."""
    vault = make_vault(tmp_path)
    instance = vault / "40-Projects" / "etianqu"
    related = "\n".join(f'  - "[[Far{index}]]"' for index in range(1, 5))
    write_note(
        instance / "Project.md",
        "project-note",
        status="active",
        extra=f"related:\n{related}\n",
    )
    for index in range(1, 4):
        write_note(
            instance / f"Near{index}.md",
            "conversation-digest",
            date=f"2026-08-0{index}",
        )
    for index in range(1, 5):
        write_note(vault / "30-Insights" / f"Far{index}.md", "insight-note")

    payload = resume_project.build(
        vault,
        note=Path("40-Projects/etianqu/Project.md"),
        as_of=AS_OF,
        max_sources=3,
    )

    origins = [source["origin"] for source in payload["sources"]]
    assert origins == ["instance-directory"] * 3, (
        f"a weaker origin displaced a directory source: {origins}"
    )
    assert payload["truncated"] is True
    assert payload["summary"]["sources_available"] == 7


def test_proximity_still_never_establishes_membership(tmp_path):
    """Hard negative that predates this change and must keep holding.

    Both new routes are explicit declarations. A note that merely sits nearby,
    or shares a subject, is still not a source.
    """
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "Summary.md", "project-note", status="active"
    )
    write_note(vault / "30-Insights" / "Unrelated.md", "insight-note")
    write_note(vault / "40-Projects" / "Sibling.md", "insight-note")

    payload = resume_project.build(
        vault, note=Path("40-Projects/Summary.md"), as_of=AS_OF
    )

    assert payload["sources"] == []
