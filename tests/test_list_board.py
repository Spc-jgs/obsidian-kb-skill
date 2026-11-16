"""The personal board is one note, and listing it is not the open-loop queue.

These tests are the read side. The write utterances and the writer are
covered in ``tests/test_todo_board.py``. Row 80 also reads ``todo-board.md``
for the same five headings and six sample lines.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.board_contract import (
    BOARD_PATH,
    BOARD_SECTIONS,
    parse_board,
    render_board,
)
from obsidian_kb_skill.scripts.list_board import main
from obsidian_kb_skill.scripts.note_catalog import MAX_NOTE_BYTES
from obsidian_kb_skill.scripts.review_open_loops import review_open_loops
from tests.test_error_code_contract import _codes_in


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "obsidian_kb_skill" / "scripts"
REFERENCE = ROOT / "core" / "retrieval-references" / "list-board.md"
WRITE_REFERENCE = ROOT / "core" / "references" / "todo-board.md"
RETRIEVAL = ROOT / "core" / "RETRIEVAL.md"
TODAY = "2026-11-13"

# The six lines the reference must show, in section order. ``已完成`` has two
# because ``勾掉：`` and ``取消：`` are different rows. ``勾掉：`` is a line
# marker; the spoken success sentence is a different string and is forbidden.
SAMPLE_LINES = (
    "- [ ] 回复客户 📅 2026-11-13",
    "- [ ] 补测试 📅 2026-11-20",
    "- [ ] 收拾书桌",
    "- 2026-11-13 14:30 停车在 B2",
    "- 2026-11-12 勾掉：买牛奶",
    "- 2026-11-13 取消：收拾书桌",
)
WRITE_SUCCESSES = ("已记在没定日子", "已勾掉", "已改到")


def vault_of(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def write_board(vault: Path, sections: dict[str, list[str]], today: str = TODAY) -> Path:
    path = vault / BOARD_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_board(today, sections), encoding="utf-8")
    return path


def invoke(capsys, vault: Path, *args: str) -> tuple[int, dict]:
    code = main([str(vault), *args])
    payload = json.loads(capsys.readouterr().out)
    return code, payload


def test_board_sections_are_the_words_the_agent_speaks():
    """Row 80. Both references, the constant, and the renderer name one board."""
    text = REFERENCE.read_text(encoding="utf-8")
    write_text = WRITE_REFERENCE.read_text(encoding="utf-8")
    for name in BOARD_SECTIONS:
        assert f"## {name}" in text, name
        assert f"## {name}" in write_text, name
    for line in SAMPLE_LINES:
        assert line in text, line
        assert line in write_text, line
    for sentence in WRITE_SUCCESSES:
        assert sentence not in text, sentence
        assert sentence in write_text, sentence

    rendered = render_board(TODAY)
    for name in BOARD_SECTIONS:
        assert f"## {name}\n" in rendered, name

    note = render_board(
        TODAY,
        {
            "今天": [SAMPLE_LINES[0]],
            "之后": [SAMPLE_LINES[1]],
            "没定日子": [SAMPLE_LINES[2]],
            "备忘": [SAMPLE_LINES[3]],
            "已完成": [SAMPLE_LINES[4], SAMPLE_LINES[5]],
        },
    )
    board = parse_board(note)
    assert [row.text for row in board.rows["今天"]] == ["回复客户"]
    assert [row.due for row in board.rows["今天"]] == [TODAY]
    assert [row.text for row in board.rows["之后"]] == ["补测试"]
    assert [row.text for row in board.rows["没定日子"]] == ["收拾书桌"]
    assert [row.text for row in board.rows["备忘"]] == ["停车在 B2"]
    assert [row.done_mark for row in board.rows["已完成"]] == ["勾掉", "取消"]


def test_list_spoken_contract_matches_the_board_parser():
    """Row 83. The sentences the agent says are the sentences the parser allows."""
    text = REFERENCE.read_text(encoding="utf-8")
    for sentence in (
        "看板上没有待办",
        "没有备忘",
        "空",
        "有 {n} 条仍写在旧栏目",
        "不要说都做完了",
    ):
        assert sentence in text, sentence
    for key in ("counts", "sections", "misplaced", "memos"):
        assert key in text, key
    for line in SAMPLE_LINES:
        assert line in text, line
    for sentence in WRITE_SUCCESSES:
        assert sentence not in text, sentence
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


def test_list_utterances_are_routed_by_the_retrieval_sentence():
    """Row 82. The two list phrases are not an open-loop question."""
    text = RETRIEVAL.read_text(encoding="utf-8")
    assert len(text.splitlines()) == 146
    parts = text.split("## When the user asks what is still open", 1)
    assert len(parts) == 2
    own, open_loops = parts
    assert "## When the user asks for their own todos or memos" in own
    for phrase in ("列一下我现在的代办", "列一下备忘"):
        assert phrase in own
        assert phrase in open_loops
    assert "list-board <vault>" in own
    assert "Do not run `review-open-loops`" in own
    assert (
        'Not these phrases: "列一下我现在的代办" and "列一下备忘" '
        "are the section above."
    ) in open_loops
    assert "list-board" not in open_loops
    assert "review-open-loops" in open_loops


def test_the_retrieval_header_stays_one_trigger_line():
    header = (ROOT / "skills" / "obsidian-knowledge-retrieval" / "header.md").read_text(
        encoding="utf-8"
    )
    description = next(
        line for line in header.splitlines() if line.startswith("description:")
    )
    assert description.startswith('description: "Use when ')
    assert description.endswith('"')
    assert "\n" not in description
    for phrase in ("列一下我现在的代办", "列一下备忘", "listing does not grant a write"):
        assert phrase in description
    for absent in ("capture", "tick", "cancel"):
        assert absent not in description.lower()


def test_an_oversize_board_is_malformed_before_it_is_parsed(capsys, tmp_path):
    vault = vault_of(tmp_path)
    path = vault / BOARD_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (MAX_NOTE_BYTES + 1))

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 2
    assert payload["error"]["code"] == "board-malformed"
    assert payload["error"]["details"] == {"reason": "size"}
    assert "schema_version" not in payload


def test_a_future_row_under_today_is_spoken_in_later_and_not_rewritten(capsys, tmp_path):
    """Count and speak by the date. The heading the row sits under stays put."""
    vault = vault_of(tmp_path)
    path = write_board(vault, {"今天": ["- [ ] 补测试 📅 2026-11-20"]})
    before = path.read_bytes()

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 0
    assert path.read_bytes() == before
    assert payload["counts"]["今天"] == 0
    assert payload["counts"]["今天"] == len(payload["sections"]["今天"])
    assert payload["counts"]["之后"] == 1
    assert payload["counts"]["之后"] == len(payload["sections"]["之后"])
    assert payload["counts"]["没定日子"] == 0
    row = payload["sections"]["之后"][0]
    assert row["text"] == "补测试"
    assert row["due"] == "2026-11-20"
    assert row["file_section"] == "今天"
    assert payload["misplaced"] == [{**row, "spoken_section": "之后"}]
    assert "memos" not in payload


def test_surrounding_spaces_on_a_real_row_are_kept(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ]  回复客户  📅 2026-11-13"]})

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 0
    assert payload["sections"]["今天"][0]["text"] == " 回复客户 "
    assert payload["misplaced"] == []


def test_an_overdue_row_stays_in_today_and_keeps_its_date(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(vault, {"今天": ["- [ ] 昨天的 📅 2026-11-12"]})

    _, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert payload["counts"]["今天"] == 1
    assert payload["sections"]["今天"][0]["due"] == "2026-11-12"
    assert payload["misplaced"] == []


@pytest.mark.parametrize(
    ("sections", "reason"),
    [
        ({"今天": ["- [ ] 收拾书桌"]}, "pattern"),
        ({"没定日子": ["- [ ] 补测试 📅 2026-11-20"]}, "pattern"),
        ({"已完成": ["- 2026-11-12 勾掉:买牛奶"]}, "pattern"),
        ({"已完成": ["- 2026-11-13 取消:收拾书桌"]}, "pattern"),
        ({"备忘": ["```"]}, "fence"),
        ({"今天": ["- [ ]    📅 2026-11-13"]}, "pattern"),
    ],
)
def test_a_row_in_the_wrong_shape_rejects_the_whole_file(capsys, tmp_path, sections, reason):
    vault = vault_of(tmp_path)
    write_board(vault, sections)

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 2
    assert payload["error"]["code"] == "board-malformed"
    assert payload["error"]["details"]["reason"] == reason


def test_render_puts_one_blank_line_after_each_heading_and_none_between_items():
    text = render_board(
        TODAY,
        {
            "今天": ["- [ ] 一 📅 2026-11-13", "- [ ] 二 📅 2026-11-13"],
            "已完成": ["- 2026-11-13 勾掉：一"],
        },
    )
    assert (
        "\n## 今天\n\n- [ ] 一 📅 2026-11-13\n- [ ] 二 📅 2026-11-13\n## 之后\n\n"
        in text
    )
    assert text.endswith("- 2026-11-13 勾掉：一\n")
    assert not text.endswith("\n\n")

    padded = text.replace(
        "- [ ] 一 📅 2026-11-13\n- [ ] 二",
        "- [ ] 一 📅 2026-11-13\n\n\n- [ ] 二",
        1,
    )
    parsed = parse_board(padded)
    assert [row.text for row in parsed.rows["今天"]] == ["一", "二"]
    rebuilt = render_board(
        TODAY,
        {"今天": ["- [ ] 一 📅 2026-11-13", "- [ ] 二 📅 2026-11-13"]},
    )
    assert "\n\n\n- [ ] 二" not in rebuilt


def test_todos_do_not_carry_memos_or_a_web_clip(capsys, tmp_path):
    vault = vault_of(tmp_path)
    write_board(
        vault,
        {
            "今天": [SAMPLE_LINES[0]],
            "备忘": [SAMPLE_LINES[3]],
        },
    )
    clip = vault / "clips" / "one.md"
    clip.parent.mkdir()
    clip.write_text(
        "---\ndate: 2026-11-13\ntype: web-clip\ntags: [clip]\n---\n\n"
        "# 剪藏\n\n## 后续行动\n\n- [ ] 剪藏里的下一步\n",
        encoding="utf-8",
    )

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")
    rendered = json.dumps(payload, ensure_ascii=False)

    assert code == 0
    assert "memos" not in payload
    assert "停车在 B2" not in rendered
    assert "剪藏里的下一步" not in rendered
    report = review_open_loops(vault)
    assert "回复客户" not in json.dumps(report, ensure_ascii=False)
    assert "剪藏里的下一步" in [item["text"] for item in report["items"]]


def test_a_missing_board_is_an_empty_view_and_creates_nothing(capsys, tmp_path, monkeypatch):
    vault = vault_of(tmp_path)
    seen = {"existing": 0, "target": 0}
    import obsidian_kb_skill.scripts.list_board as reader
    from obsidian_kb_skill.scripts.vault_paths import resolve_target_within_vault

    def existing(*_args, **_kwargs):
        seen["existing"] += 1
        raise AssertionError("a missing board must not use resolve_existing")

    def target(*args, **kwargs):
        seen["target"] += 1
        return resolve_target_within_vault(*args, **kwargs)

    monkeypatch.setattr(reader, "resolve_existing_within_vault", existing)
    monkeypatch.setattr(reader, "resolve_target_within_vault", target)

    code, todos = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")
    _, memos = invoke(capsys, vault, "--today", TODAY, "--view", "memos", "--json")

    assert code == 0
    assert seen == {"existing": 0, "target": 2}
    assert todos["exists"] is False
    assert todos["counts"] == {"今天": 0, "之后": 0, "没定日子": 0}
    assert todos["sections"] == {"今天": [], "之后": [], "没定日子": []}
    assert todos["misplaced"] == []
    assert "memos" not in todos
    assert memos["exists"] is False
    assert memos["count"] == 0
    assert memos["memos"] == []
    assert "sections" not in memos
    assert "counts" not in memos
    assert not (vault / BOARD_PATH).exists()
    assert not (vault / "15-Daily").exists()


def test_a_symlink_parent_outside_the_vault_is_not_an_empty_board(capsys, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_bytes(b"keep")
    vault = vault_of(tmp_path)
    (vault / "15-Daily").symlink_to(outside, target_is_directory=True)

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 3
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert payload["schema_version"] == "1.0"
    assert "exists" not in payload
    assert secret.read_bytes() == b"keep"
    assert not (outside / "待办.md").exists()


def test_a_board_symlink_to_the_outside_is_rejected(capsys, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    vault = vault_of(tmp_path)
    path = vault / BOARD_PATH
    path.parent.mkdir(parents=True)
    path.symlink_to(outside)

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")

    assert code == 3
    assert payload["error"]["code"] == "PATH_OUTSIDE_VAULT"
    assert outside.read_text(encoding="utf-8") == "outside"


def test_an_unresolvable_vault_root_uses_the_shared_path_envelope(capsys, tmp_path):
    missing = tmp_path / "no-such-vault"

    code, payload = invoke(capsys, missing, "--today", TODAY, "--view", "todos", "--json")

    assert code == 3
    assert payload["error"]["code"] == "INVALID_VAULT_ROOT"
    assert payload["schema_version"] == "1.0"
    assert payload["command"] is None


def test_memos_sort_by_clock_then_later_line_and_do_not_write(capsys, tmp_path):
    vault = vault_of(tmp_path)
    path = write_board(
        vault,
        {
            "备忘": [
                "- 2026-11-13 14:30 先写的下午",
                "- 2026-11-13 09:00 用户指定的早上",
                "- 2026-11-13 14:30 后写的同刻",
            ]
        },
    )
    before = path.read_bytes()

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "memos", "--json")

    assert code == 0
    assert path.read_bytes() == before
    assert "sections" not in payload
    assert "counts" not in payload
    assert [item["text"] for item in payload["memos"]] == [
        "后写的同刻",
        "先写的下午",
        "用户指定的早上",
    ]
    assert payload["count"] == 3
    assert payload["memos"][0]["at"] == "2026-11-13 14:30"


def test_a_heading_the_board_does_not_have_is_malformed(capsys, tmp_path):
    vault = vault_of(tmp_path)
    path = write_board(vault, {"今天": [SAMPLE_LINES[0]]})
    path.write_text(
        path.read_text(encoding="utf-8") + "## 待办事项\n\n- [ ] 坏栏目\n",
        encoding="utf-8",
    )

    code, payload = invoke(capsys, vault, "--today", TODAY, "--view", "todos", "--json")
    report = review_open_loops(vault)

    assert code == 2
    assert payload["error"]["code"] == "board-malformed"
    assert payload["error"]["details"]["reason"] == "heading"
    assert "坏栏目" not in [item["text"] for item in report["items"]]
    assert report["scanned"] == 1


def test_the_open_loop_queue_skips_the_personal_board(tmp_path):
    """Row 81. Skip by path and by type. A broken board must not become a loop."""
    for name in ("review_open_loops.py", "list_board.py"):
        assert "todo-board" not in (SCRIPTS / name).read_text(encoding="utf-8")

    by_path = vault_of(tmp_path / "by-path")
    note = by_path / BOARD_PATH
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ndate: 2026-11-13\ntype: daily-note\ntags: [todo]\n---\n\n"
        "# 待办\n\n## 待办事项\n\n- [ ] 路径排除\n",
        encoding="utf-8",
    )
    other = by_path / "clips" / "one.md"
    other.parent.mkdir()
    other.write_text(
        "---\ndate: 2026-11-13\ntype: web-clip\ntags: [clip]\n---\n\n"
        "# 剪藏\n\n## 后续行动\n\n- [ ] 剪藏里的下一步\n",
        encoding="utf-8",
    )
    path_report = review_open_loops(by_path)
    assert "路径排除" not in [item["text"] for item in path_report["items"]]
    assert [item["text"] for item in path_report["items"]] == ["剪藏里的下一步"]
    assert path_report["scanned"] == 2

    by_type = vault_of(tmp_path / "by-type")
    typed = by_type / "笔记" / "另一篇.md"
    typed.parent.mkdir(parents=True)
    typed.write_text(
        "---\ndate: 2026-11-13\ntype: todo-board\ntags: [todo]\n---\n\n"
        "# 另一篇\n\n## 待办事项\n\n- [ ] 类型排除\n",
        encoding="utf-8",
    )
    type_report = review_open_loops(by_type)
    assert type_report["items"] == []
    assert type_report["scanned"] == 1


def test_apply_is_rejected_by_argparse_without_a_board_code(capsys, tmp_path):
    vault = vault_of(tmp_path)
    with pytest.raises(SystemExit) as raised:
        main([str(vault), "--today", TODAY, "--view", "todos", "--apply", "--json"])
    assert raised.value.code == 2
    assert '"code"' not in capsys.readouterr().out


def test_the_write_runner_points_list_board_at_the_retrieval_skill():
    runner = ROOT / "skills" / "obsidian-knowledge-base" / "scripts" / "run_helper.py"
    result = subprocess.run(
        [sys.executable, str(runner), "list-board"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "obsidian-knowledge-retrieval" in result.stderr


def test_a_bad_view_is_refused_before_the_vault_is_opened(capsys, tmp_path):
    missing = tmp_path / "no-such-vault"
    code, payload = invoke(capsys, missing, "--today", "not-a-date", "--json")
    assert code == 2
    assert payload["error"]["code"] == "board-invalid-view"

    code, payload = invoke(capsys, missing, "--today", "周五", "--view", "todos", "--json")
    assert code == 2
    assert payload["error"]["code"] == "board-invalid-date"
    assert payload["error"]["details"] == {"parameter": "--today"}


def test_the_reader_does_not_call_the_clock():
    for name in ("list_board.py", "board_contract.py"):
        tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "utcnow", "today"}, name


def test_board_contract_emits_no_refusal_code():
    """Row 84. A code literal here would have to be documented on the write side."""
    assert _codes_in(SCRIPTS / "board_contract.py") == (set(), set())


def test_board_contract_imports_nothing_from_the_package():
    """Row 84. The whole tree, so an import hidden in a function fails too."""
    tree = ast.parse((SCRIPTS / "board_contract.py").read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            root = module.split(".", 1)[0]
            if root in {"obsidian_kb_skill", "yaml"}:
                offenders.append(f"{node.lineno}:{module}")
    assert offenders == []
