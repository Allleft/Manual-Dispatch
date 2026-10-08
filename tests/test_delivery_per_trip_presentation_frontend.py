import subprocess
import textwrap
import unittest
from pathlib import Path

from tests.test_driver_availability_frontend import NODE_HARNESS


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION_HARNESS = NODE_HARNESS + r"""
const {createDeliveryHistoryActions} = await import('./js/actions/workspace/delivery-history-actions.js');
const {createSavedRunSheetHistory} = await import('./js/render/delivery/delivery-history-renderer.js');
const {createRunSheetList} = await import('./js/render/delivery/delivery-run-sheet-renderer.js');
const date = '2026-09-15';
const actions = new Proxy({}, {get: () => () => {}});
const historyActions = createDeliveryHistoryActions({actions, state: {}, api: {}});
function sheet(id, driver, name, trip, changes = {}) {
  const row = {row_id: id+'-ROW', task_id: id+'-ORDER', company_name_snapshot: 'Customer '+id,
    invoice_number_snapshot: 'INV-'+id, pallet_quantity_snapshot: 1};
  return {run_sheet_id: id, delivery_date: date, dispatch_date: date, driver_id: driver,
    driver_name_snapshot: name, trip_no: trip, status: 'SAVED', execution_status: 'OPEN',
    vehicle_rego_snapshot: 'REGO-'+id, trips: [{trip_no: trip || 'trip1', orders: [row]}],
    ...changes};
}
const stateFor = rows => ({dispatchDate: date, deliveryTripSummaryDate: date,
  deliverySavedHistoryDate: date, deliverySavedHistoryRunSheets: rows, deliveryBusyActionKeys: {}});
"""


class DeliveryPerTripPresentationFrontendTest(unittest.TestCase):
    def run_node(self, body):
        completed = subprocess.run(
            ["node", "--input-type=module", "-"],
            input=PRESENTATION_HARNESS + textwrap.dedent(body),
            cwd=ROOT / "frontend", capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_history_sort_is_date_desc_name_id_trip_and_does_not_mutate_input(self):
        self.run_node("""
            const rows = [sheet('A', 'D2', 'john', 'trip2'), sheet('Z', 'D1', 'John', 'trip2'),
              sheet('B', 'D2', 'john', 'trip1'), sheet('Y', 'D1', 'John', 'trip1'),
              sheet('G', 'D3', 'gavin', null), sheet('OLD', 'D1', 'John', null, {delivery_date: '2026-09-14'}),
              sheet('NEW', 'D1', 'John', null, {delivery_date: '2026-09-16'})];
            const before = JSON.stringify(rows);
            const expected = ['NEW', 'G', 'Y', 'Z', 'B', 'A', 'OLD'];
            assert.deepEqual(historyActions.sortDeliverySavedHistory(rows).map(row => row.run_sheet_id), expected);
            assert.deepEqual(historyActions.sortDeliverySavedHistory([...rows].reverse()).map(row => row.run_sheet_id), expected);
            assert.equal(JSON.stringify(rows), before);
        """)

    def test_history_keeps_saved_siblings_without_driver_date_dedupe(self):
        self.run_node("""
            const rows = [sheet('SECOND', 'D1', 'John', 'trip2'), sheet('FIRST', 'D1', 'John', 'trip1'),
              sheet('DRAFT', 'D2', 'Gavin', 'trip1', {status: 'GENERATED'})];
            const saved = historyActions.sortDeliverySavedHistory(rows);
            assert.deepEqual(saved.map(row => row.trip_no), ['trip1', 'trip2']);
            const history = createSavedRunSheetHistory(stateFor(saved), actions);
            assert(history.textContent.includes('2 records'));
            for (const label of ['Trip: Trip 1', 'Trip: Trip 2', 'REGO-FIRST', 'REGO-SECOND', date, 'John', 'SAVED', 'OPEN'])
              assert(history.textContent.includes(label), label);
            assert.equal(history.querySelectorAll('.workspace-daily-run-sheet-driver').length, 2);
        """)

    def test_run_sheet_cards_keep_independent_status_identity_and_vehicle(self):
        self.run_node("""
            const rows = [sheet('FIRST', 'D1', 'John', 'trip1', {execution_status: 'CLOSED'}),
              sheet('SECOND', 'D1', 'John', 'trip2')];
            const cards = createRunSheetList(rows, stateFor(rows), actions).querySelectorAll('.workspace-run-sheet-document-card');
            assert.equal(cards.length, 2);
            assert(cards[0].textContent.includes('John — Trip 1'));
            assert(cards[0].textContent.includes('CLOSED'));
            assert(cards[0].textContent.includes('REGO-FIRST'));
            assert(!cards[0].textContent.includes('REGO-SECOND'));
            assert(cards[1].textContent.includes('John — Trip 2'));
            assert(cards[1].textContent.includes('OPEN'));
            assert(!cards[1].textContent.includes('CLOSED'));
        """)

    def test_closeout_outcome_is_visible_only_on_its_history_entry(self):
        self.run_node("""
            const first = sheet('FIRST', 'D1', 'John', 'trip1', {execution_status: 'CLOSED',
              outcomes: [{run_sheet_row_id: 'FIRST-ROW', outcome: 'DELIVERED'}]});
            const second = sheet('SECOND', 'D1', 'John', 'trip2');
            const history = createSavedRunSheetHistory(stateFor([first, second]), actions);
            const outcomes = history.querySelectorAll('.workspace-run-sheet-outcomes');
            assert.equal(outcomes.length, 1);
            assert(outcomes[0].textContent.includes('INV-FIRST'));
            assert(outcomes[0].textContent.includes('Delivered'));
            assert(!outcomes[0].textContent.includes('INV-SECOND'));
        """)

    def test_legacy_history_and_card_remain_single_combined_without_fake_trip(self):
        self.run_node("""
            const legacy = sheet('LEGACY', 'D1', 'John', null);
            legacy.trips.push({trip_no: 'trip2', orders: [{row_id: 'L2', invoice_number_snapshot: 'LEGACY-SECOND'}]});
            const state = stateFor([legacy]);
            const history = createSavedRunSheetHistory(state, actions);
            const cards = createRunSheetList([legacy], state, actions).querySelectorAll('.workspace-run-sheet-document-card');
            assert.equal(history.querySelectorAll('.workspace-daily-run-sheet-driver').length, 1);
            assert.equal(cards.length, 1);
            for (const text of [history.textContent, cards[0].textContent]) {
              assert(text.includes('INV-LEGACY') && text.includes('LEGACY-SECOND'));
              assert(!text.includes('Trip 1') && !text.includes('Trip 2'));
            }
        """)
