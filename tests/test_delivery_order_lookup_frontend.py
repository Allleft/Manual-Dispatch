import re
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


DOM = r"""
import assert from 'node:assert/strict';
class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attributes = {}; this.dataset = {};
    this.listeners = {}; this.value = ''; this.disabled = false; this.scrollTop = 0;
    this.className = ''; this._text = ''; this.parentNode = null;
    this.classList = {
      add: (...names) => { this.className += ' ' + names.join(' '); },
      contains: (name) => this.className.split(/\s+/).includes(name),
    };
  }
  append(...nodes) { nodes.forEach(node => { node.parentNode = this; this.children.push(node); }); }
  replaceChildren(...nodes) { this.children.forEach(node => node.parentNode = null); this.children = []; this.append(...nodes); }
  set textContent(value) { this._text = String(value ?? ''); this.replaceChildren(); }
  get textContent() { return this._text + this.children.map(node => node.textContent).join(' '); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter(item => item !== fn); }
  fire(type, props = {}) { const event = {preventDefault() {}, stopPropagation() {}, ...props}; (this.listeners[type] || []).forEach(fn => fn(event)); }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  focus() { document.activeElement = this; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const matches = node => selector.split(',').some(raw => {
      const item = raw.trim();
      if (item.startsWith('.')) return node.classList.contains(item.slice(1));
      if (item === '[data-find-delivery-invoice]') return 'findDeliveryInvoice' in node.dataset;
      if (item.includes(':not([disabled])')) return node.tagName === item.split(':')[0] && !node.disabled;
      if (item === "button[type='submit']") return node.tagName === 'button' && node.type === 'submit';
      if (item === 'a[href]') return node.tagName === 'a' && !!node.href;
      if (item.startsWith('[tabindex]')) return node.tabIndex != null && node.tabIndex !== -1;
      return node.tagName === item;
    });
    const found = [];
    const visit = node => { if (matches(node)) found.push(node); node.children.forEach(visit); };
    this.children.forEach(visit); return found;
  }
}
const body = new Node('body');
globalThis.document = {
  body, activeElement: null,
  createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag),
  createTextNode: text => { const node = new Node('#text'); node.textContent = text; return node; },
  createDocumentFragment: () => new Node('fragment'),
  querySelector: selector => body.querySelector(selector),
  addEventListener: (...args) => body.addEventListener(...args),
  removeEventListener: (...args) => body.removeEventListener(...args),
};
const timers = [];
globalThis.window = {
  location: { protocol: 'http:', origin: 'http://localhost', hash: '' },
  scrollX: 0, scrollY: 240, setTimeout: fn => timers.push(fn),
  requestAnimationFrame: fn => timers.push(fn),
  scrollTo(x, y) { this.scrollX = x; this.scrollY = y; },
};
const flush = () => { while (timers.length) timers.shift()(); };
const { defaultDeliveryOrderLookupState } = await import('./frontend/js/state/delivery-order-lookup-state.js');
"""


