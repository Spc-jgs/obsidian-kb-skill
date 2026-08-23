#!/usr/bin/env python3
"""Deterministic, explainable, read-only search for an Obsidian Vault."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import datetime
from difflib import SequenceMatcher
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
from obsidian_kb_skill.scripts.link_graph import blank_code_examples
from obsidian_kb_skill.scripts.note_catalog import (
    EXEMPT_NAMES,
    SOURCE_ARCHIVE_FOLDER,
    VALID_NOTE_TYPES,
    normalize_tag_key,
)
from obsidian_kb_skill.scripts.query_expansion import (
    EXPANSION_WEIGHT,
    LEXICON_FOLDER,
    LexiconError,
    QueryExpansion,
    expand_query,
    load_lexicon,
)
from obsidian_kb_skill.scripts.text_tokens import tokenize
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    validate_vault_root,
)


SCHEMA_VERSION = "1.0"
MAX_QUERY_CHARS = 500
MAX_TOP_K = 20
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_SNIPPET_CHARS = 480
MAX_ISSUES = 20
MAX_TAG_CHARS = 100
FIELD_WEIGHTS = {
    "title": 6.0,
    "aliases": 5.0,
    "tags": 3.0,
    "headings": 2.0,
    "links": 2.0,
    "body": 1.0,
}
IGNORED_DIRECTORY_NAMES = {
    "Attachments",
    "Templates",
    # Archived sources are evidence, not knowledge: a 35 KB blog post buried a
    # 7.6 KB digest and a quarter of that note's citations landed in the
    # author's prose. Excluded here rather than de-ranked, because the walk
    # applies this set to child directories and never to the scope root, so
    # `--scope 95-Sources` still reaches it when the user asks what the source
    # actually said.
    SOURCE_ARCHIVE_FOLDER,
    "__pycache__",
    "node_modules",
    ".git",
    ".obsidian",
    ".venv",
    ".workbuddy",
    ".claude",
    ".cursor",
    ".codex",
    ".agents",
    ".obsidian-kb-backups",
    # The Vault's own lexicon lives here. It is configuration for the search,
    # not knowledge the search should return. Dot-prefixed names are skipped
    # anyway; naming it keeps the reason in the file that acts on it.
    LEXICON_FOLDER,
}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Passage:
    """One visible Markdown section of a note's body, scored on its own.

    A note is ranked whole and cited by line, and until #118 those two used
    different units: BM25 charged the note for every word it contained, then a
    snippet was picked from whatever survived. On the reference Vault the notes
    that lost most to this are the ones worth reading — of the 19 notes at or
    above 10 KB, the fewest headings any carries is 12 and the median is 30,
    because a real note is long *because* it has sections.

    `heading` is `None` for the text before the first heading, which is a
    section like any other and must be able to answer.
    """

    heading: str | None
    start_line: int
    end_line: int
    tokens: Counter[str]
    length: int


@dataclass(frozen=True)
class SearchDocument:
    path: Path
    relative: str
    title: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...]
    headings: tuple[str, ...]
    links: tuple[str, ...]
    body: str
    body_start_line: int
    field_tokens: dict[str, Counter[str]]
    passages: tuple[Passage, ...] = ()
    note_type: str | None = None
    note_date: str | None = None
    # When the note says it last changed. Deliberately separate from
    # `note_date`, and never filled in from it: "written in July" and "changed
    # recently" are different questions, and one field answering both makes a
    # project touched yesterday look two months stale.
    note_updated: str | None = None

    @property
    def weighted_length(self) -> float:
        """Every field over the whole document. Kept for what it honestly says.

        No longer what BM25 normalises against — see `scoring_length`. A note's
        total size is still the right answer to "how big is this note", and
        conflating that with "how big is the unit being scored" is what made a
        30 KB note pay for text the query never asked about.
        """
        return sum(
            FIELD_WEIGHTS[field] * sum(tokens.values())
            for field, tokens in self.field_tokens.items()
        )

    @property
    def name_length(self) -> float:
        """Weighted length of everything that is not body text.

        Title, aliases, tags, headings and links describe the whole note, so
        every passage carries them. Only the body is partitioned.
        """
        return sum(
            FIELD_WEIGHTS[field] * sum(tokens.values())
            for field, tokens in self.field_tokens.items()
            if field != "body"
        )

    @property
    def mean_passage_length(self) -> float:
        """What a section of *this* note typically costs to read."""
        if not self.passages:
            return 0.0
        return sum(passage.length for passage in self.passages) / len(self.passages)

    def scoring_length(self, passage: Passage) -> float:
        """Names plus one section, charged at no less than a typical section.

        BM25 rewards short documents, and rightly: a short note is focused and
        cheap to read. A short *section* of a long note is neither — reaching it
        still means opening the long note. Scoring a three-word section as
        though it were a three-word document hands it that bonus unearned, and
        it is not hypothetical: a stub reading `jitter 上限。` outscored a note
        whose section actually explains the answer, 0.580 to 0.504. #118 listed
        this risk before the code existed.

        So a section is charged at least what a typical section of its own note
        costs. No constant is involved, and the floor is inert exactly where it
        should be: a note without headings has one section equal to its whole
        body, so `passage.length` *is* the mean and short unstructured notes
        keep the advantage they have always had.

        A note cannot escape by chopping itself into many small sections
        either — that lowers the mean for every section at once, including the
        ones that would have won.
        """
        return self.name_length + FIELD_WEIGHTS["body"] * max(
            passage.length, self.mean_passage_length
        )

    @property
    def average_scoring_length(self) -> float:
        """This note's contribution to the corpus average, as one sample.

        One sample per note rather than one per passage: the ranker returns
        notes, and letting a 100-section note supply a hundred measurements
        would let a handful of documents set the yardstick everything else is
        judged against.
        """
        return self.name_length + FIELD_WEIGHTS["body"] * self.mean_passage_length


EMPTY_PASSAGE = Passage(
    heading=None, start_line=0, end_line=0, tokens=Counter(), length=0
)


def _passages(body: str) -> tuple[Passage, ...]:
    """Split a body at its visible headings, one passage per section.

    Line numbers are body-relative and 0-based; the caller adds
    `body_start_line`. A section with no tokens at all — a heading with nothing
    under it — is dropped, since it can never score and would only pull the
    corpus average down. A body with no headings yields exactly one passage
    equal to the whole body, which is what makes this change a no-op on the
    short unstructured notes that make up most of a Vault.
    """
    starts: list[int] = [0]
    headings: list[str | None] = [None]
    lines = body.splitlines()
    # Boundaries come from the body with code blanked, content from the body
    # itself. A `#` line inside a fence is a shell comment, not a section — on
    # the reference Vault 22 of 199 notes carry 255 such lines, and one Python
    # note was split into 100 sections where it has 52. Splitting there makes
    # every fragment short, and a short passage pays almost no length penalty,
    # so the note scores high on subjects it only mentions. But the code itself
    # must stay searchable, so only the split reads the blanked copy.
    # `blank_code_examples` preserves line numbering exactly, which is what
    # lets one index address both.
    marks = blank_code_examples(body).splitlines()
    for index, line in enumerate(lines):
        source = marks[index] if index < len(marks) else line
        match = HEADING_RE.match(source)
        if match:
            starts.append(index)
            headings.append(match.group(2).strip())
    bounds = starts[1:] + [len(lines)]
    passages: list[Passage] = []
    for heading, start, end in zip(headings, starts, bounds):
        tokens = Counter(tokenize("\n".join(lines[start:end])))
        total = sum(tokens.values())
        if not total:
            continue
        passages.append(
            Passage(
                heading=heading,
                start_line=start,
                end_line=end,
                tokens=tokens,
                length=total,
            )
        )
    return tuple(passages)


def _normalize_name(text: str) -> str:
    return " ".join(tokenize(text))


def _visible_markdown(text: str) -> str:
    """Remove hidden comments while preserving line numbering."""

    def replace_comment(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return HTML_COMMENT_RE.sub(replace_comment, text)


def _string_values(value: Any) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value]
    return tuple(
        str(item).strip()
        for item in values
        if isinstance(item, (str, int, float)) and str(item).strip()
    )


def _title_from_body(path: Path, body: str) -> str:
    """The note's H1, or its filename — never a comment inside a code block.

    `FIELD_WEIGHTS["title"]` is 6x body, so this line decides what the note is
    at the heaviest weight there is. Two notes on the reference Vault had no H1
    at all and took their identity from a ```bash comment instead.
    """
    for line in blank_code_examples(body).splitlines():
        match = re.match(r"^#[ \t]+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return path.stem


def _headings(body: str) -> tuple[str, ...]:
    """The note's real headings — a `#` line inside a fence is quoted code.

    `headings` is a scored field at 2x body weight, so a shell comment landing
    here is scored as structure the author never wrote.
    """
    return tuple(
        match.group(2).strip()
        for line in blank_code_examples(body).splitlines()
        if (match := HEADING_RE.match(line))
    )


def _wikilink_text(body: str) -> tuple[str, ...]:
    values: list[str] = []
    for match in WIKILINK_RE.finditer(body):
        raw = match.group(1)
        target, separator, label = raw.partition("|")
        visible = label if separator else target
        visible = visible.split("#", 1)[0].split("^", 1)[0].strip()
        if visible:
            values.append(visible)
    return tuple(values)


def _body_start_line(parsed: FrontmatterResult) -> int:
    body_start = len(parsed.normalized_text) - len(parsed.body)
    return parsed.normalized_text[:body_start].count("\n") + 1


def _is_iso_date(value: str) -> bool:
    """True when the text is a real ISO calendar date, not merely ISO-shaped."""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _scalar(value: Any) -> str | None:
    """Return a frontmatter scalar as text, or None when it is not one."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def parse_note_date(value: Any) -> str | None:
    """Return a note's date as ISO `YYYY-MM-DD`, or None when it has none.

    PyYAML returns a `date` for an unquoted value and a `str` for a quoted one,
    and both spellings occur in a real Vault. A value that is neither is simply
    "no date": a filter must never raise over a note's metadata.
    """
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str) and ISO_DATE_RE.match(value.strip()):
        # Shape is not validity. `2026-13-45` matches the pattern and would then
        # be range-compared as text, ranking a month that does not exist as a
        # real date. The filter flags are already validated this way; a note's
        # own metadata has to clear the same bar.
        head = value.strip()[:10]
        return head if _is_iso_date(head) else None
    return None


