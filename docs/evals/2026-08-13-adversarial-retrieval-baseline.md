# Adversarial retrieval — baseline (#117)

**Status: recorded, not accepted.** This document says what the current ranker
does on a set built to make it fail. It does not say that behaviour is correct.

## Why the stable corpus was not enough

`tests/fixtures/retrieval_eval_cases.json` holds 16 notes whose bodies total
2,123 bytes — the whole corpus is smaller than one document this set requires.
The v1.31 cross-lingual report stated the consequence directly: results were
identical for `EXPANSION_WEIGHT` from 0.25 through 1.00, so the corpus could
not choose a weight.

An evaluation set that cannot fail is a guard that was green from birth, one
corpus wide. It certifies whatever the ranker currently does, and a ranking
change measured against it can only look neutral or better.

## The set

`tests/fixtures/retrieval_adversarial_cases.json` — 20 notes, 23 queries, five
families, each with controls:

| Family | What it puts under stress | Control it carries |
|---|---|---|
| `dilution` | The same evidence paragraph in a 0.2 KB note and in **two** 30 KB notes — one an unstructured wall of text, one divided into 32 sections — with notes that mention the terms only in passing | An exact title must still win outright, so no fix can be a blanket length bonus |
| `crowding` | Five near-identical dailies against one insight note holding the conclusion | When the dailies really are the answer, several of them in Top-K is correct |
| `ambiguity` | `代理` is in `AMBIGUOUS_TERMS` and expands into both the `agent` and `proxy` concepts | The unambiguous synonym `智能体` must not drift |
| `field` | A stub whose title matches against a long note whose body answers the question | The stub's own alias must still retrieve it, so no fix can demote short notes wholesale |
| `no-answer` | A strong shared term with a note that does not answer the question | — |

Filler is Latin, generated deterministically from `filler_paragraphs`, and
asserted to share no token with any query: its only contribution is length.
Section titles are drawn from the same filler, so a sectioned note gains no
`headings` weight its unstructured twin lacks — structure is the only variable
between the two.

### The set shipped able to fail, but not at the question it was for (#136)

The first version generated every long note the same way: append unstructured
filler. Measured afterwards on the reference Vault — 186 notes, excluding
`95-Sources`, `Templates` and `Attachments`:

```
notes >= 10 KB: 19
  headings  median 30   min 12   max 100
  with <= 1 heading: 0
```

The three longest are 55.3 KB / 30 headings, 31.8 KB / 14, and 31.7 KB / 55.
**A real long note is long because it has many sections**, and the shape the
fixture used occurs zero times. The consequence was not theoretical: a
passage-ranking candidate scored byte-identically to master across all 22
cases, because a note with one heading has exactly one passage and any
heading-based split is a no-op on it. The set could not answer the question
#118 exists to ask.

Both shapes are now present. The unstructured note stays — an archived clipping
really can be a wall of text — and keeping the pair is what lets a result say
*which* shape a change helped, rather than that something moved.

## Baseline

Recorded in `tests/fixtures/retrieval_adversarial_baseline.json` against the
commit named in that file. **13 of 23 cases reproduce a limitation.**

> **Superseded in part by #118.** The section below records what the ranker did
> *before* section-level ranking, which is what the numbers in this document
> were measured against. The frozen baseline in
> `retrieval_adversarial_baseline.json` has since been re-recorded: on
> `adv-dilution-01` the sectioned 75 KB note now enters at rank 2 while its
> unstructured twin stays absent, dilution's MRR moves 0.867 → 0.9, and the four
> other families are unchanged on every metric. The limitation is narrower now,
> not gone — a long note *without* headings has one section and no remedy here
> at all.

### 1. Whole-document length normalisation

`adv-dilution-01` — **both** notes holding the exact evidence paragraph are
absent from Top-5. What does appear:

```
1. 11.903  20-Learning/retry/backoff-compact.md    ← same paragraph, 0.3 KB
2.  6.835  20-Learning/ops/grpc-deadline.md        ← mentions the terms in passing
3.  3.700  20-Learning/ops/queue-consumer.md       ← mentions the terms in passing
4.  3.382  20-Learning/ops/capacity-review.md      ← says outright it does not cover this
5.  3.236  20-Learning/ops/jitter-note.md          ← lists jitter variants by name
  (absent)  20-Learning/retry/backoff-handbook.md  ← same paragraph, 74.6 KB, 1 heading
  (absent)  20-Learning/retry/backoff-manual.md    ← same paragraph, 75.6 KB, 33 headings
```

`SearchDocument.weighted_length` sums every field across the whole document, so
a long note pays for text the query never asked about. Nothing between rank 2
and rank 5 contains the paragraph.

