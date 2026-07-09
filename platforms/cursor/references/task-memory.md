# Task Memory Workflow (multi-agent handoff)

> **Load this file only after the user enables task memory.** When task memory is off (the default), do **not** read this file — it is kept out of the always-loaded skill body on purpose to save context tokens.

This workflow carries the *state of one long task* across agent handoffs — multi-agent continuity. Example: Agent A (WorkBuddy) does part of a task, then Agent B (Codex) resumes it. The task memory is a single **agent-agnostic** note (`TASK.md`) that any agent can read to pick up where the last one left off. It must be plain markdown + structured frontmatter so every agent (WorkBuddy / Codex / Qoder / Claude) can parse it.

## Activation (the toggle)

**OFF by default.** This layer is *disabled* unless the user explicitly turns it on in the session (says "开启任务记忆" / "handoff", or a task note carries `task-memory: enabled`). When off, agents work exactly as before: no task note is read or written, zero overhead. Rationale: a global always-on task log becomes noise nobody maintains, so activation is per-task and explicit.

- **Global master switch** (optional): env `OBSIDIAN_KB_TASK_MEMORY=on|off` (default `off`). When `off`, the whole workflow is skipped regardless of any task note.
- **Per-task switch**: once the user opts in, create `Tasks/<slug>/TASK.md` with `task-memory: enabled` in its frontmatter. That field *is* the per-task toggle — set `disabled` (or delete the note) to turn it off for that task.
- If the user says "关闭任务记忆", set `task-memory: disabled` (or move the note to `90-Archive/`) and stop maintaining it.

## TASK.md structure

A `task-memory` note, created via `create_note.py` (`--type task-memory --folder Tasks/<slug>`) or a native write tool:

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

- `decisions` / `constraints` / `open` / `artifacts` are the **crystallized** layers (machine-readable, survive across agents). `step` is the volatile working state. `Log` is a bounded, timestamped handoff trail (keep the last ~30 lines; drop older).
- The body prose (`## Decisions` / `## Open`) mirrors the frontmatter for skimming; frontmatter is the source of truth.

## Handoff protocol

**Outgoing agent (before yielding):**
1. Resolve & validate the vault; locate the task note (`Tasks/<slug>/TASK.md`).
2. Update it: set `step` to what it's handing off, append to `decisions` / `open` / `artifacts` as needed, add self to `agents`, and append one `Log` line (`[<agent>] <what finished / what's next>`). Bump `updated`.
   - Prefer the constraint-based updater `scripts/update_note.py` (`obsidian-update-note`): it writes only frontmatter + the Log, never clobbers prose, and caps the Log. Dry-run by default; pass `--apply` to write.
   - Agents with a native write tool may edit the note directly instead.
3. Hand the next agent (or the user) the task slug so they can read it.

**Incoming agent (first action):**
1. Read `Tasks/<slug>/TASK.md` *before* doing anything else.
2. Honor `decisions` / `constraints` — do not contradict or redo them.
3. Continue from `step`; when done with its part, run the outgoing steps above before yielding.

> Rule of thumb: the task note should let a cold agent resume in one read. If it can't, the outgoing agent under-wrote it. Keep `decisions` short and `Log` bounded.
