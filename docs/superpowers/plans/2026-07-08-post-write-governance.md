# Obsidian Post-Write Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the Obsidian knowledge-base skill so every note is validated after writing, Folder Index structure regressions are detected, local Vault rules take precedence, and optional Git operations stop safely on divergence.

**Architecture:** Keep `core/OBSIDIAN_KB.md` as the behavioral source of truth and regenerate all four platform adapters. Extend the existing read-only auditor with a focused Folder Index block check, lock both code and instruction behavior with pytest, then repair the two concrete Vault violations found in the QoderWork run.

**Tech Stack:** Python 3.9+, PyYAML, pytest, Markdown instruction files, Git, Obsidian Folder Index fenced blocks.

## Global Constraints

- User request overrides Vault-local governance files; Vault-local governance overrides generic skill defaults.
- Keep reading Folder Index `data.json`; control-plane files count toward total scanned files but not content-note full reads.
- Default to one target note per invocation; ask before creating multiple notes.
- Do not perform Git commit or push unless the user or Vault-local rules require it.
- Stop on Git divergence or conflict; never auto-resolve an INDEX conflict.
- Do not prohibit legitimate manual explanations, learning progress, or cross-folder navigation in INDEX files.
- Use TDD for auditor and instruction-contract changes.
- Regenerate adapters only through `python build.py`.

---

### Task 1: Detect broken Folder Index structure

**Files:**
- Modify: `tests/test_audit_vault.py`
- Modify: `scripts/audit_vault.py`

**Interfaces:**
- Consumes: `_frontmatter(text)` and `Finding` in `scripts/audit_vault.py`.
- Produces: deterministic `missing-folder-index-content` and `duplicate-folder-index-content` findings from `audit_vault(vault: Path)`.

- [ ] **Step 1: Add failing tests for missing and duplicate Folder Index content blocks**

```python
def test_reports_missing_folder_index_content_block(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n# Notes\n",
        encoding="utf-8",
    )

    assert "missing-folder-index-content" in codes(tmp_path)


def test_reports_duplicate_folder_index_content_blocks(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n"
        "```folder-index-content\n```\n"
        "## Manual navigation\n"
        "```folder-index-content\n```\n",
        encoding="utf-8",
    )

    assert "duplicate-folder-index-content" in codes(tmp_path)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_audit_vault.py -k 'folder_index_content' -v`

Expected: both tests fail because neither finding code exists yet.

- [ ] **Step 3: Implement one exact block counter**

Add a line-anchored regex and helper in `scripts/audit_vault.py`:

```python
FOLDER_INDEX_CONTENT_RE = re.compile(
    r"^\s*```folder-index-content(?:\s+[^\n]*)?\s*$", re.MULTILINE
)


def _audit_folder_index_content(
    findings: list[Finding],
    relative: Path,
    text: str,
    metadata: dict[str, Any] | None,
) -> None:
    if not metadata or metadata.get("type") != "folder-index":
        return
    count = len(FOLDER_INDEX_CONTENT_RE.findall(text))
    if count == 0:
        _add(
            findings,
            "missing-folder-index-content",
            relative,
            "folder-index note must contain one folder-index-content block",
        )
    elif count > 1:
        _add(
            findings,
            "duplicate-folder-index-content",
            relative,
            "folder-index note must contain exactly one folder-index-content block",
        )
```

Call the helper from the Markdown audit loop immediately after `_audit_metadata`.

- [ ] **Step 4: Run focused and complete auditor tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_audit_vault.py -v`

Expected: all auditor tests pass; the existing valid index with manual content remains accepted.

- [ ] **Step 5: Commit the auditor change**

```bash
git add scripts/audit_vault.py tests/test_audit_vault.py
git commit -m "feat: audit Folder Index content blocks"
```

---

### Task 2: Encode the post-write workflow contract

**Files:**
- Modify: `tests/test_build.py`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `core/templates/web-clip.md`

