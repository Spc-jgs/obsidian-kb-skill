# Bounded Backup Retention and v1.11.1 Release Design

## Goal

Bound the disk usage of write-before backups without giving an AI agent any
cleanup decisions or deletion commands. Every successful `update-note` write
must leave at most the configured number of backups per note, with a safe
default of one. Complete the change as v1.11.1, pass repeated local and remote
release gates with no P0 issue, then synchronize and verify the local Codex
Skill installation.

## Scope

This release includes:

- a global, user-owned backup retention setting;
- deterministic cleanup inside the Python runtime after a successful write;
- Bash and PowerShell configuration lifecycle parity;
- safety, installed-product, wheel, and cross-platform tests;
- v1.11.1 metadata, documentation, release, and local Codex synchronization.

This release does not add an AI-facing cleanup helper, scheduled background
task, backup restore workflow, or unrelated refactor. Atomic note replacement,
JSON-envelope unification, an installation doctor, and `audit_vault.py`
decomposition remain separately scoped improvements.

## Approaches Considered

### 1. In-process post-write retention module — selected

`update_note.py` calls a focused `backup_policy.py` module after the note write
succeeds. The module reads global settings, scans and groups backup files, and
deletes only excess product-owned backups. The agent's command and prompt stay
unchanged, so cleanup costs no AI reasoning or directory-listing tokens.

### 2. AI-facing `prune-backups` helper — rejected

A separate command has a clear CLI boundary, but the agent must remember when
to call it and interpret the result. Missed calls allow unbounded growth and
the extra orchestration consumes tokens.

### 3. Scheduled cleaner — rejected

`launchd`, cron, and Task Scheduler would decouple cleanup from writes, but add
cross-platform installation state, delayed enforcement, and another lifecycle
to diagnose and uninstall.

## Global Settings Contract

The user-owned file is:

```text
~/.obsidian-kb-settings.json
```

Its initial schema is:

```json
{
  "schema_version": 1,
  "backup": {
    "keep_per_note": 1
  }
}
```

Rules:

- A missing file means `keep_per_note = 1`; wheel and source use require no
  installer-created file.
- `keep_per_note` must be an integer from 1 through 1000. Boolean values are
  not integers for this contract. Zero is rejected so the last recoverable
  version is never intentionally removed.
- An unreadable file, malformed JSON, unsupported schema, missing object shape,
  or invalid retention value disables deletion for that invocation and emits a
  warning. The note write may still proceed and its new backup remains.
- The helper exposes no retention CLI option. AI agents cannot override policy
  per invocation.
- Bash and PowerShell create the default file only when absent and never
  overwrite user edits during install or upgrade.
- Default uninstall preserves the settings file. Explicit `--purge-config` or
  `-PurgeConfig` removes both `~/.obsidian-kb-config` and
  `~/.obsidian-kb-settings.json`.

## Runtime Components

### `backup_policy.py`

The module owns these responsibilities behind small testable interfaces:

- resolve the settings path from `Path.home()` with an injectable home for
  tests;
- parse and validate `schema_version` and `backup.keep_per_note`;
- discover only real backup files below `.obsidian-kb-backups/` without
  following symlink files or directories;
- recognize only timestamp directories named `YYYY-MM-DD-HHMMSS` with an
  optional positive numeric collision suffix (`-2`, `-3`, and so on);
- group files by their path relative to the timestamp directory;
- retain the protected backup from the current update plus the newest prior
  files up to `keep_per_note`;
- delete older regular files and remove empty product-owned directories from
  the bottom up, never removing the backup root;
- return a compact result containing retention, scanned/deleted counts, and
  warnings.

The current backup is passed as a protected path. For `keep_per_note = 1`, it
is the only retained copy even if the system clock moves backwards or another
file has a newer modification time. Other backups are ordered deterministically
by modification time, timestamp directory name, and relative path.

### `update_note.py`

The write path becomes:

1. Validate the Vault and note path.
2. Render the intended note bytes.
3. For an existing note, create the unique byte-for-byte backup.
4. Write the note.
5. Mark the write applied.
6. Invoke global backup pruning in-process. An initialization write also invokes
   pruning, without a protected current backup.
7. Continue audit and link suggestions.

