# What This Note Depends On (reference)

Loaded when the user asks what a note builds on, what its conclusions rest on,
or which of its links actually matter.

`explore-neighborhood` shows every link a note declares. This answers the
narrower question: of those, which ones does the note say it **leans on**, and
for what.

## Run it

```
python <skill-root>/scripts/run_helper.py suggest-directed-links <vault> \
  --note 20-Learning/<note>.md --max-candidates 10 --json
```

## The judgement is not similarity

This is worth stating because the obvious guess is wrong. Two notes sharing a
subject are not related here, and two notes sharing a *word* are the case this
helper exists to reject: a note about a release quality gate and a note about
airport departure gates share "gate" and nothing else. A ranking built on word
overlap scores that pair highly; this helper scores it zero.

A candidate needs two things at once, **in one sentence of the source note**:

1. an explicit reference to the target, and
2. a phrase saying what the reference is for — *cites*, *delegates to*,
   *imports*, *follows*, *is expressed as a multiple of*, *for its … stage*.

A bare link is not a dependency. A note whose `## See also` section lists five
links has declared five links and no dependencies, and this helper will return
nothing for it — correctly. `links_without_a_dependency` counts those, so
"nothing found" can be told apart from "nothing linked".

## Directional, and never mirrored

`A` saying what it uses `B` for tells you nothing about `B`. Run it on the other
note to ask the other question; the answer is frequently empty, and that is the
normal case rather than a gap — the note that explains something usually does
not know who relies on it.

Never report a returned dependency as mutual. "This design cites those
measurements" is what the Vault says; "these two are related" is not.

## Reading a candidate

Each carries `target`, the `line` the sentence sits on, `markers` (which
dependency phrases fired), and `evidence` — the sentence itself.

**Quote the evidence.** It is one sentence the author wrote, and it is the whole
justification for the candidate. A candidate reported without it is this helper
being used as an oracle, which is exactly what it was built not to be.

`markers` is there so the reader can judge the strength of the claim. *delegates
to* is a stronger statement of dependency than *references*; the helper does not
rank them and neither should you without saying you are.

## What it deliberately does not do

- **No score to sort by.** There is no threshold and no confidence number. A
  candidate either has a declared dependency or it is not a candidate.
- **No new links.** Candidates are proposals for a human, never applied. Adding
  a link or a `related` entry is a write and belongs to `obsidian-knowledge-base`
  with a new explicit request.
- **No inference from proximity, folder, type or date.**
- **No resolution of an ambiguous name.** A link matching two notes is skipped
  rather than guessed, the same rule `explore-neighborhood` and `resume-project`
  follow.

Folder indexes and archived sources are excluded and counted in `excluded`: an
index lists its folder and an archive is captured evidence, and neither is a
dependency the author declared.

## The vocabulary is observed, not invented

The dependency phrases come from the 16 labelled positive directions frozen in
`tests/fixtures/directed_link_eval_cases.json`, written before any scorer
existed. A phrase with no label behind it would be a guess dressed as a
vocabulary, so the table does not grow on intuition — a Vault that states
dependency some other way will return nothing, and that is an honest miss rather
than a silent one.

## Refusals

- `missing-note` — no file at that path.

See `shared-errors.md` for the path and Vault guards this helper shares with the
rest of the Skill.
