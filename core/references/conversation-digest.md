# Conversation Digest Workflow (reference)

Loaded only when the user asks to compress a chat into a note. The always-loaded skill body points here.

## Conversation Digest Workflow

Turn a conversation into a **reusable context artifact** — a note a future agent (or you) re-reads in seconds to resume work (triggers: "沉淀这段对话", "summarize this chat", "把对话存成笔记").

> **Design intent.** A digest is *decision-dense, link-rich, and short* — **not** a transcript or essay. Its only job: let a future reader answer *"what was decided, what's open, where are the details"* without re-reading the chat. Put depth in the linked durable notes; keep the digest shallow.

### When to use
- The conversation produced decisions, trade-offs, or action items worth keeping.
- The user explicitly asks to save or summarize.

### Routing
- Specific active project → `40-Projects/`. Otherwise → `30-Insights/` with `type: conversation-digest`.
- One digest per *coherent topic*; split only when topics are independent.

### Format (keep scannable)
1. Resolve & validate the vault (same as Note Creation).
2. `type: conversation-digest`. **Frontmatter carries the load** — a future agent scans this first:
   - `date`: today.
   - `tags`: 2–5 lowercase kebab-case (general category; satisfies the validator).
   - `decisions`: **list of short, self-contained decision lines** (≤ ~120 chars; state the outcome, add *why* only if non-obvious). This is the primary field.
   - `open`: optional open questions / blockers carried forward.
   - `source`: counterpart or agent (e.g. "WorkBuddy").
   - `related`: wikilinks to the *durable* notes holding the details — the digest stays shallow on purpose.
3. Body (target ≤ ~250 words):
   - `## TL;DR` — one or two sentences: what this conversation achieved.
   - `## Decisions` — bullets mirroring `decisions` (1 line each; link out instead of explaining).
   - `## Open` — optional bullets mirroring `open`.
   - **No** "background / narrative / revised-ideas" essays.
4. Wikilinks: prefer *existing* durable notes over re-explaining (bounded-search rules from Note Creation).
5. Write, apply the detected index strategy, validate (same as Note Creation).

### Quality guarantee (no factual drift, no loss)
- **Grounded only.** Every `decisions` bullet must trace to this conversation. If you're unsure X was actually decided, **do not write it** — capture outcomes, not inferences.
- **Atomic, not narrative.** One self-contained outcome per bullet. Depth belongs in `related` notes; never re-tell the story (prose is where drift crept in before).
- **Conflict resolution (Mem0-style).** If a new decision contradicts an existing digest's `decisions`, **update the old bullet** — never append a contradictory second one.
- **Completeness.** `TL;DR` + `decisions` are mandatory and non-empty. An empty-decisions digest is invalid.
- **Self-check.** After writing, run `audit_vault.py --strict` and re-read the note; delete any claim not grounded in the chat.

> Rule of thumb: a future agent gets the gist in <30 seconds and knows which linked note holds the depth. If not, shorten it.
