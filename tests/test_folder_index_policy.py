import ast
import json
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.folder_index_policy import (
    FolderIndexConfig,
    StaticIndexEntry,
    append_static_index_entry,
    expected_folder_index,
    is_folder_index_excluded,
    read_folder_index_config,
)
from obsidian_kb_skill.scripts.vault_paths import VaultPathError


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian" / "plugins" / "obsidian-folder-index").mkdir(
        parents=True
    )
    (vault / "30-Insights").mkdir()
    return vault


def enable_folder_index(vault: Path, settings: dict) -> None:
    (vault / ".obsidian" / "community-plugins.json").write_text(
        '["obsidian-folder-index"]', encoding="utf-8"
    )
    (vault / ".obsidian" / "plugins" / "obsidian-folder-index" / "data.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def test_disabled_plugin_uses_default_config(tmp_path: Path):
    config = read_folder_index_config(make_vault(tmp_path))
    assert config == FolderIndexConfig()


def test_enabled_plugin_reads_native_and_custom_settings(tmp_path: Path):
    vault = make_vault(tmp_path)
    enable_folder_index(vault, {
        "graphOverwrite": True,
        "rootIndexFile": "HOME.md",
        "indexFileUserSpecified": True,
        "indexFilename": "MAP",
        "excludeFolders": ["Templates", "/90-Archive/"],
        "excludePatterns": ["Private/*"],
    })
    config = read_folder_index_config(vault)
    assert config == FolderIndexConfig(
        enabled=True,
        graph_overwrite=True,
        root_index_file="HOME.md",
        user_specified=True,
        index_filename="MAP",
        exclude_folders=("Templates", "90-Archive"),
        exclude_patterns=("Private/*",),
    )


def test_excluded_folder_and_glob_are_not_skill_owned():
    config = FolderIndexConfig(
        enabled=True,
        exclude_folders=("Templates",),
        exclude_patterns=("Private/*",),
    )
    assert is_folder_index_excluded(Path("Templates/Web"), config)
    assert is_folder_index_excluded(Path("Private/Notes"), config)
    assert not is_folder_index_excluded(Path("30-Insights"), config)


def test_expected_index_name_handles_root_native_and_custom(tmp_path: Path):
    vault = make_vault(tmp_path)
    folder = vault / "30-Insights"
    native = FolderIndexConfig(enabled=True, root_index_file="HOME.md")
    custom = FolderIndexConfig(
        enabled=True, user_specified=True, index_filename="MAP"
    )
    assert expected_folder_index(vault, vault, native) == vault / "HOME.md"
    assert expected_folder_index(folder, vault, native) == folder / "30-Insights.md"
    assert expected_folder_index(folder, vault, custom) == folder / "MAP.md"


@pytest.mark.parametrize("managed_body", [
    "```folder-index-content\n```\n",
    "```dataview\nLIST\n```\n",
])
def test_static_append_skips_managed_indexes(tmp_path: Path, managed_body: str):
    vault = make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    original = f"# Insights\n\n{managed_body}"
    index.write_text(original, encoding="utf-8")
    result = append_static_index_entry(vault, StaticIndexEntry(
        note=Path("30-Insights/idea.md"), title="Idea", date="2026-07-16"
    ))
    assert result.status == "unmanaged"
    assert index.read_text(encoding="utf-8") == original


def test_static_append_reports_missing_index(tmp_path: Path):
    vault = make_vault(tmp_path)
    result = append_static_index_entry(vault, StaticIndexEntry(
        note=Path("30-Insights/idea.md"), title="Idea", date="2026-07-16"
    ))
    assert result.status == "missing"


def test_static_append_writes_exact_relative_link_and_date(tmp_path: Path):
    vault = make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    index.write_text("# Insights\n", encoding="utf-8")
    result = append_static_index_entry(vault, StaticIndexEntry(
        note=Path("30-Insights/idea.md"), title="Idea", date="2026-07-16"
    ))
    assert result.status == "appended"
    assert result.index == index
    assert index.read_text(encoding="utf-8") == (
        "# Insights\n- [[30-Insights/idea|Idea]] (2026-07-16)\n"
    )


def test_static_append_rejects_note_outside_vault(tmp_path: Path):
    vault = make_vault(tmp_path)
    with pytest.raises(VaultPathError):
        append_static_index_entry(vault, StaticIndexEntry(
            note=Path("../outside.md"), title="Outside", date="2026-07-16"
        ))


def test_production_modules_do_not_import_audit_or_inbox_private_policy():
    scripts = Path(__file__).resolve().parent.parent / "obsidian_kb_skill" / "scripts"
    private_policy = {
        "_folder_index_config",
        "_is_folder_index_excluded",
        "_maybe_update_static_index",
    }
    for path in scripts.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "obsidian_kb_skill.scripts.audit_vault",
                "obsidian_kb_skill.scripts.process_inbox",
            }:
                continue
            imported = {alias.name for alias in node.names}
            assert imported.isdisjoint(private_policy), path.name
