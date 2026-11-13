"""Tests for task lifecycle mutation CLI (complete-loop)."""
from __future__ import annotations

from pathlib import Path
import pytest

from obsidian_kb_skill.scripts.backup_policy import STAMP_RE
from obsidian_kb_skill.scripts.complete_loop import complete_loop
from obsidian_kb_skill.scripts.vault_paths import PathOutsideVaultError


def init_vault_with_note(tmp_path: Path, filename: str, content: str) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir(parents=True)
    note_path = vault / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return vault


def test_complete_loop_ticks_task_with_date(tmp_path):
    vault = init_vault_with_note(
        tmp_path,
        "15-Daily/2026-11-13.md",
        "# 2026-11-13\n\n## 待办事项\n\n- [ ] 买牛奶\n",
    )

    result = complete_loop(
        vault,
        path="15-Daily/2026-11-13.md",
        line=5,
        action="tick",
        date="2026-11-13",
        apply=True,
    )

    assert result["ok"] is True
    assert result["applied"] is True
    assert "- [x] 买牛奶 ✅ 2026-11-13" in result["after"]

    # Verify disk
    content = (vault / "15-Daily/2026-11-13.md").read_text(encoding="utf-8")
    assert "- [x] 买牛奶 ✅ 2026-11-13" in content


def test_complete_loop_cancels_task(tmp_path):
    vault = init_vault_with_note(
        tmp_path,
        "tasks.md",
        "## 待办事项\n\n- [ ] 无效需求\n",
    )

    result = complete_loop(
        vault,
        path="tasks.md",
        line=3,
        action="cancel",
        date="2026-11-13",
        apply=True,
    )

    assert result["ok"] is True
    assert "- [-] 无效需求 ⛔ 2026-11-13" in result["after"]
    content = (vault / "tasks.md").read_text(encoding="utf-8")
    assert "- [-] 无效需求 ⛔ 2026-11-13" in content


def test_complete_loop_rejects_a_path_outside_the_vault(tmp_path):
    vault = init_vault_with_note(tmp_path, "tasks.md", "- [ ] 库内\n")
    outside = tmp_path / "secret.md"
    outside.write_text("- [ ] 库外\n", encoding="utf-8")

    with pytest.raises(PathOutsideVaultError):
        complete_loop(vault, path="../secret.md", line=1, action="tick", apply=True)

    assert "[x]" not in outside.read_text(encoding="utf-8")


def test_complete_loop_backup_uses_a_timestamp_directory(tmp_path, monkeypatch):
    from obsidian_kb_skill.scripts import update_note
    from obsidian_kb_skill.scripts.backup_policy import BackupPolicy

    vault = init_vault_with_note(tmp_path, "tasks.md", "- [ ] 买牛奶\n")
    monkeypatch.setattr(update_note, "_backup_timestamp", lambda: "2026-11-13-120000")
    monkeypatch.setattr(
        "obsidian_kb_skill.scripts.complete_loop.load_backup_policy",
        lambda home=None: BackupPolicy(1, True),
    )

    complete_loop(vault, path="tasks.md", line=1, action="tick", date="2026-11-13", apply=True)

    stamps = [path.name for path in (vault / ".obsidian-kb-backups").iterdir() if path.is_dir()]
    assert stamps == ["2026-11-13-120000"]
    assert STAMP_RE.fullmatch(stamps[0])
    backup = next((vault / ".obsidian-kb-backups").rglob("*.md"))
    assert backup.read_text(encoding="utf-8") == "- [ ] 买牛奶\n"


def test_complete_loop_postpones_task(tmp_path):
    vault = init_vault_with_note(
        tmp_path,
        "tasks.md",
        "## 待办事项\n\n- [ ] 顺延任务 📅 2026-11-13\n",
    )

    result = complete_loop(
        vault,
        path="tasks.md",
        line=3,
        action="postpone",
        date="2026-11-20",
        apply=True,
    )

    assert result["ok"] is True
    assert "📅 2026-11-20" in result["after"]
    assert "2026-11-13" not in result["after"]


def test_complete_loop_validates_expected_text(tmp_path):
    vault = init_vault_with_note(
        tmp_path,
        "tasks.md",
        "## 待办事项\n\n- [ ] 买牛奶\n",
    )

    with pytest.raises(ValueError, match="does not match expected"):
        complete_loop(
            vault,
            path="tasks.md",
            line=3,
            expected_text="买咖啡",
            action="tick",
            apply=True,
        )


def test_complete_loop_dry_run_leaves_file_unchanged(tmp_path):
    vault = init_vault_with_note(
        tmp_path,
        "tasks.md",
        "## 待办事项\n\n- [ ] 原有未完成\n",
    )

    result = complete_loop(
        vault,
        path="tasks.md",
        line=3,
        action="tick",
        apply=False,
    )

    assert result["ok"] is True
    assert result["applied"] is False
    content = (vault / "tasks.md").read_text(encoding="utf-8")
    assert "- [ ] 原有未完成" in content


def test_complete_loop_cli_json(tmp_path, capsys):
    from obsidian_kb_skill.scripts.complete_loop import main
    import json

    vault = init_vault_with_note(
        tmp_path,
        "tasks.md",
        "## 待办事项\n\n- [ ] 打电话确认\n",
    )

    ret = main([
        str(vault),
        "--path", "tasks.md",
        "--line", "3",
        "--action", "tick",
        "--date", "2026-11-13",
        "--apply",
        "--json",
    ])
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["applied"] is True
    assert "- [x] 打电话确认 ✅ 2026-11-13" in data["after"]

