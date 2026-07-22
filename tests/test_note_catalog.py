import ast
import json
from pathlib import Path

import pytest

import obsidian_kb_skill.scripts.scaffold_templates as scaffold_templates

from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE,
    FOLDER_TO_DEFAULT_TYPE,
    MANAGED_NOTE_FOLDERS,
    NOTE_TYPES,
    NoteTypeSpec,
    STANDARD_NOTE_FOLDERS,
    TYPE_TO_FOLDER,
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
    VALID_NOTE_TYPES,
)


ROOT = Path(__file__).resolve().parent.parent


def _assignment_values(source: str) -> dict[str, list[ast.expr | None]]:
    """Return values assigned to simple names by Assign and AnnAssign nodes."""
    assignments: dict[str, list[ast.expr | None]] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(value)
    return assignments


EXPECTED_DURABLE = {
    "daily-note": ("Daily Note.md", "daily-note.md", "15-Daily", "daily"),
    "meeting-note": ("Meeting Note.md", "meeting-note.md", "10-Work", "meeting"),
    "learning-note": ("Learning Note.md", "learning-note.md", "20-Learning", "learning"),
    "web-clip": ("Web Clip.md", "web-clip.md", "20-Learning", "web-clip"),
    "insight-note": ("Insight Note.md", "insight-note.md", "30-Insights", "insight"),
    "conversation-digest": ("Digest Note.md", "digest-note.md", "30-Insights", "insight"),
    "project-note": ("Project Note.md", "project-note.md", "40-Projects", "project"),
    "person-note": ("Person Note.md", "person-note.md", "50-People", "people"),
}


def test_catalog_derives_every_existing_public_mapping():
    assert {
        slug: (
            TYPE_TO_TEMPLATE[slug],
            TYPE_TO_TEMPLATE_ASSET[slug],
            TYPE_TO_FOLDER[slug],
            DEFAULT_TAG_BY_TYPE[slug],
        )
        for slug in EXPECTED_DURABLE
    } == EXPECTED_DURABLE


def test_task_memory_is_routable_but_has_no_conventional_template():
    assert NOTE_TYPES["task-memory"].template_name is None
    assert TYPE_TO_FOLDER["task-memory"] == "Tasks"
    assert DEFAULT_TAG_BY_TYPE["task-memory"] == "task"
    assert "task-memory" not in TYPE_TO_TEMPLATE


def test_ambiguous_folders_have_an_explicit_default_type():
    assert FOLDER_TO_DEFAULT_TYPE["20-Learning"] == "learning-note"
    assert FOLDER_TO_DEFAULT_TYPE["30-Insights"] == "insight-note"


def test_audit_preserves_legacy_types_without_making_them_creatable():
    assert {"daily-report", "weekly-report", "archive-note"} <= VALID_NOTE_TYPES
    assert not {"daily-report", "weekly-report", "archive-note"} & NOTE_TYPES.keys()
    assert not {"daily-report", "weekly-report", "archive-note"} & TYPE_TO_FOLDER.keys()


def test_audit_and_folder_sets_are_derived_from_explicit_contracts():
    assert VALID_NOTE_TYPES == (
        frozenset(NOTE_TYPES)
        | {"daily-report", "weekly-report", "archive-note", "folder-index", "moc"}
    )
    assert MANAGED_NOTE_FOLDERS == (
        "00-Inbox", "10-Work", "15-Daily", "20-Learning",
        "30-Insights", "40-Projects", "50-People", "90-Archive",
    )
    assert STANDARD_NOTE_FOLDERS == {
        "00-Inbox", "10-Work", "15-Daily", "20-Learning",
        "30-Insights", "40-Projects", "50-People", "90-Archive", "Tasks",
    }


def test_catalog_literals_have_one_owner():
    forbidden = {
        "audit_vault.py": {"REQUIRED_TYPES", "VALID_NOTE_TYPES"},
        "create_note.py": {
            "DEFAULT_TAG_BY_TYPE", "TYPE_TO_FOLDER", "TYPE_TO_TEMPLATE",
        },
        "process_inbox.py": {
            "DEFAULT_TAG_BY_TYPE", "FOLDER_TO_DEFAULT_TYPE", "TYPE_TO_FOLDER",
        },
        "create_category.py": {"STANDARD_NOTE_FOLDERS"},
    }
    scripts = ROOT / "obsidian_kb_skill" / "scripts"
    for filename, names in forbidden.items():
        assignments = _assignment_values(
            (scripts / filename).read_text(encoding="utf-8")
        )
        assert names.isdisjoint(assignments)

    vault_info_assignments = _assignment_values(
        (scripts / "vault_info.py").read_text(encoding="utf-8")
    )
    note_folder_values = vault_info_assignments.get("NOTE_FOLDERS", [])
    assert len(note_folder_values) == 1
    expected = ast.parse("list(MANAGED_NOTE_FOLDERS)", mode="eval").body
    assert ast.dump(note_folder_values[0]) == ast.dump(expected)


def test_scaffold_template_metadata_is_owned_by_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    source = (
        ROOT / "obsidian_kb_skill/scripts/scaffold_templates.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = _assignment_values(source)
    assert "TEMPLATE_MAP" not in assignments
    assert any(
        isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Attribute)
        and isinstance(node.iter.func.value, ast.Name)
        and node.iter.func.value.id == "NOTE_TYPES"
        and node.iter.func.attr == "items"
        for node in ast.walk(tree)
    )

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "catalog-asset.md").write_text("catalog body\n", encoding="utf-8")
    monkeypatch.setattr(
        scaffold_templates,
        "NOTE_TYPES",
        {
            "catalog-type": NoteTypeSpec(
                "catalog-type",
                "Catalog Name.md",
                "catalog-asset.md",
                "30-Insights",
                "catalog",
            ),
            "no-template": NoteTypeSpec(
                "no-template", None, None, "Tasks", "task", False
            ),
        },
    )
    monkeypatch.setattr(scaffold_templates, "template_dir", lambda **_: assets)

    assert scaffold_templates.main([str(vault), "--apply", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["written"] == ["Catalog Name.md"]
    assert payload["missing"] == []
    assert (vault / "Templates/Catalog Name.md").read_text(encoding="utf-8") == (
        "catalog body\n"
    )


def test_assignment_detection_includes_annotated_assignments():
    source = """
PLAIN = {"local": "literal"}
ANNOTATED: dict[str, str] = {"local": "literal"}
"""
    assert set(_assignment_values(source)) == {"PLAIN", "ANNOTATED"}
