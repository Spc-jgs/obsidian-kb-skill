# Obsidian Knowledge Base Skill

**v1.6.0** | **Turn any AI coding agent into your personal knowledge management assistant.**

A cross-platform skill that teaches AI agents (QoderWork, Claude Code, OpenAI Codex, Cursor) how to create, organize, and interlink notes in your [Obsidian](https://obsidian.md) vault — automatically.

[中文版](README.md)

---

## The Problem

We talk to AI assistants every day — brainstorming ideas, analyzing articles, reviewing meetings, debugging problems. These conversations produce genuinely valuable knowledge, but it almost always evaporates the moment you close the chat window.

Manually copying insights into a note-taking app is tedious and inconsistent. The friction is too high: you need to decide where to put it, how to format it, what tags to use, and how it connects to existing notes. So most of the time, you just... don't.

## The Solution

This skill eliminates that friction by teaching your AI agent a complete knowledge management workflow. You just say things like *"save this to my knowledge base"* or *"record this meeting"*, and the agent handles everything:

- Picks the right note type and template
- Fills in structured metadata (date, tags, source)
- Writes to the correct folder in your Obsidian vault
- Applies the detected Folder Index, Dataview, or static index strategy
- Cross-links related notes with `[[wikilinks]]`

Your knowledge accumulates automatically, in a structured format that scales from 10 notes to 10,000.

## Download

### Option 1: Git Clone (Recommended)

```bash
git clone https://github.com/Spc-jgs/obsidian-kb-skill.git
cd obsidian-kb-skill
```

### Option 2: Download ZIP

1. Go to https://github.com/Spc-jgs/obsidian-kb-skill
2. Click the green **Code** button
3. Select **Download ZIP**
4. Extract to your preferred directory

### Option 3: Grab Only Your Platform File

If you don't want to clone the entire repo, you can copy just the instruction file for your platform:

| AI Tool | File Needed | Direct Link |
|---------|-------------|-------------|
| QoderWork | `platforms/qoderwork/SKILL.md` | [SKILL.md](platforms/qoderwork/SKILL.md) |
| Claude Code | `platforms/claude-code/CLAUDE.md` | [CLAUDE.md](platforms/claude-code/CLAUDE.md) |
| OpenAI Codex | `platforms/codex/AGENTS.md` | [AGENTS.md](platforms/codex/AGENTS.md) |
| Cursor | `platforms/cursor/obsidian-kb.mdc` | [obsidian-kb.mdc](platforms/cursor/obsidian-kb.mdc) |

Each platform file is **self-contained** — a single file with instructions, templates, and routing rules. Copy and it works.

## Usage Scenarios

### Scenario 1: Auto-Capture Knowledge from AI Conversations

You discuss a technical topic with AI, say "microservices vs monolith trade-offs." When the discussion wraps up, you say *"save this to my knowledge base."* The AI distills the key insights into a structured note in `30-Insights/`, complete with tags, context, and links to related notes.

### Scenario 2: Auto-Generated Meeting Notes

After a requirements review meeting, you tell the AI: *"Record the requirements review — attendees were Alice and Bob, we discussed the V2 auth plan, decided on OAuth2."* The AI creates a meeting note in `10-Work/` using the meeting template, with structured fields for participants, decisions, and action items.

### Scenario 3: One-Click Web Clipping

You find a great article and send it to the AI: *"Clip this article https://example.com/article."* The AI uses the web clip template to extract highlights, capture key quotes, save the original URL, and store it in `20-Learning/`.

### Scenario 4: Continuous Learning Notes

While studying a course or reading a book, you share your thoughts with the AI and say *"record my learning notes on Redis persistence."* The AI organizes core concepts, your understanding, and open questions using the learning note template.

### Scenario 5: Long-Term Project Tracking

When starting a new project, tell the AI *"create a project note for the dashboard redesign."* The AI creates a project note in `40-Projects/` with goals, timeline, and risks. As the project progresses, the AI appends updates to the same note's progress log.

### Scenario 6: Unified Knowledge Base Across AI Tools

You use Cursor at work, QoderWork for research at home, and Claude Code for quick questions on the go — all knowledge flows into **one Obsidian vault** with **the same folder structure and templates**, regardless of which AI tool generated it.

## How It Works

### Core Idea: Teach AI with Markdown Instructions

This skill is fundamentally a **Markdown-formatted behavior instruction file**. It contains no code, calls no APIs, and runs no services. It simply tells the AI agent in natural language:

1. Where your knowledge base is (path)
2. What it looks like (folder structure)
3. How each type of note should be written (templates + YAML frontmatter)
4. Which content goes to which folder (routing rules)
5. How to tag notes (tagging conventions)
6. How to detect and respect Folder Index, Dataview, or static index ownership

After reading this instruction file, the AI agent has "learned" your knowledge management conventions. When you say "save to knowledge base," it follows the rules and directly reads/writes your Obsidian vault using standard file operations.

### Architecture: One Core, Multiple Adapters

```
                  ┌──────────────────────────┐
                  │  core/OBSIDIAN_KB.md     │
                  │  (universal instructions, │
                  │   platform-agnostic)      │
                  └────────┬─────────────────┘
                           │
            ┌──────────────┼──────────────────┐
            │              │                  │
    ┌───────▼──────┐ ┌────▼────────┐ ┌───────▼───────┐
    │  SKILL.md    │ │ CLAUDE.md   │ │  AGENTS.md    │ ...
    │ (QoderWork)  │ │(Claude Code)│ │ (Codex)       │
    └──────────────┘ └─────────────┘ └───────────────┘
```

The core instruction file `core/OBSIDIAN_KB.md` is the "single source of truth" defining all knowledge management rules. Platform adapter files are derived from it, containing **identical rules** in each platform's native format.

### Why No Plugins or APIs Are Needed

An Obsidian vault is just a **folder full of .md files**. No database, no proprietary format. AI agents are naturally good at reading and writing files. So:

- **Creating a note** = writing a .md file at the right path
- **Handling an index** = leave plugin-managed indexes untouched; append only in Static mode
- **Cross-linking notes** = inserting `[[filename|display text]]` in the content
- **Structured metadata** = writing YAML frontmatter at the top of the file

Every action the AI takes is a standard file operation. This means zero dependencies, zero network requests, zero extra cost. Your knowledge base stays entirely local — privacy by design.

### Runtime Flow

```
You: "Save the key insights from our microservices discussion"

AI Agent internally executes:
  1. Reads ~/.obsidian-kb-config → gets vault path D:\MyKnowledgeBase
  2. Identifies trigger word "insights" → routes to 30-Insights/
  3. Reads Templates/insight-note.md → loads the insight note template
  4. Fills YAML frontmatter (date, tags, one-line insight)
  5. Generates body content (context, analysis, implications, next steps)
  6. Writes to 30-Insights/2026-06-10 Microservices Insights.md
  7. Detects the index strategy → leaves Folder Index / Dataview untouched and appends only in Static mode
  8. Replies: "Saved to 30-Insights/2026-06-10 Microservices Insights.md"
```

## Supported Platforms

| Platform | Config File | Install Location |
|----------|------------|-----------------|
| **QoderWork / Qoder CLI** | `SKILL.md` | `~/.qoderwork/skills/obsidian-knowledge-base/` |
| **Claude Code** | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **OpenAI Codex** | `AGENTS.md` | `~/AGENTS.md` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

All four platform files contain **identical instructions** — same folder routing, same templates, same YAML conventions, same tagging conventions. Only the file format differs to match each platform's convention.

## Quick Start

### 1. Download the project

```bash
git clone https://github.com/Spc-jgs/obsidian-kb-skill.git
cd obsidian-kb-skill
```

### 2. Configure your vault path

```bash
cp .env.example .env
```

Edit `.env` with your vault path:

```env
OBSIDIAN_KB_VAULT=D:\MyKnowledgeBase
```

If your vault doesn't exist yet, the installer will create the full folder structure automatically.

### 3. Run the installer

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
- Create native folder-named indexes from Folder Index settings, or `INDEX.md` fallbacks without the plugin
- Write your vault path to `~/.obsidian-kb-config` (runtime config)
- Install the skill file to your chosen AI platform's convention location

### 4. Open in Obsidian

Open your vault folder in Obsidian. You'll see the folder structure, templates, and index pages ready to go.

### 5. Start capturing

Tell your AI assistant:

- *"Save this discussion about system design to my knowledge base"*
- *"Record the Q2 planning meeting"*
- *"Clip this article: https://example.com/article"*
- *"Create a project note for the dashboard redesign"*

### Manual Installation (Without the Installer)

If you prefer manual control or the installer doesn't fit your needs:

```bash
# 1. Create the config file with your vault path
echo "D:\MyKnowledgeBase" > ~/.obsidian-kb-config

# 2. Copy the platform instruction file to the convention location
# QoderWork:
cp platforms/qoderwork/SKILL.md ~/.qoderwork/skills/obsidian-knowledge-base/SKILL.md

# Claude Code:
cp platforms/claude-code/CLAUDE.md ~/.claude/CLAUDE.md

# Cursor:
cp platforms/cursor/obsidian-kb.mdc ~/.cursor/rules/obsidian-kb.mdc

# 3. Copy templates to your vault
cp core/templates/en/*.md /your/vault/path/Templates/
```

## Vault Structure

```
YourVault/
├── 00-Inbox/          Quick capture — native Folder Index uses 00-Inbox.md
├── 10-Work/           Meeting notes, work documents, team discussions
├── 15-Daily/          Daily notes, journals, morning plans, reviews
├── 20-Learning/       Articles, study notes, web clips, course materials
├── 30-Insights/       Analysis, ideas, AI-generated insights
├── 40-Projects/       Active project context and progress logs
├── 50-People/         Contacts, team members, interaction logs
├── 90-Archive/        Completed or inactive items
├── Templates/         7 pre-built note templates
├── Attachments/       Images and file attachments
└── INDEX.md           Root navigation hub (non-root indexes use folder names)
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

### Choose the Template Language

The installer uses Chinese templates by default. Select English explicitly when needed:

```bash
./install.sh --locale zh-CN
./install.sh --locale en
```

On Windows PowerShell, use `-Locale zh-CN` or `-Locale en`. Existing templates are preserved; combine the locale switch with `--force` / `-Force` to replace them.

### Upgrading Templates

Re-running the installer won't overwrite existing templates by default. Use `--force` to update templates and replace the marker-wrapped skill block inside `CLAUDE.md` / `AGENTS.md` with the new version:

```bash
# macOS / Linux
./install.sh --force

# Windows
.\install.ps1 -Force
```

> The installer wraps injected content in `<!-- BEGIN obsidian-kb-skill -->` / `<!-- END obsidian-kb-skill -->` markers. Re-running replaces the block in place without touching your other instructions in those files.

### Uninstalling

```bash
# macOS / Linux
./install.sh --uninstall

# Windows
.\install.ps1 -Uninstall
```

Uninstall removes the QoderWork skill, Cursor rule, and config file, and **automatically strips the marker-wrapped skill block from `CLAUDE.md` / `AGENTS.md`** while preserving the rest of those files. Your Obsidian vault and note contents are never deleted.

## Sharing

This skill is designed to be shared. When distributing to others:

1. Share the entire `obsidian-kb-skill/` folder (or point them to this repo)
2. **Do not** include your `.env` file (it's already in `.gitignore`)
3. They copy `.env.example` to `.env`, set their own vault path, and run the installer

## Customization

**Add templates:** Create new `.md` files in your vault's `Templates/` folder with the same YAML frontmatter pattern.

**Add folders:** Create a new numbered folder (e.g., `60-Research/`). Native Folder Index mode creates `60-Research/60-Research.md`; use the `INDEX.md` fallback only without the plugin.

**Change tags:** Edit the platform instruction file's tagging section to add domain-specific tags.

**Change routing:** Modify the folder routing table to redirect certain trigger keywords to different folders.

## Project Structure

```
obsidian-kb-skill/
├── .env.example                Config template (commit to git)
├── .env                        Your local config (gitignored)
├── .gitignore
├── build.py                    Adapter generator (core + header → 4 adapters)
├── core/
│   ├── OBSIDIAN_KB.md          Single source of truth — agent-agnostic instructions
│   └── templates/              7 default Chinese templates + English templates in en/
├── scripts/
│   └── audit_vault.py          Read-only Vault auditor
├── tests/                      Build, template, and auditor tests
├── platforms/
│   ├── qoderwork/
│   │   ├── header.md           QoderWork-specific YAML frontmatter
│   │   └── SKILL.md            Generated artifact (do NOT edit)
│   ├── claude-code/
│   │   ├── header.md
│   │   └── CLAUDE.md           Generated artifact
│   ├── codex/
│   │   ├── header.md
│   │   └── AGENTS.md           Generated artifact
│   └── cursor/
│       ├── header.md
│       └── obsidian-kb.mdc     Generated artifact
├── install.sh                  macOS / Linux installer
├── install.ps1                 Windows installer
├── CHANGELOG.md
└── README.md
```

## Editing the Skill / Contributing

All four platform adapters are generated from a single source of truth by `build.py`. **Never edit `platforms/*/SKILL.md` or other generated artifacts directly** — your changes will be wiped on the next build.

```bash
# 1. Edit the shared rules
$EDITOR core/OBSIDIAN_KB.md

# 2. Or edit a platform-specific header (frontmatter / trigger description)
$EDITOR platforms/qoderwork/header.md

# 3. Regenerate all four adapters
python build.py

# 4. Verify generated files match the source (use in CI / pre-commit)
python build.py --check

# 5. Run the test suite (installs pytest via dev extras)
pip install -e ".[dev]"
pytest
```

One edit → four platforms stay in sync. No more "change one place, sync four places" maintenance pain.

### Audit an Existing Vault

Use the read-only auditor to check required frontmatter, note types, unclosed code fences, broken or ambiguous wikilinks, and duplicate folder indexes:

```bash
python scripts/audit_vault.py /path/to/vault --strict
```

Exit code `0` means clean, `1` means findings were reported, and `2` means the path is not an Obsidian vault. The auditor never modifies files.

## Design Principles

- **Just Markdown.** No databases, no APIs, no vendor lock-in. Your knowledge is plain text files that will outlive any app.
- **Agent-agnostic.** The core logic is platform-independent. Each AI tool gets a thin adapter file in its native format.
- **Convention over configuration.** Sensible defaults for folder structure, naming, tags, and templates. Customize only what you need.
- **Self-contained at runtime.** After installation, each platform file has everything it needs — no external dependencies.
- **Local-first.** All data stays on your machine, no cloud services involved, privacy by design.

## FAQ

**Q: Do I need to pay for Obsidian?**
A: No. Obsidian is completely free for personal use.

**Q: Is it safe for AI to read/write my files?**
A: The AI only operates within your specified vault path and doesn't touch other files. All operations are local.

**Q: Can I use multiple AI tools simultaneously?**
A: Yes! That's exactly what this project is designed for — all AI tools share one vault with the same conventions.

**Q: Will the installer overwrite my existing notes?**
A: No. The installer only creates missing folders and files. It never modifies existing content.

## Recommended Obsidian Plugins

- **[Folder Index](https://github.com/turulix/obsidian-folder-index)** — Recommended when manually created folders and notes should receive automatic indexes and appear as a complete hierarchy in Graph View. Enable Graph View overwrite and use native folder-named indexes (disable the custom index filename). Folder Index 1.0.30 cannot connect parent and child folders when every non-root index is named `INDEX.md`; the root index may still be `INDEX.md`.
- **[Dataview](https://github.com/blacksmithgu/obsidian-dataview)** — Use it for metadata-driven tables, dashboards, and dynamic views. When Folder Index is not active, the installer-provided `INDEX.md` queries keep folder listings current. Rendered Dataview links are not persistent semantic relationships, so related concepts should still use `[[wikilinks]]` in note content or the `related` property.
- **[Calendar](https://github.com/liamcain/obsidian-calendar-plugin)** — Visual calendar for daily notes.
- **[Kanban](https://github.com/mgmeyers/obsidian-kanban)** — Project boards that read from your vault.
- **[Templater](https://github.com/SilentVoid13/Templater)** — Advanced template processing for manual note creation.

## License

MIT — use freely, modify, share.
