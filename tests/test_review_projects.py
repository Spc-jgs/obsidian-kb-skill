from __future__ import annotations

import datetime
import json
from pathlib import Path

from obsidian_kb_skill.scripts.review_projects import main, review_projects


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "40-Projects").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def _note(
    vault: Path,
    name: str,
    *,
    note_type: str = "project-note",
    date: str | None = "2026-06-01",
    updated: str | None = None,
    status: str | None = "active",
    body: str = "",
) -> Path:
    fields = []
    if date is not None:
        fields.append(f'date: "{date}"')
    if updated is not None:
        fields.append(f'updated: "{updated}"')
    fields.append(f"type: {note_type}")
    if status is not None:
        fields.append(f"status: {status}")
    path = vault / "40-Projects" / f"{name}.md"
    path.write_text(
        "---\n" + "\n".join(fields) + f"\n---\n\n# {name}\n\n{body}",
        encoding="utf-8",
    )
    return path


def test_review_projects_builds_explainable_stable_queue(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "Blocked",
        updated="2026-08-09",
        status="blocked",
        body="## 下一步行动\n\n- [ ] Ask security for approval\n",
    )
    _note(vault, "Missing Date", date=None)
    _note(
        vault,
        "Stale With Tasks",
        date="2025-01-01",
        updated="2026-07-01",
        body="## 下一步行动\n\n- [ ] Ship the smallest probe\n- [ ] Measure it\n",
    )
    _note(vault, "Older But No Tasks", updated="2026-05-01")
    _note(vault, "Fresh", updated="2026-08-01")
    _note(vault, "Closed", updated="2025-01-01", status="completed")
    _note(
        vault,
        "Not A Project",
        note_type="insight-note",
        updated="2025-01-01",
    )

    payload = review_projects(
        vault,
        as_of=datetime.date(2026, 8, 10),
        stale_days=30,
        top_k=10,
    )

    assert payload["schema_version"] == "1.0"
    assert payload["ok"] is True
    assert payload["command"] == "review-projects"
    assert payload["read_only"] is True
    assert [item["path"] for item in payload["items"]] == [
        "40-Projects/Blocked.md",
        "40-Projects/Missing Date.md",
        "40-Projects/Stale With Tasks.md",
        "40-Projects/Older But No Tasks.md",
    ]
    assert payload["items"][0]["reasons"] == ["blocked", "open-tasks:1"]
    assert payload["items"][0]["next_action"] == "Ask security for approval"
    assert payload["items"][1]["activity_date"] is None
    assert payload["items"][1]["age_days"] is None
    assert payload["items"][1]["reasons"] == ["missing-activity-date"]
    assert payload["items"][2]["activity_date"] == "2026-07-01"
    assert payload["items"][2]["age_days"] == 40
    assert payload["items"][2]["open_tasks"] == 2
    assert payload["items"][2]["reasons"] == ["stale:40-days", "open-tasks:2"]
    assert payload["summary"] == {
        "files": 7,
        "projects": 6,
        "candidates": 4,
        "returned": 4,
        "skipped": 0,
    }
    assert payload["issues"] == []


def test_next_action_ignores_comments_and_fences_and_prefers_standard_section(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "Visible",
        updated="2026-01-01",
        body=(
            "<!-- - [ ] hidden instruction -->\n\n"
            "```markdown\n- [ ] fake code task\n```\n\n"
            "## Risks\n\n- [ ] generic open item\n\n"
            "## Next Steps\n\n- [ ] Do the real next action\n"
        ),
    )

    payload = review_projects(
        vault,
        as_of=datetime.date(2026, 8, 10),
        stale_days=30,
        top_k=10,
    )

    assert payload["items"][0]["open_tasks"] == 2
    assert payload["items"][0]["next_action"] == "Do the real next action"


def test_next_action_is_bounded_for_agent_context(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "Long Action",
        updated="2026-01-01",
        body="## 下一步行动\n\n- [ ] " + ("x" * 250) + "\n",
    )

    payload = review_projects(
        vault,
        as_of=datetime.date(2026, 8, 10),
        stale_days=30,
        top_k=10,
    )

    action = payload["items"][0]["next_action"]
    assert len(action) == 200
    assert action.endswith("…")


