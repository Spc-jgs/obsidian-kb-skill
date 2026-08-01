# Task 4 Report: Backup Store, Manifest, Journal, and Locks

## Prior implementation report (`6a0ac41`)

Status: DONE

Commit: `6a0ac41` (`feat: add inbox transaction recovery store`)

The original Task 4 implementation changed exactly the four allowed files and
established the recovery-store API, nine failure checkpoints, exact source and
index backups, sorted compact manifest JSON, a fsynced `backup-ready` event,
deterministic source/index locks, and exact top-level `inbox/` retention. Its
focused suite was 53 passed; its Task 4 plus Vault/path suite was 87 passed; the
broad suite passed with only the known Task 8 generated-payload check excluded.

The original report also recorded two self-review RED/GREEN cycles:

- final-component source-backup symlink replacement was rejected by reopening
  with `O_NOFOLLOW`;
- a lock replaced before cleanup was preserved by comparing `(device, inode)`.

It recorded the following checkpoint behavior: failures before a durable
manifest removed owned recovery debris; failures at `manifest-fsync` and
`journal-backup-ready` retained the durable manifest and verified backups; all
business source/index/destination states stayed exact. It explicitly deferred
generated payload synchronization to Task 8 and reported no master, merge,
push, CLI, restore, or business-file mutation.

That report's final concern was the intentionally stale generated runtime:
`tests/test_lazy_references.py::test_build_check_still_passes` remains the one
known excluded gate until Task 8.

## Independent-review repair wave

Status: DONE_PENDING_INDEPENDENT_REVIEW

Branch/base: `fix/inbox-task4-hardening` from exact `6a0ac41`

Repair commit: `1cef079` (`fix: harden inbox recovery preparation`)

Tracked scope:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `tests/test_inbox_transaction.py`

No Task 5 mutation, restore, CLI, generated payload, lifecycle behavior,
retention-policy behavior, or unrelated refactor was added.

### Root-cause analysis

1. Source verification compared only SHA-256. Although bytes were read from an
   `O_NOFOLLOW` fd, the fd's `fstat` was never compared with the frozen
   `SourceIdentity`; identical bytes on a new inode therefore passed.
2. The operation directory was created exclusively but later recovery writes
   re-resolved absolute paths. Its creation identity was neither retained nor
   bound to fd-relative writes, so a contained symlink replacement redirected
   manifest/journal/backup I/O.
3. Cleanup tracked pathnames rather than the identities created by the
   transaction. A same-kind regular replacement therefore satisfied the kind
   check and was unlinked.
4. Lock creation delegated to a helper that closed its creation fd before
   pathname `lstat`; acquisition failures before the outer held-lock append
   orphaned the public lock. Release then used check-then-pathname-unlink, so a
   replacement between those calls could be deleted.
5. Backup verification protected only the final component. Path resolution and
   the later `open` were separate, allowing an ancestor to become a contained
   symlink and redirect the read.
6. File fsync did not persist newly created parent directory entries. Success
   could therefore claim crash durability without durable directory entries.

The lock-release architecture required a deliberate portability decision:
portable POSIX exposes no unlink-by-fd. Public `*.lock` entries are therefore
atomically renamed with directory fds into the inert
`.locks/.released/` namespace. The moved inode is compared with the identity
captured by `fstat` on the still-open creation fd. Unknown replacements are
hard-linked back only with no-overwrite semantics when possible and are always
preserved; owned and unknown tombstones are never pathname-unlinked. These tiny
inert tombstones are the explicit safety cost of eliminating the deletion race.

### RED evidence

The initial integrated regression command was:

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q \
  -k 'changed_planned_identity or same_byte_replacement or \
  operation_root_replacement or preserves_regular_file_replacing or \
  ancestor_symlink_swap or lock_fsync_failure or after_identity_check or \
  tombstone or directory_entries or shared_index_lock'
```

Actual result: exit 1, 11 failed and 2 passed. The expected failures proved:

- all four frozen identity fields and a real same-byte inode replacement were
  accepted;
- operation-root replacement redirected writes and returned success;
- cleanup deleted an unknown regular backup replacement;
- an in-Vault ancestor symlink passed backup verification;
- lock fsync failure left a public orphan lock;
- a replacement injected between release verification and removal was deleted;
- no directory fsync followed durable file creation.

The two already-green controls proved that different sources sharing one index
were serialized and that a clean release permitted reacquisition.

Two supplemental TDD cycles found during self-review:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py::test_initial_journal_never_appends_to_unknown_existing_file -q
```

