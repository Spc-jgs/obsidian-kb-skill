"""Tests for user-confirmed Vault category initialization."""
from __future__ import annotations

import json
from pathlib import Path

from obsidian_kb_skill.scripts.create_category import (
    PlannedChange,
    plan_category,
    render_category_index,
)


def make_vault(
    tmp_path: Path,
    *,
    folder_index: bool = False,
    custom_index: bool = False,
    dataview: bool = False,
) -> Path:
    vault = tmp_path / "vault"
    obsidian = vault / ".obsidian"
    obsidian.mkdir(parents=True)
    (vault / "Templates").mkdir()
    learning = vault / "20-Learning"
    learning.mkdir()

    plugins = ["obsidian-folder-index"] if folder_index else []
    (obsidian / "community-plugins.json").write_text(
        json.dumps(plugins), encoding="utf-8"
    )
    if folder_index:
        plugin = obsidian / "plugins" / "obsidian-folder-index"
        plugin.mkdir(parents=True)
        (plugin / "data.json").write_text(
            json.dumps(
                {
                    "graphOverwrite": True,
                    "indexFileUserSpecified": custom_index,
                    "indexFilename": "HOME",
                    "rootIndexFile": "INDEX.md",
                }
            ),
            encoding="utf-8",
        )
        (learning / ("HOME.md" if custom_index else "20-Learning.md")).write_text(
            "---\ntype: folder-index\ntags: [moc]\n---\n"
            "```folder-index-content\n```\n",
            encoding="utf-8",
        )
    elif dataview:
        (learning / "INDEX.md").write_text(
            "# Learning\n\n```dataview\nLIST FROM \"20-Learning\"\n```\n",
            encoding="utf-8",
        )
    else:
        (learning / "INDEX.md").write_text(
            "---\ntype: moc\ntags: [moc]\n---\n# Learning\n",
            encoding="utf-8",
        )
    return vault


def test_plans_native_folder_index(tmp_path: Path):
    vault = make_vault(tmp_path, folder_index=True)

    plan = plan_category(vault, "20-Learning/Rust")

    assert plan.folder == Path("20-Learning/Rust")
    assert plan.parent == Path("20-Learning")
    assert plan.category == "Rust"
    assert plan.index_mode == "folder-index"
    assert plan.index_path == Path("20-Learning/Rust/Rust.md")
    assert plan.planned_changes == (
        PlannedChange("directory", Path("20-Learning/Rust")),
        PlannedChange("index", Path("20-Learning/Rust/Rust.md")),
    )


def test_plans_custom_folder_index_filename(tmp_path: Path):
    vault = make_vault(tmp_path, folder_index=True, custom_index=True)

    plan = plan_category(vault, "20-Learning/Rust")

    assert plan.index_mode == "folder-index"
    assert plan.index_path == Path("20-Learning/Rust/HOME.md")
    assert any("structural graph incomplete" in item for item in plan.warnings)


def test_renders_one_folder_index_content_block(tmp_path: Path):
    vault = make_vault(tmp_path, folder_index=True)

    text = render_category_index(plan_category(vault, "20-Learning/Rust"))

    assert "type: folder-index" in text
    assert "- moc" in text
    assert "# Rust" in text
    assert text.count("```folder-index-content") == 1


def test_inherits_dataview_mode_from_parent(tmp_path: Path):
    vault = make_vault(tmp_path, dataview=True)

    plan = plan_category(vault, "20-Learning/Rust")
    text = render_category_index(plan)

    assert plan.index_mode == "dataview"
    assert plan.index_path == Path("20-Learning/Rust/INDEX.md")
    assert "```dataview" in text
    assert 'FROM "20-Learning/Rust"' in text


def test_falls_back_to_static_index(tmp_path: Path):
    vault = make_vault(tmp_path)

    plan = plan_category(vault, "20-Learning/Rust")
    text = render_category_index(plan)

    assert plan.index_mode == "static"
    assert plan.index_path == Path("20-Learning/Rust/INDEX.md")
    assert "type: moc" in text
    assert "# Rust" in text
    assert "dataview" not in text


def test_existing_category_is_a_noop_plan(tmp_path: Path):
    vault = make_vault(tmp_path)
    category = vault / "20-Learning" / "Rust"
    category.mkdir()
    (category / "INDEX.md").write_text("original\n", encoding="utf-8")

    plan = plan_category(vault, "20-Learning/Rust")

    assert plan.exists is True
    assert plan.planned_changes == ()
    assert plan.index_path == Path("20-Learning/Rust/INDEX.md")
