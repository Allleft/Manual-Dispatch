import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from backend.schemas import (
    EnsureOpShopPickupTasksRequest,
    EnsureOpShopPickupTasksResult,
    OpShopPickupTask,
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
        start = _parse_iso_date(request.start_date, "start_date")
        days = int(request.days or 14)
        if days < 1:
            raise ValueError("days must be at least 1")
        if days > MAX_GENERATION_DAYS:
            raise ValueError(f"days must be {MAX_GENERATION_DAYS} or less")

        end = start + timedelta(days=days - 1)
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

            for target_date in _date_range(start, end):
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
                created_tasks.append(self.repository.insert_opshop_pickup_task(task))

        return EnsureOpShopPickupTasksResult(
            window_start=start.isoformat(),
            window_end=end.isoformat(),
            days=days,
            schedules_checked=len(schedules),
            tasks_created=len(created_tasks),
            tasks_existing=tasks_existing,
            schedules_skipped=sum(skip_reasons.values()),
            skip_reasons=skip_reasons,
            warnings=warnings,
            created_tasks=created_tasks,
        )

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
