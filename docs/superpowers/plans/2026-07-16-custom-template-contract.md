# Custom Template Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make natural-language instructions in user-customized Vault templates govern note generation without adding template-body reads to unchanged-template captures.

**Architecture:** Add one shared `template_contract` module that normalizes, hashes, classifies, parses, and exposes conventional templates. Compact discovery reports only customized type slugs; the agent loads one full contract only for the selected custom type, and create-note uses an optional expected hash to reject stale contracts before mutation.

**Tech Stack:** Python 3.11+, argparse, PyYAML, hashlib, pytest, generated cross-platform Skill payloads.

## Global Constraints

- Do not support renamed template files in this release; record it only as deferred backlog.
- Do not require custom template markup, comments, or a DSL.
- Support only `{{date}}` and `{{title}}`; unknown placeholders fail contract loading.
- Preserve the unchanged-template helper path, except for the bounded `custom_templates` discovery field.
- Preserve existing merge precedence, structured preflight, exclusive apply, automatic audit, Git safety, and installer preservation of user templates.
- Do not introduce another semantic model.

---

### Task 1: Shared Template Inspection and Customization Detection

**Files:**
- Create: `obsidian_kb_skill/scripts/template_contract.py`
- Modify: `obsidian_kb_skill/scripts/note_types.py`
- Create: `tests/test_template_contract.py`

**Interfaces:**
- Produces: `normalize_template_text(text: str) -> str`.
- Produces: `template_sha256(text: str) -> str`.
- Produces: `inspect_template(vault: Path, note_type: str) -> dict[str, Any] | None`.
- Produces: `custom_template_types(vault: Path) -> list[str]`.
- Adds `TYPE_TO_TEMPLATE_ASSET: dict[str, str]` beside the existing fixed Vault filename map.

- [ ] **Step 1: Write failing classification tests**

Create tests proving shipped Chinese and English templates classify as standard, BOM/CRLF/final-newline differences remain standard, a changed instruction marks only its type custom, and a missing conventional file is omitted:

```python
def test_changed_instruction_marks_only_one_template_custom(tmp_path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(target.read_text() + "\n必须给出风险。\n", encoding="utf-8")

    assert custom_template_types(vault) == ["web-clip"]
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_template_contract.py -q`

Expected: collection fails because `template_contract` and `TYPE_TO_TEMPLATE_ASSET` do not exist.

- [ ] **Step 3: Implement normalization, hashing, and classification**

Normalize only BOM, line endings, and final newline. Resolve shipped assets through `resource_locator.template_dir()`, compare against both the root Chinese asset and `en/` variant, and preserve fixed filename lookup.

- [ ] **Step 4: Parse one contract and validate placeholders**

`inspect_template` returns relative path, normalized SHA-256, parsed frontmatter, complete body, `customized`, supported placeholders, and sorted unknown placeholders. YAML errors carry source, full-Markdown line, column, and message.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest tests/test_template_contract.py tests/test_user_template.py -q`

Expected: all tests pass.

Commit:

```bash
git add obsidian_kb_skill/scripts/template_contract.py obsidian_kb_skill/scripts/note_types.py tests/test_template_contract.py
git commit -m "feat: classify customized Vault templates"
```

### Task 2: Compact Discovery and Template Contract CLI

**Files:**
- Modify: `obsidian_kb_skill/scripts/vault_info.py`
- Modify: `obsidian_kb_skill/scripts/template_contract.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_vault_info.py`
- Modify: `tests/test_json_output.py`

**Interfaces:**
- Extends every `vault-info` result with `custom_templates: list[str]`.
- Produces CLI: `template-contract <vault> --type <slug> --json`.
- Produces console entry point: `obsidian-template-contract`.

- [ ] **Step 1: Write failing discovery and CLI tests**

Assert compact discovery reports custom type slugs but no template body, and the CLI returns exactly one contract with body and SHA. Add error tests for unsupported type, malformed YAML, and unknown placeholders; each error must exit 2 and include a stable `error.code`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_vault_info.py tests/test_json_output.py -q`

Expected: failures because `custom_templates` and the CLI are absent.

- [ ] **Step 3: Add bounded discovery field**

Call `custom_template_types(vault)` once from `collect()`. Keep compact projection limited to removing index `notes`; never place template bodies in discovery.

- [ ] **Step 4: Add read-only contract CLI**

Implement argparse for Vault and type, validate the Vault root, print the contract as JSON, and return structured errors:

```json
{"error":{"code":"unknown-template-placeholder","placeholders":["project"]}}
```

