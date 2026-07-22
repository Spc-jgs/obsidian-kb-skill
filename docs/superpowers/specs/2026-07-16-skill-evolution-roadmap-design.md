# Obsidian KB Skill Evolution Roadmap Design

## Goal

Evolve `obsidian-kb-skill` from a reliable capture toolkit into a safe,
maintainable knowledge-lifecycle system. Improve project and code boundaries,
note quality, Inbox processing, template upgrades, documentation, runtime token
cost, and forward evaluation without weakening explicit-save consent, Vault
containment, preview-before-write, or user-owned template protection.

## Evidence Baseline

The roadmap starts from commit `8785da8f98a7f111ed68b8964418c0c63658ba2a`
on an isolated `design/skill-evolution-roadmap` worktree.

- `441` tests pass.
- `python build.py --check` reports no generated-tree drift.
- `core/` is the canonical source for instructions, references, and templates.
- `obsidian_kb_skill/` is the canonical Python source.
- Copies under `skills/`, `platforms/`, and packaged resources are intentional
  distribution artifacts, not independent source trees.
- The standard `SKILL.md` is about 541 tokens by byte approximation; the
  ordinary create instruction path is recorded as 2,296 `o200k_base` tokens.
- The Chinese and English READMEs total 1,231 lines and contain stale runtime
  descriptions.
- The only real forward-evaluation artifact targets v1.12.0, while the current
  release is v1.19.1.

The audit also reproduced a data-integrity defect: applying Inbox processing to
a note with malformed YAML removes the original frontmatter, writes inferred
defaults, moves the note, and deletes the source. Inbox adoption must not expand
until this path is made fail-closed and recoverable.

## Approved Product Boundaries

1. Work never begins on `master`. Each deliverable uses an isolated worktree and
   a dedicated branch.
2. High-risk changes are separate from unrelated features and include preview,
   backup, restore, failure injection, and rollback documentation.
3. The Skill acts only on explicit save or Vault-management intent. It never
   writes for ordinary Q&A, debugging, casual chat, or summarize-only requests.
4. Inbox processing starts only after an explicit request. Scheduled or
   threshold-based behavior may produce a read-only reminder, never a write.
5. Inbox defaults to a bounded plan of at most ten entries. Semantic rewriting
   is reviewed one note at a time.
6. A reviewed plan is bound to source hashes. Changed input invalidates the plan.
7. New templates apply to new notes. Existing notes are not bulk rewritten and
   do not become invalid merely because a later template adds sections.
8. An installed official template may auto-upgrade only when it exactly matches
   a known historical official hash. Customized or unknown templates are never
   overwritten automatically.
9. Every automatic template upgrade creates a restorable backup. `--force`
   remains the only explicit unconditional overwrite path.

## Considered Approaches

### A. Local Hardening Only

Fix the Inbox parser defect, align a few references, polish templates, and leave
the existing product model unchanged.

This is easy to ship and review, but it leaves capture, clarification,
enrichment, connection, review, and archive as unrelated features. Inbox would
remain a filing command rather than a knowledge-quality workflow.

### B. Deterministic Core with Agent Curation

Use deterministic Python for containment, parsing, classification evidence,
planning, hashes, backups, atomic writes, validation, and restore. Use the Agent
for ambiguity resolution, summarization, knowledge connection, and learning
prompts. Agent-generated semantic changes are plans or diffs until the user
confirms them.

This preserves the project's local and deterministic safety philosophy while
using the model where semantic judgment is valuable. It is the selected design.

### C. Full Lifecycle State Engine

Add lifecycle status, confidence, review dates, automated scoring, automatic
promotion, and archive state to every note.

This enables dashboards and automation, but creates frontmatter inflation,
large migrations, false precision, and model judgments that look like facts.
It is rejected until real usage demonstrates a need that cannot be met by B.

## Architecture

The target architecture has five explicit layers:

1. **Domain contracts** — note types, folders, templates, default tags,
   frontmatter parsing, and index ownership. These are importable public modules,
   not private helpers borrowed from the auditor.
2. **Deterministic operations** — create, update, Inbox plan/apply/restore,
   template migration, audit, link candidates, and installation. Each operation
   exposes typed request, plan, result, and structured error boundaries.
3. **Skill orchestration** — a small trigger and dispatch surface plus one
   self-contained primary reference per operation. Conditional references remain
   one level deep.
4. **Knowledge assets** — concise bilingual templates whose sections encode the
   most valuable cognitive action for each note type.
5. **Verification** — unit/integration tests, generated-tree checks, token and
   output budgets, installer smoke tests, and repeatable agent forward evals.

