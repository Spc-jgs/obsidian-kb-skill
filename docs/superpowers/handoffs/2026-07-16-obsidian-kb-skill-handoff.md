# Obsidian KB Skill Evolution Handoff

> **2026-07-19 update:** The Task 4 repair reached an architecture stop after
> this handoff was written. For the current Task 4 state and exact resume
> procedure, read
> `2026-07-19-inbox-transaction-architecture-handoff.md`. The roadmap and
> accepted Tasks 1–3 history below remain valid; the old “one fix wave next”
> instruction does not.

**Written:** 2026-07-16, Asia/Shanghai
**Last updated:** 2026-07-19, Asia/Shanghai
**Reason:** Context/token budget is low. Work was intentionally stopped at a
safe task boundary. Do not reconstruct state from conversation memory; use this
document, Git, and `.superpowers/sdd/progress.md`.

## User Goal and Standing Authorization

Continuously improve `obsidian-kb-skill`: project/code structure, robustness,
maintainability, README, features, knowledge templates, Inbox integration,
Skill reasonableness, and token use. The user explicitly authorized multiple
Agents and autonomous scoped decisions.

Binding delivery rules:

- never implement on `master`;
- use separate branches/worktrees for independent risk domains;
- high-risk changes must be reversible and independently reviewable;
- preserve unrelated/user changes;
- use TDD, independent task review, full verification, and reversible commits;
- do not merge or push unless the user changes the standing instruction;
- continue from the latest accepted clean base, not from memory.

The existing Goal objective is the long-running optimization objective. It was
created earlier under thread ID `019f6aa1-7579-71b3-9585-126c6b9d0c9b` and the
Goal service still displayed an old `blocked` status from a superseded design
gate. The user subsequently approved the design and resumed work. Do not create
a duplicate Goal; continue the existing objective unless the product allows a
proper resume/status transition.

## Repository and Worktrees

Repository:

```text
/Users/shaopc/playground/obsidian-kb-skill
```

Worktrees at handoff:

```text
master
  /Users/shaopc/playground/obsidian-kb-skill
  8785da8

design/skill-evolution-roadmap
  /Users/shaopc/playground/obsidian-kb-skill/.worktrees/skill-evolution-roadmap
  7fb770b

fix/shared-note-domain                 ACCEPTED / FROZEN
  /Users/shaopc/playground/obsidian-kb-skill/.worktrees/shared-note-domain
  8132365

fix/inbox-data-safety                 ACTIVE
  /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-data-safety
  implementation HEAD before this handoff document: 6a0ac41
```

`master` remained untouched and clean at `8785da8`. No branch was pushed or
merged. GitHub CLI authentication was not relied on.

## Accepted Roadmap

Read these first:

- `docs/superpowers/specs/2026-07-16-skill-evolution-roadmap-design.md`
- `docs/superpowers/plans/2026-07-16-shared-note-domain.md`
- `docs/superpowers/specs/2026-07-16-inbox-data-safety-design.md`
- `docs/superpowers/plans/2026-07-16-inbox-data-safety.md`

The roadmap has 13 risk-separated branches. Only branch 1 is accepted; branch
2 is active:

1. `fix/shared-note-domain` — accepted at `8132365`.
2. `fix/inbox-data-safety` — active; Tasks 1–3 accepted, Task 4 implemented and
   independently reviewed, but review requested changes.
3. `fix/self-contained-primary-references`.
4. `feat/inbox-lifecycle`.
5. `feat/knowledge-templates-v2`.
6. `feat/template-safe-migration`.
7. `test/runtime-token-budgets`.
8. `docs/readme-information-architecture`.
9. `eval/current-forward-matrix`.
10. `refactor/audit-snapshot-engine`.
11. `refactor/create-note-pipeline`.
12. `fix/build-graph-hardening`.
13. `refactor/transactional-installer-core`.

Do not pull Inbox lifecycle features into the active data-safety branch. The
ten-item limit, reviewed plan files, public plan/item IDs, confidence/evidence,
`inbox-note`, enrichment, and Skill routing belong to branch 4.

## Completed and Accepted Work

### `fix/shared-note-domain`

Accepted HEAD: `8132365`. Independent final review: Ready to merge Yes.
Verification at acceptance: 504 tests passed, build check passed, packaging
subset 44 passed. The worktree and branch are deliberately preserved.

Major outcomes:

