import ast
import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from attache_bridge.config import AttacheBridgeConfig, AttacheBridgeConfigurationError
from attache_bridge import launcher, service_secrets
from attache_bridge.main import create_app


ROOT = Path(__file__).resolve().parents[1]


class ServiceSecretsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bridge-service-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bridge-secrets.dpapi.json"
        self.payload = {"version": 1, "scope": "LocalMachine",
                        "connection_string": "DSN=FAKE;PWD=synthetic-sensitive",
                        "api_token": "synthetic-sensitive-token"}
        self.envelope = {"version": 1, "scope": "LocalMachine",
                         "ciphertext": base64.b64encode(b"fake-encrypted-blob").decode()}
        self.write_envelope(self.envelope)
        self.decrypt = Mock(return_value=json.dumps(self.payload).encode())

    def write_envelope(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def assert_safe_failure(self, operation):
        with self.assertRaises(service_secrets.ServiceSecretsError) as raised:
            operation()
        self.assertEqual(service_secrets.ERROR_MESSAGE, str(raised.exception))
        self.assertNotIn("synthetic-sensitive", str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)

    def test_valid_encrypted_envelope(self):
        values = service_secrets.load_service_secrets(self.path, decrypt=self.decrypt)
        self.assertEqual(self.payload["connection_string"], values["connection_string"])
        self.assertEqual(self.payload["api_token"], values["api_token"])
        self.decrypt.assert_called_once_with(b"fake-encrypted-blob")
        self.assertNotIn("synthetic-sensitive", self.path.read_text())

    def test_missing_file_and_relative_path_fail_closed(self):
        for path in (self.path.parent / "missing", "relative.json"):
            with self.subTest(path=path):
                self.assert_safe_failure(lambda: service_secrets.load_service_secrets(path, decrypt=self.decrypt))
        self.decrypt.assert_not_called()

    def test_bad_envelopes_fail_before_decrypt(self):
        for raw in (b"not-json", b"[]", b"null", b"x" * 65537,
                    b'{"version":1,"version":1}', b"\xff"):
            with self.subTest(raw_size=len(raw)):
                self.path.write_bytes(raw)
                self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))
        for changes in ({"version": 2}, {"version": True}, {"scope": "CurrentUser"},
                        {"ciphertext": "!!!"}, {"ciphertext": ""}, {"extra": "bad"}):
            with self.subTest(changes=changes):
                self.write_envelope(dict(self.envelope, **changes))
                self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))
        self.decrypt.assert_not_called()

    def test_decryption_failure_is_redacted(self):
        self.decrypt.side_effect = RuntimeError("synthetic-sensitive-token")
        self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))

    def test_payload_corruption_missing_values_and_versions_fail_closed(self):
        for raw in (b"not-json", b"null", b"[]", b'{"version":1,"version":1}'):
            with self.subTest(raw=raw):
                self.decrypt.return_value = raw
                self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))
        for key, value in (("connection_string", ""), ("api_token", " "),
                           ("api_token", None), ("api_token", 42), ("api_token", "bad\nvalue"),
                           ("version", 2), ("scope", "CurrentUser")):
            with self.subTest(key=key, value=value):
                self.decrypt.return_value = json.dumps(dict(self.payload, **{key: value})).encode()
                self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))
        for key in self.payload:
            self.decrypt.return_value = json.dumps({k: v for k, v in self.payload.items() if k != key}).encode()
            self.assert_safe_failure(lambda: service_secrets.load_service_secrets(self.path, decrypt=self.decrypt))

    def test_config_file_and_explicit_environment_precedence(self):
        env = {"ATTACHE_BRIDGE_SECRETS_FILE": str(self.path)}
        with patch.object(service_secrets, "_decrypt_dpapi", self.decrypt):
            config = AttacheBridgeConfig.from_environment(env)
            self.assertTrue(config.configured)
            self.assertNotIn("synthetic-sensitive", repr(config))
            for name, field in (("ATTACHE_BRIDGE_API_TOKEN", "api_token"),
                                ("ATTACHE_ODBC_CONNECTION_STRING", "connection_string")):
                override = AttacheBridgeConfig.from_environment(dict(env, **{name: "explicit-value"}))
                self.assertEqual("explicit-value", getattr(override, field))
                with self.assertRaises(AttacheBridgeConfigurationError):
                    AttacheBridgeConfig.from_environment(dict(env, **{name: ""}))

    def test_complete_explicit_environment_bypasses_stale_service_file(self):
        with patch("attache_bridge.config.load_service_secrets", side_effect=AssertionError("no file read")) as load:
            for path in (str(self.path), str(self.path.parent / "missing"), ""):
                config = AttacheBridgeConfig.from_environment({"ATTACHE_BRIDGE_SECRETS_FILE": path,
                    "ATTACHE_ODBC_CONNECTION_STRING": "explicit", "ATTACHE_BRIDGE_API_TOKEN": "explicit"})
                self.assertEqual("explicit", config.connection_string)
                self.assertEqual("explicit", config.api_token)
            for name in ("ATTACHE_ODBC_CONNECTION_STRING", "ATTACHE_BRIDGE_API_TOKEN"):
                env = {"ATTACHE_BRIDGE_SECRETS_FILE": str(self.path),
                       "ATTACHE_ODBC_CONNECTION_STRING": "explicit", "ATTACHE_BRIDGE_API_TOKEN": "explicit"}
                env[name] = " "
                with self.assertRaises(AttacheBridgeConfigurationError):
                    AttacheBridgeConfig.from_environment(env)
            load.assert_not_called()

    def test_partial_override_cannot_hide_invalid_service_file(self):
        self.path.write_text("broken synthetic-sensitive", encoding="utf-8")
        for name in ("ATTACHE_ODBC_CONNECTION_STRING", "ATTACHE_BRIDGE_API_TOKEN"):
            with self.subTest(name=name), self.assertRaises(AttacheBridgeConfigurationError) as raised:
                AttacheBridgeConfig.from_environment({"ATTACHE_BRIDGE_SECRETS_FILE": str(self.path),
                                                      name: "explicit"})
            self.assertEqual(service_secrets.ERROR_MESSAGE, str(raised.exception))

    def test_manual_environment_without_file_does_not_load_dpapi(self):
        with patch("attache_bridge.config.load_service_secrets", side_effect=AssertionError("no file")):
            config = AttacheBridgeConfig.from_environment({"ATTACHE_ODBC_CONNECTION_STRING": "manual",
                "ATTACHE_BRIDGE_API_TOKEN": "manual-token", "ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS": "7"})
            self.assertEqual("manual", config.connection_string)
            self.assertEqual("manual-token", config.api_token)
            self.assertEqual(7, config.query_timeout_seconds)
            self.assertFalse(AttacheBridgeConfig.from_environment({}).configured)

    def test_bad_service_file_health_and_lookup_fail_without_repository_or_leaks(self):
        repository_factory = Mock(side_effect=AssertionError("no ODBC"))
        environment = {"ATTACHE_BRIDGE_SECRETS_FILE": str(self.path)}
        with patch.object(service_secrets, "_decrypt_dpapi", side_effect=RuntimeError("synthetic-sensitive")), \
             TestClient(create_app(config_provider=lambda: AttacheBridgeConfig.from_environment(environment),
                                   repository_factory=repository_factory)) as client:
            self.assertEqual({"status": "ok", "configured": False}, client.get("/health").json())
            for path in ("/v1/invoices/185479", "/v1/invoices?from_date=2026-09-02"):
                response = client.get(path, headers={"X-Attache-Bridge-Token": "fake"})
                self.assertEqual(503, response.status_code)
                self.assertNotIn("synthetic-sensitive", response.text)
                self.assertNotIn(str(self.path), response.text)
        repository_factory.assert_not_called()

    def test_invalid_service_file_stops_launcher_without_leak(self):
        output, server = [], Mock()
        with patch.object(service_secrets, "_decrypt_dpapi", side_effect=RuntimeError("synthetic-sensitive")):
            code = launcher.main([], environ={"ATTACHE_BRIDGE_SECRETS_FILE": str(self.path)},
                                 run_server=server, output=output.append)
        self.assertEqual(2, code)
        server.assert_not_called()
        self.assertNotIn("synthetic-sensitive", "\n".join(output))

    def test_dpapi_rejects_non_windows(self):
        with patch.object(service_secrets.os, "name", "posix"):
            self.assert_safe_failure(lambda: service_secrets._decrypt_dpapi(b"fake"))

    def test_ctypes_decrypt_disables_ui_and_zeroes_frees_output(self):
        output_buffer = (ctypes.c_ubyte * 3)(65, 66, 67)
        crypt32, kernel32 = Mock(), Mock()

        def unprotect(source, description, entropy, reserved, prompt, flags, result):
            self.assertEqual(1, flags)
            self.assertIsNone(prompt)
            self.assertEqual(4, source._obj.size)
            result._obj.size = 3
            result._obj.data = ctypes.cast(output_buffer, ctypes.POINTER(ctypes.c_ubyte))
            return True

        crypt32.CryptUnprotectData.side_effect = unprotect
        with patch.object(service_secrets.os, "name", "nt"), \
             patch.object(ctypes, "WinDLL", create=True, side_effect=[crypt32, kernel32]):
            self.assertEqual(b"ABC", service_secrets._decrypt_dpapi(b"fake"))
        self.assertEqual([0, 0, 0], list(output_buffer))
        kernel32.LocalFree.assert_called_once()


