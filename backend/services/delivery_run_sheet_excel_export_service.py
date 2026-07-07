from io import BytesIO

from datetime import datetime
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.page import PageMargins


DAILY_RUN_SHEET_HEADERS = [
    "Customer Name",
    "Suburb",
    "Invoice #",
    "PRODUCT",
    "KGS",
    "Pallets",
    "COD",
    "CQ",
    "Time Out",
    "Time In",
    "Print Name",
    "Comments / Signature",
    "No. of Pallets Returned",
]
DELIVERY_DATE_EXPORT_HEADERS = [
    "Customer Name",
    "Suburb",
    "Invoice #",
    "PRODUCT",
    "KGS",
    "Pallets",
]
MIN_TABLE_ROWS = 18
_INVALID_SHEET_NAME_CHARACTERS = re.compile(r"[\\/*?:\[\]]")


def build_delivery_run_sheet_excel(run_sheet):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Daily Run Sheet"
    _configure_print_layout(worksheet)
    _write_top_form(worksheet, run_sheet)
    _write_order_table(worksheet, run_sheet)
    _apply_column_widths(worksheet)
    return _save(workbook)


def build_delivery_run_sheets_excel(run_sheets, delivery_date):
    if not run_sheets:
        raise ValueError(
            "No Generated or Saved Delivery Run Sheets are available for this Delivery Date."
        )

    workbook = Workbook()
    workbook.remove(workbook.active)
    used_sheet_names = set()
    for run_sheet in run_sheets:
        worksheet = workbook.create_sheet(
            _unique_sheet_name(run_sheet.driver_name_snapshot, used_sheet_names)
        )
        _configure_print_layout(worksheet)
        _write_date_export_form(worksheet, run_sheet, delivery_date)
        _apply_date_export_column_widths(worksheet)
    return _save(workbook)


def _configure_print_layout(worksheet):
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.page_margins = PageMargins(
        left=0.25,
        right=0.25,
        top=0.35,
        bottom=0.35,
        header=0.1,
        footer=0.1,
    )


def _write_date_export_form(worksheet, run_sheet, delivery_date):
    worksheet.sheet_view.showGridLines = False
    worksheet.print_options.horizontalCentered = True
    worksheet.print_title_rows = "7:7"

    worksheet["A1"] = f"DATE: {_display_date(delivery_date)}"
    worksheet["A1"].font = Font(bold=True, size=11)
    worksheet.merge_cells("B1:D1")
    worksheet["B1"] = "DAILY RUN SHEET"
    worksheet["B1"].font = Font(bold=True, size=18)
    worksheet["B1"].alignment = Alignment(horizontal="center", vertical="center")
    worksheet.merge_cells("E1:F1")
    worksheet["E1"] = f"DRIVER: {run_sheet.driver_name_snapshot or ''}"
    worksheet["E1"].font = Font(bold=True, size=11)
    worksheet["E1"].alignment = Alignment(
        horizontal="right",
        vertical="center",
        wrap_text=True,
    )
    worksheet.row_dimensions[1].height = 26

    operational_fields = [
        (3, "START TIME: ______________________"),
        (
            4,
            "TIME LOADING STARTED (TO BE FILLED IN BY STOREMAN): ______________________",
        ),
        (
            5,
            "TIME LOADING COMPLETED (TO BE FILLED IN BY STOREMAN): ______________________",
        ),
    ]
    for row_index, label in operational_fields:
        worksheet.merge_cells(
            start_row=row_index,
            start_column=1,
            end_row=row_index,
            end_column=len(DELIVERY_DATE_EXPORT_HEADERS),
        )
        cell = worksheet.cell(row=row_index, column=1, value=label)
        cell.font = Font(bold=True, size=10)
        cell.alignment = Alignment(vertical="center")
        worksheet.row_dimensions[row_index].height = 20

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_row = 7
    for column_index, header in enumerate(DELIVERY_DATE_EXPORT_HEADERS, start=1):
        cell = worksheet.cell(row=header_row, column=column_index, value=header)
        cell.font = Font(bold=True, size=10)
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    worksheet.row_dimensions[header_row].height = 24

    snapshot_rows = _ordered_snapshot_rows(run_sheet)
    row_index = header_row + 1
    for order in snapshot_rows:
        _write_date_export_order_row(worksheet, row_index, order, border)
        row_index += 1
    for _ in range(max(MIN_TABLE_ROWS - len(snapshot_rows), 0)):
        _write_date_export_empty_row(worksheet, row_index, border)
        row_index += 1

    worksheet.merge_cells(
        start_row=row_index + 1,
        start_column=1,
        end_row=row_index + 1,
        end_column=len(DELIVERY_DATE_EXPORT_HEADERS),
    )
    finish = worksheet.cell(
        row=row_index + 1,
        column=1,
        value="FINISH TIME: ______________________",
    )
    finish.font = Font(bold=True, size=10)
    finish.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[row_index + 1].height = 22
    worksheet.print_area = f"A1:F{row_index + 1}"


def _ordered_snapshot_rows(run_sheet):
    return [
        order
        for trip in (run_sheet.trips or [])
        for order in (trip.orders or [])
    ]


