# Native Folder Index Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release obsidian-kb-skill v1.6.0, migrate the live Vault to native folder-named indexes, install the release in shared `.agents`, and prove a newly captured article is reachable from the root graph index.

**Architecture:** The auditor reads Folder Index configuration and derives the expected root and per-folder index paths. The live Vault uses `INDEX.md` only at root and `<folder-name>.md` below root, matching Folder Index 1.0.30 graph traversal. Installers, shared instructions, migration docs, and the real capture workflow use the same configuration-driven path function.

**Tech Stack:** Python 3.9+, PyYAML, pytest, Bash, PowerShell, Markdown, Obsidian Folder Index 1.0.30, Git, GitHub CLI.

## Global Constraints

- Root index remains `INDEX.md`; every managed non-root folder uses `<folder-name>.md`.
- `graphOverwrite=true`, `indexFileUserSpecified=false`, and `autoRenameIndexFile=true` are required for the live Vault.
- Folder Index owns generated directory membership; no manual member lists are introduced.
- Existing index bodies and note bodies are preserved during path migration.
- Obsidian must be closed during the migration and reopened only after filesystem and configuration checks pass.
- Every code behavior change follows RED-GREEN TDD.
- Generated platform adapters are changed only through `python build.py`.
- No automatic Git content-conflict resolution is allowed.
- Release version is `1.6.0`.

---

### Task 1: Add configuration-aware graph auditing

**Files:**
- Modify: `tests/test_audit_vault.py`
- Modify: `scripts/audit_vault.py`

**Interfaces:**
- Produces `FolderIndexConfig` with `enabled`, `graph_overwrite`, `root_index_file`, `user_specified`, `index_filename`, and excluded paths.
- Produces `expected_folder_index(folder, vault, config) -> Path`.
- Extends `audit_vault(vault)` with graph configuration, index naming, and graph-chain findings.

- [ ] **Step 1: Add fixture helpers and failing graph tests**

Create helpers that write an enabled plugin manifest and `data.json`. Add tests proving:

```python
def test_reports_graph_incompatible_uniform_custom_index_name(tmp_path):
    configure_folder_index(tmp_path, user_specified=True, index_filename="INDEX")
    make_index(tmp_path / "INDEX.md", note_type="moc")
    (tmp_path / "Topic").mkdir()
    make_index(tmp_path / "Topic" / "INDEX.md")
    assert "graph-incompatible-index-config" in codes(tmp_path)


def test_accepts_native_folder_named_graph_chain(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    topic = tmp_path / "Topic"
    topic.mkdir()
    make_index(topic / "Topic.md")
    write_note(topic / "2026-07-08 Note.md")
    assert not {
        "graph-incompatible-index-config",
        "missing-folder-index",
        "misnamed-folder-index",
        "broken-folder-graph-chain",
    } & codes(tmp_path)


def test_reports_missing_and_misnamed_native_folder_index(tmp_path):
    configure_folder_index(tmp_path, user_specified=False)
    make_index(tmp_path / "INDEX.md", note_type="moc")
    missing = tmp_path / "Missing"
    missing.mkdir()
    legacy = tmp_path / "Legacy"
    legacy.mkdir()
    make_index(legacy / "INDEX.md")
    assert {"missing-folder-index", "misnamed-folder-index"} <= codes(tmp_path)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_audit_vault.py -k 'graph or native or misnamed' -v`

Expected: failures because configuration loading and graph findings do not exist.

- [ ] **Step 3: Implement configuration loading and expected paths**

Add `json`, a frozen `FolderIndexConfig` dataclass, safe JSON loading, path exclusion, and:

```python
def expected_folder_index(folder: Path, vault: Path, config: FolderIndexConfig) -> Path:
    if folder == vault:
        return vault / config.root_index_file
    if config.user_specified:
        return folder / f"{config.index_filename}.md"
    return folder / f"{folder.name}.md"
```

- [ ] **Step 4: Implement graph compatibility and chain audit**

For enabled Folder Index mode:

- report uniform custom index naming when Graph overwrite is active and managed child folders exist;
- require one configured index in every managed non-root folder;
- report legacy folder-index files at a non-expected path;
- verify each child index is the exact folder-named file Folder Index graph traversal will discover;
- preserve existing metadata, wikilink, duplicate-owner, and fenced-block checks.

