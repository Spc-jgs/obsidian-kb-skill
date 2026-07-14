# Note Creation Instruction Streamlining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ordinary new-note path unambiguous and minimal while preserving every existing quality gate.

**Architecture:** Keep `core/OBSIDIAN_KB.md` and `core/references/note-creation.md` as the only editable instruction sources. Add policy assertions to the existing lazy-reference tests, then rebuild all generated adapters and packaged resources with `build.py`.

**Tech Stack:** Markdown instruction sources, Python/pytest policy tests, repository `build.py` generator.

## Global Constraints

- Do not change helper behavior or `suggest-links` scoring.
- Preserve Vault governance, `--preflight-json`, `--apply --compact-json`, automatic audit, template merging, and index handling.
- Ordinary new-note creation loads only `note-creation.md`; other references are conditional.
- Ordinary creation does not manually read templates, call `detect-index` after `vault-info`, re-read a cleanly audited note, or write secondary memory/log notes.

---

### Task 1: Lock the streamlined contract with failing tests

**Files:**
- Modify: `tests/test_lazy_references.py`

**Interfaces:**
- Consumes: canonical Markdown from `core/OBSIDIAN_KB.md` and `core/references/note-creation.md`.
- Produces: policy assertions that describe the minimal ordinary-create workflow.

- [ ] Add assertions that the core gate maps new-note creation to only `note-creation.md`, marks Task Memory explicit opt-in, and does not present YAML/rules/Git references as default reads.
- [ ] Add assertions that the note-creation reference says one `vault-info` call is sufficient, reserves `detect-index` for diagnosis, delegates template loading, trusts a clean apply audit, and forbids secondary memory/log writes without explicit intent.
- [ ] Run the focused tests and confirm they fail against v1.14.0 wording for the expected missing or contradictory contracts.

### Task 2: Implement the minimal instruction edit

**Files:**
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `core/references/note-creation.md`
- Regenerate: `skills/obsidian-knowledge-base/**`, `platforms/*/**`, `obsidian_kb_skill/scripts/resources/references/**`

**Interfaces:**
- Consumes: failing policy assertions from Task 1.
- Produces: generated instructions with one ordinary-create reference and one discovery call.

- [ ] Rewrite the reference selector in the core gate as explicit operation-to-reference mappings and conditional opt-ins.
- [ ] Collapse discovery and index guidance in `note-creation.md`; keep `detect-index` only as a diagnostic escape hatch.
- [ ] State that `create-note` loads the active template and that a clean compact apply audit completes verification.
- [ ] State that no Task Memory, `.workbuddy/memory`, daily log, or secondary recap is written without separate explicit intent.
- [ ] Run `uv run python build.py` to regenerate every adapter, packaged reference, helper payload, and manifest.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Prove compatibility and quantify the result

**Files:**
- Modify if needed: `CHANGELOG.md`

**Interfaces:**
- Consumes: generated artifacts from Task 2.
- Produces: verified instruction savings and regression evidence.

- [ ] Run lazy-reference, build, create-note, audit, installer, and complete pytest suites.
- [ ] Run `uv run python build.py --check` and `git diff --check`.
- [ ] Count `SKILL.md + note-creation.md` with `o200k_base` and compare against the v1.14.0 baseline of 3,240 tokens.
- [ ] Review the final diff for accidental helper or `suggest-links` changes.
- [ ] Commit the implementation, push the branch, open a standard GitHub PR, and wait for required CI checks.