Cleanup never runs before the write succeeds. A backup or note-write failure
leaves all backups untouched. A cleanup failure occurs after committed note
content, so it does not roll back the note and does not return a failure code
that could provoke an agent retry and another backup. Normal human output stays
silent on successful cleanup; warnings are printed to stderr. JSON output adds
a compact `backup_cleanup` object for deterministic auditability.

## Deletion Safety Boundary

Cleanup is a destructive operation and is treated as the release's P0-sensitive
surface:

- Never follow a symlink directory or symlink file.
- Never delete an unknown top-level item or a file that does not match the
  strict timestamp-directory plus relative-note layout. Unknown items are
  retained and reported as warnings.
- Resolve every candidate against the canonical Vault boundary before deletion.
- Delete files with `unlink()` only after verifying they are real regular files.
- Remove directories with `rmdir()` only when empty and only below the backup
  root.
- Treat malformed configuration as "retain everything", not as a default
  authorization to delete.
- Protect the backup created for the current update independent of sorting.

P0 means unexpected note loss, deletion outside the product-owned backup tree,
symlink escape, destructive installer behavior, or a broken installed runtime.
The version cannot be tagged while any such issue is known or unverified.

## Test Contract

Unit and integration tests must prove:

- missing settings defaults to one retained backup;
- configured values such as two and three retain exactly that many per note;
- invalid, boolean, zero, negative, excessive, malformed, and unsupported-schema
  settings perform zero deletions and report a warning;
- multiple note paths are grouped and retained independently;
- the current backup is protected despite clock or mtime ordering;
- no cleanup occurs after backup or note-write failure;
- cleanup runs only after a successful apply and initialization can converge
  older backup groups;
- partial cleanup errors preserve write success and surface warnings without
  encouraging a retry;
- symlink files, symlink directories, unknown layouts, traversal shapes, and
  out-of-Vault targets cannot cause deletion;
- empty directories are removed only below `.obsidian-kb-backups`;
- JSON output reports the compact cleanup result while normal successful output
  adds no cleanup chatter;
- Bash and PowerShell create, preserve, and explicitly purge settings identically;
- a disposable installed Skill and wheel read settings from a temporary HOME
  after the release/source tree is deleted.

## Release and Iteration Gate

The release version is 1.11.1. Before publishing:

1. Run the focused tests red before implementation and green after it.
2. Run Skill quick validation, `build.py --check`, `uv lock --check`, compile
   checks, Bash syntax, and the full local pytest suite.
3. Exercise a disposable release install and installed helper from a neutral
   directory after removing the source release.
4. Build and install the wheel independently and exercise its console scripts.
5. Review the complete diff specifically for P0 deletion, path, data-loss, and
   installer risks.
6. If any test or review finds a problem, fix it and restart the relevant focused
   test followed by the complete local gate. Repeat until no P0 remains.
7. Push a PR and require Linux Python 3.11, Linux Python 3.14, and Windows
   PowerShell/Python 3.11 jobs to pass.
8. Merge and require the master push gate to pass before creating the v1.11.1
   tag and GitHub Release.

## Local Synchronization After Release

After the published tag is verified:

1. Run the released Bash installer for the local Codex platform, which also
   creates the canonical support runtime. Do not mutate QoderWork, Claude Code,
   or Cursor installations in this synchronization step.
2. Preserve the existing Vault path config and create the global settings file
   only if missing.
3. Compare the installed Codex and canonical payload file sets and hashes with
   the released canonical Skill.
4. Run the installed launcher from a neutral directory against a disposable
   Vault, including a two-update retention scenario that leaves one backup.
5. Confirm installed metadata reports v1.11.1 behavior, configuration survives,
   and no source-checkout import is used.

## Follow-up Optimization Priorities

These are not mixed into v1.11.1:

1. P1: write notes through a same-directory temporary file plus `os.replace()`
   for atomic replacement.
2. P1: unify success and error JSON envelopes across all eight helpers.
3. P1: add a deterministic `doctor/version` command for installed-version and
   payload-drift diagnosis.
4. P2: split the 826-line `audit_vault.py` into rule-focused modules without
   changing findings.
5. P2: further consolidate Bash and PowerShell configuration parsing around
   shared contract fixtures.
