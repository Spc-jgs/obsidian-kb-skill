# Standard Skill Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `obsidian-knowledge-base` as a complete standard Skill whose installed copy remains usable without the source checkout, then repair the runtime contract gaps found by installed-product testing and release v1.11.0.

**Architecture:** `skills/obsidian-knowledge-base/` becomes the canonical payload with `SKILL.md`, `agents/`, `references/`, `scripts/`, and `assets/`. `build.py` exactly mirrors core references/templates and the helper package into that payload; both installers copy that tree and configure a private PyYAML vendor directory used by one Skill-local helper launcher.

**Tech Stack:** Python 3.11+, Bash, Windows PowerShell 5.1+, setuptools, PyYAML, pytest, GitHub Actions.

## Global Constraints

- Installed helpers must work after the release/source directory is deleted.
- Codex and QoderWork receive the complete canonical payload; Claude Code and Cursor use the canonical support copy at `~/.obsidian-kb-skill/skill/`.
- The installer must not modify global Python site-packages or shell profiles.
- Vault templates remain user-owned and are overwritten only by explicit `--force` / `-Force`.
- Uninstall preserves the Vault, sibling skills, and `~/.obsidian-kb-config` unless config purge is explicitly requested.
- Marker validation, update backups, and other runtime repairs use separate commits from the installer distribution change.
- Release version is `1.11.0`; do not move the `v1.10.0` tag.

---

### Task 1: Build a Complete Canonical Skill Payload

**Files:**
- Modify: `build.py`
- Modify: `tests/test_build.py`
- Create: `skills/obsidian-knowledge-base/agents/openai.yaml`
- Create: `skills/obsidian-knowledge-base/scripts/run_helper.py`
- Generate: `skills/obsidian-knowledge-base/assets/templates/**`
- Generate: `skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/**`

**Interfaces:**
- Consumes: `core/references/`, `core/templates/`, and `obsidian_kb_skill/`.
- Produces: `sync_exact_tree(src: Path, dst: Path, *, exclude: Callable[[Path], bool]) -> None`, `tree_drift(src: Path, dst: Path, *, exclude: Callable[[Path], bool]) -> list[str]`, and the canonical payload tree used by both installers.

- [ ] **Step 1: Write failing build-contract tests**

Add tests that require the standard Skill anatomy and exact generated-tree checks:

```python
def test_standard_skill_has_required_resource_directories():
    root = ROOT / "skills/obsidian-knowledge-base"
    assert (root / "SKILL.md").is_file()
    assert (root / "agents/openai.yaml").is_file()
    assert (root / "references/note-creation.md").is_file()
    assert (root / "scripts/run_helper.py").is_file()
    assert (root / "scripts/obsidian_kb_skill/scripts/create_note.py").is_file()
    assert (root / "assets/templates/digest-note.md").is_file()


def test_generated_tree_drift_reports_missing_changed_and_extra(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir(); dst.mkdir()
    (src / "same.md").write_text("same", encoding="utf-8")
    (src / "changed.md").write_text("new", encoding="utf-8")
    (src / "missing.md").write_text("missing", encoding="utf-8")
    (dst / "same.md").write_text("same", encoding="utf-8")
    (dst / "changed.md").write_text("old", encoding="utf-8")
    (dst / "extra.md").write_text("extra", encoding="utf-8")
    assert build.tree_drift(src, dst, exclude=lambda _: False) == [
        "changed: changed.md", "extra: extra.md", "missing: missing.md"
    ]
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_build.py -q`

Expected: FAIL because the standard resource directories and exact-tree helpers do not exist.

- [ ] **Step 3: Implement exact tree synchronization and payload generation**

In `build.py`, compare relative file maps, remove stale generated files during normal builds, and append every drift item during `--check`. Exclude `.DS_Store`, `__pycache__`, `*.pyc`, package `scripts/resources/`, and installer-created `vendor/`/runtime metadata from the Skill helper copy.

Generate `agents/openai.yaml` deterministically with the Skill Creator helper:

```bash
python /Users/shaopc/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  skills/obsidian-knowledge-base \
  --interface 'display_name=Obsidian Knowledge Base' \
  --interface 'short_description=Save and govern notes in a local Obsidian vault' \
  --interface 'default_prompt=Use $obsidian-knowledge-base to save this into my Obsidian vault.'
```

