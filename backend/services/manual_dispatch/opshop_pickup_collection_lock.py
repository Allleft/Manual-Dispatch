OPSHOP_PICKUP_COLLECTION_SAVED_LOCK_MESSAGE = (
    "OP SHOP Pickup Collection has already been saved for this driver and pickup date."
)
OPSHOP_PICKUP_COLLECTION_GENERATED_LOCK_MESSAGE = (
    "OP SHOP Pickup Collection has already been generated for this driver and "
    "pickup date. Cancel the generated OP SHOP Pickup Collection before making changes."
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


def ensure_opshop_pickup_collection_key_mutable(
    repository,
    dispatch_date,
    driver_id,
    pickup_date,
):
    collection = repository.get_opshop_pickup_collection_for_driver(
        dispatch_date,
        pickup_date,
        driver_id,
    )
    _raise_for_collection(collection)


def ensure_opshop_pickup_not_reserved(repository, dispatch_date, pickup_task_id):
    for collection in repository.list_opshop_pickup_collections():
        if any(
            pickup.pickup_task_id_snapshot == pickup_task_id
            for pickup in collection.pickups
        ):
            _raise_for_collection(collection)


def _raise_for_collection(collection):
    if not collection:
        return
    if collection.status == "SAVED":
        raise ValueError(OPSHOP_PICKUP_COLLECTION_SAVED_LOCK_MESSAGE)
    if collection.status == "GENERATED":
        raise ValueError(OPSHOP_PICKUP_COLLECTION_GENERATED_LOCK_MESSAGE)
