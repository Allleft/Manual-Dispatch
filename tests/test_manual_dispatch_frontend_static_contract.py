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

    def test_frontend_fetch_calls_remain_in_api_module(self):
        api_module = FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"

        for source_path in FRONTEND_ROOT.rglob("*.js"):
            source = source_path.read_text(encoding="utf-8")
            if source_path == api_module:
                continue
            self.assertNotIn("fetch(", source, f"Fetch should stay centralized in API module: {source_path}")
