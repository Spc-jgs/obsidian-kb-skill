# Runtime Token Optimizations Design

## Goal

Reduce avoidable note-capture retries and context output without removing Vault governance, template enforcement, Git safety, preflight, write, or audit steps.

## Scope

This release changes three skill-runtime behaviors:

1. Template-order validation reports the complete expected and actual heading sequences in one finding instead of stopping at the first mismatch.
2. `vault-info` gains an opt-in compact response that omits per-folder note filename arrays while preserving validity, templates, folder existence, index ownership, and global Folder Index configuration.
3. The create workflow performs governance-triggered Git preflight immediately after discovery and governance inspection, before fetching or deeply reading source material.

The user's Vault receives a separate Git maintenance commit that ignores the complete `.obsidian/` directory and removes already tracked `.obsidian` files from the index without deleting local files.

## Template Diagnostics

`_audit_required_template_headings` will keep the current ordered-subsequence rule. When the rule fails, it emits one `missing-template-heading` finding whose message includes:

- the full required heading sequence;
- the full actual heading sequence;
- the first required heading that cannot be matched in order.

One finding keeps the existing validation count stable while providing enough information to repair every missing or misplaced required section in one edit. The helper will not inject headings or placeholder content.

## Compact Vault Discovery

The default `vault-info` JSON contract remains unchanged for compatibility. A new `--compact` flag removes only each index object's `notes` field. Diagnostic callers can continue using the default response, while the ordinary note-creation workflow uses `vault-info --json --compact`.

Compact output retains `mode`, `index_file`, `can_append`, plugin ownership, warnings, and every other index field required to avoid manual `detect-index` calls. The implementation will derive compact output from the same `collect()` result so index detection keeps one source of truth.

## Git Ordering

The note-creation reference will define this order:

1. locate and validate the Vault with compact discovery;
2. inspect applicable governance;
3. if governance requires Git, load the Git reference and finish its pre-write synchronization;
4. only then fetch or deeply read external source content;
5. continue preflight, apply, and automatic audit.

This is an instruction-only ordering fix. Git blocking rules remain unchanged.

## Vault Ignore Policy

The Vault `.gitignore` will contain `.obsidian/`. Existing tracked files under that directory will be removed with `git rm --cached`, preserving the local Obsidian configuration. The Vault commit will contain only `.gitignore` and index removals under `.obsidian/`.

## Testing

- Unit tests prove one template finding contains expected, actual, and first mismatch data.
- CLI and collection tests prove compact `vault-info` omits only `notes` and default output remains compatible.
- Reference-contract tests prove ordinary creation uses compact discovery and places Git preflight before source retrieval.
- Full pytest, build checks, wheel/install smoke checks, and installed Codex/WorkBuddy verification gate release `v1.17.0`.

## Non-Goals

- No semantic model for links or governance parsing.
- No automatic template-section generation.
- No weakening of dirty-worktree, divergence, conflict, preflight, or audit checks.
- No arbitrary partial read of natural-language `AGENTS.md`; machine-readable governance can be designed separately.
