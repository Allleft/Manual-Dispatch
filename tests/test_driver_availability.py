import importlib
import tempfile
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from manual_dispatch_test_bootstrap import configure_test_environment

configure_test_environment()

from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CloseDeliveryRunSheetRequest,
    CloseDeliveryRunSheetRowRequest,
    CreateOpShopTemplateRequest,
    DeliveryWorkspaceAssignOrderRequest,
    GenerateDeliveryRunSheetRequest,
    OperatorAccountIdentity,
    OpShopWorkspaceAssignmentBatchRequest,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
    UpdateDriverRequest,
    UpdateVehicleRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class RecordingLogbook:
    def __init__(self):
        self.entries = []

    def record(self, **entry):
        self.entries.append(entry)


class DriverAvailabilityBehavior:
    def setUp(self):
        if self.repository_kind == "sqlite":
            temporary = tempfile.TemporaryDirectory(prefix="driver-availability-")
            self.addCleanup(temporary.cleanup)
            with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
                self.repository = SQLiteManualDispatchRepository(
                    Path(temporary.name) / "test.sqlite3"
                )
        else:
            self.repository = InMemoryManualDispatchRepository()
        self.service = ManualDispatchService(self.repository, logbook=RecordingLogbook())
        self.dispatch_date = "2026-05-05"
        self.password = uuid.uuid4().hex
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Availability tester",
                password=self.password,
                confirm_password=self.password,
            )
        )
        self.identity = OperatorAccountIdentity(
            account_id=self.account.account_id,
            account_name=self.account.account_name,
        )

    def _set_available(self, available):
        return self.service.update_delivery_driver(
            "D001", UpdateDriverRequest(is_available=available)
        )

    def _assign(self, order_id="ORD-001", driver_id="D001", trip_no="trip1", scoped=True):
        if scoped:
            return self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id=order_id,
                    driver_id=driver_id,
                    trip_no=trip_no,
                )
            )
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id=order_id,
                driver_id=driver_id,
                trip_no=trip_no,
            )
        )

    def _generate(self):
        return self.service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id="D001",
            )
        )

    def _save(self, sheet):
        return self.service.save_generated_delivery_run_sheet(
            sheet.run_sheet_id,
            SaveGeneratedWorkspaceSnapshotRequest(
                saved_by_account_name=self.account.account_name,
                saved_by_account_id=self.account.account_id,
            ),
        )

    def _close(self, sheet):
        return self.service.close_saved_delivery_run_sheet(
            sheet.run_sheet_id,
            CloseDeliveryRunSheetRequest(rows=[
                CloseDeliveryRunSheetRowRequest(
                    run_sheet_row_id=row.row_id, outcome="DELIVERED"
                )
                for trip in sheet.trips for row in trip.orders
            ]),
            self.identity,
        )

    def _regular_template(self, default_driver_id=None, name="Availability pickup"):
        return self.service.create_opshop_template(
            CreateOpShopTemplateRequest(
                name=name,
                run_type="REGULAR",
                run_day="Tuesday",
                pickup_frequency="Weekly",
                default_driver_id=default_driver_id,
            )
        )

    def _pickup(self, schedule_id, dispatch_date=None):
        board = self.service.get_opshop_workspace_board(dispatch_date or self.dispatch_date)
        return next(item for item in board.opshop_pickups if item.schedule_id == schedule_id)

    def test_toggle_preserves_orders_assignments_and_vehicle_selections(self):
        self._assign()
        self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(
            dispatch_date=self.dispatch_date, driver_id="D001", vehicle_id="V001"
        ))
        assignments = deepcopy(self.repository.list_assignments(self.dispatch_date))
        selections = deepcopy(self.repository.list_driver_vehicle_assignments(self.dispatch_date))
        order = deepcopy(self.repository.get_order("ORD-001"))
        self.assertFalse(self._set_available(False).is_available)
        self.assertEqual(assignments, self.repository.list_assignments(self.dispatch_date))
        self.assertEqual(selections, self.repository.list_driver_vehicle_assignments(self.dispatch_date))
        self.assertEqual(order, self.repository.get_order("ORD-001"))
        for board in (
            self.service.get_board(self.dispatch_date),
            self.service.get_delivery_workspace_board(self.dispatch_date),
            self.service.get_delivery_trip_summary_board(self.dispatch_date),
        ):
            self.assertIn("D001", [driver.driver_id for driver in board.drivers])
            self.assertEqual(assignments, board.assignments)

    def test_generated_open_run_sheet_contents_and_assignments_are_unchanged(self):
        self._assign()
        sheet = deepcopy(self._generate())
        assignments = deepcopy(self.repository.list_assignments(self.dispatch_date))
        self._set_available(False)
        self.assertEqual(sheet, self.service.get_delivery_run_sheet(sheet.run_sheet_id))
        self.assertEqual(assignments, self.repository.list_assignments(self.dispatch_date))
        board = self.service.get_delivery_trip_summary_board(self.dispatch_date)
        self.assertIn("D001", [driver.driver_id for driver in board.drivers])

    def test_saved_open_run_sheet_contents_are_unchanged(self):
        self._assign()
        sheet = deepcopy(self._save(self._generate()))
        self.assertEqual("OPEN", sheet.execution_status)
        self._set_available(False)
        self.assertEqual(sheet, self.service.get_delivery_run_sheet(sheet.run_sheet_id))
        self.assertEqual(sheet, self.service.get_saved_delivery_run_sheet_for_export(sheet.run_sheet_id))
        with self.assertRaisesRegex(ValueError, "Run Sheet history"):
            self.service.delete_delivery_driver("D001")
        board = self.service.get_delivery_trip_summary_board(self.dispatch_date)
        self.assertIn("D001", [driver.driver_id for driver in board.drivers])

    def test_existing_work_can_generate_save_and_close_while_unavailable(self):
        self._assign()
        self._set_available(False)
        sheet = self._save(self._generate())
        self._close(sheet)
        closed = self.service.get_delivery_run_sheet(sheet.run_sheet_id)
        self.assertEqual("CLOSED", closed.execution_status)
        self.assertEqual("FINALIZED", self.repository.get_order("ORD-001").status)
        self.assertFalse(self.repository.get_driver("D001").is_available)

    def test_new_and_reassigned_orders_reject_unavailable_driver(self):
        self._assign("ORD-003", "D002")
        self._set_available(False)
        before = deepcopy(self.repository.list_assignments(self.dispatch_date))
        for scoped in (False, True):
            for order_id in ("ORD-002", "ORD-003"):
                with self.subTest(scoped=scoped, order_id=order_id):
                    with self.assertRaisesRegex(ValueError, "unavailable for new assignments"):
                        self._assign(order_id, scoped=scoped)
                    self.assertEqual(before, self.repository.list_assignments(self.dispatch_date))

    def test_existing_assignee_can_change_trip_while_unavailable(self):
        self._assign()
        self._set_available(False)
        for scoped, trip in ((False, "trip2"), (True, "trip1")):
            self._assign(trip_no=trip, scoped=scoped)
            current = self.repository.get_assignment(self.dispatch_date, "ORDER", "ORD-001")
            self.assertEqual(("D001", trip), (current.driver_id, current.trip_no))

    def test_reenabled_driver_becomes_eligible_for_new_assignments(self):
        self._set_available(False)
        self.assertNotIn("D001", [driver.driver_id for driver in self.repository.list_drivers()])
        self._set_available(True)
        self.assertIn("D001", [driver.driver_id for driver in self.repository.list_drivers()])
        self._assign("ORD-002")
        self.assertEqual("D001", self.repository.get_assignment(
            self.dispatch_date, "ORDER", "ORD-002"
        ).driver_id)

    def test_delete_active_driver_remains_blocked_after_toggle(self):
        self._assign()
        self._set_available(False)
        for delete in (self.service.delete_driver, self.service.delete_delivery_driver):
            with self.assertRaisesRegex(ValueError, "current orders"):
                delete("D001")
        self.assertFalse(self.repository.get_driver("D001").is_deleted)

    def test_delete_driver_with_vehicle_selection_remains_blocked(self):
        self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(
            dispatch_date=self.dispatch_date, driver_id="D001", vehicle_id="V001"
        ))
        self._set_available(False)
        with self.assertRaisesRegex(ValueError, "vehicle selection history"):
            self.service.delete_delivery_driver("D001")
        self.assertFalse(self.repository.get_driver("D001").is_deleted)

    def test_delete_driver_with_generated_sheet_remains_blocked(self):
        self._assign()
        sheet = deepcopy(self._generate())
        for available in (True, False):
            self._set_available(available)
            with self.assertRaisesRegex(ValueError, "Run Sheet history"):
                self.service.delete_delivery_driver("D001")
            self.assertEqual(sheet, self.service.get_delivery_run_sheet(sheet.run_sheet_id))

    def test_delete_driver_with_saved_closed_sheet_preserves_history(self):
        self._assign()
        sheet = self._save(self._generate())
        self._set_available(False)
        self._close(sheet)
        closed = deepcopy(self.service.get_delivery_run_sheet(sheet.run_sheet_id))
        with self.assertRaisesRegex(ValueError, "Run Sheet history"):
            self.service.delete_delivery_driver("D001")
        self.assertEqual(closed, self.service.get_delivery_run_sheet(sheet.run_sheet_id))

    def test_legacy_assignment_history_delete_guard_is_unchanged(self):
        self._set_available(False)
        with patch.object(self.repository, "driver_has_final_summary_history", return_value=True):
            with self.assertRaisesRegex(ValueError, "assignment history"):
                self.service.delete_driver("D001")
        self.assertFalse(self.repository.get_driver("D001").is_deleted)

    def test_vehicle_availability_guard_is_unchanged(self):
        self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(
            dispatch_date=self.dispatch_date, driver_id="D001", vehicle_id="V001"
        ))
        with self.assertRaisesRegex(ValueError, "clear this vehicle"):
            self.service.update_vehicle("V001", UpdateVehicleRequest(is_available=False))
        self.assertTrue(self.repository.get_vehicle("V001").is_available)

    def test_opshop_existing_assignee_is_preserved_and_new_assignments_rejected(self):
        template = self._regular_template()
        pickup = self._pickup(template.schedule_id)
        request = OpShopWorkspaceAssignmentBatchRequest(
            dispatch_date=self.dispatch_date,
            assignments=[{"pickup_task_id": pickup.pickup_task_id, "driver_id": "D001"}],
        )
        self.service.apply_opshop_workspace_assignments(request)
        self._set_available(False)
        self.service.apply_opshop_workspace_assignments(request)
        board = self.service.get_opshop_trip_summary_board(pickup.pickup_date)
        self.assertIn("D001", [driver.driver_id for driver in board.drivers])
        next_pickup = self._pickup(template.schedule_id, "2026-05-12")
        with self.assertRaisesRegex(ValueError, "unavailable for new assignments"):
            self.service.apply_opshop_workspace_assignments(OpShopWorkspaceAssignmentBatchRequest(
                dispatch_date="2026-05-12",
                assignments=[{"pickup_task_id": next_pickup.pickup_task_id, "driver_id": "D001"}],
            ))
        self.assertIsNone(self.repository.get_opshop_pickup_task(next_pickup.pickup_task_id).driver_id)

    def test_legacy_opshop_batch_rejects_new_work_but_keeps_existing_assignee(self):
        template = self._regular_template()
        pickup = self._pickup(template.schedule_id)
        request = ApplyWeeklyOpShopPickupAssignmentsRequest(
            dispatch_date=self.dispatch_date,
            assignments=[{"pickup_task_id": pickup.pickup_task_id, "driver_id": "D001"}],
        )
        self._set_available(False)
        with self.assertRaisesRegex(ValueError, "unavailable for new assignments"):
            self.service.apply_weekly_opshop_pickup_assignments(request)
        self._set_available(True)
        self.service.apply_weekly_opshop_pickup_assignments(request)
        self._set_available(False)
        self.service.apply_weekly_opshop_pickup_assignments(request)
        self.assertEqual("D001", self.repository.get_opshop_pickup_task(pickup.pickup_task_id).driver_id)

    def test_auto_assignment_skips_unavailable_default_without_changing_existing_work(self):
        template = self._regular_template("D001")
        current = self._pickup(template.schedule_id)
        assignment = deepcopy(self.repository.get_assignment(
            current.pickup_date, "OPSHOP_PICKUP", current.pickup_task_id
        ))
        self.assertEqual("D001", current.driver_id)
        self._set_available(False)
        future = self._pickup(template.schedule_id, "2026-05-12")
        self.assertIsNone(future.driver_id)
        self.assertEqual(assignment, self.repository.get_assignment(
            current.pickup_date, "OPSHOP_PICKUP", current.pickup_task_id
        ))
        self._set_available(True)
        future = self._pickup(template.schedule_id, "2026-05-19")
        self.assertEqual("D001", future.driver_id)

