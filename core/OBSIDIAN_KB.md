# Obsidian Personal Knowledge Base — Universal Instructions

> **Version**: 1.7.0
>
> **Source of truth**: This file (`core/OBSIDIAN_KB.md`) is the single source of truth for the standard Agent Skill and all compatibility adapters. Each generated artifact combines its explicit `header.md` with this body (starting from "## Overview"). **Do not edit generated files directly — edit this file or the relevant header and re-run `python build.py`.**

## Overview

This document provides instructions for AI coding agents to create, organize, and manage notes in an Obsidian-based personal knowledge base. It is agent-agnostic and works with any AI tool that can read/write local files.

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

Detect the vault's index strategy before creating or updating a note:

1. Read `.obsidian/community-plugins.json`. If `obsidian-folder-index` is enabled, use **Folder Index mode**.
2. Otherwise, inspect the target folder's index file. If it contains a `dataview` or `dataviewjs` block, use **Dataview mode**.
3. Otherwise, use **Static mode**.

### Folder Index mode

- Read `.obsidian/plugins/obsidian-folder-index/data.json` when available.
- If `indexFileUserSpecified` is `true`, the folder index is `{indexFilename}.md` inside each folder. Otherwise, it is named after the folder. The root index uses `rootIndexFile`.
- **Graph compatibility:** Folder Index 1.0.30 looks for `<folder-name>.md` when it connects a parent folder to a child folder in Graph View. When complete folder hierarchy edges are required, use native folder-named indexes (`indexFileUserSpecified: false`) and keep a separate configured root index. A uniform custom name such as `INDEX.md` can render folder contents but cannot produce nested parent-to-child graph edges in this plugin version.
- If `graphOverwrite` is `false`, keep using Folder Index mode but tell the user that structural folder edges are not enabled in Graph View. Suggest enabling the setting; do not silently modify plugin configuration.
- If `graphOverwrite` is `true` and `indexFileUserSpecified` is `true`, do not claim that the structural graph is complete. Report the incompatible configuration and recommend a coordinated migration; never rename existing indexes silently during a capture request.
- Treat the plugin-generated index and its `folder-index-content` block as plugin-owned. Never append note links to it.
- When the agent creates a new folder while Obsidian may be closed, create the missing index file with the configured name and this minimal body so the folder is immediately usable:

  ````markdown
  ---
  type: folder-index
  tags: [moc]
  ---
  ```folder-index-content
  ```
  ````

- Folder Index provides structural folder-to-note relationships. It does not replace semantic links between related ideas.

### Dataview mode

- Treat the query block as the generated listing and do not append links.
- Remember that rendered Dataview links are views, not persistent semantic relationships in note content.

### Static mode

- Append a Markdown wikilink to the existing folder index only when neither plugin-managed mode is active.
- Use `INDEX.md` as the conventional fallback filename.

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

### Step 8: Apply the Detected Index Strategy

Use the strategy detected before writing:

1. **Folder Index mode**: do not edit an existing index. If this workflow created a new folder and its configured index is missing, create only the minimal `folder-index-content` file described above.
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

## Conversation Digest Workflow

Use this to archive a long conversation as durable, linkable knowledge (triggers: "沉淀这段对话", "summarize this chat", "把对话存成笔记"). A digest is a curated summary — **not** a transcript.

### When to use
- The conversation produced decisions, trade-offs, or action items worth keeping.
- The user explicitly asks to save or summarize the discussion.

### Session wrap-up (会话收尾)
The agent should proactively offer — or directly produce — a conversation digest when the user signals the **end of a session**, without requiring an exact command. Recognize wrap-up intent from cues such as: "结束", "收尾", "总结一下", "沉淀本次对话", "把对话记下来", "做个摘要", or any message that clearly closes the work. On detecting it:
- Run the **Steps** below (validate vault → conversation-digest template → fill frontmatter → distill → bounded wikilinks → write + index + validate).
- Route per **Routing** above (active project → `40-Projects/`, otherwise `30-Insights/`).
- Self-verify with `obsidian-audit-vault <vault>` and confirm the new note produces **zero findings** before reporting done.
- If an explicit digest was already produced on request earlier in the session, do not duplicate it.

This turns digest creation into a natural session close rather than a separate manual step.

### Routing
- Conversation about a specific active project → `40-Projects/` (file under the project folder, or a Digest Note there).
- Otherwise → `30-Insights/` with the Digest Note template.
- One digest per coherent topic. Split only when topics are independent; without confirmation, write one aggregate digest and suggest later extraction.

### Steps
1. Resolve & validate the vault (same as Note Creation).
2. Set `type: conversation-digest` and use the Digest Note template.
3. Fill frontmatter: `date` (today), `type: conversation-digest`, `tags`, `source` (the counterpart or agent, e.g. "WorkBuddy"), `related: []`.
4. Distill into the template sections — background, confirmed conclusions, rejected/revised ideas, follow-up tasks, related projects, open questions. Capture decisions, not raw chatter.
5. Add wikilinks with the bounded-search rules from Note Creation Step 6.
6. Write the file, apply the detected index strategy, and validate (same checks as Note Creation Step 9).

