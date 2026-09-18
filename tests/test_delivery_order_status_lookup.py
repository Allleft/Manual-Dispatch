import importlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.repositories.sqlite.snapshot_repository_mixin import DELIVERY_ORDER_HISTORY_SQL
from backend.schemas import (
    CloseDeliveryRunSheetRequest, CloseDeliveryRunSheetRowRequest, Driver, Order,
    GenerateDeliveryRunSheetRequest, RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest, to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client


DATE = "2026-09-17"
NEXT_DATE = "2026-09-18"


class LookupContract:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lookup-")
        self.addCleanup(self.temp.cleanup)
        self.repository = self.make_repository()
        self.logbook = Mock()
        self.service = ManualDispatchService(self.repository, logbook=self.logbook)
        self.identity = self.service.register_operator_account(RegisterOperatorAccountRequest(
            account_name="Lookup QA", password="secret123", confirm_password="secret123",
        ))
        self.repository.create_driver(Driver(
            "LOOKUP-DRIVER", "Lookup Driver", None, None, True, None, False,
        ))
        self.order = Order(
            order_id="LOOKUP-ORDER", invoice_number="001234", order_no="QA-ORDER",
            company_name="Synthetic Lookup Customer", phone=None,
            delivery_address="1 QA Street", suburb="Dandenong", postcode="3175",
            delivery_date=DATE, zone="South East", urgency="normal", preferred_driver_id=None,
            pallet_quantity=1, loose_bags_quantity=2, carton_quantity=3,
            start_time=None, end_time=None, note=None,
        )
        self.repository.create_order(self.order)

    def lookup(self, invoice="001234"):
        return self.service.lookup_delivery_orders_by_invoice(invoice)

    def match(self):
        result = self.lookup()
        self.assertEqual(1, result.match_count)
        return result.orders[0]

    def assign(self, dispatch_date="1999-01-01", trip="trip2"):
        self.repository.upsert_assignment(
            dispatch_date, "ORDER", self.order.order_id, "LOOKUP-DRIVER", trip,
        )

    def generate(self):
        return self.service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(
            dispatch_date="1999-01-01",
            delivery_date=self.repository.get_order(self.order.order_id).delivery_date,
            driver_id="LOOKUP-DRIVER",
        ))

    def save(self, sheet):
        return self.service.save_generated_delivery_run_sheet(
            sheet.run_sheet_id, SaveGeneratedWorkspaceSnapshotRequest(
                self.identity.account_name, self.identity.account_id,
            ),
        )

    def close(self, sheet, outcome="RETURN_TO_POOL"):
        return self.service.close_saved_delivery_run_sheet(
            sheet.run_sheet_id, CloseDeliveryRunSheetRequest([
                CloseDeliveryRunSheetRowRequest(
                    sheet.trips[0].orders[0].row_id, outcome,
                    reason_code="TIME_RAN_OUT" if outcome == "RETURN_TO_POOL" else None,
                    note="Synthetic QA note",
                    next_delivery_date=NEXT_DATE if outcome == "RETURN_TO_POOL" else None,
                ),
            ]), self.identity,
        )

    def returned(self):
        self.assign()
        return self.close(self.save(self.generate()))

    def test_unknown_invoice(self):
        self.assertEqual({"invoice_number": "UNKNOWN", "match_count": 0, "orders": []},
                         to_dict(self.lookup("UNKNOWN")))

    def test_unassigned_is_not_date_filtered(self):
        self.assertEqual("UNASSIGNED", self.match().current_status)
        self.repository.update_order(replace(self.order, delivery_date="1990-01-01"))
        self.assertEqual("1990-01-01", self.match().order.delivery_date)

    def test_assignment_context_is_global(self):
        self.assign()
        match = self.match()
        self.assertEqual("ASSIGNED", match.current_status)
        self.assertEqual("Lookup Driver", match.assignment.driver_name)
        self.assertEqual("LOOKUP-DRIVER", match.assignment.driver_id)
        self.assertEqual("1999-01-01", match.assignment.dispatch_date)
        self.assertEqual("trip2", match.assignment.trip_no)

    def test_generated_outranks_assignment(self):
        self.assign()
        sheet = self.generate()
        match = self.match()
        self.assertEqual("RUN_SHEET_GENERATED", match.current_status)
        self.assertIsNotNone(match.assignment)
        self.assertEqual(sheet.run_sheet_id, match.active_run_sheet.run_sheet_id)

    def test_saved_open_outranks_assignment(self):
        self.assign()
        self.save(self.generate())
        self.assertEqual("RUN_SHEET_SAVED_OPEN", self.match().current_status)
        self.assertEqual("OPEN", self.match().active_run_sheet.execution_status)

    def test_delivered_retains_closeout_evidence(self):
        self.assign()
        sheet = self.close(self.save(self.generate()), "DELIVERED")
        match = self.match()
        self.assertEqual("DELIVERED", match.current_status)
        self.assertEqual("FINALIZED", match.order.status)
        self.assertIsNone(match.assignment)
        self.assertIsNone(match.active_run_sheet)
        self.assertEqual(sheet.run_sheet_id, match.latest_closeout.run_sheet_id)
        self.assertEqual("Lookup QA", match.latest_closeout.recorded_by_account_name)

    def test_returned_to_pool(self):
        self.returned()
        match = self.match()
        self.assertEqual("RETURNED_TO_POOL", match.current_status)
        self.assertEqual("ACTIVE", match.order.status)
        self.assertEqual(NEXT_DATE, match.order.delivery_date)
        self.assertIsNone(match.assignment)
        self.assertEqual("TIME_RAN_OUT", match.latest_closeout.reason_code)
        self.assertEqual("Synthetic QA note", match.latest_closeout.note)
        self.assertEqual(DATE, match.latest_closeout.delivery_date)
        self.assertEqual(NEXT_DATE, match.latest_closeout.next_delivery_date)

    def test_return_reassign(self):
        self.returned()
        self.assign(dispatch_date="2000-02-02", trip="trip1")
        match = self.match()
        self.assertEqual("ASSIGNED", match.current_status)
        self.assertEqual("trip1", match.assignment.trip_no)
        self.assertEqual("RETURN_TO_POOL", match.latest_closeout.outcome)

    def test_return_reassign_new_run_sheet(self):
        self.returned()
        self.assign()
        sheet = self.generate()
        self.assertEqual("RUN_SHEET_GENERATED", self.match().current_status)
        self.save(sheet)
        match = self.match()
        self.assertEqual("RUN_SHEET_SAVED_OPEN", match.current_status)
        self.assertEqual("RETURN_TO_POOL", match.latest_closeout.outcome)
        self.assertEqual(2, len(match.run_sheet_history))

    def test_second_successful_delivery(self):
        first = self.returned()
        self.assign()
        second = self.close(self.save(self.generate()), "DELIVERED")
        match = self.match()
        self.assertEqual("DELIVERED", match.current_status)
        self.assertEqual(["DELIVERED", "RETURN_TO_POOL"],
                         [row.outcome for row in match.run_sheet_history])
        self.assertEqual(second.run_sheet_id, match.latest_closeout.run_sheet_id)
        self.assertEqual(first.run_sheet_id, match.run_sheet_history[1].run_sheet_id)

    def test_cancelled(self):
        self.repository.cancel_order(self.order.order_id)
        self.assertEqual("CANCELLED", self.match().current_status)

    def test_cancelled_outranks_stale_open_sheet(self):
        self.assign()
        self.generate()
        self.repository.cancel_order(self.order.order_id)
        self.assertEqual("CANCELLED", self.match().current_status)

    def test_legacy_finalized_does_not_invent_delivery(self):
        self.repository.update_order(replace(self.order, status="FINALIZED"))
        match = self.match()
        self.assertEqual("FINALIZED", match.current_status)
        self.assertIsNone(match.latest_closeout)

    def test_all_duplicate_matches_without_changing_active_list(self):
        for index, status in enumerate(("CANCELLED", "FINALIZED")):
            self.repository.create_order(replace(self.order, order_id=f"DUP-{index}", status=status))
        self.assertEqual(3, self.lookup().match_count)
        self.assertEqual({"CANCELLED", "FINALIZED", "UNASSIGNED"},
                         {row.current_status for row in self.lookup().orders})
        self.assertFalse(any(order.status != "ACTIVE" for order in self.repository.list_orders()))

    def test_trim_preserves_leading_zeroes_and_exact_match(self):
        self.assertEqual("001234", self.lookup(" 001234 ").invoice_number)
        self.assertEqual(1, self.lookup(" 001234 ").match_count)
        for value in ("1234", "00123", "001234%", "' OR 1=1 --"):
            self.assertEqual(0, self.lookup(value).match_count)

    def test_blank_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invoice number is required"):
            self.lookup("  ")

    def test_cancel_generated_returns_to_assigned_without_fake_history(self):
        self.assign()
        sheet = self.generate()
        self.service.cancel_generated_delivery_run_sheet(sheet.run_sheet_id)
        match = self.match()
        self.assertEqual("ASSIGNED", match.current_status)
        self.assertEqual([], match.run_sheet_history)

    def test_order_identity_history_compatibility(self):
        self.assign()
        sheet = self.generate()
        row = sheet.trips[0].orders[0]
        row.task_id = "LEGACY-TASK-REFERENCE"
        row.invoice_number_snapshot = "OLD-INVOICE"
        self.repository.upsert_delivery_run_sheet(sheet)
        match = self.match()
        self.assertEqual("RUN_SHEET_GENERATED", match.current_status)
        self.assertEqual("OLD-INVOICE", match.run_sheet_history[0].invoice_number_snapshot)
        row.task_id = self.order.order_id
        row.order_id_snapshot = None
        self.repository.upsert_delivery_run_sheet(sheet)
        self.assertEqual(1, len(self.match().run_sheet_history))

    def test_multiple_open_rows_fail_explicitly(self):
        self.assign()
        self.generate()
        with patch.object(self.repository, "list_delivery_run_sheet_history_for_order",
                          return_value=[self.match().active_run_sheet] * 2):
            with self.assertRaisesRegex(ValueError, "integrity error"):
                self.lookup()

    def test_lookup_has_no_side_effects_or_board_bridge_logbook_calls(self):
        self.returned()
        before = to_dict(self.match())
        self.logbook.reset_mock()
        with patch.object(self.service, "get_delivery_workspace_board", side_effect=AssertionError("board")), \
             patch.object(self.service.delivery_order_date_rollover_service, "_roll_forward",
                          side_effect=AssertionError("rollover")), \
             patch.object(self.repository, "list_orders", side_effect=AssertionError("active board")), \
             patch.object(self.repository, "list_delivery_run_sheets", side_effect=AssertionError("full history scan")), \
             patch("backend.integrations.attache_bridge_client.AttacheBridgeClient.lookup_invoice",
                   side_effect=AssertionError("Attaché lookup")), \
             patch("backend.integrations.attache_bridge_client.AttacheBridgeClient.lookup_invoices_from_date",
                   side_effect=AssertionError("Attaché batch lookup")):
            for _ in range(2):
                self.assertEqual(before, to_dict(self.match()))
        self.logbook.record.assert_not_called()


