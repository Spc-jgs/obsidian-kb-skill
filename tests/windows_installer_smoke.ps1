$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("obsidian-kb-skill-" + [guid]::NewGuid())
$Release = Join-Path $Sandbox "release"
$HomeDir = Join-Path $Sandbox "home"
$Vault = Join-Path $Sandbox "vault"
$Neutral = Join-Path $Sandbox "neutral"
$Hostile = Join-Path $Sandbox "hostile-cwd"

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-PayloadFiles {
    param([string]$Root, [switch]$ExcludeHeader)
    return @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object {
        $_.Name -ne ".DS_Store" -and $_.DirectoryName -notmatch "__pycache__" -and
        $_.Extension -ne ".pyc" -and $_.Extension -ne ".pyo" -and
        (-not $ExcludeHeader -or $_.FullName -ne (Join-Path $Root "header.md"))
    } | ForEach-Object {
        $_.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'
    } | Sort-Object)
}

function Assert-PayloadMatches {
    param([string]$Source, [string]$Destination, [string]$Label)
    $expected = Get-PayloadFiles $Source -ExcludeHeader
    $actual = Get-PayloadFiles $Destination
    Assert-True (-not (Compare-Object $expected $actual)) "$Label file set differs from source payload"
    foreach ($relative in $expected) {
        $sourceHash = (Get-FileHash -LiteralPath (Join-Path $Source $relative) -Algorithm SHA256).Hash
        $destinationHash = (Get-FileHash -LiteralPath (Join-Path $Destination $relative) -Algorithm SHA256).Hash
        Assert-True ($sourceHash -eq $destinationHash) "$Label hash differs for $relative"
    }
}

