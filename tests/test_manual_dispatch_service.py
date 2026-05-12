import unittest

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateOrderRequest,
    UnassignTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class ManualDispatchServiceTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.service = ManualDispatchService(self.repository)

    def test_get_board_returns_demo_data(self):
        board = self.service.get_board("2026-05-05")

        self.assertEqual("2026-05-05", board.dispatch_date)
        self.assertEqual(["Dandenong", "Clayton", "Springvale"], [order.suburb for order in board.orders])
        self.assertEqual(
            ["INV-1001", "INV-1002", "INV-1003"],
            [order.invoice_number for order in board.orders],
        )
        self.assertEqual(
            ["0400 000 001", "0400 000 002", "0400 000 003"],
            [order.phone for order in board.orders],
        )
        self.assertEqual(["John", "Tony", "David"], [driver.name for driver in board.drivers])
        self.assertEqual([False, True, False], [driver.pallet_only for driver in board.drivers])
        self.assertEqual(["ABC123", "XYZ888", "MCC001"], [vehicle.rego for vehicle in board.vehicles])

    def test_get_board_filters_orders_by_dispatch_date(self):
        created = self.service.create_order(
            CreateOrderRequest(
                company_name="Date Filter Customer",
                suburb="Richmond",
                delivery_date="2026-05-06",
            )
        )

        board_0505 = self.service.get_board("2026-05-05")
        board_0506 = self.service.get_board("2026-05-06")

        self.assertNotIn(created.order_id, [order.order_id for order in board_0505.orders])
        self.assertIn(created.order_id, [order.order_id for order in board_0506.orders])
        self.assertTrue(
            all(order.delivery_date == "2026-05-05" for order in board_0505.orders)
        )
        self.assertTrue(
            all(order.delivery_date == "2026-05-06" for order in board_0506.orders)
        )

    def test_assign_task_creates_assignment_with_task_type_and_task_id(self):
        assignment = self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        self.assertEqual("A-001", assignment.assignment_id)
        self.assertEqual("ORDER", assignment.task_type)
        self.assertEqual("ORD-001", assignment.task_id)
        self.assertEqual("D001", assignment.driver_id)
        self.assertEqual("trip1", assignment.trip_no)

    def test_unassign_task_removes_assignment(self):
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

        board = self.service.get_board("2026-05-05")
        self.assertEqual([], board.assignments)

    def test_assign_vehicle_to_driver_stores_driver_date_vehicle_selection(self):
        vehicle_assignment = self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        self.assertEqual("2026-05-05", vehicle_assignment.dispatch_date)
        self.assertEqual("D001", vehicle_assignment.driver_id)
        self.assertEqual("V002", vehicle_assignment.vehicle_id)

    def test_assigning_vehicle_does_not_modify_task_assignment_records(self):
        task_assignment = self.service.assign_task(
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
        self.assertEqual([task_assignment], board.assignments)
        self.assertFalse(hasattr(board.assignments[0], "vehicle_id"))

    def test_invalid_trip_no_is_rejected(self):
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

    def test_invalid_driver_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.assign_task(
                AssignTaskRequest(
                    dispatch_date="2026-05-05",
                    task_type="ORDER",
                    task_id="ORD-001",
                    driver_id="D999",
                    trip_no="trip1",
                )
            )


if __name__ == "__main__":
    unittest.main()
