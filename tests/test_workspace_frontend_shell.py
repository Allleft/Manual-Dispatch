import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class WorkspaceFrontendShellTest(unittest.TestCase):
    def setUp(self):
        self.app = self._read("app.js")
        self.state = self._read("js/state/app-state.js")
        self.api = "\n".join(
            self._read(path)
            for path in (
                "js/api/manual-dispatch-api.js",
                "js/api/manual-dispatch/shared-api.js",
                "js/api/manual-dispatch/delivery-api.js",
                "js/api/manual-dispatch/opshop-api.js",
                "js/api/manual-dispatch/legacy-api.js",
            )
        )
        self.auth_actions = self._read("js/actions/auth-actions.js")
        self.opshop_entry_state = self._read(
            "js/state/opshop-collection-entry-state.js"
        )
        self.workspace_actions = "\n".join(
            self._read(path)
            for path in (
                "js/actions/workspace-actions.js",
                "js/actions/workspace/workspace-request-context.js",
                "js/actions/workspace/workspace-route-loaders.js",
                "js/actions/workspace/workspace-state-reset.js",
                "js/actions/workspace/delivery-history-actions.js",
                "js/actions/workspace/opshop-history-actions.js",
                "js/actions/workspace/opshop-workspace-actions.js",
                "js/actions/workspace/opshop-trip-summary-actions.js",
                "js/actions/workspace/delivery-trip-summary-actions.js",
                "js/actions/workspace/workspace-busy-actions.js",
                "js/actions/workspace/delivery-task-pool-actions.js",
                "js/actions/workspace/delivery-vehicle-queue.js",
                "js/actions/workspace/delivery-run-sheet-actions.js",
                "js/actions/workspace/opshop-task-pool-actions.js",
                "js/actions/workspace/opshop-collection-actions.js",
                "js/actions/workspace/delivery-workspace-actions.js",
                "js/actions/workspace/delivery-specification-actions.js",
                "js/actions/workspace/delivery-attache-actions.js",
                "js/actions/workspace/workspace-async-guards.js",
            )
        )
        self.home_renderer = self._read("js/render/workspace-home-renderer.js")
        self.navigation_renderer = self._read(
            "js/render/workspace-navigation-renderer.js"
        )
        self.delivery_renderer = "\n".join(
            self._read(path)
            for path in (
                "js/render/delivery-workspace-renderer.js",
                "js/render/delivery/delivery-workspace-page.js",
                "js/render/delivery/delivery-task-pool-renderer.js",
                "js/render/delivery/delivery-trip-summary-renderer.js",
                "js/render/delivery/delivery-history-renderer.js",
                "js/render/delivery/delivery-run-sheet-renderer.js",
                "js/render/delivery/delivery-order-modal-renderer.js",
                "js/render/delivery/delivery-attache-modal-renderer.js",
                "js/render/delivery/delivery-specification-modal-renderer.js",
                "js/render/delivery/delivery-generation-modal-renderer.js",
                "js/render/delivery/delivery-closeout-modal-renderer.js",
                "js/render/delivery/delivery-renderer-utils.js",
            )
        )
        self.delivery_closeout_utils = self._read(
            "js/utils/delivery-closeout-utils.js"
        )
        self.delivery_vehicle_utils = self._read(
            "js/utils/delivery-vehicle-utils.js"
        )
        self.delivery_order_priority_utils = self._read(
            "js/utils/delivery-order-priority-utils.js"
        )
        self.opshop_renderer = "\n".join(
            self._read(path)
            for path in (
                "js/render/opshop-workspace-renderer.js",
                "js/render/opshop/opshop-workspace-page.js",
                "js/render/opshop/opshop-task-pool-renderer.js",
                "js/render/opshop/opshop-regular-renderer.js",
                "js/render/opshop/opshop-oncall-renderer.js",
                "js/render/opshop/opshop-countryside-renderer.js",
                "js/render/opshop/opshop-template-page-renderer.js",
                "js/render/opshop/opshop-trip-summary-renderer.js",
                "js/render/opshop/opshop-history-renderer.js",
                "js/render/opshop/opshop-collection-renderer.js",
                "js/render/opshop/opshop-renderer-utils.js",
            )
        )
        self.opshop_date_group_renderer = self._read(
            "js/render/opshop-date-group-list-renderer.js"
        )
        self.opshop_workspace_modal_utils = self._read(
            "js/utils/opshop-workspace-modal-utils.js"
        )
        self.styles = self._read("styles.css")

    def test_login_defaults_to_home_and_logged_out_routes_do_not_load(self):
        self.assertIn(
            'onAuthenticated: () => setWorkspaceRoute("home", { replace: true })',
            self.app,
        )
        self.assertIn("onAuthenticated();", self.auth_actions)
        self.assertIn('workspaceRoute: "home"', self.state)
        self.assertIn("if (!state.isLoggedIn)", self.workspace_actions)
        self.assertIn('if (route === "home")', self.workspace_actions)
        self.assertNotIn("loadBoard(state.dispatchDate);", self.app)
        self.assertNotIn("loadFinalSummaryDates();\n", self.app.rsplit("renderBoard();", 1)[-1])

    def test_all_workspace_routes_and_legacy_redirects_are_declared(self):
        for route in (
            "home",
            "delivery/task-pool",
            "delivery/trip-summary",
            "delivery/run-sheet",
            "delivery/history",
            "opshop/task-pool/regular",
            "opshop/task-pool/oncall",
            "opshop/task-pool/countryside",
            "opshop/trip-summary",
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
            ("trip-summary", "delivery/trip-summary"),
            ("final-summary", "delivery/history"),
            ("opshop", "opshop/task-pool/regular"),
            ("opshop/task-pool", "opshop/task-pool/regular"),
            ("opshop/regular", "opshop/task-pool/regular"),
            ("opshop/oncall", "opshop/task-pool/oncall"),
            ("opshop/countryside", "opshop/task-pool/countryside"),
        ):
            self.assertIn(f'"{legacy_route}": "{scoped_route}"', self.app)
        self.assertIn('window.addEventListener("hashchange"', self.app)
        self.assertIn('return WORKSPACE_ROUTES.has(redirectedRoute) ? redirectedRoute : "home"', self.app)

    def test_home_is_navigation_only_and_does_not_fetch_board_data(self):
        self.assertIn('href: "#delivery/task-pool"', self.home_renderer)
        self.assertIn('href: "#opshop/task-pool/regular"', self.home_renderer)
        self.assertNotIn("fetch(", self.home_renderer)
        self.assertNotIn("apiGet", self.home_renderer)
        self.assertNotIn("apiList", self.home_renderer)
        early_return = self.workspace_actions.split(
            "async function loadWorkspaceRoute", 1
        )[1].split("async function loadDeliveryRoute", 1)[0]
        self.assertIn('route === "home"', early_return)
        self.assertIn("return;", early_return)
        self.assertIn("getWorkspaceMigrationStatus", early_return)

    def test_scoped_api_client_has_all_workspace_endpoints(self):
        for endpoint in (
            "/api/manual-dispatch/delivery/board",
            "/api/manual-dispatch/delivery/trip-summary",
            "/api/manual-dispatch/opshop/board",
            "/api/manual-dispatch/opshop/trip-summary",
            "/api/manual-dispatch/shared/specifications",
            "/api/manual-dispatch/delivery/run-sheets",
            "/api/manual-dispatch/opshop/pickup-collections",
            "/api/manual-dispatch/workspace-migration-status",
            "/api/manual-dispatch/delivery/assignments",
            "/api/manual-dispatch/delivery/assignments/unassign",
            "/api/manual-dispatch/delivery/vehicle-assignments",
            "/api/manual-dispatch/delivery/vehicle-assignments/clear",
            "/api/manual-dispatch/delivery/specifications",
            "/api/manual-dispatch/delivery/drivers",
            "/api/manual-dispatch/delivery/vehicles",
            "/api/manual-dispatch/delivery/orders",
            "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
            "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
            "/api/manual-dispatch/delivery/run-sheets/generated",
            "/api/manual-dispatch/opshop/pickups/assignments/apply",
            "/api/manual-dispatch/opshop/pickups/assignments/unassign",
            "/api/manual-dispatch/opshop/countryside-route-groups/",
            "/api/manual-dispatch/opshop/pickup-collections/generated",
            "/api/manual-dispatch/opshop/pickup-collections/export-excel",
        ):
            self.assertIn(endpoint, self.api)
        self.assertIn("/export-excel", self.api)
        self.assertIn("requestBlobDownload", self.api)
        self.assertIn("Content-Disposition", self.api)
        self.assertIn("error.status = response.status", self.api)
        self.assertIn("error.detail = detail", self.api)

    def test_history_api_clients_use_service_date_without_dispatch_date(self):
        delivery_block = self.api.split(
            "export async function apiListDeliveryRunSheetsByDeliveryDate", 1
        )[1].split(
            "export async function apiListDeliveryRunSheetsByDispatchAndDeliveryDate", 1
        )[0]
        self.assertIn("query: { delivery_date: deliveryDate, status }", delivery_block)
        self.assertNotIn("dispatch_date", delivery_block)

        opshop_block = self.api.split(
            "export async function apiListOpShopPickupCollectionsByPickupDate", 1
        )[1].split(
            "export async function apiListOpShopPickupCollectionsByDispatchAndPickupDate", 1
        )[0]
        self.assertIn("query: { pickup_date: pickupDate, status }", opshop_block)
        self.assertNotIn("dispatch_date", opshop_block)

    def test_delivery_and_opshop_loaders_are_independent(self):
        delivery_loader = self.workspace_actions.split(
            "async function loadDeliveryRoute", 1
        )[1].split("async function loadOpShopRoute", 1)[0]
        opshop_loader = self.workspace_actions.split(
            "async function loadOpShopRoute", 1
        )[1].split("async function updateDispatchDate", 1)[0]

        self.assertIn("api.getDeliveryWorkspaceBoard", delivery_loader)
        self.assertIn("api.listDeliveryRunSheets", delivery_loader)
        self.assertNotIn("api.getOpShopWorkspaceBoard", delivery_loader)
        self.assertNotIn("api.listOpShopPickupCollections", delivery_loader)

        self.assertIn("api.getOpShopWorkspaceBoard", opshop_loader)
        self.assertIn("api.listOpShopPickupCollections", opshop_loader)
        self.assertNotIn("api.getDeliveryWorkspaceBoard", opshop_loader)
        self.assertNotIn("api.listDeliveryRunSheets", opshop_loader)
        self.assertNotIn("apiGetSharedSpecifications", self.workspace_actions)

    def test_workspace_date_labels_distinguish_board_and_service_dates(self):
        self.assertIn('label.textContent = "Dispatch board date"', self.delivery_renderer)
        self.assertIn('label.textContent = "Pickup workspace date"', self.opshop_renderer)
        self.assertIn('field.textContent = "Delivery date"', self.delivery_renderer)
        self.assertIn('field.textContent = "Pickup date"', self.opshop_renderer)

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
        self.assertNotIn('"/api/manual-dispatch/orders"', new_workspace_source)
        self.assertNotIn('"/api/manual-dispatch/drivers"', new_workspace_source)
        self.assertNotIn('"/api/manual-dispatch/vehicles"', new_workspace_source)
        self.assertNotIn("import-attache-pdf-preview\", formData);", new_workspace_source)
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
        self.assertIn("Delivery Orders", self.delivery_renderer)
        self.assertNotIn("Filter active unassigned Orders", self.delivery_renderer)
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

    def test_workspace_renderers_omit_redundant_static_helper_text(self):
        source = "\n".join(
            (
                self._read("index.html"),
                self.home_renderer,
                self.delivery_renderer,
                self.opshop_renderer,
            )
        )
        for removed in (
            "Manual office workflow",
            "Choose a workspace",
            "Delivery operations",
            "Pickup operations",
            "Delivery orders and OP SHOP pickups now have separate workspaces",
            "Assign pickups and manage independent saved pickup collections.",
            "Plan driver trips, generate Delivery Run Sheets, and review saved history.",
            "Assign Regular, Oncall, and Countryside pickups before reviewing them by driver.",
            "Active scheduled pickup tasks for the current board window",
            "Active countryside pickup tasks with route-group context",
            "Actual request-driven pickup tasks created by office staff",
            "Filter active unassigned Orders, then assign each Order directly to a Driver and Trip.",
            "Review driver trips, manage assigned orders, select vehicles, and generate Delivery Run Sheets.",
            "Review generated and saved Delivery Run Sheets by actual Delivery date.",
            "Search saved Delivery Run Sheets by their actual Delivery Date.",
            "Review assigned pickups by driver before generating a Pickup Collection.",
            "Review generated and saved OP SHOP Pickup Collection weight sheets by actual Pickup date.",
            "Search saved OP SHOP Pickup Collections by their actual Pickup Date.",
            "Add, edit, review, and soft-disable Regular and Oncall templates.",
        ):
            self.assertNotIn(removed, source)

        for retained in (
            "OP SHOP Pickup",
            "OP SHOP Pickup Task Pool",
            "Regular Pickup Schedule",
            "Oncall Pickup Requests",
            "Countryside Route Pickups",
            "Order Delivery",
            "Delivery Orders",
            "Manage Templates",
            "Add Pickup Task",
            "Apply Assignment Changes",
            "Add Order",
            "Import Attache Invoices",
            "Driver & Vehicle Specification",
            "Pickup workspace date",
            "Dispatch board date",
            "No Regular pickups are visible for this dispatch date.",
            "No unassigned Delivery Orders are available.",
        ):
            self.assertIn(retained, source)

        self.assertIn('nav.setAttribute("aria-label", "OP SHOP Pickup workspace")', source)
        self.assertIn('nav.setAttribute("aria-label", "Order Delivery workspace")', source)
        self.assertIn('tabs.setAttribute("aria-label", "OP SHOP Task Pool pickup type")', source)
        self.assertIn('link.setAttribute("aria-current", "page")', source)

    def test_section_heading_without_description_only_creates_title(self):
        setup = r"""
            class FakeNode {
              constructor(tagName) {
                this.tagName = tagName;
                this.children = [];
                this.className = "";
                this.textContent = "";
              }
              append(...children) { this.children.push(...children); }
            }
            globalThis.document = {
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
            };
        """
        body = r"""
            const heading = module.createSectionHeading("Only title");
            if (heading.children.length !== 1) {
              throw new Error(`Expected one child, got ${heading.children.length}`);
            }
            if (heading.children[0].tagName !== "h3" || heading.children[0].textContent !== "Only title") {
              throw new Error("Heading title was not preserved");
            }
            if (heading.children.some((child) => child.tagName === "p")) {
              throw new Error("Empty description paragraph was rendered");
            }
        """
        for renderer_utils in (
            "js/render/delivery/delivery-renderer-utils.js",
            "js/render/opshop/opshop-renderer-utils.js",
        ):
            self._run_frontend_module_script(renderer_utils, body, setup=setup)

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
        self.assertIn("Trip Summary", self.delivery_renderer)
        self.assertIn("Run Sheets", self.delivery_renderer)
        self.assertIn("Saved History", self.delivery_renderer)
        self.assertIn("Manual Dispatch", self._read("index.html"))
        self.assertIn("Home", self.navigation_renderer)
        self.assertIn("Switch workspace", self.navigation_renderer)

    def test_workspace_state_and_independent_loading_errors_are_present(self):
        for state_field in (
            "workspaceRoute",
            "activeWorkspace",
            "workspaceMigrationStatus",
            "isWorkspaceMigrationStatusLoading",
            "workspaceMigrationStatusError",
            "deliveryBoard",
            "deliveryRunSheets",
            "deliveryTripSummaryBoard",
            "deliveryTripSummaryRunSheets",
            "deliveryTripSummaryDate",
            "deliverySavedHistoryDate",
            "deliverySavedHistoryRunSheets",
            "opshopBoard",
            "opshopPickupCollections",
            "opshopTripSummaryBoard",
            "opshopTripSummaryCollections",
            "opshopSavedHistoryDate",
            "opshopSavedHistoryCollections",
            "sharedSpecifications",
            "isDeliveryWorkspaceLoading",
            "deliveryWorkspaceError",
            "deliveryActionError",
            "deliveryBusyActionKeys",
            "deliveryGenerationConfirmation",
            "deliveryAssignmentDrafts",
            "deliveryVehicleDrafts",
            "deliveryVehicleClaims",
            "deliveryVehicleClaimSequence",
            "deliveryVehicleErrors",
            "deliveryVehiclePendingKeys",
            "isOpShopWorkspaceLoading",
            "opshopWorkspaceError",
            "opshopActionError",
            "opshopBusyActionKeys",
            "opshopGenerationConfirmation",
            "opshopAssignmentDrafts",
            "countrysideRouteGroupDrafts",
            "deliveryTaskPoolFilters",
            "deliveryOrderDetailId",
            "deliveryOrderForm",
            "deliveryOrderFormMode",
            "deliveryOrderModalError",
            "deliveryAttacheImportState",
            "deliverySpecificationModalOpen",
            "deliverySpecificationTab",
            "deliveryDriverForm",
            "deliveryVehicleForm",
            "deliverySpecificationError",
            "deliverySpecificationBusyKey",
        ):
            self.assertIn(f"{state_field}:", self.state)
        self.assertNotIn('"opshop/history": "opshop/collections"', self.app)
        self.assertIn('state.deliverySavedHistoryRunSheets = []', self.auth_actions)
        self.assertIn('state.opshopSavedHistoryCollections = []', self.auth_actions)
        self.assertIn('step: "files"', self.state)
        self.assertIn("expandedRowIds: {}", self.state)
        for transient_field in (
            "deliveryVehicleDrafts",
            "deliveryVehicleClaims",
            "deliveryVehicleErrors",
            "deliveryVehiclePendingKeys",
        ):
            self.assertIn(f"state.{transient_field} = {{}}", self.auth_actions)
        self.assertIn(
            "workspaceActions.resetDeliveryVehicleTransientState()",
            self.app,
        )
        self.assertIn(
            "resetDeliveryVehicleTransientState: clearDeliveryVehicleTransientState",
            self.workspace_actions,
        )

    def test_next_business_day_local_date_uses_weekday_rules_without_mutation(self):
        self._run_frontend_module_script(
            "js/utils/date-utils.js",
            """
            const cases = [
              [[2026, 8, 3], "2026-08-04"],
              [[2026, 8, 4], "2026-08-05"],
              [[2026, 8, 5], "2026-08-06"],
              [[2026, 8, 6], "2026-08-07"],
              [[2026, 8, 7], "2026-08-10"],
              [[2026, 8, 8], "2026-08-10"],
              [[2026, 8, 9], "2026-08-10"],
              [[2026, 4, 30], "2026-05-01"],
              [[2026, 12, 31], "2027-01-01"],
              [[2026, 7, 31], "2026-08-03"],
            ];
            for (const [[year, month, day], expected] of cases) {
              const input = new Date(year, month - 1, day, 15, 45, 30);
              const originalTime = input.getTime();
              const actual = module.getNextBusinessDayLocalDateString(input);
              if (actual !== expected) {
                throw new Error(`${year}-${month}-${day} returned ${actual}, expected ${expected}`);
              }
              if (input.getTime() !== originalTime) {
                throw new Error("getNextBusinessDayLocalDateString mutated its Date input");
              }
            }
            """,
        )

    def test_app_state_separates_trip_summary_default_from_today(self):
        self._run_frontend_module_script(
            "js/state/app-state.js",
            """
            if (module.DEFAULT_DISPATCH_DATE !== "2026-08-04") {
              throw new Error(`wrong Dispatch default ${module.DEFAULT_DISPATCH_DATE}`);
            }
            if (module.DEFAULT_TRIP_SUMMARY_DATE !== "2026-08-05") {
              throw new Error(`wrong Trip Summary default ${module.DEFAULT_TRIP_SUMMARY_DATE}`);
            }
            for (const field of [
              "driverSummaryDeliveryDate",
              "deliveryTripSummaryDate",
              "opshopTripSummaryDate",
            ]) {
              if (module.state[field] !== "2026-08-05") {
                throw new Error(`${field} did not use the Trip Summary default`);
              }
            }
            for (const field of [
              "dispatchDate",
              "deliverySavedHistoryDate",
              "opshopSavedHistoryDate",
              "historyDate",
            ]) {
              if (module.state[field] !== "2026-08-04") {
                throw new Error(`${field} no longer defaults to today`);
              }
            }
            """,
            setup="""
            const RealDate = Date;
            globalThis.Date = class extends RealDate {
              constructor(...args) {
                if (args.length) {
                  super(...args);
                } else {
                  super(2026, 7, 4, 12, 0, 0, 0);
                }
              }
              static now() {
                return new RealDate(2026, 7, 4, 12, 0, 0, 0).getTime();
              }
            };
            """,
        )

    def test_delivery_stage_6d_tools_are_scoped_to_delivery_workspace(self):
        for label in (
            "Search",
            "Delivery Date",
            "Phone",
            "Address",
            "Postcode",
            "Start",
            "End",
            "Urgency",
            "Notes",
            "Clear filters",
            "Add Order",
            "Import Attache Invoices",
            "Driver & Vehicle Specification",
            "Delivery Order",
            "General Information",
            "Product Lines",
            "Load Summary",
            "PALLETS",
            "Preview Import",
            "Confirm Import",
            "Back to files",
            "Select all ready",
            "Drivers",
            "Vehicles",
            "Driver ID",
            "Vehicle ID",
        ):
            self.assertIn(label, self.delivery_renderer)

        for action in (
            "updateDeliveryTaskPoolFilter",
            "clearDeliveryTaskPoolFilters",
            "openDeliveryOrderDetail",
            "openAddDeliveryOrder",
            "saveDeliveryOrderForm",
            "cancelActiveDeliveryOrder",
            "openDeliveryAttacheImport",
            "previewDeliveryAttacheImport",
            "commitDeliveryAttacheImport",
            "backDeliveryAttacheImportToFiles",
            "selectAllReadyDeliveryAttacheRows",
            "clearDeliveryAttacheImportSelection",
            "removeDeliveryAttacheImportFile",
            "toggleDeliveryAttacheImportExpanded",
            "addDeliveryAttacheImportProductLine",
            "removeDeliveryAttacheImportProductLine",
            "updateDeliveryAttacheImportProductLine",
            "openDeliverySpecifications",
            "saveDeliveryDriver",
            "saveDeliveryVehicle",
        ):
            self.assertIn(action, self.workspace_actions)

        for api_helper in (
            "apiGetDeliverySpecifications",
            "apiCreateDeliveryOrder",
            "apiUpdateDeliveryOrder",
            "apiCancelDeliveryOrder",
            "apiPreviewDeliveryAttacheInvoices",
            "apiCommitDeliveryAttacheInvoices",
            "apiCreateDeliveryDriver",
            "apiUpdateDeliveryDriver",
            "apiDeleteDeliveryDriver",
            "apiCreateDeliveryVehicle",
            "apiUpdateDeliveryVehicle",
            "apiDeleteDeliveryVehicle",
        ):
            self.assertIn(api_helper, self.api)

        self.assertIn("filterDeliveryTaskPoolOrders", self.delivery_renderer)
        self.assertIn("deliveryOrderSearchText", self.delivery_renderer)
        self.assertIn("order.product_lines", self.delivery_renderer)
        self.assertIn("createAttacheProductLineEditor", self.delivery_renderer)
        self.assertIn("updateDeliveryAttacheImportProductLine", self.delivery_renderer)
        self.assertIn("isOrderCapturedByRunSheet", self.delivery_renderer)
        self.assertIn("state.deliveryTaskPoolFilters", self.delivery_renderer)
        self.assertIn("deliveryAttachePreviewRequestVersion", self.workspace_actions)
        self.assertIn("deliverySpecificationRequestVersion", self.workspace_actions)
        self.assertIn('state.workspaceRoute === "delivery/task-pool"', self.workspace_actions)
        self.assertIn("state.deliveryAttacheImportState?.isOpen", self.workspace_actions)
        self.assertIn("clearDeliveryTaskPoolModals", self.workspace_actions)

    def test_stage_6d_2_delivery_modal_and_upload_contracts(self):
        order_actions = self.delivery_renderer.split(
            "function createDeliveryOrderActions", 1
        )[1].split("function createDeliveryOrderForm", 1)[0]
        modal_helper = self.delivery_renderer.split(
            "function createWorkspaceModal", 1
        )[1].split("function trapModalFocus", 1)[0]
        button_helper = self.delivery_renderer.split(
            "function createActionButton", 1
        )[1].split("function createMetricGrid", 1)[0]
        upload_step = self.delivery_renderer.split(
            "function createDeliveryAttacheFileStep", 1
        )[1].split("function createDeliveryAttachePreview", 1)[0]

        self.assertEqual(1, order_actions.count('createActionButton("Close"'))
        self.assertIn('iconOnly: true', modal_helper)
        self.assertIn('accessibleLabel: "Close"', modal_helper)
        self.assertIn('button.setAttribute("aria-label", description)', button_helper)
        self.assertIn('button.title = description', button_helper)
        self.assertIn('dropZone.addEventListener("dragenter"', upload_step)
        self.assertIn('dropZone.addEventListener("dragover"', upload_step)
        self.assertIn('dropZone.addEventListener("dragleave"', upload_step)
        self.assertIn('dropZone.addEventListener("drop"', upload_step)
        self.assertIn('event.preventDefault()', upload_step)
        self.assertIn('event.dataTransfer?.files || []', upload_step)
        self.assertIn('source: "drop"', upload_step)
        self.assertIn('workspace-attache-dropzone-active', upload_step)
        self.assertNotIn(
            "Review driver trips, manage assigned orders, select vehicles, and generate Delivery Run Sheets.",
            self.delivery_renderer,
        )
        self.assertNotIn(
            "assign orders to driver trips, select vehicles",
            self.delivery_renderer,
        )
        self.assertIn('No Drivers available.', self.delivery_renderer)
        self.assertIn('No Vehicles available.', self.delivery_renderer)
        self.assertIn('function invalidateDeliveryAttachePreview()', self.workspace_actions)
        self.assertIn('No PDF files were dropped.', self.workspace_actions)

    def test_attache_preview_handles_success_failure_and_duplicate_click(self):
        self._run_delivery_attache_actions_script(
            """
            function createHarness(previewImpl) {
              const selectedFiles = [{ name: "invoice.pdf", type: "application/pdf" }];
              const state = {
                isLoggedIn: true,
                authSessionVersion: 7,
                workspaceRoute: "delivery/task-pool",
                activeWorkspace: "delivery",
                dispatchDate: "2026-07-23",
                deliveryAttacheImportState: {
                  isOpen: true,
                  isPreviewing: false,
                  isCommitting: false,
                  step: "files",
                  files: selectedFiles,
                  rows: [],
                  expandedRowIds: {},
                  error: "",
                  success: "",
                },
              };
              const apiCalls = [];
              let renderCount = 0;
              const context = {
                state,
                renderWorkspace: () => { renderCount += 1; },
                api: {
                  previewDeliveryAttacheInvoices: async (files) => {
                    apiCalls.push(files);
                    return previewImpl(files);
                  },
                },
                deliveryAttachePreviewRequestVersion: 0,
                actions: {},
              };
              context.actions.captureMutationContext = () => ({
                route: state.workspaceRoute,
                dispatchDate: state.dispatchDate,
                activeWorkspace: state.activeWorkspace,
                authSessionVersion: state.authSessionVersion,
              });
              context.actions.isDeliveryMutationCurrent = (snapshot) =>
                state.isLoggedIn
                && snapshot.route === state.workspaceRoute
                && snapshot.dispatchDate === state.dispatchDate
                && snapshot.activeWorkspace === state.activeWorkspace
                && snapshot.authSessionVersion === state.authSessionVersion;
              return {
                actions: createDeliveryAttacheActions(context),
                apiCalls,
                context,
                getRenderCount: () => renderCount,
                selectedFiles,
                state,
              };
            }

            let resolveSuccess;
            const successResponse = new Promise((resolve) => {
              resolveSuccess = resolve;
            });
            const success = createHarness(async () => successResponse);
            const firstPreview = success.actions.previewDeliveryAttacheImport();
            const duplicatePreview = success.actions.previewDeliveryAttacheImport();
            if (success.apiCalls.length !== 1) {
              throw new Error("duplicate Preview click started another request");
            }
            if (!success.state.deliveryAttacheImportState.isPreviewing) {
              throw new Error("Preview did not enter loading state");
            }
            resolveSuccess({
              rows: [
                { row_id: "READY", selected: true, importable: true, is_duplicate: false },
                { row_id: "DUPLICATE", selected: true, importable: true, is_duplicate: true },
                { row_id: "INVALID", selected: true, importable: false, is_duplicate: false },
              ],
            });
            await Promise.all([firstPreview, duplicatePreview]);
            if (success.apiCalls[0] !== success.selectedFiles) {
              throw new Error("Preview API did not receive the selected files");
            }
            if (success.context.deliveryAttachePreviewRequestVersion !== 1) {
              throw new Error("outer Preview request version did not increment");
            }
            if (success.state.deliveryAttacheImportState.step !== "review") {
              throw new Error("successful Preview did not advance to review");
            }
            const successRows = success.state.deliveryAttacheImportState.rows;
            if (successRows.length !== 3) {
              throw new Error("successful Preview rows were not stored");
            }
            if (!successRows[0].selected || successRows[1].selected || successRows[2].selected) {
              throw new Error("Preview row selection eligibility was not normalized");
            }
            if (success.state.deliveryAttacheImportState.isPreviewing) {
              throw new Error("successful Preview did not clear loading state");
            }
            if (success.state.deliveryAttacheImportState.error) {
              throw new Error("successful Preview displayed an error");
            }
            if (success.getRenderCount() !== 2) {
              throw new Error("successful Preview did not render loading and completion states");
            }

            const failure = createHarness(async () => {
              throw new Error("broken PDF");
            });
            await failure.actions.previewDeliveryAttacheImport();
            if (failure.apiCalls.length !== 1) {
              throw new Error("failed Preview did not call the API exactly once");
            }
            if (failure.context.deliveryAttachePreviewRequestVersion !== 1) {
              throw new Error("failed Preview did not increment the outer request version");
            }
            if (!failure.state.deliveryAttacheImportState.error.includes(
              "Unable to preview Attache invoices. broken PDF"
            )) {
              throw new Error("failed Preview did not show the existing user-facing error");
            }
            if (failure.state.deliveryAttacheImportState.isPreviewing) {
              throw new Error("failed Preview did not clear loading state");
            }
            if (
              !failure.state.deliveryAttacheImportState.isOpen
              || failure.state.deliveryAttacheImportState.step !== "files"
              || failure.state.deliveryAttacheImportState.files.length !== 1
            ) {
              throw new Error("failed Preview did not remain usable for retry");
            }
            if (failure.getRenderCount() !== 2) {
              throw new Error("failed Preview did not render loading and error states");
            }
            """
        )

    def test_attache_preview_is_invalidated_by_close_files_and_navigation(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const previews = [deferred(), deferred(), deferred()];
            let previewIndex = 0;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              deliveryTaskPoolFilters: { search: "", delivery_date: "", urgency: "All" },
              deliveryOrderDetailId: "",
              deliveryOrderForm: {},
              deliveryOrderFormMode: "",
              deliveryOrderModalError: "",
              deliveryAttacheImportState: {},
              deliverySpecificationModalOpen: false,
              deliveryDriverForm: null,
              deliveryDriverEditingId: "",
              deliveryVehicleForm: null,
              deliveryVehicleEditingId: "",
              deliverySpecificationError: "",
              deliverySpecificationBusyKey: "",
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
              opshopBusyActionKeys: {},
            };
            const api = {
              previewDeliveryAttacheInvoices: async () => previews[previewIndex++].promise,
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              listDeliveryRunSheets: async () => [],
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              confirmAction: () => true,
              api,
            });
            const pdf = (name) => ({ name, type: "application/pdf" });

            actions.openDeliveryAttacheImport();
            actions.updateDeliveryAttacheImportFiles([pdf("old.pdf")]);
            const closedPreview = actions.previewDeliveryAttacheImport();
            actions.closeDeliveryAttacheImport();
            actions.openDeliveryAttacheImport();
            previews[0].resolve({ rows: [{ row_id: "STALE-CLOSE" }] });
            await closedPreview;
            if ((state.deliveryAttacheImportState.rows || []).length) {
              throw new Error("closed Preview populated a reopened Import modal");
            }

            actions.updateDeliveryAttacheImportFiles([pdf("first.pdf")]);
            const replacedPreview = actions.previewDeliveryAttacheImport();
            actions.updateDeliveryAttacheImportFiles([pdf("replacement.pdf")]);
            previews[1].resolve({ rows: [{ row_id: "STALE-FILES" }] });
            await replacedPreview;
            if (state.deliveryAttacheImportState.files[0].name !== "replacement.pdf") {
              throw new Error("replacement file selection was overwritten");
            }
            if ((state.deliveryAttacheImportState.rows || []).length) {
              throw new Error("replaced-file Preview populated stale rows");
            }

            actions.updateDeliveryAttacheImportFiles([pdf("route.pdf")]);
            const routedPreview = actions.previewDeliveryAttacheImport();
            state.workspaceRoute = "delivery/trip-summary";
            await actions.loadWorkspaceRoute("delivery/trip-summary");
            previews[2].resolve({ rows: [{ row_id: "STALE-ROUTE" }] });
            await routedPreview;
            if (state.deliveryAttacheImportState.isOpen) {
              throw new Error("navigation did not close the Import modal");
            }
            if ((state.deliveryAttacheImportState.rows || []).length) {
              throw new Error("route-stale Preview populated rows");
            }
            if (state.deliveryAttacheImportState.error) {
              throw new Error("route-stale Preview displayed an obsolete error");
            }

            state.workspaceRoute = "delivery/task-pool";
            actions.openDeliveryAttacheImport();
            actions.updateDeliveryAttacheImportFiles(
              [{ name: "notes.txt", type: "text/plain" }],
              { source: "drop" },
            );
            if ((state.deliveryAttacheImportState.files || []).length) {
              throw new Error("non-PDF drop was accepted");
            }
            if (!state.deliveryAttacheImportState.error.includes("No PDF files were dropped")) {
              throw new Error("non-PDF drop did not show a clear validation error");
            }
            """
        )

    def test_delivery_workspace_wires_scoped_assignment_vehicle_and_lifecycle_actions(self):
        task_pool_block = self.delivery_renderer.split(
            "function createDeliveryTaskPool", 1
        )[1].split("function createOrderCard", 1)[0]
        panel_block = self.delivery_renderer.split(
            "function createDeliveryTaskPoolPanel", 1
        )[1].split("function createOrderCard", 1)[0]
        self.assertIn("Delivery Orders", panel_block)
        self.assertNotIn("Filter active unassigned Orders", panel_block)
        self.assertLess(panel_block.index('"Add Order"'), panel_block.index('"Import Attache Invoices"'))
        self.assertLess(panel_block.index('"Import Attache Invoices"'), panel_block.index('"Driver & Vehicle Specification"'))
        self.assertIn("createOrderAssignmentControls", self.delivery_renderer)
        self.assertIn('"Driver"', self.delivery_renderer)
        self.assertIn('"Trip"', self.delivery_renderer)
        self.assertIn('"Assign"', self.delivery_renderer)
        self.assertIn("applyDeliveryOrderAssignment", self.delivery_renderer)

        self.assertIn("updateDeliveryTripSummaryDate", self.delivery_renderer)
        self.assertNotIn("updateDeliveryTripAddOrderDraft", self.delivery_renderer)
        self.assertNotIn("addDeliveryOrderToTrip", self.delivery_renderer)
        self.assertNotIn("createAddOrderControl", self.delivery_renderer)
        self.assertIn("moveDeliveryOrderToTrip", self.delivery_renderer)
        self.assertIn("unassignDeliveryOrder", self.delivery_renderer)
        self.assertIn("updateDeliveryVehicleSelection", self.delivery_renderer)
        self.assertIn("generateDeliveryRunSheet", self.delivery_renderer)
        self.assertIn("saveDeliveryRunSheet", self.delivery_renderer)
        self.assertIn("cancelDeliveryRunSheet", self.delivery_renderer)
        self.assertIn("exportDeliveryRunSheet", self.delivery_renderer)
        self.assertNotIn("Ready to Generate", self.delivery_renderer)
        self.assertIn("driver_id: driverId", self.workspace_actions)
        self.assertIn("trip_no: tripNo", self.workspace_actions)
        self.assertIn("order_id: orderId", self.workspace_actions)
        self.assertIn("vehicle_id: vehicleId", self.workspace_actions)
        self.assertIn("saved_by_account_name: state.accountName || null", self.workspace_actions)
        self.assertIn("Delivery date", self.delivery_renderer)
        self.assertNotIn("input.min", self.delivery_renderer)
        self.assertIn("state.deliveryTripSummaryBoard", self.delivery_renderer)
        self.assertIn("state.deliveryTripSummaryRunSheets", self.delivery_renderer)
        self.assertIn("Trip 1", self.delivery_renderer)
        self.assertIn("Trip 2", self.delivery_renderer)
        self.assertIn("Add Order", self.delivery_renderer)
        self.assertIn("Move to Trip 2", self.delivery_renderer)
        self.assertIn("Move to Trip 1", self.delivery_renderer)
        self.assertIn("Generate Run Sheet", self.delivery_renderer)
        self.assertIn("navigateWorkspaceRoute: setWorkspaceRoute", self.app)
        self.assertIn("navigateWorkspaceRoute = null", self.workspace_actions)
        self.assertIn('await navigateWorkspaceRoute("delivery/run-sheet")', self.workspace_actions)
        self.assertNotIn('window.history.pushState(null, "", "#delivery/run-sheet")', self.workspace_actions)
        self.assertIn("const deliveryDate = nextDate || DEFAULT_TRIP_SUMMARY_DATE", self.workspace_actions)
        self.assertIn("state.deliveryTripSummaryDate = deliveryDate", self.workspace_actions)
        self.assertIn("loadDeliveryTripSummaryData", self.workspace_actions)
        self.assertIn("api.getDeliveryTripSummary", self.workspace_actions)
        self.assertIn("dispatchDate,", self.workspace_actions)
        self.assertIn("deliveryDate: scopedDeliveryDate", self.workspace_actions)
        self.assertIn(
            "api.listDeliveryRunSheetsByDeliveryDate",
            self.workspace_actions,
        )
        self.assertIn("state.deliveryTripSummaryBoard = board", self.workspace_actions)
        self.assertIn("Trip 1 orders", self.delivery_renderer)
        self.assertIn("Trip 2 orders", self.delivery_renderer)
        self.assertIn("Saved Run Sheet History", self.delivery_renderer)
        self.assertIn("Export Excel", self.delivery_renderer)
        self.assertIn("workspace-run-sheet-document-card", self.delivery_renderer)
        self.assertIn("Vehicle", self.delivery_renderer)
        self.assertIn('label: "Select vehicle"', self.delivery_renderer)
        self.assertIn("formatDeliveryVehicleOptionLabel", self.delivery_renderer)
        self.assertNotIn("Selected vehicle:", self.delivery_renderer)
        self.assertNotIn("Capacity:", self.delivery_renderer)
        self.assertNotIn("workspace-vehicle-capacity-summary", self.delivery_renderer)
        self.assertNotIn("runSheet.dispatch_date === dispatchDate", self.delivery_renderer)
        self.assertNotIn("assignment.dispatch_date === dispatchDate", self.delivery_renderer)
        action_block = self.delivery_renderer.split(
            "function createDeliveryOrderActions", 1
        )[1].split("function createDeliveryOrderForm", 1)[0]
        self.assertLess(action_block.index('"Close"'), action_block.index('"Edit Order"'))
        self.assertLess(action_block.index('"Edit Order"'), action_block.index('"Cancel Order"'))
        self.assertIn("workspace-modal-action-danger", action_block)
        self.assertIn("createWorkspaceModal", self.delivery_renderer)
        self.assertIn("trapModalFocus", self.delivery_renderer)
        self.assertIn('document.addEventListener("keydown", handleDocumentEscape)', self.delivery_renderer)
        self.assertIn('document.removeEventListener("keydown", handleDocumentEscape)', self.delivery_renderer)
        assigned_order_block = self.delivery_renderer.split(
            "function createAssignedOrderRow", 1
        )[1].split("function createRunSheetList", 1)[0]
        assigned_order_actions = assigned_order_block.split(
            "const actionsRow = document.createElement", 1
        )[1]
        self.assertIn("workspace-order-detail-trigger", assigned_order_block)
        self.assertIn('title.type = "button"', assigned_order_block)
        self.assertIn("title.dataset.orderId", assigned_order_block)
        self.assertIn("actions.openDeliveryOrderDetail", assigned_order_block)
        self.assertIn("order.order_id", assigned_order_block)
        self.assertIn("readOnly: true", assigned_order_block)
        self.assertIn("View Delivery Order", assigned_order_block)
        self.assertNotIn("openDeliveryOrderDetail", assigned_order_actions)
        self.assertIn("deliveryOrderDetailReadOnly", self.state)
        self.assertIn("deliveryOrderDetailReadOnly", self.workspace_actions)
        self.assertIn("Delivery Order Details", self.delivery_renderer)
        self.assertIn("createDeliveryOrderReadOnlyActions", self.delivery_renderer)
        self.assertIn('"Current Assignment"', self.delivery_renderer)
        self.assertIn('"Current assigned driver"', self.delivery_renderer)
        self.assertIn('"Current trip"', self.delivery_renderer)
        self.assertIn("focusDeliveryOrderDetailTrigger", self.workspace_actions)
        self.assertIn(".workspace-order-detail-trigger", self.workspace_actions)
        self.assertIn("item.dataset.orderId === orderId", self.workspace_actions)

    def test_delivery_run_sheets_align_document_cards_and_preserve_full_snapshot_paper(self):
        history_block = self.delivery_renderer.split(
            "function createSavedRunSheetHistory", 1
        )[1].split("function createRunSheetList", 1)[0]
        operational_block = self.delivery_renderer.split(
            "function createRunSheetList", 1
        )[1].split("function createDailyRunSheetPaper", 1)[0]
        paper_suite = self.delivery_renderer.split(
            "function createDailyRunSheetPaper", 1
        )[1].split("function createRunSheetDocumentCard", 1)[0]
        paper_function = paper_suite.split("const DAILY_RUN_SHEET_COLUMNS", 1)[0]
        document_card_block = self.delivery_renderer.split(
            "function createRunSheetDocumentCard", 1
        )[1].split("function createDeliveryOrderModal", 1)[0]

        self.assertEqual(
            1,
            self.delivery_renderer.count("function createDailyRunSheetPaper"),
        )
        self.assertIn(
            'createDailyRunSheetPaper(runSheet, state, actions, { context: "history" })',
            history_block,
        )
        self.assertNotIn("createRunSheetDocumentCard", history_block)
        self.assertIn("createRunSheetDateGroup", operational_block)
        self.assertIn("createRunSheetDocumentCard(runSheet, state, actions)", operational_block)
        self.assertIn("Delivery date:", operational_block)
        self.assertIn("generated/saved run sheets for this Delivery Date", operational_block)
        self.assertIn("dataset.deliveryRunSheetExport", operational_block)
        self.assertNotIn('"Generated Run Sheets"', operational_block)
        self.assertNotIn('"Saved Run Sheets"', operational_block)
        self.assertIn('"Saved Run Sheet History"', history_block)
        self.assertNotIn(
            '"Search saved Delivery Run Sheets by their actual Delivery Date."',
            history_block,
        )
        self.assertIn('field.textContent = "Delivery date"', history_block)
        self.assertIn("actions.updateDeliverySavedHistoryDate", history_block)
        self.assertIn(
            '"No saved Delivery Run Sheets were found for this Delivery Date."',
            history_block,
        )
        self.assertNotIn('"Save Run Sheet"', history_block)
        self.assertNotIn('"Cancel Generated"', history_block)

        for expected in (
            '"DAILY RUN SHEET"',
            '"DATE:"',
            '"DRIVER:"',
            '"REGO#:"',
            "runSheet.vehicle_rego_snapshot",
            '"Not selected"',
            "START TIME: ______________________",
            "TIME LOADING STARTED (TO BE FILLED IN BY STOREMAN)",
            "TIME LOADING COMPLETED (TO BE FILLED IN BY STOREMAN)",
            "FINISH TIME: ______________________",
            "dailyRunSheetSnapshotRows(runSheet)",
            "runSheet.trips",
            "product_lines_snapshot",
            "product_snapshot",
            "formatProductDetailLine(line, index + 1)",
            "formatRunSheetKgTotal(order)",
            "workspace-daily-run-sheet-product-cell",
            "formatRunSheetProduct(order)",
            '${labelText} ${valueText}',
            '"COD"',
            '"CQ"',
            '"Time In"',
            '"Time Out"',
            '"PRINT NAME"',
            '"SIGNATURE"',
            '"NO. # PALLETS RETND"',
        ):
            self.assertIn(expected, paper_suite)
        row_values_block = paper_suite.split(
            "function dailyRunSheetRowValues", 1
        )[1].split("function formatRunSheetProduct", 1)[0]
        self.assertIn("loose_bags_quantity_snapshot", row_values_block)
        self.assertIn("carton_quantity_snapshot", row_values_block)
        self.assertIn("note_snapshot", row_values_block)
        self.assertNotIn("state.deliveryBoard", paper_suite)
        self.assertIn("runSheet.status", paper_function)
        self.assertIn("context === \"history\"", paper_function)
        self.assertIn("Saved:", paper_function)
        self.assertIn("Saved by:", paper_function)
        self.assertIn("Workspace date:", paper_function)
        self.assertIn("embedded = false", paper_function)
        self.assertIn("if (!embedded)", paper_function)

        for expected in (
            "workspace-run-sheet-document-card",
            "workspace-run-sheet-card-meta",
            "workspace-run-sheet-actions",
            "Workspace date:",
            "Delivery date:",
            "Driver:",
            "Status:",
            "createBadge(runSheet.status",
            "createDailyRunSheetPaper(runSheet, state, actions, { embedded: true })",
            '"Save Run Sheet"',
            '"Cancel Generated"',
            '"Export Excel"',
        ):
            self.assertIn(expected, document_card_block)

        actions_block = paper_function.split(
            'actionsRow.className = "workspace-action-row workspace-daily-run-sheet-actions"', 1
        )[1]
        history_actions, operational_actions = actions_block.split("} else {", 1)
        self.assertIn('"Export Excel"', history_actions)
        self.assertIn("actions.exportDeliveryRunSheet", history_actions)
        self.assertNotIn('"Save Run Sheet"', history_actions)
        self.assertNotIn('"Cancel Generated"', history_actions)
        self.assertIn('"Save Run Sheet"', operational_actions)
        self.assertIn('"Cancel Generated"', operational_actions)
        self.assertNotIn('"Export Excel"', operational_actions)

        self.assertIn("workspace-daily-run-sheet-table-scroll", self.styles)
        self.assertIn("overflow-x: auto", self.styles)
        self.assertIn("min-width: 1974px", self.styles)
        self.assertIn(".workspace-run-sheet-document-card", self.styles)
        self.assertIn(".workspace-run-sheet-date-group", self.styles)
        self.assertIn(".workspace-run-sheet-card-meta", self.styles)
        self.assertIn(".workspace-run-sheet-actions", self.styles)
        self.assertIn(".workspace-run-sheet-paper-list", self.styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", self.styles)
        self.assertIn("min-height: 44px", self.styles)
        self.assertIn("white-space: pre-line", self.styles)

    def test_delivery_run_sheet_closeout_contract_and_pure_helpers(self):
        for expected in (
            "apiCloseDeliveryRunSheet",
            "/closeout",
            "closeDeliveryRunSheet: apiCloseDeliveryRunSheet",
        ):
            self.assertIn(expected, self.api + self.workspace_actions)
        for expected in (
            "deliveryRunSheetCloseout",
            "deliveryActionSuccess",
        ):
            self.assertIn(expected, self.state)
        for expected in (
            "`delivery-closeout:${draft.run_sheet_id}`",
            "state.deliveryBusyActionKeys?.[actionKey]",
            "buildDeliveryCloseoutConfirmation",
            "buildDeliveryCloseoutPayload",
            "Mark All Delivered",
            "Choose outcome",
            "Return to Delivery Task Pool",
            "Close Run Sheet",
            "execution_status",
            "closeout_summary",
            "closed_by_account_name",
            "Closeout outcomes",
            "delivery_address_snapshot",
            "suburb_snapshot",
            "Driver:",
        ):
            self.assertIn(
                expected,
                self.workspace_actions
                + self.delivery_renderer
                + self.delivery_closeout_utils,
            )
        self.assertIn("workspace-delivery-closeout-row", self.styles)
        self.assertIn("workspace-run-sheet-outcomes", self.styles)

        self._run_frontend_module_script(
            "js/utils/delivery-closeout-utils.js",
            """
            const runSheet = {
              run_sheet_id: "DRS-1",
              delivery_date: "2026-07-28",
              driver_name_snapshot: "Driver",
              trips: [{
                trip_no: "trip1",
                orders: [
                  {
                    row_id: "ROW-1",
                    row_no: 1,
                    invoice_number_snapshot: "INV-1",
                    company_name_snapshot: "A",
                    delivery_address_snapshot: "1 Test Street",
                    suburb_snapshot: "Dandenong",
                  },
                  { row_id: "ROW-2", invoice_number_snapshot: "INV-2", company_name_snapshot: "B" },
                ],
              }],
            };
            const draft = module.createDeliveryCloseoutDraft(runSheet);
            if (draft.rows[0].row_no !== 1 ||
                draft.rows[0].delivery_address !== "1 Test Street" ||
                draft.rows[0].suburb !== "Dandenong") {
              throw new Error("Closeout draft omitted row context");
            }
            if (draft.rows.some((row) => row.outcome)) {
              throw new Error("Closeout outcomes were defaulted");
            }
            if (!module.validateDeliveryCloseoutDraft(draft).includes("Choose an outcome")) {
              throw new Error("Missing outcomes were not rejected");
            }
            const missingOutcomeErrors = module.getDeliveryCloseoutRowErrors(
              draft.rows[0],
              draft.delivery_date,
            );
            if (Object.keys(missingOutcomeErrors).join(",") !== "outcome") {
              throw new Error("Missing outcome leaked return-specific errors");
            }
            draft.rows[0].outcome = "DELIVERED";
            draft.rows[0].reason_code = "OTHER";
            draft.rows[0].next_delivery_date = "";
            if (Object.keys(module.getDeliveryCloseoutRowErrors(
              draft.rows[0],
              draft.delivery_date,
            )).length) {
              throw new Error("Delivered row retained return-specific errors");
            }
            draft.rows[1].outcome = "RETURN_TO_POOL";
            draft.rows[1].reason_code = "OTHER";
            draft.rows[1].next_delivery_date = "2026-07-29";
            if (!module.validateDeliveryCloseoutDraft(draft).includes("Add a note")) {
              throw new Error("OTHER without a note was not rejected");
            }
            draft.rows[1].note = "Customer requested retry";
            if (module.validateDeliveryCloseoutDraft(draft)) {
              throw new Error("Valid closeout draft was rejected");
            }
            const payload = module.buildDeliveryCloseoutPayload(draft);
            if (Object.keys(payload.rows[0]).sort().join(",") !==
                "next_delivery_date,note,outcome,reason_code,run_sheet_row_id") {
              throw new Error("Closeout payload leaked derived identity fields");
            }
            if (payload.rows[0].reason_code !== null || payload.rows[0].next_delivery_date !== null) {
              throw new Error("Delivered payload retained return-only fields");
            }
            const confirmation = module.buildDeliveryCloseoutConfirmation(draft);
            if (!confirmation.includes("1 delivered; 1 returned") ||
                !confirmation.includes("2026-07-29") ||
                !confirmation.includes("cannot be edited")) {
              throw new Error("Final confirmation omitted irreversible summary details");
            }
            """,
        )

    def test_delivery_ui_usability_refresh_contracts(self):
        for expected in (
            "workspace-load-summary-fields",
            "workspace-load-summary-field",
            "workspace-load-product-layout",
            "workspace-product-line-table-scroll",
            "dataset.productLineId",
            "_draft_id",
            "formatProductLineTotals",
            '"Note (optional)"',
        ):
            self.assertIn(expected, self.delivery_renderer + self.workspace_actions)
        self.assertIn(
            "product_lines: (form.product_lines || []).map((line) => ({",
            self.workspace_actions,
        )

        for expected in (
            "workspace-attache-review-toolbar",
            "Search invoice, order or customer",
            "Filter invoice reviews",
            "dataset.invoiceReviewId",
            "applyAttacheReviewVisibility",
            "Warnings / Parse Issues",
            "updateDeliveryAttacheReviewSearch",
            "updateDeliveryAttacheReviewFilter",
        ):
            self.assertIn(expected, self.delivery_renderer + self.workspace_actions)

        for expected in (
            "workspace-daily-run-sheet-table-region",
            "Scroll horizontally to review all delivery and signature columns.",
            "width: 1974px",
            "word-break: normal",
            "white-space: nowrap",
        ):
            self.assertIn(expected, self.delivery_renderer + self.styles)

        update_block = self.workspace_actions.split(
            "function updateDeliveryCloseoutRow", 1
        )[1].split("function markAllDeliveryCloseoutRowsDelivered", 1)[0]
        mark_all_block = self.workspace_actions.split(
            "function markAllDeliveryCloseoutRowsDelivered", 1
        )[1].split("async function submitDeliveryRunSheetCloseout", 1)[0]
        self.assertNotIn("renderWorkspace()", update_block)
        self.assertNotIn("renderWorkspace()", mark_all_block)
        self.assertIn("patchDeliveryCloseoutCard", self.delivery_renderer)
        self.assertIn('form.addEventListener("submit"', self.delivery_renderer)
        self.assertIn('submit.type = "submit"', self.delivery_renderer)
        self.assertIn("event.preventDefault()", self.delivery_renderer)

    def test_delivery_closeout_footer_and_local_validation_contract(self):
        closeout_renderer = self._read(
            "js/render/delivery/delivery-closeout-modal-renderer.js"
        )
        closeout_styles = self.styles.split(
            ".workspace-modal-delivery-closeout", 1
        )[1].split("@media (max-width: 1024px)", 1)[0]

        for expected in (
            'modalShell.classList.add("workspace-modal-delivery-closeout")',
            "body.dataset.deliveryCloseoutScrollContainer",
            'form.id = "workspace-delivery-closeout-form"',
            'cancel.type = "button"',
            'submit.type = "submit"',
            'submit.setAttribute("form", form.id)',
            "body.append(form)",
            "modalShell.append(actionsRow)",
            "patchDeliveryCloseoutValidation(card, row)",
            "data-closeout-field",
            "dataset.closeoutErrorFor",
        ):
            self.assertIn(expected, closeout_renderer)
        self.assertNotIn("form.append(actionsRow)", closeout_renderer)

        for expected in (
            "grid-template-rows: auto minmax(0, 1fr) auto",
            "overflow: hidden",
            "position: static",
            "overflow-y: auto",
            "overscroll-behavior-y: contain",
            ".workspace-delivery-closeout-actions",
            "position: relative",
        ):
            self.assertIn(expected, self.styles)
        actions_styles = closeout_styles.split(
            ".workspace-delivery-closeout-actions", 1
        )[1]
        self.assertNotIn("position: absolute", actions_styles)
        self.assertNotIn("position: fixed", actions_styles)
        self.assertNotIn("position: sticky", actions_styles)

    def test_delivery_closeout_field_errors_follow_current_draft(self):
        self._run_workspace_actions_script(
            """
            const state = {
              deliveryRunSheetCloseout: {
                run_sheet_id: "DRS-VALIDATION",
                delivery_date: "2026-07-29",
                driver_name: "Driver",
                error: "",
                rows: [
                  {
                    run_sheet_row_id: "ROW-A",
                    order_label: "184068",
                    outcome: "RETURN_TO_POOL",
                    reason_code: "",
                    next_delivery_date: "",
                    note: "",
                    validation_errors: {},
                  },
                  {
                    run_sheet_row_id: "ROW-B",
                    order_label: "184069",
                    outcome: "DELIVERED",
                    reason_code: "",
                    next_delivery_date: "",
                    note: "Delivered note",
                    validation_errors: {},
                  },
                ],
              },
              deliveryBusyActionKeys: {},
            };
            let apiCalls = 0;
            let renders = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => { renders += 1; },
              confirmAction: () => true,
              api: {
                closeDeliveryRunSheet: async () => {
                  apiCalls += 1;
                  return {};
                },
              },
            });
            const draft = state.deliveryRunSheetCloseout;
            const first = draft.rows[0];
            const second = draft.rows[1];

            await actions.submitDeliveryRunSheetCloseout();
            if (!first.validation_errors.reason_code ||
                !first.validation_errors.next_delivery_date) {
              throw new Error("Submit did not create field-level return errors");
            }
            const secondErrors = JSON.stringify(second.validation_errors);

            actions.updateDeliveryCloseoutRow("ROW-A", "outcome", "DELIVERED");
            if (Object.keys(first.validation_errors).length ||
                JSON.stringify(second.validation_errors) !== secondErrors) {
              throw new Error("Delivered outcome did not clear only its row errors");
            }

            actions.updateDeliveryCloseoutRow("ROW-A", "outcome", "");
            await actions.submitDeliveryRunSheetCloseout();
            if (Object.keys(first.validation_errors).join(",") !== "outcome") {
              throw new Error("Empty outcome retained return-specific errors");
            }

            actions.updateDeliveryCloseoutRow(
              "ROW-A",
              "outcome",
              "RETURN_TO_POOL",
            );
            await actions.submitDeliveryRunSheetCloseout();
            actions.updateDeliveryCloseoutRow(
              "ROW-A",
              "reason_code",
              "TIME_RAN_OUT",
            );
            if (first.validation_errors.reason_code ||
                !first.validation_errors.next_delivery_date) {
              throw new Error("Valid reason cleared the wrong field error");
            }
            actions.updateDeliveryCloseoutRow(
              "ROW-A",
              "next_delivery_date",
              "2026-07-30",
            );
            if (Object.keys(first.validation_errors).length) {
              throw new Error("Valid date did not immediately clear its error");
            }

            actions.updateDeliveryCloseoutRow("ROW-A", "reason_code", "OTHER");
            await actions.submitDeliveryRunSheetCloseout();
            if (!first.validation_errors.note) {
              throw new Error("OTHER without note did not create note error");
            }
            actions.updateDeliveryCloseoutRow(
              "ROW-A",
              "note",
              "Customer requested another attempt",
            );
            if (first.validation_errors.note) {
              throw new Error("Valid OTHER note did not immediately clear its error");
            }
            if (apiCalls !== 0 || renders !== 0) {
              throw new Error("Local validation called the API or rerendered workspace");
            }
            """
        )

    def test_delivery_order_product_table_layout_contract(self):
        product_block = self.delivery_renderer.split(
            "export function createProductLineEditor", 1
        )[1].split(
            "export function createLoadAndProductLinesSection", 1
        )[0]
        load_block = self.delivery_renderer.split(
            "export function createLoadAndProductLinesSection", 1
        )[1].split(
            "function createProductLineInput", 1
        )[0]

        self.assertEqual(1, product_block.count('document.createElement("table")'))
        self.assertEqual(1, product_block.count('document.createElement("thead")'))
        self.assertEqual(1, product_block.count('document.createElement("tbody")'))
        self.assertEqual(2, product_block.count('document.createElement("tr")'))
        self.assertEqual(1, product_block.count('const row = document.createElement("tr")'))
        self.assertEqual(8, product_block.count("createProductLineCell("))
        self.assertIn('document.createElement("colgroup")', product_block)
        self.assertIn('"workspace-product-line-table-row"', product_block)
        self.assertIn('"actions"', product_block)
        self.assertIn("dataset.productLineId = line._draft_id", product_block)
        self.assertIn('"Add Product Line"', product_block)
        self.assertIn('"Remove product line"', product_block)
        self.assertIn("Total Actual Quantity:", product_block)

        self.assertEqual(1, load_block.count('"Load Summary"'))
        self.assertNotIn("workspace-load-metrics", load_block)
        self.assertIn("workspace-load-summary-fields", load_block)
        self.assertEqual(3, load_block.count('["'))

        for expected in (
            "grid-template-rows: auto minmax(0, 1fr) auto",
            ".workspace-modal-order > .workspace-modal-header",
            "position: static",
            ".workspace-modal-order > .workspace-order-modal-body",
            "overflow-x: hidden",
            ".workspace-modal-order > .workspace-modal-footer",
            "grid-template-columns: repeat(3, minmax(160px, 1fr))",
            "min-width: 1200px",
            ".workspace-product-column-name { width: 280px; }",
            "overflow-x: auto",
            "word-break: normal",
        ):
            self.assertIn(expected, self.styles)
        self.assertNotIn(".workspace-product-line-row {", self.styles)
        self.assertNotIn("workspace-load-metrics", self.styles)

    def test_delivery_order_product_line_actions_keep_stable_row_identity(self):
        self._run_workspace_actions_script(
            """
            const state = {
              deliveryOrderForm: {
                product_lines: [
                  {
                    _draft_id: "LINE-A",
                    product_code: "A",
                    product_name: "Alpha",
                    quantity: 1,
                    unit: "BAG",
                    package_quantity: 1,
                    package_unit: "BAG1",
                  },
                  {
                    _draft_id: "LINE-B",
                    product_code: "B",
                    product_name: "Beta",
                    quantity: 2,
                    unit: "CARTON",
                    package_quantity: 2,
                    package_unit: "BOX",
                  },
                ],
              },
            };
            let renders = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => { renders += 1; },
              api: {},
            });

            const changes = {
              product_code: "RSING10KG",
              product_name: "COLOUR RAGS 10KG NET",
              quantity: "45",
              unit: "BAG",
              package_quantity: "45",
              package_unit: "BAG10",
            };
            Object.entries(changes).forEach(([field, value]) => {
              actions.updateDeliveryOrderProductLine("LINE-A", field, value);
            });
            const first = state.deliveryOrderForm.product_lines[0];
            const second = state.deliveryOrderForm.product_lines[1];
            if (first.product_name !== changes.product_name ||
                first.quantity !== 45 ||
                first.package_quantity !== 45) {
              throw new Error("Stable row update did not update the requested fields");
            }
            if (second.product_code !== "B" || second.product_name !== "Beta") {
              throw new Error("Stable row update changed a different product line");
            }

            actions.addDeliveryOrderProductLine();
            const added = state.deliveryOrderForm.product_lines.at(-1);
            if (!added._draft_id || state.deliveryOrderForm.product_lines.length !== 3) {
              throw new Error("Add Product Line did not create a stable draft row");
            }
            actions.removeDeliveryOrderProductLine(added._draft_id);
            if (state.deliveryOrderForm.product_lines.length !== 2 ||
                state.deliveryOrderForm.product_lines.some(
                  (line) => line._draft_id === added._draft_id
                )) {
              throw new Error("Remove Product Line did not remove the stable draft row");
            }
            if (renders !== 2) {
              throw new Error("Add/remove render behavior changed");
            }
            """
        )

    def test_delivery_date_excel_export_is_scoped_busy_and_non_mutating(self):
        self.assertIn(
            "/api/manual-dispatch/delivery/run-sheets/export-excel?delivery_date=",
            self.api,
        )
        self.assertIn('"Export Excel File"', self.delivery_renderer)
        self.assertIn('"Preparing Excel File..."', self.delivery_renderer)
        self.assertNotIn("Export Excel File", self.opshop_renderer)
        self._run_workspace_actions_script(
            """
            let resolveExport;
            const exportGate = new Promise((resolve) => { resolveExport = resolve; });
            let exportCalls = 0;
            let generateCalls = 0;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/run-sheet",
              activeWorkspace: "delivery",
              dispatchDate: "2026-07-06",
              deliveryTripSummaryDate: "2026-07-07",
              deliveryBusyActionKeys: {},
              deliveryActionError: "",
              deliveryAssignmentDrafts: { "ORDER-1": { driver_id: "D001" } },
              deliveryVehicleDrafts: {},
              opshopBusyActionKeys: {},
            };
            const beforeDrafts = JSON.stringify(state.deliveryAssignmentDrafts);
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                exportDeliveryRunSheetsExcel: async (deliveryDate) => {
                  exportCalls += 1;
                  if (deliveryDate !== "2026-07-07") {
                    throw new Error(`wrong export date: ${deliveryDate}`);
                  }
                  return exportGate;
                },
                createGeneratedDeliveryRunSheet: async () => {
                  generateCalls += 1;
                },
              },
            });
            const first = actions.exportDeliveryRunSheets("2026-07-07");
            const second = actions.exportDeliveryRunSheets("2026-07-07");
            if (exportCalls !== 1) {
              throw new Error(`rapid Delivery export made ${exportCalls} API calls`);
            }
            if (!state.deliveryBusyActionKeys["delivery-export-date:2026-07-07"]) {
              throw new Error("Delivery date export did not expose its isolated busy state");
            }
            resolveExport({ filename: "Daily_Run_Sheets_2026-07-07.xlsx" });
            await Promise.all([first, second]);
            if (generateCalls !== 0) {
              throw new Error("Delivery date export called Generate API");
            }
            if (state.workspaceRoute !== "delivery/run-sheet" ||
                state.deliveryTripSummaryDate !== "2026-07-07" ||
                JSON.stringify(state.deliveryAssignmentDrafts) !== beforeDrafts) {
              throw new Error("Delivery date export mutated route, date, or assignments");
            }
            if (Object.keys(state.deliveryBusyActionKeys).length !== 0) {
              throw new Error("Delivery date export busy state was not cleared");
            }

            const failureState = {
              ...state,
              deliveryBusyActionKeys: {},
              deliveryActionError: "",
            };
            const failureActions = createWorkspaceActions({
              state: failureState,
              renderWorkspace: () => {},
              api: {
                exportDeliveryRunSheetsExcel: async () => {
                  throw new Error("Workbook preparation failed");
                },
              },
            });
            await failureActions.exportDeliveryRunSheets("2026-07-07");
            if (failureState.deliveryActionError !== "Workbook preparation failed") {
              throw new Error("Delivery export failure was not surfaced accurately");
            }
            """
        )

    def test_delivery_vehicle_selector_labels_and_duplicate_state_contract(self):
        vehicle_control = self.delivery_renderer.split(
            "function createDriverVehicleControl", 1
        )[1].split("function createTripPanel", 1)[0]
        vehicle_action = self.workspace_actions.split(
            "async function updateDeliveryVehicleSelection", 1
        )[1].split("async function generateDeliveryRunSheet", 1)[0]

        self.assertIn("formatDeliveryVehicleOptionLabel", vehicle_control)
        self.assertIn("getDeliveryVehicleConflictDriverNames", vehicle_control)
        self.assertIn("workspace-vehicle-select-invalid", vehicle_control)
        self.assertIn('select.setAttribute("aria-invalid"', vehicle_control)
        self.assertIn('select.setAttribute("aria-describedby"', vehicle_control)
        self.assertIn("workspace-vehicle-conflict-warning", vehicle_control)
        self.assertIn("hasVehicleConflict", vehicle_control)
        self.assertIn("backendConflictMessage", vehicle_control)
        self.assertIn("Updating vehicle...", vehicle_control)
        self.assertIn("select.disabled = isLocked || isUpdatingVehicle", vehicle_control)
        self.assertNotIn('"Save vehicle"', vehicle_control)
        self.assertNotIn('"Clear Vehicle"', vehicle_control)
        self.assertNotIn("vehicleSummary", vehicle_control)
        self.assertIn("getDeliveryVehicleConflictDriverNames", vehicle_action)
        self.assertLess(
            vehicle_action.index("if (conflictDriverNames.length)"),
            vehicle_action.index("api.assignDeliveryWorkspaceVehicle"),
        )
        self.assertIn("api.clearDeliveryWorkspaceVehicle", vehicle_action)
        self.assertIn("deliveryVehicleErrors", vehicle_action)
        self.assertIn("deliveryVehicleClaims", vehicle_action)
        self.assertIn("deliveryVehiclePendingKeys", vehicle_control)
        self.assertIn("deliveryVehicleQueues", vehicle_action)
        vehicle_current_check = self.workspace_actions.split(
            "function isDeliveryVehicleQueueCurrent", 1
        )[1].split("function updateDeliveryVehicleClaim", 1)[0]
        self.assertIn("state.deliveryTripSummaryDate", vehicle_current_check)
        self.assertNotIn("state.dispatchDate", vehicle_current_check)
        self.assertNotIn("applyDeliveryVehicleAssignment", self.workspace_actions)
        self.assertNotIn("clearDeliveryVehicleAssignment", self.workspace_actions)
        self.assertIn("pallet capacity", self.delivery_vehicle_utils)
        self.assertIn("assigned to", self.delivery_vehicle_utils)
        create_select = self.delivery_renderer.split(
            "function createSelect", 1
        )[1].split("function createBoundInput", 1)[0]
        self.assertLess(
            create_select.index("options.forEach"),
            create_select.index('select.value = value || ""'),
        )

    def test_delivery_vehicle_conflicts_cover_saved_drafts_dates_and_current_driver(self):
        module_uri = (
            FRONTEND_ROOT / "js/utils/delivery-vehicle-utils.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{
              formatDeliveryVehicleConflictMessage,
              formatDeliveryVehicleOptionLabel,
              getDeliveryVehicleConflictDriverNames,
            }} = await import({module_uri!r});

            const drivers = [
              {{ driver_id: "A", name: "Driver A" }},
              {{ driver_id: "B", name: "Driver B" }},
              {{ driver_id: "C", name: "Driver C" }},
            ];
            const savedBoard = {{
              drivers,
              driver_vehicle_assignments: [
                {{ delivery_date: "2026-06-29", driver_id: "B", vehicle_id: "V1" }},
                {{ delivery_date: "2026-06-30", driver_id: "C", vehicle_id: "V1" }},
              ],
            }};
            const find = (board, claims, date, driver, vehicle) =>
              getDeliveryVehicleConflictDriverNames({{
                board,
                claims,
                deliveryDate: date,
                driverId: driver,
                vehicleId: vehicle,
              }});

            const savedConflict = find(savedBoard, {{}}, "2026-06-29", "A", "V1");
            if (savedConflict.join(",") !== "Driver B") {{
              throw new Error("same-date saved assignment conflict was not detected");
            }}
            if (find(savedBoard, {{}}, "2026-06-29", "B", "V1").length) {{
              throw new Error("current Driver's own assignment was treated as duplicate");
            }}
            if (find(savedBoard, {{}}, "2026-06-28", "A", "V1").length) {{
              throw new Error("assignment on a different Delivery Date was blocked");
            }}
            if (find(savedBoard, {{ "2026-06-29|B": {{ vehicle_id: "V2", sequence: 1 }} }}, "2026-06-29", "A", "V1").join(",") !== "Driver B") {{
              throw new Error("unsaved replacement draft released a still-saved vehicle");
            }}

            const firstClaimWins = find(
              {{ drivers, driver_vehicle_assignments: [] }},
              {{
                "2026-06-29|A": {{ vehicle_id: "V1", sequence: 1 }},
                "2026-06-29|B": {{ vehicle_id: "V1", sequence: 2 }},
              }},
              "2026-06-29",
              "B",
              "V1",
            );
            if (firstClaimWins.join(",") !== "Driver A") {{
              throw new Error("later local claim did not yield to the earliest claimant");
            }}
            if (find(
              {{ drivers, driver_vehicle_assignments: [] }},
              {{
                "2026-06-29|A": {{ vehicle_id: "V1", sequence: 1 }},
                "2026-06-29|B": {{ vehicle_id: "V1", sequence: 2 }},
              }},
              "2026-06-29",
              "A",
              "V1",
            ).length) {{
              throw new Error("later claim incorrectly invalidated the first claimant");
            }}
            if (find(savedBoard, {{ "2026-06-29|A": {{ vehicle_id: "V2", sequence: 1 }} }}, "2026-06-29", "A", "V2").length) {{
              throw new Error("available replacement vehicle kept a stale conflict");
            }}

            const multiple = find(
              {{
                drivers,
                driver_vehicle_assignments: [
                  {{ delivery_date: "2026-06-29", driver_id: "B", vehicle_id: "V1" }},
                  {{ delivery_date: "2026-06-29", driver_id: "C", vehicle_id: "V1" }},
                ],
              }},
              {{}},
              "2026-06-29",
              "A",
              "V1",
            );
            if (formatDeliveryVehicleConflictMessage(multiple) !==
                "This vehicle is already assigned to: Driver B, Driver C.") {{
              throw new Error("multiple-driver conflict warning is incorrect");
            }}
            if (formatDeliveryVehicleOptionLabel(
              {{ vehicle_id: "V1", rego: "1AW4P1", pallet_capacity: 28 }},
              ["Driver B"],
            ) !== "1AW4P1 — 28 pallet capacity — assigned to Driver B") {{
              throw new Error("vehicle option label is incorrect");
            }}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_delivery_task_pool_priority_normalization_sorting_and_source_safety(self):
        module_uri = (
            FRONTEND_ROOT / "js/utils/delivery-order-priority-utils.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{
              isDeliveryOrderUrgent,
              normalizeDeliveryOrderUrgency,
              sortDeliveryTaskPoolOrders,
            }} = await import({module_uri!r});

            for (const value of ["Urgent", "URGENT", "urgent", " urgent "]) {{
              if (normalizeDeliveryOrderUrgency(value) !== "Urgent") {{
                throw new Error(`Urgency was not normalized: ${{value}}`);
              }}
              if (!isDeliveryOrderUrgent({{ urgency: value }})) {{
                throw new Error(`Urgency was not detected: ${{value}}`);
              }}
            }}
            for (const value of ["", null, "priority", "normal"]) {{
              if (normalizeDeliveryOrderUrgency(value) !== "Normal") {{
                throw new Error(`Non-urgent value was not canonical Normal: ${{value}}`);
              }}
            }}

            const orders = [
              {{ order_id: "N-EARLY", urgency: "Normal", delivery_date: "2026-06-01", start_time: "07:00", invoice_number: "1" }},
              {{ order_id: "U-MISSING-DATE", urgency: " urgent ", delivery_date: "", start_time: "06:00", invoice_number: "9" }},
              {{ order_id: "U-LATE-TIME", urgency: "URGENT", delivery_date: "2026-06-03", start_time: "10:00", invoice_number: "5" }},
              {{ order_id: "U-EARLY-TIME", urgency: "Urgent", delivery_date: "2026-06-03", start_time: "08:00", invoice_number: "8" }},
              {{ order_id: "U-MISSING-TIME", urgency: "urgent", delivery_date: "2026-06-03", start_time: "", invoice_number: "2" }},
              {{ order_id: "U-EARLIER-DATE", urgency: "urgent", delivery_date: "2026-06-02", start_time: "15:00", invoice_number: "7" }},
              {{ order_id: "FALLBACK-B", urgency: "Normal", delivery_date: "bad", start_time: "bad", invoice_number: "20", order_no: "B" }},
              {{ order_id: "FALLBACK-A2", urgency: "Normal", delivery_date: "bad", start_time: "bad", invoice_number: "20", order_no: "A" }},
              {{ order_id: "FALLBACK-A1", urgency: "Normal", delivery_date: "bad", start_time: "bad", invoice_number: "20", order_no: "A" }},
              {{ order_id: "STABLE", urgency: "Normal", delivery_date: "bad", start_time: "bad", invoice_number: "30", order_no: "S" }},
              {{ order_id: "STABLE", urgency: "Normal", delivery_date: "bad", start_time: "bad", invoice_number: "30", order_no: "S" }},
            ];
            const before = orders.map((order) => order.order_id).join(",");
            const sorted = sortDeliveryTaskPoolOrders(orders);
            const expected = [
              "U-EARLIER-DATE",
              "U-EARLY-TIME",
              "U-LATE-TIME",
              "U-MISSING-TIME",
              "U-MISSING-DATE",
              "N-EARLY",
              "FALLBACK-A1",
              "FALLBACK-A2",
              "FALLBACK-B",
              "STABLE",
              "STABLE",
            ].join(",");
            if (sorted.map((order) => order.order_id).join(",") !== expected) {{
              throw new Error(`Unexpected priority order: ${{sorted.map((order) => order.order_id).join(",")}}`);
            }}
            if (orders.map((order) => order.order_id).join(",") !== before) {{
              throw new Error("Priority sort mutated the scoped board Orders array");
            }}
            if (sorted === orders) {{
              throw new Error("Priority sort returned the source array");
            }}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_delivery_task_pool_sorts_urgent_then_oldest_invoice_date(self):
        self._run_frontend_module_script(
            "js/utils/delivery-order-priority-utils.js",
            r"""
            const orders = [
              {
                order_id: "A",
                urgency: "Normal",
                invoice_date: "2026-08-09",
                delivery_date: "2026-08-15",
              },
              {
                order_id: "B",
                urgency: "Normal",
                invoice_date: "2026-08-10",
                delivery_date: "2026-08-14",
              },
              {
                order_id: "C",
                urgency: "Normal",
                invoice_date: "2026-08-11",
                delivery_date: "2026-08-13",
              },
              {
                order_id: "D",
                urgency: "Urgent",
                invoice_date: "2026-08-12",
                delivery_date: "2026-08-16",
              },
              {
                order_id: "E",
                urgency: "Normal",
                invoice_date: null,
                delivery_date: "2026-08-16",
              },
            ];
            const sorted = module.sortDeliveryTaskPoolOrders(orders);
            if (sorted.map((order) => order.order_id).join("") !== "DABCE") {
              throw new Error(`Invoice date precedence failed: ${sorted.map((order) => order.order_id)}`);
            }

            const invalid = module.sortDeliveryTaskPoolOrders([
              {
                order_id: "VALID",
                urgency: "Normal",
                invoice_date: "2026-08-11",
                delivery_date: "2026-08-20",
              },
              {
                order_id: "INVALID",
                urgency: "Normal",
                invoice_date: "2026-02-30",
                delivery_date: "2026-08-19",
              },
              {
                order_id: "MISSING",
                urgency: "Normal",
                invoice_date: null,
                delivery_date: "2026-08-18",
              },
            ]);
            if (invalid[0].order_id !== "VALID") {
              throw new Error("Invalid Invoice Date sorted ahead of a valid Invoice Date");
            }
            if (invalid.slice(1).map((order) => order.order_id).join("|") !== "MISSING|INVALID") {
              throw new Error("Missing/invalid Invoice Dates did not use later deterministic tie-breakers");
            }
            """,
        )

    def test_delivery_search_typing_keeps_input_focus_caret_route_and_scroll(self):
        task_pool_uri = (
            FRONTEND_ROOT / "js/render/delivery/delivery-task-pool-renderer.js"
        ).as_uri()
        actions_uri = (FRONTEND_ROOT / "js/actions/workspace-actions.js").as_uri()
        script = textwrap.dedent(
            r"""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.nodeType = tagName === "#text" ? 3 : 1;
                this.children = [];
                this.parentNode = null;
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.hidden = false;
                this.value = "";
                this.type = "";
                this.placeholder = "";
                this.selectionStart = 0;
                this.selectionEnd = 0;
                this.scrollTop = 0;
                this.scrollLeft = 0;
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\s+/).includes(token),
                  toggle: (token, enabled) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    enabled ? classes.add(token) : classes.delete(token);
                    this._className = [...classes].join(" ");
                    return enabled;
                  },
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) {
                this._text = String(value ?? "");
                this.children = [];
              }
              append(...children) {
                children.forEach((child) => {
                  if (child === null || child === undefined) return;
                  child.parentNode = this;
                  this.children.push(child);
                });
              }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
              focus() { document.activeElement = this; }
              setSelectionRange(start, end) {
                this.selectionStart = start;
                this.selectionEnd = end;
              }
              replaceWith(replacement) {
                if (!this.parentNode) throw new Error("Cannot replace a detached node");
                const index = this.parentNode.children.indexOf(this);
                replacement.parentNode = this.parentNode;
                this.parentNode.children[index] = replacement;
                this.parentNode = null;
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  const isClass = selector.startsWith(".");
                  const matched = isClass
                    ? node.classList?.contains(selector.slice(1))
                    : String(node.tagName || "").toLowerCase() === selector.toLowerCase();
                  if (matched) matches.push(node);
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }

            const body = new FakeNode("body");
            globalThis.document = {
              activeElement: null,
              body,
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
              querySelector: (selector) => body.querySelector(selector),
            };
            const scrollCalls = [];
            globalThis.window = {
              location: { protocol: "http:", hash: "" },
              history: { pushState: () => {} },
              scrollX: 17,
              scrollY: 321,
              scrollTo: (x, y) => {
                scrollCalls.push([x, y]);
                window.scrollX = x;
                window.scrollY = y;
              },
            };
            globalThis.requestAnimationFrame = (callback) => callback();

            const { createDeliveryTaskPool } = await import("__TASK_POOL_URI__");
            const { createWorkspaceActions } = await import("__ACTIONS_URI__");
            const board = {
              orders: [
                {
                  order_id: "TARGET",
                  invoice_number: "185517",
                  invoice_date: "2026-08-11",
                  order_no: "32074",
                  company_name: "Custom Performance Garage",
                  phone: "",
                  delivery_address: "1 Test Road",
                  suburb: "Hallam",
                  postcode: "3803",
                  delivery_date: "2026-08-13",
                  urgency: "Normal",
                  pallet_quantity: 0,
                  loose_bags_quantity: 5,
                  carton_quantity: 0,
                  product_lines: [],
                },
                {
                  order_id: "OTHER",
                  invoice_number: "299999",
                  invoice_date: "2026-09-20",
                  order_no: "OTHER",
                  company_name: "Other Buyer",
                  phone: "",
                  delivery_address: "2 Test Road",
                  suburb: "Seville",
                  postcode: "9999",
                  delivery_date: "2026-09-20",
                  urgency: "Normal",
                  pallet_quantity: 0,
                  loose_bags_quantity: 0,
                  carton_quantity: 0,
                  product_lines: [],
                },
              ],
              assignments: [],
              drivers: [],
            };
            const state = {
              isLoggedIn: true,
              activeWorkspace: "delivery",
              workspaceRoute: "delivery/task-pool",
              dispatchDate: "2026-08-12",
              deliveryBoard: board,
              deliveryTaskPoolFilters: { search: "", delivery_date: "", urgency: "All" },
              deliveryAssignmentDrafts: {},
              deliveryBusyActionKeys: {},
            };
            let renders = 0;
            let boardGets = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {
                renders += 1;
                body.children = [];
                document.activeElement = null;
              },
              api: {
                getDeliveryWorkspaceBoard: async () => {
                  boardGets += 1;
                  return board;
                },
              },
            });
            body.append(createDeliveryTaskPool(board, state, actions));
            const search = body.querySelectorAll("input")[0];
            search.focus();

            const typeText = (text) => {
              for (const character of text) {
                search.value += character;
                search.setSelectionRange(search.value.length, search.value.length);
                search.listeners.input[0]();
                if (document.activeElement !== search) {
                  throw new Error(`Search focus was lost after ${search.value}`);
                }
                if (search.selectionStart !== search.value.length
                    || search.selectionEnd !== search.value.length) {
                  throw new Error(`Search caret moved after ${search.value}`);
                }
                if (body.querySelectorAll("input")[0] !== search) {
                  throw new Error(`Search input node was replaced after ${search.value}`);
                }
                const cards = body.querySelectorAll(".workspace-order-card");
                if (cards.length !== 1 || !cards[0].textContent.includes("185517")) {
                  throw new Error(`Live filtered results were stale after ${search.value}`);
                }
                const count = body.querySelector(".workspace-filter-count");
                if (count.textContent !== "1 of 2 visible Orders") {
                  throw new Error(`Visible metric was stale after ${search.value}: ${count.textContent}`);
                }
                if (state.deliveryTaskPoolFilters.search !== search.value) {
                  throw new Error("Search state did not accumulate the input value");
                }
                if (state.workspaceRoute !== "delivery/task-pool") {
                  throw new Error("Search changed the workspace route");
                }
                if (window.scrollX !== 17 || window.scrollY !== 321) {
                  throw new Error("Search changed the page scroll position");
                }
              }
            };

            typeText("185517");
            search.value = "";
            search.setSelectionRange(0, 0);
            search.listeners.input[0]();
            typeText("custom performance");
            if (renders !== 0) throw new Error(`Search broadly rendered ${renders} times`);
            if (boardGets !== 0) throw new Error(`Search fetched the board ${boardGets} times`);
            if (scrollCalls.some(([x, y]) => x !== 17 || y !== 321)) {
              throw new Error("Search restored an incorrect scroll position");
            }
            """
        ).replace("__TASK_POOL_URI__", task_pool_uri).replace(
            "__ACTIONS_URI__", actions_uri
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_delivery_invoice_date_is_visible_editable_searchable_and_mapped(self):
        order_actions = self._read("js/actions/workspace/delivery-task-pool-actions.js")
        order_modal = self._read("js/render/delivery/delivery-order-modal-renderer.js")
        attache_modal = self._read("js/render/delivery/delivery-attache-modal-renderer.js")
        task_pool = self._read("js/render/delivery/delivery-task-pool-renderer.js")

        self.assertIn('invoice_date: order.invoice_date || ""', order_actions)
        self.assertIn('invoice_date: form.invoice_date || null', order_actions)
        self.assertIn('["Invoice Date", order.invoice_date]', order_modal)
        self.assertIn('createBoundInput("Invoice Date"', order_modal)
        self.assertIn('createInlineMeta("Invoice Date", row.invoice_date)', attache_modal)
        self.assertIn('createInlineField("Invoice Date"', attache_modal)
        self.assertIn('createChip(`Invoice Date:', task_pool)
        search_block = task_pool.split("function deliveryOrderSearchText", 1)[1]
        self.assertIn("order.invoice_date", search_block)

    def test_attache_review_expand_collapse_preserves_scroll_state_and_summary_order(self):
        renderer_uri = (
            FRONTEND_ROOT / "js/render/delivery/delivery-attache-modal-renderer.js"
        ).as_uri()
        actions_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            r"""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.nodeType = tagName === "#text" ? 3 : 1;
                this.children = [];
                this.parentNode = null;
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.hidden = false;
                this.checked = false;
                this.value = "";
                this.type = "";
                this.scrollTop = 0;
                this.scrollLeft = 0;
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\s+/).includes(token),
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) {
                this._text = String(value ?? "");
                this.children = [];
              }
              append(...children) {
                children.forEach((child) => {
                  if (child === null || child === undefined) return;
                  child.parentNode = this;
                  this.children.push(child);
                });
              }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              getAttribute(name) { return this.attributes[name]; }
              addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
              focus(options) {
                this.focusOptions = options;
                document.activeElement = this;
              }
              matches(selector) {
                if (selector.startsWith(".")) {
                  return this.classList.contains(selector.slice(1));
                }
                return String(this.tagName || "").toLowerCase() === selector.toLowerCase();
              }
              closest(selector) {
                let current = this;
                while (current) {
                  if (current.matches?.(selector)) return current;
                  current = current.parentNode;
                }
                return null;
              }
              replaceWith(replacement) {
                if (!this.parentNode) throw new Error("Cannot replace a detached node");
                const index = this.parentNode.children.indexOf(this);
                replacement.parentNode = this.parentNode;
                this.parentNode.children[index] = replacement;
                this.parentNode = null;
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  if (node.matches?.(selector)) matches.push(node);
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }

            const body = new FakeNode("body");
            globalThis.document = {
              activeElement: null,
              body,
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
              createDocumentFragment: () => new FakeNode("#fragment"),
            };

            const { createAttacheReviewRow } = await import("__RENDERER_URI__");
            const { createDeliveryAttacheActions } = await import("__ACTIONS_URI__");
            const row = {
              row_id: "TOTAL-TOOLS",
              invoice_number: "185505",
              invoice_date: "2026-08-11",
              order_no: "129534",
              company_name: "TOTAL TOOLS - DANDENONG",
              phone: "9798 4533",
              delivery_address: "221-232 GREENS ROAD",
              suburb: "DANDENONG",
              postcode: "3175",
              delivery_date: "2026-08-14",
              start_time: "",
              end_time: "",
              urgency: "Normal",
              pallet_quantity: 1,
              loose_bags_quantity: 0,
              carton_quantity: 0,
              product_lines: [],
              warnings: [],
              note: "",
              selected: true,
              importable: true,
              is_duplicate: false,
            };
            const state = {
              workspaceRoute: "delivery/task-pool",
              deliveryAttacheImportState: {
                isOpen: true,
                step: "review",
                rows: [row],
                expandedRowIds: {},
                search: "dandenong",
                filter: "WARNING",
              },
            };
            let renders = 0;
            let boardGets = 0;
            const actions = createDeliveryAttacheActions({
              state,
              renderWorkspace: () => { renders += 1; },
              confirmAction: () => true,
              navigateWorkspaceRoute: () => { throw new Error("Expand changed route"); },
              api: {
                getDeliveryWorkspaceBoard: async () => {
                  boardGets += 1;
                  return {};
                },
              },
              actions: {},
            });
            const modalBody = new FakeNode("div");
            modalBody.className = "workspace-modal-body";
            const reviewList = new FakeNode("div");
            reviewList.className = "workspace-attache-review-list";
            reviewList.append(createAttacheReviewRow(
              row,
              state.deliveryAttacheImportState,
              actions,
            ));
            modalBody.append(reviewList);
            body.append(modalBody);
            modalBody.scrollTop = 900;

            let card = reviewList.children[0];
            const labels = card.querySelectorAll(".workspace-inline-meta")
              .map((item) => item.children[0].textContent);
            const expectedLabels = [
              "Invoice",
              "Invoice Date",
              "Order",
              "Customer",
              "Suburb",
              "Delivery Date",
              "Load",
            ];
            if (labels.join("|") !== expectedLabels.join("|")) {
              throw new Error(`Collapsed summary order was ${labels.join("|")}`);
            }

            const click = (button) => button.listeners.click[0]({ stopPropagation: () => {} });
            let toggle = card.querySelector("button");
            toggle.focus();
            click(toggle);
            card = reviewList.children[0];
            toggle = card.querySelector("button");
            if (!state.deliveryAttacheImportState.expandedRowIds[row.row_id]) {
              throw new Error("Expand did not update state");
            }
            if (!card.querySelector(".workspace-attache-expanded-editor")) {
              throw new Error("Expand did not patch the review row");
            }
            if (modalBody.scrollTop !== 900) throw new Error("Expand reset modal scroll");
            if (document.activeElement !== toggle) throw new Error("Expand lost logical focus");
            if (!toggle.focusOptions?.preventScroll) {
              throw new Error("Expand focus may scroll the modal");
            }
            if (!row.selected || state.deliveryAttacheImportState.search !== "dandenong"
                || state.deliveryAttacheImportState.filter !== "WARNING") {
              throw new Error("Expand lost review selection/filter state");
            }
            if (!state.deliveryAttacheImportState.isOpen) throw new Error("Expand closed modal");
            if (state.workspaceRoute !== "delivery/task-pool") throw new Error("Expand changed route");

            click(toggle);
            card = reviewList.children[0];
            toggle = card.querySelector("button");
            if (state.deliveryAttacheImportState.expandedRowIds[row.row_id]) {
              throw new Error("Collapse did not update state");
            }
            if (card.querySelector(".workspace-attache-expanded-editor")) {
              throw new Error("Collapse did not patch the review row");
            }
            if (modalBody.scrollTop !== 900) throw new Error("Collapse reset modal scroll");
            if (document.activeElement !== toggle) throw new Error("Collapse lost logical focus");
            if (!toggle.focusOptions?.preventScroll) {
              throw new Error("Collapse focus may scroll the modal");
            }
            if (renders !== 0) throw new Error(`Expand/Collapse broadly rendered ${renders} times`);
            if (boardGets !== 0) throw new Error(`Expand/Collapse fetched board ${boardGets} times`);
            """
        ).replace("__RENDERER_URI__", renderer_uri).replace(
            "__ACTIONS_URI__", actions_uri
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_delivery_task_pool_applies_priority_after_filters_and_urgent_styles(self):
        task_pool_block = self.delivery_renderer.split(
            "function createDeliveryTaskPool", 1
        )[1].split("function createDeliveryTaskPoolPanel", 1)[0]
        self.assertIn("sortDeliveryTaskPoolOrders(", task_pool_block)
        self.assertIn("filterDeliveryTaskPoolOrders(unassignedOrders", task_pool_block)
        self.assertIn(
            "const filteredOrders = sortDeliveryTaskPoolOrders(\n"
            "    filterDeliveryTaskPoolOrders(unassignedOrders",
            task_pool_block,
        )
        self.assertIn("normalizeDeliveryOrderUrgency(order.urgency)", self.delivery_renderer)
        self.assertIn("normalizeDeliveryOrderUrgency(urgency)", self.delivery_renderer)
        self.assertIn('card.classList.toggle("workspace-order-card-urgent", isUrgent)', self.delivery_renderer)
        self.assertIn('urgencyBadge.classList.toggle("workspace-order-badge-urgent", isUrgent)', self.delivery_renderer)
        self.assertIn('urgencyChip.classList.toggle("workspace-order-chip-urgent", isUrgent)', self.delivery_renderer)
        self.assertIn('card.setAttribute("role", "button")', self.delivery_renderer)
        self.assertIn(
            'controls.addEventListener("click", (event) => event.stopPropagation())',
            self.delivery_renderer,
        )
        self.assertIn(
            'controls.addEventListener("keydown", (event) => event.stopPropagation())',
            self.delivery_renderer,
        )
        self.assertIn('const driverSelect = createSelect(', self.delivery_renderer)
        self.assertIn('const tripSelect = createSelect(', self.delivery_renderer)
        self.assertIn('"Assign",', self.delivery_renderer)
        self.assertIn("workspace-order-card-urgent", self.styles)
        self.assertIn("workspace-order-badge-urgent", self.styles)
        self.assertIn("workspace-order-chip-urgent", self.styles)
        urgent_css = self.styles.split(".workspace-order-card-urgent", 1)[1].split(
            ".workspace-order-card-body", 1
        )[0]
        self.assertIn("var(--danger)", urgent_css)
        self.assertIn("var(--danger-soft)", urgent_css)
        self.assertNotIn("opshop", urgent_css.lower())

    def test_vehicle_autosave_serializes_latest_intent_per_driver(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            async function runScenario(latestVehicleId) {
              const firstResponse = deferred();
              const state = {
                isLoggedIn: true,
                workspaceRoute: "delivery/trip-summary",
                activeWorkspace: "delivery",
                dispatchDate: "2026-06-29",
                deliveryTripSummaryDate: "2026-06-29",
                deliveryBoard: {
                  orders: [], assignments: [],
                  drivers: [{ driver_id: "A", name: "Driver A" }],
                  vehicles: [], driver_vehicle_assignments: [],
                },
                deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
                deliveryVehicleClaimSequence: 0, deliveryVehicleErrors: {},
                deliveryVehiclePendingKeys: {}, deliveryBusyActionKeys: {},
              };
              const writes = [];
              let activeWrites = 0;
              let maxActiveWrites = 0;
              const updateBoard = (vehicleId) => ({
                ...state.deliveryBoard,
                driver_vehicle_assignments: vehicleId ? [{
                  delivery_date: "2026-06-29", driver_id: "A", vehicle_id: vehicleId,
                }] : [],
              });
              const api = {
                assignDeliveryWorkspaceVehicle: async (payload) => {
                  activeWrites += 1;
                  maxActiveWrites = Math.max(maxActiveWrites, activeWrites);
                  writes.push(payload.vehicle_id);
                  if (writes.length === 1) {
                    await firstResponse.promise;
                  }
                  activeWrites -= 1;
                  return updateBoard(payload.vehicle_id);
                },
                clearDeliveryWorkspaceVehicle: async () => {
                  activeWrites += 1;
                  maxActiveWrites = Math.max(maxActiveWrites, activeWrites);
                  writes.push("");
                  activeWrites -= 1;
                  return updateBoard("");
                },
              };
              const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
              const first = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
              await Promise.resolve();
              const intermediate = actions.updateDeliveryVehicleSelection(
                "2026-06-29", "A", "V2",
              );
              const latest = actions.updateDeliveryVehicleSelection(
                "2026-06-29", "A", latestVehicleId,
              );
              if (writes.join(",") !== "V1") {
                throw new Error("latest Vehicle write was sent before the first completed");
              }
              firstResponse.resolve();
              await Promise.all([first, intermediate, latest]);
              const finalVehicle = state.deliveryBoard.driver_vehicle_assignments[0]?.vehicle_id || "";
              if (writes.join(",") !== `V1,${latestVehicleId}` || finalVehicle !== latestVehicleId) {
                throw new Error(`serialized Vehicle writes did not finish at ${latestVehicleId || "blank"}`);
              }
              if (maxActiveWrites !== 1 || Object.keys(state.deliveryVehicleDrafts).length) {
                throw new Error("same-Driver Vehicle writes overlapped or left stale intent");
              }
            }

            await runScenario("V2");
            await runScenario("");
            """
        )

    def test_leaving_trip_summary_clears_vehicle_intent_and_reloads_saved_state(self):
        load_route_block = self.workspace_actions.split(
            "async function loadWorkspaceRoute", 1
        )[1].split("async function loadMigrationStatus", 1)[0]
        self.assertLess(
            load_route_block.index('route !== "delivery/trip-summary"'),
            load_route_block.index("!state.isLoggedIn"),
        )

    def test_vehicle_queue_route_exit_keeps_physical_writes_serial_and_new_intent_current(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }
            async function flush() {
              for (let index = 0; index < 8; index += 1) {
                await Promise.resolve();
              }
            }

            async function runScenario(finalVehicleId, failFirst) {
              const firstGate = deferred();
              const secondGate = deferred();
              let persistedVehicleId = "";
              let activeWrites = 0;
              let maxActiveWrites = 0;
              const writes = [];
              const board = () => ({
                orders: [], assignments: [],
                drivers: [{ driver_id: "A", name: "Driver A" }],
                vehicles: [
                  { vehicle_id: "V1", rego: "ONE", pallet_capacity: 10 },
                  { vehicle_id: "V2", rego: "TWO", pallet_capacity: 20 },
                ],
                driver_vehicle_assignments: persistedVehicleId ? [{
                  dispatch_date: "2026-06-29",
                  delivery_date: "2026-06-29",
                  driver_id: "A",
                  vehicle_id: persistedVehicleId,
                }] : [],
              });
              const state = {
                isLoggedIn: true,
                workspaceRoute: "delivery/trip-summary",
                activeWorkspace: "delivery",
                dispatchDate: "2026-06-29",
                deliveryTripSummaryDate: "2026-06-29",
                deliveryBoard: board(), deliveryRunSheets: [],
                deliveryAssignmentDrafts: {}, deliveryVehicleDrafts: {},
                deliveryVehicleClaims: {}, deliveryVehicleClaimSequence: 0,
                deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
                deliveryBusyActionKeys: {}, deliveryActionError: "",
              };
              async function write(vehicleId) {
                const writeIndex = writes.length;
                writes.push(vehicleId);
                activeWrites += 1;
                maxActiveWrites = Math.max(maxActiveWrites, activeWrites);
                try {
                  await (writeIndex === 0 ? firstGate.promise : secondGate.promise);
                  if (writeIndex === 0 && failFirst) {
                    throw new Error("old V1 failed");
                  }
                  persistedVehicleId = vehicleId;
                  return board();
                } finally {
                  activeWrites -= 1;
                }
              }
              const api = {
                assignDeliveryWorkspaceVehicle: async (payload) => write(payload.vehicle_id),
                clearDeliveryWorkspaceVehicle: async () => write(""),
                getDeliveryWorkspaceBoard: async () => board(),
                listDeliveryRunSheets: async () => [],
              };
              const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
              const key = "2026-06-29|A";

              const first = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
              await flush();
              if (writes.join(",") !== "V1" || !state.deliveryVehiclePendingKeys[key]) {
                throw new Error("old V1 did not enter its physical and logical queues");
              }
              state.deliveryVehicleErrors[key] = "old error";
              state.workspaceRoute = "delivery/task-pool";
              await actions.loadWorkspaceRoute("delivery/task-pool");
              for (const field of [
                "deliveryVehicleDrafts",
                "deliveryVehicleClaims",
                "deliveryVehicleErrors",
                "deliveryVehiclePendingKeys",
              ]) {
                if (Object.keys(state[field] || {}).length) {
                  throw new Error(`${field} survived route exit`);
                }
              }

              state.workspaceRoute = "delivery/trip-summary";
              state.activeWorkspace = "delivery";
              await actions.loadWorkspaceRoute("delivery/trip-summary");
              const latest = actions.updateDeliveryVehicleSelection(
                "2026-06-29", "A", finalVehicleId,
              );
              if (state.deliveryVehicleDrafts[key] !== finalVehicleId) {
                throw new Error("new route intent did not appear immediately");
              }
              if (!state.deliveryVehiclePendingKeys[key]) {
                throw new Error("new route intent did not become pending immediately");
              }
              if (writes.join(",") !== "V1" || maxActiveWrites !== 1) {
                throw new Error("new route intent overlapped the old physical write");
              }

              firstGate.resolve();
              await flush();
              const expectedWrites = `V1,${finalVehicleId}`;
              if (writes.join(",") !== expectedWrites) {
                throw new Error(`new physical write did not follow V1: ${writes.join(",")}`);
              }
              if (!state.deliveryVehiclePendingKeys[key]) {
                throw new Error("old logical finalizer removed the new pending state");
              }
              if (state.deliveryVehicleDrafts[key] !== finalVehicleId) {
                throw new Error("old response removed or replaced the new draft");
              }
              if (maxActiveWrites !== 1) {
                throw new Error("same Driver/date physical writes were concurrent");
              }

              secondGate.resolve();
              await Promise.all([first, latest]);
              const displayedVehicleId =
                state.deliveryBoard.driver_vehicle_assignments[0]?.vehicle_id || "";
              if (persistedVehicleId !== finalVehicleId || displayedVehicleId !== finalVehicleId) {
                throw new Error(`latest intent was not final: ${persistedVehicleId}/${displayedVehicleId}`);
              }
              if (
                state.deliveryVehiclePendingKeys[key]
                || Object.prototype.hasOwnProperty.call(state.deliveryVehicleDrafts, key)
                || state.deliveryVehicleErrors[key]
              ) {
                throw new Error("completed latest queue left transient UI state");
              }
              await actions.loadWorkspaceRoute("delivery/trip-summary");
              const refreshedVehicleId =
                state.deliveryBoard.driver_vehicle_assignments[0]?.vehicle_id || "";
              if (refreshedVehicleId !== finalVehicleId) {
                throw new Error("refresh did not preserve the latest persisted Vehicle");
              }
            }

            await runScenario("V2", false);
            await runScenario("", false);
            await runScenario("V2", true);
            await runScenario("", true);
            """
        )

    def test_vehicle_queue_logout_invalidates_old_response_before_immediate_login(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }
            async function flush() {
              for (let index = 0; index < 8; index += 1) {
                await Promise.resolve();
              }
            }
            const firstGate = deferred();
            const secondGate = deferred();
            const writes = [];
            let persistedVehicleId = "";
            const board = () => ({
              orders: [], assignments: [],
              drivers: [{ driver_id: "A", name: "Driver A" }], vehicles: [],
              driver_vehicle_assignments: persistedVehicleId ? [{
                delivery_date: "2026-06-29", driver_id: "A", vehicle_id: persistedVehicleId,
              }] : [],
            });
            const state = {
              isLoggedIn: true, workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery", dispatchDate: "2026-06-29",
              deliveryTripSummaryDate: "2026-06-29", deliveryBoard: board(),
              deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
              deliveryVehicleClaimSequence: 0, deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {}, deliveryBusyActionKeys: {},
            };
            const api = {
              assignDeliveryWorkspaceVehicle: async (payload) => {
                const index = writes.length;
                writes.push(payload.vehicle_id);
                await (index === 0 ? firstGate.promise : secondGate.promise);
                persistedVehicleId = payload.vehicle_id;
                return board();
              },
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
            const oldWrite = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
            await flush();
            state.isLoggedIn = false;
            actions.resetDeliveryVehicleTransientState();
            state.isLoggedIn = true;
            state.workspaceRoute = "delivery/trip-summary";
            state.activeWorkspace = "delivery";
            const newWrite = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V2");
            if (state.deliveryVehicleDrafts["2026-06-29|A"] !== "V2") {
              throw new Error("new login did not own the current Vehicle draft");
            }
            firstGate.resolve();
            await flush();
            if (writes.join(",") !== "V1,V2") {
              throw new Error("new login Vehicle write did not follow the old physical tail");
            }
            if (state.deliveryBoard.driver_vehicle_assignments.length) {
              throw new Error("old login response overwrote the new session board");
            }
            if (!state.deliveryVehiclePendingKeys["2026-06-29|A"]) {
              throw new Error("old login finalizer removed new login pending state");
            }
            secondGate.resolve();
            await Promise.all([oldWrite, newWrite]);
            if (state.deliveryBoard.driver_vehicle_assignments[0]?.vehicle_id !== "V2") {
              throw new Error("new login did not finish with V2");
            }
            """
        )
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const vehicleWrite = deferred();
            let persistedVehicleId = "";
            const board = () => ({
              orders: [], assignments: [],
              drivers: [{ driver_id: "A", name: "Driver A" }],
              vehicles: [{ vehicle_id: "V1", rego: "ONE", pallet_capacity: 12 }],
              driver_vehicle_assignments: persistedVehicleId ? [{
                dispatch_date: "2026-06-29",
                delivery_date: "2026-06-29",
                driver_id: "A",
                vehicle_id: persistedVehicleId,
              }] : [],
            });
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryTripSummaryDate: "2026-06-29",
              deliveryBoard: board(), deliveryRunSheets: [],
              deliveryTripSummaryBoard: null, deliveryTripSummaryRunSheets: [],
              deliveryAssignmentDrafts: {}, deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {}, deliveryVehicleClaimSequence: 0,
              deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
              deliveryBusyActionKeys: {}, deliveryActionError: "",
            };
            const api = {
              assignDeliveryWorkspaceVehicle: async () => vehicleWrite.promise,
              getDeliveryWorkspaceBoard: async () => board(),
              getDeliveryTripSummary: async () => board(),
              listDeliveryRunSheets: async () => [],
              listDeliveryRunSheetsByDeliveryDate: async () => [],
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
            const pending = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
            await Promise.resolve();
            if (!state.deliveryVehiclePendingKeys["2026-06-29|A"]) {
              throw new Error("Vehicle write was not pending before route exit");
            }

            state.workspaceRoute = "delivery/task-pool";
            await actions.loadWorkspaceRoute("delivery/task-pool");
            for (const field of [
              "deliveryVehicleDrafts",
              "deliveryVehicleClaims",
              "deliveryVehicleErrors",
              "deliveryVehiclePendingKeys",
            ]) {
              if (Object.keys(state[field] || {}).length) {
                throw new Error(`${field} survived Trip Summary exit`);
              }
            }

            persistedVehicleId = "V1";
            vehicleWrite.resolve(board());
            await pending;
            if ((state.deliveryBoard.driver_vehicle_assignments || []).length) {
              throw new Error("stale Vehicle response overwrote the current route board");
            }

            state.workspaceRoute = "delivery/trip-summary";
            await actions.loadWorkspaceRoute("delivery/trip-summary");
            if (state.deliveryTripSummaryBoard.driver_vehicle_assignments[0]?.vehicle_id !== "V1") {
              throw new Error("Trip Summary did not reload the persisted scoped board state");
            }
            """
        )

    def test_delivery_order_mutations_update_in_place_preserve_scroll_and_default_trip_one(self):
        self._run_workspace_actions_script(
            """
            window.scrollX = 18;
            window.scrollY = 640;
            const restored = [];
            window.requestAnimationFrame = (callback) => callback();
            window.scrollTo = (x, y) => restored.push([x, y]);
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryTripSummaryDate: "2026-06-29",
              deliveryBoard: {
                orders: [{ order_id: "ORDER-1", delivery_date: "2026-06-29" }],
                assignments: [], drivers: [], driver_vehicle_assignments: [],
              },
              deliveryActionError: "", deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: { "ORDER-1": { driver_id: "A" } },
              deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
              deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
            };
            const payloads = [];
            const boardWithTrip = (tripNo) => ({
              ...state.deliveryBoard,
              assignments: [{ task_id: "ORDER-1", driver_id: "A", trip_no: tripNo }],
            });
            const api = {
              assignDeliveryWorkspaceOrder: async (payload) => {
                payloads.push(payload);
                return boardWithTrip(payload.trip_no);
              },
              unassignDeliveryWorkspaceOrder: async () => ({
                ...state.deliveryBoard, assignments: [],
              }),
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });

            await actions.applyDeliveryOrderAssignment("ORDER-1");
            if (payloads[0].trip_no !== "trip1" || state.deliveryBoard.assignments[0].trip_no !== "trip1") {
              throw new Error("Task Pool Order did not default to Trip 1");
            }
            if (state.deliveryAssignmentDrafts["ORDER-1"]) {
              throw new Error("successful in-place Assign kept its draft");
            }

            state.workspaceRoute = "delivery/trip-summary";
            await actions.moveDeliveryOrderToTrip("ORDER-1", "A", "trip2");
            if (state.deliveryTripSummaryBoard.assignments[0].trip_no !== "trip2") {
              throw new Error("Move did not update the returned board in place");
            }
            await actions.unassignDeliveryOrder("ORDER-1");
            if (state.deliveryTripSummaryBoard.assignments.length) {
              throw new Error("Unassign did not update the returned board in place");
            }
            if (!restored.length || restored.some(([x, y]) => x !== 18 || y !== 640)) {
              throw new Error("Delivery mutation renders did not preserve window scroll");
            }

            actions.updateDeliveryAssignmentDraft("ORDER-1", "trip_no", "trip2");
            if (state.deliveryAssignmentDrafts["ORDER-1"].trip_no !== "trip2") {
              throw new Error("explicit Trip 2 draft did not survive re-render");
            }
            """
        )

    def test_vehicle_autosave_queues_are_independent_across_drivers_and_merge_responses(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }
            const responses = { A: deferred(), B: deferred() };
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryTripSummaryDate: "2026-06-29",
              deliveryBoard: {
                orders: [], assignments: [],
                drivers: [
                  { driver_id: "A", name: "Driver A" },
                  { driver_id: "B", name: "Driver B" },
                ],
                vehicles: [], driver_vehicle_assignments: [],
              },
              deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
              deliveryVehicleClaimSequence: 0, deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {}, deliveryBusyActionKeys: {},
            };
            let activeWrites = 0;
            let maxActiveWrites = 0;
            const api = {
              assignDeliveryWorkspaceVehicle: async (payload) => {
                activeWrites += 1;
                maxActiveWrites = Math.max(maxActiveWrites, activeWrites);
                const board = await responses[payload.driver_id].promise;
                activeWrites -= 1;
                return board;
              },
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
            const first = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
            const second = actions.updateDeliveryVehicleSelection("2026-06-29", "B", "V2");
            await Promise.resolve();
            if (maxActiveWrites !== 2) {
              throw new Error("different Driver Vehicle queues did not run independently");
            }
            responses.B.resolve({
              ...state.deliveryBoard,
              driver_vehicle_assignments: [{
                delivery_date: "2026-06-29", driver_id: "B", vehicle_id: "V2",
              }],
            });
            await Promise.resolve();
            responses.A.resolve({
              ...state.deliveryBoard,
              driver_vehicle_assignments: [{
                delivery_date: "2026-06-29", driver_id: "A", vehicle_id: "V1",
              }],
            });
            await Promise.all([first, second]);
            const saved = state.deliveryBoard.driver_vehicle_assignments
              .map((item) => `${item.driver_id}:${item.vehicle_id}`)
              .sort()
              .join(",");
            if (saved !== "A:V1,B:V2") {
              throw new Error(`out-of-order Driver responses lost an assignment: ${saved}`);
            }
            """
        )

    def test_order_mutation_blocks_do_not_reload_delivery_route(self):
        for function_name, next_function in (
            ("applyDeliveryOrderAssignment", "moveDeliveryOrderToTrip"),
            ("moveDeliveryOrderToTrip", "unassignDeliveryOrder"),
            ("unassignDeliveryOrder", "updateDeliveryVehicleSelection"),
        ):
            block = self.workspace_actions.split(
                f"async function {function_name}", 1
            )[1].split(f"async function {next_function}", 1)[0]
            self.assertNotIn("loadDeliveryRoute", block)
            self.assertIn("state.deliveryBoard = updatedBoard", block)
            self.assertIn("renderDeliveryWorkspacePreservingScroll", block)

        assignment_controls = self.delivery_renderer.split(
            "function createOrderAssignmentControls", 1
        )[1].split("function filterDeliveryTaskPoolOrders", 1)[0]
        self.assertIn('const selectedTripNo = draft.trip_no || "trip1"', assignment_controls)
        self.assertIn('draft.driver_id || ""', assignment_controls)
        self.assertIn("!draft.driver_id", assignment_controls)

    def test_stale_order_mutation_does_not_replace_board_or_restore_old_scroll(self):
        self._run_workspace_actions_script(
            """
            let resolveAssignment;
            window.scrollX = 4;
            window.scrollY = 500;
            const restored = [];
            window.requestAnimationFrame = (callback) => callback();
            window.scrollTo = (x, y) => restored.push([x, y]);
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryBoard: {
                marker: "current", orders: [{ order_id: "ORDER-1" }],
                assignments: [], driver_vehicle_assignments: [],
              },
              deliveryActionError: "", deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {
                "ORDER-1": { driver_id: "A", trip_no: "trip1" },
              },
              deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
              deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
            };
            const api = {
              assignDeliveryWorkspaceOrder: async () => new Promise((resolve) => {
                resolveAssignment = resolve;
              }),
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });
            const pending = actions.applyDeliveryOrderAssignment("ORDER-1");
            const restoresBeforeDateChange = restored.length;
            state.dispatchDate = "2026-06-30";
            state.deliveryBoard = { marker: "new-date", orders: [], assignments: [] };
            resolveAssignment({ marker: "stale", orders: [], assignments: [] });
            await pending;
            if (state.deliveryBoard.marker !== "new-date") {
              throw new Error("stale Order mutation replaced the current board");
            }
            if (restored.length !== restoresBeforeDateChange) {
              throw new Error("stale Order mutation restored scroll from the old date");
            }
            """
        )

    def test_vehicle_selector_auto_saves_preserves_first_claim_and_retries_released_draft(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryBoard: {
                orders: [],
                assignments: [],
                drivers: [
                  { driver_id: "A", name: "Driver A" },
                  { driver_id: "B", name: "Driver B" },
                ],
                vehicles: [
                  { vehicle_id: "V1", rego: "ONE", pallet_capacity: 12 },
                  { vehicle_id: "V2", rego: "TWO", pallet_capacity: 20 },
                ],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {},
              deliveryVehicleClaimSequence: 0,
              deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {},
              opshopBusyActionKeys: {},
            };
            const firstAssignment = deferred();
            let assignCalls = 0;
            let clearCalls = 0;
            const assignedPayloads = [];
            const api = {
              assignDeliveryWorkspaceVehicle: async (payload) => {
                assignCalls += 1;
                assignedPayloads.push(payload);
                if (assignCalls === 1) {
                  return firstAssignment.promise;
                }
                return {
                  ...state.deliveryBoard,
                  driver_vehicle_assignments: [{
                    delivery_date: payload.delivery_date,
                    driver_id: payload.driver_id,
                    vehicle_id: payload.vehicle_id,
                  }],
                };
              },
              clearDeliveryWorkspaceVehicle: async () => {
                clearCalls += 1;
                return { ...state.deliveryBoard, driver_vehicle_assignments: [] };
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const first = actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
            await Promise.resolve();
            await actions.updateDeliveryVehicleSelection("2026-06-29", "B", "V1");
            if (assignCalls !== 1) {
              throw new Error("later duplicate claimant reached the scoped API");
            }
            if (state.deliveryVehicleDrafts["2026-06-29|A"] !== "V1" ||
                state.deliveryVehicleDrafts["2026-06-29|B"] !== "V1") {
              throw new Error("first or later local claimant was not preserved");
            }
            if (!state.deliveryVehiclePendingKeys["2026-06-29|A"] ||
                state.deliveryVehiclePendingKeys["2026-06-29|B"]) {
              throw new Error("automatic save did not isolate busy state to the affected Driver");
            }

            firstAssignment.resolve({
              ...state.deliveryBoard,
              driver_vehicle_assignments: [{
                delivery_date: "2026-06-29",
                driver_id: "A",
                vehicle_id: "V1",
              }],
            });
            await first;
            if (state.deliveryBoard.driver_vehicle_assignments[0].driver_id !== "A") {
              throw new Error("first claimant was not saved");
            }

            await actions.updateDeliveryVehicleSelection("2026-06-29", "A", "");
            await Promise.resolve();
            await Promise.resolve();
            if (clearCalls !== 1) {
              throw new Error("blank selection did not call the scoped clear API");
            }
            if (assignCalls !== 2 || assignedPayloads[1].driver_id !== "B") {
              throw new Error("clearing the first claimant did not release and auto-save the pending draft");
            }
            """
        )

    def test_vehicle_backend_conflict_stays_inline_until_available_selection_saves(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-29",
              deliveryBoard: {
                orders: [], assignments: [],
                drivers: [{ driver_id: "A", name: "Driver A" }],
                vehicles: [
                  { vehicle_id: "V1", rego: "ONE", pallet_capacity: 12 },
                  { vehicle_id: "V2", rego: "TWO", pallet_capacity: 20 },
                ],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {},
              deliveryVehicleClaimSequence: 0,
              deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {},
              opshopBusyActionKeys: {},
            };
            let assignCalls = 0;
            const api = {
              assignDeliveryWorkspaceVehicle: async (payload) => {
                assignCalls += 1;
                if (payload.vehicle_id === "V1") {
                  throw new Error("Vehicle ONE is already assigned to Driver B for this delivery date.");
                }
                return {
                  ...state.deliveryBoard,
                  driver_vehicle_assignments: [{
                    delivery_date: payload.delivery_date,
                    driver_id: payload.driver_id,
                    vehicle_id: payload.vehicle_id,
                  }],
                };
              },
            };
            const actions = createWorkspaceActions({ state, renderWorkspace: () => {}, api });

            await actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V1");
            if (state.deliveryVehicleDrafts["2026-06-29|A"] !== "V1") {
              throw new Error("backend conflict silently reverted the attempted selection");
            }
            if (!state.deliveryVehicleErrors["2026-06-29|A"].includes("Driver B")) {
              throw new Error("backend conflict was not stored as an inline field error");
            }

            await actions.updateDeliveryVehicleSelection("2026-06-29", "A", "V2");
            if (assignCalls !== 2 || state.deliveryVehicleErrors["2026-06-29|A"]) {
              throw new Error("available replacement did not clear the warning and auto-save");
            }
            """
        )

    def test_delivery_trip_summary_actions_use_scoped_payloads_and_allow_history_dates(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryTripSummaryDate: "2026-06-24",
              deliveryBoard: {
                orders: [
                  { order_id: "ORDER-1", delivery_date: "2026-06-22" },
                  { order_id: "ORDER-2", delivery_date: "2026-06-22" },
                ],
                assignments: [],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
            };
            const assignedPayloads = [];
            const generatedPayloads = [];
            const navigatedRoutes = [];
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              assignDeliveryWorkspaceOrder: async (payload) => {
                assignedPayloads.push(payload);
                return state.deliveryBoard;
              },
              createGeneratedDeliveryRunSheet: async (payload) => {
                generatedPayloads.push(payload);
                return { run_sheet_id: "DRS-1" };
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
              navigateWorkspaceRoute: (route) => {
                navigatedRoutes.push(route);
                state.workspaceRoute = route;
                state.activeWorkspace = route.split("/")[0];
                window.location.hash = `#${route}`;
              },
            });

            actions.updateDeliveryTripSummaryDate("2026-06-22");
            if (state.deliveryTripSummaryDate !== "2026-06-22") {
              throw new Error("Trip Summary rejected historical delivery date");
            }
            actions.updateDeliveryAssignmentDraft("ORDER-1", "driver_id", "D001");
            actions.updateDeliveryAssignmentDraft("ORDER-1", "trip_no", "trip1");
            await actions.applyDeliveryOrderAssignment("ORDER-1");
            await actions.moveDeliveryOrderToTrip("ORDER-2", "D001", "trip2");
            const expectedKeys = "driver_id,order_id,trip_no";
            for (const payload of assignedPayloads) {
              if (Object.keys(payload).sort().join(",") !== expectedKeys) {
                throw new Error("Delivery assignment payload contains unexpected fields");
              }
            }
            if (assignedPayloads[0].order_id !== "ORDER-1" ||
                assignedPayloads[0].driver_id !== "D001" ||
                assignedPayloads[0].trip_no !== "trip1") {
              throw new Error("Add Order payload was not scoped correctly");
            }
            if (assignedPayloads[1].order_id !== "ORDER-2" ||
                assignedPayloads[1].trip_no !== "trip2") {
              throw new Error("Move Order payload was not scoped correctly");
            }

            actions.generateDeliveryRunSheet({
              delivery_date: "2026-06-22",
              driver_id: "D001",
              driver_name: "Driver One",
              orders: [{ order_id: "ORDER-1" }],
              totals: {},
            });
            if (generatedPayloads.length !== 0) {
              throw new Error("opening Delivery confirmation called Generate API");
            }
            await actions.confirmGenerateDeliveryRunSheet();
            if (generatedPayloads[0].dispatch_date !== "2026-06-24" ||
                generatedPayloads[0].delivery_date !== "2026-06-22" ||
                generatedPayloads[0].driver_id !== "D001") {
              throw new Error("Generate Run Sheet payload was not scoped correctly");
            }
            if (state.workspaceRoute !== "delivery/run-sheet" ||
                window.location.hash !== "#delivery/run-sheet" ||
                navigatedRoutes.join(",") !== "delivery/run-sheet") {
              throw new Error("Generate did not navigate to Delivery Run Sheets");
            }
            """
        )

    def test_delivery_generate_ignores_dispatch_changes_but_rejects_stale_routes(self):
        self._run_workspace_actions_script(
            """
            async function runScenario(mutator, shouldNavigate) {
              const state = {
                isLoggedIn: true,
                workspaceRoute: "delivery/trip-summary",
                activeWorkspace: "delivery",
                dispatchDate: "2026-06-24",
                deliveryTripSummaryDate: "2026-06-24",
                deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
                deliveryRunSheets: [],
                deliveryActionError: "",
                deliveryBusyActionKeys: {},
                deliveryAssignmentDrafts: {},
                deliveryVehicleDrafts: {},
                opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
                opshopPickupCollections: [],
                opshopActionError: "",
                opshopBusyActionKeys: {},
                opshopAssignmentDrafts: {},
                countrysideRouteGroupDrafts: {},
              };
              let resolveGenerate;
              const api = {
                createGeneratedDeliveryRunSheet: async () => new Promise((resolve) => {
                  resolveGenerate = () => resolve({ run_sheet_id: "DRS-1" });
                }),
              };
              const navigatedRoutes = [];
              const actions = createWorkspaceActions({
                state,
                renderWorkspace: () => {},
                api,
                navigateWorkspaceRoute: (route) => {
                  navigatedRoutes.push(route);
                  state.workspaceRoute = route;
                },
              });
              actions.generateDeliveryRunSheet({
                delivery_date: "2026-06-24",
                driver_id: "D001",
                driver_name: "Driver One",
                orders: [{ order_id: "ORDER-1" }],
                totals: {},
              });
              const pending = actions.confirmGenerateDeliveryRunSheet();
              mutator(state);
              resolveGenerate();
              await pending;
              if (shouldNavigate && navigatedRoutes.join(",") !== "delivery/run-sheet") {
                throw new Error("Dispatch-only change incorrectly made Generate stale");
              }
              if (!shouldNavigate && navigatedRoutes.length !== 0) {
                throw new Error("Stale route Generate response navigated unexpectedly");
              }
            }

            await runScenario((state) => { state.dispatchDate = "2026-06-25"; }, true);
            await runScenario((state) => { state.workspaceRoute = "delivery/task-pool"; }, false);
            await runScenario((state) => {
              state.workspaceRoute = "opshop/regular";
              state.activeWorkspace = "opshop";
            }, false);
            """
        )

    def test_generation_confirmations_gate_api_and_prevent_double_submit(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const deliveryGate = deferred();
            let deliveryCalls = 0;
            const deliveryState = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-07-06",
              deliveryTripSummaryDate: "2026-07-06",
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryGenerationConfirmation: null,
              deliveryAssignmentDrafts: {}, deliveryVehicleDrafts: {},
              opshopBusyActionKeys: {}, opshopGenerationConfirmation: null,
            };
            const deliveryRoutes = [];
            const deliveryActions = createWorkspaceActions({
              state: deliveryState,
              renderWorkspace: () => {},
              api: {
                createGeneratedDeliveryRunSheet: async () => {
                  deliveryCalls += 1;
                  return deliveryGate.promise;
                },
              },
              navigateWorkspaceRoute: (route) => {
                deliveryRoutes.push(route);
                deliveryState.workspaceRoute = route;
              },
            });
            const deliveryCandidate = {
              delivery_date: "2026-07-06", driver_id: "D003",
              driver_name: "John Georgiadis",
              orders: [{ order_id: "ORDER-1", order_number: "1001" }],
              totals: { pallets: 1, bags: 0, cartons: 2 },
            };
            deliveryActions.generateDeliveryRunSheet(deliveryCandidate);
            if (deliveryCalls !== 0 || !deliveryState.deliveryGenerationConfirmation) {
              throw new Error("Delivery confirmation opening mutated server state");
            }
            deliveryActions.closeDeliveryGenerationConfirmation();
            if (deliveryCalls !== 0 || deliveryState.deliveryGenerationConfirmation) {
              throw new Error("Delivery confirmation Cancel mutated server state");
            }
            deliveryActions.generateDeliveryRunSheet(deliveryCandidate);
            const firstDeliveryConfirm = deliveryActions.confirmGenerateDeliveryRunSheet();
            const secondDeliveryConfirm = deliveryActions.confirmGenerateDeliveryRunSheet();
            if (deliveryCalls !== 1) {
              throw new Error(`Delivery rapid confirm made ${deliveryCalls} API calls`);
            }
            deliveryActions.closeDeliveryGenerationConfirmation();
            if (!deliveryState.deliveryGenerationConfirmation) {
              throw new Error("Delivery confirmation closed while Generate was pending");
            }
            deliveryGate.resolve({ run_sheet_id: "DRS-1" });
            await Promise.all([firstDeliveryConfirm, secondDeliveryConfirm]);
            if (deliveryRoutes.join(",") !== "delivery/run-sheet") {
              throw new Error("Delivery confirmed Generate did not continue existing navigation");
            }

            const opshopGate = deferred();
            let opshopCalls = 0;
            const opshopState = {
              isLoggedIn: true,
              workspaceRoute: "opshop/trip-summary",
              activeWorkspace: "opshop",
              dispatchDate: "2026-07-06",
              opshopTripSummaryDate: "2026-07-06",
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              opshopActionError: "", opshopBusyActionKeys: {},
              opshopGenerationConfirmation: null,
              opshopAssignmentDrafts: {}, countrysideRouteGroupDrafts: {},
              deliveryBusyActionKeys: {}, deliveryGenerationConfirmation: null,
            };
            const opshopActions = createWorkspaceActions({
              state: opshopState,
              renderWorkspace: () => {},
              api: {
                createGeneratedOpShopPickupCollection: async () => {
                  opshopCalls += 1;
                  return opshopGate.promise;
                },
                getOpShopWorkspaceBoard: async () => opshopState.opshopBoard,
                listOpShopPickupCollections: async () => [],
              },
            });
            const pickups = Array.from({ length: 5 }, (_, index) => ({
              pickup_task_id: `P-${index + 1}`,
              opshop_name: `Regular ${index + 1}`,
              pickup_date: "2026-07-06",
              run_type: "REGULAR",
            }));
            const opshopCandidate = {
              pickup_date: "2026-07-06", driver_id: "D003",
              driver_name: "John Georgiadis", pickups,
              regular_count: 5, oncall_count: 0, countryside_count: 0,
            };
            opshopActions.generateOpShopPickupCollection(opshopCandidate);
            if (opshopCalls !== 0 || opshopState.opshopGenerationConfirmation.regular_count !== 5) {
              throw new Error("OP SHOP confirmation opening mutated or lost its five-pickup preview");
            }
            opshopActions.closeOpShopGenerationConfirmation();
            if (opshopCalls !== 0 || opshopState.opshopGenerationConfirmation) {
              throw new Error("OP SHOP confirmation Cancel mutated server state");
            }
            opshopActions.generateOpShopPickupCollection(opshopCandidate);
            const firstOpShopConfirm = opshopActions.confirmGenerateOpShopPickupCollection();
            const secondOpShopConfirm = opshopActions.confirmGenerateOpShopPickupCollection();
            if (opshopCalls !== 1) {
              throw new Error(`OP SHOP rapid confirm made ${opshopCalls} API calls`);
            }
            opshopActions.closeOpShopGenerationConfirmation();
            if (!opshopState.opshopGenerationConfirmation) {
              throw new Error("OP SHOP confirmation closed while Generate was pending");
            }
            opshopGate.resolve({ collection_id: "OPC-1" });
            await Promise.all([firstOpShopConfirm, secondOpShopConfirm]);
            if (opshopState.opshopGenerationConfirmation) {
              throw new Error("successful OP SHOP confirmation did not close");
            }
            """
        )

    def test_generation_confirmations_clear_when_their_trip_summary_route_is_left(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: false,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              deliveryGenerationConfirmation: { driver_id: "D001" },
              opshopGenerationConfirmation: { driver_id: "D002" },
              deliveryBusyActionKeys: {}, opshopBusyActionKeys: {},
              deliveryVehicleDrafts: {}, deliveryVehicleClaims: {},
              deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {},
            });

            await actions.loadWorkspaceRoute("delivery/trip-summary");
            if (!state.deliveryGenerationConfirmation || state.opshopGenerationConfirmation) {
              throw new Error("Delivery route did not retain only its own confirmation");
            }

            state.opshopGenerationConfirmation = { driver_id: "D002" };
            await actions.loadWorkspaceRoute("opshop/trip-summary");
            if (state.deliveryGenerationConfirmation || !state.opshopGenerationConfirmation) {
              throw new Error("OP SHOP route did not retain only its own confirmation");
            }

            await actions.loadWorkspaceRoute("home");
            if (state.deliveryGenerationConfirmation || state.opshopGenerationConfirmation) {
              throw new Error("leaving Trip Summary retained a generation confirmation");
            }
            """
        )

    def test_generation_confirmation_failure_keeps_truthful_modal_error(self):
        self._run_workspace_actions_script(
            """
            const deliveryState = {
              isLoggedIn: true, workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery", dispatchDate: "2026-07-06",
              deliveryActionError: "", deliveryBusyActionKeys: {},
              deliveryGenerationConfirmation: null,
            };
            const deliveryActions = createWorkspaceActions({
              state: deliveryState, renderWorkspace: () => {},
              api: { createGeneratedDeliveryRunSheet: async () => { throw new Error("Delivery changed"); } },
            });
            deliveryActions.generateDeliveryRunSheet({
              delivery_date: "2026-07-06", driver_id: "D003",
              driver_name: "John", orders: [{ order_id: "O-1" }], totals: {},
            });
            await deliveryActions.confirmGenerateDeliveryRunSheet();
            if (deliveryState.deliveryGenerationConfirmation?.error !== "Delivery changed") {
              throw new Error("Delivery rejection did not remain in confirmation modal state");
            }

            const opshopState = {
              isLoggedIn: true, workspaceRoute: "opshop/trip-summary",
              activeWorkspace: "opshop", dispatchDate: "2026-07-06",
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [], opshopActionError: "",
              opshopBusyActionKeys: {}, opshopGenerationConfirmation: null,
              opshopAssignmentDrafts: {}, countrysideRouteGroupDrafts: {},
            };
            let reloads = 0;
            const opshopActions = createWorkspaceActions({
              state: opshopState, renderWorkspace: () => {},
              api: {
                createGeneratedOpShopPickupCollection: async () => { throw new Error("Pickup changed"); },
                getOpShopTripSummary: async () => { reloads += 1; return opshopState.opshopBoard; },
                listOpShopPickupCollectionsByPickupDate: async () => [],
              },
            });
            opshopActions.generateOpShopPickupCollection({
              pickup_date: "2026-07-06", driver_id: "D003", driver_name: "John",
              pickups: [{ pickup_task_id: "P-1" }],
              regular_count: 1, oncall_count: 0, countryside_count: 0,
            });
            await opshopActions.confirmGenerateOpShopPickupCollection();
            if (reloads !== 1 || opshopState.opshopGenerationConfirmation?.error !== "Pickup changed") {
              throw new Error("OP SHOP rejection did not reconcile and remain in confirmation modal state");
            }
            """
        )

    def test_generation_confirmation_renderers_show_required_review_content(self):
        for expected in (
            "Confirm Delivery Run Sheet",
            "Confirm Generate Run Sheet",
            "Assigned Delivery Orders",
            "Vehicle capacity",
            "Cartons",
            'dataset.workspaceGenerate = "delivery"',
            "closeDisabled: isGenerating",
        ):
            self.assertIn(expected, self.delivery_renderer)
        for expected in (
            "Confirm Pickup Collection",
            "Confirm Generate Pickup Collection",
            "Assigned OP SHOP Pickups",
            "Total pickups",
            "Regular",
            "Oncall",
            "Countryside",
            'dataset.workspaceGenerate = "opshop"',
        ):
            self.assertIn(
                expected,
                self.opshop_renderer + self.opshop_workspace_modal_utils,
            )
        self.assertIn("workspace-generation-preview-list", self.styles)
        self.assertIn("overflow-y: auto", self.styles)
        self.assertNotIn("window.confirm(", self.delivery_renderer)
        self.assertNotIn("window.confirm(", self.opshop_renderer)

    def test_opshop_workspace_wires_scoped_assignment_route_and_collection_actions(self):
        self.assertIn("Apply Assignment Changes", self.opshop_renderer)
        self.assertIn("assignCountrysideRouteGroup", self.opshop_renderer)
        self.assertIn("generateOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("saveOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("cancelOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("exportOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("Generate Pickup Collection", self.opshop_renderer)
        self.assertNotIn("Ready to Generate", self.opshop_renderer)
        self.assertIn("pickup_task_id: pickup.pickup_task_id", self.workspace_actions)
        self.assertIn("driver_id: state.opshopAssignmentDrafts[pickup.pickup_task_id] || null", self.workspace_actions)
        self.assertIn("function changedOpShopAssignmentDrafts", self.workspace_actions)
        self.assertIn("assignOpShopWorkspaceCountrysideRouteGroup", self.workspace_actions)
        self.assertIn("Regular pickups", self.opshop_renderer)
        self.assertIn("Oncall pickups", self.opshop_renderer)
        self.assertIn("Countryside pickups", self.opshop_renderer)
        self.assertIn("Total pickups", self.opshop_renderer)
        opshop_apply_block = self.workspace_actions.split(
            "async function applyOpShopAssignmentChanges", 1
        )[1].split("async function unassignOpShopPickup", 1)[0]
        self.assertNotIn("task_type", opshop_apply_block)
        self.assertNotIn("trip_no", opshop_apply_block)

    def test_opshop_generate_failure_reloads_authoritative_board_before_error(self):
        generate_block = self.workspace_actions.split(
            "async function confirmGenerateOpShopPickupCollection", 1
        )[1].split("async function saveOpShopPickupCollection", 1)[0]
        run_action_block = self.workspace_actions.split(
            "async function runOpShopAction", 1
        )[1].split("function getDeliveryAssignmentDraft", 1)[0]

        self.assertNotIn("dispatch_date: context.dispatchDate", generate_block)
        self.assertIn("pickup_date: candidate.pickup_date", generate_block)
        self.assertIn("driver_id: candidate.driver_id", generate_block)
        self.assertIn("await loadOpShopRoute(context.route)", generate_block)
        self.assertIn("state.opshopGenerationConfirmation =", generate_block)
        self.assertIn("error: error.message", generate_block)
        self.assertIn("onError = null", run_action_block)
        self.assertIn('typeof onError === "function"', run_action_block)

    def test_opshop_workspace_uses_three_stage_workflow_and_internal_task_pool_tabs(self):
        self.assertIn('{ route: "opshop/task-pool/regular", label: "Task Pool" }', self.opshop_renderer)
        self.assertIn('{ route: "opshop/trip-summary", label: "Trip Summary" }', self.opshop_renderer)
        self.assertIn('{ route: "opshop/collections", label: "Pickup Collections" }', self.opshop_renderer)
        top_tabs = self.opshop_renderer.split("const OPSHOP_TABS", 1)[1].split("];", 1)[0]
        self.assertNotIn("Templates", top_tabs)
        self.assertIn('{ route: "opshop/history", label: "Saved History" }', top_tabs)
        self.assertIn('{ view: "regular", label: "Regular" }', self.opshop_renderer)
        self.assertIn('{ view: "oncall", label: "Oncall" }', self.opshop_renderer)
        self.assertIn('{ view: "countryside", label: "Countryside" }', self.opshop_renderer)
        self.assertIn('tabs.setAttribute("role", "tablist")', self.opshop_renderer)
        self.assertIn('button.setAttribute("aria-selected"', self.opshop_renderer)
        self.assertIn("actions.updateOpShopTaskPoolView(item.view)", self.opshop_renderer)
        self.assertIn('"Manage Templates",\n    "#opshop/templates"', self.opshop_renderer)
        self.assertIn('state.opshopTaskPoolReturnRoute || "opshop/task-pool/regular"', self.opshop_renderer)
        self.assertIn('opshopTaskPoolView: "regular"', self.state)
        self.assertIn('opshopTaskPoolReturnRoute: "opshop/task-pool/regular"', self.state)
        self.assertIn("function updateOpShopTaskPoolView(view)", self.workspace_actions)
        task_pool_view_action = self.workspace_actions.split(
            "function updateOpShopTaskPoolView", 1
        )[1].split("function toggleRegularOpShopDateGroup", 1)[0]
        self.assertIn("navigateWorkspaceRoute(route)", task_pool_view_action)
        self.assertNotIn("loadOpShopRoute", task_pool_view_action)
        self.assertNotIn("window.location", task_pool_view_action)
        self.assertIn('"opshop/task-pool/regular": "regular"', self.app)
        self.assertIn('"opshop/task-pool/oncall": "oncall"', self.app)
        self.assertIn('"opshop/task-pool/countryside": "countryside"', self.app)
        self.assertIn('!OPSHOP_TASK_POOL_ROUTE_VIEWS[redirectedRoute]', self.app)
        self.assertIn("const isSubtypeOnlyChange", self.app)
        self.assertIn("if (!isSubtypeOnlyChange)", self.app)

    def test_regular_task_pool_uses_shared_date_groups_and_compact_rows(self):
        self.assertIn("createRegularPickupDateGroups", self.opshop_renderer)
        self.assertIn("createRegularPickupRow", self.opshop_renderer)
        self.assertIn("createOpShopDateGroupList", self.opshop_renderer)
        self.assertIn('idPrefix: "workspace-regular"', self.opshop_renderer)
        self.assertIn("Current Assignee:", self.opshop_renderer)
        self.assertIn('"Assigned to"', self.opshop_renderer)
        self.assertIn('"View details"', self.opshop_renderer)
        self.assertIn('"Edit"', self.opshop_renderer)
        self.assertIn('"Delete"', self.opshop_renderer)
        regular_branch = self.opshop_renderer.split(
            'if (route === "regular")', 1
        )[1].split('} else {', 1)[0]
        self.assertIn("createRegularPickupDateGroups", regular_branch)
        self.assertNotIn("createPickupCard", regular_branch)
        self.assertIn('toggle.type = "button"', self.opshop_date_group_renderer)
        self.assertIn('aria-expanded', self.opshop_date_group_renderer)
        self.assertIn('aria-controls', self.opshop_date_group_renderer)
        self.assertIn('collapsed ? "Collapsed" : "Expanded"', self.opshop_date_group_renderer)
        self.assertIn("getDateGroupCollapsed", self.opshop_date_group_renderer)
        self.assertIn("list.hidden = collapsed", self.opshop_date_group_renderer)
        self.assertIn("workspace-regular-pickup-row", self.styles)
        self.assertIn("workspace-regular-pickup-controls", self.styles)
        self.assertRegex(
            self.styles,
            r"\.workspace-regular-pickup-list \.opshop-date-card-list\[hidden\]\s*\{\s*display: none;\s*\}",
        )

    def test_oncall_task_pool_uses_shared_date_groups_and_compact_rows(self):
        oncall_renderer = self._read("js/render/opshop/opshop-oncall-renderer.js")
        task_pool_renderer = self._read(
            "js/render/opshop/opshop-task-pool-renderer.js"
        )
        self.assertIn("createOncallPickupDateGroups", oncall_renderer)
        self.assertIn("createOncallPickupRow", oncall_renderer)
        self.assertIn("createOpShopDateGroupList", oncall_renderer)
        self.assertIn("state.collapsedOncallOpShopPickupDates", oncall_renderer)
        self.assertIn('idPrefix: "workspace-oncall"', oncall_renderer)
        self.assertIn("Current Assignee:", oncall_renderer)
        self.assertIn('"Assigned to"', oncall_renderer)
        self.assertIn('"View details"', oncall_renderer)
        self.assertIn('"Edit"', oncall_renderer)
        self.assertIn('"Delete"', oncall_renderer)
        oncall_branch = task_pool_renderer.split(
            '} else if (route === "oncall") {', 1
        )[1].split("} else {", 1)[0]
        self.assertIn("createOncallPickupDateGroups", oncall_branch)
        self.assertNotIn("createPickupCard", oncall_branch)

        self._run_frontend_module_script(
            "js/render/opshop/opshop-oncall-renderer.js",
            r"""
            const toggledDates = [];
            const state = {
              dispatchDate: "2026-08-12",
              collapsedOncallOpShopPickupDates: {},
              opshopBoard: {
                drivers: [
                  { driver_id: "DRIVER-A", name: "Alpha Driver" },
                  { driver_id: "DRIVER-B", name: "Beta Driver" },
                ],
              },
              opshopAssignmentDrafts: {},
              opshopBusyActionKeys: {},
            };
            const actions = {
              toggleOncallOpShopDateGroup: (pickupDate) => toggledDates.push(pickupDate),
              openOpShopPickupDetail: () => {},
              startEditOpShopPickupTask: () => {},
              startDeleteOpShopPickupTask: () => {},
              updateOpShopAssignmentDraft: () => {},
              unassignOpShopPickup: () => {},
            };
            const pickup = (overrides) => ({
              pickup_task_id: "PICKUP-BASE",
              opshop_name: "Base OP SHOP",
              suburb: "COBURG",
              pickup_date: "2026-08-12",
              run_type: "ON_CALL",
              pickup_category: "NORMAL",
              assigned_to_locked: false,
              assignment_lock_reason: null,
              is_assigned: false,
              driver_id: null,
              assigned_driver_id: null,
              assigned_driver_name: null,
              ...overrides,
            });
            const grouped = module.createOncallPickupDateGroups([
              pickup({
                pickup_task_id: "OLD-BOUNDARY",
                opshop_name: "Old Boundary Shop",
                pickup_date: "2026-07-29",
                assigned_to_locked: true,
                assignment_lock_reason: "Historical pickup is locked.",
                is_assigned: true,
                driver_id: "DRIVER-A",
                assigned_driver_id: "DRIVER-A",
                assigned_driver_name: "Alpha Driver",
              }),
              pickup({
                pickup_task_id: "YESTERDAY",
                opshop_name: "Yesterday Shop",
                pickup_date: "2026-08-11",
                assigned_to_locked: true,
                assignment_lock_reason: "Historical pickup is locked.",
                is_assigned: true,
                driver_id: "DRIVER-A",
                assigned_driver_id: "DRIVER-A",
                assigned_driver_name: "Alpha Driver",
              }),
              pickup({
                pickup_task_id: "TODAY-UNASSIGNED",
                opshop_name: "Alpha Shop",
              }),
              pickup({
                pickup_task_id: "TODAY-ASSIGNED",
                opshop_name: "Zulu Shop",
                suburb: "RICHMOND",
                is_assigned: true,
                driver_id: "DRIVER-B",
                assigned_driver_id: "DRIVER-B",
                assigned_driver_name: "Beta Driver",
              }),
              pickup({
                pickup_task_id: "FUTURE",
                opshop_name: "Future Shop",
                pickup_date: "2026-08-13",
              }),
            ], state, actions);

            const sections = grouped.querySelectorAll(".opshop-date-group");
            if (sections.length !== 4) {
              throw new Error(`Expected 4 exact-date groups, got ${sections.length}`);
            }
            const headings = sections.map((section) => section.children[0].textContent);
            for (const expected of [
              "Wednesday 29/7(1 pickup)Collapsed",
              "Tuesday 11/8(1 pickup)Collapsed",
              "Wednesday 12/8(2 pickups)Expanded",
              "Thursday 13/8(1 pickup)Expanded",
            ]) {
              if (!headings.includes(expected)) {
                throw new Error(`Missing Oncall heading: ${expected}; got ${headings.join(" | ")}`);
              }
            }
            const lists = sections.map((section) => section.children[1]);
            if (lists[0].hidden !== true || lists[1].hidden !== true
                || lists[2].hidden !== false || lists[3].hidden !== false) {
              throw new Error("Oncall default collapsed/expanded dates are incorrect");
            }
            const historicalRow = lists[1].children[0];
            const historicalButtons = historicalRow.querySelectorAll("button");
            for (const label of ["Edit", "Delete", "Unassign now"]) {
              if (!historicalButtons.find((button) => button.textContent === label)?.disabled) {
                throw new Error(`Historical Oncall row left ${label} enabled`);
              }
            }
            if (!historicalRow.querySelector("select").disabled) {
              throw new Error("Historical Oncall assignment remained mutable");
            }
            const todayRows = lists[2].children;
            if (!todayRows[0].textContent.includes("Zulu Shop")
                || !todayRows[1].textContent.includes("Alpha Shop")) {
              throw new Error("Oncall rows are not stably sorted assigned-first");
            }
            const compactText = todayRows[0].textContent;
            for (const expected of [
              "Zulu Shop",
              "RICHMOND",
              "Pickup Date: 2026-08-12",
              "Current Assignee: Beta Driver",
              "Assigned to",
              "View details",
              "Edit",
              "Delete",
            ]) {
              if (!compactText.includes(expected)) {
                throw new Error(`Compact Oncall row is missing: ${expected}`);
              }
            }
            const firstToggle = sections[0].querySelector("button");
            firstToggle.listeners.click[0]({
              preventDefault: () => {},
              stopPropagation: () => {},
            });
            if (toggledDates.join("|") !== "2026-07-29") {
              throw new Error("Oncall group toggle changed more than its own date");
            }
            """,
            setup=r"""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.children = [];
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.hidden = false;
                this.value = "";
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\s+/).includes(token),
                  toggle: (token, enabled) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    enabled ? classes.add(token) : classes.delete(token);
                    this._className = [...classes].join(" ");
                    return enabled;
                  },
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) { this._text = String(value ?? ""); }
              append(...children) { this.children.push(...children); }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) {
                (this.listeners[type] ||= []).push(listener);
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  if (selector.startsWith(".")
                    ? node.classList?.contains(selector.slice(1))
                    : node.tagName === selector) {
                    matches.push(node);
                  }
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }
            globalThis.document = {
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
            };
            """,
        )

    def test_regular_rows_render_last_pickup_date_badge_after_pickup_date(self):
        regular_renderer = self._read("js/render/opshop/opshop-regular-renderer.js")
        oncall_renderer = self._read("js/render/opshop/opshop-oncall-renderer.js")
        countryside_renderer = self._read(
            "js/render/opshop/opshop-countryside-renderer.js"
        )
        self.assertIn("opshop-list-item-last-pickup-date", regular_renderer)
        self.assertIn(
            'formatOptional(pickup.last_pickup_date, "No record")',
            regular_renderer,
        )
        self.assertIn(
            "meta.append(suburb, pickupDate, lastPickupDate)",
            regular_renderer,
        )
        self.assertNotIn("fetch(", regular_renderer)
        self.assertNotIn("opshop-list-item-last-pickup-date", oncall_renderer)
        self.assertNotIn("opshop-list-item-last-pickup-date", countryside_renderer)
        self.assertRegex(
            self.styles,
            r"\.opshop-list-item-last-pickup-date\s*\{[^}]*"
            r"border:\s*1px solid #ef9a9a;[^}]*background:\s*#fff1f1;"
            r"[^}]*color:\s*#b42318;",
        )
        self._run_frontend_module_script(
            "js/render/opshop/opshop-regular-renderer.js",
            r"""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.children = [];
                this.attributes = {};
                this.listeners = {};
                this._className = "";
                this._text = text;
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\s+/).includes(token),
                  toggle: (token, force) => {
                    const classes = new Set(this._className.split(/\s+/).filter(Boolean));
                    const enabled = force === undefined ? !classes.has(token) : Boolean(force);
                    enabled ? classes.add(token) : classes.delete(token);
                    this._className = [...classes].join(" ");
                    return enabled;
                  },
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) { this._text = String(value ?? ""); }
              append(...children) { this.children.push(...children); }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) {
                (this.listeners[type] ||= []).push(listener);
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  if (selector.startsWith(".")
                    ? node.classList?.contains(selector.slice(1))
                    : node.tagName === selector) {
                    matches.push(node);
                  }
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }
            globalThis.document = {
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
            };
            const state = {
              dispatchDate: "2026-07-24",
              opshopBoard: { drivers: [] },
              opshopAssignmentDrafts: {},
            };
            const actions = {
              openOpShopPickupDetail: () => {},
              startEditOpShopPickupTask: () => {},
              startDeleteOpShopPickupTask: () => {},
              updateOpShopAssignmentDraft: () => {},
            };
            const basePickup = {
              pickup_task_id: "PICKUP-1",
              opshop_name: "Synthetic OP SHOP",
              suburb: "COBURG",
              pickup_date: "2026-07-24",
              run_type: "REGULAR",
              pickup_category: "NORMAL",
              assigned_to_locked: false,
              is_assigned: false,
              driver_id: null,
              assigned_driver_id: null,
            };
            const cases = [
              ["2026-07-17", "Last Pickup Date: 2026-07-17"],
              [null, "Last Pickup Date: No record"],
              [undefined, "Last Pickup Date: No record"],
            ];
            cases.forEach(([lastPickupDate, expectedText], index) => {
              const pickup = { ...basePickup, pickup_task_id: `PICKUP-${index + 1}` };
              if (index < 2) pickup.last_pickup_date = lastPickupDate;
              const row = module.createRegularPickupRow(pickup, state, actions);
              const meta = row.children[1].children[1];
              const classes = meta.children.map((child) => child.className);
              if (classes.join("|") !== "opshop-list-item-suburb|opshop-list-item-date|opshop-list-item-last-pickup-date") {
                throw new Error(`Unexpected metadata order: ${classes.join("|")}`);
              }
              const badge = meta.children[2];
              if (badge.textContent !== expectedText) {
                throw new Error(`Unexpected Last Pickup Date text: ${badge.textContent}`);
              }
              if (Object.values(badge.listeners).flat().length !== 0) {
                throw new Error("Last Pickup Date badge must not be interactive");
              }
              const actionLabels = row.querySelectorAll("button").map((button) => button.textContent);
              if (actionLabels.join("|") !== "View details|Edit|Delete") {
                throw new Error(`Row actions changed: ${actionLabels.join("|")}`);
              }
            });
            """,
        )

    def test_opshop_pickup_date_excel_export_is_scoped_busy_and_non_mutating(self):
        self.assertIn(
            "/api/manual-dispatch/opshop/pickup-collections/export-excel?",
            self.api,
        )
        self.assertIn("apiExportOpShopPickupCollectionsExcel", self.api)
        self.assertIn("exportOpShopPickupCollectionsExcel", self.workspace_actions)
        self.assertIn('"Export Daily Collections"', self.opshop_renderer)
        self.assertIn('"Preparing Daily Export..."', self.opshop_renderer)
        self._run_workspace_actions_script(
            """
            let resolveExport;
            const exportGate = new Promise((resolve) => { resolveExport = resolve; });
            let exportCalls = 0;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-07-06",
              opshopTripSummaryDate: "2026-07-07",
              opshopBusyActionKeys: {},
              opshopActionError: "",
              opshopAssignmentDrafts: { "PICKUP-1": "D001" },
              countrysideRouteGroupDrafts: {},
              deliveryBusyActionKeys: {},
            };
            const beforeDrafts = JSON.stringify(state.opshopAssignmentDrafts);
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                exportOpShopPickupCollectionsExcel: async ({ pickupDate }) => {
                  exportCalls += 1;
                  if (pickupDate !== "2026-07-07") {
                    throw new Error(`wrong export scope: ${pickupDate}`);
                  }
                  return exportGate;
                },
              },
            });
            const first = actions.exportOpShopPickupCollections("2026-07-07");
            const second = actions.exportOpShopPickupCollections("2026-07-07");
            if (exportCalls !== 1) {
              throw new Error(`rapid OP SHOP export made ${exportCalls} API calls`);
            }
            if (!state.opshopBusyActionKeys["opshop-export-date:2026-07-07"]) {
              throw new Error("OP SHOP pickup date export did not expose busy state");
            }
            resolveExport({ filename: "Daily_OPSHOP_Collections_2026-07-07.xlsx" });
            await Promise.all([first, second]);
            if (state.workspaceRoute !== "opshop/collections" ||
                state.opshopTripSummaryDate !== "2026-07-07" ||
                JSON.stringify(state.opshopAssignmentDrafts) !== beforeDrafts) {
              throw new Error("OP SHOP pickup date export mutated route, date, or assignments");
            }
            if (Object.keys(state.opshopBusyActionKeys).length !== 0) {
              throw new Error("OP SHOP pickup date export busy state was not cleared");
            }

            const failureState = {
              ...state,
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const failureActions = createWorkspaceActions({
              state: failureState,
              renderWorkspace: () => {},
              api: {
                exportOpShopPickupCollectionsExcel: async () => {
                  throw new Error("OP SHOP workbook preparation failed");
                },
              },
            });
            await failureActions.exportOpShopPickupCollections("2026-07-07");
            if (failureState.opshopActionError !== "OP SHOP workbook preparation failed") {
              throw new Error("OP SHOP export failure was not surfaced accurately");
            }
            """
        )

    def test_oncall_template_picker_uses_high_contrast_option_styles(self):
        oncall_renderer = self._read("js/render/opshop-oncall-pickup-list-modal-renderer.js")
        self.assertIn("opshop-template-picker-option-main", oncall_renderer)
        self.assertIn("opshop-template-picker-option-meta", oncall_renderer)
        self.assertIn("opshop-template-picker-option-selected", oncall_renderer)
        self.assertIn('option.setAttribute("aria-selected"', oncall_renderer)
        option_styles = self.styles.split(".opshop-template-picker-option {", 1)[1].split(
            ".opshop-template-picker-option-text",
            1,
        )[0]
        main_styles = self.styles.split(".opshop-template-picker-option-main {", 1)[1].split(
            ".opshop-template-picker-option-meta",
            1,
        )[0]
        meta_styles = self.styles.split(".opshop-template-picker-option-meta {", 1)[1].split(
            ".opshop-template-picker-selected-mark",
            1,
        )[0]
        hover_styles = self.styles.split(".opshop-template-picker-option:hover,", 1)[1].split(
            ".opshop-template-picker-option-selected",
            1,
        )[0]
        selected_styles = self.styles.split(".opshop-template-picker-option-selected,", 1)[1].split(
            ".opshop-template-picker-empty",
            1,
        )[0]
        self.assertIn("background: linear-gradient(135deg, #0f5f46, #0a4635)", option_styles)
        self.assertIn("color: #ffffff", option_styles)
        self.assertIn(".opshop-template-picker-option *", self.styles)
        self.assertIn("color: #ffffff", main_styles)
        self.assertIn("color: #ffffff", meta_styles)
        self.assertIn(".opshop-template-picker-option:focus-visible", hover_styles)
        self.assertIn("background: linear-gradient(135deg, #137454, #0e5c45)", hover_styles)
        self.assertIn("color: #ffffff", hover_styles)
        self.assertIn("background: linear-gradient(135deg, #176d51, #0d513d)", selected_styles)
        self.assertIn("color: #ffffff", selected_styles)

    def test_regular_date_toggle_preserves_drafts_without_board_reload(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              activeWorkspace: "opshop",
              workspaceRoute: "opshop/task-pool/regular",
              dispatchDate: "2026-07-02",
              collapsedRegularOpShopPickupDates: {},
              opshopAssignmentDrafts: { "TASK-1": "" },
            };
            let boardCalls = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                getWorkspaceMigrationStatus: async () => ({}),
                getOpShopWorkspaceBoard: async () => { boardCalls += 1; return {}; },
              },
            });

            actions.toggleRegularOpShopDateGroup("2026-07-01");
            if (state.collapsedRegularOpShopPickupDates["2026-07-01"] !== false) {
              throw new Error("past date did not expand from its default collapsed state");
            }
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "TASK-1")) {
              throw new Error("explicit Unassigned draft was lost during toggle");
            }
            if (boardCalls !== 0) {
              throw new Error("date group toggle reloaded the scoped board");
            }
            actions.toggleRegularOpShopDateGroup("2026-07-01");
            if (state.collapsedRegularOpShopPickupDates["2026-07-01"] !== true) {
              throw new Error("expanded date group did not collapse");
            }
            """
        )

    def test_oncall_date_toggle_changes_only_one_group_without_board_reload(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              activeWorkspace: "opshop",
              workspaceRoute: "opshop/task-pool/oncall",
              dispatchDate: "2026-08-12",
              collapsedOncallOpShopPickupDates: { "2026-08-10": true },
              opshopAssignmentDrafts: { "TASK-1": "" },
            };
            let boardCalls = 0;
            let renderCalls = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => { renderCalls += 1; },
              api: {
                getWorkspaceMigrationStatus: async () => ({}),
                getOpShopWorkspaceBoard: async () => { boardCalls += 1; return {}; },
              },
            });

            actions.toggleOncallOpShopDateGroup("2026-08-11");
            if (state.collapsedOncallOpShopPickupDates["2026-08-11"] !== false) {
              throw new Error("past Oncall date did not expand from default collapsed state");
            }
            if (state.collapsedOncallOpShopPickupDates["2026-08-10"] !== true) {
              throw new Error("Oncall toggle changed another date group");
            }
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "TASK-1")) {
              throw new Error("Oncall toggle lost the explicit Unassigned draft");
            }
            if (boardCalls !== 0 || renderCalls !== 1
                || state.workspaceRoute !== "opshop/task-pool/oncall"
                || state.dispatchDate !== "2026-08-12") {
              throw new Error("Oncall toggle fetched data or changed route/date");
            }
            actions.toggleOncallOpShopDateGroup("2026-08-11");
            if (state.collapsedOncallOpShopPickupDates["2026-08-11"] !== true
                || renderCalls !== 2 || boardCalls !== 0) {
              throw new Error("Expanded Oncall group did not collapse locally");
            }
            """
        )

    def test_scoped_regular_task_forms_do_not_render_duplicate_list(self):
        modal_renderer = self._read(
            "js/render/opshop-pickup-list-modal-renderer.js"
        )
        regular_actions = self._read("js/actions/opshop-pickup-actions.js")
        self.assertIn("isScopedFormOnly", modal_renderer)
        self.assertIn('state.activeWorkspace === "opshop"', modal_renderer)
        self.assertIn('if (!isScopedFormOnly)', modal_renderer)
        self.assertIn("createPickupGroups", modal_renderer)
        self.assertIn("opshop-pickup-form-only-modal", modal_renderer)
        self.assertIn("closeScopedOperationModal", regular_actions)
        self.assertIn('state.isOpShopPickupListOpen = false', regular_actions)
        self.assertIn(
            'if (state.activeWorkspace !== "opshop")',
            regular_actions,
        )

    def test_opshop_templates_reuse_full_regular_oncall_management(self):
        template_renderer = self._read(
            "js/render/opshop-template-management-modal-renderer.js"
        )
        template_actions = self._read("js/actions/opshop-template-actions.js")
        self.assertIn("createOpShopTemplateManagementPanel", self.opshop_renderer)
        self.assertNotIn("function createTemplateCard", self.opshop_renderer)
        for action in (
            "cancelTemplateForm",
            "disableTemplate",
            "saveTemplate",
            "selectTemplateTab",
            "startAddTemplate",
            "startDisableTemplate",
            "startEditTemplate",
            "toggleTemplateIncludeInactive",
            "updateTemplateForm",
        ):
            self.assertIn(action, self.app)
        self.assertIn("Regular Templates", template_renderer)
        self.assertIn("Oncall Templates", template_renderer)
        self.assertIn("Show disabled templates", template_renderer)
        self.assertIn("Add Template", template_renderer)
        self.assertIn("Edit", template_renderer)
        self.assertIn("Disable", template_renderer)
        self.assertIn("Default Driver", template_renderer)
        self.assertIn('state.opshopBoard?.drivers || []', template_renderer)
        self.assertIn("refreshScopedBoard = null", template_actions)
        self.assertIn('state.activeWorkspace === "opshop"', template_actions)
        self.assertIn("await refreshScopedBoard();", template_actions)
        self.assertIn(
            "refreshScopedBoard: () => workspaceActions.loadWorkspaceRoute(state.workspaceRoute)",
            self.app,
        )
        template_update = template_actions.split(
            "function updateTemplateForm", 1
        )[1].split("async function saveTemplate", 1)[0]
        self.assertIn("if (shouldRender)", template_update)
        self.assertNotIn(
            "state.opshopTemplateForm = form;\n    renderBoard();",
            template_update,
        )

    def test_opshop_templates_reuse_countryside_route_management(self):
        countryside_renderer = self._read(
            "js/render/opshop-countryside-pickup-list-modal-renderer.js"
        )
        countryside_actions = self._read(
            "js/actions/opshop-countryside-pickup-actions.js"
        )
        self.assertIn(
            "createCountrysideRouteManagementPanel",
            self.opshop_renderer,
        )
        self.assertIn(
            "export function createCountrysideRouteManagementPanel",
            countryside_renderer,
        )
        self.assertIn("Countryside Route Management", self.opshop_renderer)
        for label in (
            "New Route",
            "Rename",
            "Disable",
            "Add OP SHOP to this route",
            "Move",
            "Remove",
            "Route Template Detail",
        ):
            self.assertIn(label, countryside_renderer)
        for action in (
            "createCountrysideRouteGroup",
            "renameCountrysideRouteGroup",
            "disableCountrysideRouteGroup",
            "addCountrysideRouteTemplate",
            "moveCountrysideRouteTemplate",
            "removeCountrysideRouteTemplate",
        ):
            self.assertIn(action, self.app)
        self.assertIn("loadManagementData", self.app)
        self.assertIn("refreshScopedBoard = null", countryside_actions)
        self.assertIn('state.activeWorkspace === "opshop"', countryside_actions)
        self.assertIn("await refreshScopedBoard();", countryside_actions)
        self.assertIn('state.opshopBoard?.drivers || []', countryside_renderer)
        self.assertNotIn("fetch(", countryside_renderer)
        self.assertIn(".opshop-countryside-management-panel", self.styles)

    def test_opshop_task_pool_reuses_legacy_task_crud_without_assignment_apply(self):
        regular_actions = self._read("js/actions/opshop-pickup-actions.js")
        oncall_actions = self._read("js/actions/opshop-oncall-pickup-actions.js")
        countryside_actions = self._read(
            "js/actions/opshop-countryside-pickup-actions.js"
        )
        modal_adapter = self._read("js/utils/opshop-workspace-modal-utils.js")
        selectors = self._read("js/state/selectors.js")

        self.assertIn('"Add Pickup Task"', self.opshop_renderer)
        self.assertIn('"View details"', self.opshop_renderer)
        self.assertIn('"Edit"', self.opshop_renderer)
        self.assertIn('"Delete"', self.opshop_renderer)
        self.assertIn("actions.startAddOpShopPickupTask(route)", self.opshop_renderer)
        self.assertIn("actions.startEditOpShopPickupTask(pickup)", self.opshop_renderer)
        self.assertIn("actions.startDeleteOpShopPickupTask(pickup)", self.opshop_renderer)
        self.assertIn("pickup.assigned_to_locked", self.opshop_renderer)
        self.assertIn("syncScopedOpShopModalState", modal_adapter)
        self.assertIn("state.opshopBoard.opshop_pickups", modal_adapter)
        self.assertIn("state.opshopBoard?.opshop_pickups?.find", selectors)
        self.assertIn("refreshScopedBoard = null", regular_actions)
        self.assertIn("refreshScopedBoard = null", oncall_actions)
        self.assertIn("refreshScopedBoard = null", countryside_actions)
        self.assertIn("closeOpShopPickupListWithoutApply", self.app)
        self.assertIn("closeOncallOpShopPickupListWithoutApply", self.app)
        self.assertIn("closeCountrysideOpShopPickupListWithoutApply", self.app)
        self.assertIn('state.activeWorkspace === "opshop"', self.app)
        regular_form_update = regular_actions.split(
            "function updatePickupTaskForm", 1
        )[1].split("async function handleCreatePickupTask", 1)[0]
        self.assertIn('["schedule_id", "pickup_date"].includes(field)', regular_form_update)
        self.assertIn("renderBoard();", regular_form_update)

    def test_regular_board_load_keeps_persisted_assignments_authoritative(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/task-pool/regular",
              dispatchDate: "2026-06-30",
              opshopBoard: null,
              opshopPickupCollections: [],
              opshopAssignmentDrafts: { "REG-EXPLICIT": "" },
              countrysideRouteGroupDrafts: {},
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
            };
            const pickup = (id, values = {}) => ({
              pickup_task_id: id,
              run_type: "REGULAR",
              pickup_category: "NORMAL",
              pickup_date: "2026-07-01",
              default_driver_id: "DRIVER-1",
              assigned_driver_id: "",
              driver_id: "",
              is_assigned: false,
              assigned_to_locked: false,
              ...values,
            });
            const board = {
              drivers: [{ driver_id: "DRIVER-1", name: "Driver One" }],
              countryside_route_groups: [],
              opshop_pickups: [
                pickup("REG-PERSISTED", {
                  is_assigned: true,
                  assigned_driver_id: "DRIVER-1",
                }),
                pickup("REG-EXPLICIT"),
                pickup("REG-UNASSIGNED"),
              ],
            };
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getOpShopWorkspaceBoard: async () => board,
              listOpShopPickupCollections: async () => [{
                status: "SAVED",
                driver_id: "DRIVER-1",
                pickup_date: "2026-07-02",
              }],
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.loadWorkspaceRoute("opshop/task-pool/regular");
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "REG-EXPLICIT")) {
              throw new Error("explicit Unassigned draft key was removed");
            }
            if (state.opshopAssignmentDrafts["REG-EXPLICIT"] !== "") {
              throw new Error("explicit Unassigned draft was overwritten");
            }
            for (const pickupId of ["REG-PERSISTED", "REG-UNASSIGNED"]) {
              if (Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, pickupId)) {
                throw new Error(`board load created a local assignment draft for ${pickupId}`);
              }
            }
            """
        )

    def test_opshop_trip_summary_groups_pickups_and_preserves_collection_locks(self):
        self.assertIn('state.workspaceRoute === "opshop/trip-summary"', self.opshop_renderer)
        self.assertIn("function createOpShopTripSummary(", self.opshop_renderer)
        self.assertIn('field.textContent = "Pickup date"', self.opshop_renderer)
        self.assertIn("actions.updateOpShopTripSummaryDate(input.value)", self.opshop_renderer)
        self.assertIn("assignedOpShopPickupsForDriver", self.opshop_renderer)
        self.assertIn('createOpShopPickupGroup("Regular"', self.opshop_renderer)
        self.assertIn('createOpShopPickupGroup("Oncall"', self.opshop_renderer)
        self.assertIn('createOpShopPickupGroup("Countryside"', self.opshop_renderer)
        self.assertIn("pickup.route_group_name", self.opshop_renderer)
        self.assertIn("pickup.task_notes", self.opshop_renderer)
        self.assertIn("actions.unassignOpShopPickup(pickup.pickup_task_id)", self.opshop_renderer)
        self.assertIn('collection.status === "SAVED"', self.opshop_renderer)
        self.assertIn("Saved Pickup Collection locks this driver and pickup date.", self.opshop_renderer)
        self.assertIn("Generated Pickup Collection is awaiting confirmation", self.opshop_renderer)
        self.assertIn("readyPickupCollectionCandidates(board, collections)", self.opshop_renderer)
        self.assertIn("Generate Pickup Collection", self.opshop_renderer)
        self.assertIn("opshopTripSummaryDate: DEFAULT_TRIP_SUMMARY_DATE", self.state)
        self.assertIn("state.opshopTripSummaryBoard", self.opshop_renderer)
        self.assertIn("state.opshopTripSummaryCollections", self.opshop_renderer)
        self.assertIn("async function updateOpShopTripSummaryDate(nextDate)", self.workspace_actions)
        self.assertIn("loadOpShopTripSummaryData", self.workspace_actions)
        self.assertIn("api.getOpShopTripSummary", self.workspace_actions)
        self.assertIn("pickupDate: scopedPickupDate", self.workspace_actions)
        self.assertIn(
            "api.listOpShopPickupCollectionsByPickupDate",
            self.workspace_actions,
        )
        self.assertIn("state.opshopTripSummaryBoard = board", self.workspace_actions)
        self.assertNotIn("collection.dispatch_date === dispatchDate", self.opshop_renderer)

    def test_opshop_trip_summary_pickup_cards_open_read_only_detail_modal(self):
        row_block = self.opshop_renderer.split(
            "function createOpShopTripPickupRow", 1
        )[1].split("function createCollectionList", 1)[0]

        self.assertIn('trigger.type = "button"', row_block)
        self.assertIn('trigger.className = "workspace-opshop-trip-pickup-trigger"', row_block)
        self.assertIn('trigger.setAttribute("aria-label"', row_block)
        self.assertIn("onOpenPickupDetail(pickup, trigger)", row_block)
        self.assertIn("event.preventDefault()", row_block)
        self.assertIn("event.stopPropagation()", row_block)
        self.assertNotIn("task_notes", row_block)
        self.assertNotIn("status_notes", row_block)
        self.assertNotIn("Pickup General Info", self.opshop_renderer)
        self.assertNotIn("workspace-opshop-general-info", self.opshop_renderer)
        self.assertNotIn("expandedOpShopTripPickupDetails", self.opshop_renderer)
        self.assertNotIn("workspace-opshop-general-info", self.styles)

    def test_opshop_pickup_detail_modal_has_operational_fields_and_no_ids(self):
        modal_source = self.opshop_workspace_modal_utils
        for label in (
            "OP SHOP / company",
            "Category",
            "Pickup date",
            "Current assignee",
            "Default driver",
            "Suburb",
            "Area / region",
            "Full address",
            "Frequency",
            "Run day",
            "Time window",
            "Call before arrival",
            "Key required",
            "Trailer restriction",
            "Contact name",
            "Contact phone",
            "Access instructions",
            "Route group",
            "Notes",
        ):
            self.assertIn(f'"{label}"', modal_source)
        self.assertIn('[pickup.task_notes, pickup.status_notes]', modal_source)
        self.assertIn('.join("\\n\\n")', modal_source)
        for internal_label in (
            "Task ID",
            "Assignment ID",
            "Lock ID",
            "Schedule ID",
        ):
            self.assertNotIn(internal_label, modal_source)
        self.assertIn("white-space: pre-wrap", self.styles)
        self.assertIn("overflow-wrap: anywhere", self.styles)

    def test_opshop_trip_summary_unassign_is_independent_from_detail_modal(self):
        row_block = self.opshop_renderer.split(
            "function createOpShopTripPickupRow", 1
        )[1].split("function createCollectionList", 1)[0]
        self.assertIn("event.stopPropagation()", row_block)
        self.assertIn("actions.unassignOpShopPickup(pickup.pickup_task_id)", row_block)
        self.assertIn("onOpenPickupDetail(pickup, trigger)", row_block)
        self.assertIn("isLocked", row_block)
        self.assertIn("pickup.assigned_to_locked", row_block)

    def test_opshop_pickup_detail_modal_is_single_local_and_accessible(self):
        modal_source = self.opshop_workspace_modal_utils.split(
            "export function openOpShopPickupDetailModal", 1
        )[1].split("function createOpShopDetailSection", 1)[0]
        self.assertIn('host.querySelector(".workspace-opshop-detail-backdrop")?.remove()', modal_source)
        self.assertIn('modal.setAttribute("role", "dialog")', modal_source)
        self.assertIn('modal.setAttribute("aria-modal", "true")', modal_source)
        self.assertIn('modal.setAttribute("aria-labelledby", titleId)', modal_source)
        self.assertIn('event.key === "Escape"', modal_source)
        self.assertIn('event.key === "Tab"', modal_source)
        self.assertIn("trapOpShopModalFocus(modal, event)", modal_source)
        self.assertIn("focusOpShopElement(trigger, true)", modal_source)
        self.assertIn("element.focus({ preventScroll: true })", modal_source)
        self.assertIn("host.append(backdrop)", modal_source)
        self.assertNotIn("fetch(", modal_source)
        self.assertNotIn("api.", modal_source)
        self.assertNotIn("renderOpShopWorkspace", modal_source)
        self.assertNotIn("state.", modal_source)

    def test_countryside_route_group_heading_is_an_independent_detail_trigger(self):
        route_card = self.opshop_renderer.split(
            "function createRouteGroupAssignmentForm", 1
        )[1].split("function createTemplateManagementPage", 1)[0]

        self.assertIn('detailTrigger.type = "button"', route_card)
        self.assertIn(
            'detailTrigger.className = "workspace-route-group-detail-trigger"',
            route_card,
        )
        self.assertIn('detailTrigger.setAttribute(\n    "aria-label"', route_card)
        self.assertIn("event.preventDefault()", route_card)
        self.assertIn("event.stopPropagation()", route_card)
        self.assertIn("onOpenRouteGroupDetail({", route_card)
        self.assertIn("templates: routeTemplates.get(group.route_group_id) || []", route_card)
        self.assertIn("pickupDate: draft.pickup_date", route_card)
        self.assertIn("trigger: detailTrigger", route_card)
        self.assertIn("row.append(detailTrigger, controls, assignButton)", route_card)
        self.assertIn(
            'const pickupDateField = createDateField(\n    "Pickup date"',
            route_card,
        )
        self.assertIn(
            'const driverField = createSelect(\n    "Assigned to"',
            route_card,
        )
        self.assertIn(
            'const notesField = createTextField(\n    "Notes"',
            route_card,
        )
        self.assertIn('"Assign Route Group"', route_card)

    def test_countryside_route_group_drill_down_is_single_local_and_active_only(self):
        modal_source = self.opshop_workspace_modal_utils.split(
            "export function openCountrysideRouteGroupDetailModal", 1
        )[1].split("function createOpShopDetailSection", 1)[0]
        template_filter = self.opshop_renderer.split(
            "function templatesByRouteGroup", 1
        )[1].split("function createSelect", 1)[0]

        self.assertIn("const activeTemplates = templates.filter(isActiveCountrysideTemplate)", modal_source)
        self.assertIn('template.active_flag !== false', modal_source)
        self.assertIn('template.status !== "On_Hold"', modal_source)
        self.assertIn('template.active_flag !== false', template_filter)
        self.assertIn('template.status !== "On_Hold"', template_filter)
        self.assertIn('workspace-opshop-route-template-list', modal_source)
        self.assertIn('createCountrysideTemplateRow(template', modal_source)
        self.assertIn('No active OP SHOP templates are available', modal_source)
        self.assertIn('renderTemplateDetail(template)', modal_source)
        self.assertIn('"OP SHOP / company"', modal_source)
        self.assertIn('"Category", "Countryside"', modal_source)
        self.assertIn('"Template status"', modal_source)
        self.assertIn('"Template context", "ON_CALL + COUNTRYSIDE"', modal_source)
        self.assertIn('"Actual pickup status", matchingTask?.status', modal_source)
        self.assertIn('"Actual assignee", matchingTask?.assigned_driver_name', modal_source)
        self.assertIn('backLabel.textContent = "Back to Route Group"', modal_source)
        self.assertIn('renderRouteGroup(template.schedule_id)', modal_source)
        self.assertIn('focusOpShopElement(focusTarget)', modal_source)
        self.assertIn('focusOpShopElement(trigger, true)', modal_source)
        self.assertEqual(1, modal_source.count('modal.setAttribute("role", "dialog")'))
        self.assertNotIn("fetch(", modal_source)
        self.assertNotIn("api.", modal_source)
        self.assertNotIn("renderOpShopWorkspace", modal_source)

    def test_countryside_route_group_drill_down_has_accessible_responsive_styles(self):
        for selector in (
            ".workspace-route-group-detail-trigger {",
            ".workspace-route-group-detail-trigger:focus-visible {",
            ".workspace-opshop-route-template-row {",
            ".workspace-opshop-route-template-row:focus-visible {",
            ".workspace-modal-opshop-route-detail,",
            ".workspace-opshop-route-detail-body {",
        ):
            self.assertIn(selector, self.styles)
        self.assertIn("min-height: 3.25rem", self.styles)
        self.assertIn("min-height: 4.75rem", self.styles)
        self.assertIn("overflow-wrap: anywhere", self.styles)
        self.assertIn(
            ".workspace-modal-opshop-route-detail .workspace-modal-icon,",
            self.styles,
        )
        self.assertIn(
            "background: linear-gradient(135deg, var(--accent), var(--accent-strong));",
            self.styles,
        )

    def test_opshop_pickup_detail_close_button_keeps_label_and_icon_together(self):
        modal_source = self.opshop_workspace_modal_utils.split(
            "export function openOpShopPickupDetailModal", 1
        )[1].split("function createOpShopDetailSection", 1)[0]
        close_styles = self.styles.split(
            ".workspace-modal-close.workspace-opshop-detail-close {", 1
        )[1].split("}", 1)[0]
        close_icon_styles = self.styles.split(
            ".workspace-modal-close.workspace-opshop-detail-close .ui-icon {", 1
        )[1].split("}", 1)[0]

        self.assertIn('close.type = "button"', modal_source)
        self.assertIn('closeText.textContent = "Close"', modal_source)
        self.assertIn('close.append(closeText, createIcon("x"))', modal_source)
        self.assertIn("header.append(titleGroup, close)", modal_source)
        for declaration in (
            "display: inline-flex",
            "align-items: center",
            "justify-content: center",
            "flex-shrink: 0",
            "white-space: nowrap",
            "line-height: 1",
            "min-height: 2.75rem !important",
        ):
            self.assertIn(declaration, close_styles)
        self.assertNotIn("position: absolute", close_icon_styles)
        self.assertNotIn("transform:", close_icon_styles)
        self.assertNotIn("margin-left: -", close_icon_styles)
        self.assertNotIn("margin-right: -", close_icon_styles)

    def test_locked_opshop_pickups_keep_detail_trigger_but_disable_unassign(self):
        row_block = self.opshop_renderer.split(
            "function createOpShopTripPickupRow", 1
        )[1].split("function createCollectionList", 1)[0]
        self.assertIn("onOpenPickupDetail(pickup, trigger)", row_block)
        self.assertNotIn("isLocked ||", row_block.split("trigger.addEventListener", 1)[1].split("const button", 1)[0])
        self.assertIn("isLocked", row_block.split("const button", 1)[1])
        self.assertIn("pickup.assigned_to_locked", row_block.split("const button", 1)[1])

    def test_delivery_trip_summary_does_not_gain_opshop_general_info(self):
        self.assertNotIn("openOpShopPickupDetailModal", self.delivery_renderer)
        self.assertNotIn("workspace-opshop-pickup-detail", self.delivery_renderer)

    def test_opshop_collections_and_history_share_full_weight_sheet(self):
        self.assertIn("Pickup Collections", self.opshop_renderer)
        self.assertIn("groupCollectionsByPickupDate", self.opshop_renderer)
        self.assertIn("createCollectionDateGroup", self.opshop_renderer)
        self.assertIn("Pickup date:", self.opshop_renderer)
        self.assertIn("Workspace date:", self.opshop_renderer)
        self.assertIn("actions.exportOpShopPickupCollections(pickupDate)", self.opshop_renderer)
        self.assertIn("dataset.opshopDailyCollectionExport", self.opshop_renderer)
        self.assertIn("saveOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("cancelOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("exportOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("exportOpShopPickupCollections", self.opshop_renderer)

        history_block = self.opshop_renderer.split(
            "function createSavedPickupCollectionHistory", 1
        )[1].split("function createCollectionList", 1)[0]
        self.assertIn('"Saved Pickup Collection History"', history_block)
        self.assertNotIn(
            '"Search saved OP SHOP Pickup Collections by their actual Pickup Date."',
            history_block,
        )
        self.assertIn('field.textContent = "Pickup date"', history_block)
        self.assertIn("actions.updateOpShopSavedHistoryDate", history_block)
        self.assertIn(
            '"No saved Pickup Collections were found for this Pickup Date."',
            history_block,
        )
        self.assertIn("{ historyMode: true }", history_block)
        self.assertNotIn("createCollectionDateGroup", history_block)
        self.assertNotIn("exportOpShopPickupCollections", history_block)
        self.assertNotIn("Save Collection", history_block)
        self.assertNotIn("Cancel Generated", history_block)

        collection_card_block = self.opshop_renderer.split(
            "function createCollectionCard", 1
        )[1].split("const OPSHOP_COLLECTION_WEIGHT_COLUMNS", 1)[0]
        self.assertNotIn("workspace-fact-grid", collection_card_block)
        self.assertNotIn("Pickup count", collection_card_block)
        self.assertNotIn("Regular pickups", collection_card_block)
        self.assertNotIn("Oncall pickups", collection_card_block)
        self.assertNotIn("Countryside pickups", collection_card_block)
        self.assertIn("{ historyMode = false }", collection_card_block)
        self.assertIn("if (historyMode)", collection_card_block)
        self.assertIn("Saved by:", collection_card_block)
        self.assertIn("Generated:", collection_card_block)
        self.assertIn("Saved:", collection_card_block)
        self.assertIn("!historyMode && collection.status === \"GENERATED\"", collection_card_block)
        self.assertIn('"Save Collection"', collection_card_block)
        self.assertIn('"Cancel Generated"', collection_card_block)
        self.assertIn('"Export Excel"', collection_card_block)
        self.assertIn('"Exporting..."', collection_card_block)
        self.assertIn("historyMode", collection_card_block)
        self.assertIn("collection.status === \"SAVED\"", collection_card_block)
        self.assertIn(
            "card.append(top, meta, weightSheet, actionsRow)",
            collection_card_block,
        )

        self.assertEqual(
            1,
            self.opshop_renderer.count("function createCollectionWeightSheetPreview"),
        )
        self.assertIn("DAILY OP SHOP COLLECTIONS - WEIGHT SHEET", self.opshop_renderer)
        self.assertIn("PLEASE RECORD WEIGHT OF BAGS FOR EACH OP SHOP", self.opshop_renderer)
        column_block = self.opshop_renderer.split(
            "const OPSHOP_COLLECTION_WEIGHT_COLUMNS = [", 1
        )[1].split("];", 1)[0]
        expected_columns = [
            '"OPSHOP NAME"',
            '"SUBURB"',
            '"CLOTHING KG"',
            '"SHOES KG"',
            '"TIME IN"',
            '"TIME OUT"',
            '"TROLLEYS OUT TO OPSHOPS"',
            '"TROLLEYS IN TO MCC"',
            '"HARD TOYS"',
            '"SOFT TOYS"',
            '"BLACK BAGS"',
            '"SHOE BAGS"',
        ]
        for column in expected_columns:
            self.assertIn(column, column_block)
        self.assertEqual(24, column_block.count('"'))

        row_values_block = self.opshop_renderer.split(
            "function collectionWeightSheetRowValues", 1
        )[1].split("function readyPickupCollectionCandidates", 1)[0]
        self.assertIn("pickup.opshop_name_snapshot", row_values_block)
        self.assertIn("pickup.suburb_snapshot", row_values_block)
        self.assertIn("OPSHOP_COLLECTION_ENTRY_FIELDS.map", row_values_block)
        self.assertIn("getOpShopCollectionEntryValue", row_values_block)
        self.assertIn("collectionWeightSheetRowValues(", self.opshop_renderer)
        self.assertIn("input.type = field.type", self.opshop_renderer)
        self.assertIn('input.min = "0"', self.opshop_renderer)
        self.assertIn("input.step = field.step", self.opshop_renderer)
        self.assertIn('"Save Weight Sheet"', collection_card_block)
        self.assertIn("opshopCollectionEntryDrafts", self.state)
        self.assertIn(
            "Object.prototype.hasOwnProperty.call",
            self.opshop_entry_state,
        )
        self.assertNotIn("value ||", self.opshop_entry_state)
        self.assertIn("workspace-opshop-weight-sheet-table-wrap", self.styles)
        self.assertIn(".workspace-pickup-collection-paper-list", self.styles)
        self.assertIn("min-width: 980px", self.styles)
        self.assertIn(
            'route === "opshop/trip-summary"',
            self.workspace_actions,
        )

    def test_opshop_collection_entry_actions_flush_drafts_before_save_and_exports(self):
        self._run_workspace_actions_script(
            """
            const makePickup = (rowId) => ({
              row_id: rowId,
              opshop_name_snapshot: rowId,
              suburb_snapshot: "Coburg",
              clothing_kg_snapshot: 5,
              shoes_kg_snapshot: 2.5,
              time_in_snapshot: null,
              time_out_snapshot: null,
              trolleys_out_to_opshops_snapshot: 1,
              trolleys_in_to_mcc_snapshot: 2,
              hard_toys_snapshot: 3,
              soft_toys_snapshot: 4,
              black_bags_snapshot: 5,
              shoe_bags_snapshot: 6,
            });
            const makeCollection = (id, rowId) => ({
              collection_id: id,
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [makePickup(rowId)],
            });
            const collectionA = makeCollection("COL-A", "ROW-A");
            const collectionB = makeCollection("COL-B", "ROW-B");
            const calls = [];
            let failCollectionId = "";
            const api = {
              updateOpShopPickupCollectionRows: async (collectionId, payload) => {
                calls.push(["patch", collectionId, payload]);
                if (collectionId === failCollectionId) {
                  throw new Error("entry failure");
                }
                const source = state.opshopPickupCollections.find(
                  (collection) => collection.collection_id === collectionId,
                );
                const rowPayload = payload.rows[0];
                return {
                  ...source,
                  pickups: source.pickups.map((pickup) => pickup.row_id === rowPayload.row_id
                    ? {
                      ...pickup,
                      clothing_kg_snapshot: rowPayload.clothing_kg === "" ? null : rowPayload.clothing_kg,
                      shoes_kg_snapshot: rowPayload.shoes_kg === "" ? null : rowPayload.shoes_kg,
                      time_in_snapshot: rowPayload.time_in || null,
                      time_out_snapshot: rowPayload.time_out || null,
                      trolleys_out_to_opshops_snapshot: rowPayload.trolleys_out_to_opshops === "" ? null : rowPayload.trolleys_out_to_opshops,
                      trolleys_in_to_mcc_snapshot: rowPayload.trolleys_in_to_mcc === "" ? null : rowPayload.trolleys_in_to_mcc,
                      hard_toys_snapshot: rowPayload.hard_toys === "" ? null : rowPayload.hard_toys,
                      soft_toys_snapshot: rowPayload.soft_toys === "" ? null : rowPayload.soft_toys,
                      black_bags_snapshot: rowPayload.black_bags === "" ? null : rowPayload.black_bags,
                      shoe_bags_snapshot: rowPayload.shoe_bags === "" ? null : rowPayload.shoe_bags,
                    }
                    : pickup),
                };
              },
              saveGeneratedOpShopPickupCollection: async (collectionId) => {
                calls.push(["save", collectionId]);
                return {};
              },
              exportOpShopPickupCollectionExcel: async (collectionId) => {
                calls.push(["single", collectionId]);
              },
              exportOpShopPickupCollectionsExcel: async ({ pickupDate }) => {
                calls.push(["daily", pickupDate]);
              },
              listOpShopPickupCollectionsByPickupDate: async () => (
                state.opshopPickupCollections
              ),
            };
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collectionA, collectionB],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              accountName: "Operator",
              accountId: "7",
            };
            const actions = createWorkspaceActions({
              state,
              api,
              renderWorkspace: () => {},
              confirmAction: () => true,
            });

            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "clothing_kg", "");
            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "hard_toys", "0");
            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "time_in", "09:15");
            await actions.saveOpShopPickupCollectionWeightSheet("COL-A");
            const firstPatch = calls[0];
            if (
              firstPatch[0] !== "patch"
              || firstPatch[2].rows[0].clothing_kg !== ""
              || firstPatch[2].rows[0].hard_toys !== 0
              || firstPatch[2].rows[0].shoes_kg !== 2.5
            ) {
              throw new Error("explicit blank, zero, or persisted row values were lost");
            }
            if (
              state.opshopCollectionEntryDrafts["COL-A"]
              || state.opshopPickupCollections[0].pickups[0].hard_toys_snapshot !== 0
            ) {
              throw new Error("successful weight entry save did not reconcile state");
            }

            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "shoes_kg", "4.5");
            await actions.exportOpShopPickupCollection("COL-A");
            if (calls.at(-2)[0] !== "patch" || calls.at(-1)[0] !== "single") {
              throw new Error("single export did not flush entries first");
            }

            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "black_bags", "7");
            actions.updateOpShopCollectionEntryDraft("COL-B", "ROW-B", "shoe_bags", "8");
            await actions.exportOpShopPickupCollections("2026-05-05");
            const dailyTail = calls.slice(-3).map((item) => item[0] + ":" + item[1]).join(",");
            if (dailyTail !== "patch:COL-A,patch:COL-B,daily:2026-05-05") {
              throw new Error("daily export did not flush generated collections sequentially");
            }

            actions.updateOpShopCollectionEntryDraft("COL-A", "ROW-A", "soft_toys", "9");
            await actions.saveOpShopPickupCollection("COL-A");
            const saveTail = calls.slice(-2).map((item) => item[0]).join(",");
            if (saveTail !== "patch,save") {
              throw new Error("Save Collection did not flush entries before promotion");
            }

            state.opshopPickupCollections = [];
            state.opshopSavedHistoryCollections = [{
              collection_id: "COL-HISTORY",
              status: "SAVED",
              pickup_date: "2026-05-05",
              pickups: [],
            }];
            await actions.exportOpShopPickupCollection("COL-HISTORY");
            if (calls.at(-1)[0] !== "single" || calls.at(-1)[1] !== "COL-HISTORY") {
              throw new Error("Saved History collection was no longer exportable");
            }
          """
        )

    def test_opshop_collection_entry_failure_retains_draft_and_blocks_daily_export(self):
        self._run_workspace_actions_script(
            """
            const collection = {
              collection_id: "COL-FAIL",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [{
                row_id: "ROW-FAIL",
                clothing_kg_snapshot: 1,
                shoes_kg_snapshot: null,
                time_in_snapshot: null,
                time_out_snapshot: null,
                trolleys_out_to_opshops_snapshot: null,
                trolleys_in_to_mcc_snapshot: null,
                hard_toys_snapshot: null,
                soft_toys_snapshot: null,
                black_bags_snapshot: null,
                shoe_bags_snapshot: null,
              }],
            };
            let exportCalls = 0;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collection],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                updateOpShopPickupCollectionRows: async () => {
                  throw new Error("invalid entry");
                },
                exportOpShopPickupCollectionsExcel: async () => {
                  exportCalls += 1;
                },
              },
            });
            actions.updateOpShopCollectionEntryDraft(
              "COL-FAIL", "ROW-FAIL", "clothing_kg", "3.25",
            );
            await actions.exportOpShopPickupCollections("2026-05-05");
            if (exportCalls !== 0) {
              throw new Error("daily export continued after entry flush failure");
            }
            if (
              state.opshopCollectionEntryDrafts["COL-FAIL"]["ROW-FAIL"].clothing_kg
              !== "3.25"
            ) {
              throw new Error("failed entry flush discarded the user's draft");
            }
            if (state.opshopActionError !== "invalid entry") {
              throw new Error("entry flush failure was not surfaced");
            }
            """
        )

    def test_opshop_save_collection_aborts_when_newer_draft_appears_during_patch(self):
        self._run_workspace_actions_script(
            """
            const pickup = {
              row_id: "ROW-SAVE",
              clothing_kg_snapshot: 1,
              shoes_kg_snapshot: null,
              time_in_snapshot: null,
              time_out_snapshot: null,
              trolleys_out_to_opshops_snapshot: null,
              trolleys_in_to_mcc_snapshot: null,
              hard_toys_snapshot: null,
              soft_toys_snapshot: null,
              black_bags_snapshot: null,
              shoe_bags_snapshot: null,
            };
            const collection = {
              collection_id: "COL-SAVE",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [pickup],
            };
            let resolveFirstPatch;
            let patchCalls = 0;
            let saveCalls = 0;
            let serverCollection = collection;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collection],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const api = {
              updateOpShopPickupCollectionRows: async (_collectionId, payload) => {
                patchCalls += 1;
                const updated = {
                  ...serverCollection,
                  status: "GENERATED",
                  pickups: [{
                    ...pickup,
                    clothing_kg_snapshot: payload.rows[0].clothing_kg,
                  }],
                };
                if (patchCalls === 1) {
                  return new Promise((resolve) => {
                    resolveFirstPatch = () => {
                      serverCollection = updated;
                      resolve(updated);
                    };
                  });
                }
                serverCollection = updated;
                return updated;
              },
              saveGeneratedOpShopPickupCollection: async () => {
                saveCalls += 1;
                serverCollection = { ...serverCollection, status: "SAVED" };
                return serverCollection;
              },
              listOpShopPickupCollectionsByPickupDate: async () => [serverCollection],
            };
            const actions = createWorkspaceActions({
              state,
              api,
              renderWorkspace: () => {},
            });

            actions.updateOpShopCollectionEntryDraft(
              "COL-SAVE", "ROW-SAVE", "clothing_kg", "2.5",
            );
            const firstSave = actions.saveOpShopPickupCollection("COL-SAVE");
            await Promise.resolve();
            actions.updateOpShopCollectionEntryDraft(
              "COL-SAVE", "ROW-SAVE", "clothing_kg", "7.5",
            );
            resolveFirstPatch();
            await firstSave;

            if (saveCalls !== 0) {
              throw new Error("Save Collection continued after a newer draft appeared");
            }
            if (state.opshopPickupCollections[0].status !== "GENERATED") {
              throw new Error("collection was finalized from stale V1 data");
            }
            if (
              state.opshopPickupCollections[0].pickups[0].clothing_kg_snapshot !== 2.5
              || state.opshopCollectionEntryDrafts["COL-SAVE"]["ROW-SAVE"].clothing_kg !== "7.5"
              || state.opshopCollectionEntryDraftVersions["COL-SAVE"] !== 2
            ) {
              throw new Error("V1 persistence or dirty V2 state was not preserved");
            }

            await actions.saveOpShopPickupCollection("COL-SAVE");
            if (
              patchCalls !== 2
              || saveCalls !== 1
              || state.opshopPickupCollections[0].status !== "SAVED"
              || state.opshopPickupCollections[0].pickups[0].clothing_kg_snapshot !== 7.5
              || state.opshopCollectionEntryDrafts["COL-SAVE"]
              || state.opshopCollectionEntryDraftVersions["COL-SAVE"]
            ) {
              throw new Error("explicit retry did not persist V2 before finalizing");
            }
            """
        )

    def test_opshop_single_export_aborts_when_newer_draft_appears_during_patch(self):
        self._run_workspace_actions_script(
            """
            const pickup = {
              row_id: "ROW-EXPORT",
              clothing_kg_snapshot: 1,
              shoes_kg_snapshot: null,
              time_in_snapshot: null,
              time_out_snapshot: null,
              trolleys_out_to_opshops_snapshot: null,
              trolleys_in_to_mcc_snapshot: null,
              hard_toys_snapshot: null,
              soft_toys_snapshot: null,
              black_bags_snapshot: null,
              shoe_bags_snapshot: null,
            };
            const collection = {
              collection_id: "COL-EXPORT",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [pickup],
            };
            const calls = [];
            let resolveFirstPatch;
            let patchCalls = 0;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collection],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                updateOpShopPickupCollectionRows: async (_collectionId, payload) => {
                  patchCalls += 1;
                  calls.push("patch:" + payload.rows[0].clothing_kg);
                  const updated = {
                    ...collection,
                    pickups: [{
                      ...pickup,
                      clothing_kg_snapshot: payload.rows[0].clothing_kg,
                    }],
                  };
                  if (patchCalls === 1) {
                    return new Promise((resolve) => {
                      resolveFirstPatch = () => resolve(updated);
                    });
                  }
                  return updated;
                },
                exportOpShopPickupCollectionExcel: async () => {
                  calls.push("export");
                },
              },
            });

            actions.updateOpShopCollectionEntryDraft(
              "COL-EXPORT", "ROW-EXPORT", "clothing_kg", "2.5",
            );
            const firstExport = actions.exportOpShopPickupCollection("COL-EXPORT");
            await Promise.resolve();
            actions.updateOpShopCollectionEntryDraft(
              "COL-EXPORT", "ROW-EXPORT", "clothing_kg", "7.5",
            );
            resolveFirstPatch();
            await firstExport;
            if (calls.includes("export")) {
              throw new Error("single export continued after a newer draft appeared");
            }
            if (
              state.opshopCollectionEntryDrafts["COL-EXPORT"]["ROW-EXPORT"].clothing_kg
              !== "7.5"
            ) {
              throw new Error("single export discarded the newer draft");
            }

            await actions.exportOpShopPickupCollection("COL-EXPORT");
            if (calls.join(",") !== "patch:2.5,patch:7.5,export") {
              throw new Error("single export retry did not PATCH V2 before exporting once");
            }
            """
        )

    def test_opshop_daily_export_aborts_when_newer_draft_appears_during_patch(self):
        self._run_workspace_actions_script(
            """
            const makePickup = (rowId) => ({
              row_id: rowId,
              clothing_kg_snapshot: 1,
              shoes_kg_snapshot: null,
              time_in_snapshot: null,
              time_out_snapshot: null,
              trolleys_out_to_opshops_snapshot: null,
              trolleys_in_to_mcc_snapshot: null,
              hard_toys_snapshot: null,
              soft_toys_snapshot: null,
              black_bags_snapshot: null,
              shoe_bags_snapshot: null,
            });
            const collectionA = {
              collection_id: "COL-DAILY-A",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [makePickup("ROW-DAILY-A")],
            };
            const collectionB = {
              collection_id: "COL-DAILY-B",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [makePickup("ROW-DAILY-B")],
            };
            const calls = [];
            let resolveFirstPatch;
            let firstPatch = true;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collectionA, collectionB],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                updateOpShopPickupCollectionRows: async (collectionId, payload) => {
                  calls.push("patch:" + collectionId + ":" + payload.rows[0].clothing_kg);
                  const source = collectionId === "COL-DAILY-A" ? collectionA : collectionB;
                  const updated = {
                    ...source,
                    pickups: [{
                      ...source.pickups[0],
                      clothing_kg_snapshot: payload.rows[0].clothing_kg,
                    }],
                  };
                  if (firstPatch) {
                    firstPatch = false;
                    return new Promise((resolve) => {
                      resolveFirstPatch = () => resolve(updated);
                    });
                  }
                  return updated;
                },
                exportOpShopPickupCollectionsExcel: async () => {
                  calls.push("daily");
                },
              },
            });

            actions.updateOpShopCollectionEntryDraft(
              "COL-DAILY-A", "ROW-DAILY-A", "clothing_kg", "2.5",
            );
            actions.updateOpShopCollectionEntryDraft(
              "COL-DAILY-B", "ROW-DAILY-B", "clothing_kg", "3.5",
            );
            const firstExport = actions.exportOpShopPickupCollections("2026-05-05");
            await Promise.resolve();
            actions.updateOpShopCollectionEntryDraft(
              "COL-DAILY-A", "ROW-DAILY-A", "clothing_kg", "7.5",
            );
            resolveFirstPatch();
            await firstExport;
            if (calls.join(",") !== "patch:COL-DAILY-A:2.5") {
              throw new Error("daily export did not abort as a whole on newer draft");
            }
            if (
              state.opshopCollectionEntryDrafts["COL-DAILY-A"]["ROW-DAILY-A"].clothing_kg
              !== "7.5"
              || !state.opshopCollectionEntryDrafts["COL-DAILY-B"]
            ) {
              throw new Error("daily abort did not preserve all pending drafts");
            }

            await actions.exportOpShopPickupCollections("2026-05-05");
            if (
              calls.join(",")
              !== "patch:COL-DAILY-A:2.5,patch:COL-DAILY-A:7.5,patch:COL-DAILY-B:3.5,daily"
            ) {
              throw new Error("daily retry did not stably flush all drafts before one export");
            }
            """
        )

    def test_opshop_saved_and_history_weight_sheets_ignore_stale_drafts(self):
        self.assertIn(
            "collection.collection_id,\n      !readOnly,",
            self.opshop_renderer,
        )
        self._run_frontend_module_script(
            "js/render/opshop/opshop-collection-renderer.js",
            """
            const pickup = {
              row_id: "ROW-READONLY",
              opshop_name_snapshot: "Read Only Shop",
              suburb_snapshot: "Coburg",
              clothing_kg_snapshot: 2.5,
            };
            const state = {
              opshopCollectionEntryDrafts: {
                "COL-SAVED": { "ROW-READONLY": { clothing_kg: "7.5" } },
                "COL-HISTORY": { "ROW-READONLY": { clothing_kg: "7.5" } },
              },
            };
            for (const collectionId of ["COL-SAVED", "COL-HISTORY"]) {
              const values = module.collectionWeightSheetRowValues(
                pickup,
                state,
                collectionId,
                false,
              );
              if (values[2] !== 2.5) {
                throw new Error(collectionId + " displayed an unpersisted draft");
              }
            }
            """,
        )

    def test_opshop_collection_older_patch_response_preserves_newer_draft(self):
        self._run_workspace_actions_script(
            """
            const pickup = {
              row_id: "ROW-RACE",
              clothing_kg_snapshot: 1,
              shoes_kg_snapshot: null,
              time_in_snapshot: null,
              time_out_snapshot: null,
              trolleys_out_to_opshops_snapshot: null,
              trolleys_in_to_mcc_snapshot: null,
              hard_toys_snapshot: null,
              soft_toys_snapshot: null,
              black_bags_snapshot: null,
              shoe_bags_snapshot: null,
            };
            const collection = {
              collection_id: "COL-RACE",
              status: "GENERATED",
              pickup_date: "2026-05-05",
              pickups: [pickup],
            };
            let resolvePatch;
            let sentPayload;
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/collections",
              activeWorkspace: "opshop",
              dispatchDate: "2026-05-05",
              opshopTripSummaryDate: "2026-05-05",
              opshopSavedHistoryDate: "2026-05-05",
              opshopPickupCollections: [collection],
              opshopCollectionEntryDrafts: {},
              opshopCollectionEntryDraftVersions: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api: {
                updateOpShopPickupCollectionRows: async (collectionId, payload) => {
                  sentPayload = payload;
                  return new Promise((resolve) => {
                    resolvePatch = resolve;
                  });
                },
              },
            });

            actions.updateOpShopCollectionEntryDraft(
              "COL-RACE", "ROW-RACE", "clothing_kg", "2.5",
            );
            const pending = actions.saveOpShopPickupCollectionWeightSheet("COL-RACE");
            await Promise.resolve();
            if (sentPayload.rows[0].clothing_kg !== 2.5) {
              throw new Error("V1 draft was not sent");
            }
            actions.updateOpShopCollectionEntryDraft(
              "COL-RACE", "ROW-RACE", "clothing_kg", "7.5",
            );
            resolvePatch({
              ...collection,
              pickups: [{ ...pickup, clothing_kg_snapshot: 2.5 }],
            });
            await pending;

            if (
              state.opshopCollectionEntryDrafts["COL-RACE"]["ROW-RACE"].clothing_kg
              !== "7.5"
              || state.opshopCollectionEntryDraftVersions["COL-RACE"] !== 2
            ) {
              throw new Error("older PATCH response erased the newer V2 draft");
            }
          """
        )

    def test_opshop_daily_flush_stops_after_route_switch_or_logout(self):
        self._run_workspace_actions_script(
            """
            async function runInvalidationScenario(kind) {
              const makePickup = (rowId) => ({
                row_id: rowId,
                clothing_kg_snapshot: 1,
                shoes_kg_snapshot: null,
                time_in_snapshot: null,
                time_out_snapshot: null,
                trolleys_out_to_opshops_snapshot: null,
                trolleys_in_to_mcc_snapshot: null,
                hard_toys_snapshot: null,
                soft_toys_snapshot: null,
                black_bags_snapshot: null,
                shoe_bags_snapshot: null,
              });
              const collectionA = {
                collection_id: "COL-A",
                status: "GENERATED",
                pickup_date: "2026-05-05",
                pickups: [makePickup("ROW-A")],
              };
              const collectionB = {
                collection_id: "COL-B",
                status: "GENERATED",
                pickup_date: "2026-05-05",
                pickups: [makePickup("ROW-B")],
              };
              const calls = [];
              let resolveFirstPatch;
              const state = {
                isLoggedIn: true,
                workspaceRoute: "opshop/collections",
                activeWorkspace: "opshop",
                dispatchDate: "2026-05-05",
                opshopTripSummaryDate: "2026-05-05",
                opshopSavedHistoryDate: "2026-05-05",
                opshopPickupCollections: [collectionA, collectionB],
                opshopCollectionEntryDrafts: {},
                opshopCollectionEntryDraftVersions: {},
                opshopBusyActionKeys: {},
                opshopActionError: "",
              };
              const actions = createWorkspaceActions({
                state,
                renderWorkspace: () => {},
                api: {
                  updateOpShopPickupCollectionRows: async (collectionId) => {
                    calls.push("patch:" + collectionId);
                    if (collectionId === "COL-A") {
                      return new Promise((resolve) => {
                        resolveFirstPatch = resolve;
                      });
                    }
                    return collectionB;
                  },
                  exportOpShopPickupCollectionsExcel: async () => {
                    calls.push("export");
                  },
                },
              });
              actions.updateOpShopCollectionEntryDraft(
                "COL-A", "ROW-A", "clothing_kg", "2",
              );
              actions.updateOpShopCollectionEntryDraft(
                "COL-B", "ROW-B", "shoes_kg", "3",
              );
              const pending = actions.exportOpShopPickupCollections("2026-05-05");
              await Promise.resolve();

              if (kind === "route") {
                state.workspaceRoute = "opshop/history";
              } else {
                state.isLoggedIn = false;
                state.workspaceRoute = "home";
                state.activeWorkspace = "";
                state.opshopCollectionEntryDrafts = {};
                state.opshopCollectionEntryDraftVersions = {};
              }
              resolveFirstPatch(collectionA);
              await pending;

              if (calls.join(",") !== "patch:COL-A") {
                throw new Error(kind + " invalidation allowed stale flush continuation");
              }
              if (
                kind === "route"
                && (
                  !state.opshopCollectionEntryDrafts["COL-A"]
                  || !state.opshopCollectionEntryDrafts["COL-B"]
                )
              ) {
                throw new Error("route-switch stale response cleared pending drafts");
              }
            }

            await runInvalidationScenario("route");
            await runInvalidationScenario("logout");
          """
        )

    def test_opshop_save_and_single_export_stop_after_route_switch_or_logout(self):
        self._run_workspace_actions_script(
            """
            async function runInvalidationScenario(actionKind, invalidationKind) {
              const pickup = {
                row_id: "ROW-STALE",
                clothing_kg_snapshot: 1,
                shoes_kg_snapshot: null,
                time_in_snapshot: null,
                time_out_snapshot: null,
                trolleys_out_to_opshops_snapshot: null,
                trolleys_in_to_mcc_snapshot: null,
                hard_toys_snapshot: null,
                soft_toys_snapshot: null,
                black_bags_snapshot: null,
                shoe_bags_snapshot: null,
              };
              const collection = {
                collection_id: "COL-STALE",
                status: "GENERATED",
                pickup_date: "2026-05-05",
                pickups: [pickup],
              };
              const originalCollections = [collection];
              let continuationCalls = 0;
              let loadCalls = 0;
              let resolvePatch;
              const state = {
                isLoggedIn: true,
                workspaceRoute: "opshop/collections",
                activeWorkspace: "opshop",
                dispatchDate: "2026-05-05",
                opshopTripSummaryDate: "2026-05-05",
                opshopSavedHistoryDate: "2026-05-05",
                opshopPickupCollections: originalCollections,
                opshopCollectionEntryDrafts: {},
                opshopCollectionEntryDraftVersions: {},
                opshopBusyActionKeys: {},
                opshopActionError: "",
              };
              const actions = createWorkspaceActions({
                state,
                renderWorkspace: () => {},
                api: {
                  updateOpShopPickupCollectionRows: async () => (
                    new Promise((resolve) => {
                      resolvePatch = resolve;
                    })
                  ),
                  saveGeneratedOpShopPickupCollection: async () => {
                    continuationCalls += 1;
                  },
                  exportOpShopPickupCollectionExcel: async () => {
                    continuationCalls += 1;
                  },
                  listOpShopPickupCollectionsByPickupDate: async () => {
                    loadCalls += 1;
                    return [];
                  },
                },
              });
              actions.updateOpShopCollectionEntryDraft(
                "COL-STALE", "ROW-STALE", "clothing_kg", "2.5",
              );
              const pending = actionKind === "save"
                ? actions.saveOpShopPickupCollection("COL-STALE")
                : actions.exportOpShopPickupCollection("COL-STALE");
              await Promise.resolve();

              if (invalidationKind === "route") {
                state.workspaceRoute = "opshop/history";
              } else {
                state.isLoggedIn = false;
                state.workspaceRoute = "home";
                state.activeWorkspace = "";
                state.opshopCollectionEntryDrafts = {};
                state.opshopCollectionEntryDraftVersions = {};
              }
              resolvePatch({
                ...collection,
                pickups: [{ ...pickup, clothing_kg_snapshot: 2.5 }],
              });
              await pending;

              if (continuationCalls !== 0 || loadCalls !== 0) {
                throw new Error(
                  actionKind + " continued after " + invalidationKind + " invalidation",
                );
              }
              if (state.opshopPickupCollections !== originalCollections) {
                throw new Error("stale PATCH response reconciled collection state");
              }
              if (
                invalidationKind === "route"
                && state.opshopCollectionEntryDrafts["COL-STALE"]["ROW-STALE"].clothing_kg
                !== "2.5"
              ) {
                throw new Error("route invalidation cleared the pending draft");
              }
              if (Object.keys(state.opshopBusyActionKeys).length) {
                throw new Error("stale action left its busy token behind");
              }
            }

            for (const actionKind of ["save", "export"]) {
              for (const invalidationKind of ["route", "logout"]) {
                await runInvalidationScenario(actionKind, invalidationKind);
              }
            }
            """
        )

    def test_trip_summary_date_loads_service_date_scoped_data_without_polluting_task_pool_boards(self):
        self._run_workspace_actions_script(
            """
            const deliveryTaskPoolBoard = { marker: "delivery-task-pool", orders: [], assignments: [], driver_vehicle_assignments: [], drivers: [] };
            const deliveryTripBoard = {
              marker: "delivery-trip-summary",
              orders: [{ order_id: "ORDER-HIST", delivery_date: "2026-06-22" }],
              assignments: [{ task_id: "ORDER-HIST", driver_id: "DRIVER-1" }],
              driver_vehicle_assignments: [{ delivery_date: "2026-06-22", driver_id: "DRIVER-1", vehicle_id: "VEHICLE-1" }],
              drivers: [{ driver_id: "DRIVER-1" }],
            };
            const opshopTaskPoolBoard = { marker: "opshop-task-pool", opshop_pickups: [], countryside_route_groups: [] };
            const opshopTripBoard = {
              marker: "opshop-trip-summary",
              opshop_pickups: [{ pickup_task_id: "PICKUP-HIST", pickup_date: "2026-06-22", driver_id: "DRIVER-1" }],
              drivers: [{ driver_id: "DRIVER-1" }],
            };
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryBoard: deliveryTaskPoolBoard,
              deliveryRunSheets: [],
              deliveryTripSummaryDate: "2026-06-24",
              deliveryTripSummaryBoard: null,
              deliveryTripSummaryRunSheets: [],
              deliveryAssignmentDrafts: { "ORDER-DRAFT": { driver_id: "DRIVER-2" } },
              deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {},
              deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {},
              deliveryBusyActionKeys: {},
              deliveryActionError: "",
              opshopBoard: opshopTaskPoolBoard,
              opshopPickupCollections: [],
              opshopTripSummaryDate: "2026-06-24",
              opshopTripSummaryBoard: null,
              opshopTripSummaryCollections: [],
              opshopAssignmentDrafts: { "PICKUP-DRAFT": "DRIVER-2" },
              countrysideRouteGroupDrafts: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => {
                throw new Error("Delivery Trip Summary should not load dispatch board");
              },
              getDeliveryTripSummary: async ({ deliveryDate }) => {
                if (deliveryDate !== "2026-06-22") {
                  throw new Error(`wrong Delivery Trip Summary scope ${deliveryDate}`);
                }
                return deliveryTripBoard;
              },
              listDeliveryRunSheetsByDeliveryDate: async (deliveryDate) => {
                if (deliveryDate !== "2026-06-22") {
                  throw new Error(`wrong Delivery Run Sheet scope ${deliveryDate}`);
                }
                return [{ run_sheet_id: "DRS-HIST", delivery_date: deliveryDate }];
              },
              getOpShopWorkspaceBoard: async () => {
                throw new Error("OP SHOP Trip Summary should not load dispatch board");
              },
              getOpShopTripSummary: async ({ pickupDate }) => {
                if (pickupDate !== "2026-06-22") {
                  throw new Error(`wrong OP SHOP Trip Summary scope ${pickupDate}`);
                }
                return opshopTripBoard;
              },
              listOpShopPickupCollectionsByPickupDate: async (pickupDate) => {
                if (pickupDate !== "2026-06-22") {
                  throw new Error(`wrong OP SHOP collection scope ${pickupDate}`);
                }
                return [{ collection_id: "OPC-HIST", pickup_date: pickupDate }];
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.updateDeliveryTripSummaryDate("2026-06-22");
            if (state.deliveryBoard !== deliveryTaskPoolBoard) {
              throw new Error("Delivery Task Pool board was polluted by Trip Summary reload");
            }
            if (state.deliveryTripSummaryBoard !== deliveryTripBoard ||
                state.deliveryTripSummaryRunSheets[0].run_sheet_id !== "DRS-HIST") {
              throw new Error("Delivery Trip Summary scoped board/run sheets were not loaded");
            }
            if (!Object.prototype.hasOwnProperty.call(state.deliveryAssignmentDrafts, "ORDER-DRAFT")) {
              throw new Error("Delivery Task Pool assignment drafts were pruned by Trip Summary reload");
            }

            state.workspaceRoute = "opshop/trip-summary";
            state.activeWorkspace = "opshop";
            await actions.updateOpShopTripSummaryDate("2026-06-22");
            if (state.opshopBoard !== opshopTaskPoolBoard) {
              throw new Error("OP SHOP Task Pool board was polluted by Trip Summary reload");
            }
            if (state.opshopTripSummaryBoard !== opshopTripBoard ||
                state.opshopTripSummaryCollections[0].collection_id !== "OPC-HIST") {
              throw new Error("OP SHOP Trip Summary scoped board/collections were not loaded");
            }
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "PICKUP-DRAFT")) {
              throw new Error("OP SHOP Task Pool assignment drafts were pruned by Trip Summary reload");
            }
            """
        )

    def test_opshop_trip_summary_unassign_uses_post_response_without_refresh(self):
        self._run_workspace_actions_script(
            """
            const returnedBoard = {
              marker: "post-response",
              pickup_date: "2026-06-24",
              opshop_pickups: [],
              drivers: [],
            };
            const staleBoard = {
              marker: "stale-board",
              pickup_date: "2026-06-24",
              opshop_pickups: [{ pickup_task_id: "PICKUP-1" }],
              drivers: [],
            };
            let getCalls = 0;
            let postCalls = 0;
            let navigationCalls = 0;
            let staleResolve;
            let useDeferredResponse = false;
            const deferredResponse = new Promise((resolve) => {
              staleResolve = resolve;
            });
            const state = {
              isLoggedIn: true,
              authSessionVersion: 7,
              workspaceRoute: "opshop/trip-summary",
              activeWorkspace: "opshop",
              dispatchDate: "2026-06-23",
              opshopTripSummaryDate: "2026-06-24",
              opshopTripSummaryBoard: staleBoard,
              opshopTripSummaryCollections: [],
              opshopBoard: { marker: "task-pool", opshop_pickups: [] },
              opshopPickupCollections: [],
              opshopAssignmentDrafts: {
                "PICKUP-1": "DRIVER-1",
                "PICKUP-OTHER": "DRIVER-2",
              },
              countrysideRouteGroupDrafts: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
            };
            const api = {
              getOpShopTripSummary: async () => {
                getCalls += 1;
                throw new Error("Trip Summary GET must not run after unassign");
              },
              getOpShopWorkspaceBoard: async () => {
                getCalls += 1;
                throw new Error("Task Pool GET must not run after unassign");
              },
              listOpShopPickupCollectionsByPickupDate: async () => {
                getCalls += 1;
                throw new Error("Collection GET must not run after unassign");
              },
              unassignOpShopWorkspacePickup: async (payload) => {
                postCalls += 1;
                if (payload.pickup_task_id !== "PICKUP-1"
                    || Object.prototype.hasOwnProperty.call(payload, "dispatch_date")) {
                  throw new Error("Trip Summary unassign sent the wrong scoped payload");
                }
                return useDeferredResponse ? deferredResponse : returnedBoard;
              },
            };
            window.location.hash = "#opshop/trip-summary";
            window.scrollX = 5;
            window.scrollY = 480;
            window.scrollTo = (x, y) => {
              window.scrollX = x;
              window.scrollY = y;
            };
            let renderCalls = 0;
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {
                renderCalls += 1;
                window.scrollX = 0;
                window.scrollY = 0;
              },
              api,
              navigateWorkspaceRoute: () => {
                navigationCalls += 1;
              },
            });

            await actions.unassignOpShopPickup("PICKUP-1");
            if (state.opshopTripSummaryBoard !== returnedBoard) {
              throw new Error("POST response did not replace Trip Summary board in place");
            }
            if (state.opshopBoard.marker !== "task-pool") {
              throw new Error("Trip Summary unassign polluted the Task Pool board");
            }
            if (Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "PICKUP-1")
                || state.opshopAssignmentDrafts["PICKUP-OTHER"] !== "DRIVER-2") {
              throw new Error("Trip Summary unassign did not clear only the matching draft");
            }
            if (getCalls !== 0 || navigationCalls !== 0
                || window.location.hash !== "#opshop/trip-summary") {
              throw new Error("Trip Summary unassign refreshed or navigated");
            }
            if (postCalls !== 1 || renderCalls < 2
                || window.scrollX !== 5 || window.scrollY !== 480) {
              throw new Error("Trip Summary unassign lost POST/render/scroll behavior");
            }
            if (state.opshopTripSummaryDate !== "2026-06-24"
                || state.workspaceRoute !== "opshop/trip-summary"
                || state.opshopActionError
                || Object.keys(state.opshopBusyActionKeys).length) {
              throw new Error("Trip Summary unassign lost date/route/error/busy invariants");
            }

            useDeferredResponse = true;
            state.opshopTripSummaryBoard = staleBoard;
            state.opshopAssignmentDrafts["PICKUP-1"] = "DRIVER-1";
            const staleAction = actions.unassignOpShopPickup("PICKUP-1");
            state.opshopTripSummaryDate = "2026-06-25";
            staleResolve({ marker: "obsolete-response", opshop_pickups: [] });
            await staleAction;
            if (state.opshopTripSummaryBoard !== staleBoard
                || state.opshopAssignmentDrafts["PICKUP-1"] !== "DRIVER-1") {
              throw new Error("Stale Trip Summary response replaced current state");
            }
            if (getCalls !== 0 || navigationCalls !== 0 || postCalls !== 2
                || Object.keys(state.opshopBusyActionKeys).length) {
              throw new Error("Stale Trip Summary unassign broke request guards");
            }
            """,
            setup="""
            globalThis.requestAnimationFrame = (callback) => {
              callback();
              return 1;
            };
            globalThis.setTimeout = () => {
              throw new Error("Trip Summary unassign must not use a delay");
            };
            """,
        )

    def test_generated_opshop_task_pool_controls_are_locked_with_driver_text(self):
        oncall_uri = (FRONTEND_ROOT / "js/render/opshop/opshop-oncall-renderer.js").as_uri()
        countryside_uri = (
            FRONTEND_ROOT / "js/render/opshop/opshop-countryside-renderer.js"
        ).as_uri()
        utils_uri = (FRONTEND_ROOT / "js/render/opshop/opshop-renderer-utils.js").as_uri()
        self._run_frontend_module_script(
            "js/render/opshop/opshop-regular-renderer.js",
            f"""
            const oncall = await import({oncall_uri!r});
            const countryside = await import({countryside_uri!r});
            const utils = await import({utils_uri!r});
            const lockText = "Already generated to Driver One";
            const state = {{
              dispatchDate: "2026-07-24",
              opshopBoard: {{
                drivers: [{{ driver_id: "DRIVER-1", name: "Driver One" }}],
                opshop_pickups: [],
              }},
              opshopAssignmentDrafts: {{ "PICKUP-LOCKED": "DRIVER-2" }},
              countrysideRouteGroupDrafts: {{
                "ROUTE-1": {{
                  pickup_date: "2026-07-24",
                  assigned_driver_id: "DRIVER-2",
                  notes: "Stale draft",
                }},
              }},
              opshopBusyActionKeys: {{}},
            }};
            const actions = {{
              openOpShopPickupDetail: () => {{}},
              startEditOpShopPickupTask: () => {{}},
              startDeleteOpShopPickupTask: () => {{}},
              updateOpShopAssignmentDraft: () => {{}},
              unassignOpShopPickup: () => {{}},
              updateCountrysideRouteGroupDraft: () => {{}},
              assignCountrysideRouteGroup: () => {{}},
            }};
            const locked = {{
              pickup_task_id: "PICKUP-LOCKED",
              opshop_name: "Synthetic OP SHOP",
              suburb: "COBURG",
              street_address: "1 Test Street",
              pickup_date: "2026-07-24",
              run_type: "ON_CALL",
              pickup_category: "NORMAL",
              status: "ASSIGNED",
              assigned_to_locked: true,
              assignment_lock_reason: lockText,
              is_assigned: true,
              driver_id: "DRIVER-1",
              assigned_driver_id: "DRIVER-1",
              assigned_driver_name: "Driver One",
            }};

            const regularRow = module.createRegularPickupRow(
              {{ ...locked, run_type: "REGULAR" }},
              state,
              actions,
            );
            const regularButtons = regularRow.querySelectorAll("button");
            if (!regularRow.querySelector("select").disabled
                || !regularButtons.find((button) => button.textContent === "Edit").disabled
                || !regularButtons.find((button) => button.textContent === "Delete").disabled
                || !regularRow.textContent.includes(lockText)) {{
              throw new Error("Regular generated pickup controls/text are not locked");
            }}

            const oncallCard = oncall.createOncallPickupRow(locked, state, actions);
            const oncallButtons = oncallCard.querySelectorAll("button");
            for (const label of ["Edit", "Delete", "Unassign now"]) {{
              if (!oncallButtons.find((button) => button.textContent === label)?.disabled) {{
                throw new Error(`Oncall generated pickup left ${{label}} enabled`);
              }}
            }}
            if (!oncallCard.querySelector("select").disabled
                || !oncallCard.textContent.includes(lockText)) {{
              throw new Error("Oncall generated pickup assignment/text are not locked");
            }}

            const countrysidePickup = {{
              ...locked,
              pickup_category: "COUNTRYSIDE",
              route_group_id: "ROUTE-1",
              route_group_name: "Country Route",
            }};
            state.opshopBoard.opshop_pickups = [countrysidePickup];
            const routeForm = countryside.createRouteGroupAssignmentForm(
              {{ route_group_id: "ROUTE-1", route_group_name: "Country Route" }},
              new Map([["ROUTE-1", [{{ template_id: "TEMPLATE-1" }}]]]),
              [countrysidePickup],
              state,
              actions,
              () => {{}},
            );
            if (routeForm.querySelectorAll("input").some((input) => !input.disabled)
                || !routeForm.querySelector("select").disabled
                || !routeForm.querySelectorAll("button")
                  .find((button) => button.textContent === "Assign Route Group")?.disabled
                || !routeForm.textContent.includes(lockText)) {{
              throw new Error("Countryside generated pickup mutation/text are not locked");
            }}
            if (utils.changedOpShopAssignments([locked], state).length !== 0) {{
              throw new Error("Generated pickup remained eligible for bulk assignment");
            }}
            """,
            setup="""
            class FakeNode {
              constructor(tagName, text = "") {
                this.tagName = tagName;
                this.children = [];
                this.attributes = {};
                this.listeners = {};
                this.dataset = {};
                this.disabled = false;
                this.value = "";
                this._text = text;
                this._className = "";
                this.classList = {
                  add: (...tokens) => {
                    const classes = new Set(this._className.split(/\\s+/).filter(Boolean));
                    tokens.forEach((token) => classes.add(token));
                    this._className = [...classes].join(" ");
                  },
                  contains: (token) => this._className.split(/\\s+/).includes(token),
                  toggle: (token, enabled) => {
                    const classes = new Set(this._className.split(/\\s+/).filter(Boolean));
                    enabled ? classes.add(token) : classes.delete(token);
                    this._className = [...classes].join(" ");
                    return enabled;
                  },
                };
              }
              get className() { return this._className; }
              set className(value) { this._className = String(value || ""); }
              get textContent() {
                return this._text + this.children.map((child) => child.textContent || "").join("");
              }
              set textContent(value) { this._text = String(value ?? ""); }
              append(...children) { this.children.push(...children); }
              setAttribute(name, value) { this.attributes[name] = String(value); }
              addEventListener(type, listener) {
                (this.listeners[type] ||= []).push(listener);
              }
              querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
              querySelectorAll(selector) {
                const matches = [];
                const visit = (node) => {
                  if (selector.startsWith(".")
                    ? node.classList?.contains(selector.slice(1))
                    : node.tagName === selector) {
                    matches.push(node);
                  }
                  node.children?.forEach(visit);
                };
                this.children.forEach(visit);
                return matches;
              }
            }
            globalThis.document = {
              createElement: (tagName) => new FakeNode(tagName),
              createElementNS: (_namespace, tagName) => new FakeNode(tagName),
              createTextNode: (text) => new FakeNode("#text", String(text)),
            };
            """,
        )

    def test_trip_summary_empty_fallback_and_route_reload_use_shared_default(self):
        self._run_workspace_actions_script(
            """
            const deliveryDates = [];
            const opshopDates = [];
            const state = {
              isLoggedIn: true,
              authSessionVersion: 1,
              workspaceRoute: "delivery/trip-summary",
              activeWorkspace: "delivery",
              dispatchDate: "2026-08-04",
              deliveryTripSummaryDate: "",
              deliveryTripSummaryBoard: null,
              deliveryTripSummaryRunSheets: [],
              deliveryRunSheets: [],
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {},
              deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {},
              deliveryBusyActionKeys: {},
              deliveryActionError: "",
              deliveryActionSuccess: "",
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              opshopTripSummaryDate: "",
              opshopTripSummaryBoard: null,
              opshopTripSummaryCollections: [],
              opshopPickupCollections: [],
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
            };
            const api = {
              getDeliveryTripSummary: async ({ deliveryDate }) => {
                deliveryDates.push(deliveryDate);
                return { orders: [], assignments: [], driver_vehicle_assignments: [], drivers: [] };
              },
              listDeliveryRunSheetsByDeliveryDate: async (deliveryDate) => {
                deliveryDates.push(deliveryDate);
                return [];
              },
              getOpShopTripSummary: async ({ pickupDate }) => {
                opshopDates.push(pickupDate);
                return { opshop_pickups: [], drivers: [] };
              },
              listOpShopPickupCollectionsByPickupDate: async (pickupDate) => {
                opshopDates.push(pickupDate);
                return [];
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.updateDeliveryTripSummaryDate("");
            if (state.deliveryTripSummaryDate !== "2026-08-05"
                || deliveryDates.some((date) => date !== "2026-08-05")) {
              throw new Error("Delivery empty date did not use the shared next-business-day default");
            }

            state.workspaceRoute = "opshop/trip-summary";
            state.activeWorkspace = "opshop";
            await actions.updateOpShopTripSummaryDate("");
            if (state.opshopTripSummaryDate !== "2026-08-05"
                || opshopDates.some((date) => date !== "2026-08-05")) {
              throw new Error("OP SHOP empty date did not use the shared next-business-day default");
            }

            state.deliveryTripSummaryDate = "2026-07-20";
            state.workspaceRoute = "delivery/run-sheet";
            state.activeWorkspace = "delivery";
            await actions.loadWorkspaceRoute(state.workspaceRoute);
            state.workspaceRoute = "delivery/trip-summary";
            await actions.loadWorkspaceRoute(state.workspaceRoute);
            if (state.deliveryTripSummaryDate !== "2026-07-20"
                || !deliveryDates.slice(-3).every((date) => date === "2026-07-20")) {
              throw new Error("Delivery route reload replaced the manual Trip Summary date");
            }

            state.opshopTripSummaryDate = "2026-09-14";
            state.workspaceRoute = "opshop/collections";
            state.activeWorkspace = "opshop";
            await actions.loadWorkspaceRoute(state.workspaceRoute);
            state.workspaceRoute = "opshop/trip-summary";
            await actions.loadWorkspaceRoute(state.workspaceRoute);
            if (state.opshopTripSummaryDate !== "2026-09-14"
                || !opshopDates.slice(-3).every((date) => date === "2026-09-14")) {
              throw new Error("OP SHOP route reload replaced the manual Trip Summary date");
            }
            if (state.dispatchDate !== "2026-08-04") {
              throw new Error("Trip Summary date changes modified Dispatch Date");
            }
            """,
            setup="""
            const RealDate = Date;
            globalThis.Date = class extends RealDate {
              constructor(...args) {
                if (args.length) {
                  super(...args);
                } else {
                  super(2026, 7, 4, 12, 0, 0, 0);
                }
              }
              static now() {
                return new RealDate(2026, 7, 4, 12, 0, 0, 0).getTime();
              }
            };
            """,
        )

    def test_opshop_default_driver_is_suggested_not_auto_submitted(self):
        self.assertIn("Suggested default", self.opshop_renderer)
        self.assertIn("defaultDriverHint", self.opshop_renderer)
        self.assertIn("defaultDriverExists", self.opshop_renderer)
        self.assertIn("`${defaultName} suggested`", self.opshop_renderer)
        self.assertIn("`${defaultName} unavailable`", self.opshop_renderer)
        self.assertIn('pickup.run_type !== "REGULAR"', self.opshop_renderer)
        self.assertIn("Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts", self.opshop_renderer)
        changed_block = self.opshop_renderer.split(
            "function changedOpShopAssignments", 1
        )[1].split("function selectedOpShopDriverId", 1)[0]
        self.assertIn("state.opshopAssignmentDrafts", changed_block)
        self.assertNotIn("default_driver_id", changed_block)
        create_select_block = self.opshop_renderer.split(
            "function createSelect", 1
        )[1].split("function createDateField", 1)[0]
        self.assertLess(
            create_select_block.index("options.forEach"),
            create_select_block.index('select.value = value || ""'),
        )

    def test_generated_cancel_requires_confirmation_before_scoped_api_call(self):
        self._run_workspace_actions_script(
            """
            const baseState = {
              isLoggedIn: true,
              workspaceRoute: "delivery/run-sheet",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: { "ORDER-1": { driver_id: "DRIVER-1" } },
              deliveryVehicleDrafts: {},
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: { "PICKUP-1": "DRIVER-1" },
              countrysideRouteGroupDrafts: {},
            };

            let deliveryCancelCalls = 0;
            let opshopCancelCalls = 0;
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => baseState.deliveryBoard,
              getOpShopWorkspaceBoard: async () => baseState.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              cancelGeneratedDeliveryRunSheet: async () => { deliveryCancelCalls += 1; },
              cancelGeneratedOpShopPickupCollection: async () => { opshopCancelCalls += 1; },
            };

            const declined = createWorkspaceActions({
              state: baseState,
              renderWorkspace: () => {},
              api,
              confirmAction: () => false,
            });
            await declined.cancelDeliveryRunSheet("DRS-1");
            if (deliveryCancelCalls !== 0 || Object.keys(baseState.deliveryBusyActionKeys || {}).length || baseState.deliveryActionError) {
              throw new Error("declined Delivery cancel changed state or called API");
            }
            baseState.workspaceRoute = "opshop/collections";
            baseState.activeWorkspace = "opshop";
            await declined.cancelOpShopPickupCollection("OPC-1");
            if (opshopCancelCalls !== 0 || Object.keys(baseState.opshopBusyActionKeys || {}).length || baseState.opshopActionError) {
              throw new Error("declined OP SHOP cancel changed state or called API");
            }

            const confirmed = createWorkspaceActions({
              state: baseState,
              renderWorkspace: () => {},
              api,
              confirmAction: () => true,
            });
            baseState.workspaceRoute = "delivery/run-sheet";
            baseState.activeWorkspace = "delivery";
            await confirmed.cancelDeliveryRunSheet("DRS-1");
            baseState.workspaceRoute = "opshop/collections";
            baseState.activeWorkspace = "opshop";
            await confirmed.cancelOpShopPickupCollection("OPC-1");
            if (deliveryCancelCalls !== 1 || opshopCancelCalls !== 1) {
              throw new Error("confirmed cancel did not call scoped cancel APIs");
            }
            """
        )

    def test_opshop_batch_apply_preserves_unsubmitted_drafts_and_failed_drafts(self):
        self._run_workspace_actions_script(
            """
            const pickups = [
              { pickup_task_id: "REG-1", assigned_driver_id: "", driver_id: "" },
              { pickup_task_id: "ONCALL-1", assigned_driver_id: "DRIVER-OLD", driver_id: "DRIVER-OLD" },
              { pickup_task_id: "COUNTRY-1", assigned_driver_id: "DRIVER-3", driver_id: "DRIVER-3" },
            ];
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/oncall",
              activeWorkspace: "opshop",
              dispatchDate: "2026-06-24",
              opshopBoard: { opshop_pickups: pickups, countryside_route_groups: [] },
              opshopPickupCollections: [],
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: {
                "REG-1": "DRIVER-1",
                "ONCALL-1": "",
                "COUNTRY-1": "DRIVER-2",
              },
              countrysideRouteGroupDrafts: {},
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
            };
            const submitted = [];
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              applyOpShopWorkspaceAssignments: async (payload) => {
                submitted.push(payload);
                return state.opshopBoard;
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.applyOpShopAssignmentChanges([pickups[1]]);
            if (submitted.length !== 1 || submitted[0].assignments[0].driver_id !== null) {
              throw new Error("explicit Unassigned draft was not sent as null");
            }
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "REG-1")) {
              throw new Error("Regular draft was not preserved after Oncall apply");
            }
            if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "COUNTRY-1")) {
              throw new Error("Countryside draft was not preserved after Oncall apply");
            }
            if (Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, "ONCALL-1")) {
              throw new Error("submitted Oncall draft was not removed after success");
            }

            api.applyOpShopWorkspaceAssignments = async () => {
              const error = new Error("apply failed");
              error.status = 400;
              throw error;
            };
            const beforeFailure = JSON.stringify(state.opshopAssignmentDrafts);
            await actions.applyOpShopAssignmentChanges([pickups[0]]);
            if (JSON.stringify(state.opshopAssignmentDrafts) !== beforeFailure) {
              throw new Error("failed OP SHOP apply changed drafts");
            }
            if (state.opshopActionError !== "apply failed") {
              throw new Error("failed OP SHOP apply did not surface validation error");
            }
            """
        )

    def test_stale_mutation_responses_do_not_replace_current_workspace_state(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              let reject;
              const promise = new Promise((done, fail) => {
                resolve = done;
                reject = fail;
              });
              return { promise, resolve, reject };
            }

            const deliveryMutation = deferred();
            const opshopMutation = deferred();
            const staleDeliveryError = deferred();
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryBoard: {
                marker: "date-a",
                orders: [{ order_id: "ORDER-1" }],
                assignments: [],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: { "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" } },
              deliveryVehicleDrafts: {},
              opshopBoard: {
                marker: "opshop-a",
                opshop_pickups: [{ pickup_task_id: "PICKUP-1", assigned_driver_id: "", driver_id: "" }],
                countryside_route_groups: [],
              },
              opshopPickupCollections: [],
              opshopWorkspaceError: "",
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: { "PICKUP-1": "DRIVER-1" },
              countrysideRouteGroupDrafts: {},
            };
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              assignDeliveryWorkspaceOrder: async () => deliveryMutation.promise,
              applyOpShopWorkspaceAssignments: async () => opshopMutation.promise,
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const deliveryAction = actions.applyDeliveryOrderAssignment("ORDER-1");
            state.dispatchDate = "2026-06-25";
            state.deliveryBoard = { marker: "date-b", orders: [], assignments: [], driver_vehicle_assignments: [] };
            deliveryMutation.resolve({ marker: "stale-date-a" });
            await deliveryAction;
            if (state.deliveryBoard.marker !== "date-b") {
              throw new Error("stale Delivery mutation overwrote current board");
            }
            if (state.deliveryActionError || Object.keys(state.deliveryBusyActionKeys || {}).length) {
              throw new Error("stale Delivery mutation left error or busy state");
            }

            state.workspaceRoute = "opshop/regular";
            state.activeWorkspace = "opshop";
            state.dispatchDate = "2026-06-24";
            const opshopAction = actions.applyOpShopAssignmentChanges(state.opshopBoard.opshop_pickups);
            state.workspaceRoute = "opshop/oncall";
            state.opshopBoard = { marker: "opshop-new-route", opshop_pickups: [], countryside_route_groups: [] };
            opshopMutation.resolve({ marker: "stale-opshop-route" });
            await opshopAction;
            if (state.opshopBoard.marker !== "opshop-new-route") {
              throw new Error("stale OP SHOP mutation overwrote current board");
            }
            if (state.opshopActionError || Object.keys(state.opshopBusyActionKeys || {}).length) {
              throw new Error("stale OP SHOP mutation left error or busy state");
            }

            api.assignDeliveryWorkspaceOrder = async () => staleDeliveryError.promise;
            state.workspaceRoute = "delivery/task-pool";
            state.activeWorkspace = "delivery";
            state.dispatchDate = "2026-06-24";
            state.deliveryAssignmentDrafts = { "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" } };
            const deliveryErrorAction = actions.applyDeliveryOrderAssignment("ORDER-1");
            state.dispatchDate = "2026-06-25";
            const validationError = new Error("stale validation error");
            validationError.status = 400;
            staleDeliveryError.reject(validationError);
            await deliveryErrorAction;
            if (state.deliveryActionError) {
              throw new Error("stale Delivery validation error appeared on current page");
            }
            if (Object.keys(state.deliveryBusyActionKeys || {}).length) {
              throw new Error("stale Delivery validation error left busy state");
            }
            """
        )

    def test_dispatch_date_change_clears_workspace_drafts_and_errors(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/countryside",
              activeWorkspace: "opshop",
              dispatchDate: "2026-06-24",
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryActionError: "old delivery error",
              deliveryBusyActionKeys: { "delivery-assignment:ORDER-1": "old" },
              deliveryAssignmentDrafts: { "ORDER-1": { driver_id: "DRIVER-1" } },
              deliveryVehicleDrafts: { "2026-06-24|DRIVER-1": "VEHICLE-1" },
              deliveryVehicleClaims: {
                "2026-06-24|DRIVER-1": { vehicle_id: "VEHICLE-1", sequence: 1 },
              },
              deliveryVehicleErrors: { "2026-06-24|DRIVER-1": "old" },
              deliveryVehiclePendingKeys: { "2026-06-24|DRIVER-1": true },
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              opshopActionError: "old opshop error",
              opshopBusyActionKeys: { "opshop-unassign:PICKUP-1": "old" },
              opshopAssignmentDrafts: { "PICKUP-1": "DRIVER-1" },
              countrysideRouteGroupDrafts: {
                "ROUTE-1": {
                  pickup_date: "2026-06-24",
                  assigned_driver_id: "DRIVER-1",
                  notes: "old note",
                },
              },
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
            };
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => ({
                opshop_pickups: [],
                countryside_route_groups: [{ route_group_id: "ROUTE-1" }],
              }),
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.updateDispatchDate("2026-06-25");
            if (state.dispatchDate !== "2026-06-25") {
              throw new Error("dispatch date did not update");
            }
            for (const [name, value] of Object.entries({
              deliveryAssignmentDrafts: state.deliveryAssignmentDrafts,
              deliveryVehicleDrafts: state.deliveryVehicleDrafts,
              deliveryVehicleClaims: state.deliveryVehicleClaims,
              deliveryVehicleErrors: state.deliveryVehicleErrors,
              deliveryVehiclePendingKeys: state.deliveryVehiclePendingKeys,
              opshopAssignmentDrafts: state.opshopAssignmentDrafts,
              countrysideRouteGroupDrafts: state.countrysideRouteGroupDrafts,
            })) {
              if (Object.keys(value || {}).length) {
                throw new Error(`${name} was not cleared on dispatch date change`);
              }
            }
            if (state.deliveryActionError || state.opshopActionError) {
              throw new Error("workspace action errors were not cleared");
            }

            actions.updateCountrysideRouteGroupDraft("ROUTE-1", "assigned_driver_id", "DRIVER-2");
            if (state.countrysideRouteGroupDrafts["ROUTE-1"].pickup_date !== "2026-06-25") {
              throw new Error("Countryside route-group draft did not default to new dispatch date");
            }
            """
        )

    def test_dispatch_date_change_does_not_modify_saved_history_state(self):
        self._run_workspace_actions_script(
            """
            const deliveryHistory = [{ run_sheet_id: "DRS-HISTORY" }];
            const opshopHistory = [{ collection_id: "OPC-HISTORY" }];
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryTripSummaryDate: "2026-06-24",
              opshopTripSummaryDate: "2026-06-24",
              deliverySavedHistoryDate: "2026-05-10",
              deliverySavedHistoryRunSheets: deliveryHistory,
              opshopSavedHistoryDate: "2026-05-11",
              opshopSavedHistoryCollections: opshopHistory,
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {},
              deliveryVehicleErrors: {},
              deliveryVehiclePendingKeys: {},
              deliveryBusyActionKeys: {},
              deliveryActionError: "",
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
              opshopBusyActionKeys: {},
              opshopActionError: "",
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
            };
            const api = {
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.updateDispatchDate("2026-06-25");
            if (state.deliveryTripSummaryDate !== "2026-06-24"
                || state.opshopTripSummaryDate !== "2026-06-24") {
              throw new Error("Dispatch Date changed independent Trip Summary dates");
            }
            if (state.deliverySavedHistoryDate !== "2026-05-10"
                || state.deliverySavedHistoryRunSheets !== deliveryHistory
                || state.opshopSavedHistoryDate !== "2026-05-11"
                || state.opshopSavedHistoryCollections !== opshopHistory) {
              throw new Error("Dispatch Date changed independent History state");
            }
            """
        )

    def test_concurrent_delivery_busy_keys_are_independent_and_token_guarded(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const first = deferred();
            const second = deferred();
            const oldSameKey = deferred();
            const newSameKey = deferred();
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliveryBoard: {
                orders: [{ order_id: "ORDER-1" }, { order_id: "ORDER-2" }],
                assignments: [],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {
                "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" },
                "ORDER-2": { driver_id: "DRIVER-2", trip_no: "trip1" },
              },
              deliveryVehicleDrafts: {},
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
            };
            let sameKeyCall = 0;
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              assignDeliveryWorkspaceOrder: async (payload) => {
                if (payload.order_id === "ORDER-2") {
                  return second.promise;
                }
                if (payload.dispatch_date === "2026-06-25") {
                  return newSameKey.promise;
                }
                sameKeyCall += 1;
                return sameKeyCall === 1 ? first.promise : oldSameKey.promise;
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const firstAction = actions.applyDeliveryOrderAssignment("ORDER-1");
            const secondAction = actions.applyDeliveryOrderAssignment("ORDER-2");
            if (!state.deliveryBusyActionKeys["delivery-assignment:ORDER-1"] ||
                !state.deliveryBusyActionKeys["delivery-assignment:ORDER-2"]) {
              throw new Error("Delivery did not track two busy actions independently");
            }
            first.resolve({});
            await firstAction;
            if (!state.deliveryBusyActionKeys["delivery-assignment:ORDER-2"]) {
              throw new Error("finishing first Delivery action cleared second busy key");
            }
            second.resolve({});
            await secondAction;
            if (Object.keys(state.deliveryBusyActionKeys).length) {
              throw new Error("Delivery busy registry did not clear after both actions finished");
            }

            state.dispatchDate = "2026-06-24";
            state.deliveryAssignmentDrafts = { "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" } };
            const oldAction = actions.applyDeliveryOrderAssignment("ORDER-1");
            await actions.updateDispatchDate("2026-06-25");
            state.deliveryAssignmentDrafts = { "ORDER-1": { driver_id: "DRIVER-NEW", trip_no: "trip1" } };
            const currentAction = actions.applyDeliveryOrderAssignment("ORDER-1");
            oldSameKey.resolve({});
            await oldAction;
            if (!state.deliveryBusyActionKeys["delivery-assignment:ORDER-1"]) {
              throw new Error("old-date Delivery action cleared current-date same-key busy state");
            }
            newSameKey.resolve({});
            await currentAction;
            if (Object.keys(state.deliveryBusyActionKeys).length) {
              throw new Error("current-date Delivery action did not clear its busy key");
            }
            """
        )

    def test_concurrent_opshop_busy_keys_are_independent_and_token_guarded(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const first = deferred();
            const second = deferred();
            const oldSameKey = deferred();
            const newSameKey = deferred();
            const pickup = { pickup_task_id: "PICKUP-1", assigned_driver_id: "", driver_id: "" };
            const state = {
              isLoggedIn: true,
              workspaceRoute: "opshop/regular",
              activeWorkspace: "opshop",
              dispatchDate: "2026-06-24",
              opshopBoard: {
                opshop_pickups: [pickup],
                countryside_route_groups: [
                  { route_group_id: "ROUTE-1" },
                  { route_group_id: "ROUTE-2" },
                ],
              },
              opshopPickupCollections: [],
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: { "PICKUP-1": "DRIVER-1" },
              countrysideRouteGroupDrafts: {
                "ROUTE-1": { pickup_date: "2026-06-24", assigned_driver_id: "DRIVER-1", notes: "" },
                "ROUTE-2": { pickup_date: "2026-06-24", assigned_driver_id: "DRIVER-2", notes: "" },
              },
              deliveryBoard: { orders: [], assignments: [], driver_vehicle_assignments: [] },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: {},
            };
            let routeOneCall = 0;
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              assignOpShopWorkspaceCountrysideRouteGroup: async (routeGroupId, payload) => {
                if (routeGroupId === "ROUTE-2") {
                  return second.promise;
                }
                if (payload.dispatch_date === "2026-06-25") {
                  return newSameKey.promise;
                }
                routeOneCall += 1;
                return routeOneCall === 1 ? first.promise : oldSameKey.promise;
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const firstAction = actions.assignCountrysideRouteGroup("ROUTE-1");
            const secondAction = actions.assignCountrysideRouteGroup("ROUTE-2");
            if (!state.opshopBusyActionKeys["opshop-route-group:ROUTE-1"] ||
                !state.opshopBusyActionKeys["opshop-route-group:ROUTE-2"]) {
              throw new Error("OP SHOP did not track two busy actions independently");
            }
            first.resolve({});
            await firstAction;
            if (!state.opshopBusyActionKeys["opshop-route-group:ROUTE-2"]) {
              throw new Error("finishing first OP SHOP action cleared second busy key");
            }
            second.resolve({});
            await secondAction;
            if (Object.keys(state.opshopBusyActionKeys).length) {
              throw new Error("OP SHOP busy registry did not clear after both actions finished");
            }

            state.dispatchDate = "2026-06-24";
            state.countrysideRouteGroupDrafts = {
              "ROUTE-1": { pickup_date: "2026-06-24", assigned_driver_id: "DRIVER-1", notes: "" },
            };
            const oldAction = actions.assignCountrysideRouteGroup("ROUTE-1");
            await actions.updateDispatchDate("2026-06-25");
            state.countrysideRouteGroupDrafts = {
              "ROUTE-1": { pickup_date: "2026-06-25", assigned_driver_id: "DRIVER-NEW", notes: "" },
            };
            const currentAction = actions.assignCountrysideRouteGroup("ROUTE-1");
            oldSameKey.resolve({});
            await oldAction;
            if (!state.opshopBusyActionKeys["opshop-route-group:ROUTE-1"]) {
              throw new Error("old-date OP SHOP action cleared current-date same-key busy state");
            }
            newSameKey.resolve({});
            await currentAction;
            if (Object.keys(state.opshopBusyActionKeys).length) {
              throw new Error("current-date OP SHOP action did not clear its busy key");
            }
            """
        )

    def test_workspace_actions_handle_migration_conflict_and_normal_errors(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              workspaceMigrationStatus: null,
              isWorkspaceMigrationStatusLoading: false,
              workspaceMigrationStatusError: "",
              deliveryBoard: {
                orders: [{ order_id: "ORDER-1" }],
                assignments: [],
                driver_vehicle_assignments: [],
              },
              deliveryRunSheets: [],
              opshopBoard: { opshop_pickups: [], countryside_route_groups: [] },
              opshopPickupCollections: [],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {
                "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" },
              },
              deliveryVehicleDrafts: {},
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
              opshopBusyActionKeys: {},
              opshopAssignmentDrafts: {},
              countrysideRouteGroupDrafts: {},
            };
            let migrationChecks = 0;
            const migrationError = new Error("Workspace migration required");
            migrationError.status = 409;
            const validationError = new Error("Driver is required");
            validationError.status = 400;
            const api = {
              getWorkspaceMigrationStatus: async () => {
                migrationChecks += 1;
                return { delivery_ready: false, opshop_ready: true };
              },
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              getOpShopWorkspaceBoard: async () => state.opshopBoard,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
              assignDeliveryWorkspaceOrder: async () => { throw migrationError; },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });
            window.location.replace = (value) => {
              window.location.replaced = value;
            };
            await actions.applyDeliveryOrderAssignment("ORDER-1");
            if (state.workspaceRoute !== "home" || window.location.replaced !== "#home") {
              throw new Error("409 migration guard did not return home");
            }
            if (migrationChecks !== 1 || !state.workspaceMigrationStatus) {
              throw new Error("409 migration guard did not refresh migration status");
            }
            if (state.deliveryActionError) {
              throw new Error("409 left stale delivery action error");
            }

            state.workspaceRoute = "delivery/task-pool";
            state.activeWorkspace = "delivery";
            state.deliveryAssignmentDrafts = {
              "ORDER-1": { driver_id: "DRIVER-1", trip_no: "trip1" },
            };
            api.assignDeliveryWorkspaceOrder = async () => { throw validationError; };
            await actions.applyDeliveryOrderAssignment("ORDER-1");
            if (state.workspaceRoute !== "delivery/task-pool") {
              throw new Error("normal validation error redirected away from page");
            }
            if (state.deliveryActionError !== "Driver is required") {
              throw new Error("normal validation error was not surfaced");
            }
            """
        )

    def test_home_disables_only_migration_blocked_workspace_cards(self):
        self.assertIn("workspaceMigrationStatus", self.home_renderer)
        self.assertIn('readyField: "delivery_ready"', self.home_renderer)
        self.assertIn('readyField: "opshop_ready"', self.home_renderer)
        self.assertIn('card.setAttribute("aria-disabled", "true")', self.home_renderer)
        self.assertIn("Workspace migration is required", self.home_renderer)
        self.assertIn("legacy_generated_summary_count", self.home_renderer)

    def test_workspace_loaders_guard_against_stale_delivery_and_opshop_responses(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              const promise = new Promise((done) => { resolve = done; });
              return { promise, resolve };
            }

            const oldDelivery = deferred();
            const newDelivery = deferred();
            const oldOpShop = deferred();
            const newOpShop = deferred();
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/task-pool",
              dispatchDate: "2026-06-24",
              deliveryBoard: null,
              opshopBoard: null,
              deliveryRunSheets: [],
              opshopPickupCollections: [],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
            };
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: (date) =>
                date === "2026-06-24" ? oldDelivery.promise : newDelivery.promise,
              getOpShopWorkspaceBoard: (date) =>
                date === "2026-06-24" ? oldOpShop.promise : newOpShop.promise,
              listDeliveryRunSheets: async () => [],
              listOpShopPickupCollections: async () => [],
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const firstDelivery = actions.loadWorkspaceRoute("delivery/task-pool");
            state.dispatchDate = "2026-06-25";
            const secondDelivery = actions.loadWorkspaceRoute("delivery/task-pool");
            newDelivery.resolve({ marker: "new-delivery" });
            await secondDelivery;
            oldDelivery.resolve({ marker: "old-delivery" });
            await firstDelivery;
            if (state.deliveryBoard.marker !== "new-delivery") {
              throw new Error("stale Delivery response replaced current data");
            }
            if (state.isDeliveryWorkspaceLoading) {
              throw new Error("stale Delivery response changed current loading state");
            }

            state.workspaceRoute = "opshop/regular";
            state.dispatchDate = "2026-06-24";
            const firstOpShop = actions.loadWorkspaceRoute("opshop/regular");
            state.dispatchDate = "2026-06-25";
            const secondOpShop = actions.loadWorkspaceRoute("opshop/regular");
            newOpShop.resolve({ marker: "new-opshop" });
            await secondOpShop;
            oldOpShop.resolve({ marker: "old-opshop" });
            await firstOpShop;
            if (state.opshopBoard.marker !== "new-opshop") {
              throw new Error("stale OP SHOP response replaced current data");
            }
            if (state.isOpShopWorkspaceLoading) {
              throw new Error("stale OP SHOP response changed current loading state");
            }
            """
        )

    def test_history_loaders_handle_current_empty_and_error_states(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/history",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliverySavedHistoryDate: "2026-06-22",
              deliverySavedHistoryRunSheets: [{ run_sheet_id: "OLD" }],
              opshopSavedHistoryDate: "2026-06-22",
              opshopSavedHistoryCollections: [{ collection_id: "OLD" }],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
            };
            let deliveryMode = "empty";
            let opshopMode = "empty";
            const api = {
              listDeliveryRunSheetsByDeliveryDate: async () => {
                if (deliveryMode === "error") {
                  throw new Error("Delivery unavailable");
                }
                return [];
              },
              listOpShopPickupCollectionsByPickupDate: async () => {
                if (opshopMode === "error") {
                  throw new Error("OP SHOP unavailable");
                }
                return [];
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.loadWorkspaceRoute("delivery/history");
            if (state.deliverySavedHistoryRunSheets.length
                || state.isDeliveryWorkspaceLoading
                || state.deliveryWorkspaceError) {
              throw new Error("Delivery empty History state was not clean");
            }
            deliveryMode = "error";
            await actions.loadWorkspaceRoute("delivery/history");
            if (state.deliverySavedHistoryRunSheets.length
                || state.isDeliveryWorkspaceLoading
                || !state.deliveryWorkspaceError.includes("Unable to load Saved Run Sheet history. Delivery unavailable")) {
              throw new Error("Delivery current History error was not scoped");
            }

            state.workspaceRoute = "opshop/history";
            state.activeWorkspace = "opshop";
            await actions.loadWorkspaceRoute("opshop/history");
            if (state.opshopSavedHistoryCollections.length
                || state.isOpShopWorkspaceLoading
                || state.opshopWorkspaceError) {
              throw new Error("OP SHOP empty History state was not clean");
            }
            opshopMode = "error";
            await actions.loadWorkspaceRoute("opshop/history");
            if (state.opshopSavedHistoryCollections.length
                || state.isOpShopWorkspaceLoading
                || !state.opshopWorkspaceError.includes("Unable to load Saved Pickup Collection history. OP SHOP unavailable")) {
              throw new Error("OP SHOP current History error was not scoped");
            }
            """
        )
    def test_history_loaders_ignore_stale_date_responses_and_errors(self):
        self._run_workspace_actions_script(
            """
            function deferred() {
              let resolve;
              let reject;
              const promise = new Promise((done, fail) => {
                resolve = done;
                reject = fail;
              });
              return { promise, resolve, reject };
            }

            const oldDelivery = deferred();
            const newDelivery = deferred();
            const oldOpShop = deferred();
            const newOpShop = deferred();
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/history",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliverySavedHistoryDate: "2026-06-22",
              deliverySavedHistoryRunSheets: [],
              deliveryRunSheets: [{ run_sheet_id: "DRS-OPERATIONAL" }],
              opshopSavedHistoryDate: "2026-06-22",
              opshopSavedHistoryCollections: [],
              opshopPickupCollections: [{ collection_id: "OPC-OPERATIONAL" }],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
            };
            const api = {
              listDeliveryRunSheetsByDeliveryDate: (date) =>
                date === "2026-06-22" ? oldDelivery.promise : newDelivery.promise,
              listOpShopPickupCollectionsByPickupDate: (date) =>
                date === "2026-06-22" ? oldOpShop.promise : newOpShop.promise,
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            const oldDeliveryRequest = actions.loadWorkspaceRoute("delivery/history");
            const newDeliveryRequest = actions.updateDeliverySavedHistoryDate("2026-06-23");
            newDelivery.resolve([
              { run_sheet_id: "DRS-NEW", status: "SAVED", delivery_date: "2026-06-23" },
            ]);
            await newDeliveryRequest;
            const staleDeliveryFailure = new Error("stale Delivery migration conflict");
            staleDeliveryFailure.status = 409;
            oldDelivery.reject(staleDeliveryFailure);
            await oldDeliveryRequest;
            if (state.deliverySavedHistoryDate !== "2026-06-23"
                || state.deliverySavedHistoryRunSheets[0].run_sheet_id !== "DRS-NEW"
                || state.isDeliveryWorkspaceLoading
                || state.deliveryWorkspaceError) {
              throw new Error("stale Delivery history request changed current state");
            }

            state.workspaceRoute = "opshop/history";
            state.activeWorkspace = "opshop";
            const oldOpShopRequest = actions.loadWorkspaceRoute("opshop/history");
            const newOpShopRequest = actions.updateOpShopSavedHistoryDate("2026-06-23");
            newOpShop.resolve([
              { collection_id: "OPC-NEW", status: "SAVED", pickup_date: "2026-06-23" },
            ]);
            await newOpShopRequest;
            oldOpShop.reject(new Error("stale OP SHOP failure"));
            await oldOpShopRequest;
            if (state.opshopSavedHistoryDate !== "2026-06-23"
                || state.opshopSavedHistoryCollections[0].collection_id !== "OPC-NEW"
                || state.isOpShopWorkspaceLoading
                || state.opshopWorkspaceError) {
              throw new Error("stale OP SHOP history request changed current state");
            }
            """
        )

    def test_history_loaders_use_only_service_date_and_preserve_operational_state(self):
        self._run_workspace_actions_script(
            """
            const deliveryOperational = [{ run_sheet_id: "DRS-OPERATIONAL" }];
            const opshopOperational = [{ collection_id: "OPC-OPERATIONAL" }];
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/history",
              activeWorkspace: "delivery",
              dispatchDate: "2026-06-24",
              deliverySavedHistoryDate: "2026-06-22",
              deliverySavedHistoryRunSheets: [],
              deliveryRunSheets: deliveryOperational,
              opshopSavedHistoryDate: "2026-06-23",
              opshopSavedHistoryCollections: [],
              opshopPickupCollections: opshopOperational,
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              deliveryActionError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
              opshopActionError: "",
            };
            const deliveryCalls = [];
            const opshopCalls = [];
            let sharedCalls = 0;
            const api = {
              listDeliveryRunSheetsByDeliveryDate: async (date, status) => {
                deliveryCalls.push([date, status]);
                return [
                  { run_sheet_id: "DRS-Z", status: "SAVED", delivery_date: date, driver_name_snapshot: "Zulu", dispatch_date: "2026-06-01" },
                  { run_sheet_id: "DRS-G", status: "GENERATED", delivery_date: date, driver_name_snapshot: "Generated", dispatch_date: "2026-06-24" },
                  { run_sheet_id: "DRS-B", status: "SAVED", delivery_date: date, driver_name_snapshot: "Alpha", dispatch_date: "2026-06-24" },
                  { run_sheet_id: "DRS-A", status: "SAVED", delivery_date: date, driver_name_snapshot: "Alpha", dispatch_date: "2026-05-31" },
                ];
              },
              listOpShopPickupCollectionsByPickupDate: async (date, status) => {
                opshopCalls.push([date, status]);
                return [
                  { collection_id: "OPC-Z", status: "SAVED", pickup_date: date, driver_name_snapshot: "Zulu", dispatch_date: "2026-06-01" },
                  { collection_id: "OPC-G", status: "GENERATED", pickup_date: date, driver_name_snapshot: "Generated", dispatch_date: "2026-06-24" },
                  { collection_id: "OPC-B", status: "SAVED", pickup_date: date, driver_name_snapshot: "Alpha", dispatch_date: "2026-06-24" },
                  { collection_id: "OPC-A", status: "SAVED", pickup_date: date, driver_name_snapshot: "Alpha", dispatch_date: "2026-05-31" },
                ];
              },
              listDeliveryRunSheets: async () => {
                throw new Error("dispatch-scoped Delivery API called");
              },
              listOpShopPickupCollections: async () => {
                throw new Error("dispatch-scoped OP SHOP API called");
              },
              getSharedSpecifications: async () => {
                sharedCalls += 1;
                throw new Error("shared specifications unavailable");
              },
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.loadWorkspaceRoute("delivery/history");
            if (deliveryCalls.length !== 1 || deliveryCalls[0].join("|") !== "2026-06-22|SAVED") {
              throw new Error("Delivery history query was not service-date-only SAVED");
            }
            if (state.deliverySavedHistoryRunSheets.map((item) => item.run_sheet_id).join(",") !== "DRS-A,DRS-B,DRS-Z") {
              throw new Error("Delivery history was not filtered and stably sorted");
            }
            if (state.deliveryRunSheets !== deliveryOperational || state.dispatchDate !== "2026-06-24") {
              throw new Error("Delivery history polluted operational state");
            }

            state.workspaceRoute = "opshop/history";
            state.activeWorkspace = "opshop";
            await actions.loadWorkspaceRoute("opshop/history");
            if (opshopCalls.length !== 1 || opshopCalls[0].join("|") !== "2026-06-23|SAVED") {
              throw new Error("OP SHOP history query was not service-date-only SAVED");
            }
            if (state.opshopSavedHistoryCollections.map((item) => item.collection_id).join(",") !== "OPC-A,OPC-B,OPC-Z") {
              throw new Error("OP SHOP history was not filtered and stably sorted");
            }
            if (state.opshopPickupCollections !== opshopOperational || state.dispatchDate !== "2026-06-24") {
              throw new Error("OP SHOP history polluted operational state");
            }
            if (sharedCalls !== 0) {
              throw new Error("history unexpectedly requested shared specifications");
            }
            """
        )

    def _run_frontend_module_script(self, relative_path, body, setup=""):
        module_uri = (FRONTEND_ROOT / relative_path).as_uri()
        script = textwrap.dedent(
            f"""
            {setup}
            const module = await import({module_uri!r});
            {body}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def _run_delivery_attache_actions_script(self, body):
        module_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            const {{ createDeliveryAttacheActions }} = await import({module_uri!r});
            {body}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def _run_workspace_actions_script(self, body, setup=""):
        module_uri = (FRONTEND_ROOT / "js/actions/workspace-actions.js").as_uri()
        script = textwrap.dedent(
            f"""
            {setup}
            globalThis.window = {{
              location: {{ protocol: "http:", hash: "" }},
              history: {{
                pushState: (_state, _title, url) => {{
                  window.location.hash = String(url || "");
                }},
              }},
            }};
            const {{ createWorkspaceActions }} = await import({module_uri!r});
            {body}
            """
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    @staticmethod
    def _read(relative_path):
        return (FRONTEND_ROOT / relative_path).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
