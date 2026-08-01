### Task 1: Runtime Models and Ownership-Free Type Boundary

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/__init__.py`
- Create: `obsidian_kb_skill/scripts/inbox_tx/models.py`
- Create: `tests/test_inbox_tx_models.py`

**Interfaces:**
- Consumes: stdlib only.
- Produces: `ApplyStatus`, `RestoreStatus`, `TransactionState`,
  `InboxTransactionIssue`, `FileIdentity`, `FileMetadata`, `RecoveryDebris`,
  `InboxApplyResult`, `InboxRestoreResult`, `InboxFailure`,
  `InboxTransactionError`, and `InboxFailureInjector`.

- [ ] **Step 1: Write frozen-model and dependency RED tests**

Create tests that import every type, reject mutation of frozen results, enforce
`applied`/status consistency through direct-constructor `__post_init__`
validation, require Vault-relative result paths, and use the AST import graph to
prove `models.py` does not import `inbox_plan` through an absolute, relative,
aliased, or `from` import. There is no separate factory API in this task.

```python
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
```

- [ ] **Step 2: Run the model tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_models.py -q
```

Expected: collection fails because `inbox_tx.models` does not exist.

- [ ] **Step 3: Implement exact independent model types**

Use these public shapes and validate relative paths in `__post_init__` without
resolving the filesystem:

```python
ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]
RestoreStatus = Literal[
    "ready", "restored", "already_restored", "blocked", "recovery_required"
]

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

@dataclass(frozen=True)
class InboxFailure:
    code: str
    message: str
    restore_id: str | None
    recovery_location: Path | None
    warnings: tuple[str, ...]
    recovery_debris: RecoveryDebris | None
    business_mutation_started: bool
```

The direct constructors are the only construction API. Their `__post_init__`
methods enforce these exact runtime invariants without touching the filesystem:

- `InboxApplyResult.applied` is exactly
  `(InboxApplyResult.status == "applied")`;
- `InboxRestoreResult.applied` is exactly
  `(InboxRestoreResult.status == "restored")`;
- a runtime status outside its declared `Literal` values raises `ValueError`;
- `source` is nonempty and Vault-relative; optional `destination`, `backup`,
  `InboxTransactionIssue.path`, `InboxFailure.recovery_location`, and every
  `RecoveryDebris.location` are nonempty and Vault-relative when present;
- Vault-relative means not absolute and containing no empty, dot, or parent
  component; validation is lexical and never calls `resolve()` or accesses the
  filesystem;
- a runtime debris classification outside `"incomplete"`/`"unknown"` raises
  `ValueError`.

Define `InboxTransactionError` with `__init__(failure: InboxFailure)`; store the
same frozen object on `.failure` and initialize the exception message from
`failure.message`. Define the injector as a protocol with
`checkpoint(name: str) -> None`. `inbox_tx/__init__.py` must remain an internal
package marker and must not wildcard re-export internals.

- [ ] **Step 4: Run model tests and static import checks**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_models.py -q
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_tx
```

Expected: all model tests pass; compileall exits `0`.

- [ ] **Step 5: Commit the independent runtime model boundary**

```bash
git add obsidian_kb_skill/scripts/inbox_tx tests/test_inbox_tx_models.py
git commit -m "refactor: define inbox transaction runtime models"
```

---

