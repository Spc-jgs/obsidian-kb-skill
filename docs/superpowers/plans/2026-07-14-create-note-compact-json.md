# Create Note Compact JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in compact JSON for successful `create-note` apply calls while preserving the existing `--json` contract.

**Architecture:** Keep rendering, writing, indexing, auditing, and link suggestion unchanged. Add a CLI output mode that participates in structured error handling and filters `rendered` only at the final successful apply boundary. Update canonical docs and regenerate platform artifacts through `build.py`.

**Tech Stack:** Python 3.11+, `argparse`, JSON, pytest subprocess integration tests, repository `build.py`.

## Global Constraints

- Existing `create-note --json` dry-run and apply payloads continue to include `rendered`.
- `--compact-json` implies JSON output and is valid only with `--apply`.
- Compact success preserves `vault`, `folder`, `path`, `applied`, `dry_run`, `audit`, and `suggested_links`, omitting only `rendered`.
- Compact validation/runtime failures use structured JSON.
- Do not add persisted previews, temporary drafts, hashes, or a new schema.
- Edit canonical sources and regenerate derived Skill/platform files.

---

### Task 1: Compact apply JSON contract

**Files:**
- Modify: `tests/test_json_output.py`
- Modify: `obsidian_kb_skill/scripts/create_note.py`

**Interfaces:**
- Consumes: existing `create-note` arguments and result object.
- Produces: `--compact-json`; error code `compact-json-requires-apply`; successful apply JSON without `rendered`.

- [ ] **Step 1: Write the failing compact apply test**

Add after `test_create_note_apply_json`:

```python
def test_create_note_apply_compact_json_omits_rendered(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "obsidian_kb_skill.scripts.create_note",
            str(vault), "--type", "insight-note", "--title", "Compact",
            "--stdin", "--apply", "--compact-json",
        ],
        input="# Compact\n\nBody.\n",
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["applied"] is True
    assert payload["dry_run"] is False
    assert payload["audit"] == {"ok": True, "count": 0, "findings": []}
    assert "rendered" not in payload
    assert Path(payload["path"]).read_text(encoding="utf-8").endswith(
        "# Compact\n\nBody.\n"
    )
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
uv run --no-sync python -m pytest tests/test_json_output.py::test_create_note_apply_compact_json_omits_rendered -q
```

Expected: FAIL because `argparse` rejects `--compact-json`.

- [ ] **Step 3: Write the failing no-apply guard test**

```python
def test_create_note_compact_json_requires_apply(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "obsidian_kb_skill.scripts.create_note",
            str(vault), "--type", "insight-note", "--title", "No Apply",
            "--stdin", "--compact-json",
        ],
        input="# No Apply\n",
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "error": {
            "code": "compact-json-requires-apply",
            "message": "--compact-json requires --apply",
        }
    }
    assert not list(vault.rglob("*No Apply*.md"))
```

- [ ] **Step 4: Run both tests and verify RED**

Run:

```bash
uv run --no-sync python -m pytest \
  tests/test_json_output.py::test_create_note_apply_compact_json_omits_rendered \
  tests/test_json_output.py::test_create_note_compact_json_requires_apply -q
```

Expected: both FAIL because the flag is absent.

- [ ] **Step 5: Implement minimal CLI behavior**

Add the parser flag:

```python
parser.add_argument(
    "--compact-json",
    action="store_true",
    help="With --apply, emit JSON without the rendered Markdown body",
)
```

After parsing, derive the output mode and reject compact dry-run before Vault validation:

```python
json_mode = args.json or args.compact_json
if args.compact_json and not args.apply:
    print(json.dumps({
        "error": {
            "code": "compact-json-requires-apply",
            "message": "--compact-json requires --apply",
        }
    }, ensure_ascii=False, indent=2))
    return 2
```

Replace output/error branches using `args.json` with `json_mode`. At the final output boundary:

```python
if json_mode:
    payload = (
        {key: value for key, value in result.items() if key != "rendered"}
        if args.compact_json
        else result
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    print(f"created: {dest}")
```

- [ ] **Step 6: Run focused tests and verify GREEN**

```bash
uv run --no-sync python -m pytest tests/test_json_output.py -q
```

Expected: all JSON tests PASS, including legacy apply `--json` retaining `rendered`.

- [ ] **Step 7: Commit**

```bash
git add obsidian_kb_skill/scripts/create_note.py tests/test_json_output.py
git commit -m "feat(create-note): add compact apply JSON output"
```

---

### Task 2: Usage guidance and generated payloads

**Files:**
- Modify: `core/references/note-creation.md`
- Modify: `README.md`
- Modify: `README_EN.md`
- Regenerate: `skills/obsidian-knowledge-base/**`
- Regenerate: `platforms/claude-code/**`
- Regenerate: `platforms/codex/**`
- Regenerate: `platforms/cursor/**`
- Regenerate: `platforms/qoderwork/**`

**Interfaces:**
- Consumes: `--compact-json` from Task 1.
- Produces: canonical preview/apply guidance and synchronized distributable payloads.

- [ ] **Step 1: Update canonical reference**

In the web-clip section, document:

```markdown
After checking a valid preview, repeat the invocation with
`--apply --compact-json` to write the note while returning only structured
path, audit, and link-suggestion data. Keep `--json` on dry-run when the full
`rendered` preview is needed. Plain `--apply` is also concise when
machine-readable output is unnecessary.
```

Add `--compact-json` to the write-helper apply example. State that legacy
`--apply --json` remains available when the caller needs final Markdown.

- [ ] **Step 2: Update Chinese and English READMEs**

Document these stable modes in both files:

```text
--json                 Full preview or legacy apply JSON including rendered.
--apply                Concise human audit and created path.
--apply --compact-json Structured apply result without rendered.
```

Do not deprecate or redefine `--json`.

- [ ] **Step 3: Regenerate adapters**

```bash
uv run --no-sync python build.py
```

Expected: standard Skill/platform references and deterministic manifest hashes update.

- [ ] **Step 4: Verify generated outputs and focused behavior**

```bash
uv run --no-sync python build.py --check
uv run --no-sync python -m pytest tests/test_build.py tests/test_json_output.py tests/test_skill_runtime.py -q
```

Expected: build check exits 0 and all selected tests PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md README_EN.md core/references/note-creation.md skills platforms
git commit -m "docs(create-note): recommend compact apply responses"
```

---

### Task 3: Full verification and distributable smoke test

**Files:**
- Verify only; no planned source modifications.

**Interfaces:**
- Consumes: generated standard Skill payload from Task 2.
- Produces: fresh source-suite and generated-helper evidence.

- [ ] **Step 1: Run complete tests**

```bash
uv run --no-sync python -m pytest
```

Expected: all tests PASS with zero failures.

- [ ] **Step 2: Run generated-Skill black-box smoke**

Create a temporary valid Vault with a MOC `30-Insights/INDEX.md`. Invoke:

```bash
python skills/obsidian-knowledge-base/scripts/run_helper.py create-note \
  "$TEMP_VAULT" --type insight-note --title "Compact JSON Smoke" \
  --stdin --apply --compact-json
```

Feed template-compatible Markdown. Assert `applied` and `audit.ok` are true,
`rendered` is absent, and `audit-vault --json` returns zero findings.
Delete the temporary Vault.

- [ ] **Step 3: Verify repository state**

```bash
git diff --check
git status --short --branch
git log -4 --oneline --decorate
```

Expected: no unstaged implementation changes, no whitespace errors, and design
plus implementation commits at the branch tip.

