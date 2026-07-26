import importlib
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignTaskRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    Driver,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    Order,
    ProductDetailLine,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
    Vehicle,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class WorkspaceScopedBoardsTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-scoped-board-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.dispatch_date = "2026-05-05"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        self.previous_seed_flag = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self._seed_delivery_reference_data()
        self._seed_regular_template()
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Scoped Board Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )

        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        authenticate_test_client(
            self.client,
            self.service,
            getattr(self, "account", None),
        )

    def tearDown(self):
        self.api_module.service = self.original_service
        self._restore_environment("MANUAL_DISPATCH_DB_PATH", self.previous_db_path)
        self._restore_environment(
            "MANUAL_DISPATCH_SEED_DEMO_DATA",
            self.previous_seed_flag,
        )
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scoped_api_contracts_are_domain_only_and_validate_dates(self):
        self._seed_and_assign_oncall_pickup()
        self._assign_order()

        delivery_response = self.client.get(
            "/api/manual-dispatch/delivery/board",
            params={"dispatch_date": self.dispatch_date},
        )
        opshop_response = self.client.get(
            "/api/manual-dispatch/opshop/board",
            params={"dispatch_date": self.dispatch_date},
        )
        shared_response = self.client.get(
            "/api/manual-dispatch/shared/specifications"
        )

        self.assertEqual(200, delivery_response.status_code)
        self.assertEqual(
            {
                "dispatch_date",
                "orders",
                "drivers",
                "vehicles",
                "assignments",
                "driver_vehicle_assignments",
                "saved_vehicle_assignment_locks",
            },
            set(delivery_response.json()),
        )
        self.assertEqual(
            {"ORDER"},
            {item["task_type"] for item in delivery_response.json()["assignments"]},
        )
        self.assertFalse(
            {
                "opshop_pickups",
                "templates",
                "countryside_route_groups",
                "pickup_category",
                "route_group_id",
            }
            & self._nested_keys(delivery_response.json())
        )

        self.assertEqual(200, opshop_response.status_code)
        self.assertEqual(
            {
                "dispatch_date",
                "opshop_pickups",
                "drivers",
                "templates",
                "countryside_route_groups",
            },
            set(opshop_response.json()),
        )
        self.assertFalse(
            {
                "orders",
                "invoice_number",
                "order_no",
                "product_lines",
                "pallet_quantity",
                "loose_bags_quantity",
                "driver_vehicle_assignments",
                "vehicle_id",
                "trip_no",
                "total_pallets",
                "total_loose_bags",
            }
            & self._nested_keys(opshop_response.json())
        )
        self.assertEqual(
            {"drivers", "vehicles"},
            set(shared_response.json()),
        )

        for path in (
            "/api/manual-dispatch/delivery/board",
            "/api/manual-dispatch/opshop/board",
            "/api/manual-dispatch/delivery/trip-summary",
            "/api/manual-dispatch/opshop/trip-summary",
        ):
            if "delivery/trip-summary" in path:
                params = {
                    "dispatch_date": self.dispatch_date,
                    "delivery_date": "2026-02-31",
                }
            elif "opshop/trip-summary" in path:
                params = {
                    "dispatch_date": self.dispatch_date,
                    "pickup_date": "2026-02-31",
                }
            else:
                params = {"dispatch_date": "2026-02-31"}
            invalid = self.client.get(path, params=params)
            self.assertEqual(400, invalid.status_code)
            self.assertIn("valid YYYY-MM-DD", invalid.json()["detail"])

    def test_delivery_trip_summary_board_is_scoped_by_delivery_date(self):
        delivery_date = "2026-05-06"
        self._create_delivery_order("ORDER-2", delivery_date)
        self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=self.dispatch_date,
                order_id="ORDER-2",
                driver_id="DRIVER-1",
                trip_no="trip2",
            )
        )
        self.service.assign_delivery_workspace_vehicle(
            DeliveryWorkspaceVehicleAssignmentRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=delivery_date,
                driver_id="DRIVER-1",
                vehicle_id="VEHICLE-1",
            )
        )

        response = self.client.get(
            "/api/manual-dispatch/delivery/trip-summary",
            params={
                "delivery_date": delivery_date,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()

        self.assertIsNone(payload["dispatch_date"])
        self.assertEqual(delivery_date, payload["delivery_date"])
        self.assertEqual(["ORDER-2"], [order["order_id"] for order in payload["orders"]])
        self.assertEqual(["ORDER-2"], [item["task_id"] for item in payload["assignments"]])
        self.assertEqual(
            [
                {
                    "dispatch_date": self.dispatch_date,
                    "delivery_date": delivery_date,
                    "driver_id": "DRIVER-1",
                    "vehicle_id": "VEHICLE-1",
                }
            ],
            payload["driver_vehicle_assignments"],
        )

        task_pool_response = self.client.get(
            "/api/manual-dispatch/delivery/board",
            params={"dispatch_date": self.dispatch_date},
        )
        self.assertEqual(200, task_pool_response.status_code)
        self.assertIn(
            "ORDER-1",
            {order["order_id"] for order in task_pool_response.json()["orders"]},
        )

    def test_opshop_trip_summary_board_is_scoped_by_pickup_date(self):
        pickup_date = "2026-05-06"
        pickup_id = self._seed_and_assign_oncall_pickup(
            pickup_id="PICKUP-ONCALL-FUTURE",
            pickup_date=pickup_date,
        )

        response = self.client.get(
            "/api/manual-dispatch/opshop/trip-summary",
            params={
                "pickup_date": pickup_date,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()

        self.assertIsNone(payload["dispatch_date"])
        self.assertEqual(pickup_date, payload["pickup_date"])
        self.assertEqual([pickup_id], [pickup["pickup_task_id"] for pickup in payload["opshop_pickups"]])
        self.assertEqual(["DRIVER-1"], [pickup["driver_id"] for pickup in payload["opshop_pickups"]])

    def test_delivery_trip_summary_ignores_legacy_dispatch_date_filter(self):
        delivery_date = "2026-05-06"
        other_dispatch_date = "2026-05-07"
        self._create_delivery_order("ORDER-HIST", delivery_date)
        self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=self.dispatch_date,
                order_id="ORDER-HIST",
                driver_id="DRIVER-1",
                trip_no="trip1",
            )
        )
        self.service.assign_delivery_workspace_vehicle(
            DeliveryWorkspaceVehicleAssignmentRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=delivery_date,
                driver_id="DRIVER-1",
                vehicle_id="VEHICLE-1",
            )
        )

        current_response = self.client.get(
            "/api/manual-dispatch/delivery/trip-summary",
            params={
                "dispatch_date": self.dispatch_date,
                "delivery_date": delivery_date,
            },
        )
        self.assertEqual(200, current_response.status_code)
        current_payload = current_response.json()
        self.assertIsNone(current_payload["dispatch_date"])
        self.assertEqual(
            ["ORDER-HIST"],
            [assignment["task_id"] for assignment in current_payload["assignments"]],
        )
        self.assertEqual(
            [self.dispatch_date],
            [
                assignment["dispatch_date"]
                for assignment in current_payload["driver_vehicle_assignments"]
            ],
        )

        saved = self.service.save_generated_delivery_run_sheet(
            self.service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=delivery_date,
                    driver_id="DRIVER-1",
                )
            ).run_sheet_id,
            self._save_request(),
        )
        other_response = self.client.get(
            "/api/manual-dispatch/delivery/trip-summary",
            params={
                "dispatch_date": other_dispatch_date,
                "delivery_date": delivery_date,
            },
        )
        self.assertEqual(200, other_response.status_code)
        other_payload = other_response.json()
        self.assertIsNone(other_payload["dispatch_date"])
        self.assertEqual([], other_payload["assignments"])
        self.assertEqual(
            [self.dispatch_date],
            [
                assignment["dispatch_date"]
                for assignment in other_payload["driver_vehicle_assignments"]
            ],
        )
        self.assertEqual(1, len(other_payload["saved_vehicle_assignment_locks"]))
        current_locked_response = self.client.get(
            "/api/manual-dispatch/delivery/trip-summary",
            params={
                "dispatch_date": self.dispatch_date,
                "delivery_date": delivery_date,
            },
        )
        self.assertEqual(other_payload, current_locked_response.json())
        self.assertEqual(
            [],
            [
                run_sheet.run_sheet_id
                for run_sheet in self.repository.list_delivery_run_sheets(
                    other_dispatch_date,
                    delivery_date,
                )
            ],
        )
        self.assertEqual(
            [saved.run_sheet_id],
            [
                run_sheet.run_sheet_id
                for run_sheet in self.repository.list_delivery_run_sheets(
                    self.dispatch_date,
                    delivery_date,
                )
            ],
        )

    def test_opshop_trip_summary_ignores_legacy_dispatch_date_filter(self):
        pickup_date = "2026-05-06"
        other_dispatch_date = "2026-05-07"
        pickup_id = self._seed_and_assign_oncall_pickup(
            pickup_id="PICKUP-HIST",
            pickup_date=pickup_date,
        )

        current_response = self.client.get(
            "/api/manual-dispatch/opshop/trip-summary",
            params={
                "dispatch_date": self.dispatch_date,
                "pickup_date": pickup_date,
            },
        )
        self.assertEqual(200, current_response.status_code)
        current_payload = current_response.json()
        self.assertIsNone(current_payload["dispatch_date"])
        self.assertEqual(
            [pickup_id],
            [pickup["pickup_task_id"] for pickup in current_payload["opshop_pickups"]],
        )

        other_response = self.client.get(
            "/api/manual-dispatch/opshop/trip-summary",
            params={
                "dispatch_date": other_dispatch_date,
                "pickup_date": pickup_date,
            },
        )
        self.assertEqual(200, other_response.status_code)
        self.assertIsNone(other_response.json()["dispatch_date"])
        self.assertEqual(current_payload, other_response.json())

        unassign = self.client.post(
            "/api/manual-dispatch/opshop/pickups/assignments/unassign",
            json={
                "dispatch_date": other_dispatch_date,
                "pickup_task_id": pickup_id,
            },
        )
        self.assertEqual(200, unassign.status_code)
        task = self.repository.get_opshop_pickup_task(pickup_id)
        self.assertEqual("ACTIVE", task.status)
        self.assertIsNone(task.driver_id)
        self.assertIsNone(
            self.repository.find_assignment_for_task("OPSHOP_PICKUP", pickup_id)
        )

        task_pool_response = self.client.get(
            "/api/manual-dispatch/opshop/board",
            params={"dispatch_date": self.dispatch_date},
        )
        self.assertEqual(200, task_pool_response.status_code)
        self.assertIn(
            pickup_id,
            {
                pickup["pickup_task_id"]
                for pickup in task_pool_response.json()["opshop_pickups"]
            },
        )

    def test_delivery_and_shared_boards_do_not_ensure_regular_pickups(self):
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

        with patch.object(
            self.service.opshop_pickup_service,
            "ensure_regular_opshop_pickup_tasks_for_week",
            side_effect=AssertionError("Delivery/shared route called Regular ensure"),
        ):
            delivery = self.service.get_delivery_workspace_board(self.dispatch_date)
            shared = self.service.get_shared_specifications()

        self.assertEqual(["ORDER-1"], [order.order_id for order in delivery.orders])
        self.assertEqual(["DRIVER-1"], [driver.driver_id for driver in shared.drivers])
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_opshop_board_ensures_regular_tasks_idempotently(self):
        first = self.service.get_opshop_workspace_board(self.dispatch_date)
        first_regular_ids = {
            pickup.pickup_task_id
            for pickup in first.opshop_pickups
            if pickup.run_type == "REGULAR"
        }
        second = self.service.get_opshop_workspace_board(self.dispatch_date)
        second_regular_ids = {
            pickup.pickup_task_id
            for pickup in second.opshop_pickups
            if pickup.run_type == "REGULAR"
        }

        self.assertEqual(1, len(first_regular_ids))
        self.assertEqual(first_regular_ids, second_regular_ids)
        self.assertEqual(1, len(self.repository.list_opshop_pickup_tasks()))

    def test_opshop_board_serializes_regular_last_pickup_date_or_null(self):
        history_date = "2026-04-28"
        history_task_id = "PICKUP-REGULAR-HISTORY"
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=history_task_id,
                schedule_id="SCHEDULE-REGULAR",
                opshop_id="OPSHOP-REGULAR",
                pickup_date=history_date,
                task_type="OPSHOP_PICKUP",
                generated_from="REGULAR",
                status="ACTIVE",
                dispatch_date=history_date,
                driver_id=None,
                trip_no=None,
                notes="Synthetic saved history",
                created_at="2026-04-28T00:00:00+00:00",
                updated_at="2026-04-28T00:00:00+00:00",
            )
        )
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=history_date,
                task_type="OPSHOP_PICKUP",
                task_id=history_task_id,
                driver_id="DRIVER-1",
                trip_no="trip1",
            )
        )
        generated = self.service.create_generated_opshop_pickup_collection(
            GenerateOpShopPickupCollectionRequest(
                dispatch_date=history_date,
                pickup_date=history_date,
                driver_id="DRIVER-1",
            )
        )
        self.service.save_generated_opshop_pickup_collection(
            generated.collection_id,
            self._save_request(),
        )

        no_history_opshop_id = "OPSHOP-REGULAR-NO-HISTORY"
        self.repository.upsert_opshop_location(
            self._location(no_history_opshop_id, "Regular No History")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHEDULE-REGULAR-NO-HISTORY",
                no_history_opshop_id,
                run_type="REGULAR",
                run_day="TUESDAY",
            )
        )

        response = self.client.get(
            "/api/manual-dispatch/opshop/board",
            params={"dispatch_date": self.dispatch_date},
        )

        self.assertEqual(200, response.status_code)
        regular_by_opshop_id = {
            pickup["opshop_id"]: pickup
            for pickup in response.json()["opshop_pickups"]
            if pickup["run_type"] == "REGULAR"
            and pickup["pickup_date"] == self.dispatch_date
        }
        self.assertEqual(
            history_date,
            regular_by_opshop_id["OPSHOP-REGULAR"]["last_pickup_date"],
        )
        self.assertIsNone(
            regular_by_opshop_id[no_history_opshop_id]["last_pickup_date"]
        )

    def test_delivery_snapshots_filter_only_orders_and_saved_lock_is_scoped(self):
        self._assign_order()
        pickup_id = self._seed_and_assign_oncall_pickup()

        generated = self.service.create_generated_delivery_run_sheet(
            self._delivery_generate_request()
        )
        generated_board = self.service.get_delivery_workspace_board(self.dispatch_date)
        self.assertNotIn("ORDER-1", self._delivery_order_ids(generated_board))
        self.assertNotIn("ORDER-1", self._delivery_assignment_ids(generated_board))
        self.assertEqual([], generated_board.saved_vehicle_assignment_locks)
        self.assertIn(
            pickup_id,
            self._opshop_pickup_ids(
                self.service.get_opshop_workspace_board(self.dispatch_date)
            ),
        )

        self.assertTrue(
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        )
        cancelled_board = self.service.get_delivery_workspace_board(self.dispatch_date)
        self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(cancelled_board))
        self.assertIn("ORDER-1", self._delivery_assignment_ids(cancelled_board))

        saved = self.service.save_generated_delivery_run_sheet(
            self.service.create_generated_delivery_run_sheet(
                self._delivery_generate_request()
            ).run_sheet_id,
            self._save_request(),
        )
        saved_board = self.service.get_delivery_workspace_board(self.dispatch_date)
        self.assertNotIn("ORDER-1", self._delivery_order_ids(saved_board))
        self.assertNotIn("ORDER-1", self._delivery_assignment_ids(saved_board))
        self.assertEqual(
            [
                {
                    "dispatch_date": self.dispatch_date,
                    "delivery_date": self.dispatch_date,
                    "driver_id": "DRIVER-1",
                    "run_sheet_id": saved.run_sheet_id,
                }
            ],
            [to_dict(lock) for lock in saved_board.saved_vehicle_assignment_locks],
        )
        self.assertIn(
            pickup_id,
            self._opshop_pickup_ids(
                self.service.get_opshop_workspace_board(self.dispatch_date)
            ),
        )

    def test_delivery_run_sheet_reserves_orders_across_dispatch_dates(self):
        other_dispatch_date = "2026-05-06"
        self._create_delivery_order("ORDER-2", self.dispatch_date)
        self._create_delivery_order("ORDER-UNRELATED", other_dispatch_date)
        self._assign_order("ORDER-1")
        self._assign_order("ORDER-2")
        original_assignments = [
            to_dict(assignment)
            for assignment in self.repository.list_assignments(self.dispatch_date)
        ]

        generated = self.service.create_generated_delivery_run_sheet(
            self._delivery_generate_request()
        )
        other_board = self.service.get_delivery_workspace_board(other_dispatch_date)
        other_board_response = self.client.get(
            "/api/manual-dispatch/delivery/board",
            params={"dispatch_date": other_dispatch_date},
        )
        self.assertEqual(200, other_board_response.status_code)
        api_payload = other_board_response.json()
        api_task_pool_order_ids = {
            order["order_id"] for order in other_board_response.json()["orders"]
        } - {assignment["task_id"] for assignment in api_payload["assignments"]}

        self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(other_board))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(other_board))
        self.assertNotIn("ORDER-1", api_task_pool_order_ids)
        self.assertNotIn("ORDER-2", api_task_pool_order_ids)
        self.assertIn("ORDER-UNRELATED", api_task_pool_order_ids)
        self.assertNotIn("ORDER-1", self._delivery_assignment_ids(other_board))
        self.assertNotIn("ORDER-2", self._delivery_assignment_ids(other_board))
        self.assertIn("ORDER-UNRELATED", self._delivery_task_pool_order_ids(other_board))
        self.assertEqual(
            original_assignments,
            [
                to_dict(assignment)
                for assignment in self.repository.list_assignments(self.dispatch_date)
            ],
        )
        with self.assertRaisesRegex(ValueError, "already been generated"):
            self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=other_dispatch_date,
                    order_id="ORDER-1",
                    driver_id="DRIVER-1",
                    trip_no="trip1",
                )
            )

        self.assertTrue(
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        )
        released_board = self.service.get_delivery_workspace_board(other_dispatch_date)
        original_after_cancel = self.service.get_delivery_workspace_board(
            self.dispatch_date
        )
        self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(released_board))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(released_board))
        self.assertIn("ORDER-UNRELATED", self._delivery_task_pool_order_ids(released_board))
        self.assertIn("ORDER-1", self._delivery_assignment_ids(original_after_cancel))
        self.assertIn("ORDER-2", self._delivery_assignment_ids(original_after_cancel))

        self.service.unassign_delivery_workspace_order(
            DeliveryWorkspaceUnassignOrderRequest(
                dispatch_date=self.dispatch_date,
                order_id="ORDER-1",
            )
        )
        after_unassign_other = self.service.get_delivery_workspace_board(
            other_dispatch_date
        )
        self.assertIn("ORDER-1", self._delivery_task_pool_order_ids(after_unassign_other))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(after_unassign_other))
        self._assign_order("ORDER-1")

        saved = self.service.save_generated_delivery_run_sheet(
            self.service.create_generated_delivery_run_sheet(
                self._delivery_generate_request()
            ).run_sheet_id,
            self._save_request(),
        )
        saved_other_board = self.service.get_delivery_workspace_board(
            other_dispatch_date
        )
        saved_original_board = self.service.get_delivery_workspace_board(
            self.dispatch_date
        )
        self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(saved_other_board))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(saved_other_board))
        self.assertIn("ORDER-UNRELATED", self._delivery_task_pool_order_ids(saved_other_board))
        self.assertEqual([], saved_other_board.saved_vehicle_assignment_locks)
        self.assertEqual(
            [saved.run_sheet_id],
            [
                lock.run_sheet_id
                for lock in saved_original_board.saved_vehicle_assignment_locks
            ],
        )
        with self.assertRaisesRegex(ValueError, "already been saved"):
            self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=other_dispatch_date,
                    order_id="ORDER-2",
                    driver_id="DRIVER-1",
                    trip_no="trip1",
                )
            )

    def test_manual_assignment_is_global_and_reassigns_without_duplicates(self):
        other_dispatch_date = "2026-05-06"
        third_dispatch_date = "2026-05-08"
        self._create_delivery_order("ORDER-2", self.dispatch_date)
        self._create_delivery_order("ORDER-UNRELATED", other_dispatch_date)
        self._assign_order("ORDER-1")
        self._assign_order("ORDER-2")

        for dispatch_date in (other_dispatch_date, third_dispatch_date):
            board = self.service.get_delivery_workspace_board(dispatch_date)
            self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(board))
            self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(board))
            self.assertIn("ORDER-UNRELATED", self._delivery_task_pool_order_ids(board))

        original_board = self.service.get_delivery_workspace_board(self.dispatch_date)
        self.assertIn("ORDER-1", self._delivery_assignment_ids(original_board))
        self.assertIn("ORDER-2", self._delivery_assignment_ids(original_board))
        self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=other_dispatch_date,
                order_id="ORDER-1",
                driver_id="DRIVER-1",
                trip_no="trip2",
            )
        )
        assignment = self.repository.find_assignment_for_task("ORDER", "ORDER-1")
        self.assertEqual(self.dispatch_date, assignment.dispatch_date)
        self.assertEqual("DRIVER-1", assignment.driver_id)
        self.assertEqual("trip2", assignment.trip_no)
        self.assertEqual(
            1,
            len(
                self.repository.list_assignments_for_task(
                    "ORDER",
                    "ORDER-1",
                )
            ),
        )

        self.service.unassign_delivery_workspace_order(
            DeliveryWorkspaceUnassignOrderRequest(
                dispatch_date=other_dispatch_date,
                order_id="ORDER-1",
            )
        )
        self.assertIsNone(
            self.repository.find_assignment_for_task("ORDER", "ORDER-1")
        )

        released_other = self.service.get_delivery_workspace_board(other_dispatch_date)
        released_original = self.service.get_delivery_workspace_board(
            self.dispatch_date
        )
        self.assertIn("ORDER-1", self._delivery_task_pool_order_ids(released_other))
        self.assertIn("ORDER-1", self._delivery_task_pool_order_ids(released_original))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(released_other))
        self.assertNotIn("ORDER-2", self._delivery_task_pool_order_ids(released_original))
        self.assertIn("ORDER-UNRELATED", self._delivery_task_pool_order_ids(released_other))

    def test_opshop_snapshots_filter_only_pickups_and_cancel_restores_them(self):
        self._assign_order()
        pickup_id = self._seed_and_assign_oncall_pickup()

        generated = self.service.create_generated_opshop_pickup_collection(
            self._opshop_generate_request()
        )
        generated_board = self.service.get_opshop_workspace_board(self.dispatch_date)
        self.assertNotIn(pickup_id, self._opshop_pickup_ids(generated_board))
        self.assertNotIn(
            "ORDER-1",
            self._delivery_task_pool_order_ids(
                self.service.get_delivery_workspace_board(self.dispatch_date)
            ),
        )

        self.assertTrue(
            self.service.cancel_generated_opshop_pickup_collection(
                generated.collection_id
            )
        )
        cancelled_board = self.service.get_opshop_workspace_board(self.dispatch_date)
        self.assertIn(pickup_id, self._opshop_pickup_ids(cancelled_board))

        self.service.save_generated_opshop_pickup_collection(
            self.service.create_generated_opshop_pickup_collection(
                self._opshop_generate_request()
            ).collection_id,
            self._save_request(),
        )
        saved_board = self.service.get_opshop_workspace_board(self.dispatch_date)
        self.assertNotIn(pickup_id, self._opshop_pickup_ids(saved_board))
        delivery_board = self.service.get_delivery_workspace_board(self.dispatch_date)
        self.assertNotIn("ORDER-1", self._delivery_task_pool_order_ids(delivery_board))
        self.assertIn("ORDER-1", self._delivery_assignment_ids(delivery_board))

    def test_legacy_board_routes_and_service_boundaries_remain_intact(self):
        legacy_board = self.service.get_board(self.dispatch_date)
        self.assertTrue(hasattr(legacy_board, "scheduled_opshop_pickups"))
        self.assertTrue(hasattr(legacy_board, "oncall_opshop_pickups"))
        self.assertTrue(hasattr(legacy_board, "orders"))

        route_pairs = {
            (method, route.path)
            for route in self.api_module.router.routes
            for method in route.methods
        }
        self.assertIn(("GET", "/api/manual-dispatch/board"), route_pairs)
        self.assertIn(("POST", "/api/manual-dispatch/final-summaries"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/delivery/board"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/delivery/trip-summary"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/opshop/board"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/opshop/trip-summary"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/shared/specifications"), route_pairs)

        delivery_source = Path(
            "backend/services/manual_dispatch/delivery_workspace_board_service.py"
        ).read_text(encoding="utf-8")
        opshop_source = Path(
            "backend/services/manual_dispatch/opshop_workspace_board_service.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "board_service.get_board",
            "list_final_trip_summaries",
            "ensure_regular_opshop",
            "list_opshop",
        ):
            self.assertNotIn(forbidden, delivery_source)
        for forbidden in (
            "board_service.get_board",
            "list_final_trip_summaries",
            "list_orders(",
            "list_driver_vehicle_assignments",
            "list_delivery_run_sheets",
        ):
            self.assertNotIn(forbidden, opshop_source)

    def _seed_delivery_reference_data(self):
        self.repository.create_driver(
            Driver(
                driver_id="DRIVER-1",
                name="Test Driver",
                start_time="07:00",
                end_time="15:00",
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
            )
        )
        self.repository.create_vehicle(
            Vehicle(
                vehicle_id="VEHICLE-1",
                rego="TEST01",
                type="Truck",
                is_available=True,
                pallet_capacity=12,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            )
        )
        self.repository.create_order(
            Order(
                order_id="ORDER-1",
                invoice_number="INV-1",
                order_no="ORDER-NO-1",
                company_name="Delivery Customer",
                phone="03 9000 0000",
                delivery_address="1 Delivery Street",
                suburb="DANDENONG",
                postcode="3175",
                delivery_date=self.dispatch_date,
                zone="SOUTH EAST",
                urgency="Normal",
                preferred_driver_id=None,
                pallet_quantity=2,
                loose_bags_quantity=3,
                start_time="09:00",
                end_time="12:00",
                note="Delivery note",
                status="ACTIVE",
                product_lines=[
                    ProductDetailLine(
                        product_name="Rags",
                        quantity=2,
                        unit="PALLETS",
                    )
                ],
            )
        )

    def _seed_regular_template(self):
        self.repository.upsert_opshop_location(
            self._location("OPSHOP-REGULAR", "Regular OP SHOP")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHEDULE-REGULAR",
                "OPSHOP-REGULAR",
                run_type="REGULAR",
                run_day="TUESDAY",
            )
        )

    def _seed_and_assign_oncall_pickup(
        self,
        pickup_id="PICKUP-ONCALL",
        pickup_date=None,
    ):
        pickup_date = pickup_date or self.dispatch_date
        self.repository.upsert_opshop_location(
            self._location("OPSHOP-ONCALL", "Oncall OP SHOP")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(
                "SCHEDULE-ONCALL",
                "OPSHOP-ONCALL",
                run_type="ON_CALL",
                run_day=None,
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=pickup_id,
                schedule_id="SCHEDULE-ONCALL",
                opshop_id="OPSHOP-ONCALL",
                pickup_date=pickup_date,
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date=self.dispatch_date,
                driver_id=None,
                trip_no=None,
                notes="Pickup note",
                created_at="2026-05-01T00:00:00+00:00",
                updated_at="2026-05-01T00:00:00+00:00",
            )
        )
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                task_id=pickup_id,
                driver_id="DRIVER-1",
                trip_no="trip1",
            )
        )
        return pickup_id

    def _create_delivery_order(self, order_id, delivery_date):
        self.repository.create_order(
            Order(
                order_id=order_id,
                invoice_number=f"INV-{order_id}",
                order_no=f"ORDER-NO-{order_id}",
                company_name=f"Delivery Customer {order_id}",
                phone="03 9000 0000",
                delivery_address="2 Delivery Street",
                suburb="DANDENONG",
                postcode="3175",
                delivery_date=delivery_date,
                zone="SOUTH EAST",
                urgency="Normal",
                preferred_driver_id=None,
                pallet_quantity=1,
                loose_bags_quantity=0,
                start_time="10:00",
                end_time="13:00",
                note="Delivery note",
                status="ACTIVE",
                product_lines=[
                    ProductDetailLine(
                        product_name="Rags",
                        quantity=1,
                        unit="PALLETS",
                    )
                ],
            )
        )

    def _assign_order(self, order_id="ORDER-1"):
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id=order_id,
                driver_id="DRIVER-1",
                trip_no="trip1",
            )
        )

    def _delivery_generate_request(self):
        return GenerateDeliveryRunSheetRequest(
            dispatch_date=self.dispatch_date,
            delivery_date=self.dispatch_date,
            driver_id="DRIVER-1",
        )

    def _opshop_generate_request(self):
        return GenerateOpShopPickupCollectionRequest(
            dispatch_date=self.dispatch_date,
            pickup_date=self.dispatch_date,
            driver_id="DRIVER-1",
        )

    def _save_request(self):
        return SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
        )

    @staticmethod
    def _location(opshop_id, name):
        return OpShopLocation(
            opshop_id=opshop_id,
            name=name,
            suburb="COBURG",
            street_address="1 Sydney Road",
            area_region="NORTH",
            primary_contact="Mary",
            primary_phone="0400 000 001",
            secondary_contact="John",
            secondary_phone="0400 000 002",
            access_type="Rear dock",
            key_required=True,
            trailer_restriction="Small truck only",
            status_notes="Ring first",
            is_active=True,
            created_at="2026-05-01T00:00:00+00:00",
            updated_at="2026-05-01T00:00:00+00:00",
        )

    @staticmethod
    def _schedule(schedule_id, opshop_id, *, run_type, run_day):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id=opshop_id,
            run_day=run_day,
            run_type=run_type,
            pickup_frequency="Weekly",
            time_window="09:00-12:00",
            call_before_arrival=True,
            call_timing="30 minutes",
            status="Active",
            active_flag=True,
            fortnight_group=None,
            review_required=False,
            review_reason=None,
            created_at="2026-05-01T00:00:00+00:00",
            updated_at="2026-05-01T00:00:00+00:00",
        )

    @staticmethod
    def _delivery_order_ids(board):
        return {order.order_id for order in board.orders}

    @staticmethod
    def _delivery_task_pool_order_ids(board):
        assigned_order_ids = {assignment.task_id for assignment in board.assignments}
        return {order.order_id for order in board.orders} - assigned_order_ids

    @staticmethod
    def _delivery_assignment_ids(board):
        return {assignment.task_id for assignment in board.assignments}

    @staticmethod
    def _opshop_pickup_ids(board):
        return {pickup.pickup_task_id for pickup in board.opshop_pickups}

    @classmethod
    def _nested_keys(cls, value):
        if isinstance(value, dict):
            keys = set(value)
            for item in value.values():
                keys.update(cls._nested_keys(item))
            return keys
        if isinstance(value, list):
            keys = set()
            for item in value:
                keys.update(cls._nested_keys(item))
            return keys
        return set()

    @staticmethod
    def _restore_environment(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
