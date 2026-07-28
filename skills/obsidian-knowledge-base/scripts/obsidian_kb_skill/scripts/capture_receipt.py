#!/usr/bin/env python3
"""Validate content-bound semantic evidence for one finished deep capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.metadata_quality import is_meaningful_metadata
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    validate_vault_root,
)


SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 1024 * 1024
PROFILES = frozenset(
    {
        "tutorial-procedure",
        "resource-survey",
        "conceptual-opinion",
        "research-evidence",
    }
)
PROFILE_REQUIRED_KINDS = {
    "tutorial-procedure": frozenset(
        {"prerequisite", "procedure", "verification", "failure-mode"}
    ),
    "resource-survey": frozenset(
        {
            "canonical-link",
            "compatibility",
            "limitation",
            "selection-criteria",
            "starting-example",
        }
    ),
    "conceptual-opinion": frozenset(
        {"causal-claim", "application-method", "boundary", "counterexample"}
    ),
    "research-evidence": frozenset(
        {
            "decision-implication",
            "evidence",
            "limitation",
            "measurement-context",
            "uncertainty",
        }
    ),
}
PRACTICAL_ARTIFACTS = {
    "tutorial-procedure": frozenset({"reproducible-procedure"}),
    "resource-survey": frozenset({"selection-decision"}),
    "conceptual-opinion": frozenset({"application-method"}),
    "research-evidence": frozenset({"decision-method"}),
}
MATERIAL_KINDS = frozenset().union(*PROFILE_REQUIRED_KINDS.values()) | frozenset(
    {
        "assumption",
        "code",
        "command",
        "configuration",
        "counterexample",
        "dependency",
        "failure-mode",
        "limitation",
        "parameter",
        "prerequisite",
        "result",
        "risk",
        "version",
    }
)
NUMERIC_PROVENANCE = frozenset(
    {
        "primary-source",
        "source-self-report",
        "supplemental-primary",
        "calculation",
    }
)

# Metrics and measurement-shaped values are the highest-risk unsupported
# inventions observed in real captures. Dates and ordinary list numbers are
# intentionally excluded; versions remain covered by profile material items.
_METRIC_RE = re.compile(
    r"(?<![\w])(?:"
    r"\d+(?:\.\d+)?\s*(?:%|％)"
    r"|\d+(?:\.\d+)?\s*(?:小时|分钟|秒|天|周|个月|年|毫秒)"
    r"|\d+(?:\.\d+)?\s*(?:万|亿)"
    r"|\d+(?:\.\d+)?\s*(?:ms|s|min|mins|minutes?|hours?|days?|weeks?|months?|years?)\b"
    r"|\d+(?:\.\d+)?\s*(?:/|:|：)\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*(?:[kKmMbB]|thousand|million|billion)\b"
    r"|\d{1,3}(?:,\d{3})+(?:\+)?"
    r"|⭐\s*\d+(?:\.\d+)?(?:\s*[kKmMbB])?"
    r")"
)
_FENCE_OPEN_RE = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
_FRONTMATTER_LINE_RE = re.compile(r"(?m)^---[ \t]*$")
_COPYABLE_SKILL_COMMAND_RE = re.compile(
    r"^[ \t]*(?:"
    r"cat\b[^\r\n]*?>{1,2}[^\r\n]*SKILL\.md"
    r"|tee\b[^\r\n]*SKILL\.md"
    r"|set-content\b[^\r\n]*SKILL\.md"
    r"|out-file\b[^\r\n]*SKILL\.md"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


class CaptureReceiptError(ValueError):
    """Stable semantic-receipt validation failure."""

    def __init__(
        self, code: str, message: str, *, details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


def requires_capture_receipt(note_type: str, folder: str) -> bool:
    """Return whether a routed note is a finished source-backed article."""
    parts = Path(folder).parts
    return note_type == "web-clip" and (not parts or parts[0] != "00-Inbox")


def rendered_sha256(rendered: str) -> str:
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def receipt_sha256(receipt: dict[str, Any]) -> str:
    canonical = json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_receipt_json(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CaptureReceiptError(
            "invalid-capture-receipt-json",
            "capture receipt must be valid JSON",
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc
    if not isinstance(payload, dict):
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "capture receipt root must be an object",
        )
    return payload


def load_receipt_file(path: Path) -> dict[str, Any]:
    """Read one bounded regular UTF-8 receipt without echoing its contents."""
    try:
        if path.is_symlink() or not path.is_file():
            raise CaptureReceiptError(
                "invalid-capture-receipt-file",
                "capture receipt file must be a regular non-symlink file",
            )
        size = path.stat().st_size
        if size > MAX_RECEIPT_BYTES:
            raise CaptureReceiptError(
                "capture-receipt-too-large",
                "capture receipt file exceeds the 1 MiB safety limit",
                details={"bytes": size, "limit": MAX_RECEIPT_BYTES},
            )
        return parse_receipt_json(path.read_text(encoding="utf-8"))
    except CaptureReceiptError:
        raise
    except UnicodeError as exc:
        raise CaptureReceiptError(
            "invalid-capture-receipt-file",
            "capture receipt file must contain valid UTF-8",
        ) from exc
    except OSError as exc:
        raise CaptureReceiptError(
            "invalid-capture-receipt-file",
            f"cannot read capture receipt file: {exc}",
        ) from exc


def _url_list(receipt: dict[str, Any], field: str, *, required: bool) -> list[str]:
    value = receipt.get(field)
    if not isinstance(value, list) or (required and not value):
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            f"{field} must be {'a non-empty' if required else 'an'} array",
        )
    urls: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                f"{field} entries must be non-empty URLs",
            )
        parsed = urlparse(item)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                f"{field} contains a non-HTTP URL",
                details={"value": item},
            )
        urls.append(item)
    if len(urls) != len(set(urls)):
        raise CaptureReceiptError(
            "invalid-capture-receipt", f"{field} must not contain duplicates"
        )
    return urls


def _selected_profiles(receipt: dict[str, Any]) -> tuple[str, ...]:
    singular = receipt.get("profile")
    plural = receipt.get("profiles")
    if singular is not None and plural is not None:
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "use either profile or profiles, not both",
        )
    if singular is not None:
        values = [singular]
    elif isinstance(plural, list):
        values = plural
    else:
        values = []
    if (
        not values
        or any(not isinstance(item, str) or item not in PROFILES for item in values)
        or len(values) != len(set(values))
    ):
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "profile selection must contain unique supported profiles",
            details={"supported": sorted(PROFILES)},
        )
    if plural is not None and values != sorted(values):
        raise CaptureReceiptError(
            "invalid-capture-receipt", "profiles must be sorted"
        )
    return tuple(values)


def _fence_opening(line: str) -> tuple[str, int] | None:
    match = _FENCE_OPEN_RE.fullmatch(line.rstrip("\r\n"))
    if match is None:
        return None
    fence = match.group("fence")
    if fence[0] == "`" and "`" in match.group("info"):
        return None
    return fence[0], len(fence)


def _is_fence_closing(line: str, character: str, length: int) -> bool:
    return (
        re.fullmatch(
            rf"[ \t]{{0,3}}{re.escape(character)}{{{length},}}[ \t]*",
            line.rstrip("\r\n"),
        )
        is not None
    )


def _iter_fenced_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    body: list[str] | None = None
    fence_character = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        if body is None:
            opening = _fence_opening(line)
            if opening is None:
                continue
            fence_character, fence_length = opening
            body = []
            continue
        if _is_fence_closing(line, fence_character, fence_length):
            blocks.append("".join(body))
            body = None
            fence_character = ""
            fence_length = 0
            continue
        body.append(line)
    if body is not None:
        blocks.append("".join(body))
    return blocks


def _mask_text(value: str) -> str:
    return "".join(
        "\n" if character == "\n" else "\r" if character == "\r" else " "
        for character in value
    )


def _mask_html_comments(line: str, inside: bool) -> tuple[str, bool]:
    output: list[str] = []
    position = 0
    while position < len(line):
        if inside:
            end = line.find("-->", position)
            if end < 0:
                output.append(_mask_text(line[position:]))
                return "".join(output), True
            output.append(_mask_text(line[position : end + 3]))
            position = end + 3
            inside = False
            continue
        start = line.find("<!--", position)
        if start < 0:
            output.append(line[position:])
            break
        output.append(line[position:start])
        position = start
        inside = True
    return "".join(output), inside


def _reader_facing_body(rendered: str) -> str:
    """Return Markdown body with hidden comments masked outside visible code."""
    parsed = parse_frontmatter(rendered, source="candidate")
    body = parsed.body if parsed.present and parsed.issue is None else rendered
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    inside_comment = False
    for line in body.splitlines(keepends=True):
        if fence_character is None:
            if not inside_comment:
                opening = _fence_opening(line)
                if opening is not None:
                    fence_character, fence_length = opening
                    output.append(line)
                    continue
            visible, inside_comment = _mask_html_comments(line, inside_comment)
            output.append(visible)
            continue
        output.append(line)
        if _is_fence_closing(line, fence_character, fence_length):
            fence_character = None
            fence_length = 0
    return "".join(output)


def _mask_fenced_code(text: str) -> str:
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        if fence_character is None:
            opening = _fence_opening(line)
            if opening is None:
                output.append(line)
                continue
            fence_character, fence_length = opening
            output.append(_mask_text(line))
            continue
        output.append(_mask_text(line))
        if _is_fence_closing(line, fence_character, fence_length):
            fence_character = None
            fence_length = 0
    return "".join(output)


def _exact_anchor(reader_facing: str, value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaptureReceiptError(
            "invalid-capture-receipt", f"{field} must be non-empty text"
        )
    if value not in reader_facing:
        raise CaptureReceiptError(
            "missing-receipt-anchor",
            f"{field} does not exist in reader-facing candidate content",
            details={"anchor": value},
        )
    return value


def _masked_body(rendered: str) -> str:
    body = _mask_fenced_code(_reader_facing_body(rendered))

    def mask(match: re.Match[str]) -> str:
        return _mask_text(match.group(0))

    body = re.sub(r"`[^`\n]*`", mask, body)
    body = re.sub(r"https?://[^\s)>]+", mask, body)
    return body


def _metric_spans(rendered: str) -> tuple[str, list[tuple[int, int, str]]]:
    body = _masked_body(rendered)
    spans: list[tuple[int, int, str]] = []
    for match in _METRIC_RE.finditer(body):
        value = match.group(0)
        if re.fullmatch(r"(?:19|20)\d{2}\s*年", value):
            continue
        spans.append((match.start(), match.end(), value))
    return body, spans


def _validate_copyable_skill_frontmatter(rendered: str) -> None:
    """Reject malformed YAML in shell examples that create a SKILL.md."""
    parsed = parse_frontmatter(rendered, source="candidate")
    body = parsed.body if parsed.present and parsed.issue is None else rendered
    for block_index, block in enumerate(_iter_fenced_blocks(body)):
        if _COPYABLE_SKILL_COMMAND_RE.search(block) is None:
            continue
        delimiters = list(_FRONTMATTER_LINE_RE.finditer(block))
        if len(delimiters) < 2:
            raise CaptureReceiptError(
                "invalid-copyable-skill-frontmatter",
                "copyable SKILL.md example requires a closed YAML frontmatter block",
                details={"block": block_index},
            )
        yaml_text = block[delimiters[0].end() : delimiters[1].start()]
        try:
            metadata = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            raise CaptureReceiptError(
                "invalid-copyable-skill-frontmatter",
                "copyable SKILL.md example contains invalid YAML",
                details={
                    "block": block_index,
                    "line": mark.line + 1 if mark is not None else None,
                    "column": mark.column + 1 if mark is not None else None,
                },
            ) from exc
        if not isinstance(metadata, dict) or not all(
            is_meaningful_metadata(metadata.get(field))
            for field in ("name", "description")
        ):
            raise CaptureReceiptError(
                "invalid-copyable-skill-frontmatter",
                "copyable SKILL.md frontmatter requires meaningful name and description",
                details={"block": block_index},
            )


def _excerpt_spans(body: str, excerpts: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for excerpt in excerpts:
        start = 0
        while True:
            index = body.find(excerpt, start)
            if index < 0:
                break
            spans.append((index, index + len(excerpt)))
            start = index + 1
    return spans


def validate_capture_receipt(
    receipt: dict[str, Any],
    rendered: str,
    *,
    candidate_source: str,
) -> dict[str, Any]:
    """Validate and summarize one receipt bound to ``rendered``."""
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            f"schema_version must be {SCHEMA_VERSION}",
        )
    _validate_copyable_skill_frontmatter(rendered)
    actual_content_sha256 = rendered_sha256(rendered)
    if receipt.get("content_sha256") != actual_content_sha256:
        raise CaptureReceiptError(
            "capture-receipt-content-mismatch",
            "capture receipt is not bound to the rendered candidate",
            details={
                "expected": actual_content_sha256,
                "actual": receipt.get("content_sha256"),
            },
        )
    reader_facing = _reader_facing_body(rendered)
    profiles = _selected_profiles(receipt)
    if receipt.get("source_access") != "complete":
        raise CaptureReceiptError(
            "incomplete-source-access",
            "finished deep capture requires source_access: complete",
        )
    primary_sources = _url_list(receipt, "primary_sources", required=True)
    supplemental_sources = _url_list(
        receipt, "supplemental_sources", required=False
    )
    if set(primary_sources) & set(supplemental_sources):
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "primary and supplemental sources must be disjoint",
        )
    if candidate_source not in primary_sources:
        raise CaptureReceiptError(
            "source-receipt-mismatch",
            "candidate source metadata must appear in primary_sources",
            details={"candidate_source": candidate_source},
        )
    all_sources = set(primary_sources) | set(supplemental_sources)
    resource_ids: set[str] = set()
    resource_evidence: dict[str, set[str]] = {}
    resources = receipt.get("resources")
    if "resource-survey" in profiles:
        if not isinstance(resources, list) or not resources:
            raise CaptureReceiptError(
                "incomplete-resource-evidence",
                "resource-survey requires a non-empty resources array",
            )
        resource_names: set[str] = set()
        resource_urls: set[str] = set()
        for index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                raise CaptureReceiptError(
                    "invalid-capture-receipt",
                    "resources entries must be objects",
                    details={"index": index},
                )
            resource_id = resource.get("id")
            if (
                not isinstance(resource_id, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", resource_id)
                or resource_id in resource_ids
            ):
                raise CaptureReceiptError(
                    "invalid-capture-receipt",
                    "resource IDs must be unique lowercase slugs",
                    details={"index": index},
                )
            name = resource.get("name")
            if not is_meaningful_metadata(name) or name in resource_names:
                raise CaptureReceiptError(
                    "invalid-capture-receipt",
                    "resource names must be unique meaningful text",
                    details={"index": index},
                )
            canonical_url = resource.get("canonical_url")
            if not isinstance(canonical_url, str):
                raise CaptureReceiptError(
                    "invalid-capture-receipt",
                    "resource canonical_url must be an HTTP URL",
                    details={"index": index},
                )
            parsed_url = urlparse(canonical_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
                or canonical_url in resource_urls
            ):
                raise CaptureReceiptError(
                    "invalid-capture-receipt",
                    "resource canonical URLs must be unique HTTP URLs",
                    details={"index": index},
                )
            _exact_anchor(
                reader_facing,
                canonical_url,
                field=f"resources[{index}].canonical_url",
            )
            resource_ids.add(resource_id)
            resource_names.add(str(name))
            resource_urls.add(canonical_url)
            resource_evidence[resource_id] = set()
    elif resources is not None:
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "resources is allowed only when resource-survey is selected",
        )

    unresolved = receipt.get("unresolved_items")
    if not isinstance(unresolved, list):
        raise CaptureReceiptError(
            "invalid-capture-receipt", "unresolved_items must be an array"
        )
    if unresolved:
        raise CaptureReceiptError(
            "unresolved-material-items",
            "finished deep capture cannot contain unresolved material items",
            details={"count": len(unresolved)},
        )

    material_items = receipt.get("material_items")
    if not isinstance(material_items, list) or not material_items:
        raise CaptureReceiptError(
            "invalid-capture-receipt",
            "material_items must be a non-empty array",
        )
    ids: set[str] = set()
    material_kinds: set[str] = set()
    for index, item in enumerate(material_items):
        if not isinstance(item, dict):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "material_items entries must be objects",
                details={"index": index},
            )
        item_id = item.get("id")
        if (
            not isinstance(item_id, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", item_id)
            or item_id in ids
        ):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "material item IDs must be unique lowercase slugs",
                details={"index": index},
            )
        ids.add(item_id)
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in MATERIAL_KINDS:
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "material item has an unsupported kind",
                details={"index": index, "kind": kind},
            )
        material_kinds.add(kind)
        if item.get("status") != "resolved":
            raise CaptureReceiptError(
                "unresolved-material-items",
                "every material item must have status: resolved",
                details={"id": item_id},
            )
        if item.get("source") not in all_sources:
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "material item source must be declared",
                details={"id": item_id},
            )
        resource_id = item.get("resource_id")
        if resource_id is not None and (
            not isinstance(resource_id, str) or resource_id not in resource_ids
        ):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "material item resource_id must identify a declared resource",
                details={"id": item_id, "resource_id": resource_id},
            )
        if "resource-survey" in profiles and kind in {
            "canonical-link",
            "compatibility",
            "limitation",
        }:
            if not isinstance(resource_id, str) or resource_id not in resource_ids:
                raise CaptureReceiptError(
                    "incomplete-resource-evidence",
                    f"{kind} evidence must identify one concrete resource",
                    details={"id": item_id},
                )
            resource_evidence[str(resource_id)].add(str(kind))
        _exact_anchor(
            reader_facing,
            item.get("note_anchor"),
            field=f"material_items[{index}].note_anchor",
        )
    for profile in profiles:
        missing = PROFILE_REQUIRED_KINDS[profile] - material_kinds
        if missing:
            raise CaptureReceiptError(
                "incomplete-profile-evidence",
                f"{profile} is missing required material evidence",
                details={"missing_kinds": sorted(missing)},
            )
    required_resource_kinds = {"canonical-link", "compatibility", "limitation"}
    for resource_id, evidence in resource_evidence.items():
        missing = required_resource_kinds - evidence
        if missing:
            raise CaptureReceiptError(
                "incomplete-resource-evidence",
                "each resource needs canonical-link, compatibility, and limitation evidence",
                details={
                    "resource_id": resource_id,
                    "missing_kinds": sorted(missing),
                },
            )

    numeric_claims = receipt.get("numeric_claims")
    if not isinstance(numeric_claims, list):
        raise CaptureReceiptError(
            "invalid-capture-receipt", "numeric_claims must be an array"
        )
    numeric_excerpts: list[str] = []
    for index, claim in enumerate(numeric_claims):
        if not isinstance(claim, dict):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "numeric_claims entries must be objects",
                details={"index": index},
            )
        excerpt = _exact_anchor(
            reader_facing,
            claim.get("note_excerpt"),
            field=f"numeric_claims[{index}].note_excerpt",
        )
        numeric_excerpts.append(excerpt)
        provenance = claim.get("provenance")
        if provenance not in NUMERIC_PROVENANCE:
            raise CaptureReceiptError(
                "missing-numeric-provenance",
                "numeric claim requires a supported provenance",
                details={"index": index, "supported": sorted(NUMERIC_PROVENANCE)},
            )
        source = claim.get("source")
        if provenance in {"primary-source", "source-self-report"}:
            allowed_sources = set(primary_sources)
        elif provenance == "supplemental-primary":
            allowed_sources = set(supplemental_sources)
        else:
            allowed_sources = all_sources
        if source not in allowed_sources:
            raise CaptureReceiptError(
                "missing-numeric-provenance",
                "numeric claim source does not match its provenance",
                details={"index": index, "source": source},
            )
        if not is_meaningful_metadata(claim.get("measurement_context")):
            raise CaptureReceiptError(
                "missing-measurement-context",
                "numeric claim requires meaningful measurement context",
                details={"index": index},
            )

    body, metrics = _metric_spans(rendered)
    covered_spans = _excerpt_spans(body, numeric_excerpts)
    uncovered = [
        value
        for start, end, value in metrics
        if not any(left <= start and end <= right for left, right in covered_spans)
    ]
    if uncovered:
        raise CaptureReceiptError(
            "uncovered-numeric-claim",
            "every measurement-shaped value must be covered by numeric_claims",
            details={"values": uncovered[:20], "truncated": len(uncovered) > 20},
        )

    inferences = receipt.get("inferences")
    if not isinstance(inferences, list):
        raise CaptureReceiptError(
            "invalid-capture-receipt", "inferences must be an array"
        )
    for index, inference in enumerate(inferences):
        if not isinstance(inference, dict):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "inferences entries must be objects",
                details={"index": index},
            )
        excerpt = _exact_anchor(
            reader_facing,
            inference.get("note_excerpt"),
            field=f"inferences[{index}].note_excerpt",
        )
        if not is_meaningful_metadata(inference.get("basis")):
            raise CaptureReceiptError(
                "invalid-capture-receipt",
                "inference requires an evidence basis",
                details={"index": index},
            )
        label = inference.get("label")
        if not is_meaningful_metadata(label) or str(label) not in excerpt:
            raise CaptureReceiptError(
                "unlabeled-inference",
                "inference label must occur inside its reader-facing excerpt",
                details={"index": index},
            )

    practical = receipt.get("practical_artifact")
    if not isinstance(practical, dict):
        raise CaptureReceiptError(
            "missing-practical-artifact",
            "selected profiles require one practical artifact",
        )
    practical_kind = practical.get("kind")
    allowed_artifacts = frozenset().union(
        *(PRACTICAL_ARTIFACTS[profile] for profile in profiles)
    )
    if practical_kind not in allowed_artifacts:
        raise CaptureReceiptError(
            "missing-practical-artifact",
            "practical artifact kind does not match the selected profiles",
            details={"allowed": sorted(allowed_artifacts)},
        )
    _exact_anchor(
        reader_facing,
        practical.get("note_anchor"),
        field="practical_artifact.note_anchor",
    )

    summary = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "sha256": receipt_sha256(receipt),
        "content_sha256": actual_content_sha256,
        "profiles": list(profiles),
        "primary_source_count": len(primary_sources),
        "supplemental_source_count": len(supplemental_sources),
        "material_item_count": len(material_items),
        "numeric_claim_count": len(numeric_claims),
        "inference_count": len(inferences),
        "unresolved_item_count": 0,
    }
    if "resource-survey" in profiles:
        summary["resource_count"] = len(resource_ids)
    return summary


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Validate a content-bound deep-capture semantic receipt."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument(
        "--content-file",
        required=True,
        help="Vault-relative path to the complete candidate Markdown",
    )
    receipt_input = parser.add_mutually_exclusive_group(required=True)
    receipt_input.add_argument(
        "--receipt-json", help="Compact capture receipt JSON"
    )
    receipt_input.add_argument(
        "--receipt-file",
        type=Path,
        help="Path to a bounded UTF-8 capture receipt JSON file",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(json.dumps({"error": {"code": "invalid-vault", "message": str(exc)}}))
        return 2
    try:
        candidate = resolve_existing_within_vault(
            vault, args.content_file, label="--content-file"
        )
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--content-file", json_mode=True)
    if not candidate.is_file():
        print(
            json.dumps(
                {
                    "error": {
                        "code": "invalid-content-file",
                        "message": "--content-file must be a regular file",
                    }
                },
                ensure_ascii=False,
            )
        )
        return 2
    try:
        rendered = candidate.read_text(encoding="utf-8")
        parsed = parse_frontmatter(
            rendered, source=candidate.relative_to(vault).as_posix()
        )
        candidate_source = (
            parsed.metadata.get("source")
            if parsed.issue is None and isinstance(parsed.metadata, dict)
            else None
        )
        if not isinstance(candidate_source, str) or not candidate_source:
            raise CaptureReceiptError(
                "missing-candidate-source",
                "candidate frontmatter requires a non-empty source",
            )
        receipt = (
            parse_receipt_json(args.receipt_json)
            if args.receipt_json is not None
            else load_receipt_file(args.receipt_file)
        )
        result = validate_capture_receipt(
            receipt, rendered, candidate_source=candidate_source
        )
    except UnicodeError:
        error = CaptureReceiptError(
            "invalid-utf8-input", "candidate must contain valid UTF-8"
        )
        print(json.dumps({"error": error.payload()}, ensure_ascii=False))
        return 2
    except CaptureReceiptError as exc:
        print(json.dumps({"error": exc.payload()}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
