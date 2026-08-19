import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class DeliveryAreaFrontendContractTest(unittest.TestCase):
    def test_group_drag_keyboard_detail_and_import_contracts_are_wired(self):
        task_pool = self._read("js/render/delivery/delivery-task-pool-renderer.js")
        order_modal = self._read("js/render/delivery/delivery-order-modal-renderer.js")
        attache_modal = self._read("js/render/delivery/delivery-attache-modal-renderer.js")
        attache_actions = self._read("js/actions/workspace/delivery-attache-actions.js")
        docket_actions = self._read("js/actions/workspace/delivery-docket-actions.js")
        delivery_actions = self._read("js/actions/workspace/delivery-task-pool-actions.js")
        api = self._read("js/api/manual-dispatch/delivery-api.js")

        self.assertLess(task_pool.index('title: "South East"'), task_pool.index('title: "Local"'))
        self.assertIn('title: "Needs Area Review"', task_pool)
        self.assertIn('groups.className = "workspace-delivery-task-pool-groups"', task_pool)
        self.assertIn("sortDeliveryTaskPoolOrders(items)", task_pool)
        self.assertIn('handle.draggable = !busy', task_pool)
        self.assertIn('event.dataTransfer.setData("application/x-manual-dispatch-order"', task_pool)
        self.assertIn("deliveryOrderDragAutoScroll.start()", task_pool)
        self.assertGreaterEqual(task_pool.count("deliveryOrderDragAutoScroll.stop()"), 2)
        self.assertIn('["SOUTHEAST", "Move to South East"]', task_pool)
        self.assertIn('["LOCAL", "Move to Local"]', task_pool)
        self.assertEqual(1, task_pool.count("actions.moveDeliveryOrderToArea(orderId, area)"))

        self.assertIn('"Reset to Automatic"', order_modal)
        self.assertIn("actions.resetDeliveryOrderArea(order.order_id)", order_modal)
        self.assertIn('"Delivery Area (required)"', order_modal)
        self.assertIn('onChange: actions.classifyDeliveryOrderForm', order_modal)

        self.assertIn('createInlineMeta("Delivery Area"', attache_modal)
        self.assertIn('createInlineMeta("Region"', attache_modal)
        self.assertIn("actions.classifyDeliveryAttacheImportRow(row.row_id)", attache_modal)
        self.assertIn("classifyDeliveryDocketImportRow", attache_modal)
        self.assertIn("applyDeliveryAreaClassification", attache_actions)
        self.assertIn("applyDeliveryAreaClassification", docket_actions)

        persistence = delivery_actions.split(
            "async function persistDeliveryOrderArea", 1
        )[1].split("function renderWorkspacePreservingModalScroll", 1)[0]
        self.assertNotIn("loadDeliveryRoute", persistence)
        self.assertIn("Object.assign(order, previous)", persistence)
        self.assertIn("context.deliveryAreaMutationVersions", persistence)
        self.assertIn("/delivery-area", api)
        self.assertIn("/delivery/area-classification", api)

    def test_delivery_drag_auto_scroll_direction_lifecycle_and_cleanup(self):
        module_uri = (
            FRONTEND_ROOT / "js/utils/delivery-drag-auto-scroll.js"
        ).as_uri()
        self._run_node(
            f"""
            const {{
              createDeliveryDragAutoScroll,
              deliveryDragScrollVelocity,
            }} = await import({module_uri!r});

            class FakeEventTarget {{
              constructor() {{ this.listeners = new Map(); }}
              addEventListener(type, listener) {{
                if (!this.listeners.has(type)) this.listeners.set(type, new Set());
                this.listeners.get(type).add(listener);
              }}
              removeEventListener(type, listener) {{
                this.listeners.get(type)?.delete(listener);
              }}
              dispatch(type, event = {{}}) {{
                for (const listener of [...(this.listeners.get(type) || [])]) {{
                  listener(event);
                }}
              }}
              count(type) {{ return this.listeners.get(type)?.size || 0; }}
            }}

            const events = new FakeEventTarget();
            const windowEvents = new FakeEventTarget();
            const frames = new Map();
            const scrollCalls = [];
            let nextFrameId = 1;
            let scrollTop = 500;
            const controller = createDeliveryDragAutoScroll({{
              eventTarget: events,
              windowTarget: windowEvents,
              getViewportHeight: () => 800,
              getScrollState: () => ({{ scrollTop, maxScrollTop: 1000 }}),
              scrollBy: (deltaY) => {{
                scrollCalls.push(deltaY);
                scrollTop = Math.max(0, Math.min(1000, scrollTop + deltaY));
              }},
              requestFrame: (callback) => {{
                const id = nextFrameId++;
                frames.set(id, callback);
                return id;
              }},
              cancelFrame: (id) => frames.delete(id),
            }});
            const runFrame = (timestamp) => {{
              const entry = frames.entries().next().value;
              if (!entry) throw new Error("expected a pending animation frame");
              const [id, callback] = entry;
              frames.delete(id);
              callback(timestamp);
            }};

            events.dispatch("dragover", {{ clientY: 799 }});
            if (frames.size || scrollCalls.length) {{
              throw new Error("auto-scroll ran without an active Delivery drag");
            }}

            controller.start();
            if (!controller.isActive()
                || events.count("dragover") !== 1
                || events.count("dragend") !== 1
                || events.count("drop") !== 1
                || windowEvents.count("blur") !== 1) {{
              throw new Error("Delivery drag did not install one tracking lifecycle");
            }}

            events.dispatch("dragover", {{ clientY: 400 }});
            if (frames.size) throw new Error("middle viewport position scheduled scrolling");

            events.dispatch("dragover", {{ clientY: 750 }});
            const callsBeforeBottomPrime = scrollCalls.length;
            runFrame(0);
            if (scrollCalls.length !== callsBeforeBottomPrime || frames.size !== 1) {{
              throw new Error("first RAF scrolled without an elapsed timestamp delta");
            }}
            runFrame(1000 / 60);
            const slowerDown = scrollCalls.at(-1);
            if (!(slowerDown > 0) || frames.size !== 1) {{
              throw new Error("bottom edge did not start continuous downward scrolling");
            }}
            events.dispatch("dragover", {{ clientY: 795 }});
            runFrame(1000 / 30);
            const fasterDown = scrollCalls.at(-1);
            if (!(fasterDown > slowerDown)) {{
              throw new Error("scroll speed did not increase closer to the bottom edge");
            }}

            events.dispatch("dragover", {{ clientY: 400 }});
            if (frames.size) throw new Error("leaving the edge zone did not cancel scrolling");
            const callCountAfterLeave = scrollCalls.length;

            events.dispatch("dragover", {{ clientY: 30 }});
            const callsBeforeTopPrime = scrollCalls.length;
            runFrame(100);
            if (scrollCalls.length !== callsBeforeTopPrime || frames.size !== 1) {{
              throw new Error("edge re-entry reused a stale RAF timestamp");
            }}
            runFrame(100 + (1000 / 60));
            if (!(scrollCalls.at(-1) < 0)) {{
              throw new Error("top edge did not request upward scrolling");
            }}
            if (scrollCalls.length !== callCountAfterLeave + 1) {{
              throw new Error("top edge produced duplicate scrolling in one frame");
            }}

            events.dispatch("dragover", {{ clientY: 400 }});
            scrollTop = 0;
            const callsAtTopLimit = scrollCalls.length;
            events.dispatch("dragover", {{ clientY: 0 }});
            runFrame(200);
            if (scrollCalls.length !== callsAtTopLimit || frames.size) {{
              throw new Error("top boundary left a jittering or runaway scroll loop");
            }}
            scrollTop = 1000;
            const callsAtBottomLimit = scrollCalls.length;
            events.dispatch("dragover", {{ clientY: 800 }});
            runFrame(300);
            if (scrollCalls.length !== callsAtBottomLimit || frames.size) {{
              throw new Error("bottom boundary left a jittering or runaway scroll loop");
            }}

            events.dispatch("dragend");
            if (controller.isActive() || frames.size
                || events.count("dragover") || events.count("dragend")
                || events.count("drop") || windowEvents.count("blur")) {{
              throw new Error("dragend did not fully clean up auto-scroll");
            }}

            controller.start();
            controller.start();
            if (events.count("dragover") !== 1 || events.count("drop") !== 1) {{
              throw new Error("repeated drags duplicated global listeners");
            }}
            events.dispatch("dragover", {{ clientY: 799 }});
            if (frames.size !== 1) throw new Error("repeated drag created duplicate RAF loops");
            events.dispatch("drop");
            if (controller.isActive() || frames.size || events.count("dragover")) {{
              throw new Error("drop did not fully clean up auto-scroll");
            }}

            controller.start();
            events.dispatch("dragover", {{ clientY: 1 }});
            windowEvents.dispatch("blur");
            if (controller.isActive() || frames.size) {{
              throw new Error("drag cancellation/loss did not stop auto-scroll");
            }}

            if (deliveryDragScrollVelocity(400, 800) !== 0
                || !(deliveryDragScrollVelocity(1, 800) < 0)
                || !(deliveryDragScrollVelocity(799, 800) > 0)) {{
              throw new Error("edge velocity contract is incorrect");
            }}
            """
        )

    def test_delivery_drag_auto_scroll_is_frame_rate_independent(self):
        module_uri = (
            FRONTEND_ROOT / "js/utils/delivery-drag-auto-scroll.js"
        ).as_uri()
        self._run_node(
            f"""
            const {{
              createDeliveryDragAutoScroll,
              DELIVERY_DRAG_MAX_FRAME_DELTA_MS,
              DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND,
            }} = await import({module_uri!r});

            class FakeEventTarget {{
              constructor() {{ this.listeners = new Map(); }}
              addEventListener(type, listener) {{
                if (!this.listeners.has(type)) this.listeners.set(type, new Set());
                this.listeners.get(type).add(listener);
              }}
              removeEventListener(type, listener) {{
                this.listeners.get(type)?.delete(listener);
              }}
              dispatch(type, event = {{}}) {{
                for (const listener of [...(this.listeners.get(type) || [])]) {{
                  listener(event);
                }}
              }}
            }}

            function simulate(frameTimestamps, clientY) {{
              const events = new FakeEventTarget();
              const windowEvents = new FakeEventTarget();
              const scrollCalls = [];
              let scrollTop = 10000;
              let pendingFrame = null;
              let pendingFrameId = null;
              let nextFrameId = 1;
              const controller = createDeliveryDragAutoScroll({{
                eventTarget: events,
                windowTarget: windowEvents,
                getViewportHeight: () => 800,
                getScrollState: () => ({{ scrollTop, maxScrollTop: 50000 }}),
                scrollBy: (deltaY) => {{
                  scrollCalls.push(deltaY);
                  scrollTop += deltaY;
                }},
                requestFrame: (callback) => {{
                  if (pendingFrame) throw new Error("duplicate RAF loop scheduled");
                  pendingFrameId = nextFrameId++;
                  pendingFrame = callback;
                  return pendingFrameId;
                }},
                cancelFrame: (frameId) => {{
                  if (frameId === pendingFrameId) {{
                    pendingFrame = null;
                    pendingFrameId = null;
                  }}
                }},
              }});
              const runFrame = (timestamp) => {{
                if (!pendingFrame) throw new Error("expected pending RAF callback");
                const callback = pendingFrame;
                pendingFrame = null;
                pendingFrameId = null;
                callback(timestamp);
              }};

              controller.start();
              events.dispatch("dragover", {{ clientY }});
              frameTimestamps.forEach(runFrame);
              controller.stop();
              return {{
                distance: scrollTop - 10000,
                scrollCalls,
              }};
            }}

            const sixtyHz = simulate(
              Array.from({{ length: 61 }}, (_, index) => index * (1000 / 60)),
              800,
            );
            const oneTwentyHz = simulate(
              Array.from({{ length: 121 }}, (_, index) => index * (1000 / 120)),
              800,
            );
            if (!(sixtyHz.distance > 0) || !(oneTwentyHz.distance > 0)) {{
              throw new Error("equivalent elapsed time lost downward direction");
            }}
            if (Math.abs(sixtyHz.distance - oneTwentyHz.distance) > 0.5) {{
              throw new Error(
                `frame-rate dependent distance: 60Hz=${{sixtyHz.distance}}, 120Hz=${{oneTwentyHz.distance}}`,
              );
            }}
            if (Math.abs(sixtyHz.distance - DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND) > 0.5) {{
              throw new Error(`one-second distance exceeded velocity bound: ${{sixtyHz.distance}}`);
            }}

            const upward = simulate(
              Array.from({{ length: 61 }}, (_, index) => index * (1000 / 60)),
              0,
            );
            if (!(upward.distance < 0)
                || Math.abs(Math.abs(upward.distance) - sixtyHz.distance) > 0.5) {{
              throw new Error("time-based upward direction or magnitude is incorrect");
            }}

            const delayed = simulate([0, 1000], 800);
            const maximumDelayedJump = (
              DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND
              * DELIVERY_DRAG_MAX_FRAME_DELTA_MS
              / 1000
            );
            if (!(delayed.distance > 0)
                || delayed.distance > maximumDelayedJump + 0.01
                || delayed.scrollCalls.length !== 1) {{
              throw new Error(`delayed frame was not clamped: ${{JSON.stringify(delayed)}}`);
            }}
            """
        )

    def test_optimistic_move_noop_reset_and_failure_rollback(self):
        module_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-task-pool-actions.js"
        ).as_uri()
        self._run_node(
            f"""
            const {{ createDeliveryTaskPoolActions }} = await import({module_uri!r});

            function createOrder() {{
              return {{
                order_id: "ORD-AREA",
                company_name: "Preserved Customer",
                auto_delivery_region: "SOUTHEAST",
                auto_delivery_area: "SOUTHEAST",
                delivery_area_override: null,
                delivery_area: "SOUTHEAST",
                delivery_area_source: "AUTO",
              }};
            }}

            function createHarness(updateImpl) {{
              const order = createOrder();
              const filters = {{ search: "customer", delivery_date: "2026-08-20", urgency: "Urgent" }};
              const drafts = {{ "ORD-AREA": {{ driver_id: "D001", trip_no: "trip2" }} }};
              const state = {{
                workspaceRoute: "delivery/task-pool",
                activeWorkspace: "delivery",
                dispatchDate: "2026-08-20",
                isLoggedIn: true,
                authSessionVersion: 1,
                deliveryBoard: {{ orders: [order], assignments: [] }},
                deliveryTaskPoolFilters: filters,
                deliveryAssignmentDrafts: drafts,
                deliveryBusyActionKeys: {{}},
                deliveryActionError: "",
              }};
              const calls = [];
              let boardLoads = 0;
              let routeLoads = 0;
              let renders = 0;
              const context = {{
                state,
                api: {{
                  updateDeliveryOrderArea: async (orderId, area) => {{
                    calls.push([orderId, area, order.delivery_area, order.delivery_area_source]);
                    return updateImpl(orderId, area, order);
                  }},
                  getDeliveryWorkspaceBoard: async () => {{ boardLoads += 1; }},
                }},
                renderWorkspace: () => {{ renders += 1; }},
                confirmAction: () => true,
                navigateWorkspaceRoute: () => {{}},
                deliveryAreaMutationVersions: {{}},
                deliveryOrderAreaClassificationVersion: 0,
                actions: {{}},
              }};
              context.actions.currentDeliveryBoard = () => state.deliveryBoard;
              context.actions.renderDeliveryWorkspacePreservingScroll = () => {{ renders += 1; }};
              context.actions.loadDeliveryRoute = async () => {{ routeLoads += 1; }};
              context.actions.runDeliveryAction = async (_key, callback, onError) => {{
                renders += 1;
                try {{ await callback({{ route: state.workspaceRoute }}); }}
                catch (error) {{ onError(error); }}
                finally {{ renders += 1; }}
              }};
              context.actions.isDeliveryMutationCurrent = () => true;
              context.actions.pruneDeliveryVehicleDrafts = () => {{}};
              context.actions.invalidateDeliveryAttachePreview = () => {{}};
              context.actions.dispatchMetadataForContext = () => ({{}});
              context.actions.defaultDeliveryAttacheImportState = () => ({{}});
              return {{
                actions: createDeliveryTaskPoolActions(context),
                boardLoads: () => boardLoads,
                calls,
                drafts,
                filters,
                order,
                renders: () => renders,
                routeLoads: () => routeLoads,
                state,
              }};
            }}

            const success = createHarness(async (_orderId, area) => area === null
              ? {{
                  auto_delivery_region: "SOUTHEAST",
                  auto_delivery_area: "SOUTHEAST",
                  delivery_area_override: null,
                  delivery_area: "SOUTHEAST",
                  delivery_area_source: "AUTO",
                }}
              : {{
                  auto_delivery_region: "SOUTHEAST",
                  auto_delivery_area: "SOUTHEAST",
                  delivery_area_override: area,
                  delivery_area: area,
                  delivery_area_source: "MANUAL",
                }});
            await success.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            if (success.calls.length !== 1 || success.calls[0].join("|") !== "ORD-AREA|LOCAL|LOCAL|MANUAL") {{
              throw new Error("PATCH did not observe the optimistic manual state");
            }}
            if (success.order.delivery_area !== "LOCAL"
                || success.order.delivery_area_override !== "LOCAL"
                || success.order.delivery_area_source !== "MANUAL") {{
              throw new Error("successful move did not retain canonical manual state");
            }}
            if (success.state.deliveryTaskPoolFilters !== success.filters
                || success.state.deliveryAssignmentDrafts !== success.drafts
                || success.order.company_name !== "Preserved Customer") {{
              throw new Error("area move disturbed filters, drafts, or unrelated order fields");
            }}
            if (success.boardLoads() || success.routeLoads()) {{
              throw new Error("successful move reloaded the board or route");
            }}
            await success.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            if (success.calls.length !== 1) throw new Error("same-area move called the API");

            await success.actions.resetDeliveryOrderArea("ORD-AREA");
            if (success.calls.length !== 2 || success.calls[1][1] !== null) {{
              throw new Error("Reset to Automatic did not PATCH null");
            }}
            if (success.order.delivery_area !== "SOUTHEAST"
                || success.order.delivery_area_override !== null
                || success.order.delivery_area_source !== "AUTO") {{
              throw new Error("Reset to Automatic did not restore automatic fields");
            }}

            const failure = createHarness(async () => {{ throw new Error("network down"); }});
            const before = JSON.stringify(failure.order);
            await failure.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            if (JSON.stringify(failure.order) !== before) {{
              throw new Error("failed move did not restore the exact prior order fields");
            }}
            if (!failure.state.deliveryActionError.includes("previous area has been restored")) {{
              throw new Error("failed move did not expose a clear rollback error");
            }}
            if (failure.boardLoads() || failure.routeLoads()) {{
              throw new Error("failed move reloaded the board or route");
            }}

            const partial = createHarness(async (_orderId, area) => ({{
              delivery_area_override: area,
              delivery_area: area,
              delivery_area_source: "MANUAL",
            }}));
            await partial.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            if (partial.order.auto_delivery_region !== "SOUTHEAST"
                || partial.order.auto_delivery_area !== "SOUTHEAST") {{
              throw new Error("omitted response properties erased known automatic state");
            }}

            const explicitNull = createHarness(async (_orderId, area) => ({{
              auto_delivery_region: null,
              auto_delivery_area: null,
              delivery_area_override: area,
              delivery_area: area,
              delivery_area_source: "MANUAL",
            }}));
            await explicitNull.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            if (explicitNull.order.auto_delivery_region !== null
                || explicitNull.order.auto_delivery_area !== null) {{
              throw new Error("explicit null response properties were not applied");
            }}

            const pending = [];
            const stale = createHarness((_orderId, area) => new Promise((resolve, reject) => {{
              pending.push({{ area, resolve, reject }});
            }}));
            const moveA = stale.actions.moveDeliveryOrderToArea("ORD-AREA", "LOCAL");
            const moveB = stale.actions.moveDeliveryOrderToArea("ORD-AREA", "SOUTHEAST");
            pending[1].resolve({{
              auto_delivery_region: "SOUTHEAST",
              auto_delivery_area: "SOUTHEAST",
              delivery_area_override: "SOUTHEAST",
              delivery_area: "SOUTHEAST",
              delivery_area_source: "MANUAL",
            }});
            await moveB;
            pending[0].reject(new Error("late failure from Move A"));
            await moveA;
            if (stale.order.delivery_area !== "SOUTHEAST"
                || stale.order.delivery_area_override !== "SOUTHEAST"
                || stale.order.delivery_area_source !== "MANUAL") {{
              throw new Error("late Move A failure rolled back the newer Move B state");
            }}
            """
        )

    def test_409_is_rolled_back_before_generic_migration_guard(self):
        task_pool_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-task-pool-actions.js"
        ).as_uri()
        busy_uri = (
            FRONTEND_ROOT / "js/actions/workspace/workspace-busy-actions.js"
        ).as_uri()
        self._run_node(
            f"""
            const {{ createDeliveryTaskPoolActions }} = await import({task_pool_uri!r});
            const {{ createWorkspaceBusyActions }} = await import({busy_uri!r});

            let reloads = 0;
            globalThis.window = {{ location: {{ reload: () => {{ reloads += 1; }} }} }};

            async function runCase({{ autoArea, autoRegion, previousArea, targetArea }}) {{
              const order = {{
                order_id: "ORD-AREA-409",
                company_name: "Preserved Customer",
                auto_delivery_region: autoRegion,
                auto_delivery_area: autoArea,
                delivery_area_override: previousArea,
                delivery_area: previousArea,
                delivery_area_source: "MANUAL",
              }};
              const previous = JSON.stringify(order);
              const filters = {{ search: "keep", delivery_date: "2026-08-20", urgency: "Urgent" }};
              const drafts = {{ "ORD-AREA-409": {{ driver_id: "D001", trip_no: "trip2" }} }};
              const state = {{
                workspaceRoute: "delivery/task-pool",
                activeWorkspace: "delivery",
                dispatchDate: "2026-08-20",
                isLoggedIn: true,
                authSessionVersion: 1,
                deliveryBoard: {{ orders: [order], assignments: [] }},
                deliveryTaskPoolFilters: filters,
                deliveryAssignmentDrafts: drafts,
                deliveryBusyActionKeys: {{}},
                deliveryActionError: "",
              }};
              let boardLoads = 0;
              let routeLoads = 0;
              let guardCalls = 0;
              let guardObservedState = "";
              let preservingRenders = 0;
              let token = 0;
              const context = {{
                state,
                api: {{
                  updateDeliveryOrderArea: async () => {{
                    const error = new Error("Order is reserved by a generated Run Sheet");
                    error.status = 409;
                    throw error;
                  }},
                  getDeliveryWorkspaceBoard: async () => {{ boardLoads += 1; }},
                }},
                renderWorkspace: () => {{}},
                confirmAction: () => true,
                navigateWorkspaceRoute: () => {{}},
                deliveryAreaMutationVersions: {{}},
                deliveryOrderAreaClassificationVersion: 0,
                actions: {{}},
              }};
              context.actions.currentDeliveryBoard = () => state.deliveryBoard;
              context.actions.renderDeliveryWorkspacePreservingScroll = () => {{
                preservingRenders += 1;
              }};
              context.actions.loadDeliveryRoute = async () => {{ routeLoads += 1; }};
              context.actions.captureMutationContext = () => ({{
                route: state.workspaceRoute,
                dispatchDate: state.dispatchDate,
                activeWorkspace: state.activeWorkspace,
                authSessionVersion: state.authSessionVersion,
              }});
              context.actions.nextActionToken = () => `token-${{++token}}`;
              context.actions.isDeliveryMutationCurrent = () => true;
              context.actions.handleWorkspaceMigrationGuard = async (error) => {{
                guardCalls += 1;
                guardObservedState = JSON.stringify(order);
                return error.status === 409;
              }};
              context.actions.pruneDeliveryVehicleDrafts = () => {{}};
              context.actions.invalidateDeliveryAttachePreview = () => {{}};
              context.actions.dispatchMetadataForContext = () => ({{}});
              context.actions.defaultDeliveryAttacheImportState = () => ({{}});
              context.actions.runDeliveryAction = createWorkspaceBusyActions(
                context,
              ).runDeliveryAction;

              const actions = createDeliveryTaskPoolActions(context);
              await actions.moveDeliveryOrderToArea("ORD-AREA-409", targetArea);

              if (guardCalls !== 1 || guardObservedState !== previous) {{
                throw new Error("generic 409 guard ran before the optimistic state was restored");
              }}
              if (JSON.stringify(order) !== previous) {{
                throw new Error("409 left the Order in the optimistic Delivery Area");
              }}
              if (state.deliveryTaskPoolFilters !== filters
                  || state.deliveryAssignmentDrafts !== drafts) {{
                throw new Error("409 rollback disturbed filters or assignment drafts");
              }}
              if (boardLoads || routeLoads || reloads) {{
                throw new Error("409 rollback reloaded the board, route, or page");
              }}
              if (preservingRenders < 3) {{
                throw new Error("409 rollback did not use the scroll-preserving render path");
              }}
            }}

            await runCase({{
              autoArea: "SOUTHEAST",
              autoRegion: "SOUTHEAST",
              previousArea: "LOCAL",
              targetArea: "SOUTHEAST",
            }});
            await runCase({{
              autoArea: "LOCAL",
              autoRegion: "WEST",
              previousArea: "SOUTHEAST",
              targetArea: "LOCAL",
            }});

            delete globalThis.window;
            """
        )

    def test_attache_row_reclassification_preserves_warnings_and_drops_stale_results(self):
        module_uri = (
            FRONTEND_ROOT / "js/actions/workspace/delivery-attache-actions.js"
        ).as_uri()
        self._run_node(
            f"""
            const {{ createDeliveryAttacheActions }} = await import({module_uri!r});
            const reviewWarning = "Delivery area could not be determined from suburb/postcode. Needs Review.";
            const state = {{
              isLoggedIn: true,
              authSessionVersion: 1,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-08-20",
              deliveryDocumentImportState: {{ source: "attache" }},
              deliveryAttacheImportState: {{
                isOpen: true,
                rows: [{{
                  row_id: "ROW-1",
                  suburb: "Sunshine",
                  postcode: "3020",
                  warnings: ["Keep parser warning", reviewWarning],
                }}],
              }},
            }};
            let classify = async (suburb) => suburb === "Sunshine"
              ? {{ known: true, auto_delivery_region: "WEST", auto_delivery_area: "LOCAL", delivery_area: "LOCAL" }}
              : {{ known: false, auto_delivery_region: null, auto_delivery_area: null, delivery_area: null }};
            let renders = 0;
            const context = {{
              state,
              api: {{ classifyDeliveryArea: (...args) => classify(...args) }},
              renderWorkspace: () => {{ renders += 1; }},
              confirmAction: () => true,
              navigateWorkspaceRoute: () => {{}},
              deliveryAttachePreviewRequestVersion: 0,
              deliveryAttacheAreaClassificationVersions: {{}},
              actions: {{}},
            }};
            context.actions.captureMutationContext = () => ({{
              route: state.workspaceRoute,
              dispatchDate: state.dispatchDate,
              activeWorkspace: state.activeWorkspace,
              authSessionVersion: state.authSessionVersion,
            }});
            context.actions.isDeliveryMutationCurrent = () => true;
            const actions = createDeliveryAttacheActions(context);

            await actions.classifyDeliveryAttacheImportRow("ROW-1");
            let row = state.deliveryAttacheImportState.rows[0];
            if (row.delivery_area !== "LOCAL" || row.auto_delivery_region !== "WEST") {{
              throw new Error("known import row was not reclassified");
            }}
            if (row.warnings.join("|") !== "Keep parser warning") {{
              throw new Error("known reclassification removed unrelated warnings or kept review warning");
            }}

            actions.updateDeliveryAttacheImportRow("ROW-1", "suburb", "Unknown Place");
            await actions.classifyDeliveryAttacheImportRow("ROW-1");
            row = state.deliveryAttacheImportState.rows[0];
            if (row.delivery_area !== null
                || row.warnings.filter((warning) => warning === reviewWarning).length !== 1
                || !row.warnings.includes("Keep parser warning")) {{
              throw new Error("unknown reclassification did not preserve warnings exactly once");
            }}

            const pending = [];
            classify = () => new Promise((resolve) => pending.push(resolve));
            actions.updateDeliveryAttacheImportRow("ROW-1", "suburb", "Box Hill");
            actions.updateDeliveryAttacheImportRow("ROW-1", "postcode", "3128");
            const oldRequest = actions.classifyDeliveryAttacheImportRow("ROW-1");
            actions.updateDeliveryAttacheImportRow("ROW-1", "suburb", "Sunshine");
            actions.updateDeliveryAttacheImportRow("ROW-1", "postcode", "3020");
            const newRequest = actions.classifyDeliveryAttacheImportRow("ROW-1");
            pending[1]({{ known: true, auto_delivery_region: "WEST", auto_delivery_area: "LOCAL", delivery_area: "LOCAL" }});
            await newRequest;
            pending[0]({{ known: true, auto_delivery_region: "EAST", auto_delivery_area: "SOUTHEAST", delivery_area: "SOUTHEAST" }});
            await oldRequest;
            row = state.deliveryAttacheImportState.rows[0];
            if (row.delivery_area !== "LOCAL" || row.auto_delivery_region !== "WEST") {{
              throw new Error("stale import row classification overwrote the latest location");
            }}
            if (renders !== 3) {{
              throw new Error(`unexpected import reclassification render count: ${{renders}}`);
            }}
            """
        )

    def _run_node(self, body):
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", textwrap.dedent(body)],
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
