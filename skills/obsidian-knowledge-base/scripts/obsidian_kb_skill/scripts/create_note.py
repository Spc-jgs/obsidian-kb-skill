#!/usr/bin/env python3
"""Create a single Obsidian note with validated frontmatter and a safe write.

Constraint-based wrapper around the note-creation rules in core/OBSIDIAN_KB.md.
Agents without a native file-write tool should call THIS script instead of
writing their own one-off file-writing script.

Read-only by default: it prints the resolved path, the frontmatter that would be
written, and the body, but writes nothing. Pass --apply to actually create the
file. It never overwrites an existing file (a numeric suffix is appended).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.capture_receipt import (
    CAPTURE_DEPTHS,
    CaptureReceiptError,
    load_receipt_file,
    parse_receipt_json,
    requires_capture_receipt,
    validate_capture_receipt,
)
from obsidian_kb_skill.scripts.frontmatter import (
    FrontmatterIssue,
    parse_frontmatter,
    portable_yaml_scalars,
)
from obsidian_kb_skill.scripts.note_catalog import (
    DEFAULT_TAG_BY_TYPE,
    TYPE_TO_FOLDER,
    TYPE_TO_TEMPLATE,
)
from obsidian_kb_skill.scripts.metadata_quality import is_meaningful_metadata
from obsidian_kb_skill.scripts.folder_index_policy import (
    StaticIndexEntry,
    append_static_index_entry,
)
from obsidian_kb_skill.scripts.audit_vault import Finding, audit_note, audit_note_text
from obsidian_kb_skill.scripts.suggest_links import suggest_links
from obsidian_kb_skill.scripts import preflight_cache
from obsidian_kb_skill.scripts.preflight_cache import PreflightCacheError
from obsidian_kb_skill.scripts.template_contract import (
    heading_level_repair,
    template_path,
    template_sha256,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    PathNotFoundError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    structured_error,
    validate_vault_root,
)

# Codes the writer refuses rather than reports. The audit grades twenty codes
# `defect`, and most of them describe the Vault rather than this note: #159
# settled that a wikilink to an unwritten note is standard Obsidian usage, and a
# duplicate project note is about what the Vault already holds. Refusing every
# defect would make it impossible to create a note that points forward. What is
# refused here is the narrower class the author clears by rewriting the body —
# a template that shipped instead of being executed.
REFUSED_ON_APPLY = frozenset(
    {
        "residual-template-instruction",
        "unresolved-template-placeholder",
    }
)


def sha256_argument(value: str) -> str:
    """Accept only the canonical digest format emitted by template-contract."""
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise argparse.ArgumentTypeError(
            "must be exactly 64 lowercase hexadecimal characters"
        )
    return value

# Extra frontmatter fields written only when the user's template does NOT already
# define them. These are minimal placeholders so the file still parses as the
# expected type — users are expected to define their own fields in
# {VAULT}/Templates/<Name>.md. The vault template is the single source of truth;
# this dict is just a safety net for new notes whose template was never created.
EXTRA_FIELDS: dict[str, dict[str, Any]] = {
    "daily-note": {"related": []},
    "meeting-note": {"participants": [], "project": "", "related": []},
    "learning-note": {"source": "", "category": "", "related": []},
    "web-clip": {
        "source": "",
        "author": "",
        "published": "",
        "capture_depth": "standard",
        "related": [],
    },
    "insight-note": {"source": "", "related": []},
    "conversation-digest": {"source": "", "project": "", "related": []},
    "project-note": {"status": "active", "related": []},
    "person-note": {"role": "", "organization": "", "related": []},
    "task-memory": {
        "status": "active", "task-memory": "enabled", "agents": [],
        "decisions": [], "constraints": [], "artifacts": [], "open": [],
    },
}


class InvalidTaskMemoryFolderError(ValueError):
    """A task-memory destination that is not a real `Tasks/<slug>` path."""

    code = "invalid-task-memory-folder"

    def __init__(self, folder: str) -> None:
        self.folder = folder
        super().__init__(
            "task-memory requires a normalized lowercase Tasks/<slug> "
            f"operational path; resolved to {folder}"
        )


class InvalidFrontmatterError(ValueError):
    """Malformed YAML in a closed Markdown frontmatter block."""

    code = "invalid-frontmatter"

    def __init__(self, issue: FrontmatterIssue) -> None:
        self.source = issue.source
        self.line = issue.line
        self.column = issue.column
        self.message = issue.message
        super().__init__(self.message)

    def payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "source": self.source,
                "line": self.line,
                "column": self.column,
                "message": self.message,
            }
        }


def report_invalid_frontmatter(
    error: InvalidFrontmatterError, *, json_mode: bool
) -> int:
    if json_mode:
        print(json.dumps(error.payload(), ensure_ascii=False, indent=2))
    else:
        location = ""
        if error.line is not None and error.column is not None:
            location = f" at line {error.line}, column {error.column}"
        print(
            f"error: invalid YAML frontmatter in {error.source}{location}: "
            f"{error.message}",
            file=sys.stderr,
        )
    return 2


def validate_vault(vault: Path, *, json_mode: bool = False) -> None:
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        exc = InvalidVaultRootError(f"not an Obsidian vault: {vault}")
        if json_mode:
            print(json.dumps(structured_error(exc, param="vault"), ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not (vault / "Templates").is_dir():
        print(
            "warning: Templates/ folder not found; proceeding without template check.",
            file=sys.stderr,
        )


def sanitize_filename(name: str) -> str:
    # Drop characters that are unsafe in file names; keep unicode letters/spaces.
    unsafe = '/\\:*?"<>|'
    cleaned = "".join("_" if ch in unsafe else ch for ch in name).strip().strip(".")
    return cleaned or "untitled"


def is_task_memory_folder(note_type: str, folder: str) -> bool:
    """Allow only the explicit operational Tasks/<slug> initialization shape."""
    if note_type != "task-memory" or "\\" in folder or Path(folder).is_absolute():
        return False
    raw_parts = folder.split("/")
    return (
        len(raw_parts) == 2
        and raw_parts[0] == "Tasks"
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", raw_parts[1]) is not None
    )


def initialize_task_memory_folder(vault: Path, folder: str) -> tuple[Path, ...]:
    """Create only Tasks/<slug>, returning directories created for rollback."""
    target = resolve_target_within_vault(
        vault, folder, label="task-memory destination folder"
    )
    created: list[Path] = []
    try:
        for directory in (target.parent, target):
            if directory.exists():
                continue
            directory.mkdir()
            created.append(directory)
        verified = resolve_existing_within_vault(
            vault, folder, label="task-memory destination folder"
        )
        if verified != target or not verified.is_dir():
            raise OSError("task-memory destination changed during initialization")
        # The shape rule is checked against the requested string, so a symlink
        # named `Tasks` filed operational notes outside the Tasks tree while
        # still passing validation. Require the resolved path to satisfy it too.
        resolved_relative = verified.relative_to(validate_vault_root(vault))
        if not is_task_memory_folder("task-memory", resolved_relative.as_posix()):
            raise InvalidTaskMemoryFolderError(resolved_relative.as_posix())
    except Exception:
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return tuple(created)


def cleanup_empty_directories(paths: tuple[Path, ...]) -> None:
    for directory in reversed(paths):
        try:
            directory.rmdir()
        except OSError:
            pass


def split_frontmatter(
    text: str, *, source: str = "input"
) -> tuple[dict[str, Any], str]:
    """Return (metadata, body) splitting a leading YAML frontmatter block if present."""
    result = parse_frontmatter(text, source=source)
    if result.issue is not None and result.issue.code == "invalid-frontmatter":
        raise InvalidFrontmatterError(result.issue)
    if result.issue is not None or not result.present:
        return {}, result.normalized_text
    return result.metadata or {}, result.body


def missing_required_metadata(note_type: str, metadata: dict[str, Any]) -> list[str]:
    """Return required fields that are empty or vague placeholders."""
    if note_type != "web-clip":
        return []
    return [
        field
        for field in ("source", "author", "published")
        if not is_meaningful_metadata(metadata.get(field))
    ]


def report_invalid_utf8_input(source: str, *, json_mode: bool) -> int:
    """Report invalid Unicode input without leaking a Python traceback."""
    message = f"{source} must contain valid UTF-8"
    if json_mode:
        print(json.dumps({
            "error": {"code": "invalid-utf8-input", "message": message}
        }, ensure_ascii=False))
    else:
        print(f"error: {message}", file=sys.stderr)
    return 2


def finding_payload(findings: list[Finding]) -> dict[str, Any]:
    """Return the stable machine-readable shape for note-level findings."""
    return {
        "ok": not findings,
        "count": len(findings),
        "findings": [
            {"code": item.code, "path": item.path, "message": item.message}
            for item in findings
        ],
    }


def stage_preflight_content(
    vault: Path,
    sha256: str,
    rendered: str,
    rendered_bytes: bytes,
    *,
    raw_input: str | None,
    note_type: str,
    title: str,
) -> dict[str, Any]:
    """Report content identity, staging the input so apply can reference it."""
    reusable = raw_input is not None and preflight_cache.stage(
        vault, sha256, raw_input, note_type=note_type, title=title
    )
    return {
        "sha256": sha256,
        "utf8_bytes": len(rendered_bytes),
        "line_count": len(rendered.splitlines()),
        "reusable": reusable,
    }


def heading_fix_proposal(
    vault: Path,
    note_type: str,
    raw_input: str | None,
    findings: list[Finding],
    sha256: str,
) -> dict[str, Any] | None:
    """Describe the level-only repair that would clear a heading finding.

    Reported, never applied: the agent asks for the rewrite explicitly. Without
    this the only remedy for one wrong `#` was to resend the whole document.
    """
    if raw_input is None or not any(
        finding.code == "missing-template-heading" for finding in findings
    ):
        return None
    contract = template_path(vault, note_type)
    if contract is None or not contract.is_file():
        return None
    repair = heading_level_repair(raw_input, contract.read_text(encoding="utf-8"))
    if repair is None:
        return None
    return {
        "kind": "heading-level-mismatch",
        "message": (
            "every required section exists at the wrong ATX level; rerun "
            f"preflight with --from-preflight {sha256} --fix-heading-levels "
            "to apply these edits without resending the body"
        ),
        "edits": repair[1],
    }


def preflight_validation(
    vault: Path,
    note_type: str,
    raw_input: str | None,
    findings: list[Finding],
    sha256: str,
) -> dict[str, Any]:
    """Return note-level findings plus a repair the agent can ask for."""
    payload = finding_payload(findings)
    proposal = heading_fix_proposal(vault, note_type, raw_input, findings, sha256)
    if proposal is not None:
        payload["suggested_fix"] = proposal
    return payload


def print_preview(vault: Path, folder: str, dest: Path, rendered: str) -> None:
    """Print the human-readable dry-run preview."""
    print(f"vault : {vault}")
    print(f"folder: {folder}")
    print(f"path  : {dest}")
    print("---- frontmatter + body (preview) ----")
    print(rendered)
    print("--------------------------------------")


def _load_user_template(vault: Path | None, note_type: str) -> tuple[dict[str, Any], str] | None:
    """Read {vault}/Templates/<Name>.md if it exists; return (frontmatter, body).

    Body has every `{{date}}` placeholder substituted with today's date string
    supplied by the caller is NOT done here — the caller already knows the date
    and we want to be explicit about substitution at the call site.

    Returns None when the vault has no Templates/ folder, the type has no
    conventional template name, or the template file is missing. Callers then
    fall back to a minimal body so the note is still usable.
    """
    if vault is None:
        return None
    fname = TYPE_TO_TEMPLATE.get(note_type)
    if not fname:
        return None
    path = vault / "Templates" / fname
    if not path.is_file():
        return None
    return split_frontmatter(
        path.read_text(encoding="utf-8"),
        source=f"template {path.as_posix()}",
    )


def _substitute_date(text: str, date: str) -> str:
    """Replace every {{date}} placeholder with the actual date string."""
    return text.replace("{{date}}", date)


def _render_template_body(text: str, *, date: str, title: str) -> str:
    """Fill template variables and bind its first H1 to the requested title."""
    heading = " ".join(title.splitlines()).strip() or "untitled"
    rendered = _substitute_date(text, date).replace("{{title}}", heading)
    lines = rendered.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"# {heading}{newline}"
            return "".join(lines)
    separator = "" if not rendered or rendered.startswith("\n") else "\n"
    return f"# {heading}\n{separator}{rendered}"


def build_note(
    *,
    note_type: str,
    title: str,
    date: str,
    body: str,
    given_meta: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    folder: str | None = None,
    vault: Path | None = None,
) -> tuple[str, str]:
    """Return (folder, rendered_markdown) for the note.

    Body resolution order:
      1. Explicit `body` argument (from --content-file / --stdin) wins.
      2. Otherwise, the user's {vault}/Templates/<Name>.md is used as the body
         (its frontmatter is merged into the note's frontmatter, so the user's
         template can introduce extra fields and they'll be preserved on write).
      3. If no user template exists, a minimal `# title\\n\\n` body is used.

    Frontmatter resolution order: type defaults < user template frontmatter <
    given_meta (stdin/content-file) < explicit CLI overrides. This means a user
    adding fields to their template (e.g. a `mood:` field on Daily Note) will
    see them appear on every new note, while input frontmatter can fill those
    fields for one invocation.
    """
    target = folder or TYPE_TO_FOLDER.get(note_type)
    if not target:
        raise ValueError(
            f"unknown type '{note_type}' and no --folder given. "
            f"Known types: {', '.join(sorted(TYPE_TO_FOLDER))}"
        )

    user_template = _load_user_template(vault, note_type)
    user_tpl_meta, user_tpl_body = user_template if user_template else ({}, "")

    # Body: explicit body wins. A template body has date/title variables filled
    # and its first H1 is the requested note title; user-owned explicit content
    # is never rewritten.
    if body.strip():
        final_body = body
    elif user_tpl_body:
        final_body = _render_template_body(user_tpl_body, date=date, title=title)
    else:
        final_body = f"# {title}\n"

    # Frontmatter merge (lowest -> highest precedence).
    meta: dict[str, Any] = {}
    meta.update(EXTRA_FIELDS.get(note_type, {}))
    if user_tpl_meta:
        meta.update(user_tpl_meta)
    if given_meta:
        meta.update(given_meta)
    # Explicit CLI overrides always win.
    meta["type"] = note_type
    meta["date"] = date
    if tags is not None:
        meta["tags"] = tags
    if not meta.get("tags"):
        meta["tags"] = [DEFAULT_TAG_BY_TYPE.get(note_type, "note")]
    if "related" not in meta:
        meta["related"] = []
    meta = portable_yaml_scalars(meta)

    dump = yaml.safe_dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    ).strip()
    rendered = f"---\n{dump}\n---\n"
    if final_body and not final_body.startswith("\n"):
        rendered += "\n"
    rendered += final_body
    return target, rendered


def destination_candidates(vault: Path, folder: str, filename: str) -> Iterator[Path]:
    """Yield the base destination followed by numeric-suffix alternatives."""
    dest_folder = vault / folder
    base = dest_folder / filename
    yield base
    index = 2
    while True:
        yield dest_folder / f"{base.stem}-{index}{base.suffix}"
        index += 1


def resolve_dest(vault: Path, folder: str, filename: str) -> Path:
    """Predict the first available destination for a dry-run preview."""
    return next(candidate for candidate in destination_candidates(vault, folder, filename)
                if not candidate.exists())


def write_new_note(
    vault: Path,
    folder: str,
    filename: str,
    rendered_bytes: bytes,
) -> Path:
    """Create one note exclusively, retrying suffixes when another writer wins."""
    for candidate in destination_candidates(vault, folder, filename):
        try:
            with candidate.open("xb") as handle:
                handle.write(rendered_bytes)
            return candidate
        except FileExistsError:
            continue
    raise AssertionError("unreachable destination candidate loop")


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Create one Obsidian note with validated frontmatter (never overwrites)."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian vault")
    parser.add_argument("--type", required=True, help="Note type slug, e.g. insight-note")
    parser.add_argument("--title", required=True, help="Short note title (becomes filename)")
    parser.add_argument("--folder", help="Override the routed target folder")
    parser.add_argument(
        "--content-file", type=Path,
        help="Path to complete Markdown inside the Vault (frontmatter is merged, "
             "explicit values win)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read complete UTF-8 Markdown from standard input; optional frontmatter is merged",
    )
    parser.add_argument(
        "--from-preflight",
        type=sha256_argument,
        help="Reuse the content a previous preflight staged under this SHA-256 "
             "instead of resending the body; the rerender must hash identically",
    )
    parser.add_argument(
        "--fix-heading-levels",
        action="store_true",
        help="Preflight only: rewrite the ATX level of headings whose text "
             "already matches the Vault template, and report every edit",
    )
    parser.add_argument("--tags", help="Comma-separated tags overriding the type default")
    parser.add_argument("--date", help="Date (YYYY-MM-DD); defaults to today")
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write the file (default is a dry run that only prints)",
    )
    parser.add_argument(
        "--no-audit", action="store_true",
        help="Skip the automatic post-write audit (runs by default after --apply)",
    )
    parser.add_argument(
        "--suggest-links", action="store_true",
        help="After writing, print link suggestions reusing suggest_links.py "
             "(requires --apply; the note must exist on disk to score)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit a single JSON object instead of human-readable text",
    )
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="With --apply, emit JSON without the rendered Markdown body",
    )
    parser.add_argument(
        "--preflight-json",
        action="store_true",
        help="Dry-run with final metadata, content identity, and validation "
             "without echoing the Markdown body",
    )
    parser.add_argument(
        "--expect-template-sha256",
        type=sha256_argument,
        help="Reject the operation if the conventional Vault template changed",
    )
    receipt_input = parser.add_mutually_exclusive_group()
    receipt_input.add_argument(
        "--capture-receipt-json",
        help="Content-bound semantic evidence required for a finished web clip",
    )
    receipt_input.add_argument(
        "--capture-receipt-file",
        type=Path,
        help="Path to a bounded UTF-8 semantic receipt JSON file",
    )
    parser.add_argument(
        "--expect-capture-receipt-sha256",
        type=sha256_argument,
        help="On apply, require the exact semantic receipt accepted by preflight",
    )
    args = parser.parse_args(argv)
    json_mode = args.json or args.compact_json or args.preflight_json

    if args.preflight_json and (args.apply or args.json or args.compact_json):
        print(json.dumps({
            "error": {
                "code": "invalid-output-mode",
                "message": (
                    "--preflight-json cannot be combined with --apply, --json, "
                    "or --compact-json"
                ),
            }
        }, ensure_ascii=False, indent=2))
        return 2

    if args.compact_json and not args.apply:
        print(json.dumps({
            "error": {
                "code": "compact-json-requires-apply",
                "message": "--compact-json requires --apply",
            }
        }, ensure_ascii=False, indent=2))
        return 2

    if args.from_preflight and (args.stdin or args.content_file):
        print(json.dumps({
            "error": {
                "code": "conflicting-content-source",
                "message": (
                    "--from-preflight replaces the body; do not combine it with "
                    "--stdin or --content-file"
                ),
            }
        }, ensure_ascii=False, indent=2))
        return 2

    # A repair is a dry-run proposal. Restricting it to preflight means content
    # is never silently rewritten on the way to disk: the agent sees the edits
    # and the new hash first, then applies that hash deliberately.
    if args.fix_heading_levels and not args.preflight_json:
        print(json.dumps({
            "error": {
                "code": "fix-requires-preflight",
                "message": "--fix-heading-levels requires --preflight-json",
            }
        }, ensure_ascii=False, indent=2))
        return 2

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        if json_mode:
            print(json.dumps(structured_error(exc, param="vault"), ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    validate_vault(vault, json_mode=json_mode)

    if args.expect_template_sha256:
        current_template = template_path(vault, args.type)
        actual_sha256 = None
        if current_template is not None:
            try:
                actual_sha256 = template_sha256(
                    current_template.read_text(encoding="utf-8")
                )
            except UnicodeError:
                actual_sha256 = None
        if actual_sha256 != args.expect_template_sha256:
            error = {
                "error": {
                    "code": "template-changed",
                    "message": (
                        "the Vault template changed after its contract was read; "
                        "read the contract again before creating the note"
                    ),
                    "note_type": args.type,
                    "expected_sha256": args.expect_template_sha256,
                    "actual_sha256": actual_sha256,
                }
            }
            if json_mode:
                print(json.dumps(error, ensure_ascii=False, indent=2))
            else:
                print(f"error: {error['error']['message']}", file=sys.stderr)
            return 2

    # Enforce the Vault path boundary on every user-supplied path before any
    # read or write. Routing through vault_paths (never Path() + startswith)
    # is the single defense against ../ traversal, absolute escapes, symlink
    # redirects, and Windows drive/UNC spoofing.
    if args.folder:
        try:
            resolve_target_within_vault(vault, args.folder, label="--folder")
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--folder", json_mode=json_mode)
    content_path: Path | None = None
    if args.content_file:
        try:
            content_path = resolve_existing_within_vault(
                vault, args.content_file, label="--content-file"
            )
        except VaultPathError as exc:
            return report_cli_violation(
                exc, param="--content-file", json_mode=json_mode
            )

    date = args.date or datetime.date.today().isoformat()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    body_text = ""
    given_meta: dict[str, Any] = {}
    raw_input: str | None = None
    content_source = (
        "--content-file" if args.content_file
        else "stdin" if args.stdin
        else "--from-preflight"
    )
    try:
        if content_path is not None:
            raw_input = content_path.read_text(encoding="utf-8")
            given_meta, body_text = split_frontmatter(
                raw_input, source=content_path.relative_to(vault).as_posix()
            )
        elif args.stdin:
            raw_input = sys.stdin.read()
            given_meta, body_text = split_frontmatter(raw_input, source="stdin")
        elif args.from_preflight:
            raw_input = preflight_cache.load(
                vault, args.from_preflight, note_type=args.type, title=args.title
            )
            given_meta, body_text = split_frontmatter(
                raw_input, source="--from-preflight"
            )
    except InvalidFrontmatterError as exc:
        return report_invalid_frontmatter(exc, json_mode=json_mode)
    except UnicodeError:
        return report_invalid_utf8_input(content_source, json_mode=json_mode)
    except PreflightCacheError as exc:
        if json_mode:
            print(json.dumps({"error": exc.payload()}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc.code}: {exc.message}", file=sys.stderr)
        return 2

    heading_edits: list[dict[str, Any]] | None = None
    if args.fix_heading_levels and raw_input is not None:
        contract = template_path(vault, args.type)
        repair = (
            heading_level_repair(raw_input, contract.read_text(encoding="utf-8"))
            if contract is not None and contract.is_file()
            else None
        )
        if repair is not None:
            raw_input, heading_edits = repair
            given_meta, body_text = split_frontmatter(
                raw_input, source="--fix-heading-levels"
            )

    try:
        folder, rendered = build_note(
            note_type=args.type,
            title=args.title,
            date=date,
            body=body_text,
            given_meta=given_meta,
            tags=tags,
            folder=args.folder,
            vault=vault,
        )
    except InvalidFrontmatterError as exc:
        return report_invalid_frontmatter(exc, json_mode=json_mode)
    except ValueError as exc:
        if json_mode:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2

    filename = (
        "TASK.md"
        if args.type == "task-memory"
        else f"{date} {sanitize_filename(args.title)}.md"
    )
    if args.type == "task-memory" and not is_task_memory_folder(args.type, folder):
        error = {
            "code": "invalid-task-memory-folder",
            "message": (
                "task-memory requires a normalized lowercase Tasks/<slug> "
                "operational path"
            ),
            "folder": folder,
        }
        if json_mode:
            print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {error['message']}: {folder}", file=sys.stderr)
        return 2
    dest = resolve_dest(vault, folder, filename)

    result: dict[str, Any] = {
        "vault": str(vault),
        "folder": folder,
        "path": str(dest),
        "rendered": rendered,
        "ok": True,
        "applied": False,
        "dry_run": not args.apply,
        "audit": None,
        "suggested_links": None,
    }

    try:
        rendered_bytes = rendered.encode("utf-8")
    except UnicodeError:
        return report_invalid_utf8_input(content_source, json_mode=json_mode)

    content_sha256 = hashlib.sha256(rendered_bytes).hexdigest()
    # Staged content is only a transport shortcut if it still renders to what
    # preflight accepted. A repair changes the content on purpose and mints a
    # new hash instead of failing this check.
    reused_unchanged = bool(args.from_preflight) and not heading_edits
    if reused_unchanged and content_sha256 != args.from_preflight:
        error = {
            "code": "preflight-content-changed",
            "message": (
                "staged content no longer renders to the preflighted hash; the "
                "date, tags, or Vault template changed since preflight"
            ),
            "expected_sha256": args.from_preflight,
            "actual_sha256": content_sha256,
        }
        if json_mode:
            print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {error['message']}", file=sys.stderr)
        return 2

    rendered_meta, rendered_body = split_frontmatter(rendered)
    missing_fields = missing_required_metadata(args.type, rendered_meta)
    if missing_fields and not args.preflight_json:
        error = {
            "code": "missing-required-metadata",
            "note_type": args.type,
            "fields": missing_fields,
        }
        if json_mode:
            payload = {**result, "error": error} if not args.apply else {"error": error}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if not args.apply:
                print_preview(vault, folder, dest, rendered)
            print(
                "error: web-clip requires non-empty metadata: "
                + ", ".join(missing_fields),
                file=sys.stderr,
            )
        return 2

    capture_depth = rendered_meta.get("capture_depth")
    if args.type == "web-clip" and (
        not isinstance(capture_depth, str) or capture_depth not in CAPTURE_DEPTHS
    ):
        error = {
            "code": "invalid-capture-depth",
            "message": "web-clip capture_depth must be 'standard' or 'verified'",
            "actual": capture_depth,
        }
        if json_mode:
            payload = {**result, "error": error} if not args.apply else {"error": error}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if not args.apply:
                print_preview(vault, folder, dest, rendered)
            print(f"error: {error['message']}", file=sys.stderr)
        return 2

    task_memory_initialization = False
    try:
        destination_folder = resolve_existing_within_vault(
            vault, folder, label="destination folder"
        )
    except PathNotFoundError:
        if args.type == "task-memory":
            try:
                destination_folder = resolve_target_within_vault(
                    vault, folder, label="task-memory destination folder"
                )
            except VaultPathError as exc:
                return report_cli_violation(
                    exc, param="destination folder", json_mode=json_mode
                )
            task_memory_initialization = True
        else:
            error = {
                "code": "missing-destination-folder",
                "message": (
                    "destination folder must already exist; create a governed "
                    "category with create-category after explicit confirmation"
                ),
                "folder": folder,
            }
            if json_mode:
                print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
            else:
                print(f"error: {error['message']}: {folder}", file=sys.stderr)
            return 2
    except VaultPathError as exc:
        return report_cli_violation(
            exc, param="destination folder", json_mode=json_mode
        )
    if not task_memory_initialization and not destination_folder.is_dir():
        error = {
            "code": "invalid-destination-folder",
            "message": "destination folder must be a real directory",
            "folder": folder,
        }
        if json_mode:
            print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {error['message']}: {folder}", file=sys.stderr)
        return 2

    folder = destination_folder.relative_to(vault).as_posix()
    dest = resolve_dest(vault, folder, filename)
    result["folder"] = folder
    result["path"] = str(dest)

    canonical_parts = Path(folder).parts
    if (
        args.type == "web-clip"
        and capture_depth == "verified"
        and canonical_parts
        and canonical_parts[0] == "00-Inbox"
    ):
        error = {
            "code": "capture-depth-route-mismatch",
            "message": (
                "verified capture is a finished knowledge path and cannot target "
                "00-Inbox"
            ),
            "folder": folder,
        }
        if json_mode:
            print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
        else:
            print(f"error: {error['message']}", file=sys.stderr)
        return 2

    receipt_required = requires_capture_receipt(args.type, folder, capture_depth)
    receipt_error: CaptureReceiptError | None = None
    semantic_receipt: dict[str, Any] | None = None
    receipt_provided = bool(
        args.capture_receipt_json is not None or args.capture_receipt_file is not None
    )
    if receipt_provided and args.type != "web-clip":
        receipt_error = CaptureReceiptError(
            "unexpected-capture-receipt",
            "capture receipts apply only to source-backed web clips",
        )
    elif receipt_provided and not receipt_required:
        receipt_error = CaptureReceiptError(
            "unexpected-capture-receipt",
            "capture receipts apply only to verified web clips outside 00-Inbox",
        )
    elif receipt_required and not receipt_provided:
        receipt_error = CaptureReceiptError(
            "missing-capture-receipt",
            "finished web clip requires a content-bound semantic receipt",
        )
    elif receipt_provided:
        candidate_source = rendered_meta.get("source")
        if not isinstance(candidate_source, str) or not candidate_source:
            receipt_error = CaptureReceiptError(
                "missing-candidate-source",
                "capture receipt validation requires non-empty source metadata",
            )
        else:
            try:
                receipt = (
                    parse_receipt_json(args.capture_receipt_json)
                    if args.capture_receipt_json is not None
                    else load_receipt_file(args.capture_receipt_file)
                )
                semantic_receipt = validate_capture_receipt(
                    receipt,
                    rendered,
                    candidate_source=candidate_source,
                )
            except CaptureReceiptError as exc:
                receipt_error = exc
    if semantic_receipt is not None and args.expect_capture_receipt_sha256:
        if semantic_receipt["sha256"] != args.expect_capture_receipt_sha256:
            receipt_error = CaptureReceiptError(
                "capture-receipt-changed",
                "capture receipt changed after semantic preflight",
                details={
                    "expected": args.expect_capture_receipt_sha256,
                    "actual": semantic_receipt["sha256"],
                },
            )
    if (
        receipt_required
        and args.apply
        and receipt_error is None
        and not args.expect_capture_receipt_sha256
    ):
        receipt_error = CaptureReceiptError(
            "missing-capture-receipt-sha256",
            "deep-capture apply requires the receipt SHA-256 accepted by preflight",
        )
    if receipt_required or receipt_provided:
        result["semantic_receipt"] = semantic_receipt

    if receipt_error is not None:
        if args.preflight_json:
            findings = audit_note_text(vault, dest, rendered)
            payload = {
                "vault": str(vault),
                "folder": folder,
                "path": str(dest),
                "applied": False,
                "dry_run": True,
                "frontmatter": rendered_meta,
                "content": stage_preflight_content(
                    vault,
                    content_sha256,
                    rendered,
                    rendered_bytes,
                    raw_input=raw_input,
                    note_type=args.type,
                    title=args.title,
                ),
                "validation": preflight_validation(
                    vault, args.type, raw_input, findings, content_sha256
                ),
                "semantic_receipt": {
                    "ok": False,
                    "error": receipt_error.payload(),
                },
                "suggested_links": None,
            }
            if heading_edits:
                payload["applied_fix"] = {
                    "kind": "heading-level-mismatch",
                    "edits": heading_edits,
                }
        else:
            payload = {"error": receipt_error.payload()}
        if json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"error: {receipt_error.code}: {receipt_error.message}",
                file=sys.stderr,
            )
        return 2

    if args.preflight_json:
        findings = audit_note_text(vault, dest, rendered)
        payload = {
            "vault": str(vault),
            "folder": folder,
            "path": str(dest),
            "applied": False,
            "dry_run": True,
            "frontmatter": rendered_meta,
            "content": stage_preflight_content(
                vault,
                content_sha256,
                rendered,
                rendered_bytes,
                raw_input=raw_input,
                note_type=args.type,
                title=args.title,
            ),
            "validation": preflight_validation(
                vault, args.type, raw_input, findings, content_sha256
            ),
            "suggested_links": None,
        }
        if heading_edits:
            payload["applied_fix"] = {
                "kind": "heading-level-mismatch",
                "edits": heading_edits,
            }
        if receipt_required or receipt_provided:
            payload["semantic_receipt"] = semantic_receipt
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not findings else 2

    if not args.apply:
        if json_mode:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_preview(vault, folder, dest, rendered)
            print("(dry run) pass --apply to write the file.")
        return 0

    # Audit the candidate before anything touches the disk. `audit_note_text`
    # exists for exactly this and was only ever reached from --preflight-json;
    # the apply path audited the file it had already written, reported
    # `audit.ok: false`, and returned 0.
    refused = [
        finding
        for finding in audit_note_text(vault, dest, rendered)
        if finding.code in REFUSED_ON_APPLY
    ]
    if refused:
        error = {
            "code": "unfinished-template-body",
            "message": (
                "the body still holds template scaffolding that should have "
                "been executed and removed before saving"
            ),
            "details": {
                "path": str(dest),
                "findings": [
                    {"code": finding.code, "message": finding.message}
                    for finding in refused
                ],
            },
        }
        if json_mode:
            print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
        else:
            print(
                f"error: {error['code']}: refusing to write {dest.name}",
                file=sys.stderr,
            )
            for finding in refused:
                print(f"  - {finding.code}: {finding.message}", file=sys.stderr)
        return 2

    if not rendered_body.strip() and not json_mode:
        print("warning: empty body; creating a frontmatter-only note.", file=sys.stderr)

    created_task_directories: tuple[Path, ...] = ()
    if task_memory_initialization:
        try:
            created_task_directories = initialize_task_memory_folder(vault, folder)
        except (OSError, VaultPathError) as exc:
            error = {
                "code": "task-memory-initialization-failed",
                "message": str(exc),
                "folder": folder,
            }
            if json_mode:
                print(json.dumps({"error": error}, ensure_ascii=False, indent=2))
            else:
                print(f"error: {error['message']}: {folder}", file=sys.stderr)
            return 2
    try:
        dest = write_new_note(vault, folder, filename, rendered_bytes)
    except OSError:
        cleanup_empty_directories(created_task_directories)
        raise
    result["path"] = str(dest)
    result["applied"] = True

    # Update a static INDEX when applicable (Folder Index / Dataview owned
    # listings are left untouched, mirroring process_inbox).
    append_static_index_entry(
        vault,
        StaticIndexEntry(
            note=dest.relative_to(vault),
            title=args.title,
            date=date,
        ),
    )

    if not args.no_audit:
        findings = audit_note(vault, dest)
        result["audit"] = finding_payload(findings)
        if not json_mode:
            rel = dest.relative_to(vault)
            if findings:
                print(f"AUDIT: {len(findings)} issue(s) found in {rel}:")
                for finding in findings:
                    print(f"  - {finding.code}: {finding.message}")
            else:
                print(f"AUDIT: OK — no issues in {rel}")

    if args.suggest_links:
        recs = suggest_links(vault, dest)
        result["suggested_links"] = [
            {"path": p.relative_to(vault).as_posix(), "score": s, "reasons": r}
            for p, s, r in recs
        ]
        if not json_mode:
            if recs:
                print("SUGGESTED LINKS:")
                for path, score, reasons in recs:
                    print(f"  {score:>3}  {path.relative_to(vault).as_posix()}")
                    for reason in reasons:
                        print(f"        - {reason}")
            else:
                print("SUGGESTED LINKS: none")

    if json_mode:
        payload = (
            {key: value for key, value in result.items() if key != "rendered"}
            if args.compact_json
            else result
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"created: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
