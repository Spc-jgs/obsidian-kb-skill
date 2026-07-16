#!/usr/bin/env python3
"""Inspect conventional Vault templates and expose customized contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    portable_yaml_scalars,
)
from obsidian_kb_skill.scripts.note_types import (
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
)
from obsidian_kb_skill.scripts.resource_locator import template_dir
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    validate_vault_root,
)


SUPPORTED_PLACEHOLDERS = ("date", "title")
PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")
ATX_HEADING_RE = re.compile(r"^(#{2,6})[ \t]+(.+?)[ \t]*$")
FENCE_LINE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


class TemplateFrontmatterError(ValueError):
    """Malformed YAML in a conventional Vault template."""

    def __init__(
        self,
        message: str,
        *,
        source: str,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.source = source
        self.line = line
        self.column = column
        self.message = message
        super().__init__(message)


def normalize_template_text(text: str) -> str:
    """Normalize transport-only text details for stable template hashing."""
    normalized = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip("\n") + "\n"


def template_sha256(text: str) -> str:
    """Hash normalized UTF-8 template content."""
    return hashlib.sha256(normalize_template_text(text).encode("utf-8")).hexdigest()


def _split_frontmatter(text: str, *, source: str) -> tuple[dict[str, Any], str]:
    normalized = normalize_template_text(text)
    result = parse_frontmatter(normalized, source=source)
    if result.issue is not None:
        raise TemplateFrontmatterError(
            result.issue.message,
            source=result.issue.source,
            line=result.issue.line,
            column=result.issue.column,
        )
    if not result.present:
        return {}, result.normalized_text
    return portable_yaml_scalars(result.metadata or {}), result.body


def _starter_hashes(note_type: str) -> set[str]:
    asset = TYPE_TO_TEMPLATE_ASSET[note_type]
    root = template_dir()
    paths = (root / asset, root / "en" / asset)
    return {
        template_sha256(path.read_text(encoding="utf-8"))
        for path in paths
        if path.is_file()
    }


def template_path(vault: Path, note_type: str) -> Path | None:
    filename = TYPE_TO_TEMPLATE.get(note_type)
    if filename is None:
        return None
    path = vault / "Templates" / filename
    return path if path.is_file() else None


def markdown_section_headings(
    text: str, *, levels: tuple[int, ...] = (2, 3, 4, 5, 6)
) -> list[str]:
    """Return ATX section headings outside frontmatter and fenced code."""
    normalized = normalize_template_text(text)
    if normalized.startswith("---\n"):
        end = normalized.find("\n---\n", 4)
        if end != -1:
            normalized = normalized[end + 5 :]

    headings: list[str] = []
    open_fence: tuple[str, int] | None = None
    for line in normalized.splitlines():
        fence = FENCE_LINE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if open_fence is None:
                open_fence = (marker[0], len(marker))
            elif (
                marker[0] == open_fence[0]
                and len(marker) >= open_fence[1]
                and not line[fence.end() :].strip()
            ):
                open_fence = None
            continue
        if open_fence is not None:
            continue
        heading = ATX_HEADING_RE.fullmatch(line)
        if heading and len(heading.group(1)) in levels:
            headings.append(heading.group(2).strip())
    return headings


def template_shape(vault: Path, note_type: str) -> dict[str, Any] | None:
    """Return only one conventional template's ordered level-two headings."""
    path = template_path(vault, note_type)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    return {
        "type": note_type,
        "path": path.relative_to(vault).as_posix(),
        "headings": markdown_section_headings(text, levels=(2,)),
    }


def inspect_template(vault: Path, note_type: str) -> dict[str, Any] | None:
    """Return one conventional template contract, or None when it is missing."""
    path = template_path(vault, note_type)
    if path is None:
        return None
    raw = path.read_text(encoding="utf-8")
    digest = template_sha256(raw)
    metadata, body = _split_frontmatter(
        raw, source=f"template {path.as_posix()}"
    )
    placeholders = {match.strip() for match in PLACEHOLDER_RE.findall(raw)}
    unknown = sorted(placeholders.difference(SUPPORTED_PLACEHOLDERS))
    return {
        "type": note_type,
        "path": path.relative_to(vault).as_posix(),
        "customized": digest not in _starter_hashes(note_type),
        "sha256": digest,
        "frontmatter": metadata,
        "body": body,
        "supported_placeholders": list(SUPPORTED_PLACEHOLDERS),
        "unknown_placeholders": unknown,
    }


def custom_template_types(vault: Path) -> list[str]:
    """Return conventional note types whose Vault templates are customized."""
    result: list[str] = []
    for note_type in TYPE_TO_TEMPLATE:
        path = template_path(vault, note_type)
        if path is None:
            continue
        digest = template_sha256(path.read_text(encoding="utf-8"))
        if digest not in _starter_hashes(note_type):
            result.append(note_type)
    return result


def _error(code: str, **details: Any) -> dict[str, Any]:
    return {"error": {"code": code, **details}}


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Return one conventional Vault template contract as JSON."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--type", required=True, dest="note_type", help="Note type slug")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(json.dumps(_error("invalid-vault", message=str(exc)), ensure_ascii=False))
        return 2
    if args.note_type not in TYPE_TO_TEMPLATE:
        print(json.dumps(_error(
            "unsupported-template-type",
            note_type=args.note_type,
            supported=sorted(TYPE_TO_TEMPLATE),
        ), ensure_ascii=False))
        return 2
    try:
        contract = inspect_template(vault, args.note_type)
    except TemplateFrontmatterError as exc:
        print(json.dumps(_error(
            "invalid-template-frontmatter",
            source=exc.source,
            line=exc.line,
            column=exc.column,
            message=exc.message,
        ), ensure_ascii=False))
        return 2
    if contract is None:
        print(json.dumps(_error(
            "missing-template", note_type=args.note_type
        ), ensure_ascii=False))
        return 2
    if contract["unknown_placeholders"]:
        print(json.dumps(_error(
            "unknown-template-placeholder",
            placeholders=contract["unknown_placeholders"],
        ), ensure_ascii=False))
        return 2
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
