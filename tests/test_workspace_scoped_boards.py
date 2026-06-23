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
        ):
            invalid = self.client.get(path, params={"dispatch_date": "2026-02-31"})
            self.assertEqual(400, invalid.status_code)
            self.assertIn("valid YYYY-MM-DD", invalid.json()["detail"])

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
        self.assertIn("ORDER-1", self._delivery_order_ids(cancelled_board))
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

    def test_opshop_snapshots_filter_only_pickups_and_cancel_restores_them(self):
        self._assign_order()
        pickup_id = self._seed_and_assign_oncall_pickup()

        generated = self.service.create_generated_opshop_pickup_collection(
            self._opshop_generate_request()
        )
        generated_board = self.service.get_opshop_workspace_board(self.dispatch_date)
        self.assertNotIn(pickup_id, self._opshop_pickup_ids(generated_board))
        self.assertIn(
            "ORDER-1",
            self._delivery_order_ids(
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
        self.assertIn("ORDER-1", self._delivery_order_ids(delivery_board))
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
        self.assertIn(("GET", "/api/manual-dispatch/opshop/board"), route_pairs)
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

    def _seed_and_assign_oncall_pickup(self):
        pickup_id = "PICKUP-ONCALL"
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
                pickup_date=self.dispatch_date,
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

    def _assign_order(self):
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id="ORDER-1",
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
