# Inbox Transaction Capability Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unsafe prepared-path Inbox boundary with a capability-
scoped, crash-recoverable per-note transaction that is used by the real CLI and
fails closed without overwriting unknown Vault data.

**Architecture:** `inbox_transaction.py` becomes a thin public façade over a
focused internal `inbox_tx` package. One context-bound session owns a persistent
Vault-level Inbox lock, path capabilities, recovery record, live backups/stage,
and exact journal state through durable commit, abort, rollback, or recovery-
required handling. Offline restore reopens only persisted schema-2 state in a
fresh process.

**Tech Stack:** CPython 3.11+, stdlib `dataclasses`, `enum`, `fcntl`, `hashlib`,
`json`, `os`, `pathlib`, `stat`, existing PyYAML/planner/audit/Vault policies,
pytest, uv, build.py, wheel/install/runtime test harnesses.

## Global Constraints

- Follow
  `docs/superpowers/specs/2026-07-19-inbox-transaction-capability-session-design.md`
  exactly. It supersedes the old Task 4/5 boundary and every conflicting Task 6
  locking, journal, truncated-tail, rollback, and restore mechanism while
  preserving the old Tasks 6–9 product outcomes that the specification names.
- Create `fix/inbox-transaction-capability-session` in a fresh sibling worktree
  from the final Reviewer-accepted HEAD of
  `design/inbox-transaction-capability-session` using
  `superpowers:using-git-worktrees`.
- At branch creation, record that exact 40-character HEAD once as
  `Implementation base: <hash>` and the then-current `master` commit once as
  `Master base: <hash>` in the ignored task report using `apply_patch`. Every
  review/final command must read the recorded values, assert the implementation
  base remains an ancestor, and assert `master` remains exact; never recompute a
  replacement baseline.
- Never edit, commit, merge, or switch `master`; never push unless the user
  changes the standing instruction.
- Do not cherry-pick `5f8d2df`; Wave 3 is evidence only. Reuse an idea only
  after a fresh RED test proves it belongs in the new ownership model.
- Preserve accepted Tasks 1–3: strict source snapshots, byte-preserving plans,
  and pure static-index plans.
- Mutation is supported only on CPython 3.11+ Linux/macOS on a local filesystem
  with the complete mutation capability contract. Windows and network mounts
  are mutation-unsupported.
- Planning remains available everywhere. Preview opens a recovery record only
  after `PreviewCapabilityProbe` proves component no-follow path binding.
- Source, destination, and managed index paths must remain outside the entire
  `.obsidian-kb-backups/` control namespace.
- No business mutation precedes durable source/index backups, rendered
  destination stage, schema-2 manifest, and `backup-ready` journal state.
- Acquire one persistent Vault Inbox advisory lock without waiting; do not
  unlink, rename, tombstone, or age-steal the lock file.
- Do not store owned fds, identities, expected journal bytes, or backup payloads
  in mutable process-global registries.
- Every fd-owning factory owns all locally opened descriptors until it returns
  successfully. Any exception before return closes them in reverse order;
  successful return is the only ownership-transfer point. If an operation
  directory already exists, the typed failure carries its incomplete
  `RecoveryDebris` after local descriptors are closed.
- Do not expose `PreparedInboxOperation` or public `prepare_inbox_operation()`.
- Every task follows RED → focused GREEN → relevant regression → commit → exact-
  range spec review → code-quality review. Do not begin the next task until both
  reviewers accept the current task.
- Keep the known generated-payload drift isolated until Task 9. Do not claim the
  full suite is green before `build.py` and `build.py --check` run there.

## Execution Preflight

At execution time, use `superpowers:using-git-worktrees`, then run:

```bash
git branch --show-current
git status --short --branch
git rev-parse HEAD
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_inbox_transaction.py \
  tests/test_backup_policy.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q
```

Expected: branch `fix/inbox-transaction-capability-session`, clean worktree,
and the selected baseline tests pass. Print the design and `master` HEADs once,
then record the literal outputs as `Implementation base: <hash>` and
`Master base: <hash>` in
`.superpowers/sdd/progress.md` using `apply_patch`:

```bash
git rev-parse design/inbox-transaction-capability-session
git rev-parse master
```

Verify the new implementation branch starts exactly there before any edit:

```bash
BASE=$(sed -n 's/^Implementation base: //p' .superpowers/sdd/progress.md)
MASTER_BASE=$(sed -n 's/^Master base: //p' .superpowers/sdd/progress.md)
test "$(git rev-parse HEAD)" = "$BASE"
test "$(git rev-parse master)" = "$MASTER_BASE"
```

## File Responsibility Map

- `obsidian_kb_skill/scripts/inbox_transaction.py`: stable public apply/restore
  façade and type re-exports only.
- `obsidian_kb_skill/scripts/inbox_restore.py`: offline preview and guarded
  restore orchestration.
- `obsidian_kb_skill/scripts/inbox_tx/models.py`: runtime states, identities,
  issues, results, failures, debris, and injector protocol; no planner import.
- `obsidian_kb_skill/scripts/inbox_tx/paths.py`: platform probes, bound Vault
  directories, no-follow traversal, durable fd I/O, link/replace/unlink.
- `obsidian_kb_skill/scripts/inbox_tx/lock.py`: persistent `.locks/inbox.lock`,
  `flock`, owner diagnostics, verification, and deterministic release.
- `obsidian_kb_skill/scripts/inbox_tx/recovery.py`: schema-2 manifest, backups,
  destination stage, journal chain, unresolved scan, and crash-tail repair.
- `obsidian_kb_skill/scripts/inbox_tx/session.py`: online prepare/apply state and
  complete resource lifetime.
- `obsidian_kb_skill/scripts/inbox_tx/rollback.py`: exact owned-state rollback
  and shared restore primitives.
- `obsidian_kb_skill/scripts/process_inbox.py`: compatibility CLI adapter only.
- Tests split by the same boundaries; end-to-end product behavior stays in
  `test_inbox_transaction.py`, `test_inbox_restore.py`, and existing CLI tests.

---

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

### Task 2: Bound Path Capabilities and Platform Probes

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/paths.py`
- Create: `tests/test_inbox_tx_paths.py`

**Interfaces:**
- Consumes: `FileIdentity`, `FileMetadata`, `InboxFailure`, existing
  `validate_vault_root()` policy.
- Produces:

```python
@dataclass(frozen=True)
class CapabilitySupport:
    supported: bool
    code: str | None
    message: str | None

@dataclass(frozen=True)
class PreviewCapabilitySupport:
    supported: bool
    code: str | None
    message: str | None
    serialization: Literal["shared-lock", "double-read"] | None

    def __post_init__(self) -> None:
        if self.supported != (self.serialization is not None):
            raise ValueError("preview support and serialization must agree")

