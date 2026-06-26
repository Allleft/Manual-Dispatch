import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignTaskRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    RegisterOperatorAccountRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class WorkspaceApiAndExportsTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-api-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Workspace API Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.dispatch_date = "2026-05-05"
        self._assign_order()
        self._seed_and_assign_pickup()

        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_independent_routes_generate_list_get_save_cancel_and_export(self):
        expected_routes = {
            ("GET", "/api/manual-dispatch/delivery/specifications"),
            ("POST", "/api/manual-dispatch/delivery/drivers"),
            ("PATCH", "/api/manual-dispatch/delivery/drivers/{driver_id}"),
            ("DELETE", "/api/manual-dispatch/delivery/drivers/{driver_id}"),
            ("POST", "/api/manual-dispatch/delivery/vehicles"),
            ("PATCH", "/api/manual-dispatch/delivery/vehicles/{vehicle_id}"),
            ("DELETE", "/api/manual-dispatch/delivery/vehicles/{vehicle_id}"),
            ("POST", "/api/manual-dispatch/delivery/orders"),
            ("PATCH", "/api/manual-dispatch/delivery/orders/{order_id}"),
            ("POST", "/api/manual-dispatch/delivery/orders/{order_id}/cancel"),
            ("POST", "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview"),
            ("POST", "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit"),
            ("POST", "/api/manual-dispatch/delivery/run-sheets/generated"),
            ("GET", "/api/manual-dispatch/delivery/run-sheets"),
            ("GET", "/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}"),
            ("POST", "/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/save"),
            (
                "POST",
                "/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/cancel-generated",
            ),
            (
                "GET",
                "/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/export-excel",
            ),
            ("POST", "/api/manual-dispatch/opshop/pickup-collections/generated"),
            ("GET", "/api/manual-dispatch/opshop/pickup-collections"),
            (
                "GET",
                "/api/manual-dispatch/opshop/pickup-collections/{collection_id}",
            ),
            (
                "POST",
                "/api/manual-dispatch/opshop/pickup-collections/{collection_id}/save",
            ),
            (
                "POST",
                "/api/manual-dispatch/opshop/pickup-collections/{collection_id}/cancel-generated",
            ),
            (
                "GET",
                "/api/manual-dispatch/opshop/pickup-collections/{collection_id}/export-excel",
            ),
        }
        actual_routes = {
            (method, route.path)
            for route in self.api_module.router.routes
            for method in route.methods
        }
        self.assertFalse(expected_routes - actual_routes)

        delivery = self.client.post(
            "/api/manual-dispatch/delivery/run-sheets/generated",
            json=self._delivery_generate_payload(),
        )
        self.assertEqual(200, delivery.status_code)
        run_sheet_id = delivery.json()["run_sheet_id"]
        self.assertEqual(
            200,
            self.client.get(
                f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}"
            ).status_code,
        )
        self.assertEqual(
            1,
            len(
                self.client.get(
                    "/api/manual-dispatch/delivery/run-sheets",
                    params={"dispatch_date": self.dispatch_date},
                ).json()
            ),
        )

        cancelled_delivery = self.client.post(
            f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/cancel-generated"
        )
        self.assertEqual({"cancelled": True}, cancelled_delivery.json())

        saved_run_sheet_id = self._generate_and_save_delivery()
        delivery_export = self.client.get(
            f"/api/manual-dispatch/delivery/run-sheets/{saved_run_sheet_id}/export-excel"
        )
        self.assertEqual(200, delivery_export.status_code)
        self.assertIn("Delivery_Run_Sheet_", delivery_export.headers["content-disposition"])

        collection = self.client.post(
            "/api/manual-dispatch/opshop/pickup-collections/generated",
            json=self._collection_generate_payload(),
        )
        self.assertEqual(200, collection.status_code)
        collection_id = collection.json()["collection_id"]
        cancelled_collection = self.client.post(
            f"/api/manual-dispatch/opshop/pickup-collections/{collection_id}/cancel-generated"
        )
        self.assertEqual({"cancelled": True}, cancelled_collection.json())

        saved_collection_id = self._generate_and_save_collection()
        collection_export = self.client.get(
            f"/api/manual-dispatch/opshop/pickup-collections/{saved_collection_id}/export-excel"
        )
        self.assertEqual(200, collection_export.status_code)
        self.assertIn(
            "OPSHOP_Pickup_Collection_",
            collection_export.headers["content-disposition"],
        )

    def test_api_rejects_saved_snapshot_overwrite(self):
        run_sheet_id = self._generate_and_save_delivery()
        collection_id = self._generate_and_save_collection()

        duplicate_delivery_save = self.client.post(
            f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/save",
            json=self._save_payload(),
        )
        duplicate_collection_save = self.client.post(
            f"/api/manual-dispatch/opshop/pickup-collections/{collection_id}/save",
            json=self._save_payload(),
        )
        regenerate_delivery = self.client.post(
            "/api/manual-dispatch/delivery/run-sheets/generated",
            json=self._delivery_generate_payload(),
        )
        regenerate_collection = self.client.post(
            "/api/manual-dispatch/opshop/pickup-collections/generated",
            json=self._collection_generate_payload(),
        )

        self.assertEqual(400, duplicate_delivery_save.status_code)
        self.assertEqual(400, duplicate_collection_save.status_code)
        self.assertEqual(400, regenerate_delivery.status_code)
        self.assertEqual(400, regenerate_collection.status_code)

    def test_exports_use_saved_snapshots_and_keep_domains_separate(self):
        run_sheet_id = self._generate_and_save_delivery()
        collection_id = self._generate_and_save_collection()

        order = self.repository.get_order("ORD-001")
        order.company_name = "Edited Live Customer"
        self.repository.update_order(order)
        location = self.repository.get_opshop_location("OPSHOP-WORKSPACE")
        location.name = "Edited Live OP SHOP"
        self.repository.upsert_opshop_location(location)

        delivery_values = self._workbook_values(
            self.client.get(
                f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/export-excel"
            ).content
        )
        collection_values = self._workbook_values(
            self.client.get(
                f"/api/manual-dispatch/opshop/pickup-collections/{collection_id}/export-excel"
            ).content
        )

        self.assertIn("Demo Customer A", delivery_values)
        self.assertNotIn("Edited Live Customer", delivery_values)
        self.assertNotIn("Northside Op Shop", delivery_values)
        self.assertNotIn("OP SHOP Name", delivery_values)
        self.assertIn("Northside Op Shop", collection_values)
        self.assertNotIn("Edited Live OP SHOP", collection_values)
        self.assertIn("Call Before Arrival", collection_values)
        self.assertIn("30 minutes", collection_values)
        self.assertNotIn("Trip 1", collection_values)
        self.assertNotIn("Total Pallets", collection_values)
        self.assertNotIn("Demo Customer A", collection_values)

    def test_delivery_export_uses_daily_run_sheet_form_layout(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id="ORD-002",
                driver_id="D001",
                trip_no="trip2",
            )
        )
        run_sheet_id = self._generate_and_save_delivery()
        workbook = load_workbook(
            BytesIO(
                self.client.get(
                    f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/export-excel"
                ).content
            )
        )
        worksheet = workbook.active
        self.assertEqual("Daily Run Sheet", worksheet.title)
        self.assertEqual("landscape", worksheet.page_setup.orientation)
        self.assertEqual(str(worksheet.PAPERSIZE_A4), str(worksheet.page_setup.paperSize))

        values = [
            cell.value
            for row in worksheet.iter_rows()
            for cell in row
            if cell.value is not None
        ]
        self.assertIn("DAILY RUN SHEET", values)
        self.assertIn("Date:", values)
        self.assertIn(self.dispatch_date, values)
        self.assertIn("Driver:", values)
        self.assertIn("John", values)
        self.assertIn("Start Time:", values)
        self.assertIn(
            "Time Loading Started (to be filled in by storeman):",
            values,
        )
        self.assertIn(
            "Time Loading Completed (to be filled in by storeman):",
            values,
        )
        self.assertIn("Finish Time:", values)
        self.assertNotIn("Final Trip Summary", values)
        self.assertNotIn("Address", values)
        self.assertNotIn("Product Details", values)
        self.assertNotIn("Order #", values)

        header_row = [cell.value for cell in worksheet[9]]
        self.assertEqual(
            [
                "Customer Name",
                "Suburb",
                "Invoice #",
                "BAGS",
                "KGS",
                "Pallets",
                "COD",
                "CQ",
                "Time Out",
                "Time In",
                "Print Name",
                "Comments / Signature",
                "No. of Pallets Returned",
            ],
            header_row,
        )

        rows = list(worksheet.iter_rows(values_only=True))
        customer_a_index = next(
            index for index, row in enumerate(rows) if row[0] == "Demo Customer A"
        )
        trip_2_index = next(index for index, row in enumerate(rows) if row[0] == "TRIP 2")
        customer_b_index = next(
            index for index, row in enumerate(rows) if row[0] == "Demo Customer B"
        )
        self.assertLess(customer_a_index, trip_2_index)
        self.assertLess(trip_2_index, customer_b_index)
        customer_a_row = rows[customer_a_index]
        self.assertEqual("INV-1001", customer_a_row[2])
        self.assertEqual(0, customer_a_row[3])
        self.assertIsNone(customer_a_row[4])
        self.assertEqual(2, customer_a_row[5])
        for manual_column in range(6, 13):
            self.assertIsNone(customer_a_row[manual_column])

    def test_legacy_final_summary_schema_and_routes_remain_available(self):
        route_pairs = {
            (method, route.path)
            for route in self.api_module.router.routes
            for method in route.methods
        }
        self.assertIn(("POST", "/api/manual-dispatch/final-summaries"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/final-summaries"), route_pairs)
        self.assertIn(("GET", "/api/manual-dispatch/board"), route_pairs)

        with sqlite3.connect(self.db_path) as connection:
            legacy_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        self.assertTrue(
            {
                "final_trip_summaries",
                "final_trip_summary_rows",
                "final_trip_summary_opshop_pickup_rows",
            }.issubset(legacy_tables)
        )

    def _assign_order(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

    def _seed_and_assign_pickup(self):
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="OPSHOP-WORKSPACE",
                name="Northside Op Shop",
                suburb="Coburg",
                street_address="1 Sydney Road",
                area_region="North",
                primary_contact="Mary",
                primary_phone="0400 000 001",
                secondary_contact=None,
                secondary_phone=None,
                access_type="Rear dock",
                key_required=True,
                trailer_restriction="Small truck only",
                status_notes="Ring first",
                is_active=True,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id="SCHEDULE-WORKSPACE",
                opshop_id="OPSHOP-WORKSPACE",
                run_day="TUESDAY",
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
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id="PICKUP-WORKSPACE",
                schedule_id="SCHEDULE-WORKSPACE",
                opshop_id="OPSHOP-WORKSPACE",
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date=self.dispatch_date,
                driver_id=None,
                trip_no=None,
                notes="Leave at rear door",
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                task_id="PICKUP-WORKSPACE",
                driver_id="D001",
                trip_no="trip1",
            )
        )

    def _generate_and_save_delivery(self):
        generated = self.client.post(
            "/api/manual-dispatch/delivery/run-sheets/generated",
            json=self._delivery_generate_payload(),
        )
        run_sheet_id = generated.json()["run_sheet_id"]
        saved = self.client.post(
            f"/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/save",
            json=self._save_payload(),
        )
        self.assertEqual(200, saved.status_code)
        return run_sheet_id

    def _generate_and_save_collection(self):
        generated = self.client.post(
            "/api/manual-dispatch/opshop/pickup-collections/generated",
            json=self._collection_generate_payload(),
        )
        collection_id = generated.json()["collection_id"]
        saved = self.client.post(
            f"/api/manual-dispatch/opshop/pickup-collections/{collection_id}/save",
            json=self._save_payload(),
        )
        self.assertEqual(200, saved.status_code)
        return collection_id

    def _delivery_generate_payload(self):
        return {
            "dispatch_date": self.dispatch_date,
            "delivery_date": self.dispatch_date,
            "driver_id": "D001",
        }

    def _collection_generate_payload(self):
        return {
            "dispatch_date": self.dispatch_date,
            "pickup_date": self.dispatch_date,
            "driver_id": "D001",
        }

    def _save_payload(self):
        return {
            "saved_by_account_name": self.account.account_name,
            "saved_by_account_id": self.account.account_id,
        }

    @staticmethod
    def _workbook_values(workbook_bytes):
        workbook = load_workbook(BytesIO(workbook_bytes))
        return [
            cell.value
            for worksheet in workbook.worksheets
            for row in worksheet.iter_rows()
            for cell in row
            if cell.value is not None
        ]


if __name__ == "__main__":
    unittest.main()
