# Review package: 36e09a8..fde3337

## Commits
fde3337 fix: reject duplicate keys in inbox rendering
a572cfc fix: fail closed on unsafe inbox plans
e7c3bad refactor: model immutable inbox plans

## Files changed
 obsidian_kb_skill/scripts/inbox_plan.py | 594 +++++++++++++++++++++++++++++++-
 tests/test_inbox_plan.py                | 471 +++++++++++++++++++++++++
 2 files changed, 1064 insertions(+), 1 deletion(-)

## Diff
diff --git a/obsidian_kb_skill/scripts/inbox_plan.py b/obsidian_kb_skill/scripts/inbox_plan.py
index 228ae9d..bbf718f 100644
--- a/obsidian_kb_skill/scripts/inbox_plan.py
+++ b/obsidian_kb_skill/scripts/inbox_plan.py
@@ -1,26 +1,104 @@
-"""Read-only, immutable snapshots of Inbox source notes."""
+"""Read-only, immutable planning for Inbox source notes."""
 from __future__ import annotations
 
+import datetime
 import hashlib
 import os
+import re
 import stat
 from dataclasses import dataclass
 from pathlib import Path
+from typing import TYPE_CHECKING, Any, Literal, Mapping
+
+import yaml
+from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
 
 from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
+from obsidian_kb_skill.scripts.note_catalog import (
+    DEFAULT_TAG_BY_TYPE,
+    FOLDER_TO_DEFAULT_TYPE,
+    TYPE_TO_FOLDER,
+)
 from obsidian_kb_skill.scripts.vault_paths import (
     VaultPathError,
     resolve_target_within_vault,
     validate_vault_root,
 )
 
+if TYPE_CHECKING:
+    from obsidian_kb_skill.scripts.folder_index_policy import StaticIndexPlan
+
+
+InboxStatus = Literal["ready", "skipped", "blocked"]
+
+# Trigger keywords (lowercased substrings) -> target folder. Keep this local to
+# Inbox planning so importing the pure planner does not pull in the CLI module.
+_KEYWORD_ROUTES = (
+    (("meeting", "standup", "review", "sync"), "10-Work"),
+    (("article", "learning", "book", "course", "tutorial"), "20-Learning"),
+    (("web", "url", "blog", "clip"), "20-Learning"),
+    (("analysis", "insight", "idea", "takeaway"), "30-Insights"),
+    (("project", "milestone", "sprint"), "40-Projects"),
+    (("person", "contact", "team"), "50-People"),
+)
+
+_DEFAULT_TAG_BY_FOLDER = {
+    folder: DEFAULT_TAG_BY_TYPE[note_type]
+    for folder, note_type in FOLDER_TO_DEFAULT_TYPE.items()
+}
+
+_FRONTMATTER_KEYS = ("date", "type", "tags")
+
+
+class _DuplicateFrontmatterKeyError(yaml.YAMLError):
+    def __init__(self, key: object, mark: Any) -> None:
+        super().__init__(f"duplicate frontmatter key: {key!r}")
+        self.key = key
+        self.mark = mark
+
+
+def _node_identity(node: Node) -> tuple[object, ...]:
+    """Return a stable fallback identity for a YAML key node."""
+    if isinstance(node, ScalarNode):
+        return ("scalar", node.tag, node.value)
+    if isinstance(node, SequenceNode):
+        return ("sequence", node.tag, tuple(_node_identity(item) for item in node.value))
+    if isinstance(node, MappingNode):
+        return (
+            "mapping",
+            node.tag,
+            tuple(
+                (_node_identity(key), _node_identity(value))
+                for key, value in node.value
+            ),
+        )
+    return (node.id, node.tag)
+
+
+class _DuplicateKeyLoader(yaml.SafeLoader):
+    def construct_mapping(self, node: Node, deep: bool = False) -> dict[Any, Any]:
+        if isinstance(node, MappingNode):
+            seen: set[object] = set()
+            for key_node, _value_node in node.value:
+                try:
+                    key: object = self.construct_object(key_node, deep=True)
+                    hash(key)
+                    identity: object = ("constructed", key)
+                except (TypeError, yaml.constructor.ConstructorError):
+                    key = _node_identity(key_node)
+                    identity = ("node", key)
+                if identity in seen:
+                    raise _DuplicateFrontmatterKeyError(key, key_node.start_mark)
+                seen.add(identity)
+        return super().construct_mapping(node, deep=deep)
+
 
 @dataclass(frozen=True)
 class InboxIssue:
     code: str
     message: str
     line: int | None = None
     column: int | None = None
 
 
 @dataclass(frozen=True)
@@ -35,20 +113,49 @@ class SourceIdentity:
 class InboxSourceSnapshot:
     source: Path
     identity: SourceIdentity | None
     raw: bytes | None
     sha256: str | None
     text: str | None
     frontmatter: FrontmatterResult | None
     issue: InboxIssue | None
 
 
