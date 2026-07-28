# Note Creation Workflow (reference)

Load only for an explicitly requested **new** note. This file is the complete
ordinary-create workflow: do not also load `yaml-standards.md`,
`rules-and-errors.md`, `git.md`, or `task-memory.md` unless the current task
specifically needs troubleshooting, Git post-processing, or opted-in handoff.

## Minimal Ordinary Path

1. Infer the type when confidence is high, then run one discovery call:
   `vault-info --json --compact --type <slug>`. Use `--type` only for
   template-backed types; omit `--type` for opted-in `task-memory` or uncertainty.
2. Read Vault-local governance at the root and target path; choose type, folder,
   naming, metadata, README, and Git actions from those rules.
3. If governance requires Git, load `git.md` and complete its pre-write check
   before fetching or deeply reading source content.
4. For a finished source-backed article or material rewrite, read only
   `deep-capture.md` and complete its semantic gate before preflight.
5. If discovery reports the selected destination in `crowded_folders`, read
   only `folder-routing.md` and resolve the route before writing.
6. Supply complete Markdown to `create-note --preflight-json` and inspect the
   structured validation.
7. Repeat the same input with `--apply --compact-json`; keep automatic audit on.
8. Optionally use bounded link suggestions, then report the saved path.

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
strategies, custom templates, crowded-folder signals, and selected standard
headings in one call:

```bash
python <skill-root>/scripts/run_helper.py vault-info <vault> \
  --json --compact --type <slug>
```

Stop if invalid. Apply rules in this order: user request → Vault-local
governance files (`AGENTS.md`, `CLAUDE.md`, etc.) at the root and target path →
generic skill defaults. Do not scan the whole Vault. Follow governed subfolders
with `--folder` when their route is more specific than the type default. If governance requires Git, load
`git.md` and finish its pre-write synchronization now, before fetching or deeply
reading source content. Preflight heading diagnostics remain the fallback. Do
not run a second discovery call.

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

### Article capture depth

A saved article is deep by default when the user asks to learn, summarize into
the knowledge base, archive as knowledge, or “沉淀” it. Before drafting or
materially rewriting a finished source-backed article, read only
`deep-capture.md` and follow its intent routing, source access, profile,
materiality, coverage, enrichment, and acceptance contract.

An explicitly quick, bookmark, save-for-later, or unread source belongs in
`00-Inbox/` and must not be presented as finished knowledge. If required source
material is inaccessible, follow `deep-capture.md` instead of silently reducing
the result to a concept summary.

### Missing category exception

Existing governed categories skip this entire exception. If a stable topic has
no category, read only `missing-category.md`, propose one full category path,
tell the user it may be renamed, and separately ask whether to update the
applicable `AGENTS.md`. Do not mutate before both answers are recorded.

### Crowded destination

If compact discovery reports the selected existing destination in
`crowded_folders`, read only `folder-routing.md`. Reuse an existing suitable
child or propose one stable subject child under that contract. Do not create a
missing directory through `create-note`.

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
Do not use vague placeholders such as `unknown`, `未知`, `N/A`, `TODO`, or
`待补充` to bypass this gate. When the complete source genuinely omits a fact,
use an explicit provenance marker such as `author: "原文未署名"` or
`published: "原文未标明"`.

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

For a finished article outside `00-Inbox`, `deep-capture.md` adds a required
content-bound `--capture-receipt-json`. The first preflight may intentionally
return `missing-capture-receipt` together with the final content SHA-256; build
the receipt against that hash and rerun preflight. This is not a successful
preflight and must not be followed by apply. Preserve the accepted
`semantic_receipt.sha256` for apply.

Use the mutually exclusive `--capture-receipt-file <path>` form described in
`deep-capture.md` when the receipt is too detailed for safe inline shell
transport.

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
  [--capture-receipt-json '<compact-json>' \
   --expect-capture-receipt-sha256 <preflight-receipt-sha256>] \
  --apply --compact-json
```

`--content-file` must resolve inside the Vault; external content belongs on
`--stdin`. The helper merges the template, writes exclusively with a numeric
suffix on collision, updates only a static index when applicable, and returns
the applied path plus audit. The destination directory must already exist. Do
not manually update Folder Index or Dataview.

### Step 9: Validate Result

Keep automatic audit enabled. It checks frontmatter, required template
headings, broken wikilinks, unresolved placeholders, and required web-clip
metadata. A clean compact apply audit completes verification; do not re-read
the note merely to prove it exists. Investigate only if the audit reports a
finding or the user explicitly requests an additional content review.

The per-note create audit follows the active Vault template, including a
customized contract. A full-vault audit additionally checks every historical
`web-clip` against the versioned v1.20 deep-capture heading baseline and reports
an outdated `Templates/Web Clip.md`; preserving an old template must not lower
that historical quality gate.

Mechanical audit does not prove semantic depth. For deep article capture,
completion additionally requires the semantic acceptance in
`deep-capture.md`. Do not report success when either gate fails.

## Write Boundary

An ordinary create request writes at most the requested note and, only for a
static strategy, its index entry. Do not read or write `.workbuddy/memory`,
Task Memory, a daily log, or a secondary recap unless the user separately asks
for it or higher-priority runtime instructions explicitly require it.

### Step 10: Confirm to User

Report the saved path, a brief capture summary, audit status, and only useful
follow-up actions. For deep capture, separately report the selected profile,
source coverage, semantic receipt SHA-256, unresolved item count, semantic
acceptance, and mechanical audit. Do not narrate redundant internal reads or
checks.
