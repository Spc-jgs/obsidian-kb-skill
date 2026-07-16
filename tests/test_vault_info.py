"""Tests for vault_info.py — read-only cold-start context."""
from __future__ import annotations

from pathlib import Path

from obsidian_kb_skill.scripts import vault_info

collect = vault_info.collect


def _make_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    for t in ("Daily Note.md", "Meeting Note.md", "Web Clip.md"):
        (vault / "Templates" / t).write_text(
            "---\ntype: daily-note\ndate: 2026-01-01\n---\n", encoding="utf-8"
        )
    for f in ("00-Inbox", "20-Learning", "30-Insights"):
        (vault / f).mkdir()
        (vault / f / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    return vault


def test_valid_vault_reports_true_with_templates(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    assert info["valid"] is True
    assert info["validation"] == {
        "exists": True,
        "is_obsidian": True,
        "has_templates": True,
    }
    assert info["templates"] == ["Daily Note", "Meeting Note", "Web Clip"]
    assert info["warnings"] == []


def test_standard_folders_reported_with_existence_and_index(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    folders = info["standard_folders"]
    # Present folders marked exists; missing folders (e.g. 40-Projects) not.
    assert folders["00-Inbox"]["exists"] is True
    assert folders["20-Learning"]["exists"] is True
    assert folders["40-Projects"]["exists"] is False
    # Note folders carry an index strategy; Templates/Attachments do not.
    assert folders["30-Insights"]["index"]["mode"] == "static"
    assert folders["30-Insights"]["index"]["can_append"] is True
    assert folders["Templates"]["index"] is None
    assert folders["Attachments"]["index"] is None


def test_invalid_vault_reports_false_with_warnings(tmp_path: Path):
    vault = tmp_path / "missing_vault"
    info = collect(vault)
    assert info["valid"] is False
    assert info["validation"]["exists"] is False
    assert any("does not exist" in w for w in info["warnings"])
    # No crash; templates empty and folders exist=False.
    assert info["templates"] == []
    assert info["standard_folders"]["00-Inbox"]["exists"] is False


def test_folder_index_global_present(tmp_path: Path):
    vault = _make_vault(tmp_path)
    info = collect(vault)
    g = info["folder_index_global"]
    assert set(g) == {"enabled", "graph_overwrite", "user_specified", "root_index_file"}
    assert g["root_index_file"] == "INDEX.md"


def test_custom_templates_reports_only_type_slugs(tmp_path: Path):
    vault = _make_vault(tmp_path)

    info = collect(vault)

    assert info["custom_templates"] == [
        "daily-note",
        "meeting-note",
        "web-clip",
    ]
    assert all(isinstance(item, str) for item in info["custom_templates"])


def test_collect_omits_template_shape_without_selected_type(tmp_path: Path):
    vault = _make_vault(tmp_path)

    info = collect(vault)

    assert "template_shape" not in info


def test_collect_returns_only_selected_template_shape(tmp_path: Path):
    vault = _make_vault(tmp_path)
    (vault / "Templates" / "Web Clip.md").write_text(
        "---\ntype: web-clip\n---\n# Clip\n\n## Source\n\nInstruction.\n## Summary\n",
        encoding="utf-8",
    )

    info = collect(vault, note_type="web-clip")

    assert info["template_shape"] == {
        "type": "web-clip",
        "path": "Templates/Web Clip.md",
        "headings": ["Source", "Summary"],
    }
    assert "Instruction." not in str(info["template_shape"])


def test_collect_returns_null_shape_for_missing_selected_template(tmp_path: Path):
    vault = _make_vault(tmp_path)
    (vault / "Templates" / "Web Clip.md").unlink()

    info = collect(vault, note_type="web-clip")

    assert info["template_shape"] is None


def test_compact_omits_note_lists_without_mutating_full_result(tmp_path: Path):
    vault = _make_vault(tmp_path)
    full = collect(vault)

    out = vault_info.compact(full)

    full_index = full["standard_folders"]["20-Learning"]["index"]
    compact_index = out["standard_folders"]["20-Learning"]["index"]
    assert "notes" in full_index
    assert "notes" not in compact_index
    assert compact_index["mode"] == "static"
    assert compact_index["index_file"] == "INDEX.md"
    assert compact_index["can_append"] is True
