"""Tests for user-confirmed Vault category initialization."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

import obsidian_kb_skill.scripts.create_category as create_category
from obsidian_kb_skill.scripts.create_category import (
    CategoryValidationError,
    PlannedChange,
    apply_category,
    main,
    plan_category,
    render_category_index,
)
from obsidian_kb_skill.scripts.folder_index_policy import (
    StaticIndexEntry,
    append_static_index_entry,
)
from obsidian_kb_skill.scripts.vault_paths import VaultPathError


def make_vault(
    tmp_path: Path,
    *,
    folder_index: bool = False,
    custom_index: bool = False,
    dataview: bool = False,
    exclude_category: bool = False,
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
                    "excludeFolders": (
                        ["20-Learning/Rust"] if exclude_category else []
                    ),
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


def _write_folder_index_filename(vault: Path, value: str) -> None:
    data = vault / ".obsidian/plugins/obsidian-folder-index/data.json"
    settings = json.loads(data.read_text(encoding="utf-8"))
    settings["indexFileUserSpecified"] = True
    settings["indexFilename"] = value
    data.write_text(json.dumps(settings), encoding="utf-8")


def test_plan_rejects_escaping_folder_index_filename_without_mutation(
    tmp_path: Path,
):
    vault = make_vault(tmp_path, folder_index=True, custom_index=True)
    _write_folder_index_filename(vault, "../../../escaped")

    with pytest.raises(CategoryValidationError) as error:
        plan_category(vault, "20-Learning/Rust")

    assert error.value.code == "invalid-folder-index-config"
    assert not (tmp_path / "escaped.md").exists()
    assert not (vault / "20-Learning/Rust").exists()


@pytest.mark.parametrize("json_mode", [False, True])
def test_confirmed_apply_rejects_escaping_folder_index_filename_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    json_mode: bool,
):
    vault = make_vault(tmp_path, folder_index=True, custom_index=True)
    _write_folder_index_filename(vault, "../../../escaped")
    argv = [
        str(vault),
        "--folder",
        "20-Learning/Rust",
        "--apply",
        "--confirmed",
    ]
    if json_mode:
        argv.append("--json")

    assert main(argv) == 2

    output = capsys.readouterr()
    if json_mode:
        assert json.loads(output.out)["error"]["code"] == "invalid-folder-index-config"
        assert output.err == ""
    else:
        assert "error: invalid-folder-index-config:" in output.err
        assert "Traceback" not in output.err
    assert not (tmp_path / "escaped.md").exists()
    assert not (vault / "20-Learning/Rust").exists()


def test_apply_resolves_direct_plan_index_before_any_mutation(tmp_path: Path):
    vault = make_vault(tmp_path)
    plan = replace(
        plan_category(vault, "20-Learning/Rust"),
        index_path=Path("../escaped.md"),
    )

    with pytest.raises(VaultPathError):
        apply_category(plan)

    assert not (tmp_path / "escaped.md").exists()
    assert not (vault / "20-Learning/Rust").exists()


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


def test_folder_index_excluded_category_uses_and_updates_static_index(
    tmp_path: Path,
):
    vault = make_vault(tmp_path, folder_index=True, exclude_category=True)
    plan = plan_category(vault, "20-Learning/Rust")

    result = apply_category(plan)
    note = vault / plan.folder / "2026-07-15 Rust所有权.md"
    note.write_text("# Rust所有权\n", encoding="utf-8")
    append_static_index_entry(
        vault,
        StaticIndexEntry(
            note=note.relative_to(vault),
            title="Rust所有权",
            date="2026-07-15",
        ),
    )

    assert plan.index_mode == "static"
    assert result.findings == ()
    assert "[[20-Learning/Rust/2026-07-15 Rust所有权|Rust所有权]]" in (
        vault / plan.index_path
    ).read_text(encoding="utf-8")


def test_existing_category_is_a_noop_plan(tmp_path: Path):
    vault = make_vault(tmp_path)
    category = vault / "20-Learning" / "Rust"
    category.mkdir()
    (category / "INDEX.md").write_text("original\n", encoding="utf-8")

    plan = plan_category(vault, "20-Learning/Rust")

    assert plan.exists is True
    assert plan.planned_changes == ()
    assert plan.index_path == Path("20-Learning/Rust/INDEX.md")


def test_existing_category_preflight_reports_already_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    vault = make_vault(tmp_path)
    (vault / "20-Learning" / "Rust").mkdir()

    assert main(
        [str(vault), "--folder", "20-Learning/Rust", "--preflight-json"]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "already-exists"
    assert payload["planned_changes"] == []


def test_reports_root_and_parent_governance_reminders(tmp_path: Path):
    vault = make_vault(tmp_path)
    (vault / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
    (vault / "README.md").write_text("readme\n", encoding="utf-8")
    (vault / "20-Learning" / "AGENTS.md").write_text(
        "learning rules\n", encoding="utf-8"
    )

    plan = plan_category(vault, "20-Learning/Rust")

    assert plan.governance_reminders == (
        "AGENTS.md",
        "README.md",
        "20-Learning/AGENTS.md",
    )


@pytest.mark.parametrize(
    ("folder", "code"),
    [
        ("/tmp/Rust", "invalid-category-path"),
        ("../Rust", "invalid-category-path"),
        ("20-Learning/Missing/Rust", "missing-category-parent"),
        ("Templates/Rust", "reserved-category-path"),
        (".obsidian/Rust", "reserved-category-path"),
        ("20-Learning/Templates", "reserved-category-path"),
        ("20-Learning/.hidden", "invalid-category-name"),
        ("20-Learning/CON", "invalid-category-name"),
        (f"20-Learning/{'x' * 256}", "invalid-category-name"),
        ("20-Learning/Rust\nBad", "invalid-category-name"),
    ],
)
def test_rejects_invalid_category_paths(
    tmp_path: Path, folder: str, code: str
):
    vault = make_vault(tmp_path)

    with pytest.raises(CategoryValidationError) as error:
        plan_category(vault, folder)

    assert error.value.code == code
    assert not (vault / "20-Learning/Rust").exists()


def test_rejects_symlink_parent_escape(tmp_path: Path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, vault / "20-Learning" / "External")

    with pytest.raises(CategoryValidationError) as error:
        plan_category(vault, "20-Learning/External/Rust")

    assert error.value.code == "invalid-category-path"
    assert not (outside / "Rust").exists()


def test_rejects_existing_but_ungoverned_nested_parent(tmp_path: Path):
    vault = make_vault(tmp_path)
    (vault / "20-Learning" / "Programming").mkdir()

    with pytest.raises(CategoryValidationError) as error:
        plan_category(vault, "20-Learning/Programming/Rust")

    assert error.value.code == "ungoverned-category-parent"


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_rejects_destination_collision(tmp_path: Path, kind: str):
    vault = make_vault(tmp_path)
    destination = vault / "20-Learning" / "Rust"
    if kind == "file":
        destination.write_text("occupied", encoding="utf-8")
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        os.symlink(outside, destination)

    with pytest.raises(CategoryValidationError) as error:
        plan_category(vault, "20-Learning/Rust")

    assert error.value.code == "category-collision"


def test_preflight_json_is_read_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    vault = make_vault(tmp_path, folder_index=True)

    result = main(
        [str(vault), "--folder", "20-Learning/Rust", "--preflight-json"]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["planned_changes"][0]["kind"] == "directory"
    assert payload["index"] == {
        "mode": "folder-index",
        "path": "20-Learning/Rust/Rust.md",
    }
    assert payload["applied"] is False
    assert not (vault / "20-Learning/Rust").exists()


def test_apply_requires_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    vault = make_vault(tmp_path, folder_index=True)

    result = main(
        [str(vault), "--folder", "20-Learning/Rust", "--apply", "--json"]
    )

    assert result == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "confirmation-required"
    assert not (vault / "20-Learning/Rust").exists()


def test_confirmed_apply_creates_and_audits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    vault = make_vault(tmp_path, folder_index=True)

    result = main(
        [
            str(vault),
            "--folder",
            "20-Learning/Rust",
            "--apply",
            "--confirmed",
            "--compact-json",
        ]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is True
    assert payload["created"] == [
        "20-Learning/Rust",
        "20-Learning/Rust/Rust.md",
    ]
    assert payload["audit"] == []
    assert (vault / "20-Learning/Rust/Rust.md").is_file()


def test_existing_category_apply_is_noop_and_preserves_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    vault = make_vault(tmp_path)
    category = vault / "20-Learning" / "Rust"
    category.mkdir()
    index = category / "INDEX.md"
    index.write_bytes(b"original\n")

    result = main(
        [
            str(vault),
            "--folder",
            "20-Learning/Rust",
            "--apply",
            "--confirmed",
            "--compact-json",
        ]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is False
    assert payload["status"] == "already-exists"
    assert payload["created"] == []
    assert index.read_bytes() == b"original\n"


def test_index_write_failure_removes_only_new_empty_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    vault = make_vault(tmp_path)
    plan = plan_category(vault, "20-Learning/Rust")

    def fail_write(path: Path, content: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(create_category, "_write_index_exclusively", fail_write)

    with pytest.raises(OSError, match="disk full"):
        apply_category(plan)

    assert not (vault / "20-Learning/Rust").exists()
    assert (vault / "20-Learning").is_dir()


def test_partial_index_write_failure_removes_helper_owned_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    vault = make_vault(tmp_path)
    plan = plan_category(vault, "20-Learning/Rust")

    def partial_write(path: Path, content: bytes) -> None:
        path.write_bytes(content[:10])
        raise OSError("disk full after partial write")

    monkeypatch.setattr(create_category, "_write_index_exclusively", partial_write)

    with pytest.raises(OSError, match="disk full after partial write"):
        apply_category(plan)

    assert not (vault / "20-Learning/Rust").exists()


def test_apply_failure_json_reports_created_and_cleaned_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    vault = make_vault(tmp_path)

    def fail_write(path: Path, content: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(create_category, "_write_index_exclusively", fail_write)

    result = main(
        [
            str(vault),
            "--folder",
            "20-Learning/Rust",
            "--apply",
            "--confirmed",
            "--json",
        ]
    )

    assert result == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "category-apply-failed"
    assert payload["error"]["details"] == {
        "created": ["20-Learning/Rust"],
        "cleaned": ["20-Learning/Rust"],
    }
