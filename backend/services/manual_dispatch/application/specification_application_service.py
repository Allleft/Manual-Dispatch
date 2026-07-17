from backend.schemas import ManualDispatchSpecificationResponse
from . import FacadeApplicationService


class SpecificationApplicationService(FacadeApplicationService):
    """Own specification application orchestration."""

    def get_shared_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )

    def get_delivery_specifications(self):
        return self.get_shared_specifications()

    def create_driver(self, request):
        return self.specification_service.create_driver(request)

    def update_driver(self, driver_id, request):
        return self.specification_service.update_driver(driver_id, request)

    def delete_driver(self, driver_id):
        return self.specification_service.delete_driver(driver_id)

    def create_vehicle(self, request):
        return self.specification_service.create_vehicle(request)

    def update_vehicle(self, vehicle_id, request):
        return self.specification_service.update_vehicle(vehicle_id, request)

    def delete_vehicle(self, vehicle_id):
        return self.specification_service.delete_vehicle(vehicle_id)

    def create_delivery_driver(self, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.create_driver(request)

    def update_delivery_driver(self, driver_id, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.update_driver(driver_id, request)

    def delete_delivery_driver(self, driver_id):
        self._ensure_workspace_ready("delivery")
        self._ensure_driver_not_used_by_delivery_run_sheet(driver_id)
        return self.specification_service.delete_driver(driver_id)

    def create_delivery_vehicle(self, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.create_vehicle(request)

    def update_delivery_vehicle(self, vehicle_id, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.update_vehicle(vehicle_id, request)

    def delete_delivery_vehicle(self, vehicle_id):
        self._ensure_workspace_ready("delivery")
        self._ensure_vehicle_not_used_by_delivery_run_sheet(vehicle_id)
        return self.specification_service.delete_vehicle(vehicle_id)

    def _ensure_driver_not_used_by_delivery_run_sheet(self, driver_id):
        if any(
            run_sheet.driver_id == driver_id
            for run_sheet in self.repository.list_delivery_run_sheets()
        ):
            raise ValueError(
                "Driver has Delivery Run Sheet history and cannot be deleted. "
                "Set Availability off instead."
            )

    def _ensure_vehicle_not_used_by_delivery_run_sheet(self, vehicle_id):
        if any(
            run_sheet.vehicle_id == vehicle_id
            for run_sheet in self.repository.list_delivery_run_sheets()
        ):
            raise ValueError(
                "Vehicle has Delivery Run Sheet history and cannot be deleted. "
                "Set Availability off instead."
            )
