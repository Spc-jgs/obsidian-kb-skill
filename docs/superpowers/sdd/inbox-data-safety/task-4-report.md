# Task 4 Report: Backup Store, Manifest, Journal, and Locks

Status: DONE

Commit: `6a0ac41` (`feat: add inbox transaction recovery store`)

## Scope and Four-State Safety

The commit contains exactly the four tracked files allowed by the brief:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `obsidian_kb_skill/scripts/backup_policy.py`
- `tests/test_inbox_transaction.py`
- `tests/test_backup_policy.py`

Across every normal injected preparation failure, the asserted four-state
business boundary was:

1. source bytes remained byte-for-byte exact;
2. managed index bytes remained byte-for-byte exact;
3. the destination remained lexically absent;
4. the external sentinel directory remained empty.

Task 4 writes only locks and recovery-store files. It does not create/write a
destination or temp business file, replace an index, or unlink a source.

## RED

Required initial command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q
```

Actual initial result: exit 2 during collection. The exact root failure was
`ModuleNotFoundError: No module named
'obsidian_kb_skill.scripts.inbox_transaction'`, the expected missing Task 4
production API.

Self-review added two focused security RED cycles.

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q \
  -k backup_verification_rejects_symlink_swap
```

Actual pre-fix result: 1 failed, exit 1. Replacing the newly written source
backup with an out-of-Vault symlink containing identical bytes did not raise.
Root cause: verification reused `Path.read_bytes()` on the previously resolved
path instead of re-resolving and opening with `O_NOFOLLOW`.

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q \
  -k lock_cleanup_retains_replaced_regular_file
```

Actual pre-fix result: 1 failed, exit 1. `_release_locks()` deleted an unknown
regular file that had replaced an acquired lock. Root cause: cleanup checked
only file kind, not the acquired file identity.

## GREEN and Regression

Both supplemental targeted commands passed 1 test, exit 0, after their minimal
fixes. Backup verification now uses the Vault resolver plus an `O_NOFOLLOW`
descriptor for source and index backups. Lock release records `(device, inode)`
at exclusive acquisition and preserves replacements as unsafe.

Final focused command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q
```

Actual final result: 53 passed, exit 0.

Required preparation/path regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q
```

Actual final result: 87 passed, exit 0.

Additional broad regression:

```bash
uv run --locked --extra dev pytest -q \
  -k 'not test_build_check_still_passes'
```

Actual result: exit 0 with only the known generated-tree build check
deselected. The unfiltered full suite had exactly one failure:
`tests/test_lazy_references.py::test_build_check_still_passes`. Its output says
the generated Skill runtime is out of sync for prior Task 1-3 canonical changes
and this Task's new/changed canonical files. Distribution sync is expressly
outside Task 4's four-file scope and belongs to Task 8; no generated file was
modified to conceal that pending gate.

Additional checks:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py
git diff --check
```

Both exited 0. The post-commit status was clean on
`fix/inbox-data-safety`.

## Checkpoint Results

- `lock-source`: injected before source lock acquisition; no operation record,
  no held lock, four-state unchanged.
- `lock-index`: any earlier acquired lock was identity-checked and released;
  no operation record, four-state unchanged.
- `backup-root`: both acquired locks were released; no operation directory,
  four-state unchanged.
- `backup-source-write`: the exclusive empty operation directory was removed;
  locks released, four-state unchanged.
- `backup-source-fsync`: exact source backup had been fsynced, but without a
  durable manifest it was safely removed with its owned directories; locks
  released, four-state unchanged.
- `backup-index-write`: unpersisted exact source-backup debris was safely
  removed; locks released, four-state unchanged.
- `manifest-write`: verified backups and unpersisted operation debris were
  safely removed; locks released, four-state unchanged.
- `manifest-fsync`: the already-fsynced manifest and verified exact backups
  were retained as a durable recovery record; locks released, four-state
  unchanged.
- `journal-backup-ready`: the durable manifest/backups were retained and no
  success was returned without the journal event; locks released, four-state
  unchanged.

The malicious backup-symlink injection deliberately leaves unsafe debris
instead of following or deleting it. The external target remains unchanged.
The lock-replacement injection likewise retains the unknown replacement and
returns a cleanup warning.

## Self-review

- `ApplyStatus`, `InboxApplyResult`, and `PreparedInboxOperation` field order,
  defaults, and reflected type hints exactly match the brief.
- Restore IDs contain an ASCII UTC `Z` timestamp and a random 16-hex suffix.
  Operation directories are created with exclusive semantics below the exact
  `.obsidian-kb-backups/inbox/<restore-id>/` namespace.
- All Vault source, destination, index, operation, lock, backup, manifest, and
  journal targets pass through the canonical Vault resolvers. Existing/broken
  symlink backup and lock roots fail closed without external writes.
- Source and optional changing-index locks use SHA-256 keys and are acquired in
  sorted hash-key order. A second transaction receives the stable original
  owner restore ID and cannot overwrite or steal the first lock.
- `_write_new_durable()` uses exclusive creation, buffered write, flush, and
  `os.fsync()`. Manifest JSON uses sorted compact keys, UTF-8, and a final
  newline. It stores only Vault-relative POSIX paths.
- Exact source/index bytes are read from regular files, durably copied, then
  re-resolved/re-read and checked for exact byte and hash equality before the
  manifest is written.
- `prepare_inbox_operation()` returns only after the verified backups,
  fsynced manifest, and fsynced `backup-ready` JSONL event exist. It returns
  held locks for Task 5; all failure paths release this operation's safe locks.
- The injector is protocol-only. The production module has no environment or
  CLI failure backdoor and emits only the nine Task 4 checkpoint names.
- Ordinary retention skips exactly top-level `inbox` without warnings.
  Timestamp histories containing an `inbox/` note path still prune normally,
  and near names such as `inbox-copy` remain visible as unknown warnings.
- No master operation, push, merge, generated runtime change, business-file
  mutation, or unrelated refactor was performed.
- The requested reviewer-dispatch skill could not allocate another agent
  because the collaboration thread limit was already reached. The same review
  rubric was applied locally and produced the two supplemental RED/GREEN fixes
  above.

## Concerns

- `build.py --check` remains intentionally red until Task 8 synchronizes the
  accumulated canonical runtime changes into generated distributions. All
  Task 4 required regressions and the full suite excluding that one known gate
  are green.
