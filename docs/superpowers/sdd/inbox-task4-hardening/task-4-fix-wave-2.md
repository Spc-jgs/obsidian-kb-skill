# Task 4 Fix Wave 2: Recovery-Record Identity and Race-Free Cleanup

Base for this wave: `1cef079`.

The first hardening wave closed source identity, operation-root binding,
ancestor no-follow traversal, lock acquisition/release races, directory fsync,
and shared-index coverage. Independent re-review still returned spec FAIL,
quality CHANGES_REQUESTED, Task 4 NO. Resolve the complete list below in one
TDD wave; do not start Task 5.

Read `.superpowers/sdd/task-4-brief.md`, `.superpowers/sdd/task-4-report.md`,
and `.superpowers/sdd/task-4-review-package.md` first. Continue to change only:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `tests/test_inbox_transaction.py`
- the Task 4 backup-policy files only if genuinely required

## Critical

1. Manifest replacement after its fsync currently succeeds. A probe at the
   `manifest-fsync` checkpoint replaces `manifest.json` with
   `{"unknown":true}` and observes:

   ```text
   PREPARED True UNKNOWN_MANIFEST True JOURNAL_READY backup-ready
   ```

   Retain the identity returned by `_write_new_at()`. Before creating the
   journal and again immediately before success, read through the bound
   operation fd and require both the exact creation identity and exact expected
   manifest payload/hash. A mismatch must fail closed without modifying or
   deleting the unknown replacement.

2. A same-byte regular backup replacement currently passes byte/hash
   verification even though the replacement inode and directory entry were not
   durably created by this transaction. For source and index backup
   verification, require the same-fd observed identity to equal the recorded
   creation identity as well as exact bytes/hash. Revalidate the complete
   recovery preamble before journal creation and immediately before success.

## Important

1. `_remove_owned_file()` and `_remove_owned_directory()` still perform
   `stat→unlink/rmdir`. A deterministic interleaving produced:

   ```text
   SWAPPED True UNKNOWN_EXISTS False SAVED_EXISTS True WARNINGS []
   ```

   Remove these pathname deletion races. Preferred architecture: create and
   bind an inert `.obsidian-kb-backups/inbox/.discarded/` namespace up front;
   on any pre-manifest failure, atomically dir-fd rename the **entire operation
   root** from its public restore-id name to a random non-operation tombstone,
   fsync both parents, verify the moved root identity, and never pathname-delete
   that tombstone. If an unknown replacement was moved, preserve it in the
   inert namespace and report a warning; never overwrite or delete it. The
   operation list/tests must ignore only the exact reserved `.discarded` and
   `.locks` names. A different equally strong no-delete design is acceptable,
   but no `check→unlink/rmdir` may remain in security cleanup.

2. `_write_new_at()` obtains a creation fd and calls `fstat` before entering
   its close guard. Injection currently gives:

   ```text
   ERROR injected-fstat
   ORPHAN_EXISTS True
   ```

   Every successful `open()` must immediately enter a guaranteed close path.
   Cover `_write_new_at`, operation-directory open/fstat, bound-operation
   open/fstat, and any equivalent acquired-before-guard pattern. If identity
   capture fails after exclusive creation, safely quarantine/preserve the
   created object or rely on whole-operation inert quarantine; do not leak an
   fd or public orphan.

3. `_append_event()` binds only the initial `backup-ready` creation. Later
   phases use `O_APPEND|O_CREAT` and will append to an unknown regular
   replacement. Record the initial journal creation identity. Every later
   append must open the existing file through the bound operation fd, compare
   same-fd identity with that recorded identity before writing, never create a
   missing journal, and fail closed on replacement. The initial phase remains
   exclusive. Add a real second-phase regression proving unknown bytes remain
   exact.

## Minor bookkeeping

- Cleanup/release warnings remain an explicit Task 5 result-mapping todo if the
  Task 4 raising API cannot return them.
- Inert `.locks/.released/` and `.discarded/` objects are the accepted safety
  cost of portable POSIX no-delete semantics. Record their unbounded inode
  growth as a later lifecycle/capacity design item; do not reintroduce unsafe
  cleanup in this wave.

## TDD and verification contract

Write/run deterministic RED tests for every item before production edits and
append exact failure output to `.superpowers/sdd/task-4-report.md`. Then run:

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

git diff --check 1cef079..HEAD
```

Self-review every previous finding as well. Commit this wave as one reversible
commit, append report evidence, and return concise status/commit/tests/concerns.
