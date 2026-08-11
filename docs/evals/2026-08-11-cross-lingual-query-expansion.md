# Cross-Lingual Query Expansion

Closes [#73](https://github.com/Spc-jgs/obsidian-kb-skill/issues/73). Measured on
the versioned synthetic retrieval corpus at fixture schema 3: 16 notes, 48
queries, read-only, offline, no persistent index.

Reproduce both numbers:

```bash
uv run --no-sync python evals/run_retrieval_baseline.py
uv run --no-sync python evals/run_retrieval_baseline.py --no-expand
```

## What the v1.30 failure actually was

The five failing semantic queries returned **zero results**, not wrong ones. The
corpus is written in English; the queries are Chinese; `tokenize()` emits Latin
words and CJK bigrams, and those alphabets never meet. BM25 had nothing to rank.

The three that passed all passed for the same reason — the note happened to
carry a Chinese alias sharing a bigram with the query (`目录索引图谱`,
`Server-Sent Events 代理延迟`, `向量检索决策`). None of them passed through
cross-lingual matching, because there was none.

That reframes the problem. This was never a ranking weakness that a better
scorer would fix; it was a vocabulary gap between the language the reader thinks
in and the language the note was written in.

## Result

| Group | Queries | Recall@5 before | after | MRR before | after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Alias or bilingual | 8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Metadata-filtered | 8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **Semantic (gate)** | 8 | 0.3750 | **1.0000** | 0.3125 | **0.9375** |
| Semantic holdout | 8 | 0.5000 | 1.0000 | 0.5000 | 1.0000 |
| No-answer | 6 | — | — | FP 0.0 | FP 0.0 |

The gate asked for at least 5 of 8. All 8 hit, 7 of them at rank 1.

The one at rank 2 is `semantic-03`, 让另一个代理接着完成上次没做完的工作. Chinese
代理 is both *agent* and *proxy*; the lexicon expands both readings and says so,
and the SSE reverse-proxy note takes rank 1 on `proxy` in its title. That is the
declared ambiguity behaving as designed rather than a near miss: the response
names both concepts, so a reader can see which reading produced which result.

Latency is unchanged — 6.42 ms mean, 7.20 ms P95, against 6.81 / 7.58 before.
Expansion runs once per query over 83 concepts and adds nothing per document,
so it does not scale with Vault size. The budget allowed 2×; the measurement is
under 1×, which is noise, not a speed-up.

`read_only: true` on both runs.

## The holdout, and how much it is worth

Eight extra Chinese queries over the same corpus were written and committed in
`9234cab`, **before any lexicon existed**, with their pre-expansion score frozen
in the same commit. Git history establishes the ordering; the report does not
have to be believed on it.

They went from 4/8 to 8/8. The four that were already passing were, again, alias
bigram coincidences; the four that gained had zero token overlap with their
English targets.

What this is worth, stated honestly:

- The holdout runs on the **same 16-note corpus**, written by the same author in
  the same sitting. It measures robustness to different phrasing, not to a
  different Vault, a different subject area, or a different writer.
- The pre-expansion **per-query outcomes were inspected** when freezing the
  baseline, so the author had seen which holdout queries failed before writing
  the lexicon. Terms were chosen on domain merit and none were lifted from a
  holdout query that had no independent claim to being standard vocabulary — but
  this is a discipline, not a mechanism, and it makes the holdout a moderate
  signal rather than a clean one.
- It is not a release gate, and the test that reads it is one-sided: it may only
  fail on regression. Gating it would invite the next author to optimise against
  it, and the set would stop measuring generalisation the moment it started
  measuring compliance.

Sixteen notes is a small, clean corpus. Every number here should be read as
"the mechanism works and nothing regressed", not as an estimate of the gain on a
real Vault.

## The weight was not chosen by measurement

`EXPANSION_WEIGHT` was swept across the full 48-query corpus:

| Weight | Semantic | Holdout | Exact / Alias / Filtered | No-answer FP |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 (off) | 3/8, MRR 0.3125 | 4/8, MRR 0.5000 | all 1.0000 | 0.0 |
| 0.25 | 8/8, MRR 0.9375 | 8/8, MRR 0.9375 | all 1.0000 | 0.0 |
| 0.30 | 8/8, MRR 0.9375 | 8/8, MRR 0.9375 | all 1.0000 | 0.0 |
| **0.45** | 8/8, MRR 0.9375 | 8/8, MRR 1.0000 | all 1.0000 | 0.0 |
| 0.60 | 8/8, MRR 0.9375 | 8/8, MRR 1.0000 | all 1.0000 | 0.0 |
| 0.80 | 8/8, MRR 0.9375 | 8/8, MRR 1.0000 | all 1.0000 | 0.0 |
| 1.00 | 8/8, MRR 0.9375 | 8/8, MRR 1.0000 | all 1.0000 | 0.0 |

**Recall is flat from 0.25 to 1.00, and nothing breaks even at full weight.**
This corpus cannot choose the value. The honest conclusion is that the sweep
answered a different question than it was designed to: it shows the gain is not
an artefact of a tuned constant, and it shows this corpus is too small and too
clean to exercise the down-weighting at all.

0.45 therefore ships on principle, not evidence: a typed word is evidence and an
expanded word is a hypothesis, one direct title token scores roughly 4–6 under
the current field weights, and holding expansion below half keeps two guessed
body hits from displacing one real title hit. Its protective value on a Vault
large enough for expanded tokens to collide with unrelated notes is **untested**.
A future corpus that does discriminate should revisit the number.

## What is guarding no-answer precision

Expansion is the most plausible way to turn six honest "nothing found" answers
into six confident wrong ones, so it stays a hard gate rather than a soft score.

None of the six no-answer queries fires a single concept. That is not luck; it
follows from the lexicon being domain-scoped, and it is asserted per query in
`tests/test_query_expansion.py` rather than inferred from the aggregate.

The structural rules are checked mechanically, on the built-in table and on any
Vault's own file alike: unique lowercase ids, 2–12 terms, 2–40 characters, no
term from `LEXICON_STOPWORDS`, and any term claimed by two concepts must appear
in `AMBIGUOUS_TERMS` — so 代理 meaning both *agent* and *proxy* is a decision on
the record, and any other collision is an editing accident the test fails on.

## What this does not establish

- **Not that the lexicon is complete.** 83 concepts covering the subjects this
  Skill serves. A Vault about immunology gets nothing from it and must write its
  own `.obsidian-kb/retrieval-lexicon.json`.
- **Not that curation scales.** The lexicon grows, and each addition is a chance
  to introduce a word that means five things. The stopword list and the
  ambiguity declaration bound the damage; neither prevents it.
- **Not a semantic capability.** This matches words through a table a person
  wrote. It has no notion of meaning, and a paraphrase using vocabulary absent
  from both the note and the table still returns nothing.
- **Not a verdict on embeddings.** #73 required a measured lexical baseline
  before considering a vector provider. This is that baseline, now with the
  cheap deterministic option exhausted on this corpus. The next candidate has to
  beat 8/8 semantic and 8/8 holdout at 7.2 ms P95, offline, with citations —
  which is a materially harder bar than the 3/8 it would have faced before.
