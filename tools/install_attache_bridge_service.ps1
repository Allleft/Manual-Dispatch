#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$WinSWPath,
    [Parameter(Mandatory = $true)][string]$WinSWSha256,
    [Parameter(Mandatory = $true)][string]$BridgePath,
    [Parameter(Mandatory = $true)][string]$BridgeSha256,
    [Parameter(Mandatory = $true)][string]$ServiceAccount,
    [string]$DeploymentDirectory = (Join-Path $env:ProgramFiles 'ManualDispatchAttacheBridge'),
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'attache_bridge_service\ServiceCommon.ps1')
Assert-ServiceAdministrator
$deployment = Resolve-ServiceDirectory $DeploymentDirectory
if (Test-Path -LiteralPath $deployment) { throw 'Use a new deployment directory; never overwrite an existing installation.' }
if (Get-Service -Name $BridgeServiceId -ErrorAction SilentlyContinue) { throw 'Service already exists; follow the reviewed upgrade/rollback runbook.' }
Assert-ApprovedExecutable $WinSWPath $WinSWSha256
Assert-ApprovedExecutable $BridgePath $BridgeSha256
if ((Get-Item -LiteralPath $WinSWPath).VersionInfo.FileMajorPart -ne 3) {
    throw 'An independently approved WinSW 3.x executable is required.'
}
$accountSid = Get-ServiceAccountSid $ServiceAccount
$templatePath = Join-Path $PSScriptRoot 'attache_bridge_service\ManualDispatchAttacheBridge.xml'
if (-not $PSCmdlet.ShouldProcess($deployment, 'Provision encrypted secrets and install Bridge service')) { return }

# Refuse inherited secret overrides: service identity/env must be reviewed, not guessed.
foreach ($name in @('ATTACHE_ODBC_CONNECTION_STRING', 'ATTACHE_BRIDGE_API_TOKEN')) {
    if ([Environment]::GetEnvironmentVariable($name, 'Machine') -or
        [Environment]::GetEnvironmentVariable($name, 'Process')) {
        throw 'Clear conflicting service secret environment overrides privately before provisioning.'
    }
}

New-Item -ItemType Directory -Path $deployment | Out-Null
Set-ServicePathAcl $deployment $accountSid
$logs = Join-Path $deployment 'logs'
New-Item -ItemType Directory -Path $logs | Out-Null
Set-ServicePathAcl $logs $accountSid -LogDirectory
$secretsPath = Join-Path $deployment 'bridge-secrets.dpapi.json'
[IO.File]::WriteAllBytes($secretsPath, [byte[]]@())
Set-ServicePathAcl $secretsPath $accountSid -SecretsFile
$wrapper = Join-Path $deployment 'ManualDispatchAttacheBridge.exe'
$bridge = Join-Path $deployment 'attache-bridge.exe'
Copy-Item -LiteralPath $WinSWPath -Destination $wrapper
Copy-Item -LiteralPath $BridgePath -Destination $bridge
Assert-ApprovedExecutable $wrapper $WinSWSha256
Assert-ApprovedExecutable $bridge $BridgeSha256
Copy-Item -LiteralPath $templatePath -Destination (Join-Path $deployment 'ManualDispatchAttacheBridge.xml')

Add-Type -AssemblyName System.Security
$odbc = $null
$token = $null
$plainBytes = $null
$odbcText = $null
$tokenText = $null
$json = $null
try {
    # Full credential-bearing string is hidden, allowing the existing DSN to remain untouched.
    $odbc = Read-Host 'Approved ODBC connection string (existing User DSN, UID and PWD)' -AsSecureString
    $token = Read-Host 'Existing shared Bridge API token' -AsSecureString
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($odbc)
        $odbcText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
        $tokenText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    if ([string]::IsNullOrWhiteSpace($odbcText) -or [string]::IsNullOrWhiteSpace($tokenText) -or
        $odbcText -match '[\r\n\x00]' -or $tokenText -match '[\r\n\x00]') { throw 'Invalid input.' }
    $json = @{version = 1; scope = 'LocalMachine'; connection_string = $odbcText; api_token = $tokenText} | ConvertTo-Json -Compress
    $plainBytes = [Text.Encoding]::UTF8.GetBytes($json)
    if ($plainBytes.Length -gt 16384) { throw 'Input too large.' }
    $cipherBytes = [Security.Cryptography.ProtectedData]::Protect(
        $plainBytes, $null, [Security.Cryptography.DataProtectionScope]::LocalMachine)
    $envelope = @{version = 1; scope = 'LocalMachine'; ciphertext = [Convert]::ToBase64String($cipherBytes)} | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($secretsPath, $envelope, [Text.UTF8Encoding]::new($false))
    Assert-ServicePathAcl $secretsPath $accountSid -SecretsFile
} catch {
    throw 'Secret provisioning failed. No service was installed; do not paste raw diagnostic state.'
} finally {
    if ($null -ne $plainBytes) { [Array]::Clear($plainBytes, 0, $plainBytes.Length) }
    if ($null -ne $odbc) { $odbc.Dispose() }
    if ($null -ne $token) { $token.Dispose() }
    $odbcText = $null; $tokenText = $null; $json = $null
    # Managed strings may survive until GC; no plaintext is written or logged.
}

$manifest = @{version = 1; service_id = $BridgeServiceId; account_sid = $accountSid;
    bridge_sha256 = $BridgeSha256.ToUpperInvariant(); winsw_sha256 = $WinSWSha256.ToUpperInvariant();
    xml_sha256 = (Get-FileHash -LiteralPath (Join-Path $deployment 'ManualDispatchAttacheBridge.xml') -Algorithm SHA256).Hash}
[IO.File]::WriteAllText((Join-Path $deployment 'service-install.json'), ($manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
Write-Output 'Enter the SAME authorized Windows service account in the WinSW prompt. Password is never passed on the command line.'
Assert-ServicePathAcl $deployment $accountSid
Assert-ServicePathAcl $logs $accountSid -LogDirectory
Assert-ServicePathAcl $secretsPath $accountSid -SecretsFile
Invoke-BridgeWrapper $wrapper 'install'
$installed = Get-CimInstance Win32_Service -Filter "Name='$BridgeServiceId'"
Assert-RegisteredServicePath $installed $wrapper
$accountMatches = $false
try { $accountMatches = (Get-ServiceAccountSid $installed.StartName) -eq $accountSid } catch { $accountMatches = $false }
if (-not $accountMatches) {
    Invoke-BridgeWrapper $wrapper 'uninstall'
    throw 'Service account mismatch; service removed. Encrypted artifacts retained for review.'
}
Write-Output "BRIDGE_SHA256=$($manifest.bridge_sha256)"
Write-Output 'SERVICE_INSTALLED_NOT_STARTED'
if ($Start) { Invoke-BridgeWrapper $wrapper 'start' }
