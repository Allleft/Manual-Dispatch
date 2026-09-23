# Attaché Bridge Windows Service (WinSW 3.x)

This runbook is an operator-controlled deployment path, not evidence that the
new service has been installed or tested on the real host. No automatic binary
download, DSN setup, firewall change, or NAS work is performed by these scripts.

## Verified Archive gate

The authorized operator verified Archive-running-with-Bridge successfully on
**2026-09-22**. Frozen build base: `072492149f212f2935cfc85c1e0554e99c83dfc4`;
EXE SHA256: `E80F1C98FA5C3A168B404D20C080618F3FA5A02FBF405BDBC440FD0012F8731F`.
Invoice 185479 returned HTTP 200 in approximately 677 ms with the expected
header and six raw lines. Bridge and port 8787 stayed available, no external
established TCP session was observable, and Archive started after normal users
exited. This evidence was supplied by the operator, not reproduced here.

```
BRIDGE_RUNNING_ARCHIVE_SMOKE_PASS
ODBC_SESSION_RELEASE_GATE_PASS
```

There is currently **no requirement to stop Bridge before Archive**. A running
Bridge is not the same as an active ODBC/FairCom session. The service still uses
request-scoped connections, one per Direct request or Current/Future batch,
`finally` cleanup and early `pyodbc.pooling = False`. `/health` opens no ODBC
connection; authentication is checked before repository creation.

## Boundaries and modes

- Manual/frozen smoke mode remains available. The unchanged launcher defaults
  to `127.0.0.1:8787`; explicit authorized host arguments are still supported.
- Service mode wraps the same console EXE with WinSW, bound specifically to
  `10.254.254.23:8787`. Never bind `0.0.0.0`.
- Service mode explicitly sets `ATTACHE_BRIDGE_CONNECTION_TIMEOUT_SECONDS=10`
  and `ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS=15`: ODBC connection timeout is
  10 seconds and query timeout is 15 seconds. These non-secret values match the
  already completed real Bridge smoke/business validation, avoiding a change
  to the generic 5/5-second defaults when switching to Service mode. Generic
  configuration and manual-launcher defaults remain unchanged. This alignment
  does not mean the Windows Service itself has been real-host validated.
- Keep the existing approved firewall boundary:
  **office `192.168.18.0/24` -> `10.254.254.23:8787`**.
- Do not modify FairCom data, DSN or firewall during installation. Do not
  convert the existing 64-bit User DSN `Manual Dispatch - Attache Test` to a
  System DSN. Do not terminate unknown Attaché/FairCom processes.
- Never place passwords/tokens, even encrypted production secret files, in Git,
  normal documentation, screenshots, PowerShell transcripts, or support dumps.
- Do not touch production SQLite, formal Logbook, NAS or other service processes.

## Dependencies and identity

