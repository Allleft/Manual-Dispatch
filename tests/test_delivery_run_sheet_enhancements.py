import json
import secrets
import subprocess
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook

from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    CloseDeliveryRunSheetRequest, CloseDeliveryRunSheetRowRequest,
    CreateDriverRequest, CreateOrderRequest, DeliveryWorkspaceAssignOrderRequest,
    GenerateDeliveryRunSheetRequest, OperatorAccountIdentity,
    ProductDetailLine, RegisterOperatorAccountRequest, SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.delivery_run_sheet_excel_export_service import (
    _loose_bag_summary, _product_quantity_summary,
    build_delivery_run_sheet_excel, build_delivery_run_sheets_excel,
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


def summary_data_rows(worksheet):
    return [row for row in worksheet.iter_rows(min_row=finish_row(worksheet) + 4)
            if row[5].value not in (None, "PACKAGE TYPE")]


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

    def test_package_summary_is_independent_of_loose_bag_reconciliation(self):
        orders = [loose_order(), loose_order(2, loose=5, pallets=1), loose_order(3, loose=2, lines=[])]
        self.assertEqual((3, 7, 10), self.summary(orders)[1:])
        worksheet = self.workbook(orders)
        values = {row[0].value: row[9].value for row in worksheet}
        self.assertEqual(3, values["Product A"])
        for label in ("Known product total", "UNALLOCATED loose bags", "Total loose bags"):
            self.assertNotIn(label, values)
        self.assertEqual("Product A", worksheet.cell(worksheet.max_row, 1).value)

    def test_summary_below_finish_and_print_area_includes_all_rows(self):
        for count in (1, 18, 30, 55):
            for trip in ("trip1", "trip2", None):
                with self.subTest(count=count, trip=trip):
                    worksheet = self.workbook([loose_order(n) for n in range(1, count + 1)], trip=trip)
                    finish = finish_row(worksheet)
                    self.assertTrue(all(cell.value is None for cell in worksheet[finish + 1]))
                    self.assertEqual("PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)", worksheet.cell(finish + 2, 1).value)
                    self.assertIn(f"$A$1:$N${worksheet.max_row}", worksheet.print_area)
                    self.assertEqual((1, 0), (worksheet.page_setup.fitToWidth, worksheet.page_setup.fitToHeight))
                    self.assertEqual("$7:$8", worksheet.print_title_rows)
                    self.assertTrue(all(area.min_row > finish or area.max_row < 9 for area in worksheet.merged_cells.ranges))
                    self.assertEqual(count * 3, worksheet.cell(worksheet.max_row, 10).value)

    def test_long_summary_name_continues_without_counting_bags_again(self):
        name = "\n".join(f"Synthetic long product line FINAL-{n}" for n in range(70))
        worksheet = self.workbook([loose_order(lines=[bags(name=name)])])
        first = finish_row(worksheet) + 4
        rows = summary_data_rows(worksheet)
        self.assertGreater(len(rows), 1)
        self.assertEqual(name, "".join(row[0].value or "" for row in rows))
        self.assertEqual(3, sum(row[9].value or 0 for row in rows))
        self.assertTrue(all(worksheet.row_dimensions[row[0].row].height <= 409.5 for row in rows))

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


class ProductQuantitySummaryTest(unittest.TestCase):
    workbook = LooseBagSummaryTest.workbook

    def summary(self, lines, **changes):
        return _product_quantity_summary([loose_order(lines=lines, **changes)])

    def test_all_native_package_units_are_included(self):
        units = ("BAG10", "BAG5", "BAG1.5", "BAG", "BAGS", "BOX", "CTN", "CARTON", "PKT",
                 "PKT100", "ROLL", "PACK", "EA", "PAIR", "BALE", "DRUM")
        for unit in units:
            with self.subTest(unit=unit):
                result = self.summary([bags(count=2, unit=unit)])
                self.assertEqual([2], list(result.values()))
                package_type = next(iter(result))[2]
                self.assertEqual({"BAG10": "10kg Bag", "BAG5": "5kg Bag", "BAG1.5": "1.5kg Bag",
                                  "BAGS": "BAG"}.get(unit, unit), package_type)

    def test_explicit_package_pair_takes_precedence_and_is_counted_once(self):
        line = ProductDetailLine("Frozen", 100, "KG", "SKU", 10, "BAG10")
        self.assertEqual({("Frozen", "SKU", "10kg Bag"): 10}, self.summary([line]))

    def test_absent_package_pair_uses_native_quantity_unit(self):
        for unit in ("BOX", "BAG", "CTN", "CARTON", "PKT"):
            with self.subTest(unit=unit):
                self.assertEqual({("Frozen", "SKU", unit): 2},
                                 self.summary([ProductDetailLine("Frozen", 2, unit, "SKU")]))

    def test_weight_and_other_measurements_do_not_invent_packages(self):
        for unit in ("KG", "KGS", "G", "MG", "TONNE", "L", "ML", "M", "M2", "M3"):
            with self.subTest(unit=unit):
                self.assertEqual({}, self.summary([ProductDetailLine("Weight only", 100, unit)]))
                self.assertEqual({}, self.summary([bags(unit=unit)]))

    def test_partial_package_pair_does_not_fall_back_to_base_quantity(self):
        for quantity, unit in ((None, "BOX"), (2, None), (2, "")):
            with self.subTest(quantity=quantity, unit=unit):
                self.assertEqual({}, self.summary([ProductDetailLine("Partial", 7, "BOX", "P", quantity, unit)]))

    def test_invalid_counts_are_not_replaced_by_base_count(self):
        for count in (True, -1, 1.5, "invalid", float("nan"), float("inf")):
            with self.subTest(count=count):
                self.assertEqual({}, self.summary([ProductDetailLine("Invalid", 7, "BOX", "P", count, "BOX")]))

    def test_unidentified_and_malformed_package_units_are_not_guessed(self):
        for unit in ("", "UNKNOWN", "BAG0", "BAG-10", "BAG10KG", "NOT A UNIT", "=FORMULA"):
            with self.subTest(unit=unit):
                self.assertEqual({}, self.summary([bags(unit=unit)]))
        self.assertEqual({}, self.summary([bags(name="", code=None)]))

    def test_zero_explicit_count_is_not_replaced_by_weight(self):
        self.assertEqual({("Product A", "A", "10kg Bag"): 0}, self.summary([bags(count=0)]))

    def test_palletized_and_mixed_load_lines_are_excluded_without_load_changes(self):
        for loose, pallets in ((0, 2), (5, 1)):
            with self.subTest(loose=loose, pallets=pallets):
                order = loose_order(loose=loose, pallets=pallets, lines=[bags(count=45)])
                before = deepcopy(order)
                self.assertEqual({}, _product_quantity_summary([order]))
                self.assertEqual(before, order)

    def test_matching_product_packages_aggregate_across_orders(self):
        self.assertEqual({("Product A", "A", "10kg Bag"): 8},
                         _product_quantity_summary([loose_order(), loose_order(2, lines=[bags(count=5)])]))

    def test_sizes_and_distinct_native_units_stay_separate(self):
        result = self.summary([bags(count=2, unit=unit) for unit in ("BAG10", "BAG5", "BOX", "CTN", "CARTON")])
        self.assertEqual(5, len(result))
        self.assertEqual({"10kg Bag", "5kg Bag", "BOX", "CTN", "CARTON"}, {key[2] for key in result})

    def test_equivalent_bag_notation_and_plural_generic_bags_merge(self):
        self.assertEqual({("Product A", "A", "10kg Bag"): 5, ("Product A", "A", "BAG"): 5},
                         self.summary([bags(count=2, unit="bag 10.00"), bags(count=3),
                                       bags(count=2, unit="BAG"), bags(count=3, unit="BAGS")]))

    def test_missing_name_falls_back_to_code_and_can_join_same_frozen_sku(self):
        self.assertEqual({("Product A", "A", "10kg Bag"): 5},
                         self.summary([bags(name="", count=2), bags(count=3)]))
        self.assertEqual({("A", "A", "10kg Bag"): 2}, self.summary([bags(name=" ", count=2)]))

    def test_distinct_skus_with_same_name_are_disambiguated(self):
        worksheet = self.workbook([loose_order(lines=[bags(code="ONE"), bags(code="TWO"), bags(code=None)])])
        labels = [cell.value for cell in worksheet["A"]]
        for label in ("Product A (ONE)", "Product A (TWO)", "Product A (code not recorded)"):
            self.assertIn(label, labels)

    def test_visually_similar_names_without_codes_stay_separate(self):
        self.assertEqual(2, len(self.summary([bags(name="Product A", code=None), bags(name="Product-A", code=None)])))

    def test_summary_sort_and_sku_name_selection_are_deterministic(self):
        lines = [bags("Zulu", 1, "BOX", "Z"), bags("alpha", 2, "BOX", "A"), bags("Alpha", 3, "BOX", "A")]
        first = self.summary(lines)
        self.assertEqual(list(first.items()), list(self.summary(list(reversed(lines))).items()))
        self.assertEqual([("Alpha", "A", "BOX"), ("Zulu", "Z", "BOX")], list(first))
        self.assertEqual(5, next(iter(first.values())))

    def example_orders(self):
        # Synthetic packaging fields reproduce the workbook descriptions, not unavailable historical IDs/JSON.
        rags = lambda count: bags("COLOR TSHIRT RAGS", count, "BAG10", "SYNTHETIC-RAGS")
        return [loose_order(1, loose=10, lines=[rags(10), ProductDetailLine(
                    "NITRILE BLAX GLOVE XL (100 GLOVESperBOX)", 2, "BOX", "SYNTHETIC-GLOVE")]),
                loose_order(2, loose=6, lines=[rags(6), ProductDetailLine(
                    "FINESSE-3PLY T/PAPER 180 SHTS x 72 ROLLS", 2, "BAG", "SYNTHETIC-PAPER")])]

    def test_workbook_described_bag_box_and_bag_combinations(self):
        products = _product_quantity_summary(self.example_orders())
        self.assertEqual(16, products[("COLOR TSHIRT RAGS", "SYNTHETIC-RAGS", "10kg Bag")])
        self.assertEqual(2, products[("NITRILE BLAX GLOVE XL (100 GLOVESperBOX)", "SYNTHETIC-GLOVE", "BOX")])
        self.assertEqual(2, products[("FINESSE-3PLY T/PAPER 180 SHTS x 72 ROLLS", "SYNTHETIC-PAPER", "BAG")])
        self.assertEqual(20, sum(products.values()))
        self.assertEqual(16, sum(order.loose_bags_quantity_snapshot for order in self.example_orders()))

    def test_old_allocator_conditional_box_and_extra_bag_rejections_remain(self):
        orders = self.example_orders()
        for order, count in zip(orders, (10, 6)):
            self.assertEqual(({}, 0, count, count), _loose_bag_summary([order]))
        explicit_box = replace(orders[0], product_lines_snapshot=[orders[0].product_lines_snapshot[0],
                             ProductDetailLine("Glove", 2, "BOX", "GLOVE", 2, "BOX")])
        self.assertEqual(({}, 0, 10, 10), _loose_bag_summary([explicit_box]))
        explicit_bag = replace(orders[1], product_lines_snapshot=[orders[1].product_lines_snapshot[0],
                             ProductDetailLine("Paper", 2, "BAG", "PAPER", 2, "BAG")])
        self.assertEqual(({}, 0, 6, 6), _loose_bag_summary([explicit_bag]))

    def test_daily_driver_and_trip_worksheets_are_independent(self):
        orders = self.example_orders()
        sheets = [synthetic_sheet([orders[index % 2]], trip=trip, driver_name_snapshot=driver,
                                 run_sheet_id=f"SYNTHETIC-{driver}-{trip}")
                  for index, (driver, trip) in enumerate((("Driver A", "trip1"), ("Driver A", "trip2"),
                                                        ("Driver B", "trip1"), ("Driver B", "trip2")))]
        before = deepcopy(sheets)
        workbook = load_workbook(BytesIO(build_delivery_run_sheets_excel(sheets, DATE)))
        self.addCleanup(workbook.close)
        self.assertEqual(4, len(workbook.worksheets))
        for worksheet, expected in zip(workbook.worksheets, (10, 6, 10, 6)):
            rows = {row[0].value: row[9].value for row in worksheet}
            self.assertEqual(expected, rows["COLOR TSHIRT RAGS"])
        self.assertEqual(before, sheets)

    def test_carton_singular_plural_and_other_quantities_are_in_rightmost_column(self):
        for unit, count, suffix in (("CARTON", 1, "Carton"), ("CARTON", 3, "Cartons"),
                                    ("BOX", 2, "BOX"), ("BAG", 2, "BAG"), ("BAG10", 1, "Bag"),
                                    ("BAG10", 10, "Bags")):
            with self.subTest(unit=unit, count=count):
                worksheet = self.workbook([loose_order(lines=[bags(count=count, unit=unit)])])
                row = finish_row(worksheet) + 4
                cell = worksheet.cell(row, 10)
                self.assertEqual(count, cell.value)
                self.assertEqual('#,##0" ' + suffix + '"', cell.number_format)
                self.assertEqual("00C00000", cell.font.color.rgb)
                self.assertEqual("00000000", worksheet.cell(row, 1).font.color.rgb)
                self.assertEqual(12, cell.font.sz)
                self.assertIn(f"J{row}:N{row}", {str(area) for area in worksheet.merged_cells.ranges})

    def test_footer_rows_are_removed_without_formatted_trailing_rows(self):
        worksheet = self.workbook(self.example_orders())
        cells = [cell.value for row in worksheet for cell in row]
        for label in ("Known product total", "UNALLOCATED loose bags", "Total loose bags"):
            self.assertNotIn(label, cells)
        start = finish_row(worksheet) + 2
        self.assertEqual(["PRODUCT", "PACKAGE TYPE", "QTY"], [worksheet.cell(start + 1, col).value for col in (1, 6, 10)])
        self.assertEqual(start + 4, worksheet.max_row)
        self.assertEqual("2 BOX", str(worksheet.cell(worksheet.max_row, 10).value) + " BOX")
        self.assertEqual("00000000", worksheet.cell(worksheet.max_row, 1).fill.fgColor.rgb)
        self.assertIn(f"$N${worksheet.max_row}", worksheet.print_area)

    def test_weight_only_snapshot_omits_empty_summary_without_fabricated_totals(self):
        worksheet = self.workbook([loose_order(lines=[ProductDetailLine("Weight only", 100, "KG")])])
        self.assertEqual(finish_row(worksheet), worksheet.max_row)
        self.assertNotIn("PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)", [cell.value for row in worksheet for cell in row])
        self.assertIn(f"$A$1:$N${finish_row(worksheet)}", worksheet.print_area)

    def test_large_integer_package_count_preserves_exact_digits(self):
        count = 9007199254740993
        result = self.summary([bags(count=count)])
        self.assertEqual(count, next(iter(result.values())))
        worksheet = self.workbook([loose_order(lines=[bags(count=count)])])
        cell = worksheet.cell(finish_row(worksheet) + 4, 10)
        self.assertEqual(("9,007,199,254,740,993 Bags", "s"), (cell.value, cell.data_type))



class NonPalletProductQuantitySummaryTest(unittest.TestCase):
    workbook = LooseBagSummaryTest.workbook

    def test_same_sku_filters_orders_before_aggregation_and_name_selection(self):
        orders = [loose_order(lines=[bags("Zero pallet name", 3)]),
                  loose_order(2, pallets=1, lines=[bags("Excluded name", 54)]),
                  loose_order(3, lines=[bags("Zero pallet name", 5)])]
        self.assertEqual({("Zero pallet name", "A", "10kg Bag"): 8}, _product_quantity_summary(orders))

    def test_pallet_mixed_loose_and_cartons_excludes_every_line(self):
        order = replace(loose_order(pallets=1, loose=5, lines=[bags(count=5), bags("Carton", 2, "CARTON", "C")]),
                        carton_quantity_snapshot=2)
        self.assertEqual({}, _product_quantity_summary([order]))

    def test_positive_pallet_order_does_not_inspect_product_lines(self):
        self.assertEqual({}, _product_quantity_summary([
            SimpleNamespace(pallet_quantity_snapshot=1, product_lines_snapshot=object())]))

    def test_zero_loose_cartons_and_other_native_packages_remain_eligible(self):
        units = ("BAG10", "BAG5", "BAG1.5", "BAG", "BAGS", "BOX", "CTN", "CARTON", "PKT", "ROLL")
        eligible = loose_order(loose=0, lines=[bags(count=2, unit=unit) for unit in units])
        excluded = replace(eligible, pallet_quantity_snapshot=1)
        products = _product_quantity_summary([eligible, excluded])
        self.assertEqual(20, sum(products.values()))
        self.assertEqual(9, len(products))
        self.assertEqual(4, products[("Product A", "A", "BAG")])
        self.assertEqual(2, products[("Product A", "A", "CARTON")])

    def test_missing_pallet_snapshot_fails_safely(self):
        with self.assertRaisesRegex(ValueError, "Pallet snapshot quantity"):
            _product_quantity_summary([SimpleNamespace(product_lines_snapshot=[bags()])])

    def test_invalid_or_ambiguous_pallet_snapshots_fail_export(self):
        for pallets in (None, -1, True, False, 0.0, 0.5, "0", "", "unknown", float("nan"), float("inf")):
            with self.subTest(pallets=pallets):
                sheet = synthetic_sheet([loose_order()])
                sheet.trips[0].orders[0] = replace(sheet.trips[0].orders[0], pallet_quantity_snapshot=pallets)
                with self.assertRaisesRegex(ValueError, "Pallet snapshot quantity"):
                    build_delivery_run_sheet_excel(sheet)
                with self.assertRaisesRegex(ValueError, "Pallet snapshot quantity"):
                    build_delivery_run_sheets_excel([sheet], DATE)

    def test_all_pallet_sheets_omit_heading_headers_and_formatted_summary(self):
        for trip in ("trip1", "trip2", None):
            for count in (1, 18, 30, 55):
                with self.subTest(trip=trip, count=count):
                    worksheet = self.workbook([loose_order(n, pallets=1) for n in range(1, count + 1)], trip=trip)
                    finish = finish_row(worksheet)
                    self.assertEqual(finish, worksheet.max_row)
                    self.assertIn(f"$A$1:$N${finish}", worksheet.print_area)
                    self.assertNotIn("PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)", [cell.value for row in worksheet for cell in row])
                    self.assertTrue(all(area.max_row < finish for area in worksheet.merged_cells.ranges))
                    self.assertEqual(count, sum(bool(worksheet.cell(row, 4).value) for row in range(9, finish)))
                    self.assertEqual((1, 0), (worksheet.page_setup.fitToWidth, worksheet.page_setup.fitToHeight))
                    self.assertEqual("$7:$8", worksheet.print_title_rows)
                    self.assertTrue(all(item.id == count + 8 for item in worksheet.row_breaks.brk))

    def test_empty_or_unquantified_eligible_orders_omit_summary(self):
        for lines in ([], [ProductDetailLine("Only KG", 12, "KG")], [bags(unit="UNKNOWN")]):
            with self.subTest(lines=lines):
                worksheet = self.workbook([loose_order(lines=lines), loose_order(2, pallets=1)])
                self.assertEqual(finish_row(worksheet), worksheet.max_row)
                self.assertIn(f"$N${worksheet.max_row}", worksheet.print_area)

    def test_main_table_keeps_all_frozen_rows_ids_weights_pallets_and_product_text(self):
        orders = [loose_order(3, pallets=2, lines=[bags("Pallet product", 45)]),
                  loose_order(1, pallets=0, lines=[bags("Eligible product", 3)]),
                  loose_order(2, pallets=1, lines=[bags("Mixed product", 5)])]
        before = deepcopy(orders)
        worksheet = self.workbook(orders)
        self.assertEqual(["QA-INV-3", "QA-INV-1", "QA-INV-2"], [worksheet.cell(row, 4).value for row in (9, 10, 11)])
        self.assertEqual([2, 0, 1], [worksheet.cell(row, 7).value for row in (9, 10, 11)])
        self.assertEqual([999, 999, 999], [worksheet.cell(row, 6).value for row in (9, 10, 11)])
        self.assertEqual(["Pallet product - 10kg x 45Bag", "Eligible product - 10kg x 3Bag", "Mixed product - 10kg x 5Bag"],
                         [worksheet.cell(row, 5).value for row in (9, 10, 11)])
        self.assertEqual(before, orders)
        summary = {row[0].value: row[9].value for row in worksheet.iter_rows(min_row=finish_row(worksheet) + 4)}
        self.assertEqual({"Eligible product": 3}, summary)

    def test_driver_trip_and_legacy_saved_exports_use_independent_frozen_eligibility(self):
        combinations = (("Driver A", "trip1", 0, 3), ("Driver A", "trip2", 1, 8),
                        ("Driver B", "trip1", 0, 5), ("Driver B", "trip2", 2, 9), ("Legacy", None, 0, 7))
        sheets = [synthetic_sheet([loose_order(lines=[bags(count=count)], pallets=pallets)], trip=trip,
                                 driver_name_snapshot=driver, run_sheet_id=f"{driver}-{trip}")
                  for driver, trip, pallets, count in combinations]
        before = deepcopy(sheets)
        book = load_workbook(BytesIO(build_delivery_run_sheets_excel(sheets, sheets[0].delivery_date)))
        self.addCleanup(book.close)
        for sheet, worksheet in zip(sheets, book.worksheets):
            single = load_workbook(BytesIO(build_delivery_run_sheet_excel(sheet)))
            self.addCleanup(single.close)
            self.assertEqual(list(single.active.values), list(worksheet.values))
            order = sheet.trips[0].orders[0]
            labels = [cell.value for row in worksheet for cell in row]
            self.assertEqual(order.pallet_quantity_snapshot == 0, "PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)" in labels)
            if order.pallet_quantity_snapshot == 0:
                self.assertEqual(order.product_lines_snapshot[0].package_quantity, worksheet.cell(worksheet.max_row, 10).value)
        self.assertEqual(before, sheets)

    def test_cartonized_1_5kg_products_stay_one_carton_each_for_zero_pallet_order(self):
        from tests.test_attache_carton_packaging import carton_payload, normalize
        # Use confirmed Attaché normalization, then only vary the frozen pallet value.
        lines = [ProductDetailLine(**line) for line in normalize(carton_payload())["product_lines"]]
        order = loose_order(loose=0, lines=lines)
        products = _product_quantity_summary([order, replace(order, pallet_quantity_snapshot=1)])
        self.assertEqual(2, len(products))
        self.assertTrue(all(key[2] == "CARTON" and count == 1 for key, count in products.items()))
        worksheet = self.workbook([order, replace(order, pallet_quantity_snapshot=1)])
        self.assertEqual([42, 42], [worksheet.cell(row, 6).value for row in (9, 10)])
        self.assertIn("1 Carton", worksheet["E9"].value)
        self.assertNotIn("14Bag", worksheet["E9"].value)

    def test_continued_summary_counts_only_eligible_package_once(self):
        name = "\n".join(f"Synthetic non-pallet summary END-{n}" for n in range(70))
        worksheet = self.workbook([loose_order(lines=[bags(name, 3)]), loose_order(2, pallets=1, lines=[bags(name, 100)])])
        rows = summary_data_rows(worksheet)
        self.assertEqual(name, "".join(row[0].value or "" for row in rows))
        self.assertEqual(3, sum(row[9].value or 0 for row in rows))


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
