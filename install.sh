#!/bin/bash
# Obsidian Knowledge Base Skill — Universal Installer
#
# Usage:
#   ./install.sh --vault /path/to/vault [--platforms qoderwork,claude-code,codex,cursor,workbuddy]
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
STANDARD_SKILL_DIR="$SCRIPT_DIR/skills/obsidian-knowledge-base"
RETRIEVAL_SKILL_DIR="$SCRIPT_DIR/skills/obsidian-knowledge-retrieval"
SUPPORT_ROOT="$HOME/.obsidian-kb-skill"
CANONICAL_SKILL="$SUPPORT_ROOT/skill"
CANONICAL_RETRIEVAL_SKILL="$SUPPORT_ROOT/retrieval-skill"
RUNTIME_FILE="$SUPPORT_ROOT/runtime.json"
VENDOR_DIR="$SUPPORT_ROOT/vendor"
SETTINGS_FILE="$HOME/.obsidian-kb-settings.json"
VAULT_PATH=""
PLATFORMS="qoderwork,claude-code,codex,cursor,workbuddy"
LOCALE="zh-CN"
FORCE_UPGRADE=false
DO_UNINSTALL=false
PURGE_CONFIG=false
# Install everything except the platform Skill files. Distributing those is the
# only job here that a Skill manager also does; the vendored runtime, the
# interpreter record, the Vault path and the Vault's own structure are not
# provided by any manager, so "just use the manager" yields an install whose
# first helper call fails to import. See #113.
RUNTIME_ONLY=false
PLATFORMS_EXPLICIT=false
PYTHON_BIN=""
# Skill directories left alone because a manager owns them.
MANAGED_SKIPS=0

copy_skill_payload() {
  local source_dir="$1"
  local destination_dir="$2"
  if [ ! -f "$source_dir/SKILL.md" ]; then
    echo "Missing standard Skill payload: $source_dir/SKILL.md" >&2
    return 1
  fi
  rm -rf "$destination_dir"
  mkdir -p "$destination_dir"
  cp -R "$source_dir/." "$destination_dir/"
  rm -f "$destination_dir/header.md"
  find "$destination_dir" -name '.DS_Store' -delete
  find "$destination_dir" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "$destination_dir" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  chmod +x "$destination_dir/scripts/run_helper.py"
}

