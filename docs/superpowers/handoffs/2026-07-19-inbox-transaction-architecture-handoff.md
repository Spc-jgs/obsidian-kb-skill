# Obsidian KB Skill — Inbox Transaction Architecture Handoff

**Written:** 2026-07-19, Asia/Shanghai

**Status:** safe pause; Goal remains active

**Authoritative for:** the current Task 4 stop point and the next resume action

This handoff supersedes the Task 4 / next-action sections of
`2026-07-16-obsidian-kb-skill-handoff.md`. The earlier document remains the
authoritative history for the roadmap and accepted Tasks 1–3.

## Non-negotiable delivery rules

- Never implement on `master`.
- Keep independent risk domains on separate branches/worktrees.
- Preserve reversible commits and do not destroy temporary evidence branches.
- Do not merge or push unless the user changes the standing instruction.
- Use TDD, exact-range independent review, and verification before acceptance.
- Do not start Task 5 until the redesigned Task 4 contract is accepted.

## Goal state

The existing Goal is active; do not create a duplicate.

```text
thread: 019f6aa1-7579-71b3-9585-126c6b9d0c9b
status: active
objective: continuously improve project/code structure, robustness, README,
           templates, Inbox integration, Skill reasonableness, and token use
```

The user asked for a safe pause because the current context/token budget was
ending. This is not a claim that the overall Goal or Inbox branch is complete.

## Verified repository state

All listed worktrees were clean when this handoff was written.

```text
master                              8785da8  untouched
  /Users/shaopc/playground/obsidian-kb-skill

fix/inbox-data-safety               26e30f5  active integration branch
  .worktrees/inbox-data-safety

wip/inbox-task4-wave3-architecture  5f8d2df  evidence only; never cherry-pick as accepted
  .worktrees/inbox-task4-hardening

fix/inbox-task4-hardening            f5ef1ec  last ordered hardening evidence
  branch ref only; same repair worktree is currently on the WIP branch

fix/shared-note-domain              8132365  accepted and frozen
  .worktrees/shared-note-domain

design/skill-evolution-roadmap      7fb770b  accepted roadmap/design history
  .worktrees/skill-evolution-roadmap
```

No merge or push was performed. `gh auth status` succeeded for account
`Spc-jgs`; `origin` uses HTTPS and the token reports `repo` scope. This confirms
the local credential is available for ordinary fetch/pull/push operations, but
no write was attempted as part of this check.

## Accepted work

- `fix/shared-note-domain` is accepted at `8132365`.
- Inbox data-safety Tasks 1–3 are accepted through `604b64a`.
- Original Task 4 implementation exists at `6a0ac41`, but Task 4 is not accepted.
- Hardening evidence is ordered as:
  1. `1cef079` — harden Inbox recovery preparation;
  2. `f5ef1ec` — bind Inbox recovery identities;
  3. `5f8d2df` — Wave 3 exploration only, explicitly non-accepted.

Do not cherry-pick `5f8d2df` onto `fix/inbox-data-safety`. Do not describe
`1cef079` or `f5ef1ec` as final Task 4 acceptance: later probes showed that the
underlying contract still needs redesign.

## Exact stop reason

Task 4 reached an architecture boundary, not a routine patch backlog. Three
deterministic probes showed:

1. The canonical public operation directory can be replaced after its last
   pathname verification but before `prepare_inbox_operation()` returns. The
   returned pathname can therefore name unknown content even while checks on
   the old directory fd pass.
2. An unknown journal event can be appended between an exact read and the
   transaction's own append. Updating expected bytes afterward does not make
   the read/use interval atomic.
3. If the bound `.discarded/` namespace is replaced after operation-directory
   creation and a durability step fails, safe quarantine refuses the unknown
   namespace but the public incomplete operation can remain. The cleanup
   warning was previously swallowed.

Adding another final check only moves the race. Therefore:

```text
Task 4: ARCHITECTURE_REASSESSMENT_REQUIRED
Task 5: BLOCKED BY TASK 4 CONTRACT
Wave 4: FORBIDDEN WITHOUT A NEW DESIGN AND PLAN
```

Read the primary evidence before resuming:

- `.worktrees/inbox-task4-hardening/.superpowers/sdd/task-4-wave-3-architecture-blocker.md`
- `.worktrees/inbox-task4-hardening/.superpowers/sdd/task-4-wave-3-handoff.md`
- `.worktrees/inbox-task4-hardening/.superpowers/sdd/task-4-report.md`

## Last verification evidence

These results describe the partial Wave 3 implementation; they are not Task 4
acceptance:

```text
focused Task 4 suite:                         89 passed
Task 4 + Vault/path regression suite:        123 passed
broad suite excluding known generated drift: 628 passed
compileall and diff-check:                    passed
architecture probes:                         reproduced the blockers
```

The known deferred red gate remains
`tests/test_lazy_references.py::test_build_check_still_passes`; generated Skill
payload synchronization belongs to Task 8. Do not claim a fully green branch
before Task 8 runs `build.py` and `build.py --check`.

## Recommended redesign direction (proposal, not yet an accepted spec)

The next design should replace the timeless prepared-path snapshot with a
capability-scoped transaction session:

