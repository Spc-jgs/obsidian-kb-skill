# Note Creation Instruction Streamlining Design

## Goal

Reduce avoidable context reads and tool calls during ordinary note creation without removing Vault governance, structured preflight, exclusive creation, post-write audit, or bounded link suggestions.

## Baseline Evidence

A real WorkBuddy run loaded `SKILL.md`, `note-creation.md`, and `yaml-standards.md`, manually inspected the active template, called both `vault-info` and `detect-index`, verified the written file again after the helper audit, and appended an unrelated `.workbuddy/memory` entry. The extra YAML reference alone cost 713 `o200k_base` tokens. The run still needed the core create workflow, so the problem is redundant guidance rather than missing automation.

## Design

### One explicit reference per ordinary operation

The always-loaded gate maps each operation to exactly one required reference. A new note loads only `note-creation.md`. YAML, rules, Git, and task-memory references are conditional troubleshooting or opt-in material, not a default reference bundle.

### One discovery call

`vault-info --json` remains the cold-start call and supplies Vault validity, templates, and folder index strategies. Ordinary creation must not call `detect-index` afterward. `detect-index` remains available for explicit index diagnosis and maintenance, while `create-note` continues to apply the selected folder's index policy internally.

### No manual template read

The agent supplies complete Markdown and metadata to `create-note`; the helper loads and merges the Vault template. Direct template inspection is reserved for template debugging or an explicit template-editing request.

### No redundant post-write verification

`create-note --apply --compact-json` already returns its audit. A successful zero-finding audit is the completion check. Re-reading the created note is reserved for an audit failure or an explicit user request.

### No automatic memory write

Creating a normal note writes only that note, plus a static index when the detected strategy requires it. The agent must not read or write `.workbuddy/memory`, Task Memory, daily logs, or any secondary recap unless the user explicitly requests that separate operation or higher-priority runtime instructions require it.

## Preserved Quality Gates

- Read root and target-path Vault governance before choosing type, folder, metadata, naming, README, and Git actions.
- Use `create-note --preflight-json` before mutation.
- Apply with `--apply --compact-json` and keep automatic per-note audit enabled.
- Preserve exclusive non-overwriting writes, template merging, web-clip required metadata, and static-index handling.
- Keep link suggestions bounded and optional; do not change their scoring in this release.

## Verification

- Static policy tests must fail against v1.14.0 wording and pass after the edit.
- Generated platform adapters and packaged references must match the core source.
- Existing create-note, audit, installer, and full test suites must remain green.
- Measure `SKILL.md + note-creation.md` with `o200k_base` before and after; report instruction savings separately from article and tool-output tokens.