class DeliveryOrderLookupFrontendTest(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(
            ["node", "--input-type=module", "-e", DOM + textwrap.dedent(script)],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_common_header_all_four_routes_without_fifth_tab(self):
        self.run_node("""
            const { createWorkspacePage } = await import('./frontend/js/render/delivery/delivery-workspace-page.js');
            let opened = 0;
            for (const route of ['task-pool', 'trip-summary', 'run-sheet', 'history']) {
              const page = createWorkspacePage({workspaceRoute: 'delivery/' + route}, () => {}, {
                openDeliveryOrderLookup: () => opened++,
              });
              assert.equal(page.querySelectorAll('a').length, 4);
              const button = page.querySelector('[data-find-delivery-invoice]');
              const nav = page.querySelector('nav');
              assert.equal(page.querySelectorAll('[data-find-delivery-invoice]').length, 1);
              assert.equal(button.parentNode, nav);
              assert.equal(page.querySelector('header').contains(button), false);
              assert.equal(button.tagName, 'button');
              assert.equal(button.type, 'button');
              assert.equal(button.classList.contains('button-primary'), true);
              assert.equal(button.classList.contains('workspace-action-button'), true);
              assert.equal(button.classList.contains('workspace-tab'), false);
              assert.equal(button.attributes['aria-current'], undefined);
              const tabs = nav.querySelectorAll('a');
              assert.deepEqual(tabs.map(tab => tab.textContent), ['Task Pool', 'Trip Summary', 'Run Sheets', 'Saved History']);
              assert.equal(tabs.filter(tab => tab.attributes['aria-current'] === 'page').length, 1);
              assert.equal(tabs.find(tab => tab.attributes['aria-current'] === 'page').href, '#delivery/' + route);
              assert.equal(button.textContent, 'Find Invoice'); button.fire('click');
            }
            assert.equal(opened, 4);
        """)

    def test_api_wrapper_uses_get_exact_invoice_without_date(self):
        self.run_node("""
            const { apiLookupDeliveryOrdersByInvoice } = await import('./frontend/js/api/manual-dispatch/delivery-api.js');
            let requested;
            globalThis.fetch = async (url, options) => {
              requested = {url: new URL(url), options};
              return {ok: true, status: 200, json: async () => ({match_count: 0, orders: []})};
            };
            await apiLookupDeliveryOrdersByInvoice('0012&3');
            assert.equal(requested.url.pathname, '/api/manual-dispatch/delivery/orders/lookup');
            assert.deepEqual([...requested.url.searchParams.entries()], [['invoice_number', '0012&3']]);
            assert.equal(requested.options.method || 'GET', 'GET');
        """)

    def test_actions_loading_error_no_match_and_protected_state(self):
        self.run_node("""
            const { createWorkspaceActions } = await import('./frontend/js/actions/workspace-actions.js');
            const drafts = {order: {driver_id: 'draft'}};
            const filters = {search: 'keep me'};
            const state = {isLoggedIn: true, authSessionVersion: 1, workspaceRoute: 'delivery/history',
              dispatchDate: '1990-01-01', deliveryAssignmentDrafts: drafts, deliveryTaskPoolFilters: filters};
            const pending = []; let renders = 0;
            const actions = createWorkspaceActions({state, renderWorkspace: () => renders++, api: {
              lookupDeliveryOrdersByInvoice: query => new Promise((resolve, reject) => pending.push({query, resolve, reject})),
            }});
            actions.openDeliveryOrderLookup();
            assert.equal(state.deliveryOrderLookup.open, true);
            actions.updateDeliveryOrderLookupQuery(' 001234 ');
            const request = actions.searchDeliveryOrderLookup();
            assert.equal(state.deliveryOrderLookup.loading, true);
            await actions.searchDeliveryOrderLookup(); assert.equal(pending.length, 1);
            assert.equal(pending[0].query, '001234');
            pending[0].resolve({invoice_number: '001234', match_count: 0, orders: []}); await request;
            assert.equal(state.deliveryOrderLookup.result.match_count, 0);
            assert.equal(state.deliveryOrderLookup.open, true);
            assert.equal(state.deliveryOrderLookup.loading, false);
            const failure = actions.searchDeliveryOrderLookup(); pending[1].reject(new Error('offline')); await failure;
            assert.match(state.deliveryOrderLookup.error, /offline/);
            assert.equal(state.deliveryOrderLookup.open, true);
            assert.equal(state.workspaceRoute, 'delivery/history'); assert.equal(state.dispatchDate, '1990-01-01');
            assert.equal(state.deliveryAssignmentDrafts, drafts); assert.equal(state.deliveryTaskPoolFilters, filters);
            assert.equal(window.scrollY, 240);
            actions.closeDeliveryOrderLookup(); assert.equal(state.deliveryOrderLookup.open, false);
            assert.equal(state.deliveryOrderLookup.result, null);
            assert.ok(renders >= 5);
        """)

    def test_stale_search_close_reopen_and_logout_responses_ignored(self):
        self.run_node("""
            const { createDeliveryOrderLookupActions } = await import('./frontend/js/actions/workspace/delivery-order-lookup-actions.js');
            const state = {isLoggedIn: true, authSessionVersion: 1};
            const pending = [];
            const actions = createDeliveryOrderLookupActions({state, renderWorkspace() {}, api: {
              lookupDeliveryOrdersByInvoice: query => new Promise((resolve, reject) => pending.push({query, resolve, reject})),
            }});
            actions.openDeliveryOrderLookup(); actions.updateDeliveryOrderLookupQuery('old');
            const old = actions.searchDeliveryOrderLookup();
            actions.updateDeliveryOrderLookupQuery('new'); const newer = actions.searchDeliveryOrderLookup();
            pending[1].resolve({invoice_number: 'new'}); await newer;
            pending[0].resolve({invoice_number: 'old'}); await old;
            assert.equal(state.deliveryOrderLookup.result.invoice_number, 'new');
            const closing = actions.searchDeliveryOrderLookup(); actions.closeDeliveryOrderLookup(); actions.openDeliveryOrderLookup();
            pending[2].reject(new Error('late error')); await closing;
            assert.equal(state.deliveryOrderLookup.error, ''); assert.equal(state.deliveryOrderLookup.result, null);
            actions.updateDeliveryOrderLookupQuery('logout'); const logout = actions.searchDeliveryOrderLookup();
            state.authSessionVersion++; state.isLoggedIn = false; state.deliveryOrderLookup = defaultDeliveryOrderLookupState();
            pending[3].resolve({invoice_number: 'logout'}); await logout;
            assert.equal(state.deliveryOrderLookup.open, false); assert.equal(state.deliveryOrderLookup.result, null);
        """)

    def test_state_reset_preserves_lookup_across_delivery_tabs_and_clears_on_exit(self):
        self.run_node("""
            const { createWorkspaceStateReset } = await import('./frontend/js/actions/workspace/workspace-state-reset.js');
            const lookup = {...defaultDeliveryOrderLookupState(), open: true, query: 'QA'};
            const state = {deliveryOrderLookup: lookup};
            const reset = createWorkspaceStateReset({state, actions: {
              invalidateDeliveryAttachePreview() {}, defaultDeliveryAttacheImportState: () => ({}),
              defaultDeliveryAttacheCurrentFutureImportState: () => ({}),
            }});
            reset.clearGenerationConfirmationsForRoute('delivery/history');
            assert.equal(state.deliveryOrderLookup, lookup);
            reset.clearGenerationConfirmationsForRoute('opshop/task-pool/regular');
            assert.deepEqual(state.deliveryOrderLookup, defaultDeliveryOrderLookupState());
            state.deliveryOrderLookup = lookup; reset.clearWorkspaceDraftsForDispatchDateChange();
            assert.deepEqual(state.deliveryOrderLookup, defaultDeliveryOrderLookupState());
        """)
        auth = (ROOT / "frontend/js/actions/auth-actions.js").read_text(encoding="utf-8")
        self.assertIn("state.deliveryOrderLookup = defaultDeliveryOrderLookupState()", auth)

    def test_modal_submit_loading_no_match_error_duplicate_statuses_and_escape(self):
        self.run_node("""
            const { createDeliveryOrderLookupModal } = await import('./frontend/js/render/delivery/delivery-order-lookup-modal-renderer.js');
            const lookup = {...defaultDeliveryOrderLookupState(), open: true};
            const state = {deliveryOrderLookup: lookup}; let submits = 0; let closed = 0;
            const actions = {closeDeliveryOrderLookup: () => closed++,
              updateDeliveryOrderLookupQuery: value => lookup.query = value,
              searchDeliveryOrderLookup: () => submits++};
            const root = createDeliveryOrderLookupModal(state, actions); body.append(root); flush();
            const input = root.querySelector('input'); const search = root.querySelector("button[type='submit']");
            assert.equal(document.activeElement, input); assert.equal(search.disabled, true);
            assert.equal(input.type, 'text'); input.value = '001234'; input.fire('input');
            assert.equal(lookup.query, '001234'); assert.equal(search.disabled, false);
            // Native submit form covers both Enter and the Search submit button.
            root.querySelector('form').fire('submit'); assert.equal(submits, 1);
            lookup.loading = true; createDeliveryOrderLookupModal(state, actions, root);
            assert.equal(search.disabled, true); assert.match(root.textContent, /Searching/);
            lookup.loading = false; lookup.result = {invoice_number: '001234', match_count: 0, orders: []};
            createDeliveryOrderLookupModal(state, actions, root); assert.match(root.textContent, /No Manual Dispatch Order found/);
            lookup.result = null; lookup.error = 'API unavailable'; createDeliveryOrderLookupModal(state, actions, root);
            assert.match(root.textContent, /API unavailable/); lookup.error = '';
            const history = {run_sheet_id: 'DRS-QA', dispatch_date: '2000-01-01', delivery_date: '2026-09-17',
              driver_id: 'D-QA', driver_name_snapshot: 'QA Driver', vehicle_rego_snapshot: 'QA-VEHICLE',
              trip_no: 'trip1', status: 'SAVED', execution_status: 'CLOSED', generated_at: 'generated-time',
              saved_at: 'saved-time', outcome: 'RETURN_TO_POOL', reason_code: 'TIME_RAN_OUT', note: '<script>literal</script>',
              next_delivery_date: '2026-09-18', recorded_at: 'recorded-time', closed_at: 'closed-time', recorded_by_account_name: 'QA Operator'};
            const statuses = ['UNASSIGNED', 'ASSIGNED', 'RUN_SHEET_GENERATED', 'RUN_SHEET_SAVED_OPEN', 'DELIVERED', 'RETURNED_TO_POOL', 'CANCELLED', 'FINALIZED'];
            const orders = statuses.map(current_status => ({order_id: current_status, current_status, status_label: current_status,
              order: {invoice_number: '001234', company_name: 'QA Customer', order_no: 'QA-NUMBER', delivery_date: '2026-09-18',
                status: 'ACTIVE', delivery_address: '1 QA Street', suburb: 'QA Suburb', postcode: '0000',
                pallet_quantity: 1, loose_bags_quantity: 2, carton_quantity: 3},
              assignment: {driver_id: 'D-QA', driver_name: 'New Driver', trip_no: 'trip2', dispatch_date: '2026-09-18'},
              active_run_sheet: {...history, outcome: null, execution_status: 'OPEN'}, latest_closeout: history, run_sheet_history: [history]}));
            lookup.result = {invoice_number: '001234', match_count: 8, orders};
            const modalBody = root.querySelector('.workspace-modal-body'); modalBody.scrollTop = 321;
            createDeliveryOrderLookupModal(state, actions, root);
            assert.equal(root.querySelectorAll('.delivery-order-lookup-match').length, 8);
            assert.match(root.textContent, /8 Manual Dispatch Orders found/);
            for (const code of statuses) assert.ok(root.textContent.includes(code));
            for (const text of ['New Driver', 'Trip 2', 'DRS-QA', 'QA-VEHICLE', 'TIME_RAN_OUT', 'QA Operator', 'recorded-time', 'closed-time']) {
              assert.ok(root.textContent.includes(text), text);
            }
            assert.equal(root.querySelectorAll('script').length, 0);
            assert.equal(modalBody.scrollTop, 321);
            const dialog = root.querySelector('article'); assert.equal(dialog.attributes['role'], 'dialog');
            assert.equal(dialog.attributes['aria-modal'], 'true');
            const summaries = root.querySelectorAll('summary');
            assert.equal(summaries.length, orders.length);
            for (const summary of summaries) {
              assert.equal(summary.tabIndex, 0);
              assert.equal(summary.parentNode.tagName, 'details');
              assert.equal(summary.parentNode.children[0], summary);
            }
            const focusable = dialog.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])");
            assert.equal(focusable[focusable.indexOf(search) + 1], summaries[0]);
            search.focus(); let prevented = false;
            dialog.fire('keydown', {key: 'Tab', preventDefault() { prevented = true; }});
            assert.equal(prevented, false); // Native Tab may advance to the summary.
            const close = root.querySelector('.workspace-modal-close'); close.focus();
            dialog.fire('keydown', {key: 'Tab', shiftKey: true});
            assert.equal(document.activeElement, summaries.at(-1));
            dialog.fire('keydown', {key: 'Tab'}); assert.equal(document.activeElement, close);
            // This minimal DOM has no native activation. Ensure the real handler
            // leaves Enter/Space to the native details/summary implementation.
            summaries[0].focus();
            for (const key of ['Enter', ' ']) {
              let blocked = false;
              dialog.fire('keydown', {key, preventDefault() { blocked = true; }});
              assert.equal(blocked, false);
            }
            dialog.fire('keydown', {key: 'Escape'}); assert.equal(closed, 1);
        """)

    def test_module_boundaries_and_responsive_styles(self):
        renderer = (ROOT / "frontend/js/render/delivery-workspace-renderer.js").read_text(encoding="utf-8")
        self.assertIn("createDeliveryOrderLookupModal(state, actions, lookupModal)", renderer)
        actions = (ROOT / "frontend/js/actions/workspace/delivery-order-lookup-actions.js").read_text(encoding="utf-8")
        for forbidden in ("loadDeliveryRoute", "getDeliveryWorkspaceBoard", "board.orders", "window.location.reload", "dispatch_date"):
            self.assertNotIn(forbidden, actions)
        css = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")
        self.assertIn(".workspace-modal-invoice-lookup", css)
        self.assertIn("width: min(920px, calc(100vw - 32px))", css)
        self.assertIn(".delivery-order-lookup-match .workspace-modal-fact-grid", css)

    def test_invoice_modal_width_overrides_generic_width(self):
        css = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")
        generic = re.findall(r"(?m)^\.workspace-modal\s*\{([^}]+)\}", css)
        specific = re.findall(r"(?m)^\.workspace-modal\.workspace-modal-invoice-lookup\s*\{([^}]+)\}", css)
        self.assertTrue(any("width:" in rule for rule in generic))
        self.assertEqual(1, len(specific))
        self.assertIn("width: min(920px, calc(100vw - 32px));", specific[0])
        self.assertNotIn("!important", specific[0])
        self.assertTrue(all("!important" not in declaration for rule in generic
                            for declaration in rule.split(";") if "width:" in declaration))
        # Two class selectors outrank the generic single class even when earlier.
        self.assertGreater(".workspace-modal.workspace-modal-invoice-lookup".count("."),
                           ".workspace-modal".count("."))
