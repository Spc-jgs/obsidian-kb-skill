# Obsidian Knowledge Base Skill

**v1.12.1** | **Turn any AI coding agent into your personal knowledge management assistant.**

A cross-platform skill that teaches AI agents (QoderWork, Claude Code, OpenAI Codex, Cursor, WorkBuddy) how to create, organize, and interlink notes in your [Obsidian](https://obsidian.md) vault — automatically.

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

## What's New in v1.12

v1.12 formally installs the complete standard Skill into WorkBuddy and makes installed state independently diagnosable:

- Bash and PowerShell install the identical complete payload at `~/.workbuddy/skills/obsidian-knowledge-base/`. Upgrade replaces only an old symlink entry, and uninstall preserves its target clone and sibling Skills.
- The standard Skill carries a deterministic `manifest.json`; read-only `doctor --json` verifies payload, runtime, dependencies, and required resources without repairing or deleting anything.
- `run_helper.py <helper> --help` now reaches all nine child CLIs directly. Doctor still runs when `runtime.json` is malformed.
- The create-note stdin/content-file frontmatter merge and precedence are now discoverable in CLI help, the lazy reference, and regression tests, including `source` and `related`.
- Installed-product tests remove the release source and then run doctor and core helpers from the WorkBuddy copy. A real WorkBuddy forward task and P0 audit remain release gates.

See [CHANGELOG.md](CHANGELOG.md) under `[1.12.1]` for the complete diff. Detailed usage remains lazy-loaded from `core/references/note-creation.md`.

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

### Option 3: Grab the Standard Skill Folder or a Compatibility File

If your Vault structure and templates already exist, you can copy only the instruction file for your platform:

| AI Tool | File Needed | Direct Link |
|---------|-------------|-------------|
| Agent Skills / Codex / QoderWork | complete `skills/obsidian-knowledge-base/` | [Skill entry](skills/obsidian-knowledge-base/SKILL.md) |
| Claude Code | `platforms/claude-code/CLAUDE.md` | [CLAUDE.md](platforms/claude-code/CLAUDE.md) |
| OpenAI Codex (compatibility entry) | `platforms/codex/AGENTS.md` | [AGENTS.md](platforms/codex/AGENTS.md) |
| Cursor | `platforms/cursor/obsidian-kb.mdc` | [obsidian-kb.mdc](platforms/cursor/obsidian-kb.mdc) |

Compatibility files provide only the entry rules; their references, assets, and helpers come from `~/.obsidian-kb-skill/skill/`, which the installer creates. **Copying one instruction file is neither a complete standard Skill nor a Vault setup.** Use the installer for first-time and compatibility installations.

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

This project uses **Markdown behavior instructions** as its rule layer and bundles local Python helpers for deterministic, error-prone operations. It calls no cloud API and runs no daemon: the rules guide the agent, while helpers enforce path safety, scaffold templates, write notes, detect indexes, and audit results.

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
    │Standard Skill│ │ CLAUDE.md   │ │  AGENTS.md    │ ...
    │Codex/QoderWork││(Claude Code)│ │(compatibility)│
    └──────────────┘ └─────────────┘ └───────────────┘
```

The core instruction file `core/OBSIDIAN_KB.md` is the single source of truth. It is a tiny gatekeeper (source **21 lines**, generated `SKILL.md` **25 lines**) with a prominent **DO NOT auto-save** rule and pointers into `core/references/*`; the heavy workflows live in those reference files and are loaded by an agent **only when it is about to save**, so loading the skill costs almost no tokens. The platform-independent entry is `skills/obsidian-knowledge-base/SKILL.md`; `platforms/*` remains as compatibility output. All artifacts (including the shipped `references/` for each platform) are generated by `build.py`.

### Why No Plugins or APIs Are Needed

An Obsidian vault is just a **folder full of .md files**. No database, no proprietary format. AI agents are naturally good at reading and writing files. So:

- **Creating a note** = writing a .md file at the right path
- **Handling an index** = leave plugin-managed indexes untouched; append only in Static mode
- **Cross-linking notes** = inserting `[[filename|display text]]` in the content
- **Structured metadata** = writing YAML frontmatter at the top of the file

Runtime actions are local file operations. The rule layer has no service dependency; helpers require Python 3.11+ and PyYAML, and the installer keeps a missing PyYAML dependency inside the Skill's private support directory. Vault contents are not sent to a cloud service.

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
| **OpenAI Codex** | standard `SKILL.md` | `~/.agents/skills/obsidian-knowledge-base/` |
| **WorkBuddy** | standard `SKILL.md` | `~/.workbuddy/skills/obsidian-knowledge-base/` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

The standard Skill and compatibility artifacts contain identical core instructions. `~/.agents/skills` is Codex's user-level discovery path; it is not a universal discovery path for every agent.

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
- Copy 8 note templates into your vault
- Create native folder-named indexes from Folder Index settings, or `INDEX.md` fallbacks without the plugin
- Write your vault path to `~/.obsidian-kb-config` (runtime config)
- Create global `~/.obsidian-kb-settings.json` once; `backup.keep_per_note` defaults to `1` and accepts 1–1000
- Install the complete standard Skill payload at each selected platform location
- Configure a private helper runtime and run `vault-info` from a neutral directory as post-install verification

By default, all platform entries are installed. Codex, QoderWork, and WorkBuddy
receive complete copies of the same standard Skill. WorkBuddy discovers it at
`~/.workbuddy/skills/obsidian-knowledge-base`. Claude Code and Cursor keep their
compatibility files.

Run the read-only diagnostic from any working directory:

```bash
python ~/.workbuddy/skills/obsidian-knowledge-base/scripts/run_helper.py doctor --json
```

### 4. Open in Obsidian

Open your vault folder in Obsidian. You'll see the folder structure, templates, and index pages ready to go.

### 5. Start capturing

Tell your AI assistant:

- *"Save this discussion about system design to my knowledge base"*
- *"Record the Q2 planning meeting"*
- *"Clip this article: https://example.com/article"*
- *"Create a project note for the dashboard redesign"*

### Manual Installation (Without the Installer)

The standard Skill is no longer one `SKILL.md`; it also carries lazy references, helper code, and template assets. For manual setup, copy the full directory and provide a Python environment that can import PyYAML:

```bash
# 1. Create the config file with your vault path
echo "D:\MyKnowledgeBase" > ~/.obsidian-kb-config

# 2. Copy the complete standard Skill and remove the build-only header.md
# QoderWork:
cp -R skills/obsidian-knowledge-base ~/.qoderwork/skills/
rm ~/.qoderwork/skills/obsidian-knowledge-base/header.md

# OpenAI Codex:
cp -R skills/obsidian-knowledge-base ~/.agents/skills/
rm ~/.agents/skills/obsidian-knowledge-base/header.md

# Claude Code:
# Use the marker-aware installer to avoid overwriting an existing CLAUDE.md.
./install.sh --platforms claude-code

# Cursor:
cp platforms/cursor/obsidian-kb.mdc ~/.cursor/rules/obsidian-kb.mdc

# 3. Seed missing templates without overwriting user templates
python ~/.agents/skills/obsidian-knowledge-base/scripts/run_helper.py \
  scaffold-templates /your/vault/path --apply
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
├── Templates/         8 pre-built note templates
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
| **Conversation Digest** | Distill AI chat summaries | Background, confirmed conclusions, revised ideas, follow-up tasks |

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

# Only WorkBuddy
./install.sh --platforms workbuddy

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

### Upgrading the Skill and Templates

Re-running the installer idempotently updates the Codex/QoderWork/WorkBuddy Skill. Existing templates remain untouched by default; use `--force` to update templates and replace the marker-wrapped Claude Code block:

```bash
# macOS / Linux
./install.sh --force

# Windows
.\install.ps1 -Force
```

> Claude Code still uses a marker block. Upgrade does not proactively remove a legacy block in `~/AGENTS.md`; uninstall safely removes it.

### Uninstalling

```bash
# macOS / Linux
./install.sh --uninstall

# Windows
.\install.ps1 -Uninstall
```

Uninstall removes the Codex/QoderWork Skills, only the product-owned WorkBuddy Skill directory, the Cursor rule, private runtime, and marker blocks from `CLAUDE.md` and legacy `AGENTS.md`. Sibling Skills, the old symlink target Git checkout, the Vault, notes, `~/.obsidian-kb-config`, and `~/.obsidian-kb-settings.json` are preserved by upgrade and default uninstall; explicit config purge removes it together with the Vault-path config. Use `./install.sh --uninstall --purge-config` or `.\install.ps1 -Uninstall -PurgeConfig` for that explicit purge.

## Sharing

This skill is designed to be shared. When distributing to others:

1. Share the entire `obsidian-kb-skill/` folder (or point them to this repo)
2. **Do not** include your `.env` file (it's already in `.gitignore`)
3. They copy `.env.example` to `.env`, set their own vault path, and run the installer

## Customization

**Add templates:** Create new `.md` files in your vault's `Templates/` folder with the same YAML frontmatter pattern.

**Add folders:** Create a new numbered folder (e.g., `60-Research/`). Native Folder Index mode creates `60-Research/60-Research.md`; use the `INDEX.md` fallback only without the plugin.

**Change tags:** Prefer Vault-local tag rules in the Vault's `AGENTS.md`. To change project defaults, edit `core/OBSIDIAN_KB.md` and run `python build.py`.

**Change routing:** Prefer the Vault's `AGENTS.md` routing table. Edit `core/OBSIDIAN_KB.md` only when changing defaults for every new installation.

## Project Structure

```
obsidian-kb-skill/
├── .python-version             Default development interpreter: Python 3.14.6
├── uv.lock                     Reproducible dependency lockfile
├── .env.example                Config template (commit to git)
├── .env                        Your local config (gitignored)
├── .gitignore
├── build.py                    Generator (core + header → 5 artifacts)
├── core/
│   ├── OBSIDIAN_KB.md          Gatekeeper (source 21 lines / generated 25): DO NOT auto-save + pointers to references/
│   ├── references/             Full workflow specs (lazy-loaded: read only when about to save)
│   │   ├── conversation-digest.md
│   │   ├── git.md
│   │   ├── note-creation.md    Full create workflow and installed runner usage
│   │   ├── rules-and-errors.md
│   │   ├── task-memory.md
│   │   ├── update-note.md
│   │   └── yaml-standards.md
│   └── templates/              8 default Chinese templates (incl. conversation digest) + English templates in en/
├── obsidian_kb_skill/
│   └── scripts/                8 packaged CLIs, path-safety layer, and wheel resources
├── tests/                      Build, installer, path-safety, CLI, wheel, and runtime tests
├── skills/
│   └── obsidian-knowledge-base/
│       ├── header.md           Standard Agent Skill header
│       ├── agents/             Codex UI metadata
│       ├── references/         Lazy-loaded references (copied by build.py)
│       ├── scripts/            Launcher plus bundled helper package
│       ├── assets/templates/   Chinese and English template assets
│       └── SKILL.md            Platform-independent generated entry
├── platforms/
│   ├── qoderwork/
│   │   ├── references/
│   │   └── SKILL.md            Compatibility mirror of the standard Skill
│   ├── claude-code/
│   │   ├── header.md
│   │   ├── references/
│   │   └── CLAUDE.md           Generated artifact
│   ├── codex/
│   │   ├── header.md
│   │   ├── references/
│   │   └── AGENTS.md           Generated artifact
│   └── cursor/
│       ├── header.md
│       ├── references/
│       └── obsidian-kb.mdc     Generated artifact
├── install.sh                  macOS / Linux installer
├── install.ps1                 Windows installer
├── CHANGELOG.md
└── README.md
```

## Editing the Skill / Contributing

The standard Skill and four compatibility artifacts are generated from one source by `build.py`. **Never edit generated instruction artifacts directly.**

The default development interpreter is Python 3.14.6; the minimum supported
version is Python 3.11. Use [uv](https://docs.astral.sh/uv/) for the standard
reproducible workflow:

```bash
# 1. Create the Python 3.14.6 .venv from uv.lock
uv sync --locked --extra dev

# 2. Edit the shared rules
$EDITOR core/OBSIDIAN_KB.md

# 3. Or edit the standard Skill header (frontmatter / trigger description)
$EDITOR skills/obsidian-knowledge-base/header.md

# 4. Regenerate and verify all five artifacts
uv run --no-sync python build.py
uv run --no-sync python build.py --check

# 5. Run the test suite
uv run --no-sync python -m pytest
```

Without uv, use a standard venv and upgrade packaging tools before the editable
install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pytest
```

CI consumes the same lockfile and runs build checks and tests on Python 3.11 and
3.14.

After installing `.[dev]` or a wheel, all eight helpers are available as console
commands. Installer-deployed standard Skills use `<skill-root>/scripts/run_helper.py`;
both entry styles invoke the same Python implementation:

```bash
obsidian-audit-vault        /path/to/vault --strict
obsidian-process-inbox      /path/to/vault --apply
obsidian-suggest-links      /path/to/vault --note 30-Insights/some-note.md
obsidian-create-note        /path/to/vault --type insight-note --title "Short Title" --content-file body.md --apply
obsidian-update-note        /path/to/vault --note Tasks/some-task/TASK.md --step "..." --by Codex --log "finished X, handing to WorkBuddy" --apply
obsidian-vault-info         /path/to/vault --json
obsidian-detect-index       /path/to/vault --folder 30-Insights --json
obsidian-scaffold-templates /path/to/vault --apply
```

Adding `--json` to any of these commands outputs a single machine-readable JSON
document (schemas documented in each script's `--help`), so an agent or another
tool can consume the output without parsing human-readable text.

### Audit an Existing Vault

Use the read-only auditor to check required frontmatter, note types, unclosed code fences, broken or ambiguous wikilinks, and duplicate folder indexes:

```bash
obsidian-audit-vault /path/to/vault --strict
```

Exit code `0` means clean, `1` means findings were reported, and `2` means the path is not an Obsidian vault. The auditor never modifies files.

> **Audit scope and tunables**
> - The auditor automatically skips **hidden directories** (names starting with `.`) and known tool/metadata folders (`.git`, `.obsidian`, `.venv`, `.workbuddy`, ...). Files inside them are never treated as notes, so agent working memory under `.workbuddy/`, `.claude/`, `.cursor/`, etc. will not be falsely reported.
> - `similar-title` (similar titles) and `orphan-note` (orphan notes) are **advisory** checks only — they never force or modify anything. `similar-title` uses a `difflib` similarity threshold of **0.85** (in `obsidian_kb_skill/scripts/audit_vault.py`, `_audit_titles`: `ratio >= 0.85`). If your vault has many titles that differ only by a date prefix and the noise feels too loud, raise the threshold to `0.90` or similar to quiet it down — at the cost of possibly missing near-duplicate titles that are worth merging.

### Filing the Inbox

`process_inbox.py` files quick-capture / pending notes from `00-Inbox/` into the inferred target folder, filling in missing `date` / `type` / `tags`. By default it only prints the plan and changes nothing:

```bash
obsidian-process-inbox /path/to/vault --plan    # read-only preview
obsidian-process-inbox /path/to/vault --apply   # file notes (never overwrites existing files)
```

The target folder is inferred from the note's `type` or body keywords (matching the routing table in `core/OBSIDIAN_KB.md`); when the Folder Index plugin is disabled, a link is appended to the target folder's static `INDEX.md`.

### Suggesting Links

`suggest_links.py` scores candidate wikilink targets for a single note within a bounded scope (the note's folder plus up to two sibling folders) by shared tags, matching type, and title-token overlap. It only prints candidates and reasons, and never writes to files:

```bash
obsidian-suggest-links /path/to/vault --note 30-Insights/some-note.md --top-n 10
```

Decide after human review whether to insert a link, so the vault is never changed automatically.

### Creating a Note (when no native write tool exists)

The `create-note` helper is a **constraint-based note creator**: when the environment has no native file-write tool (some CLI-only agents), call it instead of writing your own throwaway Python/shell script to do the I/O. By default it only prints the path and content it would write (dry run); add `--apply` to actually persist. On a name collision it appends `-2` / `-3` automatically and **never overwrites**.

```bash
obsidian-create-note /path/to/vault \
    --type insight-note --title "Short Title" \
    --content-file body.md --apply
```

- `--type`: note type (matches the routing table); `--title` becomes the filename.
- `--content-file`: path to the body `.md` (any frontmatter inside is merged, explicit values win); or use `--stdin` to read the body from standard input.
- `--tags`: override the type default tags; `--date`: override the date (defaults to today); `--folder`: override the routed target folder.
- After writing, it updates a static `INDEX.md` according to the detected index strategy (Folder Index / Dataview managed listings are left untouched).
- This pairs with the Step 7 "tool choice" rule in `core/OBSIDIAN_KB.md`: agents prefer their native write tool, otherwise use this script rather than inventing one.

### Task Memory (multi-agent long-task handoff)

The **Task Memory Workflow** in `core/references/task-memory.md` closes the memory gap when multiple agents接力 (hand off) the same long task: before each agent yields, it updates one `Tasks/<slug>/TASK.md` (status, decisions, constraints, open items, artifacts touched, handoff log); the next agent reads it as its first action.

**Off by default, opt in** — the global env `OBSIDIAN_KB_TASK_MEMORY=on|off` (default `off`) is the master switch; per-task, the `task-memory: enabled` field turns it on. Say "开启任务记忆 / handoff" in a session to activate, "关闭" to deactivate. When off, there is zero overhead.

`obsidian-update-note` is the matching **constraint-based updater**: it backs up an existing note before writing, changes only structured frontmatter fields, and appends a timestamped line to `## Log` — it never overwrites your prose; `Log` is auto-capped to the last 30 entries (TTL); dry run by default, `--apply` to write. If the note does not exist it is initialized from the template (upsert), so one command both starts and updates a task:

```bash
obsidian-update-note /path/to/vault \
    --note Tasks/foo/TASK.md --status active --step "implement X module" \
    --add-decision "Chose Postgres over Mongo (scale)" \
    --by WorkBuddy --log "scaffold done, handing data layer to Codex" --apply
```

## Design Principles

- **Markdown data layer.** No database, cloud API, or vendor lock-in; the knowledge itself remains plain text.
- **Agent-agnostic.** The core logic is platform-independent. Each AI tool gets a thin adapter file in its native format.
- **Convention over configuration.** Sensible defaults for folder structure, naming, tags, and templates. Customize only what you need.
- **Self-contained after installation.** The standard Skill carries references, scripts, and assets; the installer explicitly configures and verifies the Python/PyYAML helper boundary.
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
