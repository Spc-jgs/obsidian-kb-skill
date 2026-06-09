#!/bin/bash
# Obsidian Knowledge Base Skill — Universal Installer
#
# Usage:
#   ./install.sh --vault /path/to/vault [--platforms qoderwork,claude-code,codex,cursor]
#   ./install.sh  # reads vault path from .env file
#
# Configuration (priority order):
#   1. --vault CLI argument
#   2. OBSIDIAN_KB_VAULT in .env (same directory as this script)
#   3. OBSIDIAN_KB_VAULT environment variable
#   4. ~/.obsidian-kb-config (from previous install)
#   5. Interactive prompt

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_PATH=""
PLATFORMS="qoderwork,claude-code,codex,cursor"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --vault) VAULT_PATH="$2"; shift 2 ;;
    --platforms) PLATFORMS="$2"; shift 2 ;;
    --help)
      echo "Usage:"
      echo "  ./install.sh --vault /path/to/vault"
      echo "  ./install.sh   (reads from .env or env var)"
      echo ""
      echo "Options:"
      echo "  --vault PATH       Path to your Obsidian vault"
      echo "  --platforms LIST   Comma-separated: qoderwork,claude-code,codex,cursor (default: all)"
      echo ""
      echo "Configuration sources (checked in order):"
      echo "  1. --vault argument"
      echo "  2. OBSIDIAN_KB_VAULT in .env (skill directory)"
      echo "  3. OBSIDIAN_KB_VAULT environment variable"
      echo "  4. ~/.obsidian-kb-config (from previous install)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Resolve vault path from multiple sources
