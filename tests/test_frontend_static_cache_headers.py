import unittest

from fastapi.testclient import TestClient

from backend.main import app


class FrontendStaticCacheHeaderTest(unittest.TestCase):
    def test_frontend_js_is_served_without_browser_cache(self):
        client = TestClient(app)

        response = client.get("/frontend/app.js")

        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers.get("cache-control"))


if __name__ == "__main__":
    unittest.main()
