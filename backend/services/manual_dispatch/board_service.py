from backend.schemas import ManualDispatchBoardResponse, ManualDispatchSpecificationResponse
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService
from backend.services.manual_dispatch.suburb_distance_service import (
    get_estimated_distance_km,
)


class BoardService:
    def __init__(self, repository, opshop_pickup_service=None):
        self.repository = repository
        self.opshop_pickup_service = opshop_pickup_service or OpShopPickupService(
            repository
        )

    def get_board(self, dispatch_date):
        scheduled_generation = self.opshop_pickup_service.ensure_regular_opshop_pickup_tasks_for_week(
            dispatch_date
        )
        orders = self.repository.list_orders()
        for order in orders:
            order.estimated_distance_km_from_warehouse = get_estimated_distance_km(
                order.suburb
            )

        scheduled_pickups = self.repository.list_scheduled_opshop_pickup_board_items_for_window(
            scheduled_generation.window_start,
            scheduled_generation.window_end,
        )
        for pickup in scheduled_pickups:
            pickup.assigned_to_locked = pickup.pickup_date < dispatch_date
        oncall_pickups = self.repository.list_oncall_opshop_pickup_board_items(
            dispatch_date
        )
        for pickup in oncall_pickups:
            pickup.assigned_to_locked = pickup.pickup_date < dispatch_date

        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=orders,
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=self.repository.list_assignments(dispatch_date),
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
            opshop_pickups=[],
            assigned_opshop_pickups=self.repository.list_assigned_opshop_pickup_board_items(
                dispatch_date
            ),
            scheduled_opshop_pickups=scheduled_pickups,
            oncall_opshop_pickups=oncall_pickups,
            opshop_regular_list_window_start=scheduled_generation.window_start,
            opshop_regular_list_window_end=scheduled_generation.window_end,
        )

    def get_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )
