# Inbox Data Safety Design

> **Status: NOT MERGED; partly superseded.** The Task 4/5 transaction and
> recovery architecture described here was replaced by
> `2026-07-19-inbox-transaction-capability-session-design.md`. Tasks 1–3 remain
> accepted on the local branch `fix/inbox-data-safety`.
>
> The data-loss path described under "Problem" was closed separately in v1.25.1
> for the parsing case. Backup, source hashes, atomic commit, and restore
> remain unimplemented.

**Date:** 2026-07-16  
**Branch:** `fix/inbox-data-safety`  
**Base:** accepted `fix/shared-note-domain` at `8132365`  
**Status:** Approved under the user's standing authorization to make scoped
design decisions and continue without pausing. This spec refines the already
approved evolution roadmap; it does not change that roadmap's product choices.

## Problem

The current Inbox processor treats malformed, unclosed, null, and non-mapping
frontmatter like absent frontmatter. On `--apply` it can replace the original
frontmatter, write inferred defaults, move the note, delete the source, and only
then update the destination index. There is no backup, source hash, atomic
commit, rollback, restore command, or truthful per-item result.

This is a demonstrated data-loss path. It must be closed before Inbox becomes
more discoverable or gains lifecycle features.

## Scope Decision

This branch implements the data-safety kernel promised by the roadmap:

- fail-closed discovery, UTF-8 decoding, and frontmatter parsing;
- immutable typed plan and result objects inside the helper;
- raw source-byte hashes and frozen mechanical render proposals;
- a journaled transaction for each individual note;
- byte-for-byte backup, rollback, guarded restore, and failure injection;
- no-overwrite Vault containment for sources, destinations, indexes, backups,
  locks, and temporary files;
- accurate applied, skipped, blocked, failed, and recovery-required results;
- compatibility adapters for the current CLI and JSON plan surface.

The branch deliberately does **not** implement the roadmap's later Inbox
lifecycle surface. In particular, it does not add the ten-item default limit,
external reviewed plan files, public plan IDs or item selection, confidence,
evidence, questions, `inbox-note`, semantic enrichment, or Skill routing. Those
belong to `feat/inbox-lifecycle` so the safety kernel can be reviewed and
reverted independently.

The existing `--apply` command therefore remains available. It plans the Inbox
once, freezes each item's bytes and proposal, and applies those typed plans
without reclassification. A later branch will require a separately reviewed
plan artifact.

## Approaches Considered

### A. Parse guard plus a copied backup

This is small but leaves destination overwrite races, partial index writes,
source deletion before index failure, misleading counts, and no reliable
restore semantics. It does not satisfy the accepted transaction contract.

### B. Journaled transaction per note — selected

Planning and mutation are separate. Each note has frozen preconditions and a
dedicated recovery record. Mutations are ordered so the source remains intact
until the destination and index are installed and checked. A failure rolls back
only that note. This matches the roadmap's "transactional single-item apply"
while keeping today's multi-note CLI as a sequence of independent transactions.

### C. Batch-wide two-phase commit

An all-or-nothing batch would need locks and recovery coordination across many
directories and indexes. One conflicting note could prevent recovery of the
whole batch. That complexity is not justified and is explicitly outside this
branch.

## Safety Invariants

The implementation must preserve these invariants:

1. A malformed, unclosed, null, list, scalar, unreadable, non-UTF-8, symlinked,
   non-regular, or out-of-Vault Inbox item is never modified or moved.
2. The exact raw source bytes used for planning are hashed. Apply refuses an
   item whose source bytes or file identity changed after planning.
3. No existing destination is overwritten, including dangling symlinks and
   files created after planning.
4. The destination body bytes are identical to the source body bytes. This
   branch performs only explicit mechanical frontmatter additions.
5. Existing valid frontmatter bytes, comments, key order, quoting, BOM, and
   newline convention are preserved. Missing keys are inserted before the
   closing delimiter; a note without frontmatter receives a new block.
6. An existing `date`, `type`, or `tags` key is never replaced, even when its
   value is empty. Ambiguous empty required metadata blocks apply rather than
   creating a duplicate key or guessing over user content.
7. The original source and managed index bytes are durably backed up before
   any business-file mutation.
8. The source is removed only after destination installation, managed index
   installation, on-disk hash verification, and note audit have completed.
9. A result is `applied` only when the source is absent, the destination hash
   equals the frozen render hash, the index is unchanged or equals its expected
   post-image, and the committed journal event exists.
10. Automatic rollback overwrites only bytes that still match this transaction's
    expected before/after hashes. Unknown concurrent edits are preserved and
    produce `recovery_required`.
11. Every reported count is derived from actual typed results, never the number
    of discovered plans.
12. JSON mode emits one JSON document on stdout and never a traceback.

## Architecture

### `inbox_plan.py`: pure planning and rendering

