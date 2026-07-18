# Obsidian KB Skill — Inbox Transaction Plan Review Handoff

**Written:** 2026-07-19, Asia/Shanghai

**Status:** safe pause; Goal remains active; implementation has not started

**Authoritative for:** the Inbox transaction redesign, reviewed specification,
implementation-plan review findings, and the exact next resume action

This document supersedes the Inbox Task 4/5 status and resume instructions in
`2026-07-19-inbox-transaction-architecture-handoff.md`. That earlier handoff
remains useful as the evidence trail for why the old prepared-path contract was
abandoned.

## Non-negotiable delivery rules

- Never implement, merge, or commit on `master`.
- Keep independent risk domains on separate branches/worktrees.
- Preserve reversible commits and evidence branches; never cherry-pick Wave 3
  commit `5f8d2df` as accepted implementation.
- Do not merge or push unless the user changes the standing instruction.
- Use TDD, exact-range independent review, and verification before acceptance.
- Do not start production implementation until the plan below receives two
  independent `READY` verdicts for its exact final commit.
- Do not mark the Goal complete: the broader README, templates, Inbox product
  integration, Skill/token optimization, and remaining roadmap work are still
  pending.

## Goal state

The existing Goal remains active; do not create a duplicate and do not mark it
blocked merely because this session paused.

```text
thread: 019f6aa1-7579-71b3-9585-126c6b9d0c9b
status: active
objective: continuously improve project/code structure, robustness, README,
           templates, Inbox integration, Skill reasonableness, and token use
```

The user requested this checkpoint because the current token/context budget was
ending. This is a deliberate safe pause, not completion.

## Repository and worktree state at pause

```text
master
  path:   /Users/shaopc/playground/obsidian-kb-skill
  commit: 8785da8
  rule:   untouched; never work here

fix/inbox-data-safety
  path:   .worktrees/inbox-data-safety
  commit: c816607
  role:   accepted Inbox integration history and prior architecture handoff

design/inbox-transaction-capability-session
  path:   .worktrees/inbox-transaction-design
  commit before this checkpoint: 29b4a2f
  role:   active design and implementation-plan branch

wip/inbox-task4-wave3-architecture
  path:   .worktrees/inbox-task4-hardening
  commit: 5f8d2df
  role:   evidence only; never cherry-pick as accepted

fix/shared-note-domain
  path:   .worktrees/shared-note-domain
  commit: 8132365
  role:   accepted and frozen

design/skill-evolution-roadmap
  path:   .worktrees/skill-evolution-roadmap
  commit: 7fb770b
  role:   accepted roadmap/design history
```

No merge or push was performed. The earlier read-only credential check showed
that `gh auth status` succeeds for `Spc-jgs`, `origin` uses HTTPS, and the token
reports `repo` scope. This demonstrates likely fetch/pull/push capability but no
remote write was attempted.

## Completed and accepted in this design wave

The final specification is:

```text
docs/superpowers/specs/2026-07-19-inbox-transaction-capability-session-design.md
exact reviewed commit: cacec59
review result: READY from two independent reviewers
```

Specification history:

```text
6072b46 docs: design capability-scoped inbox transactions
7bf3bde docs: specify inbox recovery protocols
5771836 docs: close inbox crash recovery gaps
cacec59 docs: complete inbox crash phase protocol
```

The accepted design replaces the path-only prepared operation with a
capability-scoped transaction session. Its key invariants are:

- Public mutation remains the thin `apply_inbox_item()` façade; no public
  prepare API and no path-only `PreparedInboxOperation`.
- One session holds the Vault capability, persistent Vault-level Inbox lock,
  recovery/journal/backup/stage capabilities, rollback resources, and warnings
  through a terminal state.
- The persistent lock path is
  `.obsidian-kb-backups/inbox/.locks/inbox.lock`; ordinary release never deletes
  or tombstones it.
- Schema 2 recovery manifests and a hash-chained journal use the exact phase
  protocol in the specification.
- Destination publication uses a durable recovery stage and no-overwrite
  hard-link semantics. Unsupported publication fails closed according to the
  specified absent/exact/unknown classification.
- Recovery handles missing, empty, partial, repaired, and crash-classified
  journal bootstrap states.
- Source removal is last. Rollback preserves unknown edits and requires exact
  ownership plus expected content when live identity is available.
- Preview is read-only and uses a separate secure path capability; if no safe
  no-follow traversal exists it fails before opening a recovery record.
- Mutation is supported only on the specified CPython 3.11 Linux/macOS local
  filesystem capability set. Planning remains available elsewhere.
- The threat model is intentionally honest: advisory-lock cooperation and
  observed interference are covered; a malicious same-OS-user process racing
  adjacent syscalls is outside the guarantee.

Baseline tests were green before the docs-only design work:

```text
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py \
  tests/test_inbox_transaction.py \
  tests/test_backup_policy.py \
  tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q

result: passed, exit 0
```

## Implementation plan status — not accepted

The current plan is:

```text
docs/superpowers/plans/2026-07-19-inbox-transaction-capability-session.md
initial plan commit: 29b4a2f
review result: NOT READY (0 Critical, 6 Important, 4 Minor across two reviews)
production implementation: NOT STARTED
```