class MemoryLookupTest(LookupContract, unittest.TestCase):
    def make_repository(self):
        repository = InMemoryManualDispatchRepository()
        repository.orders = []
        repository.assignments = []
        repository.delivery_run_sheets = []
        return repository


class SQLiteLookupTest(LookupContract, unittest.TestCase):
    def make_repository(self):
        return SQLiteManualDispatchRepository(Path(self.temp.name) / "lookup.sqlite3")

    def test_lookup_database_image_and_read_only_connection(self):
        self.returned()
        with closing(sqlite3.connect(self.repository.db_path)) as connection:
            before = list(connection.iterdump())
        self.lookup()
        with closing(sqlite3.connect(self.repository.db_path)) as connection:
            self.assertEqual(before, list(connection.iterdump()))
        from backend.db.connection import connect
        with self.repository.delivery_order_lookup_snapshot():
            with connect(self.repository.db_path) as connection:
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("UPDATE manual_orders SET status = 'CANCELLED'")

    def test_lookup_indexes_and_query_plan(self):
        with closing(sqlite3.connect(self.repository.db_path)) as connection:
            plan = " ".join(str(row) for row in connection.execute(
                "EXPLAIN QUERY PLAN " + DELIVERY_ORDER_HISTORY_SQL, (self.order.order_id,) * 3,
            ))
            self.assertIn("idx_delivery_run_sheet_rows_task (task_type=? AND task_id=?)", plan)
            self.assertIn("idx_delivery_run_sheet_rows_order_snapshot (task_type=? AND order_id_snapshot=?)", plan)
            invoice_plan = str(list(connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM manual_orders WHERE invoice_number = ?", ("001234",),
            )))
            self.assertIn("idx_manual_orders_invoice_number", invoice_plan)
            indexes = list(connection.execute("PRAGMA index_list(manual_orders)"))
            self.assertEqual(0, next(row[2] for row in indexes if row[1] == "idx_manual_orders_invoice_number"))


