### Task 4: Backup Store, Manifest, Journal, and Locks

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Create: `tests/test_inbox_transaction.py`
- Modify: `obsidian_kb_skill/scripts/backup_policy.py`
- Modify: `tests/test_backup_policy.py`

**Interfaces:**
- Consumes: ready `InboxPlanItem`, Vault resolvers, `sha256_bytes()`.
- Produces:

```python
ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]

class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...

@dataclass(frozen=True)
class InboxApplyResult:
    source: Path
    destination: Path | None
    status: ApplyStatus
    applied: bool
    restore_id: str | None
    backup: Path | None
    issue: InboxIssue | None
    warnings: tuple[str, ...] = ()
    rollback_actions: tuple[str, ...] = ()

@dataclass(frozen=True)
class PreparedInboxOperation:
    vault: Path
    item: InboxPlanItem
    restore_id: str
    operation_root: Path
    manifest: Mapping[str, Any]
    held_locks: tuple[Path, ...]

def prepare_inbox_operation(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> PreparedInboxOperation: ...
```

- [ ] **Step 1: Write RED tests for zero-mutation preparation failures**

Create a `FailAt` injector:

```python
class FailAt:
    def __init__(self, checkpoint: str) -> None:
        self.checkpoint_name = checkpoint

    def checkpoint(self, name: str) -> None:
        if name == self.checkpoint_name:
            raise OSError(f"injected:{name}")
```

Parametrize `lock-source`, `lock-index`, `backup-root`, `backup-source-write`,
`backup-source-fsync`, `backup-index-write`, `manifest-write`,
`manifest-fsync`, and `journal-backup-ready`. At every point assert source and
index bytes unchanged, destination absent, Vault outside path empty, and any
created lock released unless it represents a durable recovery record.

Test concurrent preparation of the same source and shared index. Assert the
second operation returns a stable busy/blocked result without stealing the
first lock. Test symlinked backup root and lock root fail closed.

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q
```

Expected: missing module/API failures.

- [ ] **Step 3: Implement contained durable operation preparation**

Use `.obsidian-kb-backups/inbox/<restore-id>/` with an ASCII UTC timestamp and
random hex suffix. Create the operation directory with `exist_ok=False`. Store
only Vault-relative POSIX paths in `manifest.json`. Write JSON with sorted keys,
UTF-8, and a final newline.

Provide these internal primitives with exact responsibilities:

```python
def _checkpoint(injector: InboxFailureInjector | None, name: str) -> None: ...
def _write_new_durable(path: Path, payload: bytes) -> None: ...
def _append_event(operation: PreparedInboxOperation, phase: str, **data: Any) -> None: ...
def _acquire_lock(vault: Path, key: str, restore_id: str) -> Path: ...
def _release_locks(paths: Iterable[Path]) -> tuple[str, ...]: ...
```

`_write_new_durable()` must use exclusive creation, flush, and `os.fsync()`.
Acquire source and optional index locks in sorted hash-key order. Back up exact
source/index bytes, verify their hashes after reading the backup, persist the
manifest, then append `backup-ready` before returning.

Update backup retention so the exact top-level `inbox` namespace is preserved
silently. It must not hide similarly named ordinary timestamp directories.

- [ ] **Step 4: Run preparation, backup, and path regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q
```

Expected: all pass; no injected preparation failure changes a business file.

- [ ] **Step 5: Commit the recovery store**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py \
  tests/test_inbox_transaction.py tests/test_backup_policy.py
git commit -m "feat: add inbox transaction recovery store"
```

---

