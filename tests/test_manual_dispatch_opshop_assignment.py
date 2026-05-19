import unittest
import shutil
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
    OpShopLocation,
    OpShopPickupTask,
    RegisterOperatorAccountRequest,
    SaveFinalTripSummaryRequest,
    UnassignTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class ManualDispatchOpShopAssignmentTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.repository.upsert_opshop_location(self._location())
        self.service = ManualDispatchService(self.repository)

    def test_assign_active_opshop_pickup_creates_assignment_and_updates_task(self):
        self.repository.upsert_opshop_pickup_task(self._task("TASK-001"))

        assignment = self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id="TASK-001",
                driver_id="D001",
                trip_no="trip2",
            )
        )

        task = self.repository.get_opshop_pickup_task("TASK-001")
        board = self.service.get_board("2026-05-18")

        self.assertEqual("OPSHOP_PICKUP", assignment.task_type)
        self.assertEqual("TASK-001", assignment.task_id)
        self.assertEqual("ASSIGNED", task.status)
        self.assertEqual("D001", task.driver_id)
        self.assertEqual("trip2", task.trip_no)
        self.assertEqual(["TASK-001"], [item.pickup_task_id for item in board.assigned_opshop_pickups])
        self.assertNotIn("TASK-001", [item.pickup_task_id for item in board.opshop_pickups])
        self.assertEqual(["TASK-001"], [item.task_id for item in board.assignments])

    def test_assign_missing_opshop_pickup_fails(self):
        with self.assertRaises(ValueError):
            self.service.assign_task(
                AssignTaskRequest(
                    dispatch_date="2026-05-18",
                    task_type="OPSHOP_PICKUP",
                    task_id="TASK-MISSING",
                    driver_id="D001",
                    trip_no="trip1",
                )
            )

    def test_assign_cancelled_completed_or_assigned_opshop_pickup_fails(self):
        for status in ["CANCELLED", "COMPLETED", "ASSIGNED"]:
            with self.subTest(status=status):
                task_id = f"TASK-{status}"
                self.repository.upsert_opshop_pickup_task(self._task(task_id, status=status))

                with self.assertRaises(ValueError):
                    self.service.assign_task(
                        AssignTaskRequest(
                            dispatch_date="2026-05-18",
                            task_type="OPSHOP_PICKUP",
                            task_id=task_id,
                            driver_id="D001",
                            trip_no="trip1",
                        )
                    )

    def test_unassign_opshop_pickup_clears_assignment_and_returns_to_task_pool(self):
        self.repository.upsert_opshop_pickup_task(self._task("TASK-001"))
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id="TASK-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        board = self.service.unassign_task(
            UnassignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id="TASK-001",
            )
        )

        task = self.repository.get_opshop_pickup_task("TASK-001")
        self.assertEqual("ACTIVE", task.status)
        self.assertIsNone(task.driver_id)
        self.assertIsNone(task.trip_no)
        self.assertEqual([], board.assignments)
        self.assertEqual([], board.assigned_opshop_pickups)
        self.assertIn("TASK-001", [item.pickup_task_id for item in board.opshop_pickups])

    def test_delivery_order_assignment_still_works(self):
        assignment = self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        self.assertEqual("ORDER", assignment.task_type)
        self.assertEqual("ORD-001", assignment.task_id)

    def test_final_trip_summary_rejects_opshop_pickup_rows(self):
        self.repository.upsert_opshop_pickup_task(self._task("TASK-001"))
        self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Mandy",
                password="secret123",
                confirm_password="secret123",
            )
        )

        with self.assertRaisesRegex(ValueError, "ORDER tasks only"):
            self.service.save_final_trip_summary(
                SaveFinalTripSummaryRequest(
                    dispatch_date="2026-05-18",
                    delivery_date="2026-05-18",
                    driver_id="D001",
                    driver_name_snapshot="John",
                    vehicle_id=None,
                    vehicle_rego_snapshot=None,
                    total_pallets=0,
                    total_loose_bags=0,
                    generated_at="2026-05-19T00:00:00+00:00",
                    saved_by_account_name="Mandy",
                    trips=[
                        {
                            "trip_no": "trip1",
                            "orders": [
                                {
                                    "task_type": "OPSHOP_PICKUP",
                                    "task_id": "TASK-001",
                                    "company_name_snapshot": "Northside Op Shop",
                                    "suburb_snapshot": "Coburg",
                                    "delivery_address_snapshot": "1 Sydney Road",
                                }
                            ],
                        }
                    ],
                )
            )

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

    def _task(self, pickup_task_id, status="ACTIVE"):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=None,
            opshop_id="OPSHOP-001",
            pickup_date="2026-05-20",
            task_type="OPSHOP_PICKUP",
            generated_from="STANDARD",
            status=status,
            dispatch_date="2026-05-20",
            driver_id="D001" if status == "ASSIGNED" else None,
            trip_no="trip1" if status == "ASSIGNED" else None,
            notes="Manual fixture",
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )


class SQLiteManualDispatchOpShopAssignmentTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-assignment-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.repository.upsert_opshop_location(self._location())
        self.repository.upsert_opshop_pickup_task(self._task("TASK-001"))
        self.service = ManualDispatchService(self.repository)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_assign_and_unassign_opshop_pickup_persists_task_status(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id="TASK-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        assigned_task = self.repository.get_opshop_pickup_task("TASK-001")
        assigned_board = self.service.get_board("2026-05-18")

        self.assertEqual("ASSIGNED", assigned_task.status)
        self.assertEqual("D001", assigned_task.driver_id)
        self.assertEqual("trip1", assigned_task.trip_no)
        self.assertEqual(["TASK-001"], [item.pickup_task_id for item in assigned_board.assigned_opshop_pickups])

        self.service.unassign_task(
            UnassignTaskRequest(
                dispatch_date="2026-05-18",
                task_type="OPSHOP_PICKUP",
                task_id="TASK-001",
            )
        )

        unassigned_task = self.repository.get_opshop_pickup_task("TASK-001")
        unassigned_board = self.service.get_board("2026-05-18")

        self.assertEqual("ACTIVE", unassigned_task.status)
        self.assertIsNone(unassigned_task.driver_id)
        self.assertIsNone(unassigned_task.trip_no)
        self.assertEqual([], unassigned_board.assigned_opshop_pickups)
        self.assertIn("TASK-001", [item.pickup_task_id for item in unassigned_board.opshop_pickups])

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

    def _task(self, pickup_task_id):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=None,
            opshop_id="OPSHOP-001",
            pickup_date="2026-05-20",
            task_type="OPSHOP_PICKUP",
            generated_from="STANDARD",
            status="ACTIVE",
            dispatch_date="2026-05-20",
            driver_id=None,
            trip_no=None,
            notes="SQLite fixture",
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