**Interfaces:**
- Consumes: the QoderWork baseline failure (six tags, mixed-case tag, unsafe INDEX conflict resolution).
- Produces: shared instruction text consumed verbatim by all platform adapters and a Chinese Web Clip template using `## 理解与启发`.

- [ ] **Step 1: Add failing instruction-contract tests**

Add to `tests/test_build.py`:

```python
class TestGovernanceContract:
    @classmethod
    def setup_class(cls):
        cls.core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
        cls.web_clip = (ROOT / "core" / "templates" / "web-clip.md").read_text(
            encoding="utf-8"
        )

    def test_local_vault_rules_precede_generic_defaults(self):
        assert "Vault-local governance" in self.core
        assert "generic skill defaults" in self.core

    def test_create_workflow_validates_before_confirmation(self):
        validate = self.core.index("### Step 9: Validate Result")
        confirm = self.core.index("### Step 10: Confirm to User")
        assert validate < confirm

    def test_batch_capture_requires_confirmation(self):
        assert "Default to one target note per invocation" in self.core
        assert "ask the user before creating multiple notes" in self.core

    def test_git_stops_on_divergence_or_conflict(self):
        assert "Stop on divergence or conflict" in self.core
        assert "Never auto-resolve INDEX conflicts" in self.core

    def test_web_clip_defines_bounded_interpretation(self):
        assert "## 理解与启发" in self.web_clip
        assert "2–4 句" in self.web_clip
        assert "不要代替用户表达个人立场" in self.web_clip
```

- [ ] **Step 2: Run contract tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_build.py::TestGovernanceContract -v`

Expected: all five tests fail against v1.4.0 instructions.

- [ ] **Step 3: Update the shared workflow and template minimally**

Modify `core/OBSIDIAN_KB.md` to add:

- an explicit precedence section after Vault Validation;
- write-after validation as Create Step 9 and Update Step 7;
- confirmation/reporting renumbered after validation;
- bounded candidate routing using local governance, target INDEX, parent INDEX, then 1–2 siblings;
- control-plane versus content-note read accounting;
- one-note default with confirmation before multiple notes;
- optional Git post-processing that stages only task files and stops on divergence/conflict;
- a validation failure rule in Error Handling.

Modify `core/templates/web-clip.md`:

```markdown
## 理解与启发

> 用 2–4 句话区分原文观点与自己的推论，不机械复述核心观点，也不要代替用户表达个人立场。
```

- [ ] **Step 4: Run contract tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_build.py::TestGovernanceContract -v`

Expected: 5 passed.

- [ ] **Step 5: Commit the instruction source changes**

```bash
git add core/OBSIDIAN_KB.md core/templates/web-clip.md tests/test_build.py
git commit -m "feat: validate notes after knowledge capture"
```

---

### Task 3: Release v1.5.0 and regenerate platform adapters

**Files:**
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Regenerate: `platforms/qoderwork/SKILL.md`
- Regenerate: `platforms/claude-code/CLAUDE.md`
- Regenerate: `platforms/codex/AGENTS.md`
- Regenerate: `platforms/cursor/obsidian-kb.mdc`

**Interfaces:**
- Consumes: completed core instructions from Task 2.
- Produces: version `1.5.0` metadata and four byte-synchronized adapters.

- [ ] **Step 1: Change version metadata and release notes**

Set all visible project versions to `1.5.0`. Add a `2026-07-08` changelog entry covering post-write validation, Folder Index block auditing, Vault-local precedence, clarified cost accounting, one-note capture boundary, and safe optional Git handling.

- [ ] **Step 2: Regenerate every adapter**

Run: `.venv/bin/python build.py`

Expected: four platform adapter files are regenerated from the shared core.

- [ ] **Step 3: Verify generated output and full test suite**

Run: `.venv/bin/python build.py --check`

Expected: exit 0 and all adapters reported up to date.

Run: `.venv/bin/python -m pytest tests/ -v`

Expected: all tests pass.

- [ ] **Step 4: Commit release synchronization**

```bash
git add core/OBSIDIAN_KB.md pyproject.toml README.md README_EN.md CHANGELOG.md platforms
git commit -m "release: prepare obsidian kb skill v1.5.0"
```