> Rule of thumb: if a future agent (or you) could not act on it, it does not belong in the digest.

## Update Existing Note Workflow

When the user wants to append to or edit an existing note (project, person, daily, etc.):

### Step 1: Resolve & Validate Vault Path

Same as Create workflow.

### Step 2: Locate the Target Note

1. If the user named the file, resolve its path directly
2. Otherwise, read the relevant folder's detected index file and pick the best match
3. If multiple candidates exist, **ask the user** which one — do not guess

### Step 3: Read the Existing Note in Full

Always read the complete file before editing. Note the YAML frontmatter, section headings, and current content.

### Step 4: Decide the Insertion Point

Match the new content to the most appropriate section:
- `project-note`: append to `## Updates` / `## Decisions` / `## Tasks` as appropriate
- `person-note`: append to `## Interactions` (newest first or chronological — match existing style)
- `daily-note`: append to the time-block section matching the current time
- If no obvious section exists, append a new `## YYYY-MM-DD Update` subsection at the end

### Step 5: Backup, Then Apply the Edit

1. **Always back up first.** Copy the original file (as bytes — preserve content exactly) to:
   ```
   {VAULT}/.obsidian-kb-backups/YYYY-MM-DD-HHMMSS/{original-relative-path}
   ```
   Example: editing `40-Projects/2026-Q3-OKR.md` at 14:32:07 creates `{VAULT}/.obsidian-kb-backups/2026-06-11-143207/40-Projects/2026-Q3-OKR.md`. The folder structure under the timestamp mirrors the vault so multiple files in one session stay organized. Create parent directories as needed.
2. **Preserve** YAML frontmatter (only bump `updated:` field if present)
3. **Insert** new content at the chosen point — do not rewrite unrelated sections
4. Re-emit the file with **UTF-8 (no BOM)** encoding
5. If the edit removes or rewrites more than a few lines, ask the user to confirm first
6. **Tell the user** where the backup landed so they can roll back manually if needed

### Step 6: Refresh a Static Index (Only If Needed)

Skip index changes in Folder Index and Dataview modes. In Static mode, update an index line only if the note's title, date, or summary blurb changed.

### Step 7: Validate Result

Re-read the updated note and any changed static index. Apply the same metadata, placeholder, wikilink, index-ownership, and encoding checks from Create Step 9. If a reusable Vault auditor is available, run it in strict/read-only mode. Fix validation failures before reporting or performing version-control actions.

### Step 8: Report Diff Summary

Tell the user:
- Which file was edited (full path)
- Which section(s) received new content
- A 1–2 sentence summary of what was added

## Optional Git Post-Processing

Git is not a default part of note capture. Run it only when the user explicitly requests it or applicable Vault-local governance requires it.

### Pre-write Git synchronization

When Git is required, perform this before Create Step 1 or Update Step 1:

1. Inspect the worktree. If unrelated changes exist, stop and report them.
2. Fetch the tracked remote branch without modifying files.
3. If the worktree is clean and local is only behind, run `git merge --ff-only <remote>/<branch>`.
4. If local is already current or only ahead, continue.
5. If histories are diverged or `merge --ff-only` fails, stop and report. Do not create a local commit first and then auto-merge remote work.

### Post-write Git publication

1. Complete post-write validation first.
2. Inspect the worktree and stage only files created or changed by this invocation. Never include unrelated user changes.
3. Commit, then fetch the remote branch again and compare local and remote history.
4. **Stop on divergence or conflict.** Report the state instead of merging, rebasing, or choosing a conflict side automatically.
5. **Never auto-resolve INDEX conflicts.** In particular, never replace a Folder Index `folder-index-content` block with a manual note list to make a merge pass.
6. Push only when the remote is not ahead and histories are not diverged.

## YAML Frontmatter Standards

All notes must have:

```yaml
---
date: "YYYY-MM-DD"
type: note-type-slug
tags: [tag1, tag2]
---
```

Additional fields by type:

| Type | Extra Fields |
|------|-------------|
| `daily-note` | `related: []` |
| `meeting-note` | `participants: []`, `project: ""`, `related: []` |
| `learning-note` | `source: ""`, `category: ""`, `related: []` |
| `web-clip` | `source: ""`, `author: ""`, `published: ""`, `related: []` |
| `project-note` | `status: active`, `updated: "YYYY-MM-DD"`, `related: []` |
| `insight-note` | `source: ""`, `related: []` |
| `person-note` | `role: ""`, `organization: ""`, `updated: "YYYY-MM-DD"`, `related: []` |
| `conversation-digest` | `source: ""`, `related: []` |

