# Retrieval Metadata Filters Implementation Plan

Design: `docs/superpowers/specs/2026-08-06-retrieval-metadata-filters-design.md`

## Release Target

Minor on top of v1.28.0 — the retrieval helper gains optional arguments and two
result fields. Every new argument is optional and the unfiltered output is
unchanged apart from the added per-result `type` and `date`, so no Vault
migration and no write-path change is involved.

Delivery rules for this branch follow the standing project convention: never
implement on `master`, RED tests before implementation, `python build.py`
before any doc assertion runs, and `build.py --check` before the release gate.
Every PR waits for all CI jobs to report green before it is merged.

## Task 1: Share the non-note exemption

The narrowest change and the one that stands alone; it ships even if the rest
is deferred.

- Move `EXEMPT_NAMES` out of `audit_vault` into the shared note domain
  (`note_catalog`) and import it back into `audit_vault` under the same name so
  no existing caller changes.
- `note_catalog` is **not** in the retrieval bundle today — `build.py`'s
  `RETRIEVAL_HELPER_FILES` is an explicit whitelist of seven modules and
  `audit_vault` is deliberately not among them. Add `note_catalog` to it. The
  module imports only `dataclasses`, and Task 4 needs `VALID_NOTE_TYPES` from it
  anyway to validate `--type`.
- `normalize_tag_key` moves the same way, for the same reason: Task 2 matches
  tags with it, and two definitions of "same tag" across the two Skills would
  drift.
- `search_vault._markdown_files` skips any file whose *name* is in the set, at
  any depth — `20-Learning/Python/AGENTS.md` counts.
- Skipped scaffolding is not an `issues` entry: it is not a malformed note, and
  the `issues` list is for things the user may need to fix.
- `scanned` gains `excluded` so the count still reconciles.

RED first:

- a fixture Vault with `README.md`, a nested `sub/AGENTS.md`, and one real note,
  asserting only the note is indexed and `scanned.excluded == 2`;
- a drift-lock asserting `EXEMPT_NAMES` has exactly one definition across the
  package, matching the shared error-code contract test's approach.

## Task 2: Filter domain, no CLI yet

Pure functions over already-parsed documents, so they are testable without
subprocesses.

- Extend `SearchDocument` with `note_type: str | None` and `note_date: str |
  None`, both read from the frontmatter `_document` already parses. No extra
  I/O, no extra read of the file.
- `parse_note_date(value)` accepts a `datetime.date`, or a string whose first
  ten characters are ISO `YYYY-MM-DD` (PyYAML returns a `date` for an unquoted
  value and a `str` for a quoted one — both occur in the reference Vault).
  Anything else is "no date", never an exception.
- `Filters` dataclass with `types`, `tags`, `after`, `before`, and a
  `select(documents)` returning the surviving documents plus an exclusion
  tally keyed by dimension, with `missing-date` counted separately from a date
  that simply falls outside the range. A note is counted against the first
  dimension that rejects it, so the tally sums rather than double-counting.
- Repeats within one dimension are OR; dimensions combine with AND.
- Tag matching reuses `normalize_tag_key`, so `--tag springboot` finds
  `spring-boot`. Filtering must not reproduce the separator bug the audit was
  just fixed for.

RED first: one test per dimension, one for two dimensions combined, one for
`missing-date` being counted apart from an out-of-range date, and one asserting
tag matching survives a separator and plural difference.

## Task 3: Wire filters into search

- Filters run over the loaded documents *before* scoring, so IDF is computed
  over the filtered set and `score` keeps its current meaning.
- The response gains `filters` exactly as the design specifies: `applied`,
  `candidates`, `matched`, `excluded`.
- `filters` is present whenever any filter is active and omitted otherwise, so
  an unfiltered call's payload does not grow.
- Each result gains `type` and `date`.

RED first: a Vault where a filter matches nothing, asserting `results == []`
*and* `filters.excluded` explains which dimension removed everything. The
silent-empty case is the one this whole design exists to prevent.

## Task 4: CLI and refusals

- `--type`, `--tag` repeatable; `--after`, `--before` single ISO dates.
- New refusals in the established `invalid-*` shape: `invalid-date`,
  `invalid-date-range`, `invalid-type`, `invalid-tag`. Exit 2, structured error
  payload, nothing else emitted.
- Register the new codes in the retrieval error-code contract so
  `tests/test_error_code_contract.py` covers them without a hand-maintained
  list, and regenerate `core/retrieval-references/shared-errors.md` if the
  shared block moves.

RED first: one test per refusal, asserting exit code, `error.code`, and that no
results are emitted alongside a refusal.

## Task 5: Skill instructions

- `core/RETRIEVAL.md` step 3: resolve relative time expressions against today's
  date before calling, and pass ISO dates. The helper never parses "上周".
- `core/retrieval-references/search.md`: when to filter, how to read
  `filters.excluded`, and the rule that an empty result under an active filter
  is reported as "nothing matched this filter", never as "your Vault has
  nothing on this".
- Add the four refusal codes to the existing `## Refusal Codes` table.
- Run `python build.py` — six artifacts and both manifests regenerate — then
  `build.py --check`.

## Task 6: Regression fixture

- Commit the twelve reference queries as a fixture with their expected
  non-knowledge-file count, so the P1 improvement (18% → 3% of top-5 slots)
  cannot silently regress.
- The fixture runs against a synthetic Vault committed to `tests/fixtures`, not
  against the user's real Vault; the real-Vault numbers stay in the design doc
  as the evidence that motivated it.

## Verification gate

- Full suite green locally, `build.py --check` clean.
- `uv lock` if and only if the version changes; see the release checklist.
- PR opened, **all CI jobs green before merge** — the 1.28.0 release failed
  `uv sync --locked` on every job while the local suite passed, so local green
  is not evidence.
- Re-run the twelve reference queries against the real Vault and report the
  before/after noise count in the PR.

## Out of scope

Ranking weights, BM25, vector retrieval, answer synthesis, and the connectivity
signal parked in issue #57.
