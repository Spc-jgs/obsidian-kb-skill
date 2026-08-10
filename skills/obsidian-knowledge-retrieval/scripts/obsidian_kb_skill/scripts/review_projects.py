#!/usr/bin/env python3
"""Build a bounded, explainable, read-only project revival queue."""
from __future__ import annotations

import argparse
import datetime
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.note_catalog import EXEMPT_NAMES
from obsidian_kb_skill.scripts.search_vault import parse_note_date
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    validate_vault_root,
)


SCHEMA_VERSION = "1.0"
DEFAULT_STALE_DAYS = 30
MAX_STALE_DAYS = 3650
DEFAULT_TOP_K = 10
MAX_TOP_K = 20
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ISSUES = 20
MAX_NEXT_ACTION_CHARS = 200
PROJECT_TYPE = "project-note"
CLOSED_STATUSES = {
    "archived",
    "canceled",
    "cancelled",
    "closed",
    "completed",
    "done",
}
IGNORED_DIRECTORY_NAMES = {
    "Attachments",
    "Templates",
    "95-Sources",
    "__pycache__",
    "node_modules",
    ".git",
    ".obsidian",
    ".venv",
    ".workbuddy",
    ".claude",
    ".cursor",
    ".codex",
    ".agents",
    ".obsidian-kb-backups",
}
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")
OPEN_TASK_RE = re.compile(r"^[ \t]*[-*+][ \t]+\[[ \t]\][ \t]+(.+?)\s*$")
NEXT_ACTION_HEADINGS = {"下一步行动", "next actions", "next steps"}


@dataclass(frozen=True)
class ProjectItem:
    path: str
    title: str
    status: str
    activity_date: datetime.date | None
    age_days: int | None
    open_tasks: int
    next_action: str | None
    reasons: tuple[str, ...]
    priority: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "status": self.status,
            "activity_date": (
                self.activity_date.isoformat() if self.activity_date else None
            ),
            "age_days": self.age_days,
            "open_tasks": self.open_tasks,
            "next_action": self.next_action,
            "reasons": list(self.reasons),
        }


def _ignored_directory(path: Path) -> bool:
    return path.name.startswith(".") or path.name in IGNORED_DIRECTORY_NAMES


def _markdown_files(scope: Path) -> Iterable[Path]:
    for directory, names, filenames in os.walk(scope, followlinks=False):
        parent = Path(directory)
        names[:] = sorted(
            name
            for name in names
            if not _ignored_directory(parent / name)
            and not (parent / name).is_symlink()
        )
        for name in sorted(filenames):
            path = parent / name
            if (
                path.suffix.lower() == ".md"
                and not path.is_symlink()
                and path.name not in EXEMPT_NAMES
            ):
                yield path