This new module owns immutable planning types and byte-preserving mechanical
rendering. It has no mutation APIs.

Core public types:

```python
@dataclass(frozen=True)
class InboxIssue:
    code: str
    message: str
    line: int | None = None
    column: int | None = None

@dataclass(frozen=True)
class InboxProposal:
    destination: Path              # Vault-relative
    target: str
    note_type: str
    tags: tuple[str, ...]
    metadata_updates: tuple[tuple[str, object], ...]
    rendered_bytes: bytes
    rendered_sha256: str
    index: StaticIndexPlan

@dataclass(frozen=True)
class InboxPlanItem:
    source: Path                   # Vault-relative
    source_sha256: str | None
    title: str | None
    status: Literal["ready", "skipped", "blocked"]
    proposal: InboxProposal | None
    issue: InboxIssue | None

@dataclass(frozen=True)
class InboxPlan:
    effective_date: str
    items: tuple[InboxPlanItem, ...]
```

Discovery uses `os.scandir()` without following symlinks, sorts by filename,
and includes unsafe entries as blocked results without reading through them.
There is no item limit in this branch.

Planning reads bytes once, decodes strict UTF-8, checks the shared
`FrontmatterResult.issue`, validates metadata shapes, freezes the current date,
route, destination, explicit updates, rendered bytes, source/render hashes, and
static-index pre/post image. Keyword routing remains unchanged and is not
presented as confidence.

The renderer works on raw bytes. For valid frontmatter, it inserts only missing
`date`, `type`, and `tags` entries immediately before the closing delimiter. For
absent frontmatter, it prepends a new block. It preserves the BOM, LF/CRLF,
body slice, existing frontmatter bytes, and trailing newline state. The rendered
candidate is parsed again before the item can become `ready`.

### `folder_index_policy.py`: pure static-index proposal

Add an immutable `StaticIndexPlan` and `plan_static_index_entry()` alongside
the existing compatibility API. The plan records:

- `action`: `append`, `unchanged`, `missing`, or `unmanaged`;
- Vault-relative index path when one exists;
- exact before and after bytes;
- SHA-256 hashes for both states;
- the exact wikilink line.

Planning is read-only. It refuses uncertain ownership or unsafe paths. Existing
`append_static_index_entry()` remains available to other consumers and delegates
to the same policy rules; only the Inbox transaction uses atomic installation.

### `inbox_transaction.py`: mutation, journal, rollback, restore

This new module owns one-note transactions. It exposes:

```python
class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...

def apply_inbox_item(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxApplyResult: ...

def preview_inbox_restore(vault: Path, restore_id: str) -> InboxRestoreResult: ...

def restore_inbox_operation(
    vault: Path,
    restore_id: str,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxRestoreResult: ...
```

The production injector is a no-op. Tests inject failures through the protocol;
there is no environment-variable or CLI test backdoor.

Backups live at:

```text
.obsidian-kb-backups/inbox/<restore-id>/
├── manifest.json
├── events.jsonl
├── source/00-Inbox/<note>.md
└── index/<target>/<index>.md       # only when a managed index changes
```

The manifest contains schema version, restore ID, Vault-relative paths, source
and rendered hashes, destination-absent precondition, index before/after hashes,
and file metadata needed for best-effort permission/time restoration. It never
contains absolute host paths. The backup policy treats `inbox/` as a reserved,
preserved namespace and never prunes it as ordinary note history.

The event journal is append-only JSON Lines. Each complete line is flushed and
fsynced. Recovery decisions use the manifest plus observed file hashes, not the
journal alone. A truncated final line is ignored.

Locks use atomic creation under `.obsidian-kb-backups/inbox/.locks/`, with names
derived from Vault-relative path hashes. Source and managed-index locks are
acquired in deterministic order. Stale locks are never removed merely because
they are old; the result reports the owning restore ID and requires recovery.

### `process_inbox.py`: compatibility and orchestration

The current CLI becomes a thin adapter:

- default and `--plan` build an `InboxPlan` and preserve the current text and
  top-level JSON-list plan shape, adding only backward-compatible status/error
  fields;
- `--apply` builds the plan once, applies each `ready` item independently, and
  serializes actual results;
- `--restore RESTORE_ID` is a read-only preview;
- `--restore RESTORE_ID --apply` performs a guarded restore;
- summaries show exact counts for ready/skipped/blocked/applied/failed and
  recovery-required items;
- blocked validation produces exit 2, fully rolled-back runtime failure exit 3,
  and recovery-required exit 4. Mixed apply runs keep all item results and use
  the highest-severity exit code.

The legacy module-level `plan_note()`, `apply_plan()`, and `process_vault()`
functions remain as narrow adapters during this branch so installed callers do
not fail with import errors. They delegate to typed APIs and return compatible
dictionaries where required.

## Transaction Flow

