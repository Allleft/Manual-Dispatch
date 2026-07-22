import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.main import ENABLE_API_DOCS_ENV, create_app

try:
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    TestClient = None


class PhaseDClosureTest(unittest.TestCase):
    @unittest.skipIf(TestClient is None, "FastAPI TestClient is unavailable")
    def test_api_docs_are_default_disabled_and_explicitly_enabled(self):
        with patch.dict(os.environ, {ENABLE_API_DOCS_ENV: "false"}):
            disabled_client = TestClient(create_app())
        with patch.dict(os.environ, {ENABLE_API_DOCS_ENV: "true"}):
            enabled_client = TestClient(create_app())

        self.assertEqual(200, disabled_client.get("/health").status_code)
        for path in ("/docs", "/redoc", "/openapi.json"):
            with self.subTest(path=path, enabled=False):
                self.assertEqual(404, disabled_client.get(path).status_code)
            with self.subTest(path=path, enabled=True):
                self.assertEqual(200, enabled_client.get(path).status_code)

    def test_cancel_order_fixture_closes_sqlite_before_cleanup(self):
        source = Path("tests/test_manual_dispatch_cancel_order.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("with sqlite3.connect(", source)
        self.assertIn("_closing_sqlite_connection", source)
