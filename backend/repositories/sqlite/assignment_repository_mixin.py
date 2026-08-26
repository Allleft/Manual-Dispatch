from backend.db.connection import connect
from backend.schemas import (
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
)

class SQLiteAssignmentRepositoryMixin:
    """Assignment persistence responsibilities."""

    def list_assignments(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE dispatch_date = ?
                    AND (
                        (
                            task_type = 'ORDER'
                            AND EXISTS (
                                SELECT 1
                                FROM manual_orders
                                WHERE manual_orders.order_id = manual_dispatch_assignments.task_id
                                    AND manual_orders.status = 'ACTIVE'
                            )
                        )
                        OR (
                            task_type = 'OPSHOP_PICKUP'
                            AND EXISTS (
                                SELECT 1
                                FROM opshop_pickup_tasks
                                WHERE opshop_pickup_tasks.pickup_task_id = manual_dispatch_assignments.task_id
                                    AND opshop_pickup_tasks.status = 'ASSIGNED'
                            )
                        )
                    )
                ORDER BY assignment_id
                """,
                (dispatch_date,),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_delivery_order_assignments_for_delivery_date(self, delivery_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT assignment.*
                FROM manual_dispatch_assignments AS assignment
                JOIN manual_orders AS manual_order
                    ON manual_order.order_id = assignment.task_id
                WHERE assignment.task_type = 'ORDER'
                    AND manual_order.status = 'ACTIVE'
                    AND manual_order.delivery_date = ?
                ORDER BY assignment.assignment_id
                """,
                (delivery_date,),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_assigned_opshop_pickup_board_items(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    assignment.dispatch_date AS dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    assignment.driver_id AS driver_id,
                    assignment.trip_no AS trip_no,
                    task.trip_sequence,
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
                FROM manual_dispatch_assignments assignment
                JOIN opshop_pickup_tasks task
                    ON task.pickup_task_id = assignment.task_id
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = assignment.driver_id
                WHERE assignment.dispatch_date = ?
                    AND assignment.task_type = 'OPSHOP_PICKUP'
                    AND task.status = 'ASSIGNED'
                ORDER BY
                    assignment.driver_id,
                    assignment.trip_no,
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                (dispatch_date,),
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

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
        clauses = [
            "task.pickup_date = ?",
            "assignment.task_type = 'OPSHOP_PICKUP'",
            "task.status = 'ASSIGNED'",
        ]
        parameters = [pickup_date]
        if dispatch_date:
            clauses.append("assignment.dispatch_date = ?")
            parameters.append(dispatch_date)
        where_clause = " AND ".join(clauses)
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    task.pickup_task_id,
                    task.task_type,
                    task.schedule_id,
                    task.opshop_id,
                    task.pickup_date,
                    assignment.dispatch_date AS dispatch_date,
                    task.status,
                    task.generated_from,
                    task.notes AS task_notes,
                    assignment.driver_id AS driver_id,
                    assignment.trip_no AS trip_no,
                    task.trip_sequence,
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
                FROM manual_dispatch_assignments assignment
                JOIN opshop_pickup_tasks task
                    ON task.pickup_task_id = assignment.task_id
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN opshop_countryside_route_groups route_group
                    ON route_group.route_group_id = schedule.route_group_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = assignment.driver_id
                WHERE {where_clause}
                ORDER BY
                    assignment.driver_id,
                    assignment.trip_no,
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def list_collectable_opshop_pickup_board_items(
        self,
        pickup_date,
        driver_id,
        dispatch_date=None,
    ):
        assignment_dispatch_clause = (
            "AND assignment.dispatch_date = ?"
            if dispatch_date
            else ""
        )
        parameters = [pickup_date, driver_id]
        if dispatch_date:
            parameters.append(dispatch_date)
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
                    task.trip_sequence,
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
                WHERE task.task_type = 'OPSHOP_PICKUP'
                    AND task.pickup_date = ?
                    AND task.status = 'ASSIGNED'
                    AND task.driver_id = ?
                    AND EXISTS (
                        SELECT 1
                        FROM manual_dispatch_assignments assignment
                        WHERE assignment.task_type = 'OPSHOP_PICKUP'
                            AND assignment.task_id = task.pickup_task_id
                            AND assignment.driver_id = task.driver_id
                            {assignment_dispatch_clause}
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM opshop_pickup_collection_rows collection_row
                        JOIN opshop_pickup_collections collection
                            ON collection.collection_id = collection_row.collection_id
                        WHERE collection_row.pickup_task_id_snapshot = task.pickup_task_id
                            AND collection.status IN ('GENERATED', 'SAVED')
                    )
                ORDER BY
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_opshop_pickup_board_item(row) for row in rows]

    def list_driver_vehicle_assignments(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_driver_vehicle_assignments
                WHERE dispatch_date = ?
                ORDER BY driver_id, delivery_date
                """,
                (dispatch_date,),
            ).fetchall()
        return [self._row_to_driver_vehicle_assignment(row) for row in rows]

    def list_driver_vehicle_assignments_for_delivery_date(self, delivery_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_driver_vehicle_assignments
                WHERE delivery_date = ?
                ORDER BY driver_id, dispatch_date
                """,
                (delivery_date,),
            ).fetchall()
        assignments = [self._row_to_driver_vehicle_assignment(row) for row in rows]
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
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for task in tasks:
                assignment_rows = connection.execute(
                    """
                    SELECT *
                    FROM manual_dispatch_assignments
                    WHERE task_type = 'OPSHOP_PICKUP' AND task_id = ?
                    ORDER BY assignment_id
                    """,
                    (task.pickup_task_id,),
                ).fetchall()
                if len(assignment_rows) > 1:
                    raise ValueError(
                        "Manual dispatch assignment integrity error for "
                        f"OPSHOP_PICKUP:{task.pickup_task_id}: "
                        "expected at most one row."
                    )
                existing = assignment_rows[0] if assignment_rows else None

                connection.execute(
                    """
                    INSERT INTO opshop_pickup_tasks (
                        pickup_task_id, schedule_id, opshop_id, pickup_date,
                        task_type, generated_from, status, dispatch_date,
                        driver_id, trip_no, notes, trip_sequence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        trip_sequence = excluded.trip_sequence,
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
                        task.trip_sequence,
                        task.created_at,
                        task.updated_at,
                    ),
                )
                if remove_all_existing and existing:
                    connection.execute(
                        """
                        DELETE FROM manual_dispatch_assignments
                        WHERE assignment_id = ?
                        """,
                        (existing["assignment_id"],),
                    )
                    existing = None

                if task.driver_id:
                    timestamp = self._timestamp()
                    if existing:
                        connection.execute(
                            """
                            UPDATE manual_dispatch_assignments
                            SET driver_id = ?, trip_no = 'trip1', updated_at = ?
                            WHERE assignment_id = ?
                            """,
                            (
                                task.driver_id,
                                timestamp,
                                existing["assignment_id"],
                            ),
                        )
                    else:
                        assignment_id = self._create_assignment_id(connection)
                        connection.execute(
                            """
                            INSERT INTO manual_dispatch_assignments (
                                assignment_id, dispatch_date, task_type, task_id,
                                driver_id, trip_no, assigned_at, updated_at
                            ) VALUES (?, ?, 'OPSHOP_PICKUP', ?, ?, 'trip1', ?, ?)
                            """,
                            (
                                assignment_id,
                                dispatch_date,
                                task.pickup_task_id,
                                task.driver_id,
                                timestamp,
                                timestamp,
                            ),
                        )
                elif existing:
                    connection.execute(
                        """
                        DELETE FROM manual_dispatch_assignments
                        WHERE assignment_id = ?
                        """,
                        (existing["assignment_id"],),
                    )
            connection.commit()
        return [self.get_opshop_pickup_task(task.pickup_task_id) for task in tasks]

    def update_countryside_pickup_trip_sequences(self, ordered_pickup_task_ids):
        with connect(self.db_path) as connection:
            timestamp = self._timestamp()
            for sequence, pickup_task_id in enumerate(
                ordered_pickup_task_ids,
                start=1,
            ):
                cursor = connection.execute(
                    """
                    UPDATE opshop_pickup_tasks
                    SET trip_sequence = ?, updated_at = ?
                    WHERE pickup_task_id = ?
                    """,
                    (sequence, timestamp, pickup_task_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError(
                        "OP SHOP pickup task does not exist: "
                        f"{pickup_task_id}"
                    )

    def has_assignment_for_task(self, task_type, task_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM manual_dispatch_assignments
                WHERE task_type = ? AND task_id = ?
                LIMIT 1
                """,
                (task_type, task_id),
            ).fetchone()
        return row is not None

    def driver_has_active_assignments(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM manual_dispatch_assignments
                WHERE driver_id = ?
                LIMIT 1
                """,
                (driver_id,),
            ).fetchone()
        return row is not None

    def driver_has_vehicle_selection(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM manual_driver_vehicle_assignments
                WHERE driver_id = ?
                LIMIT 1
                """,
                (driver_id,),
            ).fetchone()
        return row is not None

    def vehicle_has_current_selection(self, vehicle_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM manual_driver_vehicle_assignments
                WHERE vehicle_id = ?
                LIMIT 1
                """,
                (vehicle_id,),
            ).fetchone()
        return row is not None

    def upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no):
        timestamp = self._timestamp()

        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE task_type = ? AND task_id = ?
                ORDER BY assignment_id
                """,
                (task_type, task_id),
            ).fetchall()
            if len(rows) > 1:
                connection.rollback()
                raise ValueError(
                    "Manual dispatch assignment integrity error for "
                    f"{task_type}:{task_id}: expected at most one row."
                )
            existing = rows[0] if rows else None
            if existing:
                assignment_id = existing["assignment_id"]
                origin_dispatch_date = existing["dispatch_date"]
                connection.execute(
                    """
                    UPDATE manual_dispatch_assignments
                    SET driver_id = ?, trip_no = ?, updated_at = ?
                    WHERE assignment_id = ?
                    """,
                    (driver_id, trip_no, timestamp, assignment_id),
                )
            else:
                assignment_id = self._create_assignment_id(connection)
                origin_dispatch_date = dispatch_date
                connection.execute(
                    """
                    INSERT INTO manual_dispatch_assignments (
                        assignment_id,
                        dispatch_date,
                        task_type,
                        task_id,
                        driver_id,
                        trip_no,
                        assigned_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assignment_id,
                        origin_dispatch_date,
                        task_type,
                        task_id,
                        driver_id,
                        trip_no,
                        timestamp,
                        timestamp,
                    ),
                )
            connection.commit()

        return ManualDispatchAssignment(
            assignment_id=assignment_id,
            dispatch_date=origin_dispatch_date,
            task_type=task_type,
            task_id=task_id,
            driver_id=driver_id,
            trip_no=trip_no,
        )

    def get_assignment(self, dispatch_date, task_type, task_id):
        with connect(self.db_path) as connection:
            row = self._fetch_assignment_row(
                connection,
                dispatch_date,
                task_type,
                task_id,
            )
        return self._row_to_assignment(row) if row else None

    def find_assignment_for_task(self, task_type, task_id):
        assignments = self.list_assignments_for_task(task_type, task_id)
        if len(assignments) > 1:
            raise ValueError(
                "Manual dispatch assignment integrity error for "
                f"{task_type}:{task_id}: expected at most one row."
            )
        return assignments[0] if assignments else None

    def list_assignments_for_task(self, task_type, task_id):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE task_type = ? AND task_id = ?
                ORDER BY assignment_id
                """,
                (task_type, task_id),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def remove_assignment(self, dispatch_date, task_type, task_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM manual_dispatch_assignments
                WHERE dispatch_date = ? AND task_type = ? AND task_id = ?
                """,
                (dispatch_date, task_type, task_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def remove_assignments_for_task(self, task_type, task_id):
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT assignment_id
                FROM manual_dispatch_assignments
                WHERE task_type = ? AND task_id = ?
                ORDER BY assignment_id
                """,
                (task_type, task_id),
            ).fetchall()
            if len(rows) > 1:
                connection.rollback()
                raise ValueError(
                    "Manual dispatch assignment integrity error for "
                    f"{task_type}:{task_id}: expected at most one row."
                )
            if not rows:
                connection.commit()
                return False
            cursor = connection.execute(
                """
                DELETE FROM manual_dispatch_assignments
                WHERE assignment_id = ?
                """,
                (rows[0]["assignment_id"],),
            )
            connection.commit()
        return cursor.rowcount > 0

    def upsert_driver_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id):
        timestamp = self._timestamp()

        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_driver_vehicle_assignments (
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    vehicle_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(dispatch_date, delivery_date, driver_id)
                DO UPDATE SET
                    vehicle_id = excluded.vehicle_id,
                    updated_at = excluded.updated_at
                """,
                (dispatch_date, delivery_date, driver_id, vehicle_id, timestamp, timestamp),
            )
            connection.commit()

        return ManualDriverVehicleAssignment(
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )

    def upsert_delivery_workspace_vehicle_assignment(
        self, dispatch_date, delivery_date, driver_id, vehicle_id
    ):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current_rows = connection.execute(
                """
                SELECT *
                FROM manual_driver_vehicle_assignments
                WHERE delivery_date = ? AND driver_id = ?
                ORDER BY dispatch_date
                """,
                (delivery_date, driver_id),
            ).fetchall()
            if len(current_rows) > 1:
                connection.rollback()
                raise ValueError(
                    "Driver vehicle assignment integrity error for "
                    f"{delivery_date}:{driver_id}: expected at most one row."
                )
            conflict = connection.execute(
                """
                SELECT driver_id
                FROM manual_driver_vehicle_assignments
                WHERE delivery_date = ?
                    AND vehicle_id = ?
                    AND driver_id != ?
                ORDER BY driver_id
                LIMIT 1
                """,
                (delivery_date, vehicle_id, driver_id),
            ).fetchone()
            if conflict:
                connection.rollback()
                return None, conflict["driver_id"]

            current = current_rows[0] if current_rows else None
            origin_dispatch_date = (
                current["dispatch_date"] if current else dispatch_date
            )
            if current:
                connection.execute(
                    """
                    UPDATE manual_driver_vehicle_assignments
                    SET vehicle_id = ?, updated_at = ?
                    WHERE dispatch_date = ?
                        AND delivery_date = ?
                        AND driver_id = ?
                    """,
                    (
                        vehicle_id,
                        timestamp,
                        origin_dispatch_date,
                        delivery_date,
                        driver_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO manual_driver_vehicle_assignments (
                        dispatch_date,
                        delivery_date,
                        driver_id,
                        vehicle_id,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        origin_dispatch_date,
                        delivery_date,
                        driver_id,
                        vehicle_id,
                        timestamp,
                        timestamp,
                    ),
                )
            connection.commit()
        return (
            ManualDriverVehicleAssignment(
                dispatch_date=origin_dispatch_date,
                delivery_date=delivery_date,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
            ),
            None,
        )

    def remove_driver_vehicle_assignment(
        self,
        dispatch_date,
        driver_id,
        delivery_date=None,
    ):
        with connect(self.db_path) as connection:
            if delivery_date:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT dispatch_date
                    FROM manual_driver_vehicle_assignments
                    WHERE delivery_date = ? AND driver_id = ?
                    ORDER BY dispatch_date
                    """,
                    (delivery_date, driver_id),
                ).fetchall()
                if len(rows) > 1:
                    connection.rollback()
                    raise ValueError(
                        "Driver vehicle assignment integrity error for "
                        f"{delivery_date}:{driver_id}: expected at most one row."
                    )
                if not rows:
                    connection.commit()
                    return False
                cursor = connection.execute(
                    """
                    DELETE FROM manual_driver_vehicle_assignments
                    WHERE dispatch_date = ?
                        AND delivery_date = ?
                        AND driver_id = ?
                    """,
                    (rows[0]["dispatch_date"], delivery_date, driver_id),
                )
            else:
                cursor = connection.execute(
                    """
                    DELETE FROM manual_driver_vehicle_assignments
                    WHERE dispatch_date = ? AND driver_id = ?
                    """,
                    (dispatch_date, driver_id),
                )
            connection.commit()
        return cursor.rowcount > 0

    def _fetch_assignment_row(self, connection, dispatch_date, task_type, task_id):
        return connection.execute(
            """
            SELECT *
            FROM manual_dispatch_assignments
            WHERE dispatch_date = ? AND task_type = ? AND task_id = ?
            """,
            (dispatch_date, task_type, task_id),
        ).fetchone()

    def _create_assignment_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(assignment_id, 3) AS INTEGER)), 0) + 1
                AS next_number
            FROM manual_dispatch_assignments
            WHERE assignment_id LIKE 'A-%'
            """
        ).fetchone()
        return f"A-{row['next_number']:03d}"