install_standard_skill() {
  local source_dir="$1"
  local destination="$2"
  # A symlink here was not created by this script, and the two reasons one
  # exists need opposite handling.
  #
  # Pointing into this checkout: someone linked the install location at the
  # source tree. `cp -R` would follow the link and write back into the very
  # payload being installed, so the link must go. `copy_skill_payload` removes
  # it first, which is why this case falls through even without --force.
  #
  # Pointing anywhere else: something owns this location — typically a Skill
  # manager linking it at its own store. Replacing the link ends that ownership
  # silently: this script reports success while the manager reports drift, and
  # neither inspects the other. Skip it and say so. --force is the way to
  # override, matching how --force already governs overwriting templates.
  if [ -L "$destination" ]; then
    local resolved
    resolved=$(cd "$destination" 2>/dev/null && pwd -P || true)
    case "$resolved" in
      "$SCRIPT_DIR"|"$SCRIPT_DIR"/*)
        : # links into this checkout are replaced, never written through
        ;;
      *)
        if [ "$FORCE_UPGRADE" != true ]; then
          local target
          target=$(readlink "$destination" 2>/dev/null || echo "?")
          echo "-> Skipped (managed elsewhere): $destination -> $target"
          MANAGED_SKIPS=$((MANAGED_SKIPS + 1))
          return 0
        fi
        ;;
    esac
  fi
  copy_skill_payload "$source_dir" "$destination"
}

validate_platforms() {
  local platform
  local found=false
  IFS=',' read -ra requested <<< "$PLATFORMS"
  for platform in "${requested[@]}"; do
    platform=$(echo "$platform" | tr -d ' ')
    [ -n "$platform" ] || continue
    found=true
    case "$platform" in
      qoderwork|claude-code|codex|cursor|workbuddy) ;;
      *) echo "Unknown platform: $platform" >&2; return 1 ;;
    esac
  done
  if [ "$found" = false ]; then
    echo "No platforms selected." >&2
    return 1
  fi
}

setup_python_runtime() {
  local candidate="${OBSIDIAN_KB_PYTHON:-}"
  if [ -z "$candidate" ]; then
    if command -v python3 >/dev/null 2>&1; then
      candidate=$(command -v python3)
    elif command -v python >/dev/null 2>&1; then
      candidate=$(command -v python)
    else
      echo "Python 3.11+ is required to install bundled helpers." >&2
      return 1
    fi
  fi
  if ! "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "Python 3.11+ is required; unusable interpreter: $candidate" >&2
    return 1
  fi
  PYTHON_BIN=$("$candidate" -c 'import sys; print(sys.executable)')
  mkdir -p "$SUPPORT_ROOT"
  "$PYTHON_BIN" - "$RUNTIME_FILE" "$PYTHON_BIN" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
python = sys.argv[2]
path.write_text(
    json.dumps({"schema_version": 1, "python": [python]}, indent=2) + "\n",
    encoding="utf-8",
)
PY
  if ! PYTHONPATH="$VENDOR_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -c 'import yaml' 2>/dev/null; then
    echo "-> Installing private PyYAML runtime dependency"
    mkdir -p "$VENDOR_DIR"
    "$PYTHON_BIN" -m pip install --disable-pip-version-check \
      --target "$VENDOR_DIR" "PyYAML>=6"
  fi
}

# Markers used to wrap injected content in shared files (CLAUDE.md, AGENTS.md).
# Idempotent upgrade and clean uninstall both rely on these markers.
MARKER_BEGIN="<!-- BEGIN obsidian-kb-skill -->"
MARKER_END="<!-- END obsidian-kb-skill -->"

validate_marker_file() {
  local target="$1"
  [ -f "$target" ] || return 0
  local begin_count end_count begin_line end_line
  begin_count=$(grep -cFx "$MARKER_BEGIN" "$target" || true)
  end_count=$(grep -cFx "$MARKER_END" "$target" || true)
  if [ "$begin_count" -eq 0 ] && [ "$end_count" -eq 0 ]; then
    return 0
  fi
  if [ "$begin_count" -ne 1 ] || [ "$end_count" -ne 1 ]; then
    echo "Malformed marker block in $target: expected exactly one begin/end pair; file was not modified." >&2
    return 2
  fi
  begin_line=$(grep -nFx "$MARKER_BEGIN" "$target" | cut -d: -f1)
  end_line=$(grep -nFx "$MARKER_END" "$target" | cut -d: -f1)
  if [ "$begin_line" -ge "$end_line" ]; then
    echo "Malformed marker block in $target: markers are reversed; file was not modified." >&2
    return 2
  fi
}

# Insert or replace a marker-wrapped block in a target file.
# Args: $1 = target file, $2 = source file containing the body to inject
# Echoes one of: installed | upgraded | appended
set_marker_block() {
  local target="$1"
  local src="$2"
  local body
  body=$(cat "$src")
  local wrapped
  wrapped=$'\n'"$MARKER_BEGIN"$'\n'"$body"$'\n'"$MARKER_END"$'\n'

  validate_marker_file "$target" || return 2

  if [ ! -f "$target" ]; then
    printf '%s' "${wrapped#$'\n'}" > "$target"
    echo "installed"
    return
  fi

  if grep -qFx "$MARKER_BEGIN" "$target"; then
    # Replace existing block via awk (portable; no GNU-specific sed flags).
    local tmp
    tmp=$(mktemp)
    awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" -v repl_file="$src" '
      BEGIN { in_block = 0; printed = 0 }
      {
        if (!in_block && $0 == begin) {
          in_block = 1
          if (!printed) {
            print begin
            while ((getline line < repl_file) > 0) print line
            close(repl_file)
            print end
            printed = 1
          }
          next
        }
        if (in_block) {
          if ($0 == end) { in_block = 0 }
          next
        }
        print
      }
    ' "$target" > "$tmp"
    mv "$tmp" "$target"
    echo "upgraded"
    return
  fi

  # No existing block: append, separated by a blank line.
  printf '\n%s\n%s\n%s\n' "$MARKER_BEGIN" "$body" "$MARKER_END" >> "$target"
  echo "appended"
}

# Remove a marker-wrapped block (and trailing blank line) from a file.
# If the file becomes empty afterwards, delete it.
# Args: $1 = target file
# Returns 0 if file was modified, 1 otherwise.
remove_marker_block() {
  local target="$1"
  if [ ! -f "$target" ]; then return 1; fi
  validate_marker_file "$target" || return 2
  if ! grep -qFx "$MARKER_BEGIN" "$target"; then return 1; fi
  local tmp
  tmp=$(mktemp)
  awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" '
    BEGIN { in_block = 0 }
    {
      if (!in_block && $0 == begin) { in_block = 1; next }
      if (in_block) {
        if ($0 == end) { in_block = 0 }
        next
      }
      print
    }
  ' "$target" > "$tmp"
  # Strip trailing blank lines, then ensure single terminating newline.
  awk 'NF { last = NR } { lines[NR] = $0 } END { for (i = 1; i <= last; i++) print lines[i] }' "$tmp" > "$target"
  rm -f "$tmp"
  if [ ! -s "$target" ]; then
    rm -f "$target"
  fi
  return 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --vault) VAULT_PATH="$2"; shift 2 ;;
    --platforms) PLATFORMS="$2"; PLATFORMS_EXPLICIT=true; shift 2 ;;
    --locale) LOCALE="$2"; shift 2 ;;
    --force) FORCE_UPGRADE=true; shift ;;
    --runtime-only) RUNTIME_ONLY=true; shift ;;
    --uninstall) DO_UNINSTALL=true; shift ;;
    --purge-config) PURGE_CONFIG=true; shift ;;
    --help)
      echo "Usage:"
      echo "  ./install.sh --vault /path/to/vault"
      echo "  ./install.sh   (reads from .env or env var)"
      echo ""
      echo "Options:"
      echo "  --vault PATH       Path to your Obsidian vault"
      echo "  --platforms LIST   Comma-separated: qoderwork,claude-code,codex,cursor,workbuddy (default: all)"
      echo "  --locale LOCALE    Template language: zh-CN or en (default: zh-CN)"
      echo "  --force            Overwrite existing templates and replace marker-wrapped skill blocks"
      echo "  --runtime-only     Install the runtime, config and Vault structure only;"
      echo "                     write no platform Skill files. Use this when a Skill"
      echo "                     manager owns those locations. Cannot be combined with --platforms"
      echo "  --uninstall        Remove installed skills and legacy marker blocks"
      echo "  --purge-config     With --uninstall, also remove Vault and backup settings"
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

case "$LOCALE" in
  zh-CN|en) ;;
  *) echo "Unsupported locale: $LOCALE (expected zh-CN or en)"; exit 1 ;;
esac

# Two contradictory instructions. Silently honouring one would leave the user
# believing the other took effect, which on a managed machine is exactly the
# wrong belief to hold about whether Skill files were written.
if [ "$RUNTIME_ONLY" = true ] && [ "$PLATFORMS_EXPLICIT" = true ]; then
  echo "--runtime-only writes no platform Skill files, so --platforms has nothing to select." >&2
  echo "Drop one of them: --runtime-only for a manager-owned machine, --platforms otherwise." >&2
  exit 2
fi

validate_platforms

if [ "$DO_UNINSTALL" = true ]; then
  echo ""
  echo "=== Obsidian Knowledge Base Skill Uninstaller ==="
  echo ""
  # Remove QoderWork skill
  QODERWORK_SKILLS="$HOME/.qoderwork/skills/obsidian-knowledge-base"
  if [ -d "$QODERWORK_SKILLS" ]; then
    rm -rf "$QODERWORK_SKILLS"
    echo "-> Removed: QoderWork skill ($QODERWORK_SKILLS)"
  fi
  QODERWORK_RETRIEVAL="$HOME/.qoderwork/skills/obsidian-knowledge-retrieval"
  if [ -d "$QODERWORK_RETRIEVAL" ] || [ -L "$QODERWORK_RETRIEVAL" ]; then
    rm -rf "$QODERWORK_RETRIEVAL"
    echo "-> Removed: QoderWork retrieval skill ($QODERWORK_RETRIEVAL)"
  fi
  # Remove Codex user-level skill without touching sibling skills.
  CODEX_SKILLS="$HOME/.agents/skills/obsidian-knowledge-base"
  if [ -d "$CODEX_SKILLS" ] || [ -L "$CODEX_SKILLS" ]; then
    rm -rf "$CODEX_SKILLS"
    echo "-> Removed: Codex skill ($CODEX_SKILLS)"
  fi
  CODEX_RETRIEVAL="$HOME/.agents/skills/obsidian-knowledge-retrieval"
  if [ -d "$CODEX_RETRIEVAL" ] || [ -L "$CODEX_RETRIEVAL" ]; then
    rm -rf "$CODEX_RETRIEVAL"
    echo "-> Removed: Codex retrieval skill ($CODEX_RETRIEVAL)"
  fi
  # Remove only this WorkBuddy Skill; preserve sibling Skills and symlink targets.
  WORKBUDDY_SKILLS="$HOME/.workbuddy/skills/obsidian-knowledge-base"
  if [ -d "$WORKBUDDY_SKILLS" ] || [ -L "$WORKBUDDY_SKILLS" ]; then
    rm -rf "$WORKBUDDY_SKILLS"
    echo "-> Removed: WorkBuddy skill ($WORKBUDDY_SKILLS)"
  fi
  WORKBUDDY_RETRIEVAL="$HOME/.workbuddy/skills/obsidian-knowledge-retrieval"
  if [ -d "$WORKBUDDY_RETRIEVAL" ] || [ -L "$WORKBUDDY_RETRIEVAL" ]; then
    rm -rf "$WORKBUDDY_RETRIEVAL"
    echo "-> Removed: WorkBuddy retrieval skill ($WORKBUDDY_RETRIEVAL)"
  fi
  # Remove the canonical installed payload, private dependency, and runtime record.
  if [ -d "$SUPPORT_ROOT" ] || [ -L "$SUPPORT_ROOT" ]; then
    rm -rf "$SUPPORT_ROOT"
    echo "-> Removed: Skill support runtime ($SUPPORT_ROOT)"
  fi
  # Remove Cursor rule
  CURSOR_FILE="$HOME/.cursor/rules/obsidian-kb.mdc"
  if [ -f "$CURSOR_FILE" ]; then
    rm -f "$CURSOR_FILE"
    echo "-> Removed: Cursor rule ($CURSOR_FILE)"
  fi
  CURSOR_RETRIEVAL="$HOME/.cursor/skills/obsidian-knowledge-retrieval"
  if [ -d "$CURSOR_RETRIEVAL" ] || [ -L "$CURSOR_RETRIEVAL" ]; then
    rm -rf "$CURSOR_RETRIEVAL"
    echo "-> Removed: Cursor retrieval skill ($CURSOR_RETRIEVAL)"
  fi
  CLAUDE_RETRIEVAL="$HOME/.claude/skills/obsidian-knowledge-retrieval"
  if [ -d "$CLAUDE_RETRIEVAL" ] || [ -L "$CLAUDE_RETRIEVAL" ]; then
    rm -rf "$CLAUDE_RETRIEVAL"
    echo "-> Removed: Claude Code retrieval skill ($CLAUDE_RETRIEVAL)"
  fi
  CLAUDE_SKILLS="$HOME/.claude/skills/obsidian-knowledge-base"
  if [ -d "$CLAUDE_SKILLS" ] || [ -L "$CLAUDE_SKILLS" ]; then
    rm -rf "$CLAUDE_SKILLS"
    echo "-> Removed: Claude Code skill ($CLAUDE_SKILLS)"
  fi
  # Strip marker-wrapped block from Claude Code CLAUDE.md
  if remove_marker_block "$HOME/.claude/CLAUDE.md"; then
    echo "-> Cleaned: Claude Code skill block removed from $HOME/.claude/CLAUDE.md"
  elif [ "$?" -eq 2 ]; then
    exit 1
  fi
  # Strip marker-wrapped block from Codex AGENTS.md
  if remove_marker_block "$HOME/AGENTS.md"; then
    echo "-> Cleaned: Codex skill block removed from $HOME/AGENTS.md"
  elif [ "$?" -eq 2 ]; then
    exit 1
  fi
  # Preserve user configuration by default so reinstall keeps their choices.
  if [ "$PURGE_CONFIG" = true ] && [ -f "$HOME/.obsidian-kb-config" ]; then
    rm -f "$HOME/.obsidian-kb-config"
    echo "-> Removed: Config ($HOME/.obsidian-kb-config)"
  elif [ -f "$HOME/.obsidian-kb-config" ]; then
    echo "-> Preserved: Config ($HOME/.obsidian-kb-config)"
  fi
  if [ "$PURGE_CONFIG" = true ] && { [ -e "$SETTINGS_FILE" ] || [ -L "$SETTINGS_FILE" ]; }; then
    rm -f "$SETTINGS_FILE"
    echo "-> Removed: Backup settings ($SETTINGS_FILE)"
  elif [ -e "$SETTINGS_FILE" ] || [ -L "$SETTINGS_FILE" ]; then
    echo "-> Preserved: Backup settings ($SETTINGS_FILE)"
  fi
  echo ""
  echo "Note: Vault folder and its contents are NOT deleted."
  echo "Uninstall complete."
  exit 0
fi

# Resolve vault path from multiple sources
if [ -z "$VAULT_PATH" ]; then
  # Try .env file in skill directory
  ENV_FILE="$SCRIPT_DIR/.env"
  if [ -f "$ENV_FILE" ]; then
    VAULT_PATH=$(grep -E '^OBSIDIAN_KB_VAULT=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)
    # Trim whitespace
    VAULT_PATH=$(echo "$VAULT_PATH" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # Strip surrounding quotes if present
    VAULT_PATH="${VAULT_PATH%\"}"
    VAULT_PATH="${VAULT_PATH#\"}"
    VAULT_PATH="${VAULT_PATH%\'}"
    VAULT_PATH="${VAULT_PATH#\'}"
    if [ -n "$VAULT_PATH" ]; then
      echo "-> Read vault path from .env: $VAULT_PATH"
    fi
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  if [ -n "$OBSIDIAN_KB_VAULT" ]; then
    VAULT_PATH="$OBSIDIAN_KB_VAULT"
    echo "-> Read vault path from env var: $VAULT_PATH"
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  if [ -f "$HOME/.obsidian-kb-config" ]; then
    VAULT_PATH=$(cat "$HOME/.obsidian-kb-config")
    echo "-> Read vault path from ~/.obsidian-kb-config: $VAULT_PATH"
  fi
fi

if [ -z "$VAULT_PATH" ]; then
  echo "No vault path configured."
  echo "Provide via --vault, .env file, or OBSIDIAN_KB_VAULT env var."
  echo "Run ./install.sh --help for details."
  exit 1
fi

# Validate the bundled helper runtime before mutating the Vault.
setup_python_runtime

# Create the global retention policy once. Exclusive creation preserves every
# user edit and cannot write through a broken symlink that appears concurrently.
if [ ! -e "$SETTINGS_FILE" ] && [ ! -L "$SETTINGS_FILE" ]; then
  "$PYTHON_BIN" - "$SETTINGS_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(
            {"schema_version": 1, "backup": {"keep_per_note": 1}},
            handle,
            indent=2,
        )
        handle.write("\n")
except FileExistsError:
    pass
PY
fi

# Create the Vault when needed, then always store its canonical absolute path.
if [ ! -d "$VAULT_PATH" ]; then
  echo "-> Vault path does not exist, creating: $VAULT_PATH"
  mkdir -p "$VAULT_PATH"
fi
VAULT_PATH="$(cd -P "$VAULT_PATH" && pwd -P)"

echo "=== Obsidian Knowledge Base Skill Installer ==="
echo "Vault path: $VAULT_PATH"
if [ "$RUNTIME_ONLY" = true ]; then
  echo "Platforms:  (none — runtime only)"
else
  echo "Platforms:  $PLATFORMS"
fi
echo "Locale:     $LOCALE"
if [ "$FORCE_UPGRADE" = true ]; then echo "Mode:       FORCE (overwrite existing templates and skill blocks)"; fi
echo ""

# Step 1: Save vault config
echo "-> Saving vault config to ~/.obsidian-kb-config"
echo "$VAULT_PATH" > "$HOME/.obsidian-kb-config"

# Install one canonical support copy used by compatibility adapters and as the
# source for identical Codex/QoderWork payloads.
copy_skill_payload "$STANDARD_SKILL_DIR" "$CANONICAL_SKILL"
copy_skill_payload "$RETRIEVAL_SKILL_DIR" "$CANONICAL_RETRIEVAL_SKILL"

# Step 2: Initialize vault structure if not exists
echo "-> Checking vault structure..."
FOLDERS=("00-Inbox" "10-Work" "15-Daily" "20-Learning" "30-Insights" "40-Projects" "50-People" "90-Archive" "95-Sources" "Templates" "Attachments")
for folder in "${FOLDERS[@]}"; do
  mkdir -p "$VAULT_PATH/$folder"
done

# Copy templates if not exists
TEMPLATE_FILES=("daily-note.md" "meeting-note.md" "learning-note.md" "project-note.md" "web-clip.md" "insight-note.md" "person-note.md" "digest-note.md")
TEMPLATE_NAMES=("Daily Note.md" "Meeting Note.md" "Learning Note.md" "Project Note.md" "Web Clip.md" "Insight Note.md" "Person Note.md" "Digest Note.md")

if [ "$FORCE_UPGRADE" = true ]; then
  echo "-> Upgrade mode: will overwrite existing templates"
fi

for i in "${!TEMPLATE_FILES[@]}"; do
  if [ "$LOCALE" = "en" ]; then
    src="$CANONICAL_SKILL/assets/templates/en/${TEMPLATE_FILES[$i]}"
  else
    src="$CANONICAL_SKILL/assets/templates/${TEMPLATE_FILES[$i]}"
  fi
  dst="$VAULT_PATH/Templates/${TEMPLATE_NAMES[$i]}"
  if [ -f "$src" ]; then
    if [ ! -f "$dst" ]; then
      cp "$src" "$dst"
      echo "  Created template: ${TEMPLATE_NAMES[$i]}"
    elif [ "$FORCE_UPGRADE" = true ]; then
      cp "$src" "$dst"
      echo "  Updated template: ${TEMPLATE_NAMES[$i]}"
    fi
  fi
done

# Detect Folder Index before generating index files. The plugin's graph
# implementation requires native folder-named indexes for nested edges.
INDEX_STRATEGY="dataview"
ROOT_INDEX_FILE="INDEX.md"
CUSTOM_INDEX_FILENAME="INDEX"
PLUGIN_LIST="$VAULT_PATH/.obsidian/community-plugins.json"
FOLDER_INDEX_DATA="$VAULT_PATH/.obsidian/plugins/obsidian-folder-index/data.json"
if [ -f "$PLUGIN_LIST" ] && grep -q '"obsidian-folder-index"' "$PLUGIN_LIST" && [ -f "$FOLDER_INDEX_DATA" ]; then
  ROOT_INDEX_FILE=$(sed -nE 's/.*"rootIndexFile"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$FOLDER_INDEX_DATA" | head -1)
  CUSTOM_INDEX_FILENAME=$(sed -nE 's/.*"indexFilename"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$FOLDER_INDEX_DATA" | head -1)
  user_specified=$(sed -nE 's/.*"indexFileUserSpecified"[[:space:]]*:[[:space:]]*(true|false).*/\1/p' "$FOLDER_INDEX_DATA" | head -1)
  ROOT_INDEX_FILE="${ROOT_INDEX_FILE:-INDEX.md}"
  CUSTOM_INDEX_FILENAME="${CUSTOM_INDEX_FILENAME:-INDEX}"
  if [ "$user_specified" = "false" ]; then
    INDEX_STRATEGY="folder-index-native"
    echo "-> Folder Index detected: using native folder-named indexes"
  else
    INDEX_STRATEGY="folder-index-custom"
    echo "-> Folder Index detected: using custom index name $CUSTOM_INDEX_FILENAME.md"
    echo "   WARNING: Folder Index 1.0.30 cannot build nested Graph View edges with one custom index filename."
  fi
fi

index_filename_for_folder() {
  local folder="$1"
  case "$INDEX_STRATEGY" in
    folder-index-native) printf '%s.md' "${folder##*/}" ;;
    folder-index-custom) printf '%s.md' "$CUSTOM_INDEX_FILENAME" ;;
    *) printf 'INDEX.md' ;;
  esac
}

