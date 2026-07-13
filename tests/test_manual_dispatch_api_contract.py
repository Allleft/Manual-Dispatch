import importlib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_fresh_main_app():
    try:
        import backend.main as main_module
    except (ImportError, ModuleNotFoundError, RuntimeError) as error:
        raise unittest.SkipTest("FastAPI app could not be imported") from error

    main_module = importlib.reload(main_module)
    return main_module.app


def load_manual_dispatch_router():
    try:
        from backend.api.manual_dispatch import router
    except (ImportError, ModuleNotFoundError, RuntimeError) as error:
        raise unittest.SkipTest("Manual Dispatch router could not be imported") from error

    return router


class ManualDispatchApiContractTest(unittest.TestCase):
    def test_manual_dispatch_routes_remain_available(self):
        manual_dispatch_router = load_manual_dispatch_router()
        expected_routes = {
            ("GET", "/api/manual-dispatch/board"),
            ("GET", "/api/manual-dispatch/specifications"),
            ("GET", "/api/manual-dispatch/export-excel"),
            ("POST", "/api/manual-dispatch/auth/register"),
            ("POST", "/api/manual-dispatch/auth/login"),
            ("POST", "/api/manual-dispatch/auth/logout"),
            ("POST", "/api/manual-dispatch/auth/reset-password"),
            ("POST", "/api/manual-dispatch/assign"),
            ("POST", "/api/manual-dispatch/unassign"),
            ("POST", "/api/manual-dispatch/driver-vehicle"),
            ("POST", "/api/manual-dispatch/orders"),
            ("POST", "/api/manual-dispatch/orders/import-attache-pdf-preview"),
            ("POST", "/api/manual-dispatch/orders/import-attache-pdf-commit"),
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

    def test_backend_main_includes_manual_dispatch_router(self):
        main_py = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn(
            "from backend.api.manual_dispatch import router as manual_dispatch_router",
            main_py,
        )
        self.assertIn("app.include_router(manual_dispatch_router)", main_py)

    def test_health_route_remains_available(self):
        fresh_app = load_fresh_main_app()
        actual_routes = {
            (method, route.path)
            for route in fresh_app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertIn(("GET", "/health"), actual_routes)