---

### Task 4: Repair the live knowledge base

**Files:**
- Modify: `/Users/shaopc/Documents/my-knowledge-base/20-Learning/Java/INDEX.md`
- Modify: `/Users/shaopc/Documents/my-knowledge-base/20-Learning/Docker/2026-07-08 OrbStack端口转发与SSH连接排查.md`

**Interfaces:**
- Consumes: remote `master` containing commits `00355eb` and `f5a6903` plus the updated auditor from Task 1.
- Produces: one canonical Java Folder Index block and compliant OrbStack tags.

- [ ] **Step 1: Preserve the plugin-only newline change and fast-forward local master**

Record the one-line `data.json` diff, restore only its final newline so the worktree is clean, fetch, and run `git merge --ff-only origin/master`. Do not use reset or checkout to discard unrelated changes.

- [ ] **Step 2: Confirm the baseline violations**

Run the updated auditor against the Vault.

Expected findings include:

```text
missing-folder-index-content  20-Learning/Java/INDEX.md
invalid-tag                  20-Learning/Docker/2026-07-08 OrbStack端口转发与SSH连接排查.md
too-many-tags                20-Learning/Docker/2026-07-08 OrbStack端口转发与SSH连接排查.md
```

- [ ] **Step 3: Restore Java Folder Index ownership**

Keep frontmatter, title, and description; replace the manual `## 笔记列表` section with:

````markdown
```folder-index-content
```
````

- [ ] **Step 4: Normalize OrbStack tags**

Use exactly five tags:

```yaml
tags: [web-clip, orbstack, ssh, port-forwarding, docker]
```

- [ ] **Step 5: Run strict Vault audit and verify GREEN**

Run: `/Users/shaopc/playground/obsidian-kb-skill/.venv/bin/python /Users/shaopc/playground/obsidian-kb-skill/scripts/audit_vault.py /Users/shaopc/Documents/my-knowledge-base --strict`

Expected: `0 finding(s)` and exit 0.

- [ ] **Step 6: Verify protected workspace state and commit only the two repairs**

Run: `git diff -- .obsidian/workspace.json`

Expected: no output.

```bash
git add 20-Learning/Java/INDEX.md "20-Learning/Docker/2026-07-08 OrbStack端口转发与SSH连接排查.md"
git commit -m "fix: 恢复 Folder Index 并规范 OrbStack 标签"
```

---

### Task 5: Final verification and publication

**Files:**
- Verify: `/Users/shaopc/playground/obsidian-kb-skill`
- Verify: `/Users/shaopc/Documents/my-knowledge-base`

**Interfaces:**
- Consumes: committed Skill v1.5.0 and committed Vault repairs.
- Produces: two remote `master` branches matching verified local commits.

- [ ] **Step 1: Verify the Skill repository from a clean state**

Run:

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/python build.py --check
git diff --check
git status --short --branch
```

Expected: all tests pass, adapters are current, no whitespace errors, and no uncommitted files.

- [ ] **Step 2: Verify the knowledge base from a clean state**

Run:

```bash
/Users/shaopc/playground/obsidian-kb-skill/.venv/bin/python /Users/shaopc/playground/obsidian-kb-skill/scripts/audit_vault.py /Users/shaopc/Documents/my-knowledge-base --strict
git diff --check
git status --short --branch
```

Expected: `0 finding(s)`, no whitespace errors, and no uncommitted files.

- [ ] **Step 3: Fetch and reject divergence before pushing**

In each repository run `git fetch origin master` and `git rev-list --left-right --count origin/master...master`.

Expected: remote-behind count is `0`; local-ahead count is positive. If both sides are positive, stop without merging.

- [ ] **Step 4: Push both verified master branches**

Run `git push origin master` in each repository.

- [ ] **Step 5: Verify remote commit identity**

Compare `git rev-parse master`, `git rev-parse origin/master`, and `git ls-remote origin refs/heads/master` in each repository.

Expected: all three hashes match and divergence is `0 0`.
