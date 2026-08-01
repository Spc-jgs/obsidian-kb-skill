# Inbox Task 4 Hardening SDD Progress

Base: `6a0ac41`
Branch: `fix/inbox-task4-hardening`
Parent active branch: `fix/inbox-data-safety` at `26e30f5` when dispatched

Baseline: 87 passed for Task 4 + Vault/path regressions.

Task 4 integrated fix wave 1: complete at `1cef079`; re-review failed

- Prior review: spec FAIL, quality CHANGES_REQUESTED.
- Required closure: two Critical, five Important, two Minor findings in
  `.superpowers/sdd/task-4-fix-brief.md`.
- Re-review: spec FAIL, quality CHANGES_REQUESTED. Remaining: manifest/backup
  identity at success, race-free whole-operation cleanup, fd exception hygiene,
  and later journal identity binding.
- Task 4 fix wave 2: implementation and local verification complete from
  `1cef079`; independent review pending. See
  `.superpowers/sdd/task-4-wave-2-handoff.md`.
- Gate: exact `604b64a..<repair-head>` package, independent re-review with spec
  PASS and quality APPROVED.
- Integration after approval: cherry-pick only the accepted repair commit onto
  `fix/inbox-data-safety`, rerun focused/required regressions, then mark Task 4
  complete in the parent ledger.

Task 5+: blocked by the Task 4 review gate; not started here.

Implementation evidence so far:

- deterministic integrated RED: 11 failed / 2 control tests passed;
- supplemental RED: unknown initial journal append, 1 failed;
- supplemental RED: creation-fd fstat orphan, 1 failed;
- focused GREEN: 68 passed;
- final required Task 4 + Vault/path GREEN: 102 passed;
- final broad suite excluding the single known Task 8 generated drift:
  607 passed;
- compileall and pre-commit diff-check: exit 0.
- repair commit: `1cef079` (`fix: harden inbox recovery preparation`);
- post-commit exact range diff-check and clean status: exit 0.

Deferred Minor: the Task 4 raising API cannot transport cleanup/release
warnings from arbitrary exception paths. Task 5 must attach them when it maps
preparation exceptions into `InboxApplyResult`.

Wave 2 final local evidence (2026-07-19): required Task 4 + Vault/path
regression passed 116 tests; broad suite passed 621 selected tests with only the
known Task 8 generated drift excluded; compileall and `git diff --check` passed.
Wave 2 commit: `f5ef1ec` (`fix: bind inbox recovery identities`).

Task 4 fix wave 3: **BLOCKED; architecture reassessment required**.
The listed Wave 3 cases reached GREEN and pre-blocker gates passed (focused 89,
path 123, broad 628 selected, compile/diff), but independent pre-commit review
and a deterministic local repro proved final operation binding is not stable
through return. Related journal read/append and unavailable-quarantine races
also remain. Evidence is frozen only in non-accepted WIP `5f8d2df`; no accepted
Wave 3 commit exists. Do not attempt a fourth patch wave or Task 5. See
`.superpowers/sdd/task-4-wave-3-handoff.md`.

Wave 2 independent review: spec FAIL, quality CHANGES_REQUESTED. Remaining:
one Critical (backup ancestor identity chain) and two Important (exact advancing
journal state; quarantine after post-mkdir fsync/open failure).

Task 4 fix wave 3: in progress from `f5ef1ec`; see
`.superpowers/sdd/task-4-fix-wave-3.md`. If its re-review still fails, stop and
reassess architecture before any fourth patch wave.
