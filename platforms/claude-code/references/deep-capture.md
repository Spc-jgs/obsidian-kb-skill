# Deep Knowledge Capture (conditional reference)

Load this reference only after `web-capture.md` selects `capture_depth:
verified` for a finished source-backed capture or material rewrite. Do not load
it for standard captures, ordinary notes, or an explicitly quick, bookmark,
save-for-later, link-only, or unread-source capture.

## Verified Source Gate

This is the **deep knowledge capture** path selected for explicit or
evidence-sensitive verification. Persist `capture_depth: verified`; the
ordinary “save” or “沉淀” path remains standard unless the stronger intent or
risk is present.

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

## Content-Bound Capture Receipt

A verified `web-clip` outside `00-Inbox` requires a structured receipt. It makes
the coverage review inspectable and binds it to the exact candidate; it does not
turn agent self-review into proof that a claim is true.

Draft the complete article first. Run `create-note --preflight-json` once without
a receipt when the final rendered SHA-256 is not yet known. It must return
`missing-capture-receipt`, the content SHA-256, and no mutation. Build a compact
JSON receipt with:

```json
{
  "schema_version": 1,
  "content_sha256": "<preflight content sha256>",
  "profile": "conceptual-opinion",
  "source_access": "complete",
  "primary_sources": ["https://example.com/article"],
  "supplemental_sources": [],
  "material_items": [
    {
      "id": "application-method",
      "kind": "application-method",
      "source": "https://example.com/article",
      "note_anchor": "### 可复用的应用方法",
      "status": "resolved"
    },
    {
      "id": "causal-chain",
      "kind": "causal-claim",
      "source": "https://example.com/article",
      "note_anchor": "### 为什么这样工作",
      "status": "resolved"
    },
    {
      "id": "applicability-boundary",
      "kind": "boundary",
      "source": "https://example.com/article",
      "note_anchor": "### 适用边界",
      "status": "resolved"
    },
    {
      "id": "counterexample",
      "kind": "counterexample",
      "source": "https://example.com/article",
      "note_anchor": "### 不适用的反例",
      "status": "resolved"
    }
  ],
  "numeric_claims": [],
  "inferences": [],
  "practical_artifact": {
    "kind": "application-method",
    "note_anchor": "### 可复用的应用方法"
  },
  "unresolved_items": []
}
```

Use one `profile`, or a sorted unique `profiles` array for a hybrid:

- `tutorial-procedure`;
- `resource-survey`;
- `conceptual-opinion`;
- `research-evidence`.

Required material evidence is:

| Profile | Required material kinds | Practical artifact kind |
| --- | --- | --- |
| tutorial-procedure | `prerequisite`, `procedure`, `verification`, `failure-mode` | `reproducible-procedure` |
| resource-survey | `canonical-link`, `compatibility`, `limitation`, `selection-criteria`, `starting-example` | `selection-decision` |
| conceptual-opinion | `causal-claim`, `application-method`, `boundary`, `counterexample` | `application-method` |
| research-evidence | `decision-implication`, `evidence`, `limitation`, `measurement-context`, `uncertainty` | `decision-method` |

Every `note_anchor` and `note_excerpt` must be exact reader-facing text in the
candidate body, not YAML frontmatter or a hidden HTML comment. The candidate
`source` metadata must appear in `primary_sources`. Declare every material
supplemental source separately.

Do not collapse compatibility across unrelated resources. For a resource
survey, include exactly one reader-facing `## Resource Inventory` or
`## 资源清单` section containing the name and canonical URL of every concrete
resource and no unrelated URLs. Add a `resources` array with one unique
lowercase `id`, meaningful `name`, and matching `canonical_url` for every entry
in that section. The helper reconciles the section's complete URL set with the
receipt, so an omitted visible resource fails validation. Its
`canonical-link`, `compatibility`, and `limitation` material items must each
declare that resource's `resource_id`; every declared resource needs all three.
Profile-wide selection criteria and a starting example may compare or start
from the survey as a whole.

