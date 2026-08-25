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

One rule: **a template put a `- [ ]` under that heading**. Nothing else.

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
should you.** The queue is visibly of mixed kinds — real next actions,
conditional advice ("若使用 X，复核 Y"), and open-ended intent with no
finishable end state ("持续关注 X"). Two samples of the reference Vault gave
opposite impressions of that mix, which is exactly why nothing here claims to
have separated them.

Each item carries `text`, `path`, `line`, `heading`, `type` and the note's
`date`. Report those. The `type` is there because it is mechanically true, not
because it ranks anything.

Ordering is oldest note first — the only ordering the data supports. Undated
notes sort last rather than being assigned a guessed date.

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
the table above. The fix is to use a declared heading, not to widen this tool.
