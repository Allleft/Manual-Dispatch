import subprocess
import textwrap
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

from tests.test_delivery_per_trip_vehicle_frontend import HELPERS, JS, ROOT


ACTION_HELPERS = HELPERS + "\n" + r"""
const { createDeliveryRunSheetActions } = await import(__RUN_ACTIONS__);
const { createWorkspaceBusyActions } = await import(__BUSY__);
const { findRunSheetForDriverTrip } = await import(__RENDER_UTILS__);
function candidate(trip = "trip1", vehicle = "") {
  return { delivery_date: date, driver_id: "A", trip_no: trip, vehicle_id: vehicle,
    orders: [{ order_id: trip === "trip1" ? "ORDER-A" : "ORDER-B", trip_no: trip }], totals: {} };
}
function actionsFor(state, api = {}) {
  const { actions: queue, context } = queueFor(state, api);
  context.actionTokenCounter = 0;
  Object.assign(context.actions, queue, createWorkspaceBusyActions(context));
  context.actions.loadDeliveryRoute = async () => { throw new Error("Generation must not reset sibling state"); };
  context.api.createGeneratedDeliveryRunSheet ||= async (payload) => ({ ...payload, run_sheet_id: "RS-" + payload.trip_no, status: "GENERATED" });
  Object.assign(context.actions, createDeliveryRunSheetActions(context));
  return { actions: context.actions, context };
}
"""
for marker, name in (
    ("__RUN_ACTIONS__", "actions/workspace/delivery-run-sheet-actions.js"),
    ("__BUSY__", "actions/workspace/workspace-busy-actions.js"),
    ("__RENDER_UTILS__", "render/delivery/delivery-renderer-utils.js"),
):
    ACTION_HELPERS = ACTION_HELPERS.replace(marker, repr((JS / name).as_uri()))


