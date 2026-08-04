"""A heading at the wrong depth must not cost a full document resend.

`missing-template-heading` was a hard refusal with no repair path, so one `#`
that should have been `##` forced the whole article back through stdin. The
repair is deliberately narrow: only the ATX level moves, and only when the
result actually satisfies the template contract.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.template_contract import heading_level_repair

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}
TEMPLATE = (
    "---\ntype: insight-note\ntags: [insight]\n---\n"
    "# {{title}}\n\n## 来源与结论\n\n## 关键要点\n"
)


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", *args],
        cwd=str(ROOT),
        env=ENV,
        input=stdin,
        capture_output=True,
        text=True,
        # Windows would otherwise encode CJK stdin with the locale codec.
        encoding="utf-8",
    )


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    (vault / "Templates" / "Insight Note.md").write_text(TEMPLATE, encoding="utf-8")
    return vault


def test_repair_promotes_only_the_level(tmp_path: Path):
    body = "# 标题\n\n# 来源与结论\n\n正文\n\n# 关键要点\n\n- a\n"

    repaired, edits = heading_level_repair(body, TEMPLATE)

    assert "## 来源与结论" in repaired and "## 关键要点" in repaired
    assert "# 标题" in repaired.splitlines()[0]
    assert edits == [
        {"line": 3, "actual": "# 来源与结论", "expected": "## 来源与结论"},
        {"line": 7, "actual": "# 关键要点", "expected": "## 关键要点"},
    ]


def test_repair_matches_the_level_the_template_uses():
    template = "---\ntype: insight-note\n---\n\n## 概述\n\n### 细节\n"
    body = "# 标题\n\n## 概述\n\n## 细节\n"

    repaired, edits = heading_level_repair(body, template)

    assert "### 细节" in repaired
    assert edits == [{"line": 5, "actual": "## 细节", "expected": "### 细节"}]


def test_a_missing_section_is_not_repairable():
    body = "# 标题\n\n# 来源与结论\n\n正文\n"

    assert heading_level_repair(body, TEMPLATE) is None


def test_headings_inside_a_fence_are_not_touched():
    body = (
        "# 标题\n\n## 来源与结论\n\n```md\n# 关键要点\n```\n\n## 关键要点\n"
    )

    assert heading_level_repair(body, TEMPLATE) is None


def test_preflight_suggests_the_repair_without_applying_it(tmp_path: Path):
    vault = _make_vault(tmp_path)
    body = "# 标题\n\n# 来源与结论\n\n正文\n\n# 关键要点\n\n- a\n"

    result = _run(
        str(vault), "--type", "insight-note", "--title", "层级",
        "--date", "2026-07-14", "--stdin", "--preflight-json", stdin=body,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    validation = payload["validation"]
    assert validation["findings"][0]["code"] == "missing-template-heading"
    fix = validation["suggested_fix"]
    assert fix["kind"] == "heading-level-mismatch"
    assert [edit["expected"] for edit in fix["edits"]] == [
        "## 来源与结论",
        "## 关键要点",
    ]
    assert payload["content"]["sha256"] in fix["message"]
    assert "applied_fix" not in payload


def test_repairing_by_reference_clears_the_finding(tmp_path: Path):
    vault = _make_vault(tmp_path)
    body = "# 标题\n\n# 来源与结论\n\n正文\n\n# 关键要点\n\n- a\n"
    first = json.loads(
        _run(
            str(vault), "--type", "insight-note", "--title", "层级",
            "--date", "2026-07-14", "--stdin", "--preflight-json", stdin=body,
        ).stdout
    )

    result = _run(
        str(vault), "--type", "insight-note", "--title", "层级",
        "--date", "2026-07-14", "--from-preflight", first["content"]["sha256"],
        "--fix-heading-levels", "--preflight-json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["validation"] == {"ok": True, "count": 0, "findings": []}
    assert payload["applied_fix"]["kind"] == "heading-level-mismatch"
    assert payload["content"]["sha256"] != first["content"]["sha256"]

    applied = _run(
        str(vault), "--type", "insight-note", "--title", "层级",
        "--date", "2026-07-14", "--from-preflight", payload["content"]["sha256"],
        "--apply", "--compact-json",
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    written = Path(json.loads(applied.stdout)["path"]).read_text(encoding="utf-8")
    assert "## 来源与结论" in written and "# 标题" in written


def test_a_repair_cannot_be_applied_without_review(tmp_path: Path):
    vault = _make_vault(tmp_path)
    body = "# 标题\n\n# 来源与结论\n\n正文\n\n# 关键要点\n"

    result = _run(
        str(vault), "--type", "insight-note", "--title", "层级",
        "--stdin", "--fix-heading-levels", "--apply", "--compact-json",
        stdin=body,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "fix-requires-preflight"
    assert not list((vault / "30-Insights").glob("*.md"))
