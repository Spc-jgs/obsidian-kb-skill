"""Plan and initialize one user-confirmed category inside an Obsidian Vault."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.audit_vault import (
    FOLDER_INDEX_CONTENT_RE,
    Finding,
    _frontmatter,
    _folder_index_config,
    _is_folder_index_excluded,
    expected_folder_index,
)
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.detect_index import detect
from obsidian_kb_skill.scripts.index_templates import (
    render_dataview_index,
    render_folder_index,
    render_static_index,
)
from obsidian_kb_skill.scripts.note_catalog import STANDARD_NOTE_FOLDERS
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)

RESERVED_TOP_LEVEL = frozenset(
    {
        ".git",
        ".obsidian",
        ".obsidian-kb-backups",
        ".venv",
        "Attachments",
        "Templates",
    }
)
INVALID_NAME_CHARS = frozenset('/\\:*?"<>|')
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


class CategoryValidationError(ValueError):
    """A stable, user-actionable category request failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class CategoryApplyError(OSError):
    """An apply failure with exact helper-created and cleanup paths."""

    def __init__(
        self,
        message: str,
        *,
        created: tuple[Path, ...],
        cleaned: tuple[Path, ...],
    ) -> None:
        self.created = created
        self.cleaned = cleaned
        super().__init__(message)


@dataclass(frozen=True)
class PlannedChange:
    kind: str
    path: Path


@dataclass(frozen=True)
class CategoryPlan:
    vault: Path
    folder: Path
    parent: Path
    category: str
    exists: bool
    index_mode: str
    index_path: Path
    planned_changes: tuple[PlannedChange, ...]
    governance_reminders: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ApplyResult:
    applied: bool
    status: str
    created: tuple[Path, ...]
    findings: tuple[Finding, ...]


def _reminders(vault: Path, parent: Path) -> tuple[str, ...]:
    directories = [Path(".")]
    current = Path()
    for part in parent.parts:
        current /= part
        directories.append(current)
    reminders: list[str] = []
    for directory in directories:
        for name in ("AGENTS.md", "CLAUDE.md", "README.md"):
            candidate = directory / name
            if (vault / candidate).is_file():
                reminders.append(candidate.as_posix())
    return tuple(reminders)


def _validate_category_name(name: str) -> None:
    windows_stem = name.split(".", 1)[0].upper()
    if (
        not name
        or name != name.strip()
        or name in {".", ".."}
        or name.startswith(".")
        or name.endswith(".")
        or windows_stem in WINDOWS_RESERVED_NAMES
        or len(name.encode("utf-8")) > 255
        or any(ord(character) < 32 or character in INVALID_NAME_CHARS for character in name)
    ):
        raise CategoryValidationError(
            "invalid-category-name",
            "category name must be a portable visible directory name",
        )


def _validated_relative_folder(root: Path, folder: str) -> Path:
    raw = str(folder)
    if (
        not raw
        or "\\" in raw
        or Path(raw).is_absolute()
        or any(part in {"", ".", ".."} for part in raw.split("/"))
    ):
        raise CategoryValidationError(
            "invalid-category-path",
            "category path must be a normalized Vault-relative path",
        )
    relative = Path(raw)
    if len(relative.parts) < 2:
        raise CategoryValidationError(
            "invalid-category-path",
            "category must be a child of an existing governed parent",
        )
    if (
        any(part in RESERVED_TOP_LEVEL for part in relative.parts)
        or relative.parts[:2] == ("docs", "superpowers")
    ):
        raise CategoryValidationError(
            "reserved-category-path",
            "category cannot be created in a Vault control or resource directory",
        )
    _validate_category_name(relative.name)

    target = root / relative
    if os.path.lexists(target):
        if target.is_symlink() or not target.is_dir():
            raise CategoryValidationError(
                "category-collision",
                "category destination is occupied by a file or symlink",
            )
    try:
        resolve_target_within_vault(root, relative, label="--folder")
    except VaultPathError as exc:
        raise CategoryValidationError("invalid-category-path", str(exc)) from exc

    parent = relative.parent
    try:
        parent_path = resolve_existing_within_vault(root, parent, label="category parent")
    except VaultPathError as exc:
        raise CategoryValidationError(
            "missing-category-parent",
            "category parent must already exist inside the Vault",
        ) from exc
    if not parent_path.is_dir():
        raise CategoryValidationError(
            "missing-category-parent", "category parent must be a directory"
        )

    parent_info = detect(root, parent.as_posix())
    index_name = parent_info.get("index_file")
    has_index = bool(index_name) and (root / parent / str(index_name)).is_file()
    if parent.as_posix() not in STANDARD_NOTE_FOLDERS and not has_index:
        raise CategoryValidationError(
            "ungoverned-category-parent",
            "category parent must be a standard note folder or have an index",
        )
    return relative


