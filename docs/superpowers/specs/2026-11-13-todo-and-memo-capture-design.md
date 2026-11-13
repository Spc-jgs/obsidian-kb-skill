# Todo and Memo Capture Design

## Problem Statement

Users of the Obsidian Knowledge Base Skill currently face major friction when attempting to capture, manage, and close personal todos (待办) and quick memos/fleeting notes (备忘). The existing skill is deeply optimized for high-ceremony, long-form, immutable knowledge synthesis (e.g. verified web clippings, project overviews, structured meeting notes), which creates serious barriers for high-frequency, lightweight, item-level personal knowledge management:

1. **Lack of Item-Level Atomic Capture**: Capturing a single thought or action item requires either generating a standalone document with full YAML frontmatter, standard headings, and preflight checksum verification (cluttering the vault with single-sentence notes), or running a heavyweight update protocol that demands reading the full note, writing timestamped byte-level backups, and undergoing strict post-audit verification.
2. **Daily Note Splitting and Mutation Hazards**: When appending a todo to today's daily log, existing creation tools enforce unique file creation and automatically create numbered duplicates (e.g. `2026-11-13-2.md`), fracturing daily entries. Meanwhile, existing note update scripts are hardcoded to multi-agent task memory workflows and silently inject unwanted metadata (`task-memory: enabled`) and append to irrelevant log sections.
3. **Task Lifecycle is a Read-Only Dead End**: The open loops retrieval utility explicitly refuses to function as a task manager—it can scan unchecked boxes, but provides zero capability to mark items complete (`- [x]`), reschedule them, or cancel them.
4. **Chronological Inversion in Task Ranking**: Open loop queries rank tasks based on the host document's creation date rather than the task's actual due date. A new task added to an older project document is treated as an ancient backlog item and inappropriately prioritized over today's tasks.
5. **Rigid Heading Contracts**: Task scanners strictly recognize only five hardcoded template headings. Custom but ubiquitous headings like "今日待办", "待办清单", or "TODO" are silently ignored, causing user tasks to disappear from retrieval views.
6. **Inbox Stagnation for Fleeting Notes**: Quick memos deposited into the inbox cannot be categorized into formal knowledge folders, causing the inbox organizer to reject them with unknown-target errors, leaving them permanently stranded.

## Solution

Introduce a native, item-level capture and lifecycle management subsystem into the skill ecosystem:

1. **Atomic Entry Append Capability**: Provide an atomic, idempotent append interface that targets specific sections of daily notes or arbitrary documents. If a targeted daily note does not exist, initialize it cleanly from its template; if it already exists, append the item into the designated section without duplicating files or perturbing surrounding content.
2. **Task Lifecycle Operations**: Provide a focused lifecycle mutation interface to locate and transition action item states (marking complete with completion date stamps, cancelling, or updating due dates) directly from the command line or agent invocation.
3. **Ecosystem-Standard Task Metadata Parsing**: Extend open loop scanning to extract inline due dates (`📅 YYYY-MM-DD`) and priority markers (`🔺`, `🔼`, `🔽`) conforming to Obsidian community standards (Obsidian Tasks and Dataview). Sort tasks primarily by explicit task due dates, falling back to document dates only when undated.
4. **Decoupled Heading Synonym Resolution**: Implement an alias resolution layer for common Chinese and English action headings, preserving the strict 1:1 bidirectional template consistency inventory while accepting natural heading variations at runtime.
5. **Inbox Daily Consolidation**: Add multilingual routing keywords to inbox processing and introduce a consolidation workflow that merges short inbox memos and tasks into the daily note as list items, cleanly pruning the original temporary files.

## User Stories

