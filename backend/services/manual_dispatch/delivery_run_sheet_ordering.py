def delivery_run_sheet_driver_trip_key(run_sheet):
    return (
        (run_sheet.driver_name_snapshot or run_sheet.driver_id).casefold(),
        run_sheet.driver_id,
        {"trip1": 1, "trip2": 2}.get(run_sheet.trip_no, 0),
        run_sheet.run_sheet_id,
    )


def order_delivery_run_sheets(run_sheets):
    by_driver = sorted(run_sheets, key=delivery_run_sheet_driver_trip_key)
    return sorted(by_driver, key=lambda run_sheet: run_sheet.delivery_date, reverse=True)
