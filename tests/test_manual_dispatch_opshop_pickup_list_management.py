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
    AssignTaskRequest,
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    CreateOpShopPickupTaskRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    UpdateOpShopPickupTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class OpShopPickupListManagementTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.repository.upsert_opshop_location(self._location())
        self.repository.upsert_opshop_pickup_schedule(self._schedule("SCHED-STANDARD"))
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-REGULAR", run_type="REGULAR")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-ONCALL", run_type="ON_CALL")
        )
        self.service = ManualDispatchService(self.repository)

    def test_schedule_candidates_return_active_regular_only(self):
        candidates = self.service.list_opshop_pickup_schedule_candidates("scheduled")

        self.assertEqual(["SCHED-REGULAR"], sorted(candidate.schedule_id for candidate in candidates))
        self.assertEqual("Northside Op Shop", candidates[0].opshop_name)
        self.assertEqual("Coburg", candidates[0].suburb)
        self.assertEqual("0400 000 001", candidates[0].primary_phone)

    def test_oncall_schedule_candidates_return_active_oncall_templates(self):
        candidates = self.service.list_opshop_pickup_schedule_candidates("oncall")

        self.assertEqual(["SCHED-ONCALL"], [candidate.schedule_id for candidate in candidates])
        self.assertEqual("ON_CALL", candidates[0].run_type)
        self.assertEqual("Northside Op Shop", candidates[0].opshop_name)

    def test_create_pickup_from_standard_and_regular_schedule_succeeds(self):
        standard = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
                notes="Manual standard",
            )
        )
        regular = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-REGULAR",
                pickup_date="2026-05-19",
                notes="Manual regular",
            )
        )

        self.assertEqual("MANUAL", standard.generated_from)
        self.assertEqual("ACTIVE", standard.status)
        self.assertEqual("2026-05-18", standard.dispatch_date)
        self.assertIsNone(standard.driver_id)
        self.assertIsNone(standard.trip_no)
        self.assertEqual("MANUAL", regular.generated_from)

    def test_create_on_call_or_duplicate_pickup_fails(self):
        with self.assertRaisesRegex(ValueError, "STANDARD or REGULAR"):
            self.service.create_opshop_pickup_task(
                CreateOpShopPickupTaskRequest(
                    schedule_id="SCHED-ONCALL",
                    pickup_date="2026-05-18",
                )
            )

        self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
            )
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.create_opshop_pickup_task(
                CreateOpShopPickupTaskRequest(
                    schedule_id="SCHED-STANDARD",
                    pickup_date="2026-05-18",
                )
            )

    def test_create_oncall_pickup_from_oncall_template_succeeds_and_prevents_duplicates(self):
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-ONCALL",
                pickup_date="2026-05-20",
                notes="Phone request",
            )
        )

        self.assertEqual("ON_CALL", task.generated_from)
        self.assertEqual("ACTIVE", task.status)
        self.assertEqual("2026-05-20", task.dispatch_date)
        self.assertIsNone(task.driver_id)
        self.assertIsNone(task.trip_no)
        self.assertEqual("Phone request", task.notes)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.create_oncall_opshop_pickup_task(
                CreateOpShopPickupTaskRequest(
                    schedule_id="SCHED-ONCALL",
                    pickup_date="2026-05-20",
                )
            )
        with self.assertRaisesRegex(ValueError, "Only ON_CALL"):
            self.service.create_oncall_opshop_pickup_task(
                CreateOpShopPickupTaskRequest(
                    schedule_id="SCHED-REGULAR",
                    pickup_date="2026-05-20",
                )
            )

    def test_create_oncall_pickup_from_no_run_day_template_requires_pickup_date(self):
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule("SCHED-GAVIN", run_day=None, run_type="ON_CALL")
        )

        with self.assertRaisesRegex(ValueError, "pickup_date is required"):
            self.service.create_oncall_opshop_pickup_task(
                CreateOpShopPickupTaskRequest(schedule_id="SCHED-GAVIN")
            )
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-GAVIN",
                pickup_date="2026-05-22",
            )
        )

        self.assertEqual("ON_CALL", task.generated_from)
        self.assertEqual("2026-05-22", task.pickup_date)

    def test_update_active_pickup_date_and_notes_succeeds(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
                notes="Before",
            )
        )

        updated = self.service.update_opshop_pickup_task(
            task.pickup_task_id,
            UpdateOpShopPickupTaskRequest(
                pickup_date="2026-05-19",
                notes="After",
            ),
        )

        self.assertEqual("2026-05-19", updated.pickup_date)
        self.assertEqual("2026-05-19", updated.dispatch_date)
        self.assertEqual("After", updated.notes)

    def test_update_active_pickup_date_prevents_duplicate_schedule_date(self):
        first = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
            )
        )
        self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-19",
            )
        )

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.update_opshop_pickup_task(
                first.pickup_task_id,
                UpdateOpShopPickupTaskRequest(pickup_date="2026-05-19"),
            )

    def test_update_assigned_notes_succeeds_but_pickup_date_fails(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
                notes="Before",
            )
        )
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id=task.pickup_task_id,
                driver_id="D001",
                trip_no="trip1",
            )
        )

        updated = self.service.update_opshop_pickup_task(
            task.pickup_task_id,
            UpdateOpShopPickupTaskRequest(
                pickup_date="2026-05-18",
                notes="Assigned note",
            ),
        )

        self.assertEqual("Assigned note", updated.notes)
        with self.assertRaisesRegex(ValueError, "cannot change pickup date"):
            self.service.update_opshop_pickup_task(
                task.pickup_task_id,
                UpdateOpShopPickupTaskRequest(pickup_date="2026-05-19"),
            )

    def test_update_cancelled_or_completed_pickup_fails(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
            )
        )
        self.service.delete_opshop_pickup_task(task.pickup_task_id)

        with self.assertRaisesRegex(ValueError, "cannot be edited"):
            self.service.update_opshop_pickup_task(
                task.pickup_task_id,
                UpdateOpShopPickupTaskRequest(notes="Nope"),
            )

    def test_delete_active_pickup_cancels_and_prevents_regeneration(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
            )
        )

        cancelled = self.service.delete_opshop_pickup_task(task.pickup_task_id)
        board = self.service.get_board("2026-05-18")

        self.assertEqual("CANCELLED", cancelled.status)
        self.assertNotIn(
            task.pickup_task_id,
            [item.pickup_task_id for item in board.scheduled_opshop_pickups],
        )
        self.assertEqual(
            task.pickup_task_id,
            self.repository.find_opshop_pickup_task_by_schedule_and_date(
                "SCHED-STANDARD",
                "2026-05-18",
            ).pickup_task_id,
        )
        self.assertEqual("CANCELLED", self.repository.get_opshop_pickup_task(task.pickup_task_id).status)

    def test_delete_assigned_pickup_fails(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-STANDARD",
                pickup_date="2026-05-18",
            )
        )
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id=task.pickup_task_id,
                driver_id="D001",
                trip_no="trip1",
            )
        )

        with self.assertRaisesRegex(ValueError, "Unassign"):
            self.service.delete_opshop_pickup_task(task.pickup_task_id)

    def test_apply_weekly_assignments_assigns_visible_regular_pickups_to_trip1(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-REGULAR",
                pickup_date="2026-05-18",
            )
        )

        board = self.service.apply_weekly_opshop_pickup_assignments(
            ApplyWeeklyOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)
        assignment = self.repository.get_assignment(
            "2026-05-18",
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )

        self.assertEqual("ASSIGNED", updated.status)
        self.assertEqual("D001", updated.driver_id)
        self.assertEqual("trip1", updated.trip_no)
        self.assertEqual("OPSHOP_PICKUP", assignment.task_type)
        self.assertEqual("trip1", assignment.trip_no)
        self.assertIn(
            task.pickup_task_id,
            [item.pickup_task_id for item in board.assigned_opshop_pickups],
        )

    def test_apply_weekly_assignments_skips_locked_past_pickup_rows(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-REGULAR",
                pickup_date="2026-05-18",
            )
        )

        self.service.apply_weekly_opshop_pickup_assignments(
            ApplyWeeklyOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-21",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)

        self.assertEqual("ACTIVE", updated.status)
        self.assertIsNone(updated.driver_id)
        self.assertIsNone(
            self.repository.get_assignment(
                "2026-05-21",
                "OPSHOP_PICKUP",
                task.pickup_task_id,
            )
        )

    def test_apply_weekly_assignments_blank_driver_unassigns_visible_regular_pickup(self):
        task = self.service.create_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-REGULAR",
                pickup_date="2026-05-18",
            )
        )
        self.service.apply_weekly_opshop_pickup_assignments(
            ApplyWeeklyOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )

        self.service.apply_weekly_opshop_pickup_assignments(
            ApplyWeeklyOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": ""},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)

        self.assertEqual("ACTIVE", updated.status)
        self.assertIsNone(updated.driver_id)
        self.assertIsNone(updated.trip_no)

    def test_apply_oncall_assignments_assigns_visible_oncall_pickups_to_trip1(self):
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-ONCALL",
                pickup_date="2026-05-20",
            )
        )

        board = self.service.apply_oncall_opshop_pickup_assignments(
            ApplyOncallOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)
        assignment = self.repository.get_assignment(
            "2026-05-18",
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )

        self.assertEqual("ASSIGNED", updated.status)
        self.assertEqual("D001", updated.driver_id)
        self.assertEqual("trip1", updated.trip_no)
        self.assertEqual("OPSHOP_PICKUP", assignment.task_type)
        self.assertEqual("trip1", assignment.trip_no)
        self.assertIn(
            task.pickup_task_id,
            [item.pickup_task_id for item in board.assigned_opshop_pickups],
        )

    def test_apply_oncall_assignments_skips_locked_past_pickup_rows(self):
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-ONCALL",
                pickup_date="2026-05-18",
            )
        )

        self.service.apply_oncall_opshop_pickup_assignments(
            ApplyOncallOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-21",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)

        self.assertEqual("ACTIVE", updated.status)
        self.assertIsNone(updated.driver_id)
        self.assertIsNone(
            self.repository.get_assignment(
                "2026-05-21",
                "OPSHOP_PICKUP",
                task.pickup_task_id,
            )
        )

    def test_apply_oncall_assignments_blank_driver_unassigns_visible_oncall_pickup(self):
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id="SCHED-ONCALL",
                pickup_date="2026-05-20",
            )
        )
        self.service.apply_oncall_opshop_pickup_assignments(
            ApplyOncallOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )

        self.service.apply_oncall_opshop_pickup_assignments(
            ApplyOncallOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-18",
                assignments=[
                    {"pickup_task_id": task.pickup_task_id, "driver_id": ""},
                ],
            )
        )
        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)

        self.assertEqual("ACTIVE", updated.status)
        self.assertIsNone(updated.driver_id)
        self.assertIsNone(updated.trip_no)

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

    def _schedule(self, schedule_id, run_type="STANDARD", run_day="MONDAY"):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id="OPSHOP-001",
            run_day=run_day,
            run_type=run_type,
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


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class OpShopPickupListManagementRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-list-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.repository.upsert_opshop_location(OpShopPickupListManagementTest()._location())
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupListManagementTest()._schedule("SCHED-STANDARD")
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupListManagementTest()._schedule("SCHED-REGULAR", run_type="REGULAR")
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupListManagementTest()._schedule("SCHED-ONCALL", run_type="ON_CALL")
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

    def test_schedule_candidate_endpoint_returns_active_regular_only(self):
        response = self.client.get(
            "/api/manual-dispatch/opshop-pickup-schedules",
            params={"run_type": "scheduled"},
        )

        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(["SCHED-REGULAR"], [item["schedule_id"] for item in payload])
        self.assertEqual("Northside Op Shop", payload[0]["opshop_name"])

    def test_oncall_schedule_candidate_endpoint_returns_oncall_templates(self):
        response = self.client.get(
            "/api/manual-dispatch/opshop-pickup-schedules",
            params={"run_type": "oncall"},
        )

        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(["SCHED-ONCALL"], [item["schedule_id"] for item in payload])
        self.assertEqual("ON_CALL", payload[0]["run_type"])

    def test_create_update_and_delete_pickup_endpoints(self):
        create_response = self.client.post(
            "/api/manual-dispatch/opshop-pickups",
            json={
                "schedule_id": "SCHED-REGULAR",
                "pickup_date": "2026-05-18",
                "notes": "Manual",
            },
        )
        pickup_id = create_response.json()["pickup_task_id"]

        update_response = self.client.patch(
            f"/api/manual-dispatch/opshop-pickups/{pickup_id}",
            json={"pickup_date": "2026-05-19", "notes": "Updated"},
        )
        delete_response = self.client.delete(f"/api/manual-dispatch/opshop-pickups/{pickup_id}")

        self.assertEqual(200, create_response.status_code)
        self.assertEqual(200, update_response.status_code)
        self.assertEqual("2026-05-19", update_response.json()["pickup_date"])
        self.assertEqual("Updated", update_response.json()["notes"])
        self.assertEqual(200, delete_response.status_code)
        self.assertEqual("CANCELLED", delete_response.json()["status"])

    def test_create_oncall_and_apply_oncall_assignments_endpoints(self):
        create_response = self.client.post(
            "/api/manual-dispatch/opshop-pickups/oncall",
            json={
                "schedule_id": "SCHED-ONCALL",
                "pickup_date": "2026-05-20",
                "assigned_driver_id": "D001",
                "notes": "Phone request",
            },
        )
        pickup_id = create_response.json()["pickup_task_id"]

        apply_response = self.client.post(
            "/api/manual-dispatch/opshop-pickups/oncall-assignments/apply",
            json={
                "dispatch_date": "2026-05-18",
                "assignments": [
                    {"pickup_task_id": pickup_id, "driver_id": "D001"},
                ],
            },
        )
        payload = apply_response.json()

        self.assertEqual(200, create_response.status_code)
        self.assertEqual("ON_CALL", create_response.json()["generated_from"])
        self.assertEqual(200, apply_response.status_code)
        self.assertEqual([pickup_id], [item["pickup_task_id"] for item in payload["assigned_opshop_pickups"]])
        self.assertEqual("D001", payload["assigned_opshop_pickups"][0]["driver_id"])
        self.assertEqual("trip1", payload["assigned_opshop_pickups"][0]["trip_no"])

    def test_apply_weekly_assignments_endpoint_returns_updated_board(self):
        create_response = self.client.post(
            "/api/manual-dispatch/opshop-pickups",
            json={
                "schedule_id": "SCHED-REGULAR",
                "pickup_date": "2026-05-18",
                "notes": "Manual",
            },
        )
        pickup_id = create_response.json()["pickup_task_id"]

        apply_response = self.client.post(
            "/api/manual-dispatch/opshop-pickups/weekly-assignments/apply",
            json={
                "dispatch_date": "2026-05-18",
                "assignments": [
                    {"pickup_task_id": pickup_id, "driver_id": "D001"},
                ],
            },
        )
        payload = apply_response.json()

        self.assertEqual(200, apply_response.status_code)
        self.assertEqual([pickup_id], [item["pickup_task_id"] for item in payload["assigned_opshop_pickups"]])
        self.assertEqual("D001", payload["assigned_opshop_pickups"][0]["driver_id"])
        self.assertEqual("trip1", payload["assigned_opshop_pickups"][0]["trip_no"])


if __name__ == "__main__":
    unittest.main()
