# Task 4 Fix Wave 2 Handoff

Date: 2026-07-19
Branch: `fix/inbox-task4-hardening`
Base commit: `1cef079` (`fix: harden inbox recovery preparation`)
Wave 2 commit: `f5ef1ec` (`fix: bind inbox recovery identities`)

## Status

Implementation and local verification are complete. The next action is an
independent Task 4 review; do not start Task 5 or merge to `master` before that
gate passes.

The tracked change is deliberately limited to:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `tests/test_inbox_transaction.py`

## What Changed

- Recovery manifest, source backup, index backup, operation directory, and
  journal are bound to exact creation identities and expected bytes/hashes.
- The initial journal uses exclusive creation; later appends open without
  creation and verify the same fd, inode identity, and immutable prefix.
- Failed preparation now atomically renames the whole operation directory into
  the bound `.discarded/` namespace. Cleanup never path-deletes unknown data.
- Both `.discarded/` and `.locks/.released/` are identity-bound so replacing an
  inert namespace cannot redirect tombstone writes into an attacker-controlled
  directory.
- Creation/open fd paths close descriptors even when `fstat` or identity
  capture fails.
- Regression tests cover manifest/backup/journal replacement, same-inode
  journal mutation, cleanup races, inert-namespace replacement, and fd hygiene.

## Verification

All commands exited 0 on 2026-07-19:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q

uv run --locked --extra dev pytest -q \
  -k 'not test_build_check_still_passes'

uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py

git diff --check
```

The required path run passed 116 tests. The broad run passed 621 selected
tests; only the already-known Task 8 generated-payload check was excluded.

## Remaining Concerns

- Cleanup/release warnings cannot be returned through Task 4's raising API.
  Task 5 should attach them when mapping exceptions to `InboxApplyResult`.
- `.discarded/` and `.locks/.released/` intentionally retain tombstones. A
  future lifecycle/capacity policy must prune only with equally strong identity
  guarantees.
- The excluded generated-payload drift belongs to Task 8 and is unrelated to
  this two-file repair.

## Resume Procedure

1. Read `.superpowers/sdd/task-4-fix-wave-2.md`, this file, and
   `.superpowers/sdd/task-4-report.md`.
2. Review the exact range `1cef079..f5ef1ec` for Task 4 only.
3. Require spec PASS and quality APPROVED.
4. If approved, cherry-pick the single wave-2 commit onto
   `fix/inbox-data-safety`, rerun focused/path regressions, then unblock Task 5.
5. Do not merge or push to `master` without explicit user direction.
