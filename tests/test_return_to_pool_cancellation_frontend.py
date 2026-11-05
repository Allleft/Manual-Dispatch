import subprocess
import textwrap
import unittest
from pathlib import Path

from tests.test_delivery_order_lookup_frontend import DOM


ROOT = Path(__file__).resolve().parents[1]
SETUP = r"""
const { createDeliveryOrderModal, deliveryOrderActionLocks } = await import('./frontend/js/render/delivery/delivery-order-modal-renderer.js');
const { createDeliveryTaskPoolActions } = await import('./frontend/js/actions/workspace/delivery-task-pool-actions.js');
const order = {order_id: 'RTP', status: 'ACTIVE', company_name: 'Synthetic', product_lines: []};
const history = (status = 'SAVED', execution_status = 'CLOSED') => [{status, execution_status, trips: [{orders: [{task_id: 'RTP'}]}]}];
const eligible = {order_id: 'RTP', can_cancel: true, has_run_sheet_history: true, returned_to_pool: true, reason: ''};
function harness(api = {}, confirm = true) {
  const state = {isLoggedIn: true, authSessionVersion: 1, workspaceRoute: 'delivery/task-pool',
    deliveryOrderDetailId: '', deliveryOrderFormMode: '', deliveryOrderModalError: '',
    deliveryBoard: {orders: [order], drivers: [], assignments: []}, deliveryRunSheets: history()};
  const calls = {renders: 0, posts: 0, refresh: 0, prompts: []};
  const context = {state, api: {
    getDeliveryOrderCancellationEligibility: async () => eligible,
    cancelDeliveryOrder: async () => { calls.posts++; }, ...api,
  }, confirmAction: text => { calls.prompts.push(text); return confirm; },
  renderWorkspace: () => calls.renders++, navigateWorkspaceRoute() {}, actions: {
    currentDeliveryBoard: () => state.deliveryBoard,
    isDeliveryMutationCurrent: () => true,
    loadDeliveryRoute: async route => { assert.equal(route, 'delivery/task-pool'); calls.refresh++; },
    runDeliveryAction: async (_, work, failure) => {
      try { await work({route: state.workspaceRoute}); } catch (error) { failure(error); }
    },
  }};
  const actions = createDeliveryTaskPoolActions(context);
  return {state, calls, actions};
}
const buttons = modal => Object.fromEntries(modal.querySelector('.workspace-modal-action-bar').querySelectorAll('button').map(button => [button.textContent.trim(), button]));
"""


