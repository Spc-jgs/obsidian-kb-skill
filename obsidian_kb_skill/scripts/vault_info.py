#!/usr/bin/env python3
"""One-shot read-only vault cold-start context, emitted as JSON.

Replaces the several manual reads an agent would otherwise do on first
contact with a vault (vault discovery, the 3 validity checks, listing
Templates/, probing each folder's existence, and re-deriving the index
strategy per folder). A single call returns a compact JSON summary so the
agent spends tokens reading a summary, not raw directory listings.

Reuses `detect_index.detect` for index-strategy detection and the shared Folder
Index policy for the global config, so there is exactly one source of truth for
those rules (no prose duplication).

Output schema (JSON):
  {
    "vault": "...", "valid": true,
    "validation": {"exists": true, "is_obsidian": true, "has_templates": true},
    "templates": ["Daily Note", "Meeting Note", ...],
    "standard_folders": {
      "00-Inbox": {"exists": true, "index": {<detect result>}},
      ...
      "Templates": {"exists": true, "index": null},
      "Attachments": {"exists": true, "index": null}
    },
    "folder_index_global": {
      "enabled": false, "graph_overwrite": false,
      "user_specified": false, "root_index_file": "INDEX.md"
    },
    "crowded_folders": [
      {"path": "20-Learning/AI-Agent", "direct_notes": 24, "threshold": 20,
       "child_folders": ["Skills"], "cluster_min_notes": 5,
       "clusters": [{"term": "mcp", "kind": "tag", "notes": 8}]}
    ],
    "tag_vocabulary": {
      "scanned": 170, "distinct": 169,
      "tags": [{"tag": "ai-agent", "notes": 38}, ...]
    },
    "required_references": [{"file": "note-creation.md", "reason": "..."}],
    "warnings": ["..."]
  }

`clusters` answers whether a crowded folder holds a subject stable enough to
split off, `tag_vocabulary` answers which tags this Vault already uses so a new
note reuses one instead of coining a near-duplicate, and `required_references`
answers which reference files the selected type, template, and destination
require — all so the agent gets one answer per call instead of discovering the
same facts through its own reads.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.detect_index import detect
from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    read_frontmatter_head,
)
from obsidian_kb_skill.scripts.folder_index_policy import (
    FolderIndexConfig,
    FolderIndexConfigError,
    expected_folder_index,
    is_folder_index_excluded,
    read_folder_index_config,
)
from obsidian_kb_skill.scripts.note_catalog import (
    MANAGED_NOTE_FOLDERS,
    TYPE_TO_FOLDER,
    normalize_tag_key,
)
from obsidian_kb_skill.scripts.audit_vault import INDEX_TYPES
from obsidian_kb_skill.scripts.note_types import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.suggest_links import (
    GENERIC_TAGS,
    _tags,
    _title_tokens,
)
from obsidian_kb_skill.scripts.template_contract import (
    custom_template_types,
    template_shape,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)


# Note-bearing folders that get an index strategy; Templates/Attachments are
# listed for existence only.
NOTE_FOLDERS: list[str] = list(MANAGED_NOTE_FOLDERS)
STANDARD_FOLDERS = NOTE_FOLDERS + ["Templates", "Attachments"]
CROWDED_FOLDER_THRESHOLD = 20
MAX_CROWDED_FOLDERS = 20
# A crowded folder may only be split when a stable subject cluster exists, and
# folder-routing.md puts that bar at five notes. Reporting the clusters here is
# what makes the rule checkable: reading thirty notes to find out is not a
# bounded operation, so the rule was previously unenforceable in practice.
CLUSTER_MIN_NOTES = 5
MAX_CLUSTER_TERMS = 6
MAX_CLUSTER_SCAN = 200
# Discovery used to be pure directory stats. Clustering reads note heads, so it
# runs under a whole-call budget: the selected destination is always analyzed,
# the most crowded folders fill the rest, and anything past it reports its count
# without a cluster list rather than turning one call into thousands of opens.
MAX_CLUSTER_SCAN_TOTAL = 1000
MAX_CHILD_FOLDERS = 12
# Tag hygiene tells the writer to reuse an existing tag before inventing one,
# and then to avoid near-duplicates of tags anywhere in the Vault — but the only
# evidence it offered was the five most recent notes in one folder. That window
# cannot answer a Vault-wide question: a 170-note Vault already carries 169
# distinct tags, so the writer coins a new term, the vocabulary grows, and the
# next window is even less representative. Discovery already opens note heads,
# so it returns the vocabulary and makes the rule checkable instead of merely
# stated. Newest-first and bounded: a large Vault should report the terms it
# uses now, not every term it ever used.
MAX_VOCABULARY_TERMS = 40
MAX_VOCABULARY_SCAN = 1000
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
# Reference files the agent must load next, keyed by what it already told us.
TYPE_REFERENCES: dict[str, tuple[str, str]] = {
    "web-clip": (
        "web-capture.md",
        "source acquisition contract for a finished article",
    ),
    "conversation-digest": (
        "conversation-digest.md",
        "conversation context archive contract",
    ),
}


def _templates(vault: Path) -> list[str]:
    templates_dir = vault / "Templates"
    if not templates_dir.is_dir():
        return []
    return sorted(
        p.stem for p in templates_dir.glob("*.md") if not p.name.startswith(".")
    )


def _index_names(vault: Path, folder: Path, config: FolderIndexConfig) -> set[str]:
    names = {"INDEX.md", f"{folder.name}.md"}
    relative = folder.relative_to(vault)
    if config.enabled and not is_folder_index_excluded(relative, config):
        names.add(expected_folder_index(folder, vault, config).name)
    return names


def _head_metadata(path: Path) -> dict[str, Any] | None:
    """Parse frontmatter from the head of a note without reading the body."""
    return parse_frontmatter(
        read_frontmatter_head(path), source=path.name
    ).metadata


def _merge_overlapping_runs(counts: Counter[str]) -> Counter[str]:
    """Rejoin the bigrams a CJK title was split into, so labels stay readable.

    Tokenizing `服务器实践` yields four overlapping bigrams that all appear in the
    same notes; reported separately they read as four clusters and push real
    ones out of the list. Equal counts plus a shared boundary character is
    strong evidence they came from one phrase, so chain them back together.
    """
    merged: Counter[str] = Counter()
    by_count: dict[int, set[str]] = {}
    for term, total in counts.items():
        if len(term) == 2 and CJK_RE.fullmatch(term):
            by_count.setdefault(total, set()).add(term)
        else:
            merged[term] = total
    for total, group in by_count.items():
        tails = {term[1] for term in group}
        consumed: set[str] = set()
        for head in sorted(group):
            if head in consumed or head[0] in tails:
                continue
            chain = head
            consumed.add(head)
            while True:
                successor = next(
                    (
                        term
                        for term in sorted(group)
                        if term not in consumed and term[0] == chain[-1]
                    ),
                    None,
                )
                if successor is None:
                    break
                chain += successor[1]
                consumed.add(successor)
            merged[chain] = total
        for term in sorted(group - consumed):
            merged[term] = total
    return merged


def subject_clusters(notes: list[Path], folder: str = "") -> list[dict[str, Any]]:
    """Return the subject terms shared by enough notes to justify a child folder.

    Tags and title tokens are counted together because a Vault governs subjects
    through both. Type-default tags carry no subject information and are
    dropped, or every note in `20-Learning` would look like one big cluster.

    Two kinds of term describe the folder rather than a subject inside it, and
    both are removed rather than ranked last: the slots are the scarce resource,
    and on the reference Vault the terms they displaced were the real candidates
    (`llm-engineering` and `vibe-coding` were cut from `20-Learning/AI-Agent`
    while its top four were the folder's own name, both halves of that name, and
    the word "文章"). An empty list is a valid answer — it says this folder has
    no splittable sub-theme.
    """
    scanned = notes[:MAX_CLUSTER_SCAN]
    tags: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    for path in scanned:
        tags.update(_tags(_head_metadata(path)) - GENERIC_TAGS)
        titles.update(_title_tokens(path.stem))
    # A title token that is one hyphen-separated part of a counted tag is not an
    # independent subject: `ai` and `agent` are `ai-agent` seen twice. The
    # existing exact-match guard below never caught them. Parts rather than
    # substrings, so an unrelated token is not swallowed by a longer tag.
    tag_parts = {
        normalize_tag_key(part)
        for tag in tags
        for part in tag.split("-")
        if part
    }
    folder_key = normalize_tag_key(folder) if folder else None

    def splittable(term: str, total: int) -> bool:
        # Both sides of a split have to be able to stand as a folder. Only the
        # part being pulled out was ever checked. Expressed as a remainder
        # rather than a percentage on purpose: it reuses the threshold already
        # in play instead of inventing a second one, and it scales with the
        # folder — covering 6 of 7 notes and 172 of 200 are both 86% and are
        # not remotely the same decision.
        if len(scanned) - total < CLUSTER_MIN_NOTES:
            return False
        # A term equal to the folder's own name is a tautology at any ratio:
        # `20-Learning/AI-Agent/ai-agent/` renames the folder, it does not split
        # it. The remainder rule alone misses this, because `ai-agent` covers 25
        # of 34 notes and leaves 9 behind.
        return folder_key is None or normalize_tag_key(term) != folder_key

    counted = [("tag", tags), ("title", _merge_overlapping_runs(titles))]
    clusters = [
        {"term": term, "kind": kind, "notes": total}
        for kind, group in counted
        for term, total in group.items()
        if total >= CLUSTER_MIN_NOTES
        and not (kind == "title" and term in tags)
        and not (kind == "title" and normalize_tag_key(term) in tag_parts)
        and splittable(term, total)
    ]
    clusters.sort(key=lambda item: (-item["notes"], item["kind"], item["term"]))
    return clusters[:MAX_CLUSTER_TERMS]


def _modified_time(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _template_default_tags(vault: Path) -> set[str]:
    """Return the tags this Vault's own templates already supply.

    Read from the templates rather than a hardcoded list: the defaults are a
    property of the Vault, and a static set both misses what a Vault renamed
    (`person` → `people`) and drops real subjects that merely looked common
    somewhere else. Dropping a live subject tag from the vocabulary would invite
    the near-duplicate the vocabulary exists to prevent.
    """
    directory = vault / "Templates"
    if not directory.is_dir():
        return set()
    defaults: set[str] = set()
    for path in sorted(directory.glob("*.md")):
        defaults |= _tags(_head_metadata(path))
    return defaults


def tag_vocabulary(
    vault: Path,
    *,
    limit: int = MAX_VOCABULARY_TERMS,
    scan: int = MAX_VOCABULARY_SCAN,
) -> dict[str, Any]:
    """Return the subject tags this Vault actually uses, most-used first.

    Type-default tags are dropped because the template already fixes them, and
    index notes are skipped because their tags describe structure rather than a
    subject the writer of a new note gets to choose.
    """
    defaults = _template_default_tags(vault)
    notes: list[Path] = []
    for name in MANAGED_NOTE_FOLDERS:
        directory = vault / name
        if not directory.is_dir() or directory.is_symlink():
            continue
        notes.extend(path for path in directory.rglob("*.md") if path.is_file())
    notes.sort(key=_modified_time, reverse=True)
    scanned = notes[:scan]
    counts: Counter[str] = Counter()
    for path in scanned:
        metadata = _head_metadata(path)
        if (metadata or {}).get("type") in INDEX_TYPES:
            continue
        counts.update(_tags(metadata) - defaults)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "scanned": len(scanned),
        "distinct": len(counts),
        "tags": [{"tag": tag, "notes": total} for tag, total in ordered[:limit]],
    }


def crowded_folders(
    vault: Path,
    config: FolderIndexConfig,
    *,
    threshold: int = CROWDED_FOLDER_THRESHOLD,
    limit: int = MAX_CROWDED_FOLDERS,
    destination: str | None = None,
) -> list[dict[str, Any]]:
    """Return bounded navigation-pressure signals under managed note roots."""
    findings: list[dict[str, Any]] = []
    direct: dict[str, list[Path]] = {}
    stack = [
        vault / name
        for name in MANAGED_NOTE_FOLDERS
        if (vault / name).is_dir() and not (vault / name).is_symlink()
    ]
    while stack:
        folder = stack.pop()
        index_names = _index_names(vault, folder, config)
        notes: list[Path] = []
        child_folders: list[str] = []
        try:
            children = sorted(folder.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in children:
            if child.name.startswith(".") or child.is_symlink():
                continue
            if child.is_dir():
                stack.append(child)
                child_folders.append(child.name)
            elif (
                child.suffix.lower() == ".md"
                and child.name not in index_names
                and child.is_file()
            ):
                notes.append(child)
        if len(notes) >= threshold:
            relative = folder.relative_to(vault).as_posix()
            direct[relative] = notes
            findings.append(
                {
                    "path": relative,
                    "direct_notes": len(notes),
                    "threshold": threshold,
                    "child_folders": child_folders[:MAX_CHILD_FOLDERS],
                }
            )
    findings.sort(key=lambda item: (-item["direct_notes"], item["path"]))
    reported = findings[:limit]

    # The destination is what the routing decision is actually about, so it is
    # analyzed even when more crowded folders would have exhausted the budget.
    budget = MAX_CLUSTER_SCAN_TOTAL
    for finding in sorted(reported, key=lambda item: item["path"] != destination):
        notes = direct[finding["path"]]
        cost = min(len(notes), MAX_CLUSTER_SCAN)
        if finding["path"] != destination and cost > budget:
            continue
        budget -= cost
        finding["clusters"] = subject_clusters(
            notes, PurePosixPath(finding["path"]).name
        )
        finding["cluster_min_notes"] = CLUSTER_MIN_NOTES
    return reported


def selected_destination(note_type: str | None, folder: str | None) -> str | None:
    """Return the folder this operation will write to, as far as it is known.

    Crowded-folder paths are POSIX, so a Windows Agent passing
    `20-Learning\\AI-Agent` would match nothing and silently lose the
    crowded-destination answer — wrong, with no signal that it was wrong.
    """
    normalized = (folder or "").replace("\\", "/").strip("/")
    return normalized or TYPE_TO_FOLDER.get(note_type or "")


def required_references(
    note_type: str | None,
    custom_templates: list[str],
    crowded: list[dict[str, Any]],
    folder: str | None,
) -> list[dict[str, str]]:
    """Name every reference this operation needs, from what discovery knows.

    The conditional references were previously discovered one failure at a time:
    the agent read the create workflow, started work, hit a crowded destination
    or a customized template, and went back for another file. Discovery already
    holds every fact those conditions test, so it can answer once.
    """
    references = [
        {"file": "note-creation.md", "reason": "the new-note workflow"},
    ]
    if note_type in TYPE_REFERENCES:
        name, reason = TYPE_REFERENCES[note_type]
        references.append({"file": name, "reason": reason})
    if note_type is not None and note_type in custom_templates:
        references.append(
            {
                "file": "custom-template.md",
                "reason": f"the Vault template for {note_type} is customized",
            }
        )
    destination = selected_destination(note_type, folder)
    if destination and any(item["path"] == destination for item in crowded):
        references.append(
            {
                "file": "folder-routing.md",
                "reason": f"the selected destination {destination} is crowded",
            }
        )
    return references


def collect(
    vault: Path, note_type: str | None = None, folder: str | None = None
) -> dict[str, Any]:
    vault = vault.resolve()
    warnings: list[str] = []
    exists = vault.is_dir()
    is_obsidian = (vault / ".obsidian").is_dir()
    has_templates = (vault / "Templates").is_dir()
    valid = exists and is_obsidian and has_templates
    if not exists:
        warnings.append("vault path does not exist")
    if exists and not is_obsidian:
        warnings.append(".obsidian directory missing: not a real Obsidian vault")
    if exists and not has_templates:
        warnings.append("Templates/ directory missing")

    config = read_folder_index_config(vault)
    standard_folders: dict[str, Any] = {}
    for name in STANDARD_FOLDERS:
        directory = vault / name
        entry: dict[str, Any] = {"exists": directory.is_dir()}
        if name in NOTE_FOLDERS:
            entry["index"] = detect(vault, name) if exists else None
        else:
            entry["index"] = None
        standard_folders[name] = entry

    result = {
        "vault": str(vault),
        "valid": valid,
        "validation": {
            "exists": exists,
            "is_obsidian": is_obsidian,
            "has_templates": has_templates,
        },
        "templates": _templates(vault) if exists else [],
        "standard_folders": standard_folders,
        "folder_index_global": {
            "enabled": config.enabled,
            "graph_overwrite": config.graph_overwrite,
            "user_specified": config.user_specified,
            "root_index_file": config.root_index_file,
        },
        "custom_templates": custom_template_types(vault) if exists else [],
        "crowded_folders": (
            crowded_folders(
                vault, config, destination=selected_destination(note_type, folder)
            )
            if exists
            else []
        ),
        "warnings": warnings,
    }
    if note_type is not None:
        result["template_shape"] = template_shape(vault, note_type)
    if valid:
        result["tag_vocabulary"] = tag_vocabulary(vault)
        result["required_references"] = required_references(
            note_type,
            result["custom_templates"],
            result["crowded_folders"],
            folder,
        )
    return result


def compact(info: dict[str, Any]) -> dict[str, Any]:
    """Return discovery output without per-folder note filename arrays."""
    result = copy.deepcopy(info)
    for entry in result["standard_folders"].values():
        index = entry.get("index")
        if index is not None:
            index.pop("notes", None)
    return result


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Print a vault cold-start context summary as JSON."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--json", action="store_true", help="Emit JSON (this tool does so by default)"
    )
    p.add_argument(
        "--compact",
        action="store_true",
        help="Omit per-folder note filename arrays from discovery output",
    )
    p.add_argument(
        "--type",
        dest="note_type",
        help="Include only this conventional note type's ordered template headings",
    )
    p.add_argument(
        "--folder",
        help="Vault-relative destination, when it is more specific than the "
             "type default; makes the crowded-destination reference precise",
    )
    args = p.parse_args(argv)
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.note_type is not None and args.note_type not in TYPE_TO_TEMPLATE:
        print(json.dumps({
            "error": {
                "code": "unsupported-template-type",
                "note_type": args.note_type,
                "supported": sorted(TYPE_TO_TEMPLATE),
            }
        }, ensure_ascii=False))
        return 2
    try:
        info = collect(vault, note_type=args.note_type, folder=args.folder)
    except FolderIndexConfigError as exc:
        print(json.dumps({"error": {
            "code": exc.code,
            "message": exc.message,
        }}, ensure_ascii=False, indent=2))
        return 2
    if args.compact:
        info = compact(info)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