class DeliveryPerTripRunSheetFrontendTest(unittest.TestCase):
    def run_node(self, body):
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", ACTION_HELPERS + "\n" + textwrap.dedent(body)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_lock_lookup_matches_exact_trip_and_null_wildcard(self):
        self.run_node("""
            const sheet = { delivery_date: date, driver_id: "A", trip_no: "trip1", status: "SAVED", execution_status: "CLOSED" };
            assert(findRunSheetForDriverTrip([sheet], date, "A", "trip1") === sheet);
            assert(!findRunSheetForDriverTrip([sheet], date, "A", "trip2"));
            const legacy = { ...sheet, trip_no: null };
            for (const trip of ["trip1", "trip2"]) assert(findRunSheetForDriverTrip([legacy], date, "A", trip) === legacy);
        """)

    def test_generating_trip1_does_not_mark_trip2_busy(self):
        self.run_node("""
            const state = stateFor(), gate = deferred(), calls = [];
            const { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => {
              calls.push(payload); await gate.promise; return { ...payload, run_sheet_id: "RS1", status: "GENERATED" };
            } });
            actions.generateDeliveryRunSheet(candidate());
            const pending = actions.confirmGenerateDeliveryRunSheet(); await flush();
            assert(actions.isDeliveryGenerationBusy(candidate("trip1")));
            assert(!actions.isDeliveryGenerationBusy(candidate("trip2")));
            assert(calls[0].trip_no === "trip1"); gate.resolve(); await pending;
        """)

    def test_trip2_generation_payload_is_explicit(self):
        self.run_node("""
            const state = stateFor(), calls = [];
            const { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => {
              calls.push(payload); return { ...payload, run_sheet_id: "RS2", status: "GENERATED" };
            } });
            actions.generateDeliveryRunSheet(candidate("trip2")); await actions.confirmGenerateDeliveryRunSheet();
            assert(calls.length === 1 && calls[0].trip_no === "trip2");
        """)

    def test_missing_trip_candidate_is_not_defaulted(self):
        self.run_node("""
            const state = stateFor(), { actions } = actionsFor(state);
            for (const trip of [null, "", "trip3"]) {
              actions.generateDeliveryRunSheet(candidate(trip));
              assert(!state.deliveryGenerationConfirmation);
            }
            const missing = candidate(); delete missing.trip_no;
            actions.generateDeliveryRunSheet(missing); assert(!state.deliveryGenerationConfirmation);
        """)

    def test_pending_vehicle_waits_before_generation_and_uses_persisted_selection(self):
        self.run_node("""
            const state = stateFor(), gate = deferred(), calls = [];
            const { actions } = actionsFor(state, {
              assignDeliveryWorkspaceVehicle: async () => { await gate.promise; return board([row("A", "trip1", "V1")]); },
              createGeneratedDeliveryRunSheet: async payload => {
                assert(state.deliveryBoard.driver_vehicle_assignments[0].vehicle_id === "V1");
                calls.push(payload); return { ...payload, run_sheet_id: "RS1", status: "GENERATED" };
              },
            });
            const vehicle = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            actions.generateDeliveryRunSheet(candidate("trip1", "V1"));
            const generating = actions.confirmGenerateDeliveryRunSheet(); await flush();
            assert(calls.length === 0); gate.resolve(); await vehicle; await generating;
            assert(calls.length === 1);
        """)

    def test_failed_vehicle_queue_cannot_be_swallowed_then_generate(self):
        self.run_node("""
            const state = stateFor(), calls = [];
            const { actions } = actionsFor(state, {
              assignDeliveryWorkspaceVehicle: async () => { throw new Error("Vehicle write failed"); },
              createGeneratedDeliveryRunSheet: async payload => { calls.push(payload); },
            });
            await actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            actions.generateDeliveryRunSheet(candidate("trip1", "V1")); await actions.confirmGenerateDeliveryRunSheet();
            assert(calls.length === 0 && state.deliveryGenerationConfirmation.error === "Vehicle write failed");
        """)

    def test_conflicted_vehicle_selection_prevents_generation(self):
        self.run_node("""
            const state = stateFor([row("B", "trip1", "V1")]), calls = [];
            const { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => calls.push(payload) });
            await actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            actions.generateDeliveryRunSheet(candidate("trip1", "V1")); await actions.confirmGenerateDeliveryRunSheet();
            assert(calls.length === 0 && state.deliveryGenerationConfirmation.error.includes("conflicts"));
        """)

    def test_unpersisted_draft_and_orphan_pending_block_generation(self):
        self.run_node("""
            for (const condition of ["draft", "pending"]) {
              const state = stateFor(), calls = [], { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => calls.push(payload) });
              if (condition === "draft") state.deliveryVehicleDrafts[key(date, "A", "trip1")] = "V1";
              else state.deliveryVehiclePendingKeys[key(date, "A", "trip1")] = true;
              actions.generateDeliveryRunSheet(candidate("trip1", "V1")); await actions.confirmGenerateDeliveryRunSheet();
              assert(calls.length === 0 && state.deliveryGenerationConfirmation.error);
            }
        """)

    def test_sibling_pending_or_error_does_not_block_generation(self):
        self.run_node("""
            const state = stateFor(), { actions } = actionsFor(state);
            state.deliveryVehiclePendingKeys[key(date, "A", "trip2")] = true;
            state.deliveryVehicleErrors[key(date, "A", "trip2")] = "Sibling error";
            actions.generateDeliveryRunSheet(candidate()); await actions.confirmGenerateDeliveryRunSheet();
            assert(state.deliveryTripSummaryRunSheets[0].trip_no === "trip1");
            assert(state.deliveryVehicleErrors[key(date, "A", "trip2")] === "Sibling error");
        """)

    def test_changed_vehicle_after_preview_requires_review(self):
        self.run_node("""
            const state = stateFor([row("A", "trip1", "V2")]), calls = [];
            const { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => calls.push(payload) });
            actions.generateDeliveryRunSheet(candidate("trip1", "V1")); await actions.confirmGenerateDeliveryRunSheet();
            assert(calls.length === 0 && state.deliveryGenerationConfirmation.error.includes("Vehicle changed"));
        """)

    def test_date_or_auth_change_while_vehicle_pending_aborts_generation(self):
        self.run_node("""
            for (const change of ["date", "auth"]) {
              const state = stateFor(), gate = deferred(), calls = [];
              const { actions } = actionsFor(state, {
                assignDeliveryWorkspaceVehicle: async () => { await gate.promise; return board([row("A", "trip1", "V1")]); },
                createGeneratedDeliveryRunSheet: async payload => calls.push(payload),
              });
              const vehicle = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
              actions.generateDeliveryRunSheet(candidate("trip1", "V1")); const generating = actions.confirmGenerateDeliveryRunSheet();
              if (change === "date") state.deliveryTripSummaryDate = "2026-09-16"; else state.authSessionVersion++;
              gate.resolve(); await vehicle; await generating; assert(calls.length === 0);
            }
        """)

    def test_generation_response_preserves_sibling_sheet_draft_and_confirmation(self):
        self.run_node("""
            const state = stateFor(), gate = deferred();
            const sibling = { run_sheet_id: "SIBLING", trip_no: "trip2", status: "SAVED" };
            state.deliveryTripSummaryRunSheets = [sibling];
            const { actions } = actionsFor(state, { createGeneratedDeliveryRunSheet: async payload => {
              await gate.promise; return { ...payload, run_sheet_id: "RS1", status: "GENERATED" };
            } });
            actions.generateDeliveryRunSheet(candidate()); const pending = actions.confirmGenerateDeliveryRunSheet(); await flush();
            actions.generateDeliveryRunSheet(candidate("trip2")); const confirmation = state.deliveryGenerationConfirmation;
            state.deliveryVehicleDrafts[key(date, "A", "trip2")] = "V2";
            gate.resolve(); await pending;
            assert(state.deliveryTripSummaryRunSheets.includes(sibling));
            assert(state.deliveryTripSummaryRunSheets.length === 2);
            assert(state.deliveryGenerationConfirmation === confirmation);
            assert(state.deliveryVehicleDrafts[key(date, "A", "trip2")] === "V2");
        """)


RUNTIME_SETUP = r"""async () => {
  window.summary = await import('/js/render/delivery/delivery-trip-summary-renderer.js');
  window.preview = await import('/js/render/delivery/delivery-generation-modal-renderer.js');
  window.documents = await import('/js/render/delivery/delivery-run-sheet-renderer.js');
  window.historyView = await import('/js/render/delivery/delivery-history-renderer.js');
  window.date = '2026-09-15'; window.calls = [];
  window.board = { drivers: [{ driver_id: 'A', name: 'John', is_available: true }, { driver_id: 'B', name: 'Gavin' }],
    vehicles: [{ vehicle_id: 'V1', rego: 'TRUCK A', pallet_capacity: 8 }, { vehicle_id: 'V2', rego: 'TRUCK B', pallet_capacity: 10 }],
    orders: [1,2].map(n => ({ order_id: 'ORDER-'+n, invoice_number: 'INV-'+n, company_name: 'Customer '+n,
      delivery_date: date, delivery_address: n+' Test Road', suburb: 'Dandenong', pallet_quantity: n,
      loose_bags_quantity: n*2, carton_quantity: n*3, product_lines: [] })),
    assignments: [1,2].map(n => ({ task_id: 'ORDER-'+n, task_type: 'ORDER', driver_id: 'A', trip_no: 'trip'+n })),
    driver_vehicle_assignments: [1,2].map(n => ({ delivery_date: date, driver_id: 'A', trip_no: 'trip'+n, vehicle_id: 'V'+n })) };
  window.state = { dispatchDate: date, deliveryTripSummaryDate: date, deliveryTripSummaryRunSheets: [], deliveryBusyActionKeys: {},
    deliveryVehicleDrafts: {}, deliveryVehiclePendingKeys: {}, deliveryVehicleErrors: {}, deliveryVehicleClaims: {} };
  window.actions = new Proxy({}, { get: (_, name) => (...args) => { calls.push([name, ...args]);
    if (name === 'generateDeliveryRunSheet') state.deliveryGenerationConfirmation = args[0]; } });
  window.render = () => document.body.replaceChildren(summary.createDeliveryTripSummary(board, state, actions));
  window.sheet = (trip, status='GENERATED') => ({ run_sheet_id: 'RS-'+(trip || 'LEGACY'), delivery_date: date, dispatch_date: date,
    driver_id: 'A', driver_name_snapshot: 'John', trip_no: trip, status, execution_status: 'OPEN',
    generated_at: date+'T09:00:00Z', vehicle_rego_snapshot: trip === 'trip2' ? 'TRUCK B' : 'TRUCK A',
    total_pallets: trip === 'trip2' ? 2 : 1, total_loose_bags: 0, total_cartons: 0,
    trips: (trip ? [trip] : ['trip1','trip2']).map(t => ({ trip_no: t, orders: [{ row_id: 'ROW-'+t,
      trip_no: t, row_no: 1, invoice_number_snapshot: t === 'trip1' ? 'INV-1' : 'INV-2',
      company_name_snapshot: t === 'trip1' ? 'Customer 1' : 'Customer 2', delivery_address_snapshot: 'Test Road',
      pallet_quantity_snapshot: t === 'trip1' ? 1 : 2, product_lines_snapshot: [] }] })) });
  render();
} """


class DeliveryPerTripRunSheetRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(service_workers="block")
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.route("**/*", self.serve)
        self.page.goto("http://delivery-trip.test/", wait_until="networkidle")
        self.page.evaluate(RUNTIME_SETUP)

    def serve(self, route):
        url = urlsplit(route.request.url)
        if url.hostname != "delivery-trip.test":
            route.abort()
            return
        if url.path == "/":
            route.fulfill(body='<html><head><link rel="stylesheet" href="/styles.css"></head><body></body></html>', content_type="text/html")
            return
        root = ROOT / "frontend"
        path = (root / unquote(url.path).lstrip("/")).resolve()
        types = {".js": "application/javascript", ".css": "text/css"}
        if path.is_relative_to(root) and path.is_file() and path.suffix in types:
            route.fulfill(body=path.read_text(encoding="utf-8"), content_type=types[path.suffix])
        else:
            route.abort()

    def panel(self, trip):
        return self.page.locator(f'.workspace-trip-panel[data-driver-id="A"][data-trip-no="{trip}"]')

    def test_only_per_trip_vehicle_controls_and_no_driver_level_control(self):
        self.assertEqual(4, self.page.locator(".workspace-vehicle-control").count())
        for trip in ("trip1", "trip2"):
            self.assertEqual(1, self.panel(trip).locator("select").count())
        self.assertEqual(0, self.page.locator(".workspace-driver-card > .workspace-vehicle-control").count())
        self.assertEqual([], self.errors)

    def test_trip2_options_include_trip1_vehicle_and_action_contains_trip(self):
        self.assertIn("TRUCK A", self.panel("trip2").locator('option[value="V1"]').inner_text())
        self.panel("trip2").locator("select").select_option("V1")
        self.assertEqual(["updateDeliveryVehicleSelection", "2026-09-15", "A", "trip2", "V1"], self.page.evaluate("calls[0]"))

    def test_conflict_labels_and_warnings_are_same_trip_only(self):
        self.page.evaluate("""() => {
          board.driver_vehicle_assignments.push({ delivery_date: date, driver_id: 'B', trip_no: 'trip2', vehicle_id: 'V1' });
          state.deliveryVehicleDrafts[date+'|A|trip2'] = 'V1'; render();
        }""")
        self.assertNotIn("assigned to Gavin", self.panel("trip1").locator('option[value="V1"]').inner_text())
        self.assertIn("assigned to Gavin", self.panel("trip2").locator('option[value="V1"]').inner_text())
        self.assertEqual(0, self.panel("trip1").locator('[role="alert"]').count())
        self.assertEqual(1, self.panel("trip2").locator('[role="alert"]').count())

    def test_generate_buttons_preview_only_the_selected_trip(self):
        for number in (1, 2):
            self.panel(f"trip{number}").get_by_role("button", name=f"Generate Trip {number} Run Sheet", exact=True).click()
            value = self.page.evaluate("state.deliveryGenerationConfirmation")
            self.assertEqual(f"trip{number}", value["trip_no"])
            self.assertEqual([f"ORDER-{number}"], [order["order_id"] for order in value["orders"]])
            self.assertEqual(number, value["totals"]["pallets"])
            self.assertEqual(f"TRUCK {'A' if number == 1 else 'B'}", value["vehicle"]["rego"])
        self.page.evaluate("document.body.append(preview.createDeliveryGenerationConfirmationModal(state, actions))")
        modal = self.page.locator(".workspace-modal-backdrop")
        self.assertIn("Trip 2", modal.inner_text())
        self.assertIn("Customer 2", modal.inner_text())
        self.assertNotIn("Customer 1", modal.inner_text())

    def test_candidate_defensively_filters_a_mixed_driver_order_list(self):
        value = self.page.evaluate("""() => preview.createDeliveryGenerationCandidate(board.drivers[0], board, date, 'trip1',
          board.orders.map((order, n) => ({ order, assignment: board.assignments[n] })), state)""")
        self.assertEqual(["ORDER-1"], [order["order_id"] for order in value["orders"]])
        self.assertEqual(1, value["totals"]["pallets"])

    def test_trip1_busy_does_not_disable_trip2_generate_or_vehicle(self):
        self.page.evaluate("state.deliveryBusyActionKeys['delivery-generate:'+date+'|A|trip1'] = true; render()")
        self.assertTrue(self.panel("trip1").get_by_role("button", name="Generate Trip 1 Run Sheet").is_disabled())
        self.assertTrue(self.panel("trip1").locator("select").is_disabled())
        self.assertFalse(self.panel("trip2").get_by_role("button", name="Generate Trip 2 Run Sheet").is_disabled())
        self.assertFalse(self.panel("trip2").locator("select").is_disabled())

    def test_trip1_lock_disables_only_its_control_and_source_and_target_moves(self):
        self.page.evaluate("state.deliveryTripSummaryRunSheets = [sheet('trip1')]; render()")
        self.assertTrue(self.panel("trip1").locator("select").is_disabled())
        self.assertFalse(self.panel("trip2").locator("select").is_disabled())
        self.assertTrue(self.panel("trip1").get_by_role("button", name="Move to Trip 2").is_disabled())
        self.assertTrue(self.panel("trip2").get_by_role("button", name="Move to Trip 1").is_disabled())
        self.assertFalse(self.panel("trip2").get_by_role("button", name="Unassign", exact=True).is_disabled())
        self.assertEqual(0, self.panel("trip1").get_by_role("button", name="Generate Trip 1 Run Sheet").count())
        self.assertFalse(self.panel("trip2").get_by_role("button", name="Generate Trip 2 Run Sheet").is_disabled())

    def test_trip2_closed_lock_leaves_trip1_editable(self):
        self.page.evaluate("const closed = sheet('trip2', 'SAVED'); closed.execution_status = 'CLOSED'; state.deliveryTripSummaryRunSheets = [closed]; render()")
        self.assertTrue(self.panel("trip2").locator("select").is_disabled())
        self.assertFalse(self.panel("trip1").locator("select").is_disabled())

    def test_legacy_combined_locks_both_panels(self):
        self.page.evaluate("state.deliveryTripSummaryRunSheets = [sheet(null)]; render()")
        for trip in ("trip1", "trip2"):
            self.assertTrue(self.panel(trip).locator("select").is_disabled())
            self.assertTrue(self.panel(trip).get_by_role("button", name="Unassign", exact=True).is_disabled())
        self.assertEqual(0, self.page.locator('[data-workspace-generate="delivery"]').count())

    def test_pending_or_error_disables_only_affected_trip_generate(self):
        for field, value in (("deliveryVehiclePendingKeys", True), ("deliveryVehicleErrors", "Write failed")):
            self.page.evaluate("""({field, value}) => { state[field][date+'|A|trip1'] = value; render(); }""", {"field": field, "value": value})
            self.assertTrue(self.panel("trip1").get_by_role("button", name="Generate Trip 1 Run Sheet").is_disabled())
            self.assertFalse(self.panel("trip2").get_by_role("button", name="Generate Trip 2 Run Sheet").is_disabled())

    def test_run_sheet_cards_and_paper_distinguish_both_trips_without_dedupe(self):
        self.page.evaluate("document.body.replaceChildren(documents.createRunSheetList([sheet('trip1'), sheet('trip2')], state, actions))")
        cards = self.page.locator(".workspace-run-sheet-document-card")
        self.assertEqual(2, cards.count())
        self.assertEqual(["John — Trip 1", "John — Trip 2"], cards.locator(".workspace-record-card-top > div > h3").all_text_contents())
        self.assertIn("Trip: Trip 1", cards.nth(0).inner_text())
        self.assertIn("Trip: Trip 2", cards.nth(1).inner_text())
        self.assertNotIn("INV-2", cards.nth(0).inner_text())
        self.assertNotIn("INV-1", cards.nth(1).inner_text())

    def test_legacy_combined_card_keeps_identity_and_both_order_rows(self):
        self.page.evaluate("document.body.replaceChildren(documents.createRunSheetList([sheet(null)], state, actions))")
        self.assertEqual("John", self.page.locator(".workspace-run-sheet-document-card .workspace-record-card-top > div > h3").inner_text())
        text = self.page.locator(".workspace-daily-run-sheet").inner_text()
        self.assertNotIn("Trip: Trip", text)
        self.assertIn("INV-1", text)
        self.assertIn("INV-2", text)

    def test_history_keeps_both_saved_sheets_with_trip_identity(self):
        self.page.evaluate("state.deliverySavedHistoryRunSheets = [sheet('trip1', 'SAVED'), sheet('trip2', 'SAVED')]; document.body.replaceChildren(historyView.createSavedRunSheetHistory(state, actions))")
        papers = self.page.locator(".workspace-daily-run-sheet")
        self.assertEqual(2, papers.count())
        self.assertIn("Trip: Trip 1", papers.nth(0).inner_text())
        self.assertIn("Trip: Trip 2", papers.nth(1).inner_text())
        self.assertEqual([], self.errors)
