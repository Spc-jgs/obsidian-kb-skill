# Obsidian Knowledge Base Skill — PowerShell Installer
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

    [switch]$Help,

    [switch]$Uninstall
)

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
    Write-Host "  -Uninstall         Remove installed skill files"
    Write-Host "  -Help              Show this help message"
    Write-Host ""
    Write-Host "Configuration sources (checked in order):"
    Write-Host "  1. -VaultPath parameter"
    Write-Host "  2. OBSIDIAN_KB_VAULT in .env (skill directory)"
    Write-Host "  3. OBSIDIAN_KB_VAULT environment variable"
    Write-Host "  4. ~/.obsidian-kb-config (from previous install)"
    exit 0
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

    # Remove Cursor rule
    $cursorFile = Join-Path $env:USERPROFILE ".cursor\rules\obsidian-kb.mdc"
    if (Test-Path $cursorFile) {
        Remove-Item $cursorFile -Force
        Write-Host "-> Removed: Cursor rule ($cursorFile)" -ForegroundColor Green
    }

    # Remove config file
    $configFile = Join-Path $env:USERPROFILE ".obsidian-kb-config"
    if (Test-Path $configFile) {
        Remove-Item $configFile -Force
        Write-Host "-> Removed: Config ($configFile)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Note: Vault folder and its contents are NOT deleted." -ForegroundColor Yellow
    Write-Host "Note: Claude Code and Codex entries are NOT auto-removed (may contain other content)." -ForegroundColor Yellow
    Write-Host "Uninstall complete." -ForegroundColor Cyan
    exit 0
}

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

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
    Write-Host "Run .\install.ps1 -? for help."
    exit 1
}

Write-Host ""
Write-Host "=== Obsidian Knowledge Base Skill Installer ===" -ForegroundColor Cyan
Write-Host "Vault path: $VaultPath"
Write-Host "Platforms:  $Platforms"
Write-Host ""

# Resolve vault path (compatible with Windows PowerShell 5.1+)
$resolvedPath = Resolve-Path $VaultPath -ErrorAction SilentlyContinue
if ($resolvedPath) {
    $VaultPath = $resolvedPath.Path
} else {
    if (-not (Test-Path $VaultPath)) {
        Write-Host "-> Vault path does not exist, creating: $VaultPath" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $VaultPath -Force | Out-Null
    }
}

# Step 1: Save vault config
$configFile = Join-Path $env:USERPROFILE ".obsidian-kb-config"
Write-Host "-> Saving vault config to $configFile"
# Use [System.IO.File]::WriteAllText for UTF-8 without BOM (compatible with PS 5.1+)
[System.IO.File]::WriteAllText($configFile, $VaultPath, (New-Object System.Text.UTF8Encoding $false))

# Step 2: Initialize vault structure
Write-Host "-> Checking vault structure..."
$folders = @("00-Inbox", "10-Work", "20-Learning", "30-Insights", "40-Projects", "50-People", "90-Archive", "Templates", "Attachments")
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
}

$forceUpgrade = $false
if ($env:OBSIDIAN_KB_UPGRADE -eq "1" -or $Platforms -match "^--force") {
    $forceUpgrade = $true
    Write-Host "-> Upgrade mode: will overwrite existing templates" -ForegroundColor Yellow
}

