#!/usr/bin/env python3
"""Audit an Obsidian vault without modifying it."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import difflib
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class FolderIndexConfig:
    enabled: bool = False
    graph_overwrite: bool = False
    root_index_file: str = "INDEX.md"
    user_specified: bool = False
    index_filename: str = "INDEX"
    exclude_folders: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


EXEMPT_NAMES = {"README.md", "AGENTS.md", "CLAUDE.md"}
INDEX_TYPES = {"folder-index", "moc"}
# Findings that describe vault-wide consistency (not a defect of any single note).
# Excluded from audit_note() so a post-write self-check only reports issues in the
# note that was just written.
VAULT_WIDE_CODES = frozenset(
    {
        "orphan-note",
        "duplicate-folder-index",
        "missing-folder-index",
        "misnamed-folder-index",
        "broken-folder-graph-chain",
        "graph-incompatible-index-config",
        "near-duplicate-tags",
        "duplicate-title",
        "similar-title",
    }
)
REQUIRED_TYPES = {
    "daily-note",
    "daily-report",
    "weekly-report",
    "meeting-note",
    "learning-note",
    "web-clip",
    "insight-note",
    "conversation-digest",
    "project-note",
    "person-note",
    "archive-note",
    "task-memory",
    "folder-index",
    "moc",
}
# Folders whose contents are never real notes and must be skipped. Hidden
# (dotfile) directories are skipped automatically by _is_ignored, so this set
# only needs explicit entries for non-hidden tool/metadata folders.
IGNORED_PARTS = {
    ".git",
    ".obsidian",
    ".obsidian-kb-backups",
    ".venv",
    ".workbuddy",  # agent working memory / metadata
}
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"```[\s\S]*?```")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FOLDER_INDEX_CONTENT_RE = re.compile(
    r"^\s*```folder-index-content(?:\s+[^\n]*)?\s*$", re.MULTILINE
)

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")


def _is_ignored(relative: Path) -> bool:
    if any(part in IGNORED_PARTS for part in relative.parts):
        return True
    # Hidden directories follow the dotfile convention and hold tool/agent
    # metadata (e.g. .workbuddy, .claude, .cursor, .codebuddy, .uploads) rather
    # than notes. Skipping them avoids false positives on agent working memory
    # and similar metadata folders that may coexist with a vault. This covers a
    # hidden dir at ANY depth, including a top-level hidden folder such as
    # ".uploads" or ".claude" sitting directly under the vault root.
    if any(part.startswith(".") for part in relative.parts):
        return True
    return relative.parts[:2] == ("docs", "superpowers")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _folder_index_config(vault: Path) -> FolderIndexConfig:
    obsidian = vault / ".obsidian"
    enabled = _read_json(obsidian / "community-plugins.json", [])
    if not isinstance(enabled, list) or "obsidian-folder-index" not in enabled:
        return FolderIndexConfig()
    settings = _read_json(
        obsidian / "plugins" / "obsidian-folder-index" / "data.json", {}
    )
    if not isinstance(settings, dict):
        settings = {}
    return FolderIndexConfig(
        enabled=True,
        graph_overwrite=bool(settings.get("graphOverwrite", False)),
        root_index_file=str(settings.get("rootIndexFile", "INDEX.md")),
        user_specified=bool(settings.get("indexFileUserSpecified", False)),
        index_filename=str(settings.get("indexFilename", "INDEX")),
        exclude_folders=tuple(
            str(item).strip("/")
            for item in settings.get("excludeFolders", [])
            if str(item)
        ),
        exclude_patterns=tuple(
            str(item) for item in settings.get("excludePatterns", []) if str(item)
        ),
    )


def _is_folder_index_excluded(relative: Path, config: FolderIndexConfig) -> bool:
    if _is_ignored(relative):
        return True
    value = relative.as_posix()
    for excluded in config.exclude_folders:
        if value == excluded or value.startswith(f"{excluded}/"):
            return True
    return any(
        fnmatch.fnmatch(value, pattern) or fnmatch.fnmatch(relative.name, pattern)
        for pattern in config.exclude_patterns
    )


def expected_folder_index(folder: Path, vault: Path, config: FolderIndexConfig) -> Path:
    if folder == vault:
        return vault / config.root_index_file
    if config.user_specified:
        return folder / f"{config.index_filename}.md"
    return folder / f"{folder.name}.md"


def _markdown_files(vault: Path) -> list[Path]:
    return sorted(
        path
        for path in vault.rglob("*.md")
        if not _is_ignored(path.relative_to(vault))
    )


def _all_linkable_files(vault: Path) -> list[Path]:
    return sorted(
        path
        for path in vault.rglob("*")
        if path.is_file() and not _is_ignored(path.relative_to(vault))
    )


def _frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, "frontmatter opening fence has no closing fence"
    try:
        parsed = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, str(exc).splitlines()[0]
    if parsed is None:
        return {}, None
    if not isinstance(parsed, dict):
        return None, "frontmatter must be a YAML mapping"
    return parsed, None


def _add(
    findings: list[Finding], code: str, relative: Path, message: str
) -> None:
    findings.append(Finding(code, relative.as_posix(), message))


def _audit_metadata(
    findings: list[Finding], relative: Path, text: str, metadata: dict[str, Any] | None
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if metadata is None:
        _add(findings, "missing-frontmatter", relative, "YAML frontmatter is missing or invalid")
        metadata = {}

    note_type = metadata.get("type")
    if not note_type:
        _add(findings, "missing-type", relative, "required property 'type' is missing")
    elif note_type not in REQUIRED_TYPES:
        _add(findings, "invalid-type", relative, f"unsupported note type: {note_type}")

    if note_type not in INDEX_TYPES and not metadata.get("date"):
        _add(findings, "missing-date", relative, "required property 'date' is missing")

    tags = metadata.get("tags")
    if not tags or (isinstance(tags, list) and not any(str(tag).strip() for tag in tags)):
        _add(findings, "missing-tags", relative, "required property 'tags' is missing or empty")
        return
    tag_values = tags if isinstance(tags, list) else [tags]
    if len(tag_values) > 5:
        _add(findings, "too-many-tags", relative, "notes may have at most five tags")
    invalid = [str(tag) for tag in tag_values if not TAG_RE.fullmatch(str(tag))]
    if invalid:
        _add(findings, "invalid-tag", relative, f"tags must use lowercase kebab-case: {invalid}")


def _audit_folder_index_content(
    findings: list[Finding],
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if not metadata or metadata.get("type") != "folder-index":
        return
    count = len(FOLDER_INDEX_CONTENT_RE.findall(text))
    if count == 0:
        _add(
            findings,
            "missing-folder-index-content",
            relative,
            "folder-index note must contain one folder-index-content block",
        )
    elif count > 1:
        _add(
            findings,
            "duplicate-folder-index-content",
            relative,
            "folder-index note must contain exactly one folder-index-content block",
        )


def _audit_template_placeholders(
    findings: list[Finding],
    relative: Path,
    text: str,
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if relative.parts and relative.parts[0] == "Templates":
        return
    if PLACEHOLDER_RE.search(text):
        _add(
            findings,
            "unresolved-template-placeholder",
            relative,
            "note contains an unresolved template placeholder such as {{date}}",
        )


def _audit_related(
    findings: list[Finding],
    relative: Path,
    metadata: dict[str, Any] | None,
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if not metadata:
        return
    related = metadata.get("related")
    if related is None:
        return
    if not isinstance(related, list):
        _add(
            findings,
            "invalid-related",
            relative,
            "'related' must be a list of wikilink strings",
        )
        return
    seen: dict[str, bool] = {}
    for entry in related:
        if not isinstance(entry, str) or not entry.strip():
            _add(
                findings,
                "invalid-related-entry",
                relative,
                "related entry must be a non-empty wikilink string",
            )
            continue
        stripped = entry.strip()
        if not (stripped.startswith("[[") and stripped.endswith("]]")):
            _add(
                findings,
                "invalid-related-entry",
                relative,
                f"related entry is not a wikilink: {entry}",
            )
            continue
        target = (
            stripped[2:-2].split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
        )
        if not target:
            _add(
                findings,
                "invalid-related-entry",
                relative,
                "related entry has an empty wikilink target",
            )
            continue
        key = target.lower()
        if key in seen:
            _add(
                findings,
                "duplicate-related-entry",
                relative,
                f"duplicate related entry: {entry}",
            )
        else:
            seen[key] = True


def _audit_web_clip(
    findings: list[Finding],
    relative: Path,
    metadata: dict[str, Any] | None,
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if relative.parts and relative.parts[0] == "Templates":
        return
    if not metadata:
        return
    if metadata.get("type") != "web-clip":
        return
    for field in ("source", "author", "published"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            _add(
                findings,
                f"web-clip-missing-{field}",
                relative,
                f"web-clip note must set a non-empty '{field}' field",
            )


def _audit_empty_template(
    findings: list[Finding],
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if relative.parts and relative.parts[0] == "Templates":
        return
    if not metadata:
        return
    if metadata.get("type") in INDEX_TYPES:
        return
    body = text
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5:]
    has_heading = False
    content_chars = 0
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            has_heading = True
            continue
        content_chars += sum(1 for ch in stripped if not ch.isspace())
    if has_heading and content_chars == 0:
        _add(
            findings,
            "empty-template-note",
            relative,
            "note has only headings and no body content; looks like an unfilled template",
        )


def _candidate_paths(source: Path, target: str, vault: Path) -> Iterable[Path]:
    raw = Path(target)
    candidates = [vault / raw, source.parent / raw]
    if raw.suffix == "":
        candidates.extend((vault / f"{target}.md", source.parent / f"{target}.md"))
    return candidates


def _clean_link_target(raw: str) -> str:
    target = raw.split("|", 1)[0]
    target = target.split("#", 1)[0]
    target = target.split("^", 1)[0]
    return target.strip()


def _without_code_examples(text: str) -> str:
    text = FENCED_CODE_RE.sub("", text)
    return INLINE_CODE_RE.sub("", text)


def _audit_links(
    findings: list[Finding],
    vault: Path,
    source: Path,
    relative: Path,
    text: str,
    by_name: dict[str, list[Path]],
    by_stem: dict[str, list[Path]],
) -> None:
    for match in WIKILINK_RE.finditer(text):
        target = _clean_link_target(match.group(1))
        if not target:
            continue
        if "/" in target:
            if any(candidate.is_file() for candidate in _candidate_paths(source, target, vault)):
                continue
            _add(findings, "broken-wikilink", relative, f"unresolved wikilink: {target}")
            continue

        key_name = Path(target).name
        matches = by_name.get(key_name, [])
        if not matches and Path(key_name).suffix == "":
            matches = by_stem.get(key_name, [])
        if len(matches) == 1:
            continue
        if len(matches) > 1:
            _add(findings, "ambiguous-wikilink", relative, f"ambiguous wikilink: {target}")
        else:
            _add(findings, "broken-wikilink", relative, f"unresolved wikilink: {target}")


def _resolve_target(
    target: str,
    source: Path,
    vault: Path,
    by_name: dict[str, list[Path]],
    by_stem: dict[str, list[Path]],
) -> list[Path]:
    if "/" in target:
        return [candidate for candidate in _candidate_paths(source, target, vault) if candidate.is_file()]
    key_name = Path(target).name
    matches = by_name.get(key_name, [])
    if not matches and Path(key_name).suffix == "":
        matches = by_stem.get(key_name, [])
    return [candidate for candidate in matches if candidate.is_file()]


def _collect_references(
    source: Path,
    text: str,
    metadata: dict[str, Any] | None,
    vault: Path,
    by_name: dict[str, list[Path]],
    by_stem: dict[str, list[Path]],
) -> set[Path]:
    """Return the set of note paths that ``source`` links to (body + related)."""
    referenced: set[Path] = set()
    bodies = [_without_code_examples(text)]
    if isinstance(metadata, dict):
        related = metadata.get("related")
        if isinstance(related, list):
            for entry in related:
                if isinstance(entry, str):
                    stripped = entry.strip()
                    if stripped.startswith("[[") and stripped.endswith("]]"):
                        bodies.append(stripped[2:-2])
    for body in bodies:
        for match in WIKILINK_RE.finditer(body):
            target = _clean_link_target(match.group(1))
            if not target:
                continue
            for candidate in _resolve_target(target, source, vault, by_name, by_stem):
                if candidate != source:
                    referenced.add(candidate)
    return referenced


def _audit_orphans(
    findings: list[Finding],
    vault: Path,
    referenced: set[Path],
    index_notes: set[Path],
    candidate_notes: list[Path],
) -> None:
    indexed: set[Path] = set()
    for index_note in index_notes:
        folder = index_note.parent
        for child in folder.glob("*.md"):
            if child in index_notes:
                continue
            relative = child.relative_to(vault)
            if relative.parts and relative.parts[0] == "Templates":
                continue
            if relative.name in EXEMPT_NAMES or relative.name == "INDEX.md":
                continue
            indexed.add(child)
    for candidate in candidate_notes:
        if candidate not in referenced and candidate not in indexed:
            _add(
                findings,
                "orphan-note",
                candidate.relative_to(vault),
                "note has no inbound links and is not referenced by any index; "
                "consider linking it or filing it under an indexed folder",
            )


def _declares_folder_index(path: Path) -> bool:
    metadata, error = _frontmatter(path.read_text(encoding="utf-8"))
    return error is None and metadata is not None and metadata.get("type") == "folder-index"


def _audit_folder_index_graph(
    findings: list[Finding], vault: Path, config: FolderIndexConfig
) -> None:
    if not config.enabled:
        return

    folders = [
        path
        for path in sorted(vault.rglob("*"))
        if path.is_dir()
        and not _is_folder_index_excluded(path.relative_to(vault), config)
    ]
    root_index = expected_folder_index(vault, vault, config)
    if not root_index.is_file():
        _add(
            findings,
            "missing-folder-index",
            Path("."),
            f"configured root index is missing: {config.root_index_file}",
        )

    if config.graph_overwrite and config.user_specified and folders:
        _add(
            findings,
            "graph-incompatible-index-config",
            Path(".obsidian/plugins/obsidian-folder-index/data.json"),
            "Folder Index 1.0.30 cannot connect nested folders when one custom index filename is used",
        )

    for folder in folders:
        relative_folder = folder.relative_to(vault)
        expected = expected_folder_index(folder, vault, config)
        declared = [
            path
            for path in sorted(folder.glob("*.md"))
            if _declares_folder_index(path)
        ]
        if not expected.is_file():
            _add(
                findings,
                "missing-folder-index",
                relative_folder,
                f"expected folder index is missing: {expected.name}",
            )
        for index in declared:
            if index != expected:
                _add(
                    findings,
                    "misnamed-folder-index",
                    index.relative_to(vault),
                    f"configured folder index name is {expected.name}",
                )

        graph_target = folder / f"{folder.name}.md"
        if config.graph_overwrite and expected.is_file() and expected != graph_target:
            _add(
                findings,
                "broken-folder-graph-chain",
                expected.relative_to(vault),
                f"parent graph traversal looks for {graph_target.name}",
            )


def _normalize_tag_key(tag: str) -> str:
    key = tag.lower().replace("_", "-")
    if len(key) > 1 and key.endswith("s"):
        key = key[:-1]
    return key


def _note_title(relative: Path, text: str) -> str:
    """Return the human title of a note: first H1 heading, else filename stem."""
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
    stem = relative.stem
    return re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stem).strip()


def audit_vault(vault: Path) -> list[Finding]:
    """Return deterministic findings sorted by path, code, and message."""
    vault = vault.resolve()
    findings: list[Finding] = []
    folder_index_config = _folder_index_config(vault)
    linkable = _all_linkable_files(vault)
    by_name: dict[str, list[Path]] = defaultdict(list)
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in linkable:
        by_name[path.name].append(path)
        by_stem[path.stem].append(path)

    tag_index: dict[str, set[str]] = {}
    title_list: list[tuple[str, str, Path]] = []
    referenced: set[Path] = set()
    index_notes: set[Path] = set()
    candidate_notes: list[Path] = []
    markdown = _markdown_files(vault)
    for path in markdown:
        relative = path.relative_to(vault)
        text = path.read_text(encoding="utf-8")
        metadata, yaml_error = _frontmatter(text)
        if yaml_error:
            _add(findings, "invalid-frontmatter", relative, yaml_error)
        _audit_metadata(findings, relative, text, metadata)
        if metadata and relative.name not in EXEMPT_NAMES:
            raw_tags = metadata.get("tags")
            tag_values = (
                raw_tags
                if isinstance(raw_tags, list)
                else ([raw_tags] if isinstance(raw_tags, str) else [])
            )
            for tag in tag_values:
                if isinstance(tag, str) and tag.strip():
                    tag_index.setdefault(_normalize_tag_key(tag), set()).add(tag.strip())
            if (
                relative.parts
                and relative.parts[0] != "Templates"
                and metadata.get("type") not in INDEX_TYPES
                and relative.name != "INDEX.md"
            ):
                title = _note_title(relative, text)
                if title:
                    title_list.append((title.strip().lower(), title.strip(), relative))
        _audit_related(findings, relative, metadata)
        _audit_web_clip(findings, relative, metadata)
        _audit_empty_template(findings, relative, text, metadata)
        _audit_folder_index_content(findings, relative, text, metadata)
        if len(FENCE_RE.findall(text)) % 2:
            _add(findings, "unclosed-fence", relative, "odd number of fenced code block markers")
        _audit_template_placeholders(findings, relative, text)
        if relative.name not in EXEMPT_NAMES:
            _audit_links(
                findings,
                vault,
                path,
                relative,
                _without_code_examples(text),
                by_name,
                by_stem,
            )
        referenced |= _collect_references(path, text, metadata, vault, by_name, by_stem)
        if metadata and metadata.get("type") in INDEX_TYPES:
            index_notes.add(path)
        if (
            metadata
            and relative.name not in EXEMPT_NAMES
            and (not relative.parts or relative.parts[0] != "Templates")
            and relative.name != "INDEX.md"
            and metadata.get("type") not in INDEX_TYPES
            and metadata.get("type") != "daily-note"
        ):
            candidate_notes.append(path)

    for folder in sorted(path for path in vault.rglob("*") if path.is_dir()):
        relative_folder = folder.relative_to(vault)
        if _is_ignored(relative_folder) or folder == vault:
            continue
        conventional = folder / "INDEX.md"
        named = folder / f"{folder.name}.md"
        if conventional.is_file() and named.is_file():
            if _declares_folder_index(conventional) and _declares_folder_index(named):
                _add(
                    findings,
                    "duplicate-folder-index",
                    relative_folder,
                    f"both {conventional.name} and {named.name} own the folder index",
                )

    _audit_folder_index_graph(findings, vault, folder_index_config)

    for key, originals in tag_index.items():
        if len(originals) >= 2:
            _add(
                findings,
                "near-duplicate-tags",
                Path("."),
                f"near-duplicate tags: {', '.join(sorted(originals))} (consider merging)",
            )

    _audit_titles(findings, title_list)
    _audit_orphans(findings, vault, referenced, index_notes, candidate_notes)

    return sorted(findings, key=lambda item: (item.path, item.code, item.message))


def audit_note(vault: Path, note: Path) -> list[Finding]:
    """Audit a single note within its vault; returns *per-note* findings only.

    Reuses the full audit_vault pass (single source of truth for every rule) and
    filters to the requested note's relative path, dropping vault-wide consistency
    findings (orphans, duplicate titles, missing folder indexes, graph chains,
    near-duplicate tags) that are not defects of the note itself. This matches the
    scope of a post-write self-check (Step 9): frontmatter validity, broken
    wikilinks, unresolved placeholders, required web-clip fields, etc.
    """
    vault = vault.resolve()
    note = note.resolve()
    all_findings = audit_vault(vault)
    rel = note.relative_to(vault).as_posix()
    return [
        f
        for f in all_findings
        if f.path == rel and f.code not in VAULT_WIDE_CODES
    ]


def _audit_titles(
    findings: list[Finding],
    title_list: list[tuple[str, str, Path]],
) -> None:
    if not title_list:
        return
    seen: dict[str, list[Path]] = {}
    display: dict[str, str] = {}
    for norm, shown, relative in title_list:
        seen.setdefault(norm, []).append(relative)
        display[norm] = shown
    for norm, paths in seen.items():
        if len(paths) >= 2:
            _add(
                findings,
                "duplicate-title",
                Path("."),
                f"duplicate title '{display[norm]}' across "
                f"{len(paths)} notes: "
                f"{', '.join(p.as_posix() for p in paths)}",
            )
    for i in range(len(title_list)):
        norm_i, shown_i, rel_i = title_list[i]
        for j in range(i + 1, len(title_list)):
            norm_j, shown_j, rel_j = title_list[j]
            if norm_i == norm_j:
                continue
            ratio = difflib.SequenceMatcher(None, norm_i, norm_j).ratio()
            if ratio >= 0.85:
                _add(
                    findings,
                    "similar-title",
                    Path("."),
                    f"similar titles ({ratio:.2f}): "
                    f"'{shown_i}' ({rel_i.as_posix()}) ~ "
                    f"'{shown_j}' ({rel_j.as_posix()})",
                )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit an Obsidian vault without modifying it.")
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when findings exist")
    parser.add_argument(
        "--json", action="store_true", help="Emit findings as JSON instead of tab-separated text"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2
    findings = audit_vault(vault)
    if args.json:
        out = [
            {"code": f.code, "path": f.path, "message": f.message} for f in findings
        ]
        print(json.dumps({"count": len(findings), "findings": out},
                         ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(f"{finding.code}\t{finding.path}\t{finding.message}")
        print(f"{len(findings)} finding(s)")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
