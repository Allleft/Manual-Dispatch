from backend.schemas import (
    EnsureOpShopPickupTasksRequest,
    ManualDispatchBoardResponse,
    ManualDispatchSpecificationResponse,
)
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
        opshop_generation = self.opshop_pickup_service.ensure_opshop_pickup_tasks_for_window(
            EnsureOpShopPickupTasksRequest(start_date=dispatch_date, days=14)
        )
        orders = self.repository.list_orders()
        for order in orders:
            order.estimated_distance_km_from_warehouse = get_estimated_distance_km(
                order.suburb
            )

        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=orders,
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=self.repository.list_assignments(dispatch_date),
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
            opshop_pickups=self.repository.list_opshop_pickup_board_items_for_window(
                opshop_generation.window_start,
                opshop_generation.window_end,
            ),
        )

    def get_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )
