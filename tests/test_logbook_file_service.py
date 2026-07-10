import json
import importlib
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional test dependency guard
    FastAPI = None
    TestClient = None

from backend.schemas import (
    CreateOrderRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    DeliveryWorkspaceVehicleClearRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    OpShopWorkspaceAssignmentBatchRequest,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService


class LogbookFileServiceTest(unittest.TestCase):
    def test_record_appends_json_lines_with_utf8_and_melbourne_timezone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = LogbookFileService(temp_dir)

            service.record(
                result="SUCCESS",
                workspace="OPSHOP",
                actor="Albert",
                action="OPSHOP_TASK_CREATED",
                entity_type="OPSHOP_PICKUP",
                entity_id="PICKUP-中文",
                summary="中文 OP SHOP pickup was created.",
                pickup_date="2026-07-10",
                metadata={"name": "益店", "count": 1},
            )
            service.record(
                result="SUCCESS",
                workspace="DELIVERY",
                actor="System",
                action="ORDER_CREATED",
                entity_type="ORDER",
                entity_id="184068",
                summary="Order 184068 was created.",
            )

            files = list(Path(temp_dir).glob("manual_dispatch_logbook_*.txt"))
            self.assertEqual(1, len(files))
            lines = files[0].read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(lines))

            first = json.loads(lines[0])
            self.assertEqual("SUCCESS", first["result"])
            self.assertEqual("OPSHOP", first["workspace"])
            self.assertEqual("Albert", first["actor"])
            self.assertEqual("PICKUP-中文", first["entity_id"])
            self.assertEqual({"count": 1, "name": "益店"}, first["metadata"])
            timestamp = datetime.fromisoformat(first["time"])
            self.assertIsNotNone(timestamp.tzinfo)
            self.assertIn(timestamp.utcoffset().total_seconds(), {36000, 39600})

    def test_record_is_best_effort_when_file_write_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blocker = Path(temp_dir) / "not-a-directory"
            blocker.write_text("blocking file", encoding="utf-8")
            service = LogbookFileService(blocker)

            with self.assertLogs(
                "backend.services.manual_dispatch.logbook_file_service",
                level="ERROR",
            ):
                service.record(
                    result="SUCCESS",
                    workspace="DELIVERY",
                    actor="System",
                    action="ORDER_CREATED",
                    summary="This should not crash.",
                )


class ManualDispatchLogbookIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = self.temp_dir.name
        self.service = ManualDispatchService()
        self.dispatch_date = "2026-05-05"
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Logbook QA",
                password="secret123",
                confirm_password="secret123",
            )
        )

    def tearDown(self):
        if self.previous_logbook_dir is None:
            os.environ.pop("MANUAL_DISPATCH_LOGBOOK_DIR", None)
        else:
            os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = self.previous_logbook_dir
        self.temp_dir.cleanup()

    def test_delivery_order_assignment_vehicle_and_run_sheet_actions_are_logged(self):
        with self.service.logbook_actor(self.account.account_name):
            created = self.service.create_delivery_order(
                CreateOrderRequest(
                    invoice_number="184068",
                    order_no="7147703",
                    company_name="Carton Customer",
                    phone="0400 000 000",
                    delivery_address="1 Test Street",
                    suburb="Coburg",
                    postcode="3058",
                    delivery_date=self.dispatch_date,
                    zone="North",
                    urgency="Normal",
                    pallet_quantity=1,
                    loose_bags_quantity=0,
                    product_lines=[
                        {
                            "product_name": "COLOUR RAGS 10KG NET",
                            "quantity": 1,
                            "unit": "PALLETS",
                        }
                    ],
                )
            )
            self.service.update_delivery_order(
                created.order_id,
                CreateOrderRequest(
                    invoice_number="184068",
                    order_no="7147703",
                    company_name="Carton Customer Updated",
                    phone="0400 000 000",
                    delivery_address="1 Test Street",
                    suburb="Coburg",
                    postcode="3058",
                    delivery_date=self.dispatch_date,
                    zone="North",
                    urgency="Normal",
                    pallet_quantity=1,
                    loose_bags_quantity=0,
                    product_lines=[
                        {
                            "product_name": "COLOUR RAGS 10KG NET",
                            "quantity": 1,
                            "unit": "PALLETS",
                        }
                    ],
                ),
            )
            self.service.cancel_delivery_order(created.order_id)

            self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORD-001",
                    driver_id="D001",
                    trip_no="trip1",
                )
            )
            self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORD-001",
                    driver_id="D002",
                    trip_no="trip2",
                )
            )
            self.service.unassign_delivery_workspace_order(
                DeliveryWorkspaceUnassignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORD-001",
                )
            )

            self.service.assign_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleAssignmentRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                    vehicle_id="V001",
                )
            )
            self.service.assign_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleAssignmentRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                    vehicle_id="V002",
                )
            )
            self.service.clear_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleClearRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                )
            )

            self.service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date=self.dispatch_date,
                    order_id="ORD-001",
                    driver_id="D001",
                    trip_no="trip1",
                )
            )
            generated = self.service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                )
            )
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
            saved = self.service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                )
            )
            self.service.save_generated_delivery_run_sheet(
                saved.run_sheet_id,
                self._save_request(),
            )

        actions = [entry["action"] for entry in self._entries()]
        for action in (
            "ORDER_CREATED",
            "ORDER_UPDATED",
            "ORDER_CANCELLED",
            "ORDER_ASSIGNED",
            "ORDER_REASSIGNED",
            "ORDER_UNASSIGNED",
            "VEHICLE_ASSIGNED",
            "VEHICLE_CHANGED",
            "VEHICLE_CLEARED",
            "DELIVERY_RUN_SHEET_GENERATED",
            "DELIVERY_RUN_SHEET_CANCELLED",
            "DELIVERY_RUN_SHEET_SAVED",
        ):
            self.assertIn(action, actions)
        saved_entry = self._latest_entry("DELIVERY_RUN_SHEET_SAVED")
        self.assertEqual("Logbook QA", saved_entry["actor"])
        self.assertEqual(1, saved_entry["metadata"]["order_count"])
        for entry in self._entries():
            if entry["result"] == "SUCCESS":
                self.assertEqual("Logbook QA", entry["actor"])

    def test_opshop_task_assignment_and_collection_actions_are_logged(self):
        self._seed_opshop_pickup()
        with self.service.logbook_actor(self.account.account_name):
            self.service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date=self.dispatch_date,
                    assignments=[
                        {"pickup_task_id": "PICKUP-001", "driver_id": "D001"}
                    ],
                )
            )
            self.service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date=self.dispatch_date,
                    assignments=[
                        {"pickup_task_id": "PICKUP-001", "driver_id": "D002"}
                    ],
                )
            )
            self.service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date=self.dispatch_date,
                    assignments=[
                        {"pickup_task_id": "PICKUP-001", "driver_id": ""}
                    ],
                )
            )
            self.service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date=self.dispatch_date,
                    assignments=[
                        {"pickup_task_id": "PICKUP-001", "driver_id": "D001"}
                    ],
                )
            )
            generated = self.service.create_generated_opshop_pickup_collection(
                GenerateOpShopPickupCollectionRequest(
                    dispatch_date=self.dispatch_date,
                    pickup_date=self.dispatch_date,
                    driver_id="D001",
                )
            )
            self.service.cancel_generated_opshop_pickup_collection(
                generated.collection_id
            )
            saved = self.service.create_generated_opshop_pickup_collection(
                GenerateOpShopPickupCollectionRequest(
                    dispatch_date=self.dispatch_date,
                    pickup_date=self.dispatch_date,
                    driver_id="D001",
                )
            )
            self.service.save_generated_opshop_pickup_collection(
                saved.collection_id,
                self._save_request(),
            )

        actions = [entry["action"] for entry in self._entries()]
        for action in (
            "OPSHOP_TASK_ASSIGNED",
            "OPSHOP_TASK_REASSIGNED",
            "OPSHOP_TASK_UNASSIGNED",
            "PICKUP_COLLECTION_GENERATED",
            "PICKUP_COLLECTION_CANCELLED",
            "PICKUP_COLLECTION_SAVED",
        ):
            self.assertIn(action, actions)
        saved_entry = self._latest_entry("PICKUP_COLLECTION_SAVED")
        self.assertEqual("Logbook QA", saved_entry["actor"])
        self.assertEqual(1, saved_entry["metadata"]["pickup_count"])
        for entry in self._entries():
            if entry["result"] == "SUCCESS":
                self.assertEqual("Logbook QA", entry["actor"])

    def test_important_failed_business_attempt_is_logged(self):
        self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=self.dispatch_date,
                order_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        generated = self.service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id="D001",
            )
        )

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date=self.dispatch_date,
                    delivery_date=self.dispatch_date,
                    driver_id="D001",
                )
            )

        failed = self._latest_entry("DELIVERY_RUN_SHEET_GENERATED")
        self.assertEqual("FAILED", failed["result"])
        self.assertIn("failure_reason", failed["metadata"])
        self.assertEqual(generated.driver_name_snapshot, "John")

    def _seed_opshop_pickup(self):
        self.service.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="OPSHOP-001",
                name="Helping Hands 中文",
                suburb="COBURG",
                street_address="1 Sydney Road",
                area_region="NORTH",
                primary_contact="Mary",
                primary_phone="0400 000 001",
                secondary_contact=None,
                secondary_phone=None,
                access_type="Rear dock",
                key_required=False,
                trailer_restriction="No",
                status_notes="Ring first",
                is_active=True,
                created_at="2026-05-01T00:00:00+00:00",
                updated_at="2026-05-01T00:00:00+00:00",
            )
        )
        self.service.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id="SCHEDULE-001",
                opshop_id="OPSHOP-001",
                run_day="MONDAY",
                run_type="ON_CALL",
                pickup_frequency="On call",
                time_window="09:00-12:00",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at="2026-05-01T00:00:00+00:00",
                updated_at="2026-05-01T00:00:00+00:00",
            )
        )
        self.service.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id="PICKUP-001",
                schedule_id="SCHEDULE-001",
                opshop_id="OPSHOP-001",
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date=self.dispatch_date,
                driver_id=None,
                trip_no=None,
                notes="Test pickup",
                created_at="2026-05-01T00:00:00+00:00",
                updated_at="2026-05-01T00:00:00+00:00",
            )
        )

    def _save_request(self):
        return SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
        )

    def _entries(self):
        files = list(Path(self.temp_dir.name).glob("manual_dispatch_logbook_*.txt"))
        self.assertEqual(1, len(files))
        return [
            json.loads(line)
            for line in files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _latest_entry(self, action):
        matches = [entry for entry in self._entries() if entry["action"] == action]
        self.assertTrue(matches, f"No logbook entry found for action {action}")
        return matches[-1]


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class ManualDispatchLogbookApiActorTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"logbook-api-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.logbook_dir = self.temp_dir / "logbook"

        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        self.previous_seed_demo_data = os.environ.get(
            "MANUAL_DISPATCH_SEED_DEMO_DATA"
        )
        self.previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        self.previous_allow_registration = os.environ.get(
            "MANUAL_DISPATCH_ALLOW_REGISTRATION"
        )
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(self.logbook_dir)
        os.environ.pop("MANUAL_DISPATCH_ALLOW_REGISTRATION", None)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
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
            self.previous_seed_demo_data,
        )
        self._restore_environment(
            "MANUAL_DISPATCH_LOGBOOK_DIR",
            self.previous_logbook_dir,
        )
        self._restore_environment(
            "MANUAL_DISPATCH_ALLOW_REGISTRATION",
            self.previous_allow_registration,
        )
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_authenticated_operator_cookie_sets_logbook_actor_for_mutation_route(self):
        register_response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Office Operator",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.assertEqual(200, register_response.status_code)

        create_response = self.client.post(
            "/api/manual-dispatch/delivery/orders",
            json={
                "invoice_number": "LOG-001",
                "order_no": "A100",
                "company_name": "Logbook Customer",
                "phone": "0400 000 000",
                "delivery_address": "1 Test Street",
                "suburb": "Coburg",
                "postcode": "3058",
                "delivery_date": "2026-05-05",
                "zone": "North",
                "urgency": "Normal",
                "pallet_quantity": 1,
                "loose_bags_quantity": 0,
                "product_lines": [
                    {
                        "product_name": "COLOUR RAGS",
                        "quantity": 1,
                        "unit": "PALLETS",
                    }
                ],
            },
        )

        self.assertEqual(200, create_response.status_code)
        created_entry = self._latest_entry("ORDER_CREATED")
        self.assertEqual("Office Operator", created_entry["actor"])
        self.assertNotEqual("Unknown", created_entry["actor"])

    def _entries(self):
        files = list(self.logbook_dir.glob("manual_dispatch_logbook_*.txt"))
        self.assertEqual(1, len(files))
        return [
            json.loads(line)
            for line in files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _latest_entry(self, action):
        matches = [entry for entry in self._entries() if entry["action"] == action]
        self.assertTrue(matches, f"No logbook entry found for action {action}")
        return matches[-1]

    @staticmethod
    def _restore_environment(name, previous_value):
        if previous_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous_value


if __name__ == "__main__":
    unittest.main()
