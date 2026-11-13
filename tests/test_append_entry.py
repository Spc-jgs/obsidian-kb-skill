"""Tests for atomic entry append CLI and helper."""
from __future__ import annotations

from pathlib import Path
import pytest

from obsidian_kb_skill.scripts.append_entry import AppendRejected, append_entry
from obsidian_kb_skill.scripts.backup_policy import STAMP_RE
from obsidian_kb_skill.scripts.vault_paths import PathOutsideVaultError


def init_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir(parents=True)
    return vault


def test_append_entry_to_existing_daily_note_under_section(tmp_path):
    vault = init_vault(tmp_path)
    daily_dir = vault / "15-Daily"
    daily_dir.mkdir(parents=True)
    daily_file = daily_dir / "2026-11-13.md"
    daily_file.write_text(
        "---\ndate: \"2026-11-13\"\ntype: daily-note\n---\n\n"
        "# 2026-11-13 日记\n\n"
        "## 今日焦点\n\n"
        "重要事项\n\n"
        "## 待办事项\n\n"
        "- [ ] 原有待办\n\n"
        "## 今日复盘\n\n"
        "复盘内容\n",
        encoding="utf-8",
    )

    result = append_entry(
        vault,
        target="daily",
        date="2026-11-13",
        section="待办事项",
        entry="- [ ] 新待办",
        apply=True,
    )

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["created_file"] is False
    assert result["path"] == "15-Daily/2026-11-13.md"
    assert result["section"] == "待办事项"

    # Verify content
    content = daily_file.read_text(encoding="utf-8")
    assert "- [ ] 原有待办\n- [ ] 新待办" in content
    assert "## 今日复盘\n\n复盘内容" in content
    # No duplicate -2 file
    assert not (daily_dir / "2026-11-13-2.md").exists()


def test_append_entry_initializes_missing_daily_note(tmp_path):
    vault = init_vault(tmp_path)
    result = append_entry(
        vault,
        target="daily",
        date="2026-11-13",
        section="待办事项",
        entry="- [ ] 第一个待办",
        apply=True,
    )

    assert result["ok"] is True
    assert result["created_file"] is True
    daily_file = vault / "15-Daily" / "2026-11-13.md"
    assert daily_file.is_file()
    content = daily_file.read_text(encoding="utf-8")
    assert "type: daily-note" in content
    assert "- [ ] 第一个待办" in content


def test_append_entry_dry_run_does_not_mutate(tmp_path):
    vault = init_vault(tmp_path)
    daily_dir = vault / "15-Daily"
    daily_dir.mkdir(parents=True)
    daily_file = daily_dir / "2026-11-13.md"
    daily_file.write_text("## 待办事项\n\n- [ ] 原有\n", encoding="utf-8")

    result = append_entry(
        vault,
        target="daily",
        date="2026-11-13",
        section="待办事项",
        entry="- [ ] 不该写入",
        apply=False,
    )

    assert result["ok"] is True
    assert result["applied"] is False
    content = daily_file.read_text(encoding="utf-8")
    assert "不该写入" not in content


def test_append_entry_formats_todo_and_timestamp(tmp_path):
    vault = init_vault(tmp_path)
    daily_dir = vault / "15-Daily"
    daily_dir.mkdir(parents=True)
    daily_file = daily_dir / "2026-11-13.md"
    daily_file.write_text("## 今日记录\n\n## 待办事项\n", encoding="utf-8")

    # Todo formatting
    append_entry(
        vault,
        target="daily",
        date="2026-11-13",
        section="待办事项",
        entry="买猫粮",
        is_todo=True,
        apply=True,
    )
    # Timestamp formatting
    append_entry(
        vault,
        target="daily",
        date="2026-11-13",
        section="今日记录",
        entry="停车在B2区",
        timestamp="14:30",
        apply=True,
    )

    content = daily_file.read_text(encoding="utf-8")
    assert "- [ ] 买猫粮" in content
    assert "- 14:30 停车在B2区" in content


def test_append_entry_to_arbitrary_file(tmp_path):
    vault = init_vault(tmp_path)
    proj_file = vault / "40-Projects" / "ai.md"
    proj_file.parent.mkdir(parents=True)
    proj_file.write_text("## 下一步行动\n\n- [ ] 既有项目任务\n", encoding="utf-8")

    result = append_entry(
        vault,
        file="40-Projects/ai.md",
        section="下一步行动",
        entry="- [ ] 项目新任务",
        apply=True,
    )

    assert result["ok"] is True
    assert "- [ ] 项目新任务" in proj_file.read_text(encoding="utf-8")


def test_append_entry_cli_invocation_json(tmp_path, capsys):
    from obsidian_kb_skill.scripts.append_entry import main

    vault = init_vault(tmp_path)
    ret = main([
        str(vault),
        "--target", "daily",
        "--date", "2026-11-13",
        "--entry", "买牛奶",
        "--todo",
        "--apply",
        "--json",
    ])
    assert ret == 0
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["applied"] is True
    assert data["entry"] == "- [ ] 买牛奶"
    assert (vault / "15-Daily" / "2026-11-13.md").is_file()


