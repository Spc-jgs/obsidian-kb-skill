#!/usr/bin/env python3
"""Audit an Obsidian vault without modifying it."""
from __future__ import annotations

import argparse
import json
import re
import difflib
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.conversation_digest_contract import (
    CONVERSATION_DIGEST_CONTRACT_VERSION,
    CONVERSATION_DIGEST_HEADING_VARIANTS,
    CONVERSATION_DIGEST_RESUME_FIELD_VARIANTS,
    conversation_digest_locale,
    formatted_conversation_digest_variants,
)
from obsidian_kb_skill.scripts.deep_capture_contract import (
    DEEP_CAPTURE_CONTRACT_VERSION,
    formatted_deep_capture_variants,
    matches_deep_capture_contract,
)
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.capture_receipt import CAPTURE_DEPTHS
from obsidian_kb_skill.scripts.folder_index_policy import (
    FolderIndexConfig,
    FolderIndexConfigError,
    expected_folder_index,
    is_folder_index_excluded,
    read_folder_index_config,
)
from obsidian_kb_skill.scripts.note_catalog import VALID_NOTE_TYPES
from obsidian_kb_skill.scripts.note_types import TYPE_TO_TEMPLATE
from obsidian_kb_skill.scripts.metadata_quality import is_meaningful_metadata
from obsidian_kb_skill.scripts.template_contract import markdown_section_headings
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str


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
FENCE_OPEN_RE = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FOLDER_INDEX_CONTENT_RE = re.compile(
    r"^\s*```folder-index-content(?:\s+[^\n]*)?\s*$", re.MULTILINE
)

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
HTML_COMMENT_RE = re.compile(r"<!--([\s\S]*?)-->")
TEMPLATE_INSTRUCTION_MARKERS = (
    "用 2–4 句话",
    "用 2-4 句话",
    "区分原文观点与自己的推论",
    "说明原文解决什么问题",
    "完整重构原文的关键知识",
    "技术文章保留足以复现",
    "写清成功标准",
    "在完整理解原文后提炼",
    "只添加 vault 中真实存在",
    "explain the problem, required versions",
    "reconstruct all material knowledge",
    "for technical sources, preserve enough",
    "write clear success criteria",
    "state success criteria",
    "after reconstructing the source",
    "add only vault notes that actually exist",
    "link only to existing vault notes",
    "用不超过 12 个非空行填写全部字段",
    "只保留未来续接不能违反的范围",
    "写决定及必要理由",
    "列出路径、命令及结果",
    "写开放问题、阻塞项、第一步行动",
    "fill every field in at most 12 non-empty lines",
    "keep only scope, non-goals, user requirements",
    "state decisions and necessary rationale",
    "cite paths, commands and results",
    "state open questions, blockers, the first action",
)


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
    result = parse_frontmatter(text, source="note")
    if not result.present:
        return None, None
    if result.issue is not None:
        if result.issue.code == "invalid-frontmatter":
            return None, result.issue.context or result.issue.message
        if result.issue.code == "unclosed-frontmatter":
            return None, "frontmatter opening fence has no closing fence"
        return None, result.issue.message
    return result.metadata, None


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
    elif note_type not in VALID_NOTE_TYPES:
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


def _audit_template_instruction_comments(
    findings: list[Finding],
    relative: Path,
    text: str,
) -> None:
    if relative.name in EXEMPT_NAMES:
        return
    if relative.parts and relative.parts[0] == "Templates":
        return
    without_examples = _without_code_examples(text)
    for match in HTML_COMMENT_RE.finditer(without_examples):
        normalized = " ".join(match.group(1).lower().split())
        if not any(marker in normalized for marker in TEMPLATE_INSTRUCTION_MARKERS):
            continue
        _add(
            findings,
            "residual-template-instruction",
            relative,
            "note contains an instructional template comment that should be "
            "executed and removed before saving",
        )
        return


