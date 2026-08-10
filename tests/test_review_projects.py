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
