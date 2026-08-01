# Review package: fde3337..604b64a

## Commits
604b64a fix: normalize unsafe index filename encoding
d1eb034 refactor: plan inbox index updates without writes

## Files changed
 obsidian_kb_skill/scripts/folder_index_policy.py | 242 ++++++++++++++--
 obsidian_kb_skill/scripts/inbox_plan.py          |  35 ++-
 tests/test_folder_index_policy.py                | 353 +++++++++++++++++++++++
 tests/test_inbox_plan.py                         | 120 +++++++-
 4 files changed, 722 insertions(+), 28 deletions(-)

## Diff
diff --git a/obsidian_kb_skill/scripts/folder_index_policy.py b/obsidian_kb_skill/scripts/folder_index_policy.py
index 3537c47..6c122b9 100644
--- a/obsidian_kb_skill/scripts/folder_index_policy.py
+++ b/obsidian_kb_skill/scripts/folder_index_policy.py
@@ -1,19 +1,21 @@
 #!/usr/bin/env python3
 """Folder Index ownership and static ``INDEX.md`` append policy."""
 from __future__ import annotations
 
 import fnmatch
+import hashlib
 import json
+import os
 from dataclasses import dataclass
 from pathlib import Path
-from typing import Any
+from typing import Any, Literal
 
 from obsidian_kb_skill.scripts.vault_paths import (
     resolve_target_within_vault,
     validate_vault_root,
 )
 
 
 INVALID_FILENAME_CHARS = frozenset('/\\:*?"<>|')
 WINDOWS_RESERVED_FILENAMES = frozenset(
     {"CON", "PRN", "AUX", "NUL"}
@@ -26,38 +28,56 @@ class FolderIndexConfigError(ValueError):
     """A stable validation failure for a Folder Index filename setting."""
 
     code = "invalid-folder-index-config"
 
     def __init__(self, field: str) -> None:
         self.field = field
         self.message = f"{field} must be a portable visible basename"
         super().__init__(self.message)
 
 
+class _StrictFolderIndexConfigError(ValueError):
+    """Configuration uncertainty that legacy readers intentionally default."""
+
+
 @dataclass(frozen=True)
 class FolderIndexConfig:
     enabled: bool = False
     graph_overwrite: bool = False
     root_index_file: str = "INDEX.md"
     user_specified: bool = False
     index_filename: str = "INDEX"
     exclude_folders: tuple[str, ...] = ()
     exclude_patterns: tuple[str, ...] = ()
 
 
 @dataclass(frozen=True)
 class StaticIndexEntry:
     note: Path
     title: str
     date: str
 
 
+StaticIndexAction = Literal["append", "unchanged", "missing", "unmanaged"]
+
+
+@dataclass(frozen=True)
+class StaticIndexPlan:
+    action: StaticIndexAction
+    index: Path | None
+    before: bytes | None
+    after: bytes | None
+    before_sha256: str | None
+    after_sha256: str | None
+    line: str | None
+
+
 @dataclass(frozen=True)
 class StaticIndexResult:
     status: str
     index: Path | None
 
 
 IGNORED_PARTS = {
     ".git",
     ".obsidian",
     ".obsidian-kb-backups",
@@ -101,43 +121,133 @@ def read_folder_index_config(vault: Path) -> FolderIndexConfig:
             str(item).strip("/")
             for item in settings.get("excludeFolders", [])
             if str(item)
         ),
         exclude_patterns=tuple(
             str(item) for item in settings.get("excludePatterns", []) if str(item)
         ),
     )
 
 
