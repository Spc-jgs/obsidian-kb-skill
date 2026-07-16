# Shared Note Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace duplicated note metadata, frontmatter parsing primitives, and Folder Index policy imports with small public domain modules while preserving all current CLI behavior and generated payloads.

**Architecture:** Add immutable catalog and parse-result contracts under `obsidian_kb_skill/scripts/`, then migrate one consumer group at a time. Keep compatibility exports in `note_types.py` and consumer-specific error presentation so this structural branch does not silently tighten Inbox behavior; `fix/inbox-data-safety` will consume the shared error result in the next branch. Move Folder Index ownership and static-index append decisions out of `audit_vault.py` and `process_inbox.py` into a public policy module.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, PyYAML, pytest, existing `uv` locked environment and `build.py` generated-tree sync.

## Global Constraints

- Work only on branch `fix/shared-note-domain` in its own worktree; never modify `master`.
- Preserve documented CLI arguments, exit codes, JSON keys, rendered notes, routing, audit finding codes, installer behavior, and standard Skill manifest contents except hashes caused by the intentional Python source changes. Internal calls that violate existing Vault-containment invariants may become explicit errors.
- Do not add `inbox-note`, confidence scoring, transactional Inbox writes, template content, migration behavior, or README changes in this branch.
- The canonical Python source remains `obsidian_kb_skill/`; run `python build.py` to regenerate the standard Skill copy.
- All production edits follow RED → GREEN → REFACTOR. A test that passes before its implementation change is not evidence for that change.
- Every task ends with targeted tests, full relevant regression tests, `build.py --check`, and a focused commit.

## File Structure

- Create `obsidian_kb_skill/scripts/note_catalog.py`: immutable note specifications and derived public mappings/sets.
- Modify `obsidian_kb_skill/scripts/note_types.py`: compatibility re-exports only.
- Create `obsidian_kb_skill/scripts/frontmatter.py`: normalized parse result, structured parse issue, and portable scalar conversion.
- Create `obsidian_kb_skill/scripts/folder_index_policy.py`: Folder Index config, exclusions, expected index path, and safe static-index append policy.
- Modify consumers in `audit_vault.py`, `create_note.py`, `template_contract.py`, `process_inbox.py`, `create_category.py`, `detect_index.py`, `vault_info.py`, and `suggest_links.py` to import public contracts.
- Create `tests/test_note_catalog.py`, `tests/test_frontmatter.py`, and `tests/test_folder_index_policy.py` for focused domain behavior.
- Modify existing consumer tests only to add compatibility assertions; do not rewrite expected behavior to fit the refactor.

---

### Task 1: Establish the Canonical Note Catalog

**Files:**
- Create: `tests/test_note_catalog.py`
- Create: `obsidian_kb_skill/scripts/note_catalog.py`
- Modify: `obsidian_kb_skill/scripts/note_types.py`

**Interfaces:**
- Produces: `NoteTypeSpec`, `NOTE_TYPES`, `TYPE_TO_TEMPLATE`, `TYPE_TO_TEMPLATE_ASSET`, `TYPE_TO_FOLDER`, `DEFAULT_TAG_BY_TYPE`, `FOLDER_TO_DEFAULT_TYPE`, `AUDIT_COMPATIBILITY_TYPES`, `VALID_NOTE_TYPES`, `MANAGED_NOTE_FOLDERS`, `STANDARD_NOTE_FOLDERS`.
- Preserves: imports of `TYPE_TO_TEMPLATE` and `TYPE_TO_TEMPLATE_ASSET` from `note_types.py`.

- [ ] **Step 1: Write the failing catalog consistency tests**

Create `tests/test_note_catalog.py` with table-driven assertions:

```python
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
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_note_catalog.py -q
```

Expected: collection fails with `ModuleNotFoundError: obsidian_kb_skill.scripts.note_catalog`.

- [ ] **Step 3: Implement the immutable catalog**

Create `note_catalog.py` with one source record per supported operational type:

```python
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
```

Change `note_types.py` to import and re-export the two historical mappings. Do
not leave a second literal mapping in that file.

- [ ] **Step 4: Run GREEN and compatibility tests**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_note_catalog.py \
  tests/test_template_contract.py \
  tests/test_create_note.py \
  tests/test_vault_info.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_note_catalog.py \
  obsidian_kb_skill/scripts/note_catalog.py \
  obsidian_kb_skill/scripts/note_types.py