@dataclass(frozen=True)
class Filters:
    """Metadata constraints applied before ranking.

    Hard constraints, not weights: asking for July dailies makes a June note
    wrong, not merely less relevant. Repeats within one dimension are OR;
    dimensions combine with AND.
    """

    types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    after: str | None = None
    before: str | None = None
    # A window over `updated`, never over `date`. `review-projects` reads
    # activity as "updated falling back to date" and that is a different
    # question with a different answer; folding a fallback in here would give
    # this Vault two definitions of "recent" again, which is the drift row 22
    # was written for. See row 28.
    updated_after: str | None = None
    updated_before: str | None = None

    @property
    def active(self) -> bool:
        return bool(
            self.types
            or self.tags
            or self.after
            or self.before
            or self.updated_after
            or self.updated_before
        )

    def applied(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.types:
            payload["type"] = list(self.types)
        if self.tags:
            payload["tag"] = list(self.tags)
        if self.after:
            payload["after"] = self.after
        if self.before:
            payload["before"] = self.before
        if self.updated_after:
            payload["updated_after"] = self.updated_after
        if self.updated_before:
            payload["updated_before"] = self.updated_before
        return payload

    def select(
        self, documents: list[SearchDocument]
    ) -> tuple[list[SearchDocument], dict[str, int]]:
        """Return surviving documents and why each of the others was dropped.

        A note is counted against the first dimension that rejects it, so the
        tally sums to the number excluded rather than double-counting. Missing a
        date is reported apart from falling outside the range: one is a
        governance problem in the Vault, the other is the filter doing its job.
        """
        wanted_tags = {normalize_tag_key(tag) for tag in self.tags}
        kept: list[SearchDocument] = []
        excluded: Counter[str] = Counter()
        for document in documents:
            if self.types and document.note_type not in self.types:
                excluded["type"] += 1
                continue
            if wanted_tags and not (
                {normalize_tag_key(tag) for tag in document.tags} & wanted_tags
            ):
                excluded["tag"] += 1
                continue
            if (self.after or self.before) and document.note_date is None:
                excluded["missing-date"] += 1
                continue
            if self.after and document.note_date < self.after:
                excluded["after"] += 1
                continue
            if self.before and document.note_date > self.before:
                excluded["before"] += 1
                continue
            # Counted apart from the date dimensions and apart from each other:
            # "nobody recorded when this changed" is a governance fact about the
            # Vault, while "it changed outside your window" is the filter
            # working. Merging them would tell a user their note is old when the
            # truth is that its `updated` was never written.
            if (
                self.updated_after or self.updated_before
            ) and document.note_updated is None:
                excluded["missing-updated"] += 1
                continue
            if self.updated_after and document.note_updated < self.updated_after:
                excluded["updated-after"] += 1
                continue
            if self.updated_before and document.note_updated > self.updated_before:
                excluded["updated-before"] += 1
                continue
            kept.append(document)
        return kept, dict(excluded)


def _document(path: Path, vault: Path, text: str) -> tuple[SearchDocument | None, dict[str, Any] | None]:
    relative = path.relative_to(vault).as_posix()
    parsed = parse_frontmatter(text, source=relative)
    if parsed.issue is not None:
        return None, {
            "code": parsed.issue.code,
            "path": relative,
            "message": parsed.issue.message,
            "line": parsed.issue.line,
            "column": parsed.issue.column,
        }
    metadata = parsed.metadata or {}
    visible_body = _visible_markdown(parsed.body)
    title = _title_from_body(path, visible_body)
    aliases = _string_values(metadata.get("aliases") or metadata.get("alias") or [])
    tags = _string_values(metadata.get("tags") or [])
    headings = _headings(visible_body)
    links = _wikilink_text(visible_body)
    passages = _passages(visible_body)
    # Derived, not tokenized a second time. `TOKEN_RUN_RE` matches runs of Latin
    # or CJK characters and a newline is neither, so a run can never span a line
    # break — partitioning the body at line boundaries preserves the token
    # multiset exactly. Tokenizing twice cost 60% of query latency on the
    # reference Vault (P50 125 → 204 ms) for an identical result.
    body_tokens: Counter[str] = Counter()
    for passage in passages:
        body_tokens += passage.tokens
    fields = {
        "title": Counter(tokenize(title)),
        "aliases": Counter(tokenize(" ".join(aliases))),
        "tags": Counter(tokenize(" ".join(tags))),
        "headings": Counter(tokenize(" ".join(headings))),
        "links": Counter(tokenize(" ".join(links))),
        "body": body_tokens,
    }
    return (
        SearchDocument(
            path=path,
            relative=relative,
            title=title,
            aliases=aliases,
            tags=tags,
            headings=headings,
            links=links,
            body=visible_body,
            body_start_line=_body_start_line(parsed),
            field_tokens=fields,
            passages=passages,
            note_type=_scalar(metadata.get("type")),
            note_date=parse_note_date(metadata.get("date")),
            note_updated=parse_note_date(metadata.get("updated")),
        ),
        None,
    )


def _ignored_directory(path: Path) -> bool:
    return path.name.startswith(".") or path.name in IGNORED_DIRECTORY_NAMES


def _markdown_files(scope: Path) -> Iterable[Path]:
    for directory, names, filenames in os.walk(scope, followlinks=False):
        parent = Path(directory)
        names[:] = sorted(
            name
            for name in names
            if not _ignored_directory(parent / name)
            and not (parent / name).is_symlink()
        )
        for name in sorted(filenames):
            path = parent / name
            if path.suffix.lower() != ".md" or path.is_symlink():
                continue
            yield path


def _load_documents(
    vault: Path, scope: Path
) -> tuple[list[SearchDocument], dict[str, int], list[dict[str, Any]]]:
    documents: list[SearchDocument] = []
    issues: list[dict[str, Any]] = []
    files = 0
    skipped = 0
    excluded = 0
    for path in _markdown_files(scope):
        # Scaffolding the write Skill already exempts from note contracts. It is
        # not a malformed note, so it never becomes an `issues` entry — but a
        # long Vault README mentions every subject and outranks real notes.
        if path.name in EXEMPT_NAMES:
            excluded += 1
            continue
        files += 1
        relative = path.relative_to(vault).as_posix()
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")
            text = path.read_text(encoding="utf-8")
            document, issue = _document(path, vault, text)
        except (OSError, UnicodeError, ValueError) as exc:
            document = None
            issue = {
                "code": "unreadable-note",
                "path": relative,
                "message": str(exc),
            }
        if issue is not None:
            skipped += 1
            if len(issues) < MAX_ISSUES:
                issues.append(issue)
            continue
        assert document is not None
        documents.append(document)
    return documents, {
        "files": files,
        "indexed": len(documents),
        "skipped": skipped,
        "excluded": excluded,
    }, issues


def _document_frequencies(
    documents: list[SearchDocument], query_tokens: set[str]
) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for document in documents:
        present = {
            token
            for tokens in document.field_tokens.values()
            for token in tokens
            if token in query_tokens
        }
        frequencies.update(present)
    return frequencies


MATCH_FIELDS = ("title", "aliases", "tags", "headings", "links", "body")


def _matched_by_field(
    document: SearchDocument,
    query_tokens: list[str],
    passage: Passage | None = None,
) -> dict[str, list[str]]:
    """Which of the reader's words appear in each field of this document.

    One definition of "this word matched", read by the signals a result shows
    and by the confidence that result is reported with. Two copies would let a
    result cite a word its own confidence did not count, and nothing would say
    so — the failure this repo keeps finding at unguarded boundaries.

    `body` is read from the section that won rather than note-wide, for the
    reason `_field_matches` gives: the cited passage is what the reader sees.
    """
    return {
        field: sorted(
            {
                token
                for token in query_tokens
                if (
                    passage.tokens
                    if field == "body" and passage is not None
                    else document.field_tokens[field]
                ).get(token, 0)
            }
        )
        for field in MATCH_FIELDS
    }


def _field_matches(
    document: SearchDocument,
    query_tokens: list[str],
    passage: Passage | None = None,
) -> list[dict[str, str]]:
    """Which of the reader's words matched, and where.

    The name fields describe the whole note, so they are read note-wide. `body`
    is read from the section that won, because that is the section being cited:
    reporting a word found three sections away tells the reader it is in the
    passage in front of them. #118 named this before the code existed, and the
    first implementation did it anyway — a result citing a section holding only
    `jitter` reported `body: jitter, 毫秒`, with `毫秒` in a different section.
    """
    signals: list[dict[str, str]] = []
    labels = {
        "title": "title",
        "aliases": "alias",
        "tags": "tag",
        "headings": "heading",
        "links": "link",
        "body": "body",
    }
    by_field = _matched_by_field(document, query_tokens, passage)
    for field in MATCH_FIELDS:
        matches = by_field[field]
        if matches:
            signals.append(
                {
                    "kind": labels[field],
                    "detail": ", ".join(matches)[:160],
                }
            )
    return signals


def _name_boost(
    query: str, document: SearchDocument
) -> tuple[float, list[dict[str, str]]]:
    query_name = _normalize_name(query)
    if not query_name:
        return 0.0, []
    candidates = [("title", document.title), *[("alias", alias) for alias in document.aliases]]
    for kind, candidate in candidates:
        candidate_name = _normalize_name(candidate)
        if candidate_name == query_name:
            return 12.0, [{"kind": f"{kind}-exact", "detail": candidate}]
    best: tuple[float, str, str] | None = None
    for kind, candidate in candidates:
        ratio = SequenceMatcher(None, query_name, _normalize_name(candidate)).ratio()
        if best is None or ratio > best[0]:
            best = (ratio, kind, candidate)
    if best is not None and best[0] >= 0.72:
        return 4.0 * best[0], [
            {
                "kind": f"{best[1]}-fuzzy",
                "detail": f"{best[2]} ({best[0]:.2f})",
            }
        ]
    return 0.0, []


# BM25's two free parameters, named so an experiment can move them and a reader
# can see what they are. `b` is the length-penalty strength: 0 charges a note
# nothing for its length, 1 charges it in full proportion to how far it sits
# above the corpus average. These are the textbook defaults and have never been
# fitted to this corpus.
BM25_K1 = 1.5
BM25_B = 0.75


def _inverse_frequency(df: int, document_count: int) -> float:
    """How rare a word is in this corpus — the scorer's IDF, defined once.

    `_confidence` weighs a query's words by exactly this, so "informative" and
    "highly scored" cannot drift apart into two notions of the same word.
    """
    return math.log(1.0 + (document_count - df + 0.5) / (df + 0.5))


def _bm25_score(
    document: SearchDocument,
    token_weights: dict[str, float],
    document_frequencies: Counter[str],
    document_count: int,
    average_length: float,
) -> tuple[float, Passage | None]:
    """Weighted BM25 over the note's best section, and which section that was.

    A typed token weighs 1.0; an expanded one weighs less. The weight multiplies
    the term's finished contribution rather than its raw frequency, so an
    expanded token is worth a fixed fraction of the same token typed directly,
    independent of how often the note repeats it.

    One formula and one normalisation, exactly as before; what changed is the
    unit. The names — title, aliases, tags, headings, links — describe the whole
    note and so enter every section's frequency and length, while the body is
    partitioned and only the best-scoring section counts. A note without
    headings has one section equal to its whole body, so its score is unchanged.

    Document frequency stays note-level. "How rare is this word in the Vault" is
    a question about notes, and counting sections would make a word common
    merely because one note repeats it in thirty places.
    """
    if document_count == 0:
        return 0.0, None
    k1 = BM25_K1
    b = BM25_B
    names = {
        field: counts
        for field, counts in document.field_tokens.items()
        if field != "body"
    }
    best_score = 0.0
    best_passage: Passage | None = None
    # A note whose body holds no tokens at all — empty, or headings only — has
    # no passages. It can still match on its title, tags or aliases, so it gets
    # one empty section rather than being dropped from scoring entirely.
    for passage in document.passages or (EMPTY_PASSAGE,):
        length = document.scoring_length(passage)
        score = 0.0
        for token, weight in token_weights.items():
            frequency = sum(
                FIELD_WEIGHTS[field] * counts.get(token, 0)
                for field, counts in names.items()
            ) + FIELD_WEIGHTS["body"] * passage.tokens.get(token, 0)
            if frequency <= 0:
                continue
            inverse_frequency = _inverse_frequency(
                document_frequencies[token], document_count
            )
            normalization = k1 * (
                1.0 - b + b * length / max(average_length, 1.0)
            )
            score += weight * inverse_frequency * (
                frequency * (k1 + 1.0) / (frequency + normalization)
            )
        if best_passage is None or score > best_score:
            best_score, best_passage = score, passage
    return best_score, best_passage


def _expansion_signals(
    document: SearchDocument,
    expansion: QueryExpansion,
    passage: Passage | None = None,
) -> list[dict[str, str]]:
    """Name the concepts that actually reached this note, and nothing else.

    A concept that fired on the query but matched nothing here would be noise in
    the result; a concept that matched must be visible, or the reader cannot
    tell which words were the search's idea rather than their own.

    Same rule as `_field_matches`: names are read note-wide, body from the
    section being cited.
    """
    signals: list[dict[str, str]] = []
    fields = {
        field: (
            passage.tokens
            if field == "body" and passage is not None
            else counts
        )
        for field, counts in document.field_tokens.items()
    }
    for concept in expansion.concepts:
        hits = [
            token
            for token in concept.added
            if any(counts.get(token, 0) for counts in fields.values())
        ]
        if hits:
            signals.append(
                {
                    "kind": "expansion",
                    "detail": f"{concept.matched} → {', '.join(hits)}"[:160],
                }
            )
    return signals


def _snippet(
    document: SearchDocument,
    query_tokens: list[str],
    passage: Passage | None = None,
) -> tuple[str | None, int | None, str]:
    """Cite from the section the ranking chose, when there was one.

    Before #118 the note was ranked whole and the snippet picked afterwards, so
    the two could point at different parts of the same note and a reader
    following the line number landed somewhere the ranking never weighed.
    Restricting the search to the winning section makes them one decision.
    """
    if passage is not None:
        return _snippet_within(document, query_tokens, passage)
    return _snippet_within(
        document,
        query_tokens,
        Passage(
            heading=None,
            start_line=0,
            end_line=len(document.body.splitlines()),
            tokens=Counter(),
            length=0,
        ),
    )


def _snippet_within(
    document: SearchDocument, query_tokens: list[str], passage: Passage
) -> tuple[str | None, int | None, str]:
    lines = document.body.splitlines()
    window_start = max(0, passage.start_line)
    window_end = min(len(lines), passage.end_line)
    current_heading: str | None = None
    headings: list[str | None] = []
    scores: list[int] = []
    visible_indexes: list[int] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            current_heading = match.group(2).strip()
        headings.append(current_heading)
        if not window_start <= index < window_end:
            scores.append(0)
            continue
        plain = line.strip()
        if plain and not match:
            visible_indexes.append(index)
        tokens = Counter(tokenize(plain))
        scores.append(sum(min(tokens[token], 3) for token in set(query_tokens)))
    matched = [index for index, score in enumerate(scores) if score > 0]
    best_index = (
        min(
            matched,
            key=lambda index: (
                -scores[index],
                HEADING_RE.match(lines[index]) is not None,
                index,
            ),
        )
        if matched
        else (visible_indexes[0] if visible_indexes else None)
    )
    if best_index is None:
        return None, None, ""
    # The context window stays inside the winning section too. A line borrowed
    # from the section above reads as part of the evidence and is not.
    window = [
        lines[index].strip()
        for index in range(
            max(window_start, best_index - 1), min(window_end, best_index + 2)
        )
        if lines[index].strip() and not HEADING_RE.match(lines[index])
    ]
    text = re.sub(r"\s+", " ", " ".join(window)).strip()
    if len(text) > MAX_SNIPPET_CHARS:
        text = text[: MAX_SNIPPET_CHARS - 1].rstrip() + "…"
    return headings[best_index], document.body_start_line + best_index, text


def search_vault(
    vault: Path,
    query: str,
    *,
    top_k: int = 5,
    scope: Path | None = None,
    types: list[str] | None = None,
    tags: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    expand: bool = True,
) -> dict[str, Any]:
    """Search a validated Vault without writing files or persistent cache."""
    if not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must contain 1 to {MAX_QUERY_CHARS} characters")
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
    filters = Filters(
        types=tuple(types or ()),
        tags=tuple(tags or ()),
        after=after,
        before=before,
        updated_after=updated_after,
        updated_before=updated_before,
    )
    root = validate_vault_root(vault)
    selected_scope = (
        resolve_existing_within_vault(root, scope, label="scope")
        if scope is not None
        else root
    )
    if not selected_scope.is_dir():
        raise ValueError("scope must be a directory")
    documents, scanned, issues = _load_documents(root, selected_scope)
    # Filters run before scoring, so IDF is computed over the candidate set the
    # caller actually asked about and `score` keeps meaning what it meant.
    candidates = len(documents)
    documents, filter_excluded = filters.select(documents)
    query_tokens = tokenize(query)
    expansion = (
        expand_query(query, load_lexicon(root)) if expand else QueryExpansion()
    )
    typed = set(query_tokens)
    added = [token for token in expansion.tokens if token not in typed]
    # A token the reader typed keeps full weight even when a concept also
    # proposes it: direct evidence is never demoted by a guess that agrees.
    token_weights: dict[str, float] = {token: EXPANSION_WEIGHT for token in added}
    token_weights.update({token: 1.0 for token in query_tokens})
    scoring_tokens = query_tokens + added
    frequencies = _document_frequencies(documents, set(scoring_tokens))
    # The yardstick must describe the same unit the scorer compares against —
    # names plus one section — or every note is normalised against a length no
    # document in the corpus actually has.
    average_length = (
        sum(document.average_scoring_length for document in documents)
        / len(documents)
        if documents
        else 0.0
    )
    scored: list[
        tuple[float, SearchDocument, list[dict[str, str]], Passage | None]
    ] = []
    for document in documents:
        lexical, passage = _bm25_score(
            document,
            token_weights,
            frequencies,
            len(documents),
            average_length,
        )
        # The name boost reads the raw query only. An expansion must never
        # manufacture a title-exact match out of a word nobody typed.
        boost, bonus_signals = _name_boost(query, document)
        total = lexical + boost
        if total <= 0:
            continue
        scored.append(
            (
                total,
                document,
                bonus_signals
                # Direct matches first, then what the lexicon contributed, so a
                # `body` signal never names a word the reader did not type.
                + _field_matches(document, query_tokens, passage)
                + _expansion_signals(document, expansion, passage),
                passage,
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1].relative.casefold(), item[1].relative))
    results: list[dict[str, Any]] = []
    for rank, (score, document, signals, passage) in enumerate(
        scored[:top_k], start=1
    ):
        heading, line, snippet = _snippet(document, scoring_tokens, passage)
        results.append(
            {
                "rank": rank,
                "path": document.relative,
                "title": document.title,
                "score": round(score, 6),
                "heading": heading,
                "line": line,
                "snippet": snippet,
                "signals": signals,
                "type": document.note_type,
                "date": document.note_date,
                "updated": document.note_updated,
            }
        )
    scope_relative = selected_scope.relative_to(root).as_posix()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": "lexical",
        "query": query,
        "scope": scope_relative or ".",
        "scanned": scanned,
        "results": results,
        # Always present, including on zero results: "how much of what you asked
        # is in this answer" is a question every caller has, and a field that
        # appears only sometimes is a field callers learn not to read.
        "confidence": _confidence(
            document=scored[0][1] if scored else None,
            passage=scored[0][3] if scored else None,
            query_tokens=query_tokens,
            document_frequencies=frequencies,
            document_count=len(documents),
        ),
        "issues": issues,
        "truncated": len(scored) > top_k,
    }
    if expansion.active:
        # Which words the search added, and on whose authority. Without this the
        # reader cannot reproduce the ranking or tell a lexicon mistake from a
        # Vault that genuinely says something surprising.
        payload["expansion"] = expansion.payload()
    if filters.active:
        # Without this an over-narrow filter is indistinguishable from an empty
        # Vault, and the honest answer "nothing matched this filter" reads as
        # "you have no notes about this".
        payload["filters"] = {
            "applied": filters.applied(),
            "candidates": candidates,
            "matched": len(documents),
            "excluded": filter_excluded,
        }
    if not results:
        # `results: []` was one shape for four different facts, each with a
        # different next step. Present only when there is nothing to explain
        # away: a found result needs no account of why nothing was found.
        payload["diagnostics"] = _diagnose(
            candidates=candidates,
            matched=len(documents),
            issues=issues,
            filters=filters,
            expansion=expansion,
            scope=scope_relative or ".",
        )
    return payload


