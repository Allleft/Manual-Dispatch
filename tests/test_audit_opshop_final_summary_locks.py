import contextlib
import io
import json
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from tools.audit_opshop_final_summary_locks import (
    audit_database,
    format_console_report,
    main,
    write_json_report,
)


class AuditOpShopFinalSummaryLocksTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"opshop-lock-audit-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        SQLiteManualDispatchRepository(self.db_path)
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-OK",
            pickup_task_id="OPSHOP-OK",
            task_status="ASSIGNED",
            task_driver_id="D001",
            task_trip_no="trip1",
            include_assignment=True,
        )
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-CLEARED",
            pickup_task_id="OPSHOP-CLEARED",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_reports_ok_and_old_cleared_assignment_issues(self):
        report = audit_database(self.db_path)
        issue_types = {finding["type"] for finding in report["findings"]}

        self.assertEqual(2, report["summary"]["checked"])
        self.assertEqual(1, report["summary"]["ok"])
        self.assertIn("OK", issue_types)
        self.assertIn("TASK_NOT_ASSIGNED", issue_types)
        self.assertIn("MISSING_ASSIGNMENT", issue_types)
        self.assertIn("TASK_DRIVER_MISMATCH", issue_types)
        self.assertIn("TRIP_MISMATCH", issue_types)
        self.assertIn(
            "Historical cleared assignment",
            format_console_report(report),
        )

    def test_audit_supports_filters_and_json_output(self):
        report = audit_database(self.db_path, dispatch_date="2026-05-18")
        output_path = self.temp_dir / "audit-report.json"

        write_json_report(report, output_path)
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(str(self.db_path), payload["db_path"])
        self.assertEqual("2026-05-18", payload["filters"]["dispatch_date"])
        self.assertEqual(2, payload["summary"]["checked"])
        self.assertIn("findings", payload)

    def test_main_returns_one_when_mismatches_found(self):
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(["--db-path", str(self.db_path)])

        self.assertEqual(1, exit_code)

    def test_main_returns_two_for_missing_database_path(self):
        with contextlib.redirect_stderr(io.StringIO()):
            exit_code = main(["--db-path", str(self.temp_dir / "missing.sqlite3")])

        self.assertEqual(2, exit_code)

    def _seed_saved_opshop_snapshot(
        self,
        *,
        summary_id,
        pickup_task_id,
        task_status,
        task_driver_id,
        task_trip_no,
        include_assignment,
    ):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO opshop_locations (
                    opshop_id,
                    name,
                    suburb,
                    street_address,
                    key_required,
                    is_active,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "OPSHOP-LOCATION",
                    "Audit OP SHOP",
                    "Dandenong",
                    "1 Audit Street",
                    0,
                    1,
                    "2026-05-18T00:00:00Z",
                    "2026-05-18T00:00:00Z",
                ),
            )
            connection.execute(
                """
                INSERT INTO opshop_pickup_tasks (
                    pickup_task_id,
                    schedule_id,
                    opshop_id,
                    pickup_date,
                    task_type,
                    generated_from,
                    status,
                    dispatch_date,
                    driver_id,
                    trip_no,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pickup_task_id,
                    None,
                    "OPSHOP-LOCATION",
                    "2026-05-18",
                    "OPSHOP_PICKUP",
                    "REGULAR",
                    task_status,
                    "2026-05-18",
                    task_driver_id,
                    task_trip_no,
                    None,
                    "2026-05-18T00:00:00Z",
                    "2026-05-18T00:00:00Z",
                ),
            )
            if include_assignment:
                connection.execute(
                    """
                    INSERT INTO manual_dispatch_assignments (
                        assignment_id,
                        dispatch_date,
                        task_type,
                        task_id,
                        driver_id,
                        trip_no,
                        assigned_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"ASSIGN-{pickup_task_id}",
                        "2026-05-18",
                        "OPSHOP_PICKUP",
                        pickup_task_id,
                        "D001",
                        "trip1",
                        "2026-05-18T00:00:00Z",
                        "2026-05-18T00:00:00Z",
                    ),
                )
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id,
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    driver_name_snapshot,
                    vehicle_id,
                    vehicle_rego_snapshot,
                    total_pallets,
                    total_loose_bags,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    "2026-05-18",
                    "2026-05-18",
                    "D001",
                    "John",
                    None,
                    "No vehicle selected",
                    0,
                    0,
                    "SAVED",
                    "2026-05-18T00:00:00Z",
                    "2026-05-18T00:00:00Z",
                    "Mandy",
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO final_trip_summary_opshop_pickup_rows (
                    row_id,
                    summary_id,
                    row_no,
                    pickup_task_id_snapshot,
                    opshop_name_snapshot,
                    suburb_snapshot,
                    pickup_date_snapshot,
                    run_type_snapshot,
                    status_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"FSO-{pickup_task_id}",
                    summary_id,
                    1,
                    pickup_task_id,
                    "Audit OP SHOP",
                    "Dandenong",
                    "2026-05-18",
                    "REGULAR",
                    "ASSIGNED",
                ),
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
