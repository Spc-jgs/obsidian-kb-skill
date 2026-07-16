"""Read-only, immutable snapshots of Inbox source notes."""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    resolve_target_within_vault,
    validate_vault_root,
)


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

    try:
        raw = Path(entry.path).read_bytes()
    except OSError:
        return _blocked_snapshot(
            source,
            "unreadable-source",
            "source bytes could not be read",
            identity=identity,
        )

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