# One table, two consumers. #120 requires the text hint and the JSON code to
# come from the same place: two independent answers to "why nothing" is the
# defect this diagnosis exists to remove, reproduced one level up.
# One threshold, because the measurements support one. On the reference Vault
# (231 notes) 22 queries with no answer in it score 0.09–0.54, and 16 questions
# phrased the way a person types them, against topics the Vault does cover and
# whose top-1 is right, score 0.32–0.64. Those ranges **overlap**: no cut
# separates them. A cut at 0.30 is the one useful point — it catches 20 of the
# 22 with no answer and demotes none of the 16 correct ones.
#
# An earlier draft of this code read 0.60 with a third `high` band, from a
# positive set built by lifting sentences out of the notes' own bodies. That
# construction guarantees the words are present; it reported a 0.66 floor and a
# clean gap, and at 0.60 it would have flagged 12 of these 16 correct answers.
# The sampling produced the gap, not the ranker. Two levels are what survived.
#
# What this cannot do: the two queries that slip through are `Feign 和
# HttpExchange 有什么区别` (0.54) and `Spring Boot 事务失效` (0.48) — #170's own
# examples. Both name real technologies in the Vault's own Java and Spring
# domain, so they share informative words with notes that do not answer them.
# Near-miss detection is not solved here and must not be claimed.
#
# See docs/superpowers/specs/2026-08-23-answer-confidence-design.md.
CONFIDENCE_FLOOR = 0.30