The plan contains ten TDD tasks covering runtime models, bound paths/platform
probes, persistent locking, schema 2 recovery/journal, session preparation,
apply/rollback, fresh-process restore, CLI integration, generated packaging,
and final verification.

One review fix was started before this checkpoint: the plan now says to record
the exact final Reviewer-accepted design HEAD once in
`.superpowers/sdd/progress.md` and reuse it as the immutable implementation
review base. This checkpoint deliberately preserves that partial edit, but the
plan must not be treated as Reviewer-accepted until all findings below are
resolved and the exact new commit is re-reviewed.

## Required plan amendments before re-review

Resolve every item below in the plan, then commit and request two fresh reviews
against the exact commit.

### Important findings

1. **Use one immutable implementation base everywhere.** Task 10 still
   recomputes `git merge-base`. It must instead read `Implementation base:` from
   `.superpowers/sdd/progress.md`, assert it is non-empty and an ancestor, and
   use that literal hash for every diff/review package. Never replace it with a
   later merge-base.
2. **Require real Windows evidence.** A textual PowerShell-script contract is
   not runtime evidence. If running on Windows, execute the smoke script. On a
   non-Windows host, final cross-platform acceptance requires a Windows CI/job
   artifact for the exact implementation HEAD with exit 0. Because the standing
   instruction forbids push, do not trigger remote CI without new authority;
   report this external gate honestly if it remains pending.
3. **Thread capability probes through internal dependency injection.** Add an
   immutable/default `CapabilityProviders` bundle (or equivalent) for mutation
   and preview probes. Session and restore internals accept it; public façades
   keep stable signatures and construct defaults. Tests inject fakes.
4. **Strengthen live rollback ownership.** Destination removal requires both
   exact transaction-owned identity and the expected rendered hash whenever
   identity is available. Index rollback similarly requires exact installed
   identity and the expected after-hash. Add RED tests for identical bytes on a
   different inode for both destination and index.
5. **Define the preview shared-lock API.** Task 3 must add a read-only
   `acquire_shared_existing()` (or equivalent) that never creates/writes the
   lock, uses nonblocking shared `flock`, verifies binding, and keeps owner text
   warning-only. Task 5 uses exclusive acquisition; Task 7 uses shared.
6. **Fix factory fd ownership.** `VaultCapability.open()`,
   `InboxVaultLock.acquire_*()`, and `RecoveryRecord.create()` own every local fd
   until successful return. Any pre-return exception closes them in reverse
   order and reports incomplete recovery debris where applicable. Successful
   return is the only ownership-transfer point. Add close-trace/fd-count fault
   injection at each factory checkpoint.

### Minor findings

1. Replace source-substring dependency tests with AST/import-graph checks for
   forbidden planner/session imports.
2. Replace the `fync` typo with `fsync`.
3. Describe lock-owner metadata as crash-tolerant, warning-only diagnostics;
   the secure recovery scan is authoritative.
4. Remove the obsolete final instruction to continue old Inbox Tasks 6–9.
   After reversible integration regression, continue the next roadmap risk
   domain without rerunning superseded tasks.

## Exact next resume procedure

1. Enter the design worktree and verify branch/status before editing:

   ```bash
   cd /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-transaction-design
   git status --short --branch
   git log -5 --oneline
   ```

2. Read this handoff, the accepted specification, and the current plan in full.
3. Finish only the plan amendments listed above. Do not touch production code.
4. Run documentation integrity checks:

   ```bash
   git diff --check
   rg -n 'TODO|TBD|fync|merge-base HEAD design/inbox-transaction' \
     docs/superpowers/plans/2026-07-19-inbox-transaction-capability-session.md
   ```

5. Commit the amended plan on
   `design/inbox-transaction-capability-session` with a reversible docs-only
   commit.
6. Ask two independent reviewers to evaluate the exact commit: one for
   specification/supersession/platform gates and one for transaction ownership,
   rollback, locking, and fd lifetime. Require `READY / 0 Critical / 0
   Important` from both.
7. Only after that gate, read and use
   `superpowers:subagent-driven-development`; create a fresh
   `fix/inbox-transaction-capability-session` worktree from the exact accepted
   design HEAD, record that literal base once, and execute the plan with TDD.
8. Keep `master`, the integration branch, and Wave 3 evidence untouched. Do not
   merge or push.

## Resume checklist

```text
[ ] design worktree is clean and on design/inbox-transaction-capability-session
[ ] accepted specification commit cacec59 is an ancestor
[ ] all 6 Important and 4 Minor plan findings are fixed
[ ] plan integrity checks pass
[ ] exact amended-plan commit receives two READY verdicts
[ ] fresh implementation worktree starts from that exact commit
[ ] implementation base is recorded once, never recomputed
[ ] production work uses RED → GREEN → refactor and reversible commits
[ ] Windows exact-HEAD runtime evidence is obtained or honestly left pending
[ ] no master edit, merge, push, or Wave 3 cherry-pick occurs
```

## Final warning

Do not confuse the accepted specification (`cacec59`) with an accepted
implementation plan. The plan at `29b4a2f` failed review, and the checkpoint
following it contains only the beginning of the required corrections. The next
safe action is plan repair and exact-commit re-review, not implementation.
