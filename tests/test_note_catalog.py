from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE,
    FOLDER_TO_DEFAULT_TYPE,
    MANAGED_NOTE_FOLDERS,
    NOTE_TYPES,
    STANDARD_NOTE_FOLDERS,
    TYPE_TO_FOLDER,
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
    VALID_NOTE_TYPES,
)


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
