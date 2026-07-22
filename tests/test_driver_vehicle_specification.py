import shutil
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateDriverRequest,
    CreateVehicleRequest,
    UpdateDriverRequest,
    UpdateVehicleRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class DriverVehicleSpecificationTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"specification-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.dispatch_date = "2026-05-05"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_specifications_returns_drivers_and_vehicles(self):
        specifications = self.service.get_specifications()

        self.assertGreaterEqual(len(specifications.drivers), 3)
        self.assertGreaterEqual(len(specifications.vehicles), 3)

    def test_create_driver_saves_driver_and_generates_unique_id(self):
        driver = self.service.create_driver(
            CreateDriverRequest(
                name="Maria",
                license_no="LIC-MARIA",
                email="maria@example.com",
                phone_number="0400 999 001",
                is_available=True,
                pallet_only=True,
                preferred_zone="South East",
            )
        )

        self.assertEqual("D004", driver.driver_id)
        self.assertEqual("Maria", driver.name)
        self.assertTrue(driver.pallet_only)
        self.assertIn(driver.driver_id, [item.driver_id for item in self.service.get_board(self.dispatch_date).drivers])

    def test_update_driver_updates_fields(self):
        updated = self.service.update_driver(
            "D001",
            UpdateDriverRequest(
                name="John Updated",
                license_no="LIC-UPDATED",
                email="updated@example.com",
                phone_number="0400 111 222",
                start_time="07:30",
                end_time="15:30",
                is_available=True,
                pallet_only=True,
                preferred_zone="West",
            ),
        )

        self.assertEqual("John Updated", updated.name)
        self.assertEqual("LIC-UPDATED", updated.license_no)
        self.assertTrue(updated.pallet_only)

    def test_driver_availability_false_hides_driver_from_board_but_not_specs(self):
        self.service.update_driver(
            "D003",
            UpdateDriverRequest(name="David", is_available=False, pallet_only=False),
        )

        board_driver_ids = [driver.driver_id for driver in self.service.get_board(self.dispatch_date).drivers]
        spec_driver_ids = [driver.driver_id for driver in self.service.get_specifications().drivers]

        self.assertNotIn("D003", board_driver_ids)
        self.assertIn("D003", spec_driver_ids)

    def test_driver_availability_false_is_rejected_with_active_assignment(self):
        self._assign_order("ORD-001", "D001", "trip1")

        with self.assertRaises(ValueError) as context:
            self.service.update_driver(
                "D001",
                UpdateDriverRequest(name="John", is_available=False, pallet_only=False),
            )

        self.assertIn("unassign or finalize", str(context.exception))

    def test_delete_unused_driver_soft_deletes_and_hides_from_specs(self):
        self.service.delete_driver("D003")

        self.assertNotIn(
            "D003",
            [driver.driver_id for driver in self.service.get_specifications().drivers],
        )
        self.assertTrue(self.repository.get_driver("D003").is_deleted)

    def test_delete_driver_with_assignment_is_rejected(self):
        self._assign_order("ORD-001", "D001", "trip1")

        with self.assertRaises(ValueError):
            self.service.delete_driver("D001")

    def test_missing_driver_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_driver(CreateDriverRequest(name=""))

    def test_create_vehicle_saves_vehicle_and_generates_unique_id(self):
        vehicle = self.service.create_vehicle(
            CreateVehicleRequest(
                rego="NEW999",
                type="van",
                is_available=True,
                pallet_capacity=5,
                tub_capacity=1,
                trolley_capacity=2,
                stillage_capacity=3,
            )
        )

        self.assertEqual("V004", vehicle.vehicle_id)
        self.assertEqual("NEW999", vehicle.rego)
        self.assertIn(vehicle.vehicle_id, [item.vehicle_id for item in self.service.get_board(self.dispatch_date).vehicles])

    def test_update_vehicle_updates_fields(self):
        updated = self.service.update_vehicle(
            "V001",
            UpdateVehicleRequest(
                rego="UPD123",
                type="truck",
                is_available=True,
                pallet_capacity=12,
                tub_capacity=2,
                trolley_capacity=3,
                stillage_capacity=4,
            ),
        )

        self.assertEqual("UPD123", updated.rego)
        self.assertEqual(12, updated.pallet_capacity)

    def test_vehicle_availability_false_hides_vehicle_from_board_but_not_specs(self):
        self.service.update_vehicle(
            "V003",
            UpdateVehicleRequest(rego="MCC001", type="truck", is_available=False),
        )

        board_vehicle_ids = [vehicle.vehicle_id for vehicle in self.service.get_board(self.dispatch_date).vehicles]
        spec_vehicle_ids = [vehicle.vehicle_id for vehicle in self.service.get_specifications().vehicles]

        self.assertNotIn("V003", board_vehicle_ids)
        self.assertIn("V003", spec_vehicle_ids)

    def test_vehicle_availability_false_is_rejected_when_selected(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                vehicle_id="V001",
            )
        )

        with self.assertRaises(ValueError) as context:
            self.service.update_vehicle(
                "V001",
                UpdateVehicleRequest(rego="ABC123", type="truck", is_available=False),
            )

        self.assertIn("clear this vehicle", str(context.exception))

    def test_delete_unused_vehicle_soft_deletes_and_hides_from_specs(self):
        self.service.delete_vehicle("V003")

        self.assertNotIn(
            "V003",
            [vehicle.vehicle_id for vehicle in self.service.get_specifications().vehicles],
        )
        self.assertTrue(self.repository.get_vehicle("V003").is_deleted)

    def test_delete_selected_vehicle_is_rejected(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                vehicle_id="V001",
            )
        )

        with self.assertRaises(ValueError):
            self.service.delete_vehicle("V001")

    def test_missing_vehicle_rego_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_vehicle(CreateVehicleRequest(rego=""))

    def test_negative_vehicle_capacity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_vehicle(
                CreateVehicleRequest(rego="BAD123", pallet_capacity=-1)
            )

    def test_assign_unassign_and_choose_vehicle_still_work(self):
        assignment = self._assign_order("ORD-001", "D001", "trip1")
        vehicle_assignment = self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                vehicle_id="V001",
            )
        )

        self.assertEqual("ORD-001", assignment.task_id)
        self.assertEqual("V001", vehicle_assignment.vehicle_id)

    def _assign_order(self, order_id, driver_id, trip_no):
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id=order_id,
                driver_id=driver_id,
                trip_no=trip_no,
            )
        )


if __name__ == "__main__":
    unittest.main()
