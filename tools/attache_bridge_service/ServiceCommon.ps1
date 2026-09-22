# Shared helpers only; dot-sourcing this file performs no deployment operations.
Set-StrictMode -Version Latest
$BridgeServiceId = 'ManualDispatchAttacheBridge'

function Assert-ServiceAdministrator {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Windows is required.'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run service provisioning from an elevated Administrator PowerShell.'
    }
}

function Assert-NoReparsePoint([string]$Path) {
    $candidate = [IO.Path]::GetFullPath($Path)
    while ($candidate) {
        if (Test-Path -LiteralPath $candidate) {
            if ((Get-Item -LiteralPath $candidate -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Reparse points are not permitted in service artifact paths.'
            }
        }
        $candidate = [IO.Path]::GetDirectoryName($candidate)
    }
}

function Resolve-ServiceDirectory([string]$Path) {
    if ($Path -notmatch '^[A-Za-z]:\\' -or $Path.Contains('%')) {
        throw 'Use an absolute local drive path without environment expansion.'
    }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    # Restrict deployment to a dedicated child of Program Files, never a repo/data root.
    $parent = [IO.Path]::GetDirectoryName($full)
    if ($parent -ine [IO.Path]::GetFullPath($env:ProgramFiles).TrimEnd('\') -or
        [IO.Path]::GetFileName($full) -notmatch '^ManualDispatchAttacheBridge(?:-[A-Za-z0-9._-]+)?$') {
        throw 'Use a dedicated Program Files\ManualDispatchAttacheBridge[-version] directory.'
    }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($full))
    if ($drive.DriveFormat -ne 'NTFS') { throw 'The deployment drive must be NTFS.' }
    Assert-NoReparsePoint $full
    return $full
}

function Assert-ApprovedExecutable([string]$Path, [string]$ExpectedHash) {
    if ($ExpectedHash -notmatch '^[A-Fa-f0-9]{64}$' -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'An existing approved executable and independently verified SHA256 are required.'
    }
    Assert-NoReparsePoint $Path
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ine $ExpectedHash) {
        throw 'Executable SHA256 verification failed.'
    }
}

function Assert-ServicePathAcl([string]$Path, [string]$AccountSid, [switch]$LogDirectory, [switch]$SecretsFile) {
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $expected = @{
        'S-1-5-18' = [Security.AccessControl.FileSystemRights]::FullControl
        'S-1-5-32-544' = [Security.AccessControl.FileSystemRights]::FullControl
        $AccountSid = [Security.AccessControl.FileSystemRights]::ReadAndExecute
    }
    if ($LogDirectory) { $expected[$AccountSid] = [Security.AccessControl.FileSystemRights]::Modify }
    if ($SecretsFile) { $expected[$AccountSid] = [Security.AccessControl.FileSystemRights]::Read }
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    if ($SecretsFile) { $inherit = [Security.AccessControl.InheritanceFlags]::None }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if (-not $acl.AreAccessRulesProtected -or -not $acl.AreAccessRulesCanonical -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544' -or
        $rules.Count -ne 3) { throw 'Service ACL verification failed; installation refused.' }
    $seen = @{}
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        if (-not $expected.ContainsKey($sid) -or $seen.ContainsKey($sid)) {
            throw 'Service ACL verification failed; installation refused.'
        }
        # .NET adds Synchronize to allow ACEs; compare the complete rights mask.
        $rights = $expected[$sid] -bor [Security.AccessControl.FileSystemRights]::Synchronize
        if ($rule.IsInherited -or $rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $rule.FileSystemRights -ne $rights -or $rule.InheritanceFlags -ne $inherit -or
            $rule.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None) {
            throw 'Service ACL verification failed; installation refused.'
        }
        $seen[$sid] = $true
    }
}

function Set-ServicePathAcl([string]$Path, [string]$AccountSid, [switch]$LogDirectory, [switch]$SecretsFile) {
    $acl = if ($SecretsFile) { [Security.AccessControl.FileSecurity]::new() }
           else { [Security.AccessControl.DirectorySecurity]::new() }
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    if ($SecretsFile) { $inherit = [Security.AccessControl.InheritanceFlags]::None }
    foreach ($sidText in @('S-1-5-18', 'S-1-5-32-544', $AccountSid)) {
        $sid = [Security.Principal.SecurityIdentifier]::new($sidText)
        $rights = [Security.AccessControl.FileSystemRights]::FullControl
        if ($sidText -eq $AccountSid) {
            $rights = [Security.AccessControl.FileSystemRights]::ReadAndExecute
            if ($LogDirectory) { $rights = [Security.AccessControl.FileSystemRights]::Modify }
            if ($SecretsFile) { $rights = [Security.AccessControl.FileSystemRights]::Read }
        }
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid, $rights, $inherit, [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
    Assert-ServicePathAcl $Path $AccountSid -LogDirectory:$LogDirectory -SecretsFile:$SecretsFile
}

function Get-ServiceAccountSid([string]$Account) {
    if ($Account.StartsWith('.\')) { $Account = $env:COMPUTERNAME + '\' + $Account.Substring(2) }
    $sid = ([Security.Principal.NTAccount]::new($Account)).Translate([Security.Principal.SecurityIdentifier]).Value
    if ($sid -notmatch '^S-1-5-21-' ) {
        throw 'Specify the authorized named Windows user that owns the existing User DSN.'
    }
    return $sid
}

function Invoke-BridgeWrapper([string]$Wrapper, [string]$Action) {
    & $Wrapper $Action --no-elevate
    if ($LASTEXITCODE -ne 0) { throw "WinSW $Action failed; leave artifacts intact for review." }
}

function Assert-RegisteredServicePath($Service, [string]$Wrapper) {
    if ($Service.PathName -cne $Wrapper -and $Service.PathName -cne ('"' + $Wrapper + '"')) {
        throw 'Registered service path differs; refusing to control an unknown service.'
    }
}