try {
    New-Item -ItemType Directory -Path $Release, $HomeDir, $Neutral, $Hostile -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $Vault ".obsidian") -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "install.ps1") $Release
    Copy-Item (Join-Path $RepoRoot "skills") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "platforms") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "core") $Release -Recurse
    $ExpectedPayload = Get-PayloadFiles (Join-Path $Release "skills\obsidian-knowledge-base") -ExcludeHeader

    $OldUserProfile = $env:USERPROFILE
    $OldHome = $env:HOME
    $OldPythonPath = $env:PYTHONPATH
    $OldRuntimePython = $env:OBSIDIAN_KB_PYTHON
    $env:USERPROFILE = $HomeDir
    $env:HOME = $HomeDir
    $env:PYTHONPATH = ""
    $env:OBSIDIAN_KB_PYTHON = (Get-Command python).Source

    $WorkBuddy = Join-Path $HomeDir ".workbuddy\skills\obsidian-knowledge-base"
    $OldClone = Join-Path $Sandbox "old-workbuddy-clone"
    New-Item -ItemType Directory -Path $OldClone -Force | Out-Null
    $OldSentinel = Join-Path $OldClone "keep.txt"
    [System.IO.File]::WriteAllText($OldSentinel, "untouched")
    New-Item -ItemType Directory -Path (Split-Path -Parent $WorkBuddy) -Force | Out-Null
    $LinkTested = $false
    try {
        New-Item -ItemType SymbolicLink -Path $WorkBuddy -Target $OldClone -ErrorAction Stop | Out-Null
        $LinkTested = $true
    } catch {
        Write-Host "SKIP: WorkBuddy directory symlink migration unavailable: $($_.Exception.Message)"
    }

    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex,qoderwork,workbuddy"

    $Settings = Join-Path $HomeDir ".obsidian-kb-settings.json"
    Assert-True (Test-Path $Settings) "Global backup settings were not created"
    $InitialSettings = Get-Content $Settings -Raw | ConvertFrom-Json
    Assert-True ($InitialSettings.schema_version -eq 1) "Unexpected settings schema"
    Assert-True ($InitialSettings.backup.keep_per_note -eq 1) "Unexpected default retention"
    [System.IO.File]::WriteAllText(
        $Settings,
        '{"schema_version":1,"backup":{"keep_per_note":3}}' + "`n"
    )

    $Codex = Join-Path $HomeDir ".agents\skills\obsidian-knowledge-base"
    $Qoder = Join-Path $HomeDir ".qoderwork\skills\obsidian-knowledge-base"
    $Support = Join-Path $HomeDir ".obsidian-kb-skill\skill"
    Assert-True (Test-Path (Join-Path $Codex "references\note-creation.md")) "Codex reference missing"
    Assert-True (Test-Path (Join-Path $Qoder "scripts\run_helper.py")) "Qoder runner missing"
    Assert-True (Test-Path (Join-Path $WorkBuddy "manifest.json")) "WorkBuddy manifest missing"
    Assert-True (Test-Path (Join-Path $Support "assets\templates\digest-note.md")) "Support asset missing"
    Assert-True (Test-Path (Join-Path $Vault "Templates\Digest Note.md")) "Digest template missing"
    Assert-PayloadMatches (Join-Path $Release "skills\obsidian-knowledge-base") $Codex "Codex"
    Assert-PayloadMatches (Join-Path $Release "skills\obsidian-knowledge-base") $Qoder "Qoder"
    Assert-PayloadMatches (Join-Path $Release "skills\obsidian-knowledge-base") $WorkBuddy "WorkBuddy"
    Assert-PayloadMatches (Join-Path $Release "skills\obsidian-knowledge-base") $Support "Support"
    if ($LinkTested) {
        Assert-True (([System.IO.File]::ReadAllText($OldSentinel)) -eq "untouched") "WorkBuddy symlink target was modified"
    }

    $MissingReference = Join-Path $WorkBuddy "references\note-creation.md"
    $StaleReference = Join-Path $WorkBuddy "references\removed-in-upgrade.md"
    $DailyTemplate = Join-Path $Vault "Templates\Daily Note.md"
    Remove-Item $MissingReference -Force
    [System.IO.File]::WriteAllText($StaleReference, "stale")
    [System.IO.File]::WriteAllText($DailyTemplate, "user-owned")
    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex,qoderwork,workbuddy"
    $PreservedSettings = Get-Content $Settings -Raw | ConvertFrom-Json
    Assert-True ($PreservedSettings.backup.keep_per_note -eq 3) "Upgrade overwrote backup retention"
    Assert-True (Test-Path $MissingReference) "Upgrade did not restore missing payload file"
    Assert-True (-not (Test-Path $StaleReference)) "Upgrade kept stale payload file"
    Assert-True ((Get-Content $DailyTemplate -Raw) -eq "user-owned") "Upgrade overwrote user template"
    $Sibling = Join-Path $HomeDir ".workbuddy\skills\keep-me\SKILL.md"
    New-Item -ItemType Directory -Path (Split-Path -Parent $Sibling) -Force | Out-Null
    [System.IO.File]::WriteAllText($Sibling, "keep")

    Remove-Item $Release -Recurse -Force
    Push-Location $Neutral
    try {
        $Json = & $env:OBSIDIAN_KB_PYTHON (Join-Path $Codex "scripts\run_helper.py") vault-info $Vault --json
        Assert-True ($LASTEXITCODE -eq 0) "Installed vault-info failed"
        $Info = $Json | ConvertFrom-Json
        Assert-True ($Info.valid -eq $true) "Installed vault-info did not validate the Vault"
        $WorkBuddyJson = & $env:OBSIDIAN_KB_PYTHON (Join-Path $WorkBuddy "scripts\run_helper.py") doctor --json
        Assert-True ($LASTEXITCODE -eq 0) "Installed WorkBuddy doctor failed"
        $WorkBuddyDoctor = $WorkBuddyJson | ConvertFrom-Json
        Assert-True ($WorkBuddyDoctor.ok -eq $true) "Installed WorkBuddy doctor was unhealthy"
        $WorkBuddyInfoJson = & $env:OBSIDIAN_KB_PYTHON (Join-Path $WorkBuddy "scripts\run_helper.py") vault-info $Vault --json
        Assert-True ($LASTEXITCODE -eq 0) "Installed WorkBuddy vault-info failed"
        $WorkBuddyInfo = $WorkBuddyInfoJson | ConvertFrom-Json
        Assert-True ($WorkBuddyInfo.valid -eq $true) "Installed WorkBuddy vault-info did not validate the Vault"

        $ShadowScripts = Join-Path $Hostile "obsidian_kb_skill\scripts"
        New-Item -ItemType Directory -Path $ShadowScripts -Force | Out-Null
        [System.IO.File]::WriteAllText((Join-Path $Hostile "obsidian_kb_skill\__init__.py"), "")
        [System.IO.File]::WriteAllText((Join-Path $ShadowScripts "__init__.py"), "")
        Push-Location $Hostile
        try {
            $HostileDoctorJson = & $env:OBSIDIAN_KB_PYTHON `
                (Join-Path $WorkBuddy "scripts\run_helper.py") doctor --json
            Assert-True ($LASTEXITCODE -eq 0) "Installed WorkBuddy doctor failed from hostile cwd"
            $HostileDoctor = $HostileDoctorJson | ConvertFrom-Json
            Assert-True ($HostileDoctor.ok -eq $true) "Installed WorkBuddy doctor was unhealthy from hostile cwd"
            $HostileInfoJson = & $env:OBSIDIAN_KB_PYTHON `
                (Join-Path $WorkBuddy "scripts\run_helper.py") vault-info $Vault --json
            Assert-True ($LASTEXITCODE -eq 0) "Installed WorkBuddy vault-info failed from hostile cwd"
            $HostileInfo = $HostileInfoJson | ConvertFrom-Json
            Assert-True ($HostileInfo.valid -eq $true) "Installed WorkBuddy vault-info was invalid from hostile cwd"
        } finally {
            Pop-Location
        }

    } finally {
        Pop-Location
    }

    $Release = Join-Path $Sandbox "release-2"
    New-Item -ItemType Directory -Path $Release -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "install.ps1") $Release
    Copy-Item (Join-Path $RepoRoot "skills") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "platforms") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "core") $Release -Recurse

    $ClaudeDir = Join-Path $HomeDir ".claude"
    $ClaudeFile = Join-Path $ClaudeDir "CLAUDE.md"
    New-Item -ItemType Directory -Path $ClaudeDir -Force | Out-Null
    $Malformed = "user content`n<!-- BEGIN obsidian-kb-skill -->`norphaned`nkeep me`n"
    [System.IO.File]::WriteAllText($ClaudeFile, $Malformed)
    $MarkerFailed = $false
    try {
        & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "claude-code"
    } catch {
        $MarkerFailed = $true
    }
    Assert-True $MarkerFailed "Malformed PowerShell marker install did not fail"
    Assert-True (([System.IO.File]::ReadAllText($ClaudeFile)) -eq $Malformed) "Malformed marker file was modified"
    Remove-Item $ClaudeFile -Force

    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex" -Uninstall
    Assert-True (Test-Path (Join-Path $HomeDir ".obsidian-kb-config")) "Default uninstall removed config"
    Assert-True (Test-Path $Settings) "Default uninstall removed backup settings"
    $UninstallSettings = Get-Content $Settings -Raw | ConvertFrom-Json
    Assert-True ($UninstallSettings.backup.keep_per_note -eq 3) "Default uninstall changed backup retention"
    Assert-True (-not (Test-Path (Join-Path $HomeDir ".obsidian-kb-skill"))) "Support runtime survived uninstall"
    Assert-True (-not (Test-Path $WorkBuddy)) "WorkBuddy Skill survived uninstall"
    Assert-True (Test-Path $Sibling) "WorkBuddy sibling Skill was removed"
    Assert-True (Test-Path $Vault) "Uninstall removed Vault"

    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex"
    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex" -Uninstall -PurgeConfig
    Assert-True (-not (Test-Path (Join-Path $HomeDir ".obsidian-kb-config"))) "Purge did not remove config"
    Assert-True (-not (Test-Path $Settings)) "Purge did not remove backup settings"
} finally {
    $env:USERPROFILE = $OldUserProfile
    $env:HOME = $OldHome
    $env:PYTHONPATH = $OldPythonPath
    $env:OBSIDIAN_KB_PYTHON = $OldRuntimePython
    if (Test-Path $Sandbox) { Remove-Item $Sandbox -Recurse -Force }
}