Actual RED: exit 1, 1 failed because initial `backup-ready` appended to an
unknown pre-existing `events.jsonl` instead of using exclusive creation.

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py::test_lock_identity_capture_failure_leaves_no_public_orphan_lock -q
```

Actual RED: exit 1, 1 failed because an injected creation-fd `fstat` failure
left the newly created public `*.lock` path behind.

### GREEN implementation

- Source bytes are now read through component-by-component no-follow fd
  traversal. The same opened fd's `fstat` must match `device`, `inode`, `size`,
  and `mtime_ns`, and bytes must still match the frozen hash.
- The operation directory identity is retained. Every backup, manifest, and
  event operation uses an fd bound to the created directory and re-verifies the
  canonical operation-root entry before writes and before success.
- Every recovery ancestor is opened component-by-component with
  `O_DIRECTORY|O_NOFOLLOW`; unsupported platforms fail closed.
- Created file/directory identities are recorded and cleanup removes only an
  exact same-kind identity. Unknown or ambiguous debris is preserved.
- Lock creation retains its exclusive creation fd through the lock lifetime,
  captures identity with same-fd `fstat`, registers ownership before fallible
  writes/fsync, and safely quarantines even an unverified fstat-failure entry.
- Release uses atomic dir-fd rename into a random inert tombstone. A moved
  unknown regular file is restored with no-overwrite hard-link semantics when
  possible; no unknown or owned tombstone is ever pathname-unlinked.
- Directory entries are fsynced after every mkdir, exclusive recovery file,
  lock create/release rename, no-overwrite hard link, manifest, and event. A
  directory-fsync error surfaces as `unsupported-directory-fsync`.
- Initial `backup-ready` journal creation is exclusive and cannot append to an
  unknown file. Later Task 5 phases retain append semantics.

### Verification evidence

Focused GREEN:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q
```

Actual result: exit 0, 68 selected tests passed.

Required Task 4 plus Vault/path regression, broad suite, compileall, and exact
post-commit diff-check are recorded below after the final commit verification.

Required path regression:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q
```

Actual result: exit 0, 102 selected tests passed.

Broad suite excluding only the already-known Task 8 generated drift:

```bash
uv run --locked --extra dev pytest -q \
  -k 'not test_build_check_still_passes'
```

Actual result: exit 0, 607 selected tests passed and the one named generated
payload check was deselected.

Compile and pre-commit whitespace verification:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py
git diff --check
```

Actual result: both exited 0 with pristine output.

Post-commit scope and diff verification:

```bash
git diff --check 6a0ac41..HEAD
git status --short --branch
git log -2 --oneline
git diff --name-only 6a0ac41..HEAD
```

Actual result: exit 0; the branch is clean at `1cef079`; the exact repair range
contains only `inbox_transaction.py` and `test_inbox_transaction.py`.

### Self-review and remaining concerns

- The required public dataclass field order and function signatures are
  unchanged. The refactor is internal to Task 4 recovery preparation.
- Only public `*.lock` names participate in acquisition. Random tombstones are
  in `.locks/.released/`, never block a later acquisition, and are retained by
  design rather than pruned unsafely.
- The existing raising preparation interface cannot return cleanup/release
  warnings when an arbitrary injector or OSError is re-raised. Internally all
  unknown objects are preserved, but warning delivery must be added when Task 5
  maps exceptions into `InboxApplyResult`; this is the exact deferred Minor.
- The known Task 8 generated-payload drift remains excluded and is unrelated to
  this two-file Task 4 repair.

## Fix Wave 2 Closeout (2026-07-19)

Wave 2 closes the remaining manifest/backup/journal replacement races, replaces
per-entry cleanup with atomic whole-operation quarantine under an
identity-bound `.discarded/` namespace, identity-binds `.locks/.released/`, and
closes creation/open descriptors on all identity-capture failures. The added
tests first reproduced each failure and now pass.

Final local verification from base `1cef079`:

- focused Task 4 suite: 82 passed;
- required Task 4 + Vault/path regression: 116 passed;
- broad suite: 621 selected passed, excluding only the known Task 8 generated
  payload drift;
- compileall and `git diff --check`: exit 0.

Wave 2 is committed as `f5ef1ec` (`fix: bind inbox recovery identities`).

The complete resume and integration procedure is recorded in
`.superpowers/sdd/task-4-wave-2-handoff.md`. Independent review remains required
before cherry-picking to `fix/inbox-data-safety`; Task 5 remains blocked.

## Fix Wave 3 Closeout (2026-07-19)

### Root causes and RED evidence

