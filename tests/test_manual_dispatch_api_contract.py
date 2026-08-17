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
            ("GET", "/api/manual-dispatch/auth/session"),
            ("POST", "/api/manual-dispatch/auth/reset-password"),
            ("POST", "/api/manual-dispatch/assign"),
            ("POST", "/api/manual-dispatch/unassign"),
            ("POST", "/api/manual-dispatch/driver-vehicle"),
            ("POST", "/api/manual-dispatch/orders"),
            ("POST", "/api/manual-dispatch/orders/import-attache-pdf-preview"),
            ("POST", "/api/manual-dispatch/orders/import-attache-pdf-commit"),
            ("POST", "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview"),
            ("POST", "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit"),
            ("POST", "/api/manual-dispatch/delivery/area-classification"),
            ("PATCH", "/api/manual-dispatch/delivery/orders/{order_id}/delivery-area"),
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

    def test_manual_dispatch_auth_boundary_is_default_deny(self):
        manual_dispatch_router = load_manual_dispatch_router()
        routes = [
            route
            for route in manual_dispatch_router.routes
            if getattr(route, "methods", None)
        ]
        public_routes = {
            (method, route.path)
            for route in routes
            if not route.dependant.dependencies
            for method in route.methods
        }

        self.assertEqual(99, len(routes))
        self.assertEqual(
            {
                ("POST", "/api/manual-dispatch/auth/login"),
                ("POST", "/api/manual-dispatch/auth/register"),
                ("POST", "/api/manual-dispatch/auth/reset-password"),
            },
            public_routes,
        )
        protected_routes = [route for route in routes if route.dependant.dependencies]
        self.assertEqual(96, len(protected_routes))
        for route in protected_routes:
            dependency_names = {
                getattr(dependency.call, "__name__", "")
                for dependency in route.dependant.dependencies
            }
            self.assertIn(
                "_require_authenticated_operator",
                dependency_names,
                f"Route is missing the canonical auth dependency: {route.path}",
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

    def test_backend_uses_same_origin_policy_without_cors_middleware(self):
        fresh_app = load_fresh_main_app()
        middleware_names = {
            middleware.cls.__name__ for middleware in fresh_app.user_middleware
        }

        self.assertNotIn("CORSMiddleware", middleware_names)
