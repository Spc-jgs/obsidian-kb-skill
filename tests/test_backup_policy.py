import json
import os
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.backup_policy import (
    BackupPolicy,
    load_backup_policy,
    prune_backups,
)


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def write_settings(home: Path, value: object, *, schema: object = 1) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    settings = home / ".obsidian-kb-settings.json"
    settings.write_text(
        json.dumps({"schema_version": schema, "backup": {"keep_per_note": value}}),
        encoding="utf-8",
    )
    return settings


def backup(vault: Path, stamp: str, relative: str, content: str) -> Path:
    path = vault / ".obsidian-kb-backups" / stamp / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_missing_settings_defaults_to_one(tmp_path):
    policy = load_backup_policy(tmp_path / "home")
    assert policy == BackupPolicy(keep_per_note=1, prune_enabled=True, warnings=())


def test_valid_settings_select_retention(tmp_path):
    home = tmp_path / "home"
    write_settings(home, 3)
    assert load_backup_policy(home) == BackupPolicy(3, True)


@pytest.mark.parametrize("value", [0, -1, 1001, True, "1", None])
def test_invalid_retention_disables_pruning(tmp_path, value):
    home = tmp_path / "home"
    write_settings(home, value)
    policy = load_backup_policy(home)
    assert policy.prune_enabled is False
    assert policy.warnings


@pytest.mark.parametrize(
    "contents,schema",
    [
        ("{", 1),
        (json.dumps({"schema_version": 1}), 1),
        (json.dumps({"schema_version": 1, "backup": None}), 1),
        (json.dumps({"schema_version": 1, "backup": {}}), 1),
        (json.dumps({"schema_version": 2, "backup": {"keep_per_note": 1}}), 2),
        (json.dumps({"schema_version": True, "backup": {"keep_per_note": 1}}), True),
        (json.dumps({"schema_version": 1.0, "backup": {"keep_per_note": 1}}), 1.0),
        (json.dumps({"schema_version": "1", "backup": {"keep_per_note": 1}}), "1"),
    ],
)
def test_malformed_or_unsupported_settings_disable_pruning(
    tmp_path, contents, schema
):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".obsidian-kb-settings.json").write_text(contents, encoding="utf-8")
    policy = load_backup_policy(home)
    assert policy.prune_enabled is False
    assert policy.keep_per_note == 1
    assert policy.warnings


def test_unreadable_settings_disable_pruning(tmp_path, monkeypatch):
    home = tmp_path / "home"
    settings = write_settings(home, 1)
    original = Path.read_text

    def fail_read(path, *args, **kwargs):
        if path == settings:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    policy = load_backup_policy(home)
    assert policy.prune_enabled is False
    assert policy.warnings


def test_settings_symlink_is_not_treated_as_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    settings = home / ".obsidian-kb-settings.json"
    try:
        settings.symlink_to(home / "missing.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    policy = load_backup_policy(home)
    assert policy.prune_enabled is False
    assert policy.warnings


def test_keep_one_protects_current_and_prunes_all_note_groups(tmp_path):
    vault = make_vault(tmp_path)
    old_a = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "a0")
    current_a = backup(vault, "2026-07-10-090000", "Tasks/a/TASK.md", "a1")
    old_b = backup(vault, "2026-07-10-100001", "Tasks/b/TASK.md", "b0")
    new_b = backup(vault, "2026-07-10-100002", "Tasks/b/TASK.md", "b1")

    result = prune_backups(
        vault,
        BackupPolicy(keep_per_note=1, prune_enabled=True, warnings=()),
        protected=current_a,
    )

    assert current_a.is_file()
    assert not old_a.exists()
    assert new_b.is_file()
    assert not old_b.exists()
    assert result.scanned == 4
    assert result.deleted == 2


@pytest.mark.parametrize("protected_kind", ["missing", "outside", "wrong-file"])
def test_unverifiable_or_unmatched_protected_backup_disables_all_deletion(
    tmp_path, protected_kind
):
    vault = make_vault(tmp_path)
    first = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "one")
    second = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "two")
    if protected_kind == "missing":
        protected = vault / ".obsidian-kb-backups/missing/Tasks/a/TASK.md"
    elif protected_kind == "outside":
        protected = tmp_path / "outside.md"
        protected.write_text("outside", encoding="utf-8")
    else:
        protected = vault / "unrelated.md"
        protected.write_text("unrelated", encoding="utf-8")

    result = prune_backups(vault, BackupPolicy(1, True), protected=protected)

    assert first.is_file() and second.is_file()
    assert result.scanned == 2
    assert result.deleted == 0
    assert result.warnings


@pytest.mark.parametrize("keep", [2, 3])
def test_configured_retention_is_per_note(tmp_path, keep):
    vault = make_vault(tmp_path)
    paths = [
        backup(vault, f"2026-07-10-10000{index}", "Tasks/a/TASK.md", str(index))
        for index in range(4)
    ]
    other = [
        backup(vault, f"2026-07-10-11000{index}", "Tasks/b/TASK.md", str(index))
        for index in range(4)
    ]
    result = prune_backups(vault, BackupPolicy(keep, True))
    assert sum(path.exists() for path in paths) == keep
    assert sum(path.exists() for path in other) == keep
    assert result.deleted == 8 - (keep * 2)


