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
saying how membership was established. Today the only origin is
`instance-directory`: the note sits inside the project's own directory.

That matters because every other way of establishing membership can be wrong.
A `project` frontmatter field can be missing on a note that clearly belongs; a
`related` wikilink can point at a same-named note in another folder. A note's
location cannot be stale in either direction — it is where the user put it.

`instance_directory` is `null` for a project note living directly at
`40-Projects`, which has no directory of its own. That is a valid pre-existing
layout, not an error, and such a project simply has no subordinate output to
gather.

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
than dropped silently, and the rest of the pack is still returned.

See `shared-errors.md` for the path and Vault guards this helper shares with
the rest of the Skill.
