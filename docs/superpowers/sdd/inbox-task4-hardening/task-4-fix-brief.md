# Task 4 Integrated Safety Fix Brief

## Scope and authoritative inputs

This is one integrated repair wave for Task 4 only. Read these first:

- `.superpowers/sdd/task-4-brief.md`
- `docs/superpowers/specs/2026-07-16-inbox-data-safety-design.md`
- `docs/superpowers/plans/2026-07-16-inbox-data-safety.md`, especially Global
  Constraints and Task 4
- the original implementation report at
  `/Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-data-safety/.superpowers/sdd/task-4-report.md`

The repair branch starts at exact Task 4 implementation commit `6a0ac41`.
Change only these Task 4 files:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `obsidian_kb_skill/scripts/backup_policy.py` only if genuinely required
- `tests/test_inbox_transaction.py`
- `tests/test_backup_policy.py` only if genuinely required

Do not implement Task 5 business-file mutation, restore, CLI, lifecycle,
generated payload, or unrelated refactoring.

## Required process

Use systematic debugging before implementation and strict TDD for every
behavioral repair. Reproduce each issue with the smallest deterministic test,
run it and capture the expected RED output, then implement the root-cause fix
and capture GREEN. Do not make production changes before the corresponding RED.

These findings are coupled around ownership, identity, pathname resolution,
and durability; address the complete list in this one wave. If a safe portable
lock-release or fd-relative design is unclear, stop and report
`NEEDS_CONTEXT` rather than guessing.

## Independent review findings to resolve

### Critical

1. Same-byte replacement source is accepted. Preparation reads a verified fd
   but never compares its `(device, inode)` identity with planned
   `item.identity`. A moved source followed by a newly created identical-byte
   file currently prepares successfully. Compare the identity obtained from
   the same opened fd with the frozen planned identity before any success.

2. The exclusively created operation root can be replaced by a Vault-contained
   symlink. Later manifest/journal operations re-resolve the pathname, write to
   the redirect target, and return success. Bind all work to the originally
   created operation directory and its identity, using fd-relative safe
   operations where available. Never accept a different directory merely
   because it is still inside the Vault.

### Important

1. Failure cleanup can delete an unknown regular file that replaces a backup.
   Track creation identity and remove only the exact transaction-owned object.
   Preserve every unknown replacement or ambiguous debris.

2. Lock write/flush/fsync/lstat failure can leave an orphan lock because the
   outer `held_locks` list is updated only after `_acquire_lock()` returns.
   Acquisition must clean up its own partially created lock without deleting a
   replacement and without leaving a lock that has no durable recovery record.

3. Lock identity capture and release contain TOCTOU windows. Capture identity
   from the same creation fd with `fstat` before close. Redesign release so a
   pathname replacement between verification and removal is preserved; a
   check-then-pathname-unlink sequence is insufficient. Tests must
   deterministically force the interleaving, not merely replace the file before
   calling release.

4. Backup verification protects only the final component with `O_NOFOLLOW`.
   An ancestor directory can be replaced by a symlink between resolution and
   `os.open`. Use a safe component-by-component directory-fd traversal with
   no-follow semantics, or an equivalently strong primitive. If the platform
   lacks the required primitives, fail closed rather than falling back to an
   unsafe pathname write/read. Include a deterministic parent-swap regression.

5. File `fsync` alone does not make newly created directory entries durable.
   Add directory `fsync` checkpoints after creating directories and new files,
   ordered so manifest plus verified backups are crash durable before
   `backup-ready`, and the initial journal entry is durable before success.
   Where directory fsync is unsupported, surface truthful behavior consistent
   with the design instead of silently claiming durability. Tests should
   observe/inject the required directory-fsync boundaries.

### Minor coverage/diagnostics

1. Add a concurrency test using two different sources that share the same
   managed index so it proves index-lock serialization independently of a
   source-lock collision.

2. Preserve/report cleanup and lock-release warnings on exception paths when
   the public interface can do so without expanding Task 4. If the current
   raising interface makes that impossible without Task 5 API work, document
   the exact limitation in the report and ledger for final review; do not
   silently swallow evidence internally.

## Required verification

At minimum, report exact commands and pristine outputs for:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q

uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q

uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py

git diff --check 6a0ac41..HEAD
```

Run the broad suite once before committing, excluding only the already known
Task 8 generated-payload drift test, and record the command/result.

## Commit and report contract

Commit the complete repair as one reversible commit on
`fix/inbox-task4-hardening`. Append the prior report plus this fix wave's root
cause analysis, per-test RED/GREEN evidence, file list, self-review, and any
remaining concern to:

`.superpowers/sdd/task-4-report.md`

Return only status, commit SHA/subject, one-line test summary, concerns, and the
report path.
