# Note Creation Workflow (reference)

Loaded only when the user asks to save a **new** note. The always-loaded skill body points here. Read this *before* writing.

## Bundled Helper Runner

Set `<skill-root>` to the directory containing the active `SKILL.md`. Standard
Skill installations keep helpers under that directory. Claude Code and Cursor
compatibility adapters use `~/.obsidian-kb-skill/skill` as their Skill root.
Invoke every helper through:

```bash
python <skill-root>/scripts/run_helper.py <helper-name> ...
```

## When NOT to Use This Skill

Skip this skill (do not save to vault) when:

- The user is asking a question, debugging code, or having casual conversation
- The content is a one-off command/snippet with no lasting value
- The user has not explicitly asked to save, record, or remember
- The information is already in another canonical location (e.g. project README, git history)

Only invoke when there is **explicit save intent** (e.g. "save to Obsidian", "记一下", "沉淀到知识库", "add to my notes") **or** when summarizing a long conversation the user wants archived.


## Vault Discovery & Validation

The vault location is configured in a platform-specific way. Check in order:

1. Environment variable `OBSIDIAN_KB_VAULT` (if set)
2. Config file `~/.obsidian-kb-config` (single line containing the vault path)
3. If neither exists, ask the user for their vault path and create the config file

A valid Obsidian vault has `.obsidian/` and `Templates/` directories. To seed cold-start context (vault path, validity, template list, every folder's index strategy) in a single read-only call:

```bash
python <skill-root>/scripts/run_helper.py vault-info <vault> --json
```

If validation fails, **stop and report** — do not silently create files in a non-vault directory. Offer to (a) re-prompt for the path, or (b) initialize a new vault structure if the user confirms.


## Instruction Precedence

Apply in this order: (1) the user's current request, (2) Vault-local governance files (`AGENTS.md`, `CLAUDE.md`, etc.) at the vault root and on the target path, (3) this skill's generic skill defaults. Use the vault-local file's routing, naming, metadata, README, validation, and version-control rules when they are more specific than this skill. Do not expand this check into a full-vault scan.


## Folder Structure

```
{VAULT}/
├── 00-Inbox/                  # Quick capture, unsorted notes
├── 10-Work/                   # Meeting notes
├── 15-Daily/                  # Daily notes, journals
├── 20-Learning/               # Articles, study notes, web clips
├── 30-Insights/               # Analysis, AI-generated insights
├── 40-Projects/               # Active project context
├── 50-People/                 # Contacts, team notes
├── 90-Archive/                # Completed/inactive items
├── Templates/                 # Note templates (user-edited; the single source of truth)
├── Attachments/               # Images, files
├── .obsidian-kb-backups/      # Auto-backups from the Update workflow (created lazily)
└── INDEX.md                   # Main navigation hub
```

Folder navigation is owned by exactly one index strategy: Folder Index, Dataview, or a static Markdown list. Do not maintain two competing indexes for the same folder. Large folders (e.g. `20-Learning/`) may contain topic-based subfolders; route to the appropriate subfolder if one exists, else use the top-level folder.


## Index Strategy Detection

Run the bundled detector — do **not** read Obsidian's plugin config by hand:

```bash
python <skill-root>/scripts/run_helper.py detect-index <vault> --folder <folder> --json
```

JSON output: `mode` (`folder-index` | `dataview` | `static`), `index_file`, `can_append`, `graph_compatible`, `notes`. Apply:

- **folder-index** / **dataview**: plugin-owned — never append. Honor `graph_compatible`.
- **static**: when `can_append` is true, append a wikilink to `INDEX.md` under a "Recent" section.

**Folder Index graph compatibility (Folder Index 1.0.30):** the plugin connects a parent folder to a child folder in Graph View by looking for `<folder-name>.md`. To get a complete folder hierarchy in the graph, use native folder-named indexes (`indexFileUserSpecified: false`) and keep a separate configured root index. A uniform custom name such as `INDEX.md` can render folder contents but cannot produce nested parent-to-child graph edges in this plugin version — so when the detector reports `graph_compatible: false`, warn the user and recommend migration; never rename indexes silently.


## Note Types and Routing

`create-note --type <slug>` is the canonical write path. The slug → folder mapping is owned by the bundled `process-inbox` helper (`TYPE_TO_FOLDER`); infer the slug from conversation context or ask the user.

Slugs: `daily-note`, `meeting-note`, `learning-note`, `web-clip`, `insight-note`, `conversation-digest`, `project-note`, `person-note`, `task-memory`. Unsure or quick-capture → `00-Inbox/`.

> **Subfolders**: large folders may contain topic-based subfolders; route to the appropriate subfolder if one exists, otherwise the top-level folder.


## Decide First: Create vs Update

Before doing anything, decide whether the request is a **Create** (a new note) or an **Update** (append/edit an existing note). The Task Memory workflow is `core/references/task-memory.md`.

**Update is preferred when:**
- The user names an existing note ("add to my Q3 OKR note", "update Alice's contact")
- The content is an obvious continuation of an existing project (`project-note`), person (`person-note`), or today's daily note
- The user explicitly says "append", "update", "续上", "追加"

**Create is the default** for everything else. If ambiguous, **ask the user once** before writing.


## Note Creation Workflow

The bundled `create_note.py` does steps 1, 2, 3, 4, 5, 7, 8, 9 for you — call it instead of rolling your own. Steps 6 and 10 are agent-side.

### Step 1–2: Resolve & validate vault, determine note type

Run `vault_info.py` to get the vault path + validity + types list. Infer the type slug from the conversation or ask the user.

### Step 3: Read the template (vault template is the truth)

`{VAULT}/Templates/<Name>.md` is the single source of truth at write time. `create_note.py` reads it, fills `{{date}}` placeholders, merges the template's frontmatter into the new note, and uses the template's body as the scaffold. If the user adds a field (e.g. `mood:`) or a new section heading to their template, every new note picks it up automatically — no code change needed.

Conventional template filenames: `Daily Note`, `Meeting Note`, `Learning Note`, `Project Note`, `Web Clip`, `Insight Note`, `Person Note`, `Digest Note`. If the vault has no `Templates/` yet, bootstrap the shipped starters once (`scaffold_templates.py` will NOT clobber later edits unless `--force` is passed):

```bash
python <skill-root>/scripts/run_helper.py scaffold-templates <vault> --apply
```

### Step 4–5: Fill frontmatter & body (delegated)

`create_note.py` merges the user template's frontmatter, the type's safety-net defaults, and explicit CLI overrides. Always set (and never hardcode) `date` to today; always set `type` to the routed slug. If the template doesn't define `tags`, the type's default tag is used.

### Step 6: Wikilinks (use the helper)

Use `[[wikilinks]]` for related existing notes. Do **not** scan the entire vault — the bounded strategy lives in the bundled helper. The helper must list the target folder's filenames to populate link candidates, then scores them by shared tags / matching type / title-token overlap, and caps the result. After writing, pass `--suggest-links` to `create-note` (or call `python <skill-root>/scripts/run_helper.py suggest-links <vault> --note <path>` directly) to get scored, in-scope candidates and their reasons. Just pick from its output (≤ 5 high-confidence links, or skip).

### Step 7: Write the file (delegated)

Prefer your agent's **native file-write tool** when available. If not (some CLI-only agents), call the bundled helper — never invent a one-off script:

```bash
python <skill-root>/scripts/run_helper.py create-note <vault> --type <slug> --title "<Short Title>" \
    --content-file <path-to-body.md> --apply
```

`--stdin` reads the body from standard input; omit `--apply` to preview. The script handles encoding, frontmatter, safe numeric suffix, and the static `INDEX.md` update.

### Step 8: Apply the detected index strategy

`create_note.py` updates a static `INDEX.md` automatically when applicable; Folder Index and Dataview listings are never touched. Never append links to plugin-managed indexes. If this workflow created a new folder in Folder Index mode and its index is missing, write the minimal seed:

````markdown
---
type: folder-index
tags: [moc]
---
```folder-index-content
```
````

### Step 9: Validate Result

`create_note.py` and `update_note.py` run the per-note audit automatically after `--apply` (pass `--no-audit` to skip). Read the `AUDIT:` line and fix any reported issues before continuing. The audit covers: frontmatter validity, required template headings (must appear in the same order as the selected vault template; user-defined additional sections are allowed), broken wikilinks, unresolved placeholders, required web-clip fields, etc.

### Step 10: Confirm to User

Report back:
- Where saved (folder + filename, as an absolute path or `file://` link)
- Brief summary of captured content
- Suggested follow-up actions (e.g. linking to other notes, processing Inbox items)
