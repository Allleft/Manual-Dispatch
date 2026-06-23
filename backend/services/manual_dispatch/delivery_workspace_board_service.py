from backend.schemas import (
    DeliveryVehicleAssignmentLock,
    DeliveryWorkspaceBoardResponse,
)
from backend.services.manual_dispatch.normalization import clean_required_iso_date
from backend.services.manual_dispatch.suburb_distance_service import (
    get_estimated_distance_km,
)


class DeliveryWorkspaceBoardService:
    def __init__(self, repository):
        self.repository = repository

    def get_board(self, dispatch_date):
        dispatch_date = clean_required_iso_date(dispatch_date, "dispatch_date")
        run_sheets = self.repository.list_delivery_run_sheets(dispatch_date)
        reserved_task_ids = self._reserved_task_ids(run_sheets)

        orders = [
            order
            for order in self.repository.list_orders()
            if order.order_id not in reserved_task_ids
        ]
        for order in orders:
            order.estimated_distance_km_from_warehouse = get_estimated_distance_km(
                order.suburb
            )

        assignments = [
            assignment
            for assignment in self.repository.list_assignments(dispatch_date)
            if assignment.task_type == "ORDER"
            and assignment.task_id not in reserved_task_ids
        ]
        saved_locks = [
            DeliveryVehicleAssignmentLock(
                dispatch_date=run_sheet.dispatch_date,
                delivery_date=run_sheet.delivery_date,
                driver_id=run_sheet.driver_id,
                run_sheet_id=run_sheet.run_sheet_id,
            )
            for run_sheet in run_sheets
            if run_sheet.status == "SAVED"
        ]

        return DeliveryWorkspaceBoardResponse(
            dispatch_date=dispatch_date,
            orders=orders,
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=assignments,
            driver_vehicle_assignments=(
                self.repository.list_driver_vehicle_assignments(dispatch_date)
            ),
            saved_vehicle_assignment_locks=saved_locks,
        )

    @staticmethod
    def _reserved_task_ids(run_sheets):
        return {
            order.task_id
            for run_sheet in run_sheets
            if run_sheet.status in {"GENERATED", "SAVED"}
            for trip in run_sheet.trips
            for order in trip.orders
            if order.task_type == "ORDER" and order.task_id
        }