def test_invalid_policy_performs_zero_deletions(tmp_path):
    vault = make_vault(tmp_path)
    first = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "a0")
    second = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "a1")
    result = prune_backups(
        vault,
        BackupPolicy(keep_per_note=1, prune_enabled=False, warnings=("invalid",)),
    )
    assert first.is_file() and second.is_file()
    assert result.scanned == 0
    assert result.deleted == 0
    assert result.warnings == ("invalid",)


def test_collision_suffix_directories_are_pruned(tmp_path):
    vault = make_vault(tmp_path)
    first = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "one")
    second = backup(vault, "2026-07-10-100000-2", "Tasks/a/TASK.md", "two")
    invalid = backup(vault, "2026-07-10-100000-1", "Tasks/a/TASK.md", "keep")
    result = prune_backups(vault, BackupPolicy(1, True))
    assert not first.exists()
    assert second.is_file()
    assert invalid.is_file()
    assert result.deleted == 1
    assert result.warnings


def test_symlink_and_unknown_top_level_items_are_retained(tmp_path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    root = vault / ".obsidian-kb-backups"
    root.mkdir()
    link = root / "2026-07-10-100000"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    unknown = root / "manual-copy.md"
    unknown.write_text("keep", encoding="utf-8")

    result = prune_backups(vault, BackupPolicy(1, True))

    assert link.is_symlink()
    assert unknown.is_file()
    assert outside.read_text(encoding="utf-8") == "outside"
    assert result.warnings


def test_symlink_file_inside_timestamp_is_retained(tmp_path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    first = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "one")
    second = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "two")
    link = first.parent / "outside-link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    result = prune_backups(vault, BackupPolicy(1, True))

    assert link.is_symlink()
    assert outside.read_text(encoding="utf-8") == "outside"
    assert second.is_file()
    assert result.deleted == 1
    assert result.warnings


def test_symlink_backup_root_disables_deletion(tmp_path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = backup(outside, "2026-07-10-100000", "Tasks/a/TASK.md", "x")
    root = vault / ".obsidian-kb-backups"
    try:
        root.symlink_to(outside / ".obsidian-kb-backups", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    result = prune_backups(vault, BackupPolicy(1, True))
    assert outside_file.is_file()
    assert result.deleted == 0
    assert result.warnings


def test_unlink_error_is_warning_and_other_groups_continue(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    fail = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "old-a")
    keep_a = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "new-a")
    delete_b = backup(vault, "2026-07-10-100002", "Tasks/b/TASK.md", "old-b")
    keep_b = backup(vault, "2026-07-10-100003", "Tasks/b/TASK.md", "new-b")
    original = Path.unlink

    def fail_one(path, *args, **kwargs):
        if path == fail:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one)
    result = prune_backups(vault, BackupPolicy(1, True))
    assert fail.is_file() and keep_a.is_file()
    assert not delete_b.exists() and keep_b.is_file()
    assert result.deleted == 1
    assert result.warnings


def test_empty_directory_cleanup_stops_at_backup_root(tmp_path):
    vault = make_vault(tmp_path)
    backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "old")
    keep = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "new")
    root = vault / ".obsidian-kb-backups"
    result = prune_backups(vault, BackupPolicy(1, True))
    assert result.deleted == 1
    assert root.is_dir()
    assert keep.is_file()
    assert not (root / "2026-07-10-100000").exists()


def test_rmdir_error_becomes_warning(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    old = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "old")
    backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "new")
    failed_directory = old.parent
    original = Path.rmdir

    def fail_one(path, *args, **kwargs):
        if path == failed_directory:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "rmdir", fail_one)
    result = prune_backups(vault, BackupPolicy(1, True))
    assert result.deleted == 1
    assert failed_directory.is_dir()
    assert result.warnings


def test_regular_file_candidate_resolves_inside_vault(tmp_path):
    vault = make_vault(tmp_path)
    candidate = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "old")
    os.utime(candidate, ns=(1, 1))
    latest = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "new")
    os.utime(latest, ns=(2, 2))
    result = prune_backups(vault, BackupPolicy(1, True))
    assert not candidate.exists()
    assert latest.is_file()
    assert result.deleted == 1


def test_exact_top_level_inbox_namespace_is_preserved_silently(tmp_path):
    vault = make_vault(tmp_path)
    transaction = (
        vault / ".obsidian-kb-backups" / "inbox" / "restore-id" / "manifest.json"
    )
    transaction.parent.mkdir(parents=True)
    transaction.write_text("recovery", encoding="utf-8")

    result = prune_backups(vault, BackupPolicy(1, True))

    assert transaction.read_text(encoding="utf-8") == "recovery"
    assert result.scanned == 0
    assert result.deleted == 0
    assert result.warnings == ()


def test_inbox_like_names_are_not_hidden_from_ordinary_retention(tmp_path):
    vault = make_vault(tmp_path)
    first = backup(
        vault, "2026-07-10-100000", "inbox/Tasks/a/TASK.md", "old"
    )
    latest = backup(
        vault, "2026-07-10-100001", "inbox/Tasks/a/TASK.md", "new"
    )
    near_name = vault / ".obsidian-kb-backups" / "inbox-copy"
    near_name.mkdir(parents=True)
    (near_name / "keep.md").write_text("keep", encoding="utf-8")

    result = prune_backups(vault, BackupPolicy(1, True))

    assert not first.exists()
    assert latest.is_file()
    assert (near_name / "keep.md").is_file()
    assert result.scanned == 2
    assert result.deleted == 1
    assert result.warnings == ("retained unknown backup item: inbox-copy",)
