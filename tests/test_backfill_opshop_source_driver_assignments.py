import contextlib
import gc
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from openpyxl import Workbook

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import OpShopLocation, OpShopPickupSchedule, OpShopPickupTask
from tools.backfill_opshop_source_driver_assignments import (
    DRIVER_ALIAS_TO_NAME,
    analyze_backfill,
    apply_backfill,
)
from tools.import_oncall_opshop_pickups_to_db import (
    REQUIRED_COLUMNS as ONCALL_COLUMNS,
)
from tools.import_oncall_opshop_pickups_to_db import (
    SHEET_RUN_DAYS as ONCALL_SHEETS,
)
from tools.import_regular_opshop_pickups_to_db import (
    REQUIRED_COLUMNS as REGULAR_COLUMNS,
)
from tools.import_regular_opshop_pickups_to_db import (
    SHEET_RUN_DAYS as REGULAR_SHEETS,
)


NOW = "2026-06-01T00:00:00+00:00"


class BackfillOpShopSourceDriverAssignmentsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"opshop-backfill-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.regular_path = self.temp_dir / "regular.xlsx"
        self.oncall_path = self.temp_dir / "oncall.xlsx"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self._insert_drivers()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_alias_mapping_is_canonical(self):
        self.assertEqual("John Georgiadis", DRIVER_ALIAS_TO_NAME["john g"])
        self.assertEqual("Gavin Fynn", DRIVER_ALIAS_TO_NAME["gavin"])
        self.assertEqual("Epaminondas Tsatsoulis", DRIVER_ALIAS_TO_NAME["nonda"])
        self.assertEqual("Guanlin Li", DRIVER_ALIAS_TO_NAME["lee"])

    def test_dry_run_is_read_only_and_rejects_company_only_match(self):
        self._write_workbooks(
            regular_rows=[self._source("Shared Name", "Coburg", "1 Main Rd", "John G")],
        )
        self._add_template(
            "SCHED-OTHER",
            "Shared Name",
            "Preston",
            "99 Other St",
            "MONDAY",
            "REGULAR",
        )
        gc.collect()
        before = self._database_snapshot()
        before_bytes = self.db_path.read_bytes()

        analysis = self._analyze()

        self.assertEqual(before_bytes, self.db_path.read_bytes())
        self.assertEqual(before, self._database_snapshot())
        self.assertEqual(0, analysis["summary"]["matched_templates"])
        self.assertTrue(
            any(
                record["result_status"] == "UNMATCHED_TEMPLATE"
                for record in analysis["records"]
            )
        )

    def test_apply_updates_template_assigns_task_and_is_idempotent(self):
        self._write_workbooks(
            regular_rows=[self._source("Alpha Op Shop", "Coburg", "1 Main Road", "John G")],
        )
        self._add_template(
            "SCHED-ALPHA",
            "Alpha Op Shop",
            "Coburg",
            "1 Main Rd",
            "MONDAY",
            "REGULAR",
        )
        self._add_task("TASK-ALPHA", "SCHED-ALPHA", "2026-06-29")

        analysis = self._analyze()
        self.assertEqual(1, analysis["summary"]["templates_to_update"])
        self.assertEqual(1, analysis["summary"]["tasks_to_assign"])

        apply_backfill(analysis, self.db_path)

        schedule = self.repository.get_opshop_pickup_schedule("SCHED-ALPHA")
        task = self.repository.get_opshop_pickup_task("TASK-ALPHA")
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            "TASK-ALPHA",
        )
        self.assertEqual("DRIVER-JOHN", schedule.default_driver_id)
        self.assertEqual("John G", schedule.default_driver_alias)
        self.assertEqual("John Georgiadis", schedule.default_driver_name_snapshot)
        self.assertEqual("ASSIGNED", task.status)
        self.assertEqual("DRIVER-JOHN", task.driver_id)
        self.assertEqual("trip1", task.trip_no)
        self.assertEqual("DRIVER-JOHN", assignment.driver_id)

        second = self._analyze()
        self.assertEqual(0, second["summary"]["templates_to_update"])
        self.assertEqual(0, second["summary"]["tasks_to_assign"])

    def test_existing_assignments_and_collection_locks_are_preserved(self):
        rows = [
            self._source("Manual Choice", "Coburg", "1 First Rd", "John G"),
            self._source("Generated Lock", "Coburg", "2 Second Rd", "Nonda"),
            self._source("Saved Lock", "Coburg", "3 Third Rd", "LEE"),
        ]
        self._write_workbooks(regular_rows=rows)
        for index, row in enumerate(rows, start=1):
            schedule_id = f"SCHED-{index}"
            task_id = f"TASK-{index}"
            self._add_template(
                schedule_id,
                row["Op_Shop_Name"],
                row["Suburb"],
                row["Street_Address"],
                "MONDAY",
                "REGULAR",
            )
            self._add_task(task_id, schedule_id, "2026-06-29")
        self.repository.upsert_assignment(
            "2026-06-29",
            "OPSHOP_PICKUP",
            "TASK-1",
            "DRIVER-GAVIN",
            "trip1",
        )
        self.repository.update_opshop_pickup_task_assignment_status(
            "TASK-1",
            "ASSIGNED",
            "DRIVER-GAVIN",
            "trip1",
        )
        self._reserve_task("COL-GENERATED", "TASK-2", "GENERATED", "DRIVER-NONDA")
        self._reserve_task("COL-SAVED", "TASK-3", "SAVED", "DRIVER-LEE")

        analysis = self._analyze()
        statuses = [record["result_status"] for record in analysis["records"]]

        self.assertIn("EXISTING_ASSIGNMENT_PRESERVED", statuses)
        self.assertIn("GENERATED_LOCK_SKIPPED", statuses)
        self.assertIn("SAVED_LOCK_SKIPPED", statuses)
        self.assertEqual(0, analysis["summary"]["tasks_to_assign"])

    def test_friday_and_generic_oncall_rows_remain_distinct(self):
        self._write_workbooks(
            oncall_rows={
                "FRI": [
                    self._source(
                        "Overlap Op Shop",
                        "Dandenong",
                        "8 Friday St",
                        "Nonda",
                    )
                ],
                "Gavin": [
                    self._source(
                        "Overlap Op Shop",
                        "Dandenong",
                        "8 Friday St",
                        "Gavin",
                    )
                ],
            }
        )
        self._add_template(
            "SCHED-FRIDAY",
            "Overlap Op Shop",
            "Dandenong",
            "8 Friday St",
            "FRIDAY",
            "ON_CALL",
        )
        self._add_template(
            "SCHED-GENERIC",
            "Overlap Op Shop",
            "Dandenong",
            "8 Friday St",
            None,
            "ON_CALL",
        )

        analysis = self._analyze()
        updates = {
            record["schedule_id"]: record["proposed_template_default_driver"]
            for record in analysis["records"]
            if record["result_status"] == "TEMPLATE_WILL_UPDATE"
        }

        self.assertEqual("DRIVER-NONDA", updates["SCHED-FRIDAY"])
        self.assertEqual("DRIVER-GAVIN", updates["SCHED-GENERIC"])
        self.assertEqual(0, analysis["summary"]["ambiguous"])

    def test_apply_refuses_unknown_driver_alias(self):
        self._write_workbooks(
            regular_rows=[
                self._source("Unknown Driver", "Coburg", "7 Mystery Rd", "Mystery")
            ],
        )
        self._add_template(
            "SCHED-UNKNOWN",
            "Unknown Driver",
            "Coburg",
            "7 Mystery Rd",
            "MONDAY",
            "REGULAR",
        )
        analysis = self._analyze()

        self.assertEqual(1, analysis["summary"]["blocking_findings"])
        with self.assertRaisesRegex(ValueError, "Backfill blocked"):
            apply_backfill(analysis, self.db_path)

    def _analyze(self):
        return analyze_backfill(
            self.regular_path,
            self.oncall_path,
            self.db_path,
            "2026-06-29",
        )

    def _write_workbooks(self, regular_rows=None, oncall_rows=None):
        self._write_workbook(
            self.regular_path,
            REGULAR_SHEETS,
            REGULAR_COLUMNS,
            {"MON": regular_rows or []},
        )
        self._write_workbook(
            self.oncall_path,
            ONCALL_SHEETS,
            ONCALL_COLUMNS,
            oncall_rows or {},
        )

    @staticmethod
    def _write_workbook(path, sheets, columns, rows_by_sheet):
        workbook = Workbook()
        workbook.remove(workbook.active)
        for sheet_name in sheets:
            worksheet = workbook.create_sheet(sheet_name)
            worksheet.append(columns)
            for row in rows_by_sheet.get(sheet_name, []):
                worksheet.append([row.get(column) for column in columns])
        workbook.save(path)

    @staticmethod
    def _source(company, suburb, address, alias):
        return {
            "Op_Shop_Name": company,
            "Run_Type": "ON_CALL",
            "Active_Flag": "Yes",
            "Suburb": suburb,
            "Street_Address": address,
            "Pickup_Frequency": "Weekly",
            "Status": "Active",
            "Assigned to": alias,
        }

    def _add_template(
        self,
        schedule_id,
        company,
        suburb,
        address,
        run_day,
        run_type,
    ):
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT opshop_id
                FROM opshop_locations
                WHERE lower(trim(name)) = lower(trim(?))
                  AND lower(trim(COALESCE(suburb, ''))) = lower(trim(?))
                  AND lower(trim(COALESCE(street_address, ''))) = lower(trim(?))
                """,
                (company, suburb, address),
            ).fetchone()
        opshop_id = row[0] if row else f"LOCATION-{schedule_id}"
        if not row:
            self.repository.upsert_opshop_location(
                OpShopLocation(
                    opshop_id=opshop_id,
                    name=company,
                    suburb=suburb,
                    street_address=address,
                    area_region=None,
                    primary_contact=None,
                    primary_phone=None,
                    secondary_contact=None,
                    secondary_phone=None,
                    access_type=None,
                    key_required=False,
                    trailer_restriction=None,
                    status_notes=None,
                    is_active=True,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id=opshop_id,
                run_day=run_day,
                run_type=run_type,
                pickup_frequency="Weekly" if run_type == "REGULAR" else "On Call",
                time_window=None,
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )

    def _add_task(self, task_id, schedule_id, pickup_date):
        schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=task_id,
                schedule_id=schedule_id,
                opshop_id=schedule.opshop_id,
                pickup_date=pickup_date,
                task_type="OPSHOP_PICKUP",
                generated_from=schedule.run_type,
                status="ACTIVE",
                dispatch_date=pickup_date,
                driver_id=None,
                trip_no=None,
                notes=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )

    def _reserve_task(self, collection_id, task_id, status, driver_id):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_pickup_collections (
                    collection_id, dispatch_date, pickup_date, driver_id,
                    driver_name_snapshot, status, generated_at
                ) VALUES (?, '2026-06-29', '2026-06-29', ?, 'Driver', ?, ?)
                """,
                (collection_id, driver_id, status, NOW),
            )
            connection.execute(
                """
                INSERT INTO opshop_pickup_collection_rows (
                    row_id, collection_id, row_no, pickup_task_id_snapshot
                ) VALUES (?, ?, 1, ?)
                """,
                (f"ROW-{collection_id}", collection_id, task_id),
            )

    def _insert_drivers(self):
        drivers = (
            ("DRIVER-JOHN", "John Georgiadis"),
            ("DRIVER-GAVIN", "Gavin Fynn"),
            ("DRIVER-NONDA", "Epaminondas Tsatsoulis"),
            ("DRIVER-LEE", "Guanlin Li"),
        )
        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                """
                INSERT INTO manual_drivers (
                    driver_id, name, start_time, end_time, is_available,
                    preferred_zone, pallet_only, is_deleted
                ) VALUES (?, ?, '08:00', '16:00', 1, NULL, 0, 0)
                """,
                drivers,
            )

    def _database_snapshot(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as connection:
            return "\n".join(connection.iterdump())


if __name__ == "__main__":
    unittest.main()
