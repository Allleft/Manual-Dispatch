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
        self.assertIn("assigned_opshop_pickups", payload)
        self.assertIn("scheduled_opshop_pickups", payload)
        self.assertIn("oncall_opshop_pickups", payload)
        self.assertIn("opshop_regular_list_window_start", payload)
        self.assertIn("opshop_regular_list_window_end", payload)
        self.assertEqual([], payload["opshop_pickups"])
        self.assertEqual([], payload["assigned_opshop_pickups"])
        self.assertEqual([], payload["scheduled_opshop_pickups"])
        self.assertEqual([], payload["oncall_opshop_pickups"])
        self.assertEqual("2026-05-18", payload["opshop_regular_list_window_start"])
        self.assertEqual("2026-05-22", payload["opshop_regular_list_window_end"])
        for key in [
            "dispatch_date",
            "orders",
            "drivers",
            "vehicles",
            "assignments",
            "driver_vehicle_assignments",
        ]:
            self.assertIn(key, payload)

    def test_board_load_auto_generates_regular_current_week_for_monday_dispatch(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY", pickup_frequency="Weekly")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(["2026-05-18"], self._pickup_dates())
        self.assertEqual([], board.opshop_pickups)
        self.assertEqual(
            ["2026-05-18"],
            [item.pickup_date for item in board.scheduled_opshop_pickups],
        )
        self.assertEqual("2026-05-18", board.opshop_regular_list_window_start)
        self.assertEqual("2026-05-22", board.opshop_regular_list_window_end)

    def test_board_load_for_thursday_uses_current_monday_to_friday_week(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="FRIDAY", pickup_frequency="Weekly")
        )

        board = self.service.get_board("2026-05-21")

        self.assertEqual(["2026-05-22"], [item.pickup_date for item in board.scheduled_opshop_pickups])
        self.assertEqual("2026-05-18", board.opshop_regular_list_window_start)
        self.assertEqual("2026-05-22", board.opshop_regular_list_window_end)

    def test_board_load_for_friday_refreshes_to_next_week(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY", pickup_frequency="Weekly")
        )

        board = self.service.get_board("2026-05-22")

        self.assertEqual(["2026-05-25"], self._pickup_dates())
        self.assertEqual(["2026-05-25"], [item.pickup_date for item in board.scheduled_opshop_pickups])
        self.assertEqual("2026-05-25", board.opshop_regular_list_window_start)
        self.assertEqual("2026-05-29", board.opshop_regular_list_window_end)

    def test_board_uses_schedule_run_day_only_and_does_not_expand_frequency_days(self):
        for frequency in ["2x Weekly", "2 x Weekly", "Twice weekly", "two times weekly"]:
            with self.subTest(frequency=frequency):
                self.repository = InMemoryManualDispatchRepository()
                self.repository.upsert_opshop_location(self._location())
                self.service = ManualDispatchService(self.repository)
                self.repository.upsert_opshop_pickup_schedule(
                    self._schedule(
                        "SCHED-001",
                        run_day="THURSDAY",
                        pickup_frequency=frequency,
                    )
                )

                first = self.service.get_board("2026-05-18")
                second = self.service.get_board("2026-05-18")

                self.assertEqual(["2026-05-21"], self._pickup_dates())
                self.assertEqual(
                    ["2026-05-21"],
                    [item.pickup_date for item in first.scheduled_opshop_pickups],
                )
                self.assertEqual(
                    [item.pickup_task_id for item in first.scheduled_opshop_pickups],
                    [item.pickup_task_id for item in second.scheduled_opshop_pickups],
                )
                self.assertEqual(1, len(second.scheduled_opshop_pickups))

    def test_cancelled_regular_pickup_blocks_regeneration_for_same_schedule_date(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHED-001",
                run_day="THURSDAY",
                pickup_frequency="2x Weekly",
            )
        )
        cancelled_id = "OPSHOP-PICKUP-20260521-CANCELLED"
        self.repository.upsert_opshop_pickup_task(
            self._task(
                cancelled_id,
                schedule_id="SCHED-001",
                pickup_date="2026-05-21",
                status="CANCELLED",
            )
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual([cancelled_id], [task.pickup_task_id for task in self.repository.list_opshop_pickup_tasks()])
        self.assertEqual([], board.scheduled_opshop_pickups)

    def test_board_excludes_pickups_outside_regular_week_window(self):
        self.repository.upsert_opshop_pickup_schedule(self._schedule("SCHED-001"))
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-OUTSIDE", pickup_date="2026-05-25")
        )

        board = self.service.get_board("2026-05-18")

        self.assertNotIn("TASK-OUTSIDE", [item.pickup_task_id for item in board.scheduled_opshop_pickups])

    def test_board_returns_joined_default_driver_location_schedule_and_task_fields(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHED-001",
                run_day="TUESDAY",
                pickup_frequency="Weekly",
                time_window="9-12",
                call_before_arrival=True,
                default_driver_id="D001",
                default_driver_alias="John G",
                default_driver_name_snapshot="John Georgiadis",
            )
        )

        board = self.service.get_board("2026-05-18")
        item = board.scheduled_opshop_pickups[0]

        self.assertTrue(item.pickup_task_id.startswith("OPSHOP-PICKUP-20260519-"))
        self.assertEqual("OPSHOP_PICKUP", item.task_type)
        self.assertEqual("SCHED-001", item.schedule_id)
        self.assertEqual("OPSHOP-001", item.opshop_id)
        self.assertEqual("Northside Op Shop", item.opshop_name)
        self.assertEqual("Coburg", item.suburb)
        self.assertEqual("1 Sydney Road", item.street_address)
        self.assertEqual("0400 000 001", item.primary_phone)
        self.assertEqual("TUESDAY", item.run_day)
        self.assertEqual("REGULAR", item.run_type)
        self.assertEqual("Weekly", item.pickup_frequency)
        self.assertEqual("9-12", item.time_window)
        self.assertTrue(item.call_before_arrival)
        self.assertEqual("2026-05-19", item.pickup_date)
        self.assertEqual("2026-05-19", item.dispatch_date)
        self.assertEqual("REGULAR", item.generated_from)
        self.assertEqual("ACTIVE", item.status)
        self.assertFalse(item.is_assigned)
        self.assertEqual("D001", item.default_driver_id)
        self.assertEqual("John G", item.default_driver_alias)
        self.assertEqual("John Georgiadis", item.default_driver_name)
        self.assertIsNone(item.assigned_driver_id)
        self.assertIsNone(item.assigned_driver_name)

    def test_board_marks_past_pickups_locked_for_assigned_to_dropdown(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY")
        )

        board = self.service.get_board("2026-05-21")

        self.assertEqual("2026-05-18", board.scheduled_opshop_pickups[0].pickup_date)
        self.assertTrue(board.scheduled_opshop_pickups[0].assigned_to_locked)

    def test_board_excludes_cancelled_completed_and_inactive_schedule_pickup_tasks(self):
        self.repository.upsert_opshop_pickup_schedule(self._schedule("SCHED-001"))
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-INACTIVE", active_flag=False, status="On_Hold")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-ACTIVE", pickup_date="2026-05-18", status="ACTIVE")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-CANCELLED", pickup_date="2026-05-19", status="CANCELLED")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-COMPLETED", pickup_date="2026-05-20", status="COMPLETED")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-INACTIVE-SCHEDULE", "SCHED-INACTIVE", pickup_date="2026-05-18", status="ACTIVE")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(["TASK-ACTIVE"], [item.pickup_task_id for item in board.scheduled_opshop_pickups])
        self.assertEqual([], board.opshop_pickups)

    def test_scheduled_opshop_pickups_include_active_and_assigned_regular_only(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-STANDARD", run_type="STANDARD")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-REGULAR", run_type="REGULAR")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ONCALL", run_type="ON_CALL")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-STANDARD", "SCHED-STANDARD", pickup_date="2026-05-18", status="ACTIVE")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-ACTIVE", "SCHED-REGULAR", pickup_date="2026-05-18", status="ACTIVE")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-ASSIGNED", "SCHED-REGULAR", pickup_date="2026-05-19", status="ASSIGNED")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task("TASK-ONCALL", "SCHED-ONCALL", pickup_date="2026-05-20", status="ACTIVE")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(
            ["TASK-ACTIVE", "TASK-ASSIGNED"],
            [item.pickup_task_id for item in board.scheduled_opshop_pickups],
        )
        self.assertEqual("ASSIGNED", board.scheduled_opshop_pickups[1].status)
        self.assertTrue(board.scheduled_opshop_pickups[1].is_assigned)

    def test_board_does_not_generate_on_call_or_review_required_schedules(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ON-CALL", run_type="ON_CALL", pickup_frequency="Weekly")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHED-REVIEW",
                run_type="REGULAR",
                pickup_frequency="Weekly",
                review_required=True,
            )
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual([], board.scheduled_opshop_pickups)
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_oncall_opshop_pickups_empty_before_actual_tasks_are_created(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ONCALL", run_type="ON_CALL")
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual([], board.oncall_opshop_pickups)
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_oncall_opshop_pickups_show_created_active_and_assigned_oncall_tasks_only(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ONCALL", run_type="ON_CALL")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-REGULAR", run_type="REGULAR")
        )
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "TASK-ONCALL-ACTIVE",
                "SCHED-ONCALL",
                pickup_date="2026-05-20",
                status="ACTIVE",
                generated_from="ON_CALL",
            )
        )
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "TASK-ONCALL-ASSIGNED",
                "SCHED-ONCALL",
                pickup_date="2026-05-21",
                status="ASSIGNED",
                generated_from="ON_CALL",
            )
        )
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "TASK-ONCALL-CANCELLED",
                "SCHED-ONCALL",
                pickup_date="2026-05-22",
                status="CANCELLED",
                generated_from="ON_CALL",
            )
        )
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "TASK-REGULAR",
                "SCHED-REGULAR",
                pickup_date="2026-05-20",
                status="ACTIVE",
                generated_from="REGULAR",
            )
        )

        board = self.service.get_board("2026-05-18")

        self.assertEqual(
            ["TASK-ONCALL-ACTIVE", "TASK-ONCALL-ASSIGNED"],
            [item.pickup_task_id for item in board.oncall_opshop_pickups],
        )
        self.assertEqual("ON_CALL", board.oncall_opshop_pickups[0].run_type)
        self.assertEqual("ASSIGNED", board.oncall_opshop_pickups[1].status)
        self.assertTrue(board.oncall_opshop_pickups[1].is_assigned)

    def test_repeated_board_load_does_not_duplicate_opshop_pickups(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-001", run_day="MONDAY", pickup_frequency="Weekly")
        )

        first = self.service.get_board("2026-05-18")
        second = self.service.get_board("2026-05-18")

        self.assertEqual(1, len(first.scheduled_opshop_pickups))
        self.assertEqual(1, len(second.scheduled_opshop_pickups))
        self.assertEqual(1, len(self.repository.list_opshop_pickup_tasks()))

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
        run_type="REGULAR",
        pickup_frequency="Weekly",
        time_window="9-12",
        call_before_arrival=False,
        review_required=False,
        active_flag=True,
        status="Active",
        default_driver_id=None,
        default_driver_alias=None,
        default_driver_name_snapshot=None,
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
            status=status,
            active_flag=active_flag,
            fortnight_group=None,
            review_required=review_required,
            review_reason="Needs review" if review_required else None,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
            default_driver_id=default_driver_id,
            default_driver_alias=default_driver_alias,
            default_driver_name_snapshot=default_driver_name_snapshot,
        )

    def _task(
        self,
        pickup_task_id,
        schedule_id=None,
        pickup_date="2026-05-20",
        status="ACTIVE",
        generated_from="MANUAL",
    ):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=schedule_id or "SCHED-001",
            opshop_id="OPSHOP-001",
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from=generated_from,
            status=status,
            dispatch_date=pickup_date,
            driver_id="D001" if status == "ASSIGNED" else None,
            trip_no="trip1" if status == "ASSIGNED" else None,
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
        fixture = OpShopBoardPayloadTest()
        self.repository.upsert_opshop_location(fixture._location())
        self.repository.upsert_opshop_pickup_schedule(
            fixture._schedule(
                "SCHED-001",
                run_day="MONDAY",
                run_type="REGULAR",
                pickup_frequency="Weekly",
                default_driver_id="D001",
                default_driver_alias="John G",
                default_driver_name_snapshot="John Georgiadis",
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

    def test_board_api_response_contains_regular_scheduled_opshop_pickups(self):
        response = self.client.get(
            "/api/manual-dispatch/board",
            params={"dispatch_date": "2026-05-18"},
        )

        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertIn("opshop_pickups", payload)
        self.assertIn("oncall_opshop_pickups", payload)
        self.assertEqual([], payload["opshop_pickups"])
        self.assertEqual([], payload["oncall_opshop_pickups"])
        self.assertEqual("2026-05-18", payload["opshop_regular_list_window_start"])
        self.assertEqual("2026-05-22", payload["opshop_regular_list_window_end"])
        self.assertEqual(
            ["2026-05-18"],
            [item["pickup_date"] for item in payload["scheduled_opshop_pickups"]],
        )
        self.assertEqual("Northside Op Shop", payload["scheduled_opshop_pickups"][0]["opshop_name"])
        self.assertEqual("D001", payload["scheduled_opshop_pickups"][0]["default_driver_id"])


if __name__ == "__main__":
    unittest.main()
