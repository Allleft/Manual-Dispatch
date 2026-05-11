from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import (
    Driver,
    ManualDispatchBoardResponse,
    ManualDriverVehicleClearResponse,
    ManualDispatchSpecificationResponse,
    Order,
    SaveFinalTripSummaryRequest,
    Vehicle,
)
from backend.services.manual_dispatch.auth_service import OperatorAuthService


SUPPORTED_TASK_TYPES = {"ORDER"}
SUPPORTED_TRIPS = {"trip1", "trip2"}


class ManualDispatchService:
    def __init__(self, repository=None):
        self.repository = repository or InMemoryManualDispatchRepository()
        self.auth_service = OperatorAuthService(self.repository)

    def get_board(self, dispatch_date):
        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=self.repository.list_orders(dispatch_date),
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=self.repository.list_assignments(dispatch_date),
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
        )

    def get_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )

    def register_operator_account(self, request):
        return self.auth_service.register_operator_account(request)

    def login_operator_account(self, request):
        return self.auth_service.login_operator_account(request)

    def reset_operator_password(self, request):
        return self.auth_service.reset_operator_password(request)

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
        dispatch_date = self._clean_required_text(request.dispatch_date, "dispatch_date")
        driver_id = self._clean_required_text(request.driver_id, "driver_id")
        vehicle_id = self._clean_optional_text(getattr(request, "vehicle_id", None))

        self._validate_driver_exists(driver_id)

        if not vehicle_id:
            return self.clear_driver_vehicle_assignment(dispatch_date, driver_id)

        self._validate_vehicle_exists(vehicle_id)

        return self.repository.upsert_driver_vehicle_assignment(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id):
        dispatch_date = self._clean_required_text(dispatch_date, "dispatch_date")
        driver_id = self._clean_required_text(driver_id, "driver_id")
        self._validate_driver_exists(driver_id)
        self.repository.remove_driver_vehicle_assignment(dispatch_date, driver_id)
        return ManualDriverVehicleClearResponse(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
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
            status="ACTIVE",
        )
        return self.repository.create_order(order)

    def update_order(self, order_id, request):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        suburb = self._clean_required_text(request.suburb, "suburb")
        pallet_quantity = self._quantity_or_default(
            request.pallet_quantity,
            "pallet_quantity",
        )
        loose_bags_quantity = self._quantity_or_default(
            request.loose_bags_quantity,
            "loose_bags_quantity",
        )

        order = Order(
            order_id=existing.order_id,
            invoice_number=self._clean_optional_text(request.invoice_number),
            company_name=self._clean_optional_text(request.company_name) or "",
            phone=self._clean_optional_text(request.phone),
            delivery_address=self._clean_optional_text(request.delivery_address) or "",
            suburb=suburb,
            postcode=self._clean_optional_text(request.postcode) or "",
            delivery_date=existing.delivery_date,
            zone=self._clean_optional_text(request.zone) or "",
            urgency=self._clean_optional_text(request.urgency) or "Normal",
            preferred_driver_id=self._clean_optional_text(request.preferred_driver_id),
            pallet_quantity=pallet_quantity,
            loose_bags_quantity=loose_bags_quantity,
            start_time=self._clean_optional_text(request.start_time),
            end_time=self._clean_optional_text(request.end_time),
            note=self._clean_optional_text(request.note),
            status=existing.status,
        )
        return self.repository.update_order(order)

    def cancel_order(self, order_id):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        if existing.status == "CANCELLED":
            return existing

        if self.repository.has_assignment_for_task("ORDER", order_id):
            raise ValueError("Order must be unassigned before cancellation")

        return self.repository.cancel_order(order_id)

    def create_driver(self, request):
        driver = Driver(
            driver_id=self._generate_driver_id(),
            name=self._clean_required_text(request.name, "name"),
            start_time=self._clean_optional_text(request.start_time),
            end_time=self._clean_optional_text(request.end_time),
            is_available=self._bool_or_default(request.is_available, True),
            preferred_zone=self._clean_optional_text(request.preferred_zone),
            pallet_only=self._bool_or_default(request.pallet_only, False),
            license_no=self._clean_optional_text(request.license_no),
            email=self._clean_optional_text(request.email),
            phone_number=self._clean_optional_text(request.phone_number),
            is_deleted=False,
        )
        return self.repository.create_driver(driver)

    def update_driver(self, driver_id, request):
        existing = self.repository.get_driver(driver_id)
        if not existing or existing.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")

        is_available = self._bool_or_default(request.is_available, True)
        if not is_available and existing.is_available:
            self._ensure_driver_can_be_made_unavailable(driver_id)

        driver = Driver(
            driver_id=existing.driver_id,
            name=self._clean_required_text(request.name, "name"),
            start_time=self._clean_optional_text(request.start_time),
            end_time=self._clean_optional_text(request.end_time),
            is_available=is_available,
            preferred_zone=self._clean_optional_text(request.preferred_zone),
            pallet_only=self._bool_or_default(request.pallet_only, False),
            license_no=self._clean_optional_text(request.license_no),
            email=self._clean_optional_text(request.email),
            phone_number=self._clean_optional_text(request.phone_number),
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
        return self.get_specifications()

    def create_vehicle(self, request):
        vehicle = Vehicle(
            vehicle_id=self._generate_vehicle_id(),
            rego=self._clean_required_text(request.rego, "rego"),
            type=self._clean_optional_text(request.type) or "",
            is_available=self._bool_or_default(request.is_available, True),
            pallet_capacity=self._quantity_or_default(
                request.pallet_capacity,
                "pallet_capacity",
            ),
            tub_capacity=self._quantity_or_default(request.tub_capacity, "tub_capacity"),
            trolley_capacity=self._quantity_or_default(
                request.trolley_capacity,
                "trolley_capacity",
            ),
            stillage_capacity=self._quantity_or_default(
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

        is_available = self._bool_or_default(request.is_available, True)
        if not is_available and existing.is_available:
            self._ensure_vehicle_can_be_made_unavailable(vehicle_id)

        vehicle = Vehicle(
            vehicle_id=existing.vehicle_id,
            rego=self._clean_required_text(request.rego, "rego"),
            type=self._clean_optional_text(request.type) or "",
            is_available=is_available,
            pallet_capacity=self._quantity_or_default(
                request.pallet_capacity,
                "pallet_capacity",
            ),
            tub_capacity=self._quantity_or_default(request.tub_capacity, "tub_capacity"),
            trolley_capacity=self._quantity_or_default(
                request.trolley_capacity,
                "trolley_capacity",
            ),
            stillage_capacity=self._quantity_or_default(
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
        return self.get_specifications()

    def save_final_trip_summary(self, request: SaveFinalTripSummaryRequest):
        dispatch_date = self._clean_required_text(request.dispatch_date, "dispatch_date")
        driver_id = self._clean_required_text(request.driver_id, "driver_id")
        self._validate_driver_exists(driver_id)
        saved_by_account = self._validate_saved_by_account(
            request.saved_by_account_name,
            request.saved_by_account_id,
        )

        vehicle_id = self._clean_optional_text(request.vehicle_id)
        if vehicle_id:
            self._validate_vehicle_exists(vehicle_id)

        if self.repository.has_saved_final_trip_summary(dispatch_date, driver_id):
            raise ValueError(
                "Final Summary for this driver and dispatch date has already been saved."
            )

        rows = self._normalize_final_summary_rows(request.trips)
        if not rows:
            raise ValueError("At least one final summary row is required")

        summary = {
            "dispatch_date": dispatch_date,
            "driver_id": driver_id,
            "driver_name_snapshot": self._clean_required_text(
                request.driver_name_snapshot,
                "driver_name_snapshot",
            ),
            "vehicle_id": vehicle_id,
            "vehicle_rego_snapshot": self._clean_optional_text(
                request.vehicle_rego_snapshot
            )
            or "No vehicle selected",
            "total_pallets": sum(row["pallet_quantity_snapshot"] for row in rows),
            "total_loose_bags": sum(
                row["loose_bags_quantity_snapshot"] for row in rows
            ),
            "generated_at": self._clean_optional_text(request.generated_at),
            "saved_by_account_name": saved_by_account.account_name,
            "saved_by_account_id": saved_by_account.account_id,
        }
        return self.repository.save_final_trip_summary(summary, rows)

    def list_final_trip_summaries(self, dispatch_date):
        dispatch_date = self._clean_required_text(dispatch_date, "dispatch_date")
        return self.repository.list_final_trip_summaries(dispatch_date)

    def list_final_summary_dates(self):
        return self.repository.list_final_summary_dates()

    def get_final_trip_summary(self, summary_id):
        summary_id = self._clean_required_text(summary_id, "summary_id")
        summary = self.repository.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        return summary

    def _validate_task_type(self, task_type):
        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def _validate_task_exists(self, task_type, task_id):
        if not self.repository.get_task(task_type, task_id):
            raise ValueError(f"Task does not exist: {task_type} {task_id}")

    def _validate_driver_exists(self, driver_id):
        driver = self.repository.get_driver(driver_id)
        if not driver or driver.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")

    def _validate_vehicle_exists(self, vehicle_id):
        vehicle = self.repository.get_vehicle(vehicle_id)
        if not vehicle or vehicle.is_deleted:
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

    def _bool_or_default(self, value, default):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _ensure_driver_can_be_made_unavailable(self, driver_id):
        if self.repository.driver_has_active_assignments(driver_id):
            raise ValueError(
                "Please unassign or finalize this driver's current orders before making the driver unavailable."
            )

    def _ensure_vehicle_can_be_made_unavailable(self, vehicle_id):
        if self.repository.vehicle_has_current_selection(vehicle_id):
            raise ValueError(
                "Please clear this vehicle from current driver selections before making it unavailable."
            )

    def _validate_saved_by_account(self, account_name, account_id=None):
        cleaned_name = self._clean_required_text(
            account_name,
            "saved_by_account_name",
        )
        account = self.repository.get_operator_account_by_name(cleaned_name)
        if not account:
            raise ValueError("saved_by_account_name must reference a registered account")

        if account_id not in (None, ""):
            try:
                cleaned_account_id = int(account_id)
            except (TypeError, ValueError) as error:
                raise ValueError("saved_by_account_id must be a whole number") from error
            if cleaned_account_id != account.account_id:
                raise ValueError(
                    "saved_by_account_id does not match saved_by_account_name"
                )

        return account

    def _normalize_final_summary_rows(self, trips):
        if not isinstance(trips, list):
            raise ValueError("trips must be a list")

        normalized_rows = []
        row_no = 1
        for trip in trips:
            if not isinstance(trip, dict):
                raise ValueError("Each trip must be an object")

            trip_no = self._clean_required_text(trip.get("trip_no"), "trip_no")
            self._validate_trip_no(trip_no)

            orders = trip.get("orders") or []
            if not isinstance(orders, list):
                raise ValueError("trip orders must be a list")

            for order_snapshot in orders:
                if not isinstance(order_snapshot, dict):
                    raise ValueError("Each final summary Order row must be an object")

                task_type = self._clean_required_text(
                    order_snapshot.get("task_type") or "ORDER",
                    "task_type",
                )
                task_id = self._clean_required_text(
                    order_snapshot.get("task_id")
                    or order_snapshot.get("order_id")
                    or order_snapshot.get("order_id_snapshot"),
                    "task_id",
                )
                self._validate_task_type(task_type)
                task = self.repository.get_task(task_type, task_id)
                if not task:
                    raise ValueError(f"Task does not exist: {task_type} {task_id}")

                normalized_rows.append(
                    {
                        "trip_no": trip_no,
                        "row_no": row_no,
                        "task_type": task_type,
                        "task_id": task_id,
                        "order_id_snapshot": self._clean_optional_text(
                            order_snapshot.get("order_id_snapshot")
                            or order_snapshot.get("order_id")
                        )
                        or task_id,
                        "invoice_number_snapshot": self._clean_optional_text(
                            order_snapshot.get("invoice_number_snapshot")
                            or order_snapshot.get("invoice_number")
                        ),
                        "company_name_snapshot": self._clean_optional_text(
                            order_snapshot.get("company_name_snapshot")
                            or order_snapshot.get("company_name")
                        )
                        or "",
                        "suburb_snapshot": self._clean_optional_text(
                            order_snapshot.get("suburb_snapshot")
                            or order_snapshot.get("suburb")
                        )
                        or "",
                        "delivery_address_snapshot": self._clean_optional_text(
                            order_snapshot.get("delivery_address_snapshot")
                            or order_snapshot.get("delivery_address")
                        )
                        or "",
                        "product_snapshot": self._clean_optional_text(
                            order_snapshot.get("product_snapshot")
                            or order_snapshot.get("product")
                        ),
                        "pallet_quantity_snapshot": self._quantity_or_default(
                            order_snapshot.get("pallet_quantity_snapshot")
                            if "pallet_quantity_snapshot" in order_snapshot
                            else order_snapshot.get("pallet_quantity"),
                            "pallet_quantity_snapshot",
                        ),
                        "loose_bags_quantity_snapshot": self._quantity_or_default(
                            order_snapshot.get("loose_bags_quantity_snapshot")
                            if "loose_bags_quantity_snapshot" in order_snapshot
                            else order_snapshot.get("loose_bags_quantity"),
                            "loose_bags_quantity_snapshot",
                        ),
                        "note_snapshot": self._clean_optional_text(
                            order_snapshot.get("note_snapshot")
                            or order_snapshot.get("note")
                        ),
                    }
                )
                row_no += 1

        return normalized_rows

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

    def _generate_driver_id(self):
        return self._generate_prefixed_id("D", self.repository.list_driver_ids())

    def _generate_vehicle_id(self):
        return self._generate_prefixed_id("V", self.repository.list_vehicle_ids())

    def _generate_prefixed_id(self, prefix, existing_ids):
        highest_number = 0
        for identifier in existing_ids:
            if not identifier.startswith(prefix):
                continue
            suffix = identifier.replace(prefix, "", 1)
            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        next_number = highest_number + 1
        return f"{prefix}{next_number:03d}"
