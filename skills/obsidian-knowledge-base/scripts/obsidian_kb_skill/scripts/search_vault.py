#!/usr/bin/env python3
"""Deterministic, explainable, read-only search for an Obsidian Vault."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
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
}
LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
TOKEN_RUN_RE = re.compile(r"[A-Za-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]+")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


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

    @property
    def weighted_length(self) -> float:
        return sum(
            FIELD_WEIGHTS[field] * sum(tokens.values())
            for field, tokens in self.field_tokens.items()
        )


def tokenize(text: str) -> list[str]:
    """Return stable lowercase Latin tokens and overlapping CJK bigrams."""
    tokens: list[str] = []
    for match in TOKEN_RUN_RE.finditer(text):
        run = match.group(0)
        if LATIN_TOKEN_RE.fullmatch(run):
            tokens.append(run.lower())
        elif len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


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
    for line in body.splitlines():
        match = re.match(r"^#[ \t]+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return path.stem


def _headings(body: str) -> tuple[str, ...]:
    return tuple(
        match.group(2).strip()
        for line in body.splitlines()
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
    fields = {
        "title": Counter(tokenize(title)),
        "aliases": Counter(tokenize(" ".join(aliases))),
        "tags": Counter(tokenize(" ".join(tags))),
        "headings": Counter(tokenize(" ".join(headings))),
        "links": Counter(tokenize(" ".join(links))),
        "body": Counter(tokenize(visible_body)),
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
    for path in _markdown_files(scope):
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


def _field_matches(
    document: SearchDocument, query_tokens: list[str]
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    labels = {
        "title": "title",
        "aliases": "alias",
        "tags": "tag",
        "headings": "heading",
        "links": "link",
        "body": "body",
    }
    for field in ("title", "aliases", "tags", "headings", "links", "body"):
        matches = sorted(
            {
                token
                for token in query_tokens
                if document.field_tokens[field].get(token, 0)
            }
        )
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


def _bm25_score(
    document: SearchDocument,
    query_tokens: list[str],
    document_frequencies: Counter[str],
    document_count: int,
    average_length: float,
) -> float:
    if document_count == 0:
        return 0.0
    k1 = 1.5
    b = 0.75
    length = document.weighted_length
    score = 0.0
    for token in set(query_tokens):
        frequency = sum(
            FIELD_WEIGHTS[field] * counts.get(token, 0)
            for field, counts in document.field_tokens.items()
        )
        if frequency <= 0:
            continue
        df = document_frequencies[token]
        inverse_frequency = math.log(
            1.0 + (document_count - df + 0.5) / (df + 0.5)
        )
        normalization = k1 * (
            1.0 - b + b * length / max(average_length, 1.0)
        )
        score += inverse_frequency * (
            frequency * (k1 + 1.0) / (frequency + normalization)
        )
    return score


def _snippet(
    document: SearchDocument, query_tokens: list[str]
) -> tuple[str | None, int | None, str]:
    lines = document.body.splitlines()
    current_heading: str | None = None
    headings: list[str | None] = []
    scores: list[int] = []
    visible_indexes: list[int] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            current_heading = match.group(2).strip()
        headings.append(current_heading)
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
    window = [
        lines[index].strip()
        for index in range(max(0, best_index - 1), min(len(lines), best_index + 2))
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
) -> dict[str, Any]:
    """Search a validated Vault without writing files or persistent cache."""
    if not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must contain 1 to {MAX_QUERY_CHARS} characters")
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
    root = validate_vault_root(vault)
    selected_scope = (
        resolve_existing_within_vault(root, scope, label="scope")
        if scope is not None
        else root
    )
    if not selected_scope.is_dir():
        raise ValueError("scope must be a directory")
    documents, scanned, issues = _load_documents(root, selected_scope)
    query_tokens = tokenize(query)
    frequencies = _document_frequencies(documents, set(query_tokens))
    average_length = (
        sum(document.weighted_length for document in documents) / len(documents)
        if documents
        else 0.0
    )
    scored: list[tuple[float, SearchDocument, list[dict[str, str]]]] = []
    for document in documents:
        lexical = _bm25_score(
            document,
            query_tokens,
            frequencies,
            len(documents),
            average_length,
        )
        boost, bonus_signals = _name_boost(query, document)
        total = lexical + boost
        if total <= 0:
            continue
        scored.append(
            (total, document, bonus_signals + _field_matches(document, query_tokens))
        )
    scored.sort(key=lambda item: (-item[0], item[1].relative.casefold(), item[1].relative))
    results: list[dict[str, Any]] = []
    for rank, (score, document, signals) in enumerate(scored[:top_k], start=1):
        heading, line, snippet = _snippet(document, query_tokens)
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
            }
        )
    scope_relative = selected_scope.relative_to(root).as_posix()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "lexical",
        "query": query,
        "scope": scope_relative or ".",
        "scanned": scanned,
        "results": results,
        "issues": issues,
        "truncated": len(scored) > top_k,
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
    args = parser.parse_args(argv)

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
    payload = search_vault(
        vault,
        args.query,
        top_k=args.top_k,
        scope=selected_scope,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not payload["results"]:
        print(f"No results for: {args.query}")
        return 0
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
