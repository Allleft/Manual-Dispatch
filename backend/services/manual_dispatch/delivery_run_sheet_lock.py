DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE = (
    "Delivery Run Sheet has already been saved for this driver and delivery date."
)
DELIVERY_RUN_SHEET_GENERATED_LOCK_MESSAGE = (
    "Delivery Run Sheet has already been generated for this driver and delivery "
    "date. Cancel the generated Delivery Run Sheet before making changes."
)
DELIVERY_ORDER_ASSIGNED_LOCK_MESSAGE = (
    "Delivery Order is already assigned to a driver/trip. "
    "Unassign it before assigning it elsewhere."
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


def ensure_order_not_reserved(repository, _dispatch_date, order_id):
    run_sheet = repository.get_delivery_run_sheet_reserving_order(order_id)
    _raise_for_run_sheet(run_sheet)


def ensure_order_not_assigned_elsewhere(repository, dispatch_date, order_id):
    assignments = repository.list_assignments_for_task("ORDER", order_id)
    if any(assignment.dispatch_date != dispatch_date for assignment in assignments):
        raise ValueError(DELIVERY_ORDER_ASSIGNED_LOCK_MESSAGE)


def _raise_for_run_sheet(run_sheet):
    if not run_sheet:
        return
    if run_sheet.status == "SAVED":
        raise ValueError(DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE)
    if run_sheet.status == "GENERATED":
        raise ValueError(DELIVERY_RUN_SHEET_GENERATED_LOCK_MESSAGE)
