#!/usr/bin/env python3
"""Show the notes a Vault has already connected to one note (#121).

Search answers "which notes mention these words". This answers the other
question a reader has after finding a good note: *what does this Vault say is
connected to it* — and it answers it only from edges someone wrote down.

Every edge here is a declaration: a wikilink in the body, a `related` entry in
the frontmatter, or the same seen from the other end as a backlink. Nothing is
scored, nothing is suggested, and an ambiguous link is reported rather than
resolved. Discovering *new* candidates is #75's job and calling an edge evidence
is #85's; doing either here would let an inference read as something the user
stated.

One hop. Two hops is a different question with a different bound, and #121
defers it on purpose.

Read-only: nothing here writes, moves, or repairs a note.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.link_graph import (
    WIKILINK_RE,
    blank_code_examples,
    build_link_index,
    clean_link_target,
    candidate_paths,
)
from obsidian_kb_skill.scripts.note_catalog import (
    EXEMPT_NAMES,
    INDEX_TYPES,
    SOURCE_ARCHIVE_FOLDER,
    SOURCE_ARCHIVE_TYPE,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)

SCHEMA_VERSION = "1.0"
COMMAND = "explore-neighborhood"

ORIGIN_BODY = "body"
ORIGIN_RELATED = "related"

DIRECTION_OUT = "out"
DIRECTION_IN = "in"
DIRECTION_BOTH = "both"

STATE_RESOLVED = "resolved"
STATE_AMBIGUOUS = "ambiguous"
STATE_UNRESOLVED = "unresolved"

# A neighbourhood is knowledge the reader might want next. A folder index links
# every note in its folder, so following it returns the folder rather than a
# neighbourhood; #133 already settled that an index is a listing and not
# material. A source archive is the captured evidence behind one note, reached
# from the note that cites it — #85's territory, and deliberately not conflated
# with it here. Both are still reachable with `--include-structural`, because
# "this note only links to its folder index" is itself worth being able to see.
EXCLUDED_INDEX_NOTE = "index-note"
EXCLUDED_SOURCE_ARCHIVE = "source-archive"

DEFAULT_MAX_NODES = 20


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": False,
        "read_only": True,
        "error": {"code": code, "message": message},
    }


def _metadata(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parsed = parse_frontmatter(text, source=path.as_posix())
    if parsed.issue is not None:
        return None
    return parsed.metadata or {}


def _linkable(vault: Path) -> list[Path]:
    return [
        path
        for path in sorted(vault.rglob("*.md"))
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(vault).parts)
        and path.name not in EXEMPT_NAMES
    ]


def _related_names(metadata: dict[str, Any] | None) -> list[str]:
    """`related` entries, whether written as `[[Name]]` or as a bare name."""
    raw = (metadata or {}).get("related")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        stripped = entry.strip()
        if stripped.startswith("[[") and stripped.endswith("]]"):
            stripped = stripped[2:-2]
        cleaned = clean_link_target(stripped)
        if cleaned:
            names.append(cleaned)
    return names


def _outgoing_links(text: str) -> list[tuple[str, int]]:
    """Body wikilink targets with the 1-based line each was written on.

    Code is blanked rather than removed so the numbering survives: a wikilink
    inside a fence is syntax being quoted, and the Vault's own notes quote it
    constantly, but the reader still needs the real line of the links that are
    real.
    """
    found: list[tuple[str, int]] = []
    for index, line in enumerate(blank_code_examples(text).splitlines(), start=1):
        for match in WIKILINK_RE.finditer(line):
            target = clean_link_target(match.group(1))
            if target:
                found.append((target, index))
    return found


def _classify(path: Path, vault: Path, metadata: dict[str, Any] | None) -> str | None:
    """Why this neighbour is structural rather than knowledge, or `None`."""
    relative = path.relative_to(vault)
    note_type = (metadata or {}).get("type")
    if note_type in INDEX_TYPES:
        return EXCLUDED_INDEX_NOTE
    if relative.parts[:1] == (SOURCE_ARCHIVE_FOLDER,) or note_type == SOURCE_ARCHIVE_TYPE:
        return EXCLUDED_SOURCE_ARCHIVE
    return None


def _resolve(
    target: str, source: Path, vault: Path, index
) -> tuple[list[Path], str]:
    if "/" in target:
        matches = [
            candidate
            for candidate in candidate_paths(source, target, vault)
            if candidate.is_file()
        ]
    else:
        matches = [
            candidate for candidate in index.matches(target) if candidate.is_file()
        ]
    unique = sorted({candidate.resolve() for candidate in matches})
    if not unique:
        return [], STATE_UNRESOLVED
    if len(unique) > 1:
        return unique, STATE_AMBIGUOUS
    return unique, STATE_RESOLVED


def build(
    vault: Path,
    *,
    note: Path,
    direction: str = DIRECTION_BOTH,
    max_nodes: int = DEFAULT_MAX_NODES,
    include_structural: bool = False,
) -> dict[str, Any]:
    """Assemble the one-hop neighbourhood of one note."""
    vault = vault.resolve()
    seed = (vault / note).resolve()
    if not seed.is_file():
        return _error("missing-note", f"no such note: {note.as_posix()}")

    notes = _linkable(vault)
    index = build_link_index(notes)
    metadata_cache: dict[Path, dict[str, Any] | None] = {}

    def metadata_of(path: Path) -> dict[str, Any] | None:
        if path not in metadata_cache:
            metadata_cache[path] = _metadata(path)
        return metadata_cache[path]

    edges: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}

    def note_excluded(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    def _entry(
        source: Path, target: Path | None, name: str, origin: str,
        edge_direction: str, state: str, line: int | None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "origin": origin,
            "direction": edge_direction,
            "state": state,
            "line": line,
            "source": source.relative_to(vault).as_posix(),
            "target": target.relative_to(vault).as_posix() if target else None,
        }

    def add_outgoing(name: str, origin: str, line: int | None) -> None:
        """One link the seed note wrote, resolved or reported as unresolvable."""
        matches, state = _resolve(name, seed, vault, index)
        if state != STATE_RESOLVED:
            entry = _entry(seed, None, name, origin, DIRECTION_OUT, state, line)
            if state == STATE_AMBIGUOUS:
                entry["candidates"] = [
                    match.relative_to(vault).as_posix() for match in matches
                ]
            edges.append(entry)
            return
        neighbour = matches[0]
        if neighbour == seed:
            # A note linking to itself is not a neighbour of itself.
            return
        reason = _classify(neighbour, vault, metadata_of(neighbour))
        if reason is not None and not include_structural:
            note_excluded(reason)
            return
        entry = _entry(seed, neighbour, name, origin, DIRECTION_OUT, state, line)
        entry["neighbour"] = entry["target"]
        edges.append(entry)

    def add_inbound(
        source: Path, name: str, origin: str, line: int | None
    ) -> None:
        """One link some other note wrote that lands on the seed.

        The neighbour is the *source* here, which is why this is not the
        outgoing case with the arrow flipped: an inbound edge always resolves to
        the seed, so re-deriving the neighbour from the resolution would find
        the seed and drop every backlink as a self-link.
        """
        reason = _classify(source, vault, metadata_of(source))
        if reason is not None and not include_structural:
            note_excluded(reason)
            return
        entry = _entry(
            source, seed, name, origin, DIRECTION_IN, STATE_RESOLVED, line
        )
        entry["neighbour"] = entry["source"]
        edges.append(entry)

    seed_text = seed.read_text(encoding="utf-8")
    seed_metadata = metadata_of(seed)

    if direction in (DIRECTION_OUT, DIRECTION_BOTH):
        for name, line in _outgoing_links(seed_text):
            add_outgoing(name, ORIGIN_BODY, line)
        for name in _related_names(seed_metadata):
            add_outgoing(name, ORIGIN_RELATED, None)

    if direction in (DIRECTION_IN, DIRECTION_BOTH):
        for path in notes:
            resolved_path = path.resolve()
            if resolved_path == seed:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for name, line in _outgoing_links(text):
                matches, state = _resolve(name, path, vault, index)
                if state == STATE_RESOLVED and matches[0] == seed:
                    add_inbound(path, name, ORIGIN_BODY, line)
            for name in _related_names(metadata_of(path)):
                matches, state = _resolve(name, path, vault, index)
                if state == STATE_RESOLVED and matches[0] == seed:
                    add_inbound(path, name, ORIGIN_RELATED, None)

    # Stable and explainable: a resolved neighbour before an unresolved name,
    # then by path so two runs on an unchanged Vault agree exactly.
    edges.sort(
        key=lambda edge: (
            edge.get("neighbour") is None,
            edge.get("neighbour") or edge["name"],
            edge["direction"],
            edge["origin"],
            edge["line"] if edge["line"] is not None else -1,
        )
    )

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in edges:
        neighbour = edge.get("neighbour")
        if neighbour is None or neighbour in seen:
            continue
        seen.add(neighbour)
        path = vault / neighbour
        meta = metadata_of(path) or {}
        nodes.append(
            {
                "path": neighbour,
                "type": meta.get("type"),
                "date": str(meta["date"]) if meta.get("date") is not None else None,
                "directions": sorted(
                    {
                        other["direction"]
                        for other in edges
                        if other.get("neighbour") == neighbour
                    }
                ),
                "origins": sorted(
                    {
                        other["origin"]
                        for other in edges
                        if other.get("neighbour") == neighbour
                    }
                ),
            }
        )

    available = len(nodes)
    kept = nodes[:max_nodes]
    kept_paths = {node["path"] for node in kept}
    bounded_edges = [
        edge
        for edge in edges
        if edge.get("neighbour") is None or edge["neighbour"] in kept_paths
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": True,
        "read_only": True,
        "note": seed.relative_to(vault).as_posix(),
        "direction": direction,
        "nodes": kept,
        "edges": bounded_edges,
        "excluded": excluded,
        "truncated": available > len(kept),
        "summary": {
            "nodes_available": available,
            "edges": len(bounded_edges),
            "scanned": len(notes),
        },
    }


def _text_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"{payload['error']['code']}: {payload['error']['message']}"
    lines = [f"{payload['note']} — {len(payload['nodes'])} neighbours"]
    for node in payload["nodes"]:
        directions = "/".join(node["directions"])
        origins = ",".join(node["origins"])
        lines.append(f"  [{directions}] {node['path']}  ({origins})")
    unresolved = [
        edge for edge in payload["edges"] if edge["state"] != STATE_RESOLVED
    ]
    for edge in unresolved:
        lines.append(f"  ! {edge['state']}: {edge['name']}")
    if payload["excluded"]:
        detail = ", ".join(
            f"{count} {reason}" for reason, count in sorted(payload["excluded"].items())
        )
        lines.append(f"  excluded (structural): {detail}")
    if payload["truncated"]:
        lines.append(
            f"  truncated: {payload['summary']['nodes_available']} neighbours exist"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Show the notes a Vault has already connected to one note."
    )
    parser.add_argument("vault")
    parser.add_argument("--note", required=True)
    parser.add_argument(
        "--direction",
        choices=(DIRECTION_OUT, DIRECTION_IN, DIRECTION_BOTH),
        default=DIRECTION_BOTH,
    )
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument(
        "--include-structural",
        action="store_true",
        help="also follow folder indexes and source archives",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.max_nodes < 1:
        parser.error("--max-nodes must be at least 1")

    try:
        root = validate_vault_root(Path(args.vault))
        resolve_target_within_vault(root, Path(args.note), label="note")
    except (InvalidVaultRootError, VaultPathError) as error:
        return report_cli_violation(error, command=COMMAND, as_json=args.json)

    payload = build(
        root,
        note=Path(args.note),
        direction=args.direction,
        max_nodes=args.max_nodes,
        include_structural=args.include_structural,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_text_report(payload))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
