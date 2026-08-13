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

`tests/fixtures/retrieval_adversarial_cases.json` — 18 notes, 22 queries, five
families, each with controls:

| Family | What it puts under stress | Control it carries |
|---|---|---|
| `dilution` | The same evidence paragraph in a 0.2 KB and a 30 KB note, with six notes that mention the terms only in passing | An exact title must still win outright, so no fix can be a blanket length bonus |
| `crowding` | Five near-identical dailies against one insight note holding the conclusion | When the dailies really are the answer, several of them in Top-K is correct |
| `ambiguity` | `代理` is in `AMBIGUOUS_TERMS` and expands into both the `agent` and `proxy` concepts | The unambiguous synonym `智能体` must not drift |
| `field` | A stub whose title matches against a long note whose body answers the question | The stub's own alias must still retrieve it, so no fix can demote short notes wholesale |
| `no-answer` | A strong shared term with a note that does not answer the question | — |

Filler is Latin, generated deterministically from `filler_paragraphs`, and
asserted to share no token with any query: its only contribution is length.

## Baseline

Recorded in `tests/fixtures/retrieval_adversarial_baseline.json` against the
commit named in that file. **12 of 22 cases reproduce a limitation.**

### 1. Whole-document length normalisation

`adv-dilution-01` — the note holding the exact evidence paragraph does not
appear in Top-5 at all. What does appear:

```
1. 13.180  20-Learning/retry/backoff-compact.md    ← same paragraph, short note
2.  7.488  20-Learning/ops/grpc-deadline.md        ← mentions the terms in passing
3.  4.011  20-Learning/ops/queue-consumer.md       ← mentions the terms in passing
4.  3.472  20-Learning/ops/jitter-note.md          ← lists jitter variants by name
5.  3.405  20-Learning/agent/tool-loop.md
   (absent)  20-Learning/retry/backoff-handbook.md ← the same paragraph, 30 KB note
```

`SearchDocument.weighted_length` sums every field across the whole document, so
a long note pays for text the query never asked about. The identical paragraph
scores 13.2 in a 0.2 KB note and under 3.4 in a 30 KB one. This is the case
#118 exists for.

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

P50 9 ms, P95 11 ms across 22 queries on an 18-note corpus containing two notes
over 25 KB. Budgets in the test are set well above this so a slower CI machine
does not turn a performance check into a flake.

## Explicit non-goals

This change does not alter ranking, does not define a diversity penalty, and
does not treat several results from one project as bad by default. Whether
repetition is redundancy is decided per case by the fixture's own annotation.
