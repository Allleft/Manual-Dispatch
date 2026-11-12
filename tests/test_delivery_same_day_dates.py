import importlib
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    CreateDriverRequest, DeliveryWorkspaceAssignOrderRequest,
    GenerateDeliveryRunSheetRequest, SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.manual_dispatch import delivery_import_date
from backend.services.manual_dispatch.delivery_order_date_rollover_service import DeliveryOrderDateRolloverService
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService, MELBOURNE_TIMEZONE
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client
from tests.test_attache_carton_packaging import carton_payload, carton_pdf_bytes
from tests import test_delivery_order_date_rollover as rollover_fixtures


TODAY = "2026-11-12"
TOMORROW = "2026-11-13"
YESTERDAY = "2026-11-11"
API = "/api/manual-dispatch"


class SameDayDateFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="same-day-delivery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            "MANUAL_DISPATCH_TEST_MODE": "1",
            "MANUAL_DISPATCH_TEST_BUSINESS_DATE": TODAY,
            "MANUAL_DISPATCH_SEED_DEMO_DATA": "false",
            "MANUAL_DISPATCH_LOGBOOK_DIR": str(self.root / "logbook"),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.db_path = self.root / "synthetic.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository, LogbookFileService(self.root / "logbook"))
        api = importlib.import_module("backend.api.manual_dispatch")
        service_patch = patch.object(api, "service", self.service)
        service_patch.start()
        self.addCleanup(service_patch.stop)
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        authenticate_test_client(self.client, self.service, account_name="Same-day QA")
        self.bridge = Mock()
        bridge_patch = patch(
            "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
            return_value=self.bridge,
        )
        bridge_patch.start()
        self.addCleanup(bridge_patch.stop)
        self.sequence = 0

    def create(self, selected_date=TOMORROW):
        self.sequence += 1
        response = self.client.post(API + "/delivery/orders", json={
            "invoice_number": str(198000 + self.sequence),
            "company_name": "Synthetic same-day customer",
            "suburb": "HALLAM", "postcode": "3803",
            "delivery_date": selected_date, "invoice_date": YESTERDAY,
            "pallet_quantity": 1,
        })
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def refreshed(self, order_id):
        for _ in range(2):
            response = self.client.get(API + "/delivery/board", params={"dispatch_date": "2026-11-01"})
            self.assertEqual(200, response.status_code, response.text)
            order = next(item for item in response.json()["orders"] if item["order_id"] == order_id)
        stored = SQLiteManualDispatchRepository(self.db_path).get_order(order_id)
        self.assertEqual(stored.delivery_date, order["delivery_date"])
        return order

    def preview(self, source):
        self.sequence += 1
        payload = carton_payload()
        payload.update(invoice_number=str(197000 + self.sequence), invoice_date=TODAY,
                       terms_description="30 DAYS", outstanding_balance=0)
        self.bridge.lookup_invoice.return_value = payload
        self.bridge.lookup_invoices_from_date.return_value = [payload]
        if source == "pdf":
            response = self.client.post(API + "/delivery/orders/import-attache-pdf-preview", files={
                "files": ("synthetic.pdf", carton_pdf_bytes(), "application/pdf"),
            })
        elif source == "direct":
            response = self.client.post(API + "/delivery/orders/import-attache-direct-preview",
                                        json={"invoice_number": payload["invoice_number"]})
        elif source == "current-future":
            response = self.client.post(API + "/delivery/orders/import-attache-current-future-preview")
        else:
            document = Document()
            for line in ("DELIVERY DOCKET: 4450/188888", "DATED: 12/11/2026", "DELIVER TO:",
                         "SYNTHETIC SAME-DAY CUSTOMER", "1 QA ROAD", "HALLAM 3803",
                         "ORDER NUMBER: QA-DATE", "36 X 10KG COLOUR T-SHIRT RAGS", "1 PALLET"):
                document.add_paragraph(line)
            output = BytesIO()
            document.save(output)
            response = self.client.post(API + "/delivery/orders/import-delivery-docket-docx-preview", files={
                "files": ("synthetic.docx", output.getvalue(),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            })
        self.assertEqual(200, response.status_code, response.text)
        row = response.json()["rows"][0]
        self.assertEqual(TOMORROW, row["delivery_date"])
        return row

    def commit(self, row, source):
        kind = {"current-future": "attache-current-future", "docx": "delivery-docket-docx"}.get(source, "attache-pdf")
        body = {"rows": [row]}
        if source == "current-future":
            body["from_date"] = TODAY
        response = self.client.post(API + f"/delivery/orders/import-{kind}-commit", json=body)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(1, response.json()["imported_count"], response.json())
        return response.json()["created_orders"][0]


class DeliverySameDayApiTest(SameDayDateFixture, unittest.TestCase):
    def test_create_and_reload_preserve_today_and_future_and_existing_past_policy(self):
        for selected, expected in ((TODAY, TODAY), (TOMORROW, TOMORROW), (YESTERDAY, TOMORROW)):
            with self.subTest(selected=selected):
                order = self.create(selected)
                self.assertEqual(selected, order["delivery_date"])
                refreshed = self.refreshed(order["order_id"])
                self.assertEqual(expected, refreshed["delivery_date"])
                self.assertEqual(YESTERDAY, refreshed["invoice_date"])

    def test_task_pool_edit_survives_refresh_and_repository_reload(self):
        order = self.create()
        for selected, expected in ((TODAY, TODAY), (TOMORROW, TOMORROW), (YESTERDAY, TOMORROW), (TODAY, TODAY)):
            with self.subTest(selected=selected):
                response = self.client.patch(API + f"/delivery/orders/{order['order_id']}",
                                             json={"delivery_date": selected})
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual(selected, response.json()["delivery_date"])
                self.assertEqual(expected, self.refreshed(order["order_id"])["delivery_date"])

    def test_selected_today_survives_each_import_preview_confirm_and_reload(self):
        for source in ("pdf", "direct", "current-future", "docx"):
            with self.subTest(source=source):
                row = self.preview(source)
                invoice_date = row.get("invoice_date")
                row["delivery_date"] = TODAY
                created = self.commit(row, source)
                self.assertEqual(TODAY, created["delivery_date"])
                refreshed = self.refreshed(created["order_id"])
                self.assertEqual(TODAY, refreshed["delivery_date"])
                if invoice_date:
                    self.assertEqual(invoice_date, refreshed["invoice_date"])

    def test_import_default_future_and_past_policy_remain_unchanged(self):
        for selected, expected in ((TOMORROW, TOMORROW), (YESTERDAY, TOMORROW)):
            row = self.preview("direct")
            row["delivery_date"] = selected
            created = self.commit(row, "direct")
            self.assertEqual(expected, self.refreshed(created["order_id"])["delivery_date"])

    def test_generated_and_saved_locks_still_reject_today_edits(self):
        for status in ("GENERATED", "SAVED"):
            with self.subTest(status=status):
                order = self.create()
                driver = self.service.create_delivery_driver(CreateDriverRequest(name="QA " + status))
                self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                    order_id=order["order_id"], driver_id=driver.driver_id, trip_no="trip1"))
                sheet = self.service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(
                    delivery_date=TOMORROW, driver_id=driver.driver_id, trip_no="trip1"))
                if status == "SAVED":
                    account = self.repository.get_operator_account_by_name("Same-day QA")
                    sheet = self.service.save_generated_delivery_run_sheet(sheet.run_sheet_id,
                        SaveGeneratedWorkspaceSnapshotRequest(saved_by_account_id=account.account_id,
                                                              saved_by_account_name=account.account_name))
                frozen = deepcopy(sheet)
                response = self.client.patch(API + f"/delivery/orders/{order['order_id']}",
                                             json={"delivery_date": TODAY})
                self.assertEqual(409, response.status_code, response.text)
                self.assertEqual(TOMORROW, self.repository.get_order(order["order_id"]).delivery_date)
                self.assertEqual(frozen, self.repository.get_delivery_run_sheet(sheet.run_sheet_id))

    def test_same_day_create_and_edit_still_require_authentication(self):
        order = self.create()
        with TestClient(self.client.app) as unauthenticated:
            self.assertEqual(401, unauthenticated.post(API + "/delivery/orders", json={
                "suburb": "HALLAM", "delivery_date": TODAY,
            }).status_code)
            self.assertEqual(401, unauthenticated.patch(API + f"/delivery/orders/{order['order_id']}",
                                                       json={"delivery_date": TODAY}).status_code)
        self.assertEqual(TOMORROW, self.repository.get_order(order["order_id"]).delivery_date)


