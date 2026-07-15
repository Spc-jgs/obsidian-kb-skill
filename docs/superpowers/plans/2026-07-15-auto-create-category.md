# Automatic Category Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-confirmed, deterministic helper that initializes one missing Vault category and its governed index without changing the ordinary existing-category note path.

**Architecture:** A focused `create_category.py` module owns path validation, index-mode selection, planning, rendering, apply cleanup, and post-apply audit. The installed runner and wheel expose it as `create-category`; the lazy note-creation reference teaches the agent when to ask for naming and route-persistence decisions. Governance prose remains model-edited and user-confirmed rather than helper-parsed.

**Tech Stack:** Python 3.11+, `pathlib`, `argparse`, PyYAML, pytest, existing Vault path/index helpers, Markdown skill references, deterministic build/install scripts.

## Global Constraints

- A new category is one missing child below an existing governed note folder; recursive parent creation is forbidden.
- The user must approve the final category path before mutation; `--apply` requires `--confirmed`.
- Updating `AGENTS.md` is an independent user choice and is never performed by the helper.
- Existing categories add no prompt or helper call to ordinary note creation.
- Folder Index, Dataview, and static ownership rules remain authoritative.
- No semantic model, network call, new runtime dependency, arbitrary governance parser, category rename/merge/delete, or normal `create-note` contract change.
- Use TDD: every production behavior begins with a focused failing test.

---

### Task 1: Category planning and index rendering

**Files:**
- Create: `obsidian_kb_skill/scripts/create_category.py`
- Create: `obsidian_kb_skill/scripts/index_templates.py`
- Create: `tests/test_create_category.py`

**Interfaces:**
- Consumes: `FolderIndexConfig`, `_folder_index_config(vault)`, `expected_folder_index(folder, vault, config)`, `detect(vault, folder)`, and Vault path validators.
- Produces: `CategoryPlan`, `plan_category(vault: Path, folder: str) -> CategoryPlan`, `render_category_index(plan: CategoryPlan) -> str`, and focused renderers `render_folder_index(name: str) -> str`, `render_dataview_index(name: str, folder: Path) -> str`, and `render_static_index(name: str) -> str` in `index_templates.py`.

- [ ] **Step 1: Write failing planning and rendering tests**

Add tests that import the not-yet-created module and assert:

```python
def test_plans_native_folder_index(vault_with_folder_index):
    plan = plan_category(vault_with_folder_index, "20-Learning/Rust")
    assert plan.folder == Path("20-Learning/Rust")
    assert plan.parent == Path("20-Learning")
    assert plan.index_mode == "folder-index"
    assert plan.index_path == Path("20-Learning/Rust/Rust.md")
    assert plan.planned_changes == (
        PlannedChange("directory", Path("20-Learning/Rust")),
        PlannedChange("index", Path("20-Learning/Rust/Rust.md")),
    )

def test_renders_one_folder_index_content_block(vault_with_folder_index):
    text = render_category_index(
        plan_category(vault_with_folder_index, "20-Learning/Rust")
    )
    assert "type: folder-index" in text
    assert "# Rust" in text
    assert text.count("```folder-index-content") == 1
```

Cover a custom Folder Index filename, parent Dataview fallback, static fallback,
and an existing destination reported as `already_exists=True` with no planned
changes.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_create_category.py -v`

Expected: collection fails with `ModuleNotFoundError: obsidian_kb_skill.scripts.create_category`.

- [ ] **Step 3: Implement the minimal planner and renderer**

Create immutable dataclasses with exact fields:

```python
@dataclass(frozen=True)
class PlannedChange:
    kind: str
    path: Path

@dataclass(frozen=True)
class CategoryPlan:
    vault: Path
    folder: Path
    parent: Path
    category: str
    exists: bool
    index_mode: str
    index_path: Path
    planned_changes: tuple[PlannedChange, ...]
    governance_reminders: tuple[str, ...]
    warnings: tuple[str, ...]
```

`plan_category` resolves only the existing Vault and parent, selects Folder
Index unless excluded, otherwise inherits Dataview from the parent's detected
index and falls back to static. `render_category_index` emits exactly one
folder-index block, a same-folder Dataview query, or a static MOC heading.
Keep index text generation in `index_templates.py`; the CLI only selects a
mode and calls the matching renderer. Assert structural equivalence with the
installer's established Folder Index/Dataview/static outputs so the two paths
cannot drift unnoticed.

- [ ] **Step 4: Run tests and refactor while green**

Run: `.venv/bin/python -m pytest tests/test_create_category.py tests/test_detect_index.py tests/test_audit_vault.py -v`

Expected: all selected tests pass with no warnings.

- [ ] **Step 5: Commit the planning slice**

```bash
git add obsidian_kb_skill/scripts/create_category.py obsidian_kb_skill/scripts/index_templates.py tests/test_create_category.py
git commit -m "feat: plan governed category creation"
```

