from io import BytesIO

from datetime import datetime
import math
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.page import PageMargins


DAILY_RUN_SHEET_HEADERS = [
    "Sequence",
    "Customer Name",
    "Suburb",
    "Invoice #",
    "PRODUCT",
    "KG'S",
    "Pallets",
    "COD",
    "CQ",
    "Time In",
    "Time Out",
    "PRINT NAME",
    "SIGNATURE",
    "NO. # PALLETS RETND",
]
MIN_TABLE_ROWS = 18
_INVALID_SHEET_NAME_CHARACTERS = re.compile(r"[\\/*?:\[\]]")


def build_delivery_run_sheet_excel(run_sheet):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Daily Run Sheet"
    _configure_print_layout(worksheet)
    _write_daily_run_sheet_form(worksheet, run_sheet, run_sheet.delivery_date)
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
        _write_daily_run_sheet_form(worksheet, run_sheet, delivery_date)
    return _save(workbook)


def _configure_print_layout(worksheet):
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.page_margins = PageMargins(
        left=0.12,
        right=0.2,
        top=0.39,
        bottom=0.16,
        header=0.1,
        footer=0.1,
    )


def _write_daily_run_sheet_form(worksheet, run_sheet, delivery_date):
    worksheet.sheet_view.showGridLines = False
    worksheet.print_options.horizontalCentered = True
    worksheet.print_title_rows = "7:8"

    worksheet.merge_cells("A1:B1")
    worksheet.merge_cells("C1:E1")
    worksheet.merge_cells("F1:J1")
    worksheet.merge_cells("K1:N1")
    worksheet["A1"] = "DAILY RUN SHEET"
    worksheet["A1"].font = Font(bold=True, size=14)
    worksheet["C1"] = f"DATE  {_display_date(delivery_date)}"
    worksheet["F1"] = f"DRIVER: {run_sheet.driver_name_snapshot or ''}"
    worksheet["K1"] = f"REGO #: {_rego_snapshot_display(run_sheet)}"
    for coordinate in ("A1", "C1", "F1", "K1"):
        worksheet[coordinate].font = Font(bold=True, size=11)
        worksheet[coordinate].alignment = Alignment(
            vertical="center",
            wrap_text=True,
            shrink_to_fit=False,
        )

    worksheet["B3"] = "START TIME: ____________________________________"
    worksheet.merge_cells("B5:E5")
    worksheet["B5"] = "TIME LOADING STARTED(TO BE FILLED IN BY STOREMAN)___________"
    worksheet.merge_cells("F5:N5")
    worksheet["F5"] = "TIME LOADING COMPLETED(TO BE FILLED IN BY STOREMAN)_____________"
    for coordinate in ("B3", "B5", "F5"):
        worksheet[coordinate].font = Font(bold=True, size=9)
        worksheet[coordinate].alignment = Alignment(vertical="center", wrap_text=True)

    worksheet["J7"] = "Time"
    worksheet["K7"] = "Time"
    worksheet["M7"] = "Comments"
    worksheet["N7"] = "PALLETS"
    for coordinate in ("J7", "K7", "M7", "N7"):
        worksheet[coordinate].font = Font(bold=True, size=9)
        worksheet[coordinate].alignment = Alignment(horizontal="center", vertical="center")

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_row = 8
    for column_index, header in enumerate(DAILY_RUN_SHEET_HEADERS, start=1):
        cell = worksheet.cell(row=header_row, column=column_index, value=header)
        cell.font = Font(bold=True, size=8)
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    worksheet.row_dimensions[header_row].height = 24

    snapshot_rows = _ordered_snapshot_rows(run_sheet)
    row_index = header_row + 1
    for row_no, order in enumerate(snapshot_rows, start=1):
        _write_order_row(worksheet, row_index, row_no, order, border)
        row_index += 1
    for row_no in range(len(snapshot_rows) + 1, MIN_TABLE_ROWS + 1):
        _write_empty_row(worksheet, row_index, row_no, border)
        row_index += 1

    finish = worksheet.cell(row=row_index + 1, column=2, value="FINISH TIME:____________________________________")
    finish.font = Font(bold=True, size=9)
    finish.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[row_index + 1].height = 22
    worksheet.print_area = f"A1:N{row_index + 1}"
    _apply_column_widths(worksheet)
    _apply_row_heights(worksheet)


