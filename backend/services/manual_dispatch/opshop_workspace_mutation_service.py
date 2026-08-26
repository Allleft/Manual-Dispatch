import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from backend.schemas import OpShopPickupTask
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date,
    clean_optional_text,
    clean_required_iso_date,
    clean_required_text,
)
from backend.services.manual_dispatch.opshop_pickup_collection_lock import (
    ensure_opshop_pickup_collection_key_mutable,
    ensure_opshop_pickup_not_reserved,
)
from backend.services.manual_dispatch.transaction import immediate_transactional


class OpShopWorkspaceMutationService:
    def __init__(self, repository, validator, board_service):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service

    @immediate_transactional
    def apply_assignments(self, request):
        request_dispatch_date = clean_optional_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
        dispatch_date = request_dispatch_date
        changes = []
        seen_task_ids = set()
        for item in request.assignments or []:
            if not isinstance(item, dict):
                raise ValueError("Each OP SHOP assignment must be an object")
            self._reject_delivery_fields(item)
            pickup_task_id = clean_required_text(
                item.get("pickup_task_id"),
                "pickup_task_id",
            )
            if pickup_task_id in seen_task_ids:
                raise ValueError(f"Duplicate pickup_task_id: {pickup_task_id}")
            seen_task_ids.add(pickup_task_id)
            driver_id = clean_optional_text(item.get("driver_id"))
            task = self._mutable_pickup(dispatch_date, pickup_task_id)
            dispatch_date = dispatch_date or task.dispatch_date or task.pickup_date
            self._ensure_current_assignment_mutable(dispatch_date, task)
            if not driver_id:
                self._ensure_current_assignment_exists(dispatch_date, task)
            if driver_id:
                self.validator.validate_driver_exists(driver_id)
                ensure_opshop_pickup_collection_key_mutable(
                    self.repository,
                    dispatch_date,
                    driver_id,
                    task.pickup_date,
                )
            changes.append(self._assignment_task(task, driver_id))

        self.repository.apply_opshop_pickup_assignment_batch(
            dispatch_date,
            changes,
        )
        return self._response_board(
            request_dispatch_date,
            dispatch_date,
            changes,
        )

    @immediate_transactional
    def unassign_pickup(self, request):
        request_dispatch_date = clean_optional_iso_date(
            request.dispatch_date,
            "dispatch_date",
        )
        pickup_task_id = clean_required_text(
            request.pickup_task_id,
            "pickup_task_id",
        )
        task = self._mutable_pickup(request_dispatch_date, pickup_task_id)
        dispatch_date = (
            request_dispatch_date or task.dispatch_date or task.pickup_date
        )
        self._ensure_current_assignment_mutable(dispatch_date, task)
        self._ensure_current_assignment_exists(dispatch_date, task)
        self.repository.apply_opshop_pickup_assignment_batch(
            dispatch_date,
            [self._assignment_task(task, None)],
        )
        return self._response_board(
            request_dispatch_date,
            dispatch_date,
            [task],
        )

    @immediate_transactional
    def assign_countryside_route_group(self, route_group_id, request):
        route_group_id = clean_required_text(route_group_id, "route_group_id")
        route_group = self.repository.get_countryside_route_group(route_group_id)
        if not route_group:
            raise ValueError("Countryside route group does not exist")
        if not route_group.active_flag or str(route_group.status).strip().lower() != "active":
            raise ValueError("Countryside route group is not active")

        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        pickup_date = clean_required_iso_date(request.pickup_date, "pickup_date")
        driver_id = clean_required_text(
            request.assigned_driver_id,
            "assigned_driver_id",
        )
        self.validator.validate_driver_exists(driver_id)
        ensure_opshop_pickup_collection_key_mutable(
            self.repository,
            dispatch_date,
            driver_id,
            pickup_date,
        )

        memberships = [
            template
            for template in self.repository.list_opshop_templates(
                "ON_CALL",
                include_inactive=False,
            )
            if template.pickup_category == "COUNTRYSIDE"
            and template.route_group_id == route_group_id
        ]
        if not memberships:
            raise ValueError("Countryside route group has no active route templates")

        changes = []
        for membership in memberships:
            schedule = self.repository.get_opshop_pickup_schedule(
                membership.schedule_id
            )
            if not schedule:
                raise ValueError(
                    "Countryside route template schedule does not exist: "
                    f"{membership.schedule_id}"
                )
            existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
                membership.schedule_id,
                pickup_date,
            )
            if existing and existing.status == "COMPLETED":
                raise ValueError(
                    "Completed Countryside OP SHOP pickup tasks cannot be reassigned"
                )
            if existing:
                ensure_opshop_pickup_not_reserved(
                    self.repository,
                    dispatch_date,
                    existing.pickup_task_id,
                )
                self._ensure_current_assignment_mutable(dispatch_date, existing)
            task = self._route_group_task(
                schedule,
                existing,
                pickup_date,
                request.notes,
                driver_id,
            )
            changes.append(task)

        self.repository.apply_opshop_pickup_assignment_batch(
            dispatch_date,
            changes,
            remove_all_existing=True,
        )
        return self.board_service.get_board(dispatch_date)

    @immediate_transactional
    def reorder_countryside_pickup_order(self, request):
        pickup_date = clean_required_iso_date(
            request.pickup_date,
            "pickup_date",
        )
        driver_id = clean_required_text(request.driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)
        raw_task_ids = request.ordered_pickup_task_ids
        if not isinstance(raw_task_ids, list) or not raw_task_ids:
            raise ValueError("ordered_pickup_task_ids must be a non-empty list")
        ordered_task_ids = [
            clean_required_text(task_id, "ordered_pickup_task_ids")
            for task_id in raw_task_ids
        ]
        if len(ordered_task_ids) != len(set(ordered_task_ids)):
            raise ValueError("ordered_pickup_task_ids must not contain duplicates")

        collections = self.repository.list_opshop_pickup_collections(
            pickup_date=pickup_date
        )
        if any(
            collection.driver_id == driver_id
            and collection.status in {"GENERATED", "SAVED"}
            for collection in collections
        ):
            raise ValueError(
                "Generated or Saved OP SHOP Pickup Collection locks this "
                "driver and pickup date."
            )

        assigned_items = (
            self.repository.list_assigned_opshop_pickup_board_items_for_pickup_date(
                pickup_date
            )
        )
        current_items = [
            pickup
            for pickup in assigned_items
            if pickup.driver_id == driver_id
            and pickup.pickup_category == "COUNTRYSIDE"
        ]
        current_ids = {pickup.pickup_task_id for pickup in current_items}

        for pickup_task_id in ordered_task_ids:
            task = self.repository.get_opshop_pickup_task(pickup_task_id)
            if not task:
                raise ValueError(
                    f"OP SHOP pickup task does not exist: {pickup_task_id}"
                )
            if task.task_type != "OPSHOP_PICKUP":
                raise ValueError("Only OP SHOP pickup tasks can be reordered")
            schedule = self.repository.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.pickup_category != "COUNTRYSIDE":
                raise ValueError("Only Countryside OP SHOP pickups can be reordered")
            if task.status != "ASSIGNED":
                raise ValueError("Only assigned Countryside pickups can be reordered")
            if task.pickup_date != pickup_date:
                raise ValueError("Countryside pickup date does not match request")
            assignment = self.repository.find_assignment_for_task(
                "OPSHOP_PICKUP",
                pickup_task_id,
            )
            if not assignment or assignment.driver_id != driver_id:
                raise ValueError(
                    "Countryside pickup is not assigned to the requested driver"
                )

        submitted_ids = set(ordered_task_ids)
        if submitted_ids != current_ids:
            missing_ids = sorted(current_ids - submitted_ids)
            extra_ids = sorted(submitted_ids - current_ids)
            details = []
            if missing_ids:
                details.append(f"missing: {', '.join(missing_ids)}")
            if extra_ids:
                details.append(f"extra: {', '.join(extra_ids)}")
            raise ValueError(
                "ordered_pickup_task_ids must contain the complete Countryside "
                f"set for this driver and pickup date ({'; '.join(details)})"
            )

        effective_ids = [
            pickup.pickup_task_id
            for pickup in sorted(current_items, key=_countryside_trip_sort_key)
        ]
        if ordered_task_ids == effective_ids:
            return self.board_service.get_trip_summary_board(pickup_date), False

        self.repository.update_countryside_pickup_trip_sequences(
            ordered_task_ids
        )
        return self.board_service.get_trip_summary_board(pickup_date), True

    def _mutable_pickup(self, dispatch_date, pickup_task_id):
        task = self.repository.get_opshop_pickup_task(pickup_task_id)
        if not task or task.status not in {"ACTIVE", "ASSIGNED"}:
            raise ValueError(f"Active OP SHOP pickup does not exist: {pickup_task_id}")
        ensure_opshop_pickup_not_reserved(
            self.repository,
            dispatch_date,
            pickup_task_id,
        )
        return task

    def _ensure_current_assignment_mutable(self, dispatch_date, task):
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )
        if assignment:
            ensure_opshop_pickup_collection_key_mutable(
                self.repository,
                dispatch_date,
                assignment.driver_id,
                task.pickup_date,
            )

    def _ensure_current_assignment_exists(self, dispatch_date, task):
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )
        if not assignment:
            raise ValueError("OP SHOP pickup is not assigned.")

    def _response_board(self, request_dispatch_date, dispatch_date, tasks):
        pickup_dates = {task.pickup_date for task in tasks}
        if not request_dispatch_date and len(pickup_dates) == 1:
            return self.board_service.get_trip_summary_board(pickup_dates.pop())
        return self.board_service.get_board(dispatch_date)

    @staticmethod
    def _assignment_task(task, driver_id):
        same_scope = bool(driver_id) and task.driver_id == driver_id
        return replace(
            task,
            status="ASSIGNED" if driver_id else "ACTIVE",
            driver_id=driver_id,
            trip_no="trip1" if driver_id else None,
            trip_sequence=task.trip_sequence if same_scope else None,
            updated_at=_timestamp(),
        )

    @staticmethod
    def _route_group_task(schedule, existing, pickup_date, notes, driver_id):
        timestamp = _timestamp()
        if existing:
            same_scope = (
                existing.pickup_date == pickup_date
                and existing.driver_id == driver_id
            )
            return replace(
                existing,
                status="ASSIGNED",
                dispatch_date=pickup_date,
                driver_id=driver_id,
                trip_no="trip1",
                trip_sequence=(
                    existing.trip_sequence if same_scope else None
                ),
                notes=notes,
                generated_from="ON_CALL",
                updated_at=timestamp,
            )
        return OpShopPickupTask(
            pickup_task_id=_generated_task_id(schedule.schedule_id, pickup_date),
            schedule_id=schedule.schedule_id,
            opshop_id=schedule.opshop_id,
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="ON_CALL",
            status="ASSIGNED",
            dispatch_date=pickup_date,
            driver_id=driver_id,
            trip_no="trip1",
            notes=notes,
            created_at=timestamp,
            updated_at=timestamp,
        )

    @staticmethod
    def _reject_delivery_fields(item):
        for field_name in ("task_type", "trip_no"):
            if field_name in item:
                raise ValueError(f"OP SHOP assignments do not accept {field_name}")


def _generated_task_id(schedule_id, pickup_date):
    digest = hashlib.sha1(f"{schedule_id}|{pickup_date}".encode("utf-8")).hexdigest()
    return f"OPSHOP-PICKUP-{pickup_date.replace('-', '')}-{digest[:10].upper()}"


def _timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _countryside_trip_sort_key(pickup):
    fallback = (
        str(pickup.route_group_name or "").casefold(),
        str(pickup.suburb or "").casefold(),
        str(pickup.opshop_name or "").casefold(),
        str(pickup.pickup_task_id or ""),
    )
    sequence = pickup.trip_sequence
    if isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0:
        return (0, sequence, *fallback)
    return (1, 0, *fallback)
