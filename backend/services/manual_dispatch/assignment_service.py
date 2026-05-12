from backend.schemas import ManualDriverVehicleClearResponse
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

        return self.repository.upsert_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
            driver_id=request.driver_id,
            trip_no=request.trip_no,
        )

    def unassign_task(self, request):
        self.validator.validate_task_type(request.task_type)
        self.repository.remove_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
        )
        return self.board_service.get_board(request.dispatch_date)

    def assign_vehicle_to_driver(self, request):
        dispatch_date = clean_required_text(request.dispatch_date, "dispatch_date")
        driver_id = clean_required_text(request.driver_id, "driver_id")
        vehicle_id = clean_optional_text(getattr(request, "vehicle_id", None))

        self.validator.validate_driver_exists(driver_id)

        if not vehicle_id:
            return self.clear_driver_vehicle_assignment(dispatch_date, driver_id)

        self.validator.validate_vehicle_exists(vehicle_id)

        return self.repository.upsert_driver_vehicle_assignment(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id):
        dispatch_date = clean_required_text(dispatch_date, "dispatch_date")
        driver_id = clean_required_text(driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)
        self.repository.remove_driver_vehicle_assignment(dispatch_date, driver_id)
        return ManualDriverVehicleClearResponse(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
        )
