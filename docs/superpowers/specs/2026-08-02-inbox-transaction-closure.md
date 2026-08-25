# Inbox Transaction Work — Closure Record

**Status: closed, not abandoned.** Recorded 2026-08-02.

The accepted design in `2026-07-19-inbox-transaction-capability-session-design.md`
is not being implemented further. Task 1 of 10 is accepted, Task 2 is
implemented without independent review, and Tasks 3–10 will not start unless a
premise below changes.

The branch `fix/inbox-transaction-capability-session` is retained and pushed to
the remote. It carries the full history of all three related branches, so
nothing needs to be reconstructed if this reopens.

## What the work was for

Inbox filing performs three separate steps with no atomicity between them:

```text
1. write the destination file
2. delete the source file
3. append the index entry
```

The design would have added a Vault-level exclusive lock, a recovery journal,
byte-for-byte backups, crash-recoverable records, and a session that holds file
descriptors across the whole prepare → apply → commit lifetime. The session is
the core of it: the previous architecture returned a pathname, and a pathname
can name different content by the time the caller uses it.

## Why it is closed

### 1. The data-loss paths it targeted are closed by other means

The July design listed the problem as "no backup, source hash, atomic commit,
rollback, restore command, or truthful per-item result." Since then, the paths
that actually lost data were closed directly:

| Failure | Closed by |
| --- | --- |
| Malformed frontmatter overwritten with defaults, source deleted | v1.25.1 |
| Destination left behind when source removal fails | v1.25.1 |
| Summary claiming refused notes were applied | v1.25.1 |
| Comments and formatting destroyed on every filing | v1.26.2 |
| Symlinked Inbox entry importing content from outside the Vault | v1.26.2 |

What a crash can still produce, after those fixes:

| Crash point | Result | Recoverable |
| --- | --- | --- |
| During the destination write | partial destination, source intact | yes, visible, re-runnable |
| Between write and source removal | the note exists in two places | yes, annoying, not lossy |
| Between source removal and index append | filed but not indexed | yes, indexes are rebuildable |

None of these lose data. The transaction would convert visible, repairable
inconsistency into no inconsistency — a real improvement, but not the one the
work was started for.

### 2. The design excludes its own main adversary

From the design's threat model:

> No userspace sequence can guarantee permanent pathname identity against an
> uncooperative process running as the same OS user with write access to the
> Vault, deliberately changing paths between adjacent syscalls or ignoring an
> advisory lock. **That actor can also modify the Vault directly.**

The attacker the machinery would defend against does not need to defeat it.

### 3. The Vault is version controlled

The reference Vault is a Git repository with a commit per capture. Every
inconsistency in the table above is visible in `git status` and reversible with
`git checkout`. The journal would rebuild state that Git already holds, with
better ergonomics. See `2026-08-01-backup-boundary-decision.md`, which reaches
the same conclusion for note backups.

### 4. Inbox processing is never unattended

The roadmap states that Inbox processing starts only after an explicit request,
and that scheduled or threshold-based behaviour may produce a read-only
reminder but never a write. Transactional recovery earns most of its value in
unattended runs, which this product does not have.

## What is being given up

`inbox_tx/paths.py` — 991 lines of durable file-descriptor I/O with 841 lines of
tests, re-verified green on 2026-08-01. It is well built. Nothing else in the
project currently needs durable fd operations, so it has no second consumer.

`inbox_plan.py` — 836 lines of immutable planning types on
`fix/inbox-data-safety`. Two of its behaviours were extracted separately in
v1.26.2 (byte-preserving rendering, symlink-safe discovery). The rest exists to
support the superseded Task 4 architecture.

## Reopen if any of these becomes true

1. The Vault stops being version controlled.
2. Inbox processing becomes automated, scheduled, or otherwise unattended.
3. More than one agent processes the same Inbox concurrently.
4. A single run routinely handles hundreds of items, making a partial failure
   expensive to inspect by hand.

Any one of these invalidates the reasoning above. Resume from
`fix/inbox-transaction-capability-session` and the accepted design; do not
restart the analysis.

## Do not

- Do not resume the pre-2026-07-19 pathname-based Task 4 architecture. Three
  independent reviews failed it and three deterministic probes closed it. See
  `docs/superpowers/sdd/inbox-task4-hardening/task-4-wave-3-architecture-blocker.md`,
  and note the errata in `docs/superpowers/sdd/README.md`: the probe tests it
  cites were never committed and must be rewritten.
- Do not integrate `inbox_plan.py` wholesale to obtain the two behaviours
  already shipped in v1.26.2.

## Re-checked 2026-08-25

Twenty-three days on, during a branch sweep that came close to deleting these
branches for looking abandoned. They are not abandoned; this file says so, and
reading it is what stopped the deletion. Recorded here so the next sweep finds
the measurement rather than repeating it.

All four reopen conditions were tested. **None holds.**

| # | Condition | Measured |
|---|---|---|
| 1 | The Vault stops being version controlled | still a git repository, 159 commits |
| 2 | Inbox processing becomes unattended | no scheduled or threshold write path; `process-inbox.md` still reads "human watching the run" |
| 3 | More than one agent processes the same Inbox | no concurrent path; single-user CLI |
| 4 | A run routinely handles hundreds of items | the Inbox holds **5** |

The branch survived the sweep with its history intact: `fix/inbox-transaction-capability-session`
carries all 28 patches, local and remote at the same SHA. The two branches that
were deleted — `design/inbox-transaction-capability-session` and
`fix/inbox-data-safety` — were verified by `git merge-base --is-ancestor` to be
strict ancestors of it, so nothing this file promises to preserve was lost.
Their worktrees were removed after confirming zero uncommitted changes.

Deleting the surviving branch was considered and rejected: it costs one remote
ref, and this file's own instruction — "Resume from
`fix/inbox-transaction-capability-session`" — would become a dangling pointer.
Tidiness is not a reason to invalidate a record.
