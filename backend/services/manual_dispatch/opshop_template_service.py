import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from backend.schemas import (
    CreateOpShopTemplateRequest,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupSchedule,
)
from backend.services.manual_dispatch.normalization import (
    bool_or_default,
    clean_optional_text,
    clean_required_text,
    quantity_or_default,
)


VALID_RUN_TYPES = {"REGULAR", "ON_CALL"}
VALID_RUN_DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"}
VALID_PICKUP_CATEGORIES = {"NORMAL", "COUNTRYSIDE"}


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

    def list_countryside_route_groups(self, include_inactive=False):
        return self.repository.list_countryside_route_groups(bool(include_inactive))

    def create_countryside_route_group(self, request):
        name = clean_required_text(getattr(request, "route_group_name", None), "route_group_name")
        existing = self.repository.find_countryside_route_group_by_name(name)
        now = _timestamp()
        display_order = getattr(request, "display_order", None)
        if display_order is None:
            display_order = existing.display_order if existing else 0
        route_group = OpShopCountrysideRouteGroup(
            route_group_id=existing.route_group_id
            if existing
            else _deterministic_id("OPSHOP-COUNTRYSIDE-GROUP", _normalize_key(name)),
            route_group_name=name,
            status="Active",
            active_flag=True,
            display_order=quantity_or_default(display_order, "display_order"),
            source_marker=clean_optional_text(
                getattr(request, "source_marker", None)
                if getattr(request, "source_marker", None) is not None
                else (existing.source_marker if existing else None)
            ),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        return self.repository.upsert_countryside_route_group(route_group)

    def update_countryside_route_group(self, route_group_id, request):
        existing = self.repository.get_countryside_route_group(route_group_id)
        if not existing:
            raise ValueError(f"Countryside route group does not exist: {route_group_id}")
        fields = request.model_fields_set
        name = (
            clean_required_text(request.route_group_name, "route_group_name")
            if "route_group_name" in fields
            else existing.route_group_name
        )
        status = (
            clean_required_text(request.status, "status")
            if "status" in fields
            else existing.status
        )
        if status not in {"Active", "On_Hold"}:
            raise ValueError("route group status must be Active or On_Hold")
        active_flag = existing.active_flag
        if "active_flag" in fields:
            if request.active_flag is None:
                raise ValueError("active_flag cannot be null")
            active_flag = request.active_flag
        display_order = existing.display_order
        if "display_order" in fields:
            if request.display_order is None:
                raise ValueError("display_order cannot be null")
            display_order = quantity_or_default(request.display_order, "display_order")
        route_group = OpShopCountrysideRouteGroup(
            route_group_id=existing.route_group_id,
            route_group_name=name,
            status=status,
            active_flag=bool(active_flag),
            display_order=display_order,
            source_marker=(
                clean_optional_text(request.source_marker)
                if "source_marker" in fields
                else existing.source_marker
            ),
            created_at=existing.created_at,
            updated_at=_timestamp(),
        )
        return self.repository.upsert_countryside_route_group(route_group)

    def disable_countryside_route_group(self, route_group_id):
        existing = self.repository.get_countryside_route_group(route_group_id)
        if not existing:
            raise ValueError(f"Countryside route group does not exist: {route_group_id}")
        active_schedule_ids = {
            schedule.schedule_id
            for schedule in self.repository.list_opshop_pickup_schedules()
            if schedule.route_group_id == route_group_id
            and schedule.pickup_category == "COUNTRYSIDE"
        }
        for task in self.repository.list_opshop_pickup_tasks():
            if task.schedule_id in active_schedule_ids and task.status in {"ACTIVE", "ASSIGNED"}:
                raise ValueError(
                    "This route group has active pickup tasks. Cancel or complete them before disabling this route group."
                )
        return self.repository.disable_countryside_route_group(route_group_id)

    def list_countryside_route_memberships(self, route_group_id):
        route_group = self._active_route_group(route_group_id)
        return [
            template
            for template in self.repository.list_opshop_templates(
                "ON_CALL",
                include_inactive=False,
            )
            if template.pickup_category == "COUNTRYSIDE"
            and template.route_group_id == route_group.route_group_id
        ]

    def add_countryside_route_membership(self, route_group_id, request):
        route_group = self._active_route_group(route_group_id)
        payload = CreateOpShopTemplateRequest(
            run_type="ON_CALL",
            pickup_category="COUNTRYSIDE",
            route_group_id=route_group.route_group_id,
            name=getattr(request, "name", None),
            suburb=getattr(request, "suburb", None),
            street_address=getattr(request, "street_address", None),
            area_region=getattr(request, "area_region", None),
            primary_contact=getattr(request, "primary_contact", None),
            primary_phone=getattr(request, "primary_phone", None),
            secondary_contact=getattr(request, "secondary_contact", None),
            secondary_phone=getattr(request, "secondary_phone", None),
            pickup_frequency=getattr(request, "pickup_frequency", None) or "On Call",
            time_window=getattr(request, "time_window", None),
            call_before_arrival=getattr(request, "call_before_arrival", None),
            call_timing=getattr(request, "call_timing", None),
            access_type=getattr(request, "access_type", None),
            key_required=getattr(request, "key_required", None),
            trailer_restriction=getattr(request, "trailer_restriction", None),
            status_notes=getattr(request, "status_notes", None),
            default_driver_id=getattr(request, "default_driver_id", None),
        )
        return self.create_opshop_template(payload)

    def remove_countryside_route_membership(self, schedule_id):
        schedule = self._countryside_schedule(schedule_id)
        if self._has_active_pickup_tasks(schedule.schedule_id):
            raise ValueError(
                "This route template has active pickup tasks. Cancel or complete them before removing it from the route."
            )
        self._disable_schedule(schedule)
        return self._get_template(schedule.schedule_id, include_inactive=True)

    def move_countryside_route_membership(self, schedule_id, request):
        schedule = self._countryside_schedule(schedule_id)
        target_route_group = self._active_route_group(
            getattr(request, "target_route_group_id", None)
        )
        if schedule.route_group_id == target_route_group.route_group_id:
            raise ValueError("Target route group is already selected for this template")

        location = self.repository.get_opshop_location(schedule.opshop_id)
        if not location:
            raise ValueError(f"OP SHOP location does not exist: {schedule.opshop_id}")

        payload = CreateOpShopTemplateRequest(
            run_type="ON_CALL",
            pickup_category="COUNTRYSIDE",
            route_group_id=target_route_group.route_group_id,
            name=location.name,
            suburb=location.suburb,
            street_address=location.street_address,
            area_region=location.area_region,
            primary_contact=location.primary_contact,
            primary_phone=location.primary_phone,
            secondary_contact=location.secondary_contact,
            secondary_phone=location.secondary_phone,
            pickup_frequency=schedule.pickup_frequency or "On Call",
            time_window=schedule.time_window,
            call_before_arrival=schedule.call_before_arrival,
            call_timing=schedule.call_timing,
            access_type=location.access_type,
            key_required=location.key_required,
            trailer_restriction=location.trailer_restriction,
            status_notes=location.status_notes,
            default_driver_id=schedule.default_driver_id,
        )
        moved = self.create_opshop_template(payload)
        if moved.schedule_id != schedule.schedule_id:
            self._disable_schedule(schedule)
        return moved

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
            pickup_category=values["pickup_category"],
            route_group_id=values["route_group_id"],
            regular_route_sequence=(
                existing_schedule.regular_route_sequence
                if existing_schedule
                else None
            ),
        )
        self.repository.upsert_opshop_pickup_schedule(schedule)
        return self._get_template(schedule.schedule_id)

    def _values_from_request(self, request, existing_schedule=None, existing_location=None):
        fields = getattr(request, "model_fields_set", set())

        def from_request(field, existing_value=None):
            value = getattr(request, field, None)
            return existing_value if existing_schedule and field not in fields else value

        if existing_schedule:
            for field in (
                "run_type",
                "name",
                "pickup_category",
                "call_before_arrival",
                "key_required",
            ):
                if field in fields and getattr(request, field) is None:
                    raise ValueError(f"{field} cannot be null")

        run_type = _normalize_run_type(
            from_request("run_type", existing_schedule.run_type if existing_schedule else None)
        )
        run_day = _normalize_run_day(
            from_request("run_day", existing_schedule.run_day if existing_schedule else None)
        )
        pickup_category = _normalize_pickup_category(
            from_request(
                "pickup_category",
                existing_schedule.pickup_category if existing_schedule else "NORMAL",
            )
        )
        route_group_id = clean_optional_text(
            from_request(
                "route_group_id",
                existing_schedule.route_group_id if existing_schedule else None,
            )
        )
        if run_type == "REGULAR" and run_day not in VALID_RUN_DAYS:
            raise ValueError("REGULAR template requires run_day Monday-Friday")
        if run_day and run_day not in VALID_RUN_DAYS:
            raise ValueError("run_day must be Monday-Friday or blank for ON_CALL")
        if run_type == "REGULAR" and pickup_category == "COUNTRYSIDE":
            raise ValueError("REGULAR templates cannot use COUNTRYSIDE pickup_category")
        if pickup_category == "COUNTRYSIDE":
            if run_type != "ON_CALL":
                raise ValueError("COUNTRYSIDE templates must use ON_CALL run_type")
            if not route_group_id:
                raise ValueError("COUNTRYSIDE templates require route_group_id")
            route_group = self.repository.get_countryside_route_group(route_group_id)
            if not route_group or not route_group.active_flag or route_group.status != "Active":
                raise ValueError("COUNTRYSIDE templates require an active route group")
        else:
            route_group_id = None

        return {
            "run_type": run_type,
            "run_day": run_day,
            "pickup_category": pickup_category,
            "route_group_id": route_group_id,
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
                        "pickup_category": schedule.pickup_category,
                        "route_group_id": schedule.route_group_id,
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

    def _active_route_group(self, route_group_id):
        route_group_id = clean_required_text(route_group_id, "route_group_id")
        route_group = self.repository.get_countryside_route_group(route_group_id)
        if not route_group:
            raise ValueError(f"Countryside route group does not exist: {route_group_id}")
        if not route_group.active_flag or route_group.status != "Active":
            raise ValueError("Countryside route group must be active")
        return route_group

    def _countryside_schedule(self, schedule_id):
        schedule_id = clean_required_text(schedule_id, "schedule_id")
        schedule = self.repository.get_opshop_pickup_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Countryside route template does not exist: {schedule_id}")
        if schedule.run_type != "ON_CALL" or schedule.pickup_category != "COUNTRYSIDE":
            raise ValueError("Only Countryside ON_CALL route templates can be managed here")
        return schedule

    def _has_active_pickup_tasks(self, schedule_id):
        return any(
            task.schedule_id == schedule_id and task.status in {"ACTIVE", "ASSIGNED"}
            for task in self.repository.list_opshop_pickup_tasks()
        )


def _normalize_run_type(value):
    normalized = clean_required_text(value, "run_type").upper().replace("-", "_").replace(" ", "_")
    if normalized not in VALID_RUN_TYPES:
        raise ValueError("run_type must be REGULAR or ON_CALL")
    return normalized


def _normalize_run_day(value):
    text = clean_optional_text(value)
    return text.upper() if text else None


def _normalize_pickup_category(value):
    normalized = clean_optional_text(value)
    normalized = normalized.upper().replace("-", "_").replace(" ", "_") if normalized else "NORMAL"
    if normalized not in VALID_PICKUP_CATEGORIES:
        raise ValueError("pickup_category must be NORMAL or COUNTRYSIDE")
    return normalized


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
    parts = [
        values["opshop_id"],
        values.get("run_day") or "",
        values["run_type"],
        _normalize_key(values.get("pickup_frequency")),
        _normalize_key(values.get("time_window")),
    ]
    if values.get("pickup_category") == "COUNTRYSIDE":
        parts.extend(["COUNTRYSIDE", values.get("route_group_id") or ""])
    return "|".join(parts)


def _deterministic_id(prefix, key):
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
