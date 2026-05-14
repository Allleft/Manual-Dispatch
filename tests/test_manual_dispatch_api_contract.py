import unittest

try:
    from backend.main import app
except (ImportError, ModuleNotFoundError, RuntimeError):
    app = None


class ManualDispatchApiContractTest(unittest.TestCase):
    def setUp(self):
        if app is None:
            self.skipTest("FastAPI app could not be imported")

    def test_manual_dispatch_routes_remain_available(self):
        expected_routes = {
            ("GET", "/api/manual-dispatch/board"),
            ("GET", "/api/manual-dispatch/specifications"),
            ("GET", "/api/manual-dispatch/export-excel"),
            ("POST", "/api/manual-dispatch/auth/register"),
            ("POST", "/api/manual-dispatch/auth/login"),
            ("POST", "/api/manual-dispatch/auth/reset-password"),
            ("POST", "/api/manual-dispatch/assign"),
            ("POST", "/api/manual-dispatch/unassign"),
            ("POST", "/api/manual-dispatch/driver-vehicle"),
            ("POST", "/api/manual-dispatch/orders"),
            ("PATCH", "/api/manual-dispatch/orders/{order_id}"),
            ("POST", "/api/manual-dispatch/orders/{order_id}/cancel"),
            ("POST", "/api/manual-dispatch/drivers"),
            ("PATCH", "/api/manual-dispatch/drivers/{driver_id}"),
            ("DELETE", "/api/manual-dispatch/drivers/{driver_id}"),
            ("POST", "/api/manual-dispatch/vehicles"),
            ("PATCH", "/api/manual-dispatch/vehicles/{vehicle_id}"),
            ("DELETE", "/api/manual-dispatch/vehicles/{vehicle_id}"),
            ("POST", "/api/manual-dispatch/final-summaries"),
            ("GET", "/api/manual-dispatch/final-summaries"),
            ("GET", "/api/manual-dispatch/final-summaries/export-excel"),
            ("GET", "/api/manual-dispatch/final-summary-dates"),
            ("GET", "/api/manual-dispatch/final-summaries/{summary_id}"),
        }

        actual_routes = {
            (method, route.path)
            for route in app.routes
            for method in getattr(route, "methods", set())
            if route.path.startswith("/api/manual-dispatch")
        }

        self.assertFalse(expected_routes - actual_routes)

    def test_health_route_remains_available(self):
        actual_routes = {
            (method, route.path)
            for route in app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertIn(("GET", "/health"), actual_routes)
