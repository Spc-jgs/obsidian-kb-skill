# Archived SDD Evidence — Inbox Transaction Work

Archived 2026-08-01. These 31 documents were previously untracked.

## Why they are here

`.superpowers/` is excluded by `.git/info/exclude`, a machine-local rule that
does not travel with the repository. Every task brief, implementation report,
review package, handoff, and the architecture blocker for the Inbox transaction
effort therefore existed only inside three working directories on one machine,
in no commit and on no remote. `git log --all -- '**/task-4-wave-3-architecture-blocker.md'`
returned nothing.

That document is the reason the effort stopped. Losing it would mean the next
attempt reruns three patch waves and three failed independent reviews to
rediscover the same architectural conclusion.

## What is archived

| Directory | Source branch | Documents |
| --- | --- | --- |
| `inbox-data-safety/` | `fix/inbox-data-safety` | 13 |
| `inbox-task4-hardening/` | `fix/inbox-task4-hardening`, `wip/inbox-task4-wave3-architecture` | 11 |
| `inbox-transaction-capability-session/` | `fix/inbox-transaction-capability-session` | 7 |

Start with `inbox-task4-hardening/task-4-wave-3-architecture-blocker.md`. It
records three deterministic probes showing that the prepared-path model cannot
be repaired by another local patch, which is why a fourth wave is forbidden
without a new design.

### Errata: the probe tests it cites do not exist

That document gives three commands of the form
`pytest tests/test_inbox_transaction.py::test_probe_... -q`. **None of those
tests were ever committed.** Searching every branch and every working directory
for `probe` in `tests/test_inbox_transaction.py` returns nothing, so the
commands cannot be run as written. The probes were evidently written, executed,
and discarded before the WIP commit.

This does not weaken the conclusion. The document describes each race in enough
prose detail to be re-derived, and three independent reviews reached the same
verdict from separate evidence. But anyone resuming this work should expect to
**rewrite the probes** rather than run them, and should treat the reproduction
commands as a description of what to build, not as a working recipe.

The original text is archived unmodified; this note is the correction.

## Status of the work these describe

None of it is merged. As of this archive:

- `fix/inbox-data-safety` — Tasks 1–3 accepted; Task 4 independent review FAIL.
- `fix/inbox-task4-hardening` — repair waves 1 and 2; both re-reviews FAIL.
- `wip/inbox-task4-wave3-architecture` — explicitly non-accepted evidence only.
  Do not cherry-pick it.
- `fix/inbox-transaction-capability-session` — redesign; Task 1 accepted, Task 2
  implemented but not independently reviewed.

The branches themselves carry the code, plans, and specs. They are local to one
machine and are not on the remote.

## These are copies, not moves

The originals remain at `.superpowers/sdd/` inside each worktree because the
recorded resume procedure references those paths directly. The originals stay
the live working state; this directory is the durable record as of the archive
date. If work resumes and the originals change, re-archive rather than editing
these copies.

One correction was applied to the originals before archiving: the
capability-session `progress.md` recorded `Task 2: pending` while its own
`task-2-report.md` held a complete self-report. It now records "implemented, not
accepted" with the commit range and the open review gap.
