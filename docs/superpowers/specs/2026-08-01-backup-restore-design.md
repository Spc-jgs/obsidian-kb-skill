# Backup Restore Design

> **Status: REJECTED — not implemented. Retained as process evidence.**
>
> This design was written before checking whether the Vault is version
> controlled. It is not built and should not be built as specified.
>
> The reference Vault is a Git repository with 118 commits, one per capture,
> and `.gitignore` excludes `.obsidian-kb-backups/`. Git is therefore already
> the recovery mechanism for ordinary note edits, with full history, diffs, and
> messages. A restore helper for notes duplicates a mechanism that already
> works better, and the narrow backup coverage this document treats as a defect
> is a deliberate decision: backups exist only for high-churn Task Memory, where
> per-version Git history would be noise.
>
> The accepted decision is recorded in
> `2026-08-01-backup-boundary-decision.md`. Read that first.

## Goal

Make the existing in-Vault backup tree usable. Backups are written today and
pruned today, but nothing can read them back. A user who says "undo that
update" has no supported path, and the Skill's own rule that an Agent never
enumerates or deletes backup files leaves manual recovery explicitly off the
table.

This design closes the loop for backups that already exist. It does not add new
backup triggers, does not change retention, and does not make any existing
write path transactional.

## Evidence

`update_note.backup_note()` (`obsidian_kb_skill/scripts/update_note.py:75`)
copies a note byte-for-byte into `.obsidian-kb-backups/<stamp>/<relative>` before
a Task Memory write. `backup_policy.prune_backups()` applies per-note retention
and deletes surplus copies. A search across `obsidian_kb_skill/scripts/` and
`core/references/` returns no `restore` symbol, no restore CLI, and no reference
section describing recovery.

`docs/capture-and-governance.md:194` documents the retention policy and the
`backup.keep_per_note` setting. It never states how a note is recovered.

The reference Vault at `~/Documents/my-knowledge-base` shows what a real tree
looks like after several releases:

```text
.obsidian-kb-backups/
├── 2026-07-07-220821/   75 files — README.md, .gitignore, AGENTS.md, INDEX.md
├── 2026-07-08-110238/   21 files — README.md, AGENTS.md, CLAUDE.md, INDEX.md
├── 2026-07-28-141212/    1 file  — 20-Learning/Java/<article>.md
├── LATEST                18 bytes, referenced by no current code
└── .DS_Store
```

Three facts follow from this tree and matter for the design.

First, the tree holds **heterogeneous generations**. The 2026-07-07 and
2026-07-08 generations contain Vault scaffolding files, not notes. No current
writer produces them; `update_note.py` is the only module that writes into the
backup root, and the other four modules that name `.obsidian-kb-backups` merely
exclude it from scanning. These are legacy artifacts that a restore feature will
encounter and must describe honestly rather than present as recoverable notes.

Second, `LATEST` and `.DS_Store` do not match `STAMP_RE`
(`backup_policy.py:28`), so every prune run on this Vault emits
`retained unknown backup item` (`backup_policy.py:186`). The warning is correct
and there is currently no command that helps the user act on it.

Third, retention groups candidates by the note path relative to the stamp
directory. Scaffolding backups and note backups therefore share one retention
pool, and `keep_per_note` defaults to `1`.

## Product Model

Restore is a **write** and obeys every existing write rule: explicit user
intent, preview before mutation, Vault containment, never overwrite silently.

Three operations, each separately useful:

| Operation | Writes | Answers |
| --- | --- | --- |
| list | no | which backups exist for this note, and how they differ from it |
| restore | yes | put this note back to a chosen backup |
| audit | no | what is in the backup tree that the current contract does not recognize |

Listing and audit are read-only and may run whenever the user asks about
recovery. Restore requires the same explicit intent as any other Vault write.

### Restore Is Itself Reversible

Restoring overwrites the current content, which is a destructive act. Restore
therefore backs up the current version first, through the existing
`backup_note()`, before writing the recovered bytes. A user who restores the
wrong generation can restore again. Without this, restore would be the one write
path in the Skill with no undo — the exact defect this design exists to fix.

The freshly written backup is passed to `prune_backups(protected=...)` so
retention cannot delete the safety copy the operation just created.

### Outcomes Are Named, Not Inferred

Restore reports which of three things happened:

| Outcome | Condition |
| --- | --- |
| `replaced` | the note existed and its bytes changed |
| `recreated` | the note did not exist and was written from the backup |
| `already-current` | the note exists and is byte-identical to the backup |

`already-current` writes nothing and creates no backup. It is a success, not a
failure, and must not be reported as a restore.

## Selection Contract

A backup is addressed by note path plus stamp. The stamp is the directory name
and `STAMP_RE` is authoritative — a directory that does not match is not a
generation and can never be a restore source.

