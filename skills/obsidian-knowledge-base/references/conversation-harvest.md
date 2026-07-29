# Conversation Harvest Workflow (reference)

Load when the user asks what problems, reusable knowledge, reflection, design,
or other durable value can be extracted from a conversation.

## Purpose and Boundary

Conversation Harvest is an **analysis and routing workflow**, **not a note
type**. It evaluates the conversation before any write, recommends what should
be saved, and actively rejects low-value material. It does not replace
`conversation-digest` or Task Memory.

- Use Digest to recover one conversation's context.
- Use Task Memory to continue a mutable active task.
- Use Harvest to decide what deserves future reuse.

An analysis-only request never writes to the Vault. The word “沉淀” can express
interest in durable value without authorizing a particular note; follow the
write boundary below instead of creating a generic recap automatically.

## Candidate Analysis

Inspect the complete available conversation through these lenses. Omit a lens
when it has no substantive candidate.

### Problem

Capture the symptom or question, context, root cause or current hypothesis,
resolution, verification, and present status. Do not preserve a cheap one-off
error unless its cause or diagnostic method is reusable.

### Reusable Knowledge

Capture the principle, causal explanation, applicability, boundary, example,
and evidence. A statement that merely repeats a conclusion without explaining
when or why to use it is not durable knowledge.

### Reflection

Tie reflection to an observed event and a concrete future behavior change.
Reject generic advice such as “be more careful” when it does not change a
specific practice, check, or decision rule.

### Design

Explain the problem, mechanism, trade-off, rejected alternative when material,
and reuse conditions. Praise without mechanism or boundaries is not a design
asset.

### Decisions and Open Items

Separate confirmed decisions, blockers, and questions that still require
evidence or user choice.

## Value Gate

Recommend durable capture only when a candidate satisfies **at least two**:

1. it is likely to recur or be searched for later;
2. rediscovering it would be costly;
3. its applicability and limits can be stated;
4. conversation evidence, code, tests, or results support it;
5. it changes a future action, judgment, or design.

For every candidate, assign one reader-visible status:

- **verified** — supported by evidence present in the conversation;
- **inferred** — a reasoned interpretation, not a verified fact;
- **open** — unresolved or dependent on external confirmation;
- **skip** — not worth saving, with a short reason.

Do not promote a third-party recap, remembered detail, or claim absent from the
available conversation. Raw transcripts, generic summaries, filler generated
to populate every lens, and duplicated existing knowledge are `skip`.

## Output Before Writing

Present a compact proposal containing:

1. conversation outcome;
2. candidate items with lens, claim, evidence status, future use, and suggested
   destination or existing note;
3. explicit `skip` items;
4. unresolved evidence or selection needs.

Use bounded retrieval only when the user asks to check existing Vault knowledge
or when the combined request explicitly includes that read step. Search results
do not grant write authority.

## Write Boundary

After the value gate:

- **Analysis only:** return the proposal and write nothing.
- **One high-value candidate with a clear existing type and explicit save
  intent:** load `note-creation.md`, route it to `learning-note`,
  `insight-note`, `project-note`, or another existing governed type, and create
  at most one note.
- **Multiple independent candidates:** show the candidates and ask the user
  which one to save first. Do not silently merge unrelated knowledge or bypass
  the at most one note boundary.
- **No durable candidate:** explain why and stop. Never manufacture a note to
  make the workflow appear successful.

Do not introduce `conversation-review` frontmatter in v1. A future dedicated
type requires evidence from repeated real use that a session-level review is
itself a stable retrieval object rather than a temporary routing artifact.

## Acceptance

A successful harvest:

- distinguishes storage types from analysis lenses;
- preserves evidence status and applicability;
- includes only candidates that pass the value gate;
- exposes what was deliberately skipped;
- routes active execution state to Task Memory and context snapshots to Digest;
- writes no more than one explicitly authorized durable note;
- reports analysis acceptance separately from any later note audit.