The generated file contains only:

```yaml
interface:
  display_name: "Obsidian Knowledge Base"
  short_description: "Save and govern notes in a local Obsidian vault"
  default_prompt: "Use $obsidian-knowledge-base to save this into my Obsidian vault."
```

Create `scripts/run_helper.py` with the stable command map:

```python
HELPERS = {
    "audit-vault": "obsidian_kb_skill.scripts.audit_vault",
    "process-inbox": "obsidian_kb_skill.scripts.process_inbox",
    "suggest-links": "obsidian_kb_skill.scripts.suggest_links",
    "create-note": "obsidian_kb_skill.scripts.create_note",
    "update-note": "obsidian_kb_skill.scripts.update_note",
    "vault-info": "obsidian_kb_skill.scripts.vault_info",
    "detect-index": "obsidian_kb_skill.scripts.detect_index",
    "scaffold-templates": "obsidian_kb_skill.scripts.scaffold_templates",
}
```

The full launcher execution behavior is completed in Task 2; Task 1 establishes the file and mapping so the payload build is independently testable.

- [ ] **Step 4: Build and verify the payload**

Run:

```bash
.venv/bin/python build.py
.venv/bin/python build.py --check
.venv/bin/python -m pytest tests/test_build.py -q
```

Expected: all commands exit 0 and `skills/obsidian-knowledge-base/` has the required anatomy without `.DS_Store` or `__pycache__`.

- [ ] **Step 5: Commit the canonical payload**

```bash
git add build.py tests/test_build.py skills/obsidian-knowledge-base
git commit -m "feat(skill): build a complete standard payload"
```

### Task 2: Make the Bundled Helper Launcher and Resource Contract Work

**Files:**
- Modify: `skills/obsidian-knowledge-base/scripts/run_helper.py`
- Modify: `obsidian_kb_skill/scripts/resource_locator.py`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `core/references/note-creation.md`
- Modify: `core/references/rules-and-errors.md`
- Modify: `core/references/task-memory.md`
- Modify: `tests/test_lazy_references.py`
- Modify: `tests/test_cli_integration.py`
- Modify: `tests/test_templates.py`

**Interfaces:**
- Consumes: `~/.obsidian-kb-skill/runtime.json`, optional `~/.obsidian-kb-skill/vendor/`, and the canonical Skill root.
- Produces: `python_command() -> list[str]`, `helper_environment() -> dict[str, str]`, runner CLI `run_helper.py HELPER [ARGS...]`, and explicit resource-root support for `assets/templates/` plus `references/`.

- [ ] **Step 1: Write failing runner and resource-root tests**

Add a subprocess test that copies the standard Skill into a temporary directory, writes a runtime record using the test interpreter, empties `PYTHONPATH`, runs from another directory, and requires `vault-info --json` to succeed. Add resource-locator tests requiring this shape:

```text
skill-root/assets/templates/
skill-root/references/
```

Also assert generated references contain `scripts/run_helper.py vault-info` and no command matching `python scripts/*.py`.