git commit -m "refactor: centralize note type catalog"
```

### Task 2: Migrate Catalog Consumers Without Behavior Changes

**Files:**
- Modify: `obsidian_kb_skill/scripts/audit_vault.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Modify: `obsidian_kb_skill/scripts/process_inbox.py`
- Modify: `obsidian_kb_skill/scripts/create_category.py`
- Modify: `obsidian_kb_skill/scripts/vault_info.py`
- Modify: `tests/test_note_catalog.py`

**Interfaces:**
- Consumes: public mappings and sets from Task 1.
- Removes: consumer-owned literals `REQUIRED_TYPES`, `DEFAULT_TAG_BY_TYPE`,
  `TYPE_TO_FOLDER`, `DEFAULT_TAG_BY_FOLDER`, `FOLDER_TO_DEFAULT_TYPE`,
  `NOTE_FOLDERS`, and `STANDARD_NOTE_FOLDERS` where they duplicate the catalog.

- [ ] **Step 1: Add a failing source-boundary test**

Append to `tests/test_note_catalog.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_catalog_literals_have_one_owner():
    forbidden = {
        "audit_vault.py": "REQUIRED_TYPES =",
        "create_note.py": "DEFAULT_TAG_BY_TYPE =",
        "process_inbox.py": "TYPE_TO_FOLDER =",
        "create_category.py": "STANDARD_NOTE_FOLDERS =",
        "vault_info.py": "NOTE_FOLDERS =",
    }
    scripts = ROOT / "obsidian_kb_skill" / "scripts"
    for filename, marker in forbidden.items():
        assert marker not in (scripts / filename).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_note_catalog.py::test_catalog_literals_have_one_owner -q
```

Expected: FAIL and identify the first duplicated literal owner.

- [ ] **Step 3: Replace consumer literals with catalog imports**

Use these derivations:

```python
# audit_vault.py
from obsidian_kb_skill.scripts.note_catalog import VALID_NOTE_TYPES

# create_note.py
from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE, TYPE_TO_FOLDER, TYPE_TO_TEMPLATE,
)

# process_inbox.py
from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE, FOLDER_TO_DEFAULT_TYPE, TYPE_TO_FOLDER,
)
DEFAULT_TAG_BY_FOLDER = {
    folder: DEFAULT_TAG_BY_TYPE[note_type]
    for folder, note_type in FOLDER_TO_DEFAULT_TYPE.items()
}

# create_category.py and vault_info.py
from obsidian_kb_skill.scripts.note_catalog import (
    MANAGED_NOTE_FOLDERS, STANDARD_NOTE_FOLDERS,
)
NOTE_FOLDERS = list(MANAGED_NOTE_FOLDERS)
```

Preserve existing ordering in `vault-info` output explicitly; do not rely on set
iteration. Use `VALID_NOTE_TYPES` in audit without changing finding messages.

- [ ] **Step 4: Run GREEN and routing regressions**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_note_catalog.py \
  tests/test_audit_vault.py \
  tests/test_create_note.py \
  tests/test_process_inbox.py \
  tests/test_create_category.py \
  tests/test_vault_info.py \
  tests/test_json_output.py -q
```

Expected: all selected tests pass with unchanged JSON snapshots and routes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_note_catalog.py obsidian_kb_skill/scripts/{audit_vault.py,create_note.py,process_inbox.py,create_category.py,vault_info.py}
git commit -m "refactor: consume shared note catalog"
```

### Task 3: Add a Shared Frontmatter Parse Result

**Files:**
- Create: `tests/test_frontmatter.py`
- Create: `obsidian_kb_skill/scripts/frontmatter.py`

**Interfaces:**
- Produces: `FrontmatterIssue`, `FrontmatterResult`, `parse_frontmatter()`,
  `portable_yaml_scalars()`.
- Does not yet decide whether a consumer must reject an issue; callers preserve
  their existing presentation until the Inbox safety branch.

- [ ] **Step 1: Write failing parser contract tests**

Create `tests/test_frontmatter.py`:

