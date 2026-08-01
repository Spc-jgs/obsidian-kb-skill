# Obsidian KB Skill — Inbox Transaction Task 2 Review Handoff

**Written:** 2026-07-19, Asia/Shanghai

**Status:** safe pause after Task 2 implementation review; Goal remains active;
Task 1 is accepted; Task 2 is implemented but **not accepted**

**Authoritative for:** the current implementation branch, exact accepted work,
Task 2 review findings and their adjudication, and the next resume sequence

This document supersedes the implementation-start instructions in
`2026-07-19-inbox-transaction-plan-review-handoff.md`. That earlier handoff
remains authoritative for the accepted specification and plan history.

## Non-negotiable delivery rules

- Never implement, merge, or commit on `master`.
- Continue only in the isolated implementation worktree and preserve small,
  reversible commits.
- Do not merge or push unless the user changes the standing instruction.
- Use RED → GREEN → refactor, then exact-range independent review, for every
  implementation task.
- Do not start Task 3 until Task 2 is repaired and independently accepted.
- Do not mark the Goal complete. README, templates, Inbox product integration,
  Skill/token optimization, and Tasks 2–10 remain unfinished.

## Goal state

The existing Goal is deliberately still active:

```text
thread: 019f6aa1-7579-71b3-9585-126c6b9d0c9b
status: active
objective: continuously improve project/code structure, robustness, README,
           templates, Inbox integration, Skill reasonableness, and token use
```

The user requested a token-budget checkpoint and durable handoff. This is a
safe pause, not completion and not a blocker.

## Exact repository state before this handoff commit

```text
master
  path:   /Users/shaopc/playground/obsidian-kb-skill
  commit: 8785da8f98a7f111ed68b8964418c0c63658ba2a
  rule:   untouched; never work here

implementation
  path:   /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-transaction-capability-session
  branch: fix/inbox-transaction-capability-session
  HEAD:   792c02396f8c4efa0cea71e63b2c20129eda8fef
  state:  clean before adding this handoff

immutable bases recorded in ignored .superpowers/sdd/progress.md
  Implementation base: e3d96b3a5f0bc4db016ffe9f25ca266f182545e1
  Master base:         8785da8f98a7f111ed68b8964418c0c63658ba2a
```

`.superpowers/` is excluded only through the repository-local
`.git/info/exclude`; the exclusion did not modify a tracked branch file.

No merge or push has occurred. Earlier read-only checks established that
`gh auth status` succeeds for `Spc-jgs`, `origin` uses HTTPS, and the credential
reports `repo` scope. No remote write was attempted.

## Accepted implementation work

### Task 1 — runtime models: complete

```text
9751447 docs: make inbox model task self-contained
d0d4284 refactor: define inbox transaction runtime models
review: spec compliant; quality approved; 0 Critical / 0 Important / 0 Minor
```

Files:

```text
obsidian_kb_skill/scripts/inbox_tx/__init__.py
obsidian_kb_skill/scripts/inbox_tx/models.py
tests/test_inbox_tx_models.py
```

Evidence is in ignored `.superpowers/sdd/task-1-report.md`.

### Task 2 — bound paths and capability probes: pending

Plan-contract commits:

```text
06a8584 docs: define inbox path capability contracts
6361e64 docs: preserve path compatibility contracts
```

Those contract changes received two independent READY verdicts. The production
implementation is:

```text
792c023 fix: bind inbox transaction paths to descriptors
```

Files:

```text
obsidian_kb_skill/scripts/inbox_tx/paths.py
tests/test_inbox_tx_paths.py
```

Verified implementation evidence:

```text
focused Task 2 tests: 55 passed
specified shared regressions: 97 passed
compileall: passed
host exercised: macOS, CPython 3.14.6
Windows/Linux branches: fault-injection coverage only
```

The extra full-suite run stopped after 553 passes because the generated payload
tree is out of sync. Task 9 owns generated packaging synchronization; do not
silently edit generated files during the Task 2 repair.

Task 2's independent formal review returned **Needs fixes**. Therefore commit
`792c023` must not be described as accepted, and Task 3 must not begin.

Evidence files:

```text
.superpowers/sdd/task-2-brief.md
.superpowers/sdd/task-2-report.md
.superpowers/sdd/task-2-review-package.md
review base: 6361e64d8a785c975ea4655a59fd592d92de9ab4
review head: 792c02396f8c4efa0cea71e63b2c20129eda8fef
```

## Task 2 review adjudication

Do not apply the review mechanically. Some findings are real implementation
defects; two findings expose wording that overpromises beyond the already
accepted threat model.

### Real defects to repair with RED tests

1. `link_no_overwrite_at()` may create the destination and then fail its
   post-link identity check while reporting
   `business_mutation_started=False`. Once `os.link()` succeeds, subsequent
   failures must truthfully expose that business mutation has started so Task 6
   can fsync/classify/recover the destination.
