# Note Creation Workflow (reference)

Load only for an explicitly requested **new** note. This file is the complete
ordinary-create workflow: do not also load `yaml-standards.md`,
`rules-and-errors.md`, `git.md`, or `task-memory.md` unless the current task
specifically needs troubleshooting, Git post-processing, or opted-in handoff.

## Minimal Ordinary Path

1. Infer the type when confidence is high, then run one discovery call:
   `vault-info --json --compact --type <slug>`. If unclear, omit `--type`.
2. Read Vault-local governance at the root and target path; choose type, folder,
   naming, metadata, README, and Git actions from those rules.
3. If governance requires Git, load `git.md` and complete its pre-write check
   before fetching or deeply reading source content.
4. Supply complete Markdown to `create-note --preflight-json` and inspect the
   structured validation.
5. Repeat the same input with `--apply --compact-json`; keep automatic audit on.
6. Optionally use bounded link suggestions, then report the saved path.

The helper handles template loading, index strategy, exclusive creation, and
per-note audit. Ordinary creation needs no template read, second index probe,
or post-audit file read.

## Bundled Helper Runner

Set `<skill-root>` to the directory containing the active `SKILL.md` and invoke
helpers through:

```bash
python <skill-root>/scripts/run_helper.py <helper-name> ...
```

## Step 1: Vault Discovery and Governance

Resolve the Vault in order: `OBSIDIAN_KB_VAULT` → `~/.obsidian-kb-config` → ask.
A valid Vault contains `.obsidian/` and `Templates/`. Get its folders, index
strategies, custom templates, and selected standard headings in one call:

```bash
python <skill-root>/scripts/run_helper.py vault-info <vault> \
  --json --compact --type <slug>
```

Stop if invalid. Apply rules in this order: user request → Vault-local
governance files (`AGENTS.md`, `CLAUDE.md`, etc.) at the root and target path →
generic skill defaults. Do not scan the whole Vault. Follow governed subfolders
with `--folder` when their route is more specific than the type default. If governance requires Git, load
`git.md` and finish its pre-write synchronization now, before fetching or deeply
reading source content. A Git safety stop should happen before source-analysis
tokens are spent. When type is not yet clear, omit `--type`; preflight heading
diagnostics remain the fallback. Do not run a second discovery call.

## Index Strategy Detection (diagnostic only)

`vault-info` already reports every folder's strategy, and `create-note` applies
the chosen target's strategy internally. Do not call `detect-index` during
ordinary creation. Use it only to diagnose an explicit index problem:

```bash
python <skill-root>/scripts/run_helper.py detect-index <vault> --folder <folder> --json
```

Folder Index mode and Dataview own their listings.
Never append links to plugin-managed indexes. A static `INDEX.md` is updated by `create-note` when
applicable. Folder Index 1.0.30 graph hierarchy requires folder-named indexes;
warn on an incompatible existing configuration, but never rename it silently.

## Step 2: Choose Create, Type, and Folder

Create unless the user identifies an existing note or explicitly asks to
append/update; then follow `update-note.md`. Infer the type from context:
`daily-note`, `meeting-note`, `learning-note`, `web-clip`, `insight-note`,
`conversation-digest`, `project-note`, `person-note`, or opted-in `task-memory`.
Uncertain quick capture routes to `00-Inbox/`.

The bundled type default supplies a top-level folder. Vault governance wins for
more specific routes such as `20-Learning/Java`; express that decision with
`--folder`. The helper is not expected to parse arbitrary governance prose.

### Missing category exception

Existing governed categories skip this entire exception. If a stable topic has
no category, read only `missing-category.md`, propose one full category path,
tell the user it may be renamed, and separately ask whether to update the
applicable `AGENTS.md`. Do not mutate before both answers are recorded.

## Step 3: Delegate Template Loading

The Vault's `Templates/<Name>.md` is the source of truth. Compact discovery
returns the selected standard heading shape and `custom_templates`. Standard
types use those headings. Do not read the template file yourself. If the
selected type appears in `custom_templates`, read only `custom-template.md`,
call `template-contract` exactly once, stop on unknown placeholders, and pass
`--expect-template-sha256 <sha256>` to both preflight and apply. `create-note`
still loads the template internally and audits required template headings.

If templates are genuinely missing, ask before bootstrapping them with
`scaffold-templates <vault> --apply`; it does not overwrite without `--force`.

## Steps 4–5: Supply Complete Markdown and Preflight

Pass complete Markdown through `--stdin` or `--content-file`, including optional
frontmatter such as:

```yaml
source: "https://example.com/article"
related: ["[[Existing Note]]"]
```

Merge precedence is `type defaults < Vault template < input frontmatter < explicit CLI fields`.
Always use today's date and the routed type. `web-clip` requires non-empty
`source`, `author`, and `published`; missing fields fail before any mutation.

Pipe external or transient content through `--stdin`:

```bash
python <skill-root>/scripts/run_helper.py create-note <vault> \
  --type <slug> --title "<title>" --stdin [--expect-template-sha256 <sha256>] \
  --preflight-json
```

`--preflight-json` returns final frontmatter, destination, SHA-256, byte/line
counts, and the same note-level validation used after write without echoing the
body. A template-order finding includes the expected headings, actual headings,
and first mismatch; repair the complete sequence in one edit before rerunning
preflight. Use full `--json` only when the rendered body is explicitly needed.

## Step 6: Wikilinks

Use `[[wikilinks]]` only for high-confidence semantic relationships. With
`--suggest-links`, the bounded helper will list the target folder's filenames,
inspect only name-relevant sibling folders, score specific tags/type/Unicode
title tokens, and suppress candidates below its confidence threshold. Add at
most five useful links or skip them; never force weak links.

## Steps 7–8: Apply Once

Repeat the exact validated content:

```bash
python <skill-root>/scripts/run_helper.py create-note <vault> \
  --type <slug> --title "<title>" --stdin [--expect-template-sha256 <sha256>] \
  --apply --compact-json
```

`--content-file` must resolve inside the Vault; external content belongs on
`--stdin`. The helper merges the template, writes exclusively with a numeric
suffix on collision, updates only a static index when applicable, and returns
the applied path plus audit. Do not manually update Folder Index or Dataview.

### Step 9: Validate Result

Keep automatic audit enabled. It checks frontmatter, required template
headings, broken wikilinks, unresolved placeholders, and required web-clip
metadata. A clean compact apply audit completes verification; do not re-read
the note merely to prove it exists. Investigate only if the audit reports a
finding or the user explicitly requests an additional content review.

## Write Boundary

An ordinary create request writes at most the requested note and, only for a
static strategy, its index entry. Do not read or write `.workbuddy/memory`,
Task Memory, a daily log, or a secondary recap unless the user separately asks
for it or higher-priority runtime instructions explicitly require it.

### Step 10: Confirm to User

Report the saved path, a brief capture summary, audit status, and only useful
follow-up actions. Do not narrate redundant internal reads or checks.
