#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$DeploymentDirectory = (Join-Path $env:ProgramFiles 'ManualDispatchAttacheBridge'),
    [switch]$RemoveLocalData
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'attache_bridge_service\ServiceCommon.ps1')
Assert-ServiceAdministrator
$deployment = Resolve-ServiceDirectory $DeploymentDirectory
$manifestPath = Join-Path $deployment 'service-install.json'
Assert-NoReparsePoint $manifestPath
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.version -ne 1 -or $manifest.service_id -cne $BridgeServiceId) { throw 'Unknown deployment manifest.' }
$wrapper = Join-Path $deployment 'ManualDispatchAttacheBridge.exe'
Assert-ApprovedExecutable $wrapper $manifest.winsw_sha256
Assert-ApprovedExecutable (Join-Path $deployment 'ManualDispatchAttacheBridge.xml') $manifest.xml_sha256
$service = Get-CimInstance Win32_Service -Filter "Name='$BridgeServiceId'"
if ($null -ne $service) { Assert-RegisteredServicePath $service $wrapper }
if (-not $PSCmdlet.ShouldProcess($deployment, 'Stop and uninstall only ManualDispatchAttacheBridge')) { return }
if ($null -ne $service) {
    if ($service.State -ne 'Stopped') { Invoke-BridgeWrapper $wrapper 'stop' }
    $service = Get-CimInstance Win32_Service -Filter "Name='$BridgeServiceId'"
    if ($service.State -ne 'Stopped') { throw 'Service did not stop; no uninstall or deletion performed.' }
    Invoke-BridgeWrapper $wrapper 'uninstall'
    if (Get-Service -Name $BridgeServiceId -ErrorAction SilentlyContinue) { throw 'Service still exists; no deletion performed.' }
}
if ($RemoveLocalData) {
    # Resolve and constrain BOTH targets before any recursive deletion.
    $logs = [IO.Path]::GetFullPath((Join-Path $deployment 'logs'))
    $secrets = [IO.Path]::GetFullPath((Join-Path $deployment 'bridge-secrets.dpapi.json'))
    foreach ($target in @($logs, $secrets)) {
        if ([IO.Path]::GetDirectoryName($target) -ine $deployment) { throw 'Unsafe removal target.' }
        Assert-NoReparsePoint $target
    }
    if (Test-Path -LiteralPath $logs) {
        if (Get-ChildItem -LiteralPath $logs -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
            throw 'Log tree contains a reparse point; refusing recursive deletion.'
        }
        Remove-Item -LiteralPath $logs -Recurse -Force
    }
    if (Test-Path -LiteralPath $secrets) { Remove-Item -LiteralPath $secrets -Force }
    Write-Output 'Encrypted secrets and logs deleted; recovery requires a separate backup.'
} else {
    Write-Output 'Logs, encrypted secrets and binaries preserved; no data deleted.'
}
