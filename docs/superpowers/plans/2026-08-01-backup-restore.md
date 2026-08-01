# Backup Restore Implementation Plan

> **Status: REJECTED — no task in this plan was executed.**
>
> Retained as process evidence. The design it implements was rejected; see
> `docs/superpowers/specs/2026-08-01-backup-restore-design.md` for why, and
> `docs/superpowers/specs/2026-08-01-backup-boundary-decision.md` for the
> decision that replaced it.

Design: `docs/superpowers/specs/2026-08-01-backup-restore-design.md`

## Release Target

Patch or minor on top of v1.25.1. The feature adds a helper and a lazy
reference; it changes no existing write path, so no migration is required.

Delivery rules for this branch follow the standing project convention: never
implement on `master`, work in an isolated worktree, RED tests before
implementation, and run `build.py --check` before any release gate.

## Task 1: Backup discovery domain

Read-only enumeration of the backup tree, with no CLI yet.

- Parse the backup root into generations using `STAMP_RE` as the sole authority.
- Resolve every candidate through `resolve_existing_within_vault`; reject
  symlinks and non-regular files without raising.
- For a given note, return candidates ordered newest first, each carrying stamp,
  size, mtime, SHA-256, and byte-identity against the current note.
- Classify non-conforming entries as `unknown-item` and note-less backups as
  `orphan-backup`.

RED first: a fixture Vault containing two generations of one note, a
non-conforming `LATEST` file, a `.DS_Store`, a symlinked backup entry, and a
legacy generation of scaffolding files.

## Task 2: Listing and audit CLI

- `restore-note <vault> --note <path> --list --json`.
- `restore-note <vault> --audit-json`.
- Both are read-only and must not create the backup root if it is absent.
- An absent backup root is an empty result, not an error.
- Exit `2` with the structured error shape for containment violations, reusing
  `report_cli_violation`.

## Task 3: Preflight

- `--preflight-json` reports current SHA-256, backup SHA-256, predicted outcome
  (`replaced` / `recreated` / `already-current`), and byte delta.
- Writes nothing, creates nothing, and is mutually exclusive with `--apply`,
  matching `create-note`'s argument contract.
- Fails closed on unknown stamp, missing backup, unreadable content.

## Task 4: Apply with self-backup

The core safety task.

- Back up the current version through the existing `backup_note()` before
  writing. If that backup fails, abort without touching the note.
- Write the recovered bytes only after the safety copy exists.
- `already-current` short-circuits: no backup, no write, success.
- Pass the new safety copy to `prune_backups(protected=...)` so retention cannot
  delete it.
- Honour `--expect-backup-sha256`; a mismatch is a fail-closed refusal.
- Surface prune warnings alongside a successful restore; never swallow them.

RED first: restore replaces content, restore recreates a deleted note, identical
content is a no-op, a failing safety backup aborts the restore, and a stale
`--expect-backup-sha256` refuses.

## Task 5: Lazy reference and user documentation

- New `core/references/restore.md` describing list → preview → restore.
- One routing line in `core/OBSIDIAN_KB.md`; no existing reference grows.
- New error codes added to `rules-and-errors.md`.
- `docs/capture-and-governance.md` gains the recovery procedure next to the
  existing retention section, which currently documents only how backups are
  kept and pruned.
- `docs/troubleshooting.md` gains entries for restore refusals and for the
  `retained unknown backup item` warning, which today has no user-facing
  explanation.

## Task 6: Forward evaluation

- `tests/fixtures/backup_restore_eval_cases.json` covering the eight decisions
  listed in the design.
- `tests/test_backup_restore_eval.py` asserting fixture coverage and that every
  decision is reachable from the lazy contract text, in the style of
  `test_web_capture_eval.py`.

## Task 7: Generated artifacts and release gates

- `python build.py` to sync the six platform adapters and both manifests.
- `python build.py --check` must report no drift.
- Full `pytest tests/` green.
- Verify the helper against the real reference Vault read-only paths
  (`--list`, `--audit-json`) before any apply is demonstrated.

## Task 8: Delivery

- PR to `master`, wait for all three CI checks to reach a terminal state.
- Merge, tag, release, and sync the local install across the four integrated
  platforms (qoderwork, claude-code, cursor, workbuddy; codex is not
  integrated on this machine).
