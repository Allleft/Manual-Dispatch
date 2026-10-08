"""Shared persistence rules; NULL remains an explicit legacy scope."""


def validate_delivery_trip(trip_no):
    if trip_no not in ("trip1", "trip2"):
        raise ValueError("trip_no must be explicitly trip1 or trip2.")
    return trip_no


def validate_run_sheet_snapshot(run_sheet):
    if run_sheet.status not in ("GENERATED", "SAVED") or run_sheet.execution_status not in ("OPEN", "CLOSED"):
        raise ValueError("Invalid Delivery Run Sheet state.")
    scope = run_sheet.trip_no
    if scope is not None:
        validate_delivery_trip(scope)
        if run_sheet.legacy_summary_id is not None:
            raise ValueError("Legacy Final Trip Summary markers require a NULL scope.")
        if len(run_sheet.trips) != 1 or not run_sheet.trips[0].orders:
            raise ValueError("A per-trip Run Sheet must contain exactly one nonempty trip.")
    row_ids = set()
    positions = set()
    for trip in run_sheet.trips:
        validate_delivery_trip(trip.trip_no)
        if scope is not None and trip.trip_no != scope:
            raise ValueError("Run Sheet trip does not match its header scope.")
        for row in trip.orders:
            if row.trip_no != trip.trip_no or row.task_type != "ORDER":
                raise ValueError("Run Sheet rows must match their Delivery trip.")
            if row.row_id in row_ids or (trip.trip_no, row.row_no) in positions:
                raise ValueError("Duplicate Delivery Run Sheet snapshot row.")
            row_ids.add(row.row_id)
            positions.add((trip.trip_no, row.row_no))


def legacy_vehicle_projection(assignments):
    """LEGACY REQUIRED: fail-closed reads for old boards/Final Trip Summaries.

    Two explicit equal trips project as a day selection. Neither a missing trip
    nor a divergent pair can be inferred from historical NULL carryover.
    New trip controls and Run Sheet generation never use this projection.
    """
    from dataclasses import replace
    from backend.errors import StateChangedConflictError

    grouped = {}
    for item in assignments:
        grouped.setdefault((item.delivery_date, item.driver_id), []).append(item)
    projected = []
    occupied = set()
    for identity, rows in sorted(grouped.items()):
        legacy = [row for row in rows if row.trip_no is None]
        trips = {row.trip_no: row for row in rows if row.trip_no is not None}
        if len(legacy) > 1 or len(trips) != len(rows) - len(legacy):
            raise ValueError("Driver vehicle assignment integrity error: duplicate driver/trip.")
        if trips:
            if set(trips) != {"trip1", "trip2"} or trips["trip1"].vehicle_id != trips["trip2"].vehicle_id:
                raise StateChangedConflictError("Explicit trip_no is required for partial or divergent trip-specific vehicle selections.")
            selection = replace(trips["trip1"], trip_no=None)
        else:
            selection = replace(legacy[0])
        vehicle_key = identity[0], selection.vehicle_id
        if vehicle_key in occupied:
            raise ValueError("Driver vehicle assignment integrity error: duplicate vehicle.")
        occupied.add(vehicle_key)
        projected.append(selection)
    return projected
