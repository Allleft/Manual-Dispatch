"""Delivery vehicle rules shared by scoped and legacy-enabled entrypoints."""
import sqlite3

from backend.errors import StateChangedConflictError
from backend.services.manual_dispatch.delivery_run_sheet_lock import ensure_delivery_run_sheet_key_mutable
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date, clean_required_iso_date, clean_required_text,
)
from backend.services.manual_dispatch.transaction import immediate_transactional
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationReadinessService


class DeliveryVehicleAssignmentService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    def _scope(self, request):
        WorkspaceMigrationReadinessService(self.repository).ensure_per_trip_ready()
        delivery_date = clean_required_iso_date(request.delivery_date, "delivery_date")
        dispatch_date = clean_optional_iso_date(request.dispatch_date, "dispatch_date") or delivery_date
        driver_id = clean_required_text(request.driver_id, "driver_id")
        trip_no = clean_required_text(request.trip_no, "trip_no")
        self.validator.validate_trip_no(trip_no)
        self.validator.validate_driver_exists(driver_id)
        ensure_delivery_run_sheet_key_mutable(
            self.repository, dispatch_date, driver_id, delivery_date, trip_no,
        )
        return dispatch_date, delivery_date, driver_id, trip_no

    @immediate_transactional
    def assign(self, request):
        dispatch_date, delivery_date, driver_id, trip_no = self._scope(request)
        vehicle_id = clean_required_text(request.vehicle_id, "vehicle_id")
        self.validator.validate_vehicle_exists(vehicle_id)
        try:
            assignment, conflicting_driver_id = self.repository.upsert_delivery_trip_vehicle_assignment(
                dispatch_date, delivery_date, driver_id, vehicle_id, trip_no,
            )
        except sqlite3.IntegrityError as error:
            # The unique trip index is the final backstop for concurrent claims.
            if "UNIQUE constraint failed: manual_driver_vehicle_assignments." not in str(error):
                raise
            raise StateChangedConflictError("Vehicle assignment changed. Refresh and try again.") from error
        if conflicting_driver_id:
            self._raise_conflict(vehicle_id, conflicting_driver_id, trip_no)
        return assignment

    @immediate_transactional
    def clear(self, request):
        _, delivery_date, driver_id, trip_no = self._scope(request)
        return self.repository.remove_delivery_trip_vehicle_assignment(delivery_date, driver_id, trip_no)

    def _raise_conflict(self, vehicle_id, driver_id, trip_no):
        vehicle = self.repository.get_vehicle(vehicle_id)
        driver = self.repository.get_driver(driver_id)
        scope = f" and {trip_no}" if trip_no else ""
        raise StateChangedConflictError(
            f"Vehicle {vehicle.rego if vehicle else vehicle_id} is already assigned to "
            f"{driver.name if driver else driver_id} for this delivery date{scope}."
        )