- [ ] **Step 5: Run auditor tests and complete suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_audit_vault.py -v
.venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_vault.py tests/test_audit_vault.py
git commit -m "feat: audit native Folder Index graph chains"
```

---

### Task 2: Update capture rules and installer behavior

**Files:**
- Modify: `tests/test_build.py`
- Modify: `tests/test_templates.py`
- Create: `tests/test_installers.py`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `install.sh`
- Modify: `install.ps1`
- Regenerate: `platforms/qoderwork/SKILL.md`
- Regenerate: `platforms/claude-code/CLAUDE.md`
- Regenerate: `platforms/codex/AGENTS.md`
- Regenerate: `platforms/cursor/obsidian-kb.mdc`

**Interfaces:**
- The core instructions define native graph-safe Folder Index mode, Git pre-sync, template headings, target-folder search, `source`, and `related` semantics.
- Both installers derive the same folder index filename and body from plugin configuration.

- [ ] **Step 1: Add failing instruction-contract tests**

Tests must require these exact concepts in the core:

```python
assert "Folder Index 1.0.30" in core
assert "folder-named indexes" in core
assert "list the target folder's filenames" in core
assert "required template headings" in core
assert "canonical source URL" in core
assert "machine-readable source of truth" in core
assert "Pre-write Git synchronization" in core
assert "merge --ff-only" in core
```

- [ ] **Step 2: Add failing Bash installer smoke tests**

Run `install.sh` against temporary Vaults with isolated HOME:

- native Folder Index config creates `20-Learning/20-Learning.md`, no `20-Learning/INDEX.md`, and a `folder-index-content` block;
- no Folder Index config creates `20-Learning/INDEX.md` with Dataview fallback;
- root navigation links point to the actual generated index paths;
- PowerShell script contains matching configuration keys and native filename logic.

- [ ] **Step 3: Run contract and installer tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_templates.py tests/test_installers.py -v`

Expected: failures against v1.5.0.

- [ ] **Step 4: Update the core workflow**

Implement the design requirements without duplicating index ownership:

- warn that uniform custom names break nested graph edges in Folder Index 1.0.30;
- recommend native folder-named indexes whenever Graph overwrite is required;
- validate the root-to-target folder index chain after writes;
- list the target folder before parent/sibling searches;
- validate template headings in order;
- define canonical URL and `related`/body duplication rules;
- perform Git fetch/ff-only pre-sync before writes when Git is required.

- [ ] **Step 5: Update Bash and PowerShell installers**

Detect plugin mode from the Vault. In native mode create folder-name indexes with a plugin block. In custom mode use the configured filename and warn about nested Graph View. Without Folder Index preserve the Dataview/static fallback. Generate root navigation with actual paths.

- [ ] **Step 6: Regenerate adapters and verify GREEN**

Run:

```bash
.venv/bin/python build.py
.venv/bin/python build.py --check
.venv/bin/python -m pytest tests/ -v
bash -n install.sh
```

Expected: all tests pass and adapters are synchronized.

- [ ] **Step 7: Commit**

```bash
git add core platforms install.sh install.ps1 tests
git commit -m "feat: use graph-safe Folder Index naming"
```

---

### Task 3: Prepare and verify v1.6.0

**Files:**
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Regenerate: `platforms/*` adapters

- [ ] **Step 1: Update version and documentation**

Set version `1.6.0`. Replace recommendations for custom `INDEX` naming with native folder-named indexes, document the complete graph chain, installer behavior, migration warning, Git pre-sync, and audit findings.

- [ ] **Step 2: Regenerate and verify**

Run full pytest, `build.py --check`, `bash -n install.sh`, `git diff --check`, and isolated Bash installer smoke tests.

- [ ] **Step 3: Commit release preparation**

```bash
git add core platforms pyproject.toml README.md README_EN.md CHANGELOG.md
git commit -m "release: prepare obsidian kb skill v1.6.0"
```

---

### Task 4: Migrate the live Vault

**Files:**
- Rename: every managed non-root `INDEX.md` to `<folder-name>.md`
- Modify: `.obsidian/plugins/obsidian-folder-index/data.json`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Add: migration evidence under `docs/superpowers/reports/`

