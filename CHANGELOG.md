# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-06-11

### Added
- **Build script architecture (`build.py`)**: Single-source-of-truth generator that produces all four platform adapters from `core/OBSIDIAN_KB.md` plus per-platform `platforms/{name}/header.md`. One edit syncs all four platforms; `--check` mode verifies generated files are in sync (suitable for CI / pre-commit).
- **Per-platform `header.md`**: Each platform now has a small `header.md` containing only its YAML frontmatter / H1 / trigger hint. The shared body lives in `core/OBSIDIAN_KB.md`.
- **Generated-file banner**: All adapter files now start with an `AUTO-GENERATED` HTML comment warning against direct edits.
- **"When NOT to Use This Skill" section**: Explicit non-triggers (casual Q&A, debugging, one-off snippets) to reduce false invocations.
- **Vault Validation step**: Verifies `.obsidian/` and `Templates/` exist before any write; refuses to write into non-vault paths.
- **"Decide First: Create vs Update" section**: Forces the agent to choose Create vs Update before acting, with explicit ambiguity-handling rules.
- **Update Existing Note Workflow** (7 steps): Locate target, read in full, pick insertion point (section-aware for `project-note` / `person-note` / `daily-note`), preserve frontmatter, report diff summary. Closes the gap where the skill only knew how to create new notes.
- **Bounded wikilink search**: Cheap-first strategy in Step 6 — read folder INDEX, list 1–2 sibling folders, read first ~20 lines of 2–5 candidates, insert at most 5 wikilinks. Replaces vague "scan the vault" instruction.
- **Cost Limits section**: Hard per-invocation caps (10 files scanned, 3 full reads, 1 note written, 2 INDEX updates, 5 wikilinks) to prevent runaway token usage.
- **Tag Hygiene section**: Reuse existing tags first (scan 5 recent notes), kebab-case only, no near-duplicates, max 5 tags per note.
- **`updated:` frontmatter field**: Added to `project-note` and `person-note` types to support the Update workflow.
- **README "Editing the Skill / Contributing" section**: Explains build script architecture in both Chinese and English READMEs.

### Changed
- **Tightened skill descriptions**: All four platforms now narrow the trigger to explicit save/append intent ("save to Obsidian", "记一下", "沉淀到知识库", etc.) and explicitly exclude casual Q&A and debugging. Reduces false positives from broad words like "notes" or "knowledge".
- **Project structure**: Four `header.md` files added; four adapter files are now generated artifacts (do not edit directly).
- **Important Rules**: Now reference both Create and Update workflows, vault validation, and cost limits.

### Notes
- The four generated adapter files (`SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `obsidian-kb.mdc`) remain at their original paths, so existing installer logic and external links continue to work unchanged.
- Backward-compatible with all v1.0.0 installations — no migration required.

## [1.0.0] - 2026-06-11

### Added
- **Daily Note routing**: Added "daily, today, diary, journal, morning plan" trigger pattern to all platform adapters
- **Error handling section**: Comprehensive error handling guidelines in core instructions and all adapters
- **Template placeholder docs**: Documented `{{date}}` placeholder replacement behavior
- **Subfolder support**: Routing and INDEX update rules for topic-based subfolders (e.g. `20-Learning/Python/`)
- **Install script improvements**:
  - `-Help` / `--help` parameter with full usage documentation
  - `-Uninstall` / `--uninstall` option to cleanly remove skill files
  - `--force` upgrade mode to update existing templates
- **Cursor glob patterns**: Expanded to include `**/vault*`, `**/INDEX*`, `**/*.md`
- **`.gitignore` expanded**: Added OS artifacts (.DS_Store, Thumbs.db), editor artifacts (.vscode/, .idea/), Obsidian workspace files
- **Version identifier**: Added version `1.0.0` to core instructions and README

### Fixed
- **UTF-8 BOM on PowerShell 5.1**: Replaced `Set-Content -Encoding UTF8` with `[System.IO.File]::WriteAllText()` in install.ps1 (3 occurrences)
- **Cross-adapter consistency**: Standardized all 4 platform adapters to 9-step workflow matching core instructions
- **Template paths in Cursor**: Added `Templates/` prefix to all template references in obsidian-kb.mdc
- **"Never overwrite" rule**: Added numeric suffix guidance (`-2`, `-3`) to Codex and Cursor adapters
- **"Never hardcode date"**: Added explicit warning to Codex and Cursor adapters
- **`.env.example` comment**: Fixed misleading "should NOT be committed" message

### Changed
- Core workflow expanded from 6 steps to 9 steps (matching adapter implementations)
- All routing tables now include Daily Note as the first entry
- Rules sections now include subfolder INDEX update rule
- YAML frontmatter table now includes `daily-note` type