+def _read_strict_json(path: Path, default: Any, *, label: str) -> Any:
+    try:
+        payload = path.read_bytes()
+    except FileNotFoundError:
+        return default
+    except OSError as exc:
+        raise _StrictFolderIndexConfigError(
+            f"{label} could not be read safely"
+        ) from exc
+    try:
+        return json.loads(payload.decode("utf-8"))
+    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
+        raise _StrictFolderIndexConfigError(
+            f"{label} is not valid UTF-8 JSON"
+        ) from exc
+
+
+def _strict_folder_index_config(vault: Path) -> FolderIndexConfig:
+    """Read ownership configuration without converting uncertainty to defaults."""
+    community_path = resolve_target_within_vault(
+        vault,
+        Path(".obsidian/community-plugins.json"),
+        label="enabled plugin configuration",
+    )
+    enabled = _read_strict_json(
+        community_path, [], label="enabled plugin configuration"
+    )
+    if not isinstance(enabled, list) or not all(
+        isinstance(item, str) for item in enabled
+    ):
+        raise _StrictFolderIndexConfigError(
+            "enabled plugin configuration must be a JSON list of names"
+        )
+    if "obsidian-folder-index" not in enabled:
+        return FolderIndexConfig()
+
+    settings_path = resolve_target_within_vault(
+        vault,
+        Path(".obsidian/plugins/obsidian-folder-index/data.json"),
+        label="Folder Index configuration",
+    )
+    settings = _read_strict_json(
+        settings_path, {}, label="Folder Index configuration"
+    )
+    if not isinstance(settings, dict):
+        raise _StrictFolderIndexConfigError(
+            "Folder Index configuration must be a JSON object"
+        )
+    for field in ("rootIndexFile", "indexFilename"):
+        if field in settings and not isinstance(settings[field], str):
+            raise _StrictFolderIndexConfigError(
+                f"Folder Index configuration {field} must be text"
+            )
+    for field in ("graphOverwrite", "indexFileUserSpecified"):
+        if field in settings and not isinstance(settings[field], bool):
+            raise _StrictFolderIndexConfigError(
+                f"Folder Index configuration {field} must be boolean"
+            )
+    for field in ("excludeFolders", "excludePatterns"):
+        if field in settings and not (
+            isinstance(settings[field], list)
+            and all(isinstance(item, str) for item in settings[field])
+        ):
+            raise _StrictFolderIndexConfigError(
+                f"Folder Index configuration {field} must be text list"
+            )
+
+    config = FolderIndexConfig(
+        enabled=True,
+        graph_overwrite=settings.get("graphOverwrite", False),
+        root_index_file=settings.get("rootIndexFile", "INDEX.md"),
+        user_specified=settings.get("indexFileUserSpecified", False),
+        index_filename=settings.get("indexFilename", "INDEX"),
+        exclude_folders=tuple(
+            item.strip("/") for item in settings.get("excludeFolders", []) if item
+        ),
+        exclude_patterns=tuple(
+            item for item in settings.get("excludePatterns", []) if item
+        ),
+    )
+    _validate_index_basename(config.root_index_file, field="root_index_file")
+    if config.user_specified:
+        _validate_index_basename(config.index_filename, field="index_filename")
+    return config
+
+
 def is_folder_index_excluded(relative: Path, config: FolderIndexConfig) -> bool:
     if _is_ignored(relative):
         return True
     value = relative.as_posix()
     for excluded in config.exclude_folders:
         if value == excluded or value.startswith(f"{excluded}/"):
             return True
     return any(
         fnmatch.fnmatch(value, pattern) or fnmatch.fnmatch(relative.name, pattern)
         for pattern in config.exclude_patterns
     )
 
 
 def _validate_index_basename(value: str, *, field: str) -> str:
+    try:
+        encoded = value.encode("utf-8")
+    except UnicodeEncodeError:
+        raise FolderIndexConfigError(field) from None
     windows_stem = value.split(".", 1)[0].upper()
     if (
         not value
         or value != value.strip()
         or value in {".", ".."}
         or value.startswith(".")
         or value.endswith(".")
         or windows_stem in WINDOWS_RESERVED_FILENAMES
-        or len(value.encode("utf-8")) > 255
+        or len(encoded) > 255
         or any(
             ord(character) < 32 or character in INVALID_FILENAME_CHARS
             for character in value
         )
     ):
         raise FolderIndexConfigError(field)
     return value
 
 
 def expected_folder_index(
@@ -155,49 +265,143 @@ def expected_folder_index(
             config.index_filename, field="index_filename"
         )
         name = f"{basename}.md"
     else:
         name = f"{target_folder.name}.md"
     return resolve_target_within_vault(
         root, target_folder / name, label="folder index"
     )
 
 
-def append_static_index_entry(
-    vault: Path, entry: StaticIndexEntry
-) -> StaticIndexResult:
-    root = validate_vault_root(vault)
+def _sha256_bytes(payload: bytes) -> str:
+    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
+
+
+def _logical_note_path(vault: Path, root: Path, entry: StaticIndexEntry) -> Path:
     physical_note = resolve_target_within_vault(root, entry.note, label="note")
     logical_note = entry.note.expanduser()
     if logical_note.is_absolute():
         lexical_root = Path(vault).expanduser().absolute()
         try:
             logical_note = logical_note.relative_to(lexical_root)
         except ValueError:
             try:
                 logical_note = logical_note.relative_to(root)
             except ValueError:
                 logical_note = physical_note.relative_to(root)
+    return logical_note
+
+
+def _static_index_newline(before: bytes) -> bytes:
+    newline_at = before.find(b"\n")
+    if newline_at > 0 and before[newline_at - 1:newline_at] == b"\r":
+        return b"\r\n"
+    return b"\n"
+
+
+def _unmanaged_plan(index: Path, before: bytes) -> StaticIndexPlan:
+    digest = _sha256_bytes(before)
+    return StaticIndexPlan(
+        action="unmanaged",
+        index=index,
+        before=before,
+        after=before,
+        before_sha256=digest,
+        after_sha256=digest,
+        line=None,
+    )
+
+
+def _plan_static_index_entry_with_config(
+    vault: Path,
+    root: Path,
+    entry: StaticIndexEntry,
+    config: FolderIndexConfig,
+) -> StaticIndexPlan:
+    logical_note = _logical_note_path(vault, root, entry)
+    if "\r" in entry.title or "\n" in entry.title:
+        raise ValueError("static index title must not contain a line break")
+    link = logical_note.with_suffix("").as_posix()
+    if "\r" in link or "\n" in link or "\r" in entry.date or "\n" in entry.date:
+        raise ValueError("static index entry must fit on one line")
     target = resolve_target_within_vault(
         root, logical_note.parent, label="target folder"
     )
     target_relative = target.relative_to(root)
     index = resolve_target_within_vault(
         root, target_relative / "INDEX.md", label="static index"
     )
 
-    config = read_folder_index_config(root)
-    if config.enabled and not is_folder_index_excluded(logical_note.parent, config):
-        return StaticIndexResult("unmanaged", index if index.is_file() else None)
+    if config.enabled and not is_folder_index_excluded(
+        logical_note.parent, config
+    ):
+        if index.is_file():
+            before = index.read_bytes()
+            return _unmanaged_plan(index.relative_to(root), before)
+        return StaticIndexPlan("unmanaged", None, None, None, None, None, None)
     if not index.is_file():
-        return StaticIndexResult("missing", None)
-    index_text = index.read_text(encoding="utf-8")
-    if "folder-index-content" in index_text or "dataview" in index_text:
-        return StaticIndexResult("unmanaged", index)
-
-    line = (
-        f"- [[{logical_note.with_suffix('').as_posix()}|{entry.title}]] "
-        f"({entry.date})\n"
+        if os.path.lexists(index):
+            raise ValueError("static index is not a regular file")
+        return StaticIndexPlan("missing", None, None, None, None, None, None)
+
+    before = index.read_bytes()
+    relative_index = index.relative_to(root)
+    if b"folder-index-content" in before or b"dataview" in before:
+        return _unmanaged_plan(relative_index, before)
+
+    newline = _static_index_newline(before)
+    line_bytes = (
+        f"- [[{link}|{entry.title}]] ({entry.date})".encode("utf-8") + newline
     )
-    with index.open("a", encoding="utf-8") as handle:
-        handle.write(line)
+    line = line_bytes.decode("utf-8")
+    bare_line = line_bytes.removesuffix(newline)
+    if bare_line in before.splitlines():
+        digest = _sha256_bytes(before)
+        return StaticIndexPlan(
+            action="unchanged",
+            index=relative_index,
+            before=before,
+            after=before,
+            before_sha256=digest,
+            after_sha256=digest,
+            line=line,
+        )
+
+    separator = b"" if not before or before.endswith((b"\n", b"\r")) else newline
+    after = before + separator + line_bytes
+    return StaticIndexPlan(
+        action="append",
+        index=relative_index,
+        before=before,
+        after=after,
+        before_sha256=_sha256_bytes(before),
+        after_sha256=_sha256_bytes(after),
+        line=line,
+    )
+
+
+def plan_static_index_entry(
+    vault: Path, entry: StaticIndexEntry
+) -> StaticIndexPlan:
+    """Freeze one strict, read-only, byte-exact static index proposal."""
+    root = validate_vault_root(vault)
+    config = _strict_folder_index_config(root)
+    return _plan_static_index_entry_with_config(vault, root, entry, config)
+
+
+def append_static_index_entry(
+    vault: Path, entry: StaticIndexEntry
+) -> StaticIndexResult:
+    root = validate_vault_root(vault)
+    try:
+        config = _strict_folder_index_config(root)
+    except (_StrictFolderIndexConfigError, FolderIndexConfigError):
+        config = read_folder_index_config(root)
+    plan = _plan_static_index_entry_with_config(vault, root, entry, config)
+    index = root / plan.index if plan.index is not None else None
+    if plan.action != "append":
+        return StaticIndexResult(plan.action, index)
+
+    assert index is not None and plan.before is not None and plan.after is not None
+    with index.open("ab") as handle:
+        handle.write(plan.after[len(plan.before):])
     return StaticIndexResult("appended", index)
diff --git a/obsidian_kb_skill/scripts/inbox_plan.py b/obsidian_kb_skill/scripts/inbox_plan.py
index bbf718f..32ae55f 100644
--- a/obsidian_kb_skill/scripts/inbox_plan.py
+++ b/obsidian_kb_skill/scripts/inbox_plan.py
@@ -1,41 +1,42 @@
 """Read-only, immutable planning for Inbox source notes."""
 from __future__ import annotations
 
 import datetime
 import hashlib
 import os
 import re
 import stat
 from dataclasses import dataclass
 from pathlib import Path
-from typing import TYPE_CHECKING, Any, Literal, Mapping
+from typing import Any, Literal, Mapping
 
 import yaml
 from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
 
 from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
+from obsidian_kb_skill.scripts.folder_index_policy import (
+    StaticIndexEntry,
+    StaticIndexPlan,
+    plan_static_index_entry,
+)
 from obsidian_kb_skill.scripts.note_catalog import (
     DEFAULT_TAG_BY_TYPE,
     FOLDER_TO_DEFAULT_TYPE,
     TYPE_TO_FOLDER,
 )
 from obsidian_kb_skill.scripts.vault_paths import (
     VaultPathError,
     resolve_target_within_vault,
     validate_vault_root,
 )
 
-if TYPE_CHECKING:
-    from obsidian_kb_skill.scripts.folder_index_policy import StaticIndexPlan
-
-
 InboxStatus = Literal["ready", "skipped", "blocked"]
 
 # Trigger keywords (lowercased substrings) -> target folder. Keep this local to
 # Inbox planning so importing the pure planner does not pull in the CLI module.
 _KEYWORD_ROUTES = (
     (("meeting", "standup", "review", "sync"), "10-Work"),
     (("article", "learning", "book", "course", "tutorial"), "20-Learning"),
     (("web", "url", "blog", "clip"), "20-Learning"),
     (("analysis", "insight", "idea", "takeaway"), "30-Insights"),
     (("project", "milestone", "sprint"), "40-Projects"),
@@ -122,21 +123,21 @@ class InboxSourceSnapshot:
 
 @dataclass(frozen=True)
 class InboxProposal:
     destination: Path
     target: str
     note_type: str
     tags: tuple[str, ...]
     metadata_updates: tuple[tuple[str, object], ...]
     rendered_bytes: bytes
     rendered_sha256: str
-    index: StaticIndexPlan | None
+    index: StaticIndexPlan
 
 
 @dataclass(frozen=True)
 class InboxPlanItem:
     source: Path
     identity: SourceIdentity | None
     source_sha256: str | None
     title: str | None
     status: InboxStatus
     proposal: InboxProposal | None
@@ -727,29 +728,47 @@ def _plan_snapshot(root: Path, snapshot: InboxSourceSnapshot, date: str) -> Inbo
     try:
         rendered = render_frontmatter_updates(snapshot, dict(frozen_updates))
     except (TypeError, ValueError) as exc:
         return _issue_item(
             snapshot,
             title=title,
             status="blocked",
             issue=InboxIssue("invalid-rendered-frontmatter", str(exc)),
         )
 
+    destination_relative = resolved_destination.relative_to(root)
+    try:
+        index_plan = plan_static_index_entry(
+            root,
+            StaticIndexEntry(
+                note=destination,
+                title=title,
+                date=date,
+            ),
+        )
+    except (OSError, ValueError, VaultPathError) as exc:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue("unsafe-index-plan", str(exc)),
+        )
+
     proposal = InboxProposal(
-        destination=resolved_destination.relative_to(root),
+        destination=destination_relative,
         target=target,
         note_type=note_type,
         tags=tags,
         metadata_updates=frozen_updates,
         rendered_bytes=rendered,
         rendered_sha256=sha256_bytes(rendered),
-        index=None,
+        index=index_plan,
     )
     return InboxPlanItem(
         source=snapshot.source,
         identity=snapshot.identity,
         source_sha256=snapshot.sha256,
         title=title,
         status="ready",
         proposal=proposal,
         issue=None,
     )
diff --git a/tests/test_folder_index_policy.py b/tests/test_folder_index_policy.py
index 8ca55f4..6c0e5e5 100644
--- a/tests/test_folder_index_policy.py
+++ b/tests/test_folder_index_policy.py
@@ -1,24 +1,28 @@
 import ast
 import json
 from pathlib import Path
 
 import pytest
 
 from obsidian_kb_skill.scripts.folder_index_policy import (
     FolderIndexConfig,
+    FolderIndexConfigError,
     StaticIndexEntry,
+    StaticIndexPlan,
     append_static_index_entry,
     expected_folder_index,
     is_folder_index_excluded,
+    plan_static_index_entry,
     read_folder_index_config,
 )
+from obsidian_kb_skill.scripts.inbox_plan import sha256_bytes
 from obsidian_kb_skill.scripts.vault_paths import VaultPathError
 
 
 def make_vault(tmp_path: Path) -> Path:
     vault = tmp_path / "vault"
     (vault / ".obsidian" / "plugins" / "obsidian-folder-index").mkdir(
         parents=True
     )
     (vault / "30-Insights").mkdir()
     return vault
@@ -217,20 +221,369 @@ def test_static_append_writes_exact_relative_link_and_date(tmp_path: Path):
     result = append_static_index_entry(vault, StaticIndexEntry(
         note=Path("30-Insights/idea.md"), title="Idea", date="2026-07-16"
     ))
     assert result.status == "appended"
     assert result.index == index
     assert index.read_text(encoding="utf-8") == (
         "# Insights\n- [[30-Insights/idea|Idea]] (2026-07-16)\n"
     )
 
 
+def test_static_index_plan_is_read_only_and_byte_exact(tmp_path: Path):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Insights\r\n"
+    index.write_bytes(before)
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    line = "- [[30-Insights/Idea|Idea]] (2042-03-04)\r\n"
+    after = before + line.encode()
+    assert plan == StaticIndexPlan(
+        action="append",
+        index=Path("30-Insights/INDEX.md"),
+        before=before,
+        after=after,
+        before_sha256=sha256_bytes(before),
+        after_sha256=sha256_bytes(after),
+        line=line,
+    )
+    assert index.read_bytes() == before
+
+
+def test_static_index_plan_preserves_bom_crlf_and_missing_trailing_newline(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"\xef\xbb\xbf# Insights\r\nlast line"
+    index.write_bytes(before)
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    expected_line = "- [[30-Insights/Idea|Idea]] (2042-03-04)\r\n"
+    assert plan.before == before
+    assert plan.after == before + b"\r\n" + expected_line.encode()
+    assert plan.line == expected_line
+    assert index.read_bytes() == before
+
+
+def test_static_index_plan_reports_missing_without_writing(tmp_path: Path):
+    vault = make_vault(tmp_path)
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert plan.action == "missing"
+    assert plan.index is None
+    assert plan.before is None
+    assert plan.after is None
+    assert plan.before_sha256 is None
+    assert plan.after_sha256 is None
+    assert plan.line is None
+    assert not (vault / "30-Insights" / "INDEX.md").exists()
+
+
+def test_static_index_plan_reports_folder_index_and_dataview_as_unmanaged(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    folder_index_bytes = b"```folder-index-content\n```\n"
+    index.write_bytes(folder_index_bytes)
+
+    folder_index_plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert folder_index_plan.action == "unmanaged"
+    assert folder_index_plan.index == Path("30-Insights/INDEX.md")
+    assert folder_index_plan.before == folder_index_bytes
+    assert folder_index_plan.after == folder_index_bytes
+    assert folder_index_plan.before_sha256 == sha256_bytes(folder_index_bytes)
+    assert folder_index_plan.after_sha256 == sha256_bytes(folder_index_bytes)
+    assert folder_index_plan.line is None
+
+    dataview_bytes = b"```dataview\nLIST\n```\n"
+    index.write_bytes(dataview_bytes)
+    dataview_plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+    assert dataview_plan.action == "unmanaged"
+    assert dataview_plan.before == dataview_bytes
+    assert dataview_plan.after == dataview_bytes
+    assert index.read_bytes() == dataview_bytes
+
+
+def test_static_index_plan_reports_enabled_folder_index_as_unmanaged(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Legacy static index\n"
+    index.write_bytes(before)
+    enable_folder_index(vault, {})
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert plan.action == "unmanaged"
+    assert plan.index == Path("30-Insights/INDEX.md")
+    assert plan.before == before
+    assert plan.after == before
+    assert index.read_bytes() == before
+
+
+def test_static_index_plan_does_not_duplicate_an_existing_exact_entry(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = (
+        b"# Insights\n"
+        b"- [[30-Insights/Idea|Idea]] (2042-03-04)\n"
+    )
+    index.write_bytes(before)
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+    result = append_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert plan.action == "unchanged"
+    assert plan.before == before
+    assert plan.after == before
+    assert plan.before_sha256 == sha256_bytes(before)
+    assert plan.after_sha256 == sha256_bytes(before)
+    assert plan.line == "- [[30-Insights/Idea|Idea]] (2042-03-04)\n"
+    assert result.status == "unchanged"
+    assert result.index == index
+    assert index.read_bytes() == before
+
+
+@pytest.mark.parametrize(
+    ("config_path", "payload"),
+    [
+        (Path(".obsidian/community-plugins.json"), b"{malformed"),
+        (
+            Path(".obsidian/plugins/obsidian-folder-index/data.json"),
+            b"{malformed",
+        ),
+    ],
+)
+def test_static_index_plan_fails_closed_on_invalid_enabled_plugin_json(
+    tmp_path: Path, config_path: Path, payload: bytes
+):
+    vault = make_vault(tmp_path)
+    enable_folder_index(vault, {})
+    (vault / config_path).write_bytes(payload)
+
+    with pytest.raises(ValueError):
+        plan_static_index_entry(
+            vault,
+            StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+        )
+
+
+def test_static_append_keeps_legacy_defaults_for_invalid_plugin_json(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Insights\n"
+    index.write_bytes(before)
+    (vault / ".obsidian" / "community-plugins.json").write_bytes(b"{malformed")
+
+    result = append_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert result.status == "appended"
+    assert index.read_bytes() == (
+        before + b"- [[30-Insights/Idea|Idea]] (2042-03-04)\n"
+    )
+
+
+def test_static_append_keeps_enabled_defaults_for_invalid_plugin_data(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Plugin owned\n"
+    index.write_bytes(before)
+    enable_folder_index(vault, {})
+    (vault / ".obsidian" / "plugins" / "obsidian-folder-index" / "data.json").write_bytes(
+        b"{malformed"
+    )
+
+    result = append_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert result.status == "unmanaged"
+    assert result.index == index
+    assert index.read_bytes() == before
+
+
+@pytest.mark.parametrize(
+    "settings",
+    [
+        {"rootIndexFile": "../../outside.md"},
+        {
+            "indexFileUserSpecified": True,
+            "indexFilename": "../../outside",
+        },
+    ],
+)
+def test_static_index_plan_fails_closed_on_malicious_plugin_filenames(
+    tmp_path: Path, settings: dict
+):
+    vault = make_vault(tmp_path)
+    enable_folder_index(vault, settings)
+
+    with pytest.raises(ValueError):
+        plan_static_index_entry(
+            vault,
+            StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+        )
+    assert not (tmp_path / "outside.md").exists()
+
+
+@pytest.mark.parametrize(
+    ("settings", "field"),
+    [
+        ({"rootIndexFile": "\ud800"}, "root_index_file"),
+        (
+            {
+                "indexFileUserSpecified": True,
+                "indexFilename": "\ud800",
+            },
+            "index_filename",
+        ),
+    ],
+)
+def test_static_index_plan_normalizes_unpaired_surrogate_config_error(
+    tmp_path: Path, settings: dict, field: str
+) -> None:
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Plugin owned\n"
+    index.write_bytes(before)
+    enable_folder_index(vault, settings)
+
+    with pytest.raises(FolderIndexConfigError) as error:
+        plan_static_index_entry(
+            vault,
+            StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+        )
+
+    assert error.value.code == "invalid-folder-index-config"
+    assert error.value.field == field
+    assert index.read_bytes() == before
+
+
+@pytest.mark.parametrize(
+    "settings",
+    [
+        {"rootIndexFile": "\ud800"},
+        {
+            "indexFileUserSpecified": True,
+            "indexFilename": "\ud800",
+        },
+    ],
+)
+def test_static_append_uses_legacy_fallback_for_unpaired_surrogate_config(
+    tmp_path: Path, settings: dict
+) -> None:
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Plugin owned\n"
+    index.write_bytes(before)
+    enable_folder_index(vault, settings)
+
+    result = append_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert result.status == "unmanaged"
+    assert result.index == index
+    assert index.read_bytes() == before
+
+
+@pytest.mark.parametrize(
+    ("title", "with_index"),
+    [
+        ("First\nSecond", True),
+        ("First\rSecond", True),
+        ("First\nSecond", False),
+    ],
+)
+def test_static_index_plan_rejects_multiline_title_without_writing(
+    tmp_path: Path, title: str, with_index: bool
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Insights\n"
+    if with_index:
+        index.write_bytes(before)
+
+    with pytest.raises(ValueError, match="title"):
+        plan_static_index_entry(
+            vault,
+            StaticIndexEntry(Path("30-Insights/Idea.md"), title, "2042-03-04"),
+        )
+    if with_index:
+        assert index.read_bytes() == before
+    else:
+        assert not index.exists()
+
+
+def test_static_index_plan_keeps_physical_index_and_logical_symlink_link(
+    tmp_path: Path,
+):
+    vault = make_vault(tmp_path)
+    index = vault / "30-Insights" / "INDEX.md"
+    before = b"# Insights\n"
+    index.write_bytes(before)
+    make_directory_symlink(vault / "Alias", Path("30-Insights"))
+
+    plan = plan_static_index_entry(
+        vault,
+        StaticIndexEntry(Path("Alias/Idea.md"), "Idea", "2042-03-04"),
+    )
+
+    assert plan.action == "append"
+    assert plan.index == Path("30-Insights/INDEX.md")
+    assert plan.line == "- [[Alias/Idea|Idea]] (2042-03-04)\n"
+    assert plan.after == before + plan.line.encode()
+    assert index.read_bytes() == before
+
+
 def test_static_append_rejects_note_outside_vault(tmp_path: Path):
     vault = make_vault(tmp_path)
     with pytest.raises(VaultPathError):
         append_static_index_entry(vault, StaticIndexEntry(
             note=Path("../outside.md"), title="Outside", date="2026-07-16"
         ))
 
 
 def test_static_append_preserves_internal_alias_in_link(tmp_path: Path):
     vault = make_vault(tmp_path)
diff --git a/tests/test_inbox_plan.py b/tests/test_inbox_plan.py
index a5e7236..5f009b2 100644
--- a/tests/test_inbox_plan.py
+++ b/tests/test_inbox_plan.py
@@ -1,38 +1,45 @@
 from __future__ import annotations
 
 import os
 from dataclasses import replace
 from pathlib import Path
+from typing import get_type_hints
 
 import pytest
 
 import obsidian_kb_skill.scripts.inbox_plan as inbox_plan
 from obsidian_kb_skill.scripts.inbox_plan import (
     InboxPlanItem,
+    InboxProposal,
     legacy_plan_dict,
     plan_inbox,
     render_frontmatter_updates,
     sha256_bytes,
     snapshot_inbox_sources,
 )
 from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
+from obsidian_kb_skill.scripts.folder_index_policy import StaticIndexPlan
 
 
 def make_vault(tmp_path: Path) -> Path:
     vault = tmp_path / "vault"
     vault.mkdir()
     (vault / ".obsidian").mkdir()
     (vault / "00-Inbox").mkdir()
     return vault
 
 
+def test_inbox_proposal_requires_a_static_index_plan() -> None:
+    assert get_type_hints(InboxProposal)["index"] is StaticIndexPlan
+
+
 def make_symlink(target: Path, link: Path) -> None:
     try:
         link.symlink_to(target)
     except (OSError, NotImplementedError) as exc:
         pytest.skip(f"symlink creation unavailable: {exc}")
 
 
 def snapshot_one(tmp_path: Path, payload: bytes, name: str = "Note.md"):
     vault = make_vault(tmp_path)
     note = vault / "00-Inbox" / name
@@ -434,25 +441,136 @@ def test_plan_builds_frozen_ready_proposal_without_writing(tmp_path: Path) -> No
     assert item.proposal.note_type == "insight-note"
     assert item.proposal.tags == ("existing", "python")
     assert item.proposal.metadata_updates == (
         ("date", "2042-03-04"),
         ("type", "insight-note"),
     )
     assert item.proposal.rendered_sha256 == sha256_bytes(
         item.proposal.rendered_bytes
     )
     assert item.proposal.rendered_bytes.endswith(b"# Planned Insight\nidea body  \n")
-    assert item.proposal.index is None
+    assert item.proposal.index == StaticIndexPlan(
+        action="missing",
+        index=None,
+        before=None,
+        after=None,
+        before_sha256=None,
+        after_sha256=None,
+        line=None,
+    )
     assert note.read_bytes() == original
     assert not (vault / item.proposal.destination).exists()
 
 
+def test_plan_attaches_read_only_exact_static_index_proposal(tmp_path: Path) -> None:
+    original = b"# Planned Insight\nidea body\n"
+    vault, note, _snapshot = snapshot_one(tmp_path, original)
+    target = vault / "30-Insights"
+    target.mkdir()
+    index = target / "INDEX.md"
+    index_before = b"\xef\xbb\xbf# Insights\r\n"
+    index.write_bytes(index_before)
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "ready"
+    assert item.proposal is not None
+    line = "- [[30-Insights/Note|Planned Insight]] (2042-03-04)\r\n"
+    index_after = index_before + line.encode()
+    assert item.proposal.index == StaticIndexPlan(
+        action="append",
+        index=Path("30-Insights/INDEX.md"),
+        before=index_before,
+        after=index_after,
+        before_sha256=sha256_bytes(index_before),
+        after_sha256=sha256_bytes(index_after),
+        line=line,
+    )
+    assert note.read_bytes() == original
+    assert index.read_bytes() == index_before
+
+
+@pytest.mark.parametrize(
+    "config_payload",
+    [
+        b"{malformed",
+        b'{"obsidian-folder-index": true}',
+    ],
+)
+def test_plan_blocks_when_enabled_plugin_configuration_is_invalid(
+    tmp_path: Path, config_payload: bytes
+) -> None:
+    vault = make_vault(tmp_path)
+    (vault / "30-Insights").mkdir()
+    (vault / ".obsidian" / "community-plugins.json").write_bytes(config_payload)
+    note = vault / "00-Inbox" / "Note.md"
+    original = b"# Insight\nidea\n"
+    note.write_bytes(original)
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "blocked"
+    assert item.proposal is None
+    assert item.issue is not None
+    assert item.issue.code == "unsafe-index-plan"
+    assert note.read_bytes() == original
+
+
+def test_plan_blocks_multiline_fallback_title_without_index_write(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    target = vault / "30-Insights"
+    target.mkdir()
+    index = target / "INDEX.md"
+    index_before = b"# Insights\n"
+    index.write_bytes(index_before)
+    source = vault / "00-Inbox" / "Bad\nTitle.md"
+    original = b"idea body\n"
+    source.write_bytes(original)
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.title == "Bad\nTitle"
+    assert item.status == "blocked"
+    assert item.proposal is None
+    assert item.issue is not None
+    assert item.issue.code == "unsafe-index-plan"
+    assert source.read_bytes() == original
+    assert index.read_bytes() == index_before
+
+
+def test_plan_separates_internal_symlink_destination_from_logical_index_link(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    physical_target = vault / "Physical-Insights"
+    physical_target.mkdir()
+    make_symlink(physical_target, vault / "30-Insights")
+    index = physical_target / "INDEX.md"
+    before = b"# Insights\n"
+    index.write_bytes(before)
+    source = vault / "00-Inbox" / "Note.md"
+    source.write_bytes(b"# Insight\nidea\n")
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "ready"
+    assert item.proposal is not None
+    assert item.proposal.destination == Path("Physical-Insights/Note.md")
+    assert item.proposal.index.index == Path("Physical-Insights/INDEX.md")
+    assert item.proposal.index.line == (
+        "- [[30-Insights/Note|Insight]] (2042-03-04)\n"
+    )
+    assert index.read_bytes() == before
+
+
 def test_plan_preserves_existing_scalar_tags_and_type(tmp_path: Path) -> None:
     original = (
         b"---\n"
         b"date: 2040-01-02\n"
         b"type: web-clip\n"
         b"tags: web-clip\n"
         b"---\n# Clip\n"
     )
     vault, _note, _snapshot = snapshot_one(tmp_path, original)
     (vault / "20-Learning").mkdir()
