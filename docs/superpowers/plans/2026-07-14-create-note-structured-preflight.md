# Create Note Structured Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a body-free structured preflight for `create-note`, fix four confirmed correctness defects, preserve every existing JSON contract, and release the verified result as v1.14.0.

**Architecture:** `create_note.py` continues to own rendering and CLI orchestration. `audit_vault.py` gains a reusable in-memory per-note audit entry point so preflight and post-write validation share the same rules without creating a temporary note. The new `--preflight-json` mode emits final frontmatter, rendered-byte identity, and validation findings while legacy dry-run/apply modes remain unchanged.

**Tech Stack:** Python 3.11+, argparse, pathlib, hashlib, PyYAML, pytest, uv 0.11.26, existing `build.py` distribution pipeline, Bash/PowerShell installers, GitHub Actions and GitHub CLI.

## Global Constraints

- Do not remove Vault discovery, template application, path safety, explicit apply, index handling, post-write audit, or structured errors.
- `--json`, `--apply --json`, and `--apply --compact-json` must retain their v1.13.0 success schemas.
- `--preflight-json` must never write a note or mutate an index and must never include `rendered` or the complete body.
- Preflight and post-write audit must call the same note-level validation implementation.
- Do not add preview persistence, preview IDs, caches, or dependencies.
- Use TDD for every behavior change and commit each independently testable task.
- Build only from canonical source files; regenerate packaged resources, platform adapters, standard Skill payload, and manifest through `build.py`.
- Release version is `1.14.0` only after local gates, installed-runtime verification, PR/CI, merge, release creation, and local Codex/WorkBuddy synchronization succeed.

---

### Task 1: Correct Existing Create-Note Boundary and Output Defects

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_note.py:305-525`
- Test: `tests/test_create_note.py`
- Test: `tests/test_json_output.py`
- Test: `tests/test_path_safety_e2e.py`

**Interfaces:**
- Consumes: `resolve_existing_within_vault(...) -> Path`, `split_frontmatter(...)`.
- Produces: canonical `content_path: Path | None`, structured invalid-Vault errors in every JSON mode, and final-body-aware human warnings.

- [ ] **Step 1: Add failing hostile-cwd relative content-file coverage**

Add a subprocess test that creates `vault/input.md` with `# INSIDE`, creates an outside working directory containing its own `input.md` with `# OUTSIDE`, invokes `create-note <vault> --content-file input.md --apply --compact-json` from the outside directory, and asserts the created note contains `INSIDE` and not `OUTSIDE`.

- [ ] **Step 2: Add failing JSON and template-warning coverage**

Add tests asserting:

```python
result = run_create_note(non_vault, "--apply", "--compact-json")
assert result.returncode == 2
assert result.stderr == ""
assert json.loads(result.stdout)["error"]["code"] == "INVALID_VAULT_ROOT"
```

and that a Vault `Templates/Insight Note.md` containing real prose does not emit
`frontmatter-only` during a human-readable apply with no stdin.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_create_note.py \
  tests/test_json_output.py \
  tests/test_path_safety_e2e.py -q
```

Expected: the new hostile-cwd test reads the outside file, invalid-Vault compact mode has empty stdout, and the template-backed apply emits the false warning.

- [ ] **Step 4: Use the canonical content path and consistent JSON error path**

In `main`, initialize `content_path: Path | None = None`, assign the resolver result, and read only that path:

```python
content_path: Path | None = None
if args.content_file:
    try:
        content_path = resolve_existing_within_vault(
            vault, args.content_file, label="--content-file"
        )
    except VaultPathError as exc:
        return report_cli_violation(
            exc, param="--content-file", json_mode=json_mode
        )

if content_path is not None:
    raw = content_path.read_text(encoding="utf-8")
```

For `InvalidVaultRootError`, keep the human stderr branch unchanged and emit the
existing structured shape in JSON modes without changing the historical exit 2:

```python
except InvalidVaultRootError as exc:
    if json_mode:
        print(json.dumps(structured_error(exc, param="vault"), ensure_ascii=False))
    else:
        print(f"error: {exc}", file=sys.stderr)
    return 2
```

Import `structured_error` from `vault_paths`; do not change path-escape exit status 3.

- [ ] **Step 5: Derive the warning from final rendered body**

After `rendered_meta, rendered_body = split_frontmatter(rendered)`, replace the raw-input check with:

```python
if not rendered_body.strip() and not json_mode:
    print("warning: empty body; creating a frontmatter-only note.", file=sys.stderr)
```

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add obsidian_kb_skill/scripts/create_note.py \
  obsidian_kb_skill/scripts/vault_paths.py \
  tests/test_create_note.py tests/test_json_output.py tests/test_path_safety_e2e.py
git commit -m "fix(create-note): preserve validated input boundaries"
```

### Task 2: Make Destination Creation Exclusive

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_note.py:291-302,472-474`
- Test: `tests/test_create_note.py`

**Interfaces:**
- Consumes: `resolve_dest(vault, folder, filename) -> Path` for dry-run display.
- Produces: `write_new_note(vault, folder, filename, rendered_bytes) -> Path`, which creates exactly one new file with mode `xb` and retries suffixes on `FileExistsError`.

- [ ] **Step 1: Add a failing exclusive-create unit test**

Monkeypatch `Path.open` or the helper's internal open function so the first `xb`
attempt raises `FileExistsError` after writing sentinel bytes to the unsuffixed
path. Assert `write_new_note(...)` returns `...-2.md`, preserves the sentinel,
and writes the requested bytes only to the suffixed path.

- [ ] **Step 2: Add a concurrent subprocess regression**

Start two `create-note` subprocesses for the same Vault, title, date, and body.
Assert both exit zero, the Vault contains two distinct files, and neither file
is truncated or overwritten.

- [ ] **Step 3: Run the new tests and confirm RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_create_note.py -k 'exclusive or concurrent' -q
```

Expected: `write_new_note` is missing and/or concurrent writes select the same destination.

- [ ] **Step 4: Implement exclusive suffix allocation**

Add:

```python
def destination_candidates(vault: Path, folder: str, filename: str):
    dest_folder = vault / folder
    base = dest_folder / filename
    yield base
    index = 2
    while True:
        yield dest_folder / f"{base.stem}-{index}{base.suffix}"
        index += 1


def write_new_note(
    vault: Path, folder: str, filename: str, rendered_bytes: bytes
) -> Path:
    dest_folder = vault / folder
    dest_folder.mkdir(parents=True, exist_ok=True)
    for candidate in destination_candidates(vault, folder, filename):
        try:
            with candidate.open("xb") as handle:
                handle.write(rendered_bytes)
            return candidate
        except FileExistsError:
            continue
    raise AssertionError("unreachable destination candidate loop")
```

Use `resolve_dest` only for dry-run prediction. On apply call `write_new_note`,
replace `result["path"]` with the actual returned path, and only then update the
index and audit.

- [ ] **Step 5: Run create-note and index tests**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_create_note.py tests/test_json_output.py \
  tests/test_detect_index.py tests/test_process_inbox.py -q
```

Expected: all tests pass, including existing `-2` behavior and new concurrency coverage.

- [ ] **Step 6: Commit**

```bash
git add obsidian_kb_skill/scripts/create_note.py tests/test_create_note.py
git commit -m "fix(create-note): create note files exclusively"
```

### Task 3: Extract In-Memory Per-Note Audit

**Files:**
- Create: `obsidian_kb_skill/scripts/note_types.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py:55-78`
- Modify: `obsidian_kb_skill/scripts/audit_vault.py:624-749`
- Test: `tests/test_audit_vault.py`

**Interfaces:**
- Produces: `audit_note_text(vault: Path, note: Path, text: str) -> list[Finding]`.
- Preserves: `audit_note(vault: Path, note: Path) -> list[Finding]` and all existing finding codes/order.
- Consumed by Task 4 preflight.

- [ ] **Step 1: Add failing audit parity tests**

For valid content, missing metadata, unresolved placeholders, empty content, an
invalid related entry, a missing web-clip field, an unclosed fence, a broken
wikilink, and required Vault-template headings in the wrong order, assert:

```python
candidate = vault / "30-Insights" / "Candidate.md"
prewrite = audit_note_text(vault, candidate, rendered)
candidate.write_text(rendered, encoding="utf-8")
postwrite = audit_note(vault, candidate)
assert prewrite == postwrite
```

- [ ] **Step 2: Run the parity tests and confirm RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_audit_vault.py -k 'note_text or prewrite' -q
```

Expected: import failure because `audit_note_text` does not exist.

- [ ] **Step 3: Implement the shared note-level rule engine**

Move `TYPE_TO_TEMPLATE` unchanged from `create_note.py` into
`note_types.py`; import it from both `create_note.py` and `audit_vault.py` so
template filename routing remains a single source of truth.

Add `_audit_required_template_headings(...)`. Read only the matching existing
Vault template, extract its `##` through `######` headings, extract candidate
headings the same way, and require the template sequence to appear in order.
Additional candidate headings are allowed. Emit:

```python
Finding(
    "missing-template-heading",
    relative.as_posix(),
    f"required template heading is missing or out of order: {heading}",
)
```

for the first missing/out-of-order heading. Skip the rule when the note type has
no conventional template, the Vault template is absent, or the candidate lives
under `Templates/`.

Add a private `_audit_note_content(vault, note, text)` which:

1. resolves `vault` and validates `note` as an in-Vault target;
2. computes the relative path;
3. parses frontmatter and records `invalid-frontmatter` when needed;
4. calls `_audit_metadata`, `_audit_related`, `_audit_web_clip`,
   `_audit_empty_template`, `_audit_folder_index_content`,
   `_audit_template_placeholders`, and `_audit_required_template_headings`;
5. checks odd fenced-code markers;
6. builds `by_name` and `by_stem` from `_all_linkable_files(vault)` and calls
   `_audit_links` against `_without_code_examples(text)`;
7. returns findings sorted by `(path, code, message)`.

Expose:

```python
def audit_note_text(vault: Path, note: Path, text: str) -> list[Finding]:
    vault = validate_vault_root(vault)
    note = resolve_target_within_vault(vault, note, label="--note")
    return _audit_note_content(vault, note, text)
```

Change `audit_note` to resolve/read the file and call the same private function.
Do not call `audit_vault` from `audit_note`; the parity tests protect the
existing per-note result.

- [ ] **Step 4: Run audit tests and confirm GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_audit_vault.py -q
```

Expected: all audit tests pass.

- [ ] **Step 5: Commit**

```bash
git add obsidian_kb_skill/scripts/note_types.py \
  obsidian_kb_skill/scripts/create_note.py \
  obsidian_kb_skill/scripts/audit_vault.py tests/test_audit_vault.py
git commit -m "refactor(audit): validate candidate note content in memory"
```

### Task 4: Add Structured Preflight JSON

**Files:**
- Modify: `obsidian_kb_skill/scripts/create_note.py:305-525`
- Test: `tests/test_json_output.py`
- Test: `tests/test_create_note.py`

**Interfaces:**
- Consumes: `audit_note_text(vault, dest, rendered) -> list[Finding]`.
- Produces: CLI flag `--preflight-json` and the exact schema in the approved design.

- [ ] **Step 1: Add failing schema, identity, and no-mutation tests**

Add subprocess tests for a long Unicode note asserting:

```python
payload = json.loads(result.stdout)
assert payload["applied"] is False
assert payload["dry_run"] is True
assert "rendered" not in payload
assert body not in result.stdout
assert payload["frontmatter"] == split_frontmatter(full_preview["rendered"])[0]
raw = full_preview["rendered"].encode("utf-8")
assert payload["content"] == {
    "sha256": hashlib.sha256(raw).hexdigest(),
    "utf8_bytes": len(raw),
    "line_count": len(full_preview["rendered"].splitlines()),
}
assert payload["validation"] == {"ok": True, "count": 0, "findings": []}
assert not list(vault.rglob("*Title*.md"))
assert index.read_text(encoding="utf-8") == original_index
```

Also assert a broken wikilink returns exit 2 with structured findings and no
mutation, and conflicting combinations with `--json`, `--compact-json`, or
`--apply` return JSON exit 2.

- [ ] **Step 2: Add the structural token regression**

Run preflight for a 100-line body and a 10,000-line body. Assert the long
response is no more than 512 bytes larger than the short response and is less
than 20% of the corresponding full dry-run JSON byte length.

- [ ] **Step 3: Run preflight tests and confirm RED**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_json_output.py tests/test_create_note.py \
  -k 'preflight_json or preflight_size' -q
```

Expected: argparse rejects `--preflight-json`.

- [ ] **Step 4: Implement argument and error-mode handling**

Add the flag, compute `json_mode = args.json or args.compact_json or
args.preflight_json`, and reject invalid combinations with:

```json
{
  "error": {
    "code": "invalid-output-mode",
    "message": "--preflight-json cannot be combined with --apply, --json, or --compact-json"
  }
}
```

- [ ] **Step 5: Build and emit the preflight payload**

After rendering and required-metadata validation, call `audit_note_text` and
construct:

```python
def finding_payload(findings: list[Finding]) -> dict[str, Any]:
    return {
        "ok": not findings,
        "count": len(findings),
        "findings": [
            {"code": item.code, "path": item.path, "message": item.message}
            for item in findings
        ],
    }

preflight = {
    "vault": str(vault),
    "folder": folder,
    "path": str(dest),
    "applied": False,
    "dry_run": True,
    "frontmatter": rendered_meta,
    "content": {
        "sha256": hashlib.sha256(rendered_bytes).hexdigest(),
        "utf8_bytes": len(rendered_bytes),
        "line_count": len(rendered.splitlines()),
    },
    "validation": finding_payload(findings),
    "suggested_links": None,
}
```

Print it with `ensure_ascii=False, indent=2`; return 0 when validation is clean
and 2 when it contains findings. Return before every mutation path.

- [ ] **Step 6: Run JSON and create-note tests**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_json_output.py tests/test_create_note.py tests/test_audit_vault.py -q
```

Expected: all selected tests pass and every legacy JSON assertion remains unchanged.

- [ ] **Step 7: Commit**

```bash
git add obsidian_kb_skill/scripts/create_note.py \
  tests/test_json_output.py tests/test_create_note.py
git commit -m "feat(create-note): add structured preflight output"
```

### Task 5: Update Canonical Documentation and Generated Artifacts

**Files:**
- Modify: `core/references/note-creation.md`
- Modify: `core/OBSIDIAN_KB.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Regenerate: `obsidian_kb_skill/scripts/resources/**`
- Regenerate: `platforms/**`
- Regenerate: `skills/obsidian-knowledge-base/**`
- Test: `tests/test_build.py`
- Test: `tests/test_doctor.py`
- Test: `tests/test_installers.py`

**Interfaces:**
- Produces: documented v1.14.0 workflow and synchronized versioned distributions.

- [ ] **Step 1: Update canonical workflow wording**

Document `--preflight-json` as the recommended preview and
`--apply --compact-json` as the apply step. Explicitly state that full `--json`
remains available when verbatim rendered output is required and that the apply
step still resubmits the same Markdown in v1.14.0.

- [ ] **Step 2: Add the release changelog and version**

Set project and lockfile version to `1.14.0`. Add CHANGELOG sections:

- Added: structured body-free preflight with final metadata, hash/size, and validation.
- Fixed: canonical content-file reads, exclusive note creation, JSON invalid-Vault errors, and template false warning.
- Changed: recommended create workflow uses structured preflight then compact apply.

- [ ] **Step 3: Regenerate artifacts**

Run:

```bash
uv run --locked --extra dev python build.py
```

Expected: canonical references, packaged resources, platform adapters, standard
Skill helper copy, and manifest update to version 1.14.0.

- [ ] **Step 4: Verify generated parity and version tests**

Run:

```bash
uv run --locked --extra dev python build.py --check
uv run --locked --extra dev pytest \
  tests/test_build.py tests/test_doctor.py tests/test_installers.py -q
```

Expected: build check succeeds and all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md README.md README_EN.md pyproject.toml uv.lock \
  core platforms skills obsidian_kb_skill/scripts/resources
git commit -m "chore(release): prepare v1.14.0"
```

### Task 6: Complete Release Verification, PR, Release, and Local Sync

**Files:**
- Verify only; do not add files unless a gate exposes a defect.

**Interfaces:**
- Produces: merged v1.14.0 release and identical healthy local Codex/WorkBuddy installs.

- [ ] **Step 1: Run all local release gates**

```bash
uv run --locked --extra dev pytest
uv run --locked --extra dev python build.py --check
uv run --locked --extra dev python -m build
uv run --locked --extra dev python -m compileall -q obsidian_kb_skill skills/obsidian-knowledge-base/scripts
bash -n install.sh
git diff --check
```

Expected: zero failures, generated artifacts current, wheel/sdist built, compile
and shell syntax clean, and no whitespace errors.

- [ ] **Step 2: Run disposable installed-runtime smoke tests**

Use the existing wheel/install tests plus a neutral hostile-cwd directory to run
standard Skill `doctor`, `vault-info`, legacy create-note JSON, structured
preflight, and compact apply. Confirm the installed payload does not import the
source checkout and preflight stdout does not contain the body.

- [ ] **Step 3: Record token comparison**

Using `o200k_base`, measure a 1,000-token Unicode body under v1.13.0 full
dry-run JSON and v1.14.0 preflight JSON. Record both counts in the PR/release
notes; require at least 80% reduction in preview response tokens.

- [ ] **Step 4: Push branch and create a ready PR**

Push `feature/create-note-compact-preflight`, create a non-draft PR targeting
`master`, and include behavior compatibility, security fixes, test totals, and
token measurements.

- [ ] **Step 5: Verify CI and merge**

Wait for every required GitHub Actions job, inspect failures from logs if any,
rerun local focused tests after fixes, and merge only when the PR is clean and
mergeable.

- [ ] **Step 6: Tag and publish v1.14.0**

Create an annotated `v1.14.0` tag on the verified merge commit and publish a
non-draft, non-prerelease GitHub Release describing structured preflight,
correctness fixes, compatibility, and measured token reduction.

- [ ] **Step 7: Reinstall and verify local runtimes**

Run `bash install.sh` for the normal Codex and WorkBuddy targets. Confirm both
installed manifests exactly match `skills/obsidian-knowledge-base/manifest.json`,
report version `1.14.0`, pass `doctor --json`, run structured preflight from a
neutral hostile cwd, and preserve the user's Vault/config.

- [ ] **Step 8: Final repository and release proof**

Verify local `master == origin/master == v1.14.0`, the release targets that
commit, the latest master CI is green, local installs are healthy and identical,
and no unrelated worktree or user change was modified.
