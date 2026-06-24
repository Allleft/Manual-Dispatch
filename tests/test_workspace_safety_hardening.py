import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    DeliveryRunSheet,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetTrip,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopPickupCollection,
    OpShopPickupCollectionRowSnapshot,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.manual_dispatch.delivery_run_sheet_service import (
    DeliveryRunSheetService,
)
from backend.services.manual_dispatch.opshop_pickup_collection_service import (
    OpShopPickupCollectionService,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class WorkspaceSafetyHardeningTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-safety-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        self.previous_seed_flag = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Workspace Safety Tester",
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

    def test_fresh_database_reports_both_workspaces_ready(self):
        expected = {
            "delivery_ready": True,
            "opshop_ready": True,
            "legacy_generated_summary_count": 0,
            "delivery_unmigrated_summary_count": 0,
            "opshop_unmigrated_summary_count": 0,
            "delivery_unmigrated_summary_ids": [],
            "opshop_unmigrated_summary_ids": [],
        }
        self.assertEqual(expected, self.service.get_workspace_migration_status())
        response = self.client.get(
            "/api/manual-dispatch/workspace-migration-status"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, response.json())

    def test_delivery_only_legacy_summary_blocks_only_delivery_until_migrated(self):
        self._insert_legacy_summary("LEGACY-DELIVERY", delivery_rows=True)

        blocked = self.service.get_workspace_migration_status()
        self.assertFalse(blocked["delivery_ready"])
        self.assertTrue(blocked["opshop_ready"])
        self.assertEqual(["LEGACY-DELIVERY"], blocked["delivery_unmigrated_summary_ids"])

        self.repository.upsert_delivery_run_sheet(
            self._run_sheet("DRS-MIGRATED", "SAVED", "LEGACY-DELIVERY")
        )
        ready = self.service.get_workspace_migration_status()
        self.assertTrue(ready["delivery_ready"])
        self.assertTrue(ready["opshop_ready"])

    def test_opshop_only_legacy_summary_blocks_only_opshop_until_migrated(self):
        self._insert_legacy_summary("LEGACY-OPSHOP", opshop_rows=True)

        blocked = self.service.get_workspace_migration_status()
        self.assertTrue(blocked["delivery_ready"])
        self.assertFalse(blocked["opshop_ready"])
        self.assertEqual(["LEGACY-OPSHOP"], blocked["opshop_unmigrated_summary_ids"])

        self.repository.upsert_opshop_pickup_collection(
            self._collection("OPC-MIGRATED", "SAVED", "LEGACY-OPSHOP")
        )
        ready = self.service.get_workspace_migration_status()
        self.assertTrue(ready["delivery_ready"])
        self.assertTrue(ready["opshop_ready"])

    def test_mixed_summary_requires_both_markers_and_empty_summary_does_not_block(self):
        self._insert_legacy_summary("LEGACY-EMPTY")
        self._insert_legacy_summary(
            "LEGACY-MIXED",
            delivery_rows=True,
            opshop_rows=True,
        )
        blocked = self.service.get_workspace_migration_status()
        self.assertFalse(blocked["delivery_ready"])
        self.assertFalse(blocked["opshop_ready"])

        self.repository.upsert_delivery_run_sheet(
            self._run_sheet("DRS-MIXED", "SAVED", "LEGACY-MIXED")
        )
        delivery_only = self.service.get_workspace_migration_status()
        self.assertTrue(delivery_only["delivery_ready"])
        self.assertFalse(delivery_only["opshop_ready"])

        self.repository.upsert_opshop_pickup_collection(
            self._collection("OPC-MIXED", "SAVED", "LEGACY-MIXED")
        )
        ready = self.service.get_workspace_migration_status()
        self.assertTrue(ready["delivery_ready"])
        self.assertTrue(ready["opshop_ready"])

    def test_generated_legacy_summary_blocks_both_workspaces(self):
        self._insert_legacy_summary("LEGACY-GENERATED", status="GENERATED")
        status = self.service.get_workspace_migration_status()
        self.assertFalse(status["delivery_ready"])
        self.assertFalse(status["opshop_ready"])
        self.assertEqual(1, status["legacy_generated_summary_count"])

        response = self.client.get(
            "/api/manual-dispatch/delivery/board",
            params={"dispatch_date": "2026-06-24"},
        )
        self.assertEqual(409, response.status_code)
        self.assertIn("must be resolved", response.json()["detail"])

    def test_all_approved_scoped_routes_are_guarded_but_legacy_routes_remain_usable(self):
        self._insert_legacy_summary(
            "LEGACY-BLOCKED",
            delivery_rows=True,
            opshop_rows=True,
        )
        requests = [
            ("get", "/api/manual-dispatch/delivery/board", {"params": {"dispatch_date": "2026-06-24"}}),
            ("get", "/api/manual-dispatch/opshop/board", {"params": {"dispatch_date": "2026-06-24"}}),
            ("post", "/api/manual-dispatch/delivery/assignments", {"json": {}}),
            ("post", "/api/manual-dispatch/delivery/assignments/unassign", {"json": {}}),
            ("post", "/api/manual-dispatch/delivery/vehicle-assignments", {"json": {}}),
            ("post", "/api/manual-dispatch/delivery/vehicle-assignments/clear", {"json": {}}),
            ("post", "/api/manual-dispatch/opshop/pickups/assignments/apply", {"json": {}}),
            ("post", "/api/manual-dispatch/opshop/pickups/assignments/unassign", {"json": {}}),
            ("post", "/api/manual-dispatch/opshop/countryside-route-groups/ROUTE-1/assign", {"json": {}}),
            ("post", "/api/manual-dispatch/delivery/run-sheets/generated", {"json": {}}),
            ("get", "/api/manual-dispatch/delivery/run-sheets", {}),
            ("post", "/api/manual-dispatch/opshop/pickup-collections/generated", {"json": {}}),
            ("get", "/api/manual-dispatch/opshop/pickup-collections", {}),
        ]
        for method, path, kwargs in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(409, response.status_code, response.text)
                self.assertIn("Workspace migration is required", response.json()["detail"])

        legacy_board = self.client.get(
            "/api/manual-dispatch/board",
            params={"dispatch_date": "2026-06-24"},
        )
        legacy_summaries = self.client.get(
            "/api/manual-dispatch/final-summaries",
            params={"dispatch_date": "2026-06-24"},
        )
        shared = self.client.get("/api/manual-dispatch/shared/specifications")
        self.assertEqual(200, legacy_board.status_code)
        self.assertEqual(200, legacy_summaries.status_code)
        self.assertEqual(200, shared.status_code)

    def test_new_generate_and_list_routes_reject_invalid_dates(self):
        requests = [
            self.client.post(
                "/api/manual-dispatch/delivery/run-sheets/generated",
                json={
                    "dispatch_date": "24-06-2026",
                    "delivery_date": "2026-06-24",
                    "driver_id": "DRIVER-1",
                },
            ),
            self.client.post(
                "/api/manual-dispatch/opshop/pickup-collections/generated",
                json={
                    "dispatch_date": "2026-06-24",
                    "pickup_date": "2026-99-24",
                    "driver_id": "DRIVER-1",
                },
            ),
            self.client.get(
                "/api/manual-dispatch/delivery/run-sheets",
                params={"delivery_date": "not-a-date"},
            ),
            self.client.get(
                "/api/manual-dispatch/opshop/pickup-collections",
                params={"dispatch_date": "2026/06/24"},
            ),
        ]
        for response in requests:
            self.assertEqual(400, response.status_code, response.text)
            self.assertIn("YYYY-MM-DD", response.json()["detail"])

    def test_delivery_save_cancel_is_atomic_and_preserves_saved_snapshot(self):
        generated = self.repository.upsert_delivery_run_sheet(
            self._run_sheet("DRS-ATOMIC", "GENERATED")
        )
        saved = self.service.save_generated_delivery_run_sheet(
            generated.run_sheet_id,
            self._save_request(),
        )
        original_rows = self._rows(
            "delivery_run_sheet_rows",
            "run_sheet_id",
            generated.run_sheet_id,
        )
        original_metadata = (
            saved.saved_at,
            saved.saved_by_account_name,
            saved.saved_by_account_id,
        )

        self.assertFalse(
            self.repository.delete_generated_delivery_run_sheet(generated.run_sheet_id)
        )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.save_generated_delivery_run_sheet(
                generated.run_sheet_id,
                self._save_request(),
            )

        reloaded = self.repository.get_delivery_run_sheet(generated.run_sheet_id)
        self.assertEqual("SAVED", reloaded.status)
        self.assertEqual(
            original_metadata,
            (
                reloaded.saved_at,
                reloaded.saved_by_account_name,
                reloaded.saved_by_account_id,
            ),
        )
        self.assertEqual(
            original_rows,
            self._rows(
                "delivery_run_sheet_rows",
                "run_sheet_id",
                generated.run_sheet_id,
            ),
        )

    def test_opshop_save_cancel_is_atomic_and_preserves_saved_snapshot(self):
        generated = self.repository.upsert_opshop_pickup_collection(
            self._collection("OPC-ATOMIC", "GENERATED")
        )
        saved = self.service.save_generated_opshop_pickup_collection(
            generated.collection_id,
            self._save_request(),
        )
        original_rows = self._rows(
            "opshop_pickup_collection_rows",
            "collection_id",
            generated.collection_id,
        )
        original_metadata = (
            saved.saved_at,
            saved.saved_by_account_name,
            saved.saved_by_account_id,
        )

        self.assertFalse(
            self.repository.delete_generated_opshop_pickup_collection(
                generated.collection_id
            )
        )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.cancel_generated_opshop_pickup_collection(
                generated.collection_id
            )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.save_generated_opshop_pickup_collection(
                generated.collection_id,
                self._save_request(),
            )

        reloaded = self.repository.get_opshop_pickup_collection(
            generated.collection_id
        )
        self.assertEqual("SAVED", reloaded.status)
        self.assertEqual(
            original_metadata,
            (
                reloaded.saved_at,
                reloaded.saved_by_account_name,
                reloaded.saved_by_account_id,
            ),
        )
        self.assertEqual(
            original_rows,
            self._rows(
                "opshop_pickup_collection_rows",
                "collection_id",
                generated.collection_id,
            ),
        )

    def test_duplicate_generate_races_return_validation_conflicts(self):
        delivery_repository = _RaceDeliveryRepository()
        delivery_service = DeliveryRunSheetService(
            delivery_repository,
            _NoOpValidator(),
        )
        delivery_service._build_trips = lambda *_: self._run_sheet(
            "RACE",
            "GENERATED",
        ).trips
        delivery_service._vehicle_snapshot = lambda *_: (None, None)
        with self.assertRaisesRegex(ValueError, "already exists"):
            delivery_service.create_generated(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date="2026-06-24",
                    delivery_date="2026-06-24",
                    driver_id="DRIVER-1",
                )
            )

        opshop_repository = _RaceOpShopRepository()
        opshop_service = OpShopPickupCollectionService(
            opshop_repository,
            _NoOpValidator(),
        )
        opshop_service._build_pickups = lambda *_: self._collection(
            "RACE",
            "GENERATED",
        ).pickups
        with self.assertRaisesRegex(ValueError, "already exists"):
            opshop_service.create_generated(
                GenerateOpShopPickupCollectionRequest(
                    dispatch_date="2026-06-24",
                    pickup_date="2026-06-24",
                    driver_id="DRIVER-1",
                )
            )

    def _insert_legacy_summary(
        self,
        summary_id,
        status="SAVED",
        delivery_rows=False,
        opshop_rows=False,
    ):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id, dispatch_date, delivery_date, driver_id,
                    driver_name_snapshot, total_pallets, total_loose_bags,
                    status, generated_at, saved_at, saved_by_account_name
                ) VALUES (?, '2026-06-24', '2026-06-24', 'DRIVER-1',
                    'Driver One', 0, 0, ?, '2026-06-24T08:00:00Z',
                    '2026-06-24T08:05:00Z', 'Legacy User')
                """,
                (summary_id, status),
            )
            if delivery_rows:
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_rows (
                        row_id, summary_id, trip_no, row_no, task_type, task_id,
                        pallet_quantity_snapshot, loose_bags_quantity_snapshot
                    ) VALUES (?, ?, 'trip1', 1, 'ORDER', 'ORDER-LEGACY', 0, 0)
                    """,
                    (f"ROW-{summary_id}", summary_id),
                )
            if opshop_rows:
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_opshop_pickup_rows (
                        row_id, summary_id, row_no, pickup_task_id_snapshot,
                        pickup_date_snapshot, status_snapshot
                    ) VALUES (?, ?, 1, 'PICKUP-LEGACY', '2026-06-24', 'ASSIGNED')
                    """,
                    (f"OPROW-{summary_id}", summary_id),
                )
            connection.commit()

    def _run_sheet(self, run_sheet_id, status, legacy_summary_id=None):
        order = DeliveryRunSheetOrderSnapshot(
            row_id=f"ROW-{run_sheet_id}",
            trip_no="trip1",
            row_no=1,
            task_type="ORDER",
            task_id="ORDER-1",
            order_id_snapshot="ORDER-1",
            invoice_number_snapshot="INV-1",
            order_no_snapshot="1",
            company_name_snapshot="Customer",
            suburb_snapshot="MELBOURNE",
            delivery_address_snapshot="1 TEST ST",
            product_snapshot=None,
            pallet_quantity_snapshot=1,
            loose_bags_quantity_snapshot=0,
            note_snapshot=None,
        )
        return DeliveryRunSheet(
            run_sheet_id=run_sheet_id,
            dispatch_date="2026-06-24",
            delivery_date="2026-06-24",
            driver_id="DRIVER-1",
            driver_name_snapshot="Driver One",
            vehicle_id=None,
            vehicle_rego_snapshot=None,
            total_pallets=1,
            total_loose_bags=0,
            status=status,
            generated_at="2026-06-24T08:00:00Z",
            saved_at="2026-06-24T08:05:00Z" if status == "SAVED" else None,
            saved_by_account_name="Legacy User" if status == "SAVED" else None,
            saved_by_account_id=None,
            legacy_summary_id=legacy_summary_id,
            trips=[DeliveryRunSheetTrip(trip_no="trip1", orders=[order])],
        )

    def _collection(self, collection_id, status, legacy_summary_id=None):
        pickup = OpShopPickupCollectionRowSnapshot(
            row_id=f"ROW-{collection_id}",
            row_no=1,
            pickup_task_id_snapshot="PICKUP-1",
            opshop_name_snapshot="OP SHOP",
            suburb_snapshot="MELBOURNE",
            street_address_snapshot="1 TEST ST",
            area_region_snapshot=None,
            pickup_date_snapshot="2026-06-24",
            run_type_snapshot="ON_CALL",
            pickup_category_snapshot="NORMAL",
            route_group_id_snapshot=None,
            route_group_name_snapshot=None,
            pickup_frequency_snapshot=None,
            time_window_snapshot=None,
            primary_contact_snapshot=None,
            primary_phone_snapshot=None,
            secondary_contact_snapshot=None,
            secondary_phone_snapshot=None,
            access_type_snapshot=None,
            key_required_snapshot=False,
            trailer_restriction_snapshot=None,
            notes_snapshot=None,
            status_snapshot="ASSIGNED",
        )
        return OpShopPickupCollection(
            collection_id=collection_id,
            dispatch_date="2026-06-24",
            pickup_date="2026-06-24",
            driver_id="DRIVER-1",
            driver_name_snapshot="Driver One",
            status=status,
            generated_at="2026-06-24T08:00:00Z",
            saved_at="2026-06-24T08:05:00Z" if status == "SAVED" else None,
            saved_by_account_name="Legacy User" if status == "SAVED" else None,
            saved_by_account_id=None,
            legacy_summary_id=legacy_summary_id,
            pickups=[pickup],
        )

    def _save_request(self):
        return SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
        )

    def _rows(self, table_name, key_name, key_value):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM {table_name} WHERE {key_name} = ? ORDER BY row_id",
                    (key_value,),
                ).fetchall()
            ]

    @staticmethod
    def _restore_environment(name, previous_value):
        if previous_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous_value


class _NoOpValidator:
    @staticmethod
    def validate_driver_exists(_driver_id):
        return None


class _RaceDeliveryRepository:
    def __init__(self):
        self.created = None

    def get_delivery_run_sheet_for_driver(self, *_args):
        return self.created

    @staticmethod
    def get_driver(_driver_id):
        return SimpleNamespace(name="Driver One")

    def upsert_delivery_run_sheet(self, run_sheet):
        self.created = run_sheet
        raise RuntimeError("simulated unique constraint race")


class _RaceOpShopRepository:
    def __init__(self):
        self.created = None

    def get_opshop_pickup_collection_for_driver(self, *_args):
        return self.created

    @staticmethod
    def get_driver(_driver_id):
        return SimpleNamespace(name="Driver One")

    def upsert_opshop_pickup_collection(self, collection):
        self.created = collection
        raise RuntimeError("simulated unique constraint race")


if __name__ == "__main__":
    unittest.main()
