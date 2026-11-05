import json
import secrets
import subprocess
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    CloseDeliveryRunSheetRequest, CloseDeliveryRunSheetRowRequest,
    CreateDriverRequest, CreateOrderRequest, DeliveryWorkspaceAssignOrderRequest,
    GenerateDeliveryRunSheetRequest, OperatorAccountIdentity,
    ProductDetailLine, RegisterOperatorAccountRequest, SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.delivery_run_sheet_excel_export_service import (
    _loose_bag_summary, build_delivery_run_sheet_excel, build_delivery_run_sheets_excel,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.test_delivery_run_sheet_excel_pagination import synthetic_order, synthetic_sheet, finish_row


ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-11-05"


def bags(name="Product A", count=3, unit="BAG10", code="A"):
    return ProductDetailLine(name, 999, "KG", code, count, unit)


def loose_order(number=1, loose=3, lines=None, pallets=0):
    return synthetic_order(number, lines=lines if lines is not None else [bags(count=loose)],
                           pallet_quantity_snapshot=pallets, loose_bags_quantity_snapshot=loose)


class LooseBagSummaryTest(unittest.TestCase):
    def summary(self, orders):
        products, allocated, unallocated, total = _loose_bag_summary(orders)
        self.assertEqual(sum(order.loose_bags_quantity_snapshot for order in orders), total)
        self.assertEqual(allocated + unallocated, total)
        self.assertEqual(sum(products.values()), allocated)
        return products, allocated, unallocated, total

    def workbook(self, orders, trip="trip1", daily=False):
        sheet = synthetic_sheet(orders, trip=trip)
        before = deepcopy(sheet)
        data = build_delivery_run_sheets_excel([sheet], sheet.delivery_date) if daily else build_delivery_run_sheet_excel(sheet)
        self.assertEqual(before, sheet)
        workbook = load_workbook(BytesIO(data))
        self.addCleanup(workbook.close)
        return workbook.active

    def test_single_loose_only_product_uses_explicit_packages_not_kg(self):
        products, allocated, unallocated, total = self.summary([loose_order()])
        self.assertEqual({("Product A", "A", "10kg Bag"): 3}, products)
        self.assertEqual((3, 0, 3), (allocated, unallocated, total))

    def test_multiple_products_and_same_product_across_orders(self):
        products, allocated, unallocated, total = self.summary([
            loose_order(loose=5, lines=[bags(count=3), bags("Product B", 2, code="B")]),
            loose_order(2, loose=4),
        ])
        self.assertEqual({("Product A", "A", "10kg Bag"): 7, ("Product B", "B", "10kg Bag"): 2}, products)
        self.assertEqual((9, 0, 9), (allocated, unallocated, total))

    def test_packaging_size_and_distinct_codes_are_not_combined(self):
        products, *_ = self.summary([loose_order(loose=6, lines=[
            bags(count=1), bags(count=2, unit="BAG5"), bags(count=3, code="OTHER"),
        ])])
        self.assertEqual(3, len(products))
        worksheet = self.workbook([loose_order(loose=4, lines=[bags(count=1), bags(count=3, code="OTHER")])])
        labels = [cell.value for cell in worksheet["A"]]
        self.assertIn("Product A (A)", labels)
        self.assertIn("Product A (OTHER)", labels)

    def test_package_spelling_normalization_and_generic_bags(self):
        products, *_ = self.summary([loose_order(loose=6, lines=[
            bags(count=1, unit=" bag 10.00 "), bags(count=2, unit="BAG10"), bags(count=3, unit="BAGS"),
        ])])
        self.assertEqual({("Product A", "A", "10kg Bag"): 3, ("Product A", "A", "Bag"): 3}, products)

    def test_zero_loose_bags_ignores_all_pallet_packages(self):
        self.assertEqual(({}, 0, 0, 0), self.summary([loose_order(loose=0, pallets=2, lines=[bags(count=45)])]))

    def test_mixed_pallet_and_loose_order_is_fully_unallocated(self):
        self.assertEqual(({}, 0, 5, 5), self.summary([loose_order(loose=5, pallets=1, lines=[bags(count=5)])]))

    def test_missing_invalid_fractional_or_nonfinite_package_count_unallocated(self):
        for count in (None, "invalid", -1, 1.5, float("nan"), float("inf"), True):
            with self.subTest(count=count):
                self.assertEqual(({}, 0, 3, 3), self.summary([loose_order(lines=[bags(count=count)])]))

    def test_inconsistent_or_partial_package_data_does_not_partially_allocate(self):
        for lines in ([bags(count=2)], [bags(count=4)], [bags(count=3), bags("Unknown", None)], []):
            with self.subTest(lines=lines):
                self.assertEqual(({}, 0, 3, 3), self.summary([loose_order(lines=lines)]))

    def test_unknown_or_malformed_packaging_is_not_inferred_from_code_or_kg(self):
        for unit in (None, "", "UNKNOWN", "BAG0", "BAG-10", "BAG10KG"):
            with self.subTest(unit=unit):
                self.assertEqual(({}, 0, 3, 3), self.summary([loose_order(lines=[bags(unit=unit, code="PRODUCT10KG")])]))

    def test_explicit_non_bag_line_does_not_count_as_bags(self):
        self.assertEqual(3, self.summary([loose_order(lines=[bags(), bags("Cartons", 100, "CTN", "CTN")])])[1])

    def test_conflicting_bag_base_and_non_bag_package_unit_is_unallocated(self):
        conflicting = ProductDetailLine("Uncertain bags", 2, "BAG", "UNCERTAIN", 2, "EA")
        self.assertEqual(({}, 0, 3, 3), self.summary([loose_order(lines=[bags(), conflicting])]))

    def test_name_falls_back_to_recorded_code_and_unknown_identity_unallocated(self):
        self.assertEqual({("A", "A", "10kg Bag"): 3}, self.summary([loose_order(lines=[bags(name=" ")])])[0])
        self.assertEqual(({}, 0, 3, 3), self.summary([loose_order(lines=[bags(name="", code=None)])]))

    def test_large_explicit_integer_counts_reconcile_exactly(self):
        count = 9007199254740993
        self.assertEqual((count, 0, count), self.summary([loose_order(loose=count, lines=[bags(count=count)])])[1:])

    def test_allocated_unallocated_and_total_rows_match_frozen_orders(self):
        orders = [loose_order(), loose_order(2, loose=5, pallets=1), loose_order(3, loose=2, lines=[])]
        self.assertEqual((3, 7, 10), self.summary(orders)[1:])
        worksheet = self.workbook(orders)
        values = {row[0].value: row[9].value for row in worksheet}
        self.assertEqual(3, values["Known product total"])
        self.assertEqual(7, values["UNALLOCATED loose bags"])
        self.assertEqual(10, values["Total loose bags"])
        self.assertEqual("Total loose bags", worksheet.cell(worksheet.max_row, 1).value)

    def test_summary_below_finish_and_print_area_includes_all_rows(self):
        for count in (1, 18, 30, 55):
            for trip in ("trip1", "trip2", None):
                with self.subTest(count=count, trip=trip):
                    worksheet = self.workbook([loose_order(n) for n in range(1, count + 1)], trip=trip)
                    finish = finish_row(worksheet)
                    self.assertTrue(all(cell.value is None for cell in worksheet[finish + 1]))
                    self.assertEqual("LOOSE BAG SUMMARY BY PRODUCT", worksheet.cell(finish + 2, 1).value)
                    self.assertIn(f"$A$1:$N${worksheet.max_row}", worksheet.print_area)
                    self.assertEqual((1, 0), (worksheet.page_setup.fitToWidth, worksheet.page_setup.fitToHeight))
                    self.assertEqual("$7:$8", worksheet.print_title_rows)
                    self.assertTrue(all(area.min_row > finish or area.max_row < 9 for area in worksheet.merged_cells.ranges))
                    self.assertEqual(count * 3, worksheet.cell(worksheet.max_row, 10).value)

    def test_long_summary_name_continues_without_counting_bags_again(self):
        name = "\n".join(f"Synthetic long product line FINAL-{n}" for n in range(70))
        worksheet = self.workbook([loose_order(lines=[bags(name=name)])])
        first = finish_row(worksheet) + 4
        rows = list(worksheet.iter_rows(min_row=first, max_row=worksheet.max_row - 3))
        self.assertGreater(len(rows), 1)
        self.assertEqual(name, "".join(row[0].value or "" for row in rows))
        self.assertEqual(3, sum(row[9].value or 0 for row in rows))
        self.assertTrue(all(worksheet.row_dimensions[row[0].row].height <= 294 for row in rows))

    def test_summary_product_text_is_not_an_excel_formula(self):
        worksheet = self.workbook([loose_order(lines=[bags(name='=1+2')])])
        cell = worksheet.cell(finish_row(worksheet) + 4, 1)
        self.assertEqual(("=1+2", "s"), (cell.value, cell.data_type))

    def test_single_daily_and_legacy_export_preserve_historical_snapshot_order(self):
        orders = [loose_order(3, pallets=0), loose_order(1, pallets=2), loose_order(2, pallets=1)]
        for trip in ("trip1", "trip2", None):
            single = self.workbook(orders, trip=trip)
            daily = self.workbook(orders, trip=trip, daily=True)
            self.assertEqual(list(single.values), list(daily.values))
            self.assertEqual(["QA-INV-3", "QA-INV-1", "QA-INV-2"], [single.cell(row, 4).value for row in (9, 10, 11)])


class PalletFirstSnapshotTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="run-sheet-enhancements-")
        self.addCleanup(temp.cleanup)
        self.repository = SQLiteManualDispatchRepository(Path(temp.name) / "synthetic.sqlite3")
        self.service = ManualDispatchService(self.repository)

    def prepare(self):
        drivers = [self.service.create_delivery_driver(CreateDriverRequest(name=f"Synthetic driver {n}")) for n in (1, 2)]
        for driver in drivers:
            for trip in ("trip1", "trip2"):
                orders = [self.service.create_delivery_order(CreateOrderRequest(
                    invoice_number=invoice, company_name="Synthetic", suburb="Dandenong", postcode="3175",
                    delivery_date=DATE, pallet_quantity=pallets,
                )) for invoice, pallets in (("003", 0), ("001", 1), ("004", 1), ("002", 2), ("005", 0))]
                for index in (4, 0, 2, 3, 1):
                    self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                        order_id=orders[index].order_id, driver_id=driver.driver_id, trip_no=trip,
                    ))
        return drivers

    def frontend_order(self, board, driver_id, trip):
        script = """
          const {assignedOrdersForDriver} = await import('./frontend/js/render/delivery/delivery-renderer-utils.js');
          const board = BOARD;
          const before = JSON.stringify(board);
          const orders = assignedOrdersForDriver(board, DATE, DRIVER).filter(item => item.assignment.trip_no === TRIP);
          if (JSON.stringify(board) !== before) throw Error('Board was mutated');
          console.log(JSON.stringify(orders.map(item => item.order.order_id)));
        """
        for key, value in (("BOARD", asdict(board)), ("DATE", DATE), ("DRIVER", driver_id), ("TRIP", trip)):
            script = script.replace(key, json.dumps(value))
        result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_two_drivers_both_trips_match_ui_snapshot_excel_and_row_identity(self):
        drivers = self.prepare()
        board = self.service.get_delivery_trip_summary_board(DATE)
        all_row_ids = set()
        for driver in drivers:
            for trip in ("trip1", "trip2"):
                expected = self.frontend_order(board, driver.driver_id, trip)
                sheet = self.service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(
                    delivery_date=DATE, driver_id=driver.driver_id, trip_no=trip,
                ))
                rows = sheet.trips[0].orders
                self.assertEqual(expected, [row.order_id_snapshot for row in rows])
                self.assertEqual(["001", "002", "004", "003", "005"], [row.invoice_number_snapshot for row in rows])
                self.assertEqual([1, 2, 1, 0, 0], [row.pallet_quantity_snapshot for row in rows])
                self.assertEqual([1, 2, 3, 4, 5], [row.row_no for row in rows])
                all_row_ids.update(row.row_id for row in rows)
                for data in (build_delivery_run_sheet_excel(sheet), build_delivery_run_sheets_excel([sheet], DATE)):
                    workbook = load_workbook(BytesIO(data))
                    self.assertEqual([row.invoice_number_snapshot for row in rows], [workbook.active.cell(n, 4).value for n in range(9, 14)])
                    workbook.close()
        self.assertEqual(20, len(all_row_ids))

    def test_frozen_snapshot_survives_live_order_edits_and_closeout_uses_same_row_ids(self):
        driver = self.prepare()[0]
        sheet = self.service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(
            delivery_date=DATE, driver_id=driver.driver_id, trip_no="trip1",
        ))
        password = secrets.token_urlsafe(20)
        account = self.service.register_operator_account(RegisterOperatorAccountRequest(
            account_name="Synthetic enhancement operator", password=password, confirm_password=password,
        ))
        identity = OperatorAccountIdentity(account.account_id, account.account_name)
        saved = self.service.save_generated_delivery_run_sheet(sheet.run_sheet_id, SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_id=identity.account_id, saved_by_account_name=identity.account_name,
        ))
        before = deepcopy(saved)
        order = self.repository.get_order(saved.trips[0].orders[0].order_id_snapshot)
        self.repository.update_order(replace(order, pallet_quantity=99, company_name="Changed live order"))
        build_delivery_run_sheet_excel(self.service.get_saved_delivery_run_sheet_for_export(saved.run_sheet_id))
        self.assertEqual(before, self.repository.get_delivery_run_sheet(saved.run_sheet_id))
        request = CloseDeliveryRunSheetRequest(rows=[CloseDeliveryRunSheetRowRequest(
            run_sheet_row_id=row.row_id, outcome="RETURN_TO_POOL", reason_code="TIME_RAN_OUT", next_delivery_date="2026-11-06",
        ) for row in saved.trips[0].orders])
        closed = self.service.close_saved_delivery_run_sheet(saved.run_sheet_id, request, identity)
        self.assertEqual([row.row_id for row in saved.trips[0].orders], [row.row_id for row in closed.trips[0].orders])
        self.assertEqual({row.row_id for row in saved.trips[0].orders}, {outcome.run_sheet_row_id for outcome in closed.outcomes})
