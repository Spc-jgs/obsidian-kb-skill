"""Planner-independent runtime models for Inbox transactions."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]
RestoreStatus = Literal[
    "ready", "restored", "already_restored", "blocked", "recovery_required"
]

_APPLY_STATUSES = frozenset(
    {"applied", "skipped", "blocked", "rolled_back", "recovery_required"}
)
_RESTORE_STATUSES = frozenset(
    {"ready", "restored", "already_restored", "blocked", "recovery_required"}
)
_DEBRIS_CLASSIFICATIONS = frozenset({"incomplete", "unknown"})


def _require_vault_relative(path: Path, field_name: str) -> None:
    if (
        not path.parts
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be a nonempty Vault-relative path")


class TransactionState(enum.Enum):
    NEW = "new"
    LOCKED = "locked"
    PREPARED = "prepared"
    MUTATING = "mutating"
    ABORTING = "aborting"
    ABORTED = "aborted"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    COMMITTED = "committed"
    RECOVERY_REQUIRED = "recovery_required"
    CLOSED = "closed"


@dataclass(frozen=True)
class InboxTransactionIssue:
    code: str
    message: str
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            _require_vault_relative(self.path, "path")


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class FileMetadata:
    mode: int
    mtime_ns: int


@dataclass(frozen=True)
class RecoveryDebris:
    restore_id: str
    location: Path
    classification: Literal["incomplete", "unknown"]

    def __post_init__(self) -> None:
        _require_vault_relative(self.location, "location")
        if self.classification not in _DEBRIS_CLASSIFICATIONS:
            raise ValueError(f"unknown recovery debris classification: {self.classification}")


@dataclass(frozen=True)
class InboxApplyResult:
    source: Path
    destination: Path | None
    status: ApplyStatus
    applied: bool
    restore_id: str | None
    backup: Path | None
    issue: InboxTransactionIssue | None
    warnings: tuple[str, ...] = ()
    rollback_actions: tuple[str, ...] = ()
    recovery_debris: RecoveryDebris | None = None
    business_mutation_started: bool = False

    def __post_init__(self) -> None:
        if self.status not in _APPLY_STATUSES:
            raise ValueError(f"unknown apply status: {self.status}")
        if self.applied != (self.status == "applied"):
            raise ValueError("applied must be true exactly when status is 'applied'")
        _require_vault_relative(self.source, "source")
        if self.destination is not None:
            _require_vault_relative(self.destination, "destination")
        if self.backup is not None:
            _require_vault_relative(self.backup, "backup")


@dataclass(frozen=True)
class InboxRestoreResult:
    restore_id: str
    status: RestoreStatus
    applied: bool
    actions: tuple[str, ...]
    conflicts: tuple[InboxTransactionIssue, ...]
    issue: InboxTransactionIssue | None = None
    warnings: tuple[str, ...] = ()
    recovery_debris: RecoveryDebris | None = None

    def __post_init__(self) -> None:
        if self.status not in _RESTORE_STATUSES:
            raise ValueError(f"unknown restore status: {self.status}")
        if self.applied != (self.status == "restored"):
            raise ValueError("applied must be true exactly when status is 'restored'")


@dataclass(frozen=True)
class InboxFailure:
    code: str
    message: str
    restore_id: str | None
    recovery_location: Path | None
    warnings: tuple[str, ...]
    recovery_debris: RecoveryDebris | None
    business_mutation_started: bool

    def __post_init__(self) -> None:
        if self.recovery_location is not None:
            _require_vault_relative(self.recovery_location, "recovery_location")


class InboxTransactionError(RuntimeError):
    def __init__(self, failure: InboxFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...