class MutationCapabilityProbe(Protocol):
    def probe(self, vault: Path) -> CapabilitySupport: ...

class PreviewCapabilityProbe(Protocol):
    def probe(self, vault: Path) -> PreviewCapabilitySupport: ...

@dataclass(frozen=True)
class CapabilityProviders:
    mutation: MutationCapabilityProbe
    preview: PreviewCapabilityProbe

def default_capability_providers() -> CapabilityProviders: ...

class VaultCapability:
    @classmethod
    def open(cls, vault: Path) -> "VaultCapability": ...
    def __enter__(self) -> "VaultCapability": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def open_parent(self, relative: Path) -> "BoundDirectory": ...
    def revalidate_public_chain(self, relative: Path) -> None: ...
    def close(self) -> tuple[str, ...]: ...

def read_regular_at(parent: "BoundDirectory", name: str) \
        -> tuple[int, bytes, FileIdentity, FileMetadata]: ...
def write_new_durable_at(parent: "BoundDirectory", name: str, payload: bytes) \
        -> tuple[int, FileIdentity]: ...
def link_no_overwrite_at(
    source_parent: "BoundDirectory",
    source_name: str,
    destination_parent: "BoundDirectory",
    destination_name: str,
) -> None: ...
```

- [ ] **Step 1: Write traversal, namespace, and capability RED tests**

Cover real nested paths, a symlink at every ancestor depth, dangling final
symlink, FIFO/non-regular objects, parent traversal, absolute paths, and source/
destination/index paths under `.obsidian-kb-backups`. Inject missing `dir_fd`,
`O_NOFOLLOW`, directory fsync, hard-link, and `flock` support. Assert mutation
and preview probes are distinct and preview fails before opening a record when
safe no-follow traversal is absent. Assert `CapabilityProviders` is frozen,
`default_capability_providers()` returns stateless production adapters, and
fake mutation/preview adapters can be supplied without monkeypatching globals.
Parametrize preview support as unsupported/`None`, supported/`shared-lock`, and
supported/`double-read`; reject every inconsistent combination such as
supported/`None` or unsupported/non-`None`. This return value, not a later
global `fcntl` lookup, is the complete orchestration decision.
Fault-inject `VaultCapability.open()` after each local descriptor acquisition;
assert every pre-return failure closes the exact opened fds in reverse order and
that no `VaultCapability` ownership escapes.

```python
@pytest.mark.parametrize(
    "relative",
    [Path(".obsidian-kb-backups/x.md"), Path("../outside.md")],
)
def test_business_path_rejects_control_or_parent_namespace(relative: Path) -> None:
    with pytest.raises(InboxTransactionError) as caught:
        validate_business_relative(relative, label="Inbox source")
    assert caught.value.failure.code == "unsafe-inbox-business-path"
```

- [ ] **Step 2: Run path tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_paths.py -q
```

Expected: missing module/API failures.

- [ ] **Step 3: Implement no-follow descriptor traversal**

Open the validated Vault root once. Traverse each component with
`os.open(component, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC, dir_fd=fd)`,
validate with `fstat`, and close intermediate fds deterministically. Never
return a verified free-floating `Path` as a capability. Store the lexical root
only for relative diagnostics.

```python
def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )

def _identity(result: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=result.st_dev,
        inode=result.st_ino,
        size=result.st_size,
        mtime_ns=result.st_mtime_ns,
    )
```

`revalidate_public_chain()` must reopen from the bound Vault root and compare
every expected directory identity. Add `validate_business_relative()` and a
separate recovery-relative validator; both reject absolute/dot/parent/empty
components, while only business validation rejects `.obsidian-kb-backups`.

- [ ] **Step 4: Implement durable fd-relative mutation primitives**

Implement exact-write loops, `fsync` for every file, `fsync` for every parent
directory entry change, exclusive creation, regular-file checks, hard-link
no-overwrite publication, expected-identity unlink, expected-identity/hash
replace, and reverse-order close warnings. Treat `FileExistsError` as occupied,
not a retry signal.

- [ ] **Step 5: Implement mutation and preview probes**

Mutation probe requires CPython 3.11+, Linux/macOS, required membership in
`os.supports_dir_fd`, `O_NOFOLLOW`, directory fsync, and importable
`fcntl.flock`. Preview probe requires only secure bound no-follow traversal and
identity, then returns `serialization="shared-lock"` when `flock` is available
or `serialization="double-read"` when safe path binding exists without it.
Unsupported preview returns `serialization=None`. Do not create a CLI/
environment bypass. Document in code that network mount semantics remain
outside the guarantee even if primitive checks pass.
`default_capability_providers()` constructs the two production adapters; later
session/restore internals receive the frozen bundle explicitly while public
façades construct this default when no internal bundle is supplied.

`VaultCapability.open()` keeps locally opened fds behind an `ExitStack` (or an
equivalent explicit `try/finally`) until the fully initialized object is ready.
Disarm that cleanup only on successful return; all earlier failures close in
reverse order.

- [ ] **Step 6: Run path and shared path-policy regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_paths.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py tests/test_environment_contract.py -q
```

Expected: all selected tests pass with no out-of-Vault reads/writes.

- [ ] **Step 7: Commit path capabilities**

```bash
git add obsidian_kb_skill/scripts/inbox_tx/paths.py \
  tests/test_inbox_tx_paths.py
git commit -m "fix: bind inbox transaction paths to descriptors"
```

---

### Task 3: Persistent Vault Inbox Lock

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/lock.py`
- Create: `tests/test_inbox_tx_lock.py`

**Interfaces:**
- Consumes: `VaultCapability`, bound/durable path primitives, model failures.
- Produces:

```python
@dataclass
class InboxVaultLock:
    fd: int
    restore_id: str
    operation: Literal["apply", "restore"] | None
    warnings: list[str]

    @classmethod
    def acquire_exclusive(
        cls,
        vault: VaultCapability,
        restore_id: str,
        operation: Literal["apply", "restore"],
    ) -> "InboxVaultLock": ...

    @classmethod
    def acquire_shared_existing(
        cls,
        vault: VaultCapability,
        restore_id: str,
    ) -> "InboxVaultLock": ...

    def write_owner(self) -> None: ...
    def verify_public_binding(self) -> None: ...
    def close(self) -> tuple[str, ...]: ...
```

- [ ] **Step 1: Write persistent-lock RED tests**

Use separate processes/open descriptions to prove nonblocking exclusive busy,
automatic crash release, same lock for apply/restore, persistent pathname after
normal release, owner corruption as warning, replacement preservation, first-
creation file and `.locks` parent fsync, and no `.released`/tombstone growth.
Prove `acquire_shared_existing()` never creates or writes the lock, uses
`LOCK_SH|LOCK_NB`, permits concurrent previews, reports an exclusive holder as
busy, and treats a missing/unsafe lock as recovery-required. Inject failures
after open, binding validation, owner parsing, and before/after `flock`; assert
the locally owned fd is closed exactly once on every pre-return exception for
both acquisition modes. A shared holder has `operation is None`, and
`write_owner()` rejects it without changing bytes.

```python
def test_lock_path_persists_after_release(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    with VaultCapability.open(vault) as capability:
        lock = InboxVaultLock.acquire_exclusive(capability, RESTORE_ID, "apply")
        lock.write_owner()
        assert lock.close() == ()
    assert (vault / LOCK_RELATIVE).is_file()
```

- [ ] **Step 2: Run lock tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_lock.py -q
```

Expected: missing lock module/API failures.

- [ ] **Step 3: Implement anchored persistent lock creation/acquisition**

Create `.obsidian-kb-backups/inbox/.locks/inbox.lock` only through bound
directory fds for `acquire_exclusive()`. Fsync the new file and `.locks` parent.
Open no-follow, verify a regular file, acquire
`fcntl.flock(fd, LOCK_EX|LOCK_NB)`, and map busy to `inbox-lock-busy`. The fd is
authoritative ownership. `acquire_shared_existing()` opens only the existing
bound lock and takes `LOCK_SH|LOCK_NB`; it performs no create, truncate, owner
write, or directory mutation.

Both factories retain local ownership through an `ExitStack` (or equivalent
`try/finally`) and transfer the fd only when returning a complete
`InboxVaultLock`. Every earlier exception unlocks if needed and closes exactly
once in reverse acquisition order.

- [ ] **Step 4: Implement crash-tolerant owner diagnostics and release**

While locked, parse old diagnostics only as crash-tolerant warning metadata;
the secure unresolved-record scan remains authoritative. After session
prevalidation, an exclusive apply/restore holder writes the exact canonical
schema-2 owner object by truncate, write loop, fsync, and binding verification:

```python
owner = {
    "operation": operation,
    "pid": os.getpid(),
    "restore_id": restore_id,
    "schema": 2,
    "timestamp": utc_timestamp(),
}
```

Normal release uses unlock/close only. Never unlink or rename the path. Collect
all warnings, and keep close idempotent.

- [ ] **Step 5: Run lock, retention, and path regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_lock.py tests/test_backup_policy.py \
  tests/test_path_safety_e2e.py -q
```

Expected: all selected tests pass; a killed lock holder leaves no live lock.

- [ ] **Step 6: Commit the persistent lock**

```bash
git add obsidian_kb_skill/scripts/inbox_tx/lock.py \
  tests/test_inbox_tx_lock.py
git commit -m "fix: serialize inbox transactions with a persistent lock"
```

---

### Task 4: Schema-2 Recovery Store and Exact Journal

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/recovery.py`
- Create: `tests/test_inbox_tx_recovery.py`

**Interfaces:**
- Consumes: planner-independent recovery inputs constructed by the session,
  path capabilities, and model types. `recovery.py` must not import
  `inbox_plan.py`.
- Produces:

```python
@dataclass(frozen=True)
class RecoverySourceInput:
    path: Path
    raw: bytes
    sha256: str
    identity: FileIdentity
    metadata: FileMetadata

@dataclass(frozen=True)
class RecoveryDestinationInput:
    path: Path
    rendered: bytes
    rendered_sha256: str

@dataclass(frozen=True)
class RecoveryIndexInput:
    path: Path
    before: bytes
    before_sha256: str
    after_sha256: str
    identity: FileIdentity
    metadata: FileMetadata

@dataclass(frozen=True)
class RecoveryInputs:
    source: RecoverySourceInput
    destination: RecoveryDestinationInput
    index: RecoveryIndexInput | None

@dataclass(frozen=True)
class ManifestSource:
    path: Path
    backup: Path
    sha256: str
    identity: FileIdentity
    metadata: FileMetadata

@dataclass(frozen=True)
class ManifestDestination:
    path: Path
    stage: Path
    absent: Literal[True]
    rendered_sha256: str

@dataclass(frozen=True)
class ManifestIndex:
    action: Literal["append"]
    path: Path
    backup: Path
    before_sha256: str
    after_sha256: str
    identity: FileIdentity
    metadata: FileMetadata

@dataclass(frozen=True)
class ManifestV2:
    schema: Literal[2]
    restore_id: str
    operation: Literal["apply"]
    created_at: str
    source: ManifestSource
    destination: ManifestDestination
    index: ManifestIndex | None

@dataclass(frozen=True)
class RecoverySummary:
    restore_id: str
    location: Path
    logical_phase: str | None
    resolved: bool
    debris: RecoveryDebris | None

@dataclass
class RecoveryRecord:
    @classmethod
    def create(
        cls,
        vault: VaultCapability,
        restore_id: str,
        inputs: RecoveryInputs,
        injector: InboxFailureInjector | None,
    ) -> "RecoveryRecord": ...

    @classmethod
    def open_existing(
        cls, vault: VaultCapability, restore_id: str
    ) -> "RecoveryRecord": ...

    def append_event(self, phase: str, data: Mapping[str, object]) -> None: ...
    def close(self) -> tuple[str, ...]: ...

def scan_unresolved_records(vault: VaultCapability) \
        -> tuple[RecoveryDebris | RecoverySummary, ...]: ...
```

- [ ] **Step 1: Write manifest/backups/stage RED tests**

Assert exact schema-2 key sets, canonical JSON/newline, restore-ID grammar,
relative path cross-constraints, control-namespace rejection, source/index
backup bytes, destination stage bytes, hashes, mode/mtime metadata, no host path,
file/parent fsync ordering, and live fds. Reject schema 1, unknown keys, bad
types/hashes, mismatched backup/stage paths, symlinks, and unknown top-level
Inbox recovery entries. Use the Task 1 AST helper to prove `recovery.py` has no
absolute, relative, aliased, or `from` import of `inbox_plan`.

Fault-inject `RecoveryRecord.create()` after operation-directory creation,
backup open/write/fsync, destination-stage open/write/fsync, manifest
open/write/fsync, journal open/write/fsync, and each parent fsync. At every
pre-return failure, assert a close trace in reverse acquisition order, no leaked
fd count, and a typed `InboxTransactionError` whose failure contains the exact
incomplete `RecoveryDebris` once the operation directory exists. Add the same
local-ownership/close assertions for every failing `open_existing()` checkpoint.

- [ ] **Step 2: Write journal/state-machine RED tests**

Parametrize every legal and illegal phase transition from the spec. Assert exact
phase data keys, sequence, `previous_hash`, canonical event hash bytes, complete
expected-file compare under journal `flock`, file/operation-dir fsync, optional
index branch, malformed complete line rejection, unknown-tail rejection, and no
prefix-only acceptance.

```python
def test_event_hash_excludes_hash_and_newline() -> None:
    event = event_without_hash(sequence=0, phase="record-created")
    expected = sha256_bytes(canonical_json(event))
    stored = encode_event(event)
    assert json.loads(stored)["event_hash"] == expected
    assert stored.endswith(b"\n")