For each ready item:

1. Revalidate Vault containment, real regular source, source hash, destination
   absence, index ownership/path/hash, and rendered candidate.
2. Acquire deterministic source and index locks.
3. Create a unique restore directory with exclusive semantics.
4. Write source/index backups, manifest, and `backup-ready` event; flush and
   fsync them before business-file mutation.
5. Write the destination to a sibling temporary file, flush and fsync it, then
   install it with a no-overwrite primitive. A safe platform fallback may use an
   exclusive reservation only while holding the source lock and must journal a
   recoverable reservation state.
6. When the Skill owns a static index, recheck its pre-hash, write its post-image
   to a sibling temp file, and atomically replace it.
7. Verify destination/index hashes and run note-level audit. Audit findings are
   structured warnings; an audit exception or structurally invalid output is a
   transaction failure.
8. Remove the source last, verify final state, append and fsync `committed`, then
   release locks.

If a failure happens before source removal, rollback removes only a destination
whose hash matches the rendered hash and restores only an index whose hash
matches the expected post-image. The untouched source is verified.

If a failure happens after source removal, rollback first restores the source
from the verified backup without overwriting an unknown file, then restores the
index and removes the known destination. If any path contains unknown bytes or
a rollback step fails, all copies are preserved and the result becomes
`recovery_required` with the restore ID and exact preview command.

## Restore Contract

Restore is read-only by default. Preview compares the manifest with current
source, destination, index, and backup hashes and reports every intended action
or conflict.

Apply restore proceeds only when:

- backup files and manifest match their recorded hashes;
- the original source is absent or already equals the original hash;
- the destination still equals the transaction's rendered hash;
- a changed static index still equals the transaction's expected post-hash.

Restore never overwrites post-apply edits. It restores the source first, restores
the index only from a matching post-image, then removes the matching destination.
The backup and journal remain after restore. Repeated restore is idempotent.

## Error and Result Model

Typed item results use these terminal statuses:

- `applied`: committed and all postconditions hold;
- `skipped`: no route, destination conflict, or already-applied state; no new
  mutation;
- `blocked`: invalid input or stale plan; no new mutation;
- `rolled_back`: runtime failure occurred and exact pre-state was restored;
- `recovery_required`: automatic rollback or restore could not safely prove or
  recreate the pre-state.

`InboxApplyResult` includes source/destination paths, `applied`, restore ID,
backup path, issue, audit warnings, and rollback actions. It never exposes an
absolute path. `applied` is true only for the `applied` status.

## Failure-Injection Coverage

Tests inject failure at least at:

- source read/decode/stat and plan-time parse;
- backup directory, source copy, index copy, manifest write/flush/fsync;
- destination temp create/write/flush/fsync/install;
- index precondition, temp write/flush/fsync/replace;
- audit invocation;
- source unlink and post-unlink verification;
- journal append/flush/fsync;
- destination cleanup, index restore, and source restore;
- manual restore preview/apply with missing/corrupt backup or concurrent edits.

Every injection asserts exact source, destination, index, backup, and result
state. Symlink escape, dangling symlink, destination race, stale source hash,
idempotent rerun, BOM, CRLF, and body-byte preservation are also mandatory.

## Compatibility

- The package name, console entry point, default Inbox name, routing table,
  inferred metadata values, and static-index ownership policy do not change.
- Default operation remains read-only.
- Current text plan records and top-level JSON plan list remain recognizable.
- Existing callers of `process_vault()` still receive a list of dictionaries.
- Valid historical inputs keep their routing and destination behavior.
- `--apply` becomes safer and its final counts become truthful. Validation and
  runtime failures now have non-zero exit codes instead of false success.
- Narrow README/help changes document backup and restore behavior. The larger
  README reorganization remains a later branch.

## Non-Goals

- No Inbox type, capture template, confidence, evidence, questions, enrichment,
  semantic links, review queue, archive workflow, or background trigger.
- No ten-item plan budget, public plan artifact, public plan/item ID, or batch
  all-or-nothing commit.
- No semantic body rewrite or automatic replacement of user metadata.
- No general transaction framework for create, update, installer, or templates.
- No Inbox-backup retention or automatic stale-lock deletion.
- No template migration, README information-architecture rewrite, or token work.

## Acceptance Criteria

The branch is acceptable only when:

1. all malformed/ambiguous inputs remain byte-identical in Inbox;
2. every failure-injection point yields either exact rollback or an explicit
   recovery-required result with preserved copies;
3. no existing or out-of-Vault path is overwritten;
4. a clean apply is restorable and repeated apply/restore is idempotent;
5. CLI/JSON results and exit codes match actual per-item outcomes;
6. canonical source, standard Skill payload, build manifest, wheel/installers,
   hostile-CWD tests, and the complete test suite pass;
7. an independent final reviewer reports no Critical or Important issue.
