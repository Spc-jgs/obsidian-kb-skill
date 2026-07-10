# Bounded Backup Retention v1.11.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound write-before backups through a global user policy and deterministic post-write cleanup, release v1.11.1 with no known P0 issue, then synchronize and verify the local Codex Skill.

**Architecture:** Add a focused `backup_policy.py` module that parses `~/.obsidian-kb-settings.json` and prunes only verified regular backup files without following symlinks. `update_note.py` calls it in-process only after a successful write; installers own only initial settings scaffolding and explicit purge, while installed-product tests prove the behavior without a source checkout.

**Tech Stack:** Python 3.11+, pathlib/os.scandir, dataclasses, JSON, Bash, Windows PowerShell 5.1+, pytest, uv, GitHub Actions.

## Global Constraints

- Global settings path is exactly `~/.obsidian-kb-settings.json`.
- Missing settings default to `backup.keep_per_note = 1`.
- Valid retention is an integer from 1 through 1000; booleans and zero are invalid.
- Invalid or unreadable settings authorize zero deletions and emit a warning.
- No AI-facing cleanup command or per-invocation retention option is added.
- Cleanup runs only after a successful `update-note --apply` write.
- Never follow or delete symlinks, unknown top-level layouts, or out-of-Vault paths.
- Default uninstall preserves settings; explicit purge removes Vault config and settings.
- The release version is 1.11.1 and the v1.11.0 tag must not move.
- A version tag is forbidden while a P0 data-loss, deletion-boundary, installer, or installed-runtime issue is known or unverified.

---

### Task 1: Implement the Global Backup Policy and Safe Pruner

**Files:**
- Create: `obsidian_kb_skill/scripts/backup_policy.py`
- Create: `tests/test_backup_policy.py`
- Generate later: `skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/scripts/backup_policy.py`

**Interfaces:**
- Produces: `BackupPolicy`, `CleanupResult`, `load_backup_policy(home: Path | None = None) -> BackupPolicy`, and `prune_backups(vault: Path, policy: BackupPolicy, protected: Path | None = None) -> CleanupResult`.
- Consumes: canonical Vault validation from `obsidian_kb_skill.scripts.vault_paths`.

- [ ] **Step 1: Write failing settings-contract tests**

Create `tests/test_backup_policy.py` with fixtures and the exact contract:

```python
import json
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.backup_policy import (
    BackupPolicy,
    load_backup_policy,
    prune_backups,
)


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def write_settings(home: Path, value: object, *, schema: object = 1) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / ".obsidian-kb-settings.json").write_text(
        json.dumps({"schema_version": schema, "backup": {"keep_per_note": value}}),
        encoding="utf-8",
    )


def test_missing_settings_defaults_to_one(tmp_path):
    policy = load_backup_policy(tmp_path / "home")
    assert policy == BackupPolicy(keep_per_note=1, prune_enabled=True, warnings=())


@pytest.mark.parametrize("value", [0, -1, 1001, True, "1", None])
def test_invalid_retention_disables_pruning(tmp_path, value):
    home = tmp_path / "home"
    write_settings(home, value)
    policy = load_backup_policy(home)
    assert policy.prune_enabled is False
    assert policy.warnings
```

- [ ] **Step 2: Run settings tests and verify RED**

Run:

```bash
uv run --no-sync python -m pytest tests/test_backup_policy.py -q
```

Expected: collection fails with `ModuleNotFoundError: obsidian_kb_skill.scripts.backup_policy`.

- [ ] **Step 3: Add pruning safety and grouping tests**

Add helpers and tests that create the real timestamp layout:

```python
def backup(vault: Path, stamp: str, relative: str, content: str) -> Path:
    path = vault / ".obsidian-kb-backups" / stamp / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_keep_one_protects_current_and_prunes_all_note_groups(tmp_path):
    vault = make_vault(tmp_path)
    old_a = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "a0")
    current_a = backup(vault, "2026-07-10-090000", "Tasks/a/TASK.md", "a1")
    old_b = backup(vault, "2026-07-10-100001", "Tasks/b/TASK.md", "b0")
    new_b = backup(vault, "2026-07-10-100002", "Tasks/b/TASK.md", "b1")

    result = prune_backups(
        vault,
        BackupPolicy(keep_per_note=1, prune_enabled=True, warnings=()),
        protected=current_a,
    )

    assert current_a.is_file()
    assert not old_a.exists()
    assert new_b.is_file()
    assert not old_b.exists()
    assert result.deleted == 2


def test_invalid_policy_performs_zero_deletions(tmp_path):
    vault = make_vault(tmp_path)
    first = backup(vault, "2026-07-10-100000", "Tasks/a/TASK.md", "a0")
    second = backup(vault, "2026-07-10-100001", "Tasks/a/TASK.md", "a1")
    result = prune_backups(
        vault,
        BackupPolicy(keep_per_note=1, prune_enabled=False, warnings=("invalid",)),
    )
    assert first.is_file() and second.is_file()
    assert result.deleted == 0


def test_symlink_and_unknown_top_level_items_are_retained(tmp_path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    root = vault / ".obsidian-kb-backups"
    root.mkdir()
    link = root / "2026-07-10-100000"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    unknown = root / "manual-copy.md"
    unknown.write_text("keep", encoding="utf-8")

    result = prune_backups(
        vault,
        BackupPolicy(keep_per_note=1, prune_enabled=True, warnings=()),
    )

    assert link.is_symlink()
    assert unknown.is_file()
    assert outside.read_text(encoding="utf-8") == "outside"
    assert result.warnings
```

Add this configurable-retention test, then add named tests with the same direct
file assertions for malformed JSON, unsupported schema, unreadable settings,
collision suffixes, a symlink file inside a valid timestamp directory, partial
unlink/rmdir errors, and cleanup that stops at `.obsidian-kb-backups`:

```python
@pytest.mark.parametrize("keep", [2, 3])
def test_configured_retention_is_per_note(tmp_path, keep):
    vault = make_vault(tmp_path)
    paths = [
        backup(vault, f"2026-07-10-10000{index}", "Tasks/a/TASK.md", str(index))
        for index in range(4)
    ]
    other = [
        backup(vault, f"2026-07-10-11000{index}", "Tasks/b/TASK.md", str(index))
        for index in range(4)
    ]
    result = prune_backups(vault, BackupPolicy(keep, True))
    assert sum(path.exists() for path in paths) == keep
    assert sum(path.exists() for path in other) == keep
    assert result.deleted == 8 - (keep * 2)
```

- [ ] **Step 4: Implement `backup_policy.py`**

Implement these exact public types and validation constants:

```python
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from obsidian_kb_skill.scripts.vault_paths import (
    VaultPathError,
    resolve_existing_within_vault,
    validate_vault_root,
)

SETTINGS_NAME = ".obsidian-kb-settings.json"
DEFAULT_KEEP_PER_NOTE = 1
MAX_KEEP_PER_NOTE = 1000
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}(?:-(?:[2-9]|[1-9]\d+))?$")


@dataclass(frozen=True)
class BackupPolicy:
    keep_per_note: int
    prune_enabled: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CleanupResult:
    keep_per_note: int
    scanned: int
    deleted: int
    warnings: tuple[str, ...] = ()


def load_backup_policy(home: Path | None = None) -> BackupPolicy:
    settings = (home or Path.home()) / SETTINGS_NAME
    if not os.path.lexists(settings):
        return BackupPolicy(DEFAULT_KEEP_PER_NOTE, True)
    try:
        payload = json.loads(settings.read_text(encoding="utf-8"))
        schema = payload["schema_version"]
        value = payload["backup"]["keep_per_note"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return BackupPolicy(DEFAULT_KEEP_PER_NOTE, False, (f"invalid settings: {exc}",))
    valid = (
        schema == 1
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_KEEP_PER_NOTE
    )
    if not valid:
        return BackupPolicy(DEFAULT_KEEP_PER_NOTE, False, ("invalid backup retention settings",))
    return BackupPolicy(value, True)
```

