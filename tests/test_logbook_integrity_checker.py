import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import check_logbook_integrity as checker
from tools.logbook_contract import (
    ALLOWED_RESULTS,
    ALLOWED_WORKSPACES,
    INCIDENT_ANNOTATION_ACTION,
    INCIDENT_ANNOTATION_ACTIONS,
    INTEGRITY_INCIDENT_ANNOTATION_ACTION,
    KNOWN_ACTIONS,
    LOGBOOK_FILENAME_PATTERN,
    LOGBOOK_FILENAME_REGEX,
    NON_EMPTY_STRING_FIELDS,
    NULLABLE_STRING_FIELDS,
    REQUIRED_FIELDS,
)


MAINTENANCE_ACTIONS = {
    "REGULAR_WORKBOOK_IMPORT_COMPLETED",
    "ONCALL_WORKBOOK_IMPORT_COMPLETED",
    "COUNTRYSIDE_WORKBOOK_IMPORT_COMPLETED",
    "SOURCE_DRIVER_BACKFILL_DRY_RUN",
    "SOURCE_DRIVER_BACKFILL_APPLIED",
    "LEGACY_WORKSPACE_MIGRATION_DRY_RUN",
    "LEGACY_WORKSPACE_MIGRATION_APPLIED",
}


class LogbookIntegrityCheckerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.case_number = 0

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_contract_registry_contains_expected_actions_only(self):
        self.assertEqual(48, len(KNOWN_ACTIONS))
        self.assertEqual(
            {
                "LOGBOOK_TEST_DATA_ANNOTATED",
                "LOGBOOK_INTEGRITY_INCIDENT_ANNOTATED",
            },
            INCIDENT_ANNOTATION_ACTIONS,
        )
        self.assertEqual("LOGBOOK_TEST_DATA_ANNOTATED", INCIDENT_ANNOTATION_ACTION)
        self.assertIn(INTEGRITY_INCIDENT_ANNOTATION_ACTION, KNOWN_ACTIONS)
        self.assertTrue(MAINTENANCE_ACTIONS.issubset(KNOWN_ACTIONS))
        self.assertFalse(
            any(
                "ARCHIVE" in action or "RETENTION" in action
                for action in KNOWN_ACTIONS
            )
        )

    def test_contract_filename_constants_match_only_real_padded_months(self):
        self.assertEqual(
            "manual_dispatch_logbook_*.txt",
            LOGBOOK_FILENAME_PATTERN,
        )
        self.assertIsNotNone(
            LOGBOOK_FILENAME_REGEX.fullmatch(
                "manual_dispatch_logbook_2026-07.txt"
            )
        )
        for filename in (
            "manual_dispatch_logbook_2026-7.txt",
            "manual_dispatch_logbook_2026-13.txt",
            "manual_dispatch_logbook_2026-07-copy.txt",
            "manual_dispatch_logbook_\u0662\u0660\u0662\u0666-07.txt",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(LOGBOOK_FILENAME_REGEX.fullmatch(filename))

    def test_all_known_actions_results_workspaces_and_offsets_pass(self):
        records = []
        results = sorted(ALLOWED_RESULTS)
        workspaces = sorted(ALLOWED_WORKSPACES)
        offsets = ("+10:00", "+11:00", "Z")
        for index, action in enumerate(sorted(KNOWN_ACTIONS)):
            entity_id = (
                "incident-1"
                if action == INCIDENT_ANNOTATION_ACTION
                else f"entity-{index}"
            )
            records.append(
                self._valid_record(
                    time=f"2026-07-14T10:30:00{offsets[index % 3]}",
                    result=results[index % len(results)],
                    workspace=workspaces[index % len(workspaces)],
                    actor="\u8fd0\u8425\u5458",
                    action=action,
                    entity_id=entity_id,
                    summary="\u5b8c\u6574\u6027\u68c0\u67e5\u901a\u8fc7\u3002",
                )
            )

        result = self._check_records(records)

        self.assertEqual(48, result.records_checked)
        self.assertEqual(0, result.error_count)
        self.assertEqual(0, result.warning_count)

    def test_nullable_fields_empty_metadata_and_extra_fields_pass(self):
        record = self._valid_record(extra_top_level={"future": True})
        for name in NULLABLE_STRING_FIELDS:
            record[name] = None

        result = self._check_records([record])

        self.assertTrue(result.ok)
        self.assertEqual({}, record["metadata"])

    def test_invalid_candidate_filenames_are_reported_and_checked(self):
        for filename in (
            "manual_dispatch_logbook_2026-7.txt",
            "manual_dispatch_logbook_2026-13.txt",
            "manual_dispatch_logbook_July.txt",
            "manual_dispatch_logbook_2026-07-copy.txt",
        ):
            with self.subTest(filename=filename):
                result = self._check_records(
                    [self._valid_record()],
                    filename=filename,
                )
                self.assertIn("INVALID_FILENAME", self._codes(result))
                self.assertEqual(1, result.records_checked)

    def test_malformed_and_truncated_json_are_distinguished(self):
        malformed = self._check_raw(b'{"private":\n')
        truncated = self._check_raw(b'{"private":')

        self.assertIn("MALFORMED_JSON", self._codes(malformed))
        self.assertNotIn("TRUNCATED_FINAL_LINE", self._codes(malformed))
        self.assertIn("TRUNCATED_FINAL_LINE", self._codes(truncated))
        self.assertNotIn("MALFORMED_JSON", self._codes(truncated))

    def test_valid_final_json_without_newline_is_warning_only(self):
        result = self._check_records(
            [self._valid_record()],
            final_newline=False,
        )

        self.assertEqual(["MISSING_FINAL_NEWLINE"], self._codes(result))
        self.assertTrue(result.ok)

    def test_non_object_blank_lines_invalid_utf8_and_empty_file(self):
        non_object = self._check_raw(b"[]\n")
        valid_json = json.dumps(self._valid_record()).encode("utf-8")
        blanks = self._check_raw(b"\n \t\n" + valid_json + b"\n")
        invalid_utf8 = self._check_raw(b"\xffPRIVATE-BYTES\n")
        empty = self._check_raw(b"")

        self.assertIn("NON_OBJECT_RECORD", self._codes(non_object))
        self.assertEqual(1, blanks.records_checked)
        self.assertEqual([], blanks.issues)
        self.assertEqual(["INVALID_UTF8"], self._codes(invalid_utf8))
        self.assertEqual(["EMPTY_LOGBOOK_FILE"], self._codes(empty))
        self.assertEqual(0, empty.error_count)
        self.assertEqual(1, empty.warning_count)

    def test_unreadable_matching_path_does_not_stop_other_files(self):
        directory = self._new_directory()
        (directory / "manual_dispatch_logbook_2026-06.txt").mkdir()
        self._write_records(
            directory,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record()],
        )

        result = checker.check_logbook_integrity(directory)

        self.assertEqual(2, result.files_checked)
        self.assertEqual(1, result.records_checked)
        self.assertEqual(["UNREADABLE_FILE"], self._codes(result))

    def test_each_missing_required_field_is_reported(self):
        for name in REQUIRED_FIELDS:
            with self.subTest(field=name):
                record = self._valid_record()
                del record[name]
                result = self._check_records([record])
                matching = [
                    issue
                    for issue in result.issues
                    if issue.code == "MISSING_REQUIRED_FIELD"
                    and name in issue.message
                ]
                self.assertEqual(1, len(matching))

    def test_blank_required_strings_are_reported(self):
        for name in ("actor", "action", "summary"):
            with self.subTest(field=name):
                record = self._valid_record()
                record[name] = " \t "
                result = self._check_records([record])
                self.assertIn("EMPTY_REQUIRED_VALUE", self._codes(result))

    def test_non_string_required_fields_are_reported(self):
        for name in NON_EMPTY_STRING_FIELDS:
            with self.subTest(field=name):
                record = self._valid_record()
                record[name] = 42
                result = self._check_records([record])
                self.assertIn("INVALID_FIELD_TYPE", self._codes(result))

    def test_nullable_field_wrong_types_are_reported(self):
        invalid_values = ({}, [], 7, True)
        for index, name in enumerate(NULLABLE_STRING_FIELDS):
            with self.subTest(field=name):
                record = self._valid_record()
                record[name] = invalid_values[index % len(invalid_values)]
                result = self._check_records([record])
                self.assertIn("INVALID_FIELD_TYPE", self._codes(result))

    def test_metadata_wrong_types_are_reported(self):
        for value in (None, [], "private", 1, True):
            with self.subTest(value_type=type(value).__name__):
                result = self._check_records(
                    [self._valid_record(metadata=value)]
                )
                self.assertIn("INVALID_FIELD_TYPE", self._codes(result))

    def test_timestamp_validation_and_month_placement(self):
        cases = (
            ("not-a-time", "INVALID_TIMESTAMP"),
            ("2026-07-14T10:30:00", "NAIVE_TIMESTAMP"),
            ("2026-08-01T00:01:00+10:00", "EVENT_MONTH_MISMATCH"),
        )
        for timestamp, expected_code in cases:
            with self.subTest(timestamp=timestamp):
                result = self._check_records(
                    [self._valid_record(time=timestamp)]
                )
                self.assertIn(expected_code, self._codes(result))

    def test_timestamp_month_uses_its_own_offset_not_utc(self):
        result = self._check_records(
            [
                self._valid_record(
                    time="2026-07-01T00:30:00+10:00"
                )
            ]
        )

        self.assertNotIn("EVENT_MONTH_MISMATCH", self._codes(result))
        self.assertTrue(result.ok)

    def test_invalid_result_workspace_and_action_are_errors(self):
        cases = (
            ("result", "success", "INVALID_RESULT"),
            ("workspace", "UNKNOWN", "INVALID_WORKSPACE"),
            ("action", "FUTURE_ACTION", "UNKNOWN_ACTION"),
        )
        for field, value, expected_code in cases:
            with self.subTest(field=field):
                result = self._check_records(
                    [self._valid_record(**{field: value})]
                )
                self.assertIn(expected_code, self._codes(result))
                self.assertGreater(result.error_count, 0)

    def test_optional_dates_require_real_padded_calendar_dates(self):
        valid = self._check_records(
            [
                self._valid_record(
                    dispatch_date="2026-07-01",
                    delivery_date="2026-07-02",
                    pickup_date="2026-07-03",
                )
            ]
        )
        self.assertNotIn("INVALID_DATE_FIELD", self._codes(valid))

        for value in ("2026-7-01", "14/07/2026", "2026-02-30"):
            with self.subTest(value=value):
                invalid = self._check_records(
                    [self._valid_record(dispatch_date=value)]
                )
                self.assertIn("INVALID_DATE_FIELD", self._codes(invalid))

    def test_incident_annotation_requires_non_empty_entity_id(self):
        for action in INCIDENT_ANNOTATION_ACTIONS:
            for entity_id in (None, "  "):
                with self.subTest(action=action, entity_id=entity_id):
                    result = self._check_records(
                        [
                            self._valid_record(
                                action=action,
                                entity_id=entity_id,
                            )
                        ]
                    )
                    self.assertGreater(result.error_count, 0)

    def test_duplicate_incident_annotation_is_detected_across_files(self):
        directory = self._new_directory()
        first = self._valid_record(
            action=INCIDENT_ANNOTATION_ACTION,
            entity_id="incident-duplicate",
        )
        second = self._valid_record(
            time="2026-08-01T09:00:00+10:00",
            action=INCIDENT_ANNOTATION_ACTION,
            entity_id="incident-duplicate",
            metadata={"private": "DO-NOT-PRINT"},
        )
        self._write_records(
            directory,
            "manual_dispatch_logbook_2026-07.txt",
            [first],
        )
        self._write_records(
            directory,
            "manual_dispatch_logbook_2026-08.txt",
            [second],
        )

        result = checker.check_logbook_integrity(directory)
        text_output = checker.format_text_result(result)
        json_output = checker.format_json_result(result)

        duplicates = [
            issue
            for issue in result.issues
            if issue.code == "DUPLICATE_INCIDENT_ANNOTATION"
        ]
        self.assertEqual(1, len(duplicates))
        self.assertEqual(
            "manual_dispatch_logbook_2026-08.txt",
            duplicates[0].filename,
        )
        self.assertNotIn("DO-NOT-PRINT", text_output)
        self.assertNotIn("DO-NOT-PRINT", json_output)

    def test_duplicate_generic_incident_annotation_is_detected(self):
        records = [
            self._valid_record(
                action=INTEGRITY_INCIDENT_ANNOTATION_ACTION,
                entity_id="generic-incident",
            )
            for _ in range(2)
        ]

        result = self._check_records(records)

        self.assertEqual(
            1,
            self._codes(result).count("DUPLICATE_INCIDENT_ANNOTATION"),
        )

    def test_distinct_incident_annotations_pass(self):
        records = [
            self._valid_record(
                action=action,
                entity_id=f"{action}-{index}",
            )
            for action in INCIDENT_ANNOTATION_ACTIONS
            for index in range(2)
        ]

        result = self._check_records(records)

        self.assertNotIn(
            "DUPLICATE_INCIDENT_ANNOTATION",
            self._codes(result),
        )
        self.assertTrue(result.ok)

    def test_text_and_json_output_are_safe_and_machine_readable(self):
        directory = self._new_directory()
        private_line = b'{"address":"PRIVATE-ADDRESS"\n'
        path = directory / "manual_dispatch_logbook_2026-07.txt"
        path.write_bytes(private_line)
        result = checker.check_logbook_integrity(directory)

        text_output = checker.format_text_result(result)
        json_output = checker.format_json_result(result)
        payload = json.loads(json_output)

        self.assertIn("Files checked: 1", text_output)
        self.assertIn("MALFORMED_JSON", text_output)
        self.assertEqual(1, payload["error_count"])
        self.assertEqual(
            "MALFORMED_JSON",
            payload["issues"][0]["code"],
        )
        for output in (text_output, json_output):
            self.assertNotIn("PRIVATE-ADDRESS", output)
            self.assertNotIn(str(directory), output)

    def test_json_output_preserves_non_ascii(self):
        result = checker.IntegrityCheckResult(
            issues=[
                checker.IntegrityIssue(
                    "WARNING",
                    "TEST_WARNING",
                    "manual_dispatch_logbook_2026-07.txt",
                    None,
                    "\u5b89\u5168\u8bca\u65ad\u3002",
                )
            ]
        )

        output = checker.format_json_result(result)

        self.assertIn("\u5b89\u5168\u8bca\u65ad\u3002", output)
        self.assertNotIn("\\u5b89", output)
        self.assertEqual(
            "\u5b89\u5168\u8bca\u65ad\u3002",
            json.loads(output)["issues"][0]["message"],
        )

    def test_issues_are_sorted_deterministically(self):
        result = self._check_records(
            [
                self._valid_record(
                    result="bad",
                    workspace="bad",
                    action="bad",
                )
            ]
        )
        keys = [
            (
                issue.filename,
                issue.line_number or 0,
                issue.severity,
                issue.code,
            )
            for issue in result.issues
        ]

        self.assertEqual(sorted(keys), keys)

    def test_cli_exit_codes_for_success_errors_and_warnings(self):
        valid_dir = self._new_directory()
        self._write_records(
            valid_dir,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record()],
        )
        warning_dir = self._new_directory()
        self._write_records(
            warning_dir,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record()],
            final_newline=False,
        )
        error_dir = self._new_directory()
        self._write_records(
            error_dir,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record(action="UNKNOWN_ACTION")],
        )

        self.assertEqual(0, self._run_main(["--logbook-dir", str(valid_dir)])[0])
        self.assertEqual(1, self._run_main(["--logbook-dir", str(error_dir)])[0])
        self.assertEqual(0, self._run_main(["--logbook-dir", str(warning_dir)])[0])
        self.assertEqual(
            1,
            self._run_main(
                ["--logbook-dir", str(warning_dir), "--strict"]
            )[0],
        )

    def test_cli_exit_two_for_missing_directory_and_non_directory(self):
        missing = self.root / "missing-private-path"
        blocker = self.root / "private-file"
        blocker.write_text("private", encoding="utf-8")

        for path in (missing, blocker):
            with self.subTest(path_type="missing" if path == missing else "file"):
                exit_code, stdout, stderr = self._run_main(
                    ["--logbook-dir", str(path)]
                )
                self.assertEqual(2, exit_code)
                self.assertEqual("", stdout)
                self.assertNotIn(str(path), stderr)
                self.assertNotIn("Traceback", stderr)

    def test_empty_directory_returns_one_with_no_files_issue(self):
        directory = self._new_directory()

        exit_code, stdout, stderr = self._run_main(
            ["--logbook-dir", str(directory), "--format", "json"]
        )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertEqual("NO_LOGBOOK_FILES", payload["issues"][0]["code"])

    def test_cli_uses_environment_directory_precedence(self):
        directory = self._new_directory()
        self._write_records(
            directory,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record()],
        )

        with patch.dict(
            os.environ,
            {"MANUAL_DISPATCH_LOGBOOK_DIR": str(directory)},
        ):
            exit_code, _, _ = self._run_main([])

        self.assertEqual(0, exit_code)

    def test_cli_unexpected_failure_is_safe(self):
        with patch.object(
            checker,
            "check_logbook_integrity",
            side_effect=RuntimeError("PRIVATE-EXCEPTION-CONTENT"),
        ):
            exit_code, stdout, stderr = self._run_main(
                ["--logbook-dir", str(self.root)]
            )

        self.assertEqual(2, exit_code)
        self.assertEqual("", stdout)
        self.assertNotIn("PRIVATE-EXCEPTION-CONTENT", stderr)
        self.assertNotIn("RuntimeError", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_text_json_and_strict_checks_do_not_modify_directory(self):
        directory = self._new_directory()
        path = self._write_records(
            directory,
            "manual_dispatch_logbook_2026-07.txt",
            [self._valid_record()],
            final_newline=False,
        )
        before = self._manifest(directory)

        runs = (
            ["--logbook-dir", str(directory)],
            ["--logbook-dir", str(directory), "--format", "json"],
            ["--logbook-dir", str(directory), "--strict"],
        )
        self.assertEqual([0, 0, 1], [self._run_main(args)[0] for args in runs])

        after = self._manifest(directory)
        self.assertEqual(before, after)
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            before[path.name]["sha256"],
        )

    def _valid_record(self, **overrides):
        record = {
            "time": "2026-07-14T10:30:00+10:00",
            "result": "SUCCESS",
            "workspace": "DELIVERY",
            "actor": "Unknown",
            "action": "ORDER_CREATED",
            "entity_type": None,
            "entity_id": None,
            "summary": "Synthetic valid event.",
            "dispatch_date": None,
            "delivery_date": None,
            "pickup_date": None,
            "driver": None,
            "vehicle": None,
            "run_sheet_id": None,
            "collection_id": None,
            "metadata": {},
        }
        extra = overrides.pop("extra_top_level", None)
        record.update(overrides)
        if extra:
            record.update(extra)
        return record

    def _new_directory(self):
        self.case_number += 1
        directory = self.root / f"case-{self.case_number}"
        directory.mkdir()
        return directory

    def _check_records(
        self,
        records,
        *,
        filename="manual_dispatch_logbook_2026-07.txt",
        final_newline=True,
    ):
        directory = self._new_directory()
        self._write_records(
            directory,
            filename,
            records,
            final_newline=final_newline,
        )
        return checker.check_logbook_integrity(directory)

    def _check_raw(
        self,
        content,
        *,
        filename="manual_dispatch_logbook_2026-07.txt",
    ):
        directory = self._new_directory()
        (directory / filename).write_bytes(content)
        return checker.check_logbook_integrity(directory)

    @staticmethod
    def _write_records(
        directory,
        filename,
        records,
        *,
        final_newline=True,
    ):
        content = "\n".join(
            json.dumps(record, ensure_ascii=False)
            for record in records
        )
        if final_newline:
            content += "\n"
        path = directory / filename
        path.write_bytes(content.encode("utf-8"))
        return path

    @staticmethod
    def _codes(result):
        return [issue.code for issue in result.issues]

    @staticmethod
    def _run_main(arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = checker.main(arguments)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _manifest(directory):
        return {
            path.name: {
                "bytes": path.read_bytes(),
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(directory.iterdir())
        }


if __name__ == "__main__":
    unittest.main()