- [ ] **Step 2: Run targeted tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_lazy_references.py tests/test_cli_integration.py tests/test_templates.py -q`

Expected: FAIL because the launcher is not functional and the resource locator only accepts `templates/` at the root.

- [ ] **Step 3: Implement the launcher**

Parse `~/.obsidian-kb-skill/runtime.json` as:

```json
{"schema_version": 1, "python": ["/absolute/path/to/python"]}
```

Fall back to `[sys.executable]` when the record is absent. Build `PYTHONPATH` in this order:

1. `<skill-root>/scripts`
2. `~/.obsidian-kb-skill/vendor` when present
3. the caller's existing `PYTHONPATH`

Set `OBSIDIAN_KB_SKILL_ROOT=<skill-root>` and execute:

```python
subprocess.run([*python, "-m", HELPERS[name], *args], env=env).returncode
```

Reject an unknown helper through `argparse` with exit code 2.

- [ ] **Step 4: Align resource lookup and instructions**

Make an explicit Skill root resolve templates from `assets/templates/` and references from `references/`. Preserve support for the legacy development root containing `templates/` and `references/` only where tests require it.

Replace direct `python scripts/*.py` instructions with the stable installed form:

```text
python <skill-root>/scripts/run_helper.py <helper-name> ...
```

State that `<skill-root>` is the directory containing the active `SKILL.md`; compatibility adapters use `~/.obsidian-kb-skill/skill`.

- [ ] **Step 5: Rebuild and verify GREEN**

Run:

```bash
.venv/bin/python build.py
.venv/bin/python build.py --check
.venv/bin/python -m pytest tests/test_lazy_references.py tests/test_cli_integration.py tests/test_templates.py -q
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit the installed helper contract**

```bash
git add core obsidian_kb_skill/scripts/resource_locator.py skills platforms tests/test_lazy_references.py tests/test_cli_integration.py tests/test_templates.py build.py
git commit -m "feat(skill): run bundled helpers from the installed payload"
```

### Task 3: Close the Bash Installer Lifecycle

**Files:**
- Modify: `install.sh`
- Rewrite/extend: `tests/test_installers.py`

**Interfaces:**
- Consumes: canonical payload `skills/obsidian-knowledge-base/` and `OBSIDIAN_KB_PYTHON` override.
- Produces: exact payload copies, `~/.obsidian-kb-skill/runtime.json`, private `vendor/`, `--purge-config`, canonical Vault config, and post-install helper verification.

- [ ] **Step 1: Write failing Bash black-box tests**

Build a disposable release tree containing only installer inputs, install into a temporary `HOME`, delete the release tree, clear `PYTHONPATH`, and assert:

```python
assert installed_payload_files(home / ".agents/skills/obsidian-knowledge-base") == source_payload_files()
assert json.loads(run_installed("vault-info", vault, "--json").stdout)["valid"] is True
assert (home / ".obsidian-kb-skill/skill/references/note-creation.md").is_file()
```

Add tests for Qoder parity, Digest template parity, relative Vault canonicalization, unknown-platform failure, stale-owned-file removal on upgrade, missing-file restoration, preservation of edited Vault templates, default config preservation on uninstall, explicit config purge, sibling-skill preservation, and Vault preservation.

- [ ] **Step 2: Run installer tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_installers.py -q`

Expected: FAIL because only `SKILL.md` is copied and no installed runtime exists.

- [ ] **Step 3: Implement Python selection and private dependency setup**

Select the interpreter in this order:

1. `OBSIDIAN_KB_PYTHON`
2. `python3`
3. `python`

Require `sys.version_info >= (3, 11)`, resolve the executable path, and write `runtime.json`. Test `import yaml` with `PYTHONPATH=~/.obsidian-kb-skill/vendor`; if it fails, run:

```bash
"$PYTHON_BIN" -m pip install --disable-pip-version-check --target "$HOME/.obsidian-kb-skill/vendor" "PyYAML>=6"
```

Fail with a direct remediation message when Python or pip is unusable.

- [ ] **Step 4: Implement exact payload copying and installer verification**

Refresh the product-owned destination before copying, exclude `header.md`, `.DS_Store`, `__pycache__`, and runtime artifacts, and always create the canonical support copy. Copy the complete payload for Codex and QoderWork. Validate platform names before mutating the Vault.

After installation, require the canonical reference file and run:

```bash
"$PYTHON_BIN" "$HOME/.obsidian-kb-skill/skill/scripts/run_helper.py" vault-info "$VAULT_PATH" --json
```

from a temporary neutral directory.

- [ ] **Step 5: Implement lifecycle safety**

Canonicalize the Vault after creating it with `cd -P`. Preserve config on default uninstall, add `--purge-config`, remove `~/.obsidian-kb-skill/`, and continue preserving the Vault and siblings.

- [ ] **Step 6: Verify Bash lifecycle GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_installers.py -q
bash -n install.sh
```

Expected: all tests pass and Bash syntax validation exits 0.

- [ ] **Step 7: Commit Bash installer closure**

```bash
git add install.sh tests/test_installers.py
git commit -m "feat(installer): ship a complete Bash skill runtime"
```

### Task 4: Implement PowerShell Parity and Windows Execution Proof

**Files:**
- Modify: `install.ps1`
- Create: `tests/windows_installer_smoke.ps1`
- Modify: `.github/workflows/check.yml`
- Modify: `tests/test_installers.py`

**Interfaces:**
- Consumes: the same canonical payload and `OBSIDIAN_KB_PYTHON` override as Bash.
- Produces: behaviorally equivalent PowerShell install, upgrade, verification, uninstall, and purge operations.

- [ ] **Step 1: Replace string-presence tests with parity-contract tests**

Keep only portable source checks locally: PowerShell exposes `-PurgeConfig`, includes `digest-note.md` through directory copying rather than a template map, references the canonical support root, and contains no platform-specific resource list. Put behavioral assertions in `tests/windows_installer_smoke.ps1`.

- [ ] **Step 2: Implement PowerShell payload/runtime parity**

Mirror Bash behavior using `Copy-Item`, `ConvertTo-Json`, `Get-Command`, and `[System.IO.Path]::GetFullPath`. Support interpreter commands as an array in `runtime.json`; use `python`, `python3`, then `py -3` when no override is given. Run the installed launcher for post-install verification.

- [ ] **Step 3: Add the Windows CI job**

Add `windows-installer` on `windows-latest`, set up Python 3.11, install the locked or minimum test dependencies, run `python build.py --check`, execute `tests/windows_installer_smoke.ps1`, and run the Python test suite once on Windows.

- [ ] **Step 4: Verify what is locally provable**

Run:

```bash
.venv/bin/python -m pytest tests/test_installers.py -q
.venv/bin/python build.py --check
```

Expected: all local tests pass. Full PowerShell execution remains a release gate satisfied by pushed Windows CI.

- [ ] **Step 5: Commit PowerShell parity**

```bash
git add install.ps1 tests/windows_installer_smoke.ps1 tests/test_installers.py .github/workflows/check.yml
git commit -m "feat(installer): verify PowerShell runtime parity"
```

### Task 5: Repair Marker and Update Safety in Separate Commits

**Files:**
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `tests/test_installers.py`
- Modify: `obsidian_kb_skill/scripts/update_note.py`
- Modify: `tests/test_update_note.py`

**Interfaces:**
- Produces: fail-closed marker validation and `backup_note(vault: Path, note: Path, now: datetime | None = None) -> Path`.

- [ ] **Step 1: Write malformed-marker regression tests**

Cover lone begin, lone end, reversed markers, and two complete blocks. Snapshot the shared file bytes, run install/uninstall, require nonzero exit, and assert the bytes are unchanged.

- [ ] **Step 2: Run the malformed-marker tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_installers.py -k malformed -q`

Expected: FAIL because current marker replacement can discard content after an unmatched begin marker.

- [ ] **Step 3: Implement fail-closed marker validation and commit**

Count exact begin/end lines and require either zero of both or exactly one ordered pair before replacement/removal. Emit a recovery message naming the target file and make no write on failure.

```bash
git add install.sh install.ps1 tests/test_installers.py
git commit -m "fix(installer): fail closed on malformed marker blocks"
```

- [ ] **Step 4: Write update-backup regression tests**

Use a fixed timestamp, update an existing note, and assert the backup bytes equal the original bytes, nested relative paths are preserved, the updated note changed, and JSON output contains the Vault-relative backup path. Also assert dry-run creates no backup.

- [ ] **Step 5: Run update tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_update_note.py -q`

Expected: FAIL because `update_note.py` currently creates no backup.

- [ ] **Step 6: Implement backup-before-write and commit**

Resolve the note within the canonical Vault, create
`.obsidian-kb-backups/YYYY-MM-DD-HHMMSS/<note-relative-path>`, copy bytes before replacing the original, and include `backup` in text/JSON results. On backup failure, abort without modifying the note.

```bash
git add obsidian_kb_skill/scripts/update_note.py tests/test_update_note.py
git commit -m "fix(update): back up notes before in-place writes"
```

### Task 6: Complete Helper Consistency and Documentation

**Files:**
- Modify: `obsidian_kb_skill/scripts/scaffold_templates.py`
- Modify: `obsidian_kb_skill/scripts/detect_index.py`
- Modify: `tests/test_json_output.py`
- Modify: `tests/test_templates.py`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: JSON scaffold schema, correct executable shebang, accurate installed/source command docs, and v1.11.0 metadata.

- [ ] **Step 1: Write failing helper-consistency tests**

Require `scaffold-templates --json` to emit one document with `schema_version`, `operation`, `apply`, `force`, `written`, `skipped`, and `templates_dir`. Require every Python helper to start with `#!/usr/bin/env python3`.

- [ ] **Step 2: Run targeted tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_json_output.py tests/test_templates.py -q`

Expected: FAIL because scaffold lacks JSON and `detect_index.py` has `/usr/env`.

- [ ] **Step 3: Implement helper consistency**

Keep scaffold text output unchanged when `--json` is absent. In JSON mode, suppress line-oriented status output and print one JSON object. Correct the shebang.

- [ ] **Step 4: Update documentation and version metadata**

Document:

- installed runner commands versus wheel console commands;
- Python 3.11 minimum and private PyYAML setup;
- complete Skill anatomy and platform locations;
- safe upgrade/uninstall behavior;
- v1.11.0 release notes, path-safety fixes, backup enforcement, and Windows runtime verification.

Remove false statements that the repository contains no code, has zero runtime dependencies, or that deleted `scripts/*.py` paths still exist. Set `pyproject.toml` and core metadata to `1.11.0`.

- [ ] **Step 5: Rebuild, test, and commit**

Run:

```bash
.venv/bin/python build.py
.venv/bin/python build.py --check
.venv/bin/python -m pytest tests/test_json_output.py tests/test_templates.py tests/test_build.py -q
```

Expected: all commands exit 0.

```bash
git add obsidian_kb_skill core skills platforms tests README.md README_EN.md CHANGELOG.md pyproject.toml build.py
git commit -m "feat: prepare the v1.11.0 standard skill release"
```

### Task 7: Run Installed-Product Forward Tests and Release Gates

**Files:**
- Create or modify only if a discovered defect requires a focused test and fix.

**Interfaces:**
- Consumes: disposable release tree, temporary `HOME`, temporary Vault, installed launcher.
- Produces: raw verification logs proving the release contract and any focused regression commits discovered during testing.

- [ ] **Step 1: Validate the standard Skill**

Run:

```bash
/Users/shaopc/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/obsidian-knowledge-base
.venv/bin/python build.py --check
```

Expected: both exit 0.

- [ ] **Step 2: Run the complete local suite**

Run: `.venv/bin/python -m pytest -q`

Expected: all collected tests pass.

- [ ] **Step 3: Run a black-box installed Skill scenario**

Using a temporary release copy and temporary `HOME`:

1. Install all platforms with `OBSIDIAN_KB_PYTHON` set to an absolute Python 3.11+ interpreter.
2. Delete the release copy and change to a neutral directory.
3. Read installed `references/note-creation.md`.
4. Run `vault-info --json` and `detect-index --json`.
5. Remove one Vault template and run `scaffold-templates --apply --json`.
6. Run `create-note --apply --json` for an insight note.
7. Run `update-note --apply --json` and verify the backup bytes.
8. Run `suggest-links --json`, `process-inbox --plan --json`, and `audit-vault --json`.
9. Repeat key reads through a symlink Vault root.
10. Confirm traversal and static out-of-root symlink probes return the path-violation code.
11. Upgrade and uninstall, checking preservation rules.

Expected: no command imports the checkout, all JSON parses, intended files are created, backup and containment invariants hold, and the final uninstall leaves the Vault and config.

- [ ] **Step 4: Inspect the Skill instructions against observed behavior**

For every imperative in `SKILL.md` and its directly linked references, map the instruction to the helper or manual action that fulfills it. If a mismatch is observed, write one failing regression test, implement the smallest aligned fix, rerun the affected scenario, and commit the fix separately.

- [ ] **Step 5: Verify packaging independently**

Run from a neutral directory so this repository's `build.py` does not shadow
the packaging module:

```bash
.venv/bin/python -m pytest tests/test_wheel_install.py -q
(cd /tmp && python -m build --wheel /path/to/obsidian-kb-skill)
```

Install the produced wheel in a new venv from a neutral directory and invoke all eight console-script `--help` commands plus scaffold/create/audit smoke operations.

- [ ] **Step 6: Push the release candidate and wait for CI**

Push the branch, inspect both Linux Python matrix jobs and the Windows installer job, and fix any failure before release. Do not tag while any required job is missing or red.

- [ ] **Step 7: Tag and publish v1.11.0**

After a clean worktree, local gates, and remote CI are green:

```bash
git tag -a v1.11.0 -m "v1.11.0"
git push origin HEAD
git push origin v1.11.0
```

Verify the remote tag resolves to the tested release commit and that `v1.10.0` still resolves to `b537fcf`.
