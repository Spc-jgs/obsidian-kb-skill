# Task 3 Report: Pure Static-Index Plans

Status: DONE

Commit: `d1eb0344372d3533694d9c9d6682cc0033a87b9a`

## RED

Required focused command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q
```

Actual initial result: pytest collection failed with exit 2. Both test modules
failed to import `StaticIndexPlan` from `folder_index_policy.py`, which was the
expected missing Task 3 pure-plan API failure before production implementation.

Self-review added a second TDD cycle for three bound safety/compatibility
requirements:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q \
  -k 'legacy_defaults_for_invalid or enabled_defaults_for_invalid or rejects_multiline_title or separates_internal_symlink'
```

Actual result before the supplemental fixes: 4 failed, 2 passed, exit 1.
Legacy append raised on malformed plugin JSON, a multiline title was accepted
when `INDEX.md` was missing, and the Inbox symlink case used the physical route
inside the wikilink. Those failures directly exercised the missing behavior.

## GREEN and Regression

The supplemental targeted command passed 6 tests, exit 0, after the fixes.

Final focused command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q
```

Actual final result: 95 passed, exit 0.

Required Folder Index consumer regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py \
  tests/test_create_note.py tests/test_create_category.py \
  tests/test_process_inbox.py tests/test_detect_index.py \
  tests/test_audit_vault.py tests/test_vault_info.py -q
```

Actual final result: 231 passed, exit 0.

Additional verification:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/folder_index_policy.py \
  obsidian_kb_skill/scripts/inbox_plan.py
git diff --check
```

Both commands exited 0. The tracked-file scope gate also confirmed that the
commit contains exactly the four files permitted by the Task 3 brief.

## Self-review

- `StaticIndexPlan` is frozen and its `index` is Vault-relative whenever it is
  present. `before` and `after` are exact bytes with matching `sha256:` hashes.
- The planner is read-only. Tests compare index bytes before and after every
  append, managed, missing, invalid-config, multiline-title, and symlink case.
- LF/CRLF, UTF-8 BOM, and missing trailing-newline inputs retain their exact
  original byte prefix. New separators and entry terminators follow the
  existing index newline convention.
- Existing exact entries return `unchanged`; the compatibility append API does
  not duplicate or rewrite them.
- Folder Index-owned and Dataview-owned indexes return `unmanaged`. Missing
  static indexes return `missing` without creation.
- The strict pure planner rejects malformed/nonconforming enabled-plugin JSON,
  unsafe plugin filenames, unsafe config paths, non-regular static indexes,
  out-of-Vault paths, and multiline entry fields.
- `read_folder_index_config()` is unchanged. The legacy append API reuses the
  same pure policy core but deliberately falls back to the existing defaulting
  config reader for malformed JSON/filename settings, preserving current
  consumer behavior and result/path shapes.
- Internal symlinks are resolved for containment and physical Vault-relative
  index/destination paths, while wikilinks retain their logical Vault route.
  External symlinks remain rejected without reads or writes outside the Vault.
- `plan_inbox()` attaches a non-`None` `StaticIndexPlan` to every ready
  proposal. Any uncertain index ownership/config/path or multiline title
  yields blocked `unsafe-index-plan` with no proposal and no filesystem write.
- The existing append API signature and `StaticIndexResult` remain intact;
  successful writes still report `appended`, managed/missing outcomes retain
  their prior meanings, and only `action == "append"` writes bytes.
- No transaction writer, CLI wiring, build payload source, generated resource,
  merge, or push was added. `build.py` was not run because canonical generated
  payload sources were not modified.

## Concerns

None.

---

## Review Fix: Surrogate Config Errors and Required Index Type

Status: DONE

Commit: `604b64a0bc737422f969ef5fcb490eafd1c9ca39`

### Root Causes

1. `_validate_index_basename()` encoded the candidate inline while evaluating
   the length predicate. A JSON string containing an unpaired surrogate is
   validly decoded by Python's JSON parser, but strict UTF-8 encoding raises a
   raw `UnicodeEncodeError` before `FolderIndexConfigError` can be produced.
   Legacy append therefore never reached its existing stable policy-error
   fallback.
2. Task 3 made every ready proposal carry a concrete `StaticIndexPlan`, but the
   `InboxProposal.index` annotation retained Task 2's transitional `| None`.

### RED

Command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q \
  -k 'unpaired_surrogate or requires_a_static_index_plan'
```

Actual result before the fix: 5 failed, exit 1.

- Both `rootIndexFile` and user-specified `indexFilename` leaked
  `UnicodeEncodeError` from the pure planner instead of the stable
  `FolderIndexConfigError` contract.
- Both legacy append cases leaked the same exception instead of returning the
  prior `unmanaged` result with unchanged index bytes.
- `get_type_hints(InboxProposal)["index"]` was
  `StaticIndexPlan | None`, not `StaticIndexPlan`.

### GREEN and Regression

The same targeted command passed 5 tests, exit 0.

Focused command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q
```

Actual final result: 100 passed, exit 0.

Required Folder Index consumer regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py \
  tests/test_create_note.py tests/test_create_category.py \
  tests/test_process_inbox.py tests/test_detect_index.py \
  tests/test_audit_vault.py tests/test_vault_info.py -q
```

Actual final result: 236 passed, exit 0. This is the prior 231-test set plus
the five new review regressions.

Additional verification:

```bash
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/folder_index_policy.py \
  obsidian_kb_skill/scripts/inbox_plan.py
git diff --check
```

Both commands exited 0, and the scope gate confirmed exactly the four
Task 3-tracked files in the fix commit.

### Self-review

- Only `_validate_index_basename()` catches its own UTF-8 encoding failure and
  normalizes it to `FolderIndexConfigError(field)`. No outer catch was widened,
  so unrelated encoding or runtime failures remain visible.
- The validated byte sequence is reused for the portable 255-byte limit; valid
  basename behavior is unchanged.
- Pure plans now fail closed with stable code/field data for both plugin
  filename settings and perform no index write.
- Legacy append receives the normalized existing policy error, enters its
  established legacy-config fallback, returns `unmanaged`, and leaves exact
  index bytes unchanged without a traceback.
- `InboxProposal.index` is now statically and reflectively
  `StaticIndexPlan`. Runtime ready/blocked construction logic was not changed.
- The commit contains only the brief's four tracked files. No generated payload,
  transaction writer, merge, or push was introduced; `build.py` was not run.

### Concerns

None.