The Python package and `core/` remain the single sources of truth. Build output
continues to be checked into Git because the repository supports offline and
cross-platform distribution. Generated copies must never acquire handwritten
business logic.

## Shared Domain Contracts

The first structural change extracts stable public modules before changing
behavior:

- `note_catalog.py`: note type, template asset, Vault filename, default folder,
  default tag, and durability class.
- `frontmatter.py`: normalized UTF-8/LF parsing, mapping-only YAML, source
  locations, portable scalar normalization, and lossless body separation.
- `folder_index_policy.py`: Folder Index/Dataview/static ownership and safe
  index-update decisions.

All CLIs consume these modules. `audit_vault.py` stops acting as an implicit
utility library. A table-driven consistency test proves that every supported
note type is creatable, template-backed, routable, and accepted by audit.

Parser behavior is strict and explicit:

- malformed, unclosed, or non-mapping frontmatter is an error;
- BOM and CRLF are normalized as transport details;
- an error never causes the original block to be discarded;
- bad UTF-8 or I/O failures return a stable structured error rather than a
  traceback or partial mutation.

## Knowledge Lifecycle

### Capture

When the user explicitly asks for a quick or temporary save and the durable type
or destination is uncertain, create an `inbox-note` in `00-Inbox` with only:

```yaml
date: "<actual capture date>"
type: inbox-note
tags: [inbox]
```

The body preserves the captured material. The Agent does not invent author,
publication date, participants, owner, deadline, or user opinions.

When the user explicitly requests a durable note and the type and evidence are
clear, direct creation remains available; Inbox is not a mandatory staging area.

### Clarify

An explicit “process/organize Inbox” request loads a dedicated lifecycle
reference and runs a bounded read-only plan. Each item reports:

- stable plan item ID and source SHA-256;
- current path and proposed destination;
- proposed type and mechanical metadata changes;
- confidence (`high`, `medium`, `low`);
- evidence and conflicting evidence;
- missing facts or questions;
- whether semantic enrichment would be required.

Keywords may generate candidates but never establish high confidence. High
confidence requires an explicit valid type or an unambiguous user-approved
destination under Vault governance. Medium and low confidence items remain in
Inbox until confirmed.

### Enrich

Enrichment is single-note Agent work. It applies the selected durable template,
keeps unknown facts unknown, distinguishes sourced claims from inference, and
shows a content diff before write. It reuses ordinary create/update preflight
and audit; Inbox must not create a second, weaker write path.

### Connect

After a note is independently understandable, suggest at most five semantic
links with a one-line relationship reason. Folder indexes are structural
navigation and are never written to `related`. Suggested links remain read-only
until accepted.

### Review and Archive

Daily/weekly review and stale-project checks produce bounded read-only queues.
Archive never runs implicitly. Cross-folder moves inspect inbound path-qualified
links; when safe rewriting cannot be proven, the plan refuses the move or keeps
the path stable.

## Inbox Transaction and Recovery Contract

Inbox apply consumes a previously reviewed plan, not a fresh classification.
Before any mutation it validates every selected item, destination, source hash,
template contract, and index ownership.

For each selected note:

1. Save original bytes and metadata in the product-owned backup area.
2. Render the proposed result in memory and validate it.
3. Create the destination exclusively through a temporary sibling file and
   atomic replace/rename where supported.
4. Update a static index only when the index policy says the Skill owns it.
5. Remove the source only after the destination and index state are valid.
6. Run note-level audit and return exact applied/skipped/failed counts.

If a step fails, restore the pre-operation state when safe. If automatic restore
also fails, preserve both copies, return a recovery-required status, and print
the exact restore command. No result may report “applied” merely because an item
was present in the plan.

Batch apply accepts explicit item IDs. Semantic body rewrites are excluded from
batch apply. The default plan is limited to ten items and returns `total`,
`planned`, and `truncated`; larger scans require explicit authorization.

## Template Design

Templates use four to six primary sections and avoid generic empty headings.
Each type encodes one or two high-value cognitive actions:

- **Daily**: focus, record, tasks, and reflection that identifies one durable
  idea worth extracting.
- **Meeting**: objective, decisions with rationale, action items with owner and
  checkpoint, and unresolved questions.
- **Learning**: concise concept model, one worked example, common failure mode,
  two or three retrieval questions, and one transfer/application exercise.
- **Insight**: claim, evidence, assumptions/boundaries or counterexample, and a
  validation action.
- **Project**: goal with success criteria and scope, milestones, progress,
  decisions with rationale, risks, and owned next actions.
- **Person**: confirmed context and dated interactions only; no inferred
  personality, intent, or sensitive traits.
