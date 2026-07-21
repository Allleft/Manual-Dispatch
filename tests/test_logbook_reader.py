import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

from backend.services.manual_dispatch.logbook_file_service import (
    resolve_logbook_dir,
)
from tools import read_logbook


class LogbookReaderTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.logbook_dir = Path(self.temp_dir.name)

        self.older = {
            "time": "2026-06-30T23:59:59+10:00",
            "result": "FAILED",
            "workspace": "SYSTEM",
            "actor": "System",
            "action": "IMPORT_FAILED",
            "entity_id": "OLD-1",
            "summary": "Older entry.",
        }
        self.target = {
            "time": "2026-07-10T13:37:05+10:00",
            "result": "SUCCESS",
            "workspace": "DELIVERY",
            "actor": "Office Operator",
            "action": "ORDER_ASSIGNED",
            "entity_id": "184068",
            "summary": "Assigned alpha summary.",
            "driver": "John Driver",
            "vehicle": "TRUCK-RED",
            "run_sheet_id": "RUN-UNIQUE",
            "collection_id": "COLLECTION-UNIQUE",
        }
        self.newer = {
            "time": "2026-07-11T08:00:00+10:00",
            "result": "FAILED",
            "workspace": "OPSHOP",
            "actor": "运营员",
            "action": "PICKUP_COLLECTION_SAVED",
            "entity_id": "COLL-中文",
            "summary": "益店收集已保存。",
            "driver": "李师傅",
        }

        self._write_records(
            "manual_dispatch_logbook_2026-07.txt",
            [self.newer, self.target],
        )
        self._write_records(
            "manual_dispatch_logbook_2026-06.txt",
            [self.older],
        )
        (self.logbook_dir / "not_a_logbook.txt").write_text(
            "ignored",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discovers_monthly_files_and_returns_chronological_records(self):
        files = read_logbook.discover_logbook_files(self.logbook_dir)
        self.assertEqual(
            [
                "manual_dispatch_logbook_2026-06.txt",
                "manual_dispatch_logbook_2026-07.txt",
            ],
            [path.name for path in files],
        )

        records = read_logbook.read_logbook_records(self.logbook_dir)
        self.assertEqual(
            ["OLD-1", "184068", "COLL-中文"],
            [record["entity_id"] for record in records],
        )

    def test_filters_date_workspace_actor_action_result_driver_and_entity_id(self):
        records = read_logbook.read_logbook_records(self.logbook_dir)
        cases = (
            (
                {"date_from": date(2026, 7, 10), "date_to": date(2026, 7, 10)},
                ["184068"],
            ),
            ({"workspace": "delivery"}, ["184068"]),
            ({"actor": "office oper"}, ["184068"]),
            ({"action": "order_assigned"}, ["184068"]),
            ({"result": "success"}, ["184068"]),
            ({"driver": "john dri"}, ["184068"]),
            ({"entity_id": "184068"}, ["184068"]),
        )

        for filters, expected_ids in cases:
            with self.subTest(filters=filters):
                matches = read_logbook.filter_records(records, **filters)
                self.assertEqual(
                    expected_ids,
                    [record["entity_id"] for record in matches],
                )

    def test_searches_all_supported_user_facing_fields_case_insensitively(self):
        records = read_logbook.read_logbook_records(self.logbook_dir)
        search_values = (
            "alpha",
            "OFFICE OPER",
            "order_ass",
            "delivery",
            "184068",
            "JOHN DRI",
            "truck-red",
            "run-unique",
            "collection-unique",
        )

        for search in search_values:
            with self.subTest(search=search):
                matches = read_logbook.filter_records(records, search=search)
                self.assertEqual(
                    ["184068"],
                    [record["entity_id"] for record in matches],
                )

    def test_limit_is_optional_and_applied_after_matching(self):
        records = read_logbook.read_logbook_records(self.logbook_dir)

        self.assertEqual(3, len(read_logbook.filter_records(records)))
        self.assertEqual(2, len(read_logbook.filter_records(records, limit=2)))
        self.assertEqual([], read_logbook.filter_records(records, limit=0))

    def test_text_output_is_concise_and_handles_missing_fields(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = read_logbook.main(
                [
                    "--logbook-dir",
                    str(self.logbook_dir),
                    "--entity-id",
                    "184068",
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(
            "2026-07-10T13:37:05+10:00 | SUCCESS | DELIVERY | "
            "Office Operator | ORDER_ASSIGNED | Assigned alpha summary.\n",
            stdout.getvalue(),
        )
        self.assertNotIn("{", stdout.getvalue())
        self.assertEqual("- | - | - | - | - | -", read_logbook.format_text_record({}))

    def test_jsonl_output_preserves_non_ascii_and_each_line_is_valid_json(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = read_logbook.main(
                [
                    "--logbook-dir",
                    str(self.logbook_dir),
                    "--format",
                    "jsonl",
                ]
            )

        output = stdout.getvalue()
        parsed = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(0, exit_code)
        self.assertEqual([self.older, self.target, self.newer], parsed)
        self.assertIn("运营员", output)
        self.assertIn("益店收集已保存。", output)
        self.assertNotIn("\\u8fd0", output)

    def test_malformed_lines_warn_with_filename_and_line_number_then_continue(self):
        malformed_dir = self.logbook_dir / "malformed"
        malformed_dir.mkdir()
        path = malformed_dir / "manual_dispatch_logbook_2026-08.txt"
        path.write_text(
            json.dumps(self.target, ensure_ascii=False)
            + "\n"
            + "{raw secret-like malformed content\n"
            + "\n"
            + json.dumps(self.newer, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        stderr = io.StringIO()

        records = read_logbook.read_logbook_records(malformed_dir, stderr=stderr)

        warning = stderr.getvalue()
        self.assertEqual(2, len(records))
        self.assertIn("manual_dispatch_logbook_2026-08.txt:2", warning)
        self.assertNotIn("raw secret-like malformed content", warning)

    def test_unreadable_matching_path_warns_and_other_files_continue(self):
        unreadable = self.logbook_dir / "manual_dispatch_logbook_2026-01.txt"
        unreadable.mkdir()
        stderr = io.StringIO()

        records = read_logbook.read_logbook_records(
            self.logbook_dir,
            stderr=stderr,
        )

        self.assertEqual(3, len(records))
        self.assertIn(unreadable.name, stderr.getvalue())
        self.assertIn("unable to read file", stderr.getvalue())

    def test_directory_resolution_precedence_and_cli_environment_use(self):
        environment = {"MANUAL_DISPATCH_LOGBOOK_DIR": "environment-logbook"}
        self.assertEqual(
            Path("cli-logbook"),
            resolve_logbook_dir("cli-logbook", environ=environment),
        )
        self.assertEqual(
            Path("environment-logbook"),
            resolve_logbook_dir(environ=environment),
        )
        self.assertEqual(Path("data/logbook"), resolve_logbook_dir(environ={}))

        stdout = io.StringIO()
        with patch.dict(
            os.environ,
            {"MANUAL_DISPATCH_LOGBOOK_DIR": str(self.logbook_dir)},
        ), redirect_stdout(stdout):
            exit_code = read_logbook.main(["--limit", "1"])
        self.assertEqual(0, exit_code)
        self.assertTrue(stdout.getvalue().startswith(self.older["time"]))

    def test_invalid_date_and_limit_arguments_use_argparse_errors(self):
        parser = read_logbook.build_parser()
        for arguments in (
            ["--date-from", "2026-7-01"],
            ["--date-to", "2026-02-30"],
            ["--limit", "-1"],
        ):
            with self.subTest(arguments=arguments):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                    parser.parse_args(arguments)
                self.assertNotEqual(0, caught.exception.code)
                self.assertIn("error:", stderr.getvalue())

    def test_query_does_not_modify_input_files(self):
        paths = sorted(self.logbook_dir.iterdir())
        before = {
            path.name: (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in paths
        }

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            read_logbook.main(
                [
                    "--logbook-dir",
                    str(self.logbook_dir),
                    "--search",
                    "operator",
                    "--format",
                    "jsonl",
                ]
            )

        after_paths = sorted(self.logbook_dir.iterdir())
        after = {
            path.name: (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
            for path in after_paths
        }
        self.assertEqual(before, after)

    def test_no_matches_is_success_with_no_output(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = read_logbook.main(
                [
                    "--logbook-dir",
                    str(self.logbook_dir),
                    "--entity-id",
                    "DOES-NOT-EXIST",
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stdout.getvalue())

    def _write_records(self, filename, records):
        path = self.logbook_dir / filename
        path.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False) + "\n"
                for record in records
            ),
            encoding="utf-8",
        )


class FrontendLogoutStaticContractTest(unittest.TestCase):
    def test_logout_api_and_local_cleanup_contract(self):
        api_root = PROJECT_ROOT / "frontend" / "js" / "api"
        api_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                api_root / "manual-dispatch-api.js",
                *sorted((api_root / "manual-dispatch").glob("*.js")),
            ]
        )
        auth_source = (
            PROJECT_ROOT / "frontend" / "js" / "actions" / "auth-actions.js"
        ).read_text(encoding="utf-8")
        app_source = (PROJECT_ROOT / "frontend" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("export async function apiLogoutAccount()", api_source)
        logout_api = api_source.split(
            "export async function apiLogoutAccount()", 1
        )[1].split("export async function", 1)[0]
        self.assertIn("/api/manual-dispatch/auth/logout", logout_api)
        self.assertIn('method: "POST"', logout_api)
        self.assertNotIn("body:", logout_api)
        for forbidden in ("account_name", "account_id", "actor", "cookie"):
            self.assertNotIn(forbidden, logout_api)

        logout_action = auth_source.split("function logoutAccount()", 1)[1].split(
            "async function handleLogin", 1
        )[0]
        invalidation_action = auth_source.split(
            "function invalidateAccountSession", 1
        )[1].split("function logoutAccount", 1)[0]
        self.assertIn("apiLogoutAccount()", logout_action)
        self.assertIn("invalidateAccountSession();", logout_action)
        self.assertIn("clearAccountSession();", invalidation_action)
        self.assertIn("state.accountName = \"\";", invalidation_action)
        self.assertIn("state.accountId = \"\";", invalidation_action)
        self.assertIn("state.isLoggedIn = false;", invalidation_action)
        self.assertIn('state.authMode = "login";', invalidation_action)
        self.assertIn("clearAuthenticatedTransientState();", invalidation_action)
        self.assertIn("operator cookie may remain", logout_action)
        self.assertEqual(1, invalidation_action.count("renderBoard();"))
        self.assertIn("void authActions.logoutAccount();", app_source)


if __name__ == "__main__":
    unittest.main()
