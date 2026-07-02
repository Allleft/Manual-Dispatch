import hashlib
import re
from dataclasses import dataclass
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from backend.schemas import (
    ApplyCountrysideOpShopPickupAssignmentsRequest,
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignCountrysideRouteGroupRequest,
    CreateOpShopPickupTaskRequest,
    EnsureOpShopPickupTasksRequest,
    EnsureOpShopPickupTasksResult,
    OpShopPickupTask,
    UpdateOpShopPickupTaskRequest,
)
from backend.services.manual_dispatch.final_summary_lock import (
    is_driver_delivery_date_finalized,
)
from backend.services.manual_dispatch.opshop_pickup_collection_lock import (
    ensure_opshop_pickup_collection_key_mutable,
    ensure_opshop_pickup_not_reserved,
)


OPSHOP_FORTNIGHT_ANCHOR_DATE = date(2026, 5, 18)
MAX_GENERATION_DAYS = 31

WEEKDAY_BY_NAME = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
}

WEEKDAY_TOKEN_MAP = {
    "mon": "MONDAY",
    "monday": "MONDAY",
    "tue": "TUESDAY",
    "tues": "TUESDAY",
    "tuesday": "TUESDAY",
    "wed": "WEDNESDAY",
    "wednesday": "WEDNESDAY",
    "thu": "THURSDAY",
    "thur": "THURSDAY",
    "thurs": "THURSDAY",
    "thursday": "THURSDAY",
    "fri": "FRIDAY",
    "friday": "FRIDAY",
}

WEEKDAY_PATTERN = re.compile(
    r"\b(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday)\b",
    re.IGNORECASE,
)
MULTI_WEEKLY_PATTERN = re.compile(
    r"\b(2\s*x\s*weekly|2x\s*weekly|twice\s+weekly|two\s+times\s+weekly)\b",
    re.IGNORECASE,
)


@dataclass
class FrequencyClassification:
    frequency_type: str
    explicit_weekdays: list[str]
    is_multi_weekly: bool


