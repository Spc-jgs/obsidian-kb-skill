#!/usr/bin/env python3
"""Stage preflighted note content so apply does not re-transport the body.

The create contract is preflight-then-apply with the *same* input, so a long
article crossed the process boundary twice for one note. Preflight now keeps the
exact bytes it validated, keyed by the content SHA-256 it already reports, and
apply can reference that key instead of resending the document.

This strengthens rather than relaxes the content binding: re-sending proved
nothing, while a staged reference is re-rendered and re-hashed, so apply fails
loudly if it would write anything other than what preflight accepted.

The cache lives outside the Vault. A dry run must leave the Vault untouched, and
the staged copy is transient scratch, not knowledge.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CACHE_DIR_ENV = "OBSIDIAN_KB_PREFLIGHT_CACHE"
CACHE_DIR_NAME = ".obsidian-kb-preflight"
ENTRY_TTL_SECONDS = 24 * 60 * 60
MAX_ENTRIES = 64
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class PreflightCacheError(ValueError):
    """A staged-content reference that cannot be honoured."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    def payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


def cache_dir(home: Path | None = None) -> Path:
    """Return the staging directory, honouring an explicit override."""
    override = os.environ.get(CACHE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return (home or Path.home()) / CACHE_DIR_NAME


def _entry_path(directory: Path, sha256: str) -> Path:
    return directory / f"{sha256}.json"


def prune(directory: Path, *, now: float | None = None) -> None:
    """Drop expired and surplus entries; never let cleanup break a caller."""
    moment = time.time() if now is None else now
    try:
        entries = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix in (".json", ".tmp")
        ]
    except OSError:
        return
    survivors: list[tuple[float, Path]] = []
    for path in entries:
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        if moment - modified > ENTRY_TTL_SECONDS:
            path.unlink(missing_ok=True)
            continue
        # A `.tmp` file is either another process's write in flight or debris
        # from an interrupted one. Sweeping it on age alone avoids deleting a
        # file a concurrent stage is about to rename into place, and it can
        # never occupy a retention slot because it is not a readable entry.
        if path.suffix == ".tmp" or SHA256_RE.fullmatch(path.stem) is None:
            continue
        survivors.append((modified, path))
    survivors.sort(reverse=True)
    for _, path in survivors[MAX_ENTRIES:]:
        path.unlink(missing_ok=True)


def stage(
    vault: Path,
    sha256: str,
    raw: str,
    *,
    note_type: str,
    title: str,
    home: Path | None = None,
) -> bool:
    """Record preflighted input under its rendered content hash.

    Best-effort: a cache that cannot be written must never fail a validation
    that already succeeded. The caller reports whether staging happened.
    """
    if SHA256_RE.fullmatch(sha256) is None:
        return False
    directory = cache_dir(home)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "vault": str(vault),
        "type": note_type,
        "title": title,
        "sha256": sha256,
        "raw": raw,
    }
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = _entry_path(directory, sha256)
        temporary = target.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(target)
    except OSError:
        return False
    prune(directory)
    return True


def load(
    vault: Path,
    sha256: str,
    *,
    note_type: str,
    title: str,
    home: Path | None = None,
) -> str:
    """Return the staged input for one content hash, or explain the refusal."""
    if SHA256_RE.fullmatch(sha256) is None:
        raise PreflightCacheError(
            "invalid-preflight-reference",
            "--from-preflight takes the content SHA-256 reported by preflight",
        )
    path = _entry_path(cache_dir(home), sha256)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PreflightCacheError(
            "unknown-preflight-content",
            "no staged content for this hash; it expired or was never "
            "preflighted on this machine — rerun preflight with the full body",
            sha256=sha256,
        ) from None
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise PreflightCacheError(
            "unreadable-preflight-content",
            f"staged content could not be read: {exc}",
            sha256=sha256,
        ) from None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or not isinstance(payload.get("raw"), str)
    ):
        raise PreflightCacheError(
            "unreadable-preflight-content",
            "staged content has an unrecognized shape",
            sha256=sha256,
        )
    if payload.get("vault") != str(vault):
        raise PreflightCacheError(
            "preflight-vault-mismatch",
            "staged content was preflighted against a different Vault",
            sha256=sha256,
            staged_vault=payload.get("vault"),
        )
    # Identical content can legitimately belong to two notes, so the hash alone
    # does not identify the operation. Binding the type and title keeps a reused
    # reference pointing at the note that was actually validated.
    if payload.get("type") != note_type or payload.get("title") != title:
        raise PreflightCacheError(
            "preflight-context-mismatch",
            "staged content was preflighted for a different note type or title",
            sha256=sha256,
            staged_type=payload.get("type"),
            staged_title=payload.get("title"),
        )
    return payload["raw"]
