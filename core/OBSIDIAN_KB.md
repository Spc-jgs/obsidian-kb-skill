# Obsidian Personal Knowledge Base — Universal Instructions

## Overview

This document provides instructions for AI coding agents to create, organize, and manage notes in an Obsidian-based personal knowledge base. It is agent-agnostic and works with any AI tool that can read/write local files.

## Vault Discovery

The knowledge base vault location is configured in a platform-specific way. Check these locations in order:

1. Environment variable `OBSIDIAN_KB_VAULT` (if set)
2. Config file `~/.obsidian-kb-config` (single line containing the vault path)
3. If neither exists, ask the user for their vault path and create the config file

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
| Meeting, standup, review, sync | `10-Work/` | Meeting Note |
| Article, learning, book, course, tutorial | `20-Learning/` | Learning Note |
| Web page, URL, blog post, clip | `20-Learning/` | Web Clip |
| Analysis, insight, idea, takeaway | `30-Insights/` | Insight Note |
| Project, milestone, sprint | `40-Projects/` | Project Note |
| Person, contact, team member | `50-People/` | Person Note |
| Unsure / quick capture | `00-Inbox/` | None |

## Note Creation Workflow

### Step 1: Determine Note Type

Infer from conversation context or ask the user. Map to the table above.

### Step 2: Read the Template

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

### Step 3: Create the Note

1. Fill in the YAML frontmatter (always include `date`, `type`, `tags`)
2. Fill in the body with actual content
3. Use `[[wikilinks]]` to link to related existing notes
4. Write the file with UTF-8 encoding

### Step 4: File Naming

Format: `YYYY-MM-DD Short Title.md`

Examples:
- `2026-06-09 Microservice Architecture Notes.md`
- `2026-06-09 Q2 Product Review Meeting.md`
- `2026-06-09 Knowledge Management Insight.md`

Use the user's language for the title (Chinese filename if user speaks Chinese).

### Step 5: Update Folder Index

After creating a note, append a link in the folder's `INDEX.md`:

```markdown
- [[YYYY-MM-DD Short Title|Short Title]] (YYYY-MM-DD)
```

Insert under the "Recent Notes" / "Recent Insights" section, replacing any placeholder text.

### Step 6: Confirm to User

Report back:
- Where saved (folder + filename)
- Brief summary of captured content
- Suggested follow-up actions

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
| `meeting-note` | `participants: []`, `project: ""` |
| `learning-note` | `source: ""`, `category: ""` |
| `web-clip` | `source_url: ""`, `title: ""` |
| `project-note` | `status: active` |
| `insight` | `source_conversation: ""` |
| `person-note` | `role: ""`, `organization: ""` |

## Tagging Conventions

Standard tags (always available):
- `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`
- `ai-generated` — content from AI conversations
- `todo` — items needing action

Domain tags (add as needed):
- `frontend`, `backend`, `design`, `devops`, `management`, `strategy`, etc.

## Important Rules

1. **UTF-8 encoding** for all file writes
2. **Use current date** (from system), never hardcode
3. **Create new notes** rather than appending (unless explicitly updating)
4. **Use `[[wikilinks]]`** for internal links (not markdown links)
5. **One topic per note** — keep notes focused
6. **Match user's language** — write in whatever language the user uses
7. **Never overwrite** — if filename exists, add a suffix or ask user
8. **Batch capture** — when a conversation has multiple distinct knowledge items, create separate notes and cross-link them
