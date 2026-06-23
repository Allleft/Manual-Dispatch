from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


DELIVERY_HEADERS = [
    "No.",
    "Customer Name",
    "Suburb",
    "Address",
    "Invoice #",
    "Order #",
    "Product Details",
    "Pallets",
    "Loose Bags",
    "Notes",
]


def build_delivery_run_sheet_excel(run_sheet):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Delivery Run Sheet"

    metadata = [
        ("Dispatch Date", run_sheet.dispatch_date),
        ("Delivery Date", run_sheet.delivery_date),
        ("Driver", run_sheet.driver_name_snapshot),
        ("Rego #", run_sheet.vehicle_rego_snapshot or "No vehicle selected"),
        ("Saved By", run_sheet.saved_by_account_name or "Unknown"),
        ("Total Pallets", run_sheet.total_pallets),
        ("Total Loose Bags", run_sheet.total_loose_bags),
    ]
    for row_index, (label, value) in enumerate(metadata, start=1):
        worksheet.cell(row=row_index, column=1, value=label).font = Font(bold=True)
        worksheet.cell(row=row_index, column=2, value=value)

    row_index = len(metadata) + 2
    row_number = 1
    for trip in run_sheet.trips:
        worksheet.cell(
            row=row_index,
            column=1,
            value="Trip 1" if trip.trip_no == "trip1" else "Trip 2",
        ).font = Font(bold=True)
        row_index += 1
        for column_index, header in enumerate(DELIVERY_HEADERS, start=1):
            worksheet.cell(row=row_index, column=column_index, value=header).font = Font(
                bold=True
            )
        row_index += 1

        for order in trip.orders:
            values = [
                row_number,
                order.company_name_snapshot or "",
                order.suburb_snapshot or "",
                order.delivery_address_snapshot or "",
                order.invoice_number_snapshot or "",
                order.order_no_snapshot or "",
                _product_details(order),
                order.pallet_quantity_snapshot,
                order.loose_bags_quantity_snapshot,
                order.note_snapshot or "",
            ]
            for column_index, value in enumerate(values, start=1):
                cell = worksheet.cell(row=row_index, column=column_index, value=value)
                if column_index in {7, 10}:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            row_index += 1
            row_number += 1
        row_index += 1

    worksheet.freeze_panes = "A10"
    _apply_column_widths(worksheet)
    return _save(workbook)


def _product_details(order):
    if not order.product_lines_snapshot:
        return ""
    return "\n".join(
        f"{line.product_name} - {line.quantity} {line.unit}"
        for line in order.product_lines_snapshot
    )


def _apply_column_widths(worksheet):
    for column_cells in worksheet.columns:
        max_length = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(
            max(max_length + 2, 12),
            36,
        )


def _save(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
