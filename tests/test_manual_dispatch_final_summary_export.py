from io import BytesIO
import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from openpyxl import load_workbook

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignTaskRequest,
    RegisterOperatorAccountRequest,
    SaveFinalTripSummaryRequest,
)
from backend.services.final_summary_excel_export_service import build_final_summary_excel
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class ManualDispatchFinalSummaryExportTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"final-summary-export-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.dispatch_date = "2026-05-05"
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Mandy",
                password="secret123",
                confirm_password="secret123",
            )
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_workbook_contains_saved_snapshot_values(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._assign_order("ORD-003", "D001", "trip2")
        self.service.save_final_trip_summary(
            self._summary_request(
                driver_name="Snapshot Driver",
                vehicle_rego="SNAP123",
                trips=[
                    self._trip_payload("trip1", [self._order_payload("ORD-001")]),
                    self._trip_payload("trip2", [self._order_payload("ORD-003")]),
                ],
            )
        )

        workbook = self._load_export_workbook()
        values = self._flat_values(workbook)

        self.assertIn("Dispatch Date", values)
        self.assertIn(self.dispatch_date, values)
        self.assertIn("Delivery Date", values)
        self.assertIn("Driver", values)
        self.assertIn("Snapshot Driver", values)
        self.assertIn("Rego #", values)
        self.assertIn("SNAP123", values)
        self.assertIn("Saved By", values)
        self.assertIn("Mandy", values)
        self.assertIn("Trip 1", values)
        self.assertIn("Trip 2", values)
        self.assertIn("No.", values)
        self.assertIn("Customer Name", values)
        self.assertIn("Suburb", values)
        self.assertIn("Estimated Distance From Warehouse (km)", values)
        self.assertIn("Invoice #", values)
        self.assertIn("Product Details", values)
        self.assertIn("Load", values)

    def test_export_skips_empty_trips(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(
            self._summary_request(
                trips=[
                    self._trip_payload("trip1", [self._order_payload("ORD-001")]),
                    self._trip_payload("trip2", []),
                ],
            )
        )

        values = self._flat_values(self._load_export_workbook())

        self.assertIn("Trip 1", values)
        self.assertNotIn("Trip 2", values)

    def test_export_does_not_include_generated_or_saved_timestamps(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        values = self._flat_values(self._load_export_workbook())

        self.assertNotIn("Generated At", values)
        self.assertNotIn("Saved At", values)

    def test_export_does_not_include_password_data(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        values = self._flat_values(self._load_export_workbook())
        normalized_values = [str(value).lower() for value in values]

        self.assertFalse(any("password" in value for value in normalized_values))
        self.assertFalse(any("password_hash" in value for value in normalized_values))
        self.assertFalse(any("password_salt" in value for value in normalized_values))
        self.assertNotIn("secret123", values)

    def test_export_uses_snapshots_after_live_records_change(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(
            self._summary_request(driver_name="Original Driver", vehicle_rego="ORIG123")
        )

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE manual_orders SET company_name = ? WHERE order_id = ?",
                ("Edited Customer", "ORD-001"),
            )
            connection.execute(
                "UPDATE manual_drivers SET name = ? WHERE driver_id = ?",
                ("Edited Driver", "D001"),
            )
            connection.execute(
                "UPDATE manual_vehicles SET rego = ? WHERE vehicle_id = ?",
                ("EDIT123", "V002"),
            )
            connection.commit()

        values = self._flat_values(self._load_export_workbook())

        self.assertIn("Original Driver", values)
        self.assertIn("ORIG123", values)
        self.assertIn("Demo Customer A", values)
        self.assertNotIn("Edited Driver", values)
        self.assertNotIn("EDIT123", values)
        self.assertNotIn("Edited Customer", values)

    def test_empty_export_returns_useful_workbook(self):
        workbook_bytes = build_final_summary_excel([], self.dispatch_date)
        workbook = load_workbook(BytesIO(workbook_bytes))
        worksheet = workbook.active

        self.assertEqual("Final Summaries", worksheet.title)
        self.assertEqual(
            f"No saved Final Trip Summaries for {self.dispatch_date}",
            worksheet["A1"].value,
        )

    def _load_export_workbook(self):
        workbook_bytes = build_final_summary_excel(
            self.service.list_final_trip_summaries(self.dispatch_date),
            self.dispatch_date,
        )
        return load_workbook(BytesIO(workbook_bytes), data_only=True)

    def _flat_values(self, workbook):
        values = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                values.extend(cell for cell in row if cell is not None)
        return values

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

    def _summary_request(self, driver_name="John", vehicle_rego="XYZ888", trips=None):
        return SaveFinalTripSummaryRequest(
            dispatch_date=self.dispatch_date,
            delivery_date=self.dispatch_date,
            driver_id="D001",
            driver_name_snapshot=driver_name,
            vehicle_id="V002",
            vehicle_rego_snapshot=vehicle_rego,
            total_pallets=0,
            total_loose_bags=0,
            generated_at="2026-05-05T00:00:00Z",
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
            trips=trips
            if trips is not None
            else [self._trip_payload("trip1", [self._order_payload("ORD-001")])],
        )

    def _trip_payload(self, trip_no, orders):
        return {"trip_no": trip_no, "orders": orders}

    def _order_payload(self, order_id):
        order = self.repository.get_order(order_id)
        return {
            "task_type": "ORDER",
            "task_id": order_id,
            "order_id": order_id,
            "invoice_number": order.invoice_number,
            "company_name": order.company_name,
            "suburb": order.suburb,
            "delivery_address": order.delivery_address,
            "product": "",
            "pallet_quantity": order.pallet_quantity,
            "loose_bags_quantity": order.loose_bags_quantity,
            "note": order.note,
        }


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class ManualDispatchFinalSummaryExportRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"final-summary-export-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Mandy",
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
        self.dispatch_date = "2026-05-05"

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_endpoint_returns_xlsx(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        response = self.client.get(
            "/api/manual-dispatch/final-summaries/export-excel",
            params={"dispatch_date": self.dispatch_date},
        )

        self.assertEqual(200, response.status_code)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.headers["content-type"],
        )
        self.assertIn(
            f"final-trip-summary-{self.dispatch_date}.xlsx",
            response.headers["content-disposition"],
        )

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

    def _summary_request(self):
        order = self.repository.get_order("ORD-001")
        return SaveFinalTripSummaryRequest(
            dispatch_date=self.dispatch_date,
            delivery_date=self.dispatch_date,
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id=None,
            vehicle_rego_snapshot="No vehicle selected",
            total_pallets=order.pallet_quantity,
            total_loose_bags=order.loose_bags_quantity,
            generated_at="2026-05-05T00:00:00Z",
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
            trips=[
                {
                    "trip_no": "trip1",
                    "orders": [
                        {
                            "task_type": "ORDER",
                            "task_id": order.order_id,
                            "order_id_snapshot": order.order_id,
                            "invoice_number_snapshot": order.invoice_number,
                            "company_name_snapshot": order.company_name,
                            "suburb_snapshot": order.suburb,
                            "delivery_address_snapshot": order.delivery_address,
                            "product_snapshot": "",
                            "pallet_quantity_snapshot": order.pallet_quantity,
                            "loose_bags_quantity_snapshot": order.loose_bags_quantity,
                            "note_snapshot": order.note,
                        }
                    ],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
