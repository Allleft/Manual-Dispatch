OPSHOP_PICKUP_COLLECTION_SAVED_LOCK_MESSAGE = (
    "OP SHOP Pickup Collection has already been saved for this driver and pickup date."
)


def is_opshop_pickup_collection_finalized(
    repository,
    dispatch_date,
    driver_id,
    pickup_date,
):
    return repository.has_saved_opshop_pickup_collection(
        dispatch_date,
        driver_id,
        pickup_date,
    )


def ensure_opshop_pickup_collection_not_finalized(
    repository,
    dispatch_date,
    driver_id,
    pickup_date,
):
    if is_opshop_pickup_collection_finalized(
        repository,
        dispatch_date,
        driver_id,
        pickup_date,
    ):
        raise ValueError(OPSHOP_PICKUP_COLLECTION_SAVED_LOCK_MESSAGE)
