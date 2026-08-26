from backend.schemas import (
    OpShopPickupBoardItem,
    OpShopPickupScheduleCandidate,
    OpShopTemplate,
)

class InMemoryOpShopRepositoryMixin:
    """Opshop in-memory responsibilities."""

    def list_opshop_locations(self):
        return sorted(self.opshop_locations, key=lambda location: location.opshop_id)

    def get_opshop_location(self, opshop_id):
        return next(
            (
                location
                for location in self.opshop_locations
                if location.opshop_id == opshop_id
            ),
            None,
        )

    def upsert_opshop_location(self, location):
        for index, existing in enumerate(self.opshop_locations):
            if existing.opshop_id == location.opshop_id:
                self.opshop_locations[index] = location
                return location
        self.opshop_locations.append(location)
        return location

    def list_countryside_route_groups(self, include_inactive=False):
        groups = [
            group
            for group in self.opshop_countryside_route_groups
            if include_inactive or (group.active_flag and group.status == "Active")
        ]
        return sorted(
            groups,
            key=lambda group: (
                group.display_order,
                group.route_group_name.lower(),
                group.route_group_id,
            ),
        )

    def get_countryside_route_group(self, route_group_id):
        return next(
            (
                group
                for group in self.opshop_countryside_route_groups
                if group.route_group_id == route_group_id
            ),
            None,
        )

    def find_countryside_route_group_by_name(self, route_group_name):
        normalized = _normalize_text_key(route_group_name)
        return next(
            (
                group
                for group in self.opshop_countryside_route_groups
                if _normalize_text_key(group.route_group_name) == normalized
            ),
            None,
        )

    def upsert_countryside_route_group(self, route_group):
        for index, existing in enumerate(self.opshop_countryside_route_groups):
            if existing.route_group_id == route_group.route_group_id:
                self.opshop_countryside_route_groups[index] = route_group
                return route_group
        self.opshop_countryside_route_groups.append(route_group)
        return route_group

    def disable_countryside_route_group(self, route_group_id):
        group = self.get_countryside_route_group(route_group_id)
        if not group:
            return None
        group.status = "On_Hold"
        group.active_flag = False
        return group

    def list_opshop_pickup_schedules(self):
        return sorted(
            self.opshop_pickup_schedules,
            key=lambda schedule: schedule.schedule_id,
        )

    def list_active_opshop_pickup_schedules(self):
        return [
            schedule
            for schedule in self.list_opshop_pickup_schedules()
            if schedule.active_flag and schedule.status == "Active"
        ]

    def list_scheduled_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "REGULAR"
                and schedule.pickup_category == "NORMAL"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=None,
                    regular_route_sequence=schedule.regular_route_sequence,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.run_day or "",
                candidate.schedule_id,
            ),
        )

    def list_oncall_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "ON_CALL"
                and schedule.pickup_category == "NORMAL"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=None,
                    regular_route_sequence=schedule.regular_route_sequence,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.run_day or "ZZZ",
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.schedule_id,
            ),
        )

    def list_countryside_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "ON_CALL"
                and schedule.pickup_category == "COUNTRYSIDE"
            ):
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            if not route_group or not route_group.active_flag or route_group.status != "Active":
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=route_group.route_group_name,
                    regular_route_sequence=schedule.regular_route_sequence,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.route_group_name or "",
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.schedule_id,
            ),
        )

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        templates = []
        for schedule in self.list_opshop_pickup_schedules():
            if run_type and schedule.run_type != run_type:
                continue
            if not include_inactive and not (
                schedule.active_flag and schedule.status == "Active"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            if not location:
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            templates.append(
                OpShopTemplate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    run_type=schedule.run_type,
                    run_day=schedule.run_day,
                    name=location.name,
                    suburb=location.suburb,
                    street_address=location.street_address,
                    area_region=location.area_region,
                    primary_contact=location.primary_contact,
                    primary_phone=location.primary_phone,
                    secondary_contact=location.secondary_contact,
                    secondary_phone=location.secondary_phone,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    call_before_arrival=schedule.call_before_arrival,
                    call_timing=schedule.call_timing,
                    access_type=location.access_type,
                    key_required=location.key_required,
                    trailer_restriction=location.trailer_restriction,
                    status_notes=location.status_notes,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    status=schedule.status,
                    active_flag=schedule.active_flag,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=route_group.route_group_name if route_group else None,
                    regular_route_sequence=schedule.regular_route_sequence,
                )
            )
        return sorted(
            templates,
            key=lambda template: (
                template.run_type,
                template.name,
                template.suburb or "",
                template.run_day or "ZZZ",
                template.schedule_id,
            ),
        )

    def get_opshop_pickup_schedule(self, schedule_id):
        return next(
            (
                schedule
                for schedule in self.opshop_pickup_schedules
                if schedule.schedule_id == schedule_id
            ),
            None,
        )

    def upsert_opshop_pickup_schedule(self, schedule):
        for index, existing in enumerate(self.opshop_pickup_schedules):
            if existing.schedule_id == schedule.schedule_id:
                self.opshop_pickup_schedules[index] = schedule
                return schedule
        self.opshop_pickup_schedules.append(schedule)
        return schedule

    def list_opshop_pickup_tasks(self):
        return sorted(
            self.opshop_pickup_tasks,
            key=lambda task: task.pickup_task_id,
        )

    def list_opshop_pickup_tasks_for_window(self, start_date, end_date):
        return sorted(
            [
                task
                for task in self.opshop_pickup_tasks
                if start_date <= task.pickup_date <= end_date
            ],
            key=lambda task: (task.pickup_date, task.pickup_task_id),
        )

    def list_opshop_pickup_board_items_for_window(self, start_date, end_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status != "ACTIVE":
                continue
            if not (start_date <= task.pickup_date <= end_date):
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_scheduled_opshop_pickup_board_items_for_window(self, start_date, end_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if not (start_date <= task.pickup_date <= end_date):
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "REGULAR":
                continue
            if schedule.pickup_category != "NORMAL":
                continue
            if not schedule.active_flag or schedule.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_oncall_opshop_pickup_board_items(self, start_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if task.pickup_date < start_date:
                continue
            if task.generated_from != "ON_CALL":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL":
                continue
            if schedule.pickup_category != "NORMAL":
                continue
            if not schedule.active_flag or schedule.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_countryside_opshop_pickup_board_items(self, dispatch_date=None):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if dispatch_date and task.pickup_date < dispatch_date:
                continue
            if task.generated_from != "ON_CALL":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL":
                continue
            if schedule.pickup_category != "COUNTRYSIDE":
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            if not route_group or not route_group.active_flag or route_group.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.route_group_name or "",
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def find_opshop_pickup_task_by_schedule_and_date(self, schedule_id, pickup_date):
        return next(
            (
                task
                for task in self.opshop_pickup_tasks
                if task.schedule_id == schedule_id and task.pickup_date == pickup_date
            ),
            None,
        )

    def get_opshop_pickup_task(self, pickup_task_id):
        return next(
            (
                task
                for task in self.opshop_pickup_tasks
                if task.pickup_task_id == pickup_task_id
            ),
            None,
        )

    def insert_opshop_pickup_task(self, task):
        if self.get_opshop_pickup_task(task.pickup_task_id):
            raise ValueError(f"OP SHOP pickup task already exists: {task.pickup_task_id}")
        self.opshop_pickup_tasks.append(task)
        return task

    def upsert_opshop_pickup_task(self, task):
        for index, existing in enumerate(self.opshop_pickup_tasks):
            if existing.pickup_task_id == task.pickup_task_id:
                self.opshop_pickup_tasks[index] = task
                return task
        self.opshop_pickup_tasks.append(task)
        return task

    def update_opshop_pickup_task_assignment_status(
        self,
        pickup_task_id,
        status,
        driver_id=None,
        trip_no=None,
    ):
        task = self.get_opshop_pickup_task(pickup_task_id)
        if not task:
            return None
        same_scope = (
            status == "ASSIGNED"
            and task.status == "ASSIGNED"
            and task.driver_id == driver_id
        )
        if not same_scope:
            task.trip_sequence = None
        task.status = status
        task.driver_id = driver_id
        task.trip_no = trip_no
        task.updated_at = "2026-05-19T00:00:00+00:00"
        return task

    def _opshop_pickup_board_item(self, task, schedule, location):
        return OpShopPickupBoardItem(
            pickup_task_id=task.pickup_task_id,
            task_type=task.task_type,
            schedule_id=task.schedule_id,
            opshop_id=task.opshop_id,
            opshop_name=location.name if location else "",
            suburb=location.suburb if location else None,
            street_address=location.street_address if location else None,
            area_region=location.area_region if location else None,
            pickup_date=task.pickup_date,
            dispatch_date=task.dispatch_date,
            run_day=schedule.run_day if schedule else None,
            run_type=schedule.run_type if schedule else None,
            pickup_frequency=schedule.pickup_frequency if schedule else None,
            time_window=schedule.time_window if schedule else None,
            call_before_arrival=schedule.call_before_arrival if schedule else False,
            call_timing=schedule.call_timing if schedule else None,
            primary_contact=location.primary_contact if location else None,
            primary_phone=location.primary_phone if location else None,
            secondary_contact=location.secondary_contact if location else None,
            secondary_phone=location.secondary_phone if location else None,
            access_type=location.access_type if location else None,
            key_required=location.key_required if location else False,
            trailer_restriction=location.trailer_restriction if location else None,
            status=task.status,
            generated_from=task.generated_from,
            status_notes=location.status_notes if location else None,
            task_notes=task.notes,
            driver_id=task.driver_id,
            trip_no=task.trip_no,
            is_assigned=bool(task.driver_id or task.trip_no),
            default_driver_id=schedule.default_driver_id if schedule else None,
            default_driver_alias=schedule.default_driver_alias if schedule else None,
            default_driver_name=schedule.default_driver_name_snapshot if schedule else None,
            assigned_driver_id=task.driver_id,
            assigned_driver_name=self.get_driver(task.driver_id).name if task.driver_id and self.get_driver(task.driver_id) else None,
            pickup_category=schedule.pickup_category if schedule else "NORMAL",
            route_group_id=schedule.route_group_id if schedule else None,
            route_group_name=self.get_countryside_route_group(schedule.route_group_id).route_group_name if schedule and schedule.route_group_id and self.get_countryside_route_group(schedule.route_group_id) else None,
            regular_route_sequence=(
                schedule.regular_route_sequence if schedule else None
            ),
            trip_sequence=task.trip_sequence,
        )


def _normalize_text_key(value):
    return " ".join(str(value or "").strip().lower().split())