```

- [ ] **Step 3: Run recovery tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_recovery.py -q
```

Expected: missing recovery module/API failures.

- [ ] **Step 4: Implement exact manifest and durable record creation**

Implement the full `ManifestV2` shape from the spec. Create/bind the restore-ID
directory exclusively. Create source/index backups and
`destination/<destination.path>` stage exclusively; fsync exact bytes and every
new parent entry. Persist canonical manifest and initial `record-created` only
after their required inputs are durable. Retain open source/index/stage fds.

`create()` and `open_existing()` keep every local fd in an `ExitStack` (or
equivalent explicit `try/finally`) until a fully initialized `RecoveryRecord`
can be returned. Successful return is the only ownership transfer. A failure
after the operation directory is created first closes all local fds, then raises
the structured failure with the Vault-relative incomplete `RecoveryDebris`;
cleanup failure text is appended to warnings without replacing the primary
issue.

- [ ] **Step 5: Implement the hash-chained journal parser/appender**

Keep one verified journal fd per record. Before each append, take journal
`LOCK_EX`, compare all current bytes with expected bytes, validate schema/data/
transition, append one canonical event, fsync file and operation directory,
advance expected bytes, and unlock. Implement the complete transition table,
including `backup-ready → rolling-back`, `crash-classified`, and restore retry.

- [ ] **Step 6: Implement unresolved scan and repair primitives**

Under the Vault lock, scan only `.locks/` and real restore-ID directories.
Classify terminal/unresolved/incomplete/unknown entries exactly. Implement:

- partial-tail truncate/fsync/`journal-repaired`;
- missing/empty/partial-first journal bootstrap from verified manifest hash;
- `crash-classified` construction from stable observations;
- `rolling-back` exact-original completion to `rolled-back`;
- no repair of malformed newline-terminated events.

These are recovery-layer primitives; Task 7 decides when offline restore may
invoke them.

- [ ] **Step 7: Run recovery, path, lock, and retention regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_recovery.py tests/test_inbox_tx_paths.py \
  tests/test_inbox_tx_lock.py tests/test_backup_policy.py -q
```

Expected: all selected tests pass and ordinary retention preserves exact
`inbox/` without hiding similarly named timestamp backups.

- [ ] **Step 8: Commit the persistent recovery protocol**

```bash
git add obsidian_kb_skill/scripts/inbox_tx/recovery.py \
  tests/test_inbox_tx_recovery.py
git commit -m "feat: persist inbox recovery protocol v2"
```

---

### Task 5: Context-Bound Prepare and Abort Session (Task 4R Gate)

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/session.py`
- Create: `tests/test_inbox_tx_session.py`
- Modify: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Modify: `tests/test_inbox_transaction.py`

**Interfaces:**
- Consumes: ready `InboxPlanItem`, probes, Vault capability, persistent lock,
  unresolved scan, recovery record.
- Produces:

```python
class InboxTransactionSession:
    @classmethod
    def open(
        cls,
        vault: Path,
        item: InboxPlanItem,
        *,
        injector: InboxFailureInjector | None = None,
        capabilities: CapabilityProviders | None = None,
    ) -> "InboxTransactionSession": ...

    def __enter__(self) -> "InboxTransactionSession": ...
    def prepare(self) -> None: ...
    def abort_prepared(self, code: str) -> None: ...
    def final_result(self) -> InboxApplyResult: ...
    def close(self) -> None: ...
```

- [ ] **Step 1: Write state/lifetime RED tests**

Cover `NEW→LOCKED→PREPARED`, explicit abort, automatic normal-context abort,
exception abort, incomplete debris before manifest, durable abort after
manifest, pre-record blocked, lock busy, prior unresolved record, unsupported
mutation, closed-session rejection for every operation, idempotent close, and
`final_result()` only after `CLOSED`. Inject fake `CapabilityProviders` directly
into `open()` to prove the supplied mutation probe is called exactly once before
Vault/recovery open, the preview probe is not called, and production defaults
are used only when `capabilities is None`.

```python
def test_prepared_session_cannot_escape_context(tmp_path: Path) -> None:
    vault, item = make_ready_item(tmp_path)
    tx = InboxTransactionSession.open(vault, item)
    with tx:
        tx.prepare()
        assert tx.state is TransactionState.PREPARED
        tx.abort_prepared("test-abort")
    result = tx.final_result()
    assert result.status == "rolled_back"
    with pytest.raises(InboxTransactionError, match="closed"):
        tx.prepare()
```

- [ ] **Step 2: Write zero-business-mutation checkpoint RED tests**

Inject static probe, lock, scan, owner, operation mkdir/parent-fsync, backup,
stage, manifest, record-created, backup-ready, and abort checkpoints. Assert
exact source/index bytes, destination absence, relative restore/debris data,
warnings, mutation flag false, and the correct blocked/rolled-back/
recovery-required status.