class OpShopPickupService:
    def __init__(self, repository):
        self.repository = repository

    def ensure_opshop_pickup_tasks_for_window(self, request):
        return self._ensure_opshop_pickup_tasks_for_window(
            request,
            include_start_date=False,
        )

    def ensure_opshop_pickup_tasks_for_inclusive_window(self, request):
        return self._ensure_opshop_pickup_tasks_for_window(
            request,
            include_start_date=True,
        )

    def regular_pickup_week_window(self, dispatch_date):
        dispatch = _parse_iso_date(dispatch_date, "dispatch_date")
        current_week_monday = dispatch - timedelta(days=dispatch.weekday())
        if dispatch.weekday() <= 3:
            return current_week_monday, current_week_monday + timedelta(days=4)
        if dispatch.weekday() == 4:
            return dispatch, dispatch + timedelta(days=7)
        next_week_monday = current_week_monday + timedelta(days=7)
        return next_week_monday, next_week_monday + timedelta(days=4)

    def ensure_regular_opshop_pickup_tasks_for_week(self, dispatch_date):
        window_start, window_end = self.regular_pickup_week_window(dispatch_date)
        schedules = self.repository.list_opshop_pickup_schedules()
        skip_reasons = {}
        created_tasks = []
        tasks_existing = 0

        for schedule in schedules:
            if not _is_active_schedule(schedule):
                _increment(skip_reasons, "INACTIVE_OR_ON_HOLD")
                continue
            if schedule.review_required:
                _increment(skip_reasons, "REVIEW_REQUIRED")
                continue
            if schedule.run_type != "REGULAR":
                _increment(skip_reasons, "NON_REGULAR_NOT_IN_WEEKLY_LIST")
                continue
            if getattr(schedule, "pickup_category", "NORMAL") != "NORMAL":
                _increment(skip_reasons, "NON_NORMAL_CATEGORY_NOT_IN_WEEKLY_LIST")
                continue
            if schedule.run_day not in WEEKDAY_BY_NAME:
                _increment(skip_reasons, "UNKNOWN_RUN_DAY")
                continue

            for target_date in _date_range(window_start, window_end):
                if _weekday_name(target_date) != schedule.run_day:
                    continue
                pickup_date = target_date.isoformat()
                existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
                    schedule.schedule_id,
                    pickup_date,
                )
                if existing:
                    tasks_existing += 1
                    _increment(skip_reasons, "EXISTING_TASK")
                    continue
                task = self._build_generated_task(schedule, pickup_date)
                created = self.repository.insert_opshop_pickup_task(task)
                created_tasks.append(
                    self._apply_template_default_assignment(created, schedule)
                )

        return EnsureOpShopPickupTasksResult(
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            days=(window_end - window_start).days + 1,
            schedules_checked=len(schedules),
            tasks_created=len(created_tasks),
            tasks_existing=tasks_existing,
            schedules_skipped=sum(skip_reasons.values()),
            skip_reasons=skip_reasons,
            warnings={},
            created_tasks=created_tasks,
        )

    def list_opshop_pickup_schedule_candidates(self, run_type="scheduled"):
        normalized = (run_type or "scheduled").strip().lower()
        if normalized in {"scheduled", "regular"}:
            return self.repository.list_scheduled_opshop_pickup_schedule_candidates()
        if normalized in {"oncall", "on_call"}:
            return self.repository.list_oncall_opshop_pickup_schedule_candidates()
        if normalized in {"countryside", "country", "countryside_oncall"}:
            return self.repository.list_countryside_opshop_pickup_schedule_candidates()
        raise ValueError("Only scheduled, oncall, or countryside OP SHOP pickup schedules are supported")

    def create_opshop_pickup_task(self, request):
        request = request or CreateOpShopPickupTaskRequest()
        schedule_id = _clean_text(request.schedule_id)
        pickup_date = _parse_iso_date(request.pickup_date, "pickup_date").isoformat()
        schedule = self._get_schedulable_schedule(schedule_id)
        self._requested_assignment_context(
            request,
            pickup_date,
            default_driver_id=schedule.default_driver_id,
        )

        existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
            schedule.schedule_id,
            pickup_date,
        )
        if existing and existing.status == "CANCELLED":
            restored = self.repository.upsert_opshop_pickup_task(
                replace(
                    existing,
                    status="ACTIVE",
                    driver_id=None,
                    trip_no=None,
                    dispatch_date=pickup_date,
                    notes=request.notes,
                    generated_from="MANUAL",
                    updated_at=_timestamp(),
                )
            )
            return self._apply_created_assignment_if_requested(restored, request, schedule)
        if existing:
            raise ValueError("OP SHOP pickup task already exists for this schedule and date")

        timestamp = _timestamp()
        task = OpShopPickupTask(
            pickup_task_id=_generated_task_id(schedule.schedule_id, pickup_date),
            schedule_id=schedule.schedule_id,
            opshop_id=schedule.opshop_id,
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="MANUAL",
            status="ACTIVE",
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes=request.notes,
            created_at=timestamp,
            updated_at=timestamp,
        )
        created = self.repository.insert_opshop_pickup_task(task)
        return self._apply_created_assignment_if_requested(created, request, schedule)

    def create_oncall_opshop_pickup_task(self, request):
        request = request or CreateOpShopPickupTaskRequest()
        schedule_id = _clean_text(request.schedule_id)
        pickup_date = _parse_iso_date(request.pickup_date, "pickup_date").isoformat()
        schedule = self._get_oncall_schedule(schedule_id)
        self._requested_assignment_context(
            request,
            pickup_date,
            default_driver_id=schedule.default_driver_id,
        )

        existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
            schedule.schedule_id,
            pickup_date,
        )
        if existing and existing.status == "CANCELLED":
            restored = self.repository.upsert_opshop_pickup_task(
                replace(
                    existing,
                    status="ACTIVE",
                    driver_id=None,
                    trip_no=None,
                    dispatch_date=pickup_date,
                    notes=request.notes,
                    generated_from="ON_CALL",
                    updated_at=_timestamp(),
                )
            )
            return self._apply_created_assignment_if_requested(restored, request, schedule)
        if existing:
            raise ValueError("OP SHOP pickup task already exists for this schedule and date")

        timestamp = _timestamp()
        task = OpShopPickupTask(
            pickup_task_id=_generated_task_id(schedule.schedule_id, pickup_date),
            schedule_id=schedule.schedule_id,
            opshop_id=schedule.opshop_id,
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="ON_CALL",
            status="ACTIVE",
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes=request.notes,
            created_at=timestamp,
            updated_at=timestamp,
        )
        created = self.repository.insert_opshop_pickup_task(task)
        return self._apply_created_assignment_if_requested(created, request, schedule)

    def update_opshop_pickup_task(self, pickup_task_id, request):
        request = request or UpdateOpShopPickupTaskRequest()
        task = self.repository.get_opshop_pickup_task(pickup_task_id)
        if not task:
            raise ValueError("OP SHOP pickup task does not exist")
        if task.status in {"CANCELLED", "COMPLETED"}:
            raise ValueError("Cancelled or completed OP SHOP pickup tasks cannot be edited")
        self._ensure_opshop_task_not_saved_locked(
            task,
            _assignment_dispatch_date_for_request(request, task),
        )

        next_pickup_date = task.pickup_date
        if request.pickup_date:
            next_pickup_date = _parse_iso_date(request.pickup_date, "pickup_date").isoformat()

        if next_pickup_date != task.pickup_date:
            if task.status == "ASSIGNED":
                schedule = self.repository.get_opshop_pickup_schedule(task.schedule_id)
                if not schedule or schedule.run_type != "ON_CALL":
                    raise ValueError("Assigned OP SHOP pickup tasks cannot change pickup date")
            existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
                task.schedule_id,
                next_pickup_date,
            )
            if existing and existing.pickup_task_id != task.pickup_task_id:
                raise ValueError("OP SHOP pickup task already exists for this schedule and date")
            if task.status == "ASSIGNED" and task.driver_id:
                dispatch_date = _assignment_dispatch_date_for_request(request, task)
                if is_driver_delivery_date_finalized(
                    self.repository,
                    dispatch_date,
                    task.driver_id,
                    task.pickup_date,
                ):
                    raise ValueError("Final Trip Summary has already been saved for this driver and delivery date.")
                if is_driver_delivery_date_finalized(
                    self.repository,
                    dispatch_date,
                    task.driver_id,
                    next_pickup_date,
                ):
                    raise ValueError("Final Trip Summary has already been saved for this driver and delivery date.")

        updated = replace(
            task,
            pickup_date=next_pickup_date,
            dispatch_date=next_pickup_date,
            notes=request.notes,
            updated_at=_timestamp(),
        )
        saved = self.repository.upsert_opshop_pickup_task(updated)
        if task.status == "ASSIGNED" and task.driver_id and next_pickup_date != task.pickup_date:
            dispatch_date = _assignment_dispatch_date_for_request(request, task)
            self.repository.remove_assignments_for_task("OPSHOP_PICKUP", task.pickup_task_id)
            self.repository.upsert_assignment(
                dispatch_date,
                "OPSHOP_PICKUP",
                task.pickup_task_id,
                task.driver_id,
                task.trip_no or "trip1",
            )
        return saved

    def delete_opshop_pickup_task(self, pickup_task_id):
        task = self.repository.get_opshop_pickup_task(pickup_task_id)
        if not task:
            raise ValueError("OP SHOP pickup task does not exist")
        if task.status not in {"ACTIVE", "ASSIGNED"}:
            raise ValueError("Only active or assigned OP SHOP pickup tasks can be deleted")
        self._ensure_opshop_task_not_saved_locked(task)

        self.repository.remove_assignments_for_task("OPSHOP_PICKUP", task.pickup_task_id)

        cancelled = replace(
            task,
            status="CANCELLED",
            driver_id=None,
            trip_no=None,
            updated_at=_timestamp(),
        )
        return self.repository.upsert_opshop_pickup_task(cancelled)

    def apply_weekly_assignments(self, request):
        request = request or ApplyWeeklyOpShopPickupAssignmentsRequest(dispatch_date="")
        dispatch = _parse_iso_date(request.dispatch_date, "dispatch_date")
        window_start, window_end = self.regular_pickup_week_window(dispatch.isoformat())
        driver_ids = set(self.repository.list_driver_ids())

        for assignment in request.assignments or []:
            pickup_task_id = _clean_text(assignment.get("pickup_task_id"))
            driver_id = _clean_text(assignment.get("driver_id"))
            task = self.repository.get_opshop_pickup_task(pickup_task_id)
            if not task or task.status in {"CANCELLED", "COMPLETED"}:
                continue
            pickup_date = _parse_iso_date(task.pickup_date, "pickup_date")
            if pickup_date < dispatch:
                continue
            if not (window_start <= pickup_date <= window_end):
                continue
            schedule = self.repository.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "REGULAR" or not _is_active_schedule(schedule):
                continue

            if self._is_opshop_task_saved_locked(task, request.dispatch_date):
                continue
            if not driver_id:
                self.repository.remove_assignment(
                    request.dispatch_date,
                    "OPSHOP_PICKUP",
                    pickup_task_id,
                )
                self.repository.update_opshop_pickup_task_assignment_status(
                    pickup_task_id,
                    "ACTIVE",
                    None,
                    None,
                )
                continue
            if driver_id not in driver_ids:
                continue
            if is_driver_delivery_date_finalized(
                self.repository,
                request.dispatch_date,
                driver_id,
                task.pickup_date,
            ):
                continue

            self.repository.upsert_assignment(
                request.dispatch_date,
                "OPSHOP_PICKUP",
                pickup_task_id,
                driver_id,
                "trip1",
            )
            self.repository.update_opshop_pickup_task_assignment_status(
                pickup_task_id,
                "ASSIGNED",
                driver_id,
                "trip1",
            )

    def apply_oncall_assignments(self, request):
        request = request or ApplyOncallOpShopPickupAssignmentsRequest(dispatch_date="")
        dispatch = _parse_iso_date(request.dispatch_date, "dispatch_date")
        driver_ids = set(self.repository.list_driver_ids())

        for assignment in request.assignments or []:
            pickup_task_id = _clean_text(assignment.get("pickup_task_id"))
            driver_id = _clean_text(assignment.get("driver_id"))
            task = self.repository.get_opshop_pickup_task(pickup_task_id)
            if not task or task.status in {"CANCELLED", "COMPLETED"}:
                continue
            pickup_date = _parse_iso_date(task.pickup_date, "pickup_date")
            if pickup_date < dispatch:
                continue
            schedule = self.repository.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL" or not _is_active_schedule(schedule):
                continue
            if getattr(schedule, "pickup_category", "NORMAL") != "NORMAL":
                continue

            if self._is_opshop_task_saved_locked(task, request.dispatch_date):
                continue
            if not driver_id:
                self.repository.remove_assignment(
                    request.dispatch_date,
                    "OPSHOP_PICKUP",
                    pickup_task_id,
                )
                self.repository.update_opshop_pickup_task_assignment_status(
                    pickup_task_id,
                    "ACTIVE",
                    None,
                    None,
                )
                continue
            if driver_id not in driver_ids:
                continue
            if is_driver_delivery_date_finalized(
                self.repository,
                request.dispatch_date,
                driver_id,
                task.pickup_date,
            ):
                continue

            self.repository.upsert_assignment(
                request.dispatch_date,
                "OPSHOP_PICKUP",
                pickup_task_id,
                driver_id,
                "trip1",
            )
            self.repository.update_opshop_pickup_task_assignment_status(
                pickup_task_id,
                "ASSIGNED",
                driver_id,
                "trip1",
            )

    def apply_countryside_assignments(self, request):
        request = request or ApplyCountrysideOpShopPickupAssignmentsRequest(dispatch_date="")
        dispatch = _parse_iso_date(request.dispatch_date, "dispatch_date")
        driver_ids = set(self.repository.list_driver_ids())

        for assignment in request.assignments or []:
            pickup_task_id = _clean_text(assignment.get("pickup_task_id"))
            driver_id = _clean_text(assignment.get("driver_id"))
            task = self.repository.get_opshop_pickup_task(pickup_task_id)
            if not task or task.status in {"CANCELLED", "COMPLETED"}:
                continue
            pickup_date = _parse_iso_date(task.pickup_date, "pickup_date")
            if pickup_date < dispatch:
                continue
            schedule = self.repository.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL" or not _is_active_schedule(schedule):
                continue
            if getattr(schedule, "pickup_category", "NORMAL") != "COUNTRYSIDE":
                continue

            if self._is_opshop_task_saved_locked(task, request.dispatch_date):
                continue
            if not driver_id:
                self.repository.remove_assignment(
                    request.dispatch_date,
                    "OPSHOP_PICKUP",
                    pickup_task_id,
                )
                self.repository.update_opshop_pickup_task_assignment_status(
                    pickup_task_id,
                    "ACTIVE",
                    None,
                    None,
                )
                continue
            if driver_id not in driver_ids:
                continue
            if is_driver_delivery_date_finalized(
                self.repository,
                request.dispatch_date,
                driver_id,
                task.pickup_date,
            ):
                continue

            self.repository.upsert_assignment(
                request.dispatch_date,
                "OPSHOP_PICKUP",
                pickup_task_id,
                driver_id,
                "trip1",
            )
            self.repository.update_opshop_pickup_task_assignment_status(
                pickup_task_id,
                "ASSIGNED",
                driver_id,
                "trip1",
            )

    def _ensure_opshop_task_not_saved_locked(self, task, fallback_dispatch_date=None):
        if self._is_opshop_task_saved_locked(task, fallback_dispatch_date):
            raise ValueError("Final Trip Summary has already been saved for this driver and delivery date.")

    def _is_opshop_task_saved_locked(self, task, fallback_dispatch_date=None):
        if not task or task.status != "ASSIGNED" or not task.driver_id:
            return False
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            task.pickup_task_id,
        )
        dispatch_date = (
            assignment.dispatch_date
            if assignment
            else fallback_dispatch_date or task.dispatch_date or task.pickup_date
        )
        return is_driver_delivery_date_finalized(
            self.repository,
            dispatch_date,
            task.driver_id,
            task.pickup_date,
        )

    def assign_countryside_route_group_pickups(self, route_group_id, request):
        request = request or AssignCountrysideRouteGroupRequest(
            dispatch_date="",
            pickup_date="",
            assigned_driver_id="",
        )
        route_group_id = _clean_text(route_group_id)
        route_group = self.repository.get_countryside_route_group(route_group_id)
        if not route_group:
            raise ValueError("Countryside route group does not exist")
        if not route_group.active_flag or _clean_status(route_group.status) != "active":
            raise ValueError("Countryside route group is not active")

        dispatch_date = _parse_iso_date(request.dispatch_date, "dispatch_date").isoformat()
        pickup_date = _parse_iso_date(request.pickup_date, "pickup_date").isoformat()
        driver_id = _clean_text(request.assigned_driver_id)
        if not driver_id:
            raise ValueError("assigned_driver_id is required")
        if driver_id not in set(self.repository.list_driver_ids()):
            raise ValueError("Driver does not exist")
        if is_driver_delivery_date_finalized(
            self.repository,
            dispatch_date,
            driver_id,
            pickup_date,
        ):
            raise ValueError("Final Trip Summary has already been saved for this driver and delivery date.")

        memberships = self._active_countryside_route_memberships(route_group_id)
        if not memberships:
            raise ValueError("Countryside route group has no active route templates")

        schedules = []
        for membership in memberships:
            schedule = self.repository.get_opshop_pickup_schedule(membership.schedule_id)
            if not schedule:
                continue
            existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
                schedule.schedule_id,
                pickup_date,
            )
            if existing and existing.status == "COMPLETED":
                raise ValueError(
                    "Completed Countryside OP SHOP pickup tasks cannot be reassigned"
                )
            if existing and existing.status == "ASSIGNED" and existing.driver_id:
                if is_driver_delivery_date_finalized(
                    self.repository,
                    dispatch_date,
                    existing.driver_id,
                    existing.pickup_date,
                ):
                    raise ValueError(
                        "Final Trip Summary has already been saved for this driver and delivery date."
                    )
            schedules.append((schedule, existing))

        for schedule, existing in schedules:
            task = self._upsert_countryside_route_group_task(
                schedule,
                existing,
                pickup_date,
                request.notes,
            )
            self.repository.remove_assignments_for_task("OPSHOP_PICKUP", task.pickup_task_id)
            self.repository.upsert_assignment(
                dispatch_date,
                "OPSHOP_PICKUP",
                task.pickup_task_id,
                driver_id,
                "trip1",
            )
            self.repository.update_opshop_pickup_task_assignment_status(
                task.pickup_task_id,
                "ASSIGNED",
                driver_id,
                "trip1",
            )

    def _apply_created_assignment_if_requested(self, task, request, schedule=None):
        driver_id, dispatch_date = self._requested_assignment_context(
            request,
            task.pickup_date,
            default_driver_id=schedule.default_driver_id if schedule else None,
        )
        if not driver_id:
            return task

        return self._persist_created_assignment(task, driver_id, dispatch_date)

    def _persist_created_assignment(self, task, driver_id, dispatch_date):
        ensure_opshop_pickup_not_reserved(
            self.repository,
            dispatch_date,
            task.pickup_task_id,
        )
        self.repository.upsert_assignment(
            dispatch_date,
            "OPSHOP_PICKUP",
            task.pickup_task_id,
            driver_id,
            "trip1",
        )
        self.repository.update_opshop_pickup_task_assignment_status(
            task.pickup_task_id,
            "ASSIGNED",
            driver_id,
            "trip1",
        )
        return self.repository.get_opshop_pickup_task(task.pickup_task_id)

    def _apply_template_default_assignment(self, task, schedule):
        if not schedule.default_driver_id:
            return task
        request = CreateOpShopPickupTaskRequest(dispatch_date=task.pickup_date)
        try:
            driver_id, dispatch_date = self._requested_assignment_context(
                request,
                task.pickup_date,
                default_driver_id=schedule.default_driver_id,
            )
        except ValueError:
            # Board task generation must remain available when a stored default
            # driver is unavailable or its driver/date key is already locked.
            return task
        return self._persist_created_assignment(task, driver_id, dispatch_date)

    def _active_countryside_route_memberships(self, route_group_id):
        return [
            template
            for template in self.repository.list_opshop_templates(
                "ON_CALL",
                include_inactive=False,
            )
            if template.pickup_category == "COUNTRYSIDE"
            and template.route_group_id == route_group_id
        ]

    def _upsert_countryside_route_group_task(self, schedule, existing, pickup_date, notes):
        timestamp = _timestamp()
        if existing and existing.status == "CANCELLED":
            return self.repository.upsert_opshop_pickup_task(
                replace(
                    existing,
                    status="ACTIVE",
                    driver_id=None,
                    trip_no=None,
                    dispatch_date=pickup_date,
                    notes=notes,
                    generated_from="ON_CALL",
                    updated_at=timestamp,
                )
            )
        if existing:
            return self.repository.upsert_opshop_pickup_task(
                replace(
                    existing,
                    dispatch_date=pickup_date,
                    notes=notes,
                    generated_from="ON_CALL",
                    updated_at=timestamp,
                )
            )

        task = OpShopPickupTask(
            pickup_task_id=_generated_task_id(schedule.schedule_id, pickup_date),
            schedule_id=schedule.schedule_id,
            opshop_id=schedule.opshop_id,
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="ON_CALL",
            status="ACTIVE",
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes=notes,
            created_at=timestamp,
            updated_at=timestamp,
        )
        return self.repository.insert_opshop_pickup_task(task)

    def _requested_assignment_context(
        self,
        request,
        pickup_date,
        default_driver_id=None,
    ):
        driver_id = _clean_text(getattr(request, "assigned_driver_id", None))
        if not driver_id:
            driver_id = _clean_text(default_driver_id)
        if not driver_id:
            return None, None
        if driver_id not in set(self.repository.list_driver_ids()):
            raise ValueError("Driver does not exist")
        dispatch_date = _parse_iso_date(
            getattr(request, "dispatch_date", None) or pickup_date,
            "dispatch_date",
        ).isoformat()
        if is_driver_delivery_date_finalized(
            self.repository,
            dispatch_date,
            driver_id,
            pickup_date,
        ):
            raise ValueError("Final Trip Summary has already been saved for this driver and delivery date.")
        ensure_opshop_pickup_collection_key_mutable(
            self.repository,
            dispatch_date,
            driver_id,
            pickup_date,
        )
        return driver_id, dispatch_date

    def _ensure_opshop_pickup_tasks_for_window(self, request, include_start_date):
        start = _parse_iso_date(request.start_date, "start_date")
        days = int(request.days or 14)
        if days < 1:
            raise ValueError("days must be at least 1")
        if days > MAX_GENERATION_DAYS:
            raise ValueError(f"days must be {MAX_GENERATION_DAYS} or less")

        window_start = start if include_start_date else start + timedelta(days=1)
        window_end = (
            start + timedelta(days=days - 1)
            if include_start_date
            else start + timedelta(days=days)
        )
        schedules = self.repository.list_opshop_pickup_schedules()
        skip_reasons = {}
        warnings = {}
        created_tasks = []
        tasks_existing = 0

        for schedule in schedules:
            if not _is_active_schedule(schedule):
                _increment(skip_reasons, "INACTIVE_OR_ON_HOLD")
                continue
            if schedule.review_required:
                _increment(skip_reasons, "REVIEW_REQUIRED")
                continue
            if schedule.run_type == "ON_CALL":
                _increment(skip_reasons, "ON_CALL_NOT_AUTO_GENERATED")
                continue
            if schedule.run_type not in {"STANDARD", "REGULAR"}:
                _increment(skip_reasons, "UNKNOWN_RUN_TYPE")
                continue

            frequency = classify_pickup_frequency(schedule.pickup_frequency)
            if frequency.frequency_type == "MONTHLY":
                _increment(skip_reasons, "MONTHLY_NOT_AUTO_GENERATED")
                continue
            if frequency.frequency_type == "UNKNOWN":
                _increment(skip_reasons, "UNKNOWN_FREQUENCY")
                continue

            weekdays = self._resolve_generation_weekdays(schedule, frequency, warnings)
            if not weekdays:
                _increment(
                    skip_reasons,
                    "MISSING_RUN_DAY" if not schedule.run_day else "UNKNOWN_RUN_DAY",
                )
                continue

            if frequency.frequency_type == "FORTNIGHTLY" and schedule.fortnight_group not in {
                "A",
                "B",
            }:
                _increment(skip_reasons, "FORTNIGHT_GROUP_MISSING")
                continue

            for target_date in _date_range(window_start, window_end):
                weekday_name = _weekday_name(target_date)
                if weekday_name not in weekdays:
                    continue
                if frequency.frequency_type == "FORTNIGHTLY":
                    target_group = _fortnight_group_for_date(target_date)
                    if target_group != schedule.fortnight_group:
                        _increment(skip_reasons, "FORTNIGHT_GROUP_MISMATCH")
                        continue

                pickup_date = target_date.isoformat()
                existing = self.repository.find_opshop_pickup_task_by_schedule_and_date(
                    schedule.schedule_id,
                    pickup_date,
                )
                if existing:
                    tasks_existing += 1
                    _increment(skip_reasons, "EXISTING_TASK")
                    continue

                task = self._build_generated_task(schedule, pickup_date)
                created = self.repository.insert_opshop_pickup_task(task)
                created_tasks.append(
                    self._apply_template_default_assignment(created, schedule)
                )

        return EnsureOpShopPickupTasksResult(
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            days=days,
            schedules_checked=len(schedules),
            tasks_created=len(created_tasks),
            tasks_existing=tasks_existing,
            schedules_skipped=sum(skip_reasons.values()),
            skip_reasons=skip_reasons,
            warnings=warnings,
            created_tasks=created_tasks,
        )

    def _get_schedulable_schedule(self, schedule_id):
        if not schedule_id:
            raise ValueError("schedule_id is required")
        schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        if not schedule:
            raise ValueError("OP SHOP pickup schedule does not exist")
        if not _is_active_schedule(schedule):
            raise ValueError("OP SHOP pickup schedule is not active")
        if schedule.run_type not in {"STANDARD", "REGULAR"}:
            raise ValueError("Only STANDARD or REGULAR OP SHOP pickup schedules are supported")
        return schedule

    def _get_oncall_schedule(self, schedule_id):
        if not schedule_id:
            raise ValueError("schedule_id is required")
        schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        if not schedule:
            raise ValueError("OP SHOP pickup schedule does not exist")
        if not _is_active_schedule(schedule):
            raise ValueError("OP SHOP pickup schedule is not active")
        if schedule.run_type != "ON_CALL":
            raise ValueError("Only ON_CALL OP SHOP pickup schedules are supported")
        return schedule

    def _resolve_generation_weekdays(self, schedule, frequency, warnings):
        if frequency.explicit_weekdays:
            if schedule.run_day and schedule.run_day not in frequency.explicit_weekdays:
                _increment(warnings, "FREQUENCY_WEEKDAY_OVERRIDES_RUN_DAY")
            return frequency.explicit_weekdays

        if frequency.is_multi_weekly and schedule.run_day in WEEKDAY_BY_NAME:
            _increment(warnings, "MULTI_WEEKLY_WITHOUT_EXPLICIT_DAYS_USED_RUN_DAY_ONLY")

        if not schedule.run_day:
            return []
        if schedule.run_day not in WEEKDAY_BY_NAME:
            return []
        return [schedule.run_day]

    def _build_generated_task(self, schedule, pickup_date):
        timestamp = _timestamp()
        return OpShopPickupTask(
            pickup_task_id=_generated_task_id(schedule.schedule_id, pickup_date),
            schedule_id=schedule.schedule_id,
            opshop_id=schedule.opshop_id,
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from=schedule.run_type,
            status="ACTIVE",
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes=None,
            created_at=timestamp,
            updated_at=timestamp,
        )