### Task 2: CLI validation, confirmed apply, cleanup, and audit

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_category.py`
- Modify: `tests/test_create_category.py`
- Modify: `tests/test_json_output.py`

**Interfaces:**
- Consumes: Task 1 `CategoryPlan`, `plan_category`, and `render_category_index`.
- Produces: `apply_category(plan: CategoryPlan) -> ApplyResult`, `audit_category(plan: CategoryPlan) -> list[Finding]`, `result_payload(...) -> dict[str, Any]`, and `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing validation and CLI tests**

Add parameterized failures for absolute paths, `..`, symlink escape, Vault root,
missing parent, two missing components, reserved paths, invalid/control names,
file/symlink collisions, and `--apply` without `--confirmed`. Each asserts exit
2, a stable error code, and no created destination.

Add successful preflight and apply tests:

```python
def test_preflight_json_is_read_only(tmp_path, capsys):
    vault = make_vault(tmp_path, folder_index=True)
    assert main([str(vault), "--folder", "20-Learning/Rust", "--preflight-json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["planned_changes"][0]["kind"] == "directory"
    assert payload["index"]["path"] == "20-Learning/Rust/Rust.md"
    assert not (vault / "20-Learning/Rust").exists()

def test_apply_requires_confirmation(tmp_path):
    vault = make_vault(tmp_path, folder_index=True)
    assert main([str(vault), "--folder", "20-Learning/Rust", "--apply"]) == 2
    assert not (vault / "20-Learning/Rust").exists()

def test_confirmed_apply_creates_and_audits(tmp_path, capsys):
    vault = make_vault(tmp_path, folder_index=True)
    assert main([str(vault), "--folder", "20-Learning/Rust", "--apply", "--confirmed", "--compact-json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is True
    assert payload["audit"] == []
    assert (vault / "20-Learning/Rust/Rust.md").is_file()
```

Use a patched index writer to prove a failed index write removes only the new
empty directory. Prove an existing directory/index is unchanged byte-for-byte.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_create_category.py tests/test_json_output.py -k 'category' -v`

Expected: failures because CLI/apply/audit interfaces do not exist.

- [ ] **Step 3: Implement validation and apply**

Use `validate_vault_root`, lexical component checks, `resolve_existing_within_vault`
for the parent, and `resolve_target_within_vault` for containment. Return stable
codes such as `invalid-category-path`, `missing-category-parent`,
`reserved-category-path`, `category-collision`, and `confirmation-required`.

Implement read-only default plus `--preflight-json`, `--apply`, `--confirmed`,
`--json`, and `--compact-json`. Render index content before mutation. Create the
directory exclusively, create the index with `open("xb")`, remove only a newly
created empty directory on write failure, then audit expected path and index
structure. Never overwrite or repair an existing category.

- [ ] **Step 4: Run focused and neighboring tests**

Run: `.venv/bin/python -m pytest tests/test_create_category.py tests/test_json_output.py tests/test_create_note.py tests/test_process_inbox.py -v`

Expected: all selected tests pass; existing `create-note` behavior is unchanged.

- [ ] **Step 5: Commit the CLI slice**

```bash
git add obsidian_kb_skill/scripts/create_category.py tests/test_create_category.py tests/test_json_output.py
git commit -m "feat: create confirmed Vault categories"
```

### Task 3: Installed helper and distribution integration

**Files:**
- Modify: `pyproject.toml`
- Modify: `obsidian_kb_skill/scripts/doctor.py`
- Modify: `skills/obsidian-knowledge-base/scripts/run_helper.py`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_wheel_install.py`
- Modify: `tests/test_build.py`
- Generated: `skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/**`
- Generated: `skills/obsidian-knowledge-base/manifest.json`

**Interfaces:**
- Consumes: `obsidian_kb_skill.scripts.create_category:main`.
- Produces: wheel command `obsidian-create-category` and installed runner dispatch token `create-category`.

- [ ] **Step 1: Write failing packaging and installed-runtime tests**

Add `create-category` to the expected helper tuples, assert doctor imports
`create_category`, assert the wheel exposes `obsidian-create-category`, and run
installed `run_helper.py create-category <vault> --folder 20-Learning/Rust
--preflight-json` from a hostile working directory. Assert the source checkout
cannot be borrowed through `PYTHONPATH`.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_skill_runtime.py tests/test_doctor.py tests/test_wheel_install.py tests/test_build.py -k 'helper or category or console' -v`

Expected: failures identify the absent dispatch/module/entry point.

- [ ] **Step 3: Wire the helper into every distribution surface**

Add:

```toml
obsidian-create-category = "obsidian_kb_skill.scripts.create_category:main"
```

Add `"create-category": "obsidian_kb_skill.scripts.create_category"` to the
installed runner and `"create_category"` to doctor imports. Run
`.venv/bin/python build.py` to regenerate standard Skill payloads and manifest;
do not hand-edit generated Python copies.

- [ ] **Step 4: Run installed-runtime tests**

Run: `.venv/bin/python -m pytest tests/test_skill_runtime.py tests/test_doctor.py tests/test_wheel_install.py tests/test_build.py -v`

Expected: all pass, including hostile-cwd and wheel entry-point tests.

- [ ] **Step 5: Commit distribution integration**

```bash
git add pyproject.toml obsidian_kb_skill/scripts/doctor.py skills/obsidian-knowledge-base tests
git commit -m "feat: package the category creation helper"
```

### Task 4: Skill behavior guidance with instruction TDD

**Files:**
- Modify: `core/references/note-creation.md`
- Modify: `tests/test_lazy_references.py`
- Generated: `skills/obsidian-knowledge-base/references/note-creation.md`
- Generated: `platforms/claude-code/CLAUDE.md`
- Generated: `platforms/codex/AGENTS.md`
- Generated: `platforms/cursor/obsidian-kb.mdc`
- Generated: standard Skill payload and manifest

**Interfaces:**
- Consumes: installed `create-category` contract from Task 3.
- Produces: exceptional-path agent behavior for missing categories while preserving the minimal ordinary path.

- [ ] **Step 1: Add failing instruction contract tests**

Before editing the reference, assert that the canonical workflow contains all
of these protected behaviors:

```python
assert "category path" in text
assert "rename" in text
assert "whether to update `AGENTS.md`" in text
assert "--apply --confirmed --compact-json" in text
assert "one-off category" in text
assert "Existing governed categories" in text
assert "README" in text
```

Also assert the ordinary minimal path still names only `vault-info`,
`create-note --preflight-json`, and `create-note --apply --compact-json`; it must
not make `create-category` an unconditional step.

- [ ] **Step 2: Run the instruction tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_lazy_references.py -k 'category or ordinary' -v`

