#!/usr/bin/env python3
"""Suggest wikilink targets for a single note, read-only.

Scans a bounded scope (the note's folder plus up to two relevant sibling
folders), scores each candidate by specific shared tags, matching type, and
Unicode-aware title-token overlap, and prints only confident candidates with
reasons. It never writes to the vault — a human decides whether to insert a
link.

Reuses vault-parsing helpers from audit_vault.py.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.audit_vault import (
    EXEMPT_NAMES,
    INDEX_TYPES,
    _frontmatter,
    _is_ignored,
    _markdown_files,
    _note_title,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    validate_vault_root,
)


MIN_SCORE = 3
GENERIC_TAGS = {
    "daily",
    "digest",
    "insight",
    "java",
    "learning",
    "meeting",
    "person",
    "project",
    "task",
    "web-clip",
}
GENERIC_TITLE_TOKENS = {
    "详解",
    "指南",
    "实践",
    "教程",
    "攻略",
    "入门",
    "解析",
    "介绍",
    "总结",
    "分享",
    "guide",
    "tutorial",
    "overview",
    "introduction",
    "intro",
    "practice",
    "explained",
}


@dataclass(frozen=True)
class Candidate:
    path: Path
    metadata: dict[str, Any] | None
    title: str


def _title_tokens(title: str) -> set[str]:
    """Return useful Latin runs and overlapping CJK bigrams."""
    if not title:
        return set()
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", title.lower())
        if len(token) >= 2 and not token.isdigit()
    }
    for run in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", title):
        if len(run) >= 2:
            tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens - GENERIC_TITLE_TOKENS


def _scope_terms(title: str, metadata: dict[str, Any] | None) -> set[str]:
    terms = _title_tokens(title)
    for tag in _tags(metadata):
        terms.update(_title_tokens(tag))
    return terms


def scope_folders(vault: Path, note: Path, terms: set[str]) -> list[Path]:
    folder = note.parent
    parent = vault if folder == vault else folder.parent
    related: list[Path] = []
    for candidate in parent.iterdir():
        if not candidate.is_dir() or candidate == folder:
            continue
        if _is_ignored(candidate.relative_to(vault)):
            continue
        if _title_tokens(candidate.name) & terms:
            related.append(candidate)
    return [folder] + sorted(related)[:2]


def candidate_notes(
    vault: Path,
    note: Path,
    metadata: dict[str, Any] | None,
    title: str,
) -> list[Candidate]:
    scope = set(scope_folders(vault, note, _scope_terms(title, metadata)))
    candidates: list[Candidate] = []
    for path in _markdown_files(vault):
        if path == note:
            continue
        if path.parent not in scope:
            continue
        relative = path.relative_to(vault)
        if relative.parts and relative.parts[0] == "Templates":
            continue
        if relative.name in EXEMPT_NAMES:
            continue
        text = path.read_text(encoding="utf-8")
        candidate_metadata, _ = _frontmatter(text)
        if candidate_metadata and candidate_metadata.get("type") in INDEX_TYPES:
            continue
        candidates.append(Candidate(path, candidate_metadata, _note_title(path, text)))
    return candidates


def _tags(metadata: dict[str, Any] | None) -> set[str]:
    raw = (metadata or {}).get("tags")
    if not raw:
        return set()
    values = raw if isinstance(raw, list) else [raw]
    return {str(tag).lower() for tag in values if str(tag).strip()}


def _related_targets(metadata: dict[str, Any] | None) -> set[str]:
    related = (metadata or {}).get("related")
    targets: set[str] = set()
    if isinstance(related, list):
        for entry in related:
            if isinstance(entry, str):
                stripped = entry.strip()
                if stripped.startswith("[[") and stripped.endswith("]]"):
                    inner = stripped[2:-2].split("|")[0].split("#")[0].split("^")[0].strip().lower()
                    targets.add(inner)
    return targets


def score_pair(
    target_meta: dict[str, Any] | None,
    cand_meta: dict[str, Any] | None,
    target_title: str,
    cand_title: str,
    generic_tags: set[str] | None = None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    shared = (_tags(target_meta) & _tags(cand_meta)) - (generic_tags or set())
    if shared:
        score += 3 * len(shared)
        reasons.append("shared tags: " + ", ".join(sorted(shared)))
    t_type = (target_meta or {}).get("type")
    c_type = (cand_meta or {}).get("type")
    if t_type and t_type == c_type:
        score += 1
        reasons.append(f"same type: {t_type}")
    overlap = _title_tokens(target_title) & _title_tokens(cand_title)
    if overlap:
        score += min(6, 2 * len(overlap))
        reasons.append("title overlap: " + ", ".join(sorted(overlap)))
    return score, reasons


def suggest_links(vault: Path, note_path: Path, top_n: int = 10) -> list[tuple[Path, int, list[str]]]:
    vault = vault.resolve()
    note = note_path.resolve()
    text = note.read_text(encoding="utf-8")
    metadata, _ = _frontmatter(text)
    title = _note_title(note, text)
    related = _related_targets(metadata)
    candidates = candidate_notes(vault, note, metadata, title)
    tag_counts = Counter(tag for candidate in candidates for tag in _tags(candidate.metadata))
    generic_tags = set(GENERIC_TAGS)
    generic_tags.update(
        tag
        for tag, count in tag_counts.items()
        if count >= 2 and count * 2 >= len(candidates)
    )

    results: list[tuple[Path, int, list[str]]] = []
    for candidate in candidates:
        if candidate.path.stem.lower() in related or candidate.title.lower() in related:
            continue
        score, reasons = score_pair(
            metadata,
            candidate.metadata,
            title,
            candidate.title,
            generic_tags,
        )
        if score >= MIN_SCORE:
            results.append((candidate.path, score, reasons))
    results.sort(key=lambda item: (-item[1], item[0].as_posix()))
    return results[:top_n]


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Suggest wikilink targets for a single note (read-only)."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--note", type=Path, required=True, help="Note to suggest links for")
    parser.add_argument("--top-n", type=int, default=10, help="Max candidates to print")
    parser.add_argument(
        "--json", action="store_true", help="Emit suggestions as JSON instead of text"
    )
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2
    try:
        note = resolve_existing_within_vault(vault, args.note, label="--note")
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--note", json_mode=args.json)
    if not note.is_file():
        print(f"error: note not found: {note}", file=sys.stderr)
        return 2

    results = suggest_links(vault, note, args.top_n)
    if args.json:
        out = [
            {"path": path.as_posix(), "score": score, "reasons": reasons}
            for path, score, reasons in results
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("No link suggestions found.")
    for path, score, reasons in results:
        print(f"{score:>3}  {path.as_posix()}")
        for reason in reasons:
            print(f"        - {reason}")
    print(f"{len(results)} suggestion(s) for {note.as_posix()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