- **Web Clip**: source metadata, source claims/evidence, short quotations,
  clearly separated interpretation, and open questions/actions. Missing author
  or publication date remains missing rather than guessed.
- **Conversation Digest**: `TL;DR`, `Decisions`, and `Open`, matching its
  decision-dense reference contract. Narrative background and revised-ideas
  essays are removed.

`related` is the machine-readable relationship source. A body section exists
only when it explains why links matter, not to duplicate a raw list.

Chinese and English templates share semantic role identifiers enforced by
tests. Literal heading translation may differ, but required role, safety prompt,
and frontmatter semantics may not drift.

## Template Upgrade and Restore

Template content and migration machinery ship on separate branches.

The distribution includes a versioned manifest of normalized hashes for every
known official Chinese and English template version. Classification is:

- `missing`: seed the selected current locale on confirmation;
- `current-official`: no change;
- `historical-official`: eligible for safe automatic upgrade;
- `customized`: preserve and offer a diff;
- `unknown`: treat as customized.

Default migration is dry-run. Applying a `historical-official` upgrade:

1. verifies the current hash still matches the plan;
2. backs up original bytes with locale, source hash, target hash, and timestamp;
3. writes atomically;
4. validates the installed template contract;
5. records a restore ID.

Restore verifies the current target hash before replacing it, preventing a
rollback from overwriting edits made after migration. `--force` is explicit,
destructive, backed up, and never implied by ordinary install/upgrade.

Old notes are grandfathered. Template heading enforcement uses the template
contract active for a newly created or explicitly migrated note; a new starter
template does not retroactively add findings to every historical note.

## Skill and Token Design

The always-loaded Skill remains a dispatch surface, not a handbook. Primary
references are self-contained: they cannot say “same as Create Step N” when the
create reference was not selected. Shared critical safety rules may be repeated
briefly when that costs fewer tokens and avoids ambiguous cross-loading.

Target budgets, measured with a fixed development-only tokenizer, are:

| Surface | Budget |
|---|---:|
| Skill metadata/header | 320 bytes |
| Generated standard `SKILL.md` | 1,800 bytes and 450 tokens |
| Ordinary create instructions | 2,100 tokens |
| Ordinary update or digest path | 1,000 tokens each |
| Conditional reference increment | 350 tokens |
| Clean create preflight output | 1 KiB |
| Clean compact apply output | 1 KiB |
| Compact Vault discovery | 4 KiB |
| Default Inbox plan | 10 items and 4 KiB |

Budgets are regression ceilings, not targets to fill. A change may exceed a
ceiling only with a documented measurement, demonstrated quality benefit, and
explicit design update. Tokenizer packages remain development dependencies, not
runtime dependencies.

Digest activation is corrected: “summarize this chat” without explicit save
intent never writes to the Vault.

## README and Documentation

Each README becomes a user entry page of at most 18 KiB containing:

1. product value and safety promise;
2. five-minute agent-driven installation;
3. three representative workflows, including Inbox;
4. upgrade/custom-template behavior;
5. links to task-oriented documentation.

Detailed installation matrices, CLI contracts, architecture, development,
release, and troubleshooting move to focused `docs/` pages. Chinese and English
READMEs share a tested heading and command inventory. Version-dependent counts
are generated or tested rather than copied into prose.

Documentation reflects helper-first execution: ordinary creation uses compact
discovery, structured preflight, and compact apply. It does not tell agents to
read built-in templates directly, run `detect-index` on the normal path, or
prefer native writes over the validated helper.

## Error Handling

All mutating commands follow a common result model:

- validation errors: no mutation, exit 2;
- runtime/resource errors: no mutation when detected before commit, exit 3;
- applied with post-write warnings: explicit `applied: true` and structured
  warnings, never an ambiguous generic failure;
- recovery required: exact affected paths, backup/restore ID, and no claim of
  success;
- JSON mode: one JSON document on stdout; diagnostics stay structured.

Vault containment rejects absolute, parent-traversal, and symlink escape paths
for files, links, destinations, backups, and build outputs.

## Verification Strategy

### Code and Safety

- Table-driven note catalog consistency.
- Golden frontmatter tests for BOM, CRLF, malformed/unclosed YAML, scalar/list
  YAML, invalid UTF-8, and I/O errors.
- Inbox failure injection at destination write, source removal, index update,
  audit, and restore.
- Source-hash invalidation, idempotency, 0/1/10/11/100 Inbox item budgets, and
  accurate applied/skipped/failed counts.
- Absolute, `../`, and symlink-escape wikilinks remain inside the Vault.
- Build and installer staging failures preserve the previous working tree.
- Bash and PowerShell fixtures produce equivalent managed file sets.

