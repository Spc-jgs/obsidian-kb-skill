"""Tests for the read-only project resume pack (scripts/resume_project.py)."""
from __future__ import annotations

import datetime
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
