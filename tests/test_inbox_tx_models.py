from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

import obsidian_kb_skill.scripts.inbox_tx as inbox_tx
import obsidian_kb_skill.scripts.inbox_tx.models as models
from obsidian_kb_skill.scripts.inbox_tx.models import (
    ApplyStatus,
    FileIdentity,
    FileMetadata,
    InboxApplyResult,
    InboxFailure,
    InboxFailureInjector,
    InboxRestoreResult,
    InboxTransactionError,
    InboxTransactionIssue,
    RecoveryDebris,
    RestoreStatus,
    TransactionState,
)


def make_apply_result(
    *, status: ApplyStatus = "applied", applied: bool = True
) -> InboxApplyResult:
    return InboxApplyResult(
        source=Path("00-Inbox/A.md"),
        destination=Path("20-Learning/A.md"),
        status=status,
        applied=applied,
        restore_id="restore-1",
        backup=Path(".obsidian-kb/backups/restore-1/A.md"),
        issue=None,
    )


def make_restore_result(
    *, status: RestoreStatus = "restored", applied: bool = True
) -> InboxRestoreResult:
    return InboxRestoreResult(
        restore_id="restore-1",
        status=status,
        applied=applied,
        actions=("restore source",),
        conflicts=(),
    )


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            result.add(prefix)
            result.update(f"{prefix}.{alias.name}" for alias in node.names)
    return result


def test_runtime_models_do_not_depend_on_planner() -> None:
    imports = imported_modules(Path(models.__file__))
    assert not any(
        name.lstrip(".").split(".")[-1] == "inbox_plan" for name in imports
    )


def test_package_marker_does_not_reexport_runtime_types() -> None:
    assert not hasattr(inbox_tx, "InboxApplyResult")
    tree = ast.parse(Path(inbox_tx.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom)
        and any(alias.name == "*" for alias in node.names)
        for node in ast.walk(tree)
    )


def test_status_aliases_contain_exact_public_values() -> None:
    assert get_args(ApplyStatus) == (
        "applied",
        "skipped",
        "blocked",
        "rolled_back",
        "recovery_required",
    )
    assert get_args(RestoreStatus) == (
        "ready",
        "restored",
        "already_restored",
        "blocked",
        "recovery_required",
    )


def test_transaction_state_contains_exact_public_values() -> None:
    assert [(state.name, state.value) for state in TransactionState] == [
        ("NEW", "new"),
        ("LOCKED", "locked"),
        ("PREPARED", "prepared"),
        ("MUTATING", "mutating"),
        ("ABORTING", "aborting"),
        ("ABORTED", "aborted"),
        ("ROLLING_BACK", "rolling_back"),
        ("ROLLED_BACK", "rolled_back"),
        ("COMMITTED", "committed"),
        ("RECOVERY_REQUIRED", "recovery_required"),
        ("CLOSED", "closed"),
    ]


@pytest.mark.parametrize(
    ("model", "expected_fields"),
    [
        (InboxTransactionIssue, ("code", "message", "path")),
        (FileIdentity, ("device", "inode", "size", "mtime_ns")),
        (FileMetadata, ("mode", "mtime_ns")),
        (RecoveryDebris, ("restore_id", "location", "classification")),
        (
            InboxApplyResult,
            (
                "source",
                "destination",
                "status",
                "applied",
                "restore_id",
                "backup",
                "issue",
                "warnings",
                "rollback_actions",
                "recovery_debris",
                "business_mutation_started",
            ),
        ),
        (
            InboxRestoreResult,
            (
                "restore_id",
                "status",
                "applied",
                "actions",
                "conflicts",
                "issue",
                "warnings",
                "recovery_debris",
            ),
        ),
        (
            InboxFailure,
            (
                "code",
                "message",
                "restore_id",
                "recovery_location",
                "warnings",
                "recovery_debris",
                "business_mutation_started",
            ),
        ),
    ],
)
def test_runtime_dataclasses_have_exact_public_fields(
    model: type[object], expected_fields: tuple[str, ...]
) -> None:
    assert tuple(field.name for field in fields(model)) == expected_fields


@pytest.mark.parametrize(
    "instance",
    [
        InboxTransactionIssue("blocked", "blocked"),
        FileIdentity(device=1, inode=2, size=3, mtime_ns=4),
        FileMetadata(mode=0o644, mtime_ns=4),
        RecoveryDebris("restore-1", Path(".recovery/restore-1"), "incomplete"),
        make_apply_result(),
        make_restore_result(),
        InboxFailure("failed", "failed", None, None, (), None, False),
    ],
)
def test_runtime_dataclasses_are_frozen(instance: object) -> None:
    field = fields(instance)[0]
    with pytest.raises(FrozenInstanceError):
        setattr(instance, field.name, getattr(instance, field.name))


