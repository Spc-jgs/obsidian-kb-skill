# Shell capture detection — implementation plan

Design: `docs/superpowers/specs/2026-08-24-shell-capture-detection-design.md`
Issue: #167 (and #168, which depends on being able to name a shell)

## Release target

Minor on top of v1.35.0, folded into the pending v1.36.0. One new audit finding,
one extracted helper, no note changes shape, no migration runs. Branched off
`master` — nothing else is in flight that touches `audit_vault`.

Delivery rules as standing: RED tests before implementation, `build.py --check`
before the gate, every CI job green before merge.

## Task 1: One definition of "body content"

`_audit_empty_template` counts content inline. A second finding needs the same
count, and two loops would be free to drift.

- Extract `_body_content_chars(text) -> tuple[bool, int]` at module level,
  returning `(has_heading, content_chars)` with the existing semantics exactly:
  frontmatter stripped, lines beginning with `#` treated as headings and
  skipped, non-whitespace characters counted on the rest.
- `_audit_empty_template` calls it and keeps behaving identically.

RED first: the extraction is behaviour-preserving, so it gets no new assertion
of its own — the existing `empty-template-note` tests are its guard, and they
must stay green through the move. The identity guard belongs to Task 3.

## Task 2: The finding, and the two shapes it must catch

- `WEB_CLIP_MIN_CONTENT_CHARS = 400` beside the finding, with the measured
  distribution in a comment: shells at 100 and 220, drafts at 329 and 383,
  smallest real capture 799.
- `web-clip-captured-nothing`, severity `defect`, added to the severity table.
- Fires when `type == "web-clip"`, the note carries no tag from
  `process_inbox.DEFAULT_DRAFT_TAGS`, and `content_chars <
  WEB_CLIP_MIN_CONTENT_CHARS`.
- Message names the count and the floor, so a reader can tell a near miss from
  an empty file without opening the note.
- The existing `EXEMPT_NAMES` and `Templates/` guards apply as they do for
  `empty-template-note`.

RED first, all four before any of the code:

1. `test_reports_a_web_clip_that_captured_nothing` — the bare shape: prose
   placeholder, **no heading at all**, under the floor. This is the shape
   `empty-template-note` cannot reach and the structural predicate cannot see.
2. `test_reports_a_web_clip_whose_sections_are_all_placeholders` — the skeleton
   shape: full heading set, every section a placeholder line, under the floor.
3. `test_a_short_real_capture_is_not_reported` — a genuine capture at 799
   characters, the smallest observed on the reference Vault. Must stay silent.
4. `test_a_web_clip_that_declares_itself_incomplete_is_not_reported` — under the
   floor but tagged `incomplete`. Must stay silent; this is the case the design
   deliberately spares.

Tests 1 and 2 must be seen failing before the check exists, and 3 and 4 must be
seen failing against a deliberately over-wide version of the check (drop the
draft skip, raise the floor above 799) — a negative test that has never been
red is a test that never distinguished the fix from a blanket rule.

## Task 3: The three boundaries this creates

Registered in `docs/superpowers/specs/2026-08-12-consistency-inventory.md` in
the same change, rows 67–69.

- **The floor ↔ the distribution it came from.**
  `test_the_content_floor_is_the_value_the_distribution_supports` asserts the
  constant sits strictly between the largest shell and the smallest real
  capture as recorded, so moving it without re-measuring fails.
- **What `empty-template-note` counts ↔ what the new finding counts.** Relation
  removed by Task 1; `test_both_emptiness_findings_read_the_same_content_count`
  asserts identity by object so a local copy cannot come back.
- **The draft tag the audit skips ↔ the one `process_inbox` files on.** Relation
  removed by import; asserted in the same test that the audit's skip set *is*
  `DEFAULT_DRAFT_TAGS`, not an equal copy.

## Task 4: What the Agent reads

- `rules-and-errors.md` gains the row for `web-clip-captured-nothing`: what it
  means, and what to do — complete the capture, or tag it `incomplete` and leave
  it in the Inbox, which is the supported product for a capture that failed.
- The remedy must not be "strip the finding": the note is wrong, not mislabelled.
- `python build.py` regenerates the bundles; `build.py --check` gates.

Existing assertion `test_every_audit_code_is_documented_for_the_agent`, if one
exists, covers the new row; if it does not, the reference row is unguarded and
that is itself a registry row.

## Task 5: Verify against the real corpus

Not committed, run by hand before the PR:

- The audit over the reference Vault reports `web-clip-captured-nothing` on
  exactly the two known shells and on nothing else.
- Total finding count moves by exactly two.

Recorded in the PR body with the command, not in the repo.

## Out of scope

- The skeleton-shell criterion from §3 (one true positive; waits for a third
  shell).
- Fence-aware content counting (measured; changes no outcome on this corpus).
- #168's duplicate-source rule, which becomes tractable once a shell can be
  named but is its own change.
- Deciding what to do with the two existing notes in the user's Vault. The audit
  will name them; completing or deleting them is the user's call.
