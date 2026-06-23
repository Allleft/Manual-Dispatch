from backend.schemas import OpShopWorkspaceBoardResponse, OpShopWorkspacePickupItem
from backend.services.manual_dispatch.normalization import clean_required_iso_date
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService


class OpShopWorkspaceBoardService:
    def __init__(self, repository, pickup_service=None):
        self.repository = repository
        self.pickup_service = pickup_service or OpShopPickupService(repository)

    def get_board(self, dispatch_date):
        dispatch_date = clean_required_iso_date(dispatch_date, "dispatch_date")
        regular_window = self.pickup_service.ensure_regular_opshop_pickup_tasks_for_week(
            dispatch_date
        )
        collections = self.repository.list_opshop_pickup_collections(dispatch_date)
        reserved_task_ids = self._reserved_task_ids(collections)

        pickup_lists = [
            self.repository.list_scheduled_opshop_pickup_board_items_for_window(
                regular_window.window_start,
                regular_window.window_end,
            ),
            self.repository.list_oncall_opshop_pickup_board_items(dispatch_date),
            self.repository.list_countryside_opshop_pickup_board_items(dispatch_date),
            self.repository.list_assigned_opshop_pickup_board_items(dispatch_date),
        ]
        pickups_by_id = {}
        for pickups in pickup_lists:
            for pickup in pickups:
                if pickup.pickup_task_id in reserved_task_ids:
                    continue
                pickup.assigned_to_locked = pickup.pickup_date < dispatch_date
                pickups_by_id[pickup.pickup_task_id] = pickup

        pickups = sorted(
            (self._workspace_pickup(pickup) for pickup in pickups_by_id.values()),
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

    @staticmethod
    def _reserved_task_ids(collections):
        return {
            pickup.pickup_task_id_snapshot
            for collection in collections
            if collection.status in {"GENERATED", "SAVED"}
            for pickup in collection.pickups
            if pickup.pickup_task_id_snapshot
        }

    @staticmethod
    def _workspace_pickup(pickup):
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
            driver_id=pickup.driver_id,
            is_assigned=pickup.is_assigned,
            default_driver_id=pickup.default_driver_id,
            default_driver_alias=pickup.default_driver_alias,
            default_driver_name=pickup.default_driver_name,
            assigned_driver_id=pickup.assigned_driver_id,
            assigned_driver_name=pickup.assigned_driver_name,
            assigned_to_locked=pickup.assigned_to_locked,
            pickup_category=pickup.pickup_category,
            route_group_id=pickup.route_group_id,
            route_group_name=pickup.route_group_name,
        )