CONFIDENCE_LEVELS: dict[str, str] = {
    "evidence": "the top result carries words specific to the query",
    "none": "the results share only the query's least informative words",
}


def _confidence(
    *,
    document: "SearchDocument | None",
    passage: "Passage | None",
    query_tokens: list[str],
    document_frequencies: Counter[str],
    document_count: int,
) -> dict[str, Any]:
    """Whether the winning result answers the query or merely shares words with it.

    #170: a search that finds nothing useful returns hits anyway, with a score,
    a heading and a snippet — the shape of a search that succeeded. Asked
    "Feign 和 HttpExchange 有什么区别" the reference Vault returns a note on
    Python functional programming, and the words it matched are 么区, 什么,
    区别, 和, 有什: every one a question frame, neither technical term among
    them. The caller cannot see that, so an Agent either cites the wrong note
    or concludes the topic is already covered and never captures it.

    The measure is how much of the query's *information* the winner holds:
    IDF-weighted share of the typed tokens it matched. IDF is what makes
    "informative" countable here — a stop-word list would need a countable
    source, which #147 and #75 both settled that it must have, and question
    frames like 有什么 have none.

    Only tokens the reader typed count. An expansion token is the ranker's own
    guess at what was meant, and letting a guess certify the confidence of the
    result it produced is circular.

    Two things this does **not** measure. It is not "was this the best note":
    `adv-crowding-01` scores 1.00 with a wrong top-1, because those near-
    identical dailies really do contain every word of the query, and redundancy
    is Top-K selection's problem. And `evidence` is not a claim of correctness —
    it says the result carries specific words from the query, which a wrong note
    on a neighbouring topic can also do. Only `none` is a finding.
    """
    if document is None or not query_tokens:
        return {
            "level": "none",
            "coverage": 0.0,
            "explanation": CONFIDENCE_LEVELS["none"],
        }
    matched = {
        token
        for tokens in _matched_by_field(document, query_tokens, passage).values()
        for token in tokens
    }
    total = sum(
        _inverse_frequency(document_frequencies[token], document_count)
        for token in set(query_tokens)
    )
    held = sum(
        _inverse_frequency(document_frequencies[token], document_count)
        for token in matched
    )
    coverage = held / total if total else 0.0
    level = "evidence" if coverage >= CONFIDENCE_FLOOR else "none"
    return {
        "level": level,
        "coverage": round(coverage, 3),
        "explanation": CONFIDENCE_LEVELS[level],
    }


