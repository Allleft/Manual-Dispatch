param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$TargetPath,
    [string]$BackupDir = "backups",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

function Import-LocalEnv {
    param([string]$EnvPath)

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $EnvPath) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Resolve-RepoPath {
    param([string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return Join-Path $RepoRoot $PathValue
}

Import-LocalEnv -EnvPath (Join-Path $RepoRoot ".env")

$backupFullPath = Resolve-RepoPath -PathValue $BackupPath
if (-not (Test-Path -LiteralPath $backupFullPath)) {
    Write-Error "Backup file not found: $BackupPath"
    exit 1
}

$effectiveTarget = if ($TargetPath) { $TargetPath } elseif ($env:MANUAL_DISPATCH_DB_PATH) { $env:MANUAL_DISPATCH_DB_PATH } else { "data/manual_dispatch.sqlite3" }
$targetFullPath = Resolve-RepoPath -PathValue $effectiveTarget
$targetDir = Split-Path -Parent $targetFullPath

Write-Host "Restore target:"
Write-Host $targetFullPath
Write-Host "Backup source:"
Write-Host $backupFullPath

if (-not $Force) {
    $answer = Read-Host "Restore this backup over the runtime database? Type YES to continue"
    if ($answer -ne "YES") {
        Write-Host "Restore cancelled."
        exit 1
    }
}

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$backupFullDir = Resolve-RepoPath -PathValue $BackupDir
New-Item -ItemType Directory -Path $backupFullDir -Force | Out-Null

if (Test-Path -LiteralPath $targetFullPath) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $beforeRestorePath = Join-Path $backupFullDir "manual_dispatch_before_restore_$timestamp.sqlite3"
    Copy-Item -LiteralPath $targetFullPath -Destination $beforeRestorePath -ErrorAction Stop
    Write-Host "Current runtime database backed up before restore:"
    Write-Host $beforeRestorePath
}

Copy-Item -LiteralPath $backupFullPath -Destination $targetFullPath -Force -ErrorAction Stop

Write-Host "SQLite database restored."
Write-Host "Runtime database: $targetFullPath"
