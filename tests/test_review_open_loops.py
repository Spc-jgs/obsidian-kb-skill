"""What the author still means to do, without deciding what it means.

The queue's value rests entirely on what it refuses to collect. On the
reference Vault `可复用的项目落地检查表` holds fifteen unticked boxes that are
a reusable question list — they end in `；` and can never be ticked — and a
looser predicate that reached them would report a note's prose as open work.
So most of this file is negatives.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.review_open_loops import review_open_loops


def note(vault: Path, relative: str, body: str, *, note_type: str = "insight-note",
         date: str = "2026-07-07") -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ndate: \"{date}\"\ntype: {note_type}\ntags: [x]\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def vault_with(tmp_path: Path, *notes: tuple[str, str]) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for relative, body in notes:
        note(vault, relative, body)
    return vault


def texts(report: dict) -> list[str]:
    return [item["text"] for item in report["items"]]


def test_an_unticked_box_under_a_template_action_heading_is_collected(tmp_path):
    vault = vault_with(tmp_path, ("a.md", "## 影响与后续行动\n\n- [ ] 补一条回归测试\n"))
    report = review_open_loops(vault)
    assert texts(report) == ["补一条回归测试"]
    assert report["items"][0]["heading"] == "影响与后续行动"
    assert report["items"][0]["line"] == 9  # 1-indexed, frontmatter included
    assert report["summary"]["by_type"] == {"insight-note": 1}


def test_a_heading_no_template_declares_is_not_an_action_heading(tmp_path):
    """The fifteen-item question list, in miniature.

    This is the hard negative the whole design turns on: the queue is bounded
    by what templates declare, not by what looks like a task.
    """
    vault = vault_with(
        tmp_path,
        ("a.md", "## 可复用的项目落地检查表\n\n- [ ] Agent 从哪个目录发现 Skill；\n"),
    )
    assert review_open_loops(vault)["items"] == []


def test_a_ticked_box_is_closed(tmp_path):
    vault = vault_with(tmp_path, ("a.md", "## 影响与后续行动\n\n- [x] 已经做完了\n"))
    assert review_open_loops(vault)["items"] == []


def test_a_box_inside_a_fence_is_an_example(tmp_path):
    vault = vault_with(
        tmp_path,
        ("a.md", "## 影响与后续行动\n\n```markdown\n- [ ] 这是文档里的示例\n```\n\n- [ ] 这是真的\n"),
    )
    assert texts(review_open_loops(vault)) == ["这是真的"]


def test_inline_code_survives_into_the_item_text(tmp_path):
    """Decide on the blanked copy, read from the original (#189's pattern).

    `blank_code_examples` empties inline code too, so taking the text from it
    turned `用 `/mcp` 命令验证 MCP 连接` into `用  命令验证 MCP 连接` — a task
    stripped of the command it is about. Found by running the helper on the
    reference Vault, not by a test, which is why this one exists.
    """
    vault = vault_with(
        tmp_path,
        ("a.md", "## 影响与后续行动\n\n- [ ] 用 `/mcp` 命令验证 MCP 连接\n"),
    )
    assert texts(review_open_loops(vault)) == ["用 `/mcp` 命令验证 MCP 连接"]


def test_an_empty_box_is_template_scaffolding_not_a_loop(tmp_path):
    """Every template ships `- [ ]` with nothing after it."""
    vault = vault_with(tmp_path, ("a.md", "## 影响与后续行动\n\n- [ ]\n"))
    assert review_open_loops(vault)["items"] == []


def test_a_box_before_any_heading_is_not_collected(tmp_path):
    vault = vault_with(tmp_path, ("a.md", "- [ ] 在任何标题之前\n\n## 影响与后续行动\n"))
    assert review_open_loops(vault)["items"] == []


def test_the_action_heading_must_match_the_note_type_agnostically(tmp_path):
    """A heading declared by any template counts, whatever the note's type.

    Deliberate: a `learning-note` that writes `下一步行动` is using a heading
    the project declares as action-bearing, and refusing it would grade the
    author's filing rather than collect their open work.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    note(vault, "a.md", "## 下一步行动\n\n- [ ] 跨类型的行动项\n", note_type="learning-note")
    assert texts(review_open_loops(vault)) == ["跨类型的行动项"]


def test_oldest_loops_come_first_and_undated_notes_sort_last(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    note(vault, "new.md", "## 影响与后续行动\n\n- [ ] 新的\n", date="2026-08-01")
    note(vault, "old.md", "## 影响与后续行动\n\n- [ ] 旧的\n", date="2026-06-01")
    (vault / "undated.md").write_text(
        "---\ntype: insight-note\ntags: [x]\n---\n\n## 影响与后续行动\n\n- [ ] 没有日期\n",
        encoding="utf-8",
    )
    assert texts(review_open_loops(vault)) == ["旧的", "新的", "没有日期"]


def test_the_type_filter_restricts_the_queue(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    note(vault, "a.md", "## 影响与后续行动\n\n- [ ] 洞察的\n", note_type="insight-note")
    note(vault, "b.md", "## 下一步行动\n\n- [ ] 项目的\n", note_type="project-note")
    report = review_open_loops(vault, note_types=("project-note",))
    assert texts(report) == ["项目的"]


def test_the_report_is_read_only_and_leaves_the_vault_untouched(tmp_path):
    vault = vault_with(tmp_path, ("a.md", "## 影响与后续行动\n\n- [ ] 一件事\n"))
    before = {p: p.read_bytes() for p in sorted(vault.rglob("*.md"))}
    mtimes = {p: p.stat().st_mtime for p in before}
    report = review_open_loops(vault)
    assert report["read_only"] is True
    after = {p: p.read_bytes() for p in sorted(vault.rglob("*.md"))}
    assert after == before
    assert {p: p.stat().st_mtime for p in after} == mtimes


def test_no_loops_is_a_successful_empty_result(tmp_path):
    """Not rewritten into "everything is done" — #87 names this explicitly."""
    vault = vault_with(tmp_path, ("a.md", "## 影响与后续行动\n\n没有待办。\n"))
    report = review_open_loops(vault)
    assert report["ok"] is True
    assert report["summary"]["open_loops"] == 0
    assert report["items"] == []


def test_truncation_is_reported(tmp_path):
    body = "## 影响与后续行动\n\n" + "".join(f"- [ ] 第 {i} 件\n" for i in range(5))
    vault = vault_with(tmp_path, ("a.md", body))
    report = review_open_loops(vault, top_k=2)
    assert len(report["items"]) == 2
    assert report["truncated"] is True
    assert report["summary"]["open_loops"] == 5
