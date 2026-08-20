from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import unittest

from attache_bridge import launcher
from attache_bridge.main import app


ROOT = Path(__file__).resolve().parents[1]


class AttacheBridgeLauncherTest(unittest.TestCase):
    def test_default_host_and_port_are_loopback_only(self):
        args = launcher.parse_arguments([])

        self.assertEqual("127.0.0.1", args.host)
        self.assertEqual(8787, args.port)

    def test_explicit_host_and_port_are_supported(self):
        args = launcher.parse_arguments(
            ["--host", "192.0.2.10", "--port", "9876"]
        )

        self.assertEqual("192.0.2.10", args.host)
        self.assertEqual(9876, args.port)

    def test_invalid_port_and_unsafe_host_are_rejected(self):
        invalid_argument_sets = (
            ["--port", "0"],
            ["--port", "65536"],
            ["--port", "not-a-port"],
            ["--host", ""],
            ["--host", "127.0.0.1\nsecret"],
        )
        for arguments in invalid_argument_sets:
            with self.subTest(arguments=arguments):
                with redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit):
                        launcher.parse_arguments(arguments)

    def test_launcher_imports_and_runs_the_actual_bridge_app(self):
        calls = []
        output = []

        def run_server(application, **kwargs):
            calls.append((application, kwargs))

        exit_code = launcher.main(
            [],
            environ={},
            run_server=run_server,
            output=output.append,
        )

        self.assertIs(app, launcher.app)
        self.assertEqual(0, exit_code)
        self.assertEqual(
            [(app, {"host": "127.0.0.1", "port": 8787})],
            calls,
        )
        self.assertIn("ODBC configuration present: no", output)
        self.assertIn("Bridge token configured: no", output)

    def test_launcher_reports_presence_without_rendering_secrets(self):
        output = []
        connection_string = "DSN=FAKE;UID=hidden-user;PWD=hidden-password"
        api_token = "hidden-bridge-token"

        exit_code = launcher.main(
            ["--host", "127.0.0.1", "--port", "8787"],
            environ={
                "ATTACHE_ODBC_CONNECTION_STRING": connection_string,
                "ATTACHE_BRIDGE_API_TOKEN": api_token,
            },
            run_server=lambda _application, **_kwargs: None,
            output=output.append,
        )

        rendered = "\n".join(output)
        self.assertEqual(0, exit_code)
        self.assertIn("ODBC configuration present: yes", rendered)
        self.assertIn("Bridge token configured: yes", rendered)
        self.assertNotIn(connection_string, rendered)
        self.assertNotIn("hidden-user", rendered)
        self.assertNotIn("hidden-password", rendered)
        self.assertNotIn(api_token, rendered)

    def test_invalid_timeout_configuration_exits_without_server_or_secret(self):
        output = []
        server_calls = []

        exit_code = launcher.main(
            [],
            environ={
                "ATTACHE_ODBC_CONNECTION_STRING": "DSN=FAKE;PWD=hidden",
                "ATTACHE_BRIDGE_API_TOKEN": "hidden-token",
                "ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS": "invalid",
            },
            run_server=lambda *_args, **_kwargs: server_calls.append(True),
            output=output.append,
        )

        rendered = "\n".join(output)
        self.assertEqual(2, exit_code)
        self.assertEqual([], server_calls)
        self.assertIn("Bridge configuration is invalid.", rendered)
        self.assertNotIn("hidden", rendered)

    def test_build_and_remote_runbook_contracts_are_packaging_only(self):
        build_script = (
            ROOT / "tools" / "build_attache_bridge_windows.ps1"
        ).read_text(encoding="utf-8")
        runbook = (
            ROOT / "docs" / "attache-bridge-windows-x64-remote-smoke-test.txt"
        ).read_text(encoding="utf-8")

        for required in (
            '"--onefile"',
            '"--console"',
            "PYTHON_BITS=",
            "Get-FileHash",
            "Compress-Archive",
        ):
            self.assertIn(required, build_script)
        self.assertNotIn("pip install", build_script.lower())
        self.assertNotIn("--windowed", build_script.lower())
        self.assertNotIn("0.0.0.0", build_script)

        self.assertNotIn("python -", runbook.lower())
        self.assertNotIn("pip install", runbook.lower())
        self.assertNotIn("set-executionpolicy", runbook.lower())
        self.assertIn("127.0.0.1", runbook)
        self.assertIn("X-Attache-Bridge-Token", runbook)


if __name__ == "__main__":
    unittest.main()