For a `web-clip`, `source` stores the canonical source URL only. Keep the article title in the note heading and source-information section; use `author` and `published` for their respective values. For non-web notes, `source` may be a concise source description when no canonical URL exists.

Store semantic relationships in `related` as quoted Obsidian links, for example:

```yaml
related:
  - "[[Existing Note|Display Name]]"
```

Do not add a weak link only to satisfy a quota. Folder Index already supplies structural folder relationships; `related` is for high-confidence conceptual relationships.

The `related` property is the machine-readable source of truth for semantic relationships. A body section may repeat the same wikilink only when it adds a short explanation of why the notes are related. Do not duplicate `related` as an identical bare link list.

### Template Placeholders

Templates use `{{date}}` as a placeholder. When creating a note from a template, replace **all** `{{date}}` occurrences with the current date in `YYYY-MM-DD` format. Never leave `{{date}}` in the final note.

## Tag Hygiene

To keep the tag taxonomy from sprawling:

1. **Reuse existing tags first.** Before inventing a new tag, scan the 5 most recent notes in the target folder (read their YAML `tags:` field) and prefer an existing tag if one fits.
2. **kebab-case only.** All tags must be lowercase, hyphen-separated. No spaces, no camelCase, no underscores. Examples: `ai-agent`, `frontend`, `q3-okr`.
3. **No near-duplicates.** Do not introduce `ai-agents` if `ai-agent` exists. Do not introduce `frontEnd` or `front_end` if `frontend` exists.
4. **Max 5 tags per note.** Pick the most specific ones; drop generic catch-alls like `note` or `misc`.
5. **Standard tags** (always available): `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`, `ai-generated`, `todo`.

## Cost Limits (Per Invocation)

To prevent runaway token usage on a single save request, respect these caps:

| Operation | Hard Cap |
|---|---|
| Files scanned (directory listing or read) | 10 |
| Content notes read in full | 3 |
| Notes written or edited | 1 (the target note) |
| Index files updated | 2 (Static mode only: target folder + parent if subfolder) |
| Wikilinks inserted per note | 5 |

Short control-plane files — Vault-local governance, templates, plugin manifests, and plugin configuration — still count toward the 10-file scan cap, but do not count as content notes read in full. INDEX files and existing notes are content files. Reading only the first ~20 lines of a candidate note is a small read, not a full read.

If a task genuinely needs to exceed these caps (e.g. bulk import of 20 notes), **ask the user first** and proceed only on explicit confirmation.

## Important Rules

1. **UTF-8 encoding** for all file writes (no BOM)
2. **Use current date** (from system), never hardcode
3. **Decide Create vs Update first** — use the Update Existing Note Workflow when appropriate; do not always create new notes
4. **Use `[[wikilinks]]`** for internal links (not markdown links) — and respect the bounded-search caps in Step 6
5. **One topic per note** — keep notes focused
6. **Match user's language** — write in whatever language the user uses
7. **Never overwrite** — if filename exists, add a numeric suffix (e.g. `-2`, `-3`) or ask user
8. **Validate the vault** before writing — refuse to write to a path that is not a real Obsidian vault
9. **Validate the result** after writing — re-read the target and fix metadata, placeholder, link, or index violations before reporting success
10. **Respect cost limits** — do not scan the entire vault for a single save
11. **One index owner** — let Folder Index or Dataview own generated listings; update subfolder and parent indexes only in Static mode
12. **Bounded capture** — Default to one target note per invocation. Multiple solutions inside one source can stay in one focused note. If the source contains multiple independently reusable topics, ask the user before creating multiple notes; without confirmation, create one aggregate note and suggest later extraction.

## Error Handling

When things go wrong, follow these guidelines:

- **Vault not found / not an Obsidian vault**: Stop and report. Offer to (a) re-prompt for the correct path, or (b) initialize a new vault structure (folders + templates + INDEX) at the given location with explicit user confirmation.
- **Template missing**: Create the note using the base YAML frontmatter and standard sections. Warn the user that the template was missing and suggest re-running the installer.
- **Permission denied**: Report the error clearly and suggest checking file/directory permissions.
- **Index missing**: In Folder Index mode, create the configured minimal folder index; in Dataview mode, report the missing query page; in Static mode, create a basic `INDEX.md` before appending.
- **Filename conflict**: Append `-2` (or next available number). Inform the user of the actual filename used.
- **Encoding issues**: Always write files as UTF-8 without BOM. If the platform has encoding quirks (e.g. PowerShell 5.1), use appropriate workarounds (`[System.IO.File]::WriteAllText` with `UTF8Encoding $false`).
- **Cost cap hit**: Stop scanning, write the note with whatever wikilinks were already found, and note the truncation in the user-facing summary.
- **Post-write validation failed**: Do not confirm, commit, or push. Correct only the files from the current invocation, re-run validation, and report the unresolved finding if it cannot be fixed safely.
- **Git divergence or conflict**: Stop and report the branch state. Do not merge, rebase, or resolve INDEX content automatically.
