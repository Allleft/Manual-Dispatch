from dataclasses import replace
from backend.schemas import DeliveryWorkspaceVehicleClearRequest
from backend.services.manual_dispatch.delivery_vehicle_assignment_service import DeliveryVehicleAssignmentService
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
    clean_required_iso_date,
    clean_optional_text,
    clean_required_text,
)
from backend.services.manual_dispatch.transaction import immediate_transactional
from backend.services.manual_dispatch.delivery_order_date_rollover_service import (
    DeliveryOrderDateRolloverService,
)


class AssignmentService:
    def __init__(self, repository, validator, board_service, rollover_service=None):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service
        self.rollover_service = rollover_service or DeliveryOrderDateRolloverService(
            repository
        )

    @immediate_transactional
    def assign_task(self, request, rollover_events=None):
        request.dispatch_date = clean_required_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
        self.validator.validate_task_type(request.task_type)
        self.validator.validate_task_exists(request.task_type, request.task_id)
        current = self.repository.get_assignment(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        self.validator.validate_driver_assignment(
            request.driver_id,
            current.driver_id if current else None,
        )
        self.validator.validate_trip_no(request.trip_no)
        if request.task_type == "ORDER":
            self.rollover_service.roll_forward_eligible_unassigned_delivery_order(
                request.task_id,
                rollover_events,
            )
        delivery_date = self._get_task_delivery_date(request.task_type, request.task_id)
        ensure_driver_delivery_date_not_finalized(
            self.repository,
            request.dispatch_date,
            request.driver_id,
            delivery_date,
        )
        if request.task_type == "ORDER":
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

    @immediate_transactional
    def unassign_task(self, request, rollover_events=None):
        request.dispatch_date = clean_required_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
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
        if request.task_type == "ORDER":
            self.rollover_service.roll_forward_eligible_unassigned_delivery_order(
                request.task_id,
                rollover_events,
            )
        if request.task_type == "OPSHOP_PICKUP":
            self.repository.update_opshop_pickup_task_assignment_status(
                request.task_id,
                status="ACTIVE",
                driver_id=None,
                trip_no=None,
            )
        return self.board_service.get_board(request.dispatch_date)

    @immediate_transactional
    def assign_vehicle_to_driver(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        delivery_date = clean_required_iso_date(request.delivery_date or dispatch_date, "delivery_date")
        trip_no = clean_required_text(request.trip_no, "trip_no")
        self.validator.validate_trip_no(trip_no)
        ensure_driver_delivery_date_not_finalized(
            self.repository, dispatch_date, request.driver_id, delivery_date,
        )
        if not clean_optional_text(request.vehicle_id):
            return self.clear_driver_vehicle_assignment(dispatch_date, request.driver_id, delivery_date, trip_no)
        return DeliveryVehicleAssignmentService(self.repository, self.validator).assign(
            replace(request, dispatch_date=dispatch_date, delivery_date=delivery_date, trip_no=trip_no)
        )

    @immediate_transactional
    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None, trip_no=None):
        dispatch_date = clean_required_iso_date(dispatch_date, "dispatch_date")
        delivery_date = clean_required_iso_date(delivery_date or dispatch_date, "delivery_date")
        trip_no = clean_required_text(trip_no, "trip_no")
        self.validator.validate_trip_no(trip_no)
        ensure_driver_delivery_date_not_finalized(
            self.repository, dispatch_date, driver_id, delivery_date,
        )
        DeliveryVehicleAssignmentService(self.repository, self.validator).clear(
            DeliveryWorkspaceVehicleClearRequest(
                dispatch_date=dispatch_date, delivery_date=delivery_date, driver_id=driver_id, trip_no=trip_no,
            )
        )
        return ManualDriverVehicleClearResponse(
            dispatch_date=dispatch_date, delivery_date=delivery_date, driver_id=driver_id, trip_no=trip_no,
        )

    def _get_task_delivery_date(self, task_type, task_id):
        if task_type == "ORDER":
            return self.repository.get_order(task_id).delivery_date
        return self.repository.get_opshop_pickup_task(task_id).pickup_date