- canonical note catalog and migrated consumers;
- shared frontmatter result/issue parser with compatibility adapters;
- public Folder Index/static-index policy;
- Vault-contained Folder Index filenames and stable CLI error boundaries;
- scaffold templates derived from the catalog;
- generated standard Skill payload synchronized at that accepted point.

### `fix/inbox-data-safety` Tasks 1–3

All three passed both spec-compliance and code-quality review.

Task 1 — strict source snapshots:

```text
4049ccf fix: fail closed on unsafe inbox sources
36e09a8 fix: bind inbox reads to verified file descriptors
```

- rejects malformed/unclosed/nonmapping YAML, bad UTF-8, symlinks and
  non-regular files;
- raw-byte hashes and identity snapshots;
- `O_NOFOLLOW` when available plus same-fd `fstat`/read binding;
- Reviewer: spec PASS, quality APPROVED.

Task 2 — byte-preserving typed plans:

```text
e7c3bad refactor: model immutable inbox plans
a572cfc fix: fail closed on unsafe inbox plans
fde3337 fix: reject duplicate keys in inbox rendering
```

- frozen plan/proposal/item types;
- preserves BOM, CRLF/LF, comments, quoting, body and trailing-newline bytes;
- blocks ambiguous empty required metadata and recursive duplicate YAML keys;
- target/destination planning race checks;
- Reviewer: spec PASS, quality APPROVED.
- Retained Minor: alias-based duplicate-key line/column may point to the YAML
  anchor definition. The duplicate is still blocked; do not expand scope solely
  for diagnostic coordinates unless a later reviewer raises it materially.

Task 3 — pure static-index plan:

```text
d1eb034 refactor: plan inbox index updates without writes
604b64a fix: normalize unsafe index filename encoding
```

- frozen exact before/after bytes and hashes;
- ready Inbox proposals always carry non-optional `StaticIndexPlan`;
- strict pure config path, while legacy append consumer remains compatible;
- logical wikilink and physical symlink-contained path remain separate;
- Reviewer: spec PASS, quality APPROVED.

## Current Stop Point: Task 4 Review Failed, Fix Wave Pending

Implementation commit:

```text
6a0ac41 feat: add inbox transaction recovery store
```

Task 4 is **not accepted yet**. A fresh read-only Reviewer assessed the exact
range `604b64a..6a0ac41` and returned:

```text
Spec compliance: FAIL
Code quality: CHANGES_REQUESTED
Task 4 accepted: NO
```

Do not start Task 5 until one complete fix wave addresses the findings below,
new RED-then-GREEN regressions are recorded, and the same exact Task 4 content
receives both:

```text
Spec compliance: PASS
Code quality: APPROVED
```

Implementation scope is exactly:

- `obsidian_kb_skill/scripts/inbox_transaction.py`
- `obsidian_kb_skill/scripts/backup_policy.py`
- `tests/test_inbox_transaction.py`
- `tests/test_backup_policy.py`

Reported evidence:

- focused: 53 passed;
- required preparation/path regression: 87 passed;
- full suite excluding the deferred generated-tree check: passed;
- exact backup hash/bytes, manifest, fsync journal, sorted source/index locks,
  stable lock owner, nine failure checkpoints, symlink/broken backup roots, and
  exact `inbox/` retention namespace are covered;
- self-review found and fixed backup-symlink verification and lock-replacement
  cleanup attacks;
- Task 4 changes no business source/destination/index file.

Full ignored implementation report:

```text
.superpowers/sdd/task-4-report.md
```

### Independent Review Findings

Critical:

1. A source replaced by a different inode with identical bytes is accepted.
   The verified fd identity is not compared with the planned `item.identity`.
2. The exclusively created operation root can be replaced by a Vault-contained
   symlink; subsequent manifest/journal writes re-resolve the pathname and can
   be redirected. Bind all transaction work to the originally created root,
   preferably with fd-relative operations and stored identity.

Important:

1. Failure cleanup deletes an unknown regular file that replaces an owned
   backup. Record creation identity and delete only the exact owned object.
2. A lock write/flush/fsync failure leaves an orphan lock because ownership is
   registered only after `_acquire_lock` returns. Acquisition must clean up its
   own partially created lock without deleting a replacement.
3. Lock identity capture and release contain TOCTOU windows: capture identity
   with `fstat` on the creation fd, and redesign release so a replacement
   between verification and removal is preserved.
4. Backup verification protects only the final component with `O_NOFOLLOW`;
   an ancestor can be swapped to a symlink. Traverse every component safely
   with directory fds and fail closed where the required primitives are absent.
