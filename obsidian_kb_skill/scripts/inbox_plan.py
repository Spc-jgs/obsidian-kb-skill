"""Read-only, immutable planning for Inbox source notes."""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Mapping

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
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

if TYPE_CHECKING:
    from obsidian_kb_skill.scripts.folder_index_policy import StaticIndexPlan


InboxStatus = Literal["ready", "skipped", "blocked"]

# Trigger keywords (lowercased substrings) -> target folder. Keep this local to
# Inbox planning so importing the pure planner does not pull in the CLI module.
_KEYWORD_ROUTES = (
    (("meeting", "standup", "review", "sync"), "10-Work"),
    (("article", "learning", "book", "course", "tutorial"), "20-Learning"),
    (("web", "url", "blog", "clip"), "20-Learning"),
    (("analysis", "insight", "idea", "takeaway"), "30-Insights"),
    (("project", "milestone", "sprint"), "40-Projects"),
    (("person", "contact", "team"), "50-People"),
)

_DEFAULT_TAG_BY_FOLDER = {
    folder: DEFAULT_TAG_BY_TYPE[note_type]
    for folder, note_type in FOLDER_TO_DEFAULT_TYPE.items()
}

_FRONTMATTER_KEYS = ("date", "type", "tags")


class _DuplicateFrontmatterKeyError(yaml.YAMLError):
    def __init__(self, key: object, mark: Any) -> None:
        super().__init__(f"duplicate frontmatter key: {key!r}")
        self.key = key
        self.mark = mark


def _node_identity(node: Node) -> tuple[object, ...]:
    """Return a stable fallback identity for a YAML key node."""
    if isinstance(node, ScalarNode):
        return ("scalar", node.tag, node.value)
    if isinstance(node, SequenceNode):
        return ("sequence", node.tag, tuple(_node_identity(item) for item in node.value))
    if isinstance(node, MappingNode):
        return (
            "mapping",
            node.tag,
            tuple(
                (_node_identity(key), _node_identity(value))
                for key, value in node.value
            ),
        )
    return (node.id, node.tag)


class _DuplicateKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node: Node, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, MappingNode):
            seen: set[object] = set()
            for key_node, _value_node in node.value:
                try:
                    key: object = self.construct_object(key_node, deep=True)
                    hash(key)
                    identity: object = ("constructed", key)
                except (TypeError, yaml.constructor.ConstructorError):
                    key = _node_identity(key_node)
                    identity = ("node", key)
                if identity in seen:
                    raise _DuplicateFrontmatterKeyError(key, key_node.start_mark)
                seen.add(identity)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class InboxIssue:
    code: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class InboxSourceSnapshot:
    source: Path
    identity: SourceIdentity | None
    raw: bytes | None
    sha256: str | None
    text: str | None
    frontmatter: FrontmatterResult | None
    issue: InboxIssue | None


@dataclass(frozen=True)
class InboxProposal:
    destination: Path
    target: str
    note_type: str
    tags: tuple[str, ...]
    metadata_updates: tuple[tuple[str, object], ...]
    rendered_bytes: bytes
    rendered_sha256: str
    index: StaticIndexPlan | None


@dataclass(frozen=True)
class InboxPlanItem:
    source: Path
    identity: SourceIdentity | None
    source_sha256: str | None
    title: str | None
    status: InboxStatus
    proposal: InboxProposal | None
    issue: InboxIssue | None


@dataclass(frozen=True)
class InboxPlan:
    effective_date: str
    items: tuple[InboxPlanItem, ...]


def sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _source_identity(result: os.stat_result) -> SourceIdentity:
    return SourceIdentity(
        device=result.st_dev,
        inode=result.st_ino,
        size=result.st_size,
        mtime_ns=result.st_mtime_ns,
    )


def _blocked_snapshot(
    source: Path,
    code: str,
    message: str,
    *,
    identity: SourceIdentity | None = None,
    raw: bytes | None = None,
    sha256: str | None = None,
    text: str | None = None,
    frontmatter: FrontmatterResult | None = None,
    line: int | None = None,
    column: int | None = None,
) -> InboxSourceSnapshot:
    return InboxSourceSnapshot(
        source=source,
        identity=identity,
        raw=raw,
        sha256=sha256,
        text=text,
        frontmatter=frontmatter,
        issue=InboxIssue(code, message, line=line, column=column),
    )