```json
{
  "resources": [
    {
      "id": "example-tool",
      "name": "Example Tool",
      "canonical_url": "https://example.com/tool"
    }
  ],
  "material_items": [
    {
      "id": "example-tool-compatibility",
      "kind": "compatibility",
      "resource_id": "example-tool",
      "source": "https://example.com/article",
      "note_anchor": "Example Tool requires Java 17",
      "status": "resolved"
    }
  ]
}
```

Copyable fenced shell examples that create `SKILL.md` must contain a closed,
parseable YAML mapping with meaningful `name` and `description`; show an invalid
source snippet only as non-copyable text and provide a labeled corrected
example.

For every percentage, ratio, duration, before/after measurement, abbreviated
large count, or star count in prose, add a `numeric_claims` entry:

```json
{
  "note_excerpt": "交付周期从 12 天压缩至 5 天",
  "provenance": "source-self-report",
  "source": "https://example.com/article",
  "measurement_context": "作者自述；原文未提供样本、统计周期或对照方法"
}
```

Allowed provenance is `primary-source`, `source-self-report`,
`supplemental-primary`, or `calculation`. Do not omit a numerical conclusion
from the receipt merely because it is presented as insight.

For every writer-derived conclusion, add an `inferences` entry whose exact
excerpt, evidence basis, and explicit reader-facing label distinguish it from
source fact. The exact label must occur inside `note_excerpt`; a label supplied
only in the receipt does not count.

```json
{
  "note_excerpt": "本文推导：流程设计比工具熟练度更可迁移。",
  "basis": "原文对比了频繁变化的工具和保持稳定的任务分工",
  "label": "本文推导"
}
```

Rerun preflight with:

```bash
python <skill-root>/scripts/run_helper.py create-note <vault> \
  --type web-clip --title "<title>" --stdin \
  --capture-receipt-json '<compact-json>' --preflight-json
```

Use `--capture-receipt-file <path>` instead of the mutually exclusive inline
JSON option when a detailed receipt approaches command-line or shell-quoting
limits. It must be a regular, non-symlink UTF-8 JSON file no larger than 1 MiB;
it is transient evidence and is not copied into the Vault.

Apply the identical Markdown and receipt only when both semantic receipt and
mechanical validation pass. Pass
`--expect-capture-receipt-sha256 <semantic_receipt.sha256>` on apply. Any
template, body, or receipt change fails before mutation and requires another
semantic preflight.

For a material rewrite of an existing finished article, validate the complete
candidate before the native edit:

```bash
python <skill-root>/scripts/run_helper.py capture-receipt <vault> \
  --content-file <vault-relative-candidate> \
  --receipt-file <path> --json
```

Use `--receipt-json '<compact-json>'` instead for a safely short inline receipt.
The candidate must be an in-Vault file. Run the normal backup/edit workflow
only after validation, then mechanically audit the resulting note. Report the
receipt result; do not claim that a native edit was receipt-enforced by the
filesystem.

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
ledger plus a valid content-bound receipt: complete access, material coverage,
profile usefulness, factual support, numerical provenance, verification
context, limitations, and evidence-backed insight.

Require both gates before reporting completion. A mechanical audit with
`0 findings` is necessary but does not prove semantic quality. Report:

- selected capture profile;
- primary-source access and material supplemental sources;
- whether every material inventory item was resolved;
- capture receipt SHA-256 and unresolved item count;
- semantic acceptance separately from mechanical audit.

## Historical Notes

Do not claim that installing this Skill or passing a full-vault structural audit
semantically upgrades historical notes. Re-run this workflow only for an
explicit quality review, a bounded migration batch, or a material content
rewrite. Treat an unreviewed legacy note as unknown under the current semantic
contract, not automatically passed or failed.

## Keeping the Original

A verified capture is the case most likely to need the source retained as
evidence. Archive it with `archive-source`; see "Keeping the Original" in
`web-capture.md`. Appending the source to the note is never the answer.
