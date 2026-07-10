# Obsidian Knowledge Base Skill -- PowerShell Installer
#
# Usage:
#   .\install.ps1 -VaultPath "D:\MyKnowledgeBase"
#   .\install.ps1    # reads vault path from .env file
#
# Configuration sources (checked in order):
#   1. -VaultPath parameter
#   2. OBSIDIAN_KB_VAULT in .env (same directory as this script)
#   3. OBSIDIAN_KB_VAULT environment variable
#   4. ~/.obsidian-kb-config (from previous install)

param(
    [Parameter(Mandatory=$false)]
    [string]$VaultPath,

    [string]$Platforms = "qoderwork,claude-code,codex,cursor",

    [ValidateSet("zh-CN", "en")]
    [string]$Locale = "zh-CN",

    [switch]$Force,

    [switch]$Help,

    [switch]$Uninstall,

    [switch]$PurgeConfig
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SupportRoot = Join-Path $env:USERPROFILE ".obsidian-kb-skill"
$CanonicalSkill = Join-Path $SupportRoot "skill"
$RuntimeFile = Join-Path $SupportRoot "runtime.json"
$VendorDir = Join-Path $SupportRoot "vendor"
$SettingsFile = Join-Path $env:USERPROFILE ".obsidian-kb-settings.json"

# Markers used to wrap injected content in shared files (CLAUDE.md, AGENTS.md).
# These let us upgrade and uninstall idempotently without touching the user's other content.
$MarkerBegin = "<!-- BEGIN obsidian-kb-skill -->"
$MarkerEnd   = "<!-- END obsidian-kb-skill -->"

# UTF-8 (no BOM) encoder reused by every text write below.
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

function Read-Text {
    param([string]$Path)
    return [System.IO.File]::ReadAllText($Path)
}

function Copy-SkillPayload {
    param(
        [string]$SourceDirectory,
        [string]$DestinationDirectory
    )
    if (-not (Test-Path (Join-Path $SourceDirectory "SKILL.md"))) {
        throw "Missing standard Skill payload: $SourceDirectory\SKILL.md"
    }
    if (Test-Path $DestinationDirectory) {
        Remove-Item $DestinationDirectory -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath $SourceDirectory -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $DestinationDirectory -Recurse -Force
    }
    $header = Join-Path $DestinationDirectory "header.md"
    if (Test-Path $header) { Remove-Item $header -Force }
    Get-ChildItem -LiteralPath $DestinationDirectory -Recurse -Force | Where-Object {
        $_.Name -eq ".DS_Store" -or $_.Name -eq "__pycache__" -or
        $_.Extension -eq ".pyc" -or $_.Extension -eq ".pyo"
    } | Sort-Object { $_.FullName.Length } -Descending | Remove-Item -Recurse -Force
}

function Install-StandardSkill {
    param([string]$DestinationDirectory)
    Copy-SkillPayload -SourceDirectory $CanonicalSkill -DestinationDirectory $DestinationDirectory
}

function Test-PythonCommand {
    param([string[]]$Command)
    $executable = $Command[0]
    $prefix = @($Command | Select-Object -Skip 1)
    try {
        & $executable @prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Initialize-PythonRuntime {
    $candidates = @()
    if ($env:OBSIDIAN_KB_PYTHON) {
        $candidates += ,@($env:OBSIDIAN_KB_PYTHON)
    } else {
        foreach ($name in @("python", "python3")) {
            $command = Get-Command $name -ErrorAction SilentlyContinue
            if ($command) { $candidates += ,@($command.Source) }
        }
        $py = Get-Command "py" -ErrorAction SilentlyContinue
        if ($py) { $candidates += ,@($py.Source, "-3") }
    }

    $selected = $null
    foreach ($candidate in $candidates) {
        if (Test-PythonCommand -Command $candidate) {
            $selected = $candidate
            break
        }
    }
    if (-not $selected) {
        throw "Python 3.11+ is required to install bundled helpers. Set OBSIDIAN_KB_PYTHON to a usable interpreter."
    }

    $executable = $selected[0]
    $prefix = @($selected | Select-Object -Skip 1)
    $resolved = (& $executable @prefix -c "import sys; print(sys.executable)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $resolved) {
        throw "Could not resolve the selected Python interpreter."
    }
    New-Item -ItemType Directory -Path $SupportRoot -Force | Out-Null
    $runtime = @{
        schema_version = 1
        python = @($resolved)
    } | ConvertTo-Json
    Write-Utf8NoBom -Path $RuntimeFile -Content ($runtime + "`n")

    $oldPythonPath = $env:PYTHONPATH
    try {
        if ($oldPythonPath) {
            $env:PYTHONPATH = $VendorDir + [System.IO.Path]::PathSeparator + $oldPythonPath
        } else {
            $env:PYTHONPATH = $VendorDir
        }
        & $resolved -c "import yaml" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "-> Installing private PyYAML runtime dependency" -ForegroundColor Cyan
            New-Item -ItemType Directory -Path $VendorDir -Force | Out-Null
            & $resolved -m pip install --disable-pip-version-check --target $VendorDir "PyYAML>=6" | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Failed to install private PyYAML dependency." }
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
    return $resolved
}

function Assert-ValidMarkerBlock {
    param([string]$TargetFile)
    if (-not (Test-Path $TargetFile)) { return }
    $existing = Read-Text -Path $TargetFile
    $beginPattern = '(?m)^' + [regex]::Escape($MarkerBegin) + '\r?$'
    $endPattern = '(?m)^' + [regex]::Escape($MarkerEnd) + '\r?$'
    $begins = [regex]::Matches($existing, $beginPattern)
    $ends = [regex]::Matches($existing, $endPattern)
    if ($begins.Count -eq 0 -and $ends.Count -eq 0) { return }
    if ($begins.Count -ne 1 -or $ends.Count -ne 1) {
        throw "Malformed marker block in $TargetFile`: expected exactly one begin/end pair; file was not modified."
    }
    if ($begins[0].Index -ge $ends[0].Index) {
        throw "Malformed marker block in $TargetFile`: markers are reversed; file was not modified."
    }
}

# Insert or replace a marker-wrapped block inside an existing file.
# - If file does not exist: write the block as the entire file.
# - If file exists and contains the markers: replace the block in place.
# - If file exists without markers: append the block (separated by a blank line).
function Set-MarkerBlock {
    param(
        [string]$TargetFile,
        [string]$BlockBody
    )
    $wrapped = "$MarkerBegin`n$BlockBody`n$MarkerEnd"
    Assert-ValidMarkerBlock -TargetFile $TargetFile
    if (-not (Test-Path $TargetFile)) {
        Write-Utf8NoBom -Path $TargetFile -Content "$wrapped`n"
        return "installed"
    }
    $existing = Read-Text -Path $TargetFile
    $pattern = '(?ms)^' + [regex]::Escape($MarkerBegin) + '\r?\n.*?^' + [regex]::Escape($MarkerEnd) + '\r?$'
    if ([regex]::IsMatch($existing, $pattern)) {
        # Use a MatchEvaluator so the wrapped block is treated as a literal string
        # (avoids $1 / $& substitution surprises inside the replacement text).
        $updated = [regex]::Replace($existing, $pattern, { param($m) $wrapped })
        Write-Utf8NoBom -Path $TargetFile -Content $updated
        return "upgraded"
    }
    $trimmed = $existing.TrimEnd("`r","`n")
    $combined = "$trimmed`n`n$wrapped`n"
    Write-Utf8NoBom -Path $TargetFile -Content $combined
    return "appended"
}

# Remove a marker-wrapped block (and any single trailing blank line it leaves behind).
# Returns $true if the file was modified.
function Remove-MarkerBlock {
    param([string]$TargetFile)
    if (-not (Test-Path $TargetFile)) { return $false }
    Assert-ValidMarkerBlock -TargetFile $TargetFile
    $existing = Read-Text -Path $TargetFile
    $pattern = '(?ms)(\r?\n)*^' + [regex]::Escape($MarkerBegin) + '\r?\n.*?^' + [regex]::Escape($MarkerEnd) + '\r?$(\r?\n)*'
    if (-not [regex]::IsMatch($existing, $pattern)) { return $false }
    $stripped = [regex]::Replace($existing, $pattern, "`n").TrimEnd("`r","`n") + "`n"
    if ($stripped.Trim().Length -eq 0) {
        Remove-Item $TargetFile -Force
    } else {
        Write-Utf8NoBom -Path $TargetFile -Content $stripped
    }
    return $true
}

if ($Help) {
    Write-Host ""
    Write-Host "Obsidian Knowledge Base Skill Installer" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\install.ps1 -VaultPath `"D:\MyKnowledgeBase`""
    Write-Host "  .\install.ps1    # reads vault path from .env or config"
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -VaultPath PATH    Path to your Obsidian vault"
    Write-Host "  -Platforms LIST    Comma-separated: qoderwork,claude-code,codex,cursor (default: all)"
    Write-Host "  -Locale LOCALE     Template language: zh-CN or en (default: zh-CN)"
    Write-Host "  -Force             Overwrite existing templates and refresh installed skill content"
    Write-Host "  -Uninstall         Remove installed skills and legacy marker blocks"
    Write-Host "  -PurgeConfig       With -Uninstall, also remove Vault and backup settings"
    Write-Host "  -Help              Show this help message"
    Write-Host ""
    Write-Host "Configuration sources (checked in order):"
    Write-Host "  1. -VaultPath parameter"
    Write-Host "  2. OBSIDIAN_KB_VAULT in .env (skill directory)"
    Write-Host "  3. OBSIDIAN_KB_VAULT environment variable"
    Write-Host "  4. ~/.obsidian-kb-config (from previous install)"
    exit 0
}

$platformList = @($Platforms -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$validPlatforms = @("qoderwork", "claude-code", "codex", "cursor")
if ($platformList.Count -eq 0) { throw "No platforms selected." }
foreach ($platform in $platformList) {
    if ($validPlatforms -notcontains $platform) {
        throw "Unknown platform: $platform"
    }
}

if ($Uninstall) {
    Write-Host ""
    Write-Host "=== Obsidian Knowledge Base Skill Uninstaller ===" -ForegroundColor Yellow
    Write-Host ""

    # Remove QoderWork skill
    $skillDir = Join-Path $env:USERPROFILE ".qoderwork\skills\obsidian-knowledge-base"
    if (Test-Path $skillDir) {
        Remove-Item $skillDir -Recurse -Force
        Write-Host "-> Removed: QoderWork skill ($skillDir)" -ForegroundColor Green
    }

    # Remove Codex user-level skill without touching sibling skills.
    $codexSkillDir = Join-Path $env:USERPROFILE ".agents\skills\obsidian-knowledge-base"
    if (Test-Path $codexSkillDir) {
        Remove-Item $codexSkillDir -Recurse -Force
        Write-Host "-> Removed: Codex skill ($codexSkillDir)" -ForegroundColor Green
    }

    if (Test-Path $SupportRoot) {
        Remove-Item $SupportRoot -Recurse -Force
        Write-Host "-> Removed: Skill support runtime ($SupportRoot)" -ForegroundColor Green
    }

    # Remove Cursor rule
    $cursorFile = Join-Path $env:USERPROFILE ".cursor\rules\obsidian-kb.mdc"
    if (Test-Path $cursorFile) {
        Remove-Item $cursorFile -Force
        Write-Host "-> Removed: Cursor rule ($cursorFile)" -ForegroundColor Green
    }

    # Strip marker-wrapped block from Claude Code CLAUDE.md
    $claudeFile = Join-Path $env:USERPROFILE ".claude\CLAUDE.md"
    if (Remove-MarkerBlock -TargetFile $claudeFile) {
        Write-Host "-> Cleaned: Claude Code skill block removed from $claudeFile" -ForegroundColor Green
    }

    # Strip marker-wrapped block from Codex AGENTS.md
    $codexFile = Join-Path $env:USERPROFILE "AGENTS.md"
    if (Remove-MarkerBlock -TargetFile $codexFile) {
        Write-Host "-> Cleaned: Codex skill block removed from $codexFile" -ForegroundColor Green
    }

    # Preserve user configuration by default so reinstall keeps their choices.
    $configFile = Join-Path $env:USERPROFILE ".obsidian-kb-config"
    if ($PurgeConfig -and (Test-Path $configFile)) {
        Remove-Item $configFile -Force
        Write-Host "-> Removed: Config ($configFile)" -ForegroundColor Green
    } elseif (Test-Path $configFile) {
        Write-Host "-> Preserved: Config ($configFile)" -ForegroundColor Cyan
    }
    $settingsItem = Get-Item -LiteralPath $SettingsFile -Force -ErrorAction SilentlyContinue
    if ($PurgeConfig -and $null -ne $settingsItem) {
        Remove-Item -LiteralPath $SettingsFile -Force
        Write-Host "-> Removed: Backup settings ($SettingsFile)" -ForegroundColor Green
    } elseif ($null -ne $settingsItem) {
        Write-Host "-> Preserved: Backup settings ($SettingsFile)" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "Note: Vault folder and its contents are NOT deleted." -ForegroundColor Yellow
    Write-Host "Uninstall complete." -ForegroundColor Cyan
    exit 0
}

# Resolve vault path from multiple sources
if (-not $VaultPath) {
    # Try .env file in skill directory
    $envFile = Join-Path $ScriptDir ".env"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile
        foreach ($line in $envContent) {
            if ($line -match '^\s*OBSIDIAN_KB_VAULT\s*=\s*(.+)$') {
                $VaultPath = $Matches[1].Trim()
                # Remove surrounding quotes if present
                $VaultPath = $VaultPath -replace '^["'']|["'']$', ''
                if ($VaultPath) {
                    Write-Host "-> Read vault path from .env: $VaultPath" -ForegroundColor Cyan
                }
            }
        }
    }
}

if (-not $VaultPath) {
    # Try environment variable
    $envVault = $env:OBSIDIAN_KB_VAULT
    if ($envVault) {
        $VaultPath = $envVault
        Write-Host "-> Read vault path from env var: $VaultPath" -ForegroundColor Cyan
    }
}

if (-not $VaultPath) {
    # Try previous config
    $configFile = Join-Path $env:USERPROFILE ".obsidian-kb-config"
    if (Test-Path $configFile) {
        $VaultPath = (Get-Content $configFile -Raw).Trim()
        if ($VaultPath) {
            Write-Host "-> Read vault path from ~/.obsidian-kb-config: $VaultPath" -ForegroundColor Cyan
        }
    }
}

if (-not $VaultPath) {
    Write-Host "No vault path configured." -ForegroundColor Red
    Write-Host "Provide via -VaultPath, .env file, or OBSIDIAN_KB_VAULT env var."
    Write-Host "Run .\install.ps1 -Help for help."
    exit 1
}

$PythonExecutable = Initialize-PythonRuntime

# Create the global retention policy exactly once. Python's exclusive-create
# mode preserves user edits and refuses to write through an existing symlink.
$InitializeSettings = @'
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
'@
& $PythonExecutable -c $InitializeSettings $SettingsFile
if ($LASTEXITCODE -ne 0) { throw "Could not initialize global backup settings." }

Write-Host ""
Write-Host "=== Obsidian Knowledge Base Skill Installer ===" -ForegroundColor Cyan
Write-Host "Vault path: $VaultPath"
Write-Host "Platforms:  $Platforms"
Write-Host "Locale:     $Locale"
if ($Force) { Write-Host "Mode:       FORCE (overwrite existing templates and skill blocks)" -ForegroundColor Yellow }
Write-Host ""

# Create the Vault when needed, then always save its canonical absolute path.
if (-not (Test-Path $VaultPath)) {
    Write-Host "-> Vault path does not exist, creating: $VaultPath" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $VaultPath -Force | Out-Null
}
$VaultPath = (Resolve-Path $VaultPath).Path

# Step 1: Save vault config
$configFile = Join-Path $env:USERPROFILE ".obsidian-kb-config"
Write-Host "-> Saving vault config to $configFile"
Write-Utf8NoBom -Path $configFile -Content $VaultPath

# Install one canonical support copy used by compatibility adapters and as the
# source for identical Codex/QoderWork payloads.
$standardSkillDir = Join-Path $ScriptDir "skills\obsidian-knowledge-base"
Copy-SkillPayload -SourceDirectory $standardSkillDir -DestinationDirectory $CanonicalSkill

# Step 2: Initialize vault structure
Write-Host "-> Checking vault structure..."
$folders = @("00-Inbox", "10-Work", "15-Daily", "20-Learning", "30-Insights", "40-Projects", "50-People", "90-Archive", "Templates", "Attachments")
foreach ($folder in $folders) {
    $path = Join-Path $VaultPath $folder
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

# Copy templates
$templateMap = @{
    "daily-note.md" = "Daily Note.md"
    "meeting-note.md" = "Meeting Note.md"
    "learning-note.md" = "Learning Note.md"
    "project-note.md" = "Project Note.md"
    "web-clip.md" = "Web Clip.md"
    "insight-note.md" = "Insight Note.md"
    "person-note.md" = "Person Note.md"
    "digest-note.md" = "Digest Note.md"
}

# Legacy upgrade flag support (env var or string sentinel) -- superseded by -Force switch.
$forceUpgrade = $Force.IsPresent
if (-not $forceUpgrade -and ($env:OBSIDIAN_KB_UPGRADE -eq "1")) {
    $forceUpgrade = $true
}
if ($forceUpgrade -and -not $Force.IsPresent) {
    Write-Host "-> Upgrade mode (legacy OBSIDIAN_KB_UPGRADE=1)" -ForegroundColor Yellow
}

foreach ($src in $templateMap.Keys) {
    if ($Locale -eq "en") {
        $srcPath = Join-Path $CanonicalSkill "assets\templates\en\$src"
    } else {
        $srcPath = Join-Path $CanonicalSkill "assets\templates\$src"
    }
    $dstPath = Join-Path $VaultPath "Templates\$($templateMap[$src])"
    if (Test-Path $srcPath) {
        if (-not (Test-Path $dstPath)) {
            Copy-Item $srcPath $dstPath
            Write-Host "  Created template: $($templateMap[$src])"
        } elseif ($forceUpgrade) {
            Copy-Item $srcPath $dstPath -Force
            Write-Host "  Updated template: $($templateMap[$src])"
        }
    }
}

# Detect Folder Index before generating index files.
$indexStrategy = "dataview"
$rootIndexFile = "INDEX.md"
$customIndexFilename = "INDEX"
$pluginListPath = Join-Path $VaultPath ".obsidian\community-plugins.json"
$folderIndexDataPath = Join-Path $VaultPath ".obsidian\plugins\obsidian-folder-index\data.json"
if ((Test-Path $pluginListPath) -and (Test-Path $folderIndexDataPath)) {
    try {
        $enabledPlugins = Get-Content $pluginListPath -Raw | ConvertFrom-Json
        if ($enabledPlugins -contains "obsidian-folder-index") {
            $folderIndexSettings = Get-Content $folderIndexDataPath -Raw | ConvertFrom-Json
            if ($folderIndexSettings.rootIndexFile) { $rootIndexFile = [string]$folderIndexSettings.rootIndexFile }
            if ($folderIndexSettings.indexFilename) { $customIndexFilename = [string]$folderIndexSettings.indexFilename }
            if ($folderIndexSettings.indexFileUserSpecified -eq $false) {
                $indexStrategy = "folder-index-native"
                Write-Host "-> Folder Index detected: using native folder-named indexes" -ForegroundColor Cyan
            } else {
                $indexStrategy = "folder-index-custom"
                Write-Host "-> Folder Index detected: using custom index name $customIndexFilename.md" -ForegroundColor Cyan
                Write-Host "   WARNING: Folder Index 1.0.30 cannot build nested Graph View edges with one custom index filename." -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "-> Could not parse Folder Index settings; using INDEX.md Dataview fallback." -ForegroundColor Yellow
    }
}

function Get-IndexFileName([string]$folder) {
    if ($indexStrategy -eq "folder-index-native") {
        return "$(Split-Path $folder -Leaf).md"
    }
    if ($indexStrategy -eq "folder-index-custom") {
        return "$customIndexFilename.md"
    }
    return "INDEX.md"
}

$FolderIndexTemplate = @'
---
type: folder-index
tags: [moc]
---

# __TITLE__

__DESC__

```folder-index-content
```
'@

$DataviewIndexTemplate = @'
---
type: moc
tags: [moc]
---

# __TITLE__

__DESC__

## Notes <!-- managed by obsidian-kb-skill: dataview -->

> If the [Dataview plugin](https://github.com/blacksmithgu/obsidian-dataview) is installed, the table below auto-refreshes from this folder's notes. Otherwise, you'll see the code block as plain text -- install Dataview to activate, or replace this block with a manual list.

```dataview
TABLE date, tags
FROM "__FOLDER__"
WHERE file.name != "INDEX"
SORT date DESC
LIMIT 50
```

## Manual Notes (fallback)

<!-- Agents append here when no Dataview block is present above. -->

---
'@

function New-IndexFile($folder, $title, $desc) {
    $indexName = Get-IndexFileName $folder
    $indexPath = Join-Path $VaultPath "$folder\$indexName"
    if (-not (Test-Path $indexPath)) {
        if ($indexStrategy -like "folder-index-*") {
            $content = $FolderIndexTemplate.
                Replace('__TITLE__', $title).
                Replace('__DESC__', $desc)
        } else {
            $content = $DataviewIndexTemplate.
            Replace('__FOLDER__', $folder).
            Replace('__TITLE__', $title).
            Replace('__DESC__', $desc)
        }
        Write-Utf8NoBom -Path $indexPath -Content $content
        Write-Host "  Created index: $folder\$indexName"
    }
}

New-IndexFile "00-Inbox" "Inbox" "Quick capture zone. Process later."
New-IndexFile "10-Work" "Work" "Meeting notes and work documents."
New-IndexFile "15-Daily" "Daily" "Daily notes, journals, morning plans."
New-IndexFile "20-Learning" "Learning" "Articles, courses, and study materials."
New-IndexFile "30-Insights" "Insights" "Analysis and AI-generated insights."
New-IndexFile "40-Projects" "Projects" "Active project context documents."
New-IndexFile "50-People" "People" "Contacts and team member notes."
New-IndexFile "90-Archive" "Archive" "Completed and inactive notes."

# Main index
function Get-IndexLink([string]$folder) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension((Get-IndexFileName $folder))
    return "$folder/$name"
}

$mainIndex = Join-Path $VaultPath $rootIndexFile
if (-not (Test-Path $mainIndex)) {
    $mainContent = @"
---
type: moc
tags: [index, moc]
---

# My Knowledge Base

## Quick Navigation

- [[$(Get-IndexLink "00-Inbox")|Inbox]] -- Quick capture
- [[$(Get-IndexLink "10-Work")|Work]] -- Meeting notes, work docs
- [[$(Get-IndexLink "15-Daily")|Daily]] -- Daily notes, journals
- [[$(Get-IndexLink "20-Learning")|Learning]] -- Articles, study notes
- [[$(Get-IndexLink "30-Insights")|Insights]] -- Analysis, AI insights
- [[$(Get-IndexLink "40-Projects")|Projects]] -- Active projects
- [[$(Get-IndexLink "50-People")|People]] -- Contacts, team notes
- [[$(Get-IndexLink "90-Archive")|Archive]] -- Completed and inactive notes
"@
    if ($indexStrategy -like "folder-index-*") {
        $mainContent += @'

```folder-index-content
```
'@
    }
    Write-Utf8NoBom -Path $mainIndex -Content $mainContent
    Write-Host "  Created main index: $rootIndexFile"
}

# Obsidian config
$obsidianDir = Join-Path $VaultPath ".obsidian"
New-Item -ItemType Directory -Path $obsidianDir -Force | Out-Null
$appJson = Join-Path $obsidianDir "app.json"
if (-not (Test-Path $appJson)) {
    $obsidianConfig = @"
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
"@
    Write-Utf8NoBom -Path $appJson -Content $obsidianConfig
    Write-Host "  Created .obsidian/app.json"
}

Write-Host "-> Vault structure ready." -ForegroundColor Green
Write-Host ""

# Step 3: Install platform files
foreach ($platform in $platformList) {
    switch ($platform) {
        "qoderwork" {
            $skillDir = Join-Path $env:USERPROFILE ".qoderwork\skills\obsidian-knowledge-base"
            Install-StandardSkill -DestinationDirectory $skillDir
            Write-Host "-> Installed: QoderWork skill -> $skillDir\SKILL.md" -ForegroundColor Green
        }
        "claude-code" {
            $claudeDir = Join-Path $env:USERPROFILE ".claude"
            New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
            $claudeFile = Join-Path $claudeDir "CLAUDE.md"
            $srcFile = Join-Path $ScriptDir "platforms\claude-code\CLAUDE.md"
            $body = Read-Text -Path $srcFile
            $result = Set-MarkerBlock -TargetFile $claudeFile -BlockBody $body
            Write-Host "-> Installed: Claude Code ($result) -> $claudeFile" -ForegroundColor Green
        }
        "codex" {
            $codexSkillDir = Join-Path $env:USERPROFILE ".agents\skills\obsidian-knowledge-base"
            Install-StandardSkill -DestinationDirectory $codexSkillDir
            Write-Host "-> Installed: Codex skill -> $codexSkillDir\SKILL.md" -ForegroundColor Green
        }
        "cursor" {
            $cursorDir = Join-Path $env:USERPROFILE ".cursor\rules"
            New-Item -ItemType Directory -Path $cursorDir -Force | Out-Null
            Copy-Item (Join-Path $ScriptDir "platforms\cursor\obsidian-kb.mdc") (Join-Path $cursorDir "obsidian-kb.mdc") -Force
            Write-Host "-> Installed: Cursor -> $cursorDir\obsidian-kb.mdc" -ForegroundColor Green
            Write-Host "  (Copy to your project's .cursor\rules\ for project-level use)"
        }
        default {
            throw "Unknown platform: $platform"
        }
    }
}

# Post-install verification runs the copied helper from an unrelated directory.
$reference = Join-Path $CanonicalSkill "references\note-creation.md"
if (-not (Test-Path $reference)) {
    throw "Post-install verification failed: missing bundled reference."
}
$verifyDir = Join-Path ([System.IO.Path]::GetTempPath()) ("obsidian-kb-verify-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $verifyDir -Force | Out-Null
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = ""
    Push-Location $verifyDir
    try {
        & $PythonExecutable (Join-Path $CanonicalSkill "scripts\run_helper.py") vault-info $VaultPath --json | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Post-install verification failed: bundled vault-info helper is unusable."
        }
    } finally {
        Pop-Location
    }
} finally {
    $env:PYTHONPATH = $oldPythonPath
    Remove-Item $verifyDir -Recurse -Force
}
Write-Host "-> Installed Skill runtime verified." -ForegroundColor Green

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your vault is at: $VaultPath"
Write-Host "Open this folder in Obsidian to start using your knowledge base."
Write-Host ""
Write-Host "To save notes, just tell your AI assistant:"
Write-Host '  "Save this to my knowledge base"'
Write-Host '  "Record this meeting in Obsidian"'
Write-Host '  "Capture this insight"'
