from copy import deepcopy
from backend.repositories.delivery_scope import legacy_vehicle_projection, validate_delivery_trip
from backend.schemas import (
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
)

class InMemoryAssignmentRepositoryMixin:
    """Assignment in-memory responsibilities."""

    def list_assignments(self, dispatch_date):
        return [
            assignment
            for assignment in self.assignments
            if assignment.dispatch_date == dispatch_date
            and (
                (
                    assignment.task_type == "ORDER"
                    and self.get_order(assignment.task_id)
                    and self.get_order(assignment.task_id).status == "ACTIVE"
                )
                or (
                    assignment.task_type == "OPSHOP_PICKUP"
                    and self.get_opshop_pickup_task(assignment.task_id)
                    and self.get_opshop_pickup_task(assignment.task_id).status == "ASSIGNED"
                )
            )
        ]

    def list_delivery_order_assignments_for_delivery_date(self, delivery_date):
        return [
            assignment
            for assignment in self.assignments
            if assignment.task_type == "ORDER"
            and (order := self.get_order(assignment.task_id))
            and order.status == "ACTIVE"
            and order.delivery_date == delivery_date
        ]

    def list_assigned_opshop_pickup_board_items(self, dispatch_date):
        items = []
        for assignment in self.assignments:
            if assignment.dispatch_date != dispatch_date or assignment.task_type != "OPSHOP_PICKUP":
                continue
            task = self.get_opshop_pickup_task(assignment.task_id)
            if not task or task.status != "ASSIGNED":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            item = self._opshop_pickup_board_item(task, schedule, location)
            item.dispatch_date = assignment.dispatch_date
            item.driver_id = assignment.driver_id
            item.trip_no = assignment.trip_no
            item.is_assigned = True
            items.append(item)

        return sorted(
            items,
            key=lambda item: (
                item.driver_id or "",
                item.trip_no or "",
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_assigned_opshop_pickup_board_items_for_pickup_date(self, pickup_date):
        return self.list_assigned_opshop_pickup_board_items_for_dispatch_and_pickup_date(
            None,
            pickup_date,
        )

    def list_assigned_opshop_pickup_board_items_for_dispatch_and_pickup_date(
        self,
        dispatch_date,
        pickup_date,
    ):
        items = []
        for assignment in self.assignments:
            if assignment.task_type != "OPSHOP_PICKUP":
                continue
            if dispatch_date and assignment.dispatch_date != dispatch_date:
                continue
            task = self.get_opshop_pickup_task(assignment.task_id)
            if not task or task.status != "ASSIGNED" or task.pickup_date != pickup_date:
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            item = self._opshop_pickup_board_item(task, schedule, location)
            item.dispatch_date = assignment.dispatch_date
            item.driver_id = assignment.driver_id
            item.trip_no = assignment.trip_no
            item.is_assigned = True
            items.append(item)

        return sorted(
            items,
            key=lambda item: (
                item.driver_id or "",
                item.trip_no or "",
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_collectable_opshop_pickup_board_items(
        self,
        pickup_date,
        driver_id,
        dispatch_date=None,
    ):
        reserved_task_ids = {
            pickup.pickup_task_id_snapshot
            for collection in self.opshop_pickup_collections
            if collection.status in {"GENERATED", "SAVED"}
            for pickup in collection.pickups
            if pickup.pickup_task_id_snapshot
        }
        items = []
        for task in self.opshop_pickup_tasks:
            has_matching_assignment = any(
                assignment.task_type == "OPSHOP_PICKUP"
                and assignment.task_id == task.pickup_task_id
                and assignment.driver_id == task.driver_id
                and (not dispatch_date or assignment.dispatch_date == dispatch_date)
                for assignment in self.assignments
            )
            if (
                task.task_type != "OPSHOP_PICKUP"
                or task.pickup_date != pickup_date
                or task.status != "ASSIGNED"
                or task.driver_id != driver_id
                or not has_matching_assignment
                or task.pickup_task_id in reserved_task_ids
            ):
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_delivery_vehicle_assignments(self, dispatch_date=None, delivery_date=None):
        return deepcopy(sorted([
            row for row in self.driver_vehicle_assignments
            if (dispatch_date is None or row.dispatch_date == dispatch_date)
            and (delivery_date is None or row.delivery_date == delivery_date)
        ], key=lambda row: (row.delivery_date, row.driver_id, row.trip_no or "", row.dispatch_date)))

    def list_driver_vehicle_assignments(self, dispatch_date):
        return legacy_vehicle_projection([
            assignment
            for assignment in self.driver_vehicle_assignments
            if assignment.dispatch_date == dispatch_date
        ])

    def list_driver_vehicle_assignments_for_delivery_date(self, delivery_date):
        assignments = legacy_vehicle_projection([
            assignment
            for assignment in self.driver_vehicle_assignments
            if assignment.delivery_date == delivery_date
        ])
        seen_drivers = set()
        seen_vehicles = set()
        for assignment in assignments:
            if assignment.driver_id in seen_drivers:
                raise ValueError(
                    "Driver vehicle assignment integrity error for "
                    f"{delivery_date}:{assignment.driver_id}: duplicate driver."
                )
            if assignment.vehicle_id in seen_vehicles:
                raise ValueError(
                    "Driver vehicle assignment integrity error for "
                    f"{delivery_date}:{assignment.vehicle_id}: duplicate vehicle."
                )
            seen_drivers.add(assignment.driver_id)
            seen_vehicles.add(assignment.vehicle_id)
        return assignments

    def apply_opshop_pickup_assignment_batch(
        self,
        dispatch_date,
        tasks,
        remove_all_existing=False,
    ):
        original_tasks = deepcopy(self.opshop_pickup_tasks)
        original_assignments = deepcopy(self.assignments)
        try:
            for task in tasks:
                self.upsert_opshop_pickup_task(task)
                if remove_all_existing:
                    self.remove_assignments_for_task(
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                    )
                if task.driver_id:
                    self.upsert_assignment(
                        dispatch_date,
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                        task.driver_id,
                        "trip1",
                    )
                else:
                    self.remove_assignments_for_task(
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                    )
        except Exception:
            self.opshop_pickup_tasks = original_tasks
            self.assignments = original_assignments
            raise
        return [self.get_opshop_pickup_task(task.pickup_task_id) for task in tasks]

    def update_countryside_pickup_trip_sequences(self, ordered_pickup_task_ids):
        original_tasks = deepcopy(self.opshop_pickup_tasks)
        try:
            for sequence, pickup_task_id in enumerate(
                ordered_pickup_task_ids,
                start=1,
            ):
                task = self.get_opshop_pickup_task(pickup_task_id)
                if not task:
                    raise ValueError(
                        "OP SHOP pickup task does not exist: "
                        f"{pickup_task_id}"
                    )
                task.trip_sequence = sequence
                task.updated_at = "2026-05-19T00:00:00+00:00"
        except Exception:
            self.opshop_pickup_tasks = original_tasks
            raise

    def has_assignment_for_task(self, task_type, task_id):
        return any(
            assignment.task_type == task_type and assignment.task_id == task_id
            for assignment in self.assignments
        )

    def driver_has_active_assignments(self, driver_id):
        return any(assignment.driver_id == driver_id for assignment in self.assignments)

    def driver_has_vehicle_selection(self, driver_id):
        return any(
            assignment.driver_id == driver_id
            for assignment in self.driver_vehicle_assignments
        )

    def vehicle_has_current_selection(self, vehicle_id):
        return any(
            assignment.vehicle_id == vehicle_id
            for assignment in self.driver_vehicle_assignments
        )

    def upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no):
        assignments = self.list_assignments_for_task(task_type, task_id)
        if len(assignments) > 1:
            raise ValueError(
                "Manual dispatch assignment integrity error for "
                f"{task_type}:{task_id}: expected at most one row."
            )
        if assignments:
            existing = assignments[0]
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

    def find_assignment_for_task(self, task_type, task_id):
        assignments = self.list_assignments_for_task(task_type, task_id)
        if len(assignments) > 1:
            raise ValueError(
                "Manual dispatch assignment integrity error for "
                f"{task_type}:{task_id}: expected at most one row."
            )
        return assignments[0] if assignments else None

    def list_assignments_for_task(self, task_type, task_id):
        return [
            assignment
            for assignment in self.assignments
            if assignment.task_type == task_type and assignment.task_id == task_id
        ]

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

    def remove_assignments_for_task(self, task_type, task_id):
        assignments = self.list_assignments_for_task(task_type, task_id)
        if len(assignments) > 1:
            raise ValueError(
                "Manual dispatch assignment integrity error for "
                f"{task_type}:{task_id}: expected at most one row."
            )
        if not assignments:
            return False
        assignment_id = assignments[0].assignment_id
        self.assignments = [
            assignment
            for assignment in self.assignments
            if assignment.assignment_id != assignment_id
        ]
        return True

    def upsert_driver_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id):
        """Temporary day-level adapter; use the explicit trip contract for new writes."""
        assignment, conflict = self._upsert_legacy_delivery_vehicle(
            dispatch_date, delivery_date, driver_id, vehicle_id
        )
        if conflict:
            raise ValueError("Vehicle is already assigned for this delivery date.")
        return assignment

    def _upsert_legacy_delivery_vehicle(self, dispatch_date, delivery_date, driver_id, vehicle_id):
        assignments = [item for item in self.driver_vehicle_assignments if item.delivery_date == delivery_date]
        legacy = legacy_vehicle_projection(assignments)
        current = next((item for item in legacy if item.driver_id == driver_id), None)
        conflicts = sorted({item.driver_id for item in assignments
                            if item.vehicle_id == vehicle_id and item.driver_id != driver_id})
        if conflicts:
            return None, conflicts[0]
        if current:
            for item in assignments:
                if item.driver_id == driver_id:
                    item.vehicle_id = vehicle_id
            current.vehicle_id = vehicle_id
            return deepcopy(current), None
        assignment = ManualDriverVehicleAssignment(dispatch_date, delivery_date, driver_id, vehicle_id)
        self.driver_vehicle_assignments.append(assignment)
        return deepcopy(assignment), None

    def upsert_delivery_workspace_vehicle_assignment(
        self, dispatch_date, delivery_date, driver_id, vehicle_id
    ):
        """Current application's explicit day-level compatibility adapter."""
        return self._upsert_legacy_delivery_vehicle(dispatch_date, delivery_date, driver_id, vehicle_id)

    def list_delivery_trip_vehicle_assignments(self, delivery_date):
        assignments = [item for item in self.driver_vehicle_assignments
                       if item.delivery_date == delivery_date and item.trip_no is not None]
        drivers = set()
        vehicles = set()
        for item in assignments:
            validate_delivery_trip(item.trip_no)
            driver_key = item.driver_id, item.trip_no
            vehicle_key = item.vehicle_id, item.trip_no
            if driver_key in drivers or vehicle_key in vehicles:
                raise ValueError("Driver vehicle assignment integrity error: duplicate trip.")
            drivers.add(driver_key)
            vehicles.add(vehicle_key)
        return deepcopy(sorted(assignments, key=lambda item: (item.driver_id, item.trip_no, item.dispatch_date)))

    def get_delivery_trip_vehicle_assignment(self, delivery_date, driver_id, trip_no):
        validate_delivery_trip(trip_no)
        matches = [item for item in self.list_delivery_trip_vehicle_assignments(delivery_date)
                   if item.driver_id == driver_id and item.trip_no == trip_no]
        return matches[0] if matches else None

    def upsert_delivery_trip_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id, trip_no):
        validate_delivery_trip(trip_no)
        rows = self.list_delivery_trip_vehicle_assignments(delivery_date)
        frozen = [sheet for sheet in self.delivery_run_sheets
                  if sheet.delivery_date == delivery_date and sheet.trip_no in (None, trip_no)]
        if any(sheet.driver_id == driver_id for sheet in frozen):
            raise ValueError("Delivery Run Sheet locks this driver/date/trip.")
        conflicts = sorted({item.driver_id for item in [*rows, *frozen]
                            if item.vehicle_id == vehicle_id and item.driver_id != driver_id
                            and (getattr(item, "trip_no", None) in (None, trip_no))})
        if conflicts:
            return None, conflicts[0]
        current = self.get_delivery_trip_vehicle_assignment(delivery_date, driver_id, trip_no)
        origin = current.dispatch_date if current else dispatch_date
        assignment = ManualDriverVehicleAssignment(origin, delivery_date, driver_id, vehicle_id, trip_no)
        self.driver_vehicle_assignments = [item for item in self.driver_vehicle_assignments
                                          if (item.delivery_date, item.driver_id, item.trip_no)
                                          != (delivery_date, driver_id, trip_no)]
        self.driver_vehicle_assignments.append(assignment)
        return deepcopy(assignment), None

    def remove_delivery_trip_vehicle_assignment(self, delivery_date, driver_id, trip_no):
        validate_delivery_trip(trip_no)
        if self.get_delivery_run_sheet_for_driver(None, delivery_date, driver_id, trip_no):
            raise ValueError("Delivery Run Sheet locks this driver/date/trip.")
        before = len(self.driver_vehicle_assignments)
        self.driver_vehicle_assignments = [item for item in self.driver_vehicle_assignments
                                          if (item.delivery_date, item.driver_id, item.trip_no)
                                          != (delivery_date, driver_id, trip_no)]
        return before != len(self.driver_vehicle_assignments)

    def remove_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        """Legacy whole-day clear; never interprets a divergent per-trip selection."""
        rows = [item for item in self.driver_vehicle_assignments if item.driver_id == driver_id
                and (item.delivery_date == delivery_date if delivery_date else item.dispatch_date == dispatch_date)]
        legacy_vehicle_projection(rows)
        before = len(self.driver_vehicle_assignments)
        self.driver_vehicle_assignments = [item for item in self.driver_vehicle_assignments if item not in rows]
        return before != len(self.driver_vehicle_assignments)

    def _create_assignment_id(self):
        assignment_id = f"A-{self._next_assignment_number:03d}"
        self._next_assignment_number += 1
        return assignment_id
