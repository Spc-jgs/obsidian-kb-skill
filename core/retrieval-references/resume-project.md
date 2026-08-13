# Resume One Project (reference)

Loaded only after the user has chosen a project to pick up. `review-projects`
answers *which* project; this answers *what belongs to it*.

## Run it

```
python <skill-root>/scripts/run_helper.py resume-project <vault> \
  --note 40-Projects/<project>/<project-note>.md --json
```

`--note` is the project note itself, which `review-projects` returned as
`path`. Pass `--as-of YYYY-MM-DD` only when the user asked about a specific
date; resolve the date yourself, the helper never parses "上周".

## What it returns, and why that is trustworthy

`sources` lists the notes that belong to this project, each with an `origin`
saying how membership was established, and `origins` listing every route that
reached it. Three exist, **in descending order of trust**:

| `origin` | The claim | How it goes wrong |
|---|---|---|
| `instance-directory` | The note sits inside the project's own directory | It cannot be stale in either direction — it is where the user put it |
| `project-field` | The note's frontmatter names this project | The field can name the wrong project of the same name, and is missing on many notes that clearly belong |
| `related-link` | The project note's `related` links to it | Maintained by hand, and a link resolves by name |

Say which origin a claim rests on when it matters. "This decision is in a note
filed under the project" and "this decision is in a note the project note links
to" are different strengths of evidence, and the reader is entitled to both.

The bound is layered: a declaration never displaces a note whose membership is
readable from where it sits. When `truncated` is true, what was dropped is the
weakest layer first.

`instance_directory` is `null` for a project note living directly at
`40-Projects`, which has no directory of its own. That is a valid pre-existing
layout, not an error — #95 made migrating it a non-goal — and for such a project
the two declared routes are the **only** membership claims that exist.

Ambiguity is reported and never resolved: see `ambiguous-related-link` below.
Only explicit declarations count. Sitting nearby, sharing a subject, or being
linked from the project note's *body* establishes nothing — a body wikilink is
a reference, not a claim of membership.

## What the pack answers

`resume` holds what the **project note** says, one entry per field, each with
the path and line it came from: `goal`, `decisions`, `blockers`,
`next_actions`. A field the note does not answer is `null` and named in
`missing_sections`.

`from_sources` holds what the **source notes** say, keyed by the same fields
plus `constraints` and `evidence` — a project note has no section for those,
so their absence there is not a gap. Each entry cites its own path and line.

`contested` names fields answered on both sides. That is not automatically a
contradiction; a decision may simply be restated. **Report both and let the
user judge** — the pack deliberately does not pick a winner, and neither
should you. Recency is not authority: a project note updated last week can
still be describing a constraint a digest settled months ago.

`missing_sections` is a fact about the note, not a defect to fix. A Vault using
custom templates may legitimately have none of the standard sections; say what
is unavailable rather than assembling an answer out of surrounding prose.

## Never read `missing_sections` on its own

`missing_sections` says the pack could not fill a field. It does **not** say the
project never recorded one. Read it together with `headings`, which splits the
note's own headings into `matched` (names this pack understands) and
`unmatched` (everything else):

- **`unmatched` is non-empty** — the field may well be recorded under one of
  those headings. Say "not under a heading I recognise; the note also has
  `<names>`" and let the user look. Never say the project has no decisions.
- **Both lists are empty** — the note has no headings at all. This is the one
  case where a missing field really does mean the content is absent.
- **`matched` contains the field's own heading while the field is still
  missing** — the section exists and is empty.

The pack does not guess which unmatched heading holds what, and neither should
you from the names alone: reading them is a judgement about content, so open the
note before saying anything about it. This distinction exists because the two
readings send a user in opposite directions — one goes looking, the other writes
a decisions log that is already there.

Heading names are matched literally, in the locales the templates declare plus
variants observed in real Vaults. A note that writes `后续行动` where the
template says `下一步行动` is understood; a synonym nobody has seen yet is not,
and shows up in `unmatched` rather than being guessed at.

Source notes get no such report. A source contributing nothing is the ordinary
case — a meeting note in the project folder was never expected to answer these
fields — so its `fields: []` is not a signal of anything. The project note is
different: answering these fields is what it is for.

## Bounds

`--max-sources` (default 5) keeps the pack a known number of reads. Sources are
ordered newest first, because resuming needs current state. When more exist,
`truncated` is `true` and `summary.sources_available` gives the real count —
say so rather than presenting a partial pack as the whole picture. An undated
note sorts last but is never dropped for lacking a date.

## Read the sources, do not re-derive them

The pack tells you which notes to open. Open those and no others: do not list
the project folder, do not search for related material, do not follow links out
of curiosity. The bound exists so resuming a project costs a known number of
reads rather than an unbounded walk.

Report each conclusion with the path it came from. A statement you cannot
attribute to a returned source is your inference, and it must be labelled as
one.

## Refusals

Structured refusal through `{"ok": false, "error": {"code", "message"}}`:

- `missing-note` — no file at that path. Re-check the path `review-projects`
  returned rather than searching for a note with a similar name.
- `not-a-project-note` — the path is not typed as a project note. The pack
  resumes projects; pointing it at a digest or an insight is a caller error,
  not a Vault problem.
- `unreadable-frontmatter` — the note's YAML could not be parsed. Report it and
  stop; this Skill never repairs a note.

A source whose own frontmatter is unreadable is reported in `issues` rather
than dropped silently, and the rest of the pack is still returned. Two more
entries appear there, both about links the pack refused to follow:

- `ambiguous-related-link` — the name matches more than one note, listed in
  `candidates`. **None was used.** Picking one could file another project's
  material into this pack, where it would read as this project's own history
  and the reader would have no way to tell. Report the ambiguity and let the
  user say which they meant, or ask them to disambiguate the link.
- `unresolved-related-link` — the name matches no note at all. The link is
  stale or the note was renamed; say so rather than treating the project as
  having less material.

See `shared-errors.md` for the path and Vault guards this helper shares with
the rest of the Skill.
