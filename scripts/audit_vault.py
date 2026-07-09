#!/usr/bin/env python3
"""Audit an Obsidian vault without modifying it."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
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
REQUIRED_TYPES = {
    "daily-note",
    "daily-report",
    "weekly-report",
    "meeting-note",
    "learning-note",
    "web-clip",
    "insight-note",
    "project-note",
    "person-note",
    "archive-note",
    "folder-index",
    "moc",
}
IGNORED_PARTS = {
    ".git",
    ".obsidian",
    ".obsidian-kb-backups",
    ".venv",
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

    markdown = _markdown_files(vault)
    for path in markdown:
        relative = path.relative_to(vault)
        text = path.read_text(encoding="utf-8")
        metadata, yaml_error = _frontmatter(text)
        if yaml_error:
            _add(findings, "invalid-frontmatter", relative, yaml_error)
        _audit_metadata(findings, relative, text, metadata)
        _audit_related(findings, relative, metadata)
        _audit_web_clip(findings, relative, metadata)
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

    return sorted(findings, key=lambda item: (item.path, item.code, item.message))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit an Obsidian vault without modifying it.")
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when findings exist")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2
    findings = audit_vault(vault)
    for finding in findings:
        print(f"{finding.code}\t{finding.path}\t{finding.message}")
    print(f"{len(findings)} finding(s)")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
