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
        self.delivery_vehicle_utils = self._read(
            "js/utils/delivery-vehicle-utils.js"
        )
        self.delivery_order_priority_utils = self._read(
            "js/utils/delivery-order-priority-utils.js"
        )
        self.opshop_renderer = self._read(
            "js/render/opshop-workspace-renderer.js"
        )
        self.opshop_date_group_renderer = self._read(
            "js/render/opshop-date-group-list-renderer.js"
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
            ("opshop/history", "opshop/collections"),
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
            "/api/manual-dispatch/opshop/board",
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
        ):
            self.assertIn(endpoint, self.api)
        self.assertIn("/export-excel", self.api)
        self.assertIn("requestBlobDownload", self.api)
        self.assertIn("Content-Disposition", self.api)
        self.assertIn("error.status = response.status", self.api)
        self.assertIn("error.detail = detail", self.api)

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
        self.assertIn("Filter active unassigned Orders", self.delivery_renderer)
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
            "deliveryTripSummaryDate",
            "opshopBoard",
            "opshopPickupCollections",
            "sharedSpecifications",
            "isDeliveryWorkspaceLoading",
            "deliveryWorkspaceError",
            "deliveryActionError",
            "deliveryBusyActionKeys",
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
            "BAGS",
            "CARTONS",
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
        self.assertIn(
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
        self.assertIn("Filter active unassigned Orders", panel_block)
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
        self.assertIn("state.deliveryTripSummaryDate = nextDate", self.workspace_actions)
        self.assertIn("state.deliveryTripSummaryDate = deliveryDate", self.workspace_actions)
        self.assertIn("Trip 1 orders", self.delivery_renderer)
        self.assertIn("Trip 2 orders", self.delivery_renderer)
        self.assertIn("Saved Run Sheet History", self.delivery_renderer)
        self.assertIn("Export Daily Run Sheet", self.delivery_renderer)
        self.assertIn("View Run Sheet details / preview", self.delivery_renderer)
        self.assertIn("Vehicle", self.delivery_renderer)
        self.assertIn('label: "Select vehicle"', self.delivery_renderer)
        self.assertIn("formatDeliveryVehicleOptionLabel", self.delivery_renderer)
        self.assertNotIn("Selected vehicle:", self.delivery_renderer)
        self.assertNotIn("Capacity:", self.delivery_renderer)
        self.assertNotIn("workspace-vehicle-capacity-summary", self.delivery_renderer)
        action_block = self.delivery_renderer.split(
            "function createDeliveryOrderActions", 1
        )[1].split("function createDeliveryOrderForm", 1)[0]
        self.assertLess(action_block.index('"Close"'), action_block.index('"Edit Order"'))
        self.assertLess(action_block.index('"Edit Order"'), action_block.index('"Cancel Order"'))
        self.assertIn("workspace-modal-action-danger", action_block)
        self.assertIn("createWorkspaceModal", self.delivery_renderer)
        self.assertIn("trapModalFocus", self.delivery_renderer)

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
              deliveryAssignmentDrafts: {}, deliveryVehicleDrafts: {},
              deliveryVehicleClaims: {}, deliveryVehicleClaimSequence: 0,
              deliveryVehicleErrors: {}, deliveryVehiclePendingKeys: {},
              deliveryBusyActionKeys: {}, deliveryActionError: "",
            };
            const api = {
              assignDeliveryWorkspaceVehicle: async () => vehicleWrite.promise,
              getDeliveryWorkspaceBoard: async () => board(),
              listDeliveryRunSheets: async () => [],
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
            if (state.deliveryBoard.driver_vehicle_assignments[0]?.vehicle_id !== "V1") {
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
            if (state.deliveryBoard.assignments[0].trip_no !== "trip2") {
              throw new Error("Move did not update the returned board in place");
            }
            await actions.unassignDeliveryOrder("ORDER-1");
            if (state.deliveryBoard.assignments.length) {
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
            const expectedKeys = "dispatch_date,driver_id,order_id,trip_no";
            for (const payload of assignedPayloads) {
              if (Object.keys(payload).sort().join(",") !== expectedKeys) {
                throw new Error("Delivery assignment payload contains unexpected fields");
              }
            }
            if (assignedPayloads[0].dispatch_date !== "2026-06-24" ||
                assignedPayloads[0].order_id !== "ORDER-1" ||
                assignedPayloads[0].driver_id !== "D001" ||
                assignedPayloads[0].trip_no !== "trip1") {
              throw new Error("Add Order payload was not scoped correctly");
            }
            if (assignedPayloads[1].order_id !== "ORDER-2" ||
                assignedPayloads[1].trip_no !== "trip2") {
              throw new Error("Move Order payload was not scoped correctly");
            }

            await actions.generateDeliveryRunSheet({
              delivery_date: "2026-06-22",
              driver_id: "D001",
            });
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

    def test_stale_delivery_generate_responses_do_not_navigate(self):
        self._run_workspace_actions_script(
            """
            async function runScenario(mutator) {
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
              const pending = actions.generateDeliveryRunSheet({
                delivery_date: "2026-06-24",
                driver_id: "D001",
              });
              mutator(state);
              resolveGenerate();
              await pending;
              if (navigatedRoutes.length !== 0) {
                throw new Error("Stale Generate response navigated unexpectedly");
              }
            }

            await runScenario((state) => { state.dispatchDate = "2026-06-25"; });
            await runScenario((state) => { state.workspaceRoute = "delivery/task-pool"; });
            await runScenario((state) => {
              state.workspaceRoute = "opshop/regular";
              state.activeWorkspace = "opshop";
            });
            """
        )

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

    def test_opshop_workspace_uses_three_stage_workflow_and_internal_task_pool_tabs(self):
        self.assertIn('{ route: "opshop/task-pool/regular", label: "Task Pool" }', self.opshop_renderer)
        self.assertIn('{ route: "opshop/trip-summary", label: "Trip Summary" }', self.opshop_renderer)
        self.assertIn('{ route: "opshop/collections", label: "Pickup Collections" }', self.opshop_renderer)
        top_tabs = self.opshop_renderer.split("const OPSHOP_TABS", 1)[1].split("];", 1)[0]
        self.assertNotIn("Templates", top_tabs)
        self.assertNotIn("Saved History", top_tabs)
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
        )[1].split("function updateOpShopTripSummaryDate", 1)[0]
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
        self.assertIn("opshopTripSummaryDate: DEFAULT_DISPATCH_DATE", self.state)
        self.assertIn("function updateOpShopTripSummaryDate(nextDate)", self.workspace_actions)

    def test_opshop_collections_merge_generated_and_saved_history(self):
        self.assertIn("Generated Pickup Collections", self.opshop_renderer)
        self.assertIn("Saved Pickup Collections", self.opshop_renderer)
        self.assertIn('collection.status === "GENERATED"', self.opshop_renderer)
        self.assertIn('collection.status === "SAVED"', self.opshop_renderer)
        self.assertIn("saveOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("cancelOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("exportOpShopPickupCollection", self.opshop_renderer)
        self.assertIn("Saved by", self.opshop_renderer)
        self.assertIn("pickupCategoryCounts(collection.pickups || [])", self.opshop_renderer)
        self.assertIn(
            'route === "opshop/collections" || route === "opshop/trip-summary"',
            self.workspace_actions,
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
              deliveryBusyActionKeys: state.deliveryBusyActionKeys,
              opshopBusyActionKeys: state.opshopBusyActionKeys,
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

    def test_history_loaders_do_not_depend_on_shared_specifications(self):
        self._run_workspace_actions_script(
            """
            const state = {
              isLoggedIn: true,
              workspaceRoute: "delivery/history",
              dispatchDate: "2026-06-24",
              deliveryRunSheets: [],
              opshopPickupCollections: [],
              isDeliveryWorkspaceLoading: false,
              deliveryWorkspaceError: "",
              isOpShopWorkspaceLoading: false,
              opshopWorkspaceError: "",
            };
            let sharedCalls = 0;
            const api = {
              getWorkspaceMigrationStatus: async () => ({}),
              getDeliveryWorkspaceBoard: async () => ({}),
              getOpShopWorkspaceBoard: async () => ({}),
              listDeliveryRunSheets: async () => [{ run_sheet_id: "DRS-1" }],
              listOpShopPickupCollections: async () => [{ collection_id: "OPC-1" }],
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
            if (state.deliveryRunSheets[0].run_sheet_id !== "DRS-1") {
              throw new Error("Delivery history did not load independently");
            }
            state.workspaceRoute = "opshop/history";
            await actions.loadWorkspaceRoute("opshop/history");
            if (state.opshopPickupCollections[0].collection_id !== "OPC-1") {
              throw new Error("OP SHOP history did not load independently");
            }
            if (sharedCalls !== 0) {
              throw new Error("history unexpectedly requested shared specifications");
            }
            """
        )

    def _run_workspace_actions_script(self, body):
        module_uri = (FRONTEND_ROOT / "js/actions/workspace-actions.js").as_uri()
        script = textwrap.dedent(
            f"""
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