def _without_comments(text: str) -> str:
    def mask(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return HTML_COMMENT_RE.sub(mask, text)


def visible_markdown(text: str) -> str:
    """Remove comments and fenced blocks without executing note content."""
    visible: list[str] = []
    fence_char: str | None = None
    fence_size = 0
    for line in _without_comments(text).splitlines():
        match = FENCE_RE.match(line)
        if fence_char is None:
            if match:
                marker = match.group("fence")
                fence_char = marker[0]
                fence_size = len(marker)
                visible.append("")
            else:
                visible.append(line)
            continue
        if match:
            marker = match.group("fence")
            if marker[0] == fence_char and len(marker) >= fence_size:
                fence_char = None
                fence_size = 0
        visible.append("")
    return "\n".join(visible)


def _title(path: Path, body: str) -> str:
    for line in body.splitlines():
        match = re.match(r"^#[ \t]+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return path.stem


def _open_tasks(body: str) -> list[tuple[int, str]]:
    tasks: list[tuple[int, str]] = []
    for index, line in enumerate(body.splitlines()):
        match = OPEN_TASK_RE.match(line)
        if match:
            tasks.append((index, match.group(1).strip()))
    return tasks


def _bounded_action(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= MAX_NEXT_ACTION_CHARS:
        return compact
    return compact[: MAX_NEXT_ACTION_CHARS - 1].rstrip() + "…"


def _next_action(body: str, tasks: list[tuple[int, str]]) -> str | None:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match or match.group(2).strip().lower() not in NEXT_ACTION_HEADINGS:
            continue
        level = len(match.group(1))
        end = len(lines)
        for following in range(index + 1, len(lines)):
            next_heading = HEADING_RE.match(lines[following])
            if next_heading and len(next_heading.group(1)) <= level:
                end = following
                break
        for task_index, action in tasks:
            if index < task_index < end:
                return _bounded_action(action)
    return _bounded_action(tasks[0][1]) if tasks else None


def _scalar(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _activity_date(metadata: dict[str, Any]) -> datetime.date | None:
    for key in ("updated", "date"):
        parsed = parse_note_date(metadata.get(key))
        if parsed is not None:
            return datetime.date.fromisoformat(parsed)
    return None


def _issue(path: str, code: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "path": path, "message": message}
    payload.update({key: value for key, value in details.items() if value is not None})
    return payload


def _candidate(
    *,
    relative: str,
    path: Path,
    body: str,
    metadata: dict[str, Any],
    as_of: datetime.date,
    stale_days: int,
) -> ProjectItem | None:
    status = (_scalar(metadata.get("status")) or "unknown").lower()
    if status in CLOSED_STATUSES:
        return None
    activity_date = _activity_date(metadata)
    age_days = (as_of - activity_date).days if activity_date is not None else None
    tasks = _open_tasks(body)
    blocked = status == "blocked"
    missing_date = activity_date is None
    stale = age_days is not None and age_days >= stale_days
    if not (blocked or missing_date or stale):
        return None

    reasons: list[str] = []
    if blocked:
        reasons.append("blocked")
    if missing_date:
        reasons.append("missing-activity-date")
    elif stale:
        reasons.append(f"stale:{age_days}-days")
    if tasks:
        reasons.append(f"open-tasks:{len(tasks)}")

    if blocked:
        priority = 0
    elif missing_date:
        priority = 1
    elif tasks:
        priority = 2
    else:
        priority = 3
    return ProjectItem(
        path=relative,
        title=_title(path, body),
        status=status,
        activity_date=activity_date,
        age_days=age_days,
        open_tasks=len(tasks),
        next_action=_next_action(body, tasks),
        reasons=tuple(reasons),
        priority=priority,
    )


def review_projects(
    vault: Path,
    *,
    as_of: datetime.date,
    stale_days: int = DEFAULT_STALE_DAYS,
    top_k: int = DEFAULT_TOP_K,
    scope: Path | None = None,
) -> dict[str, Any]:
    """Return an explainable queue without mutating the Vault."""
    root = vault.resolve()
    selected_scope = (scope or root).resolve()
    items: list[ProjectItem] = []
    issues: list[dict[str, Any]] = []
    files = 0
    projects = 0
    skipped = 0
    for path in _markdown_files(selected_scope):
        files += 1
        relative = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as exc:
            skipped += 1
            if len(issues) < MAX_ISSUES:
                issues.append(_issue(relative, "unreadable-note", str(exc)))
            continue
        parsed = parse_frontmatter(text, source=relative)
        if parsed.issue is not None:
            skipped += 1
            if len(issues) < MAX_ISSUES:
                issues.append(
                    _issue(
                        relative,
                        parsed.issue.code,
                        parsed.issue.message,
                        line=parsed.issue.line,
                        column=parsed.issue.column,
                    )
                )
            continue
        metadata = parsed.metadata or {}
        if _scalar(metadata.get("type")) != PROJECT_TYPE:
            continue
        projects += 1
        activity_date = _activity_date(metadata)
        if activity_date is not None and activity_date > as_of:
            skipped += 1
            if len(issues) < MAX_ISSUES:
                issues.append(
                    _issue(
                        relative,
                        "future-activity-date",
                        f"activity date {activity_date.isoformat()} is after "
                        f"--as-of {as_of.isoformat()}",
                    )
                )
            continue
        body = visible_markdown(parsed.body)
        item = _candidate(
            relative=relative,
            path=path,
            body=body,
            metadata=metadata,
            as_of=as_of,
            stale_days=stale_days,
        )
        if item is not None:
            items.append(item)

    items.sort(
        key=lambda item: (
            item.priority,
            -(item.age_days if item.age_days is not None else -1),
            -item.open_tasks,
            item.path,
        )
    )
    returned = items[:top_k]
    scope_relative = selected_scope.relative_to(root).as_posix()
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": "review-projects",
        "read_only": True,
        "scope": scope_relative or ".",
        "as_of": as_of.isoformat(),
        "stale_days": stale_days,
        "summary": {
            "files": files,
            "projects": projects,
            "candidates": len(items),
            "returned": len(returned),
            "skipped": skipped,
        },
        "items": [item.as_dict() for item in returned],
        "issues": issues,
        "truncated": len(items) > top_k,
    }


def _json_error(code: str, message: str) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "command": "review-projects",
            "error": {"code": code, "message": message},
        },
        ensure_ascii=False,
    )


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Build a read-only project revival queue for an Obsidian Vault."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian Vault")
    parser.add_argument("--scope", type=Path, help="Optional Vault-relative directory")
    parser.add_argument(
        "--as-of", help="Review date in ISO format (YYYY-MM-DD; default: today)"
    )
    parser.add_argument(
        "--stale-days", type=int, default=DEFAULT_STALE_DAYS,
        help=f"Days without activity (1-{MAX_STALE_DAYS})",
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"Projects to return (1-{MAX_TOP_K})",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    args = parser.parse_args(argv)

    def refuse(code: str, message: str) -> int:
        if args.json:
            print(_json_error(code, message))
        else:
            print(f"error: {message}", file=sys.stderr)
        return 2

    try:
        as_of = (
            datetime.date.fromisoformat(args.as_of)
            if args.as_of is not None
            else datetime.date.today()
        )
    except ValueError:
        return refuse("invalid-date", "--as-of must be an ISO calendar date (YYYY-MM-DD)")
    if not 1 <= args.stale_days <= MAX_STALE_DAYS:
        return refuse(
            "invalid-stale-days",
            f"--stale-days must be between 1 and {MAX_STALE_DAYS}",
        )
    if not 1 <= args.top_k <= MAX_TOP_K:
        return refuse("invalid-top-k", f"--top-k must be between 1 and {MAX_TOP_K}")
    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        return report_cli_violation(exc, param="vault", json_mode=args.json)
    if not (vault / ".obsidian").is_dir():
        return refuse("invalid-vault", "not an Obsidian Vault")
    selected_scope = vault
    if args.scope is not None:
        try:
            selected_scope = resolve_existing_within_vault(
                vault, args.scope, label="--scope"
            )
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--scope", json_mode=args.json)
        if not selected_scope.is_dir():
            return refuse("invalid-scope", "--scope must be a directory")

    payload = review_projects(
        vault,
        as_of=as_of,
        stale_days=args.stale_days,
        top_k=args.top_k,
        scope=selected_scope,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not payload["items"]:
        print("No projects need review.")
    else:
        for index, item in enumerate(payload["items"], start=1):
            reasons = ", ".join(item["reasons"])
            print(f"{index:>2}. {item['path']} [{item['status']}; {reasons}]")
            if item["next_action"]:
                print(f"    next: {item['next_action']}")
    if payload["issues"]:
        print(f"{len(payload['issues'])} note(s) skipped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
