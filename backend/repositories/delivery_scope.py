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
    """The current UI has an explicit day-level compatibility contract.

    A migrated carryover may have equal seeded trip selections. Divergent
    operational selections cannot be interpreted by the old day-level UI.
    """
    legacy = [item for item in assignments if item.trip_no is None]
    by_identity = {(item.delivery_date, item.driver_id): item for item in legacy}
    if len(by_identity) != len(legacy):
        raise ValueError("Driver vehicle assignment integrity error: duplicate driver.")
    occupied = set()
    for item in legacy:
        key = item.delivery_date, item.vehicle_id
        if key in occupied:
            raise ValueError("Driver vehicle assignment integrity error: duplicate vehicle.")
        occupied.add(key)
    for item in assignments:
        if item.trip_no is None:
            continue
        carryover = by_identity.get((item.delivery_date, item.driver_id))
        if carryover is None or carryover.vehicle_id != item.vehicle_id:
            raise ValueError("Explicit trip_no is required for trip-specific vehicle selections.")
    return legacy
