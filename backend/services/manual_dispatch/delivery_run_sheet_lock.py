DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE = (
    "Delivery Run Sheet has already been saved for this driver and delivery date."
)
DELIVERY_RUN_SHEET_GENERATED_LOCK_MESSAGE = (
    "Delivery Run Sheet has already been generated for this driver and delivery "
    "date. Cancel the generated Delivery Run Sheet before making changes."
)


def is_delivery_run_sheet_finalized(
    repository,
    dispatch_date,
    driver_id,
    delivery_date,
):
    return repository.has_saved_delivery_run_sheet(
        dispatch_date,
        driver_id,
        delivery_date,
    )


def ensure_delivery_run_sheet_not_finalized(
    repository,
    dispatch_date,
    driver_id,
    delivery_date,
):
    if is_delivery_run_sheet_finalized(
        repository,
        dispatch_date,
        driver_id,
        delivery_date,
    ):
        raise ValueError(DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE)


def ensure_delivery_run_sheet_key_mutable(
    repository,
    dispatch_date,
    driver_id,
    delivery_date,
):
    run_sheet = repository.get_delivery_run_sheet_for_driver(
        dispatch_date,
        delivery_date,
        driver_id,
    )
    _raise_for_run_sheet(run_sheet)


def ensure_order_not_reserved(repository, dispatch_date, order_id):
    for run_sheet in repository.list_delivery_run_sheets(dispatch_date):
        if any(
            order.task_type == "ORDER" and order.task_id == order_id
            for trip in run_sheet.trips
            for order in trip.orders
        ):
            _raise_for_run_sheet(run_sheet)


def _raise_for_run_sheet(run_sheet):
    if not run_sheet:
        return
    if run_sheet.status == "SAVED":
        raise ValueError(DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE)
    if run_sheet.status == "GENERATED":
        raise ValueError(DELIVERY_RUN_SHEET_GENERATED_LOCK_MESSAGE)
