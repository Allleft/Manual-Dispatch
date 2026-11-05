import hashlib
import importlib
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.errors import DeliveryRunSheetLockedError
from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    CloseDeliveryRunSheetRequest, CloseDeliveryRunSheetRowRequest,
    GenerateDeliveryRunSheetRequest, SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.delivery_run_sheet_excel_export_service import build_delivery_run_sheet_excel
from tests import test_delivery_run_sheet_closeout as closeout
from tests.manual_dispatch_api_test_helpers import authenticate_test_client


class ReturnToPoolCancellationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="returned-order-cancel-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.path)
        self.fixture = closeout.DeliveryRunSheetCloseoutTest()
        self.service, self.identity, self.sheet, self.logbook = self.fixture._build_saved_sheet(self.repository)

    def close_sheet(self):
        self.sheet = self.service.close_saved_delivery_run_sheet(
            self.sheet.run_sheet_id, self.fixture._valid_request(self.sheet), self.identity,
        )

    def eligibility(self, order_id="CLOSE-ORD-3"):
        return self.service.get_delivery_order_cancellation_eligibility(order_id)

    def history(self):
        with closing(sqlite3.connect(self.path)) as connection:
            return {table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                    for table in ("delivery_run_sheets", "delivery_run_sheet_rows", "delivery_run_sheet_outcomes")}

    def cancellations(self):
        return [entry for entry in self.logbook.entries if entry["action"] == "ORDER_CANCELLED"]

    def assert_rejected(self, order_id, error=ValueError):
        before = asdict(self.repository.get_order(order_id)), self.history(), list(self.logbook.entries)
        self.assertFalse(self.eligibility(order_id)["can_cancel"])
        with self.assertRaises(error):
            self.service.cancel_delivery_order(order_id)
        self.assertEqual(before, (asdict(self.repository.get_order(order_id)), self.history(), self.logbook.entries))

    def test_generated_reservation_including_null_trip_rejected(self):
        self.assertIsNone(self.sheet.trip_no)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE delivery_run_sheets SET status = 'GENERATED', saved_at = NULL")
        self.assert_rejected("CLOSE-ORD-3", DeliveryRunSheetLockedError)

    def test_saved_open_including_null_trip_rejected(self):
        self.assertIsNone(self.sheet.trip_no)
        self.assert_rejected("CLOSE-ORD-3", DeliveryRunSheetLockedError)

    def test_returned_cancel_preserves_all_history_and_export(self):
        self.close_sheet()
        before = self.history(), asdict(self.sheet)
        export_before = self.export_cells()
        self.assertEqual({"order_id": "CLOSE-ORD-3", "can_cancel": True, "reason": "",
                          "has_run_sheet_history": True, "returned_to_pool": True}, self.eligibility())
        order = self.service.cancel_delivery_order("CLOSE-ORD-3")
        self.assertEqual("CANCELLED", order.status)
        board = self.service.get_delivery_workspace_board(closeout.NEXT_DELIVERY_DATE)
        self.assertNotIn(order.order_id, {item.order_id for item in board.orders})
        self.assertEqual(before, (self.history(), asdict(self.repository.get_delivery_run_sheet(self.sheet.run_sheet_id))))
        self.assertEqual(export_before, self.export_cells())
        self.assertEqual(1, len(self.cancellations()))

    def export_cells(self):
        sheet = self.service.get_saved_delivery_run_sheet_for_export(self.sheet.run_sheet_id)
        workbook = load_workbook(io.BytesIO(build_delivery_run_sheet_excel(sheet)))
        return [(page.title, [(cell.coordinate, cell.value, cell.style_id)
                             for row in page for cell in row if cell.value is not None])
                for page in workbook]

    def test_delivered_and_other_non_active_statuses_cannot_cancel(self):
        self.close_sheet()
        self.assert_rejected("CLOSE-ORD-1")
        for status in ("FINALIZED", "ARCHIVED"):
            with self.subTest(status=status):
                original = self.repository.get_order("CLOSE-ORD-3")
                self.repository.update_order(replace(original, status=status))
                self.assert_rejected(original.order_id)
                with self.assertRaisesRegex(ValueError, "Only ACTIVE"):
                    self.service.order_service.cancel_order(original.order_id)

    def test_returned_reassigned_on_another_date_rejected(self):
        self.close_sheet()
        self.repository.upsert_assignment("2026-08-01", "ORDER", "CLOSE-ORD-3", "CLOSE-DRIVER", "trip1")
        self.assert_rejected("CLOSE-ORD-3")

    def recapture(self):
        self.repository.upsert_assignment(closeout.NEXT_DELIVERY_DATE, "ORDER", "CLOSE-ORD-3", "CLOSE-DRIVER", "trip1")
        return self.service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(
            trip_no="trip1", delivery_date=closeout.NEXT_DELIVERY_DATE, driver_id="CLOSE-DRIVER",
        ))

    def test_returned_recaptured_generated_then_saved_open_rejected(self):
        self.close_sheet()
        self.assertTrue(self.eligibility()["can_cancel"])
        generated = self.recapture()
        self.assert_rejected("CLOSE-ORD-3", DeliveryRunSheetLockedError)
        self.service.save_generated_delivery_run_sheet(generated.run_sheet_id, SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_id=self.identity.account_id, saved_by_account_name=self.identity.account_name,
        ))
        self.assert_rejected("CLOSE-ORD-3", DeliveryRunSheetLockedError)

    def test_repeated_return_through_per_trip_sheet_is_cancellable(self):
        self.close_sheet()
        generated = self.recapture()
        saved = self.service.save_generated_delivery_run_sheet(generated.run_sheet_id, SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_id=self.identity.account_id, saved_by_account_name=self.identity.account_name,
        ))
        rows = [CloseDeliveryRunSheetRowRequest(
            run_sheet_row_id=row.row_id, outcome="RETURN_TO_POOL", reason_code="TIME_RAN_OUT",
            next_delivery_date="2026-07-30",
        ) for trip in saved.trips for row in trip.orders]
        self.service.close_saved_delivery_run_sheet(saved.run_sheet_id, CloseDeliveryRunSheetRequest(rows=rows), self.identity)
        self.assertTrue(self.eligibility()["can_cancel"])
        self.assertEqual("CANCELLED", self.service.cancel_delivery_order("CLOSE-ORD-3").status)

    def test_ordinary_active_order_keeps_existing_cancellation(self):
        template = self.repository.get_order("CLOSE-ORD-3")
        self.repository.create_order(replace(template, order_id="ORDINARY"))
        result = self.eligibility("ORDINARY")
        self.assertTrue(result["can_cancel"])
        self.assertFalse(result["has_run_sheet_history"])
        self.assertFalse(result["returned_to_pool"])
        self.assertEqual("CANCELLED", self.service.cancel_delivery_order("ORDINARY").status)

    def test_legacy_closed_missing_outcome_fails_safely(self):
        self.close_sheet()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM delivery_run_sheet_outcomes WHERE order_id = 'CLOSE-ORD-3'")
        self.assertIn("verified RETURN_TO_POOL", self.eligibility()["reason"])
        self.assert_rejected("CLOSE-ORD-3")

    def test_legacy_closed_missing_close_timestamp_fails_safely(self):
        self.close_sheet()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE delivery_run_sheets SET closed_at = NULL")
        self.assert_rejected("CLOSE-ORD-3")

    def test_duplicate_and_missing_cancellation_do_not_duplicate_audit(self):
        self.close_sheet()
        first = self.service.cancel_delivery_order("CLOSE-ORD-3")
        self.assertEqual(first, self.service.cancel_delivery_order("CLOSE-ORD-3"))
        self.assertEqual(1, len(self.cancellations()))
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.service.cancel_delivery_order("missing")
        self.assertEqual(1, len(self.cancellations()))

    def test_write_failure_rolls_back_before_audit(self):
        self.close_sheet()
        original = self.repository.cancel_order
        before = self.history(), list(self.logbook.entries)
        def fail_after_write(order_id):
            original(order_id)
            raise RuntimeError("injected cancellation persistence failure")
        with patch.object(self.repository, "cancel_order", side_effect=fail_after_write):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.service.cancel_delivery_order("CLOSE-ORD-3")
        self.assertEqual("ACTIVE", self.repository.get_order("CLOSE-ORD-3").status)
        self.assertEqual(before, (self.history(), self.logbook.entries))

    def test_eligibility_read_does_not_write_database(self):
        self.close_sheet()
        before = hashlib.sha256(self.path.read_bytes()).hexdigest(), self.path.stat().st_mtime_ns
        self.assertTrue(self.eligibility()["can_cancel"])
        self.assertEqual(before, (hashlib.sha256(self.path.read_bytes()).hexdigest(), self.path.stat().st_mtime_ns))

    def test_api_authentication_and_stale_enabled_button_are_enforced(self):
        self.close_sheet()
        module = importlib.import_module("backend.api.manual_dispatch")
        app = FastAPI()
        app.include_router(module.router)
        with patch.object(module, "service", self.service), TestClient(app) as client:
            path = "/api/manual-dispatch/delivery/orders/CLOSE-ORD-3"
            self.assertEqual(401, client.get(path + "/cancellation-eligibility").status_code)
            self.assertEqual(401, client.post(path + "/cancel").status_code)
            authenticate_test_client(client, self.service, self.identity)
            self.assertTrue(client.get(path + "/cancellation-eligibility").json()["can_cancel"])
            self.recapture()
            self.assertEqual(409, client.post(path + "/cancel").status_code)
            self.assertEqual("ACTIVE", self.repository.get_order("CLOSE-ORD-3").status)
            delivered = client.post("/api/manual-dispatch/delivery/orders/CLOSE-ORD-1/cancel")
            self.assertEqual(400, delivered.status_code)
            self.assertEqual("FINALIZED", self.repository.get_order("CLOSE-ORD-1").status)
            self.assertEqual([], self.cancellations())

    def test_in_memory_return_and_finalized_parity(self):
        repository = InMemoryManualDispatchRepository()
        service, identity, sheet, logbook = self.fixture._build_saved_sheet(repository)
        service.close_saved_delivery_run_sheet(sheet.run_sheet_id, self.fixture._valid_request(sheet), identity)
        self.assertTrue(service.get_delivery_order_cancellation_eligibility("CLOSE-ORD-3")["can_cancel"])
        self.assertEqual("CANCELLED", service.cancel_delivery_order("CLOSE-ORD-3").status)
        service.cancel_delivery_order("CLOSE-ORD-3")
        self.assertEqual(1, sum(entry["action"] == "ORDER_CANCELLED" for entry in logbook.entries))
        with self.assertRaises(ValueError):
            service.cancel_delivery_order("CLOSE-ORD-1")
        self.assertEqual("FINALIZED", repository.get_order("CLOSE-ORD-1").status)
