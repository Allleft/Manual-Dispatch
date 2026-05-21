from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


OPSHOP_RUN_SHEET_HEADERS = [
    "Driver",
    "Pickup Date",
    "Run Type",
    "OP SHOP Name",
    "Suburb",
    "Address",
    "Area / Region",
    "Primary Contact",
    "Primary Phone",
    "Secondary Contact",
    "Secondary Phone",
    "Time Window",
    "Call Before Arrival",
    "Access Type",
    "Key Required",
    "Trailer Restriction",
    "Notes",
    "Status",
]

UNASSIGNED_SECTION_TITLE = "Unassigned OP SHOP Pickups"


def build_opshop_pickup_run_sheet_excel(board_data, dispatch_date):
    """Build an independent OP SHOP pickup run sheet workbook."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "OP SHOP Run Sheet"

    worksheet["A1"] = "OP SHOP Pickup Run Sheet"
    worksheet["A1"].font = Font(bold=True, size=14)
    worksheet["A2"] = "Dispatch Date"
    worksheet["A2"].font = Font(bold=True)
    worksheet["B2"] = dispatch_date

    row_index = 4
    sections = _build_sections(board_data)

    if not sections:
        worksheet.cell(row=row_index, column=1, value=f"No OP SHOP pickups for {dispatch_date}.")
        worksheet.cell(row=row_index, column=1).font = Font(bold=True)
        _apply_column_widths(worksheet)
        return _save_workbook(workbook)

    for section_title, pickups in sections:
        worksheet.cell(row=row_index, column=1, value=section_title).font = Font(bold=True)
        row_index += 1

        for column_index, header in enumerate(OPSHOP_RUN_SHEET_HEADERS, start=1):
            cell = worksheet.cell(row=row_index, column=column_index, value=header)
            cell.font = Font(bold=True)
        row_index += 1

        for pickup in pickups:
            for column_index, value in enumerate(_pickup_row(pickup, section_title), start=1):
                cell = worksheet.cell(row=row_index, column=column_index, value=value)
                if column_index == 17:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            row_index += 1

        row_index += 1

    worksheet.freeze_panes = "A5"
    _apply_column_widths(worksheet)
    return _save_workbook(workbook)


def _build_sections(board_data):
    drivers_by_id = {driver.driver_id: driver for driver in getattr(board_data, "drivers", [])}
    pickups_by_id = {}

    for pickup in list(getattr(board_data, "scheduled_opshop_pickups", []) or []):
        pickups_by_id[pickup.pickup_task_id] = pickup
    for pickup in list(getattr(board_data, "oncall_opshop_pickups", []) or []):
        pickups_by_id[pickup.pickup_task_id] = pickup
    for pickup in list(getattr(board_data, "assigned_opshop_pickups", []) or []):
        pickups_by_id[pickup.pickup_task_id] = pickup

    grouped = {}
    unassigned = []
    for pickup in pickups_by_id.values():
        driver_id = pickup.driver_id or pickup.assigned_driver_id
        if not driver_id:
            unassigned.append(pickup)
            continue
        driver_name = (
            pickup.assigned_driver_name
            or getattr(drivers_by_id.get(driver_id), "name", None)
            or driver_id
        )
        grouped.setdefault(driver_name, []).append(pickup)

    sections = []
    for driver_name in sorted(grouped):
        sections.append((driver_name, _sort_pickups(grouped[driver_name])))
    if unassigned:
        sections.append((UNASSIGNED_SECTION_TITLE, _sort_pickups(unassigned)))
    return sections


def _sort_pickups(pickups):
    return sorted(
        pickups,
        key=lambda pickup: (
            pickup.pickup_date or "",
            pickup.suburb or "",
            pickup.opshop_name or "",
            pickup.pickup_task_id or "",
        ),
    )


def _pickup_row(pickup, section_title):
    return [
        "" if section_title == UNASSIGNED_SECTION_TITLE else section_title,
        pickup.pickup_date,
        pickup.run_type,
        pickup.opshop_name,
        pickup.suburb,
        pickup.street_address,
        pickup.area_region,
        pickup.primary_contact,
        pickup.primary_phone,
        pickup.secondary_contact,
        pickup.secondary_phone,
        pickup.time_window,
        _format_bool(pickup.call_before_arrival),
        pickup.access_type,
        _format_bool(pickup.key_required),
        pickup.trailer_restriction,
        _format_notes(pickup),
        pickup.status,
    ]


def _format_bool(value):
    return "Yes" if bool(value) else "No"


def _format_notes(pickup):
    notes = []
    if pickup.status_notes:
        notes.append(f"Status: {pickup.status_notes}")
    if pickup.task_notes:
        notes.append(f"Task: {pickup.task_notes}")
    return "\n".join(notes)


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
