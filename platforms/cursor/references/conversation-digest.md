# Conversation Digest Workflow (reference)

Loaded only when the user asks to compress a chat into a note. The always-loaded skill body points here.

## Conversation Digest Workflow

Use this to compress a conversation into a **reusable context artifact** — a note a future agent (or you) can re-read in seconds to resume work (triggers: "沉淀这段对话", "summarize this chat", "把对话存成笔记").

> **Design intent — this is the part that makes it usable as context.** A digest is *decision-dense, link-rich, and short* — **not** a transcript or a narrative essay. Its only job is to let a future reader answer *"what was decided, what's still open, where are the details"* without re-reading the whole chat. If it reads like a blog post, it failed: the prose buries the decisions and wastes context tokens when an agent loads it later. Put the depth in the linked durable notes; keep the digest shallow.

### When to use
- The conversation produced decisions, trade-offs, or action items worth keeping.
- The user explicitly asks to save or summarize the discussion.

### Routing
- Conversation about a specific active project → `40-Projects/`.
- Otherwise → `30-Insights/` with `type: conversation-digest`.
- One digest per *coherent topic*. Split only when topics are independent; without confirmation, write one aggregate digest and suggest later extraction.

### Format (agent-friendly — keep it scannable)
1. Resolve & validate the vault (same as Note Creation).
2. `type: conversation-digest`. **Frontmatter carries the load** — this is what a future agent filters/scans first:
   - `date`: today.
   - `tags`: 2–5 lowercase kebab-case tags (general category; satisfies the validator).
   - `decisions`: a **list of short, self-contained decision lines** (each ≤ ~120 chars; state the decision, and *why* only if non-obvious). This is the primary field — a future agent reads this and knows the outcome.
   - `open`: optional list of open questions / blockers carried forward.
   - `source`: the counterpart or agent (e.g. "WorkBuddy").
   - `related`: wikilinks to the *durable* notes that hold the details — the digest stays shallow on purpose.
3. Body (target ≤ ~250 words total):
   - `## TL;DR` — one or two sentences: what this conversation achieved.
   - `## Decisions` — a bullet list mirroring `decisions` (1 line each; link out to deeper notes instead of explaining).
   - `## Open` — optional bullet list mirroring `open`.
   - **No** "background / narrative / revised-ideas" essays. Those details belong in the linked durable notes, not the digest.
4. Wikilinks use the bounded-search rules from Note Creation Step 6; prefer linking to *existing* durable notes over re-explaining.
5. Write the file, apply the detected index strategy, and validate (same checks as Note Creation Step 9).

> Rule of thumb: a future agent should get the gist in <30 seconds and know exactly which linked note holds the depth. If it can't, shorten it.
