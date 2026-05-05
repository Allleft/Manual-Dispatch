from backend.schemas import (
    Driver,
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
    Order,
    Vehicle,
)


class InMemoryManualDispatchRepository:
    """Temporary in-memory data store for Phase 5.

    This is not persistence. Data resets whenever the backend process restarts.
    """

    def __init__(self):
        self.orders = [
            Order(
                order_id="ORD-001",
                company_name="Demo Customer A",
                delivery_address="1 Demo Street",
                suburb="Dandenong",
                postcode="3175",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=2,
                loose_bags_quantity=0,
                start_time=None,
                end_time=None,
                note=None,
            ),
            Order(
                order_id="ORD-002",
                company_name="Demo Customer B",
                delivery_address="2 Demo Street",
                suburb="Clayton",
                postcode="3168",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=0,
                loose_bags_quantity=12,
                start_time=None,
                end_time=None,
                note="Loose Bags only",
            ),
            Order(
                order_id="ORD-003",
                company_name="Demo Customer C",
                delivery_address="3 Demo Street",
                suburb="Springvale",
                postcode="3171",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=3,
                loose_bags_quantity=0,
                start_time=None,
                end_time=None,
                note=None,
            ),
        ]
        self.drivers = [
            Driver(
                driver_id="D001",
                name="John",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
            ),
            Driver(
                driver_id="D002",
                name="Tony",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
            ),
            Driver(
                driver_id="D003",
                name="David",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
            ),
        ]
        self.vehicles = [
            Vehicle(
                vehicle_id="V001",
                rego="ABC123",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
            Vehicle(
                vehicle_id="V002",
                rego="XYZ888",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
            Vehicle(
                vehicle_id="V003",
                rego="MCC001",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
        ]
        self.assignments = []
        self.driver_vehicle_assignments = []
        self._next_assignment_number = 1

    def list_orders(self):
        return list(self.orders)

    def list_drivers(self):
        return list(self.drivers)

    def list_vehicles(self):
        return list(self.vehicles)

    def list_assignments(self, dispatch_date):
        return [
            assignment
            for assignment in self.assignments
            if assignment.dispatch_date == dispatch_date
        ]

    def list_driver_vehicle_assignments(self, dispatch_date):
        return [
            assignment
            for assignment in self.driver_vehicle_assignments
            if assignment.dispatch_date == dispatch_date
        ]

    def get_order(self, order_id):
        return next((order for order in self.orders if order.order_id == order_id), None)

    def get_driver(self, driver_id):
        return next(
            (driver for driver in self.drivers if driver.driver_id == driver_id),
            None,
        )

    def get_vehicle(self, vehicle_id):
        return next(
            (vehicle for vehicle in self.vehicles if vehicle.vehicle_id == vehicle_id),
            None,
        )

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            return self.get_order(task_id)
        return None

    def upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no):
        existing = self.get_assignment(dispatch_date, task_type, task_id)
        if existing:
            existing.driver_id = driver_id
            existing.trip_no = trip_no
            return existing

        assignment = ManualDispatchAssignment(
            assignment_id=self._create_assignment_id(),
            dispatch_date=dispatch_date,
            task_type=task_type,
            task_id=task_id,
            driver_id=driver_id,
            trip_no=trip_no,
        )
        self.assignments.append(assignment)
        return assignment

    def get_assignment(self, dispatch_date, task_type, task_id):
        return next(
            (
                assignment
                for assignment in self.assignments
                if assignment.dispatch_date == dispatch_date
                and assignment.task_type == task_type
                and assignment.task_id == task_id
            ),
            None,
        )

    def remove_assignment(self, dispatch_date, task_type, task_id):
        before_count = len(self.assignments)
        self.assignments = [
            assignment
            for assignment in self.assignments
            if not (
                assignment.dispatch_date == dispatch_date
                and assignment.task_type == task_type
                and assignment.task_id == task_id
            )
        ]
        return len(self.assignments) != before_count

    def upsert_driver_vehicle_assignment(self, dispatch_date, driver_id, vehicle_id):
        existing = next(
            (
                assignment
                for assignment in self.driver_vehicle_assignments
                if assignment.dispatch_date == dispatch_date
                and assignment.driver_id == driver_id
            ),
            None,
        )
        if existing:
            existing.vehicle_id = vehicle_id
            return existing

        assignment = ManualDriverVehicleAssignment(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )
        self.driver_vehicle_assignments.append(assignment)
        return assignment

    def _create_assignment_id(self):
        assignment_id = f"A-{self._next_assignment_number:03d}"
        self._next_assignment_number += 1
        return assignment_id
