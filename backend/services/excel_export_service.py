from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font


EXPORT_HEADERS = [
    "Dispatch Date",
    "Driver Name",
    "Vehicle Rego",
    "Trip",
    "Order ID",
    "Company Name",
    "Delivery Address",
    "Suburb",
    "Postcode",
    "Zone",
    "Urgency",
    "Preferred Driver",
    "Pallet Quantity",
    "Loose Bags Quantity",
    "Start Time",
    "End Time",
    "Note",
]

TRIP_SORT_ORDER = {"trip1": 1, "trip2": 2}
NO_VEHICLE_SELECTED = "No vehicle selected"


def build_manual_dispatch_excel(board_data, dispatch_date):
    """Build an Excel workbook for assigned Manual Dispatch Board Orders."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Manual Dispatch"
    worksheet.append(EXPORT_HEADERS)

    for cell in worksheet[1]:
        cell.font = Font(bold=True)

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:Q1"

    for row in _build_export_rows(board_data, dispatch_date):
        worksheet.append(row)

    _apply_column_widths(worksheet)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _build_export_rows(board_data, dispatch_date):
    orders_by_id = {order.order_id: order for order in board_data.orders}
    drivers_by_id = {driver.driver_id: driver for driver in board_data.drivers}
    vehicles_by_id = {vehicle.vehicle_id: vehicle for vehicle in board_data.vehicles}
    driver_vehicle_by_driver_and_delivery = {
        (assignment.driver_id, assignment.delivery_date): assignment
        for assignment in board_data.driver_vehicle_assignments
        if assignment.dispatch_date == dispatch_date
    }

    rows = []
    for assignment in board_data.assignments:
        if assignment.task_type != "ORDER":
            continue

        order = orders_by_id.get(assignment.task_id)
        driver = drivers_by_id.get(assignment.driver_id)
        if not order or not driver:
            continue

        vehicle_assignment = driver_vehicle_by_driver_and_delivery.get(
            (driver.driver_id, order.delivery_date),
        )
        vehicle = (
            vehicles_by_id.get(vehicle_assignment.vehicle_id)
            if vehicle_assignment
            else None
        )
        preferred_driver = (
            drivers_by_id.get(order.preferred_driver_id)
            if order.preferred_driver_id
            else None
        )

        rows.append(
            [
                dispatch_date,
                driver.name,
                vehicle.rego if vehicle else NO_VEHICLE_SELECTED,
                assignment.trip_no,
                order.order_id,
                order.company_name,
                order.delivery_address,
                order.suburb,
                order.postcode,
                order.zone,
                order.urgency,
                preferred_driver.name if preferred_driver else "",
                order.pallet_quantity,
                order.loose_bags_quantity,
                order.start_time,
                order.end_time,
                order.note,
            ]
        )

    rows.sort(key=lambda row: (row[1], TRIP_SORT_ORDER.get(row[3], 99), row[4]))
    return rows


def _apply_column_widths(worksheet):
    for column_cells in worksheet.columns:
        max_length = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        column_letter = column_cells[0].column_letter
        worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 34)
