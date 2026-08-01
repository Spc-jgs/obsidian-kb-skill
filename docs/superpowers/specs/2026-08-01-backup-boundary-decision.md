# Backup and Recovery Boundary — Decision Record

**Status: accepted.** Records an existing deliberate decision that was never
written down. No code changes with this document.

## Why this document exists

An agent audited the write paths, found that `backup_note()` is called only by
`update_note.py`, found no restore path anywhere, and concluded that backup
coverage was an accidental gap. It proposed extending backups to the note-edit
path and building a restore helper, and wrote a full design and implementation
plan before checking whether the Vault was version controlled.

Both proposals were wrong. The narrow coverage is intentional. The reasoning
existed only in the maintainer's head and in one `.gitignore` comment, so the
audit had no way to reach it.

This document records the decision so the next reader does not repeat the
analysis and reach the same wrong answer. The rejected artifacts are retained
as evidence in `2026-08-01-backup-restore-design.md` and
`../plans/2026-08-01-backup-restore.md`.

## The decision

**Git is the recovery mechanism for notes. The in-Vault backup tree is not, and
must not grow into one.**

A Vault is expected to be a Git repository. The reference Vault has 118 commits,
one per capture, and its `.gitignore` contains:

```gitignore
# Skill-generated backup snapshots (local-only, restored on demand)
.obsidian-kb-backups/
```

Git provides full history, diffs, commit messages, and a remote. Any helper-side
snapshot of an ordinary note duplicates that, and does so worse: no message, no
diff, no history beyond `keep_per_note`, and invisible because the tree is
excluded from search, audit, and index scanning.

## What backups are for

Exactly one thing: **Task Memory**, written through `update_note.py`.

Task Memory is a mutable operational note that changes many times a day. A Git
commit per edit would be noise in a knowledge history whose commits are
meaningful captures. A bounded local snapshot is the right trade there, and only
there.

This is why `backup_note()` has one caller. That is the design, not an
oversight.

## What must not be added

- **No backup on the note-edit path.** Ordinary existing-note edits use native
  file tools by design (`core/OBSIDIAN_KB.md`). Adding snapshots there produces
  a shadow copy of the Vault that nobody reads, to protect content Git already
  protects better.
- **No backup on `create-note`.** It never overwrites; a name clash appends a
  numeric suffix. There is nothing to lose.
- **No backup on `process-inbox`.** It moves a note; the content exists at the
  destination before the source is removed, and `dest.exists()` blocks
  overwrites. Since v1.25.1 an unreadable frontmatter block is refused outright
  rather than rewritten.
- **No restore helper for notes.** `git checkout` and `git log` already do this,
  with better ergonomics and a real audit trail.

## Consequences accepted

`keep_per_note` defaults to `1`, so Task Memory can be rolled back one step.
That is sufficient for an operational scratch note and is not a defect.

Backup trees written by earlier releases may contain generations that no current
writer produces — Vault scaffolding files such as `README.md`, `AGENTS.md`, and
`INDEX.md`. Entries that do not match `STAMP_RE` produce a
`retained unknown backup item` warning from `prune_backups()` on every run. The
warning is correct; the debris is historical and may be removed manually. It is
not evidence of a missing feature.

## If this decision is ever revisited

It would take a Vault that is deliberately not version controlled. In that case
the question is not "add a restore helper" but "what is the recovery story for a
Vault without Git", which is a different design with a different scope. Do not
reopen this by extending `backup_note()` call sites.

## Related

- `docs/capture-and-governance.md` — retention policy and settings
- `obsidian_kb_skill/scripts/backup_policy.py` — `STAMP_RE`, retention, pruning
- `obsidian_kb_skill/scripts/update_note.py:75` — the only backup writer
