#!/usr/bin/env python3
"""Archive a captured source verbatim and link it from the note.

Separate from `create-note` on purpose: capture already binds a preflight to one
content hash for the *note*, and threading a second document through that
contract would mean two hashes and two failure modes in one call. Archiving is
also legitimately standalone — a source can be archived for a note that already
exists, which is exactly how this feature came to be needed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.source_archive import (
    SourceArchiveError,
    link_note_to_archive,
    plan_archive,
    render_archive,
)
from obsidian_kb_skill.scripts.update_note import backup_note
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)

SCHEMA_VERSION = "1.0"


def _error(code: str, message: str, **details: Any) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "error": {"code": code, "message": message, **details},
        },
        ensure_ascii=False,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive a captured source beside the note that digests it."
    )
    parser.add_argument("vault", type=Path, help="Path to the Obsidian Vault")
    parser.add_argument(
        "--note", required=True, help="Vault-relative path of the note it belongs to"
    )
    parser.add_argument("--source-url", required=True, help="Where the source came from")
    parser.add_argument("--author")
    parser.add_argument("--published", help="Source publication date (YYYY-MM-DD)")
    parser.add_argument(
        "--captured", help="Capture date (YYYY-MM-DD); defaults to today"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--stdin", action="store_true", help="Read the source text from stdin"
    )
    source.add_argument(
        "--content-file", type=Path, help="Read the source text from a Vault file"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--preflight-json", action="store_true", help="Report the plan, write nothing"
    )
    mode.add_argument("--apply", action="store_true", help="Write the archive")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Allow archiving a note that already declares an archive",
    )
    parser.add_argument("--compact-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = _build_parser().parse_args(argv)

    try:
        vault = validate_vault_root(args.vault)
    except InvalidVaultRootError as exc:
        return report_cli_violation(exc, param="vault", json_mode=True)

    try:
        note = resolve_target_within_vault(vault, Path(args.note), label="--note")
    except VaultPathError as exc:
        return report_cli_violation(exc, param="--note", json_mode=True)

    if args.stdin:
        # Universal-newline translation would silently rewrite CRLF sources on
        # the way in. Evidence has to arrive exactly as it was captured.
        sys.stdin.reconfigure(newline="")
        text = sys.stdin.read()
    else:
        try:
            content = resolve_existing_within_vault(
                vault, args.content_file, label="--content-file"
            )
        except VaultPathError as exc:
            return report_cli_violation(exc, param="--content-file", json_mode=True)
        text = content.read_bytes().decode("utf-8")

    if args.captured is not None:
        try:
            datetime.date.fromisoformat(args.captured)
        except ValueError:
            print(_error("invalid-date", "--captured must be YYYY-MM-DD"))
            return 2

    try:
        plan = plan_archive(vault, note, text, captured=args.captured)
    except SourceArchiveError as exc:
        print(_error(exc.code, exc.message, **exc.details))
        return 2

    if plan.already_archived and not args.replace:
        print(
            _error(
                "note-already-archived",
                "this note already links a source archive; pass --replace to "
                "add another",
                note=plan.note_relative,
                existing=plan.already_archived,
            )
        )
        return 2

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "note": plan.note_relative,
        "archive": {
            "path": plan.relative,
            "sha256": plan.sha256,
            "source_bytes": plan.source_bytes,
            "already_archived": plan.already_archived,
        },
    }

    if args.preflight_json:
        payload["applied"] = False
        print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact_json else 2))
        return 0

    rendered = render_archive(
        text,
        source=args.source_url,
        note=plan.note_relative,
        captured=args.captured or datetime.date.today().isoformat(),
        author=args.author,
        published=args.published,
    )
    note_text = note.read_text(encoding="utf-8")
    try:
        linked = link_note_to_archive(note_text, plan.stem)
    except SourceArchiveError as exc:
        print(_error(exc.code, exc.message, **exc.details))
        return 2

    # The note is the only pre-existing file this touches, so it gets the same
    # backup any other edit would take before a byte of it changes.
    backup = backup_note(vault, note)
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    # Bytes, not text: `write_text`/`read_text` translate line endings, and an
    # archive whose newlines were rewritten is no longer the thing it archives.
    plan.path.write_bytes(rendered.encode("utf-8"))
    note.write_text(linked, encoding="utf-8")

    payload["applied"] = True
    payload["note_backup"] = backup.relative_to(vault).as_posix()
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact_json else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