class LookupApiTest(SQLiteLookupTest):
    def setUp(self):
        super().setUp()
        module = importlib.import_module("backend.api.manual_dispatch")
        service_patch = patch.object(module, "service", self.service)
        service_patch.start()
        self.addCleanup(service_patch.stop)
        app = FastAPI()
        app.include_router(module.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_auth_blank_no_match_and_all_statuses(self):
        endpoint = "/api/manual-dispatch/delivery/orders/lookup"
        self.assertEqual(401, self.client.get(endpoint, params={"invoice_number": "001234"}).status_code)
        authenticate_test_client(self.client, self.service, self.identity)
        for params in ({}, {"invoice_number": "  "}):
            self.assertEqual(400, self.client.get(endpoint, params=params).status_code)
        response = self.client.get(endpoint, params={"invoice_number": "unknown"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["match_count"])
        self.repository.create_order(replace(self.order, order_id="CANCELLED-QA", status="CANCELLED"))
        self.repository.create_order(replace(self.order, order_id="FINALIZED-QA", status="FINALIZED"))
        response = self.client.get(endpoint, params={"invoice_number": " 001234 "})
        self.assertEqual(200, response.status_code)
        self.assertEqual(3, response.json()["match_count"])
        self.assertEqual({"UNASSIGNED", "CANCELLED", "FINALIZED"},
                         {match["current_status"] for match in response.json()["orders"]})
        self.assertNotIn("password", response.text)

    def test_api_return_then_new_assignment_and_delivered(self):
        authenticate_test_client(self.client, self.service, self.identity)
        self.returned()
        def status():
            response = self.client.get("/api/manual-dispatch/delivery/orders/lookup", params={"invoice_number": "001234"})
            self.assertEqual(200, response.status_code)
            return response.json()["orders"][0]["current_status"]
        self.assertEqual("RETURNED_TO_POOL", status())
        self.assign()
        self.assertEqual("ASSIGNED", status())
        sheet = self.generate()
        self.assertEqual("RUN_SHEET_GENERATED", status())
        self.save(sheet)
        self.assertEqual("RUN_SHEET_SAVED_OPEN", status())
        self.close(sheet, "DELIVERED")
        self.assertEqual("DELIVERED", status())