- [ ] **Step 3: Run session tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_session.py -q
```

Expected: missing session API/state failures.

- [ ] **Step 4: Implement one-owner preparation lifetime**

`open()` validates only immutable/syntactic inputs and stores the supplied
frozen `CapabilityProviders`, or constructs `default_capability_providers()`
when it is `None`. `__enter__()` establishes the context-lifetime guard and
returns without filesystem mutation. `prepare()` calls the stored mutation
probe, opens the Vault, allocates restore ID, acquires the exclusive lock with
`InboxVaultLock.acquire_exclusive()`, scans unresolved records, revalidates
item/source/destination/index/rendered bytes, writes owner, builds planner-
independent `RecoveryInputs`, creates the recovery record, and reaches durable
`backup-ready` while retaining every fd and lock on `self`; only `session.py`
imports `InboxPlanItem`.

Use instance attributes only:

```python
self._vault: VaultCapability | None
self._lock: InboxVaultLock | None
self._record: RecoveryRecord | None
self._capabilities: CapabilityProviders
self._state: TransactionState
self._warnings: list[str]
self._rollback_actions: list[str]
self._business_mutation_started: bool
self._closed: bool
```

- [ ] **Step 5: Implement abort, close, and final-result ordering**

`abort_prepared()` verifies original public state and appends `aborted`.
`__exit__()` automatically aborts an unterminated prepared context, then closes
record, lock, and Vault in reverse order while collecting warnings. A durable
terminal state is not rewritten by later fd-close warnings. `final_result()`
constructs and caches one frozen result only after `CLOSED`.

`__exit__()` suppresses only a handled `InboxTransactionError` after it has
mapped the failure through abort/rollback/recovery-required state. It never
suppresses `KeyboardInterrupt`, `SystemExit`, or another `BaseException`;
resource close still runs for them.

- [ ] **Step 6: Replace the old prepared-path implementation boundary**

Make `inbox_transaction.py` a thin type façade for the implemented types; do not
add `apply_inbox_item()` until Task 6. Delete old global registries, lock-path
cleanup, `.discarded` logic, `PreparedInboxOperation`, and public
`prepare_inbox_operation()`. Rewrite old tests around session behavior instead
of preserving private helpers.

- [ ] **Step 7: Run the Task 4R gate and forbidden-symbol scan**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_session.py tests/test_inbox_tx_lock.py \
  tests/test_inbox_tx_recovery.py tests/test_inbox_tx_paths.py \
  tests/test_inbox_transaction.py tests/test_inbox_plan.py \
  tests/test_backup_policy.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q
! rg -n "PreparedInboxOperation|prepare_inbox_operation|_HELD_LOCKS|_OPERATION_IDENTITIES|_RECOVERY_PREAMBLES|_BOUND_NAMESPACE_IDENTITIES" \
  obsidian_kb_skill
```

Expected: all tests pass; `rg` returns no matches.

- [ ] **Step 8: Commit and independently review Task 4R**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/inbox_tx/session.py \
  tests/test_inbox_tx_session.py tests/test_inbox_transaction.py
git commit -m "refactor: scope inbox preparation to a session"
```

Do not start Task 6 until exact-range reviewers return spec `PASS` and quality
`APPROVED` for Tasks 1–5 together.

---

### Task 6: Transactional Apply, Audit, Source-Last, and Rollback (Task 5R)

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/rollback.py`
- Modify: `obsidian_kb_skill/scripts/inbox_tx/session.py`
- Modify: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Modify: `tests/test_inbox_tx_session.py`
- Modify: `tests/test_inbox_transaction.py`

**Interfaces:**
- Consumes: prepared session, destination stage fd, static-index plan,
  `audit_note_text()`, live backup fds.
- Produces:

```python
def apply_inbox_item(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxApplyResult: ...

@dataclass
class RollbackResources:
    vault: VaultCapability
    record: RecoveryRecord
    source_backup_fd: int
    destination_stage_fd: int
    destination_installed_identity: FileIdentity | None
    index_backup_fd: int | None
    index_installed_identity: FileIdentity | None

def rollback_known_state(
    resources: RollbackResources,
    failure: InboxFailure,
) -> tuple[tuple[str, ...], tuple[str, ...]]: ...
```

`rollback.py` must not import `session.py`; the session constructs
`RollbackResources` and applies the returned actions/warnings to its state.

- [ ] **Step 1: Write clean-apply and ordering RED tests**

Assert durable phase order, destination exact bytes, optional index exact post-
image, safe fd-read audit through `audit_note_text`, source removal last, final
public revalidation, durable committed before lock release, stage name removed,
and result frozen after close.

```python
result = apply_inbox_item(vault, item)
assert result.status == "applied"
assert result.applied is True
assert not (vault / item.source).exists()
assert (vault / item.proposal.destination).read_bytes() == (
    item.proposal.rendered_bytes
)
assert phases(vault, result.restore_id)[-1] == "committed"
```

- [ ] **Step 2: Write public-path race and no-overwrite RED tests**

Cover public ancestor rebinding before/after destination, index, audit, and
source operations; destination file/dangling symlink appearance; actual
hard-link unsupported with destination absent; link error with exact published
inode; unknown link target; destination replacement with the exact rendered
bytes on a different inode; index identity/hash changes; index replacement with
the exact post-image bytes on a different inode; source same bytes/new inode;
control-namespace paths; and two notes sharing one index. The same-bytes/new-
inode cases must be RED because content equality alone never proves live
transaction ownership.

- [ ] **Step 3: Write full rollback checkpoint RED matrix**

Inject destination link/parent-fsync/stage-unlink, destination journal, index
temp create/write/fsync/recheck/replace/parent-fsync/journal, audit, source
recheck/unlink/parent-fsync/journal, final verify, committed append/fsync,
destination cleanup, index restore, and source restore. Every row asserts exact
business bytes plus status, restore ID, warnings, debris, mutation flag, and
rollback actions. Use the Task 1 AST helper to prove `rollback.py` has no
absolute, relative, aliased, or `from` import of `session.py`.

- [ ] **Step 4: Run apply tests and confirm RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_inbox_tx_session.py -q
```

Expected: missing `apply_inbox_item()` and mutation behavior failures.

- [ ] **Step 5: Implement destination, index, audit, and source-last flow**

In the same open session:

1. Link the verified recovery destination stage to the absent destination.
2. On link error, reobserve absent/exact-stage/unknown and abort/rollback/
   require recovery accordingly.
3. Fsync/verify destination, unlink stage name, append `destination-installed`.
4. For index append, create a deterministic exclusive sibling temp, fsync,
   recheck before identity/hash, replace, fsync/verify, append `index-installed`.
5. Read installed destination through a bound fd, verify rendered bytes, decode
   strict UTF-8, call `audit_note_text()`, append `audit-passed` with warnings.
6. Reopen/recheck source identity/hash, unlink/fsync parent last, append
   `source-removed`.
7. Revalidate all public/recovery/lock bindings and append `committed`.

- [ ] **Step 6: Implement exact owned-state rollback**

Rollback runs while the same lock and capabilities remain live. Restore source
first when absent using source backup and no-overwrite publication. Restore
index only when the public object has both the exact installed index identity
and the expected after-hash. Remove destination only when the public object has
both the exact transaction-owned stage/installed identity and the expected
rendered hash. If either half differs—even when bytes are identical on a new
inode—preserve the unknown object and stop destructive steps. Append `rolling-
back`, then `rolled-back` after exact original state or `recovery-required` with
sorted observations. These identity-and-hash conjunctions govern live in-
session rollback; Task 7 follows the specification's separately constrained
fresh-process observation rules, where inode identity is not persisted as an
authoritative cross-process ownership claim.

- [ ] **Step 7: Implement the thin public façade**

The façade creates one session, executes inside context, and freezes the result
after context exit:

```python
def apply_inbox_item(vault, item, *, injector=None):
    tx = InboxTransactionSession.open(vault, item, injector=injector)
    with tx:
        tx.prepare()
        tx.apply()
    return tx.final_result()
