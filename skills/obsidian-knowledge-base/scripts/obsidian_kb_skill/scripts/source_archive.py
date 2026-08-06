#!/usr/bin/env python3
"""Keep a captured source verbatim, beside the note rather than inside it.

A user asked for an article's original text to be kept and the Agent appended
all of it to the end of the note: 35 KB of someone else's prose around a 7.6 KB
digest, 82% of the file. A quarter of that note's search citations then landed
in the author's text rather than the user's own knowledge, and BM25 length
normalization cost the digest 20-30% of its score.

An archive is evidence, not knowledge. It lives in its own folder, keeps the
source bytes exactly as captured, and is linked from the note in both
directions so neither side becomes a dead end.
"""
from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    portable_yaml_scalars,
)
from obsidian_kb_skill.scripts.note_catalog import (
    SOURCE_ARCHIVE_FOLDER,
    SOURCE_ARCHIVE_TYPE,
)

import re

LEADING_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_TITLE_CHARS = 80
LINK_LABEL = "原文存档"


class SourceArchiveError(ValueError):
    """An archive request that cannot be honoured."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    def payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class ArchivePlan:
    """What applying would write, computed without writing anything."""

    path: Path
    relative: str
    stem: str
    sha256: str
    source_bytes: int
    note_relative: str
    already_archived: str | None


def source_sha256(text: str) -> str:
    """Hash the source text alone.

    The frontmatter is metadata about the capture, not part of the evidence, so
    it must not move the hash: a reader comparing this value against the file's
    body can tell whether the source was edited after capture.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def archive_stem(title: str, *, captured: str) -> str:
    """Return a filename stem that is unique enough and safe on every platform.

    Notes in this Vault are conventionally named `YYYY-MM-DD Title`, so blindly
    prefixing the capture date produced `2026-08-06 2026-08-06 …` on the very
    first real archive. Prefix only when the title does not already lead with a
    date of its own.
    """
    unsafe = '/\\:*?"<>|'
    cleaned = "".join("_" if ch in unsafe else ch for ch in title)
    cleaned = " ".join(cleaned.split()).strip(". ")[:MAX_TITLE_CHARS].strip()
    body = cleaned or "source"
    prefix = "" if LEADING_DATE_RE.match(body) else f"{captured} "
    return f"{prefix}{body}·原文"


def archive_directory(vault: Path, captured: str) -> Path:
    return vault / SOURCE_ARCHIVE_FOLDER / captured[:7]


def render_archive(
    text: str,
    *,
    source: str,
    note: str,
    captured: str,
    author: str | None = None,
    published: str | None = None,
) -> str:
    """Return the archive file: a frontmatter block, then the source unchanged.

    The body is not normalized in any way. The point of keeping an official
    post is that it is evidence, and a tidied copy is not evidence — so no
    heading-level repair, no template merge, no truncation, and no reflow.
    """
    metadata: dict[str, Any] = {
        "type": SOURCE_ARCHIVE_TYPE,
        "source": source,
        "captured": captured,
        "sha256": source_sha256(text),
        "note": f"[[{Path(note).stem}]]",
    }
    if author:
        metadata["author"] = author
    if published:
        metadata["published"] = published
    block = yaml.safe_dump(
        portable_yaml_scalars(metadata),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return f"---\n{block}---\n\n{text}"


def archived_body(rendered: str) -> str:
    """Return the source text back out of an archive file, byte-for-byte.

    Deliberately not `parse_frontmatter`: that normalizes CRLF to LF, which is
    the right thing for a note and the wrong thing for evidence. A source
    captured with Windows line endings must come back out with them.
    """
    if not rendered.startswith("---\n"):
        return rendered
    end = rendered.find("\n---\n", 3)
    if end == -1:
        return rendered
    return rendered[end + len("\n---\n") :].removeprefix("\n")


def declared_archive(note_text: str) -> str | None:
    """Return the archive a note already declares, if any."""
    metadata = parse_frontmatter(note_text).metadata or {}
    value = metadata.get("source_archive")
    return value.strip() if isinstance(value, str) and value.strip() else None


def plan_archive(
    vault: Path,
    note: Path,
    text: str,
    *,
    captured: str | None = None,
) -> ArchivePlan:
    """Decide where the archive goes without touching the Vault."""
    if not text.strip():
        raise SourceArchiveError(
            "empty-source-content",
            "there is no source text to archive",
        )
    if not note.is_file():
        raise SourceArchiveError(
            "invalid-note",
            "--note must name an existing note in this Vault",
            note=note.name,
        )
    stamp = captured or datetime.date.today().isoformat()
    note_relative = note.relative_to(vault).as_posix()
    directory = archive_directory(vault, stamp)
    stem = archive_stem(note.stem, captured=stamp)
    candidate = directory / f"{stem}.md"
    suffix = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{suffix}.md"
        suffix += 1
    return ArchivePlan(
        path=candidate,
        relative=candidate.relative_to(vault).as_posix(),
        stem=candidate.stem,
        sha256=source_sha256(text),
        source_bytes=len(text.encode("utf-8")),
        note_relative=note_relative,
        already_archived=declared_archive(note.read_text(encoding="utf-8")),
    )


def link_note_to_archive(note_text: str, stem: str) -> str:
    """Add the archive link to a note's frontmatter and to its first section.

    Both placements are deliberate: frontmatter so the relationship is
    machine-readable, and one visible line so the reader can click through in
    Obsidian. Nothing else in the note is touched.
    """
    parsed = parse_frontmatter(note_text)
    if parsed.metadata is None:
        raise SourceArchiveError(
            "invalid-note",
            "the note has no readable frontmatter to record the archive in",
        )
    metadata = dict(parsed.metadata)
    metadata["source_archive"] = f"[[{stem}]]"
    block = yaml.safe_dump(
        portable_yaml_scalars(metadata),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    body = parsed.body
    marker = f"{LINK_LABEL}：[[{stem}]]"
    lines = body.split("\n")
    inserted = False
    for index, line in enumerate(lines):
        if line.startswith("## "):
            lines.insert(index + 1, f"\n{marker}")
            inserted = True
            break
    if not inserted:
        lines.append(f"\n{marker}")
    return f"---\n{block}---\n{chr(10).join(lines)}"
