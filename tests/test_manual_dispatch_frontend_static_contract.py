import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class ManualDispatchFrontendStaticContractTest(unittest.TestCase):
    def test_frontend_entry_script_remains_app_module(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('<script type="module" src="app.js"></script>', index_html)
        script_sources = re.findall(r"<script[^>]+src=\"([^\"]+)\"", index_html)
        self.assertEqual(["app.js"], script_sources)

    def test_board_views_are_hash_routed_single_page_workflow(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        app_state = (
            FRONTEND_ROOT / "js" / "state" / "app-state.js"
        ).read_text(encoding="utf-8")
        nav_renderer = (
            FRONTEND_ROOT / "js" / "render" / "board-view-navigation-renderer.js"
        ).read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")
        final_summary_actions = (
            FRONTEND_ROOT / "js" / "actions" / "final-summary-actions.js"
        ).read_text(encoding="utf-8")

        self.assertIn('id="board-view-nav"', index_html)
        self.assertIn('id="task-pool-view"', index_html)
        self.assertIn('id="trip-summary-view"', index_html)
        self.assertIn('id="final-summary-view"', index_html)
        self.assertIn('id="final-summary-delivery-date"', index_html)
        self.assertIn('id="task-pool-list"', index_html)
        self.assertIn('id="driver-summary-list"', index_html)
        self.assertIn('id="final-trip-summary-list"', index_html)
        self.assertIn('id="save-final-summary-button"', index_html)
        self.assertIn('id="history-date-select"', index_html)
        self.assertIn('id="load-history-button"', index_html)
        self.assertIn('id="final-summary-history-list"', index_html)
        self.assertIn('activeBoardView: "task-pool"', app_state)
        self.assertIn('const BOARD_VIEWS = new Set(["task-pool", "trip-summary", "final-summary"])', app_js)
        self.assertIn("function getBoardViewFromHash()", app_js)
        self.assertIn("function setActiveBoardView(view)", app_js)
        self.assertIn('window.addEventListener("hashchange"', app_js)
        self.assertIn("renderBoardViewNavigation()", app_js)
        self.assertIn("renderVisibleBoardView()", app_js)
        render_board = app_js.split("function renderBoard()", 1)[1].split("const authActions", 1)[0]
        self.assertIn("renderBoardViewNavigation();", render_board)
        self.assertIn("renderVisibleBoardView();", render_board)
        self.assertNotIn("renderTaskPool();\n  renderTaskPoolFilters();\n  renderDriverSummary();", render_board)
        self.assertIn("Task Pool", nav_renderer)
        self.assertIn("Trip Summary", nav_renderer)
        self.assertIn("Final Trip Summary", nav_renderer)
        self.assertIn("aria-current", nav_renderer)
        self.assertIn("aria-pressed", nav_renderer)
        self.assertIn(".board-view {", styles)
        self.assertIn("display: none;", styles)
        self.assertIn(".board-view-active", styles)
        self.assertIn(".board-view-tab-active", styles)
        self.assertIn("setActiveBoardView = () => {}", final_summary_actions)
        self.assertIn('setActiveBoardView("final-summary")', final_summary_actions)
        self.assertIn('setActiveBoardView("trip-summary")', final_summary_actions)
        self.assertIn("onDeliveryDateChange", final_summary_renderer)
        self.assertIn('document.querySelector("#final-summary-delivery-date")', final_summary_renderer)
        self.assertIn("state.driverSummaryDeliveryDate = deliveryDate", app_js)
        self.assertIn(".final-summary-date-controls label", styles)

    def test_driver_summary_delivery_date_control_is_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="driver-summary-delivery-date"', index_html)
        self.assertIn('type="date"', index_html)

    def test_task_pool_delivery_date_filter_controls_are_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn('id="task-pool-delivery-date-filter"', index_html)
        self.assertIn('deliveryDateInput.id = "task-pool-delivery-date-filter"', task_pool_renderer)
        self.assertIn('clearDeliveryDateButton.id = "clear-task-pool-delivery-date-filter"', task_pool_renderer)
        self.assertIn('clearDeliveryDateButton.textContent = "All delivery dates"', task_pool_renderer)

    def test_order_renderers_show_delivery_date_and_edit_form_is_not_read_only(self):
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        trip_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8")
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Delivery Date:", task_pool_renderer)
        self.assertIn("assigned-delivery-date", trip_summary_renderer)
        self.assertIn('createField("Delivery Date", "delivery_date"', order_modal_renderer)
        self.assertNotIn("Delivery Date (read-only)", order_modal_renderer)

    def test_order_details_reuses_form_grid_in_read_only_mode(self):
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("function createOrderReadOnlyLayout(formState)", order_modal_renderer)
        self.assertIn('layout.className = "order-form order-readonly-form"', order_modal_renderer)
        self.assertIn('layout.append(createOrderFormGrid(formState, { mode: "view" }))', order_modal_renderer)
        self.assertIn("input.disabled = true", order_modal_renderer)
        self.assertIn("input.readOnly = true", order_modal_renderer)
        self.assertIn("select.disabled = true", order_modal_renderer)
        self.assertIn('mode: "edit"', order_modal_renderer)

    def test_order_details_and_edit_share_core_field_order(self):
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")

        field_labels = [
            "Invoice #",
            "Company Name",
            "Phone",
            "Delivery Address",
            "Suburb",
            "Postcode",
            "Delivery Date",
            "Zone",
            "Urgency",
            "Preferred Driver",
            "Pallet Quantity",
            "Loose Bags Quantity",
            "Start Time",
            "End Time",
            "Note",
        ]
        shared_grid_source = order_modal_renderer.split("function createOrderFormGrid", 1)[1]
        field_positions = [shared_grid_source.index(f'"{label}"') for label in field_labels]
        self.assertEqual(sorted(field_positions), field_positions)

    def test_attache_invoice_pdf_import_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        app_state = (
            FRONTEND_ROOT / "js" / "state" / "app-state.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "attache-invoice-import-actions.js"
        ).read_text(encoding="utf-8")
        renderer = (
            FRONTEND_ROOT / "js" / "render" / "attache-invoice-import-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Import Attache Invoices", task_pool_renderer)
        self.assertIn("onOpenAttacheInvoiceImport", task_pool_renderer)
        self.assertIn("createAttacheInvoiceImportActions", app_js)
        self.assertIn("renderAttacheInvoiceImportModal", app_js)
        self.assertIn("isAttacheInvoiceImportOpen", app_state)
        self.assertIn("/api/manual-dispatch/orders/import-attache-pdf-preview", api_module)
        self.assertIn("/api/manual-dispatch/orders/import-attache-pdf-commit", api_module)
        self.assertIn("new FormData()", api_module)
        self.assertIn("apiPreviewAttacheInvoicePdfImport", actions)
        self.assertIn("apiCommitAttacheInvoicePdfImport", actions)
        update_files_body = actions.split("function updateFiles(files)", 1)[1].split(
            "async function previewImport",
            1,
        )[0]
        self.assertIn("state.attacheInvoiceImportFiles = Array.from(files || [])", update_files_body)
        self.assertIn("renderAttacheInvoiceImportModal();", update_files_body)
        self.assertIn("Preview Import", renderer)
        self.assertIn("Confirm Import", renderer)
        self.assertIn('fileInput.accept = "application/pdf,.pdf"', renderer)
        self.assertIn("createSelectedFileFeedback", renderer)
        self.assertIn("1 file selected:", renderer)
        self.assertIn("files selected", renderer)
        self.assertIn('feedback.setAttribute("aria-live", "polite")', renderer)
        self.assertIn("row.is_duplicate", renderer)

    def test_phase16_product_detail_controls_are_present(self):
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn('productDetailButton.textContent = "Product Detail"', order_modal_renderer)
        self.assertIn('title.textContent = "Product Details"', order_modal_renderer)
        self.assertIn('addButton.textContent = "Add Product Line"', order_modal_renderer)
        self.assertIn('"Product Details"', final_summary_renderer)

    def test_phase18_final_summary_distance_display_is_present(self):
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")
        final_summary_actions = (
            FRONTEND_ROOT / "js" / "actions" / "final-summary-actions.js"
        ).read_text(encoding="utf-8")

        self.assertIn('"Estimated Distance From Warehouse (km)"', final_summary_renderer)
        self.assertIn("function formatEstimatedDistance(order)", final_summary_renderer)
        self.assertIn("function sortFinalSummaryOrders(orders)", final_summary_actions)

    def test_phase5_opshop_pickups_render_above_delivery_orders(self):
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("OP SHOP PICKUP", task_pool_renderer)
        self.assertIn("DELIVERY ORDERS", task_pool_renderer)
        self.assertLess(
            task_pool_renderer.index("OP SHOP PICKUP"),
            task_pool_renderer.index("DELIVERY ORDERS"),
        )
        self.assertIn("No OP SHOP PICKUP tasks for this Regular pickup week.", task_pool_renderer)
        self.assertIn("Regular OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Oncall OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Countryside OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("No Oncall OP SHOP pickups added.", task_pool_renderer)
        self.assertIn("onOpenOncallOpShopPickupList", task_pool_renderer)
        self.assertIn("opshop-pickup-list-summary-card", task_pool_renderer)
        self.assertIn("section.append(actions, list)", task_pool_renderer)
        self.assertIn(".opshop-summary-grid .opshop-pickup-list-summary-card", styles)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", styles)
        self.assertIn(".opshop-summary-grid {\n    grid-template-columns: minmax(0, 1fr);", styles)
        self.assertNotIn(
            ".opshop-summary-grid .opshop-pickup-list-summary-card {\n  grid-column: 1 / -1;",
            styles,
        )
        self.assertIn("max-width: none", styles)
        self.assertIn("Open List", task_pool_renderer)
        self.assertIn("state.scheduledOpShopPickups", task_pool_renderer)
        self.assertNotIn("function createOpShopPickupCard", task_pool_renderer)
        self.assertNotIn('taskType: "OPSHOP_PICKUP"', task_pool_renderer)
        self.assertNotIn('textContent = "Details"', task_pool_renderer)

    def test_phase5_opshop_pickup_detail_modal_is_read_only(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        board_state_sync = (
            FRONTEND_ROOT / "js" / "state" / "board-state-sync.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-pickup-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("opshopPickups: payload.opshop_pickups || []", board_state_sync)
        self.assertIn("assignedOpShopPickups: payload.assigned_opshop_pickups || []", board_state_sync)
        self.assertIn("scheduledOpShopPickups: payload.scheduled_opshop_pickups || []", board_state_sync)
        self.assertIn("oncallOpShopPickups: payload.oncall_opshop_pickups || []", board_state_sync)
        self.assertIn("countrysideOpShopPickups: payload.countryside_opshop_pickups || []", board_state_sync)
        self.assertIn("countrysideRouteGroups: payload.countryside_route_groups || []", board_state_sync)
        self.assertIn("finalizedDriverDeliveryDates: payload.finalized_driver_delivery_dates || []", board_state_sync)
        self.assertIn("opshopRegularListWindowStart: payload.opshop_regular_list_window_start || \"\"", board_state_sync)
        self.assertIn("opshopRegularListWindowEnd: payload.opshop_regular_list_window_end || \"\"", board_state_sync)
        self.assertIn("state.opshopPickups = board.opshopPickups", board_state_sync)
        self.assertIn("state.assignedOpShopPickups = board.assignedOpShopPickups", board_state_sync)
        self.assertIn("state.scheduledOpShopPickups = board.scheduledOpShopPickups", board_state_sync)
        self.assertIn("state.oncallOpShopPickups = board.oncallOpShopPickups", board_state_sync)
        self.assertIn("state.countrysideOpShopPickups = board.countrysideOpShopPickups", board_state_sync)
        self.assertIn("state.countrysideRouteGroups = board.countrysideRouteGroups", board_state_sync)
        self.assertIn("state.finalizedDriverDeliveryDates = board.finalizedDriverDeliveryDates", board_state_sync)
        self.assertIn(
            "assignment.delivery_date || assignment.dispatch_date || payload.dispatch_date || state.dispatchDate",
            board_state_sync,
        )
        self.assertIn("syncBoardResponse(payload, () => assignmentActions.cleanupPendingSelections())", app_js)
        self.assertIn("onOpenOpShopPickupDetail: openOpShopPickupDetail", app_js)
        self.assertIn("renderOpShopPickupDetailPopup", app_js)
        self.assertIn('closeButton.textContent = "Close"', modal_renderer)
        self.assertIn('backdrop.addEventListener("click", onCloseOpShopPickupDetail)', modal_renderer)
        self.assertIn('event.key === "Escape"', modal_renderer)
        self.assertIn('modal.addEventListener("click", (event) => event.stopPropagation())', modal_renderer)
        for label in [
            "Address / Access",
            "Street Address",
            "Access Type",
            "Key Required",
            "Trailer Restriction",
            "Contact",
            "Primary Contact",
            "Primary Phone",
            "Secondary Contact",
            "Secondary Phone",
            "Call Before Arrival",
            "Call Timing",
            "Notes",
            "Status Notes",
            "Task Notes",
        ]:
            self.assertIn(label, modal_renderer)
        self.assertNotIn("api", modal_renderer.lower())
        self.assertNotIn("fetch(", modal_renderer)

    def test_phase7_opshop_assignment_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        assignment_actions = (
            FRONTEND_ROOT / "js" / "actions" / "assignment-actions.js"
        ).read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        trip_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8")
        selectors = (FRONTEND_ROOT / "js" / "state" / "selectors.js").read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")
        assigned_opshop_renderer = trip_summary_renderer.split(
            "function createAssignedOpShopPickupTask",
            1,
        )[1]

        self.assertIn("handleAssignTask", assignment_actions)
        self.assertIn("getTaskKey(taskType, taskId)", assignment_actions)
        self.assertIn("task_type: taskType", assignment_actions)
        self.assertIn("handleAssignTask(\"ORDER\"", assignment_actions)
        self.assertIn("const taskIds = Array.isArray(taskId) ? taskId : [taskId];", assignment_actions)
        self.assertIn("taskIds.map((currentTaskId) =>", assignment_actions)
        self.assertIn("updatePendingSelection(taskType, currentTaskId", assignment_actions)
        self.assertNotIn('taskType: "OPSHOP_PICKUP"', task_pool_renderer)
        self.assertIn("assigned-opshop-task", trip_summary_renderer)
        self.assertIn("assigned-opshop-name", trip_summary_renderer)
        self.assertIn("assigned-opshop-suburb", trip_summary_renderer)
        self.assertIn(".assigned-opshop-name", styles)
        self.assertIn(".assigned-opshop-suburb", styles)
        self.assertIn(".assigned-opshop-route-group", styles)
        self.assertIn(".assigned-opshop-route-group-header", styles)
        self.assertIn(".assigned-opshop-route-group-card-list", styles)
        self.assertIn("getAssignedOpShopPickupsForDriver", trip_summary_renderer)
        self.assertIn("const hasAssignedTasks = assignedOrders.length > 0 || assignedOpShopPickups.length > 0", trip_summary_renderer)
        self.assertIn("isDriverDeliveryDateFinalized", trip_summary_renderer)
        self.assertIn(
            "state.isSaving || state.isLoading || hasLockedFinalSummary || hasSavedFinalSummary",
            trip_summary_renderer,
        )
        self.assertIn("Final Trip Summary has been saved for this driver and delivery date.", trip_summary_renderer)
        self.assertIn("if (hasAssignedTasks && !hasLockedFinalSummary && !hasSavedFinalSummary)", trip_summary_renderer)
        self.assertIn("if (!hasAssignedTasks && !hasSavedFinalSummary)", trip_summary_renderer)
        self.assertNotIn("emptyState.textContent = hasSavedFinalSummary", trip_summary_renderer)
        self.assertIn("pickup.pickup_date === state.driverSummaryDeliveryDate", selectors)
        self.assertIn("getOrderAssignmentsForDriverTrip", selectors)
        self.assertIn("createOpShopPickupGroup", trip_summary_renderer)
        self.assertIn("createOpShopPickupEntries", trip_summary_renderer)
        self.assertIn("createAssignedCountrysideRouteGroup", trip_summary_renderer)
        self.assertIn("isCountrysideRouteGroupPickup", trip_summary_renderer)
        self.assertIn('pickup.pickup_category === "COUNTRYSIDE"', trip_summary_renderer)
        self.assertIn("pickup.route_group_id", trip_summary_renderer)
        self.assertIn("Countryside Route Group:", trip_summary_renderer)
        self.assertIn("Unassign Route Group", trip_summary_renderer)
        self.assertIn("group.assignments.map((assignment) => assignment.task_id)", trip_summary_renderer)
        self.assertIn("showUnassignButton: false", trip_summary_renderer)
        self.assertIn("OP SHOP PICKUPS", trip_summary_renderer)
        self.assertIn("assigned-opshop-pickups-section", trip_summary_renderer)
        self.assertIn('assignment.task_type === "ORDER"', selectors)
        self.assertIn('assignment.task_type === "OPSHOP_PICKUP"', trip_summary_renderer)
        self.assertIn("onOpenOpShopPickupDetail(pickup.pickup_task_id)", trip_summary_renderer)
        self.assertIn("onUnassign(assignment.task_type, assignment.task_id)", trip_summary_renderer)
        self.assertNotIn("appear in a separate Final Trip Summary section", trip_summary_renderer)
        self.assertIn(
            "name.textContent = formatOptional(pickup.opshop_name || pickup.pickup_task_id)",
            assigned_opshop_renderer,
        )
        self.assertIn("suburb.textContent = formatOptional(pickup.suburb)", assigned_opshop_renderer)
        self.assertNotIn("Pickup Date:", assigned_opshop_renderer)
        self.assertNotIn("Run:", assigned_opshop_renderer)
        self.assertNotIn("Frequency:", assigned_opshop_renderer)
        self.assertNotIn("Phone:", assigned_opshop_renderer)
        self.assertNotIn("pickup.opshop_name)", assigned_opshop_renderer)
        self.assertIn("OP SHOP PICKUPS", final_summary_renderer)
        self.assertIn("createOpShopPickupSection", final_summary_renderer)
        self.assertIn("onCancelGeneratedFinalSummary", final_summary_renderer)
        self.assertIn("Cancel Generated Summary", final_summary_renderer)
        self.assertIn('summary.status === "GENERATED"', final_summary_renderer)
        self.assertIn("onReExportFinalSummary", final_summary_renderer)
        self.assertIn("Re-export", final_summary_renderer)
        self.assertIn('summary.status === "SAVED"', final_summary_renderer)
        self.assertIn("state.isReExportingFinalSummaryId", final_summary_renderer)
        self.assertIn('"Category"', final_summary_renderer)
        self.assertIn('"Route Group"', final_summary_renderer)
        self.assertIn("formatOpShopPickupCategory", final_summary_renderer)
        self.assertIn("pickup.route_group_name", final_summary_renderer)
        final_summary_opshop_section = final_summary_renderer.split(
            "function createOpShopPickupSection",
            1,
        )[1].split("function formatOpShopPickupCategory", 1)[0]
        self.assertNotIn("innerHTML", final_summary_opshop_section)

        final_summary_actions = (
            FRONTEND_ROOT / "js" / "actions" / "final-summary-actions.js"
        ).read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        board_state_sync = (
            FRONTEND_ROOT / "js" / "state" / "board-state-sync.js"
        ).read_text(encoding="utf-8")
        download_utils = (
            FRONTEND_ROOT / "js" / "utils" / "download-utils.js"
        ).read_text(encoding="utf-8")
        self.assertIn("apiCreateGeneratedFinalSummary", api_module)
        self.assertIn("apiSaveGeneratedFinalSummary", api_module)
        self.assertIn("apiCancelGeneratedFinalSummary", api_module)
        self.assertIn("apiExportFinalSummaryExcel", api_module)
        self.assertIn("/api/manual-dispatch/final-summaries/generated", api_module)
        self.assertIn("/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/save", api_module)
        self.assertIn("/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/cancel-generated", api_module)
        self.assertIn("/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/export-excel", api_module)
        self.assertIn("getAssignedOpShopPickupsForDriver", final_summary_actions)
        self.assertIn("apiCreateGeneratedFinalSummary", final_summary_actions)
        self.assertIn("apiSaveGeneratedFinalSummary", final_summary_actions)
        self.assertIn("apiCancelGeneratedFinalSummary", final_summary_actions)
        self.assertIn("apiExportFinalSummaryExcel", final_summary_actions)
        self.assertIn("handleReExportFinalSummary", final_summary_actions)
        self.assertIn("Only saved Final Trip Summaries can be exported.", final_summary_actions)
        self.assertIn("downloadExcelResponse(response, `final-trip-summary-${summary.summary_id}.xlsx`)", final_summary_actions)
        self.assertIn("assignedOrders.length === 0 && assignedOpShopPickups.length === 0", final_summary_actions)
        self.assertIn("Assign at least one Order or OP SHOP pickup", final_summary_actions)
        self.assertIn("opshop_pickups: opshopPickups", final_summary_actions)
        self.assertIn("opshop_pickups: normalized.opshop_pickups.map", final_summary_actions)
        self.assertIn("pickup_category: pickup.pickup_category || pickup.pickup_category_snapshot || \"\"", final_summary_actions)
        self.assertIn("route_group_name: pickup.route_group_name || pickup.route_group_name_snapshot || \"\"", final_summary_actions)
        self.assertIn("pickup_category_snapshot: pickup.pickup_category", final_summary_actions)
        self.assertIn("route_group_name_snapshot: pickup.route_group_name", final_summary_actions)
        self.assertIn('state.generatedTaskKeys.add(getTaskKey("OPSHOP_PICKUP", pickup.pickup_task_id))', final_summary_actions)
        self.assertIn("const generatedOrderTasks = generatedSummary.trips.flatMap((trip) => trip.orders)", final_summary_actions)
        self.assertIn("generatedOrderTasks.map((order) =>", final_summary_actions)
        self.assertIn("summary.status === \"GENERATED\"", final_summary_actions)
        self.assertIn("handleCancelGeneratedFinalSummary", final_summary_actions)
        self.assertIn("Cancel this generated Final Trip Summary and return its tasks to editable Trip Summary?", final_summary_actions)
        self.assertNotIn("const generatedTasks = [", final_summary_actions)
        generate_summary_section = final_summary_actions.split(
            "async function handleGenerateDriverSummary",
            1,
        )[1].split("function getFinalSummarySavePayload", 1)[0]
        self.assertNotIn("snapshot.opshop_pickups.map((pickup) => ({", generate_summary_section)
        self.assertNotIn("task_id: pickup.pickup_task_id", generate_summary_section)
        self.assertIn('import { downloadExcelResponse } from "../utils/download-utils.js"', final_summary_actions)
        self.assertIn("getExportFilename", download_utils)
        self.assertIn("generatedFinalTripSummaries: payload.generated_final_trip_summaries || []", board_state_sync)
        self.assertIn("function applyGeneratedFinalSummaries", board_state_sync)
        self.assertIn("state.generatedTaskKeys.add(`OPSHOP_PICKUP:${pickupTaskId}`)", board_state_sync)
        self.assertIn('!isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', selectors)
        self.assertIn("export function isDriverDeliveryDateFinalized", selectors)

    def test_phase8_opshop_pickup_list_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-pickup-actions.js"
        ).read_text(encoding="utf-8")
        app_state = (
            FRONTEND_ROOT / "js" / "state" / "app-state.js"
        ).read_text(encoding="utf-8")
        download_utils = (
            FRONTEND_ROOT / "js" / "utils" / "download-utils.js"
        ).read_text(encoding="utf-8")
        date_group_utils = (
            FRONTEND_ROOT / "js" / "utils" / "opshop-date-group-utils.js"
        ).read_text(encoding="utf-8")
        scroll_utils = (
            FRONTEND_ROOT / "js" / "utils" / "scroll-utils.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("apiListOpShopPickupSchedules", api_module)
        self.assertIn("apiCreateOpShopPickup", api_module)
        self.assertIn("apiUpdateOpShopPickup", api_module)
        self.assertIn("apiDeleteOpShopPickup", api_module)
        self.assertIn("apiApplyWeeklyOpShopPickupAssignments", api_module)
        self.assertIn("apiExportOpShopPickupRunSheetExcel", api_module)
        self.assertIn("/opshop-pickups/export-excel", api_module)
        self.assertIn("createOpShopPickupActions", actions)
        self.assertIn("openOpShopPickupList", actions)
        self.assertIn("apiApplyWeeklyOpShopPickupAssignments", actions)
        self.assertIn('!isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', actions)
        self.assertIn("state.isOpShopPickupSaving || state.isOpShopPickupListLoading", actions)
        self.assertNotIn("apiExportOpShopPickupRunSheetExcel", actions)
        self.assertNotIn("exportOpShopRunSheet", actions)
        self.assertNotIn('import { downloadExcelResponse } from "../utils/download-utils.js"', actions)
        self.assertNotIn("isOpShopRunSheetExporting", app_state)
        self.assertIn("URL.createObjectURL(blob)", download_utils)
        self.assertIn("URL.revokeObjectURL(downloadUrl)", download_utils)
        self.assertIn("updateAssignedDriverSelection", actions)
        self.assertIn("handleCreatePickupTask", actions)
        self.assertIn("handleUpdatePickupTask", actions)
        self.assertIn("handleDeletePickupTask", actions)
        self.assertIn("function shouldUseDefaultDriverForPickup(pickup)", actions)
        self.assertIn("function canUseDefaultDriverForPickup(pickup)", actions)
        self.assertIn(
            "function initializeAssignedDriverSelections({ preserveExisting = false } = {})",
            actions,
        )
        self.assertIn(
            "preserveExisting ? state.opshopPickupAssignedDriverSelections || {} : {}",
            actions,
        )
        self.assertIn(
            "initializeAssignedDriverSelections({ preserveExisting: false })",
            actions,
        )
        self.assertIn(
            "initializeAssignedDriverSelections({ preserveExisting: true })",
            actions,
        )
        self.assertIn("Object.prototype.hasOwnProperty.call(", actions)
        self.assertIn("existingSelections,", actions)
        self.assertIn("selections[pickup.pickup_task_id] = existingSelections[pickup.pickup_task_id]", actions)
        self.assertIn("state.drivers.some", actions)
        self.assertIn("state.finalizedDriverDeliveryDates.some", actions)
        self.assertIn("pickup.default_driver_id", actions)
        self.assertIn("pickup.pickup_date >= state.dispatchDate", actions)
        self.assertIn(
            "canUseDefaultDriverForPickup(pickup) ? pickup.default_driver_id : \"\"",
            actions,
        )
        self.assertIn("collapsedRegularOpShopPickupDates", app_state)
        self.assertIn("initializeCollapsedPickupDateGroups", actions)
        self.assertIn("toggleCollapsedPickupDateGroup", actions)
        self.assertIn('captureElementScroll("#opshop-pickup-list-root")', actions)
        self.assertIn("restoreElementScroll(scrollSnapshot)", actions)
        self.assertIn("requestAnimationFrame", scroll_utils)
        self.assertIn("scrollTop", scroll_utils)
        self.assertIn("scrollLeft", scroll_utils)
        self.assertNotIn("localStorage", scroll_utils)
        self.assertNotIn("sessionStorage", scroll_utils)
        self.assertNotIn("location.hash", scroll_utils)
        self.assertNotIn("scrollIntoView", scroll_utils)
        self.assertIn("onOpenOpShopPickupList", task_pool_renderer)
        self.assertIn("Regular OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Count:", task_pool_renderer)
        self.assertIn("Window:", task_pool_renderer)
        self.assertIn("Open List", task_pool_renderer)
        self.assertNotIn("Export OP SHOP Run Sheet", task_pool_renderer)
        self.assertNotIn("Exporting OP SHOP Run Sheet", task_pool_renderer)
        self.assertNotIn("onExportOpShopRunSheet", task_pool_renderer)
        self.assertNotIn("ACTIVE / ASSIGNED", task_pool_renderer)
        self.assertNotIn("ON_CALL / COUNTRYSIDE", task_pool_renderer)
        self.assertIn("function createDeliveryOrderFilterBar", task_pool_renderer)
        self.assertIn('filterBar.className = "task-filter-bar"', task_pool_renderer)
        self.assertIn('searchInput.id = "order-search"', task_pool_renderer)
        self.assertIn('urgencySelect.id = "urgency-filter"', task_pool_renderer)
        self.assertIn('deliveryDateInput.id = "task-pool-delivery-date-filter"', task_pool_renderer)
        self.assertIn('clearDeliveryDateButton.id = "clear-task-pool-delivery-date-filter"', task_pool_renderer)
        self.assertIn('summary.id = "task-filter-summary"', task_pool_renderer)
        delivery_section = task_pool_renderer.split("function createDeliveryOrderSection", 1)[1]
        self.assertIn("const filterBar = createDeliveryOrderFilterBar({ onOpenAttacheInvoiceImport });", delivery_section)
        self.assertIn("section.append(filterBar, list);", delivery_section)
        self.assertNotIn('class="task-filter-bar"', index_html)
        self.assertIn("opshopRegularListWindowStart", task_pool_renderer)
        self.assertIn("renderOpShopPickupListModal", app_js)
        self.assertIn("onOpenOpShopPickupList: opShopPickupActions.openOpShopPickupList", app_js)
        self.assertNotIn("onExportOpShopRunSheet: opShopPickupActions.exportOpShopRunSheet", app_js)
        self.assertIn("onToggleDateGroup: opShopPickupActions.toggleDateGroup", app_js)
        self.assertIn("onUpdateAssignedDriver: opShopPickupActions.updateAssignedDriverSelection", app_js)

        self.assertIn("groupPickupsByDate", modal_renderer)
        self.assertIn("state.scheduledOpShopPickups", modal_renderer)
        self.assertNotIn(".filter((pickup) => pickup.assigned_driver_id", modal_renderer)
        self.assertIn("comparePickupsWithinDateGroup", modal_renderer)
        self.assertIn("getAssignedDriverSortName", modal_renderer)
        self.assertIn("getDriverNameById", modal_renderer)
        self.assertIn("compareText(leftDriverName, rightDriverName)", modal_renderer)
        self.assertIn("compareText(left.suburb, right.suburb)", modal_renderer)
        self.assertIn("compareText(left.opshop_name, right.opshop_name)", modal_renderer)
        self.assertIn("compareText(left.pickup_task_id, right.pickup_task_id)", modal_renderer)
        self.assertIn("const hasSelection = Object.prototype.hasOwnProperty.call", modal_renderer)
        self.assertIn("state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id]", modal_renderer)
        self.assertIn("getDefaultDriverIdForVisiblePickup(pickup)", modal_renderer)
        self.assertIn("function shouldUseDefaultDriverForVisiblePickup(pickup)", modal_renderer)
        self.assertIn("function canUseDefaultDriverForVisiblePickup(pickup)", modal_renderer)
        self.assertIn("defaultDriverExistsForVisiblePickup(pickup)", modal_renderer)
        self.assertIn("isDriverFinalizedForPickup(pickup.default_driver_id, pickup.pickup_date)", modal_renderer)
        self.assertIn("pickup.pickup_date >= state.dispatchDate", modal_renderer)
        self.assertIn("getDefaultDriverHintText(pickup)", modal_renderer)
        self.assertIn("unavailable - Final Summary saved", modal_renderer)
        self.assertIn("unavailable", modal_renderer)
        self.assertIn("if (leftDriverName && !rightDriverName)", modal_renderer)
        self.assertIn("if (!leftDriverName && rightDriverName)", modal_renderer)
        self.assertIn("formatDateHeading", modal_renderer)
        self.assertIn("Monday", modal_renderer)
        self.assertIn("opshop-date-group", modal_renderer)
        self.assertIn("opshop-date-group-toggle", modal_renderer)
        self.assertIn('toggle.setAttribute("aria-expanded", String(!collapsed))', modal_renderer)
        self.assertIn('toggle.setAttribute("aria-controls", listId)', modal_renderer)
        self.assertIn("state.collapsedRegularOpShopPickupDates", modal_renderer)
        self.assertIn("getDateGroupCollapsed", modal_renderer)
        self.assertIn("list.hidden = collapsed", modal_renderer)
        self.assertIn("toggle.addEventListener(\"click\", (event) =>", modal_renderer)
        self.assertIn("event.preventDefault()", modal_renderer)
        self.assertIn("event.stopPropagation()", modal_renderer)
        self.assertNotIn("if (event.target !== backdrop)", modal_renderer)
        self.assertNotIn("backdrop.addEventListener(\"click\"", modal_renderer)
        self.assertIn("Collapsed", modal_renderer)
        self.assertIn("Expanded", modal_renderer)
        self.assertIn("opshop-date-group-toggle", styles)
        self.assertIn("opshop-date-group-count", styles)
        self.assertIn("opshop-date-group-state", styles)
        self.assertIn(".opshop-date-card-list[hidden]", styles)
        self.assertIn("display: none;", styles)
        self.assertIn("Object.prototype.hasOwnProperty.call(collapsedDates, pickupDate)", date_group_utils)
        self.assertIn("[pickupDate]: !getDateGroupCollapsed", date_group_utils)
        self.assertIn("String(pickupDate) < String(dispatchDate)", date_group_utils)
        self.assertNotIn("localStorage", date_group_utils)
        self.assertNotIn("sessionStorage", date_group_utils)
        self.assertNotIn("location.hash", date_group_utils)
        self.assertNotIn("scrollIntoView", date_group_utils)
        self.assertNotIn("localStorage", actions)
        self.assertNotIn("sessionStorage", actions)
        self.assertNotIn("location.hash", actions)
        self.assertNotIn("scrollIntoView", actions)
        self.assertNotIn("localStorage", modal_renderer)
        self.assertNotIn("sessionStorage", modal_renderer)
        self.assertNotIn("location.hash", modal_renderer)
        self.assertNotIn("scrollIntoView", modal_renderer)
        self.assertIn("opshop-list-item", modal_renderer)
        list_item_renderer = modal_renderer.split("function createPickupItem", 1)[1].split(
            "function createAssignedToSelect",
            1,
        )[0]
        self.assertIn("onOpenDetail(pickup.pickup_task_id)", modal_renderer)
        self.assertIn("event.stopPropagation()", modal_renderer)
        self.assertIn("Schedule", modal_renderer)
        self.assertIn("Pickup Date", modal_renderer)
        self.assertIn("Notes", modal_renderer)
        self.assertIn("Delete Pickup Task", modal_renderer)
        self.assertIn("[\"ACTIVE\", \"ASSIGNED\"].includes(pickup.status)", modal_renderer)
        self.assertIn("removes any OP SHOP assignment", modal_renderer)
        self.assertIn("Assigned pickups can update notes only", modal_renderer)
        self.assertIn("Assigned to", modal_renderer)
        self.assertIn("Past pickup date", modal_renderer)
        self.assertIn("opshop-assigned-to-field", modal_renderer)
        self.assertIn("opshop-list-item-meta", modal_renderer)
        self.assertIn("opshop-list-item-suburb", modal_renderer)
        self.assertIn("opshop-list-item-date", modal_renderer)
        self.assertIn("if (!lockState.isLocked)", list_item_renderer)
        self.assertIn('editButton.textContent = "Edit"', list_item_renderer)
        self.assertNotIn("Frequency:", list_item_renderer)
        self.assertNotIn("Status:", list_item_renderer)
        self.assertNotIn("Time:", list_item_renderer)
        self.assertNotIn("Phone:", list_item_renderer)
        self.assertNotIn("compact-note", list_item_renderer)
        self.assertNotIn("opshop-pickup-note", list_item_renderer)
        self.assertNotIn('deleteButton.textContent = "Delete"', list_item_renderer)
        self.assertIn("state.drivers", modal_renderer)
        self.assertNotIn("pickup.default_driver_id ||", modal_renderer)
        self.assertIn("pickup.assigned_to_locked", modal_renderer)
        self.assertIn("isDriverFinalizedForPickup", modal_renderer)
        self.assertIn("const isFinalSummaryLocked", modal_renderer)
        self.assertIn('isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', modal_renderer)
        self.assertIn("const isGeneratedFinalSummaryLocked", modal_renderer)
        self.assertIn("const isLocked", modal_renderer)
        self.assertIn("Boolean(isGeneratedFinalSummaryLocked)", modal_renderer)
        self.assertIn("select.disabled = isLocked || state.isOpShopPickupSaving", modal_renderer)
        self.assertIn("(Final Summary saved)", modal_renderer)
        self.assertIn("option.disabled = hasSavedFinalSummary", modal_renderer)
        self.assertIn("opshop-assigned-to-hint", modal_renderer)
        self.assertIn("Locked - Final Trip Summary saved", modal_renderer)
        self.assertIn("Locked - Generated in Final Trip Summary", modal_renderer)
        self.assertIn("opshop-assigned-to-lock-finalized", modal_renderer)
        self.assertIn("opshop-assigned-to-select-locked", modal_renderer)
        self.assertIn("opshop-assigned-to-lock-finalized", styles)
        self.assertIn("opshop-assigned-to-select-locked", styles)
        self.assertNotIn("createElement(\"table\")", modal_renderer)
        self.assertNotIn('textContent = "Assign"', modal_renderer)
        self.assertNotIn('textContent = "Unassign"', modal_renderer)
        self.assertNotIn("tripSelect", modal_renderer)
        self.assertNotIn('textContent = "Trip"', modal_renderer)
        self.assertNotIn("fetch(", actions)
        self.assertNotIn("fetch(", modal_renderer)

    def test_oncall_opshop_pickup_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        board_state_sync = (
            FRONTEND_ROOT / "js" / "state" / "board-state-sync.js"
        ).read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-oncall-pickup-actions.js"
        ).read_text(encoding="utf-8")
        app_state = (
            FRONTEND_ROOT / "js" / "state" / "app-state.js"
        ).read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-oncall-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")
        scroll_utils = (
            FRONTEND_ROOT / "js" / "utils" / "scroll-utils.js"
        ).read_text(encoding="utf-8")
        selectors = (FRONTEND_ROOT / "js" / "state" / "selectors.js").read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("apiListOncallOpShopPickupSchedules", api_module)
        self.assertIn("apiCreateOncallOpShopPickup", api_module)
        self.assertIn("apiApplyOncallOpShopPickupAssignments", api_module)
        self.assertIn("/opshop-pickups/oncall", api_module)
        self.assertIn("/opshop-pickups/oncall-assignments/apply", api_module)
        self.assertIn("createOncallOpShopPickupActions", actions)
        self.assertIn("openOncallOpShopPickupList", actions)
        self.assertIn("apiApplyOncallOpShopPickupAssignments", actions)
        self.assertIn('!isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', actions)
        self.assertIn("state.isOncallOpShopPickupSaving || state.isOncallOpShopPickupListLoading", actions)
        self.assertIn("apiCreateOncallOpShopPickup", actions)
        self.assertIn("updateAssignedDriverSelection", actions)
        self.assertIn("updateOncallTemplateFilter", actions)
        self.assertIn("selectOncallPickupTemplate", actions)
        self.assertIn("setOncallTemplatePickerOpen", actions)
        self.assertIn("getOncallTemplateDisplayText", actions)
        self.assertIn("candidateMatchesTemplateFilter", actions)
        self.assertIn("normalizeTemplateSearchText", actions)
        self.assertIn("if (state.isOncallOpShopPickupTemplatePickerOpen === nextOpen)", actions)
        self.assertIn("state.isOncallOpShopPickupTemplatePickerOpen = nextOpen", actions)
        self.assertIn("state.oncallOpShopPickupTemplateFilter = nextFilter", actions)
        self.assertIn("state.isOncallOpShopPickupTemplatePickerOpen = true", actions)
        self.assertIn("normalizeTemplateSearchText(nextFilter) !== normalizeTemplateSearchText(selectedCandidateText)", actions)
        self.assertIn('schedule_id: ""', actions)
        self.assertIn("schedule_id: candidate ? candidate.schedule_id : \"\"", actions)
        self.assertIn("state.oncallOpShopPickupTemplateFilter = getOncallTemplateDisplayText(candidate)", actions)
        self.assertIn("state.isOncallOpShopPickupTemplatePickerOpen = false", actions)
        self.assertIn('state.oncallOpShopPickupTemplateFilter = "";', actions)
        self.assertGreaterEqual(actions.count("resetTemplatePicker();"), 4)
        self.assertIn("collapsedOncallOpShopPickupDates", app_state)
        self.assertIn("oncallOpShopPickupTemplateFilter", app_state)
        self.assertIn("isOncallOpShopPickupTemplatePickerOpen", app_state)
        self.assertIn("initializeCollapsedPickupDateGroups", actions)
        self.assertIn("toggleCollapsedPickupDateGroup", actions)
        self.assertIn('captureElementScroll("#opshop-oncall-pickup-list-root")', actions)
        self.assertIn("restoreElementScroll(scrollSnapshot)", actions)
        self.assertIn("requestAnimationFrame", scroll_utils)
        self.assertNotIn("localStorage", scroll_utils)
        self.assertNotIn("sessionStorage", scroll_utils)
        self.assertNotIn("location.hash", scroll_utils)
        self.assertNotIn("scrollIntoView", scroll_utils)
        self.assertIn("WEEKDAY_OFFSETS", actions)
        self.assertIn("candidate.run_day", actions)
        self.assertIn('return state.dispatchDate || "";', actions)
        self.assertIn('["schedule_id", "pickup_date"].includes(field)', actions)
        self.assertIn("getOncallTargetWeekMonday(state.dispatchDate)", actions)
        self.assertNotIn("state.opshopRegularListWindowStart", actions)
        self.assertIn("renderOncallOpShopPickupListModal", app_js)
        self.assertIn("createOncallOpShopPickupActions", app_js)
        self.assertIn("onOpenOncallOpShopPickupList: oncallOpShopPickupActions.openOncallOpShopPickupList", app_js)
        self.assertIn("onToggleDateGroup: oncallOpShopPickupActions.toggleDateGroup", app_js)
        self.assertIn(
            "onUpdateTemplateFilter: oncallOpShopPickupActions.updateOncallTemplateFilter",
            app_js,
        )
        self.assertIn("onSelectTemplate: oncallOpShopPickupActions.selectOncallPickupTemplate", app_js)
        self.assertIn("onSetTemplatePickerOpen: oncallOpShopPickupActions.setOncallTemplatePickerOpen", app_js)
        self.assertIn("oncallOpShopPickups: payload.oncall_opshop_pickups || []", board_state_sync)
        self.assertIn("state.oncallOpShopPickups = board.oncallOpShopPickups", board_state_sync)
        self.assertIn("Oncall OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Oncall OP SHOP Pickup List", modal_renderer)
        self.assertIn("No Oncall OP SHOP pickups added.", modal_renderer)
        self.assertIn("Template", modal_renderer)
        self.assertIn("Pickup Date", modal_renderer)
        self.assertIn("Assigned to", modal_renderer)
        self.assertIn("Notes", modal_renderer)
        self.assertIn("createTemplatePicker", modal_renderer)
        self.assertIn("opshop-template-picker-field", modal_renderer)
        self.assertIn("opshop-template-picker-input", modal_renderer)
        self.assertIn("opshop-template-picker-input-selected", modal_renderer)
        self.assertIn("opshop-template-picker-menu", modal_renderer)
        self.assertIn("opshop-template-picker-results", modal_renderer)
        self.assertIn("opshop-template-picker-option", modal_renderer)
        self.assertIn("opshop-template-picker-option-selected", modal_renderer)
        self.assertIn("opshop-template-picker-option-main", modal_renderer)
        self.assertIn("opshop-template-picker-option-meta", modal_renderer)
        self.assertIn("opshop-template-picker-selected-mark", modal_renderer)
        self.assertIn("opshop-template-picker-empty", modal_renderer)
        self.assertIn('selectedMark.textContent = "Selected"', modal_renderer)
        self.assertIn("Search or select Oncall OP SHOP template", modal_renderer)
        self.assertIn('input.type = "text"', modal_renderer)
        self.assertNotIn("input.readOnly = true", modal_renderer)
        self.assertIn('input.setAttribute("role", "combobox")', modal_renderer)
        self.assertIn('input.setAttribute("aria-expanded", String(isExpanded))', modal_renderer)
        self.assertIn('input.setAttribute("aria-controls", pickerId)', modal_renderer)
        self.assertIn('option.setAttribute("aria-selected", String(isSelected))', modal_renderer)
        self.assertIn("option.type = \"button\"", modal_renderer)
        self.assertIn("option.addEventListener(\"pointerdown\", (event) =>", modal_renderer)
        self.assertIn("event.preventDefault()", modal_renderer)
        self.assertIn("event.stopPropagation()", modal_renderer)
        self.assertIn("opshop-template-picker-option-selected", styles)
        self.assertIn(".opshop-template-picker-option:hover", styles)
        self.assertIn(".opshop-template-picker-option:focus-visible", styles)
        self.assertIn("max-height: 320px;", styles)
        self.assertIn("overflow-y: auto;", styles)
        self.assertIn("padding: 0.62rem 0.75rem 0.8rem;", styles)
        self.assertIn("min-height: 68px;", styles)
        self.assertIn("padding: 0.86rem 1rem 1rem;", styles)
        self.assertIn("gap: 0.38rem;", styles)
        self.assertIn("line-height: 1.42;", styles)
        self.assertIn("overscroll-behavior: contain;", styles)
        self.assertIn("pointer-events: auto;", styles)
        self.assertIn("touch-action: pan-y;", styles)
        self.assertIn("onSelectTemplate(filteredCandidates[0].schedule_id)", modal_renderer)
        self.assertIn("onUpdateTemplateFilter", modal_renderer)
        self.assertIn("onSetTemplatePickerOpen", modal_renderer)
        self.assertIn("onSelectTemplate(candidate.schedule_id)", modal_renderer)
        self.assertIn("getFilteredScheduleCandidates", modal_renderer)
        self.assertIn("templateMatchesFilter", modal_renderer)
        self.assertIn("normalizeTemplateSearchText", modal_renderer)
        self.assertIn("formatScheduleCandidateOptionText", modal_renderer)
        self.assertIn("state.oncallOpShopPickupTemplateFilter", modal_renderer)
        self.assertIn("candidate.opshop_name", modal_renderer)
        self.assertIn("candidate.suburb", modal_renderer)
        self.assertIn("candidate.street_address", modal_renderer)
        self.assertIn("candidate.run_day", modal_renderer)
        self.assertIn("candidate.default_driver_name", modal_renderer)
        self.assertIn("candidate.default_driver_alias", modal_renderer)
        self.assertIn("formatScheduleCandidateOptionText(candidate)", modal_renderer)
        self.assertIn("No Oncall templates match this search.", modal_renderer)
        self.assertIn("const selectedScheduleId = state.oncallOpShopPickupForm.schedule_id || \"\";", modal_renderer)
        self.assertIn(
            "const hasNoTemplateMatches = !selectedScheduleId && hasTemplateFilter && filteredCandidates.length === 0;",
            modal_renderer,
        )
        self.assertIn("!selectedScheduleId ||", modal_renderer)
        self.assertNotIn("hasNoTemplateMatches ||", modal_renderer)
        self.assertNotIn("createScheduleSelect", modal_renderer)
        self.assertNotIn('label.textContent = "Search templates"', modal_renderer)
        self.assertNotIn('select.name = "schedule_id"', modal_renderer)
        self.assertIn("{ disabled: lockState.isLocked }", modal_renderer)
        self.assertNotIn('isLocked || (pickup && pickup.status === "ASSIGNED")', modal_renderer)
        self.assertIn("candidate.run_day || \"Gavin\"", modal_renderer)
        self.assertIn("onOpenDetail(pickup.pickup_task_id)", modal_renderer)
        self.assertIn("Past pickup date", modal_renderer)
        self.assertIn("if (!lockState.isLocked)", modal_renderer)
        self.assertIn("[\"ACTIVE\", \"ASSIGNED\"].includes(pickup.status)", modal_renderer)
        self.assertIn("removes any OP SHOP assignment", modal_renderer)
        self.assertIn("opshop-list-item-suburb", modal_renderer)
        self.assertIn("opshop-list-item-date", modal_renderer)
        self.assertIn("opshop-date-group-toggle", modal_renderer)
        self.assertIn('toggle.setAttribute("aria-expanded", String(!collapsed))', modal_renderer)
        self.assertIn('toggle.setAttribute("aria-controls", listId)', modal_renderer)
        self.assertIn("state.collapsedOncallOpShopPickupDates", modal_renderer)
        self.assertIn("getDateGroupCollapsed", modal_renderer)
        self.assertIn("list.hidden = collapsed", modal_renderer)
        self.assertIn("toggle.addEventListener(\"click\", (event) =>", modal_renderer)
        self.assertIn("event.preventDefault()", modal_renderer)
        self.assertIn("event.stopPropagation()", modal_renderer)
        self.assertNotIn("if (event.target !== backdrop)", modal_renderer)
        self.assertNotIn("backdrop.addEventListener(\"click\"", modal_renderer)
        self.assertNotIn("localStorage", actions)
        self.assertNotIn("sessionStorage", actions)
        self.assertNotIn("location.hash", actions)
        self.assertNotIn("scrollIntoView", actions)
        self.assertNotIn("localStorage", modal_renderer)
        self.assertNotIn("sessionStorage", modal_renderer)
        self.assertNotIn("location.hash", modal_renderer)
        self.assertNotIn("scrollIntoView", modal_renderer)
        self.assertIn("state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id]", modal_renderer)
        self.assertIn("isDriverFinalizedForPickup", modal_renderer)
        self.assertIn("const isFinalSummaryLocked", modal_renderer)
        self.assertIn('isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', modal_renderer)
        self.assertIn("const isGeneratedFinalSummaryLocked", modal_renderer)
        self.assertIn("Boolean(isGeneratedFinalSummaryLocked)", modal_renderer)
        self.assertIn("select.disabled = isLocked || state.isOncallOpShopPickupSaving", modal_renderer)
        self.assertIn("(Final Summary saved)", modal_renderer)
        self.assertIn("option.disabled = hasSavedFinalSummary", modal_renderer)
        self.assertIn("Locked - Final Trip Summary saved", modal_renderer)
        self.assertIn("Locked - Generated in Final Trip Summary", modal_renderer)
        self.assertIn("opshop-assigned-to-lock-finalized", modal_renderer)
        self.assertIn("opshop-assigned-to-select-locked", modal_renderer)
        self.assertIn("onCloseList: oncallOpShopPickupActions.closeOncallOpShopPickupList", app_js)
        self.assertIn("oncallOpShopPickups", selectors)
        self.assertIn("assigned-opshop-pickups-section", (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8"))
        self.assertNotIn('textContent = "Assign"', modal_renderer)
        self.assertNotIn('textContent = "Unassign"', modal_renderer)
        self.assertNotIn("tripSelect", modal_renderer)
        self.assertNotIn("Trip dropdown", modal_renderer)
        self.assertIn("OP SHOP PICKUPS", final_summary_renderer)
        self.assertIn('const EMPTY_ORDER_SUMMARY_MESSAGE = "No Delivery Orders included."', final_summary_renderer)
        self.assertNotIn("fetch(", actions)
        self.assertNotIn("fetch(", modal_renderer)

    def test_countryside_opshop_pickup_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        board_state_sync = (
            FRONTEND_ROOT / "js" / "state" / "board-state-sync.js"
        ).read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-countryside-pickup-actions.js"
        ).read_text(encoding="utf-8")
        oncall_actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-oncall-pickup-actions.js"
        ).read_text(encoding="utf-8")
        app_state = (
            FRONTEND_ROOT / "js" / "state" / "app-state.js"
        ).read_text(encoding="utf-8")
        selectors = (
            FRONTEND_ROOT / "js" / "state" / "selectors.js"
        ).read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-countryside-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")
        regular_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")
        oncall_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-oncall-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")
        trip_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8")
        styles = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn("apiListCountrysideRouteGroups", api_module)
        self.assertIn("apiCreateCountrysideRouteGroup", api_module)
        self.assertIn("apiUpdateCountrysideRouteGroup", api_module)
        self.assertIn("apiDisableCountrysideRouteGroup", api_module)
        self.assertIn("apiListCountrysideRouteMemberships", api_module)
        self.assertIn("apiAddCountrysideRouteMembership", api_module)
        self.assertIn("apiRemoveCountrysideRouteMembership", api_module)
        self.assertIn("apiMoveCountrysideRouteMembership", api_module)
        self.assertIn("apiListCountrysideOpShopPickupSchedules", api_module)
        self.assertIn("apiApplyCountrysideOpShopPickupAssignments", api_module)
        self.assertIn("apiAssignCountrysideRouteGroup", api_module)
        self.assertIn("/api/manual-dispatch/opshop-countryside-route-groups", api_module)
        self.assertIn("/memberships", api_module)
        self.assertIn("/opshop-countryside-memberships", api_module)
        self.assertIn("/opshop-pickup-schedules", api_module)
        self.assertIn('pickup_category: "COUNTRYSIDE"', api_module)
        self.assertIn("/opshop-pickups/countryside-assignments/apply", api_module)
        self.assertIn("/opshop-pickups/countryside-route-groups/", api_module)
        self.assertIn("/assign", api_module)
        self.assertIn("createCountrysideOpShopPickupActions", actions)
        self.assertIn("openCountrysideOpShopPickupList", actions)
        self.assertIn("apiAssignCountrysideRouteGroup", actions)
        self.assertNotIn("apiCreateOncallOpShopPickup", actions)
        self.assertIn("apiCreateCountrysideRouteGroup", actions)
        self.assertIn("apiAddCountrysideRouteMembership", actions)
        self.assertIn("apiMoveCountrysideRouteMembership", actions)
        self.assertIn("apiRemoveCountrysideRouteMembership", actions)
        self.assertIn("startNewRouteGroup", actions)
        self.assertIn("startRenameRouteGroup", actions)
        self.assertIn("startDisableRouteGroup", actions)
        self.assertIn("startAddRouteTemplate", actions)
        self.assertIn("startMoveRouteTemplate", actions)
        self.assertIn("startRemoveRouteTemplate", actions)
        self.assertIn("openRouteTemplateDetail", actions)
        self.assertIn("closeRouteTemplateDetail", actions)
        self.assertIn("apiApplyCountrysideOpShopPickupAssignments", actions)
        self.assertIn(
            "state.isCountrysideOpShopPickupSaving || state.isCountrysideOpShopPickupListLoading",
            actions,
        )
        self.assertIn("getVisibleCountrysidePickups()", actions)
        self.assertIn("state.countrysideOpShopPickupAssignedDriverSelections", actions)
        pickup_form_update = actions.split("function updatePickupTaskForm", 1)[1].split(
            "function resetPickupTaskForm",
            1,
        )[0]
        self.assertIn('field === "route_group_id"', pickup_form_update)
        self.assertIn('field === "pickup_date"', pickup_form_update)
        self.assertIn('field === "assigned_driver_id"', pickup_form_update)
        self.assertIn("dispatch_date: state.dispatchDate", actions)
        self.assertIn("apiAssignCountrysideRouteGroup(routeGroupId", actions)
        self.assertIn("assigned_driver_id: selectedDriverId", actions)
        self.assertIn('const shouldRender = ["schedule_id", "pickup_date"].includes(field);', oncall_actions)
        self.assertIn("dispatch_date: state.dispatchDate", oncall_actions)
        self.assertIn("selectedCountrysideRouteGroupId", app_state)
        self.assertIn("countrysideRouteGroups", app_state)
        self.assertIn("countrysideRouteMemberships", app_state)
        self.assertIn("countrysideRouteFormMode", app_state)
        self.assertIn("countrysideRouteTemplateFormMode", app_state)
        self.assertIn("isCountrysideRouteTemplateSaving", app_state)
        self.assertIn("countrysideOpShopPickups", app_state)
        self.assertIn("countrysideOpShopPickupScheduleCandidates", app_state)
        self.assertIn("isCountrysideOpShopPickupListOpen", app_state)
        self.assertIn("activeCountrysideRouteTemplateDetailId", app_state)
        self.assertIn("countrysideOpShopPickups: payload.countryside_opshop_pickups || []", board_state_sync)
        self.assertIn("countrysideRouteGroups: payload.countryside_route_groups || []", board_state_sync)
        self.assertIn("state.countrysideOpShopPickups = board.countrysideOpShopPickups", board_state_sync)
        self.assertIn("state.countrysideRouteGroups = board.countrysideRouteGroups", board_state_sync)
        self.assertIn("getCountrysideOpShopPickupByTaskId", selectors)
        self.assertIn("getCountrysideRouteGroupById", selectors)
        self.assertIn("getCountrysideScheduleCandidatesForRouteGroup", selectors)
        self.assertIn("state.countrysideOpShopPickups.find", selectors)
        self.assertIn("renderCountrysideOpShopPickupListModal", app_js)
        self.assertIn("createCountrysideOpShopPickupActions", app_js)
        self.assertIn(
            "onOpenCountrysideOpShopPickupList: countrysideOpShopPickupActions.openCountrysideOpShopPickupList",
            app_js,
        )
        self.assertIn(
            "onOpenRouteTemplateDetail: countrysideOpShopPickupActions.openRouteTemplateDetail",
            app_js,
        )
        self.assertIn(
            "onCloseRouteTemplateDetail: countrysideOpShopPickupActions.closeRouteTemplateDetail",
            app_js,
        )
        self.assertIn("Countryside OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("No Countryside OP SHOP pickups added.", task_pool_renderer)
        self.assertIn("onOpenCountrysideOpShopPickupList", task_pool_renderer)
        self.assertNotIn("Manage Countryside Routes", task_pool_renderer)
        self.assertIn("Countryside OP SHOP Pickup List", modal_renderer)
        self.assertIn("Route Group", modal_renderer)
        self.assertIn("New Route", modal_renderer)
        self.assertIn("Rename", modal_renderer)
        self.assertIn("Disable", modal_renderer)
        self.assertIn("Pickup Tasks", modal_renderer)
        self.assertIn("Route Templates", modal_renderer)
        self.assertIn("Add OP SHOP to this route", modal_renderer)
        self.assertIn("Assign Route Group", modal_renderer)
        self.assertIn("getAssignRouteGroupStartDisabledReason", modal_renderer)
        self.assertIn("getAssignRouteGroupSubmitDisabledReason", modal_renderer)
        self.assertIn("getAssignmentRouteGroupId", modal_renderer)
        self.assertIn("getRouteGroupTemplateCount", modal_renderer)
        self.assertIn("hasAnyAssignableRouteGroup", modal_renderer)
        self.assertIn("Select a route group.", modal_renderer)
        self.assertIn("No active route groups with route templates are available.", modal_renderer)
        self.assertIn("Select a pickup date.", modal_renderer)
        self.assertIn("Select an assigned driver.", modal_renderer)
        self.assertIn("This route group has no active route templates.", modal_renderer)
        start_disabled_reason = modal_renderer.split(
            "function getAssignRouteGroupStartDisabledReason",
            1,
        )[1].split("function getAssignRouteGroupSubmitDisabledReason", 1)[0]
        self.assertIn("!hasAnyAssignableRouteGroup()", start_disabled_reason)
        self.assertNotIn("state.selectedCountrysideRouteGroupId", start_disabled_reason)
        self.assertNotIn("getRouteGroupTemplateCount(state.selectedCountrysideRouteGroupId)", start_disabled_reason)
        self.assertIn("createRouteGroupSelect(onUpdateForm)", modal_renderer)
        self.assertIn("state.countrysideOpShopPickupScheduleCandidates.filter", modal_renderer)
        self.assertIn("opshop-route-assign-disabled-reason", modal_renderer)
        self.assertIn("opshop-route-assign-disabled-reason", styles)
        self.assertNotIn("Create Pickup Task", modal_renderer)
        self.assertIn("Move", modal_renderer)
        self.assertIn("Remove", modal_renderer)
        self.assertIn("Select a route group to manage route templates.", modal_renderer)
        self.assertIn("No actual Countryside pickup tasks have been assigned for this route group yet.", modal_renderer)
        self.assertIn("Use Assign Route Group to create and assign all route templates for a pickup date.", modal_renderer)
        self.assertNotIn("Select Countryside OP SHOP template", modal_renderer)
        self.assertIn("Select a route group before assigning Countryside pickups.", modal_renderer)
        self.assertIn("ON_CALL + COUNTRYSIDE", modal_renderer)
        self.assertIn("groupPickupsByRouteGroup", modal_renderer)
        self.assertIn("comparePickupsWithinRouteGroup", modal_renderer)
        self.assertIn("route_group_name", modal_renderer)
        self.assertIn("createRouteTemplateDetailPanel", modal_renderer)
        self.assertIn("Route Template Detail", modal_renderer)
        self.assertIn("OP SHOP name", modal_renderer)
        self.assertIn("Street address", modal_renderer)
        self.assertIn("Default driver", modal_renderer)
        self.assertIn("activeCountrysideRouteTemplateDetailId", modal_renderer)
        self.assertIn("card.addEventListener(\"click\", () => onOpenRouteTemplateDetail(template))", modal_renderer)
        self.assertIn("actions.addEventListener(\"click\", (event) => event.stopPropagation())", modal_renderer)
        route_template_card = modal_renderer.split("function createRouteTemplateCard", 1)[1].split(
            "function createPickupItem",
            1,
        )[0]
        self.assertNotIn("Create Pickup Task", route_template_card)
        self.assertNotIn("onStartCreatePickupFromRouteTemplate", route_template_card)
        self.assertIn("card.setAttribute(\"role\", \"button\")", modal_renderer)
        self.assertIn("card.tabIndex = 0", modal_renderer)
        self.assertIn("root.replaceChildren()", modal_renderer)
        self.assertIn("state.countrysideOpShopPickupAssignedDriverSelections[pickup.pickup_task_id]", modal_renderer)
        self.assertIn("onOpenDetail(pickup.pickup_task_id)", modal_renderer)
        self.assertIn("event.stopPropagation()", modal_renderer)
        self.assertIn("const isFinalSummaryLocked", modal_renderer)
        self.assertIn('isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id)', modal_renderer)
        self.assertIn("const isGeneratedFinalSummaryLocked", modal_renderer)
        self.assertIn("Boolean(isGeneratedFinalSummaryLocked)", modal_renderer)
        self.assertIn("select.disabled = isLocked || state.isCountrysideOpShopPickupSaving", modal_renderer)
        self.assertIn("(Final Summary saved)", modal_renderer)
        self.assertIn("option.disabled = hasSavedFinalSummary", modal_renderer)
        self.assertIn("Locked - Final Trip Summary saved", modal_renderer)
        self.assertIn("Locked - Generated in Final Trip Summary", modal_renderer)
        self.assertIn("opshop-assigned-to-lock-finalized", modal_renderer)
        self.assertIn("opshop-assigned-to-select-locked", modal_renderer)
        self.assertIn("title.textContent = formatOptional(pickup.opshop_name)", modal_renderer)
        self.assertIn("suburb.textContent = formatOptional(pickup.suburb)", modal_renderer)
        self.assertIn("routeGroup.textContent = `Route Group:", modal_renderer)
        self.assertIn("title.textContent = formatOptional(template.name)", modal_renderer)
        self.assertIn("meta.textContent", modal_renderer)
        self.assertIn("notes.textContent = truncateText(template.status_notes", modal_renderer)
        self.assertIn("note.textContent = truncateText", modal_renderer)
        self.assertNotIn("backdrop.addEventListener(\"click\"", regular_modal_renderer)
        self.assertIn("modal.addEventListener(\"click\", (event) => event.stopPropagation())", regular_modal_renderer)
        self.assertNotIn("backdrop.addEventListener(\"click\"", oncall_modal_renderer)
        self.assertIn("modal.addEventListener(\"click\", (event) => event.stopPropagation())", oncall_modal_renderer)
        self.assertNotIn("backdrop.addEventListener(\"click\"", modal_renderer)
        self.assertIn("modal.addEventListener(\"click\", (event) => event.stopPropagation())", modal_renderer)
        self.assertIn("Countryside", trip_summary_renderer)
        self.assertIn("pickup.pickup_category === \"COUNTRYSIDE\"", trip_summary_renderer)
        self.assertIn("createAssignedCountrysideRouteGroup", trip_summary_renderer)
        self.assertIn("assigned-opshop-route-group", trip_summary_renderer)
        self.assertIn("assigned-opshop-route-group-header", trip_summary_renderer)
        self.assertIn("assigned-opshop-route-group-card-list", trip_summary_renderer)
        self.assertIn("showUnassignButton: false", trip_summary_renderer)
        assigned_opshop_renderer = trip_summary_renderer.split(
            "function createAssignedOpShopPickupTask",
            1,
        )[1]
        self.assertNotIn("Route Group:", assigned_opshop_renderer)
        self.assertIn("opshop-route-group-list", styles)
        self.assertIn("opshop-route-group-section", styles)
        self.assertIn("opshop-route-template-card", styles)
        self.assertIn("opshop-list-section", styles)
        self.assertIn(".checkbox-field", styles)
        self.assertIn("align-items: center;", styles)
        self.assertIn(".opshop-route-template-detail-panel", styles)
        self.assertIn(".opshop-route-template-detail-grid", styles)
        self.assertNotIn("localStorage", actions)
        self.assertNotIn("sessionStorage", actions)
        self.assertNotIn("location.hash", actions)
        self.assertNotIn("scrollIntoView", actions)
        self.assertNotIn("localStorage", modal_renderer)
        self.assertNotIn("sessionStorage", modal_renderer)
        self.assertNotIn("location.hash", modal_renderer)
        self.assertNotIn("scrollIntoView", modal_renderer)
        self.assertNotIn("fetch(", actions)
        self.assertNotIn("fetch(", modal_renderer)

    def test_opshop_template_management_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-template-actions.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-template-management-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Manage OP SHOP Templates", task_pool_renderer)
        self.assertIn("Regular OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Oncall OP SHOP Pickup List", task_pool_renderer)
        self.assertNotIn("Export OP SHOP Run Sheet", task_pool_renderer)
        self.assertIn("/api/manual-dispatch/opshop-templates", api_module)
        self.assertIn("apiCreateOpShopTemplate", api_module)
        self.assertIn("apiUpdateOpShopTemplate", api_module)
        self.assertIn("apiDisableOpShopTemplate", api_module)
        self.assertIn("createOpShopTemplateActions", actions)
        self.assertIn("refreshTemplateConsumers", actions)
        template_form_update = actions.split("function updateTemplateForm", 1)[1].split(
            "async function saveTemplate",
            1,
        )[0]
        self.assertIn("function updateTemplateForm(field, value, options = {})", actions)
        self.assertIn('const shouldRender = options.render ?? field === "run_type";', template_form_update)
        self.assertIn("if (shouldRender)", template_form_update)
        self.assertNotIn("state.opshopTemplateForm = form;\n    renderBoard();", template_form_update)
        self.assertIn("renderOpShopTemplateManagementModal", app_js)
        self.assertIn("OP SHOP Template Management", modal_renderer)
        self.assertIn("Regular Templates", modal_renderer)
        self.assertIn("Oncall Templates", modal_renderer)
        self.assertIn("Add Template", modal_renderer)
        self.assertIn("Default Driver", modal_renderer)
        self.assertIn(
            "Disable this template? Existing pickup tasks and saved history will not be deleted.",
            modal_renderer,
        )
        self.assertNotIn("fetch(", actions)
        self.assertNotIn("fetch(", modal_renderer)

    def test_product_line_typing_updates_state_without_popup_rerender(self):
        order_actions = (
            FRONTEND_ROOT / "js" / "actions" / "order-actions.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "updateProductLines(formKey, nextLines, { rerenderPopup: false });",
            order_actions,
        )
        self.assertGreaterEqual(order_actions.count("{ rerenderPopup: true }"), 2)
        self.assertIn(
            "function updateProductLines(formKey, productLines, { rerenderPopup = true } = {})",
            order_actions,
        )

    def test_frontend_module_import_paths_exist(self):
        frontend_sources = list(FRONTEND_ROOT.rglob("*.js"))
        import_paths = []

        for source_path in frontend_sources:
            source = source_path.read_text(encoding="utf-8")
            for import_path in re.findall(r'from\s+"(\.{1,2}/[^"]+)"', source):
                import_paths.append((source_path, import_path))

        self.assertGreaterEqual(len(import_paths), 1)
        for source_path, import_path in import_paths:
            module_path = (source_path.parent / import_path).resolve()
            self.assertTrue(
                module_path.exists(),
                f"Missing frontend module import from {source_path.name}: {import_path}",
            )

    def test_no_local_storage_or_mapping_apis_are_added_to_frontend_modules(self):
        frontend_sources = list(FRONTEND_ROOT.rglob("*.js"))

        for source_path in frontend_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("localStorage", source)
            if source_path.name != "app.js":
                self.assertNotIn("location.hash", source)
            self.assertNotIn("scrollIntoView", source)
            self.assertNotIn("google.maps", source)
            self.assertNotIn("geolocation", source)

    def test_render_modules_do_not_call_fetch(self):
        render_sources = list((FRONTEND_ROOT / "js" / "render").glob("*.js"))

        self.assertGreaterEqual(len(render_sources), 1)
        for source_path in render_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("fetch(", source, f"Render module should not call fetch: {source_path}")

    def test_action_modules_do_not_call_fetch_directly(self):
        action_sources = list((FRONTEND_ROOT / "js" / "actions").glob("*.js"))

        self.assertGreaterEqual(len(action_sources), 1)
        for source_path in action_sources:
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn("fetch(", source, f"Action module should use API client helpers: {source_path}")

    def test_frontend_fetch_calls_remain_in_api_module(self):
        api_module = FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"

        for source_path in FRONTEND_ROOT.rglob("*.js"):
            source = source_path.read_text(encoding="utf-8")
            if source_path == api_module:
                continue
            self.assertNotIn("fetch(", source, f"Fetch should stay centralized in API module: {source_path}")