- An `InboxTransactionSession` context manager owns directory/file descriptors,
  advisory lock descriptors, expected journal state, and cleanup warnings for
  the complete prepare → apply → audit → commit/rollback lifetime.
- Task 5 must consume the prepared operation inside that same session; a plain
  pathname-based object must not outlive the capabilities that established it.
- Keep `inbox_transaction.py` as a thin public façade and split internals by
  capability/ownership rather than by the old Task 4/5 boundary: transaction
  session, path capabilities, lock, recovery journal/store, rollback/restore,
  and typed models. Split tests along the same boundaries.
- Replace process-global identity/lock registries with session-owned resources
  and deterministic close/release behavior.
- Prefer one persistent Vault-level Inbox lock file held with an exclusive
  advisory OS lock for the complete transaction. Inbox already applies items
  serially, so this simpler first design has little product cost and avoids the
  deadlock/shared-index/crash-owner complexity of source/index multi-locks. Do
  not delete/tombstone the lock pathname during ordinary release.
- Keep incomplete pre-manifest operation directories as explicit recovery
  debris with truthful typed warnings. Do not depend on a replaceable
  `.discarded/` namespace for best-effort deletion/quarantine.
- Compare and append journal state through one open fd in the same `flock`
  critical section, then fsync the file and operation directory. Add monotonic
  sequence numbers and a previous-event hash. An active transaction rejects a
  truncated tail; only offline recovery may classify/ignore one.
- Revalidate public ancestor bindings from the bound Vault root before and
  after each business-file mutation. Do not rely only on old directory fds,
  because a renamed old tree can remain internally valid while no longer being
  the public tree.
- Keep live backup fds available for in-process rollback; retain the on-disk
  record for crash recovery.
- Fail closed for mutation on platforms or filesystems lacking the required
  local `dir_fd`/no-follow, directory durability, and advisory-lock semantics;
  read-only planning may remain available.

The intended data flow is:

```text
acquire Vault Inbox lock
→ revalidate public bindings
→ create and bind recovery directory
→ durably write backups + manifest + journal
→ revalidate/install destination and index one mutation at a time
→ audit
→ delete source last
→ final revalidation
→ durably journal committed (or rolled back)
→ release lock
```

Any exception must enter rollback while the same lock and capabilities remain
live. The external API should prefer a single `apply_inbox_item()` façade; an
internal `with InboxTransactionSession.open(...) as tx:` may expose
`prepare()/apply()` only inside the context and must reject use after close.

Preparation/apply failures should carry at least `code`, `restore_id`, recovery
location, warnings, recovery debris, and whether business mutation started.
If identity-bound cleanup is unavailable, retain the debris and report
`recovery_required`; never report a clean environment or swallow the warning.

The design must state the threat model honestly. It can guarantee fail-closed
behavior for symlink/path attacks, crashes, observed replacement, and
cooperating Skill processes. It cannot promise to defeat an uncooperative
process running as the same OS user with Vault write permission that deliberately
changes paths between adjacent syscalls or ignores advisory locks. Such an
actor can also modify the Vault directly. Observed interference must still
produce a typed safe failure; tests must not require an impossible timeless
path-identity guarantee.

Alternative directions already considered:

- More sequential pathname revalidation: rejected because it only moves the
  verify/use window.
- A single SQLite/container recovery store: reduces file count but does not
  prevent the database pathname itself from being replaced by the same writer
  and adds migration/operational complexity.

## Resume procedure

1. Read `superpowers:using-superpowers`, `superpowers:brainstorming`,
   `superpowers:writing-plans`, and the primary evidence above.
2. Inspect Git/worktree state; never reset or clean away the WIP branch.
3. Finish the architecture decision before editing production code. Write a
   new spec on a separate design branch/worktree, explicitly superseding the
   Task 4/5 transaction portions of the 2026-07-16 Inbox design.
4. Independently review the threat model, session lifetime, warning/result
   model, crash recovery, locking, platform support, and module split.
5. After the design gate, write an executable TDD plan. Decide explicitly
   whether the implementation should reuse `f5ef1ec` or replace the Task 4
   core from the cleaner `6a0ac41` baseline; do not assume the larger WIP is a
   sound base merely because many tests pass.
6. Create a fresh implementation worktree. Use RED tests first, one cohesive
   implementer for the transaction core, then exact-range spec and quality
   review.
7. Only after Task 4 is accepted may Task 5 implement business mutations in the
   same transaction-session lifetime.
8. Continue Tasks 6–9, then the remaining roadmap branches, using their
   separate risk domains.

Suggested initial commands:

```bash
cd /Users/shaopc/playground/obsidian-kb-skill
git status --short --branch
git worktree list
git log --oneline --decorate --all -20

cd .worktrees/inbox-task4-hardening
git status --short --branch
git show --stat --oneline 5f8d2df
sed -n '1,240p' .superpowers/sdd/task-4-wave-3-architecture-blocker.md
```

## Do not forget

- The current WIP is evidence, not a candidate release.
- A green conventional test suite did not invalidate the architecture probes.
- Task 5 must not recreate the old gap by receiving a prepared pathname after
  all verification descriptors/locks have been released.
- Cleanup/release warnings are part of the public result contract; never
  swallow them to preserve only the primary exception.
- `master` is clean and must remain untouched until the user explicitly chooses
  an integration path.