+@dataclass(frozen=True)
+class InboxProposal:
+    destination: Path
+    target: str
+    note_type: str
+    tags: tuple[str, ...]
+    metadata_updates: tuple[tuple[str, object], ...]
+    rendered_bytes: bytes
+    rendered_sha256: str
+    index: StaticIndexPlan | None
+
+
+@dataclass(frozen=True)
+class InboxPlanItem:
+    source: Path
+    identity: SourceIdentity | None
+    source_sha256: str | None
+    title: str | None
+    status: InboxStatus
+    proposal: InboxProposal | None
+    issue: InboxIssue | None
+
+
+@dataclass(frozen=True)
+class InboxPlan:
+    effective_date: str
+    items: tuple[InboxPlanItem, ...]
+
+
 def sha256_bytes(payload: bytes) -> str:
     return f"sha256:{hashlib.sha256(payload).hexdigest()}"
 
 
 def _source_identity(result: os.stat_result) -> SourceIdentity:
     return SourceIdentity(
         device=result.st_dev,
         inode=result.st_ino,
         size=result.st_size,
         mtime_ns=result.st_mtime_ns,
@@ -216,10 +323,495 @@ def snapshot_inbox_sources(
                 "unreadable-inbox",
                 "Inbox directory could not be scanned",
             ),
         )
 
     source_root = inbox.relative_to(root)
     return tuple(
         _snapshot_entry(entry, source_root / entry.name)
         for entry in markdown_entries
     )
