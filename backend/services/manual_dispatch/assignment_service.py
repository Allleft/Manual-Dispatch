from backend.schemas import ManualDriverVehicleClearResponse
from backend.services.manual_dispatch.delivery_run_sheet_lock import (
    ensure_order_not_assigned_elsewhere,
    ensure_order_not_reserved,
)
from backend.services.manual_dispatch.final_summary_lock import (
    ensure_driver_delivery_date_not_finalized,
    is_driver_delivery_date_finalized,
)
from backend.services.manual_dispatch.normalization import (
    clean_optional_text,
    clean_required_text,
)


class AssignmentService:
    def __init__(self, repository, validator, board_service):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service

    def assign_task(self, request):
        self.validator.validate_task_type(request.task_type)
        self.validator.validate_task_exists(request.task_type, request.task_id)
        self.validator.validate_driver_exists(request.driver_id)
        self.validator.validate_trip_no(request.trip_no)
        delivery_date = self._get_task_delivery_date(request.task_type, request.task_id)
        ensure_driver_delivery_date_not_finalized(
            self.repository,
            request.dispatch_date,
            request.driver_id,
            delivery_date,
        )
        if request.task_type == "ORDER":
            current = self.repository.get_assignment(
                request.dispatch_date,
                "ORDER",
                request.task_id,
            )
            ensure_order_not_reserved(
                self.repository,
                request.dispatch_date,
                request.task_id,
            )
            if not current:
                ensure_order_not_assigned_elsewhere(
                    self.repository,
                    request.dispatch_date,
                    request.task_id,
                )

        assignment = self.repository.upsert_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
            driver_id=request.driver_id,
            trip_no=request.trip_no,
        )
        if request.task_type == "OPSHOP_PICKUP":
            self.repository.update_opshop_pickup_task_assignment_status(
                request.task_id,
                status="ASSIGNED",
                driver_id=request.driver_id,
                trip_no=request.trip_no,
            )
        return assignment

    def unassign_task(self, request):
        self.validator.validate_task_type(request.task_type)
        if request.task_type == "ORDER":
            ensure_order_not_reserved(
                self.repository,
                request.dispatch_date,
                request.task_id,
            )
        assignment = self.repository.get_assignment(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        if assignment:
            delivery_date = self._get_task_delivery_date(request.task_type, request.task_id)
            if is_driver_delivery_date_finalized(
                self.repository,
                request.dispatch_date,
                assignment.driver_id,
                delivery_date,
            ):
                raise ValueError(
                    "Final Trip Summary has already been saved for this driver and delivery date."
                )
        self.repository.remove_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
        )
        if request.task_type == "OPSHOP_PICKUP":
            self.repository.update_opshop_pickup_task_assignment_status(
                request.task_id,
                status="ACTIVE",
                driver_id=None,
                trip_no=None,
            )
        return self.board_service.get_board(request.dispatch_date)

    def assign_vehicle_to_driver(self, request):
        dispatch_date = clean_required_text(request.dispatch_date, "dispatch_date")
        delivery_date = clean_required_text(
            getattr(request, "delivery_date", None) or dispatch_date,
            "delivery_date",
        )
        driver_id = clean_required_text(request.driver_id, "driver_id")
        vehicle_id = clean_optional_text(getattr(request, "vehicle_id", None))

        self.validator.validate_driver_exists(driver_id)
        ensure_driver_delivery_date_not_finalized(
            self.repository,
            dispatch_date,
            driver_id,
            delivery_date,
        )

        if not vehicle_id:
            return self.clear_driver_vehicle_assignment(
                dispatch_date,
                driver_id,
                delivery_date,
            )

        self.validator.validate_vehicle_exists(vehicle_id)

        return self.repository.upsert_driver_vehicle_assignment(
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        dispatch_date = clean_required_text(dispatch_date, "dispatch_date")
        delivery_date = clean_required_text(delivery_date or dispatch_date, "delivery_date")
        driver_id = clean_required_text(driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)
        ensure_driver_delivery_date_not_finalized(
            self.repository,
            dispatch_date,
            driver_id,
            delivery_date,
        )
        self.repository.remove_driver_vehicle_assignment(
            dispatch_date,
            driver_id,
            delivery_date,
        )
        return ManualDriverVehicleClearResponse(
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver_id=driver_id,
        )

    def _get_task_delivery_date(self, task_type, task_id):
        if task_type == "ORDER":
            return self.repository.get_order(task_id).delivery_date
        return self.repository.get_opshop_pickup_task(task_id).pickup_date
