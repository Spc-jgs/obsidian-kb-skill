# Runtime Token Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce ordinary Obsidian capture retries and discovery output while preserving template, Vault, Git, preflight, write, and audit quality gates.

**Architecture:** Keep existing helper sources of truth and add narrow output improvements: aggregate template-order diagnostics inside the note auditor, project the existing vault discovery result into a compact CLI response, and clarify the instruction ordering contract. Apply the Vault `.obsidian/` ignore as a separate repository operation.

**Tech Stack:** Python 3.10+, argparse, pytest, Markdown skill references, GitHub CLI, existing build and installer scripts.

## Global Constraints

- Do not remove or bypass Vault governance, template enforcement, Git safety, preflight, write, or automatic audit.
- Preserve default `vault-info` JSON compatibility; compact output is opt-in.
- Do not inject empty template headings or use semantic models.
- Do not delete local Vault `.obsidian/` files.
- Release target is `v1.17.0`; merge by PR and verify installed Codex and WorkBuddy copies.

---

### Task 1: Aggregate Template Heading Diagnostics

**Files:**
- Modify: `tests/test_audit_vault.py`
- Modify: `obsidian_kb_skill/scripts/audit_vault.py`

**Interfaces:**
- Consumes: `_audit_required_template_headings(findings, vault, relative, text, metadata)`.
- Produces: one `Finding(code="missing-template-heading")` containing `expected headings`, `actual headings`, and `first mismatch` in its message.

- [ ] **Step 1: Write the failing test**

Change the ordered-heading test to assert one finding and all diagnostic fields:

```python
finding = next(item for item in findings if item.code == "missing-template-heading")
assert [item.code for item in findings].count("missing-template-heading") == 1
assert "expected headings: First -> Second" in finding.message
assert "actual headings: Second -> First" in finding.message
assert "first mismatch: First" in finding.message
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_audit_vault.py::test_audit_note_text_checks_required_template_heading_order -q`

Expected: FAIL because the current message reports only one heading.

- [ ] **Step 3: Implement the minimal diagnostic**

Keep the ordered-subsequence scan, record the first unmatched required heading, and emit one message after scanning:

```python
expected = " -> ".join(required) or "(none)"
observed = " -> ".join(actual) or "(none)"
message = (
    "required template headings are missing or out of order; "
    f"expected headings: {expected}; actual headings: {observed}; "
    f"first mismatch: {first_mismatch}"
)
```

- [ ] **Step 4: Verify GREEN and regressions**

Run: `uv run pytest tests/test_audit_vault.py tests/test_create_note.py tests/test_json_output.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_audit_vault.py obsidian_kb_skill/scripts/audit_vault.py
git commit -m "fix: report complete template heading diagnostics"
```

### Task 2: Add Compact Vault Discovery

**Files:**
- Modify: `tests/test_vault_info.py`
- Modify: `tests/test_json_output.py`
- Modify: `obsidian_kb_skill/scripts/vault_info.py`

**Interfaces:**
- Consumes: `collect(vault: Path) -> dict[str, Any]` unchanged.
- Produces: `compact(info: dict[str, Any]) -> dict[str, Any]` and CLI flag `vault-info <vault> --compact`.

- [ ] **Step 1: Write failing unit and CLI tests**

Add a unit test proving `compact()` removes only nested `notes`, leaves the original result unmodified, and retains `mode`, `index_file`, and `can_append`. Add a JSON integration assertion using `--compact`:

```python
full = collect(vault)
out = compact(full)
assert "notes" in full["standard_folders"]["20-Learning"]["index"]
assert "notes" not in out["standard_folders"]["20-Learning"]["index"]
assert out["standard_folders"]["20-Learning"]["index"]["mode"] == "static"
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_vault_info.py tests/test_json_output.py::test_vault_info_compact_json -q`

Expected: collection fails because `compact` and `--compact` do not exist.

- [ ] **Step 3: Implement compact projection**

Use `copy.deepcopy`, remove only `index["notes"]`, add argparse `--compact`, and project immediately before `json.dumps`. Do not change `collect()` or default output.

- [ ] **Step 4: Verify GREEN and measure output**

Run:

```bash
uv run pytest tests/test_vault_info.py tests/test_json_output.py -q
python skills/obsidian-knowledge-base/scripts/run_helper.py vault-info /Users/shaopc/Documents/my-knowledge-base --json --compact
```

Expected: tests pass; compact output contains no per-folder `notes` arrays and retains index ownership fields.

- [ ] **Step 5: Commit**

```bash
git add tests/test_vault_info.py tests/test_json_output.py obsidian_kb_skill/scripts/vault_info.py
git commit -m "feat: add compact vault discovery output"
```

### Task 3: Tighten the Ordinary Workflow Contract

**Files:**
- Modify: `tests/test_lazy_references.py`
- Modify: `obsidian_kb_skill/scripts/resources/references/note-creation.md`

**Interfaces:**
- Consumes: `vault-info --json --compact` and optional Git reference.
- Produces: an instruction contract that runs Git preflight before source retrieval and tells agents to repair all heading diagnostics in one pass.

- [ ] **Step 1: Write failing reference-contract tests**

Assert the ordinary path contains `vault-info --json --compact`, says Git preflight completes before fetching or deeply reading source content, and says a heading finding includes expected/actual/first mismatch data.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_lazy_references.py -q`

Expected: FAIL because the new compact command and ordering markers are absent.

- [ ] **Step 3: Make the minimal reference edit**

Update only the discovery, Git-ordering, and preflight-diagnostic paragraphs. Do not add template reads, YAML reference reads, `detect-index`, memory logging, or a second audit.

- [ ] **Step 4: Regenerate and verify generated artifacts**

Run:

```bash
uv run python build.py
uv run pytest tests/test_lazy_references.py tests/test_build.py -q
```

Expected: generated skill copies match their sources and tests pass.

- [ ] **Step 5: Commit**

```bash
git add obsidian_kb_skill/scripts/resources/references/note-creation.md skills platforms tests/test_lazy_references.py
git commit -m "docs: front-load git checks in note capture"
```

### Task 4: Ignore Vault Obsidian Runtime State

**Files:**
- Modify in Vault repository: `.gitignore`
- Remove from the Vault Git index only: `.obsidian/**`

**Interfaces:**
- Produces: Git ignores the full `.obsidian/` tree while local Obsidian continues using it.

- [ ] **Step 1: Replace granular ignore rules**

Set the Obsidian runtime block to:

```gitignore
# Obsidian local application state and plugins
.obsidian/
```

- [ ] **Step 2: Remove tracked files from the index without deleting local files**

Run: `git rm -r --cached .obsidian`

Expected: tracked `.obsidian` files are staged as deletions and remain present on disk.

- [ ] **Step 3: Verify scope and commit**

Run `git diff --cached --name-status`, `test -d .obsidian`, and `git check-ignore .obsidian/graph.json`. Commit only `.gitignore` plus `.obsidian` index removals, then fetch, check divergence, and push.

### Task 5: Release and Installed-State Verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_build.py`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_installers.py`
- Regenerate: `skills/obsidian-knowledge-base/manifest.json`
- Regenerate: `skills/obsidian-knowledge-base/**`
- Regenerate: `platforms/**`
- Regenerate: `uv.lock`

**Interfaces:**
- Produces: repository, packages, Codex install, and WorkBuddy install all report `1.17.0`.

- [ ] **Step 1: Run full verification before versioning**

Run: `uv run pytest -q && uv run python build.py --check && uv lock --check`.

Expected: all tests pass, generated files match, and lock is current.

- [ ] **Step 2: Prepare version `1.17.0` and build artifacts**

Update the existing version sources and changelog using repository conventions, regenerate artifacts, and build wheel and sdist with the existing build command.

- [ ] **Step 3: Verify packages and commit release preparation**

Run the full suite plus wheel/install/runtime smoke tests used by the previous release. Commit with `release: prepare v1.17.0`.

- [ ] **Step 4: Push, open PR, review, merge, and release**

Push `feature/runtime-token-optimizations`, open a ready PR, verify required checks, merge into `master`, create tag and GitHub release `v1.17.0`, then confirm release assets.

- [ ] **Step 5: Synchronize installed runtimes**

Fast-forward the local repository, run the supported installers for Codex and WorkBuddy, and verify both installed `SKILL.md` manifests and hostile-current-directory helper smoke tests report `1.17.0`.
