import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_HARNESS = r"""
import assert from 'node:assert/strict';

class FakeNode {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.className = '';
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.text = '';
    this.classList = {
      add: (...names) => { this.className += ' ' + names.join(' '); },
      toggle: (name, on) => {
        const names = new Set(this.className.split(/\s+/).filter(Boolean));
        if (on) names.add(name); else names.delete(name);
        this.className = [...names].join(' ');
      },
    };
  }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = [...nodes]; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() {
    return this.text + this.children.map(node => node.textContent ?? String(node)).join('');
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  fire(name) {
    for (const listener of this.listeners[name] || []) {
      listener({target: this, stopPropagation() {}});
    }
  }
  querySelectorAll(selector) {
    const matches = node => selector.startsWith('.')
      ? node.className.split(/\s+/).includes(selector.slice(1))
      : node.tagName === selector.toUpperCase();
    const result = [];
    for (const node of this.children) {
      if (!(node instanceof FakeNode)) continue;
      if (matches(node)) result.push(node);
      result.push(...node.querySelectorAll(selector));
    }
    return result;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
globalThis.document = {
  createElement: tag => new FakeNode(tag),
  createElementNS: (_, tag) => new FakeNode(tag),
  createTextNode: text => { const node = new FakeNode('#text'); node.textContent = text; return node; },
  createDocumentFragment: () => new FakeNode('fragment'),
};
globalThis.window = {location: {hostname: 'localhost', origin: 'http://localhost'}};

const drivers = [
  {driver_id: 'D1', name: 'Existing driver', is_available: false},
  {driver_id: 'D2', name: 'Available driver', is_available: true},
  {driver_id: 'D3', name: 'Other unavailable driver', is_available: false},
];
const options = node => node.querySelectorAll('option').map(option => option.value);
"""