+
+
+def _newline_for(raw_without_bom: bytes) -> bytes:
+    newline_at = raw_without_bom.find(b"\n")
+    if newline_at > 0 and raw_without_bom[newline_at - 1:newline_at] == b"\r":
+        return b"\r\n"
+    return b"\n"
+
+
+def _closing_frontmatter_offset(raw: bytes) -> tuple[int, bytes] | None:
+    """Return the raw closing-fence offset and opening newline convention."""
+    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
+    content = raw[bom_length:]
+    if content.startswith(b"---\r\n"):
+        newline = b"\r\n"
+        line_start = 5
+    elif content.startswith(b"---\n"):
+        newline = b"\n"
+        line_start = 4
+    else:
+        return None
+
+    while line_start <= len(content):
+        line_end = content.find(newline, line_start)
+        if line_end == -1:
+            line_end = len(content)
+            next_line = line_end
+        else:
+            next_line = line_end + len(newline)
+        if content[line_start:line_end] == b"---":
+            return bom_length + line_start, newline
+        if line_end == len(content):
+            break
+        line_start = next_line
+    return None
+
+
+def _duplicate_frontmatter_issue(raw: bytes) -> InboxIssue | None:
+    fence = _closing_frontmatter_offset(raw)
+    if fence is None:
+        return None
+    closing_offset, newline = fence
+    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
+    content_start = bom_length + 3 + len(newline)
+    try:
+        content = raw[content_start:closing_offset].decode("utf-8")
+        yaml.load(content, Loader=_DuplicateKeyLoader)
+    except _DuplicateFrontmatterKeyError as exc:
+        return InboxIssue(
+            "duplicate-frontmatter-key",
+            f"frontmatter key {exc.key!r} is repeated",
+            line=exc.mark.line + 2,
+            column=exc.mark.column + 1,
+        )
+    except (UnicodeDecodeError, yaml.YAMLError) as exc:
+        return InboxIssue("invalid-frontmatter", str(exc).splitlines()[0])
+    return None
+
+
+def _serialized_mapping_entry(
+    key: str, value: object, newline: bytes
+) -> tuple[bytes, object]:
+    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) is None:
+        raise ValueError(f"invalid frontmatter update key: {key!r}")
+    try:
+        dumped = yaml.safe_dump(
+            value,
+            sort_keys=False,
+            allow_unicode=True,
+            default_flow_style=False,
+        )
+        expected = yaml.safe_load(dumped)
+    except yaml.YAMLError as exc:
+        raise ValueError(f"frontmatter update {key!r} is not YAML-safe") from exc
+
+    lines = dumped.splitlines()
+    if lines and lines[-1] == "...":
+        lines.pop()
+    if not lines:
+        raise ValueError(f"frontmatter update {key!r} serialized to no value")
+
+    if len(lines) == 1 and not lines[0].startswith(("-", "?", ":")):
+        entry = f"{key}: {lines[0]}\n"
+    else:
+        indented = "".join(f"  {line}\n" for line in lines)
+        entry = f"{key}:\n{indented}"
+    encoded = entry.encode("utf-8").replace(b"\n", newline)
+    return encoded, expected
+
+
+def _validate_rendered_candidate(
+    snapshot: InboxSourceSnapshot,
+    rendered: bytes,
+    expected_values: Mapping[str, object],
+) -> None:
+    frontmatter_issue = _duplicate_frontmatter_issue(rendered)
+    if frontmatter_issue is not None:
+        if frontmatter_issue.code == "duplicate-frontmatter-key":
+            raise ValueError(
+                f"duplicate frontmatter key: {frontmatter_issue.message}"
+            )
+        raise ValueError(frontmatter_issue.message)
+    try:
+        rendered_text = rendered.decode("utf-8")
+    except UnicodeDecodeError as exc:
+        raise ValueError("rendered frontmatter is not valid UTF-8") from exc
+    reparsed = parse_frontmatter(rendered_text, source=snapshot.source.as_posix())
+    if reparsed.issue is not None or reparsed.metadata is None:
+        raise ValueError("rendered frontmatter is not a valid YAML mapping")
+    for key, expected in expected_values.items():
+        if reparsed.metadata.get(key) != expected:
+            raise ValueError(f"frontmatter update {key!r} did not round-trip")
+
+
+def render_frontmatter_updates(
+    snapshot: InboxSourceSnapshot,
+    updates: Mapping[str, object],
+) -> bytes:
+    """Insert absent frontmatter keys without rewriting any source bytes."""
+    if (
+        snapshot.issue is not None
+        or snapshot.raw is None
+        or snapshot.frontmatter is None
+        or snapshot.frontmatter.issue is not None
+    ):
+        raise ValueError("cannot render updates for a blocked Inbox snapshot")
+
+    raw = snapshot.raw
+    metadata = snapshot.frontmatter.metadata or {}
+    missing_updates = tuple(
+        (key, value) for key, value in updates.items() if key not in metadata
+    )
+    if not missing_updates:
+        _validate_rendered_candidate(snapshot, raw, {})
+        return raw
+
+    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
+    raw_without_bom = raw[bom_length:]
+    fence = _closing_frontmatter_offset(raw)
+    newline = fence[1] if fence is not None else _newline_for(raw_without_bom)
+    entries: list[bytes] = []
+    expected_values: dict[str, object] = {}
+    for key, value in missing_updates:
+        entry, expected = _serialized_mapping_entry(key, value, newline)
+        entries.append(entry)
+        expected_values[key] = expected
+    insertion = b"".join(entries)
+
+    if snapshot.frontmatter.present:
+        if fence is None:
+            raise ValueError("valid frontmatter has no raw closing delimiter")
+        closing_offset, _ = fence
+        rendered = raw[:closing_offset] + insertion + raw[closing_offset:]
+    else:
+        bom = raw[:bom_length]
+        rendered = (
+            bom
+            + b"---"
+            + newline
+            + insertion
+            + b"---"
+            + newline
+            + raw_without_bom
+        )
+
+    _validate_rendered_candidate(snapshot, rendered, expected_values)
+    return rendered
+
+
+def _note_title(relative: Path, text: str) -> str:
+    """Return the first H1 or the date-prefix-stripped filename stem."""
+    body = text
+    if body.startswith("---\n"):
+        end = body.find("\n---\n", 4)
+        if end != -1:
+            body = body[end + 5:]
+    for line in body.splitlines():
+        stripped = line.strip()
+        if stripped.startswith("#") and not stripped.startswith("##"):
+            candidate = stripped.lstrip("#").strip()
+            if candidate:
+                return candidate
+    return re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", relative.stem).strip()
+
+
+def _infer_target(text: str, metadata: Mapping[str, Any]) -> str | None:
+    note_type = metadata.get("type")
+    if isinstance(note_type, str) and note_type in TYPE_TO_FOLDER:
+        return TYPE_TO_FOLDER[note_type]
+    haystack = text.lower()
+    for keywords, folder in _KEYWORD_ROUTES:
+        if any(keyword in haystack for keyword in keywords):
+            return folder
+    return None
+
+
+def _ambiguous_empty(value: object) -> bool:
+    return value is None or value == "" or (
+        isinstance(value, (list, tuple, dict, set)) and not value
+    )
+
+
+def _issue_item(
+    snapshot: InboxSourceSnapshot,
+    *,
+    title: str | None,
+    status: Literal["skipped", "blocked"],
+    issue: InboxIssue,
+) -> InboxPlanItem:
+    return InboxPlanItem(
+        source=snapshot.source,
+        identity=snapshot.identity,
+        source_sha256=snapshot.sha256,
+        title=title,
+        status=status,
+        proposal=None,
+        issue=issue,
+    )
+
+
+def _metadata_issue(metadata: Mapping[str, object]) -> InboxIssue | None:
+    for key in _FRONTMATTER_KEYS:
+        if key in metadata and _ambiguous_empty(metadata[key]):
+            return InboxIssue(
+                "ambiguous-empty-metadata",
+                f"existing {key!r} metadata is empty and will not be replaced",
+            )
+    note_type = metadata.get("type")
+    if note_type is not None and not isinstance(note_type, str):
+        return InboxIssue("invalid-metadata", "existing 'type' metadata must be text")
+    tags = metadata.get("tags")
+    if tags is not None and not (
+        isinstance(tags, str)
+        or (isinstance(tags, list) and all(isinstance(tag, str) for tag in tags))
+    ):
+        return InboxIssue(
+            "invalid-metadata",
+            "existing 'tags' metadata must be text or a list of text values",
+        )
+    return None
+
+
+def _plan_snapshot(root: Path, snapshot: InboxSourceSnapshot, date: str) -> InboxPlanItem:
+    if snapshot.issue is not None:
+        return _issue_item(
+            snapshot,
+            title=None,
+            status="blocked",
+            issue=snapshot.issue,
+        )
+    if snapshot.text is None or snapshot.frontmatter is None or snapshot.raw is None:
+        return _issue_item(
+            snapshot,
+            title=None,
+            status="blocked",
+            issue=InboxIssue("unreadable-source", "source snapshot is incomplete"),
+        )
+
+    title = _note_title(snapshot.source, snapshot.text)
+    duplicate_issue = _duplicate_frontmatter_issue(snapshot.raw)
+    if duplicate_issue is not None:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=duplicate_issue,
+        )
+    metadata = snapshot.frontmatter.metadata or {}
+    metadata_issue = _metadata_issue(metadata)
+    if metadata_issue is not None:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=metadata_issue,
+        )
+
+    target = _infer_target(snapshot.text, metadata)
+    if target is None:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="skipped",
+            issue=InboxIssue("no-target", "could not infer a target folder"),
+        )
+
+    destination = Path(target) / snapshot.source.name
+    lexical_target = root / target
+    lexical_destination = root / destination
+    try:
+        resolved_target = resolve_target_within_vault(
+            root, target, label="Inbox target directory"
+        )
+    except VaultPathError:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue(
+                "unsafe-destination-path",
+                "target directory could not be resolved safely",
+            ),
+        )
+    if os.path.lexists(lexical_target) and not resolved_target.is_dir():
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue(
+                "unsafe-destination-path", "target directory is not a directory"
+            ),
+        )
+
+    try:
+        resolved_destination = resolve_target_within_vault(
+            root, destination, label="Inbox destination"
+        )
+    except VaultPathError:
+        if os.path.lexists(lexical_destination):
+            return _issue_item(
+                snapshot,
+                title=title,
+                status="skipped",
+                issue=InboxIssue(
+                    "destination-exists", "destination already exists"
+                ),
+            )
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue(
+                "unsafe-destination-path", "destination could not be resolved safely"
+            ),
+        )
+    try:
+        fresh_target = resolve_target_within_vault(
+            root, target, label="Inbox target directory"
+        )
+    except VaultPathError:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue(
+                "unsafe-destination-path",
+                "target directory changed during planning",
+            ),
+        )
+    if (
+        not fresh_target.is_dir()
+        or not resolved_destination.parent.is_dir()
+        or fresh_target != resolved_target
+        or resolved_destination.parent != fresh_target
+    ):
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue(
+                "unsafe-destination-path",
+                "target directory changed during planning",
+            ),
+        )
+    if os.path.lexists(lexical_destination) or os.path.lexists(resolved_destination):
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="skipped",
+            issue=InboxIssue("destination-exists", "destination already exists"),
+        )
+
+    existing_type = metadata.get("type")
+    note_type = (
+        existing_type
+        if isinstance(existing_type, str)
+        else FOLDER_TO_DEFAULT_TYPE[target]
+    )
+    existing_tags = metadata.get("tags")
+    if isinstance(existing_tags, str):
+        tags = (existing_tags,)
+    elif isinstance(existing_tags, list):
+        tags = tuple(existing_tags)
+    else:
+        tags = (_DEFAULT_TAG_BY_FOLDER.get(target, "note"),)
+
+    updates: list[tuple[str, object]] = []
+    if "date" not in metadata:
+        updates.append(("date", date))
+    if "type" not in metadata:
+        updates.append(("type", note_type))
+    if "tags" not in metadata:
+        updates.append(("tags", tags))
+    frozen_updates = tuple(updates)
+    try:
+        rendered = render_frontmatter_updates(snapshot, dict(frozen_updates))
+    except (TypeError, ValueError) as exc:
+        return _issue_item(
+            snapshot,
+            title=title,
+            status="blocked",
+            issue=InboxIssue("invalid-rendered-frontmatter", str(exc)),
+        )
+
+    proposal = InboxProposal(
+        destination=resolved_destination.relative_to(root),
+        target=target,
+        note_type=note_type,
+        tags=tags,
+        metadata_updates=frozen_updates,
+        rendered_bytes=rendered,
+        rendered_sha256=sha256_bytes(rendered),
+        index=None,
+    )
+    return InboxPlanItem(
+        source=snapshot.source,
+        identity=snapshot.identity,
+        source_sha256=snapshot.sha256,
+        title=title,
+        status="ready",
+        proposal=proposal,
+        issue=None,
+    )
+
+
+def plan_inbox(
+    vault: Path,
+    inbox_name: str = "00-Inbox",
+    *,
+    effective_date: str | None = None,
+) -> InboxPlan:
+    """Return one immutable, read-only plan from one source snapshot pass."""
+    frozen_date = (
+        effective_date
+        if effective_date is not None
+        else datetime.date.today().isoformat()
+    )
+    snapshots = snapshot_inbox_sources(vault, inbox_name)
+    try:
+        root = validate_vault_root(vault)
+    except VaultPathError:
+        items = tuple(
+            _issue_item(
+                snapshot,
+                title=None,
+                status="blocked",
+                issue=snapshot.issue
+                or InboxIssue("unsafe-inbox-path", "Vault root is unsafe"),
+            )
+            for snapshot in snapshots
+        )
+        return InboxPlan(effective_date=frozen_date, items=items)
+    return InboxPlan(
+        effective_date=frozen_date,
+        items=tuple(_plan_snapshot(root, snapshot, frozen_date) for snapshot in snapshots),
+    )
+
+
+def _destination_index_name(vault: Path, target: str) -> str | None:
+    folder = vault / target
+    if not folder.is_dir():
+        return None
+    for name in (f"{target}.md", "INDEX.md"):
+        if (folder / name).is_file():
+            return name[:-3]
+    return None
+
+
+def legacy_plan_dict(vault: Path, item: InboxPlanItem) -> dict[str, Any]:
+    """Adapt one typed item to the historical Inbox plan dictionary shape."""
+    root = validate_vault_root(vault)
+    result: dict[str, Any] = {
+        "path": root / item.source,
+        "target": item.proposal.target if item.proposal is not None else None,
+        "title": item.title,
+    }
+    if item.proposal is None:
+        result["skip"] = item.issue.message if item.issue is not None else "skipped"
+        return result
+    result["tags"] = list(item.proposal.tags)
+    result["type"] = item.proposal.note_type
+    result["related_suggestion"] = _destination_index_name(
+        root, item.proposal.target
+    )
+    return result
diff --git a/tests/test_inbox_plan.py b/tests/test_inbox_plan.py
index 98fff2a..a5e7236 100644
--- a/tests/test_inbox_plan.py
+++ b/tests/test_inbox_plan.py
@@ -1,38 +1,52 @@
 from __future__ import annotations
 
 import os
