# Note Creation Workflow (reference)

Loaded only when the user asks to save a **new** note. The always-loaded skill body points here. Read this *before* writing.

## When NOT to Use This Skill

Skip this skill (do not save to vault) when:

- The user is asking a question, debugging code, or having casual conversation
- The content is a one-off command/snippet with no lasting value
- The user has not explicitly asked to save, record, or remember
- The information is already in another canonical location (e.g. project README, git history)

Only invoke when there is **explicit save intent** (e.g. "save to Obsidian", "记一下", "沉淀到知识库", "add to my notes") **or** when summarizing a long conversation the user wants archived.


## Vault Discovery

The knowledge base vault location is configured in a platform-specific way. Check these locations in order:

1. Environment variable `OBSIDIAN_KB_VAULT` (if set)
2. Config file `~/.obsidian-kb-config` (single line containing the vault path)
3. If neither exists, ask the user for their vault path and create the config file


## Vault Validation

Before any write, verify the resolved vault path is a real Obsidian vault:

1. Path exists and is a directory
2. `{VAULT}/.obsidian/` directory exists (Obsidian's marker)
3. `{VAULT}/Templates/` directory exists

If any check fails, **stop and report** — do not silently create files in a non-vault directory. Offer to (a) re-prompt the user for the correct path, or (b) initialize a new vault structure at the given location if the user confirms.


## Instruction Precedence

Apply instructions in this order:

1. The user's current request
2. Applicable Vault-local governance files such as `AGENTS.md`, `CLAUDE.md`, or another local instruction file
3. This skill's generic skill defaults

Before writing, read the applicable Vault-local governance file at the vault root and any more-specific file on the target path. Use its routing, naming, metadata, README, validation, and version-control rules when they are more specific than this skill. Do not expand this check into a full-vault scan.


## Folder Structure

```
{VAULT}/
├── 00-Inbox/                  # Quick capture, unsorted notes
├── 10-Work/                   # Meeting notes, work documents
├── 15-Daily/                  # Daily notes, journals, morning plans
├── 20-Learning/               # Articles, study notes, web clips
├── 30-Insights/               # Analysis, AI-generated insights
├── 40-Projects/               # Active project context
├── 50-People/                 # Contacts, team notes
├── 90-Archive/                # Completed/inactive items
├── Templates/                 # Note templates
├── Attachments/               # Images, files
├── .obsidian-kb-backups/      # Auto-backups created by the Update workflow
└── INDEX.md                   # Main navigation hub
```

Folder navigation is owned by exactly one index strategy: Folder Index, Dataview, or a static Markdown list. Do not maintain two competing indexes for the same folder. The `.obsidian-kb-backups/` folder is created lazily on first Update; users can periodically prune it.


## Index Strategy Detection

Run the bundled detector — do **not** read Obsidian's plugin config by hand:

```bash
python scripts/detect_index.py <vault> --folder <folder>
```

It prints JSON: `mode` (`folder-index` | `dataview` | `static`), `index_file`, `can_append` (safe to append a manual link?), `graph_compatible`, and `notes` (filenames in the folder, for link candidates). Apply the result:

- **folder-index** / **dataview**: plugin-owned listings — never append; honor `graph_compatible` (warn the user if structural graph edges are off).
- **static**: when `can_append` is true, append a wikilink to `INDEX.md` under a "Recent" section.

**Folder Index graph compatibility (Folder Index 1.0.30):** the plugin connects a parent folder to a child folder in Graph View by looking for `<folder-name>.md`. To get a complete folder hierarchy in the graph, use native folder-named indexes (`indexFileUserSpecified: false`) and keep a separate configured root index. A uniform custom name such as `INDEX.md` can render folder contents but cannot produce nested parent-to-child graph edges in this plugin version — so when the detector reports `graph_compatible: false`, warn the user and recommend migration; never rename indexes silently.


## Note Types and Routing

| Trigger Pattern | Target Folder | Template |
|---|---|---|
| Daily, today, diary, journal, morning plan | `15-Daily/` | Daily Note |
| Meeting, standup, review, sync | `10-Work/` | Meeting Note |
| Article, learning, book, course, tutorial | `20-Learning/` | Learning Note |
| Web page, URL, blog post, clip | `20-Learning/` | Web Clip |
| Analysis, insight, idea, takeaway | `30-Insights/` | Insight Note |
| Summarize conversation, chat digest, 沉淀对话 | `30-Insights/` | Digest Note |
| Project, milestone, sprint | `40-Projects/` | Project Note |
| Person, contact, team member | `50-People/` | Person Note |
| Unsure / quick capture | `00-Inbox/` | None |

> **Subfolders**: Large folders (e.g. `20-Learning/`) may contain topic-based subfolders like `20-Learning/Python/` or `20-Learning/AI-Agent/`. When saving, route to the appropriate subfolder if one exists; otherwise use the top-level folder.


## Decide First: Create vs Update

Before doing anything, decide whether the request is a **Create** (a new note) or an **Update** (append/edit an existing note).

**Update is preferred when:**
- The user names an existing note ("add to my Q3 OKR note", "update Alice's contact")
- The content is an obvious continuation of an existing project (`project-note`), person (`person-note`), or today's daily note
- The user explicitly says "append", "update", "续上", "追加"

**Create is the default** for everything else.

If ambiguous, **ask the user once** ("Create a new note or append to `<best-candidate>`?") before writing.


## Note Creation Workflow

### Step 1: Resolve & Validate Vault Path

Check env var `OBSIDIAN_KB_VAULT`, then `~/.obsidian-kb-config`, then ask the user. Then run the Vault Validation checks above.

### Step 2: Determine Note Type

Infer from conversation context or ask the user. Map to the routing table above.

### Step 3: Read the Template

Templates are stored in `{VAULT}/Templates/`. Each template has:
- YAML frontmatter with metadata fields
- Section headings for structured content

Available templates:
- `Templates/Daily Note.md`
- `Templates/Meeting Note.md`
- `Templates/Learning Note.md`
- `Templates/Project Note.md`
- `Templates/Web Clip.md`
- `Templates/Insight Note.md`
- `Templates/Person Note.md`
- `Templates/Digest Note.md`

### Step 4: Fill YAML Frontmatter

Always include `date` (use current system date — **never hardcode**), `type`, `tags`. Add type-specific extra fields as defined in the YAML Frontmatter Standards below. Replace **all** `{{date}}` placeholders with today's date in `YYYY-MM-DD` format.

### Step 5: Fill Body Content

Write the actual content into the template sections. Be thorough but concise.

### Step 6: Add Wikilinks (Bounded Search)

Use `[[wikilinks]]` to link related existing notes — but do **not** scan the entire vault. Follow this cheap-first bounded strategy:

1. Use the Vault-local routing rules to identify likely topic folders
2. Read the target folder's detected index and inspect its manual navigation (cost: 1 file read)
3. **Always list the target folder's filenames** when the index uses a generated Folder Index or Dataview block, because generated members are not present in raw Markdown
4. Pick **at most 1–3 target-folder candidates** and read only their first ~20 lines to confirm relevance
5. Only if no high-confidence target-folder match exists, inspect the parent index's manual topic guidance and list filenames in **at most 1–2** high-relevance sibling folders
6. Insert **at most 5 wikilinks** per note, only for high-confidence matches

Stop when the total file-scan cap is reached. If nothing obvious turns up after the cheap passes, **skip wikilinks** — do not escalate to a full-text vault scan. An empty `related: []` is valid.

### Step 7: Write the File

Save to `{VAULT}/{FOLDER}/YYYY-MM-DD Short Title.md` with **UTF-8 encoding** (no BOM). If the filename already exists, add a numeric suffix (e.g. `-2`) or ask the user — **never overwrite**.

**How to perform the write (tool choice)**:
- Prefer your agent's **native file-write tool** when the environment provides one.
- If the environment has **no native note-writing tool** (some CLI-only agents), do **not** invent a one-off Python/shell script to do the file I/O. Call the bundled helper instead:

  ```bash
  python scripts/create_note.py <vault> --type <type> --title "<Short Title>" \
      --content-file <path-to-body.md> --apply
  ```

  `create_note.py` builds the frontmatter (with the type's required fields), picks the routed folder, writes with a safe numeric suffix, and updates a static `INDEX.md` when applicable — so encoding, frontmatter, and index rules stay consistent across agents. Pass `--stdin` instead of `--content-file` to read the body from standard input, or omit `--apply` to preview without writing.

### Step 8: Apply the Detected Index Strategy

Use the strategy detected before writing:

1. **Folder Index mode**: do not edit an existing index. If this workflow created a new folder and its configured index is missing, create only the minimal `folder-index-content` file:

   ````markdown
   ---
   type: folder-index
   tags: [moc]
   ---
   ```folder-index-content
   ```
   ````

2. **Dataview mode**: do not edit the index or its query.
3. **Static mode**: append a link under the "Recent Notes" / "Recent Insights" section:

   ```markdown
   - [[YYYY-MM-DD Short Title|Short Title]] (YYYY-MM-DD)
   ```

If the folder has subfolders (e.g. `20-Learning/Python/`), detect the strategy independently for the subfolder and parent. Never append links to plugin-managed indexes.

### Step 9: Validate Result

Re-read the written note and any index changed by this invocation before confirmation, commit, or push. Verify all of the following:

- The final path, filename, UTF-8 encoding, and selected template are correct
- All required template headings exist in the same order as the selected Vault template; additional user-defined sections are allowed
- YAML parses and contains the required `date`, `type`, and non-empty `tags`
- `type` is supported; tags use lowercase kebab-case and total no more than 5
- No template placeholders such as `{{date}}` remain
- Wikilinks stay within the cap and represent high-confidence relationships
- Folder Index and Dataview listings were not manually extended
- A newly created `folder-index` note contains exactly one `folder-index-content` block
- In Folder Index mode, every configured index from the target folder up to the root exists, and native folder-named indexes are used when Graph overwrite is expected to provide the hierarchy

If a reusable Vault auditor is available, run it in strict/read-only mode in addition to these target-file checks. Fix validation failures before continuing. Do not report success for an invalid note.

### Step 10: Confirm to User

Report back:
- Where saved (folder + filename, as an absolute path or `file://` link)
- Brief summary of captured content
- Suggested follow-up actions (e.g. linking to other notes, processing Inbox items)
