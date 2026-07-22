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

        fields = request.model_fields_set
        is_available = _patch_bool(
            request,
            fields,
            "is_available",
            existing.is_available,
        )
        if not is_available and existing.is_available:
            self.validator.ensure_driver_can_be_made_unavailable(driver_id)

        driver = Driver(
            driver_id=existing.driver_id,
            name=(
                clean_required_text(request.name, "name")
                if "name" in fields
                else existing.name
            ),
            start_time=_patch_text(request, fields, "start_time", existing.start_time),
            end_time=_patch_text(request, fields, "end_time", existing.end_time),
            is_available=is_available,
            preferred_zone=_patch_text(
                request,
                fields,
                "preferred_zone",
                existing.preferred_zone,
            ),
            pallet_only=_patch_bool(
                request,
                fields,
                "pallet_only",
                existing.pallet_only,
            ),
            license_no=_patch_text(request, fields, "license_no", existing.license_no),
            email=_patch_text(request, fields, "email", existing.email),
            phone_number=_patch_text(
                request,
                fields,
                "phone_number",
                existing.phone_number,
            ),
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

        fields = request.model_fields_set
        is_available = _patch_bool(
            request,
            fields,
            "is_available",
            existing.is_available,
        )
        if not is_available and existing.is_available:
            self.validator.ensure_vehicle_can_be_made_unavailable(vehicle_id)

        vehicle = Vehicle(
            vehicle_id=existing.vehicle_id,
            rego=(
                clean_required_text(request.rego, "rego")
                if "rego" in fields
                else existing.rego
            ),
            type=_patch_text(request, fields, "type", existing.type) or "",
            is_available=is_available,
            pallet_capacity=_patch_quantity(
                request,
                fields,
                "pallet_capacity",
                existing.pallet_capacity,
            ),
            tub_capacity=_patch_quantity(
                request,
                fields,
                "tub_capacity",
                existing.tub_capacity,
            ),
            trolley_capacity=_patch_quantity(
                request,
                fields,
                "trolley_capacity",
                existing.trolley_capacity,
            ),
            stillage_capacity=_patch_quantity(
                request,
                fields,
                "stillage_capacity",
                existing.stillage_capacity,
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


def _patch_text(request, fields, field_name, existing_value):
    if field_name not in fields:
        return existing_value
    return clean_optional_text(getattr(request, field_name))


def _patch_bool(request, fields, field_name, existing_value):
    if field_name not in fields:
        return existing_value
    value = getattr(request, field_name)
    if value is None:
        raise ValueError(f"{field_name} cannot be null")
    return bool_or_default(value, existing_value)


def _patch_quantity(request, fields, field_name, existing_value):
    if field_name not in fields:
        return existing_value
    value = getattr(request, field_name)
    if value is None:
        raise ValueError(f"{field_name} cannot be null")
    return quantity_or_default(value, field_name)