1. As a knowledge worker, I want to append a single todo item to today's daily note with a single command, so that I can capture urgent tasks without interrupting my train of thought.
2. As a knowledge worker, I want the system to automatically initialize today's daily note from the standard template if it does not yet exist when appending a todo, so that I never have to manually create the file first.
3. As an active note-taker, I want to append a timestamped memo entry to today's record section, so that I can maintain a chronological scratchpad of thoughts throughout the day.
4. As an Obsidian user, I want appending to today's daily note to never create duplicate files with `-2` suffixes, so that my daily logs remain unified and coherent.
5. As an Obsidian user, I want the append operation to fail safely if the target heading does not exist or if content is ambiguous, so that my note structure is never corrupted.
6. As a task manager, I want to mark an open todo item as completed with a single command, so that I can close the loop on finished work directly from my terminal or agent.
7. As an Obsidian Tasks user, I want completed todos to automatically receive a completion timestamp (e.g. `✅ YYYY-MM-DD`), so that my task completion history is tracked accurately.
8. As a planner, I want to postpone an open todo by updating its scheduled or due date, so that my task queue reflects current commitments without losing context.
9. As a user reviewing my day, I want to cancel an obsolete todo (marking it as dropped or cancelled), so that I know what was intentionally abandoned rather than forgotten.
10. As a user reviewing open tasks, I want task sorting to respect inline due dates (`📅 YYYY-MM-DD`) rather than solely relying on the note's creation date, so that urgent tasks added to old project notes surface at the top.
11. As a power user, I want inline priority flags (e.g. `🔺`, `🔼`, `🔽`) to be extracted and exposed in open loop queries, so that I can prioritize high-impact tasks immediately.
12. As a user with custom daily templates, I want common action headings (such as "今日待办", "待办清单", "TODO") to be recognized as action sections, so that my unticked tasks are not silently missed.
13. As a maintainer, I want heading synonym resolution to be decoupled from the primary template reflection inventory, so that repository consistency tests remain passing.
14. As an agent handling quick conversational inputs, I want natural language triggers (e.g., "记个待办", "备忘一下") to route directly to atomic capture without triggering long-form article preflight ceremonies, so that response latency remains minimal.
15. As a mobile or quick-capture user sending fleeting notes to 00-Inbox, I want the inbox processor to recognize memos and todos, so that they are routed towards daily notes rather than getting rejected as unknown targets.
16. As an inbox organizer, I want the option to merge short inbox entries into the daily note as bullet items, so that my vault is not polluted by dozens of single-sentence files.
17. As an inbox organizer, I want source inbox files to be cleanly removed after successful consolidation into the daily note, so that my inbox remains clean.
18. As a user who makes frequent edits, I want atomic append operations to use lightweight, deduplicated backup strategies, so that taking 20 quick notes a day does not generate 20 separate backup folders.
19. As a user operating in terminal and agent environments, I want all append and completion operations to return structured JSON responses with exact line numbers and diff summaries, so that automated tools can verify the result programmatically.
20. As a user concerned about data safety, I want dry-run modes for both appending and task completion, so that I can preview changes before writing them to disk.
21. As a bilingual user, I want the inbox router to recognize Chinese keywords (e.g., "待办", "备忘", "周会", "复盘"), so that Chinese notes in the inbox are routed correctly without manual tagging.
22. As an agent managing multi-step workflows, I want to target a specific project note's next actions section when creating a task, so that project-specific todos stay anchored to their project documents.
23. As a developer integrating external tools, I want the task tools to remain strictly CLI-first and deterministic, so that any script or shell automation can invoke them.
24. As an Obsidian user, I want all generated todo and memo entries to be UTF-8 without BOM, so that cross-platform file encoding issues never arise.
25. As a user with a large backlog, I want to query open loops filtered by due date range or completion status, so that I can focus only on today's agenda.
26. As a team member reviewing project notes, I want to view open action items grouped by project without opening individual project files, so that I can conduct swift standups.
27. As a minimalist, I want plain checkboxes without any plugins to remain fully supported, so that advanced metadata syntax remains optional.
28. As an auditor, I want all atomic mutations to maintain clean UTF-8 line endings and preserve surrounding whitespace, so that git diffs remain spotless.

## Implementation Decisions

