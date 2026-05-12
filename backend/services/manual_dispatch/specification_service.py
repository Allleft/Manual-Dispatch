from backend.schemas import Driver, Vehicle
from backend.services.manual_dispatch.normalization import (
    bool_or_default,
    clean_optional_text,
    clean_required_text,
    quantity_or_default,
)


class SpecificationService:
    def __init__(self, repository, validator, id_generator, board_service):
        self.repository = repository
        self.validator = validator
        self.id_generator = id_generator
        self.board_service = board_service

    def create_driver(self, request):
        driver = Driver(
            driver_id=self.id_generator.generate_driver_id(),
            name=clean_required_text(request.name, "name"),
            start_time=clean_optional_text(request.start_time),
            end_time=clean_optional_text(request.end_time),
            is_available=bool_or_default(request.is_available, True),
            preferred_zone=clean_optional_text(request.preferred_zone),
            pallet_only=bool_or_default(request.pallet_only, False),
            license_no=clean_optional_text(request.license_no),
            email=clean_optional_text(request.email),
            phone_number=clean_optional_text(request.phone_number),
            is_deleted=False,
        )
        return self.repository.create_driver(driver)

    def update_driver(self, driver_id, request):
        existing = self.repository.get_driver(driver_id)
        if not existing or existing.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")

        is_available = bool_or_default(request.is_available, True)
        if not is_available and existing.is_available:
            self.validator.ensure_driver_can_be_made_unavailable(driver_id)

        driver = Driver(
            driver_id=existing.driver_id,
            name=clean_required_text(request.name, "name"),
            start_time=clean_optional_text(request.start_time),
            end_time=clean_optional_text(request.end_time),
            is_available=is_available,
            preferred_zone=clean_optional_text(request.preferred_zone),
            pallet_only=bool_or_default(request.pallet_only, False),
            license_no=clean_optional_text(request.license_no),
            email=clean_optional_text(request.email),
            phone_number=clean_optional_text(request.phone_number),
            is_deleted=False,
        )
        return self.repository.update_driver(driver)

    def delete_driver(self, driver_id):
        existing = self.repository.get_driver(driver_id)
        if not existing or existing.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")
        if self.repository.driver_has_active_assignments(driver_id):
            raise ValueError(
                "Driver has current orders and cannot be deleted. Set Availability off instead after clearing work."
            )
        if self.repository.driver_has_vehicle_selection(driver_id):
            raise ValueError(
                "Driver has vehicle selection history and cannot be deleted. Set Availability off instead."
            )
        if self.repository.driver_has_final_summary_history(driver_id):
            raise ValueError(
                "Driver has assignment history and cannot be deleted. Set Availability off instead."
            )
        self.repository.delete_driver(driver_id)
        return self.board_service.get_specifications()

    def create_vehicle(self, request):
        vehicle = Vehicle(
            vehicle_id=self.id_generator.generate_vehicle_id(),
            rego=clean_required_text(request.rego, "rego"),
            type=clean_optional_text(request.type) or "",
            is_available=bool_or_default(request.is_available, True),
            pallet_capacity=quantity_or_default(
                request.pallet_capacity,
                "pallet_capacity",
            ),
            tub_capacity=quantity_or_default(request.tub_capacity, "tub_capacity"),
            trolley_capacity=quantity_or_default(
                request.trolley_capacity,
                "trolley_capacity",
            ),
            stillage_capacity=quantity_or_default(
                request.stillage_capacity,
                "stillage_capacity",
            ),
            is_deleted=False,
        )
        return self.repository.create_vehicle(vehicle)

    def update_vehicle(self, vehicle_id, request):
        existing = self.repository.get_vehicle(vehicle_id)
        if not existing or existing.is_deleted:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")

        is_available = bool_or_default(request.is_available, True)
        if not is_available and existing.is_available:
            self.validator.ensure_vehicle_can_be_made_unavailable(vehicle_id)

        vehicle = Vehicle(
            vehicle_id=existing.vehicle_id,
            rego=clean_required_text(request.rego, "rego"),
            type=clean_optional_text(request.type) or "",
            is_available=is_available,
            pallet_capacity=quantity_or_default(
                request.pallet_capacity,
                "pallet_capacity",
            ),
            tub_capacity=quantity_or_default(request.tub_capacity, "tub_capacity"),
            trolley_capacity=quantity_or_default(
                request.trolley_capacity,
                "trolley_capacity",
            ),
            stillage_capacity=quantity_or_default(
                request.stillage_capacity,
                "stillage_capacity",
            ),
            is_deleted=False,
        )
        return self.repository.update_vehicle(vehicle)

    def delete_vehicle(self, vehicle_id):
        existing = self.repository.get_vehicle(vehicle_id)
        if not existing or existing.is_deleted:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")
        if self.repository.vehicle_has_current_selection(vehicle_id):
            raise ValueError(
                "Vehicle has assignment/history and cannot be deleted. Set Availability off instead after clearing selections."
            )
        if self.repository.vehicle_has_final_summary_history(vehicle_id):
            raise ValueError(
                "Vehicle has assignment/history and cannot be deleted. Set Availability off instead."
            )
        self.repository.delete_vehicle(vehicle_id)
        return self.board_service.get_specifications()
