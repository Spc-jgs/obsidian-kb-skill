# Semantic Quality Gates v1.30

## Decision

v1.30 publishes evaluation gates, not a new retrieval or linking algorithm.
The lexical implementation remains offline, read-only, deterministic, and free
of a persistent index. A later semantic candidate must first beat the recorded
baseline under the accepted regression and latency limits.

## Web Capture Reference Agent

The final set ran 12 synthetic cases three times each with Codex CLI 0.147.0,
`gpt-5.6-sol`, medium reasoning, isolated temporary Vaults, user configuration
disabled, Web search disabled, and a 600-second per-run timeout.

| Group | Cases | Runs | Hard failures | Worst soft score |
| --- | ---: | ---: | ---: | ---: |
| Standard | 4 | 12 | 0 | 0.5829 |
| Verified | 4 | 12 | 0 | 0.7254 |
| Zero-write | 4 | 12 | 0 | 1.0000 |

Across all 36 accepted runs the mean soft score was 0.9023. All verified cases
bound a receipt to the applied candidate. Every failure case left the Vault
unchanged. Standard depth selection matched 8 of 12 runs: the tutorial and
material-diagram cases each escalated to verified twice, an efficiency issue
retained as a soft finding rather than hidden as success.

Harness warm-ups exposed and fixed three evaluation defects before the final
set: an unisolated runtime record, variadic `--image` prompt consumption, and an
overly literal self-report label matcher. Those invalid runs are excluded.

## Retrieval Baseline

The synthetic corpus has 40 queries and 16 notes.

| Group | Queries | Recall@5 | MRR | No-answer FP |
| --- | ---: | ---: | ---: | ---: |
| Exact | 10 | 1.0000 | 1.0000 | — |
| Alias or bilingual | 8 | 1.0000 | 1.0000 | — |
| Metadata-filtered | 8 | 1.0000 | 1.0000 | — |
| Semantic paraphrase | 8 | 0.3750 | 0.3125 | — |
| No answer | 6 | — | 0.0000 | 0.0000 |

Synthetic latency was 5.78 ms P95. A separate read-only run issued all 40
queries against a private 246-file Vault: its before/after content digest and
file count were identical, with 111.88 ms P95 latency. No private body, path,
query label, result, or raw digest is committed.

## Directed Links and Release Gate

The repository now carries 16 positive directions with explicit reader value
and evidence, plus 16 same-topic hard negatives. v1.30 deliberately adds no
scorer and no automatic link insertion.

A retrieval candidate is admissible only if semantic hits rise from 3/8 to at
least 5/8, stable groups do not regress, no-answer false positives remain zero,
contracts remain read-only and cited, and P95 stays at or below twice the
lexical baseline. Deterministic expansion is evaluated before optional local
embedding.
