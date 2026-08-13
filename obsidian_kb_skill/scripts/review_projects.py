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
from obsidian_kb_skill.scripts.note_catalog import (
    EXEMPT_NAMES,
    NON_INSTANCE_STATUSES as _NON_INSTANCE_STATUSES,
    PROJECT_NOTE_NEXT_ACTION_HEADINGS,
)
from obsidian_kb_skill.scripts.search_vault import (
    IGNORED_DIRECTORY_NAMES,
    parse_note_date,
)
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
# A finished project is finished in whatever language its author wrote the
# status in. An English-only set put `status: 已完成` back in the queue every
# review as `stale:N-days` — precisely the false positive this helper exists to
# avoid, in the language most of a bilingual Vault's notes use.
CLOSED_STATUSES = {
    "archived",
    "canceled",
    "cancelled",
    "closed",
    "completed",
    "done",
    "中止",
    "关闭",
    "取消",
    "完成",
    "已中止",
    "已关闭",
    "已取消",
    "已完成",
    "已归档",
    "已结束",
    "归档",
    "结束",
}
# These values describe a reusable project-shaped note, not a project lifecycle
# state. Keep them separate from CLOSED_STATUSES: a template never started and
# was not completed. Unknown states still remain visible by design.
#
# The set lives in `note_catalog` because the audit needs the same judgement:
# one policy, one definition. Re-exported here so existing callers and tests
# keep their import site.
NON_INSTANCE_STATUSES = _NON_INSTANCE_STATUSES
# "What is not knowledge" is one policy, so it has one definition. A second copy
# had already drifted: it spelled the archive folder as a literal instead of the
# shared constant, and it did not learn about the retrieval lexicon's folder
# when search did.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
FENCE_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")
OPEN_TASK_RE = re.compile(r"^[ \t]*[-*+][ \t]+\[[ \t]\][ \t]+(.+?)\s*$")
NEXT_ACTION_HEADINGS = {
    heading.lower() for heading in PROJECT_NOTE_NEXT_ACTION_HEADINGS
}


@dataclass(frozen=True)
class ProjectItem:
    path: str
    title: str
    status: str
    activity_date: datetime.date | None
    age_days: int | None
    open_tasks: int
    # Unchecked boxes inside the note's own next-actions section, or `None`
    # when it has no such section. `None` is not zero: one says the note put
    # nothing there, the other says it never claimed a place for its todos.
    open_tasks_in_next_actions: int | None
    next_action: str | None
    # The heading `next_action` was taken from. A checklist nested inside the
    # next-actions section cannot be separated by structure, so the reader is
    # given the one fact that separates it: what the author called it.
    next_action_heading: str | None
    reasons: tuple[str, ...]
    priority: int

    @property
    def ranking_tasks(self) -> int:
        """The count that ordered the queue. Reported so it can be checked."""
        if self.open_tasks_in_next_actions is None:
            return self.open_tasks
        return self.open_tasks_in_next_actions

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
            "open_tasks_in_next_actions": self.open_tasks_in_next_actions,
            "open_tasks_scope": (
                "whole-note"
                if self.open_tasks_in_next_actions is None
                else "next-actions"
            ),
            "next_action": self.next_action,
            "next_action_heading": self.next_action_heading,
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


def _next_action_sections(body: str) -> list[tuple[int, int]]:
    """Line ranges of every section the note calls its next actions.

    Empty when the note has no such heading — which is a different state from
    having one that holds nothing, and the two are read differently below.
    """
    lines = body.splitlines()
    sections: list[tuple[int, int]] = []
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
        sections.append((index, end))
    return sections


def _tasks_in_sections(
    tasks: list[tuple[int, str]], sections: list[tuple[int, int]]
) -> list[tuple[int, str]]:
    return [
        task
        for task in tasks
        if any(start < task[0] < end for start, end in sections)
    ]


def _heading_above(body: str, line: int) -> str | None:
    """The innermost heading a line sits under, or `None` above the first one."""
    found: str | None = None
    for index, text in enumerate(body.splitlines()):
        if index >= line:
            break
        match = HEADING_RE.match(text)
        if match:
            found = match.group(2).strip()
    return found


def _next_action(
    body: str,
    tasks: list[tuple[int, str]],
    sections: list[tuple[int, int]],
    scoped: list[tuple[int, str]] | None,
) -> tuple[str | None, str | None]:
    """The project's next action and the heading it was taken from.

    A note that declares a next-actions section has said where its todos live.
    When that section holds no checkbox, the honest answer is none: the radar
    reads checkboxes, not the numbered list a project may have written there
    instead. Reaching past the section for the first checkbox anywhere is how a
    reusable checklist's question came back as one project's next step (#109).

    The heading is returned because scoping alone does not settle the case that
    filed #109: on the reference Vault that checklist is *nested inside* the
    next-actions section, so no boundary separates it. Naming its heading is
    what a reader needs — `可复用的项目落地检查表` reads very differently from
    `P0：下一次迭代前完成`, and that judgement is theirs, not the radar's.

    A note with no such section is making no claim about placement, so the
    original whole-note fallback still applies.
    """
    if sections:
        chosen = scoped[0] if scoped else None
    else:
        chosen = tasks[0] if tasks else None
    if chosen is None:
        return None, None
    return _bounded_action(chosen[1]), _heading_above(body, chosen[0])


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
    if status in CLOSED_STATUSES or status in NON_INSTANCE_STATUSES:
        return None
    activity_date = _activity_date(metadata)
    age_days = (as_of - activity_date).days if activity_date is not None else None
    tasks = _open_tasks(body)
    # A checkbox is Markdown syntax; a todo is a claim about *this* project.
    # Notes hold checklists, examples and templates too, so the count that
    # ranks the queue is the one the note itself scoped — and the whole-note
    # count is still reported, because dropping it would trade one unexplained
    # number for another.
    sections = _next_action_sections(body)
    scoped = _tasks_in_sections(tasks, sections) if sections else None
    ranking_tasks = scoped if scoped is not None else tasks
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
    if ranking_tasks:
        reasons.append(f"open-tasks:{len(ranking_tasks)}")

    if blocked:
        priority = 0
    elif missing_date:
        priority = 1
    elif ranking_tasks:
        priority = 2
    else:
        priority = 3
    action, action_heading = _next_action(body, tasks, sections, scoped)
    return ProjectItem(
        path=relative,
        title=_title(path, body),
        status=status,
        activity_date=activity_date,
        age_days=age_days,
        open_tasks=len(tasks),
        open_tasks_in_next_actions=len(scoped) if scoped is not None else None,
        next_action=action,
        next_action_heading=action_heading,
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
    # Validated here and not only in `main`, exactly as `search_vault` does. A
    # library caller handing in an outside scope used to reach `relative_to` and
    # raise a bare ValueError carrying an absolute filesystem path: an unhandled
    # crash where the contract promises a refusal, and a path leak in a Skill
    # whose reference tells the Agent not to expose unrelated absolute paths.
    root = validate_vault_root(vault)
    selected_scope = (
        resolve_existing_within_vault(root, scope, label="scope")
        if scope is not None
        else root
    )
    if not selected_scope.is_dir():
        raise ValueError("scope must be a directory")
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
        status = (_scalar(metadata.get("status")) or "unknown").lower()
        if status in NON_INSTANCE_STATUSES:
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
            -item.ranking_tasks,
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
