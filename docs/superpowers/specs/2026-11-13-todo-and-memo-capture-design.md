# Todo and Memo Capture

**Status: corrected after review.** This replaces the original issue 215 text.
Issue 212 stays deferred and is not part of this work. The 2026-08-11 inbox
decision (filing preserves the note count and never authors a note) stays in
force.

## What was actually wrong

On `daea994` there was no section-level append. `review-open-loops` was
read-only (`read_only: true`) and could not tick, cancel, or postpone. Those
two gaps are real.

The original problem statement overstated the rest:

- Canonical action headings are 10, five Chinese and five English, mirrored
  from the templates. Not five.
- `create-note` collision names look like `2026-07-09 T-2.md` (date, space,
  title, `-2`). Not `2026-11-13-2.md`.
- Open loops ordered by frontmatter `date:`, not by filesystem creation time.
- `unknown-target` is the skip code when no keyword matches. A body that
  contains `idea` already files to `30-Insights`. Notes are not locked.
- Checksum hard-rejection is the deep-capture gate. Ordinary notes are not all
  forced through it.

## Decisions

1. **`append-entry`** writes one line into an existing heading.
   - Today's daily note is `15-Daily/YYYY-MM-DD.md`. If that file is missing,
     create it from the daily template. If the template cannot be read, fail.
     Do not invent a short skeleton. Do not add `-2`.
   - No `--section`: `--todo` uses `待办事项`; a memo uses `今日记录`.
   - A missing heading or more than one match fails with `append-failed`.
     The helper does not create a heading.
   - The same formatted line already in that section is a no-op
     (`duplicate: true`, no write).
   - Exact heading match wins. A synonym matches only when it stands for the
     requested heading. Two different synonym headings are ambiguous.
2. **`complete-loop`** is a different command from `review-open-loops`.
   `review-open-loops` stays read-only. `complete-loop` takes a vault-relative
   path, a 1-based line, and an optional `--expected-text` substring.
   `tick` writes `- [x]` and `✅ YYYY-MM-DD`. `cancel` writes `- [-]` and
   `⛔ YYYY-MM-DD`. `postpone` leaves the box open and writes `📅 YYYY-MM-DD`.
   It does not check that the line sits under an action heading.
3. **Paths** use `resolve_existing_within_vault` or, for a daily note that
   does not exist yet, `resolve_target_within_vault`.
4. **Backups** of an existing note use `backup_note`
   (`YYYY-MM-DD-HHMMSS`, disambiguated when the stamp already exists) and then
   `prune_backups`. A date-only directory is not a backup. A new file has
   nothing to snapshot.
5. **Due dates** `📅 YYYY-MM-DD` and `[due:: YYYY-MM-DD]`, and priorities
   `🔺` / `🔼` / `🔽` (plus `[priority:: high|medium|low]`), are parsed into
   the open-loop item. This syntax is new; it was not a previous vault
   convention. Plain checkboxes still work.
   Sort key: explicit due date first, earlier first; then undated tasks by
   the note's `date:`; notes with no `date:` last. Priority does not sort.
   There is no due-range filter and no completion-status filter. Checked and
   cancelled boxes stay out of the queue.
6. **Synonyms** are a fixed widening of the scanner, not a second template
   mirror. The seven values (`今日待办`, `待办清单`, `临时任务`, `TODO`,
   `Todo`, `Todos`, `备忘事项`) all name `待办事项`. They do not retarget
   `下一步行动` or `Tasks`. The reported heading stays the text in the note.
   The table must be non-empty, and every value must be a key of
   `ACTION_HEADINGS`. That guard is inventory row 80. Row 78 does not read
   this table. A heading in neither table is still ignored.
7. **Inbox** keeps whole-file moves. `待办` / `备忘` / `日记` (and `daily`,
   `todo`, `task`, `memo`, `随手记`) route to `15-Daily/<original name>`.
   `周会` stays on the meeting route (`10-Work`). `复盘` stays on the insight
   route (`30-Insights`). First match wins. There is no merge into today's
   daily note and no delete-after-merge.
8. **Triggers.** In `core/OBSIDIAN_KB.md`, `记个待办` and `备忘一下` are
   explicit item-capture intent and call `append-entry` only. Long-form
   capture still requires the existing save phrases and its preflight.
9. **`build.py`** syncs `core/` and the package tree. It does not register
   console scripts or invent runner rows. `append-entry` and `complete-loop`
   stay on the write runner. They must not be added to the retrieval bundle's
   executable helpers. Gemini CLI is not a build target.

## Out of scope

- Issue 212's three options: delete Task Memory, move `decisions` /
  `--replace-decision` onto project notes, or give task-memory a template so
  `## Open` enters the open-loop queue.
- Merging inbox files into the daily note.
- Due-range queries, completion-status queries, and priority sort.
- Daemons, calendar alarms, and reimplementing the Obsidian Tasks or Dataview
  plugins.
- Weakening "DO NOT auto-save" for articles, web clips, or research digests.