ZERO_RESULT_REASONS: dict[str, str] = {
    "all-candidates-filtered": "the active filters excluded every candidate",
    "material-files-skipped": "nothing in scope could be read",
    "no-searchable-documents": "the scope holds no searchable note",
    "no-token-overlap": "candidates exist, but none share a word with the query",
}


def _diagnose(
    *,
    candidates: int,
    matched: int,
    issues: list[dict[str, Any]],
    filters: "Filters",
    expansion: Any,
    scope: str,
) -> dict[str, Any]:
    """Why this search returned nothing, from counts already in hand.

    Only mechanically provable reasons. The helper does not guess at spelling,
    synonyms, or what the user meant, and it never re-runs: `safe_retries` are
    sentences the *user* acts on. A suggestion is a next step, not permission.

    Several reasons can hold at once, so one is named primary and the rest stay
    in `facts`. The order is by proximate cause: a filter the user just added
    explains the emptiness better than the words not overlapping, and an
    unreadable note explains it better than an empty folder — that scope is not
    empty, it is broken, and telling the user to write notes they already have
    is the wrong next step.
    """
    if matched == 0 and candidates > 0:
        reason = "all-candidates-filtered"
    elif candidates == 0 and issues:
        reason = "material-files-skipped"
    elif candidates == 0:
        reason = "no-searchable-documents"
    else:
        reason = "no-token-overlap"

    retries: list[str] = []
    if reason == "all-candidates-filtered":
        applied = ", ".join(sorted(filters.applied())) or "the active filters"
        retries.append(f"widen or drop the filter(s) you set: {applied}")
        retries.append("run the same query with no filter to see what exists")
    elif reason == "material-files-skipped":
        retries.append(
            "repair the note(s) reported in `issues`, then search again"
        )
    elif reason == "no-searchable-documents":
        if scope != ".":
            retries.append(f"drop --scope {scope} to search the whole Vault")
        retries.append("confirm this folder holds notes with a `.md` extension")
    else:
        if getattr(expansion, "active", False):
            retries.append(
                "compare with --no-expand: if that also returns nothing, the "
                "expansion is not what is missing"
            )
        else:
            retries.append(
                "no concept matched, so only the words you typed were searched"
            )
        retries.append("try a word the notes themselves use, not a synonym")
        retries.append(
            "if a term pair is genuinely missing, ask the user to approve it "
            "before editing the Vault's lexicon"
        )

    return {
        "primary_reason": reason,
        "explanation": ZERO_RESULT_REASONS[reason],
        # Everything true at once, so a second reason is visible rather than
        # discarded. `expansion_triggered` is a fact here and never a primary
        # reason: a lexicon that added nothing does not prove it is wrong.
        #
        # `scanned` is deliberately absent: the payload already carries it at
        # the top level, and a second copy here would be one more pair that has
        # to agree. Read it from there.
        "facts": {
            "candidates": candidates,
            "matched": matched,
            "files_skipped": len(issues),
            "expansion_triggered": bool(getattr(expansion, "active", False)),
            "filters_active": filters.active,
        },
        "safe_retries": retries,
    }


