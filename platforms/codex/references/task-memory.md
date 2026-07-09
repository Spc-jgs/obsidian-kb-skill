# Task Memory Workflow (multi-agent handoff)

> **Load this file only after the user enables task memory.** When off (the default), do **not** read it — it is kept out of the always-loaded skill body on purpose to save context tokens.

This workflow carries the *state of one long task* across agent handoffs. Example: Agent A (WorkBuddy) does part, then Agent B (Codex) resumes. The memory is one **agent-agnostic** note (`TASK.md`) any agent reads to pick up where the last left off — plain markdown + structured frontmatter so every agent (WorkBuddy / Codex / Qoder / Claude) parses it.

## Activation (the toggle)

**OFF by default.** Disabled unless the user explicitly opts in ("开启任务记忆" / "handoff", or a task note carries `task-memory: enabled`). When off, agents work as before: no task note read/written, zero overhead. Rationale: a global always-on task log becomes noise nobody maintains, so activation is per-task and explicit.

- **Global master switch** (optional): env `OBSIDIAN_KB_TASK_MEMORY=on|off` (default `off`).
- **Per-task switch**: once opted in, create `Tasks/<slug>/TASK.md` with `task-memory: enabled`. Set `disabled` (or archive the note) to turn off.

## TASK.md structure

Created via `create_note.py` (`--type task-memory --folder Tasks/<slug>`) or a native write tool:

```yaml
---
task-id: <slug>
type: task-memory
status: active | blocked | done
task-memory: enabled            # per-task toggle
agents: [WorkBuddy, Codex]      # who has touched it
step: "Implementing X module"   # current working state
decisions: ["Chose Postgres over Mongo (scale)"]
constraints: ["p99 < 200ms"]
artifacts: ["[[path/to/file]]"]
open: ["Awaiting API key from user"]
updated: 2026-07-09T16:00
---
## TL;DR
<2 sentences: what this task is and where it stands>

## Decisions (crystallized)
- ...

## Open
- ...

## Log
- 2026-07-09 16:00 [Codex] finished X, handing to WorkBuddy for Y
```

### Core vs Archival (MemGPT-style)
- **Core memory = frontmatter** (`status` / `step` / `decisions` / `constraints` / `open` / `artifacts`). This is the *only* slice the incoming agent reads on handoff — tiny, machine-readable, sufficient to resume.
- **Archival memory = `## Log` + body prose.** Read on demand only, when the agent needs the trail or the nuance. Never force the incoming agent to load the whole file.

## Handoff protocol

**Outgoing agent (before yielding):**
1. Resolve & validate the vault; locate `Tasks/<slug>/TASK.md`.
2. Update: set `step`, append to `decisions` / `open` / `artifacts` as needed, add self to `agents`, append one `Log` line (`[<agent>] <finished / next>`). Bump `updated`.
   - Prefer the constraint-based updater `scripts/update_note.py` (`obsidian-update-note`): writes only frontmatter + Log, never clobbers prose, caps Log. Dry-run by default; `--apply` to write.
   - **Conflict resolution (Mem0-style):** before appending a decision, check existing `decisions`. If the new info *contradicts* an old one, replace it instead of piling on: `--replace-decision "old substring::new decision"`. If no match, it appends as new.
   - Native-write agents may edit directly instead.
3. Hand the next agent (or user) the task slug.

**Incoming agent (first action):**
1. Read `Tasks/<slug>/TASK.md` — **frontmatter first** (core memory). Only open `## Log` if you need the trail.
2. Honor `decisions` / `constraints` — do not contradict or redo them.
3. Continue from `step`; before yielding, run the outgoing steps above.

### Quality guarantee (complete, valuable, no drift)
- **Provenance (Zep-style):** every `Log` line is `ISO-date [agent] what`, so a contradiction can be traced to when it was established.
- **Grounded decisions:** `decisions` capture what was *actually* chosen, not speculation. If unsure, leave it out or note it as `open`.
- **Completeness:** `status` + `decisions` + `step` are mandatory on a task note — a task note with empty `decisions` is invalid.
- **Self-check:** after a handoff write, run `audit_vault.py` and re-read the note; verify `decisions` match what was really decided before yielding.

> Rule of thumb: a cold agent should resume in one frontmatter read. If not, the outgoing agent under-wrote the core.
