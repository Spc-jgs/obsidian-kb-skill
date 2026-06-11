# Changelog

All notable changes to this project will be documented in this file.

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
