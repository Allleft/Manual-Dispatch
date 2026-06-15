import unittest

try:
    from backend.main import app
    from backend.api.manual_dispatch import router as manual_dispatch_router
except (ImportError, ModuleNotFoundError, RuntimeError):
    app = None
    manual_dispatch_router = None


class ManualDispatchApiContractTest(unittest.TestCase):
    def setUp(self):
        if app is None:
            self.skipTest("FastAPI app could not be imported")
        if manual_dispatch_router is None:
            self.skipTest("Manual Dispatch router could not be imported")

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
            ("GET", "/api/manual-dispatch/opshop-pickups/export-excel"),
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
            ("GET", "/api/manual-dispatch/final-summaries/{summary_id}/export-excel"),
            ("GET", "/api/manual-dispatch/final-summaries/{summary_id}"),
        }

        router_routes = {
            (method, route.path)
            for route in manual_dispatch_router.routes
            for method in getattr(route, "methods", set())
        }
        missing_from_router = expected_routes - router_routes
        self.assertFalse(
            missing_from_router,
            f"Manual Dispatch router is missing expected routes: {sorted(missing_from_router)}. "
            f"Actual router routes: {sorted(router_routes)}",
        )

        actual_routes = {
            (method, route.path)
            for route in app.routes
            for method in getattr(route, "methods", set())
            if route.path.startswith("/api/manual-dispatch")
        }

        missing_from_app = expected_routes - actual_routes
        self.assertFalse(
            missing_from_app,
            f"backend.main app did not include expected Manual Dispatch routes: "
            f"{sorted(missing_from_app)}. Actual app Manual Dispatch routes: {sorted(actual_routes)}",
        )

    def test_health_route_remains_available(self):
        actual_routes = {
            (method, route.path)
            for route in app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertIn(("GET", "/health"), actual_routes)