+from dataclasses import replace
 from pathlib import Path
 
 import pytest
 
+import obsidian_kb_skill.scripts.inbox_plan as inbox_plan
 from obsidian_kb_skill.scripts.inbox_plan import (
+    InboxPlanItem,
+    legacy_plan_dict,
+    plan_inbox,
+    render_frontmatter_updates,
     sha256_bytes,
     snapshot_inbox_sources,
 )
+from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
 
 
 def make_vault(tmp_path: Path) -> Path:
     vault = tmp_path / "vault"
     vault.mkdir()
     (vault / ".obsidian").mkdir()
     (vault / "00-Inbox").mkdir()
     return vault
 
 
 def make_symlink(target: Path, link: Path) -> None:
     try:
         link.symlink_to(target)
     except (OSError, NotImplementedError) as exc:
         pytest.skip(f"symlink creation unavailable: {exc}")
 
 
+def snapshot_one(tmp_path: Path, payload: bytes, name: str = "Note.md"):
+    vault = make_vault(tmp_path)
+    note = vault / "00-Inbox" / name
+    note.write_bytes(payload)
+    return vault, note, snapshot_inbox_sources(vault)[0]
+
+
 @pytest.mark.parametrize(
     ("payload", "code"),
     [
         (b"---\na: [\n---\nbody\n", "invalid-frontmatter"),
         (b"---\na: 1\nbody\n", "unclosed-frontmatter"),
         (b"---\nnull\n---\nbody\n", "frontmatter-not-mapping"),
         (b"---\n- one\n---\nbody\n", "frontmatter-not-mapping"),
         (b"---\nscalar\n---\nbody\n", "frontmatter-not-mapping"),
     ],
 )