```python
import datetime

from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    portable_yaml_scalars,
)


def test_parse_normalizes_bom_crlf_and_dates():
    result = parse_frontmatter(
        "\ufeff---\r\npublished: 2026-07-13\r\n---\r\n# Body\r\n",
        source="stdin",
    )
    assert result.present is True
    assert result.issue is None
    assert result.metadata == {"published": datetime.date(2026, 7, 13)}
    assert result.body == "# Body\n"


def test_parse_reports_malformed_yaml_without_discarding_original_text():
    source = "---\ntags: [broken\n---\n# Body\n"
    result = parse_frontmatter(source, source="Inbox/bad.md")
    assert result.metadata is None
    assert result.body == source
    assert result.issue.code == "invalid-frontmatter"
    assert result.issue.source == "Inbox/bad.md"
    assert result.issue.line == 2


def test_parse_reports_unclosed_and_non_mapping_blocks():
    unclosed = parse_frontmatter("---\ntype: insight-note\n# Body\n")
    scalar = parse_frontmatter("---\nscalar\n---\n# Body\n")
    assert unclosed.issue.code == "unclosed-frontmatter"
    assert unclosed.body.startswith("---\n")
    assert scalar.issue.code == "frontmatter-not-mapping"
    assert scalar.body.startswith("---\n")


def test_missing_frontmatter_is_not_an_error():
    result = parse_frontmatter("# Body\n")
    assert result.present is False
    assert result.metadata is None
    assert result.issue is None
    assert result.body == "# Body\n"


def test_portable_scalars_convert_nested_dates_and_tuples():
    value = {"when": datetime.date(2026, 7, 13), "items": (datetime.datetime(2026, 7, 13, 1, 2),)}
    assert portable_yaml_scalars(value) == {
        "when": "2026-07-13", "items": ["2026-07-13T01:02:00"]
    }
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_frontmatter.py -q
```

Expected: collection fails because the module does not exist.

- [ ] **Step 3: Implement the parse result**

Use immutable dataclasses:

```python
@dataclass(frozen=True)
class FrontmatterIssue:
    code: str
    source: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class FrontmatterResult:
    present: bool
    metadata: dict[str, Any] | None
    body: str
    normalized_text: str
    issue: FrontmatterIssue | None
```

`parse_frontmatter()` must:

1. remove one UTF-8 BOM and normalize line endings;
2. return `present=False` for ordinary Markdown;
3. preserve the complete normalized input in `body` when the block is unclosed,
   malformed, or not a mapping;
4. return parsed metadata and only the Markdown body on success;
5. report YAML line numbers relative to the complete input;
6. never mutate or stringify parsed scalar types.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_frontmatter.py -q
```

Expected: all parser contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_frontmatter.py obsidian_kb_skill/scripts/frontmatter.py
git commit -m "refactor: add shared frontmatter parser"
```

### Task 4: Migrate Frontmatter Consumers Through Compatibility Adapters

**Files:**
- Modify: `obsidian_kb_skill/scripts/audit_vault.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Modify: `obsidian_kb_skill/scripts/template_contract.py`
- Modify: `obsidian_kb_skill/scripts/process_inbox.py`
- Modify: `obsidian_kb_skill/scripts/suggest_links.py`
- Modify: `obsidian_kb_skill/scripts/create_category.py`
- Modify: `tests/test_frontmatter.py`
- Modify: `tests/test_create_note.py`
- Modify: `tests/test_template_contract.py`

**Interfaces:**
- Consumes: `parse_frontmatter()` and `portable_yaml_scalars()`.
- Preserves: `create_note.InvalidFrontmatterError` payload, audit `_frontmatter()`
  tuple compatibility during this branch, and current Inbox behavior until the
  next safety branch supplies a failing mutation test.

- [ ] **Step 1: Add failing ownership and compatibility tests**

Append a source-boundary assertion to `tests/test_frontmatter.py`:

```python
from pathlib import Path


def test_frontmatter_yaml_parsing_has_one_owner():
    scripts = Path(__file__).resolve().parent.parent / "obsidian_kb_skill" / "scripts"
    for filename in (
        "audit_vault.py", "create_note.py", "template_contract.py",
    ):
        text = (scripts / filename).read_text(encoding="utf-8")
        assert "yaml.safe_load(" not in text, filename
```

Add to `tests/test_create_note.py`:

```python
def test_split_frontmatter_preserves_current_non_mapping_compatibility():
    source = "---\n- one\n- two\n---\n# Body\n"
    metadata, body = split_frontmatter(source)
    assert metadata == {}
    assert body == source
```

Keep the existing malformed-YAML location test unchanged.

- [ ] **Step 2: Run RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_frontmatter.py::test_frontmatter_yaml_parsing_has_one_owner \
  tests/test_create_note.py::test_split_frontmatter_preserves_current_non_mapping_compatibility -q
```

Expected: ownership fails because three consumers still call `yaml.safe_load`.

