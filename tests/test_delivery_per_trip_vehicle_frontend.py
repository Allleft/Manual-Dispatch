import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
HELPERS = r"""
globalThis.window = {
  MANUAL_DISPATCH_API_BASE_URL: "",
  location: { protocol: "http:", origin: "http://127.0.0.1" },
};
const utils = await import(__UTILS__);
const { createDeliveryVehicleQueue } = await import(__QUEUE__);
const { createWorkspaceAsyncGuards } = await import(__GUARDS__);
const { deliveryVehicleKey: key, getDeliveryVehicleConflictDriverNames: conflicts } = utils;
const date = "2026-09-15";
const row = (driver, trip, vehicle) => ({ delivery_date: date, driver_id: driver, trip_no: trip, vehicle_id: vehicle });
function assert(value, message = "contract failed") { if (!value) throw new Error(message); }
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }
function board(rows = [], legacy = []) {
  return {
    drivers: [{ driver_id: "A", name: "John" }, { driver_id: "B", name: "Gavin" }],
    orders: [], assignments: [], driver_vehicle_assignments: rows, legacy_driver_vehicle_assignments: legacy,
  };
}
function stateFor(rows = [], legacy = []) {
  return {
    isLoggedIn: true, authSessionVersion: 1, activeWorkspace: "delivery", workspaceRoute: "delivery/trip-summary",
    dispatchDate: date, deliveryTripSummaryDate: date, deliveryBoard: board(rows, legacy),
    deliveryVehicleDrafts: {}, deliveryVehicleClaims: {}, deliveryVehicleClaimSequence: 0,
    deliveryVehiclePendingKeys: {}, deliveryVehicleErrors: {},
  };
}
function queueFor(state, api = {}) {
  const persisted = [...state.deliveryBoard.driver_vehicle_assignments];
  const defaultApi = {
    assignDeliveryWorkspaceVehicle: async (payload) => {
      const index = persisted.findIndex((item) => item.driver_id === payload.driver_id && item.trip_no === payload.trip_no);
      if (index >= 0) persisted.splice(index, 1);
      persisted.push(row(payload.driver_id, payload.trip_no, payload.vehicle_id));
      return board([...persisted]);
    },
    clearDeliveryWorkspaceVehicle: async (payload) => {
      const index = persisted.findIndex((item) => item.driver_id === payload.driver_id && item.trip_no === payload.trip_no);
      if (index >= 0) persisted.splice(index, 1);
      return board([...persisted]);
    },
  };
  const navigation = [];
  const context = {
    state, api: { ...defaultApi, ...api }, renderWorkspace() {}, actions: {},
    deliveryVehicleMutationVersion: 0, deliveryVehicleQueueIdCounter: 0,
    deliveryVehicleQueues: new Map(), deliveryVehiclePhysicalTails: new Map(),
  };
  context.actions.currentDeliveryBoard = () => state.deliveryTripSummaryBoard || state.deliveryBoard;
  context.actions.loadMigrationStatusForHome = async (message) => {
    navigation.push(message); state.workspaceRoute = "home"; state.activeWorkspace = "";
  };
  Object.assign(context.actions, createWorkspaceAsyncGuards(context));
  const actions = createDeliveryVehicleQueue(context);
  return { actions, context, navigation };
}
"""
for marker, name in (
    ("__UTILS__", "utils/delivery-vehicle-utils.js"),
    ("__QUEUE__", "actions/workspace/delivery-vehicle-queue.js"),
    ("__GUARDS__", "actions/workspace/workspace-async-guards.js"),
):
    HELPERS = HELPERS.replace(marker, repr((JS / name).as_uri()))