def _snapshot_entry(
    entry: os.DirEntry[str], source: Path
) -> InboxSourceSnapshot:
    try:
        status = entry.stat(follow_symlinks=False)
    except OSError:
        return _blocked_snapshot(
            source,
            "unreadable-source",
            "source metadata could not be read",
        )

    identity = _source_identity(status)
    if stat.S_ISLNK(status.st_mode):
        return _blocked_snapshot(
            source,
            "symlink-source",
            "source is a symbolic link",
            identity=identity,
        )
    if not stat.S_ISREG(status.st_mode):
        return _blocked_snapshot(
            source,
            "non-regular-source",
            "source is not a regular file",
            identity=identity,
        )

    flags = os.O_RDONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_BINARY", 0)
    fd: int | None = None
    try:
        fd = os.open(entry.path, flags)
        opened_status = os.fstat(fd)
        opened_identity = _source_identity(opened_status)
        if (
            not stat.S_ISREG(opened_status.st_mode)
            or opened_identity.device != identity.device
            or opened_identity.inode != identity.inode
        ):
            return _blocked_snapshot(
                source,
                "unreadable-source",
                "source changed before it could be read",
                identity=identity,
            )

        stream = os.fdopen(fd, "rb", closefd=True)
        fd = None
        with stream:
            raw = stream.read()
    except OSError:
        return _blocked_snapshot(
            source,
            "unreadable-source",
            "source bytes could not be read",
            identity=identity,
        )
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    digest = sha256_bytes(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _blocked_snapshot(
            source,
            "invalid-utf8",
            "source is not valid UTF-8",
            identity=identity,
            raw=raw,
            sha256=digest,
        )

    frontmatter = parse_frontmatter(text, source=source.as_posix())
    if frontmatter.issue is not None:
        issue = frontmatter.issue
        return _blocked_snapshot(
            source,
            issue.code,
            issue.message,
            identity=identity,
            raw=raw,
            sha256=digest,
            text=text,
            frontmatter=frontmatter,
            line=issue.line,
            column=issue.column,
        )

    return InboxSourceSnapshot(
        source=source,
        identity=identity,
        raw=raw,
        sha256=digest,
        text=text,
        frontmatter=frontmatter,
        issue=None,
    )


def snapshot_inbox_sources(
    vault: Path, inbox_name: str = "00-Inbox"
) -> tuple[InboxSourceSnapshot, ...]:
    """Snapshot every Markdown source without following or modifying entries."""
    requested_inbox = Path(inbox_name)
    try:
        root = validate_vault_root(vault)
        inbox = resolve_target_within_vault(root, inbox_name, label="Inbox")
    except VaultPathError:
        return (
            _blocked_snapshot(
                requested_inbox,
                "unsafe-inbox-path",
                "Inbox path could not be resolved safely",
            ),
        )

    try:
        with os.scandir(inbox) as entries:
            markdown_entries = sorted(
                (entry for entry in entries if entry.name.endswith(".md")),
                key=lambda entry: entry.name,
            )
    except OSError:
        return (
            _blocked_snapshot(
                requested_inbox,
                "unreadable-inbox",
                "Inbox directory could not be scanned",
            ),
        )

    source_root = inbox.relative_to(root)
    return tuple(
        _snapshot_entry(entry, source_root / entry.name)
        for entry in markdown_entries
    )


def _newline_for(raw_without_bom: bytes) -> bytes:
    newline_at = raw_without_bom.find(b"\n")
    if newline_at > 0 and raw_without_bom[newline_at - 1:newline_at] == b"\r":
        return b"\r\n"
    return b"\n"


def _closing_frontmatter_offset(raw: bytes) -> tuple[int, bytes] | None:
    """Return the raw closing-fence offset and opening newline convention."""
    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
    content = raw[bom_length:]
    if content.startswith(b"---\r\n"):
        newline = b"\r\n"
        line_start = 5
    elif content.startswith(b"---\n"):
        newline = b"\n"
        line_start = 4
    else:
        return None

    while line_start <= len(content):
        line_end = content.find(newline, line_start)
        if line_end == -1:
            line_end = len(content)
            next_line = line_end
        else:
            next_line = line_end + len(newline)
        if content[line_start:line_end] == b"---":
            return bom_length + line_start, newline
        if line_end == len(content):
            break
        line_start = next_line
    return None


def _duplicate_frontmatter_issue(raw: bytes) -> InboxIssue | None:
    fence = _closing_frontmatter_offset(raw)
    if fence is None:
        return None
    closing_offset, newline = fence
    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
    content_start = bom_length + 3 + len(newline)
    try:
        content = raw[content_start:closing_offset].decode("utf-8")
        yaml.load(content, Loader=_DuplicateKeyLoader)
    except _DuplicateFrontmatterKeyError as exc:
        return InboxIssue(
            "duplicate-frontmatter-key",
            f"frontmatter key {exc.key!r} is repeated",
            line=exc.mark.line + 2,
            column=exc.mark.column + 1,
        )
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        return InboxIssue("invalid-frontmatter", str(exc).splitlines()[0])
    return None


def _serialized_mapping_entry(
    key: str, value: object, newline: bytes
) -> tuple[bytes, object]:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) is None:
        raise ValueError(f"invalid frontmatter update key: {key!r}")
    try:
        dumped = yaml.safe_dump(
            value,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        expected = yaml.safe_load(dumped)
    except yaml.YAMLError as exc:
        raise ValueError(f"frontmatter update {key!r} is not YAML-safe") from exc

    lines = dumped.splitlines()
    if lines and lines[-1] == "...":
        lines.pop()
    if not lines:
        raise ValueError(f"frontmatter update {key!r} serialized to no value")

    if len(lines) == 1 and not lines[0].startswith(("-", "?", ":")):
        entry = f"{key}: {lines[0]}\n"
    else:
        indented = "".join(f"  {line}\n" for line in lines)
        entry = f"{key}:\n{indented}"
    encoded = entry.encode("utf-8").replace(b"\n", newline)
    return encoded, expected


def _validate_rendered_candidate(
    snapshot: InboxSourceSnapshot,
    rendered: bytes,
    expected_values: Mapping[str, object],
) -> None:
    frontmatter_issue = _duplicate_frontmatter_issue(rendered)
    if frontmatter_issue is not None:
        if frontmatter_issue.code == "duplicate-frontmatter-key":
            raise ValueError(
                f"duplicate frontmatter key: {frontmatter_issue.message}"
            )
        raise ValueError(frontmatter_issue.message)
    try:
        rendered_text = rendered.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("rendered frontmatter is not valid UTF-8") from exc
    reparsed = parse_frontmatter(rendered_text, source=snapshot.source.as_posix())
    if reparsed.issue is not None or reparsed.metadata is None:
        raise ValueError("rendered frontmatter is not a valid YAML mapping")
    for key, expected in expected_values.items():
        if reparsed.metadata.get(key) != expected:
            raise ValueError(f"frontmatter update {key!r} did not round-trip")


def render_frontmatter_updates(
    snapshot: InboxSourceSnapshot,
    updates: Mapping[str, object],
) -> bytes:
    """Insert absent frontmatter keys without rewriting any source bytes."""
    if (
        snapshot.issue is not None
        or snapshot.raw is None
        or snapshot.frontmatter is None
        or snapshot.frontmatter.issue is not None
    ):
        raise ValueError("cannot render updates for a blocked Inbox snapshot")

    raw = snapshot.raw
    metadata = snapshot.frontmatter.metadata or {}
    missing_updates = tuple(
        (key, value) for key, value in updates.items() if key not in metadata
    )
    if not missing_updates:
        _validate_rendered_candidate(snapshot, raw, {})
        return raw

    bom_length = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
    raw_without_bom = raw[bom_length:]
    fence = _closing_frontmatter_offset(raw)
    newline = fence[1] if fence is not None else _newline_for(raw_without_bom)
    entries: list[bytes] = []
    expected_values: dict[str, object] = {}
    for key, value in missing_updates:
        entry, expected = _serialized_mapping_entry(key, value, newline)
        entries.append(entry)
        expected_values[key] = expected
    insertion = b"".join(entries)

    if snapshot.frontmatter.present:
        if fence is None:
            raise ValueError("valid frontmatter has no raw closing delimiter")
        closing_offset, _ = fence
        rendered = raw[:closing_offset] + insertion + raw[closing_offset:]
    else:
        bom = raw[:bom_length]
        rendered = (
            bom
            + b"---"
            + newline
            + insertion
            + b"---"
            + newline
            + raw_without_bom
        )

    _validate_rendered_candidate(snapshot, rendered, expected_values)
    return rendered


def _note_title(relative: Path, text: str) -> str:
    """Return the first H1 or the date-prefix-stripped filename stem."""
    body = text
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5:]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("##"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                return candidate
    return re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", relative.stem).strip()


def _infer_target(text: str, metadata: Mapping[str, Any]) -> str | None:
    note_type = metadata.get("type")
    if isinstance(note_type, str) and note_type in TYPE_TO_FOLDER:
        return TYPE_TO_FOLDER[note_type]
    haystack = text.lower()
    for keywords, folder in _KEYWORD_ROUTES:
        if any(keyword in haystack for keyword in keywords):
            return folder
    return None


def _ambiguous_empty(value: object) -> bool:
    return value is None or value == "" or (
        isinstance(value, (list, tuple, dict, set)) and not value
    )


def _issue_item(
    snapshot: InboxSourceSnapshot,
    *,
    title: str | None,
    status: Literal["skipped", "blocked"],
    issue: InboxIssue,
) -> InboxPlanItem:
    return InboxPlanItem(
        source=snapshot.source,
        identity=snapshot.identity,
        source_sha256=snapshot.sha256,
        title=title,
        status=status,
        proposal=None,
        issue=issue,
    )


def _metadata_issue(metadata: Mapping[str, object]) -> InboxIssue | None:
    for key in _FRONTMATTER_KEYS:
        if key in metadata and _ambiguous_empty(metadata[key]):
            return InboxIssue(
                "ambiguous-empty-metadata",
                f"existing {key!r} metadata is empty and will not be replaced",
            )
    note_type = metadata.get("type")
    if note_type is not None and not isinstance(note_type, str):
        return InboxIssue("invalid-metadata", "existing 'type' metadata must be text")
    tags = metadata.get("tags")
    if tags is not None and not (
        isinstance(tags, str)
        or (isinstance(tags, list) and all(isinstance(tag, str) for tag in tags))
    ):
        return InboxIssue(
            "invalid-metadata",
            "existing 'tags' metadata must be text or a list of text values",
        )
    return None


def _plan_snapshot(root: Path, snapshot: InboxSourceSnapshot, date: str) -> InboxPlanItem:
    if snapshot.issue is not None:
        return _issue_item(
            snapshot,
            title=None,
            status="blocked",
            issue=snapshot.issue,
        )
    if snapshot.text is None or snapshot.frontmatter is None or snapshot.raw is None:
        return _issue_item(
            snapshot,
            title=None,
            status="blocked",
            issue=InboxIssue("unreadable-source", "source snapshot is incomplete"),
        )

    title = _note_title(snapshot.source, snapshot.text)
    duplicate_issue = _duplicate_frontmatter_issue(snapshot.raw)
    if duplicate_issue is not None:
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=duplicate_issue,
        )
    metadata = snapshot.frontmatter.metadata or {}
    metadata_issue = _metadata_issue(metadata)
    if metadata_issue is not None:
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=metadata_issue,
        )

    target = _infer_target(snapshot.text, metadata)
    if target is None:
        return _issue_item(
            snapshot,
            title=title,
            status="skipped",
            issue=InboxIssue("no-target", "could not infer a target folder"),
        )

    destination = Path(target) / snapshot.source.name
    lexical_target = root / target
    lexical_destination = root / destination
    try:
        resolved_target = resolve_target_within_vault(
            root, target, label="Inbox target directory"
        )
    except VaultPathError:
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue(
                "unsafe-destination-path",
                "target directory could not be resolved safely",
            ),
        )
    if os.path.lexists(lexical_target) and not resolved_target.is_dir():
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue(
                "unsafe-destination-path", "target directory is not a directory"
            ),
        )

    try:
        resolved_destination = resolve_target_within_vault(
            root, destination, label="Inbox destination"
        )
    except VaultPathError:
        if os.path.lexists(lexical_destination):
            return _issue_item(
                snapshot,
                title=title,
                status="skipped",
                issue=InboxIssue(
                    "destination-exists", "destination already exists"
                ),
            )
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue(
                "unsafe-destination-path", "destination could not be resolved safely"
            ),
        )
    try:
        fresh_target = resolve_target_within_vault(
            root, target, label="Inbox target directory"
        )
    except VaultPathError:
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue(
                "unsafe-destination-path",
                "target directory changed during planning",
            ),
        )
    if (
        not fresh_target.is_dir()
        or not resolved_destination.parent.is_dir()
        or fresh_target != resolved_target
        or resolved_destination.parent != fresh_target
    ):
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue(
                "unsafe-destination-path",
                "target directory changed during planning",
            ),
        )
    if os.path.lexists(lexical_destination) or os.path.lexists(resolved_destination):
        return _issue_item(
            snapshot,
            title=title,
            status="skipped",
            issue=InboxIssue("destination-exists", "destination already exists"),
        )

    existing_type = metadata.get("type")
    note_type = (
        existing_type
        if isinstance(existing_type, str)
        else FOLDER_TO_DEFAULT_TYPE[target]
    )
    existing_tags = metadata.get("tags")
    if isinstance(existing_tags, str):
        tags = (existing_tags,)
    elif isinstance(existing_tags, list):
        tags = tuple(existing_tags)
    else:
        tags = (_DEFAULT_TAG_BY_FOLDER.get(target, "note"),)

    updates: list[tuple[str, object]] = []
    if "date" not in metadata:
        updates.append(("date", date))
    if "type" not in metadata:
        updates.append(("type", note_type))
    if "tags" not in metadata:
        updates.append(("tags", tags))
    frozen_updates = tuple(updates)
    try:
        rendered = render_frontmatter_updates(snapshot, dict(frozen_updates))
    except (TypeError, ValueError) as exc:
        return _issue_item(
            snapshot,
            title=title,
            status="blocked",
            issue=InboxIssue("invalid-rendered-frontmatter", str(exc)),
        )

    proposal = InboxProposal(
        destination=resolved_destination.relative_to(root),
        target=target,
        note_type=note_type,
        tags=tags,
        metadata_updates=frozen_updates,
        rendered_bytes=rendered,
        rendered_sha256=sha256_bytes(rendered),
        index=None,
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


def plan_inbox(
    vault: Path,
    inbox_name: str = "00-Inbox",
    *,
    effective_date: str | None = None,
) -> InboxPlan:
    """Return one immutable, read-only plan from one source snapshot pass."""
    frozen_date = (
        effective_date
        if effective_date is not None
        else datetime.date.today().isoformat()
    )
    snapshots = snapshot_inbox_sources(vault, inbox_name)
    try:
        root = validate_vault_root(vault)
    except VaultPathError:
        items = tuple(
            _issue_item(
                snapshot,
                title=None,
                status="blocked",
                issue=snapshot.issue
                or InboxIssue("unsafe-inbox-path", "Vault root is unsafe"),
            )
            for snapshot in snapshots
        )
        return InboxPlan(effective_date=frozen_date, items=items)
    return InboxPlan(
        effective_date=frozen_date,
        items=tuple(_plan_snapshot(root, snapshot, frozen_date) for snapshot in snapshots),
    )


def _destination_index_name(vault: Path, target: str) -> str | None:
    folder = vault / target
    if not folder.is_dir():
        return None
    for name in (f"{target}.md", "INDEX.md"):
        if (folder / name).is_file():
            return name[:-3]
    return None


def legacy_plan_dict(vault: Path, item: InboxPlanItem) -> dict[str, Any]:
    """Adapt one typed item to the historical Inbox plan dictionary shape."""
    root = validate_vault_root(vault)
    result: dict[str, Any] = {
        "path": root / item.source,
        "target": item.proposal.target if item.proposal is not None else None,
        "title": item.title,
    }
    if item.proposal is None:
        result["skip"] = item.issue.message if item.issue is not None else "skipped"
        return result
    result["tags"] = list(item.proposal.tags)
    result["type"] = item.proposal.note_type
    result["related_suggestion"] = _destination_index_name(
        root, item.proposal.target
    )
    return result
