import hashlib
import json
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import OpShopLocation, OpShopPickupSchedule, OpShopPickupTask
from tools.check_logbook_integrity import check_logbook_integrity
from tools.repair_duplicate_opshop_locations import (
    apply_location_repair,
    audit_duplicate_locations,
    plan_location_repair,
)


class RepairDuplicateOpShopLocationsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"duplicate-opshop-repair-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.logbook_dir = self.temp_dir / "logbook"
        self.logbook_env = patch.dict(
            "os.environ",
            {"MANUAL_DISPATCH_LOGBOOK_DIR": str(self.logbook_dir)},
        )
        self.logbook_env.start()
        self.addCleanup(self.logbook_env.stop)
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "false"}):
            self.repository = SQLiteManualDispatchRepository(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_and_dry_run_detect_duplicate_identity_without_writing(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        before = self._sha256()

        audit = audit_duplicate_locations(self.db_path)
        plan = plan_location_repair(self.db_path, "CANON", ["DUP"])

        self.assertEqual(1, audit["duplicate_group_count"])
        self.assertEqual("shared shop|coburg|1 sydney rd", audit["groups"][0]["normalized_key"])
        self.assertTrue(plan["can_apply"])
        self.assertFalse(plan["already_repaired"])
        self.assertEqual(before, self._sha256())

    def test_audit_without_duplicates_returns_empty_without_writing(self):
        self._add_location("ONLY", "Only Shop", "Coburg", "1 Sydney Road")
        before = self._logical_tables()

        audit = audit_duplicate_locations(self.db_path)

        self.assertEqual(0, audit["duplicate_group_count"])
        self.assertEqual([], audit["groups"])
        self.assertEqual(before, self._logical_tables())

    def test_apply_migrates_live_references_and_preserves_immutable_snapshots(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        self._add_schedule("S-CANON", "CANON", "MONDAY")
        self._add_schedule("S-DUP", "DUP", "WEDNESDAY")
        self._add_task("T-DUP", "S-DUP", "DUP", "2026-08-05", driver_id="D001")
        self._add_assignment_and_snapshots("T-DUP")
        snapshots_before = self._snapshot_rows()
        production_logbook_before = self._directory_snapshot(
            Path.cwd() / "data" / "logbook"
        )

        result = apply_location_repair(
            self.db_path,
            "CANON",
            ["DUP"],
            yes=True,
            logbook_dir=self.logbook_dir,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(1, result["rows_updated"]["opshop_pickup_schedules"])
        self.assertEqual(1, result["rows_updated"]["opshop_pickup_tasks"])
        self.assertEqual(1, result["locations_deleted"])
        self.assertTrue(Path(result["backup_path"]).is_file())
        self.assertEqual(["CANON"], self._column("opshop_locations", "opshop_id"))
        self.assertEqual(
            ["CANON", "CANON"],
            sorted(self._column("opshop_pickup_schedules", "opshop_id")),
        )
        self.assertEqual(["CANON"], self._column("opshop_pickup_tasks", "opshop_id"))
        self.assertEqual(["T-DUP"], self._column("manual_dispatch_assignments", "task_id"))
        self.assertEqual(snapshots_before, self._snapshot_rows())
        self.assertEqual("ok", self._scalar("PRAGMA integrity_check"))
        self.assertEqual([], self._rows("PRAGMA foreign_key_check"))
        logbook_entries = list(self.logbook_dir.glob("manual_dispatch_logbook_*.txt"))
        self.assertEqual(1, len(logbook_entries))
        event = json.loads(logbook_entries[0].read_text(encoding="utf-8").strip())
        self.assertEqual("Unknown", event["actor"])
        self.assertEqual("DUPLICATE_OPSHOP_LOCATION_REPAIR_COMPLETED", event["action"])
        integrity_result = check_logbook_integrity(self.logbook_dir)
        self.assertTrue(integrity_result.ok)
        self.assertEqual(0, integrity_result.error_count)
        self.assertEqual(
            production_logbook_before,
            self._directory_snapshot(Path.cwd() / "data" / "logbook"),
        )

    def test_second_apply_is_idempotent(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        first = apply_location_repair(
            self.db_path,
            "CANON",
            ["DUP"],
            yes=True,
            logbook_dir=self.logbook_dir,
        )
        after_first = self._sha256()

        second = apply_location_repair(
            self.db_path,
            "CANON",
            ["DUP"],
            yes=True,
            logbook_dir=self.logbook_dir,
        )

        self.assertTrue(first["applied"])
        self.assertFalse(second["applied"])
        self.assertTrue(second["already_repaired"])
        self.assertIsNone(second["backup_path"])
        self.assertEqual(after_first, self._sha256())

    def test_conflicting_schedule_slot_fails_closed_without_writes(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        self._add_schedule("S-CANON", "CANON", "WEDNESDAY")
        self._add_schedule("S-DUP", "DUP", "WEDNESDAY")
        before = self._logical_tables()

        plan = plan_location_repair(self.db_path, "CANON", ["DUP"])

        self.assertFalse(plan["can_apply"])
        self.assertIn("Schedule slot conflict", " ".join(plan["conflicts"]))
        with self.assertRaisesRegex(ValueError, "Repair cannot be applied"):
            apply_location_repair(
                self.db_path,
                "CANON",
                ["DUP"],
                yes=True,
                logbook_dir=self.logbook_dir,
            )
        self.assertEqual(before, self._logical_tables())

    def test_duplicate_schedule_date_task_identity_fails_closed(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        self._add_schedule("S-DUP", "DUP", "WEDNESDAY")
        self._add_task("T-1", "S-DUP", "DUP", "2026-08-05")
        self._add_task("T-2", "S-DUP", "DUP", "2026-08-05")

        plan = plan_location_repair(self.db_path, "CANON", ["DUP"])

        self.assertFalse(plan["can_apply"])
        self.assertIn("Duplicate task identity", " ".join(plan["conflicts"]))

    def test_inactive_unreferenced_duplicate_is_removed(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location(
            "DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd", is_active=False
        )

        result = apply_location_repair(
            self.db_path,
            "CANON",
            ["DUP"],
            yes=True,
            logbook_dir=self.logbook_dir,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(["CANON"], self._column("opshop_locations", "opshop_id"))

    def test_unhandled_direct_reference_fails_closed(self):
        self._add_location("CANON", "Shared Shop", "Coburg", "1 Sydney Road")
        self._add_location("DUP", "SHARED SHOP", "COBURG", "1 Sydney Rd")
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("CREATE TABLE custom_opshop_reference (opshop_id TEXT)")
            connection.execute("INSERT INTO custom_opshop_reference VALUES ('DUP')")
        before = self._logical_tables()

        plan = plan_location_repair(self.db_path, "CANON", ["DUP"])

        self.assertFalse(plan["can_apply"])
        self.assertIn("custom_opshop_reference", " ".join(plan["conflicts"]))
        self.assertEqual(before, self._logical_tables())

    def _add_location(self, opshop_id, name, suburb, address, is_active=True):
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id=opshop_id,
                name=name,
                suburb=suburb,
                street_address=address,
                area_region="Metro",
                primary_contact=None,
                primary_phone=None,
                secondary_contact=None,
                secondary_phone=None,
                access_type=None,
                key_required=False,
                trailer_restriction=None,
                status_notes=None,
                is_active=is_active,
                created_at="2026-08-01T00:00:00+00:00",
                updated_at="2026-08-01T00:00:00+00:00",
            )
        )

    def _add_schedule(self, schedule_id, opshop_id, run_day):
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id=opshop_id,
                run_day=run_day,
                run_type="REGULAR",
                pickup_frequency="Weekly",
                time_window="9-12",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason="WORKBOOK_IMPORT",
                created_at="2026-08-01T00:00:00+00:00",
                updated_at="2026-08-01T00:00:00+00:00",
            )
        )

    def _add_task(self, task_id, schedule_id, opshop_id, pickup_date, driver_id=None):
        if driver_id:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO manual_drivers (driver_id, name) VALUES (?, ?)",
                    (driver_id, "Test Driver"),
                )
        self.repository.insert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=task_id,
                schedule_id=schedule_id,
                opshop_id=opshop_id,
                pickup_date=pickup_date,
                task_type="OPSHOP_PICKUP",
                generated_from="REGULAR",
                status="ASSIGNED" if driver_id else "ACTIVE",
                dispatch_date="2026-08-04",
                driver_id=driver_id,
                trip_no="trip1" if driver_id else None,
                notes=None,
                created_at="2026-08-01T00:00:00+00:00",
                updated_at="2026-08-01T00:00:00+00:00",
            )
        )

    def _add_assignment_and_snapshots(self, task_id):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "INSERT INTO manual_dispatch_assignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "A-1",
                    "2026-08-04",
                    "OPSHOP_PICKUP",
                    task_id,
                    "D001",
                    "trip1",
                    "2026-08-01T00:00:00+00:00",
                    "2026-08-01T00:00:00+00:00",
                ),
            )
            connection.execute(
                "INSERT INTO opshop_pickup_collections "
                "(collection_id, dispatch_date, pickup_date, driver_id, "
                "driver_name_snapshot, status, generated_at) "
                "VALUES ('C-1', '2026-08-04', '2026-08-05', 'D001', "
                "'Test Driver', 'GENERATED', '2026-08-01T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO opshop_pickup_collection_rows "
                "(row_id, collection_id, row_no, pickup_task_id_snapshot, "
                "opshop_name_snapshot, pickup_date_snapshot) "
                "VALUES ('CR-1', 'C-1', 1, ?, 'Historical Shop', '2026-08-05')",
                (task_id,),
            )
            connection.execute(
                "INSERT INTO final_trip_summaries "
                "(summary_id, dispatch_date, delivery_date, driver_id, "
                "driver_name_snapshot, status, saved_at) "
                "VALUES ('F-1', '2026-08-04', '2026-08-05', 'D001', "
                "'Test Driver', 'SAVED', '2026-08-01T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO final_trip_summary_opshop_pickup_rows "
                "(row_id, summary_id, row_no, pickup_task_id_snapshot, "
                "opshop_name_snapshot, pickup_date_snapshot) "
                "VALUES ('FR-1', 'F-1', 1, ?, 'Historical Shop', '2026-08-05')",
                (task_id,),
            )

    def _snapshot_rows(self):
        return {
            "collection": self._rows(
                "SELECT * FROM opshop_pickup_collection_rows ORDER BY row_id"
            ),
            "final": self._rows(
                "SELECT * FROM final_trip_summary_opshop_pickup_rows ORDER BY row_id"
            ),
        }

    def _logical_tables(self):
        return {
            table: self._rows(f"SELECT * FROM {table} ORDER BY 1")
            for table in (
                "opshop_locations",
                "opshop_pickup_schedules",
                "opshop_pickup_tasks",
            )
        }

    def _rows(self, sql):
        with sqlite3.connect(self.db_path) as connection:
            return [tuple(row) for row in connection.execute(sql)]

    def _column(self, table, column):
        return [row[0] for row in self._rows(f"SELECT {column} FROM {table} ORDER BY {column}")]

    def _scalar(self, sql):
        return self._rows(sql)[0][0]

    def _sha256(self):
        return hashlib.sha256(self.db_path.read_bytes()).hexdigest()

    @staticmethod
    def _directory_snapshot(directory):
        if not directory.is_dir():
            return {}
        return {
            str(path.relative_to(directory)): (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
