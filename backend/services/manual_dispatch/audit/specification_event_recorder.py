from . import FacadeAuditRecorder


class SpecificationEventRecorder(FacadeAuditRecorder):
    """Record specification event recorder events without changing semantics."""

    def _driver_name(self, driver_id):
        if not driver_id:
            return None
        driver = self.repository.get_driver(driver_id)
        return driver.name if driver else driver_id

    def _vehicle_label(self, vehicle_id):
        if not vehicle_id:
            return None
        vehicle = self.repository.get_vehicle(vehicle_id)
        return vehicle.rego if vehicle else vehicle_id