Use this non-following traversal shape and retain every skipped item:

```python
def _walk_regular_files(
    directory: Path,
    *,
    directories: list[Path],
    warnings: list[str],
):
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
    except OSError as exc:
        warnings.append(f"cannot scan {directory.name}: {exc}")
        return
    for entry in entries:
        path = Path(entry.path)
        try:
            if entry.is_symlink():
                warnings.append(f"retained symlink: {path.name}")
            elif entry.is_dir(follow_symlinks=False):
                directories.append(path)
                yield from _walk_regular_files(
                    path, directories=directories, warnings=warnings
                )
            elif entry.is_file(follow_symlinks=False):
                yield path
            else:
                warnings.append(f"retained non-regular item: {path.name}")
        except OSError as exc:
            warnings.append(f"cannot inspect {path.name}: {exc}")
```

`prune_backups` validates the canonical Vault, refuses a symlink/non-directory
backup root, accepts only `STAMP_RE` real directories, and records each candidate
as `(resolved_path, relative_note, stamp_name, mtime_ns)`. For each relative-note
group, sort by `(path == protected_resolved, mtime_ns, stamp_name, path.as_posix())`
descending and retain the first `keep_per_note`. Catch `OSError` separately for
each `unlink()` and bottom-up `rmdir()` so the function always returns a
`CleanupResult` rather than raising after a committed write.

- [ ] **Step 5: Run focused policy tests and verify GREEN**

Run:

```bash
uv run --no-sync python -m pytest tests/test_backup_policy.py tests/test_vault_paths.py -q
```

Expected: all policy and existing path-boundary tests pass.

- [ ] **Step 6: Build the canonical Skill copy and verify exact sync**

Run:

```bash
uv run --no-sync python build.py
uv run --no-sync python build.py --check
```

Expected: `backup_policy.py` exists under the canonical Skill helper package and
the build check exits 0.

- [ ] **Step 7: Commit the policy module**

```bash
git add obsidian_kb_skill/scripts/backup_policy.py \
  skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/scripts/backup_policy.py \
  tests/test_backup_policy.py
git commit -m "feat(backup): bound retained note backups"
```

### Task 2: Integrate Cleanup After Successful Task-Memory Writes

**Files:**
- Modify: `obsidian_kb_skill/scripts/update_note.py`
- Modify: `tests/test_update_note.py`
- Modify: `tests/test_json_output.py`
- Generate: `skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/scripts/update_note.py`

**Interfaces:**
- Consumes: `load_backup_policy()` and `prune_backups()` from Task 1.
- Produces: `result["backup_cleanup"]` as either `None` or `{keep_per_note, scanned, deleted, warnings}`.

- [ ] **Step 1: Write failing ordering and failure-semantics tests**

Add tests using monkeypatch call order:

```python
from obsidian_kb_skill.scripts.backup_policy import CleanupResult


def test_cleanup_runs_only_after_successful_write(vault, monkeypatch):
    note = vault / "Tasks/foo/TASK.md"
    assert update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"]) == 0
    calls = []
    original_write = pathlib.Path.write_bytes

    def tracked_write(path, data):
        if path == note:
            calls.append("write")
        return original_write(path, data)

    def tracked_prune(vault_arg, policy, protected=None):
        calls.append("prune")
        assert protected is not None and protected.is_file()
        return CleanupResult(policy.keep_per_note, scanned=2, deleted=1)

    monkeypatch.setattr(pathlib.Path, "write_bytes", tracked_write)
    monkeypatch.setattr(update_note, "prune_backups", tracked_prune)
    assert update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"]) == 0
    assert calls == ["write", "prune"]


def test_note_write_failure_never_prunes(vault, monkeypatch):
    note = vault / "Tasks/foo/TASK.md"
    assert update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"]) == 0
    original_write = pathlib.Path.write_bytes

    def fail_note_write(path, data):
        if path == note:
            raise OSError("disk")
        return original_write(path, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", fail_note_write)
    monkeypatch.setattr(update_note, "prune_backups", lambda *_args, **_kwargs: pytest.fail("pruned"))
    with pytest.raises(OSError, match="disk"):
        update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"])
```