```

Map expected internal failures into typed results; do not expose a traceback or
free-standing prepared object. The public façade intentionally exposes no
capability-probe parameter; only the internal session seam accepts injected
providers for deterministic tests.

- [ ] **Step 8: Run transaction and shared-policy regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_inbox_tx_session.py \
  tests/test_inbox_plan.py tests/test_folder_index_policy.py \
  tests/test_audit_vault.py tests/test_backup_policy.py \
  tests/test_path_safety_e2e.py -q
```

Expected: all selected tests pass and every checkpoint has a proven terminal
state.

- [ ] **Step 9: Commit and independently review Task 5R**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/inbox_tx/session.py \
  obsidian_kb_skill/scripts/inbox_tx/rollback.py \
  tests/test_inbox_tx_session.py tests/test_inbox_transaction.py
git commit -m "fix: apply inbox notes in one transaction session"
```

---

### Task 7: Fresh-Process Restore Preview and Guarded Apply

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_restore.py`
- Create: `tests/test_inbox_restore.py`
- Modify: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Modify: `obsidian_kb_skill/scripts/inbox_tx/recovery.py`
- Modify: `obsidian_kb_skill/scripts/inbox_tx/rollback.py`
- Modify: `tests/test_inbox_tx_recovery.py`
- Modify: `tests/test_inbox_transaction.py`

**Interfaces:**
- Consumes: schema-2 record parser, preview/mutation probes, persistent lock,
  shared restore primitives.
- Produces:

```python
def preview_inbox_restore(vault: Path, restore_id: str) -> InboxRestoreResult: ...

def restore_inbox_operation(
    vault: Path,
    restore_id: str,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxRestoreResult: ...

def _preview_inbox_restore(
    vault: Path,
    restore_id: str,
    *,
    capabilities: CapabilityProviders,
) -> InboxRestoreResult: ...

def _restore_inbox_operation(
    vault: Path,
    restore_id: str,
    *,
    capabilities: CapabilityProviders,
    injector: InboxFailureInjector | None,
) -> InboxRestoreResult: ...
```

The two underscore-prefixed functions are internal injection seams. Public
wrappers preserve the stable signatures above and pass
`default_capability_providers()`; there is no CLI, environment-variable, or
public probe bypass.

- [ ] **Step 1: Write read-only preview RED tests**

Cover clean committed preview, already aborted/rolled-back/restored, busy shared
lock, safe no-`flock` double-read warning, unsupported preview before record
open, missing/unsafe lock, schema 1/unknown, missing/corrupt manifest/backup/
stage, relative-path violations, symlink/control-namespace attacks, destination/
index/source unknown edits, incomplete and unknown debris, and zero writes.
Inject a fake preview probe through `_preview_inbox_restore()` and assert it is
called exactly once, the mutation probe is not called, blocked support returns
before lock/record open, and the public wrapper constructs only default
providers. A fake `serialization="shared-lock"` result must call
`acquire_shared_existing()` exactly once; a fake `serialization="double-read"`
result must never touch the lock module and must execute the stable double-read
protocol. These tests must not monkeypatch or re-read global `fcntl` support.

- [ ] **Step 2: Write every crash-prefix and repair RED test**

Build persisted records in a fresh subprocess for `record-created`,
`backup-ready`, `destination-installed`, `index-installed`, `audit-passed`,
`source-removed`, `rolling-back`, `restore-started`, partial first
`record-created`, partial `rolled-back`, and partial restored events. Assert
bootstrap/repair, exact `crash-classified`, original/partial/unknown routing,
and no dependency on session globals.

- [ ] **Step 3: Write guarded restore/failure RED tests**

Cover source-first restoration, mode/mtime best effort, index restore,
destination removal, final `restored`, repeated idempotency, other unresolved
record blocking, unsupported mutation, state change after preview, every
restore checkpoint, and retry after `restore-recovery-required`. Inject fake
providers through `_restore_inbox_operation()` and assert only its mutation
probe runs before Vault/lock/recovery open; public restore exposes no provider
parameter.

- [ ] **Step 4: Run restore tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_restore.py -q
```

Expected: missing restore module/API failures.

- [ ] **Step 5: Implement preview with the separate capability contract**

Validate restore ID, call the stored preview probe exactly once, and branch only
on its `PreviewCapabilitySupport`. If unsupported, return blocked before record
open. For `serialization="shared-lock"`, take the nonblocking shared lock through
`InboxVaultLock.acquire_shared_existing()`. For `serialization="double-read"`,
never open the lock; double-read the same bound identities/bytes and add
`unserialized-preview`. Do not inspect global `fcntl` again after the injected
probe result. The shared path never creates, truncates, or writes owner
diagnostics. Parse only a valid prefix, classify tail/debris, and derive actions
from manifest, backups, and observed public hashes.

- [ ] **Step 6: Implement exclusive restore, crash classification, and repair**

Call the injected mutation probe, acquire the exclusive Vault lock through
`InboxVaultLock.acquire_exclusive()`, scan other unresolved records, reopen
target, and revalidate. Repair only the exact allowed partial tail; bootstrap an
empty prefix from verified manifest; append
`crash-classified`; then abort, complete rolled-back, restore, or require
recovery according to the transition table. Restore source first, then index,
then remove a known destination, verify exact final state, append `restored`,
and preserve the record.

- [ ] **Step 7: Re-export restore APIs and run focused regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_restore.py tests/test_inbox_tx_recovery.py \
  tests/test_inbox_tx_lock.py tests/test_inbox_tx_paths.py \
  tests/test_inbox_transaction.py -q
```

Expected: all selected preview, crash, repair, restore, and apply tests pass.

- [ ] **Step 8: Commit restore support**

```bash
git add obsidian_kb_skill/scripts/inbox_restore.py \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/inbox_tx/recovery.py \
  obsidian_kb_skill/scripts/inbox_tx/rollback.py \
  tests/test_inbox_restore.py tests/test_inbox_tx_recovery.py \
  tests/test_inbox_transaction.py
git commit -m "feat: recover inbox transactions in a fresh process"
```

---

### Task 8: CLI Compatibility and Truthful Product Integration

**Files:**
- Modify: `obsidian_kb_skill/scripts/process_inbox.py`
- Modify: `tests/test_process_inbox.py`
- Modify: `tests/test_json_output.py`
- Modify: `tests/test_cli_integration.py`
- Modify: `tests/test_path_safety_e2e.py`

**Interfaces:**
- Consumes: `plan_inbox()`, `legacy_plan_dict()`, apply/preview/restore façade,
  typed results.
