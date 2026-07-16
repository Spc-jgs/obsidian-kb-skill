from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.inbox_plan import plan_inbox, sha256_bytes
from obsidian_kb_skill.scripts.inbox_transaction import (
    InboxLockBusyError,
    InboxPreparationError,
    _release_locks,
    _write_new_durable,
    prepare_inbox_operation,
)


class FailAt:
    def __init__(self, checkpoint: str) -> None:
        self.checkpoint_name = checkpoint
        self.seen: list[str] = []

    def checkpoint(self, name: str) -> None:
        self.seen.append(name)
        if name == self.checkpoint_name:
            raise OSError(f"injected:{name}")


def make_ready_item(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "00-Inbox").mkdir()
    target = vault / "30-Insights"
    target.mkdir()
    source = vault / "00-Inbox" / "Insight.md"
    source_bytes = b"# Insight\nexact source bytes  \n"
    source.write_bytes(source_bytes)
    index = target / "INDEX.md"
    index_bytes = b"\xef\xbb\xbf# Insights\r\n"
    index.write_bytes(index_bytes)
    item = plan_inbox(vault, effective_date="2042-03-04").items[0]
    assert item.status == "ready"
    assert item.proposal is not None
    assert item.proposal.index.action == "append"
    destination = vault / item.proposal.destination
    return vault, item, source, source_bytes, index, index_bytes, destination


def operation_directories(vault: Path) -> list[Path]:
    namespace = vault / ".obsidian-kb-backups" / "inbox"
    if not namespace.is_dir():
        return []
    return sorted(
        path for path in namespace.iterdir() if path.name != ".locks"
    )


