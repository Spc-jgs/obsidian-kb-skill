# Deep Knowledge Capture (conditional reference)

Load this reference only for a finished source-backed article capture or a
material rewrite of one. Do not load it for ordinary notes or an explicitly
quick, bookmark, save-for-later, link-only, or unread-source capture.

## Intent and Source Gate

Treat "沉淀", learning, summarizing into the knowledge base, and saving an
article without a quick/unread qualifier as a **deep knowledge capture**. Route
an explicitly quick or unread source to `00-Inbox`; never present it as finished
knowledge.

Read the complete accessible primary source and every material attachment,
image, table, code sample, or linked artifact needed to understand it. If access
is partial or blocked, stop the finished capture and report the exact missing
material. An explicitly incomplete Inbox capture is allowed only when it remains
within the user's save request.

The finished note should not need to reopen the source to recover a material
fact, understand the reasoning, reproduce or apply the source-appropriate
method, verify an important claim, or reuse the insight. Do not optimize the
finished note for brevity, token count, word-count, bullet-count, link-count,
table-count, code-block-count, or a fixed number of takeaways.

## Select a Capture Profile

Select one primary profile after reading the source. For a hybrid source, apply
the union of every materially relevant profile.

### Tutorial or Technical Procedure

Preserve material prerequisites, versions, dependencies, configuration,
commands, code, parameters, ordered steps, expected results, verification,
failure modes, recovery, and applicability boundaries.

### Resource Survey or Product Comparison

Preserve canonical resource links, positioning, compatibility or currentness,
installation or entry paths, strengths, limitations, choice criteria, a
decision comparison, and at least one usable starting example when the source
set supports one. A list of names without enough information to select and
start using a resource is incomplete.

### Conceptual or Opinion Analysis

Preserve definitions, causal reasoning, evidence, examples, counterexamples,
assumptions, boundaries, competing explanations, and a transferable
application or reasoning method.

### Research, Data, News, or Evidence Report

Preserve the question or event, date and time sensitivity, primary evidence,
method, sample or measurement context, results, uncertainty, limitations,
competing interpretations, and decision implications.

Not every profile requires executable code. The practical contract is to
reproduce a procedure, select a resource, apply a concept, or make an
evidence-aware decision according to the source's purpose.

## Materiality Standard

Treat a source item as material when omitting it would:

- change or weaken a core conclusion;
- prevent reproduction, application, or informed selection;
- hide an applicability boundary, failure condition, risk, or uncertainty;
- remove evidence needed to assess an important claim; or
- erase a version, parameter, assumption, or measurement condition that changes
  the result.

Omit repetition, advertising, decorative narrative, and nonessential rhetoric.
Preserve knowledge rather than copying the source verbatim.

## Source Inventory and Coverage Ledger

Before drafting, build a temporary source inventory with:

- core conclusions and causal claims;
- material facts, evidence, dates, versions, numbers, and parameters;
- dependencies, configuration, commands, code, and ordered procedures;
- named resources and canonical links;
- examples, counterexamples, risks, limitations, and unresolved questions.

After drafting, map each material item to a concrete heading, paragraph, table,
list item, command, or code block in the candidate note. Resolve every uncovered
item before calling `create-note --preflight-json`. Keep this ledger in working
context; do not write it into the Vault.

No unresolved material item may remain. Mark information genuinely absent from
the source as "not stated in the source" instead of guessing. When that absence
prevents the article from fulfilling its practical purpose, supplement it from
current first-party documentation, repositories, specifications, or datasets,
label the supplemental material, and retain its canonical link. Do not invent
implementation details. Keep the capture incomplete if a critical gap remains.

## Semantic Hard Failures

Do not apply the note when:

- a material source, attachment, code sample, image, or table was not read;
- a material inventory item is absent from the candidate;
- the candidate contains an unsupported factual claim;
- source facts and the writer's interpretation are not distinguishable;
- the selected profile lacks its path to reproduce, select, apply, or decide;
- a claimed result lacks the source's verification or measurement context;
- the reader still needs the primary link for a material detail;
- instructional template comments or unresolved placeholders remain.

The source may itself omit a procedure or verification method. State that
limitation honestly. Do not manufacture steps merely to fill a heading.

## Insight Contract

Derive insight only after source reconstruction. Explain the reasoning from
source evidence to the transferable principle, connection, decision rule, or
new implication. Do not replace analysis with generic claims such as "improves
efficiency", "technical equality", or "worth learning", and do not speak on the
user's behalf.

## Mechanical and Semantic Acceptance

Mechanical acceptance comes from the helper audit: frontmatter, metadata,
headings, placeholders, instructional template comments, links, fences, and
other deterministic rules.

Semantic acceptance comes from the completed source inventory and coverage
ledger: complete access, material coverage, profile usefulness, factual
support, verification context, limitations, and evidence-backed insight.

Require both gates before reporting completion. A mechanical audit with
`0 findings` is necessary but does not prove semantic quality. Report:

- selected capture profile;
- primary-source access and material supplemental sources;
- whether every material inventory item was resolved;
- semantic acceptance separately from mechanical audit.

## Historical Notes

Do not claim that installing this Skill or passing a full-vault structural audit
semantically upgrades historical notes. Re-run this workflow only for an
explicit quality review, a bounded migration batch, or a material content
rewrite. Treat an unreviewed legacy note as unknown under the current semantic
contract, not automatically passed or failed.
