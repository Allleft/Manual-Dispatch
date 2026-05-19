import importlib
import os
import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class OpShopBoardPayloadTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.repository.upsert_opshop_location(self._location())
        self.service = ManualDispatchService(self.repository)

    def test_board_response_includes_opshop_pickups_and_existing_fields(self):
        board = self.service.get_board("2026-05-18")
        payload = to_dict(board)

        self.assertIn("opshop_pickups", payload)
        self.assertEqual([], payload["opshop_pickups"])
        for key in [
            "dispatch_date",
            "orders",
            "drivers",
            "vehicles",
            "assignments",
            "driver_vehicle_assignments",
        ]:
            self.assertIn(key, payload)

    def test_board_load_auto_generates_after_14_day_opshop_window(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY", pickup_frequency="Weekly")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(["2026-05-25", "2026-06-01"], self._pickup_dates())
        self.assertEqual(
            ["2026-05-25", "2026-06-01"],
            [item.pickup_date for item in board.opshop_pickups],
        )
        self.assertNotIn("2026-05-18", [item.pickup_date for item in board.opshop_pickups])

    def test_board_excludes_pickups_outside_window(self):
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-OUTSIDE", pickup_date="2026-06-02")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual([], board.opshop_pickups)

    def test_board_returns_joined_location_schedule_and_task_fields(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHED-001",
                run_day="TUESDAY",
                run_type="STANDARD",
                pickup_frequency="Weekly",
                time_window="9-12",
                call_before_arrival=True,
            )
        )

        board = self.service.get_board("2026-05-18")
        item = board.opshop_pickups[0]

        self.assertTrue(item.pickup_task_id.startswith("OPSHOP-PICKUP-20260519-"))
        self.assertEqual("OPSHOP_PICKUP", item.task_type)
        self.assertEqual("SCHED-001", item.schedule_id)
        self.assertEqual("OPSHOP-001", item.opshop_id)
        self.assertEqual("Northside Op Shop", item.opshop_name)
        self.assertEqual("Coburg", item.suburb)
        self.assertEqual("1 Sydney Road", item.street_address)
        self.assertEqual("0400 000 001", item.primary_phone)
        self.assertEqual("TUESDAY", item.run_day)
        self.assertEqual("STANDARD", item.run_type)
        self.assertEqual("Weekly", item.pickup_frequency)
        self.assertEqual("9-12", item.time_window)
        self.assertTrue(item.call_before_arrival)
        self.assertEqual("2026-05-19", item.pickup_date)
        self.assertEqual("2026-05-19", item.dispatch_date)
        self.assertEqual("STANDARD", item.generated_from)
        self.assertEqual("ACTIVE", item.status)
        self.assertFalse(item.is_assigned)

    def test_board_excludes_cancelled_and_completed_pickup_tasks(self):
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-ACTIVE", pickup_date="2026-05-20", status="ACTIVE")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-CANCELLED", pickup_date="2026-05-21", status="CANCELLED")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-COMPLETED", pickup_date="2026-05-22", status="COMPLETED")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(["TASK-ACTIVE"], [item.pickup_task_id for item in board.opshop_pickups])

    def test_board_does_not_generate_on_call_or_review_required_schedules(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ON-CALL", run_type="ON_CALL", pickup_frequency="Weekly")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHED-REVIEW",
                run_type="STANDARD",
                pickup_frequency="Weekly",
                review_required=True,
            )
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual([], board.opshop_pickups)
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_repeated_board_load_does_not_duplicate_opshop_pickups(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY", pickup_frequency="Weekly")
        )

        first = self.service.get_board("2026-05-18")
        second = self.service.get_board("2026-05-18")

        self.assertEqual(2, len(first.opshop_pickups))
        self.assertEqual(2, len(second.opshop_pickups))
        self.assertEqual(2, len(self.repository.list_opshop_pickup_tasks()))

    def _pickup_dates(self):
        return [
            task.pickup_date
            for task in sorted(
                self.repository.list_opshop_pickup_tasks(),
                key=lambda task: (task.pickup_date, task.pickup_task_id),
            )
        ]

    def _location(self):
        return OpShopLocation(
            opshop_id="OPSHOP-001",
            name="Northside Op Shop",
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
        run_day="MONDAY",
        run_type="STANDARD",
        pickup_frequency="Weekly",
        time_window="9-12",
        call_before_arrival=False,
        review_required=False,
    ):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id="OPSHOP-001",
            run_day=run_day,
            run_type=run_type,
            pickup_frequency=pickup_frequency,
            time_window=time_window,
            call_before_arrival=call_before_arrival,
            call_timing="30 minutes" if call_before_arrival else None,
            status="Active",
            active_flag=True,
            fortnight_group=None,
            review_required=review_required,
            review_reason="Needs review" if review_required else None,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )

    def _task(self, pickup_task_id, pickup_date, status="ACTIVE"):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=None,
            opshop_id="OPSHOP-001",
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="MANUAL",
            status=status,
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes="Manual fixture",
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class OpShopBoardPayloadRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-board-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="OPSHOP-001",
                name="Northside Op Shop",
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
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id="SCHED-001",
                opshop_id="OPSHOP-001",
                run_day="MONDAY",
                run_type="STANDARD",
                pickup_frequency="Weekly",
                time_window="9-12",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at="2026-05-19T00:00:00+00:00",
                updated_at="2026-05-19T00:00:00+00:00",
            )
        )
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service

        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_board_api_response_contains_opshop_pickups(self):
        response = self.client.get(
            "/api/manual-dispatch/board",
            params={"dispatch_date": "2026-05-18"},
        )

        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertIn("opshop_pickups", payload)
        self.assertEqual(
            ["2026-05-25", "2026-06-01"],
            [item["pickup_date"] for item in payload["opshop_pickups"]],
        )
        self.assertEqual("Northside Op Shop", payload["opshop_pickups"][0]["opshop_name"])


if __name__ == "__main__":
    unittest.main()