# Create configuration-aware index files if not present.
create_index() {
  local folder="$1"
  local title="$2"
  local desc="$3"
  local index_name
  index_name=$(index_filename_for_folder "$folder")
  local index_path="$VAULT_PATH/$folder/$index_name"
  if [ -f "$index_path" ]; then
    return
  fi
  if [[ "$INDEX_STRATEGY" == folder-index-* ]]; then
    {
      printf '%s\n' '---' 'type: folder-index' 'tags: [moc]' '---' ''
      printf '# %s\n\n%s\n\n' "$title" "$desc"
      printf '%s\n' '```folder-index-content' '```'
    } > "$index_path"
  else
    cat > "$index_path" << INDEXEOF
---
type: moc
tags: [moc]
---

# $title

$desc

## Notes <!-- managed by obsidian-kb-skill: dataview -->

> If the [Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview) is installed, the table below auto-refreshes from this folder's notes. Otherwise, you'll see the code block as plain text — install Dataview to activate, or replace this block with a manual list.

\`\`\`dataview
TABLE date, tags
FROM "$folder"
WHERE file.name != "INDEX"
SORT date DESC
LIMIT 50
\`\`\`

## Manual Notes (fallback)

<!-- Agents append here when no Dataview block is present above. -->

---
INDEXEOF
  fi
  echo "  Created index: $folder/$index_name"
}

create_index "00-Inbox" "Inbox" "Quick capture zone. Process later."
create_index "10-Work" "Work" "Meeting notes and work documents."
create_index "15-Daily" "Daily" "Daily notes, journals, morning plans."
create_index "20-Learning" "Learning" "Articles, courses, and study materials."
create_index "30-Insights" "Insights" "Analysis and AI-generated insights."
create_index "40-Projects" "Projects" "Active project context documents."
create_index "50-People" "People" "Contacts and team member notes."
create_index "90-Archive" "Archive" "Completed and inactive notes."

# Create the configured root index if it does not exist.
root_link() {
  local folder="$1"
  printf '%s/%s' "$folder" "$(index_filename_for_folder "$folder" | sed 's/\.md$//')"
}
ROOT_INDEX_PATH="$VAULT_PATH/$ROOT_INDEX_FILE"
if [ ! -f "$ROOT_INDEX_PATH" ]; then
  cat > "$ROOT_INDEX_PATH" << MAINEOF
---
type: moc
tags: [index, moc]
---

# My Knowledge Base

## Quick Navigation

- [[$(root_link "00-Inbox")|Inbox]] — Quick capture
- [[$(root_link "10-Work")|Work]] — Meeting notes, work docs
- [[$(root_link "15-Daily")|Daily]] — Daily notes, journals
- [[$(root_link "20-Learning")|Learning]] — Articles, study notes
- [[$(root_link "30-Insights")|Insights]] — Analysis, AI insights
- [[$(root_link "40-Projects")|Projects]] — Active projects
- [[$(root_link "50-People")|People]] — Contacts, team notes
- [[$(root_link "90-Archive")|Archive]] — Completed and inactive notes
MAINEOF
  if [[ "$INDEX_STRATEGY" == folder-index-* ]]; then
    printf '\n```folder-index-content\n```\n' >> "$ROOT_INDEX_PATH"
  fi
  echo "  Created main index: $ROOT_INDEX_FILE"
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

echo "-> Vault structure ready."
echo ""

# Step 3: Install platform files
if [ "$RUNTIME_ONLY" = true ]; then
  PLATFORM_LIST=()
  echo "-> Runtime only: no platform Skill files written."
  echo "   Install the Skills through your Skill manager; this run supplied the"
  echo "   vendored runtime, interpreter record, Vault config and Vault structure,"
  echo "   which no manager provides."
else
  IFS=',' read -ra PLATFORM_LIST <<< "$PLATFORMS"
fi

for platform in "${PLATFORM_LIST[@]+"${PLATFORM_LIST[@]}"}"; do
  platform=$(echo "$platform" | tr -d ' ')
  case $platform in
    qoderwork)
      QODERWORK_SKILLS="$HOME/.qoderwork/skills/obsidian-knowledge-base"
      QODERWORK_RETRIEVAL="$HOME/.qoderwork/skills/obsidian-knowledge-retrieval"
      install_standard_skill "$CANONICAL_SKILL" "$QODERWORK_SKILLS"
      install_standard_skill "$CANONICAL_RETRIEVAL_SKILL" "$QODERWORK_RETRIEVAL"
      echo "-> Installed: QoderWork skill -> $QODERWORK_SKILLS/SKILL.md"
      echo "-> Installed: QoderWork retrieval -> $QODERWORK_RETRIEVAL/SKILL.md"
      ;;
    claude-code)
      CLAUDE_DIR="$HOME/.claude"
      mkdir -p "$CLAUDE_DIR"
      # Claude Code discovers skills natively, like Codex and WorkBuddy. An
      # always-loaded CLAUDE.md block charged the full instruction cost to every
      # conversation, which is exactly what the lazy entry file avoids.
      # Migrate first: drop the legacy always-loaded block so the instructions
      # are not delivered from two places at once. A malformed marker aborts
      # before anything is installed, leaving the user's file untouched and the
      # platform in its previous state rather than half-migrated.
      if remove_marker_block "$CLAUDE_DIR/CLAUDE.md"; then
        echo "-> Migrated: removed legacy Claude Code block from $CLAUDE_DIR/CLAUDE.md"
      elif [ "$?" -eq 2 ]; then
        exit 1
      fi
      CLAUDE_SKILLS="$CLAUDE_DIR/skills/obsidian-knowledge-base"
      install_standard_skill "$CANONICAL_SKILL" "$CLAUDE_SKILLS"
      echo "-> Installed: Claude Code skill -> $CLAUDE_SKILLS/SKILL.md"
      CLAUDE_RETRIEVAL="$CLAUDE_DIR/skills/obsidian-knowledge-retrieval"
      install_standard_skill "$CANONICAL_RETRIEVAL_SKILL" "$CLAUDE_RETRIEVAL"
      echo "-> Installed: Claude Code retrieval -> $CLAUDE_RETRIEVAL/SKILL.md"
      ;;
    codex)
      CODEX_SKILLS="$HOME/.agents/skills/obsidian-knowledge-base"
      CODEX_RETRIEVAL="$HOME/.agents/skills/obsidian-knowledge-retrieval"
      install_standard_skill "$CANONICAL_SKILL" "$CODEX_SKILLS"
      install_standard_skill "$CANONICAL_RETRIEVAL_SKILL" "$CODEX_RETRIEVAL"
      echo "-> Installed: Codex skill -> $CODEX_SKILLS/SKILL.md"
      echo "-> Installed: Codex retrieval -> $CODEX_RETRIEVAL/SKILL.md"
      ;;
    workbuddy)
      WORKBUDDY_SKILLS="$HOME/.workbuddy/skills/obsidian-knowledge-base"
      WORKBUDDY_RETRIEVAL="$HOME/.workbuddy/skills/obsidian-knowledge-retrieval"
      install_standard_skill "$CANONICAL_SKILL" "$WORKBUDDY_SKILLS"
      install_standard_skill "$CANONICAL_RETRIEVAL_SKILL" "$WORKBUDDY_RETRIEVAL"
      echo "-> Installed: WorkBuddy skill -> $WORKBUDDY_SKILLS/SKILL.md"
      echo "-> Installed: WorkBuddy retrieval -> $WORKBUDDY_RETRIEVAL/SKILL.md"
      ;;
    cursor)
      CURSOR_DIR="$HOME/.cursor/rules"
      mkdir -p "$CURSOR_DIR"
      cp "$SCRIPT_DIR/platforms/cursor/obsidian-kb.mdc" "$CURSOR_DIR/obsidian-kb.mdc"
      echo "-> Installed: Cursor -> $CURSOR_DIR/obsidian-kb.mdc"
      echo "  (Copy this to your project's .cursor/rules/ for project-level use)"
      CURSOR_RETRIEVAL="$HOME/.cursor/skills/obsidian-knowledge-retrieval"
      install_standard_skill "$CANONICAL_RETRIEVAL_SKILL" "$CURSOR_RETRIEVAL"
      echo "-> Installed: Cursor retrieval -> $CURSOR_RETRIEVAL/SKILL.md"
      ;;
    *)
      echo "-> Unknown platform: $platform" >&2
      exit 1
      ;;
  esac
done

# Verify the installed product from a directory unrelated to the checkout.
if [ ! -f "$CANONICAL_SKILL/references/note-creation.md" ]; then
  echo "Post-install verification failed: missing bundled reference." >&2
  exit 1
fi
if [ ! -f "$CANONICAL_RETRIEVAL_SKILL/references/search.md" ]; then
  echo "Post-install verification failed: missing bundled retrieval reference." >&2
  exit 1
fi
VERIFY_DIR=$(mktemp -d)
if ! (
  cd "$VERIFY_DIR"
  PYTHONPATH="" "$PYTHON_BIN" "$CANONICAL_SKILL/scripts/run_helper.py" \
    doctor --json >/dev/null &&
  PYTHONPATH="" "$PYTHON_BIN" "$CANONICAL_SKILL/scripts/run_helper.py" \
    vault-info "$VAULT_PATH" --json >/dev/null &&
  PYTHONPATH="" "$PYTHON_BIN" "$CANONICAL_RETRIEVAL_SKILL/scripts/run_helper.py" \
    doctor --json >/dev/null &&
  PYTHONPATH="" "$PYTHON_BIN" "$CANONICAL_RETRIEVAL_SKILL/scripts/run_helper.py" \
    vault-info "$VAULT_PATH" --json >/dev/null &&
  PYTHONPATH="" "$PYTHON_BIN" "$CANONICAL_RETRIEVAL_SKILL/scripts/run_helper.py" \
    search-vault "$VAULT_PATH" --query "__obsidian_kb_install_probe__" --json >/dev/null
); then
  rm -rf "$VERIFY_DIR"
  echo "Post-install verification failed: a bundled write or retrieval helper is unusable." >&2
  exit 1
fi
rm -rf "$VERIFY_DIR"
echo "-> Installed write and retrieval Skill runtimes verified."

echo ""
if [ "$MANAGED_SKIPS" -gt 0 ]; then
  echo ""
  echo "-> $MANAGED_SKIPS Skill location(s) are managed by another tool and were left untouched."
  echo "   Refresh them through that tool so it picks up this version,"
  echo "   or re-run with --force to replace them with a direct install."
fi

echo "=== Installation complete! ==="
echo ""
echo "Your vault is at: $VAULT_PATH"
echo "Open this folder in Obsidian to start using your knowledge base."
echo "Diagnose write Skill:     $CANONICAL_SKILL/scripts/run_helper.py doctor --json"
echo "Diagnose retrieval Skill: $CANONICAL_RETRIEVAL_SKILL/scripts/run_helper.py doctor --json"
echo ""
echo "To save notes, just tell your AI assistant:"
echo '  "Save this to my knowledge base"'
echo '  "Record this meeting in Obsidian"'
echo '  "Capture this insight"'
