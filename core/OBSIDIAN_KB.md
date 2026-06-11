# Obsidian Personal Knowledge Base — Universal Instructions

## Overview

This document provides instructions for AI coding agents to create, organize, and manage notes in an Obsidian-based personal knowledge base. It is agent-agnostic and works with any AI tool that can read/write local files.

## Vault Discovery

The knowledge base vault location is configured in a platform-specific way. Check these locations in order:

1. Environment variable `OBSIDIAN_KB_VAULT` (if set)
2. Config file `~/.obsidian-kb-config` (single line containing the vault path)
3. If neither exists, ask the user for their vault path and create the config file

> **Version**: 1.0.0

## Folder Structure

```
{VAULT}/
├── 00-Inbox/          # Quick capture, unsorted notes
├── 10-Work/           # Meeting notes, work documents
├── 20-Learning/       # Articles, study notes, web clips
├── 30-Insights/       # Analysis, AI-generated insights
├── 40-Projects/       # Active project context
├── 50-People/         # Contacts, team notes
├── 90-Archive/        # Completed/inactive items
├── Templates/         # Note templates
├── Attachments/       # Images, files
└── INDEX.md           # Main navigation hub
```

Each folder (except 90-Archive, Templates, Attachments) has an `INDEX.md` that serves as its table of contents.

## Note Types and Routing

| Trigger Pattern | Target Folder | Template |
|---|---|---|
| Daily, today, diary, journal, morning plan | `10-Work/` | Daily Note |
| Meeting, standup, review, sync | `10-Work/` | Meeting Note |
| Article, learning, book, course, tutorial | `20-Learning/` | Learning Note |
| Web page, URL, blog post, clip | `20-Learning/` | Web Clip |
| Analysis, insight, idea, takeaway | `30-Insights/` | Insight Note |
| Project, milestone, sprint | `40-Projects/` | Project Note |
| Person, contact, team member | `50-People/` | Person Note |
| Unsure / quick capture | `00-Inbox/` | None |

> **Subfolders**: Large folders (e.g. `20-Learning/`) may contain topic-based subfolders like `20-Learning/Python/` or `20-Learning/AI-Agent/`. When saving, route to the appropriate subfolder if one exists; otherwise use the top-level folder.

## Note Creation Workflow

### Step 1: Resolve Vault Path

Check env var `OBSIDIAN_KB_VAULT`, then `~/.obsidian-kb-config`, then ask the user.

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

### Step 4: Fill YAML Frontmatter

Always include `date` (use current system date — **never hardcode**), `type`, `tags`. Add type-specific extra fields as defined in the YAML Frontmatter Standards below.

### Step 5: Fill Body Content

Write the actual content into the template sections. Be thorough but concise.

### Step 6: Add Wikilinks

Use `[[wikilinks]]` to link to related existing notes. Scan the vault for related content before writing.

### Step 7: Write the File

Save to `{VAULT}/{FOLDER}/YYYY-MM-DD Short Title.md` with **UTF-8 encoding** (no BOM). If the filename already exists, add a numeric suffix (e.g. `-2`) or ask the user — **never overwrite**.

### Step 8: Update Folder INDEX

After creating a note, append a link in the folder's `INDEX.md`:

```markdown
- [[YYYY-MM-DD Short Title|Short Title]] (YYYY-MM-DD)
```

Insert under the "Recent Notes" / "Recent Insights" section, replacing any placeholder text. If the folder has subfolders (e.g. `20-Learning/Python/`), also update the subfolder's INDEX.md and then the parent folder's INDEX.md.

### Step 9: Confirm to User

Report back:
- Where saved (folder + filename)
- Brief summary of captured content
- Suggested follow-up actions (e.g. linking to other notes, processing Inbox items)

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
| `daily-note` | *(base fields only)* |
| `meeting-note` | `participants: []`, `project: ""` |
| `learning-note` | `source: ""`, `category: ""` |
| `web-clip` | `source_url: ""`, `title: ""` |
| `project-note` | `status: active` |
| `insight` | `source_conversation: ""` |
| `person-note` | `role: ""`, `organization: ""` |

### Template Placeholders

Templates use `{{date}}` as a placeholder. When creating a note from a template, replace **all** `{{date}}` occurrences with the current date in `YYYY-MM-DD` format. Never leave `{{date}}` in the final note.

## Tagging Conventions

Standard tags (always available):
- `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`
- `ai-generated` — content from AI conversations
- `todo` — items needing action

Domain tags (add as needed):
- `frontend`, `backend`, `design`, `devops`, `management`, `strategy`, etc.

## Important Rules

1. **UTF-8 encoding** for all file writes (no BOM)
2. **Use current date** (from system), never hardcode
3. **Create new notes** rather than appending (unless explicitly updating)
4. **Use `[[wikilinks]]`** for internal links (not markdown links)
5. **One topic per note** — keep notes focused
6. **Match user's language** — write in whatever language the user uses
7. **Never overwrite** — if filename exists, add a numeric suffix (e.g. `-2`, `-3`) or ask user
8. **Batch capture** — when a conversation has multiple distinct knowledge items, create separate notes and cross-link them
9. **Subfolder INDEX** — when a note goes into a subfolder (e.g. `20-Learning/Python/`), update both the subfolder INDEX and the parent folder INDEX

## Error Handling

When things go wrong, follow these guidelines:

- **Vault not found**: If the vault path doesn't exist, offer to create it and initialize the full folder structure.
- **Template missing**: If a template file doesn't exist, create the note using the base YAML frontmatter and standard sections. Warn the user that the template was missing.
- **Permission denied**: Report the error clearly and suggest checking file/directory permissions.
- **INDEX.md missing**: Create a basic INDEX.md for the folder before appending the note link.
- **Filename conflict**: If the target filename already exists, append `-2` (or next available number). Inform the user of the actual filename used.
- **Encoding issues**: Always write files as UTF-8 without BOM. If the platform has encoding quirks (e.g. PowerShell 5.1), use appropriate workarounds.