The two long notes are the measurement. They carry the same evidence, the same
filler, and sizes within 1 KB of each other; the only difference is that one is
divided into sections. A section-level ranker can help the second and cannot
help the first, so a candidate that moves both — or neither — is doing something
other than what it claims. This is the case #118 exists for, and #136 is why it
can now be read that way.

`adv-dilution-05` is the same limitation at depth, with a harder competitor:
the answer sits in the *last* section of the sectioned note, while
`capacity-review.md` names the same terms and states it does not cover them.
The short note wins by a factor of five —

```
1. 29.059  20-Learning/ops/capacity-review.md      ← "具体的退避取值不在本文范围内"
2.  5.838  20-Learning/agent/tool-loop.md
3.  5.688  20-Learning/retry/backoff-manual.md     ← holds the answer
```

— because it is the whole document and pays no length penalty, while the note
that answers is charged for thirty sections nobody asked about.

### 2. No Top-K diversity

`adv-crowding-01` — five near-identical dailies take all five slots; the note
holding the conclusion does not appear. Selection has no notion of redundancy.
The control `adv-crowding-03` shows why a blanket duplicate penalty is the
wrong fix: when the dailies are the answer, several of them belong in Top-K.

### 3. Expansion reintroduces the ambiguity it was told to avoid

`adv-ambiguity-03` is the interesting one, and it was not anticipated when the
set was designed. The query uses `智能体`, which is **unambiguous** — but it
expands to the `agent` concept, whose terms include `代理`, which then matches
`反向代理` in the network note. **Disambiguating at the query does not help,
because the expansion puts the ambiguous term back.**

### 4. Term overlap is treated as evidence

All six `no-answer` cases return hits. A query sharing one strong term with a
note produces that note; there is no notion of insufficient evidence. The
stable corpus scores 1.0 on its own no-answer group because those queries share
nothing with any note — the group was testing a different thing than its name
suggests.

### 5. Title weight outranks the answer

`adv-field-01` and `adv-field-03` — a stub whose body reads "这篇只是占位，内容
还没写" ranks above the note that answers the question, because
`FIELD_WEIGHTS["title"]` is 6x body.

## The aggregate is blind to the worst case in this set

Recorded beside the per-case rows, and the pair is the point:

| Group | Recall@5 | MRR | must-see misses | hard-negative hits |
|---|---|---|---|---|
| `dilution` | **1.000** | **1.000** | **1** | 0 |
| `crowding` | 0.750 | 0.750 | 1 | 0 |
| `ambiguity` | 0.750 | 0.750 | 0 | 5 |
| `field` | 1.000 | 0.750 | 0 | 0 |
| `no-answer` | — | — | 0 | 6 |

No-answer false-positive rate: **1.000** — every case returns something.

`dilution` scores a perfect 1.000 on both standard metrics while the note
holding the exact evidence paragraph is absent from Top-5. The metrics are not
wrong: `expected` names both notes in the pair, the short one ranks first, so
recall and reciprocal rank are satisfied. **They are simply blind to the thing
the family exists to measure.**

This is why #117 asked for the extra reporting items rather than a headline
number, and it is why the gate reads per-case rows as well as the aggregate. A
change that improved every mean in this table while one no-answer case started
returning a note would have made retrieval worse.

## How to use this baseline

It is a golden file. A ranking change is *supposed* to move it. Update it in
the same commit that changes the ranker and say which cases moved and why — the
whole point is that the movement is visible in a diff rather than absorbed into
an average.

Two assertions keep the set honest in both directions:

- `test_the_set_reproduces_at_least_one_real_limitation` fails if nothing fails,
  because a set everything passes has taught us nothing.
- `test_the_control_cases_pass_today` fails if the controls break, because a set
  that is uniformly red cannot tell a fix from a swap of one bias for another.

## Running against a real Vault

Nothing private is committed. Point the runner at your own annotated cases:

```bash
OBSIDIAN_KB_EVAL_CASES=~/eval/my-cases.json \
OBSIDIAN_KB_EVAL_VAULT=~/Documents/my-vault \
uv run --no-sync python -m pytest tests/test_retrieval_adversarial_eval.py -k real_vault -s
```

The cases file, the expected paths and the results stay in your directory. What
belongs in this repository is the aggregate and a redacted failure kind. The
run asserts the Vault is byte-identical afterwards.

## Latency

P50 17 ms, P95 24 ms across 23 queries on a 20-note corpus containing three
notes over 25 KB. Roughly double the 9/11 ms recorded before #136, which is
what a second 75 KB note costs: the corpus is read on every query and no index
is kept. Budgets in the test are set well above this so a slower CI machine
does not turn a performance check into a flake.

## Explicit non-goals

This change does not alter ranking, does not define a diversity penalty, and
does not treat several results from one project as bad by default. Whether
repetition is redundancy is decided per case by the fixture's own annotation.
