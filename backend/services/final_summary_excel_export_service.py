from io import BytesIO
import re

from openpyxl import Workbook
from openpyxl.styles import Font


FINAL_SUMMARY_HEADERS = ["No.", "Customer Name", "Suburb", "Invoice #", "Product", "Pallets"]
INVALID_SHEET_CHARACTERS = re.compile(r"[\[\]\*:/\\?]")


def build_final_summary_excel(final_summaries, dispatch_date):
    """Build an Excel workbook from saved Final Trip Summary snapshots."""
    workbook = Workbook()

    if not final_summaries:
        worksheet = workbook.active
        worksheet.title = "Final Summaries"
        worksheet["A1"] = f"No saved Final Trip Summaries for {dispatch_date}"
        worksheet["A1"].font = Font(bold=True)
        worksheet.column_dimensions["A"].width = 48
        return _save_workbook(workbook)

    default_sheet = workbook.active
    workbook.remove(default_sheet)
    used_titles = set()

    for summary in final_summaries:
        worksheet = workbook.create_sheet(_safe_sheet_title(summary, used_titles))
        _write_summary_sheet(worksheet, summary)

    return _save_workbook(workbook)


def _write_summary_sheet(worksheet, summary):
    meta_rows = [
        ("Date", summary.dispatch_date),
        ("Driver", summary.driver_name_snapshot),
        ("Rego #", summary.vehicle_rego_snapshot or "No vehicle selected"),
        ("Saved By", summary.saved_by_account_name or "Unknown"),
        ("Total Pallets", summary.total_pallets),
        ("Total Loose Bags", summary.total_loose_bags),
    ]

    for row_index, (label, value) in enumerate(meta_rows, start=1):
        worksheet.cell(row=row_index, column=1, value=label).font = Font(bold=True)
        worksheet.cell(row=row_index, column=2, value=value)

    row_index = len(meta_rows) + 2
    row_number = 1

    for trip in summary.trips:
        if not trip.orders:
            continue

        worksheet.cell(row=row_index, column=1, value=_trip_label(trip.trip_no)).font = Font(bold=True)
        row_index += 1

        for column_index, header in enumerate(FINAL_SUMMARY_HEADERS, start=1):
            cell = worksheet.cell(row=row_index, column=column_index, value=header)
            cell.font = Font(bold=True)
        row_index += 1

        for order in trip.orders:
            values = [
                row_number,
                order.company_name_snapshot or "",
                order.suburb_snapshot or "",
                order.invoice_number_snapshot or "",
                order.product_snapshot or "",
                order.pallet_quantity_snapshot,
            ]
            for column_index, value in enumerate(values, start=1):
                worksheet.cell(row=row_index, column=column_index, value=value)
            row_index += 1
            row_number += 1

        row_index += 1

    worksheet.freeze_panes = "A8"
    _apply_column_widths(worksheet)


def _safe_sheet_title(summary, used_titles):
    base = summary.driver_name_snapshot or summary.driver_id or "Summary"
    title = INVALID_SHEET_CHARACTERS.sub("-", base).strip() or "Summary"
    title = title[:31]
    candidate = title
    suffix = 2

    while candidate in used_titles:
        suffix_text = f" {suffix}"
        candidate = f"{title[: 31 - len(suffix_text)]}{suffix_text}"
        suffix += 1

    used_titles.add(candidate)
    return candidate


def _trip_label(trip_no):
    return "Trip 1" if trip_no == "trip1" else "Trip 2"


def _apply_column_widths(worksheet):
    for column_cells in worksheet.columns:
        max_length = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        column_letter = column_cells[0].column_letter
        worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 34)


def _save_workbook(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
