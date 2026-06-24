import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class WorkspaceFrontendShellTest(unittest.TestCase):
    def setUp(self):
        self.app = self._read("app.js")
        self.state = self._read("js/state/app-state.js")
        self.api = self._read("js/api/manual-dispatch-api.js")
        self.auth_actions = self._read("js/actions/auth-actions.js")
        self.workspace_actions = self._read("js/actions/workspace-actions.js")
        self.home_renderer = self._read("js/render/workspace-home-renderer.js")
        self.navigation_renderer = self._read(
            "js/render/workspace-navigation-renderer.js"
        )
        self.delivery_renderer = self._read(
            "js/render/delivery-workspace-renderer.js"
        )
        self.opshop_renderer = self._read(
            "js/render/opshop-workspace-renderer.js"
        )

    def test_login_defaults_to_home_and_logged_out_routes_do_not_load(self):
        self.assertIn(
            'onAuthenticated: () => setWorkspaceRoute("home", { replace: true })',
            self.app,
        )
        self.assertIn("onAuthenticated();", self.auth_actions)
        self.assertIn('workspaceRoute: "home"', self.state)
        self.assertIn("if (!state.isLoggedIn || route === \"home\")", self.workspace_actions)
        self.assertNotIn("loadBoard(state.dispatchDate);", self.app)
        self.assertNotIn("loadFinalSummaryDates();\n", self.app.rsplit("renderBoard();", 1)[-1])

    def test_all_workspace_routes_and_legacy_redirects_are_declared(self):
        for route in (
            "home",
            "delivery/task-pool",
            "delivery/run-sheet",
            "delivery/history",
            "opshop/regular",
            "opshop/oncall",
            "opshop/countryside",
            "opshop/templates",
            "opshop/collections",
            "opshop/history",
        ):
            self.assertIn(f'"{route}"', self.app)

        for legacy_route, scoped_route in (
            ("task-pool", "delivery/task-pool"),
            ("trip-summary", "delivery/run-sheet"),
            ("final-summary", "delivery/history"),
        ):
            self.assertIn(f'"{legacy_route}": "{scoped_route}"', self.app)
        self.assertIn('window.addEventListener("hashchange"', self.app)
        self.assertIn('return WORKSPACE_ROUTES.has(redirectedRoute) ? redirectedRoute : "home"', self.app)

    def test_home_is_navigation_only_and_does_not_fetch_board_data(self):
        self.assertIn('href: "#delivery/task-pool"', self.home_renderer)
        self.assertIn('href: "#opshop/regular"', self.home_renderer)
        self.assertNotIn("fetch(", self.home_renderer)
        self.assertNotIn("apiGet", self.home_renderer)
        self.assertNotIn("apiList", self.home_renderer)
        early_return = self.workspace_actions.split(
            "async function loadWorkspaceRoute", 1
        )[1].split("async function loadDeliveryRoute", 1)[0]
        self.assertIn('route === "home"', early_return)
        self.assertIn("return;", early_return)

    def test_scoped_api_client_has_all_read_only_workspace_endpoints(self):
        for endpoint in (
            "/api/manual-dispatch/delivery/board",
            "/api/manual-dispatch/opshop/board",
            "/api/manual-dispatch/shared/specifications",
            "/api/manual-dispatch/delivery/run-sheets",
            "/api/manual-dispatch/opshop/pickup-collections",
        ):
            self.assertIn(endpoint, self.api)

    def test_delivery_and_opshop_loaders_are_independent(self):
        delivery_loader = self.workspace_actions.split(
            "async function loadDeliveryRoute", 1
        )[1].split("async function loadOpShopRoute", 1)[0]
        opshop_loader = self.workspace_actions.split(
            "async function loadOpShopRoute", 1
        )[1].split("async function updateDispatchDate", 1)[0]

        self.assertIn("apiGetDeliveryWorkspaceBoard", delivery_loader)
        self.assertIn("apiListDeliveryRunSheets", delivery_loader)
        self.assertNotIn("apiGetOpShopWorkspaceBoard", delivery_loader)
        self.assertNotIn("apiListOpShopPickupCollections", delivery_loader)

        self.assertIn("apiGetOpShopWorkspaceBoard", opshop_loader)
        self.assertIn("apiListOpShopPickupCollections", opshop_loader)
        self.assertNotIn("apiGetDeliveryWorkspaceBoard", opshop_loader)
        self.assertNotIn("apiListDeliveryRunSheets", opshop_loader)

    def test_new_workspace_source_does_not_call_legacy_board_or_summary_apis(self):
        new_workspace_source = "\n".join(
            (
                self.workspace_actions,
                self.home_renderer,
                self.navigation_renderer,
                self.delivery_renderer,
                self.opshop_renderer,
            )
        )
        self.assertNotIn('"/api/manual-dispatch/board"', new_workspace_source)
        self.assertNotIn("final-summaries", new_workspace_source)
        self.assertNotIn("fetch(", new_workspace_source)

    def test_delivery_renderer_contains_no_opshop_labels_or_payload_fields(self):
        for forbidden in (
            "OP SHOP",
            "opshop_",
            "pickup_category",
            "route_group",
        ):
            self.assertNotIn(forbidden, self.delivery_renderer)
        self.assertIn("Active Delivery Orders", self.delivery_renderer)
        self.assertIn("Delivery Run Sheets", self.delivery_renderer)

    def test_opshop_renderer_contains_no_delivery_domain_labels_or_payload_fields(self):
        for forbidden in (
            "Delivery Orders",
            "invoice_number",
            "product_lines",
            "pallet_quantity",
            "loose_bags_quantity",
            "vehicle_id",
            "trip_no",
            "Trip 1",
            "Trip 2",
        ):
            self.assertNotIn(forbidden, self.opshop_renderer)
        self.assertIn("Regular Pickup Schedule", self.opshop_renderer)
        self.assertIn("Oncall Pickup Requests", self.opshop_renderer)
        self.assertIn("Countryside Route Pickups", self.opshop_renderer)

    def test_new_workspace_navigation_and_titles_avoid_legacy_summary_name(self):
        new_workspace_source = "\n".join(
            (
                self.home_renderer,
                self.navigation_renderer,
                self.delivery_renderer,
                self.opshop_renderer,
            )
        )
        self.assertNotIn("Final Trip Summary", new_workspace_source)
        self.assertIn("Manual Dispatch", self._read("index.html"))
        self.assertIn("Home", self.navigation_renderer)
        self.assertIn("Switch workspace", self.navigation_renderer)

    def test_workspace_state_and_independent_loading_errors_are_present(self):
        for state_field in (
            "workspaceRoute",
            "activeWorkspace",
            "deliveryBoard",
            "deliveryRunSheets",
            "opshopBoard",
            "opshopPickupCollections",
            "sharedSpecifications",
            "isDeliveryWorkspaceLoading",
            "deliveryWorkspaceError",
            "isOpShopWorkspaceLoading",
            "opshopWorkspaceError",
        ):
            self.assertIn(f"{state_field}:", self.state)

    @staticmethod
    def _read(relative_path):
        return (FRONTEND_ROOT / relative_path).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