def test_review_projects_reports_bad_frontmatter_without_blocking_queue(tmp_path):
    vault = _vault(tmp_path)
    _note(vault, "Good", updated="2026-01-01")
    (vault / "40-Projects" / "Broken.md").write_text(
        "---\ntype: [project-note\n---\n# Broken\n",
        encoding="utf-8",
    )

    payload = review_projects(
        vault,
        as_of=datetime.date(2026, 8, 10),
        stale_days=30,
        top_k=10,
    )

    assert [item["path"] for item in payload["items"]] == [
        "40-Projects/Good.md"
    ]
    assert payload["summary"]["skipped"] == 1
    assert payload["issues"][0]["path"] == "40-Projects/Broken.md"
    assert payload["issues"][0]["code"] == "invalid-frontmatter"


def test_activity_date_prefers_updated_and_future_dates_are_isolated(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "Fresh By Updated",
        date="2025-01-01",
        updated="2026-08-09",
    )
    _note(
        vault,
        "Fallback To Date",
        date="2026-06-01",
        updated="not-a-date",
    )
    _note(
        vault,
        "Future",
        date="2025-01-01",
        updated="2026-08-11",
    )

    payload = review_projects(
        vault,
        as_of=datetime.date(2026, 8, 10),
        stale_days=30,
        top_k=10,
    )

    assert [item["path"] for item in payload["items"]] == [
        "40-Projects/Fallback To Date.md"
    ]
    assert payload["items"][0]["activity_date"] == "2026-06-01"
    assert payload["summary"]["projects"] == 3
    assert payload["summary"]["skipped"] == 1
    assert payload["issues"] == [
        {
            "code": "future-activity-date",
            "path": "40-Projects/Future.md",
            "message": "activity date 2026-08-11 is after --as-of 2026-08-10",
        }
    ]


