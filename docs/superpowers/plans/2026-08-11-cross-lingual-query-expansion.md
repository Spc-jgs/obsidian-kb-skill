# Cross-Lingual Query Expansion Implementation Plan

Closes: [#73](https://github.com/Spc-jgs/obsidian-kb-skill/issues/73)

## Release Target

Minor on top of v1.30.0. One new module, one new optional Vault file, one new
refusal code, one new CLI flag. No note changes shape, no migration runs, no
index or cache is written, and the helper still makes no network call.

Branched off `master`. Delivery rules as standing: RED tests before
implementation, `python build.py` before any doc assertion, `build.py --check`
before the gate, and every CI job green before merge.

## The Problem, Stated Precisely

The v1.30 baseline resolves three of eight semantic paraphrases. Read the
failures and they are not eight instances of one weakness — they are one
mechanism failing in one specific way.

The corpus is written in English. The eight semantic queries are written in
Chinese. `tokenize()` emits lowercase Latin tokens and overlapping CJK bigrams,
so a Chinese query and an English note share **no token at all** unless the note
carries a Chinese alias. That is exactly what the three passing cases have:

| Query | Passes because |
| --- | --- |
| semantic-05 | alias `目录索引图谱` shares `目录` |
| semantic-07 | alias `Server-Sent Events 代理延迟` shares `代理` |
| semantic-08 | alias `向量检索决策` shares `向量` |

The five failures return **zero results**, not wrong results. BM25 has nothing
to rank. So this is not a ranking problem to be solved with better weights, and
it is not evidence that lexical retrieval is exhausted. It is a vocabulary gap
between the language the user thinks in and the language the note was written
in. A bilingual knowledge base has that gap on every note whose author switched
languages mid-project, which in this Skill's own Vault is most of them.

The honest name for the fix is therefore query expansion across a curated
bilingual concept lexicon — the first thing #73 asks to try, before graphs,
before title expansion, and long before a default embedding provider.

## Mechanism

### One pass, before scoring

`expand_query(query, lexicon)` returns matched concepts and the extra tokens
they contribute. The result is fed to the existing BM25 path as a second, lower
weighted token set. Everything else in `search_vault` is unchanged: the same
document loading, the same filters applied before scoring, the same name boost
on the raw query, the same read-only contract.

### Matching a concept

A concept is a set of surface terms that mean the same thing, in any mix of
languages:

```python
Concept(id="cache-stampede", terms=("缓存击穿", "缓存雪崩", "cache stampede", "single-flight"))
```

Matching is deterministic and side-free:

- **CJK terms** match as a substring of the raw query. Chinese has no word
  delimiter, so substring is the correct operator, and it is the only one that
  finds `击穿` inside `避免缓存击穿的方案`.
- **Latin terms** match as a consecutive token run over the query's Latin
  tokens, so `cache stampede` matches the query `cache stampede control` and
  does not match a query that merely contains both words far apart.

When a concept matches, every one of its **other** terms is tokenized and those
tokens become expansion tokens, minus any token the user already typed. A token
the user typed is direct evidence and must never be reweighted downward.

### Scoring

`_bm25_score` gains a per-token weight. Direct tokens weigh `1.0`; expansion
tokens weigh `EXPANSION_WEIGHT`. Document frequencies are computed over the
union, so IDF still describes the candidate set. `_name_boost` sees the raw
query only — an expansion must not manufacture a title-exact match.

### Evidence

Expansion is only acceptable if the user can see it. Three surfaces:

- Per result, a `signals` entry `{"kind": "expansion", "detail": "缓存击穿 →
  cache, stampede"}`, emitted **only** for concepts whose tokens actually occur
  in that note. `_field_matches` keeps reporting direct tokens only, so a `body`
  signal never names a word the user did not type.
- Per response, an `expansion` block naming each matched concept, the surface
  term that matched, the tokens it added, and the weight in force.
- `--no-expand`, which reproduces the exact v1.30 lexical behaviour. A
  deterministic feature that cannot be turned off cannot be compared against.

`mode` stays `"lexical"`. Rewriting a query against a word list is lexical
retrieval; calling it something else would suggest a vector store that does not
exist.

## Thresholds, Recorded Before Implementation

| Parameter | Value | Why this value |
| --- | ---: | --- |
| `EXPANSION_WEIGHT` | `0.45` | A typed word is evidence; an expanded word is a hypothesis about what the user meant, and must not outweigh evidence. Under the current field weights a single direct title token scores roughly 4–6, so keeping expansion under half means two expanded body hits cannot displace one direct title hit. Sweep 0.30 / 0.45 / 0.60 and publish all three. |
| `MAX_EXPANSION_CONCEPTS` | `8` | Bounds work and, more importantly, bounds the explanation. A response listing twenty concepts is not explainable to a reader. |
| `MAX_EXPANSION_TOKENS` | `24` | Same reason, at token granularity. Truncation is deterministic: concepts in match order, tokens in lexicon order. |
| Minimum term length | 2 chars | `uv`, `ci`, `锁`-alone are the boundary. One CJK character is a morpheme, not a concept, and would fire constantly. |
| Concept minimum | 2 terms | A concept with one term expands to nothing. |

The sweep result is published whether or not `0.45` wins. If a different value
wins on both the gate and the holdout set, it ships instead and this table is
corrected rather than defended.

## What Keeps This From Becoming Noise

The failure mode of query expansion is well known: expand enough and everything
matches everything. Four guards, in order of how much they actually carry:

1. **The lexicon is domain-scoped, not a dictionary.** Entries cover the
   subjects this Skill exists to serve — knowledge management, retrieval,
   agents, capture, and the software vocabulary those notes are written in.
   General language is out of scope by construction.
2. **No function words, ever.** A structural test rejects any lexicon entry
   whose term appears in a stoplist of general words (`方法`, `问题`, `内容`,
   `thing`, `issue`, …). This is checked mechanically, not by review.
3. **Expansion is down-weighted, not equal.** See the table.
4. **The no-answer group is a release gate.** Six queries about Martian soil,
   COBOL payroll, and Greek pottery must keep returning nothing. Expansion is
   the single most likely way to break that gate, so it stays a hard assertion,
   not a soft score.

Guard 1 is doing most of the work and is the one that decays: a lexicon grows,
and each addition is a small chance to add a word that means five things. That
is a maintenance cost this plan accepts and states, rather than hides.

## The Overfitting Problem, and What Is Actually Being Claimed

The gate is eight queries. A lexicon written while looking at those eight
queries will pass those eight queries. That proves the mechanism can be made to
work; it does not prove it works.

So the eight `semantic-holdout` queries were written and committed **first**, in
`9234cab`, before any lexicon existed, with their pre-expansion score frozen in
the same commit: 4 of 8 hits, MRR 0.5. Git history, not a claim in a report, is
what establishes the ordering. The holdout is never tuned against and never
gates the release.

Even then, the honest reading is narrow. The holdout runs on the same 16-note
corpus and was written by the same author in the same sitting, so it measures
robustness to different **phrasing**, not to a different Vault or a different
subject area. It is an upper bound on optimism, not a proof of generality. The
eval report says so in those words.

Note also that all four holdout queries that already pass do so through Chinese
aliases. If the holdout ends up improved mostly on the four that currently
return nothing, that is the mechanism working exactly as diagnosed.

## Task 1: The lexicon and its invariants

`obsidian_kb_skill/scripts/query_expansion.py`, no dependencies beyond stdlib.

- `Concept`, frozen dataclass: `id`, `terms`.
- `BUILTIN_CONCEPTS`, curated, sorted by id, grouped by subject with comments
  that say what each group is for.
- `LEXICON_STOPWORDS`, the general-language rejection list.
- `validate_concepts()` enforcing the structural rules above, used by both the
  built-in table and any user file, so the built-in table cannot quietly violate
  a rule the user file is held to.

RED first: a test that asserts the invariants over `BUILTIN_CONCEPTS` (unique
ids, ≥2 terms, term length, no stopword) and a test that the six no-answer
queries expand to nothing at all.

A term claimed by two concepts is not forbidden — Chinese 代理 really is both an
agent and a network proxy, and a search that silently picks one is worse than a
search that expands both and reports it. So collisions must be **declared** in
`AMBIGUOUS_TERMS`, and a test asserts the declared set equals the actual set.
Deliberate ambiguity passes; an editing accident fails.

## Task 2: Matching and expansion

- `expand_query(query, *, concepts) -> QueryExpansion` with `tokens`,
  `concepts` (id, matched term, added tokens), and `truncated`.
- Deterministic order: concepts by first match offset then id; tokens in
  lexicon order.

RED first: substring matching for CJK, consecutive-run matching for Latin, no
expansion token duplicating a typed token, bounded output, and stability of the
returned order across runs.

## Task 3: Wiring into `search_vault`

- `search_vault(..., expand: bool = True)`, `--no-expand` on the CLI.
- `_bm25_score` takes `dict[str, float]` weights instead of a token list.
- `_document_frequencies` and `_snippet` see the union; `_field_matches` sees
  direct tokens only; `_name_boost` sees the raw query only.
- `expansion` block in the payload when at least one concept matched.

RED first: an English-only corpus answers a Chinese query; the same search with
`--no-expand` returns nothing; a result carrying an expansion signal names the
concept; and the expansion signal is absent from notes that matched directly.

## Task 4: Vault-local lexicon

Optional `<vault>/.obsidian-kb/retrieval-lexicon.json`:

```json
{"schema_version": 1, "concepts": [{"id": "generics", "terms": ["泛型", "generics"]}]}
```

The folder is dot-prefixed, so `_ignored_directory` already keeps it out of the
index — the lexicon is configuration, and configuration is not a note.

User concepts are appended after the built-ins and held to the same
`validate_concepts()`. Bounds: 64 KiB file, 200 concepts, 12 terms each, 40
chars per term.

A malformed lexicon **refuses** with `invalid-lexicon` rather than degrading to
built-ins silently. Silent degradation makes a search unreproducible and makes
the `expansion` block a lie; a typo in a config file the user wrote is theirs to
fix, and the refusal names the file and the reason.

RED first: a valid file adds a concept; a broken file refuses with the code; a
lexicon that is a symlink out of the Vault refuses through the existing path
guard; the file itself never appears in search results.

## Task 5: Gates, report, docs

- `test_retrieval_eval.py`: `semantic` becomes a real gate (≥5 hits, no
  regression on exact/alias/filtered/no-answer, holdout reported not gated).
  The pre-expansion baseline is not deleted but re-pointed at `--no-expand`, so
  the before-numbers stay a live assertion rather than a paragraph in a report.
- Latency: assert P95 within 2× the lexical P95, as #73 requires — measured as a
  ratio between the two modes in one process, since an absolute millisecond
  threshold measures the CI runner rather than this change.
- `evals/run_retrieval_baseline.py` reports the expansion state it ran under.
- `docs/evals/2026-08-11-cross-lingual-query-expansion.md`: before/after
  per group, the weight sweep, the holdout reading with its stated limits, and
  what this does not prove.
- `core/retrieval-references/search.md`, `docs/retrieval.md`,
  `docs/rules-and-algorithms.zh.md` §7, `CHANGELOG.md` Unreleased.
- `build.py`: `query_expansion.py` joins `RETRIEVAL_HELPER_FILES`, then
  regenerate.

## Explicitly Out of Scope

- Any embedding, vector store, or model call. #73 rules it out before a measured
  gain justifies it, and this change is the measurement that has to come first.
- Automatic lexicon learning from the Vault's own alias fields. Tempting, and it
  would remove most of the curation cost, but a lexicon derived from note
  content is a lexicon an attacker can write into. Note content is untrusted
  data in this Skill, and that rule does not get an exception for convenience.
- Expanding the write Skill's `suggest-links`. Different scorer, different
  evidence bar, and #75 owns that question.
