# Deep Capture Semantic Quality Design

## Goal

Turn a finished source-backed article note into independently usable knowledge:
the reader should not need to reopen the primary link to understand the material,
apply the source-appropriate method, verify important claims, recover limitations,
or reuse the derived insight.

This change closes the gap left by v1.20.1. The existing versioned heading
baseline and mechanical audit remain necessary, but they cannot prove source
coverage, factual fidelity, reproducibility, decision usefulness, or
evidence-backed interpretation.

## Design Principles

1. Route by user intent, not merely by the presence of a URL.
2. Treat a finished article and an unread bookmark as different products.
3. Validate each source against a profile-appropriate contract instead of one
   universal content shape.
4. Compare the source inventory with the draft before mutation.
5. Let deterministic code reject only objective defects; do not disguise
   heuristic length or formatting checks as semantic truth.
6. Preserve material knowledge without imposing a word, bullet, link, table, or
   code-block quota.
7. Keep article-only instructions lazy so ordinary notes do not pay the deep
   capture context cost.

## Intent Routing

The Obsidian Skill itself still activates only on explicit write intent.
Question answering and article review without a save/update request remain
read-only.

After activation, route source-backed content as follows:

| Intent | Route |
| --- | --- |
| learn, summarize into knowledge, archive as knowledge, or "沉淀" | deep capture |
| save an article without an explicit quick/unread qualifier | deep capture |
| bookmark, save for later, unread source, or link-only capture | `00-Inbox` quick capture |
| complete or materially rewrite an existing finished article | deep capture revalidation |
| metadata-only edit | ordinary update without semantic revalidation |

If the source, required attachments, code, tables, or images are inaccessible,
the workflow must not create a finished deep article. It may create an explicitly
incomplete Inbox capture when that remains within the user's save request.

## Article Profiles

Select one primary profile after reading the source. For a hybrid source, apply
the union of all materially relevant profile requirements.

### Tutorial or Technical Procedure

Preserve material prerequisites, versions, dependencies, configuration,
commands, code, parameters, ordered steps, expected results, verification,
failure modes, recovery, and applicability boundaries.

### Resource Survey or Product Comparison

Preserve canonical resource links, positioning, compatibility or currentness,
installation or entry path, strengths, limitations, choice criteria, a decision
comparison, and at least one usable starting example when the sources support
one.

### Conceptual or Opinion Analysis

Preserve definitions, causal reasoning, supporting evidence, examples,
counterexamples, assumptions, boundaries, competing explanations, and a
transferable application or reasoning method.

### Research, Data, News, or Evidence Report

Preserve the question or event, date and time sensitivity, primary evidence,
method, sample or measurement context, results, uncertainty, limitations,
competing interpretations, and decision implications.

Not every article needs operational code. "How to use this knowledge" means
reproducing a tutorial, selecting a resource, applying a concept, or making an
evidence-aware decision according to the source profile.

## Materiality Standard

A source item is material when omitting it would do at least one of the
following:

- change or weaken a core conclusion;
- prevent reproduction, application, or informed selection;
- hide an applicability boundary, failure condition, risk, or uncertainty;
- remove the evidence needed to assess an important claim;
- erase a version, parameter, assumption, or measurement condition that changes
  the result.

Repetition, advertising, decorative narrative, and nonessential rhetoric are not
material. The coverage requirement is about knowledge, not verbatim retention.

## Source Coverage Gate

Before drafting, build a temporary source inventory containing:

- core conclusions and causal claims;
- material facts, evidence, dates, versions, numbers, and parameters;
- dependencies, configuration, commands, code, and ordered procedures;
- named resources and canonical links;
- examples, counterexamples, risks, limitations, and unresolved questions.

After drafting, map every material inventory item to a concrete location in the
candidate note. Resolve every uncovered item before preflight. Do not write the
temporary inventory into the Vault.

The semantic gate fails when:

- source access is incomplete for a material part;
- a material inventory item is absent from the draft;
- the draft contains an unsupported factual claim;
- a source fact and the writer's inference are not distinguishable;
- a profile-required path to reproduce, select, apply, or decide is missing;
- a claimed verification result lacks its method or measurement context;
- the note still requires reopening the source for a material detail.

When the primary article is too shallow to satisfy its own purpose, prefer
current first-party documentation, repositories, specifications, or datasets as
supplemental sources. Label supplemental facts and preserve their links. Do not
invent missing implementation details. If critical gaps remain, keep the capture
incomplete.