class InMemoryDriverAvailabilityTest(DriverAvailabilityBehavior, unittest.TestCase):
    repository_kind = "memory"


class SQLiteDriverAvailabilityTest(DriverAvailabilityBehavior, unittest.TestCase):
    repository_kind = "sqlite"

    def test_delivery_patch_endpoint_allows_toggle_with_work_and_keeps_delete_errors(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        self._assign()
        assignments = deepcopy(self.repository.list_assignments(self.dispatch_date))
        api_module = importlib.import_module("backend.api.manual_dispatch")
        with patch.object(api_module, "service", self.service):
            app = FastAPI()
            app.include_router(api_module.router)
            with TestClient(app) as client:
                login = client.post("/api/manual-dispatch/auth/login", json={
                    "account_name": self.account.account_name,
                    "password": self.password,
                })
                self.assertEqual(200, login.status_code, login.text)
                response = client.patch("/api/manual-dispatch/delivery/drivers/D001", json={
                    "is_available": False,
                })
                self.assertEqual(200, response.status_code, response.text)
                self.assertFalse(response.json()["is_available"])
                self.assertEqual(assignments, self.repository.list_assignments(self.dispatch_date))
                response = client.delete("/api/manual-dispatch/delivery/drivers/D001")
                self.assertEqual(400, response.status_code, response.text)
                self.assertIn("current orders", response.text)
                response = client.post("/api/manual-dispatch/delivery/assignments", json={
                    "dispatch_date": self.dispatch_date,
                    "order_id": "ORD-002", "driver_id": "D001", "trip_no": "trip1",
                })
                self.assertEqual(400, response.status_code, response.text)
                self.assertIn("unavailable", response.text)


if __name__ == "__main__":
    unittest.main()
