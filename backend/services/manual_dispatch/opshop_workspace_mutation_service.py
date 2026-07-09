import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from backend.schemas import OpShopPickupTask
from backend.services.manual_dispatch.normalization import (
    clean_optional_text,
    clean_required_iso_date,
    clean_required_text,
)
from backend.services.manual_dispatch.opshop_pickup_collection_lock import (
    ensure_opshop_pickup_collection_key_mutable,
    ensure_opshop_pickup_not_reserved,
)


class OpShopWorkspaceMutationService:
    def __init__(self, repository, validator, board_service):
        self.repository = repository
        self.validator = validator
        self.board_service = board_service

    def apply_assignments(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
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
        return self.board_service.get_board(dispatch_date)

    def unassign_pickup(self, request):
        dispatch_date = clean_required_iso_date(request.dispatch_date, "dispatch_date")
        pickup_task_id = clean_required_text(
            request.pickup_task_id,
            "pickup_task_id",
        )
        task = self._mutable_pickup(dispatch_date, pickup_task_id)
        self._ensure_current_assignment_mutable(dispatch_date, task)
        self._ensure_current_assignment_exists(dispatch_date, task)
        self.repository.apply_opshop_pickup_assignment_batch(
            dispatch_date,
            [self._assignment_task(task, None)],
        )
        return self.board_service.get_board(dispatch_date)

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
        assignment = self.repository.get_assignment(
            dispatch_date,
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
        assignment = self.repository.get_assignment(
            dispatch_date,
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )
        if not assignment:
            raise ValueError(
                "OP SHOP pickup is not assigned in this workspace dispatch date."
            )

    @staticmethod
    def _assignment_task(task, driver_id):
        return replace(
            task,
            status="ASSIGNED" if driver_id else "ACTIVE",
            driver_id=driver_id,
            trip_no="trip1" if driver_id else None,
            updated_at=_timestamp(),
        )

    @staticmethod
    def _route_group_task(schedule, existing, pickup_date, notes, driver_id):
        timestamp = _timestamp()
        if existing:
            return replace(
                existing,
                status="ASSIGNED",
                dispatch_date=pickup_date,
                driver_id=driver_id,
                trip_no="trip1",
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
