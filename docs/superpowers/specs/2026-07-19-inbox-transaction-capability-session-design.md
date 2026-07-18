# Inbox Transaction Capability Session Design

**Date:** 2026-07-19

**Branch:** `design/inbox-transaction-capability-session`

**Base:** `fix/inbox-data-safety` at `c816607`

**Status:** Approved under the user's standing authorization to make scoped
architecture decisions, keep high-risk work isolated, and continue without a
repeated confirmation pause.

## Decision Summary

Replace the pathname-only Task 4/5 handoff with one capability-scoped Inbox
transaction session. The same session owns the Vault capability, recovery
record, backup handles, journal state, and a persistent Vault-level Inbox lock
from preparation through commit or rollback.

The public mutation entry remains `apply_inbox_item()`. No public API returns a
prepared pathname object that can outlive its verified file descriptors or
locks.

This design keeps accepted Inbox Tasks 1–3 and the product outcomes of Tasks
6–9. It supersedes the old transaction/recovery architecture and the old Task
4/5 implementation boundary.

## Why the Previous Contract Is Invalid

The accepted Task 4 implementation returns a `PreparedInboxOperation` that
contains paths and lock paths. The Wave 3 exploration grew to 1,318 lines and
stored lock fds, operation identities, recovery preambles, and namespace
identities in four process-global registries. Its operation fd still closes
before preparation returns.

Three deterministic probes prove that more pathname checks cannot repair that
lifecycle:

1. The canonical restore-ID directory can be replaced after its final public
   check while checks through the old fd continue. Preparation then returns a
   pathname naming unknown content.
2. An unknown journal line can be inserted between an exact read and append.
   A later check only moves the same window.
3. If the `.discarded/` namespace is replaced after operation creation, safe
   quarantine refuses the replacement but cannot guarantee deletion of the
   incomplete operation.

The root cause is not a missing `stat()`. The safety capability is destroyed at
the Task 4 return boundary, while Task 5 expects to use mutable pathnames later.
The WIP process-global registries neither survive a restart nor provide a
bounded resource lifetime; they also retain complete source/index bytes in
memory after successful preparation.

The transaction code is not yet connected to the real product path.
`process_inbox.py` still performs direct destination writes, source unlink, and
static-index append. Branch completion must therefore prove the CLI uses the
new façade rather than merely proving isolated transaction tests.

## Supersession

This spec supersedes these parts of the 2026-07-16 Inbox data-safety design and
plan:

- the single-file `inbox_transaction.py` responsibility map;
- `prepare_inbox_operation() -> PreparedInboxOperation` as a public boundary;
- source/index hash-path lock creation and deletion;
- process-global lock, identity, preamble, or namespace registries;
- unconditional acceptance of a truncated final journal line;
- `.discarded/` quarantine as a preparation cleanup requirement;
- reservation-based mutation fallbacks on unsupported platforms;
- the requirement to implement only in the original integration worktree;
- old Task 4 tests that require every incomplete operation directory to vanish.

The following remain authoritative:

- accepted Tasks 1–3: strict snapshots, byte-preserving plans, and pure static
  index plans;
- one note per independent transaction, not a batch-wide transaction;
- exact backup and durable recovery metadata before business mutation;
- destination, index, audit, source-last mutation order;
- no overwrite of existing destinations or observed unknown bytes;
- hash-guarded rollback and restore;
- read-only restore preview and idempotent guarded restore;
- typed truthful results, JSON behavior, and exit codes `0`, `2`, `3`, `4`;
- compatibility, documentation, distribution sync, packaging, hostile-CWD,
  full-suite, and independent final-review gates from Tasks 6–9;
- no merge, push, or `master` work without a later user decision.

The evidence-only commit `5f8d2df` is not an accepted implementation and must
not be cherry-picked wholesale. Individual low-level ideas may be re-evaluated
under this design, with fresh tests and review.

## Scope

This redesign covers the Inbox safety kernel only:

- runtime capability and lock lifetime;
- secure and durable recovery-store I/O;
- journal integrity and transaction state;
- destination/index/source mutations;
- automatic rollback and offline restore;
- typed failures, warnings, and recovery debris;
- product-path integration through the existing Inbox CLI;
- focused module/test decomposition.

It does not add Inbox lifecycle features, semantic enrichment, reviewed plan
artifacts, template changes, README information-architecture work, token-budget
changes, or a general transaction framework for other commands.

## Threat Model

### Guaranteed within the supported environment

The implementation must fail closed for:

- symlinks, dangling symlinks, non-regular files, and out-of-Vault traversal;
- source identity/hash changes after planning;
- existing destinations and observed unknown destination/index/source bytes;
- crashes and injected failures at every durable or business mutation step;
- cooperating Skill apply/restore processes using the same Vault Inbox lock;
- observed replacement of recovery, lock, journal, backup, or business paths;
- malformed, reordered, duplicated, or hash-chain-invalid journal state at an
  active transaction boundary, and truncated state in normal online apply;
- unsupported platform or filesystem capability.

### Explicitly outside the prevention claim

No userspace sequence can guarantee permanent pathname identity against an
uncooperative process running as the same OS user with write access to the
Vault, deliberately changing paths between adjacent syscalls or ignoring an
advisory lock. That actor can also modify the Vault directly.

The implementation still detects such interference whenever it is observable
at a defined boundary and returns a typed safe failure. Tests must not claim a
timeless verify-to-return guarantee that the operating system does not provide.

### Supported mutation environment

Mutation in this iteration is supported only on CPython 3.11+ on Linux or
macOS, on a local filesystem, when a `MutationCapabilityProbe` establishes all
runtime primitives below. Windows and network/distributed mounts are outside
the mutation support contract; no unsafe override flag is provided. Runtime
primitive probes cannot certify mount topology, so passing them does not extend
the guarantee to a network/distributed filesystem.

The probe checks `os.supports_dir_fd`, required no-follow/open flags,
`fcntl.flock`, descriptor identity, and file/directory fsync support before an
operation directory is created. Static-probe failure returns `blocked` with no
recovery record. A probe in the recovery tree cannot prove semantics for a
nested destination mount, so the actual same-parent destination publication is
the authoritative filesystem test. If that primitive fails before publication,
the session removes only its identity-bound temp and durably rolls back; temp
cleanup uncertainty becomes `recovery_required`. The probe is an injectable
adapter in tests, not a CLI/environment-variable bypass.

The required semantics are:

- directory-relative open/stat/link/rename/unlink operations;
- no-follow opening of every traversed component;
- stable regular-file and directory identities from open descriptors;
- durable file and directory `fsync`;
- atomic exclusive destination publication through a hard-link/no-overwrite
  primitive on the same filesystem;
- advisory exclusive file locking compatible with `flock` semantics.

Planning remains available on every package-supported platform. Preview has a
separate injectable `PreviewCapabilityProbe`: it requires a securely bound
Vault root, component-by-component no-follow recovery traversal, and stable
descriptor identity. If those path capabilities are absent, preview returns
`blocked` with `unsupported-inbox-preview` without opening the requested record.
Where safe path binding and `flock` exist, preview uses the shared-lock
protocol. Where safe path binding exists but `flock` does not, it reads the
same bound record twice, requires identical identity and bytes, adds warning
`unserialized-preview`, and never authorizes restore apply. Apply and restore
mutation fail closed outside the supported mutation environment. README/help
must state this matrix exactly.

## Approaches Considered

### A. Capability-scoped session with one Vault Inbox lock — selected

One context manager owns every live descriptor and the transaction state. A
single persistent Vault-level Inbox lock serializes apply and restore. Inbox is
already processed item by item, so this gives up little useful concurrency and
removes multi-lock ordering, shared-index lock, stale-path lock, and tombstone
complexity.

### B. SQLite/WAL recovery coordinator

SQLite would make metadata transitions and owner records easier to query, but
filesystem note/index mutations are still outside the database transaction.
The database pathname remains replaceable by the same uncooperative writer,
and the design gains migrations and a second source of truth. It is rejected.

### C. Dedicated worker or supervisor process

A worker could hold all capabilities and provide strong process isolation, but
it adds IPC, lifecycle, packaging, observability, and cross-platform costs that
are disproportionate for a local Skill. It remains a future option if the
single-process session proves insufficient.

Sequential pathname revalidation without a session is not a fourth candidate;
the probes already demonstrate that it only moves the race window.

## Safety Invariants

1. No business-file mutation begins until source/index backups, manifest, and
   `backup-ready` journal state are durable.
2. The Vault Inbox lock is held across public precondition validation. Once an
   operation directory exists, it remains held until a durable `committed`,
   `aborted`, `rolled-back`, or `recovery-required` phase is written when the
   journal remains writable. A safe pre-record validation failure may release
   it without a journal event.
3. Session-owned descriptors and expected state never live in module globals.
4. Prepared state cannot be used after session close or outside its context.
5. Public ancestor chains are reopened from the bound Vault root and checked
   before and after every business mutation.
6. An existing destination, including a dangling symlink, is never overwritten.
7. The destination contains exactly the frozen rendered bytes.
8. The index is replaced only when its public identity and bytes match the
   frozen pre-image; rollback restores only the known post-image.
9. The source is unlinked last and only when its public identity and bytes still
   match the planned source.
10. A result is `applied` only after final public-state verification and a
    durable `committed` event. Descriptor-close/unlock warnings discovered
    afterward are returned without rewriting that durable business outcome.
11. Rollback changes only identities and hashes owned by this transaction.
    Unknown edits are preserved and produce `recovery_required`.
12. Cleanup and lock-release warnings are never discarded in favor of the
    primary error.
13. Incomplete recovery directories are retained and reported when identity-
    bound removal cannot be proved. The design does not depend on quarantine.
14. Persistent recovery state can be interpreted in a fresh process without
    any process-global identity registry.
15. Every path exposed in results, manifest, journal data, or diagnostics is
    Vault-relative; host absolute paths never enter persisted records or JSON.
16. Source, destination, and managed index paths are outside the entire
    `.obsidian-kb-backups/` control namespace. A custom Inbox name cannot place
    business notes inside recovery, lock, or operation trees.

## Module Architecture

Keep the current import path stable while making ownership explicit:

```text
obsidian_kb_skill/scripts/
├── inbox_transaction.py          # thin public façade and re-exports
├── inbox_restore.py              # offline preview and guarded restore
└── inbox_tx/
    ├── __init__.py               # internal package marker, no broad re-exports
    ├── models.py                 # states, results, failures, recovery metadata
    ├── paths.py                  # Vault/path capabilities and durable fd I/O
    ├── lock.py                   # persistent Vault-level Inbox advisory lock
    ├── recovery.py               # manifest, backups, journal, record parsing
    ├── session.py                # online transaction state machine/lifetime
    └── rollback.py               # exact owned-state rollback primitives
```

Tests split by the same responsibilities:

```text
tests/test_inbox_transaction.py       # public façade and end-to-end transaction
tests/test_inbox_tx_paths.py          # fd traversal, no-follow, durability
tests/test_inbox_tx_lock.py           # process serialization and crash release
tests/test_inbox_tx_recovery.py       # manifest, backups, journal chain
tests/test_inbox_tx_session.py        # lifecycle, state machine, failure mapping
tests/test_inbox_restore.py           # offline preview/apply and idempotency
```

Private helpers from the old tests are not compatibility APIs. Tests must use
the new unit boundary instead of preserving `_release_locks()`,
`_append_event()`, or `_open_bound_operation()` solely for test convenience.

### Dependency direction

`models.py` depends only on stdlib and defines its own runtime issue type; it
does not import the planner or `InboxIssue`.
`paths.py` depends only on stdlib and existing Vault validation policy.
`lock.py` and `recovery.py` depend on `models.py` and `paths.py`.
`rollback.py` depends on `models.py`, `paths.py`, and live recovery handles.
`session.py` orchestrates those units and consumes `InboxPlanItem` plus the
existing audit API. The façade and restore adapter depend inward; lower layers
never import `process_inbox.py`.

## Public Contracts

The stable façade remains:

```python
ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]

class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...

@dataclass(frozen=True)
class InboxTransactionIssue:
    code: str
    message: str
    path: Path | None = None

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

def apply_inbox_item(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxApplyResult: ...

RestoreStatus = Literal[
    "ready", "restored", "already_restored", "blocked", "recovery_required"
]

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

def preview_inbox_restore(vault: Path, restore_id: str) -> InboxRestoreResult: ...

def restore_inbox_operation(
    vault: Path,
    restore_id: str,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxRestoreResult: ...
```

`applied` is true only when `status == "applied"`. `source`, `destination`,
`backup`, and `RecoveryDebris.location` are Vault-relative when present.
`InboxRestoreResult.applied` is true only for `restored`.

Preview maps an exclusively held Vault lock to `blocked` with
`inbox-lock-busy`. A schema-2 record with an unsafe/missing persistent lock on
a mutation-supported platform, incomplete debris, unsupported schema, corrupt
manifest/backup, or unknown business bytes is `recovery_required`. Restore
apply revalidates the preview state: a safe actionable record on an unsupported
mutation platform is `blocked` with `unsupported-inbox-mutation`; an already
unsafe record remains `recovery_required`. `already_restored` is idempotent and
performs no write. Missing secure preview path capabilities return `blocked`
with `unsupported-inbox-preview` before the record is opened.

Expected validation, lock, platform, mutation, audit, rollback, and recovery
errors are converted to `InboxApplyResult` at the façade. Internal units use a
typed `InboxTransactionError` carrying:

```python
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

No traceback reaches normal CLI JSON/text output.

The façade maps an accepted planner `InboxIssue` into an
`InboxTransactionIssue`; low-level transaction modules never import
`inbox_plan.py`. `RecoveryDebris` is reserved for incomplete or unclassifiable
records. A complete durable recovery record is represented by `backup` and
`restore_id`, not mislabeled as debris.

`PreparedInboxOperation` and public `prepare_inbox_operation()` are removed.
There is no production caller of them on the accepted branch, and Task 4 has
not been accepted. If an internal prepared metadata view is useful, it is
session-bound, contains no lock paths/fds, and every accessor checks that the
session is open.

## Session Contract and State Machine

The internal API is intentionally context-bound. `apply()` advances internal
state but does not construct the frozen public result:

```python
tx = InboxTransactionSession.open(vault, item, injector=injector)
with tx:
    tx.prepare()
    tx.apply()
result = tx.final_result()
```

`apply_inbox_item()` is the only normal caller and owns this context. The
session has these states:

```text
NEW → LOCKED → PREPARED → MUTATING → COMMITTED → CLOSED
                   │          └──→ ROLLING_BACK → ROLLED_BACK → CLOSED
                   └──→ ABORTING → ABORTED → CLOSED
                                  └────────→ RECOVERY_REQUIRED → CLOSED
```

Invalid transitions raise a typed internal state error. `prepare()`, `apply()`,
journal append, backup access, commit, and rollback all reject calls after
`close()`. `close()` is deterministic and idempotent, but the context may not
report an `applied` result until terminal journal durability and cleanup
warnings are known.

`final_result()` is legal only in `CLOSED`, constructs the frozen result once,
and returns that same object on repeat calls. `__exit__()` closes live backup,
journal, operation, lock, and Vault fds in reverse ownership order and records
all close warnings before `final_result()` freezes them.

`abort_prepared(code)` is the explicit zero-business-mutation exit for Task 4R
and any caller that stops after preparation. It verifies the original business
state, appends durable `aborted`, and moves through `ABORTING` to `ABORTED`.
Leaving a context normally in `PREPARED` invokes
`abort_prepared("session-exit-without-apply")`; leaving it by exception enters
the same failure path. If exact original state or terminal journal durability
cannot be proved, the state becomes `RECOVERY_REQUIRED`.

The session exclusively owns:

- the bound Vault root fd;
- the persistent Vault Inbox lock fd;
- recovery namespace and operation directory fds;
- manifest and journal fds plus exact expected journal bytes/state;
- live source and optional index backup fds;
- current state, restore ID, warnings, rollback actions, and debris metadata;
- current known identities for owned temporary and installed objects.

No owned fd or complete backup payload is stored in a module-global object.
All fds use close-on-exec where supported and close in reverse ownership order.

## Vault-Level Inbox Lock

The lock path is persistent:

```text
.obsidian-kb-backups/inbox/.locks/inbox.lock
```

The path is created/opened relative to bound recovery directory fds with
no-follow semantics and verified as a regular file. The transaction attempts a
non-blocking exclusive advisory lock:

- busy lock: return `blocked` with code `inbox-lock-busy`, create no operation
  directory, and change no business bytes;
- acquired lock: the open fd, not pathname content, is authoritative ownership;
- normal release: unlock/close only; never unlink, rename, or tombstone the
  persistent lock file;
- crash: the OS releases the advisory lock when the process/fd dies;
- apply and restore mutation use the same lock.

On first creation, both lock bytes and the `.locks/` parent directory are
fsynced. Later owner updates use the already locked and identity-verified fd:
truncate, write canonical diagnostics, fsync, and verify the public binding.
They never replace the lock pathname. Diagnostics are canonical sorted-key
compact JSON plus newline with exact keys `schema` (`2`), `restore_id`, `pid`
(nonnegative integer), `timestamp` (UTC), and `operation` (`apply` or
`restore`).

While holding the lock, the session reads the previous diagnostic owner record.
It then securely scans every restore-ID entry under the bound Inbox recovery
root. Any incomplete, malformed, unknown-schema, nonterminal, or unresolved
`recovery-required` record blocks a new apply; restore may proceed only for its
target record and only when no different unresolved record exists. A malformed
or partial owner diagnostic is a warning, never evidence that recovery state is
safe. After the scan and item prevalidation succeed, the session writes current
owner diagnostics containing restore ID, PID, timestamp, and operation kind.
Diagnostics are a crash-safe hint and never override the OS lock or recovery
scan.

The scan allows only `.locks/` and real no-follow directories whose names match
the restore-ID grammar. Any other top-level entry is `unknown` recovery debris
and blocks mutation. `committed`, `aborted`, `rolled-back`, and `restored` are
resolved phases; nonterminal, `recovery-required`, and
`restore-recovery-required` records are unresolved.

Replacement observed while the fd is held produces `recovery_required`; the
session does not delete either object. Replacement by a writer that ignores the
advisory lock remains outside the prevention claim.

## Path Capabilities and Mutation Primitives

Every traversal starts from the bound Vault root fd. Each ancestor is opened
one component at a time as a real directory without following links. Final
objects are opened relative to their verified parent and validated through the
same fd with `fstat`.

Old open directory fds are capabilities to those objects, but do not prove the
objects remain on the public Vault path after a rename. Therefore the session
reopens and verifies the complete public ancestor chain from the Vault root
immediately before and after each business mutation.

### Destination

1. Verify public destination absence, treating every lexical entry and dangling
   symlink as occupied/unsafe.
2. Set `business_mutation_started=True`, then write frozen rendered bytes to an
   exclusive sibling temp through the bound destination parent fd; fsync and
   verify exact bytes/identity.
3. Publish with a same-filesystem kernel no-overwrite hard-link operation.
4. Fsync the destination parent, verify the public destination identity/hash,
   then unlink and durably remove the temp entry.

If the no-overwrite primitive is unsupported in the actual destination parent,
the session identity-cleans the temp and enters rollback. Exact cleanup yields
`rolled_back`; uncertain cleanup yields `recovery_required`. The design does
not reserve and later replace a public destination pathname.

### Static index

For an owned `append` plan, revalidate the public index identity and exact
before hash, write/fsync a sibling temp, revalidate again, then atomically
replace relative to the same bound parent fd. Fsync the parent and verify the
public after identity/hash. Other index actions do not mutate an index.

### Source

Immediately before unlink, reopen its public parent chain and require the exact
planned source identity/hash. Unlink relative to the bound parent fd, fsync the
parent, then verify public absence. Source removal is always the last business
mutation.

### Rollback

Live backup fds stay open until commit or rollback is complete. Rollback reads
from those fds rather than re-resolving mutable public backup paths. Persistent
backup files remain for crash recovery.

Source restoration uses an exclusive temp plus the same no-overwrite publish
primitive. Destination removal and index restoration require both the exact
transaction-owned identity where available and expected hash. Unknown objects
or bytes are retained and stop destructive rollback.

## Recovery Store and Manifest

Recovery records remain under:

```text
.obsidian-kb-backups/inbox/<restore-id>/
├── manifest.json
├── events.jsonl
├── source/00-Inbox/<note>.md
└── index/<target>/<index>.md
```

The new manifest uses schema version `2` and this exact shape (`index` is null
when no managed index mutation is planned):

```json
{
  "schema": 2,
  "restore_id": "2042-03-04-050607Z-0123456789abcdef",
  "operation": "apply",
  "created_at": "2042-03-04T05:06:07Z",
  "source": {
    "path": "00-Inbox/Idea.md",
    "backup": "source/00-Inbox/Idea.md",
    "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "identity": {"device": 1, "inode": 2, "size": 3, "mtime_ns": 4},
    "metadata": {"mode": 420, "mtime_ns": 4}
  },
  "destination": {
    "path": "30-Insights/Idea.md",
    "absent": true,
    "rendered_sha256": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  },
  "index": {
    "action": "append",
    "path": "30-Insights/INDEX.md",
    "backup": "index/30-Insights/INDEX.md",
    "before_sha256": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
    "after_sha256": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
    "identity": {"device": 1, "inode": 5, "size": 6, "mtime_ns": 7},
    "metadata": {"mode": 420, "mtime_ns": 7}
  }
}
```

Validation requires the exact key sets and JSON types above. `restore_id` must
match the restore directory name and
`YYYY-MM-DD-HHMMSSZ-[0-9a-f]{16}`. `created_at` is an ASCII UTC diagnostic
timestamp. Every hash uses `sha256:` plus exactly 64 lowercase hexadecimal
characters. Identity integers are nonnegative. `metadata.mode` is
`stat.S_IMODE()` restricted to `0..0o777`; ownership and special permission
bits are never restored. `mtime_ns` is nonnegative.

All paths are nonempty Vault-relative POSIX paths with no empty, dot, or parent
component. Source backup must equal `source/<source.path>` and index backup must
equal `index/<index.path>`. Source, destination, and index public paths must be
distinct, and none may start with `.obsidian-kb-backups`. The session repeats
this reserved-namespace check before opening any business capability.
`destination.absent` must be true. A non-null index must have action `append`,
distinct before/after hashes, and every listed field; other `StaticIndexPlan`
actions serialize as null because they cause no recovery mutation.

The file is canonical sorted-key compact JSON plus one final newline, created
exclusively, fsynced, hash-verified, and followed by an operation-directory
fsync. Runtime rollback may use identities while the same session remains
alive; offline recovery treats hashes and safe public path state as
authoritative because inode identity is not a portable persistent identifier.
The manifest never stores host absolute paths.

Rollback and restore best-effort reapply source/index `mode` and `mtime_ns`
only after exact content restoration. Metadata failure is a warning and does
not undo proven byte restoration. Tests cover mode/time restoration and warning
propagation; the implementation never calls `chown`.

The operation directory is exclusively created and immediately bound by fd.
Once created, it is retained as part of the recovery history. If preparation
fails before a complete durable manifest, it is classified as `incomplete`
debris and returned as `recovery_required`; no `.discarded/` move or unsafe
best-effort deletion is attempted. Business bytes must remain unchanged.

Schema `1` and unknown schemas fail closed in preview as unsupported. They are
not silently migrated because the old Task 4 format was never accepted or
shipped from this branch. A future explicit migration can be designed if real
Vault evidence requires it.

Ordinary backup retention continues to preserve the exact top-level `inbox/`
namespace. Automatic Inbox recovery-record pruning is outside this branch.

## Journal Contract

`events.jsonl` uses canonical sorted-key compact JSON with one final newline per
event. Every event has the exact keys `schema`, `restore_id`, `sequence`,
`previous_hash`, `phase`, `timestamp`, `data`, and `event_hash`.

- `schema` is integer `2`.
- `restore_id` matches the manifest and operation-directory name.
- `sequence` starts at `0` and increases by exactly one.
- `previous_hash` is null at sequence `0`; later it equals the preceding
  `event_hash`.
- `timestamp` is an ASCII UTC diagnostic timestamp.
- `event_hash` is the `sha256:` prefix followed by exactly 64 lowercase
  hexadecimal characters, computed over the canonical sorted-key compact JSON
  bytes of the other seven keys without a trailing newline.
- The stored line is the canonical form of all eight keys plus `\n`.

Phase names, exact `data` keys, and values are:

| Phase | Required `data` keys |
| --- | --- |
| `record-created` | `manifest_sha256` |
| `backup-ready` | `source_backup_sha256`, `index_backup_sha256` (hash or null) |
| `destination-installed` | `path`, `sha256`, `identity` |
| `index-installed` | `path`, `before_sha256`, `after_sha256`, `identity` |
| `audit-passed` | `warnings` (array of strings) |
| `source-removed` | `path`, `sha256`, `identity` |
| `committed` | `destination_sha256`, `index_sha256` (hash or null), `source_absent` (true) |
| `aborted` | `code`, `warnings`, `business_mutation_started` (false) |
| `rolling-back` | `code`, `business_mutation_started` |
| `rolled-back` | `actions`, `source_sha256`, `destination_absent` (true), `index_sha256` (hash or null) |
| `recovery-required` | `code`, `warnings`, `business_mutation_started`, `observations` |
| `journal-repaired` | `discarded_tail_sha256`, `discarded_length`, `resumes_phase` |
| `crash-classified` | `resumes_phase`, `classification`, `actions`, `observations` |
| `restore-started` | `actions` |
| `restored` | `actions`, `source_sha256`, `destination_absent` (true), `index_sha256` (hash or null) |
| `restore-recovery-required` | `code`, `warnings`, `completed_actions` |

Every path in event data is a validated Vault-relative manifest path. Hash and
identity objects use the manifest formats. Actions/warnings are arrays of
strings. `observations` is a path-sorted array of exact objects
`{"path": <relative path>, "state": "absent"|"hash", "sha256": <hash|null>}`;
`sha256` is null exactly when state is `absent`. No phase accepts additional
data keys. `crash-classified.classification` is exactly `original-state`,
`partial-mutation`, or `unknown`; its `resumes_phase` is the last valid apply
phase and its actions are path-sorted.

The legal phase transitions are:

```text
START → record-created
record-created → backup-ready | aborted | crash-classified | recovery-required
backup-ready → destination-installed | aborted | crash-classified
             | recovery-required
