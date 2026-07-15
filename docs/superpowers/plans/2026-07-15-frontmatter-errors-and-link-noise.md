# Frontmatter Errors and Link Noise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject malformed frontmatter with exact diagnostics and remove generic article words from deterministic link scoring.

**Architecture:** Add one typed parser exception at the shared frontmatter boundary, then translate it into existing CLI error channels before mutation. Keep link scoring intact and filter only normalized title tokens through a fixed local stop set.

**Tech Stack:** Python 3.11+, PyYAML, pytest, existing build/manifest tooling.

## Global Constraints

- Preserve successful CLI and JSON contracts.
- Perform no mutation after an invalid-frontmatter result.
- Add no dependency, embedding model, network call, date change, routing parser, or folder-creation behavior.
- Regenerate packaged skill resources with `build.py`.

---

### Task 1: Actionable frontmatter parse failures

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Modify: `obsidian_kb_skill/scripts/update_note.py`
- Test: `tests/test_create_note.py`
- Test: `tests/test_json_output.py`
- Test: `tests/test_update_note.py`

**Interfaces:**
- Produces: `InvalidFrontmatterError(code, message, line, column, source)` raised by `split_frontmatter`.
- Produces: stable `invalid-frontmatter` CLI error details with exit code 2.

- [ ] Add a unit test asserting malformed YAML raises with line 3 and column 17.
- [ ] Add subprocess tests asserting human and preflight JSON modes expose the same source/location and create no file.
- [ ] Add an update-note test asserting a malformed existing note is unchanged.
- [ ] Run the focused tests and confirm they fail because YAML is currently swallowed.
- [ ] Implement the exception, coordinate conversion, and caller-level error reporting.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Generic title-token filtering

**Files:**
- Modify: `obsidian_kb_skill/scripts/suggest_links.py`
- Test: `tests/test_suggest_links.py`

**Interfaces:**
- Produces: `_title_tokens(title: str) -> set[str]` with generic terms removed.

- [ ] Add a regression using the Vibe Coding and Hermes titles with matching `web-clip` type and no specific shared tag.
- [ ] Run the regression and confirm it fails with the current score-3 `详解` suggestion.
- [ ] Add the minimal Chinese/English generic token set and filter normalized tokens.
- [ ] Run focused link tests and the real-Vault read-only command.

### Task 3: Package, version, and release verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `pyproject.toml`
- Modify: version assertions under `tests/`
- Regenerate: platform adapters, packaged resources, manifest, and `uv.lock`

**Interfaces:**
- Produces: v1.15.1 source and installed payloads with identical manifests.

- [ ] Document only the two fixes and bump version to 1.15.1.
- [ ] Run `uv lock`, `build.py`, full pytest, `build.py --check`, `uv lock --check`, skill validation, and wheel/sdist inspection.
- [ ] Push the feature branch, create a PR, wait for all CI jobs, merge, and wait for post-merge CI.
- [ ] Publish v1.15.1, install Codex and WorkBuddy payloads, run both doctors, and repeat both real regressions from installed helpers.