def _json_error(code: str, message: str) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "error": {"code": code, "message": message},
        },
        ensure_ascii=False,
    )


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Search an Obsidian Vault without writing files."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian Vault")
    parser.add_argument("--query", required=True, help="Natural-language search query")
    parser.add_argument("--scope", type=Path, help="Optional Vault-relative directory")
    parser.add_argument("--top-k", type=int, default=5, help="Results to return (1-20)")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    parser.add_argument(
        "--type", dest="types", action="append", default=[],
        help="Keep only this note type; repeatable (repeats are OR)",
    )
    parser.add_argument(
        "--tag", dest="tags", action="append", default=[],
        help="Keep only notes carrying this tag; repeatable (repeats are OR)",
    )
    parser.add_argument(
        "--after", help="Keep notes dated on or after this ISO date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--before", help="Keep notes dated on or before this ISO date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--updated-after",
        help=(
            "Keep notes whose `updated` is on or after this ISO date. Reads "
            "`updated` only — a note without one is excluded, never treated "
            "as if its `date` were the answer"
        ),
    )
    parser.add_argument(
        "--updated-before",
        help="Keep notes whose `updated` is on or before this ISO date",
    )
    parser.add_argument(
        "--no-expand",
        dest="expand",
        action="store_false",
        help="Match only the words in the query, with no bilingual expansion",
    )
    args = parser.parse_args(argv)

    def refuse(code: str, message: str) -> int:
        if args.json:
            print(_json_error(code, message))
        else:
            print(f"error: {message}", file=sys.stderr)
        return 2

    if not args.query.strip() or len(args.query) > MAX_QUERY_CHARS:
        message = f"--query must contain 1 to {MAX_QUERY_CHARS} characters"
        if args.json:
            print(_json_error("invalid-query", message))
        else:
            print(f"error: {message}", file=sys.stderr)
        return 2
    if not 1 <= args.top_k <= MAX_TOP_K:
        message = f"--top-k must be between 1 and {MAX_TOP_K}"
        if args.json:
            print(_json_error("invalid-top-k", message))
        else:
            print(f"error: {message}", file=sys.stderr)
        return 2
    # Relative time ("上周", "recently") is resolved by the caller, which knows
    # today's date and the user's language; this helper takes absolute dates so
    # its behaviour stays deterministic and testable.
    for flag in ("after", "before", "updated_after", "updated_before"):
        value = getattr(args, flag)
        if value is None:
            continue
        if not _is_iso_date(value):
            return refuse(
                "invalid-date",
                f"--{flag.replace('_', '-')} must be an ISO calendar date "
                "(YYYY-MM-DD); resolve relative expressions before calling",
            )
    if args.after and args.before and args.after > args.before:
        return refuse(
            "invalid-date-range", "--after must not be later than --before"
        )
    if (
        args.updated_after
        and args.updated_before
        and args.updated_after > args.updated_before
    ):
        return refuse(
            "invalid-date-range",
            "--updated-after must not be later than --updated-before",
        )
    for value in args.types:
        if value not in VALID_NOTE_TYPES:
            return refuse(
                "invalid-type",
                f"--type {value!r} is not a known note type; "
                f"known types: {', '.join(sorted(VALID_NOTE_TYPES))}",
            )
    for value in args.tags:
        if not value.strip() or len(value) > MAX_TAG_CHARS:
            return refuse(
                "invalid-tag",
                f"--tag must contain 1 to {MAX_TAG_CHARS} non-blank characters",
            )
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        return report_cli_violation(exc, param="vault", json_mode=args.json)
    if not (vault / ".obsidian").is_dir():
        message = "not an Obsidian Vault"
        if args.json:
            print(_json_error("invalid-vault", message))
        else:
            print(f"error: {message}", file=sys.stderr)
        return 2
    selected_scope = vault
    if args.scope is not None:
        try:
            selected_scope = resolve_existing_within_vault(
                vault, args.scope, label="--scope"
            )
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--scope", json_mode=args.json)
        if not selected_scope.is_dir():
            message = "--scope must be a directory"
            if args.json:
                print(_json_error("invalid-scope", message))
            else:
                print(f"error: {message}", file=sys.stderr)
            return 2
    try:
        payload = search_vault(
            vault,
            args.query,
            top_k=args.top_k,
            scope=selected_scope,
            types=args.types,
            tags=args.tags,
            after=args.after,
            before=args.before,
            updated_after=args.updated_after,
            updated_before=args.updated_before,
            expand=args.expand,
        )
    except LexiconError as exc:
        # Refuse rather than fall back to the built-in concepts. A search that
        # quietly ran with different vocabulary than the file describes is a
        # search nobody can reproduce, and the typo is in a file the user wrote.
        return refuse("invalid-lexicon", str(exc))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    expansion = payload.get("expansion")
    if expansion:
        # Say it even when nothing matched: "we also looked for these and still
        # found nothing" is a different answer from "we only looked for what you
        # typed". The exact tokens stay in --json.
        concepts = ", ".join(
            f"{concept['matched']} → {concept['id']}"
            for concept in expansion["concepts"]
        )
        print(f"also searched ({expansion['weight']:.2f} weight): {concepts}")
    if not payload["results"]:
        print(f"No results for: {args.query}")
        diagnostics = payload.get("diagnostics")
        if diagnostics:
            # Same table as the JSON, so the two can never give different
            # answers to the same question.
            print(
                f"reason: {diagnostics['primary_reason']} — "
                f"{diagnostics['explanation']}"
            )
            facts = diagnostics["facts"]
            print(
                f"indexed {payload['scanned'].get('indexed', 0)}, "
                f"candidates {facts['candidates']}, "
                f"matched {facts['matched']}, "
                f"skipped {facts['files_skipped']}"
            )
            for retry in diagnostics["safe_retries"]:
                print(f"  try: {retry}")
        return 0
    confidence = payload["confidence"]
    if confidence["level"] == "none":
        # Before the results, not after: a reader who sees five ranked hits
        # first has already believed them. Printed only when it is not `high`,
        # the way `expansion` and `filters` announce themselves only when they
        # acted — the field itself is unconditional in --json, which is where a
        # caller reads it programmatically. Same table as the JSON, so the two
        # can never disagree about what a level means.
        print(
            f"confidence: {confidence['level']} "
            f"(coverage {confidence['coverage']:.2f}) — {confidence['explanation']}"
        )
    for result in payload["results"]:
        location = f"{result['path']}:{result['line']}" if result["line"] else result["path"]
        heading = f" — {result['heading']}" if result["heading"] else ""
        print(f"{result['rank']:>2}. {location}{heading} [{result['score']:.3f}]")
        if result["snippet"]:
            print(f"    {result['snippet']}")
        reasons = ", ".join(signal["kind"] for signal in result["signals"])
        if reasons:
            print(f"    matches: {reasons}")
    if payload["issues"]:
        print(f"{len(payload['issues'])} note(s) skipped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
