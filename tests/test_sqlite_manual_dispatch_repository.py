import sqlite3
import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    UnassignTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class SQLiteManualDispatchRepositoryTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"sqlite-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repository_initializes_schema(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertIn("manual_orders", tables)
        self.assertIn("manual_drivers", tables)
        self.assertIn("manual_vehicles", tables)
        self.assertIn("manual_dispatch_assignments", tables)
        self.assertIn("manual_driver_vehicle_assignments", tables)

    def test_seed_data_loads_orders_drivers_and_vehicles(self):
        board = self.service.get_board("2026-05-05")

        self.assertEqual(
            ["Dandenong", "Clayton", "Springvale"],
            [order.suburb for order in board.orders],
        )
        self.assertEqual(["John", "Tony", "David"], [driver.name for driver in board.drivers])
        self.assertEqual(
            ["ABC123", "XYZ888", "MCC001"],
            [vehicle.rego for vehicle in board.vehicles],
        )

    def test_assign_task_persists_assignment(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        self.assertEqual(1, len(board.assignments))
        self.assertEqual("ORDER", board.assignments[0].task_type)
        self.assertEqual("ORD-001", board.assignments[0].task_id)

    def test_unassign_task_removes_persisted_assignment(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        self.service.unassign_task(
            UnassignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")
        self.assertEqual([], board.assignments)

    def test_assign_vehicle_to_driver_persists_driver_date_vehicle_selection(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        self.assertEqual(1, len(board.driver_vehicle_assignments))
        self.assertEqual("D001", board.driver_vehicle_assignments[0].driver_id)
        self.assertEqual("V002", board.driver_vehicle_assignments[0].vehicle_id)

    def test_vehicle_assignment_does_not_modify_task_assignment_records(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip2",
            )
        )

        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        board = self.service.get_board("2026-05-05")
        self.assertEqual(1, len(board.assignments))
        self.assertFalse(hasattr(board.assignments[0], "vehicle_id"))

    def test_duplicate_vehicle_assignment_across_drivers_is_allowed(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V001",
            )
        )
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D002",
                vehicle_id="V001",
            )
        )

        board = self.service.get_board("2026-05-05")
        self.assertEqual(2, len(board.driver_vehicle_assignments))
        self.assertEqual(
            ["V001", "V001"],
            [assignment.vehicle_id for assignment in board.driver_vehicle_assignments],
        )

    def test_invalid_trip_no_is_rejected_through_service(self):
        with self.assertRaises(ValueError):
            self.service.assign_task(
                AssignTaskRequest(
                    dispatch_date="2026-05-05",
                    task_type="ORDER",
                    task_id="ORD-001",
                    driver_id="D001",
                    trip_no="trip3",
                )
            )

    def test_invalid_vehicle_id_is_rejected_through_service(self):
        with self.assertRaises(ValueError):
            self.service.assign_vehicle_to_driver(
                AssignDriverVehicleRequest(
                    dispatch_date="2026-05-05",
                    driver_id="D001",
                    vehicle_id="V999",
                )
            )


if __name__ == "__main__":
    unittest.main()
