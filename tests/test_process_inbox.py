"""Tests for the Inbox Processor (scripts/process_inbox.py)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.process_inbox import process_vault


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "00-Inbox").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def test_routes_insight_by_keyword(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\ninteresting idea\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=False)

    assert len(plans) == 1
    assert plans[0]["target"] == "30-Insights"
    # read-only: nothing moved
    assert (vault / "00-Inbox" / "Note.md").is_file()
    assert not (vault / "30-Insights" / "Note.md").exists()


def test_routes_by_type(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: ""\nauthor: ""\npublished: ""\n---\n# Clip\n',
        encoding="utf-8",
    )

    plans = process_vault(vault, apply=False)

    assert plans[0]["target"] == "20-Learning"


def test_apply_moves_and_fills_frontmatter(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    moved = vault / "30-Insights" / "Note.md"
    assert moved.is_file()
    assert not (vault / "00-Inbox" / "Note.md").exists()
    text = moved.read_text(encoding="utf-8")
    assert "type: insight-note" in text
    assert "tags:" in text
    assert "date:" in text


def test_apply_updates_static_index(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    assert "[[" in index_text
    assert "Some Insight" in index_text


def test_skips_when_target_unknown(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Misc.md").write_text(
        "# Misc\nuncategorized capture\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=True)

    assert plans[0].get("skip")
    # left in the inbox
    assert (vault / "00-Inbox" / "Misc.md").is_file()


def test_apply_skips_existing_target(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Note.md").write_text("existing\n", encoding="utf-8")
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    assert (vault / "00-Inbox" / "Note.md").is_file()
    assert (vault / "30-Insights" / "Note.md").read_text(encoding="utf-8") == "existing\n"


def test_apply_does_not_touch_folder_index_listings(tmp_path):
    vault = make_vault(tmp_path)
    obsidian = vault / ".obsidian"
    plugin = obsidian / "plugins" / "obsidian-folder-index"
    plugin.mkdir(parents=True)
    (obsidian / "community-plugins.json").write_text(
        json.dumps(["obsidian-folder-index"]), encoding="utf-8"
    )
    (vault / "30-Insights" / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n```folder-index-content\n```\n",
        encoding="utf-8",
    )
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    # Folder Index owns the listing; the processor must not append a manual link.
    assert "[[" not in index_text
