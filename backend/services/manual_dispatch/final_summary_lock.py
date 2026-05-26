FINAL_SUMMARY_SAVED_LOCK_MESSAGE = (
    "Final Trip Summary has already been saved for this driver and delivery date."
)


def is_driver_delivery_date_finalized(repository, dispatch_date, driver_id, delivery_date):
    return repository.has_saved_final_trip_summary(
        dispatch_date,
        driver_id,
        delivery_date,
    )


def ensure_driver_delivery_date_not_finalized(
    repository,
    dispatch_date,
    driver_id,
    delivery_date,
):
    if is_driver_delivery_date_finalized(
        repository,
        dispatch_date,
        driver_id,
        delivery_date,
    ):
        raise ValueError(FINAL_SUMMARY_SAVED_LOCK_MESSAGE)
