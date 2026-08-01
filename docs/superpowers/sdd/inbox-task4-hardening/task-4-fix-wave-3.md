# Task 4 Fix Wave 3: Complete Path and Journal State Binding

Base for this wave: `f5ef1ec`.

This is the third and final repair wave allowed within the current Task 4
architecture. Independent re-review returned spec FAIL, quality
CHANGES_REQUESTED with exactly one Critical and two Important findings below.
Resolve all three with strict TDD and re-run every gate. If this wave's
independent re-review still has any Critical/Important issue, stop; do not
attempt a fourth patch wave. The controller will reassess the now-large module
architecture first, as required by systematic debugging.

Read `.superpowers/sdd/task-4-brief.md`, `.superpowers/sdd/task-4-report.md`,
`.superpowers/sdd/task-4-wave-2-handoff.md`, and the current production/tests.
Do not start Task 5 or change the four-file Task 4 scope.

## Critical: bind every recovery artifact ancestor directory

The preamble binds operation root and final backup file inode/bytes/hash, but
not the identities of directories between them. A deterministic local probe at
`manifest-write`:

1. renames `operation/source/00-Inbox` to a saved name;
2. creates a new `source/00-Inbox`;
3. hard-links the original already-fsynced backup inode into the new directory.

Current result:

```text
ANCESTOR_REPLACEMENT_ACCEPTED True
```

The final inode and bytes are identical, but the manifest path now depends on
new directory entries that were not created/fsynced by this transaction.

Store each source/index backup's complete operation-relative ancestor chain and
creation identity in the recovery preamble. During verification before journal
creation and before success, open each component with the existing no-follow
directory-fd traversal and require its observed identity to equal the recorded
identity before opening the next component/final file. Manifest and journal at
the bound operation root have no additional internal ancestor. Add deterministic
RED/GREEN for both source and index backup directory-chain replacement.

## Important 1: journal expected state must be exact and advance

The preamble stores only an initial `journal_prefix`; verification and later
append use `startswith`. If an unknown complete line is appended to the same
inode after `backup-ready`, later append is accepted:

```text
UNKNOWN_PREFIX_ACCEPTED True
```

Replace prefix semantics with the complete expected journal bytes. Before any
later append require `current == journal_expected` on the same verified fd.
Only after the transaction's own event has been fully written and fsynced may
the in-memory expected state advance by exactly that event payload. Preamble
verification must also require exact equality. A partial/unknown tail causes
the live operation to fail closed; recovery parsing owns truncated-tail logic.

Add RED/GREEN for:

- an unknown complete tail preserving the valid initial event;
- two legitimate sequential internal appends, proving expected state advances;
- an unknown/partial tail after one legitimate later append, proving the next
  append refuses it without changing bytes.

## Important 2: quarantine every post-mkdir failure

`_create_operation_directory()` currently quarantines only `fstat` failure
after open. If `mkdir` succeeds and parent directory fsync or the first open of
the operation directory fails, `operation_identity` never reaches the outer
cleanup and a public restore-ID directory remains.

Separate `mkdir`'s `FileExistsError` from all later failure handling. Immediately
after successful mkdir record that this attempt owns the new public entry. Any
subsequent parent-fsync, open, or fstat failure must close any acquired fd and
atomically move the public entry to the identity-bound `.discarded` namespace,
using unknown identity when capture never succeeded. Never move a pre-existing
entry when mkdir itself reports `FileExistsError`.

Add RED/GREEN for parent-fsync failure and operation-open failure, proving:

- no public restore-ID operation remains;
- the entry is preserved under `.discarded`;
- locks are no longer public;
- no fd leaks;
- business source/index/destination bytes remain exact.

## Retained Minors

- Task 5 must carry cleanup/release warnings into `InboxApplyResult.warnings`.
- `.discarded/` and `.locks/.released/` need a future identity-safe capacity
  policy; do not add unsafe deletion or retention work here.

## Required verification and report

Capture every new RED command/output and GREEN evidence in
`.superpowers/sdd/task-4-report.md`, then run:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q

uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q

uv run --locked --extra dev pytest -q \
  -k 'not test_build_check_still_passes'

uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py

git diff --check f5ef1ec..HEAD
```

Self-review every prior finding, commit one reversible Wave 3 commit, write a
fresh ignored handoff with the exact three hardening commits that must later be
cherry-picked (`1cef079`, `f5ef1ec`, plus this Wave 3 commit), and return concise
status/commit/tests/concerns.
