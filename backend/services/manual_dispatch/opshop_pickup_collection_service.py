from datetime import datetime, timezone
from uuid import uuid4

from backend.schemas import (
    OpShopPickupCollection,
    OpShopPickupCollectionRowSnapshot,
)
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date,
    clean_optional_text,
    clean_required_iso_date,
    clean_required_text,
)


class OpShopPickupCollectionService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    def create_generated(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        pickup_date = clean_required_iso_date(request.pickup_date, "pickup_date")
        driver_id = clean_required_text(request.driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)

        existing = self.repository.get_opshop_pickup_collection_for_driver(
            dispatch_date,
            pickup_date,
            driver_id,
        )
        if existing:
            raise ValueError(
                "OP SHOP Pickup Collection already exists for this driver and pickup date."
            )

        pickups = self._build_pickups(pickup_date, driver_id)
        if not pickups:
            raise ValueError("At least one assigned OP SHOP pickup is required.")

        driver = self.repository.get_driver(driver_id)
        collection = OpShopPickupCollection(
            collection_id=f"OPC-{uuid4().hex.upper()}",
            dispatch_date=dispatch_date,
            pickup_date=pickup_date,
            driver_id=driver_id,
            driver_name_snapshot=driver.name,
            status="GENERATED",
            generated_at=_timestamp(),
            saved_at=None,
            saved_by_account_name=None,
            saved_by_account_id=None,
            legacy_summary_id=None,
            pickups=pickups,
        )
        try:
            return self.repository.upsert_opshop_pickup_collection(collection)
        except Exception as error:
            if self.repository.get_opshop_pickup_collection_for_driver(
                dispatch_date,
                pickup_date,
                driver_id,
            ):
                raise ValueError(
                    "OP SHOP Pickup Collection already exists for this driver and pickup date."
                ) from error
            raise

    def list(self, dispatch_date=None, pickup_date=None, status=None):
        return self.repository.list_opshop_pickup_collections(
            clean_optional_iso_date(dispatch_date, "dispatch_date"),
            clean_optional_iso_date(pickup_date, "pickup_date"),
            clean_optional_text(status).upper() if clean_optional_text(status) else None,
        )

    def get(self, collection_id):
        collection_id = clean_required_text(collection_id, "collection_id")
        collection = self.repository.get_opshop_pickup_collection(collection_id)
        if not collection:
            raise ValueError(
                f"OP SHOP Pickup Collection does not exist: {collection_id}"
            )
        return collection

    def save_generated(self, collection_id, request):
        account = self.validator.validate_saved_by_account(
            request.saved_by_account_name,
            request.saved_by_account_id,
        )
        promoted = self.repository.promote_generated_opshop_pickup_collection_to_saved(
            clean_required_text(collection_id, "collection_id"),
            _timestamp(),
            account.account_name,
            account.account_id,
        )
        if promoted:
            return self.get(collection_id)
        self._raise_transition_error(collection_id, "saved")

    def cancel_generated(self, collection_id):
        collection_id = clean_required_text(collection_id, "collection_id")
        cancelled = self.repository.delete_generated_opshop_pickup_collection(
            collection_id
        )
        if cancelled:
            return True
        self._raise_transition_error(collection_id, "cancelled")

    def get_for_export(self, collection_id):
        collection = self.get(collection_id)
        if collection.status not in {"GENERATED", "SAVED"}:
            raise ValueError(
                "Only generated or saved OP SHOP Pickup Collections can be exported."
            )
        return collection

    def get_saved_for_export(self, collection_id):
        return self.get_for_export(collection_id)

    def list_for_date_export(self, pickup_date, dispatch_date=None, status=None):
        pickup_date = clean_required_iso_date(pickup_date, "pickup_date")
        dispatch_date = clean_optional_iso_date(dispatch_date, "dispatch_date")
        status = clean_optional_text(status)
        normalized_status = status.upper() if status else None
        if normalized_status and normalized_status not in {"GENERATED", "SAVED"}:
            raise ValueError(
                "status must be GENERATED or SAVED for OP SHOP Pickup Collection export."
            )
        collections = self.repository.list_opshop_pickup_collections(
            dispatch_date,
            pickup_date,
            normalized_status,
        )
        if not normalized_status:
            collections = [
                collection
                for collection in collections
                if collection.status in {"GENERATED", "SAVED"}
            ]
        if not collections:
            raise ValueError(
                "No OP SHOP Pickup Collections available for this pickup date."
            )
        return sorted(
            collections,
            key=lambda item: (
                str(item.driver_name_snapshot or item.driver_id or ""),
                str(item.collection_id or ""),
            ),
        )

    def _raise_transition_error(self, collection_id, action):
        current = self.repository.get_opshop_pickup_collection(collection_id)
        if not current:
            raise ValueError(
                f"OP SHOP Pickup Collection does not exist: {collection_id}"
            )
        past_tense = "saved" if action == "saved" else "cancelled"
        raise ValueError(
            f"Only generated OP SHOP Pickup Collections can be {past_tense}."
        )

    def _build_pickups(self, pickup_date, driver_id):
        items = self.repository.list_collectable_opshop_pickup_board_items(
            pickup_date,
            driver_id,
        )
        return [
            OpShopPickupCollectionRowSnapshot(
                row_id=f"OPCR-{uuid4().hex.upper()}",
                row_no=row_no,
                pickup_task_id_snapshot=pickup.pickup_task_id,
                opshop_name_snapshot=pickup.opshop_name,
                suburb_snapshot=pickup.suburb,
                street_address_snapshot=pickup.street_address,
                area_region_snapshot=pickup.area_region,
                pickup_date_snapshot=pickup.pickup_date,
                run_type_snapshot=pickup.run_type,
                pickup_category_snapshot=pickup.pickup_category,
                route_group_id_snapshot=pickup.route_group_id,
                route_group_name_snapshot=pickup.route_group_name,
                pickup_frequency_snapshot=pickup.pickup_frequency,
                time_window_snapshot=pickup.time_window,
                primary_contact_snapshot=pickup.primary_contact,
                primary_phone_snapshot=pickup.primary_phone,
                secondary_contact_snapshot=pickup.secondary_contact,
                secondary_phone_snapshot=pickup.secondary_phone,
                access_type_snapshot=pickup.access_type,
                key_required_snapshot=pickup.key_required,
                trailer_restriction_snapshot=pickup.trailer_restriction,
                notes_snapshot=_pickup_notes(pickup),
                status_snapshot=pickup.status,
                call_before_arrival_snapshot=pickup.call_before_arrival,
                call_timing_snapshot=pickup.call_timing,
            )
            for row_no, pickup in enumerate(items, start=1)
        ]


def _pickup_notes(pickup):
    notes = []
    for value in (pickup.task_notes, pickup.status_notes):
        cleaned = clean_optional_text(value)
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    return "\n".join(notes) or None


def _timestamp():
    return datetime.now(timezone.utc).isoformat()