destination-installed → index-installed | audit-passed
                      | rolling-back | crash-classified | recovery-required
index-installed → audit-passed | rolling-back | crash-classified
                | recovery-required
audit-passed → source-removed | rolling-back | crash-classified
             | recovery-required
source-removed → committed | rolling-back | crash-classified
               | recovery-required
rolling-back → rolled-back | crash-classified | recovery-required
committed → restore-started
recovery-required → restore-started
crash-classified → aborted | restored | restore-started
                 | recovery-required | restore-recovery-required
restore-started → restored | crash-classified | restore-recovery-required
restore-recovery-required → restore-started
aborted | rolled-back | restored → no further mutation phase
```

`destination-installed → index-installed` is required when manifest `index` is
non-null; otherwise it must go directly to `audit-passed`. `journal-repaired`
is a maintenance overlay allowed after any valid non-`restored` phase. Its
`resumes_phase` must equal that preceding logical phase; the next transition is
validated as though the logical phase had not changed. A complete valid hash
chain with an illegal phase or transition is still rejected.

`crash-classified` is available only to offline restore after it holds the
exclusive Vault lock and compares manifest, valid journal prefix, backups, and
public business state. `resumes_phase` may name `record-created`,
`backup-ready`, `destination-installed`, `index-installed`, `audit-passed`,
`source-removed`, `rolling-back`, or `restore-started`. For an apply/rollback
prefix, exact original state yields `original-state` followed by durable
`aborted` and an `already_restored` result. For a `restore-started` prefix, exact
original state is followed by durable `restored`. Known transaction-owned
partial state yields `partial-mutation` followed by a new `restore-started`.
Unknown bytes, missing required backup, or ambiguous state yields `unknown`
followed by `recovery-required` for an apply/rollback prefix or
`restore-recovery-required` for a restore prefix; destructive restore does not
begin.

An active session keeps one verified journal fd open. Before append it locks
that fd exclusively, reads/compares the complete bytes with its exact expected
state, validates the chain, appends exactly one event, fsyncs the journal,
fsyncs the operation directory, updates expected state, then releases the
journal critical section. Unknown, duplicate, reordered, truncated, or invalid
tail state fails closed.

The Vault Inbox lock serializes cooperating transactions; the journal lock
makes the compare/append primitive locally complete and protects offline tools
that follow the same contract.

Offline preview may classify exactly one nonempty partial segment after the
last newline as crash residue. It never treats the segment as a completed
phase and derives actions from the manifest, valid prefix, backup hashes, and
observed business state. A malformed newline-terminated line is not truncation
and cannot be repaired automatically.

Restore apply acquires the exclusive Vault lock, re-reads the same identity and
bytes, and may repair only that exact partial tail. While holding the journal
lock it truncates to the last complete newline, fsyncs journal and operation
directory, then appends `journal-repaired` with the discarded bytes' hash and
length. It then appends `crash-classified` from the resumed logical phase and
follows the classification transition; it does not jump directly from an
arbitrary nonterminal phase to `restore-started`. Failure to reproduce,
truncate, durably record the repair, or classify observed state returns
`recovery_required` without business mutation. Normal online apply sessions
never ignore or repair a truncated/unknown tail.

## Transaction Data Flow

For one ready item:

1. Probe supported mutation capabilities.
2. Open and bind the Vault/recovery roots.
3. Allocate a restore ID in memory without creating a recovery path.
4. Acquire the persistent Vault Inbox lock without waiting.
5. Securely scan for every unresolved recovery record; block new apply if any
   exists.
6. Revalidate item, source identity/hash, destination absence, index plan, and
   rendered bytes from the public Vault tree.
7. Durably write current owner diagnostics through the locked fd.
8. Create and bind the operation directory.
9. Create exact source/index backups and retain their read fds.
10. Write/fsync schema-2 manifest and `record-created`.
11. Verify backups through the live fds; append/fsync `backup-ready`.
12. Install and verify destination; append/fsync `destination-installed`.
13. Install/verify an owned changed index; append/fsync `index-installed`.
14. Audit the installed note; append/fsync `audit-passed` with warnings.
15. Revalidate and unlink source last; append/fsync `source-removed`.
16. Revalidate public destination/index/source, recovery, journal, and lock
    bindings.
17. Append/fsync `committed`.
18. Close live backups/recovery capabilities, collect close warnings, and
    release the Vault Inbox lock.

Any exception after the operation directory exists enters failure handling
while the same session capabilities and lock remain live. If mutation started,
rollback restores source first when absent, restores a known index post-image,
and removes a known destination. It appends `rolled-back` only after exact
pre-state verification. Unknown state appends `recovery-required` when the
journal remains trustworthy and returns without overwriting unknown bytes.

## Error and Result Semantics

- `skipped`: no route, an existing destination discovered during planning, or
  an idempotent already-applied outcome; no new recovery record.
- `blocked`: invalid/stale plan, busy lock, or unsupported mutation environment
  before operation-directory creation; no business mutation or recovery debris.
- `rolled_back`: runtime preparation/mutation failure with a complete durable
  record and exact original business state proved, whether or not the first
  business mutation had begun. A durable `aborted` phase maps to this status.
- `recovery_required`: unknown business state, failed exact rollback, observed
  recovery/lock replacement, prior nonterminal record, incomplete operation
  debris, or a pre-terminal cleanup/binding failure requiring operator
  attention.
- `applied`: exact final business state and durable `committed` journal proved.

An error after operation-directory creation but before durable manifest returns
`recovery_required`, `business_mutation_started=False`, and explicit incomplete
`RecoveryDebris`. This intentionally replaces the old assertion that every
preparation failure deletes its operation directory.

Primary failures, rollback actions, cleanup failures, and lock-release failures
are accumulated deterministically. A secondary warning never replaces or hides
the primary issue. Every meaningful recovery/lock binding check occurs before
the terminal event; failure writes `recovery-required` when possible. After a
durable `committed`, descriptor close/unlock warnings cannot rewrite the
persisted transaction as noncommitted. They remain on the final `applied`
result, and a still-live OS lock naturally makes a later operation report busy.
The frozen result is constructed only by `final_result()` after context exit,
so these warnings cannot be lost.

## Offline Preview and Restore

Preview is read-only and never creates or writes a lock. On a mutation-supported
platform it opens the existing persistent lock safely and attempts a
non-blocking shared advisory lock before reading a schema-2 record. If an
apply/restore holds the exclusive lock, preview returns `blocked` with
`inbox-lock-busy`. A missing/unsafe lock on such a platform is
`recovery_required`. While holding the shared lock, preview validates
schema/paths/backups/journal prefix and reports actions, conflicts, warnings,
and debris from observed hashes.

If `PreviewCapabilityProbe` cannot bind the record without following links,
preview returns `unsupported-inbox-preview`. With safe path binding but no
`flock`, preview performs the double-read stable snapshot defined by the
support matrix and adds `unserialized-preview`. It can describe actions but
cannot authorize restore mutation on that platform.

Restore apply acquires the same Vault Inbox lock, scans for other unresolved
records, reopens/revalidates the target, and performs the exact truncated-tail
repair protocol when applicable. A nonterminal apply prefix is durably
`crash-classified`; original state terminates as `aborted`, known partial state
continues through `restore-started`, and unknown state becomes
`recovery-required`. Restoration is source-first, followed by known index
restoration and known destination removal. It never overwrites unknown edits.
Final state is verified and `restored` is durably journaled. Repeated restore is
idempotent.

An incomplete record without a valid manifest is reportable but not guessed.
The tool returns `recovery_required` with its Vault-relative location and
preserves it for manual inspection.

## CLI and Compatibility

The existing console entry point, Inbox name, routing, inferred metadata,
default read-only behavior, recognizable text plan, top-level JSON plan list,
and legacy callable names remain.

A custom Inbox name remains supported only when its resolved Vault-relative
path is outside `.obsidian-kb-backups/`; a control-namespace overlap is a
validation-blocked item and cannot reach transaction preparation.

`process_inbox.py` becomes an adapter over accepted `plan_inbox()` and the new
`apply_inbox_item()` façade. It must not call direct `write_bytes()`, `unlink()`,
or the mutating static-index compatibility API for Inbox apply.

Per-item typed results drive counts and the highest-severity exit code:

- `0`: all requested operations succeeded or were harmlessly skipped;
- `2`: validation/blocked items and no more severe outcome;
- `3`: runtime failures exactly rolled back and no recovery-required outcome;
- `4`: any recovery-required outcome.

JSON mode emits one document on stdout and no traceback. README/help documents
the recovery location, preview/apply commands, Vault-level serialization, and
supported mutation environment. The broad README reorganization remains on its
separate roadmap branch.

## Implementation Boundary

The redesign may remain reviewable in two implementation tasks without
reintroducing the invalid boundary:

- **Task 4R:** models, path capabilities, persistent lock, recovery/journal,
  and the context-bound session through durable `PREPARED`. It exposes no
  public prepared pathname object. Its tests keep the context open, explicitly
  call `abort_prepared()`, prove durable `aborted`, prove automatic abort on
  context exit, reject use after close, and perform zero business mutation.
- **Task 5R:** destination/index/audit/source-last mutation, rollback, and the
  public `apply_inbox_item()` façade inside the same session lifetime.

Task 4R may be independently reviewed as infrastructure, but Task 5R must not
replace the session with serialized metadata or reopen a pathname-only gap.
Task 6 restore consumes the persisted contract, and Tasks 7–9 retain their
product integration and final verification roles with updated module paths.

Implementation occurs on a fresh isolated implementation branch based on the
accepted integration history, not on `master` and not by treating Wave 3 WIP as
accepted. Accepted commits are cherry-picked to `fix/inbox-data-safety` only
after exact-range review and regression verification.

## Verification Strategy

### Unit contracts

- no-follow fd traversal and complete ancestor identity checks;
- durable create/write/link/replace/unlink including parent-directory fsync;
- mutation/preview capability probes, fail-closed unsupported behavior, and
  no-follow preview rejection before record access;
- persistent lock pathname, multiprocess serialization, nonblocking busy
  result, crash release, prior owner diagnostics, and no unlink/tombstone;
- schema-2 manifest validation and host-path exclusion;
- exact manifest key/type/path/hash/identity/metadata cross-validation and
  source/index mode/time restoration warnings;
- journal sequence/hash chain, phase/data/transition validation, exact expected
  bytes, active truncated/unknown-tail rejection, preview classification, and
  exclusive-lock truncate/fsync/`journal-repaired` recovery;
- context state transitions, explicit/automatic prepared abort, final-result-
  after-close construction, deterministic idempotent close, and use-after-close
  rejection;
- secure unresolved-record scan before owner diagnostics or new operation;
- reserved control-namespace rejection for source/destination/index/custom
  Inbox paths;
- zero mutable process-global ownership registries.

### Transaction contracts

- source/index backups and `backup-ready` durable before first business change;
- destination kernel no-overwrite publication;
- actual destination-parent unsupported-publication cleanup mapping;
- index before/after identity and hash guards;
- audit before source removal;
- source identity/hash recheck and removal last;
- lock held until terminal journal durability;
- live backup fds used by rollback;
- exact rollback before and after source unlink;
- unknown destination/index/source edits preserved;
- every injected failure returns truthful status, restore ID, warnings, debris,
  mutation-started flag, and rollback actions;
- two notes sharing one index remain separate per-note transactions while the
  Vault lock serializes them.
- fresh-process crash classification and restore from every apply, rollback,
  and restore nonterminal journal phase.

### Reformulated architecture probes

The old impossible assertions are replaced by tests of the supported contract:

- there is no returned pathname-only prepared operation; session capabilities
  stay live and use after close fails;
- a cooperating journal writer cannot interleave inside compare+append, and an
  unknown tail is rejected at the next active boundary;
- an injected operation-parent durability failure retains and reports
  incomplete debris instead of depending on `.discarded/` or claiming cleanup.

Tests also inject public ancestor rebinding immediately before and after every
business mutation. Observed replacement must block/require recovery without
touching unknown bytes. They do not claim to prevent an uncooperative same-user
writer between two adjacent kernel calls.

### Product and branch gates

- `process_inbox.py` product apply path contains no direct business mutation;
- existing plan/JSON/text compatibility tests pass;
- restore preview/apply, CLI counts, and exit codes match typed results;
- canonical source and generated standard Skill payload are synchronized;
- `build.py --check`, full pytest, package/wheel, installed entry points, and
  hostile-CWD verification pass after Task 8/9;
- an independent final reviewer reports no Critical or Important finding in
  threat model, lifecycle, crash recovery, locking, results, platform gate,
  product integration, or module boundaries.

## Acceptance Criteria

This redesign is complete only when all of the following are current-state
evidence, not intentions:

1. The old public prepared-path contract and process-global ownership tables no
   longer exist.
2. One context-bound session holds the Vault lock and required capabilities
   through durable `committed`, `aborted`, `rolled-back`, or
   `recovery-required` handling once an operation record exists.
3. Every business mutation is guarded by supported public-path checks and the
   exact known identity/hash contract.
4. Journal compare/append is serialized and hash-chained; active corruption
   fails closed.
5. Every failure after operation-directory creation is exact abort/rollback or
   a truthful recovery-required result with preserved copies, warnings, and
   recovery location; safe pre-record validation, busy-lock, and static
   capability failures remain truthful `blocked` results.
6. Crash recovery works in a fresh process without in-memory registry state.
7. Real CLI apply routes through `apply_inbox_item()` and no longer directly
   mutates destination, index, or source.
8. Unsupported mutation environments fail closed; planning remains usable, and
   preview runs only when `PreviewCapabilityProbe` can safely bind the record.
9. Tasks 6–9 restore, compatibility, documentation, distribution, packaging,
   full-suite, and independent-review gates all pass.
10. `master` remains unchanged until the user explicitly selects integration.
