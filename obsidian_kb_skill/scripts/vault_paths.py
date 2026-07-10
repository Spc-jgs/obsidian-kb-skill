#!/usr/bin/env python3
"""Single source of truth for Vault path-boundary enforcement.

No CLI or script may build, join, or validate a Vault path by hand. Every
Vault-relative path an agent or user supplies must pass through one of the
resolvers here. The rule is simple and deliberately strict:

    After full normalization (``Path.resolve()`` — which follows symlinks),
    the path MUST be ``relative_to`` the resolved Vault root.

That single check defeats every evasion this module is built to stop:

* ``../outside.md`` and multi-level ``../../`` traversal,
* absolute paths pointing outside the Vault,
* a target file/folder that is a symlink to a path outside the Vault,
* a parent directory that is a symlink to a path outside the Vault,
* path-prefix spoofing (``/vault-evil`` must NOT match ``/vault``),
* Windows drive letters and UNC paths that escape the Vault root.

STRINGS ARE NEVER CHECKED WITH ``startswith()``. Containment is decided only
by canonical resolution + ``relative_to``.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PureWindowsPath
from typing import Optional, Union


class VaultPathError(Exception):
    """Base class for every Vault-path policy violation."""


class InvalidVaultRootError(VaultPathError):
    """The Vault root itself is not a usable, in-bounds directory."""


class PathOutsideVaultError(VaultPathError):
    """The resolved path escapes the Vault (after following symlinks)."""


class PathNotFoundError(VaultPathError):
    """An existing-path query was given a path that does not exist."""


def _is_foreign_path(user_path: Union[str, Path]) -> bool:
    """True when ``user_path`` is a Windows-shaped absolute path foreign to a
    (POSIX or relative) Vault root.

    The danger this defends: on a POSIX host ``pathlib`` happily accepts
    ``C:\\evil`` or ``\\\\server\\share`` as *literal filenames* and would
    wrongly contain them. So any Windows drive letter or UNC string is treated
    as foreign up front, before the OS-bound ``Path`` resolver is ever called.

    On a real Windows host this pre-filter is a no-op: native drive/UNC
    containment is enforced later by ``resolve()`` + ``relative_to()`` (which
    correctly allow a same-drive in-Vault absolute path). Keeping the filter
    POSIX-only also avoids false-rejecting legitimate same-drive Windows paths.

    Pure parsing only — never instantiates an OS-bound ``WindowsPath``.
    """
    text = str(user_path)
    if os.name == "nt":
        # On Windows, let the resolver's resolve()+relative_to() decide
        # containment (it handles same-drive paths correctly). Only UNC is an
        # unconditional escape; PureWindowsPath parses it without a Windows host.
        if text.startswith("\\\\"):
            return True
        try:
            pw = PureWindowsPath(text)
        except (ValueError, NotImplementedError):
            return False
        return bool(pw.drive) and pw.is_absolute()
    # POSIX / other hosts: a drive letter or UNC string is foreign by nature.
    if text.startswith("\\\\"):
        return True
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        return True
    return False


def _assert_contained(root: Path, resolved: Path, label: str) -> Path:
    """Raise PathOutsideVaultError unless ``resolved`` is inside ``root``.

    The message deliberately never embeds ``resolved`` or ``root`` (absolute
    system paths) — it only names the offending parameter so a CLI can surface a
    clean error without leaking filesystem layout.
    """
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathOutsideVaultError(f"{label} is outside the Vault root") from None
    return resolved


def validate_vault_root(vault: Union[str, Path]) -> Path:
    """Return the canonical Vault root, or raise InvalidVaultRootError.

    The root must be a real directory (a symlink root is rejected so containment
    checks on children are never silently redirected), must exist, and must
    already be contained in itself.
    """
    raw = Path(vault).expanduser()
    if raw.is_symlink():
        raise InvalidVaultRootError(
            f"Vault root must be a real directory, not a symlink: {vault}"
        )
    try:
        root = raw.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise InvalidVaultRootError(
            f"Vault root does not exist or is unresolvable: {vault}"
        ) from exc
    if not root.is_dir():
        raise InvalidVaultRootError(f"Vault root is not a directory: {vault}")
    try:
        root.relative_to(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise InvalidVaultRootError(f"Vault root is not a usable directory: {vault}") from exc
    return root


def resolve_existing_within_vault(
    vault: Union[str, Path],
    user_path: Union[str, Path],
    *,
    label: str = "path",
) -> Path:
    """Resolve a path that MUST already exist and MUST stay inside the Vault.

    Use for: reading, updating, moving, or auditing an existing note/dir, and
    for the Vault root itself. Symlinks are followed and the final target is
    required to remain inside the Vault.
    """
    root = validate_vault_root(vault)
    if _is_foreign_path(user_path):
        raise PathOutsideVaultError(
            f"{label} is an absolute path on a foreign volume/UNC and cannot be "
            f"inside the Vault: {user_path}"
        )
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    # Non-strict resolve: follow symlinks (so a symlink-to-outside target is
    # caught by the containment check) without requiring the final component to
    # exist. Existence is enforced separately below.
    resolved = candidate.resolve()
    _assert_contained(root, resolved, label)
    if not resolved.exists():
        raise PathNotFoundError(f"{label} does not exist: {user_path}")
    return resolved


def resolve_target_within_vault(
    vault: Union[str, Path],
    user_path: Union[str, Path],
    *,
    label: str = "path",
) -> Path:
    """Resolve a path for a NEW file/dir; the target itself may not exist yet.

    Use for: create-note destinations, template output dirs, inbox folders,
    index targets. The nearest EXISTING ancestor is resolved (following
    symlinks) and must remain inside the Vault, so a symlink parent cannot
    redirect the write outside the tree. Returns the canonical absolute path.
    """
    root = validate_vault_root(vault)
    if _is_foreign_path(user_path):
        raise PathOutsideVaultError(
            f"{label} is an absolute path on a foreign volume/UNC and cannot be "
            f"inside the Vault: {user_path}"
        )
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    # Resolve the nearest existing ancestor to defeat symlink-parent escapes,
    # then require it to be inside the Vault before appending the tail.
    ancestor = _nearest_existing_parent(candidate)
    resolved_ancestor = ancestor.resolve(strict=True)
    _assert_contained(root, resolved_ancestor, label)
    # Re-attach the unresolved tail (relative to the ancestor) so callers get a
    # canonical path that is guaranteed to descend from an in-Vault directory.
    try:
        tail = candidate.relative_to(ancestor)
    except ValueError:
        tail = Path("")
    return resolved_ancestor / tail


def _nearest_existing_parent(path: Path) -> Path:
    """Walk up from ``path`` until an existing directory is found."""
    cur = path if path.is_absolute() else path
    # If the path itself exists, its parent is a fine anchor; but to defeat a
    # symlink *file* target we still anchor on the parent of the (possibly
    # non-existent) target.
    probe = path.parent if not path.exists() else path
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    return probe if probe.exists() and probe.is_dir() else path.parent


def structured_error(
    exc: VaultPathError,
    *,
    param: Optional[str] = None,
) -> dict:
    """Build a machine-readable JSON error payload for a path violation.

    Keeps the message free of unrelated system paths: it echoes only the
    offending user-supplied parameter, never internal absolute paths.
    """
    code = "PATH_OUTSIDE_VAULT" if isinstance(exc, PathOutsideVaultError) else (
        "PATH_NOT_FOUND" if isinstance(exc, PathNotFoundError) else "INVALID_VAULT_ROOT"
    )
    details: dict = {}
    if param is not None:
        details["param"] = param
    return {
        "schema_version": "1.0",
        "ok": False,
        "command": None,
        "error": {
            "code": code,
            "message": str(exc),
            "details": details,
        },
    }


# Exit code convention shared by every CLI for path/security failures.
EXIT_PATH_VIOLATION = 3


def report_cli_violation(
    exc: VaultPathError,
    *,
    param: Optional[str] = None,
    json_mode: bool = False,
) -> int:
    """Print a clean path-violation error and return the security exit code.

    Never leaks internal absolute paths: it echoes only the offending parameter
    name (when known) and the structured JSON contract. The caller's CLI returns
    this int directly.
    """
    if json_mode:
        print(json.dumps(structured_error(exc, param=param), ensure_ascii=False))
    else:
        msg = f"{param}: {exc}" if param else str(exc)
        print(f"error: {msg}", file=sys.stderr)
    return EXIT_PATH_VIOLATION
