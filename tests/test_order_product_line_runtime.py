import json
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright


FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "frontend"
ORDER = {
    "order_id": "SYN-ORDER",
    "invoice_number": "SYN-INV-1",
    "company_name": "Synthetic customer",
    "delivery_address": "1 Synthetic Road",
    "suburb": "TEST SUBURB",
    "postcode": "3000",
    "delivery_date": "2026-10-06",
    "urgency": "Normal",
    "delivery_area": "LOCAL",
    "auto_delivery_area": "LOCAL",
    "delivery_area_source": "AUTO",
    "product_lines": [
        {"product_name": name, "quantity": index + 1, "unit": "KG"}
        for index, name in enumerate(("Alpha", "Beta", "Gamma"))
    ],
}


class OrderProductLineRuntimeTest(unittest.TestCase):
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
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 760}, service_workers="block"
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.page_errors = []
        self.api_requests = []
        self.unexpected_requests = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.route("**/*", self._serve_frontend)
        self.page.goto("http://order-product-line.test/", wait_until="networkidle")
        self.page.locator("a.workspace-home-card-delivery").click()
        self.page.wait_for_load_state("networkidle")
        self.assertEqual([], self.page_errors)
        self.assertEqual([], self.unexpected_requests)

    def _serve_frontend(self, route):
        request = route.request
        url = urlsplit(request.url)
        if url.hostname != "order-product-line.test":
            self.unexpected_requests.append(request.url)
            route.abort()
            return
        if url.path.startswith("/api/"):
            self.api_requests.append((request.method, url.path))
            responses = {
                "/api/manual-dispatch/auth/session": {
                    "account_id": "SYN-ACCOUNT", "account_name": "Synthetic operator"
                },
                "/api/manual-dispatch/workspace-migration-status": {
                    "delivery_ready": True, "opshop_ready": True
                },
                "/api/manual-dispatch/delivery/board": {
                    "orders": [ORDER], "drivers": [], "vehicles": [],
                    "assignments": [], "driver_vehicle_assignments": [],
                },
            }
            if request.method != "GET" or url.path not in responses:
                self.unexpected_requests.append((request.method, request.url))
                route.abort()
            else:
                route.fulfill(json=responses[url.path])
            return
        if url.path == "/favicon.ico":
            route.fulfill(status=204)
            return
        path = (FRONTEND_ROOT / unquote(url.path).lstrip("/")).resolve()
        if url.path == "/":
            path = FRONTEND_ROOT / "index.html"
        content_types = {
            ".html": "text/html", ".js": "application/javascript", ".css": "text/css"
        }
        if (not path.is_relative_to(FRONTEND_ROOT) or not path.is_file()
                or path.suffix not in content_types):
            self.unexpected_requests.append(request.url)
            route.abort()
            return
        source = path.read_text(encoding="utf-8")
        route.fulfill(body=source, content_type=content_types[path.suffix])

    def test_add_delivery_order_keeps_real_modal_and_controls(self):
        self._assert_runtime_identity("add")

    def test_edit_delivery_order_keeps_real_modal_and_controls(self):
        self._assert_runtime_identity("edit")

    def _assert_runtime_identity(self, mode):
        if mode == "add":
            self.page.get_by_role("button", name="Add Order", exact=True).click()
        else:
            self.page.locator('.workspace-order-card[data-order-id="SYN-ORDER"]').click()
            self.page.get_by_role("button", name="Edit Order", exact=True).click()
        config = {
            "modal": "#workspace-root .workspace-modal-order",
            "scroll": ".workspace-modal-body",
            "editor": ".workspace-product-line-editor",
            "row": ".workspace-product-line-table-row",
            "remove": ".workspace-product-line-remove",
        }
        modal = self.page.locator(config["modal"])
        add = modal.get_by_role("button", name="Add Product Line", exact=True)
        if mode == "add":
            for _ in range(3):
                add.click()
        self.page.wait_for_timeout(30)
        self.page.evaluate(
            """config => {
              const modal = document.querySelector(config.modal);
              if (!modal) throw new Error('Runtime modal is missing');
              const editor = modal.querySelector(config.editor);
              const scroll = config.scroll ? modal.querySelector(config.scroll) : modal;
              const form = modal.querySelector('form');
              const controls = [...form.querySelectorAll('input, select, textarea')]
                .filter(node => !editor.contains(node));
              for (const node of controls) {
                if (node.name === 'company_name' || node.tagName === 'TEXTAREA'
                    || node.closest('label')?.textContent === 'Company Name') {
                  node.value = 'Entered synthetic value';
                  node.dispatchEvent(new Event('input', { bubbles: true }));
                }
              }
              const button = [...editor.querySelectorAll('button')]
                .find(node => node.textContent.trim() === 'Add Product Line');
              scroll.scrollTop += button.getBoundingClientRect().top
                - scroll.getBoundingClientRect().top - 40;
              if (scroll.scrollTop <= 0) throw new Error('Modal is not scrolled');
              const tableScroll = editor.querySelector('.workspace-product-line-table-scroll');
              if (tableScroll) tableScroll.scrollLeft = 100;
              window.runtimeBefore = {
                config, modal, scroll, form, editor,
                workspace: document.querySelector('#workspace-root').firstElementChild,
                controls: controls.map(node => [node, node.value]),
                buttons: [...modal.querySelectorAll('button')].filter(node => !editor.contains(node)),
                rows: [...editor.querySelectorAll(config.row)],
                scrollTop: scroll.scrollTop, tableScroll,
                scrollLeft: tableScroll?.scrollLeft,
              };
              window.forbiddenCalls = [];
              const forbid = name => () => {
                window.forbiddenCalls.push(name);
                throw new Error('Product change used ' + name);
              };
              for (const property of ['scrollTop', 'scrollLeft']) {
                const descriptor = Object.getOwnPropertyDescriptor(Element.prototype, property);
                Object.defineProperty(Element.prototype, property, {
                  ...descriptor, set: forbid(property),
                });
              }
              window.scrollTo = forbid('window.scrollTo');
              Element.prototype.scrollTo = forbid('scrollTo');
              Element.prototype.scrollIntoView = forbid('scrollIntoView');
              HTMLElement.prototype.focus = forbid('focus');
              window.requestAnimationFrame = forbid('requestAnimationFrame');
            }""",
            config,
        )
        self.api_requests.clear()
        for count in (4, 5, 6):
            add.click()
            self._assert_stable(count)
        rows = modal.locator(config["row"])
        middle = rows.nth(1)
        removed_id = middle.get_attribute("data-product-line-id")
        middle.locator(config["remove"]).evaluate("button => button.click()")
        self._assert_stable(5)
        self.assertEqual(0, modal.locator(
            f'{config["row"]}[data-product-line-id="{removed_id}"]'
        ).count())
        self.page.evaluate(
            """() => {
              const before = window.runtimeBefore;
              const rows = [...before.editor.querySelectorAll(before.config.row)];
              if (rows[0] !== before.rows[0] || rows[1] !== before.rows[2]) {
                throw new Error('Middle removal recreated surviving product rows');
              }
              rows.forEach((row, index) => {
                if (row.querySelector('.workspace-product-cell-sequence').textContent !== String(index + 1)
                    || row.querySelector('button').getAttribute('aria-label') !== `Remove product line ${index + 1}`) {
                  throw new Error('Product sequence/accessibility labels were not updated');
                }
              });
            }"""
        )
        rows.nth(1).get_by_label("Actual quantity", exact=True).evaluate(
            """input => {
              input.value = '7';
              input.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        self._assert_stable(5)
        self.assertIn("7 KG" if mode == "add" else "8 KG",
                      modal.locator(".workspace-product-line-total").inner_text())
        rows.nth(1).locator(config["remove"]).evaluate("button => button.click()")
        self._assert_stable(4)
        count = self.page.evaluate(
            """async key => {
              const { state } = await import('/js/state/app-state.js');
              return state[key].product_lines.length;
            }""", "deliveryOrderForm",
        )
        self.assertEqual(4, count)
        self.assertEqual([], self.api_requests)
        self.assertEqual([], self.unexpected_requests)
        self.assertEqual([], self.page_errors)

    def _assert_stable(self, count):
        self.page.evaluate(
            """count => {
              const before = window.runtimeBefore;
              const after = document.querySelector(before.config.modal);
              if (before.modal !== after) throw new Error('Order modal was replaced');
              const scroll = before.config.scroll ? after.querySelector(before.config.scroll) : after;
              if (scroll !== before.scroll || scroll.scrollTop !== before.scrollTop) {
                throw new Error('Modal scroll node or natural scroll position changed');
              }
              if (after.querySelector('form') !== before.form
                  || document.querySelector('#workspace-root').firstElementChild !== before.workspace
                  || before.controls.some(([node, value]) => !before.form.contains(node) || node.value !== value)
                  || before.buttons.some(node => !after.contains(node))) {
                throw new Error('Unrelated form/workspace DOM nodes or values changed');
              }
              const editor = after.querySelector(before.config.editor);
              if (editor.querySelectorAll(before.config.row).length !== count) {
                throw new Error('Visible product row count is incorrect');
              }
              if (editor !== before.editor
                  || editor.querySelector('.workspace-product-line-table-scroll') !== before.tableScroll
                  || before.tableScroll.scrollLeft !== before.scrollLeft) {
                throw new Error('Product editor or horizontal scroll container was replaced');
              }
              if (window.forbiddenCalls.length) throw new Error(window.forbiddenCalls.join(', '));
            }""", count,
        )


if __name__ == "__main__":
    unittest.main()
