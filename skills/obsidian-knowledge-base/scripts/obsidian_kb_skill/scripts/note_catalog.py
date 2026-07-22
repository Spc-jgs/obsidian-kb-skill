from dataclasses import dataclass


@dataclass(frozen=True)
class NoteTypeSpec:
    slug: str
    template_name: str | None
    template_asset: str | None
    folder: str
    default_tag: str
    default_for_folder: bool = True


def _spec(
    slug: str,
    template_name: str | None,
    template_asset: str | None,
    folder: str,
    default_tag: str,
    default_for_folder: bool = True,
) -> NoteTypeSpec:
    return NoteTypeSpec(
        slug, template_name, template_asset, folder, default_tag,
        default_for_folder,
    )


NOTE_TYPES = {
    spec.slug: spec
    for spec in (
        _spec("daily-note", "Daily Note.md", "daily-note.md", "15-Daily", "daily"),
        _spec("meeting-note", "Meeting Note.md", "meeting-note.md", "10-Work", "meeting"),
        _spec("learning-note", "Learning Note.md", "learning-note.md", "20-Learning", "learning"),
        _spec("web-clip", "Web Clip.md", "web-clip.md", "20-Learning", "web-clip", False),
        _spec("insight-note", "Insight Note.md", "insight-note.md", "30-Insights", "insight"),
        _spec("conversation-digest", "Digest Note.md", "digest-note.md", "30-Insights", "insight", False),
        _spec("project-note", "Project Note.md", "project-note.md", "40-Projects", "project"),
        _spec("person-note", "Person Note.md", "person-note.md", "50-People", "people"),
        _spec("task-memory", None, None, "Tasks", "task", False),
    )
}

TYPE_TO_TEMPLATE = {
    slug: spec.template_name
    for slug, spec in NOTE_TYPES.items()
    if spec.template_name is not None
}
TYPE_TO_TEMPLATE_ASSET = {
    slug: spec.template_asset
    for slug, spec in NOTE_TYPES.items()
    if spec.template_asset is not None
}
TYPE_TO_FOLDER = {slug: spec.folder for slug, spec in NOTE_TYPES.items()}
DEFAULT_TAG_BY_TYPE = {slug: spec.default_tag for slug, spec in NOTE_TYPES.items()}
FOLDER_TO_DEFAULT_TYPE = {
    spec.folder: slug
    for slug, spec in NOTE_TYPES.items()
    if spec.default_for_folder
}
AUDIT_COMPATIBILITY_TYPES = frozenset({
    "daily-report", "weekly-report", "archive-note",
})
VALID_NOTE_TYPES = (
    frozenset(NOTE_TYPES) | AUDIT_COMPATIBILITY_TYPES | {"folder-index", "moc"}
)
MANAGED_NOTE_FOLDERS = (
    "00-Inbox", "10-Work", "15-Daily", "20-Learning",
    "30-Insights", "40-Projects", "50-People", "90-Archive",
)
STANDARD_NOTE_FOLDERS = set(TYPE_TO_FOLDER.values()) | {
    "00-Inbox", "90-Archive",
}
