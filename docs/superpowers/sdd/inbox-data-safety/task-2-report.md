# Task 2 Report: Byte-Preserving Typed Inbox Plans

Status: DONE

Commit: `e7c3bad06438dff74209dfa0175e8c3383043d78`

## RED

Command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Actual result: pytest collection failed with exit 2 because
`InboxPlanItem` could not be imported from `inbox_plan.py`. This was the
expected missing Task 2 typed-plan/render API failure, before any production
implementation was added.

## GREEN and Regression

Focused command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Actual final result: 35 passed, exit 0.

Required regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_process_inbox.py \
  tests/test_cli_integration.py tests/test_json_output.py -q
```

Actual final result: 82 passed, exit 0. The current CLI remains on its legacy
path, so Task 2 introduces no CLI or filesystem mutation behavior.

Additional verification:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_plan.py
git diff --check
```

Both commands exited 0.

## Self-review

- The commit contains exactly the two tracked files allowed by the brief:
  `obsidian_kb_skill/scripts/inbox_plan.py` and `tests/test_inbox_plan.py`.
- `InboxStatus`, `InboxProposal`, `InboxPlanItem`, and `InboxPlan` match the
  requested interface; all plan dataclasses are frozen. `SourceIdentity` is
  retained in each typed plan item.
- `StaticIndexPlan` is imported only under `TYPE_CHECKING`, remains a forward
  annotation at runtime, and every Task 2 proposal has `index=None`.
- The renderer uses `yaml.safe_dump()` only for each inserted value. It never
  serializes the existing frontmatter mapping. Existing bytes, comments, key
  order, quoting, BOM, LF/CRLF convention, body bytes, and trailing-newline
  state are preserved.
- Existing required keys are never replaced or duplicated. Existing
  `date`/`type`/`tags` values that are null, empty strings, or empty collections
  produce a blocked `ambiguous-empty-metadata` item.
- Rendered candidates are strictly decoded and reparsed through the shared
  frontmatter parser. Every inserted value must round-trip to the value emitted
  by PyYAML or rendering fails closed.
- `plan_inbox()` snapshots sources once and freezes the effective date once.
  It freezes source/render hashes, metadata updates, title, routing, canonical
  Vault-relative destination, and proposal bytes without writing to disk.
- Type and folder routing consume the shared catalog mappings. Keyword routing
  remains behavior-compatible with the current Inbox processor.
- The Inbox-local `_note_title()` exactly retains the current first-H1 or
  date-prefix-stripped filename behavior. No dependency on
  `audit_vault._note_title()` was introduced.
- Both target directory and destination pass through the shared Vault target
  resolver. Existing destinations and dangling destination symlinks are
  skipped; unsafe target/destination resolution is blocked.
- `legacy_plan_dict()` retains the historical ready-plan keys and meanings for
  `path`, `target`, `title`, `tags`, `type`, and `related_suggestion`, and the
  historical `skip` message for an unroutable note.
- Tests cover absent frontmatter, LF, CRLF, BOM, comments, quoted values, one or
  three missing keys, scalar/list tags, all required empty/null metadata,
  source/render hashes, route/date/destination proposal changes, destination
  conflicts, target symlink escape, ready/skipped/blocked states, legacy
  adaptation, and read-only source preservation.
- No CLI wiring, index planning, or filesystem write/move/delete API was added.

## Concerns

None.

---

## Review Fix: Duplicate Keys, Resolver Race, and No-op Validation

Status: DONE

Commit: `a572cfce1612bedee042a6e5989753b9855c6085`

### Root Causes

1. The shared frontmatter parser used PyYAML's normal mapping construction, so
   a later duplicate key silently replaced the earlier value before Inbox
   policy inspected the metadata.
2. Planning validated the target directory before destination resolution but
   did not revalidate the parent structure afterward. Replacing the target
   directory with a regular file between those calls therefore produced a
   syntactically in-Vault destination beneath a non-directory parent.
3. `render_frontmatter_updates()` returned immediately when the parsed snapshot
   reported no missing keys, bypassing the strict UTF-8 decode, shared parse,
   and mapping checks applied to rendered candidates with insertions.

### RED

Command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py -q
```

Actual result before the fix: 6 failed, 35 passed, exit 1.

- Duplicate top-level `type`, duplicate top-level `tags`, and a nested duplicate
  mapping key all incorrectly planned as `ready`.
- A deterministic monkeypatch replaced `30-Insights/` with a regular file
  between the target and destination resolver calls; the item incorrectly
  planned as `ready`.
- Invalid UTF-8 and non-mapping raw candidates with no missing updates returned
  without raising `ValueError`.

### GREEN and Regression

Focused command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py -q
```

Actual final result: 41 passed in 0.06s, exit 0.

Required regression command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py tests/test_process_inbox.py \
  tests/test_cli_integration.py tests/test_json_output.py -q
```

Actual final result: 88 passed in 2.20s, exit 0.

Additional verification:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_plan.py
git diff --check
```

Both commands exited 0.

### Self-review

- The fix commit contains exactly the two tracked files allowed by the Task 2
  brief. The shared `frontmatter.py` remains unchanged.
- An Inbox-local `SafeLoader` detects duplicate keys at every constructed YAML
  mapping depth before normal dict overwrite semantics apply. The second key's
  source mark becomes stable `duplicate-frontmatter-key` line/column data.
- Duplicate required top-level keys and nested mapping keys now produce a
  blocked item with no proposal. No source or destination bytes are written.
- After destination resolution, planning resolves the target again and requires
  the fresh target, first target, and resolved destination parent to match; the
  target and parent must still be directories. Any discrepancy fails closed as
  blocked `unsafe-destination-path`.
- The planning-time check does not replace Task 4's apply-time revalidation.
- Both no-op and insertion render paths call the same strict candidate validator.
  Invalid UTF-8, parse issues, and non-mapping frontmatter raise `ValueError`
  before raw bytes can be returned as a valid proposal.
- Existing byte-preserving rendering, immutable typed fields, local title
  behavior, `TYPE_CHECKING`-only `StaticIndexPlan`, and `index=None` remain
  unchanged.

### Concerns

None.

---

## Second Review Fix: Reject Duplicate Keys in Public Rendering

Status: DONE_WITH_CONCERNS

Commit: `fde3337d985efb255696599101459c6a39d8712d`

### Root Cause

The first review fix connected `_duplicate_frontmatter_issue()` to
`plan_inbox()`, but the public `render_frontmatter_updates()` validator still
delegated only to the shared frontmatter parser. Because that parser retains
PyYAML's later-key-wins behavior, both no-op and insertion render paths accepted
and returned candidate bytes containing duplicate mapping keys.

### RED

Command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py -q -k 'render_rejects_duplicate_key'
```

Actual result before the fix: 2 failed, 41 deselected, exit 1. Both the no-op
duplicate candidate and the candidate with only a missing `date` returned bytes
instead of raising `ValueError`.

### GREEN and Regression

Targeted command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py -q -k 'render_rejects_duplicate_key'
```

Actual result: 2 passed, 41 deselected, exit 0.

Focused command:

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py -q
```

Actual final result: 43 passed in 0.06s, exit 0.

Required four-file regression command (the former 88-test set now includes the
two new tests):

```bash
uv run --locked --extra dev pytest -o addopts='' \
  tests/test_inbox_plan.py tests/test_process_inbox.py \
  tests/test_cli_integration.py tests/test_json_output.py -q
```

Actual final result: 90 passed in 2.21s, exit 0. `git diff --check` also exited
0.

### Self-review

- The commit changes only `inbox_plan.py` and `test_inbox_plan.py`; the shared
  frontmatter parser and all other tracked files remain unchanged.
- `_validate_rendered_candidate()` now passes the exact candidate bytes to the
  same Inbox-local `_duplicate_frontmatter_issue()` used by planning.
- Both no-op and insertion paths already converge on that validator, so neither
  can return duplicate-frontmatter bytes.
- A duplicate candidate raises `ValueError` before the existing strict UTF-8,
  shared parse, mapping, and inserted-value round-trip checks complete.
- Existing byte-preserving behavior and all previous Task 1/Task 2 regression
  coverage remain green.

### Retained Concern

Per the reviewer decision, alias-based duplicate keys can report the anchor
key's line/column rather than the alias occurrence. Duplicate aliases are still
rejected; only that diagnostic location is imprecise. This Minor issue is
explicitly out of scope for this narrow fix wave.