class ServiceDeploymentContractTest(unittest.TestCase):
    def test_template_is_secret_free_and_has_safety_settings(self):
        path = ROOT / "tools/attache_bridge_service/ManualDispatchAttacheBridge.xml"
        source = path.read_text(encoding="utf-8")
        root = ET.fromstring(source)
        expected = {"id": "ManualDispatchAttacheBridge", "name": "Manual Dispatch Attaché Bridge",
                    "executable": r"%BASE%\attache-bridge.exe", "workingdirectory": "%BASE%",
                    "arguments": "--host 10.254.254.23 --port 8787", "startmode": "Automatic",
                    "delayedAutoStart": "true", "interactive": "false",
                    "stoptimeout": "30 sec", "resetfailure": "1 hour", "logpath": r"%BASE%\logs",
                    "serviceaccount/prompt": "console"}
        for key, value in expected.items():
            self.assertEqual(value, root.findtext(key))
        self.assertIsNone(root.find("hidewindow"), "Keep the console available for graceful Ctrl+C")
        self.assertEqual([("restart", "10 sec"), ("restart", "30 sec"), ("restart", "60 sec")],
                         [(row.get("action"), row.get("delay")) for row in root.findall("onfailure")])
        self.assertEqual("roll-by-size", root.find("log").get("mode"))
        self.assertEqual("8", root.findtext("log/keepFiles"))
        self.assertEqual([
            ("ATTACHE_BRIDGE_SECRETS_FILE", r"%BASE%\bridge-secrets.dpapi.json"),
            ("ATTACHE_BRIDGE_CONNECTION_TIMEOUT_SECONDS", "10"),
            ("ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS", "15"),
        ], [(row.get("name"), row.get("value")) for row in root.findall("env")])
        for forbidden in ("0.0.0.0", "ATTACHE_ODBC_CONNECTION_STRING", "ATTACHE_BRIDGE_API_TOKEN",
                          "<password", "<username", "<download", "reboot", "PWD=", "DSN="):
            self.assertNotIn(forbidden, source)

    def test_scripts_have_no_external_or_operational_mutations(self):
        install = (ROOT / "tools/install_attache_bridge_service.ps1").read_text(encoding="utf-8")
        uninstall = (ROOT / "tools/uninstall_attache_bridge_service.ps1").read_text(encoding="utf-8")
        common = (ROOT / "tools/attache_bridge_service/ServiceCommon.ps1").read_text(encoding="utf-8")
        for forbidden in ("Invoke-WebRequest", "DownloadFile", "Invoke-RestMethod", "netsh",
                          "New-NetFirewallRule", "Set-NetFirewallRule", "Add-OdbcDsn", "Set-OdbcDsn",
                          "Stop-Process", "taskkill", "manual_dispatch.sqlite3", "data/logbook", "--password"):
            self.assertNotIn(forbidden.lower(), (install + uninstall + common).lower())
        for required in ("Assert-ServiceAdministrator", "Assert-ApprovedExecutable", "FileMajorPart -ne 3",
                         "-AsSecureString", "ProtectedData]::Protect", "DataProtectionScope]::LocalMachine",
                         "Set-ServicePathAcl", "ZeroFreeBSTR", "[Array]::Clear", "accountMatches",
                         "if ($Start)", "'install'", "SERVICE_INSTALLED_NOT_STARTED"):
            self.assertIn(required, install)
        self.assertNotIn("'start'", install.split("if ($Start)")[0])
        self.assertIn("if ($RemoveLocalData)", uninstall)
        self.assertNotIn("Remove-Item", uninstall.split("if ($RemoveLocalData)")[0])
        self.assertIn("Assert-RegisteredServicePath", uninstall)
        self.assertIn("$manifest.xml_sha256", uninstall)
        self.assertIn("SetAccessRuleProtection($true, $false)", common)
        self.assertIn("ReadAndExecute", common)
        self.assertIn("ReparsePoint", common)
        self.assertLess(install.index("$accountSid = Get-ServiceAccountSid"), install.index("Set-ServicePathAcl"))
        self.assertLess(install.index("Set-ServicePathAcl $secretsPath"), install.index("Read-Host"))
        before_install = install.split("Invoke-BridgeWrapper $wrapper 'install'")[0]
        self.assertIn("Assert-ServicePathAcl $deployment $accountSid", before_install)
        self.assertIn("Assert-ServicePathAcl $logs $accountSid -LogDirectory", before_install)
        self.assertIn("Assert-ServicePathAcl $secretsPath $accountSid -SecretsFile", before_install)

    def test_frozen_build_reaches_secret_loader_through_static_imports(self):
        launcher_tree = ast.parse((ROOT / "attache_bridge/launcher.py").read_text(encoding="utf-8"))
        config_tree = ast.parse((ROOT / "attache_bridge/config.py").read_text(encoding="utf-8"))
        secrets_tree = ast.parse((ROOT / "attache_bridge/service_secrets.py").read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == "attache_bridge.config"
                            for node in ast.walk(launcher_tree)))
        self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == "service_secrets" and node.level == 1
                            for node in ast.walk(config_tree)))
        self.assertTrue(any(isinstance(node, ast.Import) and any(alias.name == "ctypes" for alias in node.names)
                            for node in ast.walk(secrets_tree)))
        build = (ROOT / "tools/build_attache_bridge_windows.ps1").read_text(encoding="utf-8")
        self.assertIn('"--console"', build)
        self.assertNotIn('"--noconsole"', build)
        self.assertIn('$PythonPath -m PyInstaller @pyInstallerArguments', build)

    def test_manual_launcher_still_defaults_to_loopback(self):
        args = launcher.parse_arguments([])
        self.assertEqual("127.0.0.1", args.host)
        self.assertEqual(8787, args.port)


