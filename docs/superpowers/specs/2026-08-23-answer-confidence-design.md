# Answer confidence for `search-vault` (#170)

**Status: accepted, with a limitation that must not be papered over.**

## The problem

`search-vault` cannot say it found nothing useful. Asked something the Vault
does not cover, it returns hits with a score, a heading and a snippet — the
shape of a search that succeeded:

```bash
python3 obsidian_kb_skill/scripts/search_vault.py ~/Documents/my-knowledge-base \
  --query "Feign 和 HttpExchange 有什么区别" --top-k 3
```

Top-1 is `Python函数式编程-高阶函数map-reduce与filter.md`, at twice the score of
second place. The words it matched are `么区, 什么, 区别, 和, 有什` — every one
a question frame, neither technical term among them.

`#120` already diagnoses **zero** results. This is worse than zero, because the
caller cannot see the difference: an Agent either cites the wrong note, or
concludes the Vault already covers the topic and never captures it.

## The measure

IDF-weighted share of the **typed** query that the winning result matched:

```
coverage = Σ idf(t) for t matched by top-1  /  Σ idf(t) for t in the query
```

IDF is what makes "informative" countable. A stop-word list would need a
countable source — #147 and #75 both settled that — and question frames like
`有什么` have none. Rarity in this Vault supplies the same distinction without
anyone writing a list.

Only typed tokens count. An expansion token is the ranker's guess at what the
reader meant; letting a guess certify the confidence of the result it produced
is circular.

Both `_field_matches` (which reports the signals) and `_confidence` read one
`_matched_by_field`, and both weigh words with one `_inverse_frequency` — the
same one `_bm25_score` ranks with. Two copies would let a result cite a word its
own confidence did not count.

## The threshold, and why there is only one

Measured on the reference Vault (231 notes):

| set | n | coverage range |
|---|---:|---|
| no answer in the Vault | 22 | 0.09 – 0.54 |
| answered, top-1 correct, phrased as a question | 16 | 0.32 – 0.64 |

**These overlap.** No cut separates them. 0.30 is chosen as the one useful
operating point, not as a boundary:

| cut | negatives passing as answers | correct answers demoted |
|---:|---:|---:|
| 0.25 | 3/22 | 0/16 |
| **0.30** | **2/22** | **0/16** |
| 0.45 | 2/22 | 6/16 |
| 0.60 | 0/22 | **12/16** |

So the field has two levels, not three. `none` is a finding: the results carry
nothing specific to the query. `evidence` is the absence of that finding — it
says specific words are present, **not** that the answer is right. Two of the
18 questions measured score `evidence` on a wrong top-1.

## The hypothesis this replaced

The first implementation used 0.60 with a third `high` band, on a measured gap
of +0.126. That measurement drew its positives by lifting a prose sentence out
of each note's own body — a construction that guarantees the query's words are
in the note. It reported a 1.00 median and a 0.664 floor.

Real questions do not behave that way. `ThreadLocal 内存泄漏怎么避免` returns
the right note at coverage 0.47; `RAG 首字延迟怎么优化` at 0.55. At 0.60 both
would be flagged. The gap was a property of the sampling, not of the ranker,
and it was caught by running the shipped code against hand-written questions —
never by the test suite, which was green throughout.

Recorded in `2026-08-21-rejected-hypotheses.md` §4.

## What this does not do

**Near-miss queries are not solved.** The two negatives that pass at 0.30 are
`Feign 和 HttpExchange 有什么区别` (0.54) and `Spring Boot 事务失效` (0.48) —
#170's own two examples. Both name real technologies inside the Vault's Java
and Spring domain, so they share informative words with notes that do not
answer them. The 12 additional near-misses measured (`Spring Batch`, `OAuth2`,
`ShardingSphere`, `XXL-JOB`, `Arthas`, `JVM 调优`, `CompletableFuture`,
`分库分表`, …, each greping to zero in a Vault holding 16 Java and Spring
notes) score 0.10 – 0.27 and are caught. The failure is specific to queries
whose rare terms are *near* the corpus, and it is the shape #170 filed.

**It is not a ranking-quality signal.** `adv-crowding-01` scores 1.00 with a
wrong top-1: those near-identical dailies contain every word of the query, and
the failure is redundancy, which Top-K selection owns.

## Reproducing the numbers

The corpus is the author's private Vault, so the measurement is not a test. The
query sets are recorded in this document; the negatives are topics with zero
case-insensitive grep hits:

```bash
grep -ril "Flutter" --include='*.md' ~/Documents/my-knowledge-base | grep -v '/\.' | wc -l
```

The adversarial corpus, which is versioned, keeps the regression:
`test_a_no_answer_query_is_reported_as_carrying_no_evidence`.
