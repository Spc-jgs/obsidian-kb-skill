#!/usr/bin/env python3
"""Resolving a wikilink to the file it means, for both Skills.

This is `audit_vault`'s link resolution, extracted so retrieval can reach it
without importing the audit — which pulls in the whole write-side closure and
would not fit the retrieval bundle at all. #121 named the extraction as a
precondition of exploring a note's neighbourhood, and it is the shape the
consistency registry prefers: one definition of what a link means, shared by
object, rather than two that agree until they do not.

Everything here is read-only and has no dependency beyond `frontmatter`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    read_frontmatter_head,
)

WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
FENCE_OPEN_RE = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def declared_aliases(path: Path) -> tuple[str, ...]:
    """Return the aliases a note declares, reading only its head."""
    metadata = parse_frontmatter(
        read_frontmatter_head(path), source=path.name
    ).metadata
    if not metadata:
        return ()
    raw = metadata.get("aliases")
    if raw is None:
        raw = metadata.get("alias")
    values = raw if isinstance(raw, list) else [raw]
    return tuple(
        str(value).strip()
        for value in values
        if isinstance(value, (str, int, float)) and str(value).strip()
    )


@dataclass
class LinkIndex:
    """Resolve a wikilink target to files the way Obsidian does.

    Obsidian resolves `[[alias]]` through the target note's frontmatter
    `aliases`, so an index that only knows filenames calls a working link broken
    — and calls the note it points at an orphan, because the inbound link was
    never counted. `search_vault` already scores aliases; only the audit did not
    know about them.

    The alias map costs one pass over the Vault, so it is built on first need. A
    Vault whose links all resolve by filename never pays for it, which keeps the
    per-note audit that runs on every write as cheap as it was.
    """

    by_name: dict[str, list[Path]]
    by_stem: dict[str, list[Path]]
    linkable: list[Path]
    _aliases: dict[str, list[Path]] | None = field(default=None)

    def _alias_map(self) -> dict[str, list[Path]]:
        if self._aliases is None:
            found: dict[str, list[Path]] = defaultdict(list)
            for path in self.linkable:
                if path.suffix.lower() != ".md":
                    continue
                for alias in declared_aliases(path):
                    found[alias].append(path)
            self._aliases = dict(found)
        return self._aliases

    def matches(self, target: str) -> list[Path]:
        """Return every file a bare (non-path) wikilink target could mean.

        The stem lookup is not gated on the target "looking extensionless".
        `Path("Qwen3.6-27B实战").suffix` is `.6-27B实战` as far as pathlib is
        concerned, so any note whose title contains a dot was skipped here and
        reported as a broken link to a file that exists. A filename match still
        wins; trying the stem afterwards can only resolve links that would
        otherwise be called broken.
        """
        key = Path(target).name
        found = self.by_name.get(key, [])
        if not found:
            found = self.by_stem.get(key, [])
        if not found:
            found = self._alias_map().get(key, [])
        return found


def build_link_index(linkable: list[Path]) -> LinkIndex:
    by_name: dict[str, list[Path]] = defaultdict(list)
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in linkable:
        by_name[path.name].append(path)
        by_stem[path.stem].append(path)
    return LinkIndex(dict(by_name), dict(by_stem), linkable)


def candidate_paths(source: Path, target: str, vault: Path) -> Iterable[Path]:
    raw = Path(target)
    candidates = [vault / raw, source.parent / raw]
    if raw.suffix == "":
        candidates.extend((vault / f"{target}.md", source.parent / f"{target}.md"))
    return candidates


def clean_link_target(raw: str) -> str:
    target = raw.split("|", 1)[0]
    target = target.split("#", 1)[0]
    target = target.split("^", 1)[0]
    return target.strip()


def resolve_target(
    target: str,
    source: Path,
    vault: Path,
    index: LinkIndex,
) -> list[Path]:
    if "/" in target:
        return [
            candidate
            for candidate in candidate_paths(source, target, vault)
            if candidate.is_file()
        ]
    return [candidate for candidate in index.matches(target) if candidate.is_file()]


def _outside_fenced_code(text: str) -> tuple[list[str | None], bool]:
    """Per line: the line itself when it is prose, or `None` when it is code.

    One state machine, two views. `without_fenced_code` joins the prose and
    drops the rest; `blank_code_examples` keeps a placeholder so line numbers
    survive. Two walks of this logic would be two chances to disagree about
    where a fence ends.

    A fence marker inside an HTML comment is invisible to the reader and opens
    nothing, so it must not be reported as unclosed. Inside a fence the reverse
    holds: `<!--` is literal code and changes no state.
    """
    kept: list[str | None] = []
    fence_character: str | None = None
    fence_length = 0
    inside_comment = False
    for line in text.splitlines(keepends=True):
        candidate = line.rstrip("\r\n")
        if fence_character is None:
            if inside_comment:
                kept.append(line)
                if "-->" in candidate:
                    inside_comment = False
                continue
            opening = candidate.find("<!--")
            if opening >= 0 and "-->" not in candidate[opening:]:
                inside_comment = True
                kept.append(line)
                continue
            match = FENCE_OPEN_RE.fullmatch(candidate)
            if match is None:
                kept.append(line)
                continue
            fence = match.group("fence")
            info = match.group("info")
            if fence[0] == "`" and "`" in info:
                kept.append(line)
                continue
            fence_character = fence[0]
            fence_length = len(fence)
            kept.append(None)
            continue
        kept.append(None)
        if re.fullmatch(
            rf"[ \t]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
            candidate,
        ):
            fence_character = None
            fence_length = 0
    return kept, fence_character is not None


def without_fenced_code(text: str) -> tuple[str, bool]:
    """Return Markdown outside fenced code and whether one fence is unclosed."""
    kept, unclosed = _outside_fenced_code(text)
    return "".join(line for line in kept if line is not None), unclosed


def without_code_examples(text: str) -> str:
    outside, _ = without_fenced_code(text)
    return INLINE_CODE_RE.sub("", outside)


def blank_code_examples(text: str) -> str:
    """Remove code while preserving line numbering.

    `without_code_examples` drops whole lines, which answers *which* notes a
    note links to and destroys *where* the link is. A caller that cites a line
    needs the numbering to survive the removal, so code lines become empty
    rather than absent.
    """
    kept, _ = _outside_fenced_code(text)
    return "".join(
        INLINE_CODE_RE.sub("", line) if line is not None else "\n" for line in kept
    )
