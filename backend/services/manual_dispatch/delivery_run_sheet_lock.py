DELIVERY_RUN_SHEET_SAVED_LOCK_MESSAGE = (
    "Delivery Run Sheet has already been saved for this driver and delivery date."
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