Add this warning-semantics test so cleanup errors cannot turn a committed write
into an agent retry:

```python
def test_cleanup_warning_does_not_fail_committed_write(vault, monkeypatch, capsys):
    note = vault / "Tasks/foo/TASK.md"
    assert update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"]) == 0
    before = note.read_bytes()
    monkeypatch.setattr(
        update_note,
        "prune_backups",
        lambda *_args, **_kwargs: CleanupResult(
            keep_per_note=1,
            scanned=2,
            deleted=0,
            warnings=("cannot delete old backup",),
        ),
    )
    assert update_note.main([str(vault), "--note", "Tasks/foo/TASK.md", "--apply"]) == 0
    assert note.read_bytes() != before
    assert capsys.readouterr().err.count("cannot delete old backup") == 1
```

- [ ] **Step 2: Run update tests and verify RED**

Run:

```bash
uv run --no-sync python -m pytest tests/test_update_note.py -k 'cleanup or prune' -q
```

Expected: FAIL because `update_note` has no `prune_backups` integration or
`backup_cleanup` result.

- [ ] **Step 3: Implement post-write cleanup**

Import the policy interfaces and extend the result:

```python
from dataclasses import asdict

from obsidian_kb_skill.scripts.backup_policy import (
    load_backup_policy,
    prune_backups,
)

# result initialization
"backup_cleanup": None,

# immediately after note_path.write_bytes(...) and result["applied"] = True
policy = load_backup_policy()
cleanup = prune_backups(
    vault,
    policy,
    protected=backup_path if action == "update" else None,
)
result["backup_cleanup"] = asdict(cleanup)
for warning in cleanup.warnings:
    print(f"warning: backup cleanup: {warning}", file=sys.stderr)
```

Initialize `backup_path: Path | None = None` before the update branch. Do not add
a CLI flag and do not print success chatter in human mode.

- [ ] **Step 4: Add JSON behavior tests**

Add an apply test with temporary HOME settings and assert:

```python
assert out["backup_cleanup"] == {
    "keep_per_note": 1,
    "scanned": 2,
    "deleted": 1,
    "warnings": [],
}
```

Assert dry-run output keeps `backup_cleanup is None` and does not read or modify
the backup tree.

- [ ] **Step 5: Run integration tests and rebuild**

```bash
uv run --no-sync python -m pytest tests/test_update_note.py tests/test_json_output.py tests/test_backup_policy.py -q
uv run --no-sync python build.py
uv run --no-sync python build.py --check
```

Expected: all targeted tests pass and generated helper code matches source.

- [ ] **Step 6: Commit write integration separately**

```bash
git add obsidian_kb_skill/scripts/update_note.py \
  skills/obsidian-knowledge-base/scripts/obsidian_kb_skill/scripts/update_note.py \
  tests/test_update_note.py tests/test_json_output.py
git commit -m "feat(update): prune backups after successful writes"
```

### Task 3: Add Settings Lifecycle Parity to Both Installers

**Files:**
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `tests/test_installers.py`
- Modify: `tests/windows_installer_smoke.ps1`

**Interfaces:**
- Produces: global settings creation-if-missing, preservation on upgrade/default uninstall, and deletion on explicit purge.
- Consumes: exact JSON schema from the Global Settings Contract.

- [ ] **Step 1: Write failing Bash lifecycle tests**

Extend the release-installer black-box tests:

```python
def test_bash_settings_created_preserved_and_purged(tmp_path):
    release = _copy_release_tree(tmp_path)
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    settings = home / ".obsidian-kb-settings.json"

    _run_release_installer(release, home=home, vault=vault)
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "backup": {"keep_per_note": 1},
    }
    settings.write_text('{"schema_version":1,"backup":{"keep_per_note":3}}\n', encoding="utf-8")
    _run_release_installer(release, home=home, vault=vault)
    assert json.loads(settings.read_text(encoding="utf-8"))["backup"]["keep_per_note"] == 3
    _run_release_installer(release, home=home, vault=vault, extra_args=("--uninstall",))
    assert settings.is_file()
    _run_release_installer(release, home=home, vault=vault)
    _run_release_installer(release, home=home, vault=vault, extra_args=("--uninstall", "--purge-config"))
    assert not settings.exists()
```

- [ ] **Step 2: Run the Bash test and verify RED**

```bash
uv run --no-sync python -m pytest tests/test_installers.py -k settings -q
```

Expected: FAIL because neither installer creates or purges the settings file.

- [ ] **Step 3: Implement Bash lifecycle**

Add `SETTINGS_FILE="$HOME/.obsidian-kb-settings.json"`, create it only when
missing with the exact schema, preserve it during default uninstall, remove it
during purge, and update `--help` text. Use the existing Python runtime to write
valid JSON rather than shell interpolation:

```bash
if [ ! -e "$SETTINGS_FILE" ]; then
  "$PYTHON_BIN" - "$SETTINGS_FILE" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    json.dumps({"schema_version": 1, "backup": {"keep_per_note": 1}}, indent=2) + "\n",
    encoding="utf-8",
)
PY
fi
```

- [ ] **Step 4: Mirror the contract in PowerShell and Windows smoke**

Add `$SettingsFile = Join-Path $env:USERPROFILE ".obsidian-kb-settings.json"`.
Write the same object through `ConvertTo-Json` only when absent, preserve it on
upgrade/default uninstall, and remove it with `-PurgeConfig`. Extend the Windows
smoke script to edit retention to three, reinstall, verify preservation, then
verify default uninstall/purge semantics.

- [ ] **Step 5: Run local parity and syntax gates**

```bash
uv run --no-sync python -m pytest tests/test_installers.py -q
bash -n install.sh
uv run --no-sync python build.py --check
```

Expected: all local installer tests pass and Bash syntax is valid. Actual
PowerShell behavior remains a required pushed Windows CI gate.

- [ ] **Step 6: Commit installer settings lifecycle**

```bash
git add install.sh install.ps1 tests/test_installers.py tests/windows_installer_smoke.ps1
git commit -m "feat(installer): manage global backup settings"
```

### Task 4: Prove Installed Skill and Wheel Retention Without the Checkout

**Files:**
- Modify: `tests/test_skill_runtime.py`
- Modify: `tests/test_wheel_install.py`
- Modify: `tests/test_installers.py`

**Interfaces:**
- Consumes: complete standard payload, `run_helper.py`, wheel console scripts, and global settings.
- Produces: black-box proof that settings and cleanup work from installed artifacts after source removal.

- [ ] **Step 1: Write failing installed-Skill retention scenario**

After installing from a disposable release and deleting it, create a temporary
Vault, initialize Task Memory, update it three times through the installed
launcher, and assert one backup remains:

```python
settings = home / ".obsidian-kb-settings.json"
settings.write_text('{"schema_version":1,"backup":{"keep_per_note":1}}\n', encoding="utf-8")
for index in range(4):
    result = _run_installed_helper(
        codex,
        "update-note",
        str(vault),
        "--note", "Tasks/demo/TASK.md",
        "--step", f"step-{index}",
        "--apply", "--no-audit", "--json",
        home=home,
        cwd=neutral,
    )
    assert result.returncode == 0, result.stderr
backups = list((vault / ".obsidian-kb-backups").glob("*/Tasks/demo/TASK.md"))
assert len(backups) == 1
```

Also assert the imported module path and runner paths live under the installed
Skill, never the repository.

- [ ] **Step 2: Write failing wheel retention scenario**

In the clean wheel venv, set `HOME`/`USERPROFILE` to a temporary home containing
retention two, execute `obsidian-update-note` four times from the neutral
directory, and assert exactly two backups plus JSON `keep_per_note == 2`.

- [ ] **Step 3: Run black-box tests and verify RED**

```bash
uv run --no-sync python -m pytest tests/test_skill_runtime.py tests/test_wheel_install.py tests/test_installers.py -q
```

Expected: new scenarios fail before the installed payload is rebuilt/integrated.

- [ ] **Step 4: Rebuild and make only contract-level corrections**

Run `build.py` so `backup_policy.py` and the integrated updater enter the
canonical payload. Do not add repository paths to black-box environments. If a
test still fails, print its imported module path, add a failing assertion for
that installed path, and make only the packaging correction required by that
assertion.

- [ ] **Step 5: Run black-box tests until GREEN**

```bash
uv run --no-sync python build.py
uv run --no-sync python build.py --check
uv run --no-sync python -m pytest tests/test_skill_runtime.py tests/test_wheel_install.py tests/test_installers.py -q
```

Expected: all disposable-install and wheel scenarios pass after source removal.

- [ ] **Step 6: Commit installed-product proof**

```bash
git add build.py skills/obsidian-knowledge-base tests/test_skill_runtime.py \
  tests/test_wheel_install.py tests/test_installers.py
git commit -m "test(distribution): prove installed backup retention"
```

### Task 5: Prepare the v1.11.1 Product Contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `core/references/task-memory.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Generate: platform and standard Skill instruction/reference copies

**Interfaces:**
- Produces: consistent 1.11.1 metadata and user documentation for settings, retention, uninstall, and release behavior.

- [ ] **Step 1: Add documentation/version assertions**

Extend existing build/reference tests to assert `1.11.1`, the global settings
path, default retention one, script-owned cleanup, and preservation/purge text.
Assert SKILL instructions do not tell the AI to list or delete backups.

- [ ] **Step 2: Run documentation tests and verify RED**

```bash
uv run --no-sync python -m pytest tests/test_build.py tests/test_lazy_references.py tests/test_installers.py -q
```

Expected: new version and retention assertions fail.

- [ ] **Step 3: Update version and concise documentation**

Set `project.version = "1.11.1"`, update the core version header and both README
headers, document `~/.obsidian-kb-settings.json`, and add a 1.11.1 changelog entry.
In `task-memory.md`, state that `update-note` creates the previous-version backup
and the helper silently enforces global retention after successful writes; the
agent never manages backup files.

- [ ] **Step 4: Regenerate and lock exact artifacts**

```bash
uv lock
uv run --no-sync python build.py
uv lock --check
uv run --no-sync python build.py --check
```

Expected: lock and every generated adapter/resource/helper tree are synchronized.

- [ ] **Step 5: Run targeted documentation tests**

```bash
uv run --no-sync python -m pytest tests/test_build.py tests/test_lazy_references.py tests/test_installers.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit release metadata**

```bash
git add pyproject.toml uv.lock core README.md README_EN.md CHANGELOG.md \
  platforms skills obsidian_kb_skill/scripts/resources tests/test_build.py \
  tests/test_lazy_references.py tests/test_installers.py
git commit -m "chore(release): prepare v1.11.1"
```

### Task 6: Iterate to a P0-Clean Release and Synchronize Local Codex

**Files:**
- Review: all changes from `6f771e6..HEAD`
- Mutate externally after gates: PR, master, tag `v1.11.1`, GitHub Release, local Codex installation

**Interfaces:**
- Consumes: all previous tasks.
- Produces: merged/published v1.11.1 and a verified local Codex/canonical installation.

- [ ] **Step 1: Run the complete local gate from a clean worktree**

```bash
uv sync --locked --extra dev
uv run --no-sync python /Users/shaopc/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/obsidian-knowledge-base
uv run --no-sync python build.py --check
uv lock --check
uv run --no-sync python -m compileall -q obsidian_kb_skill skills/obsidian-knowledge-base/scripts
bash -n install.sh
uv run --no-sync python -m pytest -q
git diff --check 6f771e6..HEAD
git status -sb
```

Expected: every command exits 0 and the worktree is clean.

- [ ] **Step 2: Perform the P0 diff audit**

Inspect every changed deletion path and prove:

- no candidate outside `.obsidian-kb-backups` can be unlinked;
- symlink files/directories are retained;
- invalid settings authorize no deletion;
- current update backup is protected;
- cleanup never runs before successful write;
- cleanup failures cannot trigger an agent retry loop;
- installer upgrade/default uninstall preserve user settings and explicit purge
  removes only owned config;
- installed Skill and wheel need no checkout.

If evidence is missing or any issue appears, add a regression test first, verify
RED, fix, rerun the focused test, then restart Step 1. Repeat until no P0 is known.

- [ ] **Step 3: Push the branch and open a draft PR**

```bash
git push -u origin codex/backup-retention-v1-11-1
gh pr create --draft --base master \
  --title "Bound backup retention in v1.11.1" \
  --body '## Summary

- enforce global per-note backup retention after successful writes
- keep deletion inside verified regular backup files without following symlinks
- preserve global settings unless config purge is explicit
- prove behavior in source, installed Skill, wheel, Bash, and Windows PowerShell

## Validation

- standard Skill validation and exact build check
- complete local pytest suite
- disposable installed-Skill and wheel retention scenarios
- Linux Python 3.11/3.14 and Windows PowerShell/Python 3.11 required'
```

The PR body must describe the deletion boundary, invalid-config behavior,
installed-product proof, and exact local gates.

- [ ] **Step 4: Require and iterate on remote gates**

Wait for Linux Python 3.11, Linux Python 3.14, and Windows installer/Python 3.11.
For every failure, retrieve the complete failing job log, identify root cause,
add or strengthen a regression test, fix, rerun the complete local gate, push,
and wait again. Do not merge while a check is pending or failing.

- [ ] **Step 5: Merge and verify master independently**

Mark the PR ready, merge with a merge commit to preserve separated safety
commits, fast-forward local master, and wait for the master push workflow. The
master HEAD must have all three successful jobs before tagging.

- [ ] **Step 6: Publish v1.11.1**

```bash
git tag -a v1.11.1 -m "v1.11.1 - bounded backup retention"
git push origin v1.11.1
gh release create v1.11.1 --verify-tag \
  --title "v1.11.1 — bounded backup retention" \
  --notes '## Highlights

- keeps one write-before backup per note by default, configurable globally from 1 to 1000
- performs deterministic cleanup only after successful writes, with no AI cleanup command
- retains everything on invalid settings and never follows symlinks during deletion
- preserves settings through upgrade/default uninstall and removes them only on explicit purge

## Verification

- complete local suite and standard Skill/build gates passed
- installed Skill and wheel worked after source removal
- Linux Python 3.11/3.14 and Windows PowerShell/Python 3.11 passed'
```

Verify the tag resolves to current master and `v1.11.0` still resolves to
`6f771e68672577be4a0fa54a618940e1a53d3cca`.

- [ ] **Step 7: Synchronize the released local Codex Skill**

From current master/tag, run:

```bash
./install.sh --platforms codex
```

This intentionally replaces the old Codex symlink with the released complete
payload and creates/updates only the canonical support copy. It must not mutate
QoderWork, Claude Code, or Cursor.

- [ ] **Step 8: Verify local installed payload and real retention behavior**

Compare the released canonical source against:

```text
~/.agents/skills/obsidian-knowledge-base
~/.obsidian-kb-skill/skill
```

Exclude only source `header.md` and housekeeping artifacts; require identical
file sets and SHA-256 hashes. From a neutral directory, use the installed
`run_helper.py` against a disposable Vault, execute one initialization plus
three updates, and require one remaining backup. Delete only the disposable
Vault after verification; never mutate the user's real Vault during this smoke.

- [ ] **Step 9: Clean the merged worktree and branch**

After release and local verification, remove the owned `.worktrees/` worktree,
prune worktree metadata, delete the merged local/remote feature branch, and
confirm root `master` is clean and synchronized with origin.