class DeliverySameDayTimezoneTest(unittest.TestCase):
    def test_current_day_and_rollover_use_melbourne_at_utc_midnight_boundaries(self):
        cases = (("2026-11-11T12:59:00+00:00", "2026-11-11"),
                 ("2026-11-11T13:01:00+00:00", TODAY),
                 ("2026-06-11T14:01:00+00:00", "2026-06-12"))
        for stamp, today in cases:
            with self.subTest(instant=stamp):
                instant = datetime.fromisoformat(stamp)
                calls = []

                class Clock(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        calls.append(tz)
                        return instant.astimezone(tz)

                with (patch.dict(os.environ, {"MANUAL_DISPATCH_TEST_MODE": "false"}),
                      patch.object(delivery_import_date, "datetime", Clock)):
                    self.assertEqual(today, delivery_import_date.current_melbourne_business_date().isoformat())
                    repository = InMemoryManualDispatchRepository()
                    repository.orders.clear()
                    repository.create_order(rollover_fixtures.DeliveryOrderDateRolloverTest._order("TZ-TODAY", today))
                    self.assertEqual([], DeliveryOrderDateRolloverService(repository)
                                     .roll_forward_eligible_unassigned_delivery_orders())
                    self.assertEqual(today, repository.get_order("TZ-TODAY").delivery_date)
                self.assertTrue(calls and all(tz == MELBOURNE_TIMEZONE for tz in calls))

    def test_weekend_today_stays_today_and_overdue_date_keeps_weekday_rollover(self):
        repository = InMemoryManualDispatchRepository()
        repository.orders.clear()
        repository.create_order(rollover_fixtures.DeliveryOrderDateRolloverTest._order("TODAY", "2026-11-14"))
        repository.create_order(rollover_fixtures.DeliveryOrderDateRolloverTest._order("OVERDUE", "2026-11-13"))
        service = DeliveryOrderDateRolloverService(repository, today_provider=lambda: date(2026, 11, 14))
        service.roll_forward_eligible_unassigned_delivery_orders()
        self.assertEqual("2026-11-14", repository.get_order("TODAY").delivery_date)
        self.assertEqual("2026-11-16", repository.get_order("OVERDUE").delivery_date)