## Mechanical and Semantic Acceptance

Mechanical audit remains deterministic and covers:

- frontmatter, type, tags, paths, and required metadata;
- versioned heading order;
- unresolved template placeholders and instructional HTML comments;
- broken wikilinks and existing objective repository rules.

Semantic acceptance is an agent workflow performed against the complete source
set and candidate draft before apply. It covers source access, material
coverage, profile completeness, factual support, practical usability,
verification context, limitations, and derived insight.

A successful write must report the two gates separately. `0 findings` from the
mechanical audit must never be presented as proof of semantic quality.

## Historical Notes

Normal full-vault audit remains offline, deterministic, and read-only. It does
not fetch every historical source or claim that a structurally valid note has
passed semantic review.

Historical semantic review runs only when:

- the user explicitly requests a quality review or migration;
- a finished note receives a material content update;
- a bounded migration batch is intentionally selected.

Legacy notes therefore remain "not semantically reviewed under the current
contract" until examined; they are not silently upgraded by installing a new
Skill or template.

## Instruction Loading

Keep the common create path in `note-creation.md`. Move the article-only routing,
profiles, materiality rules, coverage gate, enrichment policy, semantic
acceptance, and reporting contract into a one-level lazy reference named
`deep-capture.md`.

Load `deep-capture.md` only after the request is classified as a finished
source-backed capture or a material rewrite of one. Quick Inbox captures and
ordinary daily, meeting, project, person, and insight notes must not load it.

## Objective Audit Addition

Add a deterministic finding for residual instructional HTML comments in
non-template notes. A rendered note may legitimately contain ordinary HTML
comments, so reject only comments that retain known template-instruction
language or unresolved template syntax. This catches the real leaked
`<!-- 用 2–4 句话... -->` failure without treating every comment as invalid.

Do not add content-length, word-count, link-count, table-count, or code-block
thresholds. They are unreliable proxies and create both filler and false
failures.

## Forward Evaluation

Maintain bounded synthetic source fixtures for four profiles. Each fixture
contains unique material anchors such as a version, official URL, command,
parameter, measurement condition, limitation, counterexample, or uncertainty.

Evaluation succeeds only when the candidate contract and acceptance checklist
require retention or explicit handling of every material anchor without
inventing absent details. Unit tests cover deterministic behavior and generated
payload parity; release acceptance additionally performs a manual
source-to-contract walkthrough for all four profiles.

## Rejected Alternatives

- More fixed headings: structural compliance already produced a shallow passing
  article.
- Minimum word or artifact counts: these reward padding and punish concise but
  complete sources.
- A single numerical quality score: a fatal missing dependency or unsupported
  claim can be hidden by points earned elsewhere.
- Automatic model-based full-vault audit: it is expensive, nondeterministic,
  network-dependent, and unreliable for dead historical links.
- Persisting a self-attested "quality passed" field as proof: metadata can record
  process provenance but cannot establish semantic truth.
- Requiring operational steps for every source: conceptual and evidence reports
  need an application or decision method, not fabricated code.

## Implementation and Release

1. Add failing tests for lazy deep-reference routing, all profile contracts,
   materiality, source coverage, hard failures, semantic/mechanical reporting,
   and instructional-comment detection.
2. Add `core/references/deep-capture.md` and reduce
   `core/references/note-creation.md` to common routing plus a conditional pointer.
3. Add the narrow deterministic audit rule and keep historical structure
   behavior unchanged.
4. Regenerate every platform adapter, packaged reference tree, standard Skill
   payload, and manifest with `build.py`.
5. Update release documentation and version from the single source of truth.
6. Run targeted tests, full pytest, `build.py --check`, `uv lock --check`,
   `git diff --check`, wheel/install/runtime smoke, and the four-profile
   walkthrough.
7. Push the feature branch, open a ready pull request, wait for every required
   GitHub check, merge, publish the release, reinstall locally, and verify
   installed version, manifest parity, and `doctor --json`.

## Non-goals

- no semantic model, webpage extractor, embedding model, or network dependency
  in the Python runtime;
- no automatic rewrite of historical Vault content;
- no change to user-owned Vault content during repository tests;
- no replacement of deterministic audit with an LLM judgment;
- no requirement that quick Inbox captures masquerade as completed knowledge.
