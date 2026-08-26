from backend.db.connection import connect

class SQLiteOpShopRepositoryMixin:
    """Opshop persistence responsibilities."""

    def list_opshop_locations(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_locations
                ORDER BY opshop_id
                """
            ).fetchall()
        return [self._row_to_opshop_location(row) for row in rows]

    def get_opshop_location(self, opshop_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_locations
                WHERE opshop_id = ?
                """,
                (opshop_id,),
            ).fetchone()
        return self._row_to_opshop_location(row) if row else None

    def upsert_opshop_location(self, location):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_locations (
                    opshop_id,
                    name,
                    suburb,
                    street_address,
                    area_region,
                    primary_contact,
                    primary_phone,
                    secondary_contact,
                    secondary_phone,
                    access_type,
                    key_required,
                    trailer_restriction,
                    status_notes,
                    is_active,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opshop_id)
                DO UPDATE SET
                    name = excluded.name,
                    suburb = excluded.suburb,
                    street_address = excluded.street_address,
                    area_region = excluded.area_region,
                    primary_contact = excluded.primary_contact,
                    primary_phone = excluded.primary_phone,
                    secondary_contact = excluded.secondary_contact,
                    secondary_phone = excluded.secondary_phone,
                    access_type = excluded.access_type,
                    key_required = excluded.key_required,
                    trailer_restriction = excluded.trailer_restriction,
                    status_notes = excluded.status_notes,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (
                    location.opshop_id,
                    location.name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    int(location.key_required),
                    location.trailer_restriction,
                    location.status_notes,
                    int(location.is_active),
                    location.created_at,
                    location.updated_at,
                ),
            )
            connection.commit()
        return self.get_opshop_location(location.opshop_id)

    def list_countryside_route_groups(self, include_inactive=False):
        where_clause = "" if include_inactive else "WHERE active_flag = 1 AND status = 'Active'"
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM opshop_countryside_route_groups
                {where_clause}
                ORDER BY display_order, lower(route_group_name), route_group_id
                """
            ).fetchall()
        return [self._row_to_countryside_route_group(row) for row in rows]

    def get_countryside_route_group(self, route_group_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_countryside_route_groups
                WHERE route_group_id = ?
                """,
                (route_group_id,),
            ).fetchone()
        return self._row_to_countryside_route_group(row) if row else None

    def find_countryside_route_group_by_name(self, route_group_name):
        normalized = _normalize_text_key(route_group_name)
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_countryside_route_groups
                WHERE lower(trim(route_group_name)) = ?
                """,
                (normalized,),
            ).fetchone()
        return self._row_to_countryside_route_group(row) if row else None

    def upsert_countryside_route_group(self, route_group):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_countryside_route_groups (
                    route_group_id,
                    route_group_name,
                    status,
                    active_flag,
                    display_order,
                    source_marker,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(route_group_id)
                DO UPDATE SET
                    route_group_name = excluded.route_group_name,
                    status = excluded.status,
                    active_flag = excluded.active_flag,
                    display_order = excluded.display_order,
                    source_marker = excluded.source_marker,
                    updated_at = excluded.updated_at
                """,
                (
                    route_group.route_group_id,
                    route_group.route_group_name,
                    route_group.status,
                    int(route_group.active_flag),
                    route_group.display_order,
                    route_group.source_marker,
                    route_group.created_at,
                    route_group.updated_at,
                ),
            )
            connection.commit()
        return self.get_countryside_route_group(route_group.route_group_id)

    def disable_countryside_route_group(self, route_group_id):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE opshop_countryside_route_groups
                SET status = 'On_Hold',
                    active_flag = 0,
                    updated_at = ?
                WHERE route_group_id = ?
                """,
                (self._timestamp(), route_group_id),
            )
            connection.commit()
        return self.get_countryside_route_group(route_group_id)

    def list_opshop_pickup_schedules(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_schedules
                ORDER BY schedule_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_schedule(row) for row in rows]

    def list_active_opshop_pickup_schedules(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_schedules
                WHERE active_flag = 1 AND status = 'Active'
                ORDER BY schedule_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_schedule(row) for row in rows]

    def list_scheduled_opshop_pickup_schedule_candidates(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    schedule.schedule_id,
                    schedule.opshop_id,
                    location.name AS opshop_name,
                    location.suburb,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    location.primary_phone,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name
                FROM opshop_pickup_schedules schedule
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                WHERE schedule.active_flag = 1
                    AND schedule.status = 'Active'
                    AND schedule.run_type = 'REGULAR'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'NORMAL'
                ORDER BY
                    COALESCE(location.name, ''),
                    COALESCE(location.suburb, ''),
                    schedule.run_day,
                    schedule.schedule_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_schedule_candidate(row) for row in rows]

    def list_oncall_opshop_pickup_schedule_candidates(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    schedule.schedule_id,
                    schedule.opshop_id,
                    location.name AS opshop_name,
                    location.suburb,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    location.primary_phone,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name
                FROM opshop_pickup_schedules schedule
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                WHERE schedule.active_flag = 1
                    AND schedule.status = 'Active'
                    AND schedule.run_type = 'ON_CALL'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'NORMAL'
                ORDER BY
                    COALESCE(schedule.run_day, 'ZZZ'),
                    COALESCE(location.name, ''),
                    COALESCE(location.suburb, ''),
                    schedule.schedule_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_schedule_candidate(row) for row in rows]

    def list_countryside_opshop_pickup_schedule_candidates(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    schedule.schedule_id,
                    schedule.opshop_id,
                    location.name AS opshop_name,
                    location.suburb,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    location.primary_phone,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name
                FROM opshop_pickup_schedules schedule
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                INNER JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                WHERE schedule.active_flag = 1
                    AND schedule.status = 'Active'
                    AND schedule.run_type = 'ON_CALL'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'COUNTRYSIDE'
                    AND route_group.active_flag = 1
                    AND route_group.status = 'Active'
                ORDER BY
                    route_group.display_order,
                    route_group.route_group_name,
                    COALESCE(location.name, ''),
                    COALESCE(location.suburb, ''),
                    schedule.schedule_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_schedule_candidate(row) for row in rows]

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        clauses = []
        parameters = []
        if run_type:
            clauses.append("schedule.run_type = ?")
            parameters.append(run_type)
        if not include_inactive:
            clauses.extend(["schedule.active_flag = 1", "schedule.status = 'Active'"])
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    schedule.*,
                    location.name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    location.key_required,
                    location.trailer_restriction,
                    location.status_notes,
                    route_group.route_group_name
                FROM opshop_pickup_schedules schedule
                INNER JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                {where_clause}
                ORDER BY
                    schedule.run_type,
                    location.name,
                    COALESCE(location.suburb, ''),
                    COALESCE(schedule.run_day, 'ZZZ'),
                    schedule.schedule_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_opshop_template(row) for row in rows]

    def get_opshop_pickup_schedule(self, schedule_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_schedules
                WHERE schedule_id = ?
                """,
                (schedule_id,),
            ).fetchone()
        return self._row_to_opshop_pickup_schedule(row) if row else None

    def upsert_opshop_pickup_schedule(self, schedule):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_pickup_schedules (
                    schedule_id,
                    opshop_id,
                    run_day,
                    run_type,
                    pickup_category,
                    route_group_id,
                    pickup_frequency,
                    time_window,
                    call_before_arrival,
                    call_timing,
                    status,
                    active_flag,
                    fortnight_group,
                    review_required,
                    review_reason,
                    default_driver_id,
                    default_driver_alias,
                    default_driver_name_snapshot,
                    regular_route_sequence,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id)
                DO UPDATE SET
                    opshop_id = excluded.opshop_id,
                    run_day = excluded.run_day,
                    run_type = excluded.run_type,
                    pickup_category = excluded.pickup_category,
                    route_group_id = excluded.route_group_id,
                    pickup_frequency = excluded.pickup_frequency,
                    time_window = excluded.time_window,
                    call_before_arrival = excluded.call_before_arrival,
                    call_timing = excluded.call_timing,
                    status = excluded.status,
                    active_flag = excluded.active_flag,
                    fortnight_group = excluded.fortnight_group,
                    review_required = excluded.review_required,
                    review_reason = excluded.review_reason,
                    default_driver_id = excluded.default_driver_id,
                    default_driver_alias = excluded.default_driver_alias,
                    default_driver_name_snapshot = excluded.default_driver_name_snapshot,
                    regular_route_sequence = excluded.regular_route_sequence,
                    updated_at = excluded.updated_at
                """,
                (
                    schedule.schedule_id,
                    schedule.opshop_id,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_category,
                    schedule.route_group_id,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    int(schedule.call_before_arrival),
                    schedule.call_timing,
                    schedule.status,
                    int(schedule.active_flag),
                    schedule.fortnight_group,
                    int(schedule.review_required),
                    schedule.review_reason,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot,
                    schedule.regular_route_sequence,
                    schedule.created_at,
                    schedule.updated_at,
                ),
            )
            connection.commit()
        return self.get_opshop_pickup_schedule(schedule.schedule_id)

    def list_opshop_pickup_tasks(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_tasks
                ORDER BY pickup_task_id
                """
            ).fetchall()
        return [self._row_to_opshop_pickup_task(row) for row in rows]

    def list_opshop_pickup_tasks_for_window(self, start_date, end_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_tasks
                WHERE pickup_date BETWEEN ? AND ?
                ORDER BY pickup_date, pickup_task_id
                """,
                (start_date, end_date),
            ).fetchall()
        return [self._row_to_opshop_pickup_task(row) for row in rows]

    def list_opshop_pickup_board_items_for_window(self, start_date, end_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    task.driver_id,
                    task.trip_no,
                    location.name AS opshop_name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    location.key_required,
                    location.trailer_restriction,
                    location.status_notes,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    schedule.call_before_arrival,
                    schedule.call_timing,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.pickup_date BETWEEN ? AND ?
                    AND task.status = 'ACTIVE'
                ORDER BY
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                (start_date, end_date),
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def list_scheduled_opshop_pickup_board_items_for_window(self, start_date, end_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    task.driver_id,
                    task.trip_no,
                    location.name AS opshop_name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    location.key_required,
                    location.trailer_restriction,
                    location.status_notes,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    schedule.call_before_arrival,
                    schedule.call_timing,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name,
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.pickup_date BETWEEN ? AND ?
                    AND task.status IN ('ACTIVE', 'ASSIGNED')
                    AND schedule.run_type = 'REGULAR'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'NORMAL'
                    AND schedule.active_flag = 1
                    AND schedule.status = 'Active'
                ORDER BY
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                (start_date, end_date),
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def list_oncall_opshop_pickup_board_items(self, start_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    task.driver_id,
                    task.trip_no,
                    location.name AS opshop_name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    location.key_required,
                    location.trailer_restriction,
                    location.status_notes,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    schedule.call_before_arrival,
                    schedule.call_timing,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name,
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.pickup_date >= ?
                    AND task.status IN ('ACTIVE', 'ASSIGNED')
                    AND task.generated_from = 'ON_CALL'
                    AND schedule.run_type = 'ON_CALL'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'NORMAL'
                    AND schedule.active_flag = 1
                    AND schedule.status = 'Active'
                ORDER BY
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                (start_date,),
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def list_countryside_opshop_pickup_board_items(self, dispatch_date=None):
        date_clause = "AND task.pickup_date >= ?" if dispatch_date else ""
        parameters = (dispatch_date,) if dispatch_date else ()
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    task.driver_id,
                    task.trip_no,
                    location.name AS opshop_name,
                    location.suburb,
                    location.street_address,
                    location.area_region,
                    location.primary_contact,
                    location.primary_phone,
                    location.secondary_contact,
                    location.secondary_phone,
                    location.access_type,
                    location.key_required,
                    location.trailer_restriction,
                    location.status_notes,
                    schedule.run_day,
                    schedule.run_type,
                    schedule.pickup_frequency,
                    schedule.time_window,
                    schedule.call_before_arrival,
                    schedule.call_timing,
                    schedule.default_driver_id,
                    schedule.default_driver_alias,
                    schedule.default_driver_name_snapshot AS default_driver_name,
                    schedule.regular_route_sequence,
                    COALESCE(schedule.pickup_category, 'NORMAL') AS pickup_category,
                    schedule.route_group_id,
                    route_group.route_group_name,
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                INNER JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.status IN ('ACTIVE', 'ASSIGNED')
                    AND task.generated_from = 'ON_CALL'
                    AND schedule.run_type = 'ON_CALL'
                    AND COALESCE(schedule.pickup_category, 'NORMAL') = 'COUNTRYSIDE'
                    AND route_group.active_flag = 1
                    AND route_group.status = 'Active'
                    {date_clause}
                ORDER BY
                    task.pickup_date,
                    route_group.display_order,
                    route_group.route_group_name,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def find_opshop_pickup_task_by_schedule_and_date(self, schedule_id, pickup_date):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_tasks
                WHERE schedule_id = ? AND pickup_date = ?
                ORDER BY pickup_task_id
                LIMIT 1
                """,
                (schedule_id, pickup_date),
            ).fetchone()
        return self._row_to_opshop_pickup_task(row) if row else None

    def get_opshop_pickup_task(self, pickup_task_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_tasks
                WHERE pickup_task_id = ?
                """,
                (pickup_task_id,),
            ).fetchone()
        return self._row_to_opshop_pickup_task(row) if row else None

    def insert_opshop_pickup_task(self, task):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_pickup_tasks (
                    pickup_task_id,
                    schedule_id,
                    opshop_id,
                    pickup_date,
                    task_type,
                    generated_from,
                    status,
                    dispatch_date,
                    driver_id,
                    trip_no,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.pickup_task_id,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.task_type,
                    task.generated_from,
                    task.status,
                    task.dispatch_date,
                    task.driver_id,
                    task.trip_no,
                    task.notes,
                    task.created_at,
                    task.updated_at,
                ),
            )
            connection.commit()
        return self.get_opshop_pickup_task(task.pickup_task_id)

    def upsert_opshop_pickup_task(self, task):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO opshop_pickup_tasks (
                    pickup_task_id,
                    schedule_id,
                    opshop_id,
                    pickup_date,
                    task_type,
                    generated_from,
                    status,
                    dispatch_date,
                    driver_id,
                    trip_no,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pickup_task_id)
                DO UPDATE SET
                    schedule_id = excluded.schedule_id,
                    opshop_id = excluded.opshop_id,
                    pickup_date = excluded.pickup_date,
                    task_type = excluded.task_type,
                    generated_from = excluded.generated_from,
                    status = excluded.status,
                    dispatch_date = excluded.dispatch_date,
                    driver_id = excluded.driver_id,
                    trip_no = excluded.trip_no,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    task.pickup_task_id,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    task.task_type,
                    task.generated_from,
                    task.status,
                    task.dispatch_date,
                    task.driver_id,
                    task.trip_no,
                    task.notes,
                    task.created_at,
                    task.updated_at,
                ),
            )
            connection.commit()
        return self.get_opshop_pickup_task(task.pickup_task_id)

    def update_opshop_pickup_task_assignment_status(
        self,
        pickup_task_id,
        status,
        driver_id=None,
        trip_no=None,
    ):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE opshop_pickup_tasks
                SET status = ?,
                    driver_id = ?,
                    trip_no = ?,
                    updated_at = ?
                WHERE pickup_task_id = ?
                """,
                (status, driver_id, trip_no, self._timestamp(), pickup_task_id),
            )
            connection.commit()
        return self.get_opshop_pickup_task(pickup_task_id)


def _normalize_text_key(value):
    return " ".join(str(value or "").strip().lower().split())
