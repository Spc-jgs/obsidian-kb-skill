# Task 1 Report: Runtime Models and Ownership-Free Type Boundary

## Status

DONE

## Implementation

- Added the internal `inbox_tx` package marker without re-exporting internals.
- Added stdlib-only, planner-independent runtime models for every public type
  named in the brief.
- Implemented frozen dataclass shapes and exact transaction state/status values.
- Added direct-constructor validation for apply/restore status consistency,
  runtime status membership, recovery debris classification, and all specified
  Vault-relative paths.
- Kept path validation lexical: it uses `Path.parts` and `Path.is_absolute()`
  and never resolves or accesses the filesystem.
- Added `InboxTransactionError`, preserving the exact frozen failure object and
  using its message, plus the checkpoint injector protocol.
- Added focused contract tests covering all imports, exact fields, frozen
  mutation rejection, defaults through construction, status invariants, path
  invariants, no-filesystem validation, exception behavior, protocol shape,
  package-marker behavior, and the planner-free AST import graph.

## Files

- `obsidian_kb_skill/scripts/inbox_tx/__init__.py`
- `obsidian_kb_skill/scripts/inbox_tx/models.py`
- `tests/test_inbox_tx_models.py`

No production or test files outside the Task 1 allowlist were changed.

## RED evidence

Command:

```text
uv run --locked --extra dev pytest tests/test_inbox_tx_models.py -q
```

Result: exit `2`, during collection, before any production code was created.
Relevant output:

```text
ERROR collecting tests/test_inbox_tx_models.py
tests/test_inbox_tx_models.py:11: in <module>
    import obsidian_kb_skill.scripts.inbox_tx as inbox_tx
E   ModuleNotFoundError: No module named 'obsidian_kb_skill.scripts.inbox_tx'
ERROR tests/test_inbox_tx_models.py
Interrupted: 1 error during collection
```

This was the expected RED because the test imported the required new runtime
boundary and the `inbox_tx` package did not yet exist.

## GREEN and regression evidence

Initial focused GREEN after minimal production implementation:

```text
uv run --locked --extra dev pytest tests/test_inbox_tx_models.py -q
..........................................................               [100%]
```

After removing one duplicate path-test parameter, the fresh submission checks
were:

```text
uv run --locked --extra dev pytest tests/test_inbox_tx_models.py -q
.........................................................                [100%]
```

Result: exit `0`, 57 focused model tests passed.

```text
uv run --locked --extra dev python -m compileall -q \
  obsidian_kb_skill/scripts/inbox_tx
```

Result: exit `0`, no output.

```text
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py \
  tests/test_inbox_transaction.py \
  tests/test_process_inbox.py -q
........................................................................ [ 97%]
..                                                                       [100%]
```

Result: exit `0`, 74 related Inbox regression tests passed.

`git diff --cached --check` also exited `0` before commit, and the staged path
list contained exactly the three Task 1 files.

## Commit

`d0d4284` — `refactor: define inbox transaction runtime models`

The commit contains 3 new files and no unrelated changes.

## Self-review

- Completeness: every produced interface and every runtime invariant from the
  amended 190-line brief is represented in implementation and focused tests.
- Quality: models are immutable and cohesive; the single private path helper
  centralizes error behavior without filesystem coupling; exception and
  protocol contracts are explicit.
- Independence: `models.py` imports only `enum`, `dataclasses`, `pathlib`, and
  `typing`; the required AST test prevents absolute, relative, aliased, and
  `from` imports of `inbox_plan`.
- YAGNI: no factory API, serialization, planner conversion, wildcard exports,
  path resolution, I/O, or later-task lock/session behavior was added.
- Test quality: tests exercise real constructors and observable behavior. The
  collection failure established RED before production code, all allowed
  statuses are covered, invalid status/consistency/classification cases are
  covered, every specified path-bearing model is covered, and an explicit
  monkeypatch guard detects filesystem access.
- Scope: the Task 1 commit changes only the allowlisted package marker, model
  module, and focused test module.

## Concerns

None.
