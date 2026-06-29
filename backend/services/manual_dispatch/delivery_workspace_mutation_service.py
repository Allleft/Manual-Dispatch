from backend.services.manual_dispatch.delivery_run_sheet_lock import (
    ensure_delivery_run_sheet_key_mutable,
    ensure_order_not_reserved,
)
from backend.services.manual_dispatch.normalization import (
    clean_required_iso_date,
    clean_required_text,
)


class DeliveryWorkspaceMutationService:
    def __init__(self, repository, validator, board_service):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service

    def assign_order(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        order = self._active_order(request.order_id)
        driver_id = clean_required_text(request.driver_id, "driver_id")
        trip_no = clean_required_text(request.trip_no, "trip_no")
        self.validator.validate_driver_exists(driver_id)
        self.validator.validate_trip_no(trip_no)

        ensure_order_not_reserved(self.repository, dispatch_date, order.order_id)
        current = self.repository.get_assignment(
            dispatch_date,
            "ORDER",
            order.order_id,
        )
        if current:
            ensure_delivery_run_sheet_key_mutable(
                self.repository,
                dispatch_date,
                current.driver_id,
                order.delivery_date,
            )
        ensure_delivery_run_sheet_key_mutable(
            self.repository,
            dispatch_date,
            driver_id,
            order.delivery_date,
        )
        self.repository.upsert_assignment(
            dispatch_date,
            "ORDER",
            order.order_id,
            driver_id,
            trip_no,
        )
        return self.board_service.get_board(dispatch_date)

    def unassign_order(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        order = self._active_order(request.order_id)
        ensure_order_not_reserved(self.repository, dispatch_date, order.order_id)
        current = self.repository.get_assignment(
            dispatch_date,
            "ORDER",
            order.order_id,
        )
        if current:
            ensure_delivery_run_sheet_key_mutable(
                self.repository,
                dispatch_date,
                current.driver_id,
                order.delivery_date,
            )
            self.repository.remove_assignment(
                dispatch_date,
                "ORDER",
                order.order_id,
            )
        return self.board_service.get_board(dispatch_date)

    def assign_vehicle(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        delivery_date = clean_required_iso_date(request.delivery_date, "delivery_date")
        driver_id = clean_required_text(request.driver_id, "driver_id")
        vehicle_id = clean_required_text(request.vehicle_id, "vehicle_id")
        self.validator.validate_driver_exists(driver_id)
        self.validator.validate_vehicle_exists(vehicle_id)
        ensure_delivery_run_sheet_key_mutable(
            self.repository,
            dispatch_date,
            driver_id,
            delivery_date,
        )
        _, conflicting_driver_id = (
            self.repository.upsert_delivery_workspace_vehicle_assignment(
                dispatch_date,
                delivery_date,
                driver_id,
                vehicle_id,
            )
        )
        if conflicting_driver_id:
            vehicle = self.repository.get_vehicle(vehicle_id)
            driver = self.repository.get_driver(conflicting_driver_id)
            vehicle_name = vehicle.rego if vehicle else vehicle_id
            driver_name = driver.name if driver else conflicting_driver_id
            raise ValueError(
                f"Vehicle {vehicle_name} is already assigned to "
                f"{driver_name} for this delivery date."
            )
        return self.board_service.get_board(dispatch_date)

    def clear_vehicle(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        delivery_date = clean_required_iso_date(request.delivery_date, "delivery_date")
        driver_id = clean_required_text(request.driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)
        ensure_delivery_run_sheet_key_mutable(
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
        return self.board_service.get_board(dispatch_date)

    def _active_order(self, order_id):
        order_id = clean_required_text(order_id, "order_id")
        order = self.repository.get_order(order_id)
        if not order or order.status != "ACTIVE":
            raise ValueError(f"Active Delivery Order does not exist: {order_id}")
        return order
