# Deep Capture v1.21 Contract Walkthrough

## Scope

This evaluation checks whether the conditional deep-capture contract exposes
the information needed to preserve material source details for every supported
article profile. It is a deterministic source-to-contract walkthrough, not a
claim that a language model can be proven correct by static tests.

The reusable synthetic sources live in
`tests/fixtures/deep_capture_eval_cases.json`. Every case contains at least
eight source-backed material anchors and three tempting but unsupported
inventions.

## Tutorial or Technical Procedure

The fixture varies Java and Spring Boot versions, a dependency coordinate, a
configuration value, a test command, an endpoint result, and failure recovery.
The contract explicitly requires prerequisites, versions, dependencies,
configuration, commands, ordered execution, expected results, verification,
failure modes, and recovery. Omitting or changing any anchor leaves an
unresolved material item or creates an unsupported factual claim.

Result: contract coverage passes.

## Resource Survey or Product Comparison

The fixture distinguishes two resources by canonical URL, Java compatibility,
entry command, target scenario, selection rule, and a legacy limitation. The
contract explicitly requires canonical links, positioning, compatibility,
installation or entry paths, strengths, limitations, choice criteria, a
decision comparison, and a usable start.

Result: contract coverage passes.

## Conceptual or Opinion Analysis

The fixture supplies a causal chain, an intervention, a counterexample, a
boundary, and a measurement-first application method. The contract requires
definitions, causal reasoning, evidence, examples, counterexamples,
assumptions, boundaries, competing explanations, and a transferable method. It
does not require fabricated operational code.

Result: contract coverage passes.

## Research, Data, News, or Evidence Report

The fixture includes an event date, experiment scope, sample size, metric,
confidence interval, control, sampling limitation, unsupported generalization,
and bounded decision implication. The contract requires time sensitivity,
primary evidence, method, sample and measurement context, uncertainty,
limitations, competing interpretations, and decision implications.

Result: contract coverage passes.

## Cross-cutting Failure Walkthrough

For every case:

- the source inventory records each material anchor;
- the coverage ledger must map each anchor to the candidate note;
- missing anchors are unresolved material items;
- any listed invention is an unsupported factual claim;
- source access failure blocks a finished note;
- supplemental implementation detail must come from a labeled first-party
  source;
- mechanical `0 findings` is reported separately and cannot override a semantic
  failure.

The static fixture does not replace future fresh-agent evaluation. It provides a
stable, non-leaking input set for that evaluation and prevents the repository
contract from silently dropping a capture profile or acceptance rule.

## Progressive Disclosure Measurement

Measured with `o200k_base` against release commit `b6b487b`:

| Instruction path | Tokens |
| --- | ---: |
| v1.20.1 `SKILL.md` + ordinary `note-creation.md` | 2,987 |
| v1.21.0 `SKILL.md` + ordinary `note-creation.md` | 2,724 |
| v1.21.0 ordinary path + conditional `deep-capture.md` | 3,993 |
| Conditional `deep-capture.md` alone | 1,269 |

Ordinary creation removes 263 tokens from the v1.20.1 path. A finished article
loads the additional semantic contract intentionally; quick Inbox captures and
non-article notes do not pay that quality cost.

## Real Vault Regression

A read-only source-tree audit of the real Vault reports
`residual-template-instruction` for
`20-Learning/Java/2026-07-27 知乎文章-SpringBoot相关的Skills全景指南.md`,
the concrete shallow article that motivated this change. The audit did not
rewrite the note.
