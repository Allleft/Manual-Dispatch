from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


COLLECTION_HEADERS = [
    "No.",
    "OP SHOP Name",
    "Suburb",
    "Address",
    "Pickup Date",
    "Run Type",
    "Category",
    "Route Group",
    "Frequency",
    "Time Window",
    "Call Before Arrival",
    "Call Timing",
    "Primary Contact",
    "Primary Phone",
    "Secondary Contact",
    "Secondary Phone",
    "Access",
    "Key Required",
    "Trailer Restriction",
    "Notes",
    "Status",
]


def build_opshop_pickup_collection_excel(collection):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "OP SHOP Collection"

    metadata = [
        ("Dispatch Date", collection.dispatch_date),
        ("Pickup Date", collection.pickup_date),
        ("Driver", collection.driver_name_snapshot),
        ("Saved By", collection.saved_by_account_name or "Unknown"),
    ]
    for row_index, (label, value) in enumerate(metadata, start=1):
        worksheet.cell(row=row_index, column=1, value=label).font = Font(bold=True)
        worksheet.cell(row=row_index, column=2, value=value)

    header_row = len(metadata) + 2
    for column_index, header in enumerate(COLLECTION_HEADERS, start=1):
        worksheet.cell(row=header_row, column=column_index, value=header).font = Font(
            bold=True
        )

    for row_index, pickup in enumerate(collection.pickups, start=header_row + 1):
        values = [
            pickup.row_no,
            pickup.opshop_name_snapshot or "",
            pickup.suburb_snapshot or "",
            pickup.street_address_snapshot or "",
            pickup.pickup_date_snapshot or "",
            pickup.run_type_snapshot or "",
            pickup.pickup_category_snapshot or "",
            pickup.route_group_name_snapshot or "",
            pickup.pickup_frequency_snapshot or "",
            pickup.time_window_snapshot or "",
            "Yes" if pickup.call_before_arrival_snapshot else "No",
            pickup.call_timing_snapshot or "",
            pickup.primary_contact_snapshot or "",
            pickup.primary_phone_snapshot or "",
            pickup.secondary_contact_snapshot or "",
            pickup.secondary_phone_snapshot or "",
            pickup.access_type_snapshot or "",
            "Yes" if pickup.key_required_snapshot else "No",
            pickup.trailer_restriction_snapshot or "",
            pickup.notes_snapshot or "",
            pickup.status_snapshot or "",
        ]
        for column_index, value in enumerate(values, start=1):
            cell = worksheet.cell(row=row_index, column=column_index, value=value)
            if column_index in {17, 20}:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    worksheet.freeze_panes = f"A{header_row + 1}"
    _apply_column_widths(worksheet)
    return _save(workbook)


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
