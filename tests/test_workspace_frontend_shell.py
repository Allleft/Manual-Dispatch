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
        self.assertIn("applyDeliveryVehicleAssignment", self.delivery_renderer)
        self.assertIn("clearDeliveryVehicleAssignment", self.delivery_renderer)
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
        self.assertIn("state.deliveryTripSummaryDate = nextDate || state.dispatchDate", self.workspace_actions)
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
        apply_action = self.workspace_actions.split(
            "async function applyDeliveryVehicleAssignment", 1
        )[1].split("async function clearDeliveryVehicleAssignment", 1)[0]

        self.assertIn("formatDeliveryVehicleOptionLabel", vehicle_control)
        self.assertIn("getDeliveryVehicleConflictDriverNames", vehicle_control)
        self.assertIn("workspace-vehicle-select-invalid", vehicle_control)
        self.assertIn('select.setAttribute("aria-invalid"', vehicle_control)
        self.assertIn('select.setAttribute("aria-describedby"', vehicle_control)
        self.assertIn("workspace-vehicle-conflict-warning", vehicle_control)
        self.assertIn("hasVehicleConflict", vehicle_control)
        self.assertIn("!currentAssignment && !hasVehicleDraft", vehicle_control)
        self.assertNotIn("vehicleSummary", vehicle_control)
        self.assertIn("getDeliveryVehicleConflictDriverNames", apply_action)
        self.assertLess(
            apply_action.index("if (conflictDriverNames.length)"),
            apply_action.index("api.assignDeliveryWorkspaceVehicle"),
        )
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
            const find = (board, drafts, date, driver, vehicle) =>
              getDeliveryVehicleConflictDriverNames({{
                board,
                drafts,
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
            if (find(savedBoard, {{ "2026-06-29|B": "V2" }}, "2026-06-29", "A", "V1").join(",") !== "Driver B") {{
              throw new Error("unsaved replacement draft released a still-saved vehicle");
            }}

            const draftConflict = find(
              {{ drivers, driver_vehicle_assignments: [] }},
              {{ "2026-06-29|B": "V1" }},
              "2026-06-29",
              "A",
              "V1",
            );
            if (draftConflict.join(",") !== "Driver B") {{
              throw new Error("same-date unsaved draft conflict was not detected");
            }}
            if (find(savedBoard, {{ "2026-06-29|A": "V2" }}, "2026-06-29", "A", "V2").length) {{
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

    def test_duplicate_vehicle_guard_blocks_api_and_clear_removes_draft(self):
        self._run_workspace_actions_script(
            """
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
                driver_vehicle_assignments: [
                  { delivery_date: "2026-06-29", driver_id: "B", vehicle_id: "V1" },
                ],
              },
              deliveryRunSheets: [],
              deliveryActionError: "",
              deliveryBusyActionKeys: {},
              deliveryAssignmentDrafts: {},
              deliveryVehicleDrafts: { "2026-06-29|A": "V1" },
              opshopBusyActionKeys: {},
            };
            let assignCalls = 0;
            let clearCalls = 0;
            const api = {
              assignDeliveryWorkspaceVehicle: async () => { assignCalls += 1; },
              clearDeliveryWorkspaceVehicle: async () => { clearCalls += 1; },
              getDeliveryWorkspaceBoard: async () => state.deliveryBoard,
              listDeliveryRunSheets: async () => [],
            };
            const actions = createWorkspaceActions({
              state,
              renderWorkspace: () => {},
              api,
            });

            await actions.applyDeliveryVehicleAssignment("2026-06-29", "A");
            if (assignCalls !== 0) {
              throw new Error("duplicate vehicle assignment reached the scoped API");
            }
            if (!state.deliveryActionError.includes("Driver B")) {
              throw new Error("duplicate vehicle guard did not name the conflicting Driver");
            }

            await actions.clearDeliveryVehicleAssignment("2026-06-29", "A");
            if (clearCalls !== 0 || state.deliveryVehicleDrafts["2026-06-29|A"] !== undefined) {
              throw new Error("Clear Vehicle did not remove the unsaved conflicting draft locally");
            }

            actions.updateDeliveryVehicleDraft("2026-06-29", "A", "V2");
            await actions.applyDeliveryVehicleAssignment("2026-06-29", "A");
            if (assignCalls !== 1) {
              throw new Error("available vehicle did not reach the scoped API");
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
        self.assertIn("Ready to Generate", self.opshop_renderer)
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