def assert_business_state_unchanged(
    source: Path,
    source_bytes: bytes,
    index: Path,
    index_bytes: bytes,
    destination: Path,
    outside: Path,
) -> None:
    assert source.read_bytes() == source_bytes
    assert index.read_bytes() == index_bytes
    assert not os.path.lexists(destination)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "checkpoint",
    [
        "lock-source",
        "lock-index",
        "backup-root",
        "backup-source-write",
        "backup-source-fsync",
        "backup-index-write",
        "manifest-write",
        "manifest-fsync",
        "journal-backup-ready",
    ],
)
def test_preparation_failure_never_mutates_business_files(
    tmp_path: Path, checkpoint: str
) -> None:
    vault, item, source, source_bytes, index, index_bytes, destination = (
        make_ready_item(tmp_path)
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    injector = FailAt(checkpoint)

    with pytest.raises(OSError, match=f"injected:{checkpoint}"):
        prepare_inbox_operation(vault, item, injector=injector)

    assert checkpoint in injector.seen
    assert_business_state_unchanged(
        source, source_bytes, index, index_bytes, destination, outside
    )
    lock_root = vault / ".obsidian-kb-backups" / "inbox" / ".locks"
    assert not lock_root.exists() or list(lock_root.iterdir()) == []
    durable_record = checkpoint in {"manifest-fsync", "journal-backup-ready"}
    operations = operation_directories(vault)
    if durable_record:
        assert len(operations) == 1
        manifest = operations[0] / "manifest.json"
        assert manifest.is_file()
        assert manifest.read_bytes().endswith(b"\n")
    else:
        assert operations == []


def test_prepare_writes_exact_verified_backups_manifest_and_journal(
    tmp_path: Path,
) -> None:
    vault, item, source, source_bytes, index, index_bytes, destination = (
        make_ready_item(tmp_path)
    )

    operation = prepare_inbox_operation(vault, item)
    try:
        assert operation.vault == vault.resolve()
        assert operation.item is item
        assert operation.operation_root == (
            vault / ".obsidian-kb-backups" / "inbox" / operation.restore_id
        )
        assert operation.operation_root.is_dir()
        assert operation.held_locks
        assert [path.name for path in operation.held_locks] == sorted(
            path.name for path in operation.held_locks
        )

        manifest_bytes = (operation.operation_root / "manifest.json").read_bytes()
        assert manifest_bytes.endswith(b"\n")
        manifest = json.loads(manifest_bytes)
        assert manifest == operation.manifest
        assert manifest_bytes == (
            json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        assert str(vault.resolve()).encode() not in manifest_bytes
        assert manifest["restore_id"] == operation.restore_id
        assert manifest["source"]["path"] == item.source.as_posix()
        assert manifest["source"]["sha256"] == sha256_bytes(source_bytes)
        assert manifest["destination"]["path"] == item.proposal.destination.as_posix()
        assert manifest["destination"]["absent"] is True
        assert manifest["index"]["path"] == item.proposal.index.index.as_posix()
        assert manifest["index"]["before_sha256"] == sha256_bytes(index_bytes)

        source_backup = operation.operation_root / manifest["source"]["backup"]
        index_backup = operation.operation_root / manifest["index"]["backup"]
        assert source_backup.read_bytes() == source_bytes
        assert index_backup.read_bytes() == index_bytes
        assert sha256_bytes(source_backup.read_bytes()) == manifest["source"]["sha256"]
        assert sha256_bytes(index_backup.read_bytes()) == manifest["index"]["before_sha256"]

        event_bytes = (operation.operation_root / "events.jsonl").read_bytes()
        assert event_bytes.endswith(b"\n")
        events = [json.loads(line) for line in event_bytes.splitlines()]
        assert events[-1]["phase"] == "backup-ready"
        assert events[-1]["restore_id"] == operation.restore_id
        assert source.read_bytes() == source_bytes
        assert index.read_bytes() == index_bytes
        assert not os.path.lexists(destination)
    finally:
        assert _release_locks(operation.held_locks) == ()


def test_write_new_durable_is_exclusive_and_fsyncs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "new.bin"
    fsynced: list[int] = []
    original_fsync = os.fsync

    def record_fsync(fd: int) -> None:
        fsynced.append(fd)
        original_fsync(fd)

    monkeypatch.setattr(os, "fsync", record_fsync)
    _write_new_durable(path, b"first")

    assert path.read_bytes() == b"first"
    assert fsynced
    with pytest.raises(FileExistsError):
        _write_new_durable(path, b"second")
    assert path.read_bytes() == b"first"


def test_backup_verification_rejects_symlink_swap(
    tmp_path: Path,
) -> None:
    vault, item, source, source_bytes, index, index_bytes, destination = (
        make_ready_item(tmp_path)
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_copy = outside / "copied-source.md"
    outside_copy.write_bytes(source_bytes)

    class SwapBackupAtVerification:
        def checkpoint(self, name: str) -> None:
            if name != "backup-source-fsync":
                return
            operation = operation_directories(vault)[0]
            backup = operation / "source" / item.source
            backup.unlink()
            try:
                backup.symlink_to(outside_copy)
            except (OSError, NotImplementedError) as exc:
                pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(InboxPreparationError, match="backup"):
        prepare_inbox_operation(
            vault, item, injector=SwapBackupAtVerification()
        )

    assert source.read_bytes() == source_bytes
    assert index.read_bytes() == index_bytes
    assert not os.path.lexists(destination)
    assert outside_copy.read_bytes() == source_bytes
    assert list(outside.iterdir()) == [outside_copy]


def test_second_preparation_reports_stable_owner_without_stealing_lock(
    tmp_path: Path,
) -> None:
    vault, item, *_rest = make_ready_item(tmp_path)
    first = prepare_inbox_operation(vault, item)
    lock_payloads = {path: path.read_bytes() for path in first.held_locks}
    try:
        with pytest.raises(InboxLockBusyError) as first_busy:
            prepare_inbox_operation(vault, item)
        with pytest.raises(InboxLockBusyError) as second_busy:
            prepare_inbox_operation(vault, item)

        assert first_busy.value.code == "inbox-lock-busy"
        assert first_busy.value.owner_restore_id == first.restore_id
        assert second_busy.value.owner_restore_id == first.restore_id
        assert {path: path.read_bytes() for path in first.held_locks} == lock_payloads
        assert all(path.is_file() for path in first.held_locks)
    finally:
        assert _release_locks(first.held_locks) == ()


def test_lock_cleanup_retains_replaced_regular_file(tmp_path: Path) -> None:
    vault, item, *_rest = make_ready_item(tmp_path)
    operation = prepare_inbox_operation(vault, item)
    replaced = operation.held_locks[0]
    replaced.unlink()
    replacement = b"unrelated concurrent file\n"
    replaced.write_bytes(replacement)

    warnings = _release_locks(operation.held_locks)

    assert replaced.read_bytes() == replacement
    assert any("unsafe Inbox lock" in warning for warning in warnings)


@pytest.mark.parametrize("unsafe_root", ["backup", "locks"])
def test_symlinked_backup_or_lock_root_fails_closed(
    tmp_path: Path, unsafe_root: str
) -> None:
    vault, item, source, source_bytes, index, index_bytes, destination = (
        make_ready_item(tmp_path)
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    backup_root = vault / ".obsidian-kb-backups"
    if unsafe_root == "backup":
        link = backup_root
    else:
        (backup_root / "inbox").mkdir(parents=True)
        link = backup_root / "inbox" / ".locks"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(OSError):
        prepare_inbox_operation(vault, item)

    assert link.is_symlink()
    assert_business_state_unchanged(
        source, source_bytes, index, index_bytes, destination, outside
    )


@pytest.mark.parametrize("unsafe_root", ["backup", "locks"])
def test_broken_backup_or_lock_root_fails_closed(
    tmp_path: Path, unsafe_root: str
) -> None:
    vault, item, source, source_bytes, index, index_bytes, destination = (
        make_ready_item(tmp_path)
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    backup_root = vault / ".obsidian-kb-backups"
    if unsafe_root == "backup":
        link = backup_root
    else:
        (backup_root / "inbox").mkdir(parents=True)
        link = backup_root / "inbox" / ".locks"
    try:
        link.symlink_to(tmp_path / "missing", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(OSError):
        prepare_inbox_operation(vault, item)

    assert link.is_symlink()
    assert_business_state_unchanged(
        source, source_bytes, index, index_bytes, destination, outside
    )
