import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class ManualDispatchFrontendStaticContractTest(unittest.TestCase):
    def test_frontend_entry_script_remains_app_module(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('<script type="module" src="app.js"></script>', index_html)

    def test_frontend_module_import_paths_exist(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        import_paths = re.findall(r'from\s+"(\./[^"]+)"', app_js)

        self.assertGreaterEqual(len(import_paths), 1)
        for import_path in import_paths:
            module_path = (FRONTEND_ROOT / import_path).resolve()
            self.assertTrue(
                module_path.exists(),
                f"Missing frontend module import: {import_path}",
            )

    def test_no_local_storage_or_mapping_apis_are_added_to_frontend_modules(self):
        frontend_sources = [
            path
            for path in FRONTEND_ROOT.rglob("*.js")
            if path.name != "app.js"
        ]

        for source_path in frontend_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("localStorage", source)
            self.assertNotIn("google.maps", source)
            self.assertNotIn("geolocation", source)
