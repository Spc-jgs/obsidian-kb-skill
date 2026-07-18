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
- malformed, truncated, reordered, duplicated, or hash-chain-invalid journal
  state at an active transaction boundary;
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

Mutation requires a local filesystem and runtime with all of these semantics:

- directory-relative open/stat/link/rename/unlink operations;
- no-follow opening of every traversed component;
- stable regular-file and directory identities from open descriptors;
- durable file and directory `fsync`;
- atomic exclusive destination publication through a hard-link/no-overwrite
  primitive on the same filesystem;
- advisory exclusive file locking compatible with `flock` semantics.

If capability probing cannot establish the complete set, planning and restore
preview remain read-only, while apply and restore mutation return a typed
`blocked` result without creating a recovery record or changing business data.

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
2. The Vault Inbox lock is held from before public precondition validation
   until a terminal `committed` or `rolled-back` event is durable and session
   cleanup has been attempted.
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
    durable `committed` event.
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

`models.py` depends only on stdlib and the accepted `InboxIssue` type.
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
class RecoveryDebris:
    restore_id: str
    location: Path
    classification: Literal["incomplete", "durable", "unknown"]

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
    recovery_debris: RecoveryDebris | None = None
    business_mutation_started: bool = False

def apply_inbox_item(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxApplyResult: ...
```

`applied` is true only when `status == "applied"`. `source`, `destination`,
`backup`, and `RecoveryDebris.location` are Vault-relative when present.

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

`PreparedInboxOperation` and public `prepare_inbox_operation()` are removed.
There is no production caller of them on the accepted branch, and Task 4 has
not been accepted. If an internal prepared metadata view is useful, it is
session-bound, contains no lock paths/fds, and every accessor checks that the
session is open.

## Session Contract and State Machine

The internal API is intentionally context-bound:

```python
with InboxTransactionSession.open(vault, item, injector=injector) as tx:
    tx.prepare()
    result = tx.apply()
```

`apply_inbox_item()` is the only normal caller and owns this context. The
session has these states:

```text
NEW → LOCKED → PREPARED → MUTATING → COMMITTED → CLOSED
                   └──────────────→ ROLLING_BACK → ROLLED_BACK → CLOSED
                                      └────────→ RECOVERY_REQUIRED → CLOSED
```

Invalid transitions raise a typed internal state error. `prepare()`, `apply()`,
journal append, backup access, commit, and rollback all reject calls after
`close()`. `close()` is deterministic and idempotent, but the context may not
report an `applied` result until terminal journal durability and cleanup
warnings are known.

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

While holding the lock, the session reads the previous diagnostic owner record.
A valid previous restore ID with a nonterminal durable recovery record blocks a
new apply as `recovery_required`. A missing record or terminal record is not
treated as live ownership; it produces a warning when inconsistent. The session
then writes and fsyncs current owner diagnostics containing restore ID, PID,
timestamp, and operation kind. Diagnostics never override actual OS lock state.

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
2. Write frozen rendered bytes to an exclusive sibling temp through the bound
   destination parent fd; fsync and verify exact bytes/identity.
3. Publish with a same-filesystem kernel no-overwrite hard-link operation.
4. Fsync the destination parent, verify the public destination identity/hash,
   then unlink and durably remove the temp entry.

If the no-overwrite primitive is unsupported, apply is unsupported. The design
does not reserve and later replace a public destination pathname.

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

The new manifest uses schema version `2`. It stores only Vault-relative POSIX
paths, hashes, observed identities/metadata, operation kind, and required
before/after state. Runtime rollback may use recorded identities while the same
session remains alive; offline recovery after restart treats hashes and safe
public path state as authoritative because inode identity is not a portable
persistent identifier. The manifest never stores host absolute paths.

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

`events.jsonl` uses canonical sorted-key JSON with a final newline. Every event
contains:

```text
schema           2
restore_id       current restore ID
sequence         zero-based, exactly previous + 1
previous_hash    null for event 0, otherwise prior event hash
phase            legal state-machine phase
timestamp        UTC diagnostic timestamp
data             phase-specific canonical mapping
event_hash       SHA-256 of the canonical event without event_hash
```

An active session keeps one verified journal fd open. Before append it locks
that fd exclusively, reads/compares the complete bytes with its exact expected
state, validates the chain, appends exactly one event, fsyncs the journal,
fsyncs the operation directory, updates expected state, then releases the
journal critical section. Unknown, duplicate, reordered, truncated, or invalid
tail state fails closed.

The Vault Inbox lock serializes cooperating transactions; the journal lock
makes the compare/append primitive locally complete and protects offline tools
that follow the same contract.

Offline preview may classify one truncated final line as crash residue. It
must never use that line as a completed phase and must derive safe actions from
the durable manifest, valid event prefix, backup hashes, and observed business
state. Active sessions never ignore a truncated tail.

## Transaction Data Flow

For one ready item:

1. Probe supported mutation capabilities.
2. Open and bind the Vault/recovery roots.
3. Allocate a restore ID in memory without creating a recovery path.
4. Acquire the persistent Vault Inbox lock without waiting and durably write
   current owner diagnostics.
5. Revalidate item, source identity/hash, destination absence, index plan, and
   rendered bytes from the public Vault tree.
6. Create and bind the operation directory.
7. Create exact source/index backups and retain their read fds.
8. Write/fsync schema-2 manifest and initial journal chain.
9. Verify backups through the live fds; append/fsync `backup-ready`.
10. Install and verify destination; append/fsync `destination-installed`.
11. Install/verify an owned changed index; append/fsync `index-installed`.
12. Audit the installed note; append/fsync `audit-passed` with warnings.
13. Revalidate and unlink source last; append/fsync `source-removed`.
14. Revalidate public destination/index/source postconditions.
15. Append/fsync `committed`.
16. Close live backups/recovery capabilities, collect cleanup warnings, and
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
  business mutation had begun.
- `recovery_required`: unknown business state, failed exact rollback, observed
  recovery/lock replacement, prior nonterminal record, incomplete operation
  debris, or lock/session cleanup failure requiring operator attention.
- `applied`: exact final business state and durable `committed` journal proved.

An error after operation-directory creation but before durable manifest returns
`recovery_required`, `business_mutation_started=False`, and explicit incomplete
`RecoveryDebris`. This intentionally replaces the old assertion that every
preparation failure deletes its operation directory.

Primary failures, rollback actions, cleanup failures, and lock-release failures
are accumulated deterministically. A secondary warning never replaces or hides
the primary issue. If terminal business state is known but session/lock cleanup
requires attention, the status is `recovery_required`, not false `applied`.

## Offline Preview and Restore

Preview is read-only and never creates or writes a lock. It opens the existing
persistent lock safely and attempts a non-blocking shared advisory lock before
reading a schema-2 record. If an apply/restore holds the exclusive lock, preview
returns a typed busy result instead of reading a moving record. A missing or
unsafe lock beside a schema-2 record is reported as recovery-required. While
holding the shared lock, preview validates schema/paths/backups/journal prefix
and reports actions, conflicts, warnings, and debris from observed hashes.

Restore apply acquires the same Vault Inbox lock, reopens and revalidates the
record, then performs source-first guarded restoration, known index restoration,
and known destination removal. It never overwrites unknown edits. Final state
is verified and `restored` is durably journaled. Repeated restore is idempotent.

An incomplete record without a valid manifest is reportable but not guessed.
The tool returns `recovery_required` with its Vault-relative location and
preserves it for manual inspection.

## CLI and Compatibility

The existing console entry point, Inbox name, routing, inferred metadata,
default read-only behavior, recognizable text plan, top-level JSON plan list,
and legacy callable names remain.

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
  public prepared pathname object. Its tests keep the context open, prove
  use-after-close rejection, and perform zero business mutation.
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
- supported-platform probe and fail-closed unsupported behavior;
- persistent lock pathname, multiprocess serialization, nonblocking busy
  result, crash release, prior owner diagnostics, and no unlink/tombstone;
- schema-2 manifest validation and host-path exclusion;
- journal sequence/hash chain, exact expected bytes, active truncated/unknown
  tail rejection, and offline truncated-tail classification;
- context state transitions, deterministic idempotent close, and use-after-
  close rejection;
- zero mutable process-global ownership registries.

### Transaction contracts

- source/index backups and `backup-ready` durable before first business change;
- destination kernel no-overwrite publication;
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
   through durable commit or rollback.
3. Every business mutation is guarded by supported public-path checks and the
   exact known identity/hash contract.
4. Journal compare/append is serialized and hash-chained; active corruption
   fails closed.
5. Every failure is exact rollback or a truthful recovery-required result with
   preserved copies, warnings, and recovery location.
6. Crash recovery works in a fresh process without in-memory registry state.
7. Real CLI apply routes through `apply_inbox_item()` and no longer directly
   mutates destination, index, or source.
8. Unsupported mutation environments fail closed while read-only operations
   remain usable.
9. Tasks 6–9 restore, compatibility, documentation, distribution, packaging,
   full-suite, and independent-review gates all pass.
10. `master` remains unchanged until the user explicitly selects integration.
