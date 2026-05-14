param(
    [Alias("Host")]
    [string]$HostName,
    [int]$Port = 0,
    [string]$DbPath
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

function Test-PortInUse {
    param(
        [string]$Address,
        [int]$PortNumber
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect($Address, $PortNumber, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(500, $false)) {
            return $false
        }

        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-PythonForOfficeTrial {
    param([string]$PythonPath)

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $PythonPath -c "import fastapi, uvicorn; assert hasattr(uvicorn, 'run')" 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

Import-LocalEnv -EnvPath (Join-Path $RepoRoot ".env")

$effectiveHost = if ($HostName) { $HostName } elseif ($env:MANUAL_DISPATCH_HOST) { $env:MANUAL_DISPATCH_HOST } else { "127.0.0.1" }
$effectivePort = if ($Port -gt 0) { $Port } elseif ($env:MANUAL_DISPATCH_PORT) { [int]$env:MANUAL_DISPATCH_PORT } else { 8130 }
$effectiveDbPath = if ($DbPath) { $DbPath } elseif ($env:MANUAL_DISPATCH_DB_PATH) { $env:MANUAL_DISPATCH_DB_PATH } else { "data/manual_dispatch.sqlite3" }

$env:MANUAL_DISPATCH_DB_PATH = $effectiveDbPath

$pythonCandidates = @(
    [PSCustomObject]@{
        Label = "virtual environment Python"
        Path = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    },
    [PSCustomObject]@{
        Label = "local route-test Python"
        Path = Join-Path $RepoRoot "tmp\route-test-venv\Scripts\python.exe"
    }
)

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonCandidates += [PSCustomObject]@{
        Label = "Python from PATH"
        Path = $pythonCommand.Source
    }
}

$pythonPath = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path -LiteralPath $candidate.Path)) {
        continue
    }

    if (Test-PythonForOfficeTrial -PythonPath $candidate.Path) {
        $pythonPath = $candidate.Path
        Write-Host "Using $($candidate.Label): $pythonPath"
        break
    }

    Write-Host "Skipping $($candidate.Label): missing required FastAPI/Uvicorn runtime support."
}

if (-not $pythonPath) {
    Write-Error "No usable Python environment found. Create .venv and install requirements.txt first."
    exit 1
}

$probeHost = if ($effectiveHost -eq "0.0.0.0") { "127.0.0.1" } else { $effectiveHost }
if (Test-PortInUse -Address $probeHost -PortNumber $effectivePort) {
    Write-Host "Port $effectivePort is already in use on $probeHost."
    Write-Host "Try another port, for example:"
    Write-Host ".\tools\start_office_trial.ps1 -Port 8131"
    exit 1
}

Set-Location $RepoRoot

Write-Host "Starting Manual Dispatch Board..."
Write-Host "Database path: $effectiveDbPath"
Write-Host "Open:"
Write-Host "http://$effectiveHost`:$effectivePort/frontend/"
Write-Host "Press Ctrl+C to stop the backend."

$uvicornRunner = "import sys, uvicorn; uvicorn.run('backend.main:app', host=sys.argv[1], port=int(sys.argv[2]))"
& $pythonPath -c $uvicornRunner $effectiveHost $effectivePort
