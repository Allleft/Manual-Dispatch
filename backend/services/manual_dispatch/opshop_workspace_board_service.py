from bisect import bisect_left
from datetime import date, timedelta

from backend.schemas import (
    OpShopTripSummaryResponse,
    OpShopWorkspaceBoardResponse,
    OpShopWorkspacePickupItem,
)
from backend.services.manual_dispatch.normalization import clean_required_iso_date
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService


def _is_iso_date(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return parsed.isoformat() == value


class OpShopWorkspaceBoardService:
    def __init__(self, repository, pickup_service=None):
        self.repository = repository
        self.pickup_service = pickup_service or OpShopPickupService(repository)

    def get_board(self, dispatch_date):
        dispatch_date = clean_required_iso_date(dispatch_date, "dispatch_date")
        regular_window = self.pickup_service.ensure_regular_opshop_pickup_tasks_for_week(
            dispatch_date
        )
        oncall_start_date = (
            date.fromisoformat(dispatch_date) - timedelta(days=14)
        ).isoformat()

        pickup_lists = [
            self.repository.list_scheduled_opshop_pickup_board_items_for_window(
                regular_window.window_start,
                regular_window.window_end,
            ),
            self.repository.list_oncall_opshop_pickup_board_items(oncall_start_date),
            self.repository.list_countryside_opshop_pickup_board_items(dispatch_date),
            self.repository.list_assigned_opshop_pickup_board_items(dispatch_date),
        ]
        candidate_pickups_by_id = {}
        for pickups in pickup_lists:
            for pickup in pickups:
                candidate_pickups_by_id[pickup.pickup_task_id] = pickup

        collections = (
            self.repository.list_opshop_pickup_collection_reservations_for_task_ids(
                candidate_pickups_by_id
            )
        )
        saved_task_ids = self._reserved_task_ids(collections, {"SAVED"})
        generated_collections_by_task_id = (
            self._generated_collections_by_task_id(collections)
        )
        pickups_by_id = {}
        for pickup_task_id, pickup in candidate_pickups_by_id.items():
            if pickup_task_id in saved_task_ids:
                continue
            pickup.assigned_to_locked = (
                pickup_task_id in generated_collections_by_task_id
                or pickup.pickup_date < dispatch_date
            )
            pickups_by_id[pickup_task_id] = pickup

        collectable_task_ids = self._collectable_task_ids(
            pickups_by_id.values()
        )
        last_pickup_dates = self._last_pickup_dates(pickups_by_id.values())

        pickups = sorted(
            (
                self._workspace_pickup(
                    pickup,
                    pickup.pickup_task_id in collectable_task_ids,
                    last_pickup_dates.get(pickup.pickup_task_id),
                    generated_collections_by_task_id.get(pickup.pickup_task_id),
                )
                for pickup in pickups_by_id.values()
            ),
            key=lambda pickup: (
                pickup.pickup_date,
                pickup.pickup_category or "",
                pickup.route_group_name or "",
                pickup.suburb or "",
                pickup.opshop_name or "",
                pickup.pickup_task_id,
            ),
        )
        return OpShopWorkspaceBoardResponse(
            dispatch_date=dispatch_date,
            opshop_pickups=pickups,
            drivers=self.repository.list_drivers(),
            templates=self.repository.list_opshop_templates(),
            countryside_route_groups=(
                self.repository.list_countryside_route_groups()
            ),
        )

    def get_trip_summary_board(self, pickup_date):
        pickup_date = clean_required_iso_date(pickup_date, "pickup_date")
        collections = self.repository.list_opshop_pickup_collections(
            pickup_date=pickup_date
        )
        reserved_task_ids = self._reserved_task_ids(collections)

        pickups_by_id = {}
        for pickup in (
            self.repository.list_assigned_opshop_pickup_board_items_for_pickup_date(
                pickup_date
            )
        ):
            if pickup.pickup_task_id in reserved_task_ids:
                continue
            pickup.assigned_to_locked = False
            pickups_by_id[pickup.pickup_task_id] = pickup

        collectable_task_ids = self._collectable_task_ids(pickups_by_id.values())
        pickups = sorted(
            (
                self._workspace_pickup(
                    pickup,
                    pickup.pickup_task_id in collectable_task_ids,
                )
                for pickup in pickups_by_id.values()
            ),
            key=lambda pickup: (
                pickup.pickup_date,
                pickup.pickup_category or "",
                pickup.route_group_name or "",
                pickup.suburb or "",
                pickup.opshop_name or "",
                pickup.pickup_task_id,
            ),
        )

        return OpShopTripSummaryResponse(
            pickup_date=pickup_date,
            opshop_pickups=pickups,
            drivers=self.repository.list_drivers(),
            templates=self.repository.list_opshop_templates(),
            countryside_route_groups=(
                self.repository.list_countryside_route_groups()
            ),
        )

    @staticmethod
    def _reserved_task_ids(collections, statuses=None):
        reserved_statuses = statuses or {"GENERATED", "SAVED"}
        return {
            pickup.pickup_task_id_snapshot
            for collection in collections
            if collection.status in reserved_statuses
            for pickup in collection.pickups
            if pickup.pickup_task_id_snapshot
        }

    @staticmethod
    def _generated_collections_by_task_id(collections):
        generated_collections = {}
        for collection in collections:
            if collection.status != "GENERATED":
                continue
            for pickup in collection.pickups:
                if pickup.pickup_task_id_snapshot:
                    generated_collections.setdefault(
                        pickup.pickup_task_id_snapshot,
                        collection,
                    )
        return generated_collections

    def _collectable_task_ids(self, pickups):
        candidate_keys = {
            (pickup.pickup_date, pickup.driver_id)
            for pickup in pickups
            if pickup.pickup_date and pickup.driver_id
        }
        return {
            pickup.pickup_task_id
            for pickup_date, driver_id in candidate_keys
            for pickup in self.repository.list_collectable_opshop_pickup_board_items(
                pickup_date,
                driver_id,
            )
        }

    def _last_pickup_dates(self, pickups):
        regular_pickups = [
            pickup
            for pickup in pickups
            if pickup.run_type == "REGULAR" and _is_iso_date(pickup.pickup_date)
        ]
        if not regular_pickups:
            return {}
        history_by_opshop_id = (
            self.repository.list_saved_opshop_pickup_dates_by_opshop_ids(
                {pickup.opshop_id for pickup in regular_pickups},
                max(pickup.pickup_date for pickup in regular_pickups),
            )
        )

        last_pickup_dates = {}
        for pickup in regular_pickups:
            historical_dates = history_by_opshop_id.get(pickup.opshop_id, [])
            predecessor_index = bisect_left(historical_dates, pickup.pickup_date)
            last_pickup_dates[pickup.pickup_task_id] = (
                historical_dates[predecessor_index - 1]
                if predecessor_index
                else None
            )
        return last_pickup_dates

    @staticmethod
    def _workspace_pickup(
        pickup,
        assignment_is_collectable,
        last_pickup_date=None,
        generated_collection=None,
    ):
        generated_driver_id = (
            generated_collection.driver_id if generated_collection else None
        )
        driver_id = (
            generated_driver_id
            or (pickup.driver_id if assignment_is_collectable else None)
        )
        assigned_driver_name = (
            generated_collection.driver_name_snapshot
            if generated_collection
            else pickup.assigned_driver_name if assignment_is_collectable else None
        )
        assignment_lock_reason = None
        if generated_collection:
            generated_driver_name = (
                generated_collection.driver_name_snapshot
                or generated_collection.driver_id
            )
            assignment_lock_reason = f"Already generated to {generated_driver_name}"
        return OpShopWorkspacePickupItem(
            pickup_task_id=pickup.pickup_task_id,
            task_type=pickup.task_type,
            schedule_id=pickup.schedule_id,
            opshop_id=pickup.opshop_id,
            opshop_name=pickup.opshop_name,
            suburb=pickup.suburb,
            street_address=pickup.street_address,
            area_region=pickup.area_region,
            pickup_date=pickup.pickup_date,
            dispatch_date=pickup.dispatch_date,
            run_day=pickup.run_day,
            run_type=pickup.run_type,
            pickup_frequency=pickup.pickup_frequency,
            time_window=pickup.time_window,
            call_before_arrival=pickup.call_before_arrival,
            call_timing=pickup.call_timing,
            primary_contact=pickup.primary_contact,
            primary_phone=pickup.primary_phone,
            secondary_contact=pickup.secondary_contact,
            secondary_phone=pickup.secondary_phone,
            access_type=pickup.access_type,
            key_required=pickup.key_required,
            trailer_restriction=pickup.trailer_restriction,
            status=pickup.status,
            generated_from=pickup.generated_from,
            status_notes=pickup.status_notes,
            task_notes=pickup.task_notes,
            driver_id=driver_id,
            is_assigned=bool(driver_id),
            default_driver_id=pickup.default_driver_id,
            default_driver_alias=pickup.default_driver_alias,
            default_driver_name=pickup.default_driver_name,
            assigned_driver_id=driver_id,
            assigned_driver_name=assigned_driver_name,
            assigned_to_locked=(
                bool(generated_collection) or pickup.assigned_to_locked
            ),
            pickup_category=pickup.pickup_category,
            route_group_id=pickup.route_group_id,
            route_group_name=pickup.route_group_name,
            last_pickup_date=last_pickup_date,
            assignment_lock_reason=assignment_lock_reason,
            regular_route_sequence=pickup.regular_route_sequence,
        )
