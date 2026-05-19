import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import OpShopLocation, OpShopPickupSchedule, OpShopPickupTask


class OpShopPickupFoundationTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-foundation-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_repository_creates_opshop_tables(self):
        SQLiteManualDispatchRepository(self.db_path)

        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertIn("opshop_locations", tables)
        self.assertIn("opshop_pickup_schedules", tables)
        self.assertIn("opshop_pickup_tasks", tables)

    def test_in_memory_repository_supports_opshop_location_upsert_and_list(self):
        repository = InMemoryManualDispatchRepository()
        location = self._location("OPSHOP-001", name="Northside Op Shop")

        repository.upsert_opshop_location(location)
        updated = self._location("OPSHOP-001", name="Northside Op Shop Updated")
        repository.upsert_opshop_location(updated)

        self.assertEqual([updated], repository.list_opshop_locations())
        self.assertEqual(updated, repository.get_opshop_location("OPSHOP-001"))

    def test_sqlite_repository_supports_opshop_location_upsert_and_list(self):
        repository = SQLiteManualDispatchRepository(self.db_path)
        location = self._location("OPSHOP-001", name="Northside Op Shop")

        repository.upsert_opshop_location(location)
        updated = self._location("OPSHOP-001", name="Northside Op Shop Updated")
        repository.upsert_opshop_location(updated)

        self.assertEqual([updated], repository.list_opshop_locations())
        self.assertEqual(updated, repository.get_opshop_location("OPSHOP-001"))

    def test_in_memory_repository_supports_opshop_schedule_upsert_and_list(self):
        repository = InMemoryManualDispatchRepository()
        schedule = self._schedule("SCHED-001", "OPSHOP-001")

        repository.upsert_opshop_pickup_schedule(schedule)
        updated = self._schedule(
            "SCHED-001",
            "OPSHOP-001",
            pickup_frequency="Fortnightly",
            active_flag=False,
        )
        repository.upsert_opshop_pickup_schedule(updated)

        self.assertEqual([updated], repository.list_opshop_pickup_schedules())
        self.assertEqual([], repository.list_active_opshop_pickup_schedules())
        self.assertEqual(updated, repository.get_opshop_pickup_schedule("SCHED-001"))

    def test_sqlite_repository_supports_opshop_schedule_upsert_and_list(self):
        repository = SQLiteManualDispatchRepository(self.db_path)
        repository.upsert_opshop_location(self._location("OPSHOP-001"))
        schedule = self._schedule("SCHED-001", "OPSHOP-001")

        repository.upsert_opshop_pickup_schedule(schedule)
        updated = self._schedule(
            "SCHED-001",
            "OPSHOP-001",
            pickup_frequency="Fortnightly",
            active_flag=False,
        )
        repository.upsert_opshop_pickup_schedule(updated)

        self.assertEqual([updated], repository.list_opshop_pickup_schedules())
        self.assertEqual([], repository.list_active_opshop_pickup_schedules())
        self.assertEqual(updated, repository.get_opshop_pickup_schedule("SCHED-001"))

    def test_in_memory_repository_supports_opshop_pickup_task_upsert_and_list(self):
        repository = InMemoryManualDispatchRepository()
        task = self._task("TASK-001", "OPSHOP-001", schedule_id="SCHED-001")

        repository.upsert_opshop_pickup_task(task)
        updated = self._task(
            "TASK-001",
            "OPSHOP-001",
            schedule_id="SCHED-001",
            status="CANCELLED",
        )
        repository.upsert_opshop_pickup_task(updated)

        self.assertEqual([updated], repository.list_opshop_pickup_tasks())
        self.assertEqual(updated, repository.get_opshop_pickup_task("TASK-001"))

    def test_sqlite_repository_supports_opshop_pickup_task_upsert_and_list(self):
        repository = SQLiteManualDispatchRepository(self.db_path)
        repository.upsert_opshop_location(self._location("OPSHOP-001"))
        repository.upsert_opshop_pickup_schedule(self._schedule("SCHED-001", "OPSHOP-001"))
        task = self._task("TASK-001", "OPSHOP-001", schedule_id="SCHED-001")

        repository.upsert_opshop_pickup_task(task)
        updated = self._task(
            "TASK-001",
            "OPSHOP-001",
            schedule_id="SCHED-001",
            status="CANCELLED",
        )
        repository.upsert_opshop_pickup_task(updated)

        self.assertEqual([updated], repository.list_opshop_pickup_tasks())
        self.assertEqual(updated, repository.get_opshop_pickup_task("TASK-001"))

    def _location(self, opshop_id, name="Northside Op Shop"):
        return OpShopLocation(
            opshop_id=opshop_id,
            name=name,
            suburb="Coburg",
            street_address="1 Sydney Road",
            area_region="North",
            primary_contact="Mary",
            primary_phone="0400 000 001",
            secondary_contact="John",
            secondary_phone="0400 000 002",
            access_type="Rear dock",
            key_required=True,
            trailer_restriction="Small truck only",
            status_notes="Ring first",
            is_active=True,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )

    def _schedule(
        self,
        schedule_id,
        opshop_id,
        pickup_frequency="Weekly",
        active_flag=True,
    ):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id=opshop_id,
            run_day="MONDAY",
            run_type="STANDARD",
            pickup_frequency=pickup_frequency,
            time_window="09:00-12:00",
            call_before_arrival=True,
            call_timing="30 minutes before arrival",
            status="Active",
            active_flag=active_flag,
            fortnight_group=None,
            review_required=False,
            review_reason=None,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )

    def _task(self, pickup_task_id, opshop_id, schedule_id=None, status="ACTIVE"):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=schedule_id,
            opshop_id=opshop_id,
            pickup_date="2026-05-25",
            task_type="OPSHOP_PICKUP",
            generated_from="MANUAL",
            status=status,
            dispatch_date=None,
            driver_id=None,
            trip_no=None,
            notes="Manual test pickup",
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
