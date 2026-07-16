#!/usr/bin/env python3
"""Inspect conventional Vault templates and expose customized contracts."""
from __future__ import annotations

import datetime
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from obsidian_kb_skill.scripts.note_types import (
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
)
from obsidian_kb_skill.scripts.resource_locator import template_dir


SUPPORTED_PLACEHOLDERS = ("date", "title")
PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")


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


def _portable_scalars(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _portable_scalars(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable_scalars(item) for item in value]
    return value


def _split_frontmatter(text: str, *, source: str) -> tuple[dict[str, Any], str]:
    normalized = normalize_template_text(text)
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        raise TemplateFrontmatterError(
            "frontmatter block is not closed", source=source, line=1, column=1
        )
    raw = normalized[4:end]
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise TemplateFrontmatterError(
            getattr(exc, "problem", None) or str(exc).splitlines()[0],
            source=source,
            line=mark.line + 2 if mark is not None else None,
            column=mark.column + 1 if mark is not None else None,
        ) from exc
    if not isinstance(parsed, dict):
        raise TemplateFrontmatterError(
            "frontmatter must be a YAML mapping", source=source, line=2, column=1
        )
    return _portable_scalars(parsed), normalized[end + 5 :]


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
