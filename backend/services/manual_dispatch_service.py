from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import ManualDispatchBoardResponse


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