if [ -z "$VAULT_PATH" ]; then
  # Try .env file in skill directory
  ENV_FILE="$SCRIPT_DIR/.env"
  if [ -f "$ENV_FILE" ]; then
    VAULT_PATH=$(grep -E '^OBSIDIAN_KB_VAULT=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)
    # Trim whitespace
    VAULT_PATH=$(echo "$VAULT_PATH" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [ -n "$VAULT_PATH" ]; then
      echo "→ Read vault path from .env: $VAULT_PATH"
    fi
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  # Try environment variable
  if [ -n "$OBSIDIAN_KB_VAULT" ]; then
    VAULT_PATH="$OBSIDIAN_KB_VAULT"
    echo "→ Read vault path from env var: $VAULT_PATH"
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  # Try previous config
  if [ -f "$HOME/.obsidian-kb-config" ]; then
    VAULT_PATH=$(cat "$HOME/.obsidian-kb-config")
    echo "→ Read vault path from ~/.obsidian-kb-config: $VAULT_PATH"
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  echo "No vault path configured."
  echo "Provide via --vault, .env file, or OBSIDIAN_KB_VAULT env var."
  echo "Run ./install.sh --help for details."
  exit 1
fi

# Resolve to absolute path
if [ -d "$VAULT_PATH" ]; then
  VAULT_PATH="$(cd "$VAULT_PATH" && pwd)"
else
  echo "→ Vault path does not exist, creating: $VAULT_PATH"
  mkdir -p "$VAULT_PATH"
fi

echo "=== Obsidian Knowledge Base Skill Installer ==="
echo "Vault path: $VAULT_PATH"
echo "Platforms:  $PLATFORMS"
echo ""

# Step 1: Save vault config
echo "→ Saving vault config to ~/.obsidian-kb-config"
echo "$VAULT_PATH" > "$HOME/.obsidian-kb-config"

# Step 2: Initialize vault structure if not exists
echo "→ Checking vault structure..."
FOLDERS=("00-Inbox" "10-Work" "20-Learning" "30-Insights" "40-Projects" "50-People" "90-Archive" "Templates" "Attachments")
for folder in "${FOLDERS[@]}"; do
  mkdir -p "$VAULT_PATH/$folder"
done

# Copy templates if not exists
TEMPLATE_FILES=("daily-note.md" "meeting-note.md" "learning-note.md" "project-note.md" "web-clip.md" "insight-note.md" "person-note.md")
TEMPLATE_NAMES=("Daily Note.md" "Meeting Note.md" "Learning Note.md" "Project Note.md" "Web Clip.md" "Insight Note.md" "Person Note.md")
for i in "${!TEMPLATE_FILES[@]}"; do
  src="$SCRIPT_DIR/core/templates/${TEMPLATE_FILES[$i]}"
  dst="$VAULT_PATH/Templates/${TEMPLATE_NAMES[$i]}"
  if [ ! -f "$dst" ] && [ -f "$src" ]; then
    cp "$src" "$dst"
    echo "  Created template: ${TEMPLATE_NAMES[$i]}"
  fi
done

# Create INDEX.md files if not exist
create_index() {
  local folder="$1"
  local title="$2"
  local desc="$3"
  if [ ! -f "$VAULT_PATH/$folder/INDEX.md" ]; then
    cat > "$VAULT_PATH/$folder/INDEX.md" << INDEXEOF
---
type: folder-index
tags: [$folder]
---

# $title

$desc

## Notes

---
INDEXEOF
    echo "  Created index: $folder/INDEX.md"
  fi
}

create_index "00-Inbox" "Inbox" "Quick capture zone. Process later."
create_index "10-Work" "Work" "Meeting notes and work documents."
create_index "20-Learning" "Learning" "Articles, courses, and study materials."
create_index "30-Insights" "Insights" "Analysis and AI-generated insights."
create_index "40-Projects" "Projects" "Active project context documents."
create_index "50-People" "People" "Contacts and team member notes."

# Create main INDEX.md if not exists
if [ ! -f "$VAULT_PATH/INDEX.md" ]; then
  cat > "$VAULT_PATH/INDEX.md" << 'MAINEOF'
---
type: moc
tags: [index, moc]
---

# My Knowledge Base

## Quick Navigation

- [[00-Inbox/INDEX|Inbox]] — Quick capture
- [[10-Work/INDEX|Work]] — Meeting notes, work docs
- [[20-Learning/INDEX|Learning]] — Articles, study notes
- [[30-Insights/INDEX|Insights]] — Analysis, AI insights
- [[40-Projects/INDEX|Projects]] — Active projects
- [[50-People/INDEX|People]] — Contacts, team notes
MAINEOF
  echo "  Created main INDEX.md"
fi

# Create .obsidian config if not exists
mkdir -p "$VAULT_PATH/.obsidian"
if [ ! -f "$VAULT_PATH/.obsidian/app.json" ]; then
  cat > "$VAULT_PATH/.obsidian/app.json" << 'OBSEOF'
{
  "alwaysUpdateLinks": true,
  "newFileLocation": "folder",
  "newFileFolderPath": "00-Inbox",
  "attachmentFolderPath": "Attachments",
  "newLinkFormat": "relative",
  "showFrontmatter": true,
  "readableLineLength": true,
  "defaultViewMode": "preview"
}
OBSEOF
  echo "  Created .obsidian/app.json"
fi

echo "→ Vault structure ready."
echo ""

# Step 3: Install platform files
IFS=',' read -ra PLATFORM_LIST <<< "$PLATFORMS"

for platform in "${PLATFORM_LIST[@]}"; do
  platform=$(echo "$platform" | tr -d ' ')
  case $platform in
    qoderwork)
      QODERWORK_SKILLS="$HOME/.qoderwork/skills/obsidian-knowledge-base"
      mkdir -p "$QODERWORK_SKILLS"
      cp "$SCRIPT_DIR/platforms/qoderwork/SKILL.md" "$QODERWORK_SKILLS/SKILL.md"
      echo "→ Installed: QoderWork skill → $QODERWORK_SKILLS/SKILL.md"
      ;;
    claude-code)
      CLAUDE_DIR="$HOME/.claude"
      mkdir -p "$CLAUDE_DIR"
      # Append to existing CLAUDE.md if it exists, otherwise create new
      CLAUDE_FILE="$CLAUDE_DIR/CLAUDE.md"
      if [ -f "$CLAUDE_FILE" ]; then
        # Check if already installed
        if grep -q "Obsidian Personal Knowledge Base" "$CLAUDE_FILE"; then
          echo "→ Skipped: Claude Code (already installed in $CLAUDE_FILE)"
        else
          echo "" >> "$CLAUDE_FILE"
          echo "---" >> "$CLAUDE_FILE"
          echo "" >> "$CLAUDE_FILE"
          cat "$SCRIPT_DIR/platforms/claude-code/CLAUDE.md" >> "$CLAUDE_FILE"
          echo "→ Installed: Claude Code (appended to $CLAUDE_FILE)"
        fi
      else
        cp "$SCRIPT_DIR/platforms/claude-code/CLAUDE.md" "$CLAUDE_FILE"
        echo "→ Installed: Claude Code → $CLAUDE_FILE"
      fi
      ;;
    codex)
      CODEX_DIR="$HOME"
      CODEX_FILE="$CODEX_DIR/AGENTS.md"
      if [ -f "$CODEX_FILE" ]; then
        if grep -q "Obsidian Personal Knowledge Base" "$CODEX_FILE"; then
          echo "→ Skipped: Codex (already installed in $CODEX_FILE)"
        else
          echo "" >> "$CODEX_FILE"
          echo "---" >> "$CODEX_FILE"
          echo "" >> "$CODEX_FILE"
          cat "$SCRIPT_DIR/platforms/codex/AGENTS.md" >> "$CODEX_FILE"
          echo "→ Installed: Codex (appended to $CODEX_FILE)"
        fi
      else
        cp "$SCRIPT_DIR/platforms/codex/AGENTS.md" "$CODEX_FILE"
        echo "→ Installed: Codex → $CODEX_FILE"
      fi
      ;;
    cursor)
      # For Cursor, the .mdc file goes in the project's .cursor/rules/ directory
      # We'll install it globally and let the user copy it to projects
      CURSOR_DIR="$HOME/.cursor/rules"
      mkdir -p "$CURSOR_DIR"
      cp "$SCRIPT_DIR/platforms/cursor/obsidian-kb.mdc" "$CURSOR_DIR/obsidian-kb.mdc"
      echo "→ Installed: Cursor → $CURSOR_DIR/obsidian-kb.mdc"
      echo "  (Copy this to your project's .cursor/rules/ for project-level use)"
      ;;
    *)
      echo "→ Unknown platform: $platform"
      ;;
  esac
done

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Your vault is at: $VAULT_PATH"
echo "Open this folder in Obsidian to start using your knowledge base."
echo ""
echo "To save notes, just tell your AI assistant:"
echo '  "Save this to my knowledge base"'
echo '  "Record this meeting in Obsidian"'
echo '  "Capture this insight"'
