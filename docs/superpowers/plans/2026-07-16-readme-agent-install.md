# README Agent-First Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the README release-note pile with a stable changelog link and make a copyable Agent-driven installation prompt the primary setup path.

**Architecture:** Keep `CHANGELOG.md` as the only release-history source. Restructure both root README files around one Agent-first quick start, while retaining the existing manual installer, platform, configuration, upgrade, uninstall, and contribution reference material.

**Tech Stack:** Markdown, pytest repository contracts, existing `build.py` drift checks.

## Global Constraints

- Do not change installer behavior, Skill runtime instructions, templates, or release version.
- Keep Chinese and English README content structurally equivalent.
- Preserve existing supported-platform and advanced installation documentation.
- Do not add a rotating release summary or collapsible changelog to either README.

---

### Task 1: Lock the README information contract

**Files:**
- Modify: `tests/test_build.py`

**Interfaces:**
- Consumes: the repository-root `README.md`, `README_EN.md`, and `CHANGELOG.md` files.
- Produces: a regression contract for Agent-first installation and changelog ownership.

- [ ] **Step 1: Add a failing README structure test**

Add this test near the existing README tests in `tests/test_build.py`:

```python
def test_readmes_use_agent_first_installation_and_changelog_owns_history():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "## 让 Agent 安装（推荐）" in readme
    assert "## Install with Your Agent (Recommended)" in readme_en
    assert readme.index("## 让 Agent 安装（推荐）") < readme.index("## 手动安装与下载")
    assert readme_en.index("## Install with Your Agent (Recommended)") < readme_en.index("## Manual Installation and Downloads")
    assert "doctor --json" in readme
    assert "doctor --json" in readme_en
    assert "CHANGELOG.md" in readme
    assert "CHANGELOG.md" in readme_en
    assert "## v1.19 新增的能力" not in readme
    assert "## v1.12 新增的能力" not in readme
    assert "## What's New in v1.19" not in readme_en
    assert "## What's New in v1.12" not in readme_en
```

- [ ] **Step 2: Run the test and verify the current README fails**

Run:

```bash
uv run pytest tests/test_build.py::test_readmes_use_agent_first_installation_and_changelog_owns_history -q
```

Expected: FAIL because the Agent-first headings do not exist yet.

---

### Task 2: Make Agent-driven installation the primary path

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`

**Interfaces:**
- Consumes: the README contract from Task 1 and the existing installer behavior.
- Produces: matching Chinese and English onboarding paths with timeless release navigation.

- [ ] **Step 1: Remove duplicate release history**

Delete all version feature sections from `## v1.19 新增的能力` through the end of `## v1.12 新增的能力` in `README.md`, and the equivalent `What's New` sections in `README_EN.md`. Replace them with one compact sentence below the introduction linking the current version to `CHANGELOG.md`.

- [ ] **Step 2: Add the primary Agent prompt**

Before any clone, ZIP, or shell command, add `## 让 Agent 安装（推荐）` and `## Install with Your Agent (Recommended)`. Each section must contain one copyable prompt that tells the current Agent to inspect the official repository, detect the platform, ask for an unknown Vault path, use the official installer, preserve templates and Vault content, run installed `doctor --json`, and report the version and installed paths.

- [ ] **Step 3: Demote existing download and script flows**

Rename the existing download/manual area to `## 手动安装与下载` and `## Manual Installation and Downloads`. Keep Git clone, ZIP, direct-file caveats, platform-specific installer commands, Vault configuration, and manual-copy instructions in this secondary area without presenting Git clone as the recommended route.

- [ ] **Step 4: Run the focused README tests**

Run:

```bash
uv run pytest tests/test_build.py::test_readmes_use_agent_first_installation_and_changelog_owns_history tests/test_build.py::test_readme_documents_standard_skill_entry tests/test_build.py::test_readmes_warn_that_one_instruction_file_is_not_a_complete_install tests/test_environment_contract.py::test_readmes_document_locked_uv_workflow -q
```

Expected: PASS.

---

### Task 3: Verify and commit the documentation update

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `tests/test_build.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: a review-ready documentation commit with no generated drift.

- [ ] **Step 1: Check heading order and stale release sections**

Run:

```bash
rg -n '^## ' README.md README_EN.md
rg -n '^## (v1\.|What.s New)' README.md README_EN.md
```

Expected: Agent-first installation precedes manual installation; the second command returns no matches.

- [ ] **Step 2: Run repository verification**

Run:

```bash
uv run pytest -q
uv run python build.py --check
uv lock --check
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Commit the implementation**

Run:

```bash
git add README.md README_EN.md tests/test_build.py docs/superpowers/plans/2026-07-16-readme-agent-install.md
git commit -m "docs: recommend agent-driven installation"
```

