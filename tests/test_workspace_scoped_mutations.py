import importlib
import os
import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignCountrysideRouteGroupRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    DeliveryWorkspaceVehicleClearRequest,
    Driver,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    OpShopWorkspaceAssignmentBatchRequest,
    OpShopWorkspaceUnassignPickupRequest,
    Order,
    ProductDetailLine,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
    Vehicle,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class WorkspaceScopedMutationsTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-mutations-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.dispatch_date = "2026-06-16"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        self.previous_seed_flag = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self._seed_reference_data()
        self._seed_order("ORDER-1")
        self._seed_order("ORDER-2")
        self._seed_order("ORDER-CANCELLED", status="CANCELLED")
        self._seed_pickup("PICKUP-1")
        self._seed_pickup("PICKUP-2")
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Scoped Mutation Tester",
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

    def test_scoped_routes_enforce_domain_contracts_and_return_scoped_boards(self):
        delivery = self.client.post(
            "/api/manual-dispatch/delivery/assignments",
            json={
                "dispatch_date": self.dispatch_date,
                "order_id": "ORDER-1",
                "driver_id": "DRIVER-1",
                "trip_no": "trip1",
            },
        )
        self.assertEqual(200, delivery.status_code)
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
            set(delivery.json()),
        )
        self.assertEqual(
            {"ORDER"},
            {item["task_type"] for item in delivery.json()["assignments"]},
        )

        invalid_trip = self.client.post(
            "/api/manual-dispatch/delivery/assignments",
            json={
                "dispatch_date": self.dispatch_date,
                "order_id": "ORDER-2",
                "driver_id": "DRIVER-1",
                "trip_no": "trip3",
            },
        )
        arbitrary_type = self.client.post(
            "/api/manual-dispatch/delivery/assignments",
            json={
                "dispatch_date": self.dispatch_date,
                "order_id": "ORDER-2",
                "driver_id": "DRIVER-1",
                "trip_no": "trip1",
                "task_type": "OPSHOP_PICKUP",
            },
        )
        pickup_as_order = self.client.post(
            "/api/manual-dispatch/delivery/assignments",
            json={
                "dispatch_date": self.dispatch_date,
                "order_id": "PICKUP-1",
                "driver_id": "DRIVER-1",
                "trip_no": "trip1",
            },
        )
        cancelled_order = self.client.post(
            "/api/manual-dispatch/delivery/assignments",
            json={
                "dispatch_date": self.dispatch_date,
                "order_id": "ORDER-CANCELLED",
                "driver_id": "DRIVER-1",
                "trip_no": "trip1",
            },
        )
        self.assertEqual(400, invalid_trip.status_code)
        self.assertEqual("Invalid trip_no: trip3", invalid_trip.json()["detail"])
        self.assertEqual(400, arbitrary_type.status_code)
        self.assertEqual(404, pickup_as_order.status_code)
        self.assertEqual(404, cancelled_order.status_code)

        opshop = self.client.post(
            "/api/manual-dispatch/opshop/pickups/assignments/apply",
            json={
                "dispatch_date": self.dispatch_date,
                "assignments": [
                    {"pickup_task_id": "PICKUP-1", "driver_id": "DRIVER-1"}
                ],
            },
        )
        self.assertEqual(200, opshop.status_code)
        self.assertEqual(
            {
                "dispatch_date",
                "opshop_pickups",
                "drivers",
                "templates",
                "countryside_route_groups",
            },
            set(opshop.json()),
        )
        self.assertNotIn("trip_no", self._nested_keys(opshop.json()))
        assignment = self.repository.get_assignment(
            self.dispatch_date,
            "OPSHOP_PICKUP",
            "PICKUP-1",
        )
        self.assertEqual("trip1", assignment.trip_no)

        for forbidden_payload in (
            {"task_type": "ORDER"},
            {"trip_no": "trip1"},
        ):
            response = self.client.post(
                "/api/manual-dispatch/opshop/pickups/assignments/apply",
                json={
                    "dispatch_date": self.dispatch_date,
                    "assignments": [
                        {
                            "pickup_task_id": "PICKUP-2",
                            "driver_id": "DRIVER-1",
                            **forbidden_payload,
                        }
                    ],
                },
            )
            self.assertEqual(400, response.status_code)
        order_as_pickup = self.client.post(
            "/api/manual-dispatch/opshop/pickups/assignments/apply",
            json={
                "dispatch_date": self.dispatch_date,
                "assignments": [
                    {"pickup_task_id": "ORDER-2", "driver_id": "DRIVER-1"}
                ],
            },
        )
        self.assertEqual(404, order_as_pickup.status_code)

    def test_generated_delivery_reserves_captured_target_and_vehicle_mutations(self):
        self._assign_order("ORDER-1", "DRIVER-1")
        self._assign_vehicle("DRIVER-1", "VEHICLE-1")
        generated = self._generate_delivery("DRIVER-1")

        blocked_actions = (
            lambda: self._assign_order("ORDER-1", "DRIVER-2"),
            lambda: self.service.unassign_delivery_workspace_order(
                DeliveryWorkspaceUnassignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORDER-1",
                )
            ),
            lambda: self._assign_order("ORDER-2", "DRIVER-1"),
            lambda: self._assign_vehicle("DRIVER-1", "VEHICLE-2"),
            lambda: self.service.clear_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleClearRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="DRIVER-1",
                )
            ),
        )
        for action in blocked_actions:
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError,
                "generated.*Cancel",
            ):
                action()

        self.assertTrue(
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        )
        self._assign_order("ORDER-2", "DRIVER-1")
        self.assertIsNotNone(
            self.repository.get_assignment(self.dispatch_date, "ORDER", "ORDER-2")
        )

    def test_saved_delivery_reserves_captured_target_and_vehicle_mutations(self):
        self._assign_order("ORDER-1", "DRIVER-1")
        self._assign_vehicle("DRIVER-1", "VEHICLE-1")
        self._save_delivery(self._generate_delivery("DRIVER-1"))

        blocked_actions = (
            lambda: self._assign_order("ORDER-1", "DRIVER-2"),
            lambda: self.service.unassign_delivery_workspace_order(
                DeliveryWorkspaceUnassignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORDER-1",
                )
            ),
            lambda: self._assign_order("ORDER-2", "DRIVER-1"),
            lambda: self._assign_vehicle("DRIVER-1", "VEHICLE-2"),
            lambda: self.service.clear_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleClearRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="DRIVER-1",
                )
            ),
        )
        for action in blocked_actions:
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError,
                "saved",
            ):
                action()

    def test_generated_opshop_collection_reserves_captured_and_target_pickups(self):
        self._assign_pickup("PICKUP-1", "DRIVER-1")
        generated = self._generate_opshop("DRIVER-1")

        blocked_actions = (
            lambda: self._assign_pickup("PICKUP-1", "DRIVER-2"),
            lambda: self.service.unassign_opshop_workspace_pickup(
                OpShopWorkspaceUnassignPickupRequest(
                    dispatch_date=self.dispatch_date,
                    pickup_task_id="PICKUP-1",
                )
            ),
            lambda: self._assign_pickup("PICKUP-2", "DRIVER-1"),
        )
        for action in blocked_actions:
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError,
                "generated.*Cancel",
            ):
                action()

        self.assertTrue(
            self.service.cancel_generated_opshop_pickup_collection(
                generated.collection_id
            )
        )
        self._assign_pickup("PICKUP-2", "DRIVER-1")
        self.assertIsNotNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "OPSHOP_PICKUP",
                "PICKUP-2",
            )
        )

    def test_saved_opshop_collection_reserves_captured_and_target_pickups(self):
        self._assign_pickup("PICKUP-1", "DRIVER-1")
        self._save_opshop(self._generate_opshop("DRIVER-1"))

        blocked_actions = (
            lambda: self._assign_pickup("PICKUP-1", "DRIVER-2"),
            lambda: self.service.unassign_opshop_workspace_pickup(
                OpShopWorkspaceUnassignPickupRequest(
                    dispatch_date=self.dispatch_date,
                    pickup_task_id="PICKUP-1",
                )
            ),
            lambda: self._assign_pickup("PICKUP-2", "DRIVER-1"),
        )
        for action in blocked_actions:
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError,
                "saved",
            ):
                action()

    def test_opshop_batch_preflight_rejects_all_rows_without_partial_writes(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date=self.dispatch_date,
                    assignments=[
                        {
                            "pickup_task_id": "PICKUP-1",
                            "driver_id": "DRIVER-1",
                        },
                        {
                            "pickup_task_id": "ORDER-1",
                            "driver_id": "DRIVER-1",
                        },
                    ],
                )
            )

        self.assertIsNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "OPSHOP_PICKUP",
                "PICKUP-1",
            )
        )
        self.assertEqual("ACTIVE", self.repository.get_opshop_pickup_task("PICKUP-1").status)

    def test_route_group_assignment_is_atomic_when_one_membership_is_reserved(self):
        self._seed_route_group()
        self._seed_pickup_task(
            "ROUTE-PICKUP-1",
            "ROUTE-SCHEDULE-1",
            "ROUTE-OPSHOP-1",
        )
        self._assign_pickup("ROUTE-PICKUP-1", "DRIVER-1")
        self._generate_opshop("DRIVER-1")

        with self.assertRaisesRegex(ValueError, "generated"):
            self.service.assign_opshop_workspace_countryside_route_group(
                "ROUTE-GROUP-1",
                AssignCountrysideRouteGroupRequest(
                    dispatch_date=self.dispatch_date,
                    pickup_date=self.dispatch_date,
                    assigned_driver_id="DRIVER-2",
                    notes="Route assignment",
                ),
            )

        original = self.repository.get_assignment(
            self.dispatch_date,
            "OPSHOP_PICKUP",
            "ROUTE-PICKUP-1",
        )
        self.assertEqual("DRIVER-1", original.driver_id)
        self.assertIsNone(
            self.repository.find_opshop_pickup_task_by_schedule_and_date(
                "ROUTE-SCHEDULE-2",
                self.dispatch_date,
            )
        )

    def test_saved_delivery_does_not_block_opshop_assignment(self):
        self._assign_order("ORDER-1", "DRIVER-1")
        self._save_delivery(self._generate_delivery("DRIVER-1"))

        board = self._assign_pickup("PICKUP-1", "DRIVER-1")
        self.assertIn("PICKUP-1", {item.pickup_task_id for item in board.opshop_pickups})
        self.assertIsNotNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "OPSHOP_PICKUP",
                "PICKUP-1",
            )
        )

    def test_saved_opshop_does_not_block_delivery_or_vehicle_assignment(self):
        self._assign_pickup("PICKUP-1", "DRIVER-1")
        self._save_opshop(self._generate_opshop("DRIVER-1"))

        delivery_board = self._assign_order("ORDER-1", "DRIVER-1")
        vehicle_board = self._assign_vehicle("DRIVER-1", "VEHICLE-1")
        self.assertIn("ORDER-1", {item.task_id for item in delivery_board.assignments})
        self.assertIn(
            "VEHICLE-1",
            {item.vehicle_id for item in vehicle_board.driver_vehicle_assignments},
        )

    def test_scoped_mutation_services_do_not_reference_legacy_or_other_module_locks(self):
        delivery_source = Path(
            "backend/services/manual_dispatch/delivery_workspace_mutation_service.py"
        ).read_text(encoding="utf-8")
        opshop_source = Path(
            "backend/services/manual_dispatch/opshop_workspace_mutation_service.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "final_summary_lock",
            "has_saved_final_trip_summary",
            "opshop_pickup_collection",
        ):
            self.assertNotIn(forbidden, delivery_source)
        for forbidden in (
            "final_summary_lock",
            "has_saved_final_trip_summary",
            "delivery_run_sheet",
            "driver_vehicle_assignment",
        ):
            self.assertNotIn(forbidden, opshop_source)

    def _assign_order(self, order_id, driver_id):
        return self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=self.dispatch_date,
                order_id=order_id,
                driver_id=driver_id,
                trip_no="trip1",
            )
        )

    def _assign_vehicle(self, driver_id, vehicle_id):
        return self.service.assign_delivery_workspace_vehicle(
            DeliveryWorkspaceVehicleAssignmentRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
            )
        )

    def _assign_pickup(self, pickup_task_id, driver_id):
        return self.service.apply_opshop_workspace_assignments(
            OpShopWorkspaceAssignmentBatchRequest(
                dispatch_date=self.dispatch_date,
                assignments=[
                    {"pickup_task_id": pickup_task_id, "driver_id": driver_id}
                ],
            )
        )

    def _generate_delivery(self, driver_id):
        return self.service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id=driver_id,
            )
        )

    def _generate_opshop(self, driver_id):
        return self.service.create_generated_opshop_pickup_collection(
            GenerateOpShopPickupCollectionRequest(
                dispatch_date=self.dispatch_date,
                pickup_date=self.dispatch_date,
                driver_id=driver_id,
            )
        )

    def _save_delivery(self, run_sheet):
        return self.service.save_generated_delivery_run_sheet(
            run_sheet.run_sheet_id,
            self._save_request(),
        )

    def _save_opshop(self, collection):
        return self.service.save_generated_opshop_pickup_collection(
            collection.collection_id,
            self._save_request(),
        )

    def _save_request(self):
        return SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
        )

    def _seed_reference_data(self):
        for number in (1, 2):
            self.repository.create_driver(
                Driver(
                    driver_id=f"DRIVER-{number}",
                    name=f"Driver {number}",
                    start_time="07:00",
                    end_time="15:00",
                    is_available=True,
                    preferred_zone=None,
                    pallet_only=False,
                )
            )
            self.repository.create_vehicle(
                Vehicle(
                    vehicle_id=f"VEHICLE-{number}",
                    rego=f"TEST0{number}",
                    type="Truck",
                    is_available=True,
                    pallet_capacity=12,
                    tub_capacity=0,
                    trolley_capacity=0,
                    stillage_capacity=0,
                )
            )

    def _seed_order(self, order_id, status="ACTIVE"):
        self.repository.create_order(
            Order(
                order_id=order_id,
                invoice_number=f"INV-{order_id}",
                order_no=f"NO-{order_id}",
                company_name=f"Customer {order_id}",
                phone="03 9000 0000",
                delivery_address="1 Delivery Street",
                suburb="DANDENONG",
                postcode="3175",
                delivery_date=self.dispatch_date,
                zone="SOUTH EAST",
                urgency="Normal",
                preferred_driver_id=None,
                pallet_quantity=1,
                loose_bags_quantity=0,
                start_time="09:00",
                end_time="12:00",
                note="Delivery note",
                status=status,
                product_lines=[
                    ProductDetailLine(
                        product_name="Rags",
                        quantity=1,
                        unit="PALLETS",
                    )
                ],
            )
        )

    def _seed_pickup(self, pickup_task_id):
        suffix = pickup_task_id.replace("PICKUP-", "")
        opshop_id = f"OPSHOP-{suffix}"
        schedule_id = f"SCHEDULE-{suffix}"
        self.repository.upsert_opshop_location(
            self._location(opshop_id, f"OP SHOP {suffix}")
        )
        self.repository.upsert_opshop_pickup_schedule(
            self._schedule(schedule_id, opshop_id)
        )
        self._seed_pickup_task(pickup_task_id, schedule_id, opshop_id)

    def _seed_pickup_task(self, pickup_task_id, schedule_id, opshop_id):
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=pickup_task_id,
                schedule_id=schedule_id,
                opshop_id=opshop_id,
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date=self.dispatch_date,
                driver_id=None,
                trip_no=None,
                notes="Pickup note",
                created_at="2026-06-01T00:00:00+00:00",
                updated_at="2026-06-01T00:00:00+00:00",
            )
        )

    def _seed_route_group(self):
        self.repository.upsert_countryside_route_group(
            OpShopCountrysideRouteGroup(
                route_group_id="ROUTE-GROUP-1",
                route_group_name="Test Route",
                status="Active",
                active_flag=True,
                display_order=1,
                source_marker="UI_CREATED",
                created_at="2026-06-01T00:00:00+00:00",
                updated_at="2026-06-01T00:00:00+00:00",
            )
        )
        for number in (1, 2):
            opshop_id = f"ROUTE-OPSHOP-{number}"
            self.repository.upsert_opshop_location(
                self._location(opshop_id, f"Route OP SHOP {number}")
            )
            self.repository.upsert_opshop_pickup_schedule(
                self._schedule(
                    f"ROUTE-SCHEDULE-{number}",
                    opshop_id,
                    pickup_category="COUNTRYSIDE",
                    route_group_id="ROUTE-GROUP-1",
                )
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
            secondary_contact=None,
            secondary_phone=None,
            access_type="Rear dock",
            key_required=False,
            trailer_restriction=None,
            status_notes="Ring first",
            is_active=True,
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
        )

    @staticmethod
    def _schedule(
        schedule_id,
        opshop_id,
        pickup_category="NORMAL",
        route_group_id=None,
    ):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id=opshop_id,
            run_day=None,
            run_type="ON_CALL",
            pickup_frequency="Weekly",
            time_window="09:00-12:00",
            call_before_arrival=True,
            call_timing="30 minutes",
            status="Active",
            active_flag=True,
            fortnight_group=None,
            review_required=False,
            review_reason=None,
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
            pickup_category=pickup_category,
            route_group_id=route_group_id,
        )

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