- Produces: compatible `plan_note()`, `apply_plan()`, `process_vault()`, and
  `main()` plus actual counts and exit codes.

- [ ] **Step 1: Write product-path and compatibility RED tests**

Prove default/`--plan` remains read-only; legacy text records and top-level JSON
plan list remain recognizable; malformed/unsafe/custom-control-Inbox input exits
2 untouched; mixed results have exact counts; rolled-back exits 3; any recovery-
required exits 4; unsupported mutation/preview is structured; restore preview/
apply works; JSON stdout is one document with no traceback/absolute path.

Add an AST/monkeypatch contract that Inbox apply no longer calls direct
`Path.write_bytes`, `Path.unlink`, or `append_static_index_entry`.

- [ ] **Step 2: Run CLI tests and confirm RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_process_inbox.py tests/test_json_output.py \
  tests/test_cli_integration.py tests/test_path_safety_e2e.py -q
```

Expected: new transaction/result/restore assertions fail against the legacy
direct-write CLI.

- [ ] **Step 3: Replace orchestration with one frozen typed plan**

`process_vault()` calls `plan_inbox()` once. Apply passes those exact ready items
to `apply_inbox_item()` without reclassification/date drift. Convert to legacy
dictionaries only at the adapter boundary. Keep these callables:

```python
def plan_note(path: Path, vault: Path) -> dict[str, Any]: ...
def apply_plan(
    plan: dict[str, Any], vault: Path, silent: bool = False
) -> InboxApplyResult: ...
def process_vault(
    vault: Path,
    apply: bool,
    inbox_name: str = "00-Inbox",
    silent: bool = False,
) -> list[dict[str, Any]]: ...
def main(argv: list[str] | None = None) -> int: ...
```

The legacy `apply_plan()` safely replans only its named contained source, then
uses the transaction façade; it never restores direct mutation.

- [ ] **Step 4: Implement result/restore serialization and exit severity**

For apply JSON, retain each plan entry and add one typed `result` object with
status/applied/relative paths/restore ID/issue/warnings/debris/mutation flag.
Compute counts from results, not plans. Use severity `0 < 2 < 3 < 4`.

```text
obsidian-process-inbox VAULT --restore RESTORE_ID
obsidian-process-inbox VAULT --restore RESTORE_ID --apply
```

Text diagnostics go to stderr; JSON mode emits one stdout document.

- [ ] **Step 5: Run complete CLI/product regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_inbox_transaction.py \
  tests/test_inbox_restore.py tests/test_process_inbox.py \
  tests/test_json_output.py tests/test_cli_integration.py \
  tests/test_path_safety_e2e.py -q
```

Expected: all selected tests pass; plan/preview do not create business state;
real apply contains no legacy direct mutation.

- [ ] **Step 6: Commit the product integration**

```bash
git add obsidian_kb_skill/scripts/process_inbox.py \
  tests/test_process_inbox.py tests/test_json_output.py \
  tests/test_cli_integration.py tests/test_path_safety_e2e.py
git commit -m "fix: route inbox cli through transactions"
```

---

