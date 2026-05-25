import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from backend.schemas import OpShopLocation, OpShopPickupSchedule
from backend.services.manual_dispatch.normalization import (
    bool_or_default,
    clean_optional_text,
    clean_required_text,
)


VALID_RUN_TYPES = {"REGULAR", "ON_CALL"}
VALID_RUN_DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"}


class OpShopTemplateService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        normalized_type = _normalize_run_type(run_type) if run_type else None
        return self.repository.list_opshop_templates(
            normalized_type,
            bool(include_inactive),
        )

    def create_opshop_template(self, request):
        values = self._values_from_request(request)
        return self._upsert_active_template(values)

    def update_opshop_template(self, schedule_id, request):
        existing_schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        if not existing_schedule:
            raise ValueError(f"OP SHOP template does not exist: {schedule_id}")
        existing_location = self.repository.get_opshop_location(existing_schedule.opshop_id)
        if not existing_location:
            raise ValueError(f"OP SHOP location does not exist: {existing_schedule.opshop_id}")

        values = self._values_from_request(
            request,
            existing_schedule=existing_schedule,
            existing_location=existing_location,
        )
        template = self._upsert_active_template(values)
        if template.schedule_id != existing_schedule.schedule_id:
            self._disable_schedule(existing_schedule)
        return template

    def disable_opshop_template(self, schedule_id):
        schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"OP SHOP template does not exist: {schedule_id}")
        self._disable_schedule(schedule)
        return self._get_template(schedule_id, include_inactive=True)

    def _upsert_active_template(self, values):
        now = _timestamp()
        existing_location = self._find_location(values)
        opshop_id = (
            existing_location.opshop_id
            if existing_location
            else _deterministic_id("OPSHOP", _location_key(values))
        )
        location = OpShopLocation(
            opshop_id=opshop_id,
            name=values["name"],
            suburb=values["suburb"],
            street_address=values["street_address"],
            area_region=values["area_region"],
            primary_contact=values["primary_contact"],
            primary_phone=values["primary_phone"],
            secondary_contact=values["secondary_contact"],
            secondary_phone=values["secondary_phone"],
            access_type=values["access_type"],
            key_required=values["key_required"],
            trailer_restriction=values["trailer_restriction"],
            status_notes=values["status_notes"],
            is_active=True,
            created_at=existing_location.created_at if existing_location else now,
            updated_at=now,
        )
        self.repository.upsert_opshop_location(location)

        driver_id, driver_name = self._validated_driver(values["default_driver_id"])
        schedule_values = {
            **values,
            "opshop_id": opshop_id,
        }
        existing_schedule = self._find_schedule(schedule_values)
        schedule_id = (
            existing_schedule.schedule_id
            if existing_schedule
            else _deterministic_id("OPSHOP-SCHEDULE", _schedule_key(schedule_values))
        )
        schedule = OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id=opshop_id,
            run_day=values["run_day"],
            run_type=values["run_type"],
            pickup_frequency=values["pickup_frequency"],
            time_window=values["time_window"],
            call_before_arrival=values["call_before_arrival"],
            call_timing=values["call_timing"],
            status="Active",
            active_flag=True,
            fortnight_group=existing_schedule.fortnight_group if existing_schedule else None,
            review_required=False,
            review_reason=None,
            created_at=existing_schedule.created_at if existing_schedule else now,
            updated_at=now,
            default_driver_id=driver_id,
            default_driver_alias=None,
            default_driver_name_snapshot=driver_name,
        )
        self.repository.upsert_opshop_pickup_schedule(schedule)
        return self._get_template(schedule.schedule_id)

    def _values_from_request(self, request, existing_schedule=None, existing_location=None):
        def from_request(field, existing_value=None):
            value = getattr(request, field, None)
            return existing_value if value is None and existing_schedule else value

        run_type = _normalize_run_type(
            from_request("run_type", existing_schedule.run_type if existing_schedule else None)
        )
        run_day = _normalize_run_day(
            from_request("run_day", existing_schedule.run_day if existing_schedule else None)
        )
        if run_type == "REGULAR" and run_day not in VALID_RUN_DAYS:
            raise ValueError("REGULAR template requires run_day Monday-Friday")
        if run_day and run_day not in VALID_RUN_DAYS:
            raise ValueError("run_day must be Monday-Friday or blank for ON_CALL")

        return {
            "run_type": run_type,
            "run_day": run_day,
            "name": clean_required_text(
                from_request("name", existing_location.name if existing_location else None),
                "name",
            ),
            "suburb": clean_optional_text(from_request("suburb", existing_location.suburb if existing_location else None)),
            "street_address": clean_optional_text(from_request("street_address", existing_location.street_address if existing_location else None)),
            "area_region": clean_optional_text(from_request("area_region", existing_location.area_region if existing_location else None)),
            "primary_contact": clean_optional_text(from_request("primary_contact", existing_location.primary_contact if existing_location else None)),
            "primary_phone": clean_optional_text(from_request("primary_phone", existing_location.primary_phone if existing_location else None)),
            "secondary_contact": clean_optional_text(from_request("secondary_contact", existing_location.secondary_contact if existing_location else None)),
            "secondary_phone": clean_optional_text(from_request("secondary_phone", existing_location.secondary_phone if existing_location else None)),
            "pickup_frequency": clean_optional_text(from_request("pickup_frequency", existing_schedule.pickup_frequency if existing_schedule else None)),
            "time_window": clean_optional_text(from_request("time_window", existing_schedule.time_window if existing_schedule else None)),
            "call_before_arrival": bool_or_default(
                from_request("call_before_arrival", existing_schedule.call_before_arrival if existing_schedule else False),
                False,
            ),
            "call_timing": clean_optional_text(from_request("call_timing", existing_schedule.call_timing if existing_schedule else None)),
            "access_type": clean_optional_text(from_request("access_type", existing_location.access_type if existing_location else None)),
            "key_required": bool_or_default(
                from_request("key_required", existing_location.key_required if existing_location else False),
                False,
            ),
            "trailer_restriction": clean_optional_text(from_request("trailer_restriction", existing_location.trailer_restriction if existing_location else None)),
            "status_notes": clean_optional_text(from_request("status_notes", existing_location.status_notes if existing_location else None)),
            "default_driver_id": clean_optional_text(from_request("default_driver_id", existing_schedule.default_driver_id if existing_schedule else None)),
        }

    def _validated_driver(self, driver_id):
        if not driver_id:
            return None, None
        self.validator.validate_driver_exists(driver_id)
        return driver_id, self.repository.get_driver(driver_id).name

    def _find_location(self, values):
        key = _location_key(values)
        return next(
            (
                location
                for location in self.repository.list_opshop_locations()
                if _location_key(
                    {
                        "name": location.name,
                        "suburb": location.suburb,
                        "street_address": location.street_address,
                    }
                )
                == key
            ),
            None,
        )

    def _find_schedule(self, values):
        key = _schedule_key(values)
        return next(
            (
                schedule
                for schedule in self.repository.list_opshop_pickup_schedules()
                if _schedule_key(
                    {
                        "opshop_id": schedule.opshop_id,
                        "run_day": schedule.run_day,
                        "run_type": schedule.run_type,
                        "pickup_frequency": schedule.pickup_frequency,
                        "time_window": schedule.time_window,
                    }
                )
                == key
            ),
            None,
        )

    def _disable_schedule(self, schedule):
        self.repository.upsert_opshop_pickup_schedule(
            replace(
                schedule,
                status="On_Hold",
                active_flag=False,
                updated_at=_timestamp(),
            )
        )

    def _get_template(self, schedule_id, include_inactive=False):
        template = next(
            (
                item
                for item in self.repository.list_opshop_templates(
                    include_inactive=include_inactive
                )
                if item.schedule_id == schedule_id
            ),
            None,
        )
        if not template:
            raise ValueError(f"OP SHOP template does not exist: {schedule_id}")
        return template


def _normalize_run_type(value):
    normalized = clean_required_text(value, "run_type").upper().replace("-", "_").replace(" ", "_")
    if normalized not in VALID_RUN_TYPES:
        raise ValueError("run_type must be REGULAR or ON_CALL")
    return normalized


def _normalize_run_day(value):
    text = clean_optional_text(value)
    return text.upper() if text else None


def _normalize_key(value):
    return " ".join(str(value or "").strip().lower().replace("-", "_").split())


def _location_key(values):
    return "|".join(
        [
            _normalize_key(values.get("name")),
            _normalize_key(values.get("suburb")),
            _normalize_key(values.get("street_address")),
        ]
    )


def _schedule_key(values):
    return "|".join(
        [
            values["opshop_id"],
            values.get("run_day") or "",
            values["run_type"],
            _normalize_key(values.get("pickup_frequency")),
            _normalize_key(values.get("time_window")),
        ]
    )


def _deterministic_id(prefix, key):
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
