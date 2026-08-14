# Explore One Note's Neighbourhood (reference)

Loaded when the user has a note in hand and asks what is connected to it.
`search-vault` answers *which notes mention these words*; this answers *what
this Vault says is connected to this one*.

## Run it

```
python <skill-root>/scripts/run_helper.py explore-neighborhood <vault> \
  --note 20-Learning/<note>.md --direction both --max-nodes 20 --json
```

`--note` is a Vault-relative path — one `search-vault` returned, or one the user
named. `--direction out` is "what does this note point at", `in` is "who points
at this note", `both` is the default.

## Everything here was declared, and nothing was inferred

Three kinds of edge, all of them written down by someone:

| `origin` | `direction` | What it means |
|---|---|---|
| `body` | `out` | The note's own text links to the target |
| `related` | `out` | The note's frontmatter `related` names the target |
| `body` / `related` | `in` | Some other note links here the same two ways |

That is the whole vocabulary. This helper **does not** score relatedness,
propose links, or read a link as *supports* / *contradicts* / *is evidence for*.
Two notes sharing a subject, sitting in one folder, or being written the same
day are not connected here — nobody said they were.

Say which kind an edge is when it matters. "The note links to this" and "the
note's `related` list names this" are both explicit, and they are not the same
claim: a body link is a reference made in passing, a `related` entry is a
statement about the note.

## Reading an edge

Each edge carries `source`, `target`, `direction`, `origin`, `line` and `state`.

`source` and `target` describe the link **as it was written**, so an inbound
edge's `target` is the note you are exploring. `neighbour` is the note at the
other end whichever way the arrow points — that is the field to read when you
want "the other note", and the one `nodes` is built from.

`line` is where the link appears in `source`, one-based, and is `null` for a
`related` entry, which lives in frontmatter rather than at a line worth citing.

`state` is one of three:

- `resolved` — the name matches exactly one file. `neighbour` names it.
- `ambiguous` — the name matches several, listed in `candidates`, and **none was
  used**. Report the ambiguity; picking one would present another note's content
  as this neighbourhood's, and the reader would have no way to tell.
- `unresolved` — the name matches nothing. The link is stale or the note was
  renamed. It is still returned, because dropping it would make a note with
  three broken links look like a note with fewer connections.

A link the note makes to itself is not an edge. A link written inside a code
fence or inline code is syntax being quoted, not a link, and is not an edge
either.

## What is left out by default

`excluded` counts the structural neighbours that were not followed:

- `index-note` — a folder index or MOC. It links every note in its folder, so
  following it returns the folder rather than a neighbourhood, and #133 already
  settled that an index is a listing rather than material.
- `source-archive` — the captured original behind a note. That is evidence
  reached from the note citing it, a different relationship with different
  trust, and conflating the two here would blur both.

`--include-structural` follows them anyway. Use it when the question really is
about structure — "why is this note only reachable through its index" is a real
question this answers.

A non-zero `excluded` with an empty `edges` list is a fact worth saying out
loud: this note's only declared connections are structural.

## Bounds

One hop. The neighbours of the neighbours are a different question with a
different cost, and this helper does not answer it — do not run it again on each
result to simulate two hops unless the user asked for exactly that.

`--max-nodes` (default 20) bounds the notes returned. When more exist,
`truncated` is `true` and `summary.nodes_available` gives the real count. Say so
rather than presenting a partial neighbourhood as the whole one.

Nodes are ordered by path, which is stable rather than meaningful: **the order
is not a ranking**. Nothing here says one neighbour matters more than another,
and presenting the first as the most relevant would be inventing the one thing
this helper refuses to compute.

## Read the notes, do not re-derive the graph

The neighbourhood names notes; opening them is a separate decision and a
separate cost. Do not follow links out of the notes you open, and do not search
for more material to fill the picture out.

Report each conclusion with the path it came from. A statement you cannot
attribute to a returned note is your inference, and it must be labelled as one.

## Refusals

- `missing-note` — no file at that path. Re-check the path rather than searching
  for a note with a similar name.

See `shared-errors.md` for the path and Vault guards this helper shares with the
rest of the Skill.