class ReturnToPoolCancellationFrontendTest(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(["node", "--input-type=module", "-e", DOM + SETUP + textwrap.dedent(script)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_generated_saved_open_and_recaptured_cancel_disabled(self):
        self.run_node("""
            for (const [status, execution] of [['GENERATED', 'OPEN'], ['SAVED', 'OPEN']]) {
              const {state, actions} = harness({getDeliveryOrderCancellationEligibility: async () => ({...eligible,
                can_cancel: false, reason: 'Reserved by a Generated or Saved/Open Delivery Run Sheet.'})});
              state.deliveryRunSheets = history(status, execution);
              await actions.openDeliveryOrderDetail('RTP');
              const modal = createDeliveryOrderModal(state, actions);
              assert.equal(buttons(modal)['Cancel Order'].disabled, true);
              assert.equal(buttons(modal)['Edit Order'].disabled, true);
              assert.match(modal.textContent, /Reserved by/);
            }
        """)

    def test_returned_cancel_enabled_edit_and_reset_still_locked(self):
        self.run_node("""
            for (const cached of [[], history(), history('GENERATED', 'OPEN')]) {
              const {state, actions} = harness(); state.deliveryRunSheets = cached;
              order.delivery_area_source = 'MANUAL';
              await actions.openDeliveryOrderDetail('RTP');
              const modal = createDeliveryOrderModal(state, actions); const controls = buttons(modal);
              assert.equal(controls['Cancel Order'].disabled, false);
              assert.equal(controls['Edit Order'].disabled, true);
              assert.equal(controls['Reset to Automatic'].disabled, true);
              assert.match(modal.textContent, /Editing remains locked, but the order can be cancelled/);
              assert.doesNotMatch(modal.textContent, /Edit and Cancel are locked/);
            }
        """)

    def test_finalized_and_reassigned_cannot_enable_cancel(self):
        self.run_node("""
            const response = {...eligible, orderId: 'RTP'};
            const finalized = deliveryOrderActionLocks({...order, status: 'FINALIZED'}, {}, history(), response);
            assert.equal(finalized.cancelLocked, true); assert.match(finalized.message, /FINALIZED/);
            const reassigned = deliveryOrderActionLocks(order, {assignments: [{task_type: 'ORDER', task_id: 'RTP'}]}, [], response);
            assert.equal(reassigned.cancelLocked, true); assert.match(reassigned.message, /unassigned/);
        """)

    def test_ordinary_active_order_has_no_lock_banner(self):
        self.run_node("""
            const {state, actions} = harness({getDeliveryOrderCancellationEligibility: async () => ({...eligible,
              has_run_sheet_history: false, returned_to_pool: false})});
            state.deliveryRunSheets = [];
            await actions.openDeliveryOrderDetail('RTP');
            const modal = createDeliveryOrderModal(state, actions);
            assert.equal(buttons(modal)['Cancel Order'].disabled, false);
            assert.equal(buttons(modal)['Edit Order'].disabled, false);
            assert.doesNotMatch(modal.textContent, /locked|Checking cancellation/);
        """)

    def test_pending_failure_and_invalid_payload_fail_closed(self):
        self.run_node("""
            for (const getter of [async () => { throw Error('offline'); }, async () => ({...eligible, order_id: 'wrong'})]) {
              const {state, actions} = harness({getDeliveryOrderCancellationEligibility: getter});
              const pending = actions.openDeliveryOrderDetail('RTP');
              assert.equal(buttons(createDeliveryOrderModal(state, actions))['Cancel Order'].disabled, true);
              await pending;
              const modal = createDeliveryOrderModal(state, actions);
              assert.equal(buttons(modal)['Cancel Order'].disabled, true);
              assert.match(modal.textContent, /Unable to verify cancellation eligibility/);
            }
        """)

    def test_confirmation_decline_sends_no_cancellation(self):
        self.run_node("""
            const {actions, calls} = harness({}, false);
            await actions.openDeliveryOrderDetail('RTP'); await actions.cancelActiveDeliveryOrder('RTP');
            assert.deepEqual(calls.prompts, ['Cancel this Delivery Order? It will disappear from the active Task Pool.']);
            assert.equal(calls.posts, 0); assert.equal(calls.refresh, 0);
        """)

    def test_success_closes_modal_and_refreshes_task_pool(self):
        self.run_node("""
            const {actions, calls, state} = harness();
            await actions.openDeliveryOrderDetail('RTP'); await actions.cancelActiveDeliveryOrder('RTP');
            assert.equal(calls.posts, 1); assert.equal(calls.refresh, 1); assert.equal(calls.prompts.length, 1);
            assert.equal(state.deliveryOrderDetailId, ''); assert.equal(state.deliveryOrderModalError, '');
        """)

    def test_backend_failure_is_visible_and_modal_remains_open(self):
        self.run_node("""
            const {actions, calls, state} = harness({cancelDeliveryOrder: async () => { throw Error('New reservation'); }});
            await actions.openDeliveryOrderDetail('RTP'); await actions.cancelActiveDeliveryOrder('RTP');
            assert.equal(state.deliveryOrderDetailId, 'RTP'); assert.equal(calls.refresh, 0);
            assert.match(createDeliveryOrderModal(state, actions).textContent, /Unable to cancel Delivery Order. New reservation/);
        """)

    def test_stale_eligibility_responses_cannot_reopen_or_overwrite(self):
        self.run_node("""
            for (const change of ['close', 'auth', 'route', 'reopen']) {
              let resolve; const {actions, state} = harness({getDeliveryOrderCancellationEligibility: () => new Promise(done => {resolve = done;})});
              const first = actions.openDeliveryOrderDetail('RTP'); const finish = resolve;
              if (change === 'close' || change === 'reopen') actions.closeDeliveryOrderModal();
              if (change === 'auth') state.authSessionVersion++;
              if (change === 'route') state.workspaceRoute = 'delivery/history';
              if (change === 'reopen') actions.openDeliveryOrderDetail('RTP');
              const current = state.deliveryOrderCancellation;
              finish(eligible); await first;
              assert.equal(state.deliveryOrderCancellation, current);
              if (change === 'close') assert.equal(state.deliveryOrderDetailId, '');
            }
        """)

    def test_readonly_details_make_no_eligibility_request(self):
        self.run_node("""
            let requests = 0; const {state, actions} = harness({getDeliveryOrderCancellationEligibility: async () => {requests++; return eligible;}});
            await actions.openDeliveryOrderDetail('RTP', {readOnly: true});
            assert.equal(requests, 0);
            assert.deepEqual(Object.keys(buttons(createDeliveryOrderModal(state, actions))), ['Close']);
        """)
