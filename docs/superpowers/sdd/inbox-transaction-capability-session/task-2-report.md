# Task 2 Report: Bound Path Capabilities and Platform Probes

## Status

DONE_WITH_CONCERNS

Implemented the exact Task 2 public surface in a descriptor-bound path layer,
with capability ownership, no-follow traversal, full regular-file identity plus
content-hash guards, explicit durability boundaries, and separate read-only
mutation/preview capability probes.

## RED evidence

Command (run before `paths.py` existed):

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_paths.py -q
```

Observed result:

```text
ERROR collecting tests/test_inbox_tx_paths.py
tests/test_inbox_tx_paths.py:11: in <module>
    from obsidian_kb_skill.scripts.inbox_tx.paths import (
E   ModuleNotFoundError: No module named 'obsidian_kb_skill.scripts.inbox_tx.paths'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

This was the expected RED: the test imported the required Task 2 API, while the
production module had intentionally not yet been created.

Additional focused RED evidence found during implementation/self-review:

- Root resolution initially preserved `InvalidVaultRootError`, not its
  underlying `OSError`, as `InboxTransactionError.__cause__`.
- `ensure_directory()` leaked the just-opened child fd if its post-open
  identity `fstat` failed.
- `open_directory()` leaked the just-opened child fd if closing the previous
  local parent fd failed.

Each was reproduced by one focused failing test before its production fix.

## GREEN and regression evidence

Focused final command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_paths.py -q
```

Result: 55 tests passed.

Brief-specified shared regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_paths.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py tests/test_environment_contract.py -q
```

Result: 97 tests passed, no warnings or failures.

Compile command:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_tx/paths.py tests/test_inbox_tx_paths.py
```

Result: exit 0 with clean output.

Staged whitespace check: `git diff --cached --check` exited 0.

An extra full-suite diagnostic was also run. It stopped at the existing
generated-tree consistency test after 553 passes because `build.py --check`
reports generated payload drift spanning pre-existing Task 1/legacy files and
this new Task 2 module. Updating generated payloads is outside the Task 2
allowlist and was deliberately not done.

## Changed files

- `obsidian_kb_skill/scripts/inbox_tx/paths.py`
- `tests/test_inbox_tx_paths.py`

The required report is the only additional uncommitted artifact.

## Commit

`792c023` — `fix: bind inbox transaction paths to descriptors`

## Contract self-review

- **FD ownership and close trace:** Vault root, root BoundDirectory, nested
  BoundDirectory, and returned regular-file fds are distinct owners. Close is
  idempotent and warnings are Vault-relative. Fault tests prove local cleanup
  and reverse close order when open/fstat/close fails; closing a parent owner
  does not close independent children.
- **Symlink/no-follow:** Directory components use descriptor-relative
  `O_DIRECTORY|O_NOFOLLOW`; ancestor symlinks at multiple depths, dangling
  final symlinks, FIFO/non-regular entries, and lexical dangling-symlink
  occupancy are covered.
- **Identity chain:** The immutable chain records root-to-leaf bindings.
  Revalidation reopens the public chain, rejects replacement, and compares
  only device/inode so legitimate sibling size/mtime changes pass.
- **Lexical policy:** Business/recovery validators reject dot/parent/absolute,
  foreign Windows drive/UNC shapes, and business use of the recovery control
  namespace. POSIX literal backslashes remain valid filenames; native name
  separators cannot smuggle traversal.
- **I/O and durability:** Positional short reads preserve offset; short writes
  complete. Durable create ordering is create/write/file-fsync/parent-fsync.
  Link/unlink/replace tests prove no implicit parent fsync and call the explicit
  boundary immediately afterward.
- **Compare-and-mutate:** Full source/destination identities and `sha256:`
  hashes are required. Every identity/hash mismatch preserves both source and
  destination objects; success verifies absence/installed source identity.
- **Probes:** Mutation and preview adapters are distinct, stateless, injectable
  via a frozen provider bundle, and read-only. Missing dir-fd, no-follow,
  directory-fsync, hard-link, and flock capabilities are exercised. Preview
  returns shared-lock or double-read as the complete serialization decision.

## Concerns

- The extra full suite is not clean because generated installable payloads are
  already out of sync and now also lack this canonical Task 2 module. The
  brief explicitly prohibited modifying those generated files; Wave/integration
  work must regenerate them later.
- Runtime tests executed on macOS/Python 3.14.6. Foreign-Windows lexical behavior
  and missing-platform primitives are fault-injected, but real Windows/Linux
  kernel behavior was not available in this checkout.
- The internal self-review agent was stopped to avoid delaying controller-owned
  independent Task review; no reviewer findings were received.
