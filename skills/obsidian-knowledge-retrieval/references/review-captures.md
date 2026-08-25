# Review captures

Answers one question: **which captures were written and never opened again?**

Every other check in these Skills asks whether a capture is *faithful* — does
the note carry the source's facts, does it declare its evidence level, did it
stop when material was unavailable. None of them asks whether the capture was
ever used, and that is the question the whole workflow exists to serve.

Read-only. It never writes, and a cold capture is not a defect.

## Run

```
python <skill-root>/scripts/run_helper.py review-captures <vault> --json
```

- `--cold-after-days N` — treat a capture as reopened only if it was touched
  more than N days after it was written. Default `0`: touched on any later day
  counts as reopened.
- `--top-k N` — how many of the coldest captures to list. Default `20`.

## What it counts

Only note types whose value depends on being used later: `web-clip`,
`learning-note`, `insight-note`, `conversation-digest`.

A `daily-report` is written once by design and a `folder-index` is generated,
so counting either would measure the Vault's shape rather than its intake.

## Read `evidence` before quoting a number

| value | means |
|---|---|
| `git-history` | the Vault is a repo; exact for tracked files, mtime for the rest |
| `file-mtime` | no repo; mtime is perturbed by sync clients and by any checkout |

The field exists because a number whose provenance is unstated invites being
read as more precise than it is.

**`evidence` names the preferred source; `evidence_coverage` says what each one
actually dated.** The choice is per note, so the single word can be true and
misleading at once — quote the split, not the word:

```json
"evidence": "git-history",
"evidence_coverage": {"git-history": 100, "file-mtime": 0}
```

An earlier version of this page said "git tracked 57 of 214 notes". It did not:
all of them were tracked, and the helper was failing to decode the escaped
paths git prints for non-ASCII filenames, so it dated them by mtime instead.
Measured on that Vault the day it was fixed, the captures split **3 / 97**
before and **100 / 0** after. That is the reason this field exists, and the
reason to read it rather than the one-word summary.

## How to report it

**Lead with the per-type split, not the total.** A single "49% are cold" says
nothing actionable. The split says which kind of capture is paying off:

```
learning-note        revisit 71%  (20/28)
conversation-digest  revisit 50%  (1/2)
web-clip             revisit 42%  (24/57)
insight-note         revisit 31%  (4/13)
```

What a person writes while working gets reopened most. Beyond that, **say the
counts, not a story** — `conversation-digest` here is one note out of two, and
the gap between `web-clip` and `insight-note` rests on 57 and 13.

This page previously read the same measurement as "notes the user wrote get
reopened; clips do not", on a split of learning 75% / insight 31% / web-clip
23%. Those numbers came from the mtime fallback described above, and correcting
it moved `web-clip` from last place to second. A conclusion about how someone
works, drawn from a number whose provenance was not checked, survived here as
prose until the number was.

**Do not propose deleting anything.** The output is feedback on intake, not a
verdict on any note. A capture that has stayed cold for a year may still be the
one that matters next month.

## Why this exists

Christian Tietze, *The Collector's Fallacy* (2014): "having a text at hand does
nothing to increase our knowledge". Andy Matuschak sets the requirement this
implements — an inbox "should encourage lingering items to be removed (e.g. it
should be obvious when one has been passed over many times)".

The same source warns against exactly this Skill's shape: automatic import
fills a reading queue with "content you have no immediate connection to" and
removes the backpressure a person applies when adding things by hand. This
helper is the backpressure, measured after the fact.
