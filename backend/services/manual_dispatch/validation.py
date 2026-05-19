from backend.services.manual_dispatch.normalization import clean_required_text


SUPPORTED_TASK_TYPES = {"ORDER", "OPSHOP_PICKUP"}
SUPPORTED_TRIPS = {"trip1", "trip2"}


class ManualDispatchValidator:
    def __init__(self, repository):
        self.repository = repository

    def validate_task_type(self, task_type):
        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def validate_task_exists(self, task_type, task_id):
        if not self.repository.get_task(task_type, task_id):
            raise ValueError(f"Task does not exist: {task_type} {task_id}")

    def validate_driver_exists(self, driver_id):
        driver = self.repository.get_driver(driver_id)
        if not driver or driver.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")

    def validate_vehicle_exists(self, vehicle_id):
        vehicle = self.repository.get_vehicle(vehicle_id)
        if not vehicle or vehicle.is_deleted:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")

    def validate_trip_no(self, trip_no):
        if trip_no not in SUPPORTED_TRIPS:
            raise ValueError(f"Invalid trip_no: {trip_no}")

    def ensure_driver_can_be_made_unavailable(self, driver_id):
        if self.repository.driver_has_active_assignments(driver_id):
            raise ValueError(
                "Please unassign or finalize this driver's current orders before making the driver unavailable."
            )

    def ensure_vehicle_can_be_made_unavailable(self, vehicle_id):
        if self.repository.vehicle_has_current_selection(vehicle_id):
            raise ValueError(
                "Please clear this vehicle from current driver selections before making it unavailable."
            )

    def validate_saved_by_account(self, account_name, account_id=None):
        cleaned_name = clean_required_text(
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
