# Inbox Filing Workflow (reference)

Loaded only when the user asks to file, sort, or clear the Vault Inbox. The
always-loaded skill body points here.

Decisions behind this workflow:
`docs/superpowers/specs/2026-08-11-inbox-filing-entrypoint-decision.md`.

## What filing is, and what it is not

**Filing moves notes the user already wrote.** Each Inbox note already exists,
already passed the explicit-save-intent gate when it was captured, and is
already the user's own words. Filing relocates it into its governed folder,
fills in the `date`, `type`, or `tags` the quick capture omitted, and appends an
index line. The Vault holds exactly as many notes after the run as before.

**Filing never authors a note.** It does not generate prose, invent links, or
create a note to hold content it could not classify. This is why the body's
`≤1 note written` bound does not apply: that bound exists to stop an Agent from
generating a pile of notes from one conversation, and filing generates none.

The bound that does apply is the Inbox itself. A run files what is in
`--inbox` and nothing else — never a path outside it, which the helper enforces
and refuses.

## Step 1: Resolve & Validate Vault Path

Same as the Create workflow. The helper additionally refuses an `--inbox` that
resolves outside the Vault.

## Step 2: Produce the Filing Plan (read-only, never skipped)

```
python <skill-root>/scripts/run_helper.py process-inbox <vault> --plan --json
```

`--plan` is read-only and is the default. Run it even when the user's request
sounds decisive: "整理一下 Inbox" is intent to file, not consent to a specific
set of moves the user has not seen yet. Destinations are **inferred** — from the
note's `type` when present, from body keywords when not — and keyword inference
is exactly what the user must be able to overrule per note.

## Step 3: Show the Plan and Get Confirmation

Present, per note: current path, destination folder, inferred `type`, and the
metadata fields filing would add. Call out anything inferred from body keywords
rather than from an existing `type` — that is where the plan is most likely to
be wrong.

**Wait for the user to confirm this plan.** Filing is a write path, so the
skill's first rule governs it: never write to the Vault on its own. Nothing
moves until the user has seen the plan and approved it.

If the user rejects individual notes, do not hand-roll a partial apply. Leave
them in the Inbox and say so — they stay for the next run.

## Step 4: Apply Only After Confirmation

```
python <skill-root>/scripts/run_helper.py process-inbox <vault> --apply
```

`--apply` moves the files, writes the missing frontmatter, and appends to a
static `INDEX.md`. It never overwrites, and it resolves a name clash differently
from note creation: when the destination already holds a file of that name the
note stays in the Inbox. Filing does **not** apply the body's `-2` rename rule —
that rule belongs to authoring a new note, and renaming someone's existing note
to make room is not filing it. Folder Index and Dataview listings are not
touched — they generate themselves.

## Step 5: Report What Actually Moved

Report the count that committed, not the count examined. Notes the helper
refused stay in the Inbox and each keeps its refusal reason — surface those
rather than reporting a clean run. A refusal is the contract working, not an
obstacle to route around: never move a refused note by hand to make the number
look better.

## Refusals

Filing refuses **per note**, not per run: a refused note leaves the rest of the
plan intact and the run still exits 0. Both phases report the same way — the
refusal is a field on that note's own plan entry, never a top-level error.
`skip` carries the readable reason, `skip_code` the machine-readable one.

**Planning refusals** — nothing was written:

- `unknown-target` — the destination folder could not be inferred. The most
  common refusal in an unstructured Inbox, and the one to expect first.
- `unreadable-frontmatter` — the note's YAML could not be parsed.
- `unsafe-inbox-entry` — the Inbox entry is not a regular file.

**Apply refusals** — raised at write time:

- `target-exists` — the destination already holds that name. Filing does not
  rename to make room.
- `source-removal-failed` — the copy was rolled back and the Vault is
  unchanged; the note is still in the Inbox.
- `partial-apply` — **the copy survived and the note now exists in both
  places.** This is the only filing refusal that leaves the Vault changed.
  Report both paths and tell the user to remove one by hand; never delete
  either copy yourself to tidy the result.

Read every entry: the array holds refused and fileable notes together, so a
plan that looks complete may contain notes that will never move. There is no
top-level `error` key to check. The readable messages also go to stderr for a
human watching the run, but `skip_code` is what you act on.

Only an `--inbox` path that resolves outside the Vault refuses the whole run,
through the usual `{"error": {"code", "message"}}` shape. See
`rules-and-errors.md` for the codes filing shares with other helpers.
