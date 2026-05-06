from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import ManualDispatchBoardResponse, Order


SUPPORTED_TASK_TYPES = {"ORDER"}
SUPPORTED_TRIPS = {"trip1", "trip2"}


class ManualDispatchService:
    def __init__(self, repository=None):
        self.repository = repository or InMemoryManualDispatchRepository()

    def get_board(self, dispatch_date):
        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=self.repository.list_orders(),
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=self.repository.list_assignments(dispatch_date),
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
        )

    def assign_task(self, request):
        self._validate_task_type(request.task_type)
        self._validate_task_exists(request.task_type, request.task_id)
        self._validate_driver_exists(request.driver_id)
        self._validate_trip_no(request.trip_no)

        return self.repository.upsert_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
            driver_id=request.driver_id,
            trip_no=request.trip_no,
        )

    def unassign_task(self, request):
        self._validate_task_type(request.task_type)
        self.repository.remove_assignment(
            dispatch_date=request.dispatch_date,
            task_type=request.task_type,
            task_id=request.task_id,
        )
        return self.get_board(request.dispatch_date)

    def assign_vehicle_to_driver(self, request):
        self._validate_driver_exists(request.driver_id)
        self._validate_vehicle_exists(request.vehicle_id)

        return self.repository.upsert_driver_vehicle_assignment(
            dispatch_date=request.dispatch_date,
            driver_id=request.driver_id,
            vehicle_id=request.vehicle_id,
        )

    def create_order(self, request):
        suburb = self._clean_required_text(request.suburb, "suburb")
        delivery_date = self._clean_required_text(
            request.delivery_date,
            "delivery_date",
        )
        pallet_quantity = self._quantity_or_default(
            request.pallet_quantity,
            "pallet_quantity",
        )
        loose_bags_quantity = self._quantity_or_default(
            request.loose_bags_quantity,
            "loose_bags_quantity",
        )

        order = Order(
            order_id=self._generate_order_id(delivery_date),
            invoice_number=self._clean_optional_text(request.invoice_number),
            company_name=self._clean_optional_text(request.company_name) or "",
            phone=self._clean_optional_text(request.phone),
            delivery_address=self._clean_optional_text(request.delivery_address) or "",
            suburb=suburb,
            postcode=self._clean_optional_text(request.postcode) or "",
            delivery_date=delivery_date,
            zone=self._clean_optional_text(request.zone) or "",
            urgency=self._clean_optional_text(request.urgency) or "Normal",
            preferred_driver_id=self._clean_optional_text(request.preferred_driver_id),
            pallet_quantity=pallet_quantity,
            loose_bags_quantity=loose_bags_quantity,
            start_time=self._clean_optional_text(request.start_time),
            end_time=self._clean_optional_text(request.end_time),
            note=self._clean_optional_text(request.note),
        )
        return self.repository.create_order(order)

    def _validate_task_type(self, task_type):
        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def _validate_task_exists(self, task_type, task_id):
        if not self.repository.get_task(task_type, task_id):
            raise ValueError(f"Task does not exist: {task_type} {task_id}")

    def _validate_driver_exists(self, driver_id):
        if not self.repository.get_driver(driver_id):
            raise ValueError(f"Driver does not exist: {driver_id}")

    def _validate_vehicle_exists(self, vehicle_id):
        if not self.repository.get_vehicle(vehicle_id):
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")

    def _validate_trip_no(self, trip_no):
        if trip_no not in SUPPORTED_TRIPS:
            raise ValueError(f"Invalid trip_no: {trip_no}")

    def _clean_required_text(self, value, field_name):
        text = self._clean_optional_text(value)
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    def _clean_optional_text(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _quantity_or_default(self, value, field_name):
        if value in (None, ""):
            return 0
        try:
            quantity = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be a whole number") from error
        if quantity < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return quantity

    def _generate_order_id(self, delivery_date):
        date_token = "".join(character for character in delivery_date if character.isdigit())
        if not date_token:
            raise ValueError("delivery_date must include a date value")

        prefix = f"ORD-{date_token}-"
        highest_number = 0
        for order in self.repository.list_orders():
            if not order.order_id.startswith(prefix):
                continue
            suffix = order.order_id.replace(prefix, "", 1)
            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        next_number = highest_number + 1
        order_id = f"{prefix}{next_number:03d}"
        while self.repository.get_order(order_id):
            next_number += 1
            order_id = f"{prefix}{next_number:03d}"
        return order_id