def test_cli_json_contract_and_read_only_behavior(tmp_path, capsys):
    vault = _vault(tmp_path)
    _note(vault, "Old", updated="2026-01-01")
    before = {
        path.relative_to(vault): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in vault.rglob("*")
        if path.is_file()
    }

    exit_code = main(
        [
            str(vault),
            "--as-of",
            "2026-08-10",
            "--stale-days",
            "30",
            "--top-k",
            "5",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["scope"] == "."
    assert payload["as_of"] == "2026-08-10"
    assert payload["items"][0]["path"] == "40-Projects/Old.md"
    after = {
        path.relative_to(vault): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_cli_refuses_invalid_bounds_and_outside_scope(tmp_path, capsys):
    vault = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    assert main([str(vault), "--as-of", "recently", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid-date"

    assert main([str(vault), "--stale-days", "0", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid-stale-days"

    assert main([str(vault), "--top-k", "21", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid-top-k"

    assert main([str(vault), "--scope", str(outside), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "PATH_OUTSIDE_VAULT"


def test_text_mode_reports_skipped_notes_even_when_queue_is_empty(tmp_path, capsys):
    vault = _vault(tmp_path)
    (vault / "40-Projects" / "Broken.md").write_text(
        "---\ntype: [project-note\n---\n# Broken\n",
        encoding="utf-8",
    )

    assert main([str(vault), "--as-of", "2026-08-10"]) == 0

    captured = capsys.readouterr()
    assert "No projects need review." in captured.out
    assert "1 note(s) skipped." in captured.err


def test_a_finished_project_stays_out_of_the_queue_in_either_language(tmp_path):
    """A Chinese `status` closed a project just as much as an English one.

    Before this, `status: 已完成` matched nothing in the closed set, so a project
    finished eighteen months ago came back every review as `stale:N-days` — the
    exact false positive the queue promises not to produce, in the language most
    of this Vault's own notes are written in.
    """
    vault = _vault(tmp_path)
    for index, status in enumerate(("completed", "已完成", "已归档", "已取消")):
        _note(vault, f"Finished {index}", date="2025-01-01", status=status)
    _note(vault, "Still Running", date="2025-01-01", status="active")

    payload = review_projects(vault, as_of=datetime.date(2026, 8, 11))

    assert [item["title"] for item in payload["items"]] == ["Still Running"]


def test_non_instance_project_templates_stay_out_but_open_states_remain(tmp_path):
    """A reusable project-shaped note is not a project instance to revive."""
    vault = _vault(tmp_path)
    _note(vault, "English Template", date="2025-01-01", status="template")
    _note(vault, "Chinese Template", date="2025-01-01", status="模板")
    _note(vault, "Draft", date="2025-01-01", status="draft")
    _note(vault, "Active", date="2025-01-01", status="active")
    _note(vault, "Unknown", date="2025-01-01", status=None)

    payload = review_projects(vault, as_of=datetime.date(2026, 8, 11))

    assert [item["title"] for item in payload["items"]] == [
        "Active",
        "Draft",
        "Unknown",
    ]
    assert payload["summary"]["projects"] == 3


def test_the_library_entrypoint_enforces_vault_containment_itself(tmp_path):
    """Not only the CLI. The sibling `search_vault` validates inside, too.

    A scope outside the Vault used to reach `Path.relative_to` and raise a bare
    ValueError carrying an absolute filesystem path — an unhandled crash where
    the contract says refusal, and a path leak the retrieval reference forbids.
    """
    import pytest

    from obsidian_kb_skill.scripts.vault_paths import PathOutsideVaultError

    vault = _vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text(
        "---\ntype: project-note\n---\n# x\n", encoding="utf-8"
    )

    with pytest.raises(PathOutsideVaultError):
        review_projects(vault, as_of=datetime.date(2026, 8, 11), scope=outside)


def test_the_review_skips_exactly_what_search_skips(tmp_path):
    """One policy for "this is not knowledge", not two copies drifting apart.

    The sets were already different: search gained `.obsidian-kb` when the
    retrieval lexicon landed, and this helper spelled `95-Sources` as a literal
    rather than the shared constant.
    """
    from obsidian_kb_skill.scripts import review_projects as radar
    from obsidian_kb_skill.scripts import search_vault as search

    assert radar.IGNORED_DIRECTORY_NAMES is search.IGNORED_DIRECTORY_NAMES


# --- A checkbox is syntax; a todo is a claim about this project (#109) -------
#
# `40-Projects/ai-bug-workflow/…完整复盘.md` on the reference Vault ends with a
# fifteen-item *reusable* checklist — things to verify when landing some *other*
# project. Its own work is a P0/P1/P2 numbered list under 下一步行动 with no
# checkbox at all. Counting every unchecked box made that note the busiest
# project in the Vault and reported a checklist question as its next action,
# while its real next steps were invisible.

# The real note's shape, verified against the file: `## 下一步行动` at line 600
# and `### 可复用的项目落地检查表` at 631 — the checklist is *nested inside* the
# section, not beside it. Scoping by section therefore does not separate them,
# and a fixture that made them siblings would pass while the defect stood.
CHECKLIST_INSIDE = """## 下一步行动

### P0：下一次迭代前完成

1. 收窄 Beta 触发条件
2. 补齐 GitLab API 证据

### 可复用的项目落地检查表

- [ ] 测试或发布基线是什么；
- [ ] 证据分层是否落到位；
- [ ] 授权是否按动作分级；

## 关联笔记
"""

# The separable case: a checklist in its own top-level section.
CHECKLIST_BESIDE = """## 下一步行动

- [ ] 改造上下文链路

## 可复用的项目落地检查表

- [ ] 测试或发布基线是什么；
- [ ] 证据分层是否落到位；
- [ ] 授权是否按动作分级；
"""


def test_a_checklist_in_its_own_section_does_not_rank_a_project_up(tmp_path):
    """Ranking follows the project's own todos, not its reusable material."""
    vault = _vault(tmp_path)
    _note(vault, "Checklist", updated="2026-01-01", body=CHECKLIST_BESIDE)
    _note(
        vault,
        "RealWork",
        updated="2026-01-01",
        body="## 下一步行动\n\n- [ ] 改造上下文链路\n- [ ] 补单元测试\n",
    )

    payload = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )

    order = [item["path"].split("/")[-1] for item in payload["items"]]
    assert order[0] == "RealWork.md", (
        f"the checklist note outranked real work: {order}"
    )
    checklist = next(i for i in payload["items"] if i["path"].endswith("Checklist.md"))
    assert checklist["open_tasks"] == 4
    assert checklist["open_tasks_in_next_actions"] == 1
    assert checklist["open_tasks_scope"] == "next-actions"


def test_a_checklist_nested_inside_the_section_is_named_not_separated(tmp_path):
    """The case that filed #109 is not mechanically separable — so say where.

    Structure cannot tell `可复用的项目落地检查表` from `P0：下一次迭代前完成`;
    both are subsections of next actions. What separates them is what the
    author called them, and that is a judgement about content — the radar
    reports the heading and leaves the judgement to the reader.

    Asserted so that a later change claiming to "fix" this case has to face
    what it would be claiming to decide.
    """
    vault = _vault(tmp_path)
    _note(vault, "Checklist", updated="2026-01-01", body=CHECKLIST_INSIDE)

    item = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )["items"][0]

    assert item["open_tasks_in_next_actions"] == 3
    assert item["next_action"] == "测试或发布基线是什么；"
    assert item["next_action_heading"] == "可复用的项目落地检查表"


def test_a_note_with_no_next_actions_section_is_not_silently_zeroed(tmp_path):
    """Scoping must not erase a whole class of project from the queue.

    A note that never had the heading is not making a claim about where its
    todos live, so the whole-note count remains the honest reading.
    """
    vault = _vault(tmp_path)
    _note(
        vault,
        "Freeform",
        updated="2026-01-01",
        body="## 待办\n\n- [ ] 一件事\n- [ ] 另一件事\n",
    )

    item = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )["items"][0]

    assert item["open_tasks"] == 2
    assert item["open_tasks_in_next_actions"] is None
    assert item["open_tasks_scope"] == "whole-note"
    assert "open-tasks:2" in item["reasons"]


def test_next_action_is_not_reached_for_outside_the_section(tmp_path):
    """A section that exists and holds no checkbox answers "none", not "guess".

    Before this, the radar reached past an empty next-actions section for the
    first checkbox anywhere in the note — which is how a reusable checklist's
    question was reported as one project's next step. Saying nothing is the
    honest answer: the project wrote a numbered list, and the radar reads
    checkboxes.
    """
    vault = _vault(tmp_path)
    _note(
        vault,
        "Numbered",
        updated="2026-01-01",
        body=(
            "## 下一步行动\n\n1. 收窄 Beta 触发条件\n2. 补齐证据\n\n"
            "## 可复用的项目落地检查表\n\n- [ ] 测试基线是什么；\n"
        ),
    )

    item = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )["items"][0]

    assert item["next_action"] is None
    assert item["next_action_heading"] is None
    assert item["open_tasks"] == 1
    assert item["open_tasks_in_next_actions"] == 0


def test_a_note_without_the_section_still_falls_back_to_its_first_task(tmp_path):
    """Hard negative: the pre-existing fallback is untouched where it applied."""
    vault = _vault(tmp_path)
    _note(
        vault,
        "Freeform",
        updated="2026-01-01",
        body="## 待办\n\n- [ ] 一件事\n",
    )

    item = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )["items"][0]

    assert item["next_action"] == "一件事"


def test_todos_inside_the_next_actions_section_are_unchanged(tmp_path):
    """Hard negative: the note that was already right must not move.

    Shaped like `40-Projects/etianqu/…设计复盘.md`, whose seven checkboxes all
    sit under `后续行动` — a heading only the shared vocabulary recognises.
    """
    vault = _vault(tmp_path)
    _note(
        vault,
        "Etianqu",
        updated="2026-01-01",
        body=(
            "## 1.0 推荐方案\n\n直连。\n\n"
            "## 后续行动\n\n- [ ] 改造 Farui 上下文链路\n- [ ] 新增 Assembler\n"
        ),
    )

    item = review_projects(
        vault, as_of=datetime.date(2026, 8, 13), stale_days=30, top_k=10
    )["items"][0]

    assert item["open_tasks"] == 2
    assert item["open_tasks_in_next_actions"] == 2
    assert item["next_action"] == "改造 Farui 上下文链路"
