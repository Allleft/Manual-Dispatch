import importlib
import json
import os
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import DeliveryWorkspaceAssignOrderRequest
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client
from tests.test_delivery_per_trip_persistence import DATE


ROOT = Path(__file__).resolve().parents[1]


class DeliveryPerTripBrowserAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="delivery-stage3-browser-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            self.repository = SQLiteManualDispatchRepository(self.root / "acceptance.sqlite3")
        self.service = ManualDispatchService(self.repository, LogbookFileService(self.root / "logbook"))
        for number, trip in enumerate(("trip1", "trip2"), 1):
            order = self.repository.get_order(f"ORD-00{number}")
            self.repository.update_order(replace(order, delivery_date=DATE))
            self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                order_id=order.order_id, driver_id="D001", trip_no=trip,
            ))
        api = importlib.import_module("backend.api.manual_dispatch")
        previous = api.service
        api.service = self.service
        self.addCleanup(setattr, api, "service", previous)
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        authenticate_test_client(self.client, self.service)
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000}, service_workers="block")
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10000)
        self.errors = []
        self.requests = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.route("**/*", self.serve)
        self.page.goto("http://per-trip-acceptance.test/", wait_until="networkidle")
        self.page.locator("a.workspace-home-card-delivery").click()
        self.page.get_by_role("link", name="Trip Summary", exact=True).click()
        self.page.get_by_label("Delivery date", exact=True).fill(DATE)
        self.page.get_by_label("Delivery date", exact=True).dispatch_event("change")
        expect(self.panel("trip1").get_by_text("INV-1001", exact=False)).to_be_visible()

    def serve(self, route):
        request = route.request
        url = urlsplit(request.url)
        if url.hostname != "per-trip-acceptance.test":
            self.errors.append(f"Unexpected network request: {request.url}")
            route.abort()
            return
        if url.path.startswith("/api/"):
            payload = request.post_data_json if request.post_data else None
            self.requests.append((request.method, url.path, payload))
            response = self.client.request(request.method, url.path + ("?" + url.query if url.query else ""), json=payload)
            route.fulfill(status=response.status_code, body=response.content,
                          content_type=response.headers.get("content-type", "application/json"))
            return
        if url.path == "/favicon.ico":
            route.fulfill(status=204)
            return
        root = ROOT / "frontend"
        path = (root / ("index.html" if url.path == "/" else unquote(url.path).lstrip("/"))).resolve()
        types = {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}
        if path.is_relative_to(root) and path.is_file() and path.suffix in types:
            route.fulfill(body=path.read_text(encoding="utf-8"), content_type=types[path.suffix])
        else:
            self.errors.append(f"Unexpected asset: {url.path}")
            route.abort()

    def panel(self, trip):
        return self.page.locator(f'.workspace-trip-panel[data-driver-id="D001"][data-trip-no="{trip}"]')

    def selected(self, trip):
        return self.repository.get_delivery_trip_vehicle_assignment(DATE, "D001", trip).vehicle_id

    def choose(self, trip, vehicle):
        self.panel(trip).locator("select").select_option(vehicle)
        expect(self.panel(trip).locator("select")).to_be_enabled()
        self.assertEqual(vehicle, self.selected(trip))

    def generate(self, trip):
        label = "Trip 1" if trip == "trip1" else "Trip 2"
        self.panel(trip).get_by_role("button", name=f"Generate {label} Run Sheet", exact=True).click()
        modal = self.page.locator(".workspace-modal-backdrop")
        self.assertEqual(1, modal.locator(".workspace-generation-preview-row").count())
        self.assertIn(label, modal.inner_text())
        modal.get_by_role("button", name="Confirm Generate Run Sheet", exact=True).click()
        expect(modal).to_have_count(0)
        expect(self.panel(trip).locator("select")).to_be_disabled()
        return next(sheet for sheet in self.service.list_delivery_run_sheets(delivery_date=DATE) if sheet.trip_no == trip)

    def test_real_frontend_independent_trip_vehicle_generate_save_and_close(self):
        self.assertEqual("John", self.repository.get_driver("D001").name)
        self.choose("trip1", "V001")
        self.choose("trip2", "V001")
        self.assertEqual(["V001", "V001"], [self.selected(trip) for trip in ("trip1", "trip2")])
        self.choose("trip2", "V002")
        self.assertEqual("V001", self.selected("trip1"))
        first = self.generate("trip1")
        expect(self.panel("trip2").locator("select")).to_be_enabled()
        expect(self.panel("trip2").locator("select")).to_have_value("V002")
        expect(self.panel("trip2").get_by_text("INV-1002", exact=False)).to_be_visible()
        second = self.generate("trip2")
        self.assertNotEqual(first.run_sheet_id, second.run_sheet_id)
        for sheet, order, vehicle in ((first, "ORD-001", "V001"), (second, "ORD-002", "V002")):
            self.assertEqual([order], [row.task_id for trip in sheet.trips for row in trip.orders])
            self.assertEqual(vehicle, sheet.vehicle_id)
        self.page.goto("http://per-trip-acceptance.test/#delivery/run-sheet", wait_until="networkidle")
        cards = self.page.locator(".workspace-run-sheet-document-card")
        expect(cards).to_have_count(2)
        first_card = cards.filter(has=self.page.get_by_role("heading", name="John — Trip 1", exact=True))
        second_card = cards.filter(has=self.page.get_by_role("heading", name="John — Trip 2", exact=True))
        self.assertIn(first.vehicle_rego_snapshot, first_card.inner_text())
        self.assertIn(second.vehicle_rego_snapshot, second_card.inner_text())
        first_card.get_by_role("button", name="Save Run Sheet", exact=True).click()
        expect(first_card.get_by_role("button", name="Close Run Sheet", exact=True)).to_be_visible()
        self.assertEqual("GENERATED", self.repository.get_delivery_run_sheet(second.run_sheet_id).status)
        second_card.get_by_role("button", name="Save Run Sheet", exact=True).click()
        expect(second_card.get_by_role("button", name="Close Run Sheet", exact=True)).to_be_visible()
        sibling = deepcopy(self.repository.get_delivery_run_sheet(second.run_sheet_id))
        sibling_order = deepcopy(self.repository.get_order("ORD-002"))
        first_card.get_by_role("button", name="Close Run Sheet", exact=True).click()
        closeout = self.page.locator(".workspace-modal-backdrop")
        closeout.get_by_role("button", name="Mark All Delivered", exact=True).click()
        closeout.get_by_role("button", name="Review and Close", exact=True).click()
        expect(closeout).to_have_count(0)
        self.assertEqual("CLOSED", self.repository.get_delivery_run_sheet(first.run_sheet_id).execution_status)
        self.assertEqual(sibling, self.repository.get_delivery_run_sheet(second.run_sheet_id))
        self.assertEqual(sibling_order, self.repository.get_order("ORD-002"))
        self.assertEqual("V002", self.selected("trip2"))
        generated = [payload for method, path, payload in self.requests if method == "POST" and path.endswith("/run-sheets/generated")]
        self.assertEqual(["trip1", "trip2"], [payload["trip_no"] for payload in generated])
        self.assertFalse(any("day-vehicle" in path for _, path, _ in self.requests))
        self.assertEqual([], self.errors)
        output = os.environ.get("MANUAL_DISPATCH_STAGE3_ACCEPTANCE_OUTPUT")
        if output:
            target = Path(output)
            target.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(target / "stage3-accepted.png"), full_page=True)
            (target / "browser-acceptance.json").write_text(json.dumps({
                "result": "PASS", "db": str(self.repository.db_path), "logbook": str(self.service.logbook.base_dir),
                "run_sheet_ids": [first.run_sheet_id, second.run_sheet_id], "generation_payloads": generated,
                "sibling_unchanged": True, "page_errors": self.errors,
            }, indent=2), encoding="utf-8")