5. Files are fsynced but parent directories are not. Add directory durability
   checkpoints after directory creation/new entries and surface a truthful
   warning or failure on unsupported platforms as required by the spec.

Minor follow-ups to include if they fit the same wave:

- test two different sources sharing one index, so the index lock itself is
  proven to serialize operations;
- preserve/report cleanup and release warnings on the exception path instead
  of silently discarding them.

The Reviewer also confirmed that the implementation scope was otherwise exact,
normal behavior did not mutate business files, retention handled the exact
`inbox/` namespace, and the ordinary manifest/journal/hash behavior was sound.

### Exact Next Action

Use `superpowers:systematic-debugging` and `superpowers:test-driven-development`.
Send the **complete** finding list above to one fixer; do not split this tightly
coupled safety repair across Agents. Require deterministic exploit tests to fail
before implementation and pass afterward. Append evidence to:

```text
.superpowers/sdd/task-4-report.md
```

There is one review-range wrinkle: tracked handoff commit `f61c226` follows the
Task 4 implementation even though it is controller documentation, not Task 4.
For the cleanest exact re-review, create a temporary repair branch/worktree at
`6a0ac41`, make the single Task 4 fix commit there, and review
`604b64a..<repair-head>`. After approval, cherry-pick only that accepted fix
commit onto `fix/inbox-data-safety`; keep the temporary branch until the
cherry-pick and active-worktree regression pass. Never base it on or merge it
into `master`.

Give the re-reviewer:

- `.superpowers/sdd/task-4-brief.md`;
- the updated `.superpowers/sdd/task-4-report.md`;
- a newly generated exact review package;
- the Inbox safety spec transaction/backup/lock sections;
- the prior Critical/Important findings above, requiring explicit disposition
  of every item.

## Known Red Gate: Generated Payload Drift

`build.py --check` currently fails because canonical Python from Tasks 1–4 has
not yet been copied into the standard Skill runtime and manifest. This was
intentional task scoping, not a hidden regression. The one known full-suite
failure is:

```text
tests/test_lazy_references.py::test_build_check_still_passes
```

The implementation plan assigns distribution synchronization to Task 8. Do not
claim the whole branch is green before Task 8 runs:

```bash
uv run --locked --extra dev python build.py
uv run --locked --extra dev python build.py --check
```

If an earlier task reviewer requires generated sync per the repository's global
gate, resolve that explicitly and record why; do not silently expand a task's
review range.

## Remaining Inbox Safety Tasks

Follow `docs/superpowers/plans/2026-07-16-inbox-data-safety.md` exactly:

- Task 5: transactional destination/index install, audit, source removal last,
  hash-guarded rollback.
- Task 6: restore preview/apply and crash-phase recovery.
- Task 7: CLI compatibility, truthful per-item results and exit codes.
- Task 8: narrow safety documentation and distribution synchronization.
- Task 9: full build/test/package/hostile-CWD verification and broad independent
  branch review.

Use one implementer at a time. After each task, generate a review package using
the recorded pre-task base (never `HEAD~1`) and require both reviewer verdicts.

## Skills and Process to Resume

At resume, read and use:

- `superpowers:using-superpowers`
- `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging` for any failure/finding
- `superpowers:requesting-code-review`
- `superpowers:verification-before-completion`
- `superpowers:finishing-a-development-branch` only after branch completion

The design and implementation-plan gates are already complete for this branch;
do not redo brainstorming or rewrite the plan unless evidence proves the spec is
wrong. Trust Git and `.superpowers/sdd/progress.md` across context compaction.

## Safety Checks Before Resuming

```bash
cd /Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-data-safety
git branch --show-current
git status --short
git log --oneline -12
git worktree list
```

Expected branch: `fix/inbox-data-safety`. The worktree should be clean after the
handoff-document commit. Never run destructive reset/checkout/clean commands.

## Final State Summary

- `master`: untouched at `8785da8`.
- Shared-domain branch: accepted and frozen at `8132365`.
- Inbox safety design and plan: committed and authoritative.
- Inbox safety Tasks 1–3: accepted.
- Task 4: implementation committed at `6a0ac41`; independent review failed with
  two Critical and five Important findings; one integrated TDD fix wave is next.
- Tasks 5–9: not started.
- No push or merge performed.
- Next move is the Task 4 safety fix wave and re-review, not Task 5.
