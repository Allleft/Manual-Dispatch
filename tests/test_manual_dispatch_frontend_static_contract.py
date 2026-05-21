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

    def test_driver_summary_delivery_date_control_is_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="driver-summary-delivery-date"', index_html)
        self.assertIn('type="date"', index_html)

    def test_task_pool_delivery_date_filter_controls_are_present(self):
        index_html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="task-pool-delivery-date-filter"', index_html)
        self.assertIn('id="clear-task-pool-delivery-date-filter"', index_html)
        self.assertIn("All delivery dates", index_html)

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

    def test_phase16_product_detail_controls_are_present(self):
        order_modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "order-modal-renderer.js"
        ).read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")

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
        self.assertIn("No Oncall OP SHOP pickups added.", task_pool_renderer)
        self.assertIn("onOpenOncallOpShopPickupList", task_pool_renderer)
        self.assertIn("opshop-pickup-list-summary-card", task_pool_renderer)
        self.assertIn(".opshop-summary-grid .opshop-pickup-list-summary-card", styles)
        self.assertIn("grid-column: 1 / -1", styles)
        self.assertIn("max-width: none", styles)
        self.assertIn("Open List", task_pool_renderer)
        self.assertIn("state.scheduledOpShopPickups", task_pool_renderer)
        self.assertNotIn("function createOpShopPickupCard", task_pool_renderer)
        self.assertNotIn('taskType: "OPSHOP_PICKUP"', task_pool_renderer)
        self.assertNotIn('textContent = "Details"', task_pool_renderer)

    def test_phase5_opshop_pickup_detail_modal_is_read_only(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-pickup-modal-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("opshopPickups: payload.opshop_pickups || []", app_js)
        self.assertIn("assignedOpShopPickups: payload.assigned_opshop_pickups || []", app_js)
        self.assertIn("scheduledOpShopPickups: payload.scheduled_opshop_pickups || []", app_js)
        self.assertIn("oncallOpShopPickups: payload.oncall_opshop_pickups || []", app_js)
        self.assertIn("opshopRegularListWindowStart: payload.opshop_regular_list_window_start || \"\"", app_js)
        self.assertIn("opshopRegularListWindowEnd: payload.opshop_regular_list_window_end || \"\"", app_js)
        self.assertIn("state.opshopPickups = board.opshopPickups", app_js)
        self.assertIn("state.assignedOpShopPickups = board.assignedOpShopPickups", app_js)
        self.assertIn("state.scheduledOpShopPickups = board.scheduledOpShopPickups", app_js)
        self.assertIn("state.oncallOpShopPickups = board.oncallOpShopPickups", app_js)
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
        self.assertNotIn('taskType: "OPSHOP_PICKUP"', task_pool_renderer)
        self.assertIn("assigned-opshop-task", trip_summary_renderer)
        self.assertIn("assigned-opshop-name", trip_summary_renderer)
        self.assertIn("assigned-opshop-suburb", trip_summary_renderer)
        self.assertIn(".assigned-opshop-name", styles)
        self.assertIn(".assigned-opshop-suburb", styles)
        self.assertIn("getAssignedOpShopPickupsForDriver", trip_summary_renderer)
        self.assertIn("pickup.pickup_date === state.driverSummaryDeliveryDate", selectors)
        self.assertIn("getOrderAssignmentsForDriverTrip", selectors)
        self.assertIn("createOpShopPickupGroup", trip_summary_renderer)
        self.assertIn("OP SHOP PICKUPS", trip_summary_renderer)
        self.assertIn("assigned-opshop-pickups-section", trip_summary_renderer)
        self.assertIn('assignment.task_type === "ORDER"', selectors)
        self.assertIn('assignment.task_type === "OPSHOP_PICKUP"', trip_summary_renderer)
        self.assertIn("onOpenOpShopPickupDetail(pickup.pickup_task_id)", trip_summary_renderer)
        self.assertIn("onUnassign(assignment.task_type, assignment.task_id)", trip_summary_renderer)
        self.assertIn("not included in Final Trip Summary or Excel export", trip_summary_renderer)
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
        self.assertNotIn("OP SHOP PICKUP", final_summary_renderer)

    def test_phase8_opshop_pickup_list_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-pickup-actions.js"
        ).read_text(encoding="utf-8")
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
        self.assertIn("apiExportOpShopPickupRunSheetExcel", actions)
        self.assertIn("exportOpShopRunSheet", actions)
        self.assertIn("updateAssignedDriverSelection", actions)
        self.assertIn("handleCreatePickupTask", actions)
        self.assertIn("handleUpdatePickupTask", actions)
        self.assertIn("handleDeletePickupTask", actions)
        self.assertIn("onOpenOpShopPickupList", task_pool_renderer)
        self.assertIn("Regular OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Count:", task_pool_renderer)
        self.assertIn("Window:", task_pool_renderer)
        self.assertIn("Open List", task_pool_renderer)
        self.assertIn("Export OP SHOP Run Sheet", task_pool_renderer)
        self.assertIn("onExportOpShopRunSheet", task_pool_renderer)
        self.assertIn("opshopRegularListWindowStart", task_pool_renderer)
        self.assertIn("renderOpShopPickupListModal", app_js)
        self.assertIn("onOpenOpShopPickupList: opShopPickupActions.openOpShopPickupList", app_js)
        self.assertIn("onExportOpShopRunSheet: opShopPickupActions.exportOpShopRunSheet", app_js)
        self.assertIn("onUpdateAssignedDriver: opShopPickupActions.updateAssignedDriverSelection", app_js)

        self.assertIn("groupPickupsByDate", modal_renderer)
        self.assertIn("comparePickupsWithinDateGroup", modal_renderer)
        self.assertIn("getAssignedDriverSortName", modal_renderer)
        self.assertIn("getDriverNameById", modal_renderer)
        self.assertIn("compareText(leftDriverName, rightDriverName)", modal_renderer)
        self.assertIn("compareText(left.suburb, right.suburb)", modal_renderer)
        self.assertIn("compareText(left.opshop_name, right.opshop_name)", modal_renderer)
        self.assertIn("compareText(left.pickup_task_id, right.pickup_task_id)", modal_renderer)
        self.assertIn("state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id]", modal_renderer)
        self.assertIn("if (leftDriverName && !rightDriverName)", modal_renderer)
        self.assertIn("if (!leftDriverName && rightDriverName)", modal_renderer)
        self.assertIn("formatDateHeading", modal_renderer)
        self.assertIn("Monday", modal_renderer)
        self.assertIn("opshop-date-group", modal_renderer)
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
        self.assertIn("if (!pickup.assigned_to_locked)", list_item_renderer)
        self.assertIn('editButton.textContent = "Edit"', list_item_renderer)
        self.assertNotIn("Frequency:", list_item_renderer)
        self.assertNotIn("Status:", list_item_renderer)
        self.assertNotIn("Time:", list_item_renderer)
        self.assertNotIn("Phone:", list_item_renderer)
        self.assertNotIn("compact-note", list_item_renderer)
        self.assertNotIn("opshop-pickup-note", list_item_renderer)
        self.assertNotIn('deleteButton.textContent = "Delete"', list_item_renderer)
        self.assertIn("state.drivers", modal_renderer)
        self.assertIn("pickup.default_driver_id", modal_renderer)
        self.assertIn("pickup.assigned_to_locked", modal_renderer)
        self.assertNotIn("createElement(\"table\")", modal_renderer)
        self.assertNotIn('textContent = "Assign"', modal_renderer)
        self.assertNotIn('textContent = "Unassign"', modal_renderer)
        self.assertNotIn("tripSelect", modal_renderer)
        self.assertNotIn("Trip", modal_renderer)
        self.assertNotIn("tripSelect", modal_renderer)
        self.assertNotIn("fetch(", actions)
        self.assertNotIn("fetch(", modal_renderer)

    def test_oncall_opshop_pickup_frontend_contract(self):
        app_js = (FRONTEND_ROOT / "app.js").read_text(encoding="utf-8")
        api_module = (
            FRONTEND_ROOT / "js" / "api" / "manual-dispatch-api.js"
        ).read_text(encoding="utf-8")
        actions = (
            FRONTEND_ROOT / "js" / "actions" / "opshop-oncall-pickup-actions.js"
        ).read_text(encoding="utf-8")
        task_pool_renderer = (
            FRONTEND_ROOT / "js" / "render" / "task-pool-renderer.js"
        ).read_text(encoding="utf-8")
        modal_renderer = (
            FRONTEND_ROOT / "js" / "render" / "opshop-oncall-pickup-list-modal-renderer.js"
        ).read_text(encoding="utf-8")
        selectors = (FRONTEND_ROOT / "js" / "state" / "selectors.js").read_text(encoding="utf-8")
        final_summary_renderer = (
            FRONTEND_ROOT / "js" / "render" / "final-summary-renderer.js"
        ).read_text(encoding="utf-8")

        self.assertIn("apiListOncallOpShopPickupSchedules", api_module)
        self.assertIn("apiCreateOncallOpShopPickup", api_module)
        self.assertIn("apiApplyOncallOpShopPickupAssignments", api_module)
        self.assertIn("/opshop-pickups/oncall", api_module)
        self.assertIn("/opshop-pickups/oncall-assignments/apply", api_module)
        self.assertIn("createOncallOpShopPickupActions", actions)
        self.assertIn("openOncallOpShopPickupList", actions)
        self.assertIn("apiApplyOncallOpShopPickupAssignments", actions)
        self.assertIn("apiCreateOncallOpShopPickup", actions)
        self.assertIn("updateAssignedDriverSelection", actions)
        self.assertIn("WEEKDAY_OFFSETS", actions)
        self.assertIn("candidate.run_day", actions)
        self.assertIn("renderOncallOpShopPickupListModal", app_js)
        self.assertIn("createOncallOpShopPickupActions", app_js)
        self.assertIn("onOpenOncallOpShopPickupList: oncallOpShopPickupActions.openOncallOpShopPickupList", app_js)
        self.assertIn("oncallOpShopPickups: payload.oncall_opshop_pickups || []", app_js)
        self.assertIn("state.oncallOpShopPickups = board.oncallOpShopPickups", app_js)
        self.assertIn("Oncall OP SHOP Pickup List", task_pool_renderer)
        self.assertIn("Oncall OP SHOP Pickup List", modal_renderer)
        self.assertIn("No Oncall OP SHOP pickups added.", modal_renderer)
        self.assertIn("Template", modal_renderer)
        self.assertIn("Pickup Date", modal_renderer)
        self.assertIn("Assigned to", modal_renderer)
        self.assertIn("Notes", modal_renderer)
        self.assertIn("Select Oncall OP SHOP template", modal_renderer)
        self.assertIn("candidate.run_day || \"Gavin\"", modal_renderer)
        self.assertIn("onOpenDetail(pickup.pickup_task_id)", modal_renderer)
        self.assertIn("Past pickup date", modal_renderer)
        self.assertIn("if (!pickup.assigned_to_locked)", modal_renderer)
        self.assertIn("[\"ACTIVE\", \"ASSIGNED\"].includes(pickup.status)", modal_renderer)
        self.assertIn("removes any OP SHOP assignment", modal_renderer)
        self.assertIn("opshop-list-item-suburb", modal_renderer)
        self.assertIn("opshop-list-item-date", modal_renderer)
        self.assertIn("state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id]", modal_renderer)
        self.assertIn("onCloseList: oncallOpShopPickupActions.closeOncallOpShopPickupList", app_js)
        self.assertIn("oncallOpShopPickups", selectors)
        self.assertIn("assigned-opshop-pickups-section", (
            FRONTEND_ROOT / "js" / "render" / "trip-summary-renderer.js"
        ).read_text(encoding="utf-8"))
        self.assertNotIn('textContent = "Assign"', modal_renderer)
        self.assertNotIn('textContent = "Unassign"', modal_renderer)
        self.assertNotIn("tripSelect", modal_renderer)
        self.assertNotIn("Trip dropdown", modal_renderer)
        self.assertNotIn("OP SHOP PICKUP", final_summary_renderer)
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
