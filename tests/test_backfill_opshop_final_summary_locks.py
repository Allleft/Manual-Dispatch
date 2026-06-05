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
from tools.backfill_opshop_final_summary_locks import (
    apply_repairs,
    audit_backfill_candidates,
    format_console_report,
    main,
    write_json_report,
)


class BackfillOpShopFinalSummaryLocksTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"opshop-lock-backfill-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        SQLiteManualDispatchRepository(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_old_cleared_record_reports_would_repair_and_does_not_write(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-CLEARED",
            pickup_task_id="OPSHOP-CLEARED",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
        )

        report = audit_backfill_candidates(self.db_path)
        task = self._fetch_task("OPSHOP-CLEARED")
        assignment = self._fetch_assignment("2026-05-18", "OPSHOP-CLEARED")

        self.assertEqual(1, report["summary"]["checked"])
        self.assertEqual(1, report["summary"]["would_repair"])
        self.assertEqual("WOULD_REPAIR", report["findings"][0]["status"])
        self.assertEqual("ACTIVE", task["status"])
        self.assertIsNone(task["driver_id"])
        self.assertIsNone(task["trip_no"])
        self.assertIsNone(assignment)

    def test_apply_old_cleared_record_restores_task_and_assignment(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-CLEARED",
            pickup_task_id="OPSHOP-CLEARED",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
        )
        dry_run = audit_backfill_candidates(self.db_path)

        report = apply_repairs(self.db_path, dry_run, yes=True)
        task = self._fetch_task("OPSHOP-CLEARED")
        assignment = self._fetch_assignment("2026-05-18", "OPSHOP-CLEARED")

        self.assertEqual(1, report["summary"]["repaired"])
        self.assertEqual("REPAIRED", report["findings"][0]["status"])
        self.assertEqual("ASSIGNED", task["status"])
        self.assertEqual("D001", task["driver_id"])
        self.assertEqual("trip1", task["trip_no"])
        self.assertEqual("2026-05-18", task["dispatch_date"])
        self.assertIsNotNone(assignment)
        self.assertEqual("D001", assignment["driver_id"])
        self.assertEqual("trip1", assignment["trip_no"])

    def test_already_ok_record_reports_already_ok_and_no_changes(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-OK",
            pickup_task_id="OPSHOP-OK",
            task_status="ASSIGNED",
            task_driver_id="D001",
            task_trip_no="trip1",
            include_assignment=True,
        )

        report = audit_backfill_candidates(self.db_path)

        self.assertEqual(1, report["summary"]["already_ok"])
        self.assertEqual("ALREADY_OK", report["findings"][0]["status"])
        self.assertIn("ALREADY_OK", format_console_report(report))

    def test_unsafe_conflict_with_different_driver_is_skipped(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-CONFLICT",
            pickup_task_id="OPSHOP-CONFLICT",
            task_status="ASSIGNED",
            task_driver_id="D002",
            task_trip_no="trip1",
            include_assignment=False,
        )

        report = audit_backfill_candidates(self.db_path)
        task_before = self._fetch_task("OPSHOP-CONFLICT")
        apply_report = apply_repairs(self.db_path, report, yes=True)
        task_after = self._fetch_task("OPSHOP-CONFLICT")

        self.assertEqual(1, report["summary"]["unsafe_conflicts"])
        self.assertEqual("SKIP_UNSAFE_CONFLICT", report["findings"][0]["status"])
        self.assertEqual(1, apply_report["summary"]["unsafe_conflicts"])
        self.assertEqual(task_before["driver_id"], task_after["driver_id"])
        self.assertEqual("D002", task_after["driver_id"])

    def test_duplicate_saved_conflict_is_skipped(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-DUP-A",
            pickup_task_id="OPSHOP-DUP",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
            driver_id="D001",
            delivery_date="2026-05-18",
        )
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-DUP-B",
            pickup_task_id="OPSHOP-DUP",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
            insert_task=False,
            driver_id="D002",
            delivery_date="2026-05-19",
            pickup_date_snapshot="2026-05-19",
        )

        report = audit_backfill_candidates(self.db_path)

        self.assertEqual(2, report["summary"]["checked"])
        self.assertEqual(2, report["summary"]["unsafe_conflicts"])
        self.assertEqual(
            {"SKIP_DUPLICATE_SAVED_CONFLICT"},
            {finding["status"] for finding in report["findings"]},
        )

    def test_json_output_and_main_dry_run_exit_zero_when_repairable_only(self):
        self._seed_saved_opshop_snapshot(
            summary_id="FTS-CLEARED",
            pickup_task_id="OPSHOP-CLEARED",
            task_status="ACTIVE",
            task_driver_id=None,
            task_trip_no=None,
            include_assignment=False,
        )
        report = audit_backfill_candidates(self.db_path)
        output_path = self.temp_dir / "backfill-report.json"

        write_json_report(report, output_path)
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(["--db-path", str(self.db_path)])

        self.assertEqual(0, exit_code)
        self.assertEqual(1, payload["summary"]["would_repair"])

    def _seed_saved_opshop_snapshot(
        self,
        *,
        summary_id,
        pickup_task_id,
        task_status,
        task_driver_id,
        task_trip_no,
        include_assignment,
        insert_task=True,
        driver_id="D001",
        delivery_date="2026-05-18",
        pickup_date_snapshot="2026-05-18",
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
                    "Backfill OP SHOP",
                    "Dandenong",
                    "1 Backfill Street",
                    0,
                    1,
                    "2026-05-18T00:00:00Z",
                    "2026-05-18T00:00:00Z",
                ),
            )
            if insert_task:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO opshop_pickup_tasks (
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
                        pickup_date_snapshot,
                        "OPSHOP_PICKUP",
                        "REGULAR",
                        task_status,
                        pickup_date_snapshot,
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
                        driver_id,
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
                    delivery_date,
                    driver_id,
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
                    f"FSO-{summary_id}",
                    summary_id,
                    1,
                    pickup_task_id,
                    "Backfill OP SHOP",
                    "Dandenong",
                    pickup_date_snapshot,
                    "REGULAR",
                    "ASSIGNED",
                ),
            )
            connection.commit()

    def _fetch_task(self, pickup_task_id):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                "SELECT * FROM opshop_pickup_tasks WHERE pickup_task_id = ?",
                (pickup_task_id,),
            ).fetchone()

    def _fetch_assignment(self, dispatch_date, pickup_task_id):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE dispatch_date = ?
                    AND task_type = 'OPSHOP_PICKUP'
                    AND task_id = ?
                """,
                (dispatch_date, pickup_task_id),
            ).fetchone()


if __name__ == "__main__":
    unittest.main()
