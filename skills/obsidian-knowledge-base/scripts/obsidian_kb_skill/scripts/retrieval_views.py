#!/usr/bin/env python3
"""Run a search the Vault has already written down (#122).

The questions a user asks repeatedly are not infinite; they are a handful of
stable views — "learning notes from the last week", "current project risks".
Each time an Agent re-translates one of those into flags it may translate it
differently, and the same question quietly gets a different answer.

A view is that translation, made once, agreed once, and kept in the Vault. It
declares **structured fields only**: no command, no pipe, no template, no
environment interpolation. Every field maps onto a parameter `search-vault`
already validates, so a view can narrow a search and can never reach past the
guards a direct call would face.

The resolved plan is returned beside the results, because a search nobody can
re-run is not reproducible — it is just repeatable by the same program.

Read-only: nothing here writes, moves, or repairs a note, and it never edits the
config it reads.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from obsidian_kb_skill.scripts.console import configure_utf8_stdio
from obsidian_kb_skill.scripts.search_vault import (
    MAX_QUERY_CHARS,
    MAX_TOP_K,
    search_vault,
)
from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    VaultPathError,
    report_cli_violation,
    resolve_target_within_vault,
    validate_vault_root,
)

SCHEMA_VERSION = "1.0"
COMMAND = "run-retrieval-view"

VIEWS_FOLDER = ".obsidian-kb"
VIEWS_FILENAME = "retrieval-views.json"
VIEWS_SCHEMA_VERSION = 1

# A view field maps onto exactly one `search_vault` parameter and adds nothing.
# Written as a table so the mapping can be checked against the real signature
# rather than trusted: renaming a parameter there would otherwise leave this
# pointing at nothing and fail in a user's Vault instead of in CI.
VIEW_TO_SEARCH = {
    "query": "query",
    "types": "types",
    "tags": "tags",
    "scope": "scope",
    "top_k": "top_k",
}
# The two activity semantics registry row 28 keeps deliberately apart. A view
# picks one; it cannot blur them, and it cannot invent a third.
DATE_FIELDS = {
    "date": ("after", "before"),
    "updated": ("updated_after", "updated_before"),
}
WINDOW_FIELDS = ("date_field", "window_days")
KNOWN_VIEW_FIELDS = frozenset(VIEW_TO_SEARCH) | frozenset(WINDOW_FIELDS) | {"id"}

MAX_VIEWS_BYTES = 32 * 1024
MAX_VIEWS = 50
MAX_VIEW_ID_CHARS = 60
MAX_WINDOW_DAYS = 366
MAX_LIST_ITEMS = 20
MAX_SCOPE_CHARS = 200


class ViewConfigError(ValueError):
    """A stable refusal for a `retrieval-views.json` that cannot be trusted."""

    code = "invalid-view-config"


@dataclass(frozen=True)
class View:
    id: str
    query: str
    types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    scope: str | None = None
    top_k: int = 5
    date_field: str | None = None
    window_days: int | None = None


def views_path(vault: Path) -> Path:
    """Where a Vault keeps its own views. Dot-prefixed, so never indexed."""
    return vault / VIEWS_FOLDER / VIEWS_FILENAME


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": False,
        "read_only": True,
        "error": {"code": code, "message": message},
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ViewConfigError(f"{VIEWS_FILENAME}: {message}")


def _string_list(value: Any, *, field: str, view_id: str) -> tuple[str, ...]:
    _require(
        isinstance(value, list),
        f"view {view_id!r}: {field!r} must be a list of strings",
    )
    _require(
        len(value) <= MAX_LIST_ITEMS,
        f"view {view_id!r}: {field!r} holds more than {MAX_LIST_ITEMS} entries",
    )
    for item in value:
        _require(
            isinstance(item, str) and item.strip(),
            f"view {view_id!r}: {field!r} holds a non-string entry",
        )
    return tuple(item.strip() for item in value)


def _read_document(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ViewConfigError(
            f"{VIEWS_FILENAME}: must be a regular file inside the Vault"
        )
    if path.stat().st_size > MAX_VIEWS_BYTES:
        raise ViewConfigError(
            f"{VIEWS_FILENAME}: file exceeds {MAX_VIEWS_BYTES} bytes"
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ViewConfigError(f"{VIEWS_FILENAME}: {exc}") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ViewConfigError(
            f"{VIEWS_FILENAME}: not valid JSON at line {exc.lineno}"
        ) from exc
    _require(isinstance(document, dict), "top level must be an object")
    _require(
        document.get("schema_version") == VIEWS_SCHEMA_VERSION,
        f"schema_version must be {VIEWS_SCHEMA_VERSION}",
    )
    return document


def _view_from_entry(entry: Any, position: int) -> View:
    _require(isinstance(entry, dict), f"view {position} must be an object")
    view_id = entry.get("id")
    _require(
        isinstance(view_id, str) and view_id.strip(),
        f"view {position} has no string 'id'",
    )
    view_id = view_id.strip()
    _require(
        len(view_id) <= MAX_VIEW_ID_CHARS,
        f"view {view_id[:20]!r}: 'id' exceeds {MAX_VIEW_ID_CHARS} characters",
    )
    # An unknown key is refused rather than ignored. Dropping it silently runs a
    # search the file does not describe, which is the whole failure this
    # helper exists to prevent.
    unknown = sorted(set(entry) - KNOWN_VIEW_FIELDS)
    _require(
        not unknown,
        f"view {view_id!r}: unknown field(s) {', '.join(unknown)}",
    )

    query = entry.get("query")
    _require(
        isinstance(query, str) and query.strip(),
        f"view {view_id!r}: 'query' must be a non-empty string",
    )
    _require(
        len(query) <= MAX_QUERY_CHARS,
        f"view {view_id!r}: 'query' exceeds {MAX_QUERY_CHARS} characters",
    )

    top_k = entry.get("top_k", 5)
    _require(
        isinstance(top_k, int)
        and not isinstance(top_k, bool)
        and 1 <= top_k <= MAX_TOP_K,
        f"view {view_id!r}: 'top_k' must be an integer from 1 to {MAX_TOP_K}",
    )

    scope = entry.get("scope")
    if scope is not None:
        _require(
            isinstance(scope, str) and scope.strip(),
            f"view {view_id!r}: 'scope' must be a string",
        )
        _require(
            len(scope) <= MAX_SCOPE_CHARS,
            f"view {view_id!r}: 'scope' exceeds {MAX_SCOPE_CHARS} characters",
        )
        scope = scope.strip()

    date_field = entry.get("date_field")
    window_days = entry.get("window_days")
    if date_field is not None:
        _require(
            date_field in DATE_FIELDS,
            f"view {view_id!r}: 'date_field' must be one of "
            f"{', '.join(sorted(DATE_FIELDS))}",
        )
    if window_days is not None:
        _require(
            isinstance(window_days, int)
            and not isinstance(window_days, bool)
            and 1 <= window_days <= MAX_WINDOW_DAYS,
            f"view {view_id!r}: 'window_days' must be an integer from 1 to "
            f"{MAX_WINDOW_DAYS}",
        )
        _require(
            date_field is not None,
            f"view {view_id!r}: 'window_days' needs a 'date_field' saying "
            "which date it means",
        )

    return View(
        id=view_id,
        query=query.strip(),
        types=_string_list(entry["types"], field="types", view_id=view_id)
        if "types" in entry and entry["types"] is not None
        else (),
        tags=_string_list(entry["tags"], field="tags", view_id=view_id)
        if "tags" in entry and entry["tags"] is not None
        else (),
        scope=scope,
        top_k=top_k,
        date_field=date_field,
        window_days=window_days,
    )


def load_views(vault: Path) -> dict[str, View]:
    """Every view the Vault declares, refusing anything it cannot trust."""
    document = _read_document(views_path(vault))
    entries = document.get("views")
    _require(isinstance(entries, list), "'views' must be a list")
    _require(
        len(entries) <= MAX_VIEWS,
        f"holds more than {MAX_VIEWS} views",
    )
    views: dict[str, View] = {}
    for position, entry in enumerate(entries, start=1):
        view = _view_from_entry(entry, position)
        _require(
            view.id not in views,
            f"view id {view.id!r} is declared twice; neither one is the view",
        )
        views[view.id] = view
    return views


def _window(view: View, as_of: datetime.date) -> dict[str, str | None]:
    """Turn `window_days` into the inclusive ISO window it means.

    Inclusive of `as_of`, so seven days is the six before it plus today. The
    caller supplies the date: reading the clock here would make one view give
    different answers on different runs, which is what a view exists to stop.
    """
    resolved: dict[str, str | None] = {
        name: None for pair in DATE_FIELDS.values() for name in pair
    }
    if view.date_field is None or view.window_days is None:
        return resolved
    after_name, before_name = DATE_FIELDS[view.date_field]
    start = as_of - datetime.timedelta(days=view.window_days - 1)
    resolved[after_name] = start.isoformat()
    resolved[before_name] = as_of.isoformat()
    return resolved


def build(
    vault: Path,
    *,
    view: str,
    as_of: datetime.date,
) -> dict[str, Any]:
    """Resolve one view into a search plan, run it, and show both."""
    vault = vault.resolve()
    path = views_path(vault)
    if not path.exists():
        return _error(
            "missing-view-config",
            f"no {VIEWS_FOLDER}/{VIEWS_FILENAME} in this Vault",
        )
    try:
        views = load_views(vault)
    except ViewConfigError as error:
        return _error(ViewConfigError.code, str(error))

    selected = views.get(view)
    if selected is None:
        known = ", ".join(sorted(views)) or "none"
        return _error(
            "unknown-view", f"no view named {view!r}; this Vault declares: {known}"
        )

    scope_path: Path | None = None
    if selected.scope is not None:
        try:
            resolved_scope = resolve_target_within_vault(
                vault, Path(selected.scope), label="scope"
            )
        except VaultPathError as error:
            return _error("invalid-view-scope", str(error))
        if not resolved_scope.is_dir():
            # A moved folder must not quietly become "the whole Vault": the view
            # would keep working, return more than it ever did, and say nothing.
            return _error(
                "invalid-view-scope",
                f"view {selected.id!r} scopes to {selected.scope!r}, which is "
                "not a directory in this Vault",
            )
        scope_path = resolved_scope

    window = _window(selected, as_of)
    plan = {
        "query": selected.query,
        "types": list(selected.types),
        "tags": list(selected.tags),
        "scope": selected.scope,
        "top_k": selected.top_k,
        **window,
    }
    payload = search_vault(
        vault,
        selected.query,
        types=list(selected.types) or None,
        tags=list(selected.tags) or None,
        scope=scope_path,
        top_k=selected.top_k,
        after=window["after"],
        before=window["before"],
        updated_after=window["updated_after"],
        updated_before=window["updated_before"],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "ok": True,
        "read_only": True,
        "view": selected.id,
        "as_of": as_of.isoformat(),
        "plan": plan,
        "results": payload["results"],
        "scanned": payload["scanned"],
        "issues": payload["issues"],
        "truncated": payload["truncated"],
        "search": {
            key: value
            for key, value in payload.items()
            if key in {"expansion", "filters", "diagnostics"}
        },
    }


def _text_report(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"{payload['error']['code']}: {payload['error']['message']}"
    plan = payload["plan"]
    active = ", ".join(
        f"{key}={value}" for key, value in plan.items() if value not in (None, [], "")
    )
    lines = [f"{payload['view']} (as of {payload['as_of']}) — {active}"]
    for item in payload["results"]:
        lines.append(f"  {item['rank']}. {item['path']}  §{item['heading']}:{item['line']}")
    if not payload["results"]:
        lines.append("  (no results)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Run a search this Vault has already written down."
    )
    parser.add_argument("vault")
    parser.add_argument("--view", required=True)
    parser.add_argument(
        "--as-of",
        required=True,
        help="ISO date the relative window is measured from; resolve it yourself",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        as_of = datetime.date.fromisoformat(args.as_of)
    except ValueError:
        parser.error("--as-of must be an ISO date (YYYY-MM-DD)")

    try:
        root = validate_vault_root(Path(args.vault))
    except (InvalidVaultRootError, VaultPathError) as error:
        return report_cli_violation(error, command=COMMAND, as_json=args.json)

    payload = build(root, view=args.view, as_of=as_of)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_text_report(payload))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
