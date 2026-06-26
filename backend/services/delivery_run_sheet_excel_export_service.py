from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.page import PageMargins


DAILY_RUN_SHEET_HEADERS = [
    "Customer Name",
    "Suburb",
    "Invoice #",
    "BAGS",
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
MIN_TABLE_ROWS = 18


def build_delivery_run_sheet_excel(run_sheet):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Daily Run Sheet"
    _configure_print_layout(worksheet)
    _write_top_form(worksheet, run_sheet)
    _write_order_table(worksheet, run_sheet)
    _apply_column_widths(worksheet)
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
    values = [
        order.company_name_snapshot or "",
        order.suburb_snapshot or "",
        order.invoice_number_snapshot or "",
        _number_or_blank(order.loose_bags_quantity_snapshot),
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
        cell.alignment = Alignment(vertical="top", wrap_text=column_index in {1, 12})


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
        "D": 8,
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
