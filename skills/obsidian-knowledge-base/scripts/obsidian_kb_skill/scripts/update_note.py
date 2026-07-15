#!/usr/bin/env python3
"""Update (or initialize) a single task-memory note for multi-agent handoffs.

Constraint-based counterpart to create_note.py for the "Task Memory Workflow"
in core/OBSIDIAN_KB.md. It edits only structured frontmatter fields and appends
to a bounded `## Log` section — it never clobbers the prose the agent writes.

Read-only by default (prints a diff/preview); pass --apply to write.
If the note does not exist yet, it is initialized from the task-memory template
(an "upsert"), so a single command both starts and updates a task.

Agents without a native file-write tool should call THIS instead of writing
their own script.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from obsidian_kb_skill.scripts.backup_policy import (
    BackupPolicy,
    CleanupResult,
    DEFAULT_KEEP_PER_NOTE,
    load_backup_policy,
    prune_backups,
)
from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.create_note import (
    InvalidFrontmatterError,
    audit_note,
    build_note,
    report_invalid_frontmatter,
    split_frontmatter,
    validate_vault,
)
from obsidian_kb_skill.scripts.suggest_links import suggest_links
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    PathNotFoundError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)

MAX_LOG_LINES = 30

TASK_DEFAULT_BODY = (
    "## TL;DR\n"
    "<2 sentences: what this task is and where it stands>\n\n"
    "## Decisions (crystallized)\n"
    "- ...\n\n"
    "## Open\n"
    "- ...\n\n"
    "## Log\n"
)


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _backup_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")


def backup_note(
    vault: Path,
    note_path: Path,
    *,
    timestamp: str | None = None,
) -> Path:
    """Copy an existing note byte-for-byte into a unique in-Vault backup path."""
    relative = note_path.relative_to(vault)
    base = timestamp or _backup_timestamp()
    suffix = 1
    while True:
        directory = base if suffix == 1 else f"{base}-{suffix}"
        backup_relative = Path(".obsidian-kb-backups") / directory / relative
        backup_path = resolve_target_within_vault(
            vault, backup_relative, label="backup path"
        )
        if not backup_path.exists():
            break
        suffix += 1
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(note_path.read_bytes())
    return backup_path


def _extend_list(existing: Any, additions: list[str]) -> list[str]:
    """Append additions to a list, de-duplicating while preserving order."""
    seq = list(existing) if isinstance(existing, list) else []
    for item in additions:
        if item and item not in seq:
            seq.append(item)
    return seq


def _replace_in_list(
    existing: Any, old_sub: str, new: str
) -> tuple[list[str], bool]:
    """Mem0-style conflict resolution: replace the first decision containing
    `old_sub` with `new`. Returns (list, replaced?). If no match, `new` is
    appended (upsert) so the command never silently drops a correction."""
    seq = list(existing) if isinstance(existing, list) else []
    for i, item in enumerate(seq):
        if old_sub and old_sub in str(item):
            seq[i] = new
            return seq, True
    if new and new not in seq:
        seq.append(new)
    return seq, False


def _append_log(body: str, line: str, max_lines: int = MAX_LOG_LINES) -> str:
    """Insert `line` at the bottom of the `## Log` section (chronological order),
    creating the section if needed, and cap to the last `max_lines` entries."""
    lines = body.splitlines()
    log_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == "## Log"), None
    )
    if log_idx is None:
        if body and not body.endswith("\n"):
            body += "\n"
        return body + "\n## Log\n" + line + "\n"

    # Block end = next heading or EOF.
    end = len(lines)
    for j in range(log_idx + 1, len(lines)):
        if lines[j].startswith("## ") and lines[j].strip() != "## Log":
            end = j
            break
    # Insert at the bottom of the block (skip trailing blanks).
    insert_at = end
    while insert_at > log_idx and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, line)

    # Cap: keep only the last `max_lines` dash-entries (drop the oldest at top).
    new_end = len(lines)
    for j in range(insert_at + 1, len(lines)):
        if lines[j].startswith("## ") and lines[j].strip() != "## Log":
            new_end = j
            break
    block = lines[log_idx + 1:new_end]
    log_entries = [ln for ln in block if ln.startswith("- ")]
    if len(log_entries) > max_lines:
        drop = len(log_entries) - max_lines
        kept_block = []
        removed = 0
        for ln in block:
            if ln.startswith("- ") and removed < drop:
                removed += 1
                continue
            kept_block.append(ln)
        lines[log_idx + 1:new_end] = kept_block
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    p = argparse.ArgumentParser(
        description="Update or initialize a task-memory note (handoff memory)."
    )
    p.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    p.add_argument(
        "--note", required=True,
        help="Path to the TASK.md (absolute, or relative to the vault)",
    )
    p.add_argument("--status", help="Set status: active | blocked | done")
    p.add_argument("--step", help="Set the current working step")
    p.add_argument(
        "--add-decision", action="append", default=[],
        help="Append a crystallized decision (repeatable)",
    )
    p.add_argument(
        "--replace-decision", action="append", default=[],
        help="Conflict resolution: replace a decision containing OLD with NEW "
             "(format 'OLD::NEW'); appends NEW if no match (repeatable)",
    )
    p.add_argument(
        "--add-constraint", action="append", default=[],
        help="Append a constraint (repeatable)",
    )
    p.add_argument(
        "--add-open", action="append", default=[],
        help="Append an open item / blocker (repeatable)",
    )
    p.add_argument(
        "--add-agent", action="append", default=[],
        help="Append an agent that touched this task (repeatable)",
    )
    p.add_argument(
        "--add-artifact", action="append", default=[],
        help="Append a wikilink/artifact path (repeatable)",
    )
    p.add_argument("--by", help="Agent label for the Log line, e.g. Codex")
    p.add_argument("--log", help="Append a Log line (handoff trail)")
    p.add_argument(
        "--apply", action="store_true",
        help="Actually write the file (default is a dry run that only prints)",
    )
    p.add_argument(
        "--no-audit", action="store_true",
        help="Skip the automatic post-write audit (runs by default after --apply)",
    )
    p.add_argument(
        "--suggest-links", action="store_true",
        help="After writing, print link suggestions reusing suggest_links.py",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit a single JSON object instead of human-readable text",
    )
    args = p.parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    validate_vault(vault)

    # Enforce the Vault boundary on the note path. An existing note is resolved
    # with symlinks followed (so a symlink-to-outside is caught); a not-yet
    # existing note (upsert target) is resolved as a new target so a symlink
    # *parent* cannot redirect the write outside the Vault. Both paths funnel
    # through vault_paths — no ad-hoc join/resolve here.
    try:
        note_path = resolve_existing_within_vault(vault, args.note, label="--note")
    except PathNotFoundError:
        # Not-yet-existing note (upsert target): validate as a new path.
        try:
            note_path = resolve_target_within_vault(vault, args.note, label="--note")
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--note", json_mode=args.json)
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--note", json_mode=args.json)

    # --- Load or initialize -------------------------------------------------
    if note_path.exists():
        raw = note_path.read_text(encoding="utf-8")
        try:
            meta, body = split_frontmatter(
                raw, source=note_path.relative_to(vault).as_posix()
            )
        except InvalidFrontmatterError as exc:
            return report_invalid_frontmatter(exc, json_mode=args.json)
        action = "update"
    else:
        # Upsert: build a fresh task-memory note from the template.
        folder = str(note_path.parent.relative_to(vault))
        title = note_path.stem
        date = datetime.date.today().isoformat()
        _, rendered = build_note(
            note_type="task-memory",
            title=title,
            date=date,
            body=TASK_DEFAULT_BODY,
            given_meta={"task-id": title, "status": "active",
                        "task-memory": "enabled", "agents": []},
            folder=folder,
        )
        meta, body = split_frontmatter(rendered)
        action = "init"

    # --- Apply updates ------------------------------------------------------
    meta["task-memory"] = "enabled"  # touching it implies opt-in
    if args.status:
        meta["status"] = args.status
    if args.step:
        meta["step"] = args.step
    if args.add_decision:
        meta["decisions"] = _extend_list(meta.get("decisions"), args.add_decision)
    for pair in args.replace_decision:
        if "::" not in pair:
            if not args.json:
                print(f"(skip) --replace-decision needs 'OLD::NEW': {pair!r}",
                      file=sys.stderr)
            continue
        old_sub, new = pair.split("::", 1)
        replaced = _replace_in_list(meta.get("decisions"), old_sub, new)
        meta["decisions"], _ = replaced
    if args.add_constraint:
        meta["constraints"] = _extend_list(meta.get("constraints"), args.add_constraint)
    if args.add_open:
        meta["open"] = _extend_list(meta.get("open"), args.add_open)
    if args.add_agent:
        meta["agents"] = _extend_list(meta.get("agents"), args.add_agent)
    if args.add_artifact:
        meta["artifacts"] = _extend_list(meta.get("artifacts"), args.add_artifact)
    meta["updated"] = _now()

    if args.log:
        label = f"[{args.by}] " if args.by else ""
        body = _append_log(body, f"- {_now()} {label}{args.log}")

    dump = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    rendered = f"---\n{dump}\n---\n"
    if body and not body.startswith("\n"):
        rendered += "\n"
    rendered += body

    result: dict[str, Any] = {
        "action": action,
        "path": str(note_path),
        "rendered": rendered,
        "applied": False,
        "dry_run": not args.apply,
        "backup": None,
        "backup_cleanup": None,
        "audit": None,
        "suggested_links": None,
    }

    if not args.apply:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"action: {action}")
            print(f"path  : {note_path}")
            print("---- resulting note (preview) ----")
            print(rendered)
            print("----------------------------------")
            print("(dry run) pass --apply to write the file.")
        return 0

    backup_path: Path | None = None
    if action == "update":
        try:
            backup_path = backup_note(vault, note_path)
        except VaultPathError as exc:
            return report_cli_violation(exc, param="backup", json_mode=args.json)
        except OSError as exc:
            if args.json:
                print(
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "ok": False,
                            "command": "update-note",
                            "error": {
                                "code": "BACKUP_FAILED",
                                "message": f"backup failed: {exc}",
                                "details": {},
                            },
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"error: backup failed: {exc}", file=sys.stderr)
            return 3
        result["backup"] = backup_path.relative_to(vault).as_posix()

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_bytes(rendered.encode("utf-8"))
    result["applied"] = True

    # Cleanup is deliberately in-process and post-commit: the agent never lists
    # or deletes backups, and a cleanup problem must not invite a retry of a
    # note write that already succeeded.
    policy = BackupPolicy(DEFAULT_KEEP_PER_NOTE, False)
    try:
        policy = load_backup_policy()
        cleanup = prune_backups(
            vault,
            policy,
            protected=backup_path if action == "update" else None,
        )
    except Exception as exc:  # noqa: BLE001 - committed writes must stay successful
        cleanup = CleanupResult(
            keep_per_note=policy.keep_per_note,
            scanned=0,
            deleted=0,
            warnings=(f"backup cleanup failed after note write: {exc}",),
        )
    result["backup_cleanup"] = asdict(cleanup)
    for warning in cleanup.warnings:
        print(f"warning: backup cleanup: {warning}", file=sys.stderr)

    if not args.no_audit:
        findings = audit_note(vault, note_path)
        result["audit"] = {
            "ok": not findings,
            "count": len(findings),
            "findings": [
                {"code": f.code, "path": f.path, "message": f.message}
                for f in findings
            ],
        }
        if not args.json:
            rel = note_path.relative_to(vault)
            if findings:
                print(f"AUDIT: {len(findings)} issue(s) found in {rel}:")
                for finding in findings:
                    print(f"  - {finding.code}: {finding.message}")
            else:
                print(f"AUDIT: OK — no issues in {rel}")

    if args.suggest_links:
        recs = suggest_links(vault, note_path)
        result["suggested_links"] = [
            {"path": p.relative_to(vault).as_posix(), "score": s, "reasons": r}
            for p, s, r in recs
        ]
        if not args.json:
            if recs:
                print("SUGGESTED LINKS:")
                for path, score, reasons in recs:
                    print(f"  {score:>3}  {path.relative_to(vault).as_posix()}")
                    for reason in reasons:
                        print(f"        - {reason}")
            else:
                print("SUGGESTED LINKS: none")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{action}d: {note_path}")
        if result["backup"]:
            print(f"backup : {result['backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