- [ ] **Step 3: Replace parser implementations with adapters**

Implement consumer adapters with explicit compatibility:

- `audit_vault._frontmatter(text)` calls `parse_frontmatter(text, source="note")`;
  returns `(None, None)` when absent, `(metadata, None)` on success, and
  `(None, issue.message)` on an issue.
- `create_note.split_frontmatter(text, source)` returns `({}, normalized_text)`
  when absent; converts only `invalid-frontmatter` into the existing
  `InvalidFrontmatterError` shape; preserves current input-as-body behavior for
  unclosed and non-mapping blocks. The next safety branch will deliberately
  tighten Inbox, not this adapter.
- `template_contract._split_frontmatter()` converts every issue into its existing
  `TemplateFrontmatterError` and uses `portable_yaml_scalars()`.
- `process_inbox`, `suggest_links`, and `create_category` import a public adapter
  or `parse_frontmatter`; they no longer import `_frontmatter` from audit.

Remove duplicate recursive scalar normalization from `create_note.py` and
`template_contract.py` after all their tests use `portable_yaml_scalars()`.

- [ ] **Step 4: Run GREEN and cross-consumer regression tests**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_frontmatter.py \
  tests/test_create_note.py \
  tests/test_template_contract.py \
  tests/test_audit_vault.py \
  tests/test_process_inbox.py \
  tests/test_suggest_links.py \
  tests/test_create_category.py \
  tests/test_json_output.py -q
```

Expected: all selected tests pass; existing CLI error locations and JSON remain
unchanged.

- [ ] **Step 5: Commit**

```bash
git add tests/test_frontmatter.py tests/test_create_note.py \
  tests/test_template_contract.py obsidian_kb_skill/scripts/{audit_vault.py,create_note.py,template_contract.py,process_inbox.py,suggest_links.py,create_category.py}
git commit -m "refactor: share frontmatter parsing contracts"
```

### Task 5: Extract Folder Index Ownership and Static Append Policy

**Files:**
- Create: `tests/test_folder_index_policy.py`
- Create: `obsidian_kb_skill/scripts/folder_index_policy.py`
- Modify: `obsidian_kb_skill/scripts/audit_vault.py`
- Modify: `obsidian_kb_skill/scripts/process_inbox.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Modify: `obsidian_kb_skill/scripts/create_category.py`
- Modify: `obsidian_kb_skill/scripts/detect_index.py`
- Modify: `obsidian_kb_skill/scripts/vault_info.py`
- Modify: `tests/test_create_category.py`

**Interfaces:**
- Produces: `FolderIndexConfig`, `read_folder_index_config()`,
  `is_folder_index_excluded()`, `expected_folder_index()`,
  `StaticIndexEntry`, `append_static_index_entry()`.
- Removes: all production imports of `_folder_index_config`,
  `_is_folder_index_excluded`, and `_maybe_update_static_index`.

- [ ] **Step 1: Write failing public policy tests**

Create `tests/test_folder_index_policy.py` covering:

```python
def test_disabled_plugin_uses_default_config(tmp_path): ...
def test_enabled_plugin_reads_native_and_custom_settings(tmp_path): ...
def test_excluded_folder_and_glob_are_not_skill_owned(tmp_path): ...
def test_expected_index_name_handles_root_native_and_custom(tmp_path): ...
def test_static_append_skips_folder_index_and_dataview(tmp_path): ...
def test_static_append_is_idempotent(tmp_path): ...
def test_static_append_writes_exact_relative_link_and_date(tmp_path): ...
```

Use this typed append interface in the tests:

```python
entry = StaticIndexEntry(
    note=Path("30-Insights/idea.md"),
    title="Idea",
    date="2026-07-16",
)
result = append_static_index_entry(vault, entry)
assert result.status in {"appended", "already-present", "unmanaged", "missing"}
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_folder_index_policy.py -q
```

Expected: collection fails because the public module does not exist.

- [ ] **Step 3: Implement policy by moving existing proven behavior**

Move, without semantic expansion:

- `FolderIndexConfig`, JSON settings read, exclusions, and expected path from
  `audit_vault.py`;
- static `INDEX.md` ownership checks and append format from `process_inbox.py`.