- **Dedicated Atomic Append Module**: A dedicated entry insertion component will be built to handle localized, section-based line insertions. It avoids the document-level checks of full note creation and the heavy multi-agent handoff machinery of existing update scripts.
- **Dedicated Task Lifecycle Mutation Module**: A dedicated task transition component will be introduced to handle line-level checkbox modifications. It verifies the original line content before mutating, ensuring concurrency safety and exact string substitution.
- **Two-Tier Heading Resolution Strategy**: The canonical list of action headings remains strictly derived 1:1 from note templates to satisfy existing consistency inventory invariants. An alias mapping table will be introduced alongside it at runtime to resolve variations like "今日待办" and "TODO" to their canonical template counterparts before inspection.
- **Inline Task Metadata Conventions**: The system will align with Obsidian Tasks and Dataview standards for parsing and formatting task metadata:
  - Due dates use `📅 YYYY-MM-DD` or `[due:: YYYY-MM-DD]`.
  - Completion timestamps use `✅ YYYY-MM-DD`.
  - Cancellation indicators use `- [-]` with `⛔ YYYY-MM-DD`.
  - Priority indicators use emoji flags (`🔺` High, `🔼` Medium, `🔽` Low).
- **Date-First Queue Ordering**: Open loop ranking logic will prioritize explicit item due dates. Items with a past or current due date float to the top; items with no explicit due date fall back to their host note's date; undated notes remain at the end.
- **Consolidation Pipeline in Inbox Filing**: Inbox processing will be expanded with a merge capability. When an inbox entry is identified as an ephemeral memo or standalone todo, the engine extracts its payload, appends it under the daily note's respective heading, and purges the inbox note upon verified append success.
- **Lightweight Coalesced Backups**: High-frequency item appends will coalesce backup snapshots within the same calendar day for the same document under the existing backup hierarchy, preventing directory spam while guaranteeing rollback safety.

## Testing Decisions

- **What makes a good test**: Tests must verify only external observable behavior at the highest possible interface boundary—specifically CLI exit codes, stdout JSON payloads, filesystem mutations, and deterministic error responses. Tests must never inspect internal helper state or private function names.
- **Testing Seam**: The single testing seam is the public CLI runner interface (`run_helper.py <command> [args] --json`) and the corresponding packaged entrypoints. This guarantees that all platform bundles (Claude Code, Cursor, Qoder, Gemini CLI) exercise the exact same code path as automated tests.
- **Modules to be tested**:
  - The atomic entry append CLI (testing target resolution, section creation/fallback, template initialization when daily note is absent, and dry-run vs apply modes).
  - The task lifecycle CLI (testing checkbox transitions, completion stamping, postponement, cancellation, and validation on line mismatch).
  - Open loops retrieval (testing inline due date extraction, priority parsing, and multi-tier sorting).
  - Heading alias resolution and consistency inventory guard tests (verifying that template invariants and alias resolutions remain synchronized).
  - Inbox processing with Chinese keyword classification and daily note entry consolidation.
- **Prior Art**:
  - `tests/test_create_note.py`, `tests/test_review_open_loops.py`, `tests/test_inbox_filing.py`, and `tests/test_consistency_inventory.py` provide existing architectural patterns for CLI test runners, mock vaults, and invariant verification.

## Out of Scope

- Background daemon services, push notifications, or system calendar/alarm integrations (these belong to external operating system integrations).
- Re-implementing Obsidian client-side plugins (e.g. Dataview or Obsidian Tasks) within Python; the skill only adheres to their syntax standards.
- Removing or diluting the "DO NOT auto-save" governance rule for comprehensive, long-form knowledge captures (web clips, articles, research digests).
- Multi-user collaborative lock managers across networked vaults.

## Further Notes

- This specification directly addresses the diagnosis in Issue #212, addressing the gap where task memory was built for rare multi-agent handoffs while everyday single-user interruption-and-resume workflows lacked lightweight tooling.
- All additions will be synchronized across platform skill definitions using `build.py` upon implementation.