foreach ($src in $templateMap.Keys) {
    $srcPath = Join-Path $ScriptDir "core\templates\$src"
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

# Create INDEX files
function New-IndexFile($folder, $title, $desc) {
    $indexPath = Join-Path $VaultPath "$folder\INDEX.md"
    if (-not (Test-Path $indexPath)) {
        $content = @"
---
type: folder-index
tags: [$folder]
---

# $title

$desc

## Notes

---
"@
        [System.IO.File]::WriteAllText($indexPath, $content, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "  Created index: $folder\INDEX.md"
    }
}

New-IndexFile "00-Inbox" "Inbox" "Quick capture zone. Process later."
New-IndexFile "10-Work" "Work" "Meeting notes and work documents."
New-IndexFile "20-Learning" "Learning" "Articles, courses, and study materials."
New-IndexFile "30-Insights" "Insights" "Analysis and AI-generated insights."
New-IndexFile "40-Projects" "Projects" "Active project context documents."
New-IndexFile "50-People" "People" "Contacts and team member notes."

# Main INDEX
$mainIndex = Join-Path $VaultPath "INDEX.md"
if (-not (Test-Path $mainIndex)) {
    $mainContent = @"
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
"@
    [System.IO.File]::WriteAllText($mainIndex, $mainContent, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "  Created main INDEX.md"
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
    [System.IO.File]::WriteAllText($appJson, $obsidianConfig, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "  Created .obsidian/app.json"
}

Write-Host "-> Vault structure ready." -ForegroundColor Green
Write-Host ""

# Step 3: Install platform files
$platformList = $Platforms -split ','

foreach ($platform in $platformList) {
    $platform = $platform.Trim()
    switch ($platform) {
        "qoderwork" {
            $skillDir = Join-Path $env:USERPROFILE ".qoderwork\skills\obsidian-knowledge-base"
            New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
            Copy-Item (Join-Path $ScriptDir "platforms\qoderwork\SKILL.md") (Join-Path $skillDir "SKILL.md") -Force
            Write-Host "-> Installed: QoderWork skill -> $skillDir\SKILL.md" -ForegroundColor Green
        }
        "claude-code" {
            $claudeDir = Join-Path $env:USERPROFILE ".claude"
            New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
            $claudeFile = Join-Path $claudeDir "CLAUDE.md"
            $srcFile = Join-Path $ScriptDir "platforms\claude-code\CLAUDE.md"
            if (Test-Path $claudeFile) {
                $existing = Get-Content $claudeFile -Raw
                if ($existing -notmatch "Obsidian Personal Knowledge Base") {
                    Add-Content -Path $claudeFile -Value "`n---`n"
                    Add-Content -Path $claudeFile -Value (Get-Content $srcFile -Raw)
                    Write-Host "-> Installed: Claude Code (appended to $claudeFile)" -ForegroundColor Green
                } else {
                    Write-Host "-> Skipped: Claude Code (already installed)" -ForegroundColor Yellow
                }
            } else {
                Copy-Item $srcFile $claudeFile
                Write-Host "-> Installed: Claude Code -> $claudeFile" -ForegroundColor Green
            }
        }
        "codex" {
            $codexFile = Join-Path $env:USERPROFILE "AGENTS.md"
            $srcFile = Join-Path $ScriptDir "platforms\codex\AGENTS.md"
            if (Test-Path $codexFile) {
                $existing = Get-Content $codexFile -Raw
                if ($existing -notmatch "Obsidian Personal Knowledge Base") {
                    Add-Content -Path $codexFile -Value "`n---`n"
                    Add-Content -Path $codexFile -Value (Get-Content $srcFile -Raw)
                    Write-Host "-> Installed: Codex (appended to $codexFile)" -ForegroundColor Green
                } else {
                    Write-Host "-> Skipped: Codex (already installed)" -ForegroundColor Yellow
                }
            } else {
                Copy-Item $srcFile $codexFile
                Write-Host "-> Installed: Codex -> $codexFile" -ForegroundColor Green
            }
        }
        "cursor" {
            $cursorDir = Join-Path $env:USERPROFILE ".cursor\rules"
            New-Item -ItemType Directory -Path $cursorDir -Force | Out-Null
            Copy-Item (Join-Path $ScriptDir "platforms\cursor\obsidian-kb.mdc") (Join-Path $cursorDir "obsidian-kb.mdc") -Force
            Write-Host "-> Installed: Cursor -> $cursorDir\obsidian-kb.mdc" -ForegroundColor Green
            Write-Host "  (Copy to your project's .cursor\rules\ for project-level use)"
        }
        default {
            Write-Host "-> Unknown platform: $platform" -ForegroundColor Yellow
        }
    }
}

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