Return a small immutable result rather than printing. Keep Folder Index and
Dataview listings untouched. Reject an entry whose note path is outside the
Vault or whose target folder resolves outside the Vault by using `vault_paths`.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_folder_index_policy.py -q
```

Expected: all focused policy tests pass.

- [ ] **Step 5: Migrate every consumer and remove private imports**

Use public imports in audit, process Inbox, create note/category, detect index,
and vault info. Preserve wrapper aliases only if an external test imports them;
production modules may not import those aliases from one another.

Replace plan-dict coupling in `create_note.py` and `process_inbox.py` with:

```python
append_static_index_entry(
    vault,
    StaticIndexEntry(
        note=destination.relative_to(vault),
        title=title,
        date=date,
    ),
)
```

- [ ] **Step 6: Add and run the private-import boundary test**

Append to `tests/test_folder_index_policy.py`:

```python
def test_production_modules_do_not_import_audit_or_inbox_private_policy():
    scripts = Path(__file__).resolve().parent.parent / "obsidian_kb_skill" / "scripts"
    for path in scripts.glob("*.py"):
        if path.name in {"audit_vault.py", "process_inbox.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "_folder_index_config" not in text, path.name
        assert "_is_folder_index_excluded" not in text, path.name
        assert "_maybe_update_static_index" not in text, path.name
```

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py \
  tests/test_audit_vault.py \
  tests/test_process_inbox.py \
  tests/test_create_note.py \
  tests/test_create_category.py \
  tests/test_detect_index.py \
  tests/test_vault_info.py \
  tests/test_json_output.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/test_folder_index_policy.py tests/test_create_category.py \
  obsidian_kb_skill/scripts/{folder_index_policy.py,audit_vault.py,process_inbox.py,create_note.py,create_category.py,detect_index.py,vault_info.py}
git commit -m "refactor: extract folder index policy"
```

### Task 6: Regenerate the Standard Skill and Verify the Branch

**Files:**
- Regenerate: `skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/**`
- Regenerate: `skills/obsidian-knowledge-base/manifest.json`
- Verify: all source, package, build, wheel, and installed-runner tests.

**Interfaces:**
- Consumes: canonical Python modules from Tasks 1–5.
- Produces: synchronized standard Skill payload with a valid manifest.

- [ ] **Step 1: Regenerate all intentional mirrors**

Run:

```bash
uv run --locked --extra dev python build.py
```

Expected: the standard Skill Python tree and manifest update; platform/reference
and template trees remain content-identical to their canonical sources.

- [ ] **Step 2: Verify generated-tree integrity**

Run:

```bash
uv run --locked --extra dev python build.py --check
uv run --locked --extra dev pytest tests/test_build.py tests/test_skill_runtime.py tests/test_doctor.py -q
```

Expected: build check passes and installed Skill runtime tests pass.

- [ ] **Step 3: Run the complete test suite**

Run:

```bash
uv run --locked --extra dev pytest
```

Expected: all tests pass with no warnings or errors.

- [ ] **Step 4: Verify packaging and hostile-CWD execution**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_wheel_install.py \
  tests/test_installers.py \
  tests/test_environment_contract.py -q
```

Expected: wheel/sdist resources, console scripts, Bash installer lifecycle, and
the checked Windows smoke contract remain green.

- [ ] **Step 5: Audit the final diff**

Run:

```bash
git diff --check design/skill-evolution-roadmap...HEAD
git diff --stat design/skill-evolution-roadmap...HEAD
rg -n 'from obsidian_kb_skill\.scripts\.audit_vault import.*_|from obsidian_kb_skill\.scripts\.process_inbox import.*_' obsidian_kb_skill/scripts || true
git status --short
```

Expected: no whitespace errors, no unintended documentation/template/installer
changes, no cross-module private imports, and only planned source/generated/test
files changed.

- [ ] **Step 6: Commit generated artifacts**

```bash
git add skills/obsidian-knowledge-base/scripts/obsidian_kb_skill \
  skills/obsidian-knowledge-base/manifest.json
git commit -m "build: sync shared note domain runtime"
```

If `build.py` regenerated canonical-source files already committed in earlier
tasks, this final commit contains only generated payload and manifest changes.

## Completion Evidence

The branch is complete only when:

1. catalog, frontmatter, and Folder Index public contract tests pass;
2. all current behavior-facing tests pass without changed expectations;
3. no production consumer imports private audit/Inbox policy helpers;
4. `build.py --check` passes;
5. the full pytest suite and packaging/installer subsets pass;
6. the diff contains no Inbox lifecycle, template, README, token-budget, or
   installer-refactor work;
7. the branch can be reverted without reverting the accepted roadmap design or
   any later Inbox data-safety commit.