def plan_category(vault: Path, folder: str) -> CategoryPlan:
    """Return the deterministic index plan for one category path."""
    try:
        root = validate_vault_root(vault)
    except InvalidVaultRootError as exc:
        raise CategoryValidationError("invalid-vault", str(exc)) from exc
    if not (root / ".obsidian").is_dir():
        raise CategoryValidationError("invalid-vault", "Vault is missing .obsidian")
    relative = _validated_relative_folder(root, folder)
    parent = relative.parent
    target = root / relative
    config = _folder_index_config(root)
    parent_info = detect(root, parent.as_posix())
    warnings = tuple(parent_info.get("warnings", ()))

    if config.enabled and not _is_folder_index_excluded(relative, config):
        mode = "folder-index"
        index = expected_folder_index(target, root, config).relative_to(root)
    else:
        mode = "dataview" if parent_info["mode"] == "dataview" else "static"
        index = relative / "INDEX.md"

    exists = target.is_dir()
    changes = () if exists else (
        PlannedChange("directory", relative),
        PlannedChange("index", index),
    )
    return CategoryPlan(
        vault=root,
        folder=relative,
        parent=parent,
        category=relative.name,
        exists=exists,
        index_mode=mode,
        index_path=index,
        planned_changes=changes,
        governance_reminders=_reminders(root, parent),
        warnings=warnings,
    )


def render_category_index(plan: CategoryPlan) -> str:
    """Render the index selected by ``plan_category``."""
    if plan.index_mode == "folder-index":
        return render_folder_index(plan.category)
    if plan.index_mode == "dataview":
        return render_dataview_index(plan.category, plan.folder)
    return render_static_index(plan.category)


def audit_category(plan: CategoryPlan) -> list[Finding]:
    """Validate only the category directory and index created by this helper."""
    findings: list[Finding] = []
    directory = plan.vault / plan.folder
    index = plan.vault / plan.index_path
    if not directory.is_dir():
        findings.append(
            Finding("missing-category-directory", plan.folder.as_posix(), "category directory is missing")
        )
        return findings
    if not index.is_file():
        findings.append(
            Finding("missing-category-index", plan.index_path.as_posix(), "category index is missing")
        )
        return findings
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(
            Finding("unreadable-category-index", plan.index_path.as_posix(), str(exc))
        )
        return findings
    metadata, error = _frontmatter(text)
    expected_type = "folder-index" if plan.index_mode == "folder-index" else "moc"
    if error or not metadata or metadata.get("type") != expected_type:
        findings.append(
            Finding(
                "invalid-category-index",
                plan.index_path.as_posix(),
                f"category index must declare type: {expected_type}",
            )
        )
    if plan.index_mode == "folder-index" and len(
        FOLDER_INDEX_CONTENT_RE.findall(text)
    ) != 1:
        findings.append(
            Finding(
                "invalid-folder-index-content",
                plan.index_path.as_posix(),
                "Folder Index category must contain exactly one folder-index-content block",
            )
        )
    elif plan.index_mode == "dataview" and "```dataview" not in text:
        findings.append(
            Finding(
                "invalid-dataview-index",
                plan.index_path.as_posix(),
                "Dataview category index is missing its query block",
            )
        )
    return findings


def _write_index_exclusively(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)