The Agent does not guess a stamp. It lists first, shows the user the candidates,
and restores the one the user chooses. When the user says "the last one", the
Agent may select the newest conforming generation that actually contains the
note, and must name the chosen stamp in its reply.

Listing reports, per candidate: stamp, size in bytes, modification time,
SHA-256, and whether the content is identical to the note's current bytes.
Identity is computed from bytes, not from parsed frontmatter, so a backup that
differs only in YAML key order is correctly reported as different.

## Failure and Write Boundary

Every failure is fail-closed and leaves the Vault unchanged:

- unknown or non-conforming stamp;
- stamp exists but holds no backup for the requested note;
- backup entry is a symlink, a directory, or not a regular file;
- backup or note path escapes the Vault after resolution;
- backup content cannot be read;
- the pre-restore backup of the current version cannot be written.

The last item is the important one: if the safety copy fails, the restore does
not proceed. Losing the current version to recover an older one would reproduce
the defect in the opposite direction.

Containment reuses `resolve_existing_within_vault` and
`resolve_target_within_vault` from `vault_paths`. No new path logic is
introduced, and no operation follows a symlink out of the Vault.

Cleanup and release warnings are part of the result, never swallowed. A restore
that succeeded but whose retention prune emitted warnings reports both.

## Audit Contract

`--audit-json` classifies the whole backup root without writing:

| Class | Meaning | Example from the reference Vault |
| --- | --- | --- |
| `generation` | directory matching `STAMP_RE` | `2026-07-28-141212` |
| `unknown-item` | entry the retention contract cannot classify | `LATEST`, `.DS_Store` |
| `orphan-backup` | backup whose note no longer exists in the Vault | `2026-07-07-220821/AGENTS.md` |

Audit **reports and never deletes**. Deletion remains policy-driven inside
`prune_backups`, preserving the standing rule that an Agent does not remove
backup files. The value of audit is that the `retained unknown backup item`
warning becomes explicable: the user learns what the entry is and can remove it
themselves.

## Deterministic Helper Contract

One new helper, `restore-note`, invoked through `run_helper.py` like every other
helper. It follows the established preflight/apply shape rather than inventing
one:

```text
restore-note <vault> --note <path> --list --json
restore-note <vault> --note <path> --from <stamp> --preflight-json
restore-note <vault> --note <path> --from <stamp> --apply --compact-json
restore-note <vault> --audit-json
```

`--preflight-json` and `--apply` are mutually exclusive, matching `create-note`.
Preflight reports the current SHA-256, the backup SHA-256, the predicted
outcome, and the byte delta; it writes nothing.

Apply accepts `--expect-backup-sha256`, binding the write to the exact content
the preflight showed. This closes the same preview/write gap that
`create-note` already closes for deep captures via
`--expect-capture-receipt-sha256`, rather than leaving the preview advisory.

Exit codes follow the existing convention: `0` success including
`already-current`, `2` for input and containment violations. Structured errors
reuse the established `{"error": {"code", "message", ...}}` shape.

## Progressive Disclosure

Restore is a recovery path, not part of ordinary capture. It must not cost
tokens on every save.

`core/OBSIDIAN_KB.md` gains one routing line only. A new
`core/references/restore.md` holds the workflow and loads only when the user
asks to undo, revert, or recover. No existing reference grows, and
`note-creation.md` is untouched.

`rules-and-errors.md` gains the new error codes, because that file is where an
Agent looks when a helper refuses.

## Forward Evaluation

Fixtures under `tests/fixtures/backup_restore_eval_cases.json` cover the
decisions this contract makes, in the tool-neutral style already used by the
capture and retrieval fixtures:

- multiple generations for one note, newest correctly identified;
- a backup byte-identical to the current note (`already-current`);
- a note deleted from the Vault (`recreated`);
- a stamp that does not match `STAMP_RE`;
- a stamp with no backup for the requested note;
- `LATEST` and `.DS_Store` classified as `unknown-item`;
- a legacy generation of scaffolding files classified as `orphan-backup`;
- a symlinked backup entry rejected without writing.

As with the existing eval sets, these assert that every decision is reachable
from the lazy contract text, keeping the reference doc and the helper honest
about each other.

## Compatibility and Non-Goals

Compatible by construction: no change to `backup_note()`, to the on-disk layout,
to `STAMP_RE`, to retention, or to any existing helper's output. Existing
backups written by earlier releases are readable, including the legacy
generations, which audit describes rather than hides.

Explicit non-goals:

- **No new backup triggers.** `create-note` and `process-inbox` still do not
  back up. Adding that changes write behavior and belongs to the stalled Inbox
  transaction work, not here.
- **No transactional guarantee.** Restore is a single-file operation. It does
  not make any multi-step flow atomic.
- **No bulk or whole-generation restore.** One note per invocation, so every
  recovery stays previewable and reversible.
- **No backup deletion.** Audit reports; retention deletes; the Agent does
  neither by hand.