@@ -264,10 +278,467 @@ def test_snapshot_returns_stable_issue_when_inbox_cannot_be_scanned(
 ) -> None:
     vault = make_vault(tmp_path)
 
     items = snapshot_inbox_sources(vault, "missing-inbox")
 
     assert len(items) == 1
     assert items[0].source == Path("missing-inbox")
     assert items[0].issue is not None
     assert items[0].issue.code == "unreadable-inbox"
     assert items[0].raw is None
+
+
+@pytest.mark.parametrize(
+    ("original", "updates", "unchanged_slices"),
+    [
+        (
+            b"# Body\nexact  \n",
+            {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
+            (b"# Body\nexact  \n",),
+        ),
+        (
+            b"---\ntitle: Keep\n---\n# Body\nexact  \n",
+            {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
+            (b"title: Keep\n", b"# Body\nexact  \n"),
+        ),
+        (
+            b"---\ndate: 2040-01-02\ntype: insight-note\n---\nbody",
+            {"tags": ("insight",)},
+            (b"date: 2040-01-02\ntype: insight-note\n", b"body"),
+        ),
+        (
+            b"---\ntype: insight-note\ntags: insight\n---\nbody\n",
+            {"date": "2042-03-04"},
+            (b"type: insight-note\ntags: insight\n", b"body\n"),
+        ),
+        (
+            b"---\ntype: insight-note\ntags: [insight, python]\n---\nbody\n",
+            {"date": "2042-03-04"},
+            (b"type: insight-note\ntags: [insight, python]\n", b"body\n"),
+        ),
+    ],
+)
+def test_render_inserts_only_missing_keys_without_rewriting_source_slices(
+    tmp_path: Path,
+    original: bytes,
+    updates: dict[str, object],
+    unchanged_slices: tuple[bytes, ...],
+) -> None:
+    _vault, note, snapshot = snapshot_one(tmp_path, original)
+
+    rendered = render_frontmatter_updates(snapshot, updates)
+
+    assert rendered != original
+    for unchanged in unchanged_slices:
+        assert unchanged in rendered
+    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
+    assert note.read_bytes() == original
+
+
+def test_render_preserves_bom_crlf_comments_quotes_and_body_bytes(
+    tmp_path: Path,
+) -> None:
+    original = (
+        b"\xef\xbb\xbf---\r\n"
+        b'title: "Keep quoting" # keep comment\r\n'
+        b"type: insight-note\r\n"
+        b"---\r\n# Body\r\nexact  \r\n"
+    )
+    _vault, note, snapshot = snapshot_one(tmp_path, original)
+
+    rendered = render_frontmatter_updates(
+        snapshot,
+        {"date": "2042-03-04", "type": "ignored", "tags": ("insight",)},
+    )
+
+    assert rendered.startswith(b"\xef\xbb\xbf---\r\n")
+    assert b'title: "Keep quoting" # keep comment\r\n' in rendered
+    assert rendered.count(b"type:") == 1
+    assert b"type: insight-note\r\n" in rendered
+    assert b"date: '2042-03-04'\r\n" in rendered
+    assert b"tags:\r\n  - insight\r\n" in rendered
+    assert rendered.endswith(b"# Body\r\nexact  \r\n")
+    assert b"\n" not in rendered.replace(b"\r\n", b"")
+    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
+    assert note.read_bytes() == original
+
+
+def test_render_without_frontmatter_preserves_bom_and_crlf_body(tmp_path: Path) -> None:
+    original = b"\xef\xbb\xbf# Body\r\nexact  \r\n"
+    _vault, _note, snapshot = snapshot_one(tmp_path, original)
+
+    rendered = render_frontmatter_updates(
+        snapshot,
+        {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
+    )
+
+    assert rendered.startswith(b"\xef\xbb\xbf---\r\n")
+    assert rendered.endswith(b"# Body\r\nexact  \r\n")
+    assert rendered.count(b"\xef\xbb\xbf") == 1
+    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
+
+
+@pytest.mark.parametrize(
+    ("key", "yaml_value"),
+    [
+        ("date", "null"),
+        ("date", "''"),
+        ("type", "null"),
+        ("type", "''"),
+        ("tags", "null"),
+        ("tags", "[]"),
+    ],
+)
+def test_plan_blocks_ambiguous_empty_existing_metadata(
+    tmp_path: Path, key: str, yaml_value: str
+) -> None:
+    vault = make_vault(tmp_path)
+    (vault / "30-Insights").mkdir()
+    (vault / "00-Inbox" / "Note.md").write_text(
+        f"---\n{key}: {yaml_value}\n---\n# Insight\nidea\n", encoding="utf-8"
+    )
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "blocked"
+    assert item.issue is not None
+    assert item.issue.code == "ambiguous-empty-metadata"
+    assert item.proposal is None
+
+
+def test_plan_builds_frozen_ready_proposal_without_writing(tmp_path: Path) -> None:
+    original = (
+        b"---\n"
+        b'title: "Keep" # comment\n'
+        b"tags: [existing, python]\n"
+        b"---\n"
+        b"# Planned Insight\nidea body  \n"
+    )
+    vault, note, snapshot = snapshot_one(tmp_path, original, "2040-Old.md")
+    (vault / "30-Insights").mkdir()
+
+    plan = plan_inbox(vault, effective_date="2042-03-04")
+
+    assert plan.effective_date == "2042-03-04"
+    assert len(plan.items) == 1
+    item = plan.items[0]
+    assert isinstance(item, InboxPlanItem)
+    assert item.source == Path("00-Inbox/2040-Old.md")
+    assert item.identity == snapshot.identity
+    assert item.source_sha256 == sha256_bytes(original)
+    assert item.title == "Planned Insight"
+    assert item.status == "ready"
+    assert item.issue is None
+    assert item.proposal is not None
+    assert item.proposal.destination == Path("30-Insights/2040-Old.md")
+    assert item.proposal.target == "30-Insights"
+    assert item.proposal.note_type == "insight-note"
+    assert item.proposal.tags == ("existing", "python")
+    assert item.proposal.metadata_updates == (
+        ("date", "2042-03-04"),
+        ("type", "insight-note"),
+    )
+    assert item.proposal.rendered_sha256 == sha256_bytes(
+        item.proposal.rendered_bytes
+    )
+    assert item.proposal.rendered_bytes.endswith(b"# Planned Insight\nidea body  \n")
+    assert item.proposal.index is None
+    assert note.read_bytes() == original
+    assert not (vault / item.proposal.destination).exists()
+
+
+def test_plan_preserves_existing_scalar_tags_and_type(tmp_path: Path) -> None:
+    original = (
+        b"---\n"
+        b"date: 2040-01-02\n"
+        b"type: web-clip\n"
+        b"tags: web-clip\n"
+        b"---\n# Clip\n"
+    )
+    vault, _note, _snapshot = snapshot_one(tmp_path, original)
+    (vault / "20-Learning").mkdir()
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "ready"
+    assert item.proposal is not None
+    assert item.proposal.target == "20-Learning"
+    assert item.proposal.note_type == "web-clip"
+    assert item.proposal.tags == ("web-clip",)
+    assert item.proposal.metadata_updates == ()
+    assert item.proposal.rendered_bytes == original
+
+
+def test_plan_statuses_propagate_snapshot_issue_and_unknown_route(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    (vault / "00-Inbox" / "bad.md").write_bytes(b"---\na: [\n---\nbody\n")
+    (vault / "00-Inbox" / "unknown.md").write_text(
+        "# Unclassified\nplain capture\n", encoding="utf-8"
+    )
+
+    items = plan_inbox(vault, effective_date="2042-03-04").items
+
+    assert [item.status for item in items] == ["blocked", "skipped"]
+    assert items[0].issue is not None
+    assert items[0].issue.code == "invalid-frontmatter"
+    assert items[0].source_sha256 == sha256_bytes(b"---\na: [\n---\nbody\n")
+    assert items[1].title == "Unclassified"
+    assert items[1].issue is not None
+    assert items[1].issue.code == "no-target"
+    assert all(item.proposal is None for item in items)
+
+
+def test_plan_existing_and_dangling_destinations_never_become_ready(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    target = vault / "30-Insights"
+    target.mkdir()
+    existing = target / "existing.md"
+    existing.write_bytes(b"existing\n")
+    (vault / "00-Inbox" / "existing.md").write_text("# Insight\nidea\n")
+    outside = tmp_path / "missing.md"
+    dangling = target / "dangling.md"
+    make_symlink(outside, dangling)
+    (vault / "00-Inbox" / "dangling.md").write_text("# Insight\nidea\n")
+
+    items = plan_inbox(vault, effective_date="2042-03-04").items
+
+    assert [item.status for item in items] == ["skipped", "skipped"]
+    assert all(item.issue is not None for item in items)
+    assert all(item.issue.code == "destination-exists" for item in items if item.issue)
+    assert all(item.proposal is None for item in items)
+    assert existing.read_bytes() == b"existing\n"
+    assert dangling.is_symlink()
+
+
+def test_plan_blocks_target_symlink_escape(tmp_path: Path) -> None:
+    vault = make_vault(tmp_path)
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    make_symlink(outside, vault / "30-Insights")
+    (vault / "00-Inbox" / "Note.md").write_text("# Insight\nidea\n")
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "blocked"
+    assert item.issue is not None
+    assert item.issue.code == "unsafe-destination-path"
+    assert item.proposal is None
+    assert not list(outside.iterdir())
+
+
+def test_plan_changes_proposal_and_hashes_for_inputs(tmp_path: Path) -> None:
+    vault = make_vault(tmp_path)
+    (vault / "20-Learning").mkdir()
+    (vault / "30-Insights").mkdir()
+    note = vault / "00-Inbox" / "Note.md"
+    note.write_text("# Insight\nidea\n", encoding="utf-8")
+    first = plan_inbox(vault, effective_date="2042-03-04").items[0]
+    second_date = plan_inbox(vault, effective_date="2042-03-05").items[0]
+    note.write_text("# Learning\narticle\n", encoding="utf-8")
+    second_route = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert first.proposal is not None
+    assert second_date.proposal is not None
+    assert second_route.proposal is not None
+    assert first.source_sha256 != second_route.source_sha256
+    assert first.proposal.rendered_sha256 != second_date.proposal.rendered_sha256
+    assert first.proposal != second_date.proposal
+    assert first.proposal.target != second_route.proposal.target
+    assert first.proposal.destination != second_route.proposal.destination
+    assert first.proposal.rendered_sha256 != second_route.proposal.rendered_sha256
+
+
+def test_legacy_plan_dict_retains_current_ready_and_skip_meanings(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    target = vault / "30-Insights"
+    target.mkdir()
+    (target / "INDEX.md").write_text("# Index\n", encoding="utf-8")
+    (vault / "00-Inbox" / "ready.md").write_text(
+        "# Ready Insight\nidea\n", encoding="utf-8"
+    )
+    (vault / "00-Inbox" / "skip.md").write_text(
+        "# Skip\nplain capture\n", encoding="utf-8"
+    )
+
+    ready, skipped = plan_inbox(vault, effective_date="2042-03-04").items
+    ready_dict = legacy_plan_dict(vault, ready)
+    skipped_dict = legacy_plan_dict(vault, skipped)
+
+    assert ready_dict == {
+        "path": vault / "00-Inbox" / "ready.md",
+        "target": "30-Insights",
+        "title": "Ready Insight",
+        "tags": ["insight"],
+        "type": "insight-note",
+        "related_suggestion": "INDEX",
+    }
+    assert skipped_dict["path"] == vault / "00-Inbox" / "skip.md"
+    assert skipped_dict["target"] is None
+    assert skipped_dict["title"] == "Skip"
+    assert skipped_dict["skip"] == "could not infer a target folder"
+
+
+@pytest.mark.parametrize(
+    ("frontmatter", "duplicate_line", "duplicate_column"),
+    [
+        (
+            "type: web-clip\ntype: insight-note\ntags: [insight]\n",
+            3,
+            1,
+        ),
+        (
+            "type: insight-note\ntags: [one]\ntags: [two]\n",
+            4,
+            1,
+        ),
+        (
+            "extra:\n  nested: one\n  nested: two\n",
+            4,
+            3,
+        ),
+    ],
+)
+def test_plan_blocks_duplicate_frontmatter_keys_at_any_mapping_depth(
+    tmp_path: Path,
+    frontmatter: str,
+    duplicate_line: int,
+    duplicate_column: int,
+) -> None:
+    vault = make_vault(tmp_path)
+    (vault / "30-Insights").mkdir()
+    (vault / "00-Inbox" / "duplicate.md").write_text(
+        f"---\n{frontmatter}---\n# Insight\nidea\n", encoding="utf-8"
+    )
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert item.status == "blocked"
+    assert item.proposal is None
+    assert item.issue is not None
+    assert item.issue.code == "duplicate-frontmatter-key"
+    assert item.issue.line == duplicate_line
+    assert item.issue.column == duplicate_column
+
+
+def test_plan_blocks_target_replaced_with_file_between_resolver_calls(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = make_vault(tmp_path)
+    target = vault / "30-Insights"
+    target.mkdir()
+    (vault / "00-Inbox" / "Note.md").write_text(
+        "# Insight\nidea\n", encoding="utf-8"
+    )
+    original_resolver = inbox_plan.resolve_target_within_vault
+    resolver_calls = 0
+
+    def replace_target_before_destination_resolution(
+        resolver_vault: Path,
+        user_path: str | Path,
+        *,
+        label: str = "path",
+    ) -> Path:
+        nonlocal resolver_calls
+        resolver_calls += 1
+        if label == "Inbox destination":
+            target.rmdir()
+            target.write_bytes(b"ordinary file\n")
+        return original_resolver(resolver_vault, user_path, label=label)
+
+    monkeypatch.setattr(
+        inbox_plan,
+        "resolve_target_within_vault",
+        replace_target_before_destination_resolution,
+    )
+
+    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
+
+    assert resolver_calls >= 4
+    assert item.status == "blocked"
+    assert item.proposal is None
+    assert item.issue is not None
+    assert item.issue.code == "unsafe-destination-path"
+    assert target.read_bytes() == b"ordinary file\n"
+
+
+@pytest.mark.parametrize(
+    "invalid_raw",
+    [
+        b"\xff",
+        b"---\nnull\n---\n",
+    ],
+)
+def test_render_revalidates_raw_candidate_when_no_updates_are_missing(
+    tmp_path: Path, invalid_raw: bytes
+) -> None:
+    original = (
+        b"---\n"
+        b"date: 2040-01-02\n"
+        b"type: insight-note\n"
+        b"tags: [insight]\n"
+        b"---\n# Insight\n"
+    )
+    _vault, _note, snapshot = snapshot_one(tmp_path, original)
+    forged = replace(snapshot, raw=invalid_raw)
+
+    with pytest.raises(ValueError):
+        render_frontmatter_updates(
+            forged,
+            {
+                "date": "2042-03-04",
+                "type": "insight-note",
+                "tags": ("insight",),
+            },
+        )
+
+
+def test_render_rejects_duplicate_key_in_no_op_candidate(tmp_path: Path) -> None:
+    original = (
+        b"---\n"
+        b"date: 2040-01-02\n"
+        b"type: web-clip\n"
+        b"type: insight-note\n"
+        b"tags: [insight]\n"
+        b"---\n# Insight\n"
+    )
+    _vault, _note, snapshot = snapshot_one(tmp_path, original)
+    assert snapshot.issue is None
+
+    with pytest.raises(ValueError, match="duplicate frontmatter key"):
+        render_frontmatter_updates(
+            snapshot,
+            {
+                "date": "2040-01-02",
+                "type": "insight-note",
+                "tags": ("insight",),
+            },
+        )
+
+
+def test_render_rejects_duplicate_key_after_inserting_missing_date(
+    tmp_path: Path,
+) -> None:
+    original = (
+        b"---\n"
+        b"type: web-clip\n"
+        b"type: insight-note\n"
+        b"tags: [insight]\n"
+        b"---\n# Insight\n"
+    )
+    _vault, _note, snapshot = snapshot_one(tmp_path, original)
+    assert snapshot.issue is None
+
+    with pytest.raises(ValueError, match="duplicate frontmatter key"):
+        render_frontmatter_updates(
+            snapshot,
+            {
+                "date": "2042-03-04",
+                "type": "insight-note",
+                "tags": ("insight",),
+            },
+        )
