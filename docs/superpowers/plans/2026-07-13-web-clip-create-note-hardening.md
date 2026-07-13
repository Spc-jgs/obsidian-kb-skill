# Web Clip Create-Note Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `create-note` accept complete web-clip metadata reliably, reject incomplete clips before writing, normalize YAML dates, and round-trip UTF-8 stdin on Windows.

**Architecture:** Keep complete Markdown frontmatter as the generic metadata API. Add recursive scalar normalization and a focused web-clip preflight in `create_note.py`, extend shared stdio configuration to stdin, and regenerate all distributed copies from canonical sources.

**Tech Stack:** Python 3.14, argparse, PyYAML, pytest, PowerShell smoke tests, generated Skill artifacts via `build.py`.

## Global Constraints

- Keep `--content-file` restricted to paths inside the Vault.
- Keep Git post-processing optional.
- Do not add web-clip-specific CLI flags.
- Do not move workflow detail into the always-loaded Skill hub.
- Write failing tests before each production change.

---

### Task 1: Normalize YAML date scalars

**Files:**
- Modify: `tests/test_create_note.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Test: `tests/test_create_note.py`

**Interfaces:**
- Produces: `normalize_yaml_scalars(value: Any) -> Any`, recursively converting `datetime.datetime` and `datetime.date` to ISO strings.
- Consumes: parsed frontmatter passed to `build_note`.

- [ ] **Step 1: Write the failing normalization test**

Add a test that calls `build_note` with `given_meta={"published": datetime.date(2026, 7, 13)}`, parses the rendered frontmatter, and asserts `published == "2026-07-13"` and `isinstance(published, str)`.

- [ ] **Step 2: Verify the test fails**

Run: `uv run pytest -q tests/test_create_note.py::test_build_note_normalizes_yaml_date_scalars`

Expected: FAIL because the parsed rendered value remains `datetime.date`.

- [ ] **Step 3: Implement recursive scalar normalization**

Add `normalize_yaml_scalars` near the frontmatter helpers. Check `datetime.datetime` before `datetime.date`, return `value.isoformat()` for both, recurse through dictionaries, lists, and tuples, and return other values unchanged. Apply it to merged metadata immediately before `yaml.safe_dump`.

- [ ] **Step 4: Verify focused tests pass**

Run: `uv run pytest -q tests/test_create_note.py::test_build_note_normalizes_yaml_date_scalars tests/test_create_note.py::test_build_note_web_clip_has_required_fields`

Expected: 2 passed.

### Task 2: Reject incomplete web clips before mutation

**Files:**
- Modify: `tests/test_create_note.py`
- Modify: `tests/test_json_output.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`
- Test: `tests/test_create_note.py`
- Test: `tests/test_json_output.py`

**Interfaces:**
- Produces: `missing_required_metadata(note_type: str, metadata: dict[str, Any]) -> list[str]`.
- Produces JSON error: `{"error": {"code": "missing-required-metadata", "note_type": "web-clip", "fields": [...]}}`.

- [ ] **Step 1: Write failing no-mutation tests**

Add CLI tests for `web-clip --apply --stdin` with body-only input. Assert exit status 2, stderr names `source`, `author`, and `published`, no Markdown file exists, and a pre-existing static `INDEX.md` is unchanged.

- [ ] **Step 2: Write failing JSON contract test**

Run the same invalid creation with `--json`; assert exit status 2 and the exact error object described in Interfaces.

- [ ] **Step 3: Verify both tests fail for the expected reason**

Run: `uv run pytest -q tests/test_create_note.py::test_web_clip_preflight_rejects_missing_metadata_without_mutation tests/test_json_output.py::test_create_note_web_clip_preflight_json_error`

Expected: FAIL because the current helper writes the note and returns 0.

- [ ] **Step 4: Implement the preflight**

After `build_note`, parse the rendered frontmatter and call `missing_required_metadata`. For web clips, require non-empty string values for `source`, `author`, and `published`. Before resolving or writing the destination, return status 2 with either the stable JSON object or one concise human-readable error. Apply the same validation in dry-run mode so invalid automation cannot return success.

- [ ] **Step 5: Add and pass a complete stdin web-clip test**

Supply complete Markdown frontmatter through stdin, including an unquoted published date and Chinese author. Assert status 0, `AUDIT: OK`, and exact normalized metadata in the created note.

- [ ] **Step 6: Run focused create-note and JSON tests**

Run: `uv run pytest -q tests/test_create_note.py tests/test_json_output.py`

Expected: all tests pass.

### Task 3: Define UTF-8 stdin across platforms

**Files:**
- Modify: `tests/test_json_output.py`
- Modify: `tests/windows_installer_smoke.ps1`
- Modify: `obsidian_kb_skill/scripts/console.py`
- Test: `tests/test_json_output.py`
- Test: `tests/windows_installer_smoke.ps1`

**Interfaces:**
- Changes: `configure_utf8_stdio()` configures `sys.stdin`, `sys.stdout`, and `sys.stderr` as UTF-8 where `reconfigure` is available.

- [ ] **Step 1: Write a failing unit contract for stdin reconfiguration**

Monkeypatch `console.sys.stdin`, `stdout`, and `stderr` with recording streams exposing `reconfigure`; assert all three receive `encoding="utf-8"`.

- [ ] **Step 2: Verify the contract fails**

Run: `uv run pytest -q tests/test_json_output.py::test_configure_utf8_stdio_includes_stdin`

Expected: FAIL because stdin is not currently reconfigured.

- [ ] **Step 3: Implement the minimal shared-console change**

Call `_reconfigure_utf8(sys.stdin)` before configuring output streams. Keep existing handling for streams that cannot be reconfigured.

- [ ] **Step 4: Add Unicode round-trip coverage**

Extend the subprocess test to pass UTF-8 Chinese text plus an emoji in complete Markdown stdin and assert exact characters in JSON `rendered` output.

- [ ] **Step 5: Add the Windows smoke scenario**

In `tests/windows_installer_smoke.ps1`, write complete Markdown as UTF-8 bytes, redirect those bytes to the installed helper's stdin, create a web clip, and assert the resulting file contains the exact Chinese text and emoji. Preserve the current installer setup and cleanup behavior.

- [ ] **Step 6: Run local UTF-8 tests**

Run: `uv run pytest -q tests/test_json_output.py tests/test_cli_integration.py`

Expected: all tests pass. The Windows-specific smoke is additionally enforced by GitHub Actions on `windows-latest`.

### Task 4: Document complete Markdown input and regenerate artifacts

**Files:**
- Modify: `core/references/note-creation.md`
- Modify: `CHANGELOG.md`
- Regenerate: platform references and bundled Skill runtime files through `build.py`
- Test: `tests/test_build.py`
- Test: `tests/test_lazy_references.py`
- Test: `tests/test_skill_runtime.py`

**Interfaces:**
- Documents: complete frontmatter precedence, web-clip stdin example, preflight failure behavior, and the Vault-local content-file boundary.

- [ ] **Step 1: Add failing documentation assertions**

Extend lazy-reference/build tests to require the canonical note-creation reference to mention complete Markdown input, input-frontmatter precedence, required web-clip metadata, and the inside-Vault `--content-file` rule.

- [ ] **Step 2: Verify documentation tests fail**

Run: `uv run pytest -q tests/test_lazy_references.py tests/test_build.py`

Expected: at least the new content assertions fail.

- [ ] **Step 3: Update canonical reference and changelog**

Add a complete `web-clip --stdin` dry-run example with quoted metadata, explain that invalid required metadata exits 2 before mutation, and explicitly retain the content-file boundary. Record the hardening under the current unreleased changelog section.

- [ ] **Step 4: Regenerate distributed artifacts**

Run: `uv run python build.py`

Expected: generated platform references and bundled Python runtime match canonical sources.

- [ ] **Step 5: Verify generated artifacts**

Run: `uv run python build.py --check`

Expected: exit 0 with no drift.

### Task 5: Full verification

**Files:**
- Verify all changed files.

**Interfaces:**
- Consumes all previous task outputs; produces a release-ready verified worktree.

- [ ] **Step 1: Run formatting and diff checks**

Run: `git diff --check`

Expected: no output and exit 0.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -q`

Expected: all tests pass with no failures.

- [ ] **Step 3: Inspect generated and source diffs**

Run: `git status --short` and `git diff --stat`.

Expected: only planned source, tests, references, changelog, and generated artifacts are modified.

- [ ] **Step 4: Commit the implementation**

Stage only planned files and commit with `fix(create-note): harden web clip input validation`.