- [ ] **Step 1: Close Obsidian and create byte-preserving backup**

Gracefully quit Obsidian. Back up all affected indexes and governance/config files under `.obsidian-kb-backups/<timestamp>/`. Record file hashes and migration inventory.

- [ ] **Step 2: Capture the failing pre-migration audit**

Run the v1.6 auditor. Expected: `graph-incompatible-index-config` plus naming/chain findings proving the original defect.

- [ ] **Step 3: Rename all managed non-root indexes**

Use `git mv` for exactly the managed directories. Keep root `INDEX.md`. Compare each renamed file body and SHA-256 with its backup to prove path-only migration.

- [ ] **Step 4: Update plugin configuration and governance**

Set:

```json
"graphOverwrite": true,
"rootIndexFile": "INDEX.md",
"autoCreateIndexFile": true,
"autoRenameIndexFile": true,
"indexFileUserSpecified": false
```

Update AGENTS, CLAUDE, and README to document root-vs-folder naming and no manual membership maintenance.

- [ ] **Step 5: Run strict migration verification**

Verify:

- strict audit returns 0 findings;
- all managed folders have exactly one expected index;
- no managed non-root `INDEX.md` remains;
- every folder index is reachable from root according to Folder Index 1.0.30 graph logic;
- every non-index note is reachable from its folder index;
- `.obsidian/workspace.json` is unchanged.

- [ ] **Step 6: Reopen Obsidian and verify plugin stability**

Open Obsidian, wait for plugin initialization, then verify no duplicate index files appeared and settings remain native.

- [ ] **Step 7: Commit migration**

```bash
git add .obsidian/plugins/obsidian-folder-index/data.json AGENTS.md CLAUDE.md README.md 00-Inbox 10-Work 15-Daily 20-Learning 30-Insights 40-Projects 50-People 90-Archive docs/superpowers/reports
git commit -m "update: 迁移 Folder Index 原生图谱索引"
```

---

### Task 5: Merge, publish, and install the Skill

- [ ] **Step 1: Verify and merge feature branch locally**

Run full tests on the feature branch and again on merged `master`. Clean up the owned worktree and branch only after successful merge.

- [ ] **Step 2: Push Skill master and publish GitHub Release**

Fetch and reject divergence, push `master`, create annotated tag `v1.6.0`, push it, and create a non-draft/non-prerelease GitHub Release from CHANGELOG highlights.

- [ ] **Step 3: Install the exact release in shared `.agents`**

Clone tag `v1.6.0` to `/Users/shaopc/.agents/obsidian-kb-skill`, create the relative shared skill symlink, and verify the installed `SKILL.md` reports v1.6.0 and is readable from both Codex homes.

---

### Task 6: Capture a real article with the shared release

**Files:**
- Create: `20-Learning/Obsidian/Obsidian.md`
- Create: `20-Learning/Obsidian/2026-07-08 Folder Index自定义索引名导致图谱断链.md`
- Modify: `README.md`

- [ ] **Step 1: Read and apply the shared installed Skill**

Resolve the Vault, run Git pre-sync, read the Vault template and plugin configuration, route to a new `20-Learning/Obsidian/` topic, and create its native same-name index.

- [ ] **Step 2: Capture the official article/source analysis**

Use the official Folder Index repository and `GraphManipulatorModule.ts` as sources. Store the canonical source URL, concise evidence, the custom-name failure mechanism, native-name solution, and a high-confidence related link if bounded search finds one.

- [ ] **Step 3: Run post-write and graph-chain validation**

Require strict audit 0 findings and prove:

```text
INDEX.md → 20-Learning/20-Learning.md → 20-Learning/Obsidian/Obsidian.md → new article
```

- [ ] **Step 4: Commit and push both repositories safely**

Update README for the new topic, commit the capture separately, fetch both remotes, reject divergence, push, and verify local/origin/remote hashes and 0/0 divergence.

- [ ] **Step 5: Final completion audit**

Re-run Skill tests/build/install smoke tests, Vault strict audit, graph reachability, shared-install version/readability, GitHub tag/Release status, protected workspace diff, and both worktree statuses. Only then report completion.