Expected: new category-behavior assertions fail against the current reference.

- [ ] **Step 3: Add the minimal exceptional-path recipe**

Add a compact conditional section after folder selection:

```markdown
### Missing category exception

If a clear stable topic has no governed category, propose one Vault-relative
path and tell the user they may rename it. In the same confirmation, record a
separate answer for whether to minimally update the applicable `AGENTS.md`.
Do not mutate before the path is confirmed. Then preflight and apply
`create-category` with `--confirmed`, perform other Vault-required structural
edits such as README maintenance, and continue the ordinary `create-note`
path. If route persistence is declined, call it a one-off category and ask
again next time. Existing governed categories skip this entire exception.
```

Because the repository session cannot dispatch evaluation subagents under the
active team constraint, use executable instruction contract tests here and
reserve a real installed WorkBuddy forward run for the release gate.

- [ ] **Step 4: Regenerate and verify instruction footprint**

Run:

```bash
.venv/bin/python build.py
.venv/bin/python -m pytest tests/test_lazy_references.py tests/test_build.py -v
.venv/bin/python - <<'PY'
from pathlib import Path
text = Path('core/references/note-creation.md').read_text()
print(len(text.split()), len(text.splitlines()))
PY
```

Expected: tests pass; generated copies match; the new section is conditional
and does not alter the ordinary step count.

- [ ] **Step 5: Commit the instruction slice**

```bash
git add core/references/note-creation.md tests/test_lazy_references.py skills platforms
git commit -m "docs: guide confirmed category creation"
```

### Task 5: Version, documentation, full verification, and PR

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: version assertions in `tests/test_build.py`, `tests/test_doctor.py`, and `tests/test_installers.py`
- Generated: all platform adapters and standard Skill manifest

**Interfaces:**
- Produces: release candidate `1.16.0` with synchronized source, generated payload, wheel, and installed runtime.

- [ ] **Step 1: Write failing release metadata assertions**

Change version tests to expect `1.16.0` and a `2026-07-15` changelog entry that
documents user-confirmed naming, optional `AGENTS.md` persistence, governed
index initialization, and zero ordinary-path overhead.

- [ ] **Step 2: Run version tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_doctor.py tests/test_installers.py -k 'version or release' -v`

Expected: failures still report `1.15.1`.

- [ ] **Step 3: Update release metadata and user documentation**

Set every source-of-truth version to `1.16.0`, run `uv lock --upgrade-package
obsidian-kb-skill`, document the new helper and interaction in both READMEs and
CHANGELOG, then run `.venv/bin/python build.py`.

- [ ] **Step 4: Run complete source and artifact verification**

Run:

```bash
.venv/bin/python -m pytest
.venv/bin/python build.py --check
uv lock --check
.venv/bin/python /Users/shaopc/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/obsidian-knowledge-base
.venv/bin/python -m build
```

Expected: full pytest passes; build, lock, and Skill validation pass; wheel and
sdist build without `.DS_Store` or generated-cache files.

- [ ] **Step 5: Verify installed runtime and real workflow**

Install Codex and WorkBuddy with the repository installer, run both doctors,
compare manifest and helper hashes, then use the installed WorkBuddy runner in
a temporary Vault to preflight/apply a category, write the first note, and
verify a second note uses ordinary `create-note` without category initialization.

- [ ] **Step 6: Commit, push, and open the PR**

```bash
git add .
git commit -m "release: prepare v1.16.0"
git push -u origin feature/auto-create-category
gh pr create --base master --head feature/auto-create-category \
  --title "feat: create missing Vault categories safely" \
  --body "Adds a confirmed create-category helper, governed index initialization, optional AGENTS.md route persistence, and no overhead for existing-category note creation."
```

Expected: clean branch, ready PR, and CI started. Merge and release only after
all required GitHub checks pass.
