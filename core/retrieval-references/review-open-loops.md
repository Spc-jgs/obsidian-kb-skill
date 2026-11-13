# review-open-loops

Collect the unticked boxes the author left under a heading a template declared
as holding action items. Read-only; it never ticks, closes, moves or rewrites
anything.

```bash
python <skill-root>/scripts/run_helper.py review-open-loops <vault> \
  --top-k 50 --json
```

`--type <note-type>` restricts the queue and is repeatable.

## What bounds the queue

One rule: **a template put a `- [ ]` under that heading**, or the heading is
one of the fixed synonyms in `ACTION_HEADING_SYNONYMS`. Nothing else. The
synonym list is a checked widening of this tool: each value is the canonical
heading `待办事项`, and the item's reported `heading` stays the text in the
note. A project note's `下一步行动` and an English `Tasks` are not synonyms of
that list; they are collected because the templates declare them.

| heading | declared by |
|---|---|
| 待办事项 | daily-note, meeting-note |
| 影响与后续行动 | insight-note |
| 跟进事项 | person-note |
| 下一步行动 | project-note |
| 后续行动 | web-clip |
| Tasks / Implications and Actions / Action Items / Follow-up Items / Next Actions | the English templates |

A heading no template declares is **not** collected, however task-like it
looks. On the reference Vault `可复用的项目落地检查表` holds fifteen unticked
boxes that are a reusable question list — they end in `；` and can never be
ticked. They are out because no template declares that heading, not because a
heuristic judged them.

Also not collected: a ticked box, a box inside a fenced code block, a box with
nothing after it (every template ships one), and a box before the note's first
heading.

## Read the items, do not grade them

**The helper assigns no severity, no priority and no category, and neither
should you.** That is not because the items are poor. Read in full, the
reference Vault's 57 web-clip items are 44 concrete actions with a finishable
end state, 8 conditional ("若使用 X，复核 Y"), 3 open-ended intent ("持续关注
X"), and 2 too vague to act on — **mostly usable**. Nothing is classified here
because no mechanical predicate separates those four; the count came from a
person reading all 57.

Say that to the user if they ask how much of the queue is real: most of it,
and the rest is visible in the text they can read themselves.

Each item carries `text`, `path`, `line`, `heading`, `type`, the note's
`date`, and optional parsed `due_date` and `priority`. Report those. The `type` is there because it is mechanically true, not
because it ranks anything.

Ordering is two tiers. A task with an explicit due date (`📅 YYYY-MM-DD` or
`[due:: YYYY-MM-DD]`) sorts before every task that has none, earlier due date
first. An undated task then uses the note's frontmatter `date:`. A note with
no `date:` sorts last. `priority` is reported and does not change the order.
Checked boxes and `- [-]` stay out of the queue.

## How to report it

Lead with the count and the per-type split, then the oldest items:

```
95 open loops across 36 notes
  web-clip 57 · insight-note 19 · project-note 9 · daily-note 5 · learning-note 3 · person-note 2
```

Say the denominator. "95 open loops" alone reads the same across a 40-note
Vault and a 400-note one.

**Do not propose closing anything.** An item's absence of recent activity is
not evidence it was abandoned, and its presence is not evidence it still
matters. If the user asks what to drop, show them the oldest and let them say.

**An empty queue is a successful result.** Report it as "no open loops found
under the declared action headings", never as "everything is done" — the
second claims knowledge of headings this never read.

## When the count looks wrong

A note whose action items live under an invented heading is invisible here. That
is the design, but it is also the first thing to check when a user says
something is missing: ask which heading they wrote it under, and compare against
the table above and `ACTION_HEADING_SYNONYMS`. Adding a heading means editing
that table and its inventory guard. Do not widen the list from the prompt.