def _audit_required_template_headings(
    findings: list[Finding],
    vault: Path,
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if not metadata or (relative.parts and relative.parts[0] == "Templates"):
        return
    template_name = TYPE_TO_TEMPLATE.get(str(metadata.get("type", "")))
    if not template_name:
        return
    template_path = vault / "Templates" / template_name
    if not template_path.is_file():
        return
    template_text = template_path.read_text(encoding="utf-8")
    required = markdown_section_headings(template_text)
    actual = markdown_section_headings(text)
    actual_index = 0
    first_mismatch: str | None = None
    for heading in required:
        while actual_index < len(actual) and actual[actual_index] != heading:
            actual_index += 1
        if actual_index == len(actual):
            first_mismatch = heading
            break
        actual_index += 1
    if first_mismatch is None:
        return
    expected = " -> ".join(required) or "(none)"
    observed = " -> ".join(actual) or "(none)"
    _add(
        findings,
        "missing-template-heading",
        relative,
        "required template headings are missing or out of order; "
        f"expected headings: {expected}; actual headings: {observed}; "
        f"first mismatch: {first_mismatch}",
    )


def _audit_deep_capture_headings(
    findings: list[Finding],
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if (
        not metadata
        or metadata.get("type") != "web-clip"
        or (relative.parts and relative.parts[0] == "Templates")
    ):
        return
    actual = markdown_section_headings(text, levels=(2,))
    if matches_deep_capture_contract(actual):
        return
    observed = " -> ".join(actual) or "(none)"
    _add(
        findings,
        "missing-deep-capture-heading",
        relative,
        f"web-clip does not satisfy the v{DEEP_CAPTURE_CONTRACT_VERSION} "
        "deep-capture heading baseline; "
        f"accepted baselines: {formatted_deep_capture_variants()}; "
        f"actual headings: {observed}",
    )


def _audit_deep_capture_template(
    findings: list[Finding],
    vault: Path,
) -> None:
    template = vault / "Templates" / "Web Clip.md"
    if not template.is_file():
        return
    actual = markdown_section_headings(
        template.read_text(encoding="utf-8"),
        levels=(2,),
    )
    if matches_deep_capture_contract(actual):
        return
    observed = " -> ".join(actual) or "(none)"
    _add(
        findings,
        "outdated-deep-capture-template",
        template.relative_to(vault),
        f"Web Clip template does not satisfy the v{DEEP_CAPTURE_CONTRACT_VERSION} "
        "deep-capture heading baseline and can keep producing shallow articles; "
        f"accepted baselines: {formatted_deep_capture_variants()}; "
        f"actual headings: {observed}",
    )


def _audit_conversation_digest_template(
    findings: list[Finding],
    vault: Path,
) -> None:
    template = vault / "Templates" / "Digest Note.md"
    if not template.is_file():
        return
    actual = markdown_section_headings(
        template.read_text(encoding="utf-8"),
        levels=(2,),
    )
    if conversation_digest_locale(actual) is not None:
        return
    observed = " -> ".join(actual) or "(none)"
    _add(
        findings,
        "outdated-conversation-digest-template",
        template.relative_to(vault),
        "Digest Note template does not satisfy the version "
        f"{CONVERSATION_DIGEST_CONTRACT_VERSION} context-recovery baseline; "
        f"accepted baselines: {formatted_conversation_digest_variants()}; "
        f"actual headings: {observed}",
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
        if not is_meaningful_metadata(value):
            _add(
                findings,
                f"web-clip-missing-{field}",
                relative,
                f"web-clip note must set a non-placeholder '{field}' field",
            )
    capture_depth = metadata.get("capture_depth")
    if capture_depth is not None and (
        not isinstance(capture_depth, str) or capture_depth not in CAPTURE_DEPTHS
    ):
        _add(
            findings,
            "web-clip-invalid-capture-depth",
            relative,
            "web-clip capture_depth must be 'standard' or 'verified' when present",
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


def _without_fenced_code(text: str) -> tuple[str, bool]:
    """Return Markdown outside fenced code and whether one fence is unclosed."""
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        candidate = line.rstrip("\r\n")
        if fence_character is None:
            match = FENCE_OPEN_RE.fullmatch(candidate)
            if match is None:
                output.append(line)
                continue
            fence = match.group("fence")
            info = match.group("info")
            if fence[0] == "`" and "`" in info:
                output.append(line)
                continue
            fence_character = fence[0]
            fence_length = len(fence)
            continue
        if re.fullmatch(
            rf"[ \t]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
            candidate,
        ):
            fence_character = None
            fence_length = 0
    return "".join(output), fence_character is not None


def _without_code_examples(text: str) -> str:
    outside, _ = _without_fenced_code(text)
    return INLINE_CODE_RE.sub("", outside)


def _h2_sections(text: str) -> dict[str, str]:
    """Return visible level-two section bodies outside frontmatter and code."""
    visible = _without_code_examples(text)
    if visible.startswith("---\n"):
        end = visible.find("\n---\n", 4)
        if end != -1:
            visible = visible[end + 5 :]
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in visible.splitlines():
        match = re.fullmatch(r"##[ \t]+(.+?)[ \t]*#*[ \t]*", line)
        if match:
            current = match.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {
        heading: "\n".join(lines)
        for heading, lines in sections.items()
    }


def _audit_conversation_digest(
    findings: list[Finding],
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if (
        not metadata
        or metadata.get("type") != "conversation-digest"
        or (relative.parts and relative.parts[0] == "Templates")
    ):
        return
    actual = markdown_section_headings(text, levels=(2,))
    locale = conversation_digest_locale(actual)
    if locale is None:
        observed = " -> ".join(actual) or "(none)"
        _add(
            findings,
            "missing-conversation-digest-heading",
            relative,
            "conversation-digest does not satisfy the version "
            f"{CONVERSATION_DIGEST_CONTRACT_VERSION} context-recovery "
            "heading baseline; accepted baselines: "
            f"{formatted_conversation_digest_variants()}; "
            f"actual headings: {observed}",
        )
        return

    required_headings = dict(CONVERSATION_DIGEST_HEADING_VARIANTS)[locale]
    resume_heading = required_headings[0]
    resume = _h2_sections(text).get(resume_heading, "")
    visible_resume = HTML_COMMENT_RE.sub("", resume)
    visible_lines = [
        line.strip()
        for line in visible_resume.splitlines()
        if line.strip()
    ]
    if len(visible_lines) > 12:
        _add(
            findings,
            "conversation-digest-resume-card-too-long",
            relative,
            "Resume Card must contain at most 12 non-empty visible lines; "
            f"found {len(visible_lines)}",
        )

    missing: list[str] = []
    for field in CONVERSATION_DIGEST_RESUME_FIELD_VARIANTS[locale]:
        pattern = re.compile(
            rf"^[ \t]*[-*][ \t]+\*\*{re.escape(field)}\*\*"
            rf"[ \t]*[:：][ \t]*(?P<value>.+?)?[ \t]*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(visible_resume)
        if match is None or not (match.group("value") or "").strip():
            missing.append(field)
    if missing:
        _add(
            findings,
            "conversation-digest-missing-resume-field",
            relative,
            "Resume Card requires non-empty values for: "
            + ", ".join(missing),
        )


def _has_unclosed_fence(text: str) -> bool:
    _, unclosed = _without_fenced_code(text)
    return unclosed


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
        and not is_folder_index_excluded(path.relative_to(vault), config)
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
    _audit_deep_capture_template(findings, vault)
    _audit_conversation_digest_template(findings, vault)
    folder_index_config = read_folder_index_config(vault)
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
        if metadata and metadata.get("type") == "web-clip":
            _audit_deep_capture_headings(findings, relative, text, metadata)
        _audit_conversation_digest(findings, relative, text, metadata)
        _audit_folder_index_content(findings, relative, text, metadata)
        if _has_unclosed_fence(text):
            _add(findings, "unclosed-fence", relative, "fenced code block is not closed")
        _audit_template_placeholders(findings, relative, text)
        _audit_template_instruction_comments(findings, relative, text)
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


def _audit_note_content(
    vault: Path,
    note: Path,
    text: str,
) -> list[Finding]:
    """Run the note-level rule set against supplied Markdown content."""
    relative = note.relative_to(vault)
    findings: list[Finding] = []
    metadata, yaml_error = _frontmatter(text)
    if yaml_error:
        _add(findings, "invalid-frontmatter", relative, yaml_error)
    _audit_metadata(findings, relative, text, metadata)
    _audit_related(findings, relative, metadata)
    _audit_web_clip(findings, relative, metadata)
    _audit_empty_template(findings, relative, text, metadata)
    _audit_conversation_digest(findings, relative, text, metadata)
    _audit_folder_index_content(findings, relative, text, metadata)
    _audit_template_placeholders(findings, relative, text)
    _audit_template_instruction_comments(findings, relative, text)
    _audit_required_template_headings(findings, vault, relative, text, metadata)
    if _has_unclosed_fence(text):
        _add(
            findings,
            "unclosed-fence",
            relative,
            "fenced code block is not closed",
        )

    linkable = _all_linkable_files(vault)
    if note not in linkable:
        linkable.append(note)
    by_name: dict[str, list[Path]] = defaultdict(list)
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(linkable):
        by_name[path.name].append(path)
        by_stem[path.stem].append(path)
    if relative.name not in EXEMPT_NAMES:
        _audit_links(
            findings,
            vault,
            note,
            relative,
            _without_code_examples(text),
            by_name,
            by_stem,
        )
    return sorted(findings, key=lambda item: (item.path, item.code, item.message))


def audit_note_text(vault: Path, note: Path, text: str) -> list[Finding]:
    """Audit candidate note content without creating the destination file."""
    vault = validate_vault_root(vault)
    note = resolve_target_within_vault(vault, note, label="--note")
    return _audit_note_content(vault, note, text)


def audit_note(vault: Path, note: Path) -> list[Finding]:
    """Audit an existing note using the same rules as candidate preflight."""
    vault = validate_vault_root(vault)
    note = resolve_existing_within_vault(vault, note, label="--note")
    return _audit_note_content(vault, note, note.read_text(encoding="utf-8"))


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
    configure_utf8_stdio()
    args = _build_parser().parse_args(argv)
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not (vault / ".obsidian").is_dir():
        print(f"error: not an Obsidian vault: {vault}", file=sys.stderr)
        return 2
    try:
        findings = audit_vault(vault)
    except FolderIndexConfigError as exc:
        if args.json:
            print(json.dumps({"error": {
                "code": exc.code,
                "message": exc.message,
            }}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc.code}: {exc.message}", file=sys.stderr)
        return 2
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
