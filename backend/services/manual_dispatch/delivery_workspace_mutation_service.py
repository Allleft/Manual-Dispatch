from backend.services.manual_dispatch.delivery_vehicle_assignment_service import DeliveryVehicleAssignmentService
from backend.services.manual_dispatch.delivery_run_sheet_lock import (
    ensure_delivery_run_sheet_key_mutable,
    ensure_order_not_reserved,
)
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date,
    clean_required_iso_date,
    clean_required_text,
)
from backend.services.manual_dispatch.delivery_order_date_rollover_service import (
    DeliveryOrderDateRolloverService,
)
from backend.services.manual_dispatch.transaction import immediate_transactional


class DeliveryWorkspaceMutationService:
    def __init__(self, repository, validator, board_service, rollover_service=None):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service
        self.vehicle_service = DeliveryVehicleAssignmentService(repository, validator)
        self.rollover_service = rollover_service or DeliveryOrderDateRolloverService(
            repository
        )

    @immediate_transactional
    def assign_order(self, request, rollover_events=None):
        self.rollover_service.roll_forward_eligible_unassigned_delivery_order(
            request.order_id,
            rollover_events,
        )
        order = self._active_order(request.order_id)
        request_dispatch_date = clean_optional_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
        dispatch_date = request_dispatch_date or order.delivery_date
        driver_id = clean_required_text(request.driver_id, "driver_id")
        trip_no = clean_required_text(request.trip_no, "trip_no")
        self.validator.validate_trip_no(trip_no)

        current = self.repository.find_assignment_for_task(
            "ORDER",
            order.order_id,
        )
        self.validator.validate_driver_assignment(
            driver_id,
            current.driver_id if current else None,
        )
        ensure_order_not_reserved(self.repository, dispatch_date, order.order_id)
        if current:
            ensure_delivery_run_sheet_key_mutable(
                self.repository,
                dispatch_date,
                current.driver_id,
                order.delivery_date,
                current.trip_no,
            )
        ensure_delivery_run_sheet_key_mutable(
            self.repository,
            dispatch_date,
            driver_id,
            order.delivery_date,
            trip_no,
        )
        self.repository.upsert_assignment(
            dispatch_date,
            "ORDER",
            order.order_id,
            driver_id,
            trip_no,
        )
        return self._response_board(
            request_dispatch_date,
            dispatch_date,
            order.delivery_date,
            rollover_events,
        )

    @immediate_transactional
    def unassign_order(self, request, rollover_events=None):
        order = self._active_order(request.order_id)
        request_dispatch_date = clean_optional_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
        dispatch_date = request_dispatch_date or order.delivery_date
        ensure_order_not_reserved(self.repository, dispatch_date, order.order_id)
        current = self.repository.find_assignment_for_task(
            "ORDER",
            order.order_id,
        )
        if current:
            ensure_delivery_run_sheet_key_mutable(
                self.repository,
                dispatch_date,
                current.driver_id,
                order.delivery_date,
                current.trip_no,
            )
            self.repository.remove_assignments_for_task(
                "ORDER",
                order.order_id,
            )
        self.rollover_service.roll_forward_eligible_unassigned_delivery_order(
            order.order_id,
            rollover_events,
        )
        order = self._active_order(order.order_id)
        return self._response_board(
            request_dispatch_date,
            dispatch_date,
            order.delivery_date,
            rollover_events,
        )

    @immediate_transactional
    def assign_vehicle(self, request):
        self.vehicle_service.assign(request)
        return self._vehicle_response_board(request)

    @immediate_transactional
    def clear_vehicle(self, request):
        self.vehicle_service.clear(request)
        return self._vehicle_response_board(request)

    @immediate_transactional
    def assign_day_vehicle(self, request):
        self.vehicle_service.assign_day_compatibility(request)
        return self._vehicle_response_board(request)

    @immediate_transactional
    def clear_day_vehicle(self, request):
        self.vehicle_service.clear_day_compatibility(request)
        return self._vehicle_response_board(request)

    def _vehicle_response_board(self, request):
        dispatch_date = clean_optional_iso_date(request.dispatch_date, "dispatch_date")
        return self._response_board(
            dispatch_date, dispatch_date or request.delivery_date, request.delivery_date,
        )

    def _response_board(
        self,
        request_dispatch_date,
        dispatch_date,
        delivery_date,
        rollover_events=None,
    ):
        if request_dispatch_date:
            return self.board_service.get_board(dispatch_date, rollover_events)
        return self.board_service.get_trip_summary_board(delivery_date)

    def _active_order(self, order_id):
        order_id = clean_required_text(order_id, "order_id")
        order = self.repository.get_order(order_id)
        if not order or order.status != "ACTIVE":
            raise ValueError(f"Active Delivery Order does not exist: {order_id}")
        return order
