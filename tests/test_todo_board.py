"""Write the one personal board. Read-side listing stays in test_list_board."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.audit_vault import audit_vault
from obsidian_kb_skill.scripts.backup_policy import DEFAULT_KEEP_PER_NOTE, STAMP_RE
from obsidian_kb_skill.scripts.board_contract import (
    BOARD_PATH,
    BOARD_TYPE,
    parse_board,
    render_board,
)
from obsidian_kb_skill.scripts.create_note import main as create_main
from obsidian_kb_skill.scripts.list_board import main as list_main
from obsidian_kb_skill.scripts.note_catalog import MAX_NOTE_BYTES
from obsidian_kb_skill.scripts.todo_board import main
from tests.test_error_code_contract import _codes_in
from tests.test_list_board import SAMPLE_LINES, TODAY, vault_of, write_board


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "obsidian_kb_skill" / "scripts"
WRITE_REFERENCE = ROOT / "core" / "references" / "todo-board.md"
LIST_REFERENCE = ROOT / "core" / "retrieval-references" / "list-board.md"
RULES = ROOT / "core" / "references" / "rules-and-errors.md"
CORE = ROOT / "core" / "OBSIDIAN_KB.md"
RETRIEVAL = ROOT / "core" / "RETRIEVAL.md"
WRITE_PHRASES = (
    "记个待办：回复客户",
    "记个待办，今天：回复客户",
    "记个待办，周五：补测试",
    "备忘一下：停车在 B2",
    "把回复客户勾掉",
    "把补测试改到下周三",
    "取消收拾书桌",
)
SUCCESS = (
    "已记在没定日子",
    "已记在今天",
    "已记在之后",
    "已记下备忘",
    "已勾掉",
    "已取消",
    "已改到",
    "另外按日期挪动了：{text} 从{from}到{to}。",
)
WRITE_ONLY_CODES = {
    "board-invalid-text",
    "board-ambiguous",
    "board-no-match",
    "board-duplicate",
    "board-folder-missing",
}


def invoke(capsys, vault: Path, *args: str) -> tuple[int, dict]:
    code = main([str(vault), *args])
    out = capsys.readouterr().out
    return code, json.loads(out) if out.strip() else {}


def capture(vault: Path, *extra: str) -> list[str]:
    return [
        "capture",
        "--kind",
        "todo",
        "--text",
        "收拾书桌",
        "--today",
        TODAY,
        *extra,
    ]


def sections(vault: Path) -> dict[str, list[str]]:
    board = parse_board((vault / BOARD_PATH).read_text(encoding="utf-8"))
    lines: dict[str, list[str]] = {}
    for name, rows in board.rows.items():
        rendered = []
        for row in rows:
            if row.done_mark:
                rendered.append(f"- {row.due} {row.done_mark}：{row.text}")
            elif row.at:
                rendered.append(f"- {row.at} {row.text}")
            elif row.due:
                rendered.append(f"- [ ] {row.text} 📅 {row.due}")
            else:
                rendered.append(f"- [ ] {row.text}")
        lines[name] = rendered
    return lines


def test_text_is_refused_before_the_vault_is_opened(capsys, tmp_path):
    missing = tmp_path / "no-such-vault"
    cases = (
        ("", "empty"),
        ("  回复客户", "whitespace"),
        ("回复客户\n第二行", "newline"),
        ("回复客户 📅 2026-11-13", "due-marker"),
    )
    for text, reason in cases:
        code, payload = invoke(
            capsys,
            missing,
            "capture",
            "--kind",
            "todo",
            "--text",
            text,
            "--today",
            TODAY,
            "--json",
        )
        assert code == 2
        assert payload["error"]["code"] == "board-invalid-text"
        assert payload["error"]["details"] == {"parameter": "--text", "reason": reason}
        assert not missing.exists()


def test_a_due_marker_inside_the_text_is_not_a_date_error(capsys, tmp_path):
    code, payload = invoke(
        capsys,
        tmp_path / "missing",
        "capture",
        "--kind",
        "todo",
        "--text",
        "带 📅 2026-11-31 的正文",
        "--today",
        "周五",
        "--json",
    )
    assert code == 2
    assert payload["error"]["details"]["reason"] == "due-marker"


def test_dates_are_refused_before_the_vault_is_opened(capsys, tmp_path):
    missing = tmp_path / "missing"
    cases = (
        (("capture", "--kind", "todo", "--text", "回复客户", "--today", "周五"), "--today"),
        (("capture", "--kind", "todo", "--text", "回复客户", "--today", TODAY, "--due", "2026-11-31"), "--due"),
        (("capture", "--kind", "memo", "--text", "停车在 B2", "--today", TODAY), "--at"),
        (("capture", "--kind", "memo", "--text", "停车在 B2", "--today", TODAY, "--due", TODAY), "--due"),
        (("capture", "--kind", "todo", "--text", "回复客户", "--today", TODAY, "--at", "14:30"), "--at"),
        (("capture", "--kind", "todo", "--text", "回复客户", "--today", TODAY, "--due", "周五", "--at", "14:30"), "--due"),
        (("reschedule", "--text", "回复客户", "--today", TODAY), "--due"),
        (("tick", "--text", "含勾掉:半角", "--today", TODAY), None),
    )
    for args, parameter in cases:
        code, payload = invoke(capsys, missing, *args, "--json")
        assert code == 2, args
        if parameter is None:
            assert payload["error"]["code"] == "board-invalid-text"
            assert payload["error"]["details"]["reason"] == "round-trip"
        else:
            assert payload["error"]["code"] == "board-invalid-date"
            assert payload["error"]["details"] == {"parameter": parameter}


def test_unknown_flags_have_no_board_code(capsys, tmp_path):
    vault = vault_of(tmp_path)
    with pytest.raises(SystemExit) as caught:
        main([str(vault), "tick", "--text", "回复客户", "--today", TODAY, "--path", "x"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "usage" in captured.err.lower() or "unrecognized" in captured.err.lower()


def test_capture_without_a_due_lands_at_the_end_of_undated(capsys, tmp_path):
    vault = vault_of(tmp_path)
    (vault / "15-Daily").mkdir()
    code, payload = invoke(capsys, vault, *capture(vault, "--apply", "--json"))
    assert code == 0
    assert payload["applied"] is True
    assert payload["section"] == "没定日子"
    assert payload["from_section"] is None
    assert payload["due"] is None
    assert payload["line_text"] == "- [ ] 收拾书桌"
    assert payload["backup"] is None
    text = (vault / BOARD_PATH).read_text(encoding="utf-8")
    assert "📅" not in text
    assert sections(vault)["没定日子"] == ["- [ ] 收拾书桌"]
    assert not (vault / ".obsidian-kb-backups").exists()


def test_a_due_chooses_the_section_and_appends(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ] 回复客户 📅 2026-11-13"], "之后": ["- [ ] 已有 📅 2026-11-20"]})
    code, _ = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "过期",
        "--due", "2026-11-01", "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert sections(vault)["今天"] == [
        "- [ ] 回复客户 📅 2026-11-13",
        "- [ ] 过期 📅 2026-11-01",
    ]
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "以后",
        "--due", "2026-11-21", "--today", TODAY, "--apply", "--json",
    )
    assert payload["section"] == "之后"
    assert sections(vault)["之后"][-1] == "- [ ] 以后 📅 2026-11-21"


def test_a_memo_appends_and_the_same_minute_is_a_duplicate(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"备忘": ["- 2026-11-13 09:00 先记的"]})
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "memo", "--text", "停车在 B2",
        "--today", TODAY, "--at", "14:30", "--apply", "--json",
    )
    assert code == 0
    assert payload["line_text"] == "- 2026-11-13 14:30 停车在 B2"
    assert payload["section"] == "备忘"
    assert sections(vault)["备忘"] == [
        "- 2026-11-13 09:00 先记的",
        "- 2026-11-13 14:30 停车在 B2",
    ]
    before = (vault / BOARD_PATH).read_bytes()
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "memo", "--text", "停车在 B2",
        "--today", TODAY, "--at", "14:30", "--apply", "--json",
    )
    assert code == 2
    assert payload["error"]["code"] == "board-duplicate"
    assert payload["error"]["details"]["at"] == "2026-11-13 14:30"
    assert (vault / BOARD_PATH).read_bytes() == before
    code, _ = invoke(
        capsys, vault, "capture", "--kind", "memo", "--text", "停车在 B2",
        "--today", TODAY, "--at", "15:00", "--apply", "--json",
    )
    assert code == 0
    assert len(sections(vault)["备忘"]) == 3


def test_tick_and_cancel_move_the_row_and_keep_the_old_heading(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(
        vault,
        {
            "今天": ["- [ ]  回复客户  📅 2026-11-13", "- [ ] 补测试 📅 2026-11-20"],
            "没定日子": ["- [ ] 收拾书桌"],
        },
    )
    code, payload = invoke(
        capsys, vault, "tick", "--text", "回复客户", "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["from_section"] == "今天"
    assert payload["section"] == "已完成"
    assert payload["line_text"] == "- 2026-11-13 勾掉：回复客户"
    assert payload["kind"] is None
    body = (vault / BOARD_PATH).read_text(encoding="utf-8")
    assert "- [x]" not in body
    assert "- [ ]  回复客户  📅 2026-11-13" not in body
    assert "- [ ] 补测试 📅 2026-11-20" in body
    assert sections(vault)["已完成"] == ["- 2026-11-13 勾掉：回复客户"]

    code, payload = invoke(
        capsys, vault, "cancel", "--text", "收拾书桌", "--today", TODAY, "--apply", "--json",
    )
    assert payload["line_text"] == "- 2026-11-13 取消：收拾书桌"
    assert "收拾书桌" not in sections(vault)["没定日子"]
    assert sections(vault)["已完成"][-1] == "- 2026-11-13 取消：收拾书桌"


def test_reschedule_of_a_misplaced_row_is_not_a_rebucket(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ] 补测试 📅 2026-11-20"]})
    code, payload = invoke(
        capsys, vault, "reschedule", "--text", "补测试", "--due", "2026-11-18",
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["from_section"] == "今天"
    assert payload["section"] == "之后"
    assert payload["rebucketed"] == []
    assert payload["line_text"] == "- [ ] 补测试 📅 2026-11-18"
    assert sections(vault)["今天"] == []
    assert sections(vault)["之后"] == ["- [ ] 补测试 📅 2026-11-18"]


def test_other_rows_keep_their_spaces_when_one_row_is_named(capsys, tmp_path):
    vault = vault_of(tmp_path)
    spaced = "- [ ]  补测试  📅 2026-11-20"
    write_board(vault, {"今天": ["- [ ] 回复客户 📅 2026-11-13", spaced]})
    code, payload = invoke(
        capsys, vault, "tick", "--text", "回复客户", "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["rebucketed"] == [
        {"text": " 补测试 ", "due": "2026-11-20", "from": "今天", "to": "之后"}
    ]
    assert spaced in (vault / BOARD_PATH).read_text(encoding="utf-8")


def test_the_same_open_text_is_ambiguous_and_a_finished_row_is_not(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(
        vault,
        {
            "今天": ["- [ ] 回复客户 📅 2026-11-13"],
            "没定日子": ["- [ ] 回复客户"],
            "已完成": ["- 2026-11-12 勾掉：买牛奶"],
        },
    )
    before = (vault / BOARD_PATH).read_bytes()
    code, payload = invoke(
        capsys, vault, "tick", "--text", "回复客户", "--today", TODAY, "--apply", "--json",
    )
    assert code == 2
    assert payload["error"]["code"] == "board-ambiguous"
    assert len(payload["error"]["details"]["candidates"]) == 2
    assert (vault / BOARD_PATH).read_bytes() == before
    assert not (vault / ".obsidian-kb-backups").exists()

    code, payload = invoke(
        capsys, vault, "tick", "--text", "买牛奶", "--today", TODAY, "--json",
    )
    assert payload["error"]["code"] == "board-no-match"
    assert payload["error"]["details"] == {"text": "买牛奶"}
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "买牛奶",
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert "- [ ] 买牛奶" in sections(vault)["没定日子"]


def test_a_substring_does_not_match(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": [SAMPLE_LINES[0]]})
    before = (vault / BOARD_PATH).read_bytes()
    code, payload = invoke(
        capsys, vault, "tick", "--text", "回复", "--today", TODAY, "--json",
    )
    assert payload["error"]["code"] == "board-no-match"
    assert (vault / BOARD_PATH).read_bytes() == before


def test_cancel_does_not_move_a_memo(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"备忘": [SAMPLE_LINES[3]]})
    code, payload = invoke(
        capsys, vault, "cancel", "--text", "停车在 B2", "--today", TODAY, "--apply", "--json",
    )
    assert code == 2
    assert payload["error"]["code"] == "board-no-match"
    assert sections(vault)["备忘"] == [SAMPLE_LINES[3]]
    assert sections(vault)["已完成"] == []


def test_dry_run_reports_the_move_and_does_not_touch_the_disk(capsys, tmp_path, monkeypatch):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ] 补测试 📅 2026-11-20"]})
    before = (vault / BOARD_PATH).read_bytes()

    def boom(*_args, **_kwargs):
        raise AssertionError("backup_note")

    monkeypatch.setattr(
        "obsidian_kb_skill.scripts.todo_board.backup_note", boom
    )
    code, payload = invoke(capsys, vault, *capture(vault, "--json"))
    assert code == 0
    assert payload["applied"] is False
    assert payload["backup"] is None
    assert payload["backup_cleanup"] is None
    assert payload["rebucketed"] == [
        {"text": "补测试", "due": "2026-11-20", "from": "今天", "to": "之后"}
    ]
    assert (vault / BOARD_PATH).read_bytes() == before

    bare = vault_of(tmp_path / "bare")
    code, payload = invoke(capsys, bare, *capture(bare, "--json"))
    assert code == 0
    assert payload["applied"] is False
    assert not (bare / "15-Daily").exists()


def test_the_first_create_has_no_backup_and_the_second_apply_does(capsys, tmp_path):
    vault = vault_of(tmp_path)
    (vault / "15-Daily").mkdir()
    code, first = invoke(capsys, vault, *capture(vault, "--apply", "--json"))
    assert code == 0
    assert first["existed_before"] is False
    assert first["backup"] is None
    assert not (vault / ".obsidian-kb-backups").exists()
    code, second = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "回复客户",
        "--due", TODAY, "--today", TODAY, "--apply", "--json",
    )
    assert second["applied"] is True
    assert second["existed_before"] is True
    assert second["backup"].endswith("15-Daily/待办.md")
    stamp = Path(second["backup"]).parts[1]
    assert STAMP_RE.fullmatch(stamp)
    assert second["backup_cleanup"]["keep_per_note"] == DEFAULT_KEEP_PER_NOTE


def test_an_unchanged_apply_does_not_write_or_back_up(capsys, tmp_path, monkeypatch):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ] 回复客户 📅 2026-11-13"]})
    before = (vault / BOARD_PATH).read_bytes()

    def boom(*_args, **_kwargs):
        raise AssertionError("backup_note")

    monkeypatch.setattr("obsidian_kb_skill.scripts.todo_board.backup_note", boom)
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("write")),
    )
    code, payload = invoke(
        capsys, vault, "reschedule", "--text", "回复客户", "--due", TODAY,
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["applied"] is True
    assert payload["backup"] is None
    assert (vault / BOARD_PATH).read_bytes() == before


def test_oversize_refuses_before_backup_including_the_first_create(capsys, tmp_path):
    one = len(render_board(TODAY, {"没定日子": ["- [ ] a"]}).encode("utf-8"))
    exact = "a" * (MAX_NOTE_BYTES - (one - 1))
    assert len(render_board(TODAY, {"没定日子": [f"- [ ] {exact}"]}).encode()) == MAX_NOTE_BYTES

    vault = vault_of(tmp_path)
    (vault / "15-Daily").mkdir()
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", exact + "a",
        "--today", TODAY, "--json",
    )
    assert code == 2
    assert payload["error"] == {
        "code": "board-malformed",
        "message": "待办.md 超过大小上限，我没有改。",
        "details": {"reason": "size"},
    }
    code, _ = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", exact + "a",
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 2
    assert not (vault / BOARD_PATH).exists()
    assert not (vault / ".obsidian-kb-backups").exists()

    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", exact,
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert (vault / BOARD_PATH).stat().st_size == MAX_NOTE_BYTES
    before = (vault / BOARD_PATH).read_bytes()
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "b",
        "--today", TODAY, "--apply", "--json",
    )
    assert payload["error"]["details"] == {"reason": "size"}
    assert (vault / BOARD_PATH).read_bytes() == before
    assert not (vault / ".obsidian-kb-backups").exists()

    huge = vault_of(tmp_path / "huge")
    path = huge / BOARD_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (MAX_NOTE_BYTES + 1))
    code, payload = invoke(capsys, huge, *capture(huge, "--apply", "--json"))
    assert payload["error"]["details"] == {"reason": "size"}
    listed = list_main([str(huge), "--today", TODAY, "--view", "todos", "--json"])
    listed_payload = json.loads(capsys.readouterr().out)
    assert listed == 2
    assert listed_payload["error"]["details"] == {"reason": "size"}


def test_backup_cleanup_keeps_only_this_board(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"没定日子": ["- [ ] 收拾书桌"]})
    original = (vault / BOARD_PATH).read_bytes()
    other = vault / "10-Work" / "其他.md"
    other.parent.mkdir()
    other.write_bytes(b"other-live")
    root = vault / ".obsidian-kb-backups"
    for stamp, payload in (
        ("2026-11-01-010101", original),
        ("2026-11-02-010101", original),
    ):
        path = root / stamp / BOARD_PATH
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
    for stamp, payload in (
        ("2026-11-03-010101", b"other-a"),
        ("2026-11-04-010101", b"other-b"),
    ):
        path = root / stamp / "10-Work" / "其他.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
    unknown = root / "2026-11-01" / "note.md"
    unknown.parent.mkdir()
    unknown.write_bytes(b"unknown")
    loose = root / "2026-11-08-010101" / "readme.txt"
    loose.parent.mkdir(parents=True)
    loose.write_bytes(b"loose")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    link = root / "2026-11-09-010101"
    link.symlink_to(outside, target_is_directory=True)

    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "回复客户",
        "--due", TODAY, "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["applied"] is True
    backup = vault / payload["backup"]
    assert backup.read_bytes() == original
    assert payload["backup_cleanup"]["keep_per_note"] == DEFAULT_KEEP_PER_NOTE
    assert payload["backup_cleanup"]["deleted"] == 2
    assert payload["backup_cleanup"]["warnings"] == []
    survivors = [
        path
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name == "待办.md"
    ]
    assert survivors == [backup]
    assert other.read_bytes() == b"other-live"
    assert (root / "2026-11-03-010101" / "10-Work" / "其他.md").read_bytes() == b"other-a"
    assert (root / "2026-11-04-010101" / "10-Work" / "其他.md").read_bytes() == b"other-b"
    assert unknown.read_bytes() == b"unknown"
    assert loose.read_bytes() == b"loose"
    assert link.is_symlink()
    assert (outside / "secret").read_bytes() == b"secret"


def test_cleanup_failures_keep_the_written_note(capsys, tmp_path, monkeypatch):
    vault = vault_of(tmp_path)
    write_board(vault, {"没定日子": ["- [ ] 收拾书桌"]})
    old = vault / ".obsidian-kb-backups" / "2026-11-01-010101" / BOARD_PATH
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")

    def deny(self, *args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(Path, "unlink", deny)
    code, payload = invoke(
        capsys, vault, "tick", "--text", "收拾书桌", "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["applied"] is True
    assert payload["backup_cleanup"]["warnings"]
    assert "勾掉：收拾书桌" in (vault / BOARD_PATH).read_text(encoding="utf-8")
    assert old.read_bytes() == b"old"

    def fail_scan(*_args, **_kwargs):
        raise OSError("scan")

    monkeypatch.setattr("obsidian_kb_skill.scripts.todo_board.os.scandir", fail_scan)
    code, payload = invoke(
        capsys, vault, "capture", "--kind", "todo", "--text", "再记一条",
        "--today", TODAY, "--apply", "--json",
    )
    assert code == 0
    assert payload["applied"] is True
    assert payload["backup_cleanup"]["warnings"]
    assert "再记一条" in (vault / BOARD_PATH).read_text(encoding="utf-8")


def test_a_missing_parent_is_not_created_and_list_does_not_use_that_code(capsys, tmp_path):
    vault = vault_of(tmp_path)
    code, payload = invoke(capsys, vault, *capture(vault, "--apply", "--json"))
    assert code == 2
    assert payload["error"]["code"] == "board-folder-missing"
    assert payload["error"]["details"] == {"path": "15-Daily"}
    assert not (vault / "15-Daily").exists()
    listed = list_main([str(vault), "--today", TODAY, "--view", "todos", "--json"])
    body = capsys.readouterr().out
    assert listed == 0
    assert "board-folder-missing" not in body


def test_path_and_backup_failures_use_the_first_envelope(capsys, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    vault = vault_of(tmp_path)
    daily = vault / "15-Daily"
    daily.symlink_to(outside, target_is_directory=True)
    code, payload = invoke(capsys, vault, *capture(vault, "--apply", "--json"))
    assert code == 3
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert payload["command"] is None
    assert not (outside / "待办.md").exists()

    real = vault_of(tmp_path / "real")
    target = outside / "待办.md"
    target.write_bytes(b"secret")
    (real / "15-Daily").mkdir()
    (real / BOARD_PATH).symlink_to(target)
    code, payload = invoke(capsys, real, *capture(real, "--apply", "--json"))
    assert code == 3
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert target.read_bytes() == b"secret"

    backed = vault_of(tmp_path / "backed")
    write_board(backed, {"没定日子": ["- [ ] 收拾书桌"]})
    before = (backed / BOARD_PATH).read_bytes()
    (backed / ".obsidian-kb-backups").symlink_to(outside, target_is_directory=True)
    code, payload = invoke(
        capsys, backed, "tick", "--text", "收拾书桌", "--today", TODAY, "--apply", "--json",
    )
    assert code == 3
    assert payload["schema_version"] == "1.0"
    assert payload["command"] is None
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert (backed / BOARD_PATH).read_bytes() == before

    def explode(*_args, **_kwargs):
        raise OSError("disk")

    monkeypatch.setattr("obsidian_kb_skill.scripts.todo_board.backup_note", explode)
    plain = vault_of(tmp_path / "plain")
    write_board(plain, {"没定日子": ["- [ ] 收拾书桌"]})
    before = (plain / BOARD_PATH).read_bytes()
    code, payload = invoke(
        capsys, plain, "tick", "--text", "收拾书桌", "--today", TODAY, "--apply", "--json",
    )
    assert code == 3
    assert payload["command"] == "todo-board"
    assert payload["error"]["code"] == "BACKUP_FAILED"
    assert payload["error"]["message"] == "backup failed: disk"
    assert (plain / BOARD_PATH).read_bytes() == before

    code = main([
        str(plain), "tick", "--text", "收拾书桌", "--today", TODAY, "--apply",
    ])
    captured = capsys.readouterr()
    assert code == 3
    assert captured.out.strip() == ""
    assert captured.err == "error: backup failed: disk\n"
    assert (plain / BOARD_PATH).read_bytes() == before

    code, payload = invoke(
        capsys, tmp_path / "absent", "tick", "--text", "回复客户", "--today", TODAY, "--json",
    )
    assert code == 3
    assert payload["error"]["code"] == "INVALID_VAULT_ROOT"


def test_the_writer_does_not_read_the_clock_or_prune_the_vault():
    source = (SCRIPTS / "todo_board.py").read_text(encoding="utf-8")
    assert "prune_backups" not in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"now", "utcnow", "today"}


def test_create_note_refuses_the_board_type_before_it_builds(capsys, tmp_path):
    vault = vault_of(tmp_path)
    code = create_main([
        str(vault), "--type", BOARD_TYPE, "--title", "待办",
        "--folder", "15-Daily", "--apply", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["error"]["code"] == "board-fixed-path"
    assert payload["error"]["message"] == "待办.md 由看板命令维护，这次没有建笔记。"
    assert payload["error"]["details"]["type"] == BOARD_TYPE
    assert list(vault.rglob("*.md")) == []


def test_the_audit_does_not_call_the_board_disconnected_or_an_orphan(tmp_path):
    indexed = vault_of(tmp_path / "indexed")
    write_board(indexed, {"没定日子": ["- [ ] 收拾书桌"]})
    (indexed / "15-Daily" / "目录.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n# 目录\n",
        encoding="utf-8",
    )
    alone = vault_of(tmp_path / "alone")
    write_board(alone, {"没定日子": ["- [ ] 收拾书桌"]})
    for vault in (indexed, alone):
        codes = {
            finding.code
            for finding in audit_vault(vault)
            if finding.path == BOARD_PATH
        }
        assert "disconnected-note" not in codes
        assert "orphan-note" not in codes
        assert "invalid-type" not in codes


def test_the_retrieval_runner_points_todo_board_at_the_write_skill(tmp_path):
    runner = ROOT / "skills" / "obsidian-knowledge-retrieval" / "scripts" / "run_helper.py"
    result = subprocess.run(
        [sys.executable, str(runner), "todo-board"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "obsidian-knowledge-base" in result.stderr


def test_write_utterances_are_routed_by_the_write_sentence():
    """Row 82. The seven write phrases are not a retrieval command."""
    text = CORE.read_text(encoding="utf-8")
    retrieval = RETRIEVAL.read_text(encoding="utf-8")
    assert len(text.splitlines()) == 44
    for phrase in WRITE_PHRASES:
        assert phrase in text
        assert phrase not in retrieval
    assert "todo-board <vault>" in text
    assert "todo-board <vault> --apply --json" not in text
    assert "obsidian-knowledge-retrieval" in text
    assert "列一下我现在的代办" in text
    assert "列一下备忘" in text


def test_write_spoken_contract_matches_the_board_parser():
    """Row 83. The write sentences live on the write reference."""
    text = WRITE_REFERENCE.read_text(encoding="utf-8")
    listing = LIST_REFERENCE.read_text(encoding="utf-8")
    for sentence in SUCCESS:
        assert sentence in text, sentence
        assert sentence not in listing, sentence
        assert sentence not in CORE.read_text(encoding="utf-8")
    for key in ("applied", "section", "from_section", "due", "rebucketed", "line_text"):
        assert key in text
    parse_board(
        render_board(
            TODAY,
            {
                "今天": [SAMPLE_LINES[0]],
                "之后": [SAMPLE_LINES[1]],
                "没定日子": [SAMPLE_LINES[2]],
                "备忘": [SAMPLE_LINES[3]],
                "已完成": [SAMPLE_LINES[4], SAMPLE_LINES[5]],
            },
        )
    )


def test_the_board_writer_is_not_in_the_retrieval_bundle():
    """Row 85. The writer is a write-skill module."""
    build_text = (ROOT / "build.py").read_text(encoding="utf-8")
    block = build_text.split("RETRIEVAL_HELPER_FILES = (", 1)[1].split("\n)", 1)[0]
    assert "todo_board.py" not in block
    retrieval = ROOT / "skills" / "obsidian-knowledge-retrieval"
    assert list(retrieval.rglob("todo_board.py")) == []
    runner = (
        ROOT / "skills" / "obsidian-knowledge-base" / "scripts" / "run_helper.py"
    ).read_text(encoding="utf-8")
    helpers = runner.split("HELPERS = {", 1)[1].split("\n}", 1)[0]
    assert "list-board" not in helpers
    assert "todo-board" in helpers


def test_board_type_is_imported_not_inlined():
    """Row 86. The type string has one owner."""
    for name in (
        "audit_vault.py",
        "create_note.py",
        "note_catalog.py",
        "review_open_loops.py",
        "list_board.py",
    ):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert '"todo-board"' not in text, name
        assert "'todo-board'" not in text, name
    for name in ("audit_vault.py", "create_note.py", "note_catalog.py"):
        assert "BOARD_TYPE" in (SCRIPTS / name).read_text(encoding="utf-8")


def test_board_code_intersection_is_documented_on_both_sides():
    """Row 87. Shared codes are in both references. The rest stay on one side."""
    list_codes, _ = _codes_in(SCRIPTS / "list_board.py")
    write_codes, _ = _codes_in(SCRIPTS / "todo_board.py")
    create_codes, _ = _codes_in(SCRIPTS / "create_note.py")
    assert list_codes & write_codes == {"board-malformed", "board-invalid-date"}
    listing = LIST_REFERENCE.read_text(encoding="utf-8")
    rules = RULES.read_text(encoding="utf-8")
    write_reference = WRITE_REFERENCE.read_text(encoding="utf-8")
    for code in list_codes & write_codes:
        assert f"`{code}`" in listing
        assert f"`{code}`" in rules
    assert write_codes - list_codes - {"BACKUP_FAILED"} == WRITE_ONLY_CODES
    for code in WRITE_ONLY_CODES:
        assert f"`{code}`" in rules
        assert f"`{code}`" not in listing
    assert "`board-invalid-view`" in listing
    assert "`board-invalid-view`" not in rules
    assert "`board-invalid-view`" not in write_reference
    assert "board-fixed-path" in create_codes
    assert "board-fixed-path" not in write_codes
    assert "`board-fixed-path`" in rules
    owners = [
        path.name
        for path in SCRIPTS.glob("*.py")
        if "board-fixed-path" in path.read_text(encoding="utf-8")
    ]
    assert owners == ["create_note.py"]


def test_the_write_descriptions_name_the_personal_board_on_one_line():
    header = (ROOT / "skills" / "obsidian-knowledge-base" / "header.md").read_text(
        encoding="utf-8"
    )
    cursor = (ROOT / "platforms" / "cursor" / "header.md").read_text(encoding="utf-8")
    for text in (header, cursor):
        description = next(
            line for line in text.splitlines() if line.startswith("description:")
        )
        assert description.startswith('description: "Use when ')
        assert description.endswith('"')
        for phrase in ("记个待办", "备忘一下", "勾掉", "改到", "取消", "列一下我现在的代办"):
            assert phrase in description
    claude = (ROOT / "platforms" / "claude-code" / "header.md").read_text(encoding="utf-8")
    trigger = next(line for line in claude.splitlines() if line.startswith("**When to use**"))
    assert "记个待办" in trigger
    assert 'description: "Use when' not in claude
    codex = (ROOT / "platforms" / "codex" / "header.md").read_text(encoding="utf-8")
    codex_trigger = next(line for line in codex.splitlines() if line.startswith("**Trigger**"))
    assert "记个待办" in codex_trigger
    assert "Compatibility adapter" in codex
    assert "skills/obsidian-knowledge-base/SKILL.md" in codex
    prompt = (
        ROOT / "skills" / "obsidian-knowledge-base" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "personal todo" in prompt
    assert "Use $obsidian-knowledge-base to evaluate what is worth capturing" in prompt