### Template Quality

- Chinese/English semantic-role parity.
- Custom template preservation and historical official classification.
- Dry-run, backup, restore, post-migration edit protection, and locale switches.
- Digest template/reference alignment.
- Blind readability checks: a reader identifies purpose, conclusion, and next
  action in thirty seconds.
- Learning-note comparison at one-day and seven-day delayed recall, including
  transfer to a new example.

### Agent Forward Evaluation

Create a versioned prompt/oracle/trace matrix covering:

- negative triggers: Q&A, debugging, casual chat, summarize-only;
- ordinary create, update, and digest;
- quick capture and Inbox plan/apply;
- custom template, missing category, and stale template hash;
- validation failure with zero writes;
- optional Git governance.

Run Codex and WorkBuddy at least three times per core scenario where the runtime
is available. Record activation, references read, helper calls, output bytes and
tokens, filesystem diff, result, and human-quality rubric. Python tests prove
helpers; forward evals prove Agent behavior. Neither substitutes for the other.

## Branch and Delivery Roadmap

Each branch starts from the latest accepted clean base, has its own spec/plan,
and is independently reviewable and revertible.

1. `fix/shared-note-domain` — public catalog/frontmatter/index contracts with no
   intentional feature change.
2. `fix/inbox-data-safety` — fail-closed parse, typed plan/result, transactional
   single-item apply, backup/restore, and failure injection.
3. `fix/self-contained-primary-references` — close update/digest workflows,
   correct save triggers, and remove redundant ordinary-path prose.
4. `feat/inbox-lifecycle` — `inbox-note`, bounded plan, confidence/evidence,
   reviewed plan IDs, single-note enrichment dispatch, and Skill routing.
5. `feat/knowledge-templates-v2` — bilingual template content and semantic-role
   tests; no installer or migration changes.
6. `feat/template-safe-migration` — historical manifest, dry-run, backup,
   restore, installer integration, and explicit force behavior.
7. `test/runtime-token-budgets` — tokenizer and output-size regression gates.
8. `docs/readme-information-architecture` — concise user entry points and
   focused task documentation.
9. `eval/current-forward-matrix` — current-version Codex/WorkBuddy behavior
   matrix and measured results.
10. `refactor/audit-snapshot-engine` — shared snapshot/link resolver and bounded
    scans after behavior is protected.
11. `refactor/create-note-pipeline` — request/preflight/render/commit/post-write
    stages with compatible JSON.
12. `fix/build-graph-hardening` — symlink-safe, failure-atomic generated trees.
13. `refactor/transactional-installer-core` — staged, verified shared installer
    core with Bash/PowerShell thin launchers.

The first two branches take priority because they remove a demonstrated data
loss risk. Inbox discovery is not expanded until both are accepted.

## Release and Rollback Policy

- One risk domain per PR and release note section.
- No feature branch merges with failing full tests, build drift, packaging, or
  relevant platform smoke tests.
- Each high-risk feature documents its backup location, restore command, and
  failure-state semantics.
- Releases are tagged only after installed-payload doctor and hostile-working-
  directory smoke tests.
- A rollback may revert one feature branch without reverting unrelated template,
  Inbox, documentation, or refactor work.

## Non-Goals

- No background Vault writes or automatic Inbox movement.
- No LLM classifier embedded in deterministic Python helpers.
- No automatic guessing of missing source facts or user beliefs.
- No mandatory lifecycle metadata on every durable note.
- No retroactive bulk rewrite of existing notes.
- No removal of offline/self-contained Skill payloads merely to reduce repository
  file duplication.
- No large installer rewrite before safety, Inbox, templates, token budgets, and
  current forward evaluations establish stable behavior.

## Success Criteria

The roadmap is successful when current evidence proves all of the following:

1. malformed or ambiguous Inbox content cannot be silently changed or lost;
2. Inbox capture, planning, confirmation, enrichment, connection, review, and
   archive boundaries are discoverable and tested;
3. templates improve comprehension and learning without increasing abandoned
   empty sections or overwriting customization;
4. official historical templates upgrade safely and restore reliably;
5. primary Skill workflows are self-contained and stay within measured token and
   output budgets;
6. READMEs match actual runtime behavior and lead users to the right workflow;
7. current Codex and WorkBuddy evaluations confirm triggers, calls, writes, and
   quality rather than relying only on unit tests;
8. large Python/build/installer components have public boundaries, bounded work,
   and failure-atomic mutation where applicable;
9. every change is delivered outside `master` in a separately revertible branch;
10. full tests, generated-tree checks, packaging checks, and relevant installed
    runtime smoke tests pass on the final integrated state.
