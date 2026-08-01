# Task 4 Fix Wave 3 Handoff

Date: 2026-07-19
Branch: `wip/inbox-task4-wave3-architecture`
Wave 3 base: `f5ef1ec` (`fix: bind inbox recovery identities`)
Evidence-only WIP: `5f8d2df` (`wip: explore complete inbox state binding`)
Accepted Wave 3 commit: **none — architecture blocker**

## Status

Status: **BLOCKED_ARCHITECTURE_REASSESSMENT**.

The listed Wave 3 findings reached RED/GREEN and the original gates passed, but
the required pre-commit independent review found a further Critical verify/use
race and two related Important races. A deterministic local probe reproduced
the Critical (`Failed: DID NOT RAISE InboxPreparationError`). Per the Wave 3
stop contract, no accepted commit was created and no fourth patch wave may be
attempted without controller/user architecture direction. Task 5 remains
blocked. `5f8d2df` freezes evidence only and must not be integrated as Wave 3.

Tracked scope remains exactly:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `tests/test_inbox_transaction.py`

## Wave 3 Changes

- Each source/index backup now stores and verifies the complete
  operation-relative ancestor directory identity chain before opening the next
  component and final recovery file.
- Journal state is exact, not prefix-based. Each later append compares the
  complete current bytes on the verified fd and advances expected bytes only
  after its own event is written and fsynced.
- Once operation `mkdir` succeeds, parent-fsync, first-open, and fstat failures
  close acquired fds and atomically quarantine the owned public entry under the
  bound `.discarded/` namespace. `FileExistsError` from mkdir never moves the
  pre-existing entry.

## TDD and Verification

Wave 3 selected RED produced 6 expected failures and 1 already-green sequential
append control. After the minimal implementation, all 7 selected cases passed.

Pre-blocker local gates on 2026-07-19 (evidence for the partial implementation,
not a completion claim):

- focused Task 4 suite: 89 passed;
- required Task 4 + Vault/path regression: 123 passed;
- broad suite: 628 selected passed, excluding only the known Task 8 generated
  payload drift;
- compileall and diff-check: exit 0.

## Architecture Blockers Found Before Commit

Critical: final binding is not stable through return. The final preamble check
opens and validates the canonical operation root, then continues entirely via
that old fd. After the second source verification, a deterministic probe renamed
the public restore-ID directory aside, created an unknown directory at the same
canonical name, and observed `prepare_inbox_operation()` return success pointing
at the unknown directory. Rechecking one more pathname only moves the race; a
finite sequence cannot atomically bind several mutable pathnames through return.

Important: an unknown journal append between exact read and the transaction's
own append can be accepted by that `_append_event()` call. The in-memory
expected bytes then differ from actual bytes. A post-write read only moves the
same race without a kernel-enforced serialization primitive.

Important: if `.discarded/` is replaced after successful operation mkdir but
before quarantine, bound-namespace verification correctly refuses the new
directory, yet Task 4 cannot quarantine the public restore-ID entry and cannot
return the swallowed cleanup warning. Guaranteeing no public orphan needs a
fallback architecture, not another local check.

## Remaining Concerns

- Task 5 must transport cleanup/release warnings through
  `InboxApplyResult.warnings`.
- `.discarded/` and `.locks/.released/` need a future identity-safe capacity
  policy. Unsafe deletion/pruning remains forbidden.
- The excluded generated-payload drift belongs to Task 8.

## Resume and Integration Order

Read this handoff, `.superpowers/sdd/task-4-fix-wave-3.md`, and
`.superpowers/sdd/task-4-report.md`. The worktree intentionally contains an
evidence-only WIP commit for architecture assessment; do not present it as
complete or cherry-pick it without a newly approved design.

The first two accepted hardening commits remain, in order:

1. `1cef079` — `fix: harden inbox recovery preparation`
2. `f5ef1ec` — `fix: bind inbox recovery identities`
3. **not created** — requires architecture decision and a new authorized plan

Do not start Task 5, a fourth patch wave, merge, or push until the architecture
is reassessed and explicitly authorized.