def apply_category(plan: CategoryPlan) -> ApplyResult:
    """Create a planned category and index without touching existing paths."""
    if plan.exists:
        return ApplyResult(False, "already-exists", (), ())

    directory = plan.vault / plan.folder
    index = plan.vault / plan.index_path
    rendered = render_category_index(plan).encode("utf-8")
    directory.mkdir()
    try:
        _write_index_exclusively(index, rendered)
    except Exception as exc:
        created = [plan.folder]
        cleaned: list[Path] = []
        if index.exists() and index.is_file() and not index.is_symlink():
            created.append(plan.index_path)
            try:
                index.unlink()
                cleaned.append(plan.index_path)
            except OSError:
                pass
        try:
            directory.rmdir()
            cleaned.append(plan.folder)
        except OSError:
            pass
        raise CategoryApplyError(
            str(exc), created=tuple(created), cleaned=tuple(cleaned)
        ) from exc
    findings = tuple(audit_category(plan))
    return ApplyResult(
        True,
        "created",
        (plan.folder, plan.index_path),
        findings,
    )


def _finding_payload(findings: tuple[Finding, ...] | list[Finding]) -> list[dict[str, str]]:
    return [
        {"code": finding.code, "path": finding.path, "message": finding.message}
        for finding in findings
    ]


def result_payload(plan: CategoryPlan, result: ApplyResult | None = None) -> dict[str, Any]:
    applied = result.applied if result is not None else False
    return {
        "vault": str(plan.vault),
        "folder": plan.folder.as_posix(),
        "parent": plan.parent.as_posix(),
        "category": plan.category,
        "exists": plan.exists,
        "applied": applied,
        "status": (
            result.status
            if result is not None
            else ("already-exists" if plan.exists else "planned")
        ),
        "index": {"mode": plan.index_mode, "path": plan.index_path.as_posix()},
        "planned_changes": [
            {"kind": change.kind, "path": change.path.as_posix()}
            for change in plan.planned_changes
        ],
        "created": [path.as_posix() for path in (result.created if result else ())],
        "governance_reminders": list(plan.governance_reminders),
        "warnings": list(plan.warnings),
        "audit": _finding_payload(result.findings) if result is not None else None,
    }


def _error_payload(
    code: str, message: str, *, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _report_error(
    code: str,
    message: str,
    *,
    json_mode: bool,
    details: dict[str, Any] | None = None,
) -> int:
    if json_mode:
        print(
            json.dumps(
                _error_payload(code, message, details=details),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"error: {code}: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Initialize one user-confirmed category and governed index."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian Vault")
    parser.add_argument(
        "--folder", required=True, help="New Vault-relative category path"
    )
    parser.add_argument("--apply", action="store_true", help="Create the category")
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="Confirm that the user approved the final category path",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Emit JSON")
    output.add_argument(
        "--preflight-json", action="store_true", help="Emit a read-only mutation plan"
    )
    output.add_argument(
        "--compact-json", action="store_true", help="Emit compact apply JSON"
    )
    args = parser.parse_args(argv)
    json_mode = args.json or args.preflight_json or args.compact_json

    if args.apply and not args.confirmed:
        return _report_error(
            "confirmation-required",
            "--apply requires --confirmed after the user approves the category path",
            json_mode=json_mode,
        )
    try:
        plan = plan_category(args.vault, args.folder)
    except CategoryValidationError as exc:
        return _report_error(exc.code, exc.message, json_mode=json_mode)

    if not args.apply:
        payload = result_payload(plan)
        if json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"folder: {payload['folder']}")
            print(f"index: {payload['index']['path']} ({payload['index']['mode']})")
            print("(dry run) pass --apply --confirmed to create the category.")
        return 0

    try:
        result = apply_category(plan)
    except CategoryApplyError as exc:
        return _report_error(
            "category-apply-failed",
            str(exc),
            json_mode=json_mode,
            details={
                "created": [path.as_posix() for path in exc.created],
                "cleaned": [path.as_posix() for path in exc.cleaned],
            },
        )
    except OSError as exc:
        return _report_error("category-apply-failed", str(exc), json_mode=json_mode)
    payload = result_payload(plan, result)
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result.status}")
        for created in result.created:
            print(f"created: {created.as_posix()}")
        if result.findings:
            for finding in result.findings:
                print(f"AUDIT: {finding.code}: {finding.message}")
        else:
            print("AUDIT: OK")
    return 0 if not result.findings else 2


if __name__ == "__main__":
    raise SystemExit(main())
