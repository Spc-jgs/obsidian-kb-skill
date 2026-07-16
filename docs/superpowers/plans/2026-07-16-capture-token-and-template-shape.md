# Capture Token and Template Shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce ordinary capture governance tokens and expose one selected standard template's ordered headings through the existing compact Vault discovery call.

**Architecture:** The Vault repository keeps one authoritative root policy and moves Python-only governance to its subtree. The Skill repository extends `vault-info` with an optional note type, derives a prose-free heading shape from only that conventional template, and moves exceptional category/custom-template instructions into one-level lazy references.

**Tech Stack:** Markdown governance, Python 3.11+, argparse, JSON, pytest, `o200k_base` analysis in an isolated `uv --with` environment, generated Skill adapters.

## Global Constraints

- Preserve Vault routes, Git publication, Folder Index ownership, prohibited operations, and README decisions.
- Preserve structured preflight, exclusive apply, automatic audit, and custom-template SHA-256 protection.
- Do not return template prose, frontmatter, lists, tables, labels, or examples in `template_shape`.
- Do not add a second ordinary discovery call, semantic model, webpage extractor, or runtime `tiktoken` dependency.
- Use separate branches and pull requests for the Vault and Skill repositories.
- Do not merge or release either repository without explicit user confirmation after PR verification.

---

### Task 1: Consolidate Vault Governance

**Files:**
- Modify: `/Users/shaopc/Documents/my-knowledge-base/AGENTS.md`
- Modify: `/Users/shaopc/Documents/my-knowledge-base/CLAUDE.md`
- Create: `/Users/shaopc/Documents/my-knowledge-base/20-Learning/Python/AGENTS.md`

**Interfaces:**
- Produces: one root cross-agent policy, one short Claude entrypoint, and Python-only subtree governance.

- [ ] **Step 1: Capture the baseline and create the Vault branch**

Run `o200k_base` measurement for root `AGENTS.md` and `CLAUDE.md`; record the 3,531-token baseline. Create `feature/compact-vault-governance` from clean `master`.

- [ ] **Step 2: Define governance preservation checks before editing**

Run a read-only marker check covering every governed route plus `YYYY-MM-DD`, required metadata, Folder Index ownership, high-confidence links, `add:`, no deletion/overwrite, `.obsidian/workspace.json`, and README update/no-update decisions. Save the command output as the RED/baseline evidence; no persistent test harness is added to the personal Vault.

- [ ] **Step 3: Write the minimal governance split**

Keep common policies in root `AGENTS.md`; replace body-template examples with `Templates/<Name>.md` ownership; move the complete Python automation/style/progress/WeChat section into `20-Learning/Python/AGENTS.md`; reduce `CLAUDE.md` to project identity plus mandatory delegation to root and path-local `AGENTS.md`.

- [ ] **Step 4: Verify policy preservation and token reduction**

Re-run every marker check, confirm the Python-local file contains all seven automation steps and all seven WeChat sections, and measure root fixed context. Target: root `AGENTS.md + CLAUDE.md <= 1,900 o200k_base` tokens.

- [ ] **Step 5: Verify Vault behavior and commit**

Run installed `vault-info --compact --type web-clip` only after Task 3 implements it; before then run current compact discovery plus a read-only Web Clip preflight. Confirm no Vault note/index mutation, inspect `git diff --check`, and commit only the three governance files.

### Task 2: Add Selected Template Shape to Vault Discovery

**Files:**
- Modify: `obsidian_kb_skill/scripts/template_contract.py`
- Modify: `obsidian_kb_skill/scripts/vault_info.py`
- Modify: `tests/test_template_contract.py`
- Modify: `tests/test_vault_info.py`
- Modify: `tests/test_json_output.py`

**Interfaces:**
- Produces: `template_shape(vault: Path, note_type: str) -> dict[str, Any] | None`.
- Extends: `collect(vault: Path, note_type: str | None = None) -> dict[str, Any]`.
- Adds CLI option: `vault-info <vault> --type <slug> --json --compact`.

- [ ] **Step 1: Write failing API tests**

Add tests proving one selected Web Clip returns its relative path and ordered level-two headings, missing conventional templates return `None`, and the field contains neither instruction prose nor frontmatter.

