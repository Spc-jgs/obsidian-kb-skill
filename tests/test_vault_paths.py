"""Unit tests for the Vault path-boundary enforcement (vault_paths.py).

These pin the security contract: normalization + relative_to() containment,
never string prefixes. They must FAIL until vault_paths.py is wired in and the
CLIs call it — but most assert the module's own behavior, so they validate the
module itself first.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.vault_paths import (
    InvalidVaultRootError,
    PathNotFoundError,
    PathOutsideVaultError,
    VaultPathError,
    _is_foreign_path,
    resolve_existing_within_vault,
    resolve_target_within_vault,
    validate_vault_root,
)


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "00-Inbox").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def _safe_symlink(target: Path, link: Path) -> None:
    """Create a symlink; skip the enclosing test if the OS forbids it."""
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this filesystem")


# --- Vault root validation ------------------------------------------------

def test_vault_root_must_exist(tmp_path):
    with pytest.raises(InvalidVaultRootError):
        validate_vault_root(tmp_path / "nope")


def test_vault_root_rejects_symlink_to_outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "vaultlink"
    _safe_symlink(outside, link)
    with pytest.raises(InvalidVaultRootError):
        validate_vault_root(link)


# --- existing-path resolution ----------------------------------------------

def test_existing_relative_inside_vault(tmp_path):
    vault = _make_vault(tmp_path)
    note = vault / "30-Insights" / "A.md"
    note.write_text("x", encoding="utf-8")
    got = resolve_existing_within_vault(vault, "30-Insights/A.md")
    assert got == note.resolve()


def test_existing_absolute_inside_vault(tmp_path):
    vault = _make_vault(tmp_path)
    note = vault / "30-Insights" / "A.md"
    note.write_text("x", encoding="utf-8")
    got = resolve_existing_within_vault(vault, note)
    assert got == note.resolve()


def test_existing_escapes_with_dotdot(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, "../outside.md")


def test_existing_multi_level_dotdot(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, "../../etc/passwd")


def test_existing_absolute_outside(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside" / "secret.md"
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, outside)


def test_existing_missing_file(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(PathNotFoundError):
        resolve_existing_within_vault(vault, "30-Insights/missing.md")


def test_prefix_spoofing_is_rejected(tmp_path):
    # /vault-evil must NOT be accepted as a child of /vault.
    base = tmp_path / "parent"
    vault = base / "vault"
    vault.mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    decoy = base / "vault-evil"
    decoy.mkdir()
    secret = decoy / "secret.md"
    secret.write_text("x", encoding="utf-8")
    # A path that textually "starts with" the vault path but resolves elsewhere.
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, str(secret))


def test_existing_symlink_file_escapes(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside" / "secret.md"
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    link = vault / "30-Insights" / "link.md"
    _safe_symlink(outside, link)
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, "30-Insights/link.md")


def test_existing_symlink_parent_escapes(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_note = outside / "nested" / "A.md"
    outside_note.parent.mkdir(parents=True)
    outside_note.write_text("x", encoding="utf-8")
    linkdir = vault / "30-Insights" / "escape"
    _safe_symlink(outside, linkdir)
    with pytest.raises(PathOutsideVaultError):
        resolve_existing_within_vault(vault, "30-Insights/escape/nested/A.md")


# --- target (to-be-created) resolution ------------------------------------

def test_target_inside_vault(tmp_path):
    vault = _make_vault(tmp_path)
    got = resolve_target_within_vault(vault, "30-Insights/New.md")
    assert got == (vault / "30-Insights" / "New.md").resolve()


def test_target_escapes_with_dotdot(tmp_path):
    vault = _make_vault(tmp_path)
    with pytest.raises(PathOutsideVaultError):
        resolve_target_within_vault(vault, "../outside.md")


def test_target_absolute_outside(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside" / "New.md"
    with pytest.raises(PathOutsideVaultError):
        resolve_target_within_vault(vault, outside)


def test_target_symlink_parent_escapes(tmp_path):
    vault = _make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    linkdir = vault / "30-Insights" / "escape"
    _safe_symlink(outside, linkdir)
    with pytest.raises(PathOutsideVaultError):
        resolve_target_within_vault(vault, "30-Insights/escape/New.md")


# --- foreign-OS path detection (Windows logic) ---------------------------
#
# We cannot instantiate an OS-bound WindowsPath on a POSIX test host, so the
# resolver's Windows *resolution* is exercised only on a real Windows machine.
# Here we prove the three things that matter and that CAN run on Linux:
#   1. A Windows drive letter or UNC string is rejected as foreign (the escape
#      vector) — both via _is_foreign_path and via the resolver raising.
#   2. A relative Windows path (backslashes, no drive/UNC) is NOT flagged
#      foreign, so it flows to the in-Vault containment check instead.
#   3. The pure Windows parser separates backslash paths exactly as Windows
#      would (proves the logic, not just POSIX behaviour).

def test_posix_rejects_windows_drive_path(tmp_path):
    vault = _make_vault(tmp_path)
    assert _is_foreign_path("C:\\evil\\x.md")
    with pytest.raises(PathOutsideVaultError):
        resolve_target_within_vault(vault, "C:\\evil\\x.md")


def test_posix_rejects_unc_path(tmp_path):
    vault = _make_vault(tmp_path)
    assert _is_foreign_path("\\\\server\\share\\x.md")
    with pytest.raises(PathOutsideVaultError):
        resolve_target_within_vault(vault, "\\\\server\\share\\x.md")


def test_relative_windows_path_not_flagged_foreign():
    # No drive, no UNC -> must be allowed through to containment, never
    # rejected up front as "foreign".
    assert not _is_foreign_path("30-Insights\\New.md")
    assert not _is_foreign_path("sub\\file.md")


def test_windows_path_parse_shape():
    # Pure (OS-independent) parser proves backslash separation yields New.md.
    from pathlib import PureWindowsPath

    p = PureWindowsPath("30-Insights\\New.md")
    assert p.name == "New.md"
    assert p.parts[-2:] == ("30-Insights", "New.md")


def test_nt_branch_rejects_foreign(monkeypatch):
    # _is_foreign_path's Windows branch, tested in isolation (no OS-bound Path
    # is constructed, so this is safe on a POSIX host).
    monkeypatch.setattr(os, "name", "nt")
    assert _is_foreign_path("Z:\\Documents\\x.md")
    assert _is_foreign_path("\\\\server\\share\\x.md")
    assert not _is_foreign_path("30-Insights\\New.md")


def test_relative_windows_style_path_accepted_and_contained(tmp_path):
    # On POSIX a backslash is a literal filename char; the path stays contained
    # in the Vault and must be accepted (no escape, no crash).
    vault = _make_vault(tmp_path)
    got = resolve_target_within_vault(vault, "30-Insights\\New.md")
    vroot = Path(vault).resolve()
    assert vroot in got.resolve().parents
