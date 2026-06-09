# Obsidian Knowledge Base Skill

**Turn any AI coding agent into your personal knowledge management assistant.**

A cross-platform skill that teaches AI agents (QoderWork, Claude Code, OpenAI Codex, Cursor) how to create, organize, and interlink notes in your [Obsidian](https://obsidian.md) vault — automatically.

---

## The Problem

We talk to AI assistants every day — brainstorming ideas, analyzing articles, reviewing meetings, debugging problems. These conversations produce genuinely valuable knowledge, but it almost always evaporates the moment you close the chat window.

Manually copying insights into a note-taking app is tedious and inconsistent. The friction is too high: you need to decide where to put it, how to format it, what tags to use, and how it connects to existing notes. So most of the time, you just... don't.

## The Solution

This skill eliminates that friction by teaching your AI agent a complete knowledge management workflow. You just say things like *"save this to my knowledge base"* or *"record this meeting"*, and the agent handles everything:

- Picks the right note type and template
- Fills in structured metadata (date, tags, source)
- Writes to the correct folder in your Obsidian vault
- Updates the folder index
- Cross-links related notes with `[[wikilinks]]`

Your knowledge accumulates automatically, in a structured format that scales from 10 notes to 10,000.

## How It Works

```
You: "Save the key insights from our microservices discussion"

AI Agent:
  1. Reads vault path from ~/.obsidian-kb-config
  2. Reads the "Insight Note" template from your vault
  3. Fills in YAML frontmatter + analysis content
  4. Writes to 30-Insights/2026-06-09 微服务架构洞察.md
  5. Appends link to 30-Insights/INDEX.md
  6. Confirms: "Saved to 30-Insights/2026-06-09 微服务架构洞察.md"
```

The skill is **just a Markdown instruction file** that teaches the agent the conventions. No plugins, no APIs, no servers — your Obsidian vault is a folder of Markdown files, and the agent reads and writes them directly.

## Supported Platforms

| Platform | Config File | Install Location |
|----------|------------|-----------------|
| **QoderWork / Qoder CLI** | `SKILL.md` | `~/.qoderwork/skills/obsidian-knowledge-base/` |
| **Claude Code** | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **OpenAI Codex** | `AGENTS.md` | `~/AGENTS.md` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

All four platform files contain **identical instructions** — same folder routing, same templates, same YAML conventions, same tagging conventions. Only the file format differs to match each platform's convention.

## Quick Start

### 1. Configure your vault path

```bash
cp .env.example .env
```

Edit `.env` with your vault path:

```env
OBSIDIAN_KB_VAULT=D:\MyKnowledgeBase
```

### 2. Run the installer

**Windows (PowerShell):**
```powershell
.\install.ps1
```

**macOS / Linux:**
```bash
chmod +x install.sh
./install.sh
```

That's it. The installer will:

- Create the vault folder structure (if it doesn't exist)
- Copy 7 note templates into your vault
- Create INDEX.md navigation files in each folder
- Write your vault path to `~/.obsidian-kb-config`
- Install the skill file to your chosen AI platform

### 3. Open in Obsidian

Open your vault folder in Obsidian. You'll see the folder structure, templates, and index pages ready to go.

### 4. Start capturing

Tell your AI assistant:

- *"Save this discussion about system design to my knowledge base"*
- *"Record the Q2 planning meeting"*
- *"Clip this article: https://example.com/article"*
- *"Create a project note for the dashboard redesign"*

## Vault Structure

```
YourVault/
├── 00-Inbox/          Quick capture — drop anything here, sort later
├── 10-Work/           Meeting notes, work documents, team discussions
├── 20-Learning/       Articles, study notes, web clips, course materials
├── 30-Insights/       Analysis, ideas, AI-generated insights
├── 40-Projects/       Active project context and progress logs
├── 50-People/         Contacts, team members, interaction logs
├── 90-Archive/        Completed or inactive items
├── Templates/         7 pre-built note templates
├── Attachments/       Images and file attachments
└── INDEX.md           Main navigation hub (Map of Content)
```

## Note Templates

| Template | Use Case | Key Fields |
|----------|----------|------------|
| **Daily Note** | Journaling, daily planning | Today's focus, tasks, reflections |
| **Meeting Note** | Meetings, standups, reviews | Participants, agenda, action items, decisions |
| **Learning Note** | Articles, books, courses | Source, key takeaways, connections to work |
| **Web Clip** | Web pages, blog posts | URL, highlights, key quotes |
| **Insight Note** | Analysis, ideas, AI conversations | One-line insight, context, implications |
| **Project Note** | Active projects | Goal, timeline, progress log, risks |
| **Person Note** | Contacts, team members | Role, interaction log, follow-up items |

All templates use YAML frontmatter for structured metadata, making notes easy to filter, search, and query with Obsidian plugins like Dataview.

## Configuration

### Vault Path Resolution

The installer and skill look for your vault path in this priority order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | CLI argument | `--vault /path/to/vault` |
| 2 | `.env` file | `OBSIDIAN_KB_VAULT=/path/to/vault` |
| 3 | Environment variable | `export OBSIDIAN_KB_VAULT=/path/to/vault` |
| 4 | Config file | `~/.obsidian-kb-config` |

### Changing Your Vault Path

Edit `.env` and re-run the installer, or update the config directly:

```bash
# macOS / Linux
echo "/new/vault/path" > ~/.obsidian-kb-config

# Windows PowerShell
[System.IO.File]::WriteAllText(
    "$env:USERPROFILE\.obsidian-kb-config",
    "D:\NewVaultPath",
    (New-Object System.Text.UTF8Encoding $false)
)
```

### Install for Specific Platforms

```bash
# Only QoderWork and Claude Code
./install.sh --platforms qoderwork,claude-code

# Only Cursor
.\install.ps1 -Platforms "cursor"
```

## Sharing

This skill is designed to be shared. When distributing to others:

1. Share the entire `obsidian-kb-skill/` folder (or point them to this repo)
2. **Do not** include your `.env` file (it's already in `.gitignore`)
3. They copy `.env.example` to `.env`, set their own vault path, and run the installer

## Customization

**Add templates:** Create new `.md` files in your vault's `Templates/` folder with the same YAML frontmatter pattern.

**Add folders:** Create a new numbered folder (e.g., `60-Research/`), add an `INDEX.md` inside, and the agents will discover it.

**Change tags:** Edit the platform instruction file's tagging section to add domain-specific tags.

**Change routing:** Modify the folder routing table to redirect certain trigger keywords to different folders.

## Project Structure

```
obsidian-kb-skill/
├── .env.example                Config template (commit to git)
├── .env                        Your local config (gitignored)
├── .gitignore
├── core/
│   ├── OBSIDIAN_KB.md          Source of truth — agent-agnostic instructions
│   └── templates/              7 portable note templates
├── platforms/
│   ├── qoderwork/SKILL.md      QoderWork adapter
│   ├── claude-code/CLAUDE.md   Claude Code adapter
│   ├── codex/AGENTS.md         OpenAI Codex adapter
│   └── cursor/obsidian-kb.mdc  Cursor adapter
├── install.sh                  macOS / Linux installer
├── install.ps1                 Windows installer
└── README.md
```

## Design Principles

- **Just Markdown.** No databases, no APIs, no vendor lock-in. Your knowledge is plain text files that will outlive any app.
- **Agent-agnostic.** The core logic is platform-independent. Each AI tool gets a thin adapter file in its native format.
- **Convention over configuration.** Sensible defaults for folder structure, naming, tags, and templates. Customize only what you need.
- **Self-contained at runtime.** After installation, each platform file has everything it needs — no external dependencies.

## Recommended Obsidian Plugins

These are optional but enhance the experience:

- **[Dataview](https://github.com/blacksmithgu/obsidian-dataview)** — Query your notes like a database (e.g., "show all meeting notes from this week")
- **[Calendar](https://github.com/liamcain/obsidian-calendar-plugin)** — Visual calendar for daily notes
- **[Kanban](https://github.com/mgmeyers/obsidian-kanban)** — Project boards that read from your vault
- **[Templater](https://github.com/SilentVoid13/Templater)** — Advanced template processing for manual note creation

## License

MIT — use freely, modify, share.
