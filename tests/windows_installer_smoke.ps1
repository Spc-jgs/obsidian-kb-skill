$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("obsidian-kb-skill-" + [guid]::NewGuid())
$Release = Join-Path $Sandbox "release"
$HomeDir = Join-Path $Sandbox "home"
$Vault = Join-Path $Sandbox "vault"
$Neutral = Join-Path $Sandbox "neutral"

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

try {
    New-Item -ItemType Directory -Path $Release, $HomeDir, $Neutral -Force | Out-Null
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

    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex,qoderwork"

    $Codex = Join-Path $HomeDir ".agents\skills\obsidian-knowledge-base"
    $Qoder = Join-Path $HomeDir ".qoderwork\skills\obsidian-knowledge-base"
    $Support = Join-Path $HomeDir ".obsidian-kb-skill\skill"
    Assert-True (Test-Path (Join-Path $Codex "references\note-creation.md")) "Codex reference missing"
    Assert-True (Test-Path (Join-Path $Qoder "scripts\run_helper.py")) "Qoder runner missing"
    Assert-True (Test-Path (Join-Path $Support "assets\templates\digest-note.md")) "Support asset missing"
    Assert-True (Test-Path (Join-Path $Vault "Templates\Digest Note.md")) "Digest template missing"
    Assert-True (-not (Compare-Object $ExpectedPayload (Get-PayloadFiles $Codex))) "Codex payload differs from source payload"
    Assert-True (-not (Compare-Object $ExpectedPayload (Get-PayloadFiles $Qoder))) "Qoder payload differs from source payload"
    Assert-True (-not (Compare-Object $ExpectedPayload (Get-PayloadFiles $Support))) "Support payload differs from source payload"

    $MissingReference = Join-Path $Codex "references\note-creation.md"
    $StaleReference = Join-Path $Codex "references\removed-in-upgrade.md"
    $DailyTemplate = Join-Path $Vault "Templates\Daily Note.md"
    Remove-Item $MissingReference -Force
    [System.IO.File]::WriteAllText($StaleReference, "stale")
    [System.IO.File]::WriteAllText($DailyTemplate, "user-owned")
    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex,qoderwork"
    Assert-True (Test-Path $MissingReference) "Upgrade did not restore missing payload file"
    Assert-True (-not (Test-Path $StaleReference)) "Upgrade kept stale payload file"
    Assert-True ((Get-Content $DailyTemplate -Raw) -eq "user-owned") "Upgrade overwrote user template"

    Remove-Item $Release -Recurse -Force
    Push-Location $Neutral
    try {
        $Json = & $env:OBSIDIAN_KB_PYTHON (Join-Path $Codex "scripts\run_helper.py") vault-info $Vault --json
        Assert-True ($LASTEXITCODE -eq 0) "Installed vault-info failed"
        $Info = $Json | ConvertFrom-Json
        Assert-True ($Info.valid -eq $true) "Installed vault-info did not validate the Vault"
    } finally {
        Pop-Location
    }

    $Release = Join-Path $Sandbox "release-2"
    New-Item -ItemType Directory -Path $Release -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "install.ps1") $Release
    Copy-Item (Join-Path $RepoRoot "skills") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "platforms") $Release -Recurse
    Copy-Item (Join-Path $RepoRoot "core") $Release -Recurse
    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex" -Uninstall
    Assert-True (Test-Path (Join-Path $HomeDir ".obsidian-kb-config")) "Default uninstall removed config"
    Assert-True (-not (Test-Path (Join-Path $HomeDir ".obsidian-kb-skill"))) "Support runtime survived uninstall"
    Assert-True (Test-Path $Vault) "Uninstall removed Vault"

    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex"
    & (Join-Path $Release "install.ps1") -VaultPath $Vault -Platforms "codex" -Uninstall -PurgeConfig
    Assert-True (-not (Test-Path (Join-Path $HomeDir ".obsidian-kb-config"))) "Purge did not remove config"
} finally {
    $env:USERPROFILE = $OldUserProfile
    $env:HOME = $OldHome
    $env:PYTHONPATH = $OldPythonPath
    $env:OBSIDIAN_KB_PYTHON = $OldRuntimePython
    if (Test-Path $Sandbox) { Remove-Item $Sandbox -Recurse -Force }
}
