import re
from dataclasses import dataclass

# The one definition of "this template placeholder was never replaced". It
# lived in `audit_vault` and `template_contract` as two near-copies, and
# `process_inbox` was about to make a third. Two copies of a rule are the shape
# the consistency inventory exists to catch; sharing the object removes the
# boundary instead of guarding it.
#
# The copies had already diverged: only `template_contract`'s captured the
# placeholder's name, which its `findall` depends on. The shared pattern keeps
# the group, since a capturing group changes nothing for the `search` callers.
TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")

# Headings that mean "what this project does next". `review-projects` locates a
# project's next action here and `resume-project` extracts the same section, and
# each used to hold its own literal set. Widening one alone is exactly what
# happened in #125, unnoticed because nothing tied them together.
#
# Each variant names where it came from; a guessed synonym makes the vocabulary
# look complete while it still fails silently.
PROJECT_NOTE_NEXT_ACTION_HEADINGS: tuple[str, ...] = (
    "下一步行动",      # core/templates/project-note.md
    "后续行动",        # observed: 40-Projects/etianqu/…AI对话上下文与落库设计复盘.md
    "next actions",   # core/templates/en/project-note.md
    "next steps",     # inherited from the radar's original set; no known source
)


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
# Verbatim copies of sources a note was built from. Deliberately not a managed
# note folder: an archive is someone else's writing kept as evidence, so it has
# no note contract to satisfy, contributes no subject tags, and never counts
# towards crowding. Retrieval hides it by default; see the design doc.
SOURCE_ARCHIVE_FOLDER = "95-Sources"
SOURCE_ARCHIVE_TYPE = "source-archive"
AUDIT_COMPATIBILITY_TYPES = frozenset({
    "daily-report", "weekly-report", "archive-note",
})
VALID_NOTE_TYPES = (
    frozenset(NOTE_TYPES)
    | AUDIT_COMPATIBILITY_TYPES
    | {"folder-index", "moc", SOURCE_ARCHIVE_TYPE}
)
MANAGED_NOTE_FOLDERS = (
    "00-Inbox", "10-Work", "15-Daily", "20-Learning",
    "30-Insights", "40-Projects", "50-People", "90-Archive",
)
STANDARD_NOTE_FOLDERS = set(TYPE_TO_FOLDER.values()) | {
    "00-Inbox", "90-Archive",
}

# Folders that group members by *what they belong to* rather than by *what they
# are about*. A project is an entity owning heterogeneous output — a status
# note, designs, retrospectives, meeting records — whose only common trait is
# the project. That is not the taxonomy folders' model, where members share a
# subject and crowding drives the split.
#
# The distinction is declared once, here, so rules can ask which kind of folder
# they are looking at. Naming the category is the point: special-casing
# `40-Projects` wherever a rule needs it is how the crowding contract came to
# be applied to a structure it was never written for.
ENTITY_FOLDERS = frozenset({"40-Projects"})

# An instance directory holds exactly one note of its entity's type. The rest of
# its contents are subordinate output carrying their own types. `review-projects`
# identifies instances per-note, so a second one here silently reports the same
# project twice.
ENTITY_INSTANCE_TYPE = {"40-Projects": "project-note"}

# Values marking a reusable, entity-shaped note that is not an instance: a
# template belongs to no project and never started one. Both Skills need the
# same judgement — retrieval keeps these out of the revival queue, and the audit
# must not report one sitting legitimately at an entity folder's root.
NON_INSTANCE_STATUSES = frozenset({
    "template",
    "模板",
})

# Files a Vault keeps for humans and agents rather than as knowledge. Both
# Skills need this judgement over the same Vault: the audit exempts them from
# note contracts, and retrieval must not rank them as notes. It lives here so
# there is one definition rather than two that can drift apart.
EXEMPT_NAMES = {"README.md", "AGENTS.md", "CLAUDE.md"}


def normalize_tag_key(tag: str) -> str:
    """Return the identity of a tag, ignoring how it happens to be spelled.

    Case, separators, and a trailing plural are spelling choices, not
    distinctions: `yaml-standards.md` names `frontend`, `front_end`, and
    `frontEnd` as one tag. The audit uses this to report near-duplicates and
    retrieval uses it to match a `--tag` filter, so a Vault carrying
    `spring-boot` answers a query for `springboot`.
    """
    key = tag.lower().replace("_", "").replace("-", "").replace(" ", "")
    if len(key) > 1 and key.endswith("s"):
        key = key[:-1]
    return key
