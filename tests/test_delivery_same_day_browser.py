import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import expect, sync_playwright

from tests.test_attache_carton_packaging import carton_payload
from tests.test_delivery_same_day_dates import SameDayDateFixture, TODAY, TOMORROW


ROOT = Path(__file__).resolve().parents[1]


class DeliverySameDayBrowserTest(SameDayDateFixture, unittest.TestCase):
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
        super().setUp()
        self.context = self.browser.new_context(timezone_id="America/Los_Angeles", service_workers="block")
        self.addCleanup(self.context.close)
        self.context.add_init_script("""
            const RealDate = Date;
            const instant = RealDate.parse('2026-11-11T13:05:00Z');
            globalThis.Date = class extends RealDate {
              constructor(...args) { super(...(args.length ? args : [instant])); }
              static now() { return instant; }
            };
        """)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10000)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.route("**/*", self.serve)

    def serve(self, route):
        request = route.request
        url = urlsplit(request.url)
        if url.hostname != "same-day-delivery.test":
            self.errors.append("Unexpected external browser request")
            route.abort()
            return
        if url.path.startswith("/api/"):
            response = self.client.request(
                request.method, url.path + ("?" + url.query if url.query else ""),
                content=request.post_data_buffer,
                headers={"content-type": request.headers.get("content-type", "application/json")},
            )
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
            self.errors.append("Unexpected browser asset")
            route.abort()

    def open_task_pool(self):
        self.page.goto("http://same-day-delivery.test/", wait_until="networkidle")
        if self.page.locator("a.workspace-home-card-delivery").is_visible():
            self.page.locator("a.workspace-home-card-delivery").click()
        self.page.get_by_role("link", name="Task Pool", exact=True).click()
        self.assertEqual("2026-11-11", self.page.evaluate("""() => {
            const d = new Date();
            return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        }"""))

    def assert_card_after_reload(self, order_id):
        card = self.page.locator(f'.workspace-order-card[data-order-id="{order_id}"]')
        expect(card.get_by_text("Delivery Date: " + TODAY, exact=True)).to_be_visible()
        self.page.reload(wait_until="networkidle")
        if self.page.locator("a.workspace-home-card-delivery").is_visible():
            self.page.locator("a.workspace-home-card-delivery").click()
        self.page.get_by_role("link", name="Task Pool", exact=True).click()
        expect(card.get_by_text("Delivery Date: " + TODAY, exact=True)).to_be_visible()
        self.assertEqual(TODAY, self.refreshed(order_id)["delivery_date"])
        self.assertEqual([], self.errors)

    def test_task_pool_native_date_input_edit_persists_across_refresh(self):
        order = self.create()
        self.open_task_pool()
        self.page.locator(f'.workspace-order-card[data-order-id="{order["order_id"]}"]').click()
        self.page.get_by_role("button", name="Edit Order", exact=True).click()
        modal = self.page.locator(".workspace-modal-backdrop")
        field = modal.get_by_label("Delivery Date", exact=True)
        field.fill(TODAY)
        self.assertTrue(field.evaluate("element => element.checkValidity()"))
        modal.get_by_role("button", name="Save Changes", exact=True).click()
        expect(modal).to_have_count(0)
        self.assert_card_after_reload(order["order_id"])

    def import_today(self, source):
        payload = carton_payload()
        payload.update(invoice_number="197777", invoice_date=TODAY,
                       terms_description="30 DAYS", outstanding_balance=0)
        self.bridge.lookup_invoice.return_value = payload
        self.bridge.lookup_invoices_from_date.return_value = [payload]
        self.open_task_pool()
        self.page.get_by_role("button", name="Import Delivery Document", exact=True).click()
        if source == "direct":
            self.page.get_by_role("button", name=re.compile("^Import from Attaché")).click()
            self.page.locator(".workspace-attache-direct-lookup input").fill("197777")
            self.page.locator(".workspace-modal-backdrop").get_by_role(
                "button", name="Find Invoice", exact=True).click()
        else:
            self.page.get_by_role("button", name=re.compile("^Import Today & Future Invoices")).click()
            self.page.get_by_role("button", name="Load Today & Future Invoices", exact=True).click()
        card = self.page.locator(".workspace-attache-review-card")
        expect(card).to_have_count(1)
        card.get_by_role("button", name="Expand", exact=True).click()
        field = card.get_by_label("Delivery Date", exact=True)
        expect(field).to_have_value(TOMORROW)
        field.fill(TODAY)
        self.assertTrue(field.evaluate("element => element.checkValidity()"))
        self.page.get_by_role("button", name=re.compile("^Confirm Import ")).click()
        modal = self.page.locator(".workspace-modal-backdrop")
        expect(modal.get_by_text(re.compile("Imported 1 Delivery Orders"))).to_be_visible()
        modal.get_by_role("button", name="Cancel", exact=True).click()
        expect(self.page.locator(".workspace-modal-backdrop")).to_have_count(0)
        order = next(item for item in self.repository.list_orders() if item.invoice_number == "197777")
        self.assertEqual(TODAY, order.delivery_date)
        self.assert_card_after_reload(order.order_id)

    def test_direct_import_manual_today_survives_confirm_and_refresh(self):
        self.import_today("direct")

    def test_today_future_import_manual_today_preserves_eligibility_proof_and_refresh(self):
        self.import_today("current-future")
