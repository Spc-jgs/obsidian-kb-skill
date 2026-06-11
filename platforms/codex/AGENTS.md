# Obsidian Personal Knowledge Base

Instructions for managing the user's Obsidian-based personal knowledge base. Apply these when the user asks to save, record, or capture information to their knowledge base, notes, or Obsidian vault.

## Vault Discovery

Check in order:
1. Environment variable `OBSIDIAN_KB_VAULT` (if set, use as vault path)
2. Config file `~/.obsidian-kb-config` (single line containing the absolute vault path)
3. If neither exists, ask the user and create the config file

## Folder Structure

```
{VAULT}/
├── 00-Inbox/          # Quick capture, unsorted
├── 10-Work/           # Meeting notes, work docs
├── 20-Learning/       # Articles, study notes, web clips
├── 30-Insights/       # Analysis, AI-generated insights
├── 40-Projects/       # Active project context
├── 50-People/         # Contacts, team notes
├── 90-Archive/        # Completed/inactive
├── Templates/         # Note templates
├── Attachments/       # Images, files
└── INDEX.md           # Main navigation hub
```

Each folder (except 90-Archive, Templates, Attachments) has an `INDEX.md` as its table of contents.

## Folder Routing

| Trigger Keywords | Target Folder | Template |
|---|---|---|
| daily, today, diary, journal | `10-Work/` | `Templates/Daily Note.md` |
| meeting, standup, review, sync | `10-Work/` | `Templates/Meeting Note.md` |
| article, learning, book, course, tutorial | `20-Learning/` | `Templates/Learning Note.md` |
| web page, URL, blog post, clip | `20-Learning/` | `Templates/Web Clip.md` |
| analysis, insight, idea, takeaway | `30-Insights/` | `Templates/Insight Note.md` |
| project, milestone, sprint | `40-Projects/` | `Templates/Project Note.md` |
| person, contact, team member | `50-People/` | `Templates/Person Note.md` |
| unsure, quick capture | `00-Inbox/` | None |

> **Subfolders**: Large folders may have topic subfolders (e.g. `20-Learning/Python/`). Route to the appropriate subfolder if one exists.

## Note Creation Workflow

1. Resolve vault path from env var or config file
2. Determine note type from context
3. Read template from `{VAULT}/Templates/`
4. Fill YAML frontmatter: date (current system date — never hardcode), type, tags
5. Fill body content with actual information
6. Use `[[wikilinks]]` for related notes
7. Write file to `{VAULT}/{FOLDER}/YYYY-MM-DD Title.md` (UTF-8, no BOM)
8. Append link to folder's `INDEX.md`
9. Confirm to user

## YAML Frontmatter

All notes require:
```yaml
---
date: "YYYY-MM-DD"
type: note-type-slug
tags: [tag1, tag2]
---
```

Extra fields by type:

| Type | Extra Fields |
|------|-------------|
| `daily-note` | *(base fields only)* |
| `meeting-note` | `participants: []`, `project: ""` |
| `learning-note` | `source: ""`, `category: ""` |
| `web-clip` | `source_url: ""`, `title: ""` |
| `project-note` | `status: active` |
| `insight` | `source_conversation: ""` |
| `person-note` | `role: ""`, `organization: ""` |

Templates use `{{date}}` — replace all with current date (`YYYY-MM-DD`).

## File Naming

`YYYY-MM-DD Short Title.md` — use user's language for title. Never overwrite — if filename exists, add numeric suffix (e.g. `-2`) or ask user.

## Tagging

Standard tags: `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`, `ai-generated`, `todo`.
Domain tags (add as needed): `frontend`, `backend`, `design`, `devops`, `management`, `strategy`.

## Rules

- UTF-8 encoding always (no BOM)
- Use current system date, never hardcode
- Create new notes rather than appending
- Use `[[wikilinks]]` not markdown links
- One topic per note
- Match user's language
- Never overwrite — if filename exists, add numeric suffix (e.g. `-2`) or ask user
- Batch: create separate notes for distinct items, cross-link with `[[wikilinks]]`
- Subfolder INDEX: update both subfolder INDEX and parent folder INDEX

## Error Handling

- **Vault not found**: Offer to create and initialize structure
- **Template missing**: Use base YAML + standard sections; warn user
- **Permission denied**: Report clearly
- **INDEX.md missing**: Create basic one first
- **Filename conflict**: Append `-2` or next available number
