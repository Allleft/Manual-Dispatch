import math
import unittest
from copy import deepcopy
from dataclasses import replace
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Border, Side

from backend.schemas import DeliveryRunSheetTrip, ProductDetailLine
from backend.services.delivery_run_sheet_excel_export_service import (
    PRODUCT_SUMMARY_HEADING, _PrintLayout, _apply_column_widths,
    _apply_row_heights, _configure_print_layout, _product_quantity_summary,
    _write_product_quantity_summary, build_delivery_run_sheet_excel,
    build_delivery_run_sheets_excel,
)
from tests.test_delivery_run_sheet_excel_pagination import (
    finish_row, synthetic_order, synthetic_sheet,
)


class DeliveryRunSheetFinalLayoutTest(unittest.TestCase):
    def workbook(self, orders, trip="trip1", **changes):
        sheet = synthetic_sheet(orders, trip=trip, **changes)
        before = deepcopy(sheet)
        book = load_workbook(BytesIO(build_delivery_run_sheet_excel(sheet)), rich_text=True)
        self.addCleanup(book.close)
        self.assertEqual(before, sheet)
        return book.active

    def order(self, number=1, pallets=0, lines=None):
        return synthetic_order(number, pallet_quantity_snapshot=pallets, lines=lines)

    def handwriting(self, worksheet, count):
        finish = finish_row(worksheet)
        slots = [row for row in range(9, finish)
                 if worksheet.cell(row, 1).value in (count + 1, count + 2)
                 and all(worksheet.cell(row, col).value is None for col in range(2, 15))]
        self.assertEqual(2, len(slots))
        self.assertEqual([finish - 3, finish - 2], slots)
        self.assertEqual([count + 1, count + 2], [worksheet.cell(row, 1).value for row in slots])
        for row in slots:
            self.assertGreaterEqual(worksheet.row_dimensions[row].height, 21.95)
            for cell in worksheet[row]:
                self.assertEqual(("thin",) * 4, tuple(getattr(cell.border, edge).style
                                                     for edge in ("left", "right", "top", "bottom")))
                self.assertFalse(cell.protection.locked)
                self.assertNotEqual("f", cell.data_type)
        self.assertFalse(worksheet.protection.sheet)
        return slots

    def boundary(self, remaining=None):
        book = Workbook()
        self.addCleanup(book.close)
        worksheet = book.active
        _configure_print_layout(worksheet)
        _apply_column_widths(worksheet)
        _apply_row_heights(worksheet)
        worksheet.print_title_rows = "7:8"
        if remaining is None:
            worksheet.row_dimensions[9].height = 22
        else:
            available = _PrintLayout(worksheet, 9).remaining
            worksheet.row_dimensions[9].height = math.floor((available - remaining) * 5) / 5
        return worksheet

    def rows(self, count=1):
        return [(PRODUCT_SUMMARY_HEADING, None, None, 21, "General"),
                ("PRODUCT", "PACKAGE TYPE", "QTY", 21, "General")] + [
                    (f"Synthetic product {n}", "BAG", n, 21, '#,##0" BAG"')
                    for n in range(1, count + 1)]

    def write(self, worksheet, rows):
        side = Side(style="thin", color="000000")
        return _write_product_quantity_summary(worksheet, 10, rows,
                                              Border(left=side, right=side, top=side, bottom=side))

    def test_exact_heading_in_individual_saved_closed_and_legacy_exports(self):
        for trip in ("trip1", "trip2", None):
            for status in ("SAVED", "CLOSED"):
                with self.subTest(trip=trip, status=status):
                    worksheet = self.workbook([self.order()], trip=trip, status=status)
                    title = worksheet.cell(finish_row(worksheet) + 2, 1)
                    self.assertEqual("PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)", title.value)
                    self.assertTrue(title.font.bold)
                    self.assertEqual(10, title.font.sz)
                    self.assertEqual("left", title.alignment.horizontal)
                    self.assertIn(f"A{title.row}:N{title.row}", {str(x) for x in worksheet.merged_cells.ranges})
                    self.assertNotIn("PRODUCT QUANTITY SUMMARY", [c.value for row in worksheet for c in row])

    def test_summary_headers_data_and_continuations_use_12pt_without_changing_other_fonts(self):
        name = "\n".join(f"Summary continuation FINAL-{n}" for n in range(60))
        worksheet = self.workbook([self.order(lines=[ProductDetailLine(name, 30, "KG", "LONG", 3, "BAG10")])])
        start = finish_row(worksheet) + 2
        continued = 0
        for row in range(start, worksheet.max_row + 1):
            if worksheet.cell(row, 1).value == PRODUCT_SUMMARY_HEADING:
                self.assertEqual(10, worksheet.cell(row, 1).font.sz)
                self.assertTrue(worksheet.cell(row, 1).font.bold)
                continue
            for column in (1, 6, 10):
                self.assertEqual(12, worksheet.cell(row, column).font.sz)
            continued += worksheet.cell(row, 6).value == "continued"
            self.assertLessEqual(worksheet.row_dimensions[row].height, 409.5)
        self.assertGreater(continued, 0)
        self.assertIn("FINAL-59", "".join(str(worksheet.cell(row, 1).value or "")
                                          for row in range(start, worksheet.max_row + 1)))
        self.assertEqual(9, worksheet["A8"].font.sz)
        self.assertEqual(8, worksheet["E9"].font.sz)
        self.assertEqual(16, worksheet.cell(finish_row(worksheet), 2).font.sz)
        for row in self.handwriting(worksheet, 1):
            self.assertEqual(8.5, worksheet.cell(row, 2).font.sz)

    def test_summary_12pt_rows_allow_wrapped_names_and_large_quantity_text(self):
        name = "Wide wrapped product description " * 25
        quantity = 10 ** 80 + 3
        worksheet = self.workbook([self.order(lines=[ProductDetailLine(name, 30, "KG", "WIDE", quantity, "BAG10")])])
        start = finish_row(worksheet) + 4
        self.assertGreater(worksheet.row_dimensions[start].height, 21)
        self.assertEqual(f"{quantity:,} Bags", worksheet.cell(start, 10).value)
        self.assertEqual(name.strip(), "".join(str(worksheet.cell(row, 1).value or "")
                                               for row in range(start, worksheet.max_row + 1)
                                               if worksheet.cell(row, 6).value != "PACKAGE TYPE"
                                               and worksheet.cell(row, 1).value != PRODUCT_SUMMARY_HEADING))
        self.assertTrue(all(worksheet.row_dimensions[row].height <= 409.5
                            for row in range(start, worksheet.max_row + 1)))
        self.assertEqual("00C00000", worksheet.cell(start, 10).font.color.rgb)

    def test_exactly_two_editable_bordered_slots_for_zero_small_and_large_sheets(self):
        for count in (0, 1, 18, 30, 55):
            for trip in ("trip1", "trip2", None):
                with self.subTest(count=count, trip=trip):
                    worksheet = self.workbook([self.order(n) for n in range(1, count + 1)], trip=trip)
                    slots = self.handwriting(worksheet, count)
                    self.assertEqual(count, sum(bool(worksheet.cell(row, 4).value) for row in range(9, slots[0])))
                    self.assertEqual(count + 9, slots[0])

    def test_two_slots_follow_final_continuation_without_replacing_real_data(self):
        name = "\n".join(f"Synthetic continuation FINAL-{n}" for n in range(100))
        order = self.order(lines=[ProductDetailLine(name, 30, "KG", "SYN", 3, "BAG10")])
        worksheet = self.workbook([order])
        slots = self.handwriting(worksheet, 1)
        text = "".join(str(worksheet.cell(row, 5).value or "") for row in range(9, slots[0]))
        self.assertIn("FINAL-99", text)
        self.assertEqual(30, sum(worksheet.cell(row, 6).value or 0 for row in range(9, slots[0])))

    def test_handwriting_pair_has_no_page_break_between_its_rows(self):
        for count in (1, 18, 19, 20, 30, 55):
            worksheet = self.workbook([self.order(n, pallets=1) for n in range(1, count + 1)])
            first, second = self.handwriting(worksheet, count)
            breaks = {item.id + 1 for item in worksheet.row_breaks.brk}
            self.assertNotIn(second, breaks)
            layout = _PrintLayout(worksheet, first)
            self.assertGreaterEqual(layout.remaining, sum(worksheet.row_dimensions[row].height
                                                          for row in (first, second)))

    def test_daily_driver_and_trip_exports_have_one_pair_and_independent_summaries(self):
        sheets = [synthetic_sheet([self.order(n)], trip=trip, driver_name_snapshot=driver)
                  for n, (driver, trip) in enumerate((("Alpha", "trip1"), ("Alpha", "trip2"),
                                                       ("Beta", "trip1"), ("Beta", "trip2")), 1)]
        before = deepcopy(sheets)
        book = load_workbook(BytesIO(build_delivery_run_sheets_excel(sheets, sheets[0].delivery_date)))
        self.addCleanup(book.close)
        self.assertEqual(4, len(book.worksheets))
        for worksheet in book:
            self.handwriting(worksheet, 1)
            self.assertEqual(45, worksheet.cell(worksheet.max_row, 10).value)
            self.assertEqual(PRODUCT_SUMMARY_HEADING, worksheet.cell(finish_row(worksheet) + 2, 1).value)
        self.assertEqual(before, sheets)

    def test_legacy_combined_trips_get_only_one_handwriting_pair(self):
        sheet = synthetic_sheet([self.order()], trip=None)
        sheet.trips.append(DeliveryRunSheetTrip("trip2", [self.order(2)]))
        before = deepcopy(sheet)
        book = load_workbook(BytesIO(build_delivery_run_sheet_excel(sheet)))
        self.addCleanup(book.close)
        self.handwriting(book.active, 2)
        self.assertEqual(["QA-INV-1", "QA-INV-2"], [book.active.cell(row, 4).value for row in (9, 10)])
        self.assertEqual(before, sheet)

    def test_all_pallet_and_unquantified_sheets_have_no_summary_page(self):
        for orders in ([self.order(pallets=1)], [self.order(lines=[])],
                       [self.order(lines=[ProductDetailLine("Weight only", 20, "KG")])], []):
            worksheet = self.workbook(orders)
            slots = self.handwriting(worksheet, len(orders))
            self.assertEqual(finish_row(worksheet), worksheet.max_row)
            self.assertIn(f"$N${worksheet.max_row}", worksheet.print_area)
            self.assertNotIn(PRODUCT_SUMMARY_HEADING, [c.value for row in worksheet for c in row])
            self.assertTrue(all(item.id + 1 <= slots[0] for item in worksheet.row_breaks.brk))

    def test_single_product_summary_stays_on_current_page_without_break(self):
        worksheet = self.workbook([self.order()])
        self.handwriting(worksheet, 1)
        self.assertEqual([], worksheet.row_breaks.brk)
        self.assertEqual(45, worksheet.cell(worksheet.max_row, 10).value)

    def test_summary_narrowly_fits_current_page(self):
        worksheet = self.boundary(remaining=63.2)
        self.assertGreaterEqual(_PrintLayout(worksheet, 10).remaining, 63)
        self.write(worksheet, self.rows())
        self.assertEqual([], worksheet.row_breaks.brk)

    def test_summary_narrowly_does_not_fit_moves_before_heading(self):
        worksheet = self.boundary(remaining=62.6)
        self.assertLess(_PrintLayout(worksheet, 10).remaining, 63)
        end = self.write(worksheet, self.rows())
        self.assertEqual([9], [item.id for item in worksheet.row_breaks.brk])
        self.assertEqual(12, end)
        self.assertEqual(PRODUCT_SUMMARY_HEADING, worksheet["A10"].value)
        self.assertEqual("PRODUCT", worksheet["A11"].value)
        self.assertEqual(1, worksheet["J12"].value)

    def test_fresh_page_boundary_summary_is_not_split(self):
        worksheet = self.boundary()
        rows = self.rows(24)
        extra = math.floor((_PrintLayout(worksheet, 10).fresh_space - sum(row[3] for row in rows)) * 5) / 5
        rows[2] = (*rows[2][:3], rows[2][3] + extra, rows[2][4])
        self.assertLessEqual(sum(row[3] for row in rows), _PrintLayout(worksheet, 10).fresh_space)
        self.write(worksheet, rows)
        self.assertEqual([9], [item.id for item in worksheet.row_breaks.brk])
        self.assertEqual(1, sum(c.value == PRODUCT_SUMMARY_HEADING for row in worksheet for c in row))

    def test_oversized_summary_repeats_headers_without_duplicate_quantities(self):
        worksheet = self.boundary()
        rows = self.rows(60)
        end = self.write(worksheet, rows)
        self.assertGreater(len(worksheet.row_breaks.brk), 1)
        self.assertEqual(sum(range(1, 61)), sum(worksheet.cell(row, 10).value for row in range(10, end + 1)
                                               if isinstance(worksheet.cell(row, 10).value, int)))
        for item in worksheet.row_breaks.brk:
            self.assertEqual(PRODUCT_SUMMARY_HEADING, worksheet.cell(item.id + 1, 1).value)
            self.assertEqual("PACKAGE TYPE", worksheet.cell(item.id + 2, 6).value)
            self.assertIsInstance(worksheet.cell(item.id + 3, 10).value, int)

    def test_logical_product_continuation_that_fits_fresh_page_is_kept_together(self):
        worksheet = self.boundary(remaining=100)
        rows = self.rows(1)[:2] + [("Part1", "BAG", 3, 294, "General"),
                                 ("Part2", "continued", None, 174, "General")]
        self.write(worksheet, rows)
        self.assertEqual([9], [item.id for item in worksheet.row_breaks.brk])
        self.assertEqual(3, worksheet["J12"].value)
        self.assertIsNone(worksheet["J13"].value)

    def test_oversized_logical_product_continues_with_headers_and_counted_once(self):
        worksheet = self.boundary()
        rows = self.rows(1)[:2] + [("Part1", "BAG", 3, 294, "General"),
                                 ("Part2", "continued", None, 294, "General"),
                                 ("Part3", "continued", None, 294, "General")]
        end = self.write(worksheet, rows)
        self.assertEqual(3, sum(worksheet.cell(row, 10).value for row in range(10, end + 1)
                                if isinstance(worksheet.cell(row, 10).value, int)))
        self.assertEqual(["Part1", "Part2", "Part3"], [worksheet.cell(row, 1).value for row in range(10, end + 1)
                                                        if worksheet.cell(row, 6).value in ("BAG", "continued")])
        self.assertEqual(len(worksheet.row_breaks.brk), sum(c.value == PRODUCT_SUMMARY_HEADING
                                                         for row in worksheet for c in row) - 1)

    def test_changed_actual_row_height_changes_break_decision(self):
        worksheet = self.boundary(remaining=64)
        worksheet.row_dimensions[9].height += 2
        self.write(worksheet, self.rows())
        self.assertEqual([9], [item.id for item in worksheet.row_breaks.brk])

    def test_changed_page_margin_changes_break_decision(self):
        worksheet = self.boundary(remaining=64)
        worksheet.page_margins.bottom += 0.5
        self.write(worksheet, self.rows())
        self.assertEqual([9], [item.id for item in worksheet.row_breaks.brk])

    def test_existing_fit_width_and_repeated_main_headers_are_preserved(self):
        worksheet = self.workbook([self.order()])
        self.assertEqual((1, 0), (worksheet.page_setup.fitToWidth, worksheet.page_setup.fitToHeight))
        self.assertTrue(worksheet.sheet_properties.pageSetUpPr.fitToPage)
        self.assertIsNone(worksheet.page_setup.scale)
        self.assertEqual("$7:$8", worksheet.print_title_rows)
        self.assertEqual("landscape", worksheet.page_setup.orientation)
        self.assertEqual(str(worksheet.PAPERSIZE_A4), str(worksheet.page_setup.paperSize))

    def test_slots_do_not_change_non_pallet_aggregation_or_frozen_ids(self):
        orders = [self.order(1, pallets=1), self.order(2), self.order(3)]
        before = deepcopy(orders)
        products = _product_quantity_summary(orders)
        worksheet = self.workbook(orders)
        self.handwriting(worksheet, 3)
        self.assertEqual(90, worksheet.cell(worksheet.max_row, 10).value)
        self.assertEqual(products, _product_quantity_summary(orders))
        self.assertEqual(before, orders)
        self.assertEqual(["QA-INV-1", "QA-INV-2", "QA-INV-3"], [worksheet.cell(row, 4).value for row in (9, 10, 11)])

    def test_confirmed_carton_products_keep_shipping_units_and_original_weight(self):
        from tests.test_attache_carton_packaging import carton_payload, normalize
        lines = [ProductDetailLine(**line) for line in normalize(carton_payload())["product_lines"]]
        order = replace(self.order(lines=lines), carton_quantity_snapshot=2)
        worksheet = self.workbook([order])
        self.handwriting(worksheet, 1)
        self.assertEqual(42, worksheet["F9"].value)
        self.assertIn("1 Carton", str(worksheet["E9"].value))
        self.assertEqual([1, 1], [worksheet.cell(row, 10).value for row in range(finish_row(worksheet) + 4, worksheet.max_row + 1)])

    def test_old_footer_totals_remain_absent(self):
        worksheet = self.workbook([self.order()])
        values = [cell.value for row in worksheet for cell in row]
        for label in ("Known product total", "UNALLOCATED loose bags", "Total loose bags"):
            self.assertNotIn(label, values)
