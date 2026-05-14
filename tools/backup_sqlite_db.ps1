param(
    [string]$SourcePath,
    [string]$BackupDir = "backups"
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

$effectiveSource = if ($SourcePath) { $SourcePath } elseif ($env:MANUAL_DISPATCH_DB_PATH) { $env:MANUAL_DISPATCH_DB_PATH } else { "data/manual_dispatch.sqlite3" }
$sourceFullPath = Resolve-RepoPath -PathValue $effectiveSource

if (-not (Test-Path -LiteralPath $sourceFullPath)) {
    Write-Host "Runtime database not found: $effectiveSource"
    exit 1
}

$backupFullDir = Resolve-RepoPath -PathValue $BackupDir
New-Item -ItemType Directory -Path $backupFullDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFileName = "manual_dispatch_$timestamp.sqlite3"
$backupPath = Join-Path $backupFullDir $backupFileName

Copy-Item -LiteralPath $sourceFullPath -Destination $backupPath -ErrorAction Stop

Write-Host "SQLite backup created."
Write-Host "Source: $sourceFullPath"
Write-Host "Backup: $backupPath"