2. `LocalMutationCapabilityProbe` must reject non-CPython runtimes explicitly,
   not merely check `sys.version_info`.
3. fd-owning factories have incomplete cleanup and error normalization:
   `RuntimeError`/other post-open exceptions can leak descriptors,
   `ensure_directory()` leaves `os.dup()` outside normalized handling, and
   retrying a descriptor after a failing `close()` can double-close a reused fd.
   Consolidate ownership with one helper or `ExitStack`; test exactly-once
   ownership transfer and every exceptional exit.
4. `revalidate_public_chain()` must normalize missing, symlink, and non-directory
   replacements of an already-bound component to `inbox-path-changed`.

### Findings that require contract clarification before code repair

The reviewer produced deterministic hooks between the final check and
`unlink`/`replace`, and between `mkdir` and reopening the new directory. Those
hooks model a malicious same-OS-user process deliberately racing adjacent
syscalls. The accepted specification explicitly excludes that actor: POSIX and
macOS do not provide a portable atomic “compare inode/hash and unlink/replace”
or “mkdir and bind this exact inode” operation through this stdlib contract.

Do not add a fake check that claims to close this window. First amend the
authoritative Task 2 plan contract to say:

- helpers provide immediate identity/hash prechecks plus post-observation under
  the cooperative persistent lock;
- a mismatch observed before mutation preserves the mismatching object;
- the API does not claim atomic compare-and-mutate against an uncooperative
  same-user process racing adjacent syscalls;
- a post-observed mismatch becomes a typed path-change/recovery condition, but
  cannot promise restoration of an unknown object already raced;
- directory creation binds the public entry opened immediately after durable
  `mkdir`; it does not claim atomic mkdir-and-open-by-inode against that excluded
  actor.

The same clarification must retain the specification's honest local-filesystem
boundary. Primitive probes cannot reliably certify all network mount topology
with portable Python stdlib calls. Add the unequivocal CPython gate; do not let
`supported=True` claim more than the probed primitives and documented local-FS
precondition. If a trustworthy platform locality signal is introduced, keep it
injectable and fail closed when it positively identifies a non-local mount.

The review also objected that public-chain revalidation reopens `self.root`.
Reopening the canonical public Vault root is required to detect replacement of
that public binding. Clarify that this one reopen compares the root identity;
afterward descendant traversal is exclusively descriptor-relative. Do not
switch solely to the old bound root fd, which would make public root replacement
invisible.

## Exact next resume sequence

1. Enter the implementation worktree and verify branch, HEAD, and cleanliness:

   ```bash
   cd /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-transaction-capability-session
   git status --short --branch
   git log -8 --oneline
   ```

2. Read this handoff, the accepted specification, the current plan's Task 2,
   `.superpowers/sdd/task-2-report.md`, and the formal review verdict.
3. Amend only the authoritative Task 2 plan/brief wording described above.
   Commit the docs-only contract repair and obtain two independent exact-HEAD
   READY reviews before changing production code.
4. Regenerate `.superpowers/sdd/task-2-brief.md` from the reviewed contract.
5. Dispatch one fresh Task 2 repair implementer. Require RED tests first for the
   four real defect groups, then the smallest coherent refactor. Append exact
   RED/GREEN commands and results to `.superpowers/sdd/task-2-report.md`.
6. Run the focused tests, specified shared regressions, and compileall. Do not
   treat the known generated-tree drift as a Task 2 regression.
7. Regenerate the exact review package from base `6361e64` through the new HEAD
   so the reviewer sees the original implementation, contract repair, and code
   repair together.
8. Obtain independent spec-compliance and quality approval with no Critical or
   Important findings. Only then update `.superpowers/sdd/progress.md` from
   `Task 2: pending` to complete and begin Task 3.

## Resume checklist

```text
[x] Goal remains active
[x] master remains untouched at 8785da8
[x] implementation/master bases recorded immutably
[x] Task 1 independently accepted
[x] Task 2 RED/GREEN implementation and regression evidence recorded
[x] Task 2 formal review completed
[ ] Task 2 threat-boundary wording repaired and dual-reviewed
[ ] Task 2 real defects repaired with new RED tests
[ ] repaired exact range independently accepted
[ ] Task 2 ledger marked complete
[ ] Tasks 3–10 executed
[ ] Windows exact-HEAD evidence obtained or honestly left pending
[ ] broader README/template/Inbox/token roadmap completed
```

## Final warning

The most dangerous resume error is to see passing tests at `792c023` and start
Task 3. Do not. Task 2 remains pending until the contract is made honest, the
real implementation defects are fixed, and the entire repaired range receives
an independent clean review.