### Task 9: Safety Documentation, Help, and Distribution Synchronization

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `obsidian_kb_skill/scripts/process_inbox.py` (`--help` only)
- Modify: `tests/test_build.py`
- Modify: `tests/test_cli_integration.py`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_wheel_install.py`
- Modify: `tests/test_installers.py`
- Modify: `tests/windows_installer_smoke.ps1`
- Regenerate through `build.py`: `skills/obsidian-knowledge-base/`, `platforms/`,
  `obsidian_kb_skill/scripts/resources/`, standard manifest/mirrors

**Interfaces:**
- Consumes: final CLI, backup layout, statuses, platform matrix.
- Produces: narrow bilingual safety docs/help and synchronized distributable
  helpers. The later README information-architecture branch remains separate.

- [ ] **Step 1: Write docs/help/distribution RED contracts**

Assert both READMEs and help contain plan/apply/restore commands, default read-
only behavior, exact backup root, Vault-level serialization, abort/rollback/
recovery semantics, exits 0/2/3/4, Linux/macOS local mutation support, Windows
structured apply block, secure preview gate, and no claim to defeat an
uncooperative same-user writer. Assert generated helper mirrors include
`inbox_restore.py` and every `inbox_tx/*.py` file.

Add hostile-runtime RED contracts: standard Skill runner and wheel console entry
run Inbox plan outside the repository; Bash-installed payload runs plan from a
neutral CWD. Update the Windows smoke script so that, when actually executed on
a Windows runner, it runs plan and receives a structured unsupported result for
apply instead of mutating. `tests/test_installers.py` verifies the script/command
contract only; it must not be cited as Windows runtime execution. Task 10 owns
the exact-HEAD Windows execution/artifact gate.

- [ ] **Step 2: Run docs/build tests and confirm RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_build.py tests/test_cli_integration.py \
  tests/test_skill_runtime.py tests/test_wheel_install.py \
  tests/test_installers.py tests/test_lazy_references.py -q
```

Expected: documentation/mirror assertions, wheel/installer hostile-runtime
contracts, Windows smoke-script contract, and the known build drift fail before
the docs/generated/script changes are made.

- [ ] **Step 3: Update only Inbox safety documentation/help**

Document in Chinese and English:

```text
obsidian-process-inbox VAULT --plan
obsidian-process-inbox VAULT --apply
obsidian-process-inbox VAULT --restore RESTORE_ID
obsidian-process-inbox VAULT --restore RESTORE_ID --apply
```

Explain fail-closed parsing, per-note recovery, `.obsidian-kb-backups/inbox/`,
no overwrite, exact abort/rollback versus recovery-required, debris, persistent
lock, local-filesystem platform limits, and read-only preview behavior. Do not
add lifecycle plans, confidence, ten-item limits, enrichment, or background
processing.

- [ ] **Step 4: Regenerate every canonical mirror and verify zero drift**

```bash
uv run --locked --extra dev python build.py
uv run --locked --extra dev python build.py --check
```

Expected: the first command updates canonical generated assets; the second
reports all generated artifacts current. Inspect `git status --short` and stage
only actual generated changes.

- [ ] **Step 5: Run docs, build, packaging, and installed-runtime regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_build.py tests/test_lazy_references.py \
  tests/test_templates.py tests/test_skill_runtime.py \
  tests/test_wheel_install.py tests/test_installers.py \
  tests/test_environment_contract.py -q
```

Expected: all selected tests pass, including the formerly deferred generated-
payload gate.

- [ ] **Step 6: Commit documentation and generated assets**

```bash
git add README.md README_EN.md CHANGELOG.md \
  obsidian_kb_skill/scripts/process_inbox.py \
  obsidian_kb_skill/scripts/resources skills platforms \
  tests/test_build.py tests/test_cli_integration.py \
  tests/test_skill_runtime.py \
  tests/test_wheel_install.py tests/test_installers.py \
  tests/windows_installer_smoke.ps1
git commit -m "docs: publish inbox recovery workflow"
```

Review staged paths before commit; do not include ignored controller files or
unrelated user changes.

---

### Task 10: Full Verification, Hostile Runtime, and Independent Branch Review

**Files:**
- No planned production or test modification. A fresh failure stops this task
  and opens a separately reviewed TDD repair task before verification restarts.
- Write ignored evidence under `.superpowers/sdd/`.

**Interfaces:**
- Consumes: all accepted Task 1–9 commits.
- Produces: complete current-state evidence, exact review package, accepted
  feature HEAD, and unchanged `master` evidence.

- [ ] **Step 1: Run build, full suite, and package gates**

```bash
uv run --locked --extra dev python build.py --check
uv run --locked --extra dev pytest
uv run --locked --extra dev pytest \
  tests/test_wheel_install.py tests/test_installers.py \
  tests/test_environment_contract.py -q
```

Expected: zero failures and zero generated drift.

- [ ] **Step 2: Run hostile-CWD, installed-entry-point, and Windows gates**

```bash
uv run --locked --extra dev pytest \
  tests/test_skill_runtime.py tests/test_wheel_install.py \
  tests/test_installers.py tests/test_doctor.py -q
```

Expected local evidence: standard Skill runner and wheel console entry run plan
from hostile/neutral CWD, and the Bash-installed payload runs plan outside the
repository. This pytest command proves the Windows smoke contract text only.

For actual Windows runtime evidence, use exactly one of these paths:

1. On a Windows runner at the implementation HEAD, run and retain the complete
   output plus exit code:

   ```powershell
   $head = (git rev-parse HEAD).Trim()
   pwsh -NoProfile -File tests/windows_installer_smoke.ps1
   if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
   Write-Output "verified-head=$head"
   ```

2. On a non-Windows host, obtain an externally produced Windows CI/job artifact
   for the exact implementation HEAD. Record its literal metadata in
   `.superpowers/sdd/windows-smoke-exact-head.json` using `apply_patch` with
   exact keys `head`, `runner_os`, `command`, `exit_code`, `job_url`, and
   `artifact_sha256`, then validate it:

   ```bash
   HEAD=$(git rev-parse HEAD)
   HEAD="$HEAD" uv run --locked --extra dev python - <<'PY'
   import json
   import os
   from pathlib import Path

   evidence = json.loads(
       Path(".superpowers/sdd/windows-smoke-exact-head.json").read_text(
           encoding="utf-8"
       )
   )
   assert set(evidence) == {
       "artifact_sha256", "command", "exit_code", "head", "job_url", "runner_os"
   }
   assert evidence["head"] == os.environ["HEAD"]
   assert evidence["runner_os"].lower().startswith("windows")
   assert evidence["command"] == (
       "pwsh -NoProfile -File tests/windows_installer_smoke.ps1"
   )
   assert evidence["exit_code"] == 0
   assert evidence["job_url"].startswith("https://")
   assert len(evidence["artifact_sha256"]) == 64
   int(evidence["artifact_sha256"], 16)
   PY
   ```

The final Reviewer must inspect the referenced job/artifact and confirm that
the reported commit equals `git rev-parse HEAD`; a locally authored JSON file
alone is not evidence. Under the standing no-push instruction, do not trigger
remote CI without new user authority. If neither path is available, local work
may be reported ready for Windows verification, but Task 10 and release
acceptance remain incomplete.

- [ ] **Step 3: Prove scope, removed architecture, and worktree cleanliness**

```bash
BASE=$(sed -n 's/^Implementation base: //p' .superpowers/sdd/progress.md)
MASTER_BASE=$(sed -n 's/^Master base: //p' .superpowers/sdd/progress.md)
test -n "$BASE"
test -n "$MASTER_BASE"
printf '%s\n' "$BASE" | rg -q '^[0-9a-f]{40}$'
printf '%s\n' "$MASTER_BASE" | rg -q '^[0-9a-f]{40}$'
test "$(git merge-base HEAD "$BASE")" = "$BASE"
test "$(git rev-parse master)" = "$MASTER_BASE"
git diff --check "$BASE"..HEAD
git status --short
git log --oneline "$BASE"..HEAD
git worktree list
! rg -n "PreparedInboxOperation|prepare_inbox_operation|_HELD_LOCKS|_OPERATION_IDENTITIES|_RECOVERY_PREAMBLES|_BOUND_NAMESPACE_IDENTITIES" \
  obsidian_kb_skill
```

Expected: diff check clean, worktree clean, only scoped commits, forbidden scan
empty, and the machine assertion proves `master` is still exactly the pre-work
HEAD recorded once in the task report.

- [ ] **Step 4: Generate the exact final review package**

```bash
BASE=$(sed -n 's/^Implementation base: //p' .superpowers/sdd/progress.md)
MASTER_BASE=$(sed -n 's/^Master base: //p' .superpowers/sdd/progress.md)
test -n "$BASE"
test "$(git rev-parse master)" = "$MASTER_BASE"
test "$(git merge-base HEAD "$BASE")" = "$BASE"
/Users/shaopc/.agents/superpowers/skills/subagent-driven-development/scripts/review-package \
  "$BASE" HEAD .superpowers/sdd/inbox-transaction-final-review.md
```

Give one fresh Reviewer the approved spec, this plan, exact range, failure/crash
matrices, full/build/package/hostile outputs, generated manifest, and unchanged
master evidence. Require explicit verdicts for threat model, capability/session
lifetime, lock, manifest/journal, crash repair, rollback/restore, platform gate,
real CLI integration, and no Critical/Important findings.

- [ ] **Step 5: Resolve findings with focused repair waves**

For every valid finding, use `superpowers:receiving-code-review`, then
`superpowers:systematic-debugging` and TDD. One tightly coupled fixer owns one
repair wave; record RED/GREEN evidence, commit independently, rerun the complete
gate, and request a fresh exact-range review. Never hide a known failure by
excluding it.

- [ ] **Step 6: Freeze the accepted implementation branch**

Only after `Ready to merge: Yes` and all current gates are green, use
`superpowers:finishing-a-development-branch`. Under the standing instruction,
keep the branch/worktree intact and record the accepted HEAD; do not merge or
push. Cherry-pick accepted commits to `fix/inbox-data-safety` only as a separate
reversible integration step with its own full regression. After that regression,
continue the next roadmap risk domain; do not rerun the old superseded Inbox
Tasks 4–9.