Do not write files.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest tests/test_template_contract.py tests/test_vault_info.py tests/test_json_output.py -q`

Commit:

```bash
git add obsidian_kb_skill/scripts/template_contract.py obsidian_kb_skill/scripts/vault_info.py pyproject.toml tests/test_vault_info.py tests/test_json_output.py
git commit -m "feat: expose custom template contracts"
```

### Task 3: Reject Stale Template Contracts in Create Note

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Modify: `tests/test_create_note.py`
- Modify: `tests/test_json_output.py`

**Interfaces:**
- Adds optional create-note flag `--expect-template-sha256 <64-lowercase-hex>`.
- Produces structured error code `template-changed` with `expected_sha256` and `actual_sha256`.

- [ ] **Step 1: Write failing preflight and apply tests**

Retrieve a contract hash, modify the template, then invoke preflight and apply with the stale hash. Assert exit 2, structured error, and no note/index mutation. Add a matching-hash test proving normal preflight succeeds.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run pytest \
  tests/test_create_note.py::test_preflight_rejects_stale_template_sha256_without_mutation \
  tests/test_create_note.py::test_apply_rejects_stale_template_sha256_without_mutation \
  tests/test_create_note.py::test_preflight_accepts_current_template_sha256 -q
```

Expected: failures because the flag is unknown.

- [ ] **Step 3: Implement the hash gate**

Validate the argument shape with argparse. After Vault validation and before build/write, hash the current conventional template with the shared normalization. Missing or changed templates produce `template-changed`; the check is optional for backward compatibility.

- [ ] **Step 4: Verify GREEN and regressions**

Run: `uv run pytest tests/test_create_note.py tests/test_json_output.py tests/test_user_template.py -q`

- [ ] **Step 5: Commit**

```bash
git add obsidian_kb_skill/scripts/create_note.py tests/test_create_note.py tests/test_json_output.py
git commit -m "feat: reject stale template contracts"
```

### Task 4: Package the Helper and Define the Agent Workflow

**Files:**
- Modify: `skills/obsidian-knowledge-base/scripts/run_helper.py`
- Modify: `obsidian_kb_skill/scripts/doctor.py`
- Modify: `core/references/note-creation.md`
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_lazy_references.py`
- Modify: `tests/test_doctor.py`
- Modify: `tests/test_wheel_install.py`
- Regenerate: `skills/obsidian-knowledge-base/**`
- Regenerate: `platforms/**`
- Regenerate: `obsidian_kb_skill/scripts/resources/**`

**Interfaces:**
- Runner dispatches `template-contract` to `obsidian_kb_skill.scripts.template_contract`.
- Doctor requires `template_contract` in the installed payload.
- Ordinary reference loads the contract only when selected type appears in `custom_templates`.

- [ ] **Step 1: Write failing packaging and reference tests**

Add `template-contract` to runtime helper expectations and hostile-cwd coverage. Assert the reference contains the natural-language interpretation rules, conditional call, expected-hash flag, internal coverage pass, and explicit renamed-template non-goal.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_skill_runtime.py tests/test_lazy_references.py tests/test_doctor.py tests/test_wheel_install.py -q`

Expected: failures because the helper and workflow are not packaged.

- [ ] **Step 3: Update runner, doctor, and source reference**

Add the helper registration and concise conditional workflow. State that instructions are executed but not copied, structural scaffolds are preserved and filled, examples guide format/depth, and material ambiguity stops before apply.

- [ ] **Step 4: Regenerate and verify GREEN**

Run:

```bash
uv run python build.py
uv run pytest tests/test_skill_runtime.py tests/test_lazy_references.py tests/test_doctor.py tests/test_wheel_install.py -q
uv run python build.py --check
```

- [ ] **Step 5: Commit**

```bash
git add core obsidian_kb_skill platforms skills tests
git commit -m "docs: apply customized template contracts"
```

### Task 5: Forward Test Quality and Verify the Product

**Files:**
- Modify only if a forward-test failure requires a tested correction in the files above.

**Interfaces:**
- Validates the installed-product behavior from a neutral or hostile current directory.

- [ ] **Step 1: Create a temporary custom Web Clip template**

Use natural Markdown containing an instruction below `## 风险评估` and a list/table scaffold. Confirm compact discovery reports only `web-clip` and contract output contains the complete instruction.

- [ ] **Step 2: Generate a representative note against the contract**

Produce explicit Markdown that executes the instruction without copying it, preserves and fills the scaffold, and passes `--expect-template-sha256` preflight and compact apply audit.

- [ ] **Step 3: Prove stale protection**

Change the template after preflight and confirm apply with the old hash returns `template-changed` without creating a note.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run pytest -q
uv run python build.py --check
uv lock --check
uv build
```

Then run installed runner doctor, compact discovery, and template-contract smoke tests from a hostile cwd.

- [ ] **Step 5: Review scope and prepare PR**

Confirm renamed-template support is absent from runtime code and remains only in the design backlog. Review `master...HEAD`, fix Critical/Important findings with tests, push the feature branch, and open a ready PR with verification evidence.
