from dataclasses import replace
from datetime import datetime, timezone
import math
import re
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
        pickup_date = clean_required_iso_date(request.pickup_date, "pickup_date")
        dispatch_date = (
            clean_optional_iso_date(request.dispatch_date, "dispatch_date")
            or pickup_date
        )
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

    def update_rows(self, collection_id, request):
        collection = self.get(collection_id)
        if collection.status != "GENERATED":
            raise ValueError(
                "Only generated OP SHOP Pickup Collections can be updated."
            )
        row_updates = list(request.rows or [])
        if not row_updates:
            raise ValueError("At least one OP SHOP Pickup Collection row is required.")

        row_ids = [
            clean_required_text(row.row_id, "row_id")
            for row in row_updates
        ]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("Duplicate OP SHOP Pickup Collection row update.")
        rows_by_id = {row.row_id: row for row in collection.pickups}
        if not set(row_ids).issubset(rows_by_id):
            raise ValueError(
                "OP SHOP Pickup Collection row does not belong to this collection."
            )

        updated_rows = []
        for row_id, row_update in zip(row_ids, row_updates):
            replacements = {}
            for field_name in row_update.model_fields_set:
                field_spec = _COLLECTION_ENTRY_FIELD_SPECS.get(field_name)
                if not field_spec:
                    continue
                snapshot_field, validator = field_spec
                replacements[snapshot_field] = validator(
                    getattr(row_update, field_name),
                    field_name,
                )
            updated_rows.append(replace(rows_by_id[row_id], **replacements))
        return self.repository.update_opshop_pickup_collection_rows(
            collection.collection_id,
            updated_rows,
        )

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
        status = clean_optional_text(status)
        normalized_status = status.upper() if status else None
        if normalized_status and normalized_status not in {"GENERATED", "SAVED"}:
            raise ValueError(
                "status must be GENERATED or SAVED for OP SHOP Pickup Collection export."
            )
        collections = self.repository.list_opshop_pickup_collections(
            None,
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


_ENTRY_TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


SQLITE_INTEGER_MAX = 2**63 - 1


def _optional_weight(value, field_name):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a non-negative number.")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")
    return float(value)


def _optional_count(value, field_name):
    if value is None or value == "":
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > SQLITE_INTEGER_MAX
    ):
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _optional_time(value, field_name):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be HH:MM.")
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _ENTRY_TIME_PATTERN.fullmatch(cleaned):
        raise ValueError(f"{field_name} must be HH:MM.")
    return cleaned


_COLLECTION_ENTRY_FIELD_SPECS = {
    "clothing_kg": ("clothing_kg_snapshot", _optional_weight),
    "shoes_kg": ("shoes_kg_snapshot", _optional_weight),
    "time_in": ("time_in_snapshot", _optional_time),
    "time_out": ("time_out_snapshot", _optional_time),
    "trolleys_out_to_opshops": (
        "trolleys_out_to_opshops_snapshot",
        _optional_count,
    ),
    "trolleys_in_to_mcc": ("trolleys_in_to_mcc_snapshot", _optional_count),
    "hard_toys": ("hard_toys_snapshot", _optional_count),
    "soft_toys": ("soft_toys_snapshot", _optional_count),
    "black_bags": ("black_bags_snapshot", _optional_count),
    "shoe_bags": ("shoe_bags_snapshot", _optional_count),
}


def _pickup_notes(pickup):
    notes = []
    for value in (pickup.task_notes, pickup.status_notes):
        cleaned = clean_optional_text(value)
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    return "\n".join(notes) or None


def _timestamp():
    return datetime.now(timezone.utc).isoformat()
