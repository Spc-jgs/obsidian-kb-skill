# Heading Semantics — Decision Record

**Status: accepted.** Records why a retrieval helper never reads a heading for
what it *means*, and closes the residual question left open on #109. The line
has now been reached from three directions and ruled the same way each time;
this document exists so a fourth issue does not re-derive it, and does not
re-derive it wrongly.

## Why this document exists

Three issues arrived at the same boundary independently:

- **#86** set it as a non-goal while designing the resume pack: a missing
  section returns `missing-section` rather than being assembled from prose.
- **#115** was tempted to cross it when free-form notes returned almost nothing,
  and declined: *"不建议的方向：从任意正文推断章节语义。#86 明确把它列为非
  目标，本 issue 不推翻该决定。"*
- **#109** hit it from the other side — not "what does this section hold" but
  "is this section's *name* telling me these checkboxes are not todos" — and
  stopped, because answering it needs the same faculty.

Each ruling lives in an issue comment. A fourth issue would have to find three
of them to learn that this is a settled boundary rather than an oversight, and
the shape of the temptation guarantees there will be a fourth: every one of
these started as a real defect with a real user cost, where crossing the line
would have fixed the case in front of the author.

## The case that forces the question

On the reference Vault, one project note under `40-Projects/ai-bug-workflow/`
is laid out like this:

```
## 下一步行动
### P0：下一次迭代前完成      ← the project's real plan, a numbered list
### 可复用的项目落地检查表     ← 15 unchecked boxes, for landing *other* projects
```

Both `###` are siblings under the same `##`. Before #109's fix the note ranked
as the busiest project in the Vault on fifteen todos it does not have, and
reported a checklist question as its next step.

PR #127 fixed the ranking by scoping the count to the note's own next-actions
section, and that fix **does not reach this note**: the checklist is *inside*
that section. `open_tasks_in_next_actions` for it is still 15.

Nothing structural separates the two subsections. What separates them is that
one is called `可复用的项目落地检查表` and the other is called
`P0：下一次迭代前完成`.

## Decision: a heading's name is content, and helpers do not read content

The helper reports the heading. It does not interpret it.

The division is not "mechanical versus fuzzy" — it is **which layer is allowed
to be wrong in a way the user can catch**. A helper's output is read as fact: a
number in `open_tasks` is a count, and a user has no way to see the judgement
that produced it. An Agent's output is read as an Agent talking, is phrased in
sentences, and can be contradicted in the next turn. Reading
`可复用的项目落地检查表` and concluding "this is reusable material, not this
project's plan" is a good inference. It is also exactly the kind of inference
that should arrive with a visible author.

Two further reasons, both from this repository's own history:

**A word list is not a criterion, and this project has already paid for
treating it as one.** #115's defect was `后续行动` versus `下一步行动` — two
characters — and the consequence was not a slightly worse answer but
`missing_sections: [decisions, blockers, next_actions]` on a note that had all
three. Any "checklist-like heading" vocabulary is the same construction with a
larger surface: it will be right on the headings its author thought of, silently
wrong on the next one, and its failure will again be a confident output rather
than a refusal.

**The helper has no standing to define what counts as a todo.** `可复用的检查表`
means something in *this* Vault because its author writes that way. A helper
that hardcodes the judgement carries one Vault's vocabulary into every other
one — the same mistake as hardcoding another system's `incomplete` tag, which
#116 deliberately made overridable for exactly this reason.

## What ships instead

`next_action_heading` names the heading the item was taken from, and
`core/retrieval-references/review-projects.md` now requires the Agent to
**state it whenever it repeats a next action** — every time, not only when it
looks suspicious, because deciding it looks fine is the judgement the reader
needs to be able to check.

That turns an invisible helper-level guess into a visible Agent-level claim.
The user sees `next_action_heading=可复用的项目落地检查表` beside the item and
can disagree. Under the rejected alternatives they would see a number.

`tests/test_review_projects.py` asserts this case at its **real nesting**, so a
future change claiming to have fixed it has to say what it decided.

## Rejected alternatives

**Depth limiting — count only boxes directly under the next-actions heading,
not under its subsections.** This returns the right answer for the note above,
and it returns it by accident: it works only because `### P0` happens to use a
numbered list. A note writing its P0 items as checkboxes under `### P0` loses
its real todos and reports zero. That is fitting one note, not deriving a
criterion, and its failure direction is worse — silently erasing work rather
than over-counting it.

**A vocabulary of checklist-like heading words** (`检查表`, `模板`, `示例`,
`checklist`, `template`). This is #115's defect rebuilt deliberately. It also
inverts the burden: a note whose next-actions section is honestly titled
`发布检查表` would have its real todos discarded.

**Structural heuristics that stand in for the judgement** — items ending in a
question mark, items with no verb, subsections whose items are all short. Each
is a content judgement wearing a regex costume, which is worse than the
judgement itself: it is equally fallible and no longer legible as an opinion.

**Doing nothing beyond #127.** Rejected because the number stays wrong for this
note and nothing says so. Reporting `next_action_heading` is what makes "the
helper does not judge" an honest position rather than an excuse.

## What would reopen this

- A helper acquiring a legitimate reason to *refuse* rather than report — as
  filing does with `draft-incomplete`, where the signal is something the note
  states about itself (a tag, an unreplaced placeholder) rather than something
  inferred from its prose. A heading is authored prose, so this route stays
  closed unless a Vault-declared marker appears.
- Evidence that Agents in practice ignore `next_action_heading` and repeat
  checklist items anyway. That is a measurement about the instruction, not
  about the helper, and its fix is the instruction.
- A user configuring their own next-actions vocabulary. That is the user
  declaring their Vault's convention, not a helper inferring it, and it does
  not cross this line.

## Scope

**In scope**: the wording in `core/retrieval-references/review-projects.md` and
this record.

**Out of scope**: any change to `review_projects.py`. The counting behaviour
shipped in PR #127 is the accepted behaviour, including
`open_tasks_in_next_actions = 15` for the note above. That number is correct for
what it measures — boxes inside the section — and the reason it misleads is
recorded here rather than corrected away.