def delivery_run_sheet_product_display(order):
    names = []
    seen = set()
    for line in getattr(order, "product_lines_snapshot", None) or []:
        product_name = str(getattr(line, "product_name", "") or "").strip()
        if not product_name:
            continue
        key = " ".join(product_name.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(product_name)
    if names:
        return "\n".join(names)
    return str(getattr(order, "product_snapshot", "") or "").strip()


def _line_count(value):
    return max(1, str(value or "").count("\n") + 1)


def _write_date_export_order_row(worksheet, row_index, order, border):
    product_display = delivery_run_sheet_product_display(order)
    values = [
        order.company_name_snapshot or "",
        order.suburb_snapshot or "",
        order.invoice_number_snapshot or order.order_no_snapshot or "",
        product_display,
        "",
        _number_or_blank(order.pallet_quantity_snapshot),
    ]
    for column_index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=value)
        cell.border = border
        cell.alignment = Alignment(
            horizontal="right" if column_index in {5, 6} else "left",
            vertical="top",
            wrap_text=column_index in {1, 2, 4},
        )
        if column_index in {5, 6} and value != "":
            cell.number_format = "General"
    worksheet.row_dimensions[row_index].height = max(22, 16 * _line_count(product_display))


def _write_date_export_empty_row(worksheet, row_index, border):
    for column_index in range(1, len(DELIVERY_DATE_EXPORT_HEADERS) + 1):
        cell = worksheet.cell(row=row_index, column=column_index, value="")
        cell.border = border
    worksheet.row_dimensions[row_index].height = 22


def _apply_date_export_column_widths(worksheet):
    widths = {
        "A": 29,
        "B": 17,
        "C": 15,
        "D": 36,
        "E": 8,
        "F": 9,
    }
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width
    worksheet.freeze_panes = "A8"


def _unique_sheet_name(driver_name, used_sheet_names):
    base_name = _INVALID_SHEET_NAME_CHARACTERS.sub(" ", str(driver_name or "Driver"))
    base_name = " ".join(base_name.split()).strip("'") or "Driver"
    base_name = base_name[:31]
    candidate = base_name
    sequence = 2
    while candidate.casefold() in used_sheet_names:
        suffix = f" ({sequence})"
        candidate = f"{base_name[:31 - len(suffix)]}{suffix}"
        sequence += 1
    used_sheet_names.add(candidate.casefold())
    return candidate


def _display_date(value):
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")


def _write_top_form(worksheet, run_sheet):
    worksheet.merge_cells("D1:J1")
    title = worksheet["D1"]
    title.value = "DAILY RUN SHEET"
    title.font = Font(bold=True, size=18)
    title.alignment = Alignment(horizontal="center")

    worksheet["A1"] = "Date:"
    worksheet["A1"].font = Font(bold=True)
    worksheet["B1"] = run_sheet.delivery_date
    worksheet["A2"] = "Driver:"
    worksheet["A2"].font = Font(bold=True)
    worksheet["B2"] = run_sheet.driver_name_snapshot

    manual_fields = [
        (4, "Start Time:"),
        (5, "Time Loading Started (to be filled in by storeman):"),
        (6, "Time Loading Completed (to be filled in by storeman):"),
        (7, "Finish Time:"),
    ]
    for row_index, label in manual_fields:
        worksheet.cell(row=row_index, column=1, value=label).font = Font(bold=True)
        worksheet.merge_cells(start_row=row_index, start_column=2, end_row=row_index, end_column=5)
        worksheet.cell(row=row_index, column=2, value="____________________________")


def _write_order_table(worksheet, run_sheet):
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_row = 9
    for column_index, header in enumerate(DAILY_RUN_SHEET_HEADERS, start=1):
        cell = worksheet.cell(row=header_row, column=column_index, value=header)
        cell.font = Font(bold=True)
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row_index = header_row + 1
    written_rows = 0
    trips = {trip.trip_no: trip for trip in run_sheet.trips}
    for trip_no in ("trip1", "trip2"):
        trip = trips.get(trip_no)
        if not trip or not trip.orders:
            continue
        if trip_no == "trip2" and written_rows:
            worksheet.merge_cells(
                start_row=row_index,
                start_column=1,
                end_row=row_index,
                end_column=len(DAILY_RUN_SHEET_HEADERS),
            )
            divider = worksheet.cell(row=row_index, column=1, value="TRIP 2")
            divider.font = Font(bold=True)
            divider.alignment = Alignment(horizontal="center")
            divider.border = border
            row_index += 1
        for order in trip.orders:
            _write_order_row(worksheet, row_index, order, border)
            row_index += 1
            written_rows += 1

    empty_rows = max(MIN_TABLE_ROWS - written_rows, 6)
    for _ in range(empty_rows):
        _write_empty_row(worksheet, row_index, border)
        row_index += 1


def _write_order_row(worksheet, row_index, order, border):
    product_display = delivery_run_sheet_product_display(order)
    values = [
        order.company_name_snapshot or "",
        order.suburb_snapshot or "",
        order.invoice_number_snapshot or "",
        product_display,
        "",
        _number_or_blank(order.pallet_quantity_snapshot),
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
    for column_index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=value)
        cell.border = border
        cell.alignment = Alignment(
            horizontal="right" if column_index in {5, 6} else "left",
            vertical="top",
            wrap_text=column_index in {1, 4, 12},
        )
        if column_index in {5, 6} and value != "":
            cell.number_format = "General"
    worksheet.row_dimensions[row_index].height = max(18, 15 * _line_count(product_display))


def _write_empty_row(worksheet, row_index, border):
    for column_index in range(1, len(DAILY_RUN_SHEET_HEADERS) + 1):
        cell = worksheet.cell(row=row_index, column=column_index, value="")
        cell.border = border


def _number_or_blank(value):
    return "" if value is None else value


def _apply_column_widths(worksheet):
    widths = {
        "A": 24,
        "B": 16,
        "C": 12,
        "D": 26,
        "E": 8,
        "F": 8,
        "G": 8,
        "H": 8,
        "I": 11,
        "J": 11,
        "K": 18,
        "L": 26,
        "M": 16,
    }
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width
    worksheet.freeze_panes = "A10"


def _save(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