class DeliveryPerTripVehicleFrontendTest(unittest.TestCase):
    def run_node(self, body):
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", HELPERS + "\n" + textwrap.dedent(body)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_keys_require_trip_and_parse_centrally(self):
        self.run_node("""
            assert(key(date, "A", "trip1") === date + "|A|trip1");
            assert(key(date, "A", "trip1") !== key(date, "A", "trip2"));
            assert(utils.parseDeliveryVehicleKey(key(date, "A", "trip2")).tripNo === "trip2");
            for (const value of [null, "", "trip3"]) {
              let rejected = false;
              try { key(date, "A", value); } catch { rejected = true; }
              assert(rejected);
            }
            assert(utils.parseDeliveryVehicleKey(date + "|A") === null);
            assert(utils.parseDeliveryVehicleKey(date + "|A|trip1|extra") === null);
        """)

    def test_trip_drafts_and_physical_tails_are_independent(self):
        self.run_node("""
            const state = stateFor(), first = deferred(), second = deferred(), writes = [];
            const { actions, context } = queueFor(state, {
              assignDeliveryWorkspaceVehicle: async (payload) => {
                writes.push(payload);
                await (payload.trip_no === "trip1" ? first.promise : second.promise);
                return board([row("A", payload.trip_no, payload.vehicle_id)]);
              },
            });
            const one = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            const two = actions.updateDeliveryVehicleSelection(date, "A", "trip2", "V2");
            assert(state.deliveryVehicleDrafts[key(date, "A", "trip1")] === "V1");
            assert(state.deliveryVehicleDrafts[key(date, "A", "trip2")] === "V2");
            assert(writes.length === 2 && context.deliveryVehiclePhysicalTails.size === 2);
            first.resolve(); await one; second.resolve(); await two;
            assert(state.deliveryBoard.driver_vehicle_assignments.length === 2);
        """)

    def test_pending_trip1_does_not_mark_trip2_pending(self):
        self.run_node("""
            const state = stateFor(), gate = deferred();
            const { actions } = queueFor(state, { assignDeliveryWorkspaceVehicle: async () => { await gate.promise; return board([row("A", "trip1", "V1")]); } });
            const pending = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            assert(state.deliveryVehiclePendingKeys[key(date, "A", "trip1")]);
            assert(!state.deliveryVehiclePendingKeys[key(date, "A", "trip2")]);
            gate.resolve(); await pending;
        """)

    def test_trip1_error_preserves_trip2_error_and_stays_on_page(self):
        self.run_node("""
            const state = stateFor();
            state.deliveryVehicleErrors[key(date, "A", "trip2")] = "trip2 failure";
            const error = Object.assign(new Error("Vehicle already assigned"), { status: 409, code: "state_changed_conflict" });
            const { actions, navigation } = queueFor(state, { assignDeliveryWorkspaceVehicle: async () => { throw error; } });
            await actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            assert(state.deliveryVehicleErrors[key(date, "A", "trip1")] === error.message);
            assert(state.deliveryVehicleErrors[key(date, "A", "trip2")] === "trip2 failure");
            assert(navigation.length === 0 && state.workspaceRoute === "delivery/trip-summary");
        """)

    def test_claims_conflict_only_in_same_trip_and_date(self):
        self.run_node("""
            const claims = {
              [key(date, "A", "trip1")]: { vehicle_id: "V1", sequence: 1 },
              [key(date, "B", "trip1")]: { vehicle_id: "V1", sequence: 2 },
            };
            const input = { board: board(), claims, deliveryDate: date, driverId: "B", vehicleId: "V1" };
            assert(conflicts({ ...input, tripNo: "trip1" }).join() === "John");
            assert(conflicts({ ...input, tripNo: "trip2" }).length === 0);
            assert(conflicts({ ...input, deliveryDate: "2026-09-16", tripNo: "trip1" }).length === 0);
        """)

    def test_persisted_conflict_only_in_same_trip_null_ignored(self):
        self.run_node("""
            const input = { board: board([row("A", "trip1", "V1")], [row("A", null, "V2")]),
              deliveryDate: date, driverId: "B", vehicleId: "V1", claims: {} };
            assert(conflicts({ ...input, tripNo: "trip1" }).join() === "John");
            assert(conflicts({ ...input, tripNo: "trip2" }).length === 0);
            assert(conflicts({ ...input, tripNo: "trip1", vehicleId: "V2" }).length === 0);
            assert(!utils.getDeliveryTripVehicleAssignment(input.board, date, "A", "trip2"));
        """)

    def test_assign_response_merge_preserves_sibling_and_other_driver(self):
        self.run_node("""
            const state = stateFor([row("A", "trip1", "OLD"), row("A", "trip2", "TWO"), row("B", "trip2", "OTHER")]);
            const { actions } = queueFor(state);
            actions.applyDeliveryVehicleBoardUpdate(board([row("A", "trip1", "NEW"), row("A", "trip2", "STALE")]), date, "A", "trip1");
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip1").vehicle_id === "NEW");
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip2").vehicle_id === "TWO");
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "B", "trip2").vehicle_id === "OTHER");
        """)

    def test_clear_response_merge_preserves_sibling_and_null(self):
        self.run_node("""
            const state = stateFor([row("A", "trip1", "ONE"), row("A", "trip2", "TWO")], [row("A", null, "OLD")]);
            const { actions } = queueFor(state);
            actions.applyDeliveryVehicleBoardUpdate(board(), date, "A", "trip1");
            assert(!utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip1"));
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip2").vehicle_id === "TWO");
            assert(state.deliveryBoard.legacy_driver_vehicle_assignments[0].vehicle_id === "OLD");
        """)

    def test_queue_payload_and_clear_include_selected_trip(self):
        self.run_node("""
            const state = stateFor(), writes = [];
            const { actions } = queueFor(state, {
              assignDeliveryWorkspaceVehicle: async (payload) => { writes.push(payload); return board([row("A", payload.trip_no, payload.vehicle_id)]); },
              clearDeliveryWorkspaceVehicle: async (payload) => { writes.push(payload); return board(); },
            });
            await actions.updateDeliveryVehicleSelection(date, "A", "trip2", "V1");
            await actions.updateDeliveryVehicleSelection(date, "A", "trip2", "");
            assert(writes.length === 2 && writes.every((payload) => payload.trip_no === "trip2"));
        """)

    def test_retry_claims_respects_trip_scope(self):
        self.run_node("""
            const state = stateFor([row("A", "trip1", "V1")]), writes = [];
            const { actions } = queueFor(state, {
              assignDeliveryWorkspaceVehicle: async (payload) => { writes.push(payload); return board([row(payload.driver_id, payload.trip_no, payload.vehicle_id)]); },
            });
            await actions.updateDeliveryVehicleSelection(date, "B", "trip1", "V1");
            assert(writes.length === 0);
            await actions.updateDeliveryVehicleSelection(date, "B", "trip2", "V1");
            assert(writes.length === 1 && writes[0].trip_no === "trip2");
            state.deliveryBoard.driver_vehicle_assignments = [];
            actions.retryAvailableDeliveryVehicleClaims();
            await flush();
            assert(writes.length === 2 && writes[1].trip_no === "trip1");
        """)

    def test_prune_preserves_valid_sibling_state_and_discards_old_keys(self):
        self.run_node("""
            const state = stateFor([row("A", "trip1", "SAVED")]);
            state.deliveryVehicleDrafts = { [key(date, "A", "trip1")]: "SAVED", [key(date, "A", "trip2")]: "DRAFT", [date + "|A"]: "OLD" };
            state.deliveryVehicleClaims = { [key(date, "A", "trip2")]: { vehicle_id: "DRAFT", sequence: 2 } };
            state.deliveryVehicleErrors = { [key(date, "A", "trip2")]: "sibling", [date + "|A"]: "old" };
            const { actions } = queueFor(state);
            actions.pruneDeliveryVehicleDrafts();
            assert(!Object.hasOwn(state.deliveryVehicleDrafts, key(date, "A", "trip1")));
            assert(state.deliveryVehicleDrafts[key(date, "A", "trip2")] === "DRAFT");
            assert(state.deliveryVehicleClaims[key(date, "A", "trip2")].vehicle_id === "DRAFT");
            assert(Object.keys(state.deliveryVehicleErrors).join() === key(date, "A", "trip2"));
        """)

    def test_same_trip_latest_intent_stays_serial(self):
        self.run_node("""
            const state = stateFor(), gate = deferred(), writes = [];
            const { actions } = queueFor(state, {
              assignDeliveryWorkspaceVehicle: async (payload) => { writes.push(payload.vehicle_id); if (writes.length === 1) await gate.promise; return board([row("A", "trip1", payload.vehicle_id)]); },
            });
            const one = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
            const two = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V2");
            assert(writes.join() === "V1");
            gate.resolve(); await Promise.all([one, two]);
            assert(writes.join() === "V1,V2");
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip1").vehicle_id === "V2");
        """)

    def test_route_exit_stale_response_and_physical_tail_preserved(self):
        self.run_node("""
            const state = stateFor(), gate = deferred(), writes = [];
            const { actions, context } = queueFor(state, {
              assignDeliveryWorkspaceVehicle: async (payload) => { writes.push(payload.vehicle_id); if (writes.length === 1) await gate.promise; return board([row("A", "trip1", payload.vehicle_id)]); },
            });
            const old = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "OLD");
            actions.clearDeliveryVehicleTransientState();
            assert(context.deliveryVehiclePhysicalTails.size === 1);
            const next = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "NEW");
            assert(writes.join() === "OLD");
            gate.resolve(); await Promise.all([old, next]);
            assert(utils.getDeliveryTripVehicleAssignment(state.deliveryBoard, date, "A", "trip1").vehicle_id === "NEW");
            assert(Object.keys(state.deliveryVehicleDrafts).length === 0);
        """)

    def test_auth_and_date_changes_ignore_stale_success_and_failure(self):
        self.run_node("""
            for (const mode of ["auth", "date", "logout"]) {
              for (const fail of [true, false]) {
                const state = stateFor(), gate = deferred();
                const { actions, navigation } = queueFor(state, { assignDeliveryWorkspaceVehicle: async () => {
                  await gate.promise;
                  if (fail) throw Object.assign(new Error("migration"), { status: 409, code: "workspace_migration_required" });
                  return board([row("A", "trip1", "OLD")]);
                } });
                const pending = actions.updateDeliveryVehicleSelection(date, "A", "trip1", "OLD");
                if (mode === "auth") state.authSessionVersion++;
                if (mode === "date") state.deliveryTripSummaryDate = "2026-09-16";
                if (mode === "logout") state.isLoggedIn = false;
                gate.resolve(); await pending;
                assert(state.deliveryBoard.driver_vehicle_assignments.length === 0);
                assert(navigation.length === 0 && Object.keys(state.deliveryVehicleErrors).length === 0);
              }
            }
        """)

    def test_migration_code_triggers_guard_business_and_locks_do_not(self):
        self.run_node("""
            for (const code of ["workspace_migration_required", "state_changed_conflict", "delivery_run_sheet_locked", undefined]) {
              const state = stateFor();
              const { actions, navigation } = queueFor(state, { assignDeliveryWorkspaceVehicle: async () => {
                throw Object.assign(new Error("409"), { status: 409, code });
              } });
              await actions.updateDeliveryVehicleSelection(date, "A", "trip1", "V1");
              assert(navigation.length === (code === "workspace_migration_required" ? 1 : 0));
            }
        """)

    def test_day_queue_entrypoint_is_retired(self):
        self.run_node("""
            const { actions } = queueFor(stateFor());
            assert(!Object.hasOwn(actions, "updateDeliveryDayVehicleSelection"));
        """)

    def test_new_trip_reads_never_project_sibling_or_null(self):
        self.run_node("""
            const selected = board([row("A", "trip1", "V1"), row("A", "trip2", "V2")]);
            assert(utils.getDeliveryTripVehicleAssignment(selected, date, "A", "trip1").vehicle_id === "V1");
            assert(utils.getDeliveryTripVehicleAssignment(selected, date, "A", "trip2").vehicle_id === "V2");
            assert(!utils.getDeliveryTripVehicleAssignment(board([], [row("A", null, "V1")]), date, "A", "trip1"));
            assert(!Object.hasOwn(utils, "getDeliveryDayVehicleAssignment"));
        """)

    def test_client_serializes_trip_and_propagates_error_code(self):
        api_uri = (JS / "api/manual-dispatch/delivery-api.js").as_uri()
        self.run_node("""
            const calls = [];
            globalThis.fetch = async (url, options) => {
              calls.push({ url, body: JSON.parse(options.body) });
              return { ok: true, json: async () => board() };
            };
            const api = await import(API_URI);
            await api.apiAssignDeliveryWorkspaceVehicle({ delivery_date: date, driver_id: "A", trip_no: "trip2", vehicle_id: "V1" });
            await api.apiClearDeliveryWorkspaceVehicle({ delivery_date: date, driver_id: "A", trip_no: "trip1" });
            assert(calls[0].body.trip_no === "trip2" && calls[1].body.trip_no === "trip1");
            assert(!Object.hasOwn(api, "apiAssignDeliveryDayVehicle"));
            globalThis.fetch = async () => ({ ok: false, status: 409, headers: { get: () => "workspace_migration_required" },
              json: async () => ({ detail: "Migration needed" }) });
            let error;
            try { await api.apiAssignDeliveryWorkspaceVehicle({ trip_no: "trip1" }); } catch (caught) { error = caught; }
            assert(error.code === "workspace_migration_required" && error.status === 409 && error.detail === "Migration needed");
        """.replace("API_URI", repr(api_uri)))

    def test_visible_layout_owns_vehicle_control_per_trip(self):
        source = (JS / "render/delivery/delivery-trip-summary-renderer.js").read_text(encoding="utf-8")
        self.assertIn("actions.updateDeliveryVehicleSelection(", source)
        self.assertNotIn("createDriverVehicleControl", source)
        panel = source.split("export function createTripPanel", 1)[1].split("export function createAssignedOrderRow", 1)[0]
        self.assertIn("createTripVehicleControl", panel)


if __name__ == "__main__":
    unittest.main()