def _ordered_snapshot_rows(run_sheet):
    return [
        order
        for trip in (run_sheet.trips or [])
        for order in (trip.orders or [])
    ]


def delivery_run_sheet_product_display(order):
    displays = []
    for line_no, line in enumerate(
        getattr(order, "product_lines_snapshot", None) or [],
        start=1,
    ):
        product_name = str(getattr(line, "product_name", "") or "").strip()
        product_code = str(getattr(line, "product_code", "") or "").strip()
        quantity = getattr(line, "quantity", None)
        unit = str(getattr(line, "unit", "") or "").strip()
        if not product_name and not product_code:
            continue
        identity = " ".join(
            part
            for part in (
                f"[{product_code}]" if product_code else "",
                product_name,
            )
            if part
        )
        quantity_text = " ".join(
            part for part in (_display_number(quantity), unit) if part
        )
        display = f"{line_no}. {identity}"
        if quantity_text:
            display += f" - {quantity_text}"
        package_quantity = getattr(line, "package_quantity", None)
        package_unit = str(getattr(line, "package_unit", "") or "").strip()
        package_text = " ".join(
            part for part in (_display_number(package_quantity), package_unit) if part
        )
        if package_text:
            display += f" | Packaging: {package_text}"
        displays.append(display)
    if displays:
        return "\n".join(displays)
    return str(getattr(order, "product_snapshot", "") or "").strip()


def _product_quantity_total(order, units):
    total = sum(
        float(getattr(line, "quantity", 0) or 0)
        for line in getattr(order, "product_lines_snapshot", None) or []
        if str(getattr(line, "unit", "") or "").strip().upper() in units
    )
    return "" if total == 0 else int(total) if total.is_integer() else total


def _display_number(value):
    if value is None or value == "":
        return ""
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _wrapped_line_count(value, column_width):
    usable_width = max(1, int(column_width) - 2)
    return sum(
        max(1, math.ceil(len(line) / usable_width))
        for line in str(value or "").split("\n")
    )


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


def _write_order_row(worksheet, row_index, row_no, order, border):
    product_display = delivery_run_sheet_product_display(order)
    values = [
        row_no,
        order.company_name_snapshot or "",
        order.suburb_snapshot or "",
        order.invoice_number_snapshot or "",
        product_display,
        _product_quantity_total(order, {"KG", "KGS"}),
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
            horizontal="center"
            if column_index in {1, 4, 6, 7, 8, 9, 10, 11, 14}
            else "left",
            vertical="top",
            wrap_text=column_index in {2, 3, 4, 5, 13},
            shrink_to_fit=False,
        )
        if column_index in {6, 7, 14} and value != "":
            cell.number_format = "General"
    content_lines = max(
        _wrapped_line_count(order.company_name_snapshot, 29),
        _wrapped_line_count(order.suburb_snapshot, 20),
        _wrapped_line_count(order.invoice_number_snapshot, 13),
        _wrapped_line_count(product_display, 55),
    )
    worksheet.row_dimensions[row_index].height = max(21.95, 15.5 * content_lines + 3)


def _write_empty_row(worksheet, row_index, row_no, border):
    for column_index in range(1, 15):
        cell = worksheet.cell(row=row_index, column=column_index, value=row_no if column_index == 1 else "")
        cell.border = border
        cell.alignment = Alignment(horizontal="center" if column_index == 1 else "left", vertical="top")
    worksheet.row_dimensions[row_index].height = 21.95


def _number_or_blank(value):
    return "" if value is None else value


def _rego_snapshot_display(run_sheet):
    rego = str(getattr(run_sheet, "vehicle_rego_snapshot", "") or "").strip()
    return rego or "Not selected"


def _apply_column_widths(worksheet):
    widths = {
        "A": 5,
        "B": 29,
        "C": 20,
        "D": 13,
        "E": 55,
        "F": 10,
        "G": 9,
        "H": 9,
        "I": 7,
        "J": 12,
        "K": 12,
        "L": 20,
        "M": 27,
        "N": 17,
    }
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width
    worksheet.freeze_panes = "B9"


def _apply_row_heights(worksheet):
    for row_index in (1, 2, 3):
        worksheet.row_dimensions[row_index].height = 21
    for row_index in (5, 6):
        worksheet.row_dimensions[row_index].height = 15.75
    worksheet.row_dimensions[8].height = 24


def _save(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
