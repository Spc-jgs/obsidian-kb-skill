# Conversation Context and Harvest Evaluation

## Scope

This evaluation covers the unreleased Conversation Digest v2 and Conversation
Harvest workflow on branch `feature/conversation-context-harvest`.

It verifies:

- intent separation between immutable conversation snapshots, mutable Task
  Memory, and durable-knowledge candidate analysis;
- the versioned Chinese and English Digest v2 heading contract;
- deterministic Resume Card completeness and line-budget findings;
- progressive disclosure from the small Skill body to operation-specific lazy
  references;
- synchronized source, generated Skill, platform adapter, wheel resource, and
  manifest surfaces;
- user documentation for design, prompts, write boundaries, and acceptance.

It does not claim that static rules can prove a natural-language summary is
factually correct. Grounding still requires the workflow's cold-reader semantic
check against the source conversation and cited artifacts.

## Routing Fixtures

`tests/fixtures/conversation_workflow_eval_cases.json` supplies four bounded
scenarios:

| Scenario | Expected route | Required distinction |
|---|---|---|
| Architecture discussion | `conversation-digest` | decision, rationale, constraint, evidence, next action |
| Bug investigation | `conversation-digest` | symptom, cause or hypothesis, fix, verification, remaining risk |
| Active task handoff | `task-memory` | mutable status, step, decisions, constraints, artifacts, open items |
| Knowledge review | `conversation-harvest` | problem, knowledge, reflection, design, and evidence states |

The contract tests require all three routes and prevent Harvest from silently
becoming a ninth note type.

## Digest v2 Structural Evaluation

The accepted localized heading baselines are:

```text
zh-CN: 恢复卡片 -> 边界与约束 -> 决策与依据 -> 证据与产物 -> 未决事项与下一步
en: Resume Card -> Scope and Constraints -> Decisions and Rationale ->
    Evidence and Artifacts -> Open Questions and Next Actions
```

Candidate and full-Vault audit paths check:

- missing or out-of-order v2 headings;
- a preserved old `Templates/Digest Note.md`;
- missing Goal, State, Current conclusion, Next step, or Key artifacts values;
- more than 12 non-empty visible lines in the Resume Card;
- leaked Digest template instructions.

Focused tests accept complete English and Chinese structures, reject an old
template/note, reject an empty required Resume Card value, and reject an
overlong Resume Card.

## Isolated Vault Smoke Test

An isolated temporary Vault was initialized with the shipped templates and an
existing `30-Insights/` directory. A Chinese Digest v2 containing all five
sections was passed through the real helper twice:

1. `create-note --preflight-json`
2. `create-note --apply --compact-json`

Observed results:

- template scaffold: `ok: true`;
- preflight: `validation.ok: true`, `0` findings;
- content identity:
  `959851123ec2a2624f4258a3b46d9e6cb1f1f2d96a321258b10b3a3ca2cbddf6`;
- apply: `applied: true`;
- automatic note audit: `ok: true`, `0` findings.

The temporary Vault was moved to Trash after verification. No real Vault
business note was created or modified.

## Real Vault Read-Only Impact Check

The source-tree auditor scanned the configured real Vault without mutation. It
reported 208 existing findings overall and exactly two findings from the new
Digest v2 contract:

- `Templates/Digest Note.md`:
  `outdated-conversation-digest-template`;
- `40-Projects/2026-07-09 Spring AI DashScope配置清理.md`:
  `missing-conversation-digest-heading`.

This is the intended migration boundary. Updating the template affects future
notes; it does not claim that one historical Digest has been semantically
upgraded. Neither file was changed in this development run.

## Progressive Disclosure

The always-loaded write Skill remains below its existing 45-line ceiling. It
contains only the authorization gate and pointers:

- conversation context archive → `conversation-digest.md`;
- conversation knowledge review → `conversation-harvest.md`;
- active task handoff → `task-memory.md`.

Harvest analysis may run after an explicit request to evaluate capture value,
but the Skill body still requires explicit save intent before any Vault
mutation. The detailed candidate lenses, value gate, evidence states, and write
boundary remain lazy.

## Documentation Acceptance

The implementation adds:

- full design rationale and engineering scope in
  `docs/superpowers/specs/2026-07-29-conversation-context-harvest-design.md`;
- user prompts, structures, routing, acceptance, and common errors in
  `docs/conversations.md`;
- entry links and summaries in root Chinese/English README files, the docs
  index, feature guide, capture/governance guide, and CHANGELOG.

The feature guide also corrects the documented note-type slug from
`digest-note` to `conversation-digest`.

## Automated Validation

- Focused conversation, template, audit, create-note, lazy-reference, and build
  tests: passed.
- Complete suite: 655 tests passed.
- `build.py --check`: passed.
- `uv lock --check`: passed.
- `git diff --check`: passed.
- Python `compileall`: passed.
- `bash -n install.sh`: passed.
- Skill Creator `quick_validate.py`: `Skill is valid!`.
- sdist and wheel build: passed.
- Isolated Python 3.14 wheel install from a neutral working directory: passed;
  the contract module loaded version `2`, resources resolved through
  `importlib.resources`, and the installed Chinese template, English template,
  and Harvest reference were present with their expected contracts.

The first package-content probe incorrectly looked for the English Resume Card
heading in the default Chinese template. The corrected neutral-directory probe
checks both localized files separately and passes; no package content changed
between the two probes.