@pytest.mark.parametrize(
    ("status", "applied"),
    [
        ("applied", True),
        ("skipped", False),
        ("blocked", False),
        ("rolled_back", False),
        ("recovery_required", False),
    ],
)
def test_apply_result_accepts_exact_status_consistency(
    status: ApplyStatus, applied: bool
) -> None:
    assert make_apply_result(status=status, applied=applied).status == status


@pytest.mark.parametrize(
    ("status", "applied"),
    [("applied", False), ("blocked", True)],
)
def test_apply_result_rejects_inconsistent_applied_flag(
    status: ApplyStatus, applied: bool
) -> None:
    with pytest.raises(ValueError, match="applied"):
        make_apply_result(status=status, applied=applied)


def test_apply_result_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status"):
        make_apply_result(status="unknown", applied=False)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "applied"),
    [
        ("ready", False),
        ("restored", True),
        ("already_restored", False),
        ("blocked", False),
        ("recovery_required", False),
    ],
)
def test_restore_result_accepts_exact_status_consistency(
    status: RestoreStatus, applied: bool
) -> None:
    assert make_restore_result(status=status, applied=applied).status == status


@pytest.mark.parametrize(
    ("status", "applied"),
    [("restored", False), ("ready", True)],
)
def test_restore_result_rejects_inconsistent_applied_flag(
    status: RestoreStatus, applied: bool
) -> None:
    with pytest.raises(ValueError, match="applied"):
        make_restore_result(status=status, applied=applied)


def test_restore_result_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status"):
        make_restore_result(status="unknown", applied=False)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source",
    [
        Path("."),
        Path(".."),
        Path("../A.md"),
        Path("00-Inbox/../A.md"),
        Path("/tmp/A.md"),
    ],
)
def test_apply_result_rejects_invalid_source(source: Path) -> None:
    with pytest.raises(ValueError, match="Vault-relative"):
        InboxApplyResult(source, None, "blocked", False, None, None, None)


def test_apply_result_rejects_absolute_destination() -> None:
    with pytest.raises(ValueError, match="Vault-relative"):
        InboxApplyResult(
            source=Path("00-Inbox/A.md"),
            destination=Path("/tmp/host-path"),
            status="blocked",
            applied=False,
            restore_id=None,
            backup=None,
            issue=None,
        )


def test_apply_result_rejects_absolute_backup() -> None:
    with pytest.raises(ValueError, match="Vault-relative"):
        InboxApplyResult(
            source=Path("00-Inbox/A.md"),
            destination=None,
            status="blocked",
            applied=False,
            restore_id=None,
            backup=Path("/tmp/host-path"),
            issue=None,
        )


@pytest.mark.parametrize(
    "model",
    [
        lambda path: InboxTransactionIssue("blocked", "blocked", path),
        lambda path: InboxFailure("failed", "failed", None, path, (), None, False),
        lambda path: RecoveryDebris("restore-1", path, "unknown"),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        Path("."),
        Path("../outside"),
        Path("recovery/../outside"),
        Path("/tmp/outside"),
    ],
)
def test_runtime_models_reject_invalid_optional_paths(model: object, path: Path) -> None:
    with pytest.raises(ValueError, match="Vault-relative"):
        model(path)  # type: ignore[operator]


def test_path_validation_is_lexical_and_does_not_touch_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("path validation accessed the filesystem")

    monkeypatch.setattr(Path, "resolve", fail)
    monkeypatch.setattr(Path, "stat", fail)

    issue = InboxTransactionIssue("warning", "warning", Path("00-Inbox/A.md"))
    debris = RecoveryDebris("restore-1", Path(".recovery/restore-1"), "unknown")
    failure = InboxFailure(
        "failed",
        "failed",
        "restore-1",
        Path(".recovery/restore-1"),
        (),
        debris,
        True,
    )
    result = InboxApplyResult(
        Path("00-Inbox/A.md"),
        Path("20-Learning/A.md"),
        "blocked",
        False,
        "restore-1",
        Path(".backups/restore-1/A.md"),
        issue,
        recovery_debris=debris,
    )

    assert failure.recovery_location == Path(".recovery/restore-1")
    assert result.source == Path("00-Inbox/A.md")


def test_recovery_debris_rejects_unknown_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        RecoveryDebris(
            "restore-1",
            Path(".recovery/restore-1"),
            "other",  # type: ignore[arg-type]
        )


def test_transaction_error_carries_same_frozen_failure() -> None:
    failure = InboxFailure("failed", "transaction failed", None, None, (), None, False)

    error = InboxTransactionError(failure)

    assert error.failure is failure
    assert str(error) == failure.message
    with pytest.raises(FrozenInstanceError):
        failure.message = "changed"


def test_failure_injector_is_protocol_with_checkpoint_contract() -> None:
    assert InboxFailureInjector._is_protocol is True
    assert list(inspect.signature(InboxFailureInjector.checkpoint).parameters) == [
        "self",
        "name",
    ]
    assert get_type_hints(InboxFailureInjector.checkpoint) == {
        "name": str,
        "return": type(None),
    }