def test_missing_section_fails_and_does_not_create_one(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "40-Projects" / "ai.md"
    note.parent.mkdir(parents=True)
    original = "## 下一步行动\n\n- [ ] 既有\n"
    note.write_text(original, encoding="utf-8")

    with pytest.raises(AppendRejected, match="does not exist"):
        append_entry(
            vault,
            file="40-Projects/ai.md",
            section="待办事项",
            entry="- [ ] 不该出现",
            apply=True,
        )

    assert note.read_text(encoding="utf-8") == original
    assert "## 待办事项" not in original


def test_duplicate_heading_is_ambiguous(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "note.md"
    original = "## 待办事项\n\n- [ ] 甲\n\n## 待办事项\n\n- [ ] 乙\n"
    note.write_text(original, encoding="utf-8")

    with pytest.raises(AppendRejected, match="ambiguous"):
        append_entry(vault, file="note.md", section="待办事项", entry="- [ ] 丙", apply=True)

    assert note.read_text(encoding="utf-8") == original


def test_identical_entry_is_not_written_twice(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "15-Daily" / "2026-11-13.md"
    note.parent.mkdir(parents=True)
    note.write_text("## 待办事项\n\n- [ ] 买牛奶\n", encoding="utf-8")

    result = append_entry(
        vault,
        file="15-Daily/2026-11-13.md",
        section="待办事项",
        entry="- [ ] 买牛奶",
        apply=True,
    )

    assert result["duplicate"] is True
    assert result["applied"] is False
    assert note.read_text(encoding="utf-8").count("- [ ] 买牛奶") == 1
    assert not (vault / ".obsidian-kb-backups").exists()


def test_memo_without_todo_flag_defaults_to_the_record_section(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "15-Daily" / "2026-11-13.md"
    note.parent.mkdir(parents=True)
    note.write_text("## 今日记录\n\n## 待办事项\n\n- [ ] 已有\n", encoding="utf-8")

    result = append_entry(
        vault,
        file="15-Daily/2026-11-13.md",
        entry="停车在B2区",
        timestamp="14:30",
        apply=True,
    )

    content = note.read_text(encoding="utf-8")
    record, tasks = content.split("## 待办事项", 1)
    assert result["section"] == "今日记录"
    assert "- 14:30 停车在B2区" in record
    assert "- 14:30 停车在B2区" not in tasks


def test_synonym_heading_receives_the_entry_when_the_canonical_one_is_absent(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "note.md"
    note.write_text("## 今日待办\n\n- [ ] 既有\n", encoding="utf-8")

    result = append_entry(
        vault,
        file="note.md",
        section="待办事项",
        entry="- [ ] 新任务",
        apply=True,
    )

    content = note.read_text(encoding="utf-8")
    assert result["matched_heading"] == "今日待办"
    assert "## 今日待办\n\n- [ ] 既有\n- [ ] 新任务" in content


def test_two_different_synonym_headings_are_ambiguous(tmp_path):
    vault = init_vault(tmp_path)
    note = vault / "note.md"
    original = "## 今日待办\n\n- [ ] 甲\n\n## TODO\n\n- [ ] 乙\n"
    note.write_text(original, encoding="utf-8")

    with pytest.raises(AppendRejected, match="ambiguous"):
        append_entry(vault, file="note.md", section="待办事项", entry="- [ ] 丙", apply=True)

    assert note.read_text(encoding="utf-8") == original


def test_path_outside_the_vault_is_rejected(tmp_path):
    vault = init_vault(tmp_path)
    outside = tmp_path / "secret.md"
    outside.write_text("## 待办事项\n\n- [ ] 原有\n", encoding="utf-8")

    with pytest.raises(PathOutsideVaultError):
        append_entry(
            vault,
            file="../secret.md",
            section="待办事项",
            entry="- [ ] 不该写出库",
            apply=True,
        )

    assert "不该写出库" not in outside.read_text(encoding="utf-8")


def test_apply_keeps_a_timestamped_backup_of_the_previous_bytes(tmp_path, monkeypatch):
    from obsidian_kb_skill.scripts import update_note
    from obsidian_kb_skill.scripts.backup_policy import BackupPolicy

    vault = init_vault(tmp_path)
    note = vault / "note.md"
    original = "## 待办事项\n\n- [ ] 原有\n"
    note.write_text(original, encoding="utf-8")
    monkeypatch.setattr(update_note, "_backup_timestamp", lambda: "2026-11-13-120000")
    monkeypatch.setattr(
        "obsidian_kb_skill.scripts.append_entry.load_backup_policy",
        lambda home=None: BackupPolicy(1, True),
    )

    append_entry(vault, file="note.md", section="待办事项", entry="- [ ] 第一次", apply=True)
    append_entry(vault, file="note.md", section="待办事项", entry="- [ ] 第二次", apply=True)

    root = vault / ".obsidian-kb-backups"
    stamps = [path.name for path in root.iterdir() if path.is_dir()]
    assert stamps
    assert all(STAMP_RE.fullmatch(name) for name in stamps)
    assert "2026-11-13" not in stamps
    blobs = [path.read_text(encoding="utf-8") for path in root.rglob("*.md")]
    assert any(blob == "## 待办事项\n\n- [ ] 原有\n- [ ] 第一次\n" or "- [ ] 第一次" in blob and "- [ ] 第二次" not in blob for blob in blobs)
    assert "- [ ] 第二次" in note.read_text(encoding="utf-8")

