# Telling a stubbed concept from a deleted note, using git history

*Issue #202. Reopens `2026-08-21-rejected-hypotheses.md` §1 on the condition
that section itself wrote down.*

## Where this comes from

§1 rejected splitting `broken-wikilink` into "concept placeholder" and "deleted
note". The criterion tried was inbound-reference counting, and it died because
every placeholder on the reference Vault was referenced exactly once — the same
as a deletion. The deeper reason it gave:

> From a single snapshot, "the note was deleted" and "the note is not written
> yet" leave the same trace: no file, and a link pointing at it. **Obsidian
> itself does not distinguish them.**

And the condition to reopen:

> A signal that genuinely separates the two — for example a Vault under git,
> where whether the target ever existed is **history rather than snapshot**;
> cost and availability would need separate evaluation.

The reference Vault is under git: 158 commits, 2026-06-10 to 2026-08-24. The
signal exists. This document is the separate evaluation §1 asked for.

## The criterion

For a target that resolved to no file, ask whether **any path that has ever
appeared in the repository's history** would have resolved it.

History is read once per audit:

```
git log --all --pretty=format: --name-only --diff-filter=ADRM -- '*.md'
```

`--all` so a note deleted on a branch still counts as having existed;
`--diff-filter=ADRM` so additions, deletions, renames and modifications all
contribute a path. The output is decoded with `review_captures._unquote_git_path`
— #201 is exactly the defect this would otherwise repeat, and on a Vault with
Chinese filenames it would repeat it silently and in the direction that makes
this feature wrong: an escaped path matches nothing, so every deleted note
would be reported as never written.

**Matching uses the audit's own resolution order**, not a looser one. A target
counts as having existed when the historical path's `name`, its `stem`, or its
stem with a `YYYY-MM-DD ` prefix removed equals the target's name — the three
keys `LinkIndex.matches` and `LinkIndex.dated_matches` use against the working
tree. A second, looser notion of "the same note" is exactly the drift this
repository keeps finding.

## Three outcomes, not two

| history | target ever existed | finding |
|---|---|---|
| unavailable | unknown | `broken-wikilink` (`defect`) — unchanged |
| available | yes | `broken-wikilink` (`defect`), message says when it was last seen |
| available | no | `link-to-unwritten-note` (`informational`) |

The third is a new code rather than a downgrade of the existing one. "History
confirms nobody ever wrote this" is a positive finding — it is how a concept
gets stubbed, which `LinkIndex.dated_matches` already names in its docstring —
and it carries more than a demoted `broken-wikilink` would. Keeping the codes
separate also keeps `broken-wikilink` meaning one thing: the link is broken, or
we cannot tell.

`informational` because linking a note that does not exist yet is standard
Obsidian usage. #159 settled that, and inventory row 48 already depends on it:
`broken-wikilink` is named there as excluded from `create-note`'s refusal set,
because refusing every `defect` would forbid writing a note that points forward.
The new code is `informational`, so it is outside that set by construction and
row 48 is untouched.

## History availability is reported, not assumed

The audit gains a top-level field saying what it had to work with:

```json
"link_history": {"source": "git-history", "paths": 316}
"link_history": {"source": "none", "reason": "not-a-git-repository"}
"link_history": {"source": "none", "reason": "shallow-clone"}
```

Following `review-captures`' `evidence` / `evidence_coverage`: a helper that
silently falls back produces output indistinguishable from the good path, which
is what #201 was. Here the stakes are higher than a wrong rate — without
history every link stays `broken-wikilink`, which is the current behaviour and
therefore invisible.

**A shallow clone is refused rather than trusted.** `git clone --depth 1`
leaves a truncated history in which nothing "ever existed", so every deleted
note would read as never written. Detected by `.git/shallow`, and by
`git rev-parse --is-shallow-repository`. This is different from a short but
complete history: a Vault initialised yesterday truthfully has no history, and
"never appeared" is then a true statement about a young repository. **No minimum
history depth is imposed** — any threshold would be a number nobody measured,
and the report states the path count so a reader can judge.

## What this cannot see

**Aliases.** `LinkIndex.matches` resolves `[[X]]` through a target note's
frontmatter `aliases`, but an alias lives in the file's *content*, and this
criterion reads only path names. A note that existed, was reachable only by its
alias, and was deleted, will be reported as `link-to-unwritten-note` — the wrong
one of the two. Reading historical blobs to recover aliases is possible and is
not done here: it turns one `git log` into a walk over every deleted file's
content, and there is no measured instance of the case it would fix.

**Zero true positives on the reference Vault.** This has to be stated plainly
because it is the weakest part of the change. All 21 distinct targets behind
the current 24 `broken-wikilink` findings have never appeared in 316 historical
paths, so on this corpus the criterion **only ever downgrades** and never
confirms a real breakage. The one note git records as deleted —
`40-Projects/2026-07-09 Obsidian KB Skill v1.8 发布与对话沉淀.md` — has no
inbound links, so it cannot produce the other outcome either.

The true positive therefore exists only in a synthetic fixture. That is
legitimate — the adversarial corpus is synthetic for the same reason — but it
means the "yes, it existed" branch is guarded by construction rather than by
observation, and this document is where that is recorded instead of being
discovered later from a passing suite.

## Cost

One `git log` per audit, not per link. Measured on the reference Vault:
**0.095s** for the full-history path query, against an audit that already walks
213 files. Two `git` probes precede it (`rev-parse --is-inside-work-tree`,
`--is-shallow-repository`), each of which exits immediately on a non-repository.

## Effect on the reference Vault

```
defect          32 -> 8
informational    8 -> 32
```

24 findings move; no finding appears or disappears. `broken-wikilink` goes to
zero on this Vault, which is itself worth noticing: it means the audit's largest
`defect` class was, in its entirety, the standard Obsidian practice of linking
a note before writing it.

## Acceptance

- A synthetic git fixture with both branches: a note linking a target that was
  committed and then deleted, and a note linking a target never committed. Both
  assertions red before the change.
- A hard negative: on a shallow clone and on a non-repository, no target is
  reclassified and `link_history.source` is `none` with a reason.
- A hard negative: the decoding is exercised by a non-ASCII target name, so
  #201 cannot come back through this path.
- Consistency inventory row: the history-matching keys ↔ `LinkIndex`'s
  resolution keys.
