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
read as more precise than it is. On the reference Vault, git tracked 57 of 214
notes when this was written.

## How to report it

**Lead with the per-type split, not the total.** A single "43% are cold" says
nothing actionable. The split says which kind of capture is paying off:

```
learning-note  revisit 75%  (21/28)
insight-note   revisit 31%  (4/13)
web-clip       revisit 23%  (12/53)
```

Notes the user wrote while working get reopened; clips do not. That is a
finding about capture practice, and it is the reason this helper exists.

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
