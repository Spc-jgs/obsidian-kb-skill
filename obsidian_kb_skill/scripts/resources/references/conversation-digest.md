# Conversation Digest Workflow (reference)

Load only when the user asks to preserve one coherent conversation as an
immutable context snapshot for later reading or continuation.

## Purpose and Boundary

Create a `conversation-digest` when the user wants to save a discussion's
context, conclusions, evidence, and next actions. The digest is an **immutable
snapshot** of that conversation, not a transcript, durable knowledge article,
or continuously updated task state.

Route by future use:

- Preserve why a conversation reached its current conclusion →
  `conversation-digest`.
- Continue an active task across agents, sessions, or tools → Task Memory
  (`task-memory.md`), which remains the authoritative mutable state.
- Identify reusable problems, knowledge, reflection, or design from a
  conversation → `conversation-harvest.md`.
- If “沉淀这段对话” does not reveal which future use the user means, ask one
  focused routing question before writing.

Route a project-specific digest to `40-Projects/`; otherwise use
`30-Insights/`. Keep one digest per coherent topic. A digest may link to an
active `TASK.md`, but must not duplicate or compete with its current state.

## Layered Context Recovery

Keep a **30-second Resume Card** at the top. The 30-second target applies to
that first layer, **not a whole-note word limit**. Include as much grounded
detail as needed below it, without narrating the chat turn by turn.

Frontmatter carries only identity, routing, and retrieval metadata:

```yaml
date: 2026-07-29
type: conversation-digest
tags: [insight, project-topic]
source: "Codex"
project: ""
related: []
```

Do not duplicate decisions or open items in both frontmatter and body. The
reader-visible body is authoritative.

Use the localized standard structure:

1. `## Resume Card`
2. `## Scope and Constraints`
3. `## Decisions and Rationale`
4. `## Evidence and Artifacts`
5. `## Open Questions and Next Actions`

The Chinese template uses the equivalent headings `恢复卡片`, `边界与约束`,
`决策与依据`, `证据与产物`, and `未决事项与下一步`.

### Resume Card

Use at most 12 non-empty visible lines. Supply non-empty values for:

- **Goal** — the problem or outcome this conversation addressed;
- **State** — exploring, decided, paused, completed, or an equally clear state;
- **Current conclusion** — the best grounded result at this snapshot;
- **Next step** — the first executable continuation, or an explicit closed/no
  further action statement;
- **Key artifacts** — the canonical files, notes, commits, URLs, logs, or an
  explicit statement that the source conversation is the only artifact.

### Scope and Constraints

Record material in-scope and out-of-scope boundaries, user requirements,
non-goals, invariants, and constraints that a future reader must not violate.
Omit chat history that does not change future action.

### Decisions and Rationale

Record atomic decisions and enough rationale to avoid reopening the original
conversation. Include a rejected or revised option only when its reason will
prevent repeated work. An exploratory conversation may say that no final
decision exists, but must preserve the current options or working conclusion.

### Evidence and Artifacts

Point to reader-inspectable evidence: file paths, commands and results, tests,
commits, pull requests, logs, screenshots, URLs, or related Vault notes.
Separate **verified**, **inferred**, and **open** claims in reader-visible text.
Never present a successful edit, test, external action, or decision as verified
when the conversation does not contain its evidence.

### Open Questions and Next Actions

Keep unresolved questions, blockers, the first safe next action, and its
completion condition. A completed conversation may explicitly state that no
next action remains instead of inventing one.

## Quality Contract

- **Grounded:** every fact, decision, failure, and status traces to the source
  conversation or a cited artifact.
- **Minimum sufficient context:** a cold reader can answer goal, state, current
  conclusion, next action, and evidence location from the Resume Card.
- **Safe continuation:** the detailed sections expose constraints, rationale,
  verification boundaries, and only the failed attempts worth not repeating.
- **No narrative transcript:** preserve causal context, not turn-by-turn prose.
- **No competing state:** Task Memory owns mutable active-task state; durable
  notes own deep knowledge.
- **Structural acceptance:** preflight and audit must accept the versioned v2
  headings and the complete Resume Card.
- **Semantic acceptance:** re-read the candidate as a cold reader. If safe
  continuation still requires reopening the chat, the digest is incomplete.

Create the note through the ordinary `note-creation.md` preflight/apply path,
then report the saved path and structural audit result separately from the
cold-reader semantic check.