Use an operator-supplied, independently approved **WinSW 3.x x64** executable.
Verify its exact release/prerelease version, publisher/provenance, SHA256 and
the supported XML/console credential-prompt behavior before executing it. The
installer checks SHA256 and file major version 3; these checks are not a trust
decision. No wrapper binary is committed or downloaded by this project.
Primary references: [WinSW v3 XML](https://github.com/winsw/winsw/blob/v3/docs/xml-config-file.md),
[CLI](https://github.com/winsw/winsw/blob/v3/docs/cli-commands.md).

Use the same authorized named Windows account that owns the existing 64-bit
User DSN, not LocalSystem/LocalService. Supply the account name at install time;
no reusable username is embedded in the template. WinSW prompts interactively
for Windows account credentials and grants service logon. Account/group-policy,
User DSN visibility in the service logon context, and ODBC permissions must be
verified by the operator. Do not resolve a failure by changing DSN scope.

### Mandatory real-host identity/DSN preflight (before service start)

The service MUST use the exact Windows identity whose profile contains
`Manual Dispatch - Attache Test`. LocalSystem, LocalService or a different
administrator cannot be assumed to see it. Before installation, the operator
must run the following in a **64-bit PowerShell session logged on as that exact
user with its normal profile loaded**, not an installer/admin identity substituted
via elevation. These are metadata-only checks, not an ODBC connection; they
do not print DSN attributes or credentials. Replace only the account placeholder.

```powershell
$expectedAccount = '<DOMAIN-or-MACHINE>\<authorized-User-DSN-owner>'
$expectedSid = ([Security.Principal.NTAccount]::new($expectedAccount)).Translate(
    [Security.Principal.SecurityIdentifier]).Value
if (-not [Environment]::Is64BitProcess) { throw 'Use 64-bit PowerShell.' }
if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne $expectedSid) {
    throw 'Wrong identity for User DSN preflight.'
}
$dsn = @(Get-OdbcDsn -Name 'Manual Dispatch - Attache Test' -DsnType User `
    -Platform '64-bit' -ErrorAction Stop)
if ($dsn.Count -ne 1) { throw 'Required 64-bit User DSN is unavailable.' }
Write-Output 'USER_DSN_IDENTITY_PREFLIGHT_PASS'
```

After installation, in the elevated control session and **before the first start**,
resolve the same expected account SID and compare it with the installed identity:

```powershell
$expectedAccount = '<DOMAIN-or-MACHINE>\<authorized-User-DSN-owner>'
$expectedSid = ([Security.Principal.NTAccount]::new($expectedAccount)).Translate(
    [Security.Principal.SecurityIdentifier]).Value
$installedService = Get-CimInstance Win32_Service -Filter "Name='ManualDispatchAttacheBridge'"
$installedSid = ([Security.Principal.NTAccount]::new($installedService.StartName)).Translate(
    [Security.Principal.SecurityIdentifier]).Value
if ($installedSid -ne $expectedSid) { throw 'Installed service identity mismatch; do not start.' }
```

The installer also enforces this SID equality. These checks do not prove profile
availability during service logon or after reboot: the service-mode lookup and
reboot acceptance below remain mandatory. Stop on failure; do not convert the
User DSN to System DSN or print credentials to diagnose it.

## Secrets and ACLs

`ATTACHE_BRIDGE_SECRETS_FILE` selects an absolute local JSON file. Envelope and
decrypted payload are both version 1 with `scope=LocalMachine`; the envelope
contains only version, scope and base64 DPAPI ciphertext. The encrypted payload
contains connection_string and api_token. The loader bounds file size, rejects
unsupported versions, missing/blank fields, duplicate JSON fields, malformed
base64 and decryption failures with a fixed error message. When file loading is
required by the precedence rules below, an invalid file fails closed.

The Windows installer uses .NET DPAPI; Python uses stdlib ctypes to decrypt.
Machine scope is intentional because an elevated installer may be a different
identity from the service user. DPAPI is bound to that Windows machine, not to
this service or user. **Any local principal able to read the blob can potentially
decrypt it on that machine**; administrators/SYSTEM are trusted. NTFS permissions
are an essential additional boundary, not optional hardening. See
[Microsoft DPAPI scope](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.dataprotectionscope).

The deployment root and log directory disable inherited ACLs. They grant only
SYSTEM and Administrators full control, plus the exact service-account SID:
read/execute on the root, Modify on logs. The secrets file independently disables
inheritance and grants that SID Read only (not write/execute); SYSTEM and
Administrators retain full control. Its ACL is established on an empty file
before credentials are requested, then verified again after ciphertext is written.

Each ACL write is followed by `Get-Acl` read-back verification of the actual
protected/canonical DACL, Administrators owner, exactly three explicit allow ACEs,
exact SIDs/rights, inheritance and propagation flags. Unexpected, inherited,
missing, overprivileged or deny ACEs fail closed. Root/log/file checks run again
immediately before WinSW installation. Ordinary Users, Authenticated Users and
Everyone are never granted access. ACL read/write/verification failures abort
installation. This verifies the filesystem DACL policy, not a simulation of every
Windows token/group privilege. If the chosen account is already an administrator,
its existing group privileges still apply. The file is never written plaintext;
decrypted values necessarily exist briefly in process memory. Native buffers
are zeroed/freed, but immutable managed/Python strings cannot be guaranteed erased.

Explicit `ATTACHE_ODBC_CONNECTION_STRING` / `ATTACHE_BRIDGE_API_TOKEN` environment
variables remain the manual-development path. Exact precedence:

- Both keys explicitly present: use both environment values and **never open or
  decrypt the service file**, even if a stale/missing path remains configured.
  Empty values never fall back to the file; incomplete credentials cannot start.
- Only one key present, with a service file selected: require a valid DPAPI file
  for the other value, then override the supplied field. Blank overrides fail closed.
- Neither key present, with a service file selected: require both values from
  the valid DPAPI payload. Without a file, retain existing environment-only behavior.

Review machine/service-user environment before installation; installer refuses
visible process/machine secret overrides rather than silently preferring stale values.
Do not export or print secret environment contents while troubleshooting.

## Prepare and install (does not start)

1. Build a fresh x64 frozen EXE containing this service-secret loader using the
   unchanged `tools/build_attache_bridge_windows.ps1` and an approved build
   environment. The previously verified SHA above identifies the old smoke EXE,
   **not** a replacement hash for the new build. Keep packaging credential-free.
   **Do not reuse the 0724921 EXE for service mode**: it lacks this loader.
   The static import chain is `launcher -> config -> service_secrets -> ctypes`;
   PyInstaller recursively analyzes these imports, so no hidden-import addition
   or pywin32 dependency is needed. `crypt32.dll`/`kernel32.dll` are Windows OS
   components, not repository artifacts. Keep the existing `--console` build.
   This is a source/build-path review, not a freshly built EXE verification;
   validate DPAPI loading and graceful stopping with the newly hashed binary.
   See [PyInstaller import analysis](https://pyinstaller.org/en/stable/operating-mode.html#analysis-finding-the-files-your-program-needs).
2. Supply independently verified hashes for the new Bridge and WinSW binaries.
   Keep the previous known-good manual EXE and private operational configuration
   available for rollback. Plan a controlled switchover of the known old Bridge
   listener; installer does not stop it or evict anything from port 8787.
3. Open elevated Windows PowerShell 5.1+ on the approved host. Choose a new
   dedicated NTFS directory directly under Program Files, named
   `ManualDispatchAttacheBridge` or `ManualDispatchAttacheBridge-<version>`.
   Existing directories/services and reparse-point paths are refused.
4. Run (replace placeholders; hashes and account name are non-secret):

```powershell
.\tools\install_attache_bridge_service.ps1 `
  -WinSWPath 'C:\Approved\WinSW-x64.exe' -WinSWSha256 '<verified-wrapper-sha256>' `
  -BridgePath 'C:\Approved\attache-bridge.exe' -BridgeSha256 '<new-bridge-sha256>' `
  -ServiceAccount '<DOMAIN-or-MACHINE>\<authorized-User-DSN-owner>'
```

The script securely prompts for the approved full ODBC connection string
(existing DSN plus UID/PWD) and shared Bridge token. Do not pass either as CLI
arguments. WinSW then separately prompts for the **same** Windows account and
password. A post-install SID check rejects an account mismatch and uninstalls
that newly created service. Passwords are not put in XML or wrapper arguments.
The non-secret manifest records Bridge/WinSW/XML hashes and the account SID.

Default completion is `SERVICE_INSTALLED_NOT_STARTED`. `-Start` is an explicit
opt-in; omit it for the first deployment. `-WhatIf` performs preflight but no
provisioning, prompts or service install. On a partial failure, inspect the
service registration and protected artifacts; do not blindly rerun/overwrite.

## Start, stop, health and acceptance

Service ID: `ManualDispatchAttacheBridge`; display name: `Manual Dispatch Attaché Bridge`.
Delayed automatic startup; failure retries 10/30/60 seconds (60 seconds repeats
for every subsequent failure), reset after 1 hour of healthy operation;
no reboot action or interactive desktop. Logs roll at 10 MB, retaining 8 files
per stdout/stderr stream. Review wrapper logs too and monitor disk usage.
`hidewindow` is deliberately omitted (WinSW default false): `hidewindow=true`
sets `CreateNoWindow=true`, which can remove the console needed for Ctrl+C.
The service runs in Session 0 with `interactive=false`; do not suppress its
console at the expense of graceful stop. WinSW first attempts Ctrl+C, waits
up to 30 seconds, and uses forced termination as the timeout fallback. WinSW
can also force termination if signal delivery itself fails; treat that as a
failed graceful-stop acceptance, not proof of normal cleanup. See
[WinSW stop/hidewindow semantics](https://github.com/winsw/winsw/blob/v3/docs/xml-config-file.md)
and [Windows console signal requirements](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent).

Required acceptance: **service stop -> graceful Bridge termination when possible
-> child Bridge processes exit -> port 8787 closes -> no retained ODBC/FairCom
session**. Verify this on the rebuilt frozen executable; unit tests cannot prove
console/control-handler behavior across WinSW and the PyInstaller child processes.

```powershell
$wrapper = 'C:\Program Files\ManualDispatchAttacheBridge\ManualDispatchAttacheBridge.exe'
& $wrapper start --no-elevate
Get-Service ManualDispatchAttacheBridge
Invoke-RestMethod 'http://10.254.254.23:8787/health'
& $wrapper stop --no-elevate
& $wrapper start --no-elevate
& $wrapper restart --no-elevate
```

Perform these only during an approved deployment window:

1. Confirm the known previous manual Bridge is stopped by its responsible
   operator and port 8787 is free. Never kill an unknown listener.
2. Complete the identity/User DSN preflight above before starting. Start the
   service; confirm the exact registered path/account, `/health`
   returns configured=true, and only the approved interface/port listens.
3. From authenticated Manual Dispatch perform a known Direct lookup (185479)
   and review expected header/six lines. Confirm wrong/missing tokens are denied.
   A healthy HTTP endpoint alone does not prove User DSN visibility.
4. Leave the service running; verify no retained observable FairCom connection.
   The September manual-process Archive gate already passed; re-observe after
   changing to service identity without claiming this deployment was pre-tested.
5. Stop/restart the service with no active lookup; verify graceful shutdown in
   logs (not routine forced termination), old child processes exit, port 8787
   closes, no ODBC/FairCom session remains, new health/lookup works and no credential
   content appears in protected logs. In a disposable/approved test window also
   verify unexpected-exit recovery, never by killing unrelated processes.
6. At an approved reboot, verify delayed autostart works without an interactive
   login. Recheck health, lookup, log ACLs and session release. Stop rollout if
   profile/DSN/service-logon/DPAPI acceptance fails. Do not change firewall/DSN.

## Stop/uninstall, rollback and rotation

```powershell
.\tools\uninstall_attache_bridge_service.ps1
```

The script verifies deployment identity/hashes, stops only this registered
service, waits for stopped state, and uninstalls it. Binaries, encrypted secrets
and logs are retained by default. `-RemoveLocalData` explicitly deletes only
the validated local secrets file and log directory after service removal; it
requires the normal high-impact confirmation and has no built-in recovery.
Keep a separately authorized backup before that flag. No broad directory wipe
or unrelated process termination is used.

After confirming the service stopped and port released, the operator may run
the retained known-good manual EXE with its approved private environment and
explicit authorized bind, then check health and one invoice. Never run manual
and service modes on the same listener simultaneously. For an upgrade or secret
rotation, stop/uninstall while preserving the previous directory, then provision
a new version-suffixed directory with reviewed binaries and new hidden inputs.
Do not copy machine-DPAPI blobs to another host and expect them to work. If install
failed before its manifest was written, retain the directory for administrator
review; the uninstaller intentionally refuses an unidentified directory.