@unittest.skipUnless(os.name == "nt", "Windows .NET ACL behavior test")
class ServiceAclBehaviorTest(unittest.TestCase):
    def test_exact_acl_policy_and_readback_fail_closed(self):
        # Real .NET ACL objects, but all filesystem ACL I/O is mocked in PowerShell.
        script = r"""
$ErrorActionPreference = 'Stop'
. './tools/attache_bridge_service/ServiceCommon.ps1'
$serviceSid = 'S-1-5-21-100-200-300-1001'
$script:GetCalls = 0
$script:SetCalls = 0
$script:FailSet = $false
function Get-Acl { param($LiteralPath, $ErrorAction) $script:GetCalls++; return $script:ActualAcl }
function Set-Acl {
    param($LiteralPath, $AclObject, $ErrorAction)
    if ($ErrorAction -ne 'Stop') { throw 'Setter must fail closed' }
    $script:SetCalls++
    if ($script:FailSet) { throw 'Synthetic ACL write failure' }
    $script:WrittenAcl = $AclObject
}
function New-TestAcl([string]$Mode) {
    $acl = if ($Mode -eq 'file') { [Security.AccessControl.FileSecurity]::new() }
           else { [Security.AccessControl.DirectorySecurity]::new() }
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    if ($Mode -eq 'file') { $inherit = [Security.AccessControl.InheritanceFlags]::None }
    foreach ($sid in @('S-1-5-18', 'S-1-5-32-544', $serviceSid)) {
        $rights = [Security.AccessControl.FileSystemRights]::FullControl
        if ($sid -eq $serviceSid) {
            $rights = [Security.AccessControl.FileSystemRights]::ReadAndExecute
            if ($Mode -eq 'file') { $rights = [Security.AccessControl.FileSystemRights]::Read }
            if ($Mode -eq 'logs') { $rights = [Security.AccessControl.FileSystemRights]::Modify }
        }
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid), $rights, $inherit,
            [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow))
    }
    return $acl
}
function Assert-Rejected([scriptblock]$Operation) {
    $rejected = $false
    try { & $Operation } catch { $rejected = $true }
    if (-not $rejected) { throw 'Unsafe ACL accepted' }
}
foreach ($mode in @('root', 'logs', 'file')) {
    $script:ActualAcl = New-TestAcl $mode
    Set-ServicePathAcl 'FAKE-NO-IO' $serviceSid -LogDirectory:($mode -eq 'logs') -SecretsFile:($mode -eq 'file')
    $sections = [Security.AccessControl.AccessControlSections]::All
    if ($script:WrittenAcl.GetSecurityDescriptorSddlForm($sections) -ne
        $script:ActualAcl.GetSecurityDescriptorSddlForm($sections)) { throw 'Unexpected ACL written' }
}
if ($script:GetCalls -ne 3 -or $script:SetCalls -ne 3) { throw 'ACL setter did not verify readback' }
foreach ($case in @('inheritance', 'owner', 'missing', 'wrong-account', 'excess-rights', 'deny',
                    'propagation', 'inherited-ace', 'S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')) {
    $script:ActualAcl = New-TestAcl 'root'
    $sidObject = [Security.Principal.SecurityIdentifier]::new($serviceSid)
    if ($case -eq 'inheritance') { $script:ActualAcl.SetAccessRuleProtection($false, $false) }
    elseif ($case -eq 'owner') { $script:ActualAcl.SetOwner($sidObject) }
    elseif ($case -eq 'missing') { $script:ActualAcl.PurgeAccessRules($sidObject) }
    elseif ($case -eq 'inherited-ace') {
        $sddl = $script:ActualAcl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All)
        $script:ActualAcl.SetSecurityDescriptorSddlForm($sddl.Replace('(A;OICI;', '(A;OICIID;'))
    } else {
        $sid = $serviceSid
        $rights = [Security.AccessControl.FileSystemRights]::ReadAndExecute
        $propagation = [Security.AccessControl.PropagationFlags]::None
        $type = [Security.AccessControl.AccessControlType]::Allow
        if ($case -eq 'wrong-account') {
            $script:ActualAcl.PurgeAccessRules($sidObject)
            $sid = 'S-1-5-21-100-200-300-1002'
        } elseif ($case -eq 'excess-rights') { $rights = [Security.AccessControl.FileSystemRights]::FullControl }
        elseif ($case -eq 'deny') { $type = [Security.AccessControl.AccessControlType]::Deny }
        elseif ($case -eq 'propagation') { $propagation = [Security.AccessControl.PropagationFlags]::InheritOnly }
        else { $sid = $case }
        $script:ActualAcl.SetAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid), $rights,
            [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit', $propagation, $type))
    }
    Assert-Rejected { Assert-ServicePathAcl 'FAKE-NO-IO' $serviceSid }
    # Set-Acl claims success, but the readback remains unsafe: installation must fail.
    Assert-Rejected { Set-ServicePathAcl 'FAKE-NO-IO' $serviceSid }
}
$script:ActualAcl = New-TestAcl 'logs'
Assert-Rejected { Assert-ServicePathAcl 'FAKE-NO-IO' $serviceSid }
$script:ActualAcl = New-TestAcl 'root'
Assert-Rejected { Assert-ServicePathAcl 'FAKE-NO-IO' $serviceSid -SecretsFile }
$script:FailSet = $true
Assert-Rejected { Set-ServicePathAcl 'FAKE-NO-IO' $serviceSid }
function Get-Acl { param($LiteralPath, $ErrorAction) throw 'Synthetic ACL read failure' }
Assert-Rejected { Assert-ServicePathAcl 'FAKE-NO-IO' $serviceSid }
Write-Output 'ACL_BEHAVIOR_PASS'
"""
        # Process-only policy for this local, unsigned test helper; no machine policy change.
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                                 "-ExecutionPolicy", "RemoteSigned", "-Command", script],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ACL_BEHAVIOR_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
