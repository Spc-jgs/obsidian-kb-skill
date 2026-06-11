# Obsidian Personal Knowledge Base

You have access to the user's Obsidian personal knowledge base. Use these instructions whenever the user wants to save, record, or capture information to their knowledge base (Obsidian / vault / notes).

## Vault Discovery

Check in order:
1. Environment variable `OBSIDIAN_KB_VAULT` (if set, use as vault path)
2. Config file `~/.obsidian-kb-config` (single line containing the absolute vault path)
3. If neither exists, ask the user for their vault path and create the config file

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
| daily, today, diary, journal, morning plan | `10-Work/` | `Templates/Daily Note.md` |
| meeting, standup, review, sync | `10-Work/` | `Templates/Meeting Note.md` |
| article, learning, book, course, tutorial | `20-Learning/` | `Templates/Learning Note.md` |
| web page, URL, blog post, clip | `20-Learning/` | `Templates/Web Clip.md` |
| analysis, insight, idea, takeaway | `30-Insights/` | `Templates/Insight Note.md` |
| project, milestone, sprint | `40-Projects/` | `Templates/Project Note.md` |
| person, contact, team member | `50-People/` | `Templates/Person Note.md` |
| unsure, quick capture | `00-Inbox/` | None |

> **Subfolders**: Large folders (e.g. `20-Learning/`) may have topic subfolders like `20-Learning/Python/`. Route to the appropriate subfolder if one exists.

## Note Creation Workflow

1. **Resolve vault path** from env var `OBSIDIAN_KB_VAULT` or `~/.obsidian-kb-config`
2. **Determine note type** from conversation context
3. **Read the template** from `{VAULT}/Templates/`
4. **Fill YAML frontmatter**: always include `date` (today's date), `type`, `tags`
5. **Fill body content** with the actual information
6. **Use `[[wikilinks]]`** to link to related existing notes
7. **Write the file**: `{VAULT}/{FOLDER}/YYYY-MM-DD Short Title.md` (UTF-8 encoding)
8. **Update folder INDEX**: append `- [[filename|title]] (date)` to the folder's `INDEX.md`
9. **Confirm** to the user: where saved, what was captured, any follow-up suggestions

## YAML Frontmatter

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

Templates use `{{date}}` — replace all occurrences with current date (`YYYY-MM-DD`). Never leave `{{date}}` in the final note.

## File Naming

Format: `YYYY-MM-DD Short Title.md`
Use the user's language for the title part. Never overwrite — if filename exists, add a numeric suffix (e.g. `-2`) or ask the user.

## Tagging

Standard tags: `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`, `ai-generated`, `todo`.
Domain tags (add as needed): `frontend`, `backend`, `design`, `devops`, `management`, `strategy`.

## Rules

- Always use UTF-8 encoding (no BOM)
- Use current system date, never hardcode a date
- Prefer creating new notes over appending to existing ones
- Use `[[wikilinks]]` for internal links, not markdown links
- One topic per note — keep notes focused
- Write in the user's language
- When a conversation contains multiple distinct knowledge items, create separate notes and cross-link them with `[[wikilinks]]`
- Subfolder INDEX: when a note goes into a subfolder, update both subfolder INDEX and parent folder INDEX

## Error Handling

- **Vault not found**: Offer to create it and initialize the folder structure
- **Template missing**: Use base YAML frontmatter + standard sections; warn the user
- **Permission denied**: Report clearly, suggest checking file permissions
- **INDEX.md missing**: Create a basic one before appending the note link
- **Filename conflict**: Append `-2` (or next number), inform user of actual filename