The remaining findings shared one cause: recovery validation bound final
objects but did not bind every state transition leading to them. Backup final
inodes were exact while their ancestor entries could change; journal validation
accepted any bytes after a valid prefix; operation ownership was not retained
between successful mkdir and identity capture.

The selected RED command was:

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q \
  -k 'backup_ancestor_replacement_with_owned_inode or \
  unknown_complete_tail or expected_bytes_advance or \
  partial_tail_after_internal_append or \
  post_mkdir_failure_quarantines'
```

Actual RED: exit 1, 6 failed and 1 passed. Source/index ancestor replacement
with a hard-linked owned backup inode was accepted; unknown complete and partial
journal tails were accepted; parent-fsync and first operation-open failures
left public restore-ID directories. The legitimate two-append control was
already green. A corrected test-only error regex was rerun and both post-mkdir
parameters then failed on the intended public-directory assertion. Technical
fix-hypothesis failure count remained zero.

### GREEN implementation and evidence

- `_OwnedRecoveryFile` now carries every operation-relative ancestor directory
  and its creation identity. Verification opens no-follow component by
  component and compares each observed identity before continuing.
- `_RecoveryPreamble.journal_expected` is the exact complete journal state.
  Later appends require equality on the same fd; expected bytes advance by
  exactly the transaction's event only after write/fsync succeeds.
- `_create_operation_directory` separates mkdir collision from later failures.
  Once mkdir succeeds, parent-fsync/open/fstat failures close fds and quarantine
  the complete public entry without deleting bytes.

Selected GREEN: exit 0, 7 passed.

Final gates:

- focused Task 4 suite: 89 passed;
- required Task 4 + Vault/path regression: 123 passed;
- broad suite: 628 selected passed, with only the known Task 8 generated drift
  excluded;
- compileall and pre-commit `git diff --check`: exit 0.

Historical findings were self-reviewed: business files remain immutable;
source/final-file/operation/namespace/ancestor identities are bound; cleanup is
whole-operation quarantine with no pathname deletion; lock release remains
atomic and identity checked; all reviewed creation/open fds are guarded; file
and directory durability calls remain present; initial journal creation is
exclusive and later journal state is exact.

Retained Minors are unchanged: Task 5 must carry cleanup/release warnings, and
the inert namespaces need a future identity-safe capacity policy. The fresh
resume/integration contract is in `.superpowers/sdd/task-4-wave-3-handoff.md`.

### Pre-commit architecture stop (supersedes Wave 3 completion wording)

Independent diff review found that sequential identity checks do not make the
final binding stable through return. This was independently reproduced with a
temporary deterministic pytest probe: after the second source recovery-file
verification, the canonical restore-ID directory was renamed aside and an
unknown directory was created at the original name. The remaining validation
continued through the already-open old operation fd and preparation returned
success. Actual probe result: exit 1, `Failed: DID NOT RAISE
InboxPreparationError`.

The same review identified an exact-read-to-append journal window and a case
where replacement of the bound `.discarded/` namespace prevents quarantine of
a just-created public operation directory. Adding another pathname recheck or
post-write read only relocates these races. Closing them requires an explicit
architecture decision about publication/immutability/serialization and cleanup
fallbacks.

Therefore Wave 3 is BLOCKED before commit. The 89/123/628 green runs above are
evidence for the partial listed fixes, not evidence that Task 4 is complete. No
Wave 3 commit was created, no fourth repair was attempted, and Task 5 remains
blocked. See `.superpowers/sdd/task-4-wave-3-handoff.md` for the exact resume
state.

Two further temporary probes independently reproduced the related Important
races before being removed from the tracked test suite:

- Journal read-to-append probe: `_write_all` inserted a complete unknown JSONL
  event immediately before the transaction's own later event on the same append
  fd. Expected `InboxPreparationError`; actual exit 1 with `Failed: DID NOT
  RAISE InboxPreparationError`.
- Discarded-namespace probe: immediately after operation mkdir, the bound
  `.discarded/` was renamed aside and replaced before an injected parent-fsync
  failure. Expected no public operations; actual exit 1 because both the saved
  discarded directory and public restore-ID directory remained.

Exact probe construction, commands, results, and the required architecture
decision are frozen in
`.superpowers/sdd/task-4-wave-3-architecture-blocker.md`.

The partial Wave 3 implementation/tests are frozen on temporary branch
`wip/inbox-task4-wave3-architecture` as evidence-only commit `5f8d2df`
(`wip: explore complete inbox state binding`). It is not an accepted repair
commit and must not be cherry-picked unless a later approved architecture
explicitly decides to reuse it.