class DriverAvailabilityFrontendTest(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(
            ["node", "--input-type=module", "-"],
            input=NODE_HARNESS + textwrap.dedent(script),
            cwd=PROJECT_ROOT / "frontend", text=True, capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_delivery_new_assignment_select_filters_unavailable_and_restores_reenabled_driver(self):
        self.run_node("""
            const {createOrderAssignmentControls} = await import('./js/render/delivery/delivery-task-pool-renderer.js');
            const controls = createOrderAssignmentControls(
              {order_id: 'ORDER'}, {drivers}, {deliveryAssignmentDrafts: {}}, {}
            );
            assert.deepEqual(options(controls.querySelector('select')), ['', 'D2']);
            drivers[0].is_available = true;
            const reenabled = createOrderAssignmentControls(
              {order_id: 'ORDER'}, {drivers}, {deliveryAssignmentDrafts: {}}, {}
            );
            assert.deepEqual(options(reenabled.querySelector('select')), ['', 'D1', 'D2']);
        """)

    def test_pickup_modal_assignment_fields_keep_existing_driver_and_filter_new_choices(self):
        self.run_node("""
            const {state} = await import('./js/state/app-state.js');
            const {renderOncallOpShopPickupListModal} = await import('./js/render/opshop-oncall-pickup-list-modal-renderer.js');
            const {renderCountrysideOpShopPickupListModal} = await import('./js/render/opshop-countryside-pickup-list-modal-renderer.js');
            const pickup = {pickup_task_id: 'PICKUP', driver_id: 'D1', status: 'ASSIGNED',
              run_type: 'ON_CALL', pickup_date: '2026-05-05'};
            Object.assign(state, {activeWorkspace: 'opshop', dispatchDate: '2026-05-05',
              opshopBoard: {drivers, opshop_pickups: [pickup]}, countrysideOpShopPickups: [pickup],
              isOncallOpShopPickupListOpen: true, oncallOpShopPickupFormMode: 'edit',
              oncallOpShopPickupEditingTaskId: 'PICKUP',
              oncallOpShopPickupForm: {assigned_driver_id: 'D1', pickup_date: pickup.pickup_date},
              isCountrysideOpShopPickupListOpen: true, countrysideOpShopPickupFormMode: 'edit',
              countrysideOpShopPickupEditingTaskId: 'PICKUP',
              countrysideOpShopPickupForm: {assigned_driver_id: 'D1', pickup_date: pickup.pickup_date}});
            for (const [render, mode, form] of [
              [renderOncallOpShopPickupListModal, 'oncallOpShopPickupFormMode', 'oncallOpShopPickupForm'],
              [renderCountrysideOpShopPickupListModal, 'countrysideOpShopPickupFormMode', 'countrysideOpShopPickupForm'],
            ]) {
              const root = new FakeNode('div');
              document.querySelector = () => root;
              render({});
              const select = root.querySelectorAll('label')
                .find(label => label.textContent.startsWith('Assigned to')).querySelector('select');
              assert.deepEqual(options(select), ['', 'D1', 'D2']);
              assert.equal(select.value, 'D1');
              assert.equal(select.disabled, false);
              state[mode] = 'add';
              state[form].assigned_driver_id = '';
              root.replaceChildren();
              render({});
              const newAssignment = root.querySelectorAll('label')
                .find(label => label.textContent.startsWith('Assigned')).querySelector('select');
              assert.deepEqual(options(newAssignment), ['', 'D2']);
            }
        """)

    def test_opshop_new_assignment_selects_exclude_unavailable_drivers(self):
        self.run_node("""
            const {createRegularPickupAssignment} = await import('./js/render/opshop/opshop-regular-renderer.js');
            const {createOncallPickupAssignment, createPickupAssignmentControls} = await import('./js/render/opshop/opshop-oncall-renderer.js');
            const pickup = {pickup_task_id: 'PICKUP', run_type: 'ON_CALL', pickup_date: '2026-05-05'};
            const state = {opshopBoard: {drivers}, opshopAssignmentDrafts: {}, dispatchDate: '2026-05-05'};
            for (const render of [createRegularPickupAssignment, createOncallPickupAssignment, createPickupAssignmentControls]) {
              const field = render(pickup, state, {});
              assert.deepEqual(options(field.querySelector('select')), ['', 'D2']);
            }
        """)

    def test_opshop_assigned_unavailable_driver_keeps_name_and_select_value(self):
        self.run_node("""
            const {createRegularPickupAssignment, currentOpShopDriverName} = await import('./js/render/opshop/opshop-regular-renderer.js');
            const pickup = {pickup_task_id: 'PICKUP', driver_id: 'D1', run_type: 'REGULAR'};
            const state = {opshopBoard: {drivers}, opshopAssignmentDrafts: {}};
            const select = createRegularPickupAssignment(pickup, state, {}).querySelector('select');
            assert.equal(select.value, 'D1');
            assert.deepEqual(options(select), ['', 'D1', 'D2']);
            assert.equal(currentOpShopDriverName(pickup, state), 'Existing driver');
        """)

    def test_unavailable_default_driver_is_not_suggested_for_new_pickups(self):
        self.run_node("""
            const {defaultDriverHint} = await import('./js/render/opshop/opshop-renderer-utils.js');
            const pickup = {run_type: 'REGULAR', pickup_date: '2026-05-05',
              default_driver_id: 'D1', default_driver_name: 'Existing driver'};
            const state = {opshopBoard: {drivers}, dispatchDate: '2026-05-05'};
            assert.equal(defaultDriverHint(pickup, state), 'Existing driver unavailable');
            drivers[0].is_available = true;
            assert.equal(defaultDriverHint(pickup, state), 'Existing driver suggested');
        """)

    def test_legacy_pending_new_assignment_is_cleared_when_driver_becomes_unavailable(self):
        self.run_node("""
            const {createAssignmentActions} = await import('./js/actions/assignment-actions.js');
            const {getTaskKey} = await import('./js/state/selectors.js');
            const key = getTaskKey('ORDER', 'ORDER');
            const state = {drivers, orders: [{order_id: 'ORDER'}], opshopPickups: [], assignments: [],
              pendingSelections: {[key]: {driver_id: 'D1', trip_no: 'trip1'}}};
            const actions = createAssignmentActions({state});
            actions.cleanupPendingSelections();
            assert.equal(state.pendingSelections[key].driver_id, '');
        """)

    def test_trip_summary_keeps_unavailable_driver_and_existing_order_actions(self):
        self.run_node("""
            const {createDriverTripSummaryCard} = await import('./js/render/delivery/delivery-trip-summary-renderer.js');
            const board = {drivers, vehicles: [], driver_vehicle_assignments: [],
              assignments: [{task_id: 'ORDER', task_type: 'ORDER', driver_id: 'D1', trip_no: 'trip1'}],
              orders: [{order_id: 'ORDER', company_name: 'Existing customer', delivery_date: '2026-05-05'}]};
            const state = {deliveryTripSummaryRunSheets: [], deliveryVehicleDrafts: {}, deliveryVehicleClaims: {}};
            const card = createDriverTripSummaryCard(drivers[0], board, '2026-05-05', state, {});
            assert(card.textContent.includes('Existing driver'));
            assert(card.textContent.includes('Unavailable'));
            assert(card.textContent.includes('Existing customer'));
            const generate = card.querySelectorAll('button').find(button => button.textContent.includes('Generate Trip 1 Run Sheet'));
            assert(generate && !generate.disabled);
        """)

    def test_specification_checkbox_toggles_and_delete_callback_is_preserved(self):
        self.run_node("""
            const {createDriverSpecificationPanel} = await import('./js/render/delivery/delivery-specification-modal-renderer.js');
            const calls = [];
            const driver = {...drivers[0], is_available: true};
            const panel = createDriverSpecificationPanel({deliverySpecifications: {drivers: [driver]}}, {
              toggleDeliveryDriverAvailability: (...args) => calls.push(['toggle', ...args]),
              deleteDeliveryDriver: id => calls.push(['delete', id]),
            });
            const checkbox = panel.querySelector('input');
            checkbox.checked = false;
            checkbox.fire('change');
            assert.equal(checkbox.checked, false);
            panel.querySelectorAll('button').find(button => button.textContent.includes('Delete')).fire('click');
            assert.deepEqual(calls, [['toggle', 'D1', false], ['delete', 'D1']]);
        """)


if __name__ == "__main__":
    unittest.main()