def classify_pickup_frequency(text):
    normalized = _normalize_frequency_text(text)
    explicit_weekdays = extract_weekdays_from_frequency(normalized)
    if not normalized:
        return FrequencyClassification("UNKNOWN", explicit_weekdays, False)
    if "month" in normalized:
        return FrequencyClassification("MONTHLY", explicit_weekdays, False)
    if "fortnight" in normalized or "f/night" in normalized or "fnight" in normalized:
        return FrequencyClassification("FORTNIGHTLY", explicit_weekdays, False)

    is_multi_weekly = bool(MULTI_WEEKLY_PATTERN.search(normalized)) or len(
        explicit_weekdays
    ) > 1
    if "week" in normalized or is_multi_weekly:
        return FrequencyClassification("WEEKLY", explicit_weekdays, is_multi_weekly)
    return FrequencyClassification("UNKNOWN", explicit_weekdays, False)


def extract_weekdays_from_frequency(text):
    weekdays = []
    for match in WEEKDAY_PATTERN.findall(text or ""):
        weekday = WEEKDAY_TOKEN_MAP[match.lower()]
        if weekday not in weekdays:
            weekdays.append(weekday)
    return weekdays


def _parse_iso_date(value, field_name):
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from error


def _assignment_dispatch_date_for_request(request, task):
    value = _clean_text(getattr(request, "dispatch_date", None))
    if value:
        return _parse_iso_date(value, "dispatch_date").isoformat()
    return _parse_iso_date(task.dispatch_date or task.pickup_date, "dispatch_date").isoformat()


def _clean_text(value):
    return str(value or "").strip()


def _is_active_schedule(schedule):
    return schedule.active_flag and _clean_status(schedule.status) == "active"


def _clean_status(value):
    return " ".join(str(value or "").strip().lower().split())


def _normalize_frequency_text(text):
    return " ".join(str(text or "").strip().lower().replace("_", " ").split())


def _date_range(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _weekday_name(target_date):
    for weekday_name, weekday_number in WEEKDAY_BY_NAME.items():
        if target_date.weekday() == weekday_number:
            return weekday_name
    return None


def _fortnight_group_for_date(target_date):
    weeks_from_anchor = (target_date - OPSHOP_FORTNIGHT_ANCHOR_DATE).days // 7
    return "A" if weeks_from_anchor % 2 == 0 else "B"


def _generated_task_id(schedule_id, pickup_date):
    digest = hashlib.sha1(f"{schedule_id}|{pickup_date}".encode("utf-8")).hexdigest()
    date_token = pickup_date.replace("-", "")
    return f"OPSHOP-PICKUP-{date_token}-{digest[:10].upper()}"


def _timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _increment(counter, key):
    counter[key] = counter.get(key, 0) + 1