- [ ] **Step 2: Write failing CLI compatibility/error tests**

Assert omitted `--type` has no `template_shape`, selected type emits one shape, and unsupported type exits 2 with `{"error":{"code":"unsupported-template-type",...}}` and no mutation.

- [ ] **Step 3: Verify RED**

Run the new targeted tests and confirm failures are caused by the absent `note_type` parameter/CLI flag/interface.

- [ ] **Step 4: Implement minimal heading extraction and optional discovery field**

Extract only Markdown level-two headings matching `^##\s+(.+?)\s*$` from the selected conventional template. Add `template_shape` only when a supported `note_type` was explicitly supplied. Keep the current response byte-compatible at the top-level field set when it is omitted.

- [ ] **Step 5: Verify GREEN and commit**

Run template-contract, vault-info, JSON-output, audit, and installed-runtime focused tests. Commit the implementation and tests.

### Task 3: Lazy-load Exceptional Creation Instructions

**Files:**
- Modify: `core/references/note-creation.md`
- Create: `core/references/missing-category.md`
- Create: `core/references/custom-template.md`
- Modify: `tests/test_lazy_references.py`
- Regenerate: `obsidian_kb_skill/scripts/resources/references/**`
- Regenerate: `skills/obsidian-knowledge-base/**`
- Regenerate: `platforms/**/references/**`

**Interfaces:**
- Ordinary create continues loading only `note-creation.md`.
- Missing category conditionally loads `missing-category.md`.
- Selected custom type conditionally loads `custom-template.md`.

- [ ] **Step 1: Write failing reference-boundary tests**

Require both new files, require their one-level pointers in `note-creation.md`, and assert detailed markers (`--apply --confirmed --compact-json`, prose/list/table/example interpretation, renamed-template backlog) live only in the conditional references.

- [ ] **Step 2: Verify RED**

Run `tests/test_lazy_references.py`; confirm failure because conditional files and pointers do not exist.

- [ ] **Step 3: Split exceptional details while preserving inline gates**

Keep user confirmation and route-persistence choice inline for missing categories. Keep `custom_templates`, exactly-one-contract, unknown-placeholder stop, and expected SHA on preflight/apply inline for custom templates. Move commands, recovery detail, semantic interpretation checklist, and renamed-template backlog to their conditional files.

- [ ] **Step 4: Update discovery command and regenerate**

Document confident-type discovery as `vault-info <vault> --json --compact --type <slug>`, with omitted type as the uncertainty fallback. Run `uv run python build.py`.

- [ ] **Step 5: Verify GREEN, measure, and commit**

Run lazy-reference/build/runtime tests and measure `SKILL.md + note-creation.md`. Target: ordinary instruction surface below 2,300 `o200k_base` tokens without loading either conditional file.

### Task 4: Product Verification and Two-Repository PRs

**Files:**
- Modify only if verification reveals a tested defect in prior task files.

**Interfaces:**
- Validates source, generated payload, installed-style runner, Vault governance, and GitHub review state.

- [ ] **Step 1: Run Skill full verification**

Run `uv run pytest -q`, `uv run python build.py --check`, `uv lock --check`, `uv build`, `git diff --check`, and hostile-directory runner smoke for standard Web Clip shape plus custom-template discovery.

- [ ] **Step 2: Run Vault forward verification**

Run installed/source runner against the real Vault read-only: selected Web Clip discovery must expose all seven headings and no prose; a complete note preflight must pass; no note or index may be written.

- [ ] **Step 3: Review scope and publish the Vault PR**

Confirm the Vault branch changes only `AGENTS.md`, `CLAUDE.md`, and `20-Learning/Python/AGENTS.md`; push and open a ready PR with before/after token evidence and policy-preservation checks.

- [ ] **Step 4: Review scope and publish the Skill PR**

Review `master...HEAD`, confirm no Critical/Important issue, push, and open a ready PR with RED/GREEN evidence, token measurement, full verification, and compatibility notes.

- [ ] **Step 5: Wait for CI and report**

Wait for Linux Python 3.11/3.14 and Windows installer checks. Report both PRs, measured savings, remaining risks, and explicitly leave merge/release pending user confirmation.
