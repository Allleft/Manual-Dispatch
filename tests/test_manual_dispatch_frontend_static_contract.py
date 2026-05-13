import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class ManualDispatchFrontendStaticContractTest(unittest.TestCase):
    def test_frontend_entry_script_remains_app_module(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('<script type="module" src="app.js"></script>', index_html)
        script_sources = re.findall(r"<script[^>]+src=\"([^\"]+)\"", index_html)
        self.assertEqual(["app.js"], script_sources)

    def test_driver_summary_delivery_date_control_is_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="driver-summary-delivery-date"', index_html)
        self.assertIn('type="date"', index_html)

    def test_task_pool_delivery_date_filter_controls_are_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="task-pool-delivery-date-filter"', index_html)
        self.assertIn('id="clear-task-pool-delivery-date-filter"', index_html)
        self.assertIn("All delivery dates", index_html)

    def test_order_renderers_show_delivery_date_and_edit_form_is_not_read_only(self):
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        trip_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8")
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Delivery Date:", task_pool_renderer)
        self.assertIn("assigned-delivery-date", trip_summary_renderer)
        self.assertIn('createOrderEditField("Delivery Date", "delivery_date"', order_modal_renderer)
        self.assertNotIn("Delivery Date (read-only)", order_modal_renderer)

    def test_phase16_product_detail_controls_are_present(self):
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn('productDetailButton.textContent = "Product Detail"', order_modal_renderer)
        self.assertIn('title.textContent = "Product Details"', order_modal_renderer)
        self.assertIn('addButton.textContent = "Add Product Line"', order_modal_renderer)
        self.assertIn('"Product Details"', final_summary_renderer)

    def test_product_line_typing_updates_state_without_popup_rerender(self):
        order_actions = (
            FRONTEND_ROOT / "js" / "actions" / "order-actions.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "updateProductLines(formKey, nextLines, { rerenderPopup: false });",
            order_actions,
        )
        self.assertGreaterEqual(order_actions.count("{ rerenderPopup: true }"), 2)
        self.assertIn(
            "function updateProductLines(formKey, productLines, { rerenderPopup = true } = {})",
            order_actions,
        )

    def test_frontend_module_import_paths_exist(self):
        frontend_sources = list(FRONTEND_ROOT.rglob("*.js"))
        import_paths = []

        for source_path in frontend_sources:
            source = source_path.read_text(encoding="utf-8")
            for import_path in re.findall(r'from\s+"(\.{1,2}/[^"]+)"', source):
                import_paths.append((source_path, import_path))

        self.assertGreaterEqual(len(import_paths), 1)
        for source_path, import_path in import_paths:
            module_path = (source_path.parent / import_path).resolve()
            self.assertTrue(
                module_path.exists(),
                f"Missing frontend module import from {source_path.name}: {import_path}",
            )

    def test_no_local_storage_or_mapping_apis_are_added_to_frontend_modules(self):
        frontend_sources = list(FRONTEND_ROOT.rglob("*.js"))

        for source_path in frontend_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("localStorage", source)
            self.assertNotIn("google.maps", source)
            self.assertNotIn("geolocation", source)

    def test_render_modules_do_not_call_fetch(self):
        render_sources = list((FRONTEND_ROOT / "js" / "render").glob("*.js"))

        self.assertGreaterEqual(len(render_sources), 1)
        for source_path in render_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("fetch(", source, f"Render module should not call fetch: {source_path}")

    def test_action_modules_do_not_call_fetch_directly(self):
        action_sources = list((FRONTEND_ROOT / "js" / "actions").glob("*.js"))

        self.assertGreaterEqual(len(action_sources), 1)
        for source_path in action_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("fetch(", source, f"Action module should use API client helpers: {source_path}")

    def test_frontend_fetch_calls_remain_in_api_module(self):
        api_module = FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"

        for source_path in FRONTEND_ROOT.rglob("*.js"):
            source = source_path.read_text(encoding="utf-8")
            if source_path == api_module:
                continue
            self.assertNotIn("fetch(", source, f"Fetch should stay centralized in API module: {source_path}")
