# Obsidian KB Skill — Inbox Transaction Plan Review Handoff

**Written:** 2026-07-19, Asia/Shanghai

**Status:** specification and implementation plan accepted; Goal remains active;
production implementation has not started

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
- Start production implementation only from the final exact HEAD of this design
  branch after the handoff-only commit also receives exact-HEAD confirmation.
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
  accepted plan commit before final handoff: 9bfe3c5
  role:   accepted design/plan history; source for the implementation branch

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

## Implementation plan status — accepted

The current plan is:

```text
docs/superpowers/plans/2026-07-19-inbox-transaction-capability-session.md
initial plan commit: 29b4a2f
accepted plan commit: 9bfe3c5ecd9a236ebcf7a09552d94fa3edc1cce5
review result: READY / 0 Critical / 0 Important / 0 Minor
               from two independent reviewers
production implementation: NOT STARTED
```

The plan contains ten TDD tasks covering runtime models, bound paths/platform
probes, persistent locking, schema 2 recovery/journal, session preparation,
apply/rollback, fresh-process restore, CLI integration, generated packaging,
and final verification.

The plan passed after two repair/review waves. The first review of `29b4a2f`
found six Important and four Minor issues. The review of `942cc2a` confirmed the
transaction boundary but found two additional Important and two Minor planning
gaps. `9bfe3c5` closed every finding and both independent reviewers returned
`READY / 0 / 0 / 0` for that exact commit.

The accepted corrections include:

- immutable one-time `Implementation base:` and `Master base:` records, with
  machine assertions and no dynamic replacement merge-base;
- actual Windows exact-HEAD execution or externally verifiable CI artifact as a
  release gate; a textual script test is explicitly insufficient;
- frozen mutation/preview providers threaded through internal session/restore
  seams, including explicit preview `shared-lock` versus `double-read` modes;
- a read-only shared-existing lock API that cannot create or write the lock;
- factory-local fd ownership until successful return, reverse close on failure,
  and incomplete debris propagation;
- live destination/index rollback requiring owned identity **and** expected
  hash, with same-bytes/new-inode RED cases;
- AST import-graph dependency checks, corrected `fsync` wording, authoritative
  recovery scan semantics, accurate supersession, Task 9 RED ordering, and no
  obsolete instruction to rerun superseded Inbox tasks.

## Exact next resume procedure

1. Enter the design worktree and verify branch/status before editing:

   ```bash
   cd /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-transaction-design
   git status --short --branch
   git log -5 --oneline
   ```

2. Read this handoff, the accepted specification, and the accepted plan in full.
3. Read and use `superpowers:using-git-worktrees`,
   `superpowers:subagent-driven-development`, and
   `superpowers:test-driven-development` before production edits.
4. Create fresh sibling branch/worktree
   `fix/inbox-transaction-capability-session` from the exact current
   `design/inbox-transaction-capability-session` HEAD. Do not reuse Wave 3.
5. Print the implementation/design HEAD and `master` HEAD once. Record their
   literal 40-character values as `Implementation base:` and `Master base:` in
   the ignored `.superpowers/sdd/progress.md` using `apply_patch`; never
   recompute replacements.
6. Run the plan's baseline suite before editing production code:

   ```bash
   uv run --locked --extra dev pytest \
     tests/test_inbox_plan.py tests/test_inbox_transaction.py \
     tests/test_backup_policy.py tests/test_vault_paths.py \
     tests/test_path_safety_e2e.py -q
   ```

7. Execute Task 1 with RED first. Use one implementer per bounded task and fresh
   spec/quality review gates before advancing, exactly as the plan requires.
8. Keep `master`, the integration branch, and Wave 3 evidence untouched. Do not
   merge or push.

## Resume checklist

```text
[x] design worktree is clean and on design/inbox-transaction-capability-session
[x] accepted specification commit cacec59 is an ancestor
[x] all plan-review findings are fixed
[x] plan integrity checks pass
[x] exact plan commit 9bfe3c5 receives two READY / 0 / 0 / 0 verdicts
[ ] fresh implementation worktree starts from the final reviewed design HEAD
[ ] implementation and master bases are recorded once, never recomputed
[ ] production work uses RED → GREEN → refactor and reversible commits
[ ] Windows exact-HEAD runtime evidence is obtained or honestly left pending
[ ] no master edit, merge, push, or Wave 3 cherry-pick occurs
```

## Final warning

The specification and plan are accepted; the implementation is not. Do not
describe docs-only commit `9bfe3c5` as a working transaction, do not cherry-pick
Wave 3, and do not skip the fresh implementation worktree, recorded baselines,
baseline tests, or Task 1 RED gate.
