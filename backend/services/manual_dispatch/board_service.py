from backend.schemas import (
    ManualDispatchBoardResponse,
    ManualDispatchSpecificationResponse,
)


class BoardService:
    def __init__(self, repository):
        self.repository = repository

    def get_board(self, dispatch_date):
        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=self.repository.list_orders(),
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=self.repository.list_assignments(dispatch_date),
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
        )

    def get_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )
