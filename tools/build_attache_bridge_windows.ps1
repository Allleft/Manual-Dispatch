param(
    [string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

function Resolve-RepositoryChildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $rootFullPath = [System.IO.Path]::GetFullPath($RepoRoot)
    $rootPrefix = $rootFullPath.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    $candidateFullPath = [System.IO.Path]::GetFullPath($PathValue)
    if (-not $candidateFullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Packaging path is outside the repository."
    }
    return $candidateFullPath
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Attaché Bridge packaging requires Windows."
}

if (-not $PythonPath) {
    $PythonPath = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}
$PythonPath = [System.IO.Path]::GetFullPath($PythonPath)
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Windows x64 Python was not found at the supplied path."
}

$LauncherPath = Join-Path $RepoRoot "attache_bridge\launcher.py"
$RunbookSource = Join-Path $RepoRoot "docs\attache-bridge-windows-x64-remote-smoke-test.txt"
$DistDir = Resolve-RepositoryChildPath -PathValue (Join-Path $RepoRoot "dist")
$DistExecutable = Resolve-RepositoryChildPath -PathValue (Join-Path $DistDir "attache-bridge.exe")
$BuildRoot = Resolve-RepositoryChildPath -PathValue (Join-Path $RepoRoot "build\attache-bridge")
$BuildWork = Resolve-RepositoryChildPath -PathValue (Join-Path $BuildRoot "work")
$BuildSpec = Resolve-RepositoryChildPath -PathValue (Join-Path $BuildRoot "spec")
$ReleaseDir = Resolve-RepositoryChildPath -PathValue (Join-Path $RepoRoot "release\attache-bridge-windows-x64")
$ReleaseZip = Resolve-RepositoryChildPath -PathValue (Join-Path $RepoRoot "release\attache-bridge-windows-x64.zip")
$ReleaseExecutable = Join-Path $ReleaseDir "attache-bridge.exe"
$ReleaseRunbook = Join-Path $ReleaseDir "REMOTE-SMOKE-TEST.txt"
$ReleaseHash = Join-Path $ReleaseDir "SHA256.txt"

foreach ($requiredPath in @($LauncherPath, $RunbookSource)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required packaging source is missing: $requiredPath"
    }
}

Push-Location $RepoRoot
try {
    $pythonBits = (& $PythonPath -c "import struct; print(struct.calcsize('P') * 8)" | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the Python build architecture."
    }
    if ($pythonBits -ne "64") {
        throw "Attaché Bridge packaging requires 64-bit Python."
    }

    & $PythonPath -c "import fastapi, pydantic, pyodbc, starlette, uvicorn; from attache_bridge.main import app; assert app is not None"
    if ($LASTEXITCODE -ne 0) {
        throw "Required Attaché Bridge imports are unavailable."
    }

    $pyInstallerVersion = (& $PythonPath -m PyInstaller --version | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $pyInstallerVersion) {
        throw "PyInstaller is not available in the selected build environment."
    }

    if (Test-Path -LiteralPath $DistExecutable) {
        Remove-Item -LiteralPath $DistExecutable -Force
    }
    if (Test-Path -LiteralPath $BuildRoot) {
        Remove-Item -LiteralPath $BuildRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $ReleaseDir) {
        Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $ReleaseZip) {
        Remove-Item -LiteralPath $ReleaseZip -Force
    }

    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
    New-Item -ItemType Directory -Path $BuildWork -Force | Out-Null
    New-Item -ItemType Directory -Path $BuildSpec -Force | Out-Null

    $pyInstallerArguments = @(
        "--noconfirm",
        "--onefile",
        "--console",
        "--name", "attache-bridge",
        "--paths", $RepoRoot,
        "--distpath", $DistDir,
        "--workpath", $BuildWork,
        "--specpath", $BuildSpec,
        $LauncherPath
    )
    & $PythonPath -m PyInstaller @pyInstallerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build Attaché Bridge."
    }
    if (-not (Test-Path -LiteralPath $DistExecutable -PathType Leaf)) {
        throw "Expected frozen executable was not created."
    }

    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    Copy-Item -LiteralPath $DistExecutable -Destination $ReleaseExecutable
    Copy-Item -LiteralPath $RunbookSource -Destination $ReleaseRunbook

    $hash = Get-FileHash -LiteralPath $ReleaseExecutable -Algorithm SHA256
    Set-Content -LiteralPath $ReleaseHash -Value @(
        "attache-bridge.exe",
        $hash.Hash
    ) -Encoding Ascii

    $packageFiles = @($ReleaseExecutable, $ReleaseRunbook, $ReleaseHash)
    Compress-Archive -LiteralPath $packageFiles -DestinationPath $ReleaseZip -CompressionLevel Optimal

    $executableInfo = Get-Item -LiteralPath $ReleaseExecutable
    Write-Output "PYTHON_BITS=$pythonBits"
    Write-Output "PYINSTALLER_VERSION=$pyInstallerVersion"
    Write-Output "EXECUTABLE=$ReleaseExecutable"
    Write-Output "EXECUTABLE_BYTES=$($executableInfo.Length)"
    Write-Output "SHA256=$($hash.Hash)"
    Write-Output "ZIP=$ReleaseZip"
}
finally {
    Pop-Location
}
