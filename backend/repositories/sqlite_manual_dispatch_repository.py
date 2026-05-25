from datetime import datetime, timezone
import json

from backend.db.connection import connect, get_database_path, initialize_database
from backend.schemas import (
    Driver,
    FinalTripSummary,
    FinalTripSummaryOrderSnapshot,
    FinalTripSummaryTrip,
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
    Order,
    OpShopLocation,
    OpShopPickupBoardItem,
    OpShopPickupSchedule,
    OpShopPickupScheduleCandidate,
    OpShopPickupTask,
    OpShopTemplate,
    OperatorAccountRecord,
    ProductDetailLine,
    Vehicle,
)


class SQLiteManualDispatchRepository:
    """SQLite-backed repository for Phase 6 manual dispatch persistence."""

    def __init__(self, db_path=None):
        self.db_path = get_database_path(db_path)
        initialize_database(self.db_path)

    def list_orders(self, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM manual_orders
                    WHERE status = 'ACTIVE' AND delivery_date = ?
                    ORDER BY order_id
                    """,
                    (delivery_date,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM manual_orders WHERE status = 'ACTIVE' ORDER BY order_id"
                ).fetchall()
        return [self._row_to_order(row) for row in rows]

    def list_drivers(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_drivers
                WHERE is_available = 1 AND is_deleted = 0
                ORDER BY driver_id
                """
            ).fetchall()
        return [self._row_to_driver(row) for row in rows]

    def list_vehicles(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_vehicles
                WHERE is_available = 1 AND is_deleted = 0
                ORDER BY vehicle_id
                """
            ).fetchall()
        return [self._row_to_vehicle(row) for row in rows]

    def list_specification_drivers(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_drivers
                WHERE is_deleted = 0
                ORDER BY driver_id
                """
            ).fetchall()
        return [self._row_to_driver(row) for row in rows]

    def list_specification_vehicles(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_vehicles
                WHERE is_deleted = 0
                ORDER BY vehicle_id
                """
            ).fetchall()
        return [self._row_to_vehicle(row) for row in rows]

    def list_driver_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute("SELECT driver_id FROM manual_drivers").fetchall()
        return [row["driver_id"] for row in rows]

    def list_vehicle_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute("SELECT vehicle_id FROM manual_vehicles").fetchall()
        return [row["vehicle_id"] for row in rows]

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
                    assigned_driver.name AS assigned_driver_name
                FROM manual_dispatch_assignments assignment
                JOIN opshop_pickup_tasks task
                    ON task.pickup_task_id = assignment.task_id
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
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

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND delivery_date = ?
                    ORDER BY saved_at DESC, summary_id
                    """,
                    (dispatch_date, delivery_date),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ?
                    ORDER BY saved_at DESC, summary_id
                    """,
                    (dispatch_date,),
                ).fetchall()
        return [self._row_to_final_trip_summary(row) for row in rows]

    def list_final_summary_dates(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT dispatch_date
                FROM final_trip_summaries
                WHERE status = 'SAVED'
                ORDER BY dispatch_date DESC
                """
            ).fetchall()
        return [row["dispatch_date"] for row in rows]

    def has_saved_final_trip_summary(self, dispatch_date, driver_id, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM final_trip_summaries
                    WHERE dispatch_date = ?
                        AND delivery_date = ?
                        AND driver_id = ?
                        AND status = 'SAVED'
                    LIMIT 1
                    """,
                    (dispatch_date, delivery_date, driver_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND driver_id = ? AND status = 'SAVED'
                    LIMIT 1
                    """,
                    (dispatch_date, driver_id),
                ).fetchone()
        return row is not None

    def get_final_trip_summary(self, summary_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM final_trip_summaries
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchone()
        return self._row_to_final_trip_summary(row) if row else None

    def get_order(self, order_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        return self._row_to_order(row) if row else None

    def get_driver(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_drivers WHERE driver_id = ?",
                (driver_id,),
            ).fetchone()
        return self._row_to_driver(row) if row else None

    def get_vehicle(self, vehicle_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_vehicles WHERE vehicle_id = ?",
                (vehicle_id,),
            ).fetchone()
        return self._row_to_vehicle(row) if row else None

    def get_operator_account_by_name(self, account_name):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM operator_accounts
                WHERE account_name = ? COLLATE NOCASE
                """,
                (account_name,),
            ).fetchone()
        return self._row_to_operator_account(row) if row else None

    def get_operator_account_by_id(self, account_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM operator_accounts
                WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
        return self._row_to_operator_account(row) if row else None

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
                    schedule.default_driver_name_snapshot AS default_driver_name
                FROM opshop_pickup_schedules schedule
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                WHERE schedule.active_flag = 1
                    AND schedule.status = 'Active'
                    AND schedule.run_type = 'REGULAR'
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
                    schedule.default_driver_name_snapshot AS default_driver_name
                FROM opshop_pickup_schedules schedule
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
                WHERE schedule.active_flag = 1
                    AND schedule.status = 'Active'
                    AND schedule.run_type = 'ON_CALL'
                ORDER BY
                    COALESCE(schedule.run_day, 'ZZZ'),
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
                    location.status_notes
                FROM opshop_pickup_schedules schedule
                INNER JOIN opshop_locations location
                    ON location.opshop_id = schedule.opshop_id
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
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id)
                DO UPDATE SET
                    opshop_id = excluded.opshop_id,
                    run_day = excluded.run_day,
                    run_type = excluded.run_type,
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
                    updated_at = excluded.updated_at
                """,
                (
                    schedule.schedule_id,
                    schedule.opshop_id,
                    schedule.run_day,
                    schedule.run_type,
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
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.pickup_date BETWEEN ? AND ?
                    AND task.status IN ('ACTIVE', 'ASSIGNED')
                    AND schedule.run_type = 'REGULAR'
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

    def list_oncall_opshop_pickup_board_items(self, dispatch_date):
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
                    assigned_driver.name AS assigned_driver_name
                FROM opshop_pickup_tasks task
                LEFT JOIN opshop_locations location
                    ON location.opshop_id = task.opshop_id
                LEFT JOIN opshop_pickup_schedules schedule
                    ON schedule.schedule_id = task.schedule_id
                LEFT JOIN manual_drivers assigned_driver
                    ON assigned_driver.driver_id = task.driver_id
                WHERE task.pickup_date >= ?
                    AND task.status IN ('ACTIVE', 'ASSIGNED')
                    AND task.generated_from = 'ON_CALL'
                    AND schedule.run_type = 'ON_CALL'
                    AND schedule.active_flag = 1
                    AND schedule.status = 'Active'
                ORDER BY
                    task.pickup_date,
                    COALESCE(location.suburb, ''),
                    COALESCE(location.name, ''),
                    task.pickup_task_id
                """,
                (dispatch_date,),
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

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            order = self.get_order(task_id)
            return order if order and order.status == "ACTIVE" else None
        if task_type == "OPSHOP_PICKUP":
            task = self.get_opshop_pickup_task(task_id)
            return task if task and task.status == "ACTIVE" else None
        return None

    def create_order(self, order):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_orders (
                    order_id,
                    invoice_number,
                    company_name,
                    phone,
                    delivery_address,
                    suburb,
                    postcode,
                    delivery_date,
                    zone,
                    urgency,
                    preferred_driver_id,
                    pallet_quantity,
                    loose_bags_quantity,
                    start_time,
                    end_time,
                    note,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_id,
                    order.invoice_number,
                    order.company_name,
                    order.phone,
                    order.delivery_address,
                    order.suburb,
                    order.postcode,
                    order.delivery_date,
                    order.zone,
                    order.urgency,
                    order.preferred_driver_id,
                    order.pallet_quantity,
                    order.loose_bags_quantity,
                    order.start_time,
                    order.end_time,
                    order.note,
                    order.status,
                ),
            )
            self._replace_order_product_lines(connection, order.order_id, order.product_lines)
            connection.commit()
        return self.get_order(order.order_id)

    def update_order(self, order):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_orders
                SET
                    invoice_number = ?,
                    company_name = ?,
                    phone = ?,
                    delivery_address = ?,
                    suburb = ?,
                    postcode = ?,
                    delivery_date = ?,
                    zone = ?,
                    urgency = ?,
                    preferred_driver_id = ?,
                    pallet_quantity = ?,
                    loose_bags_quantity = ?,
                    start_time = ?,
                    end_time = ?,
                    note = ?
                WHERE order_id = ?
                """,
                (
                    order.invoice_number,
                    order.company_name,
                    order.phone,
                    order.delivery_address,
                    order.suburb,
                    order.postcode,
                    order.delivery_date,
                    order.zone,
                    order.urgency,
                    order.preferred_driver_id,
                    order.pallet_quantity,
                    order.loose_bags_quantity,
                    order.start_time,
                    order.end_time,
                    order.note,
                    order.order_id,
                ),
            )
            self._replace_order_product_lines(connection, order.order_id, order.product_lines)
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Order does not exist: {order.order_id}")
        return self.get_order(order.order_id)

    def cancel_order(self, order_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                "UPDATE manual_orders SET status = 'CANCELLED' WHERE order_id = ?",
                (order_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Order does not exist: {order_id}")
        return self.get_order(order_id)

    def create_driver(self, driver):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_drivers (
                    driver_id,
                    name,
                    license_no,
                    email,
                    phone_number,
                    start_time,
                    end_time,
                    is_available,
                    preferred_zone,
                    pallet_only,
                    is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver.driver_id,
                    driver.name,
                    driver.license_no,
                    driver.email,
                    driver.phone_number,
                    driver.start_time,
                    driver.end_time,
                    int(driver.is_available),
                    driver.preferred_zone,
                    int(driver.pallet_only),
                    int(driver.is_deleted),
                ),
            )
            connection.commit()
        return self.get_driver(driver.driver_id)

    def update_driver(self, driver):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_drivers
                SET
                    name = ?,
                    license_no = ?,
                    email = ?,
                    phone_number = ?,
                    start_time = ?,
                    end_time = ?,
                    is_available = ?,
                    preferred_zone = ?,
                    pallet_only = ?
                WHERE driver_id = ? AND is_deleted = 0
                """,
                (
                    driver.name,
                    driver.license_no,
                    driver.email,
                    driver.phone_number,
                    driver.start_time,
                    driver.end_time,
                    int(driver.is_available),
                    driver.preferred_zone,
                    int(driver.pallet_only),
                    driver.driver_id,
                ),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Driver does not exist: {driver.driver_id}")
        return self.get_driver(driver.driver_id)

    def delete_driver(self, driver_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_drivers
                SET is_deleted = 1, is_available = 0
                WHERE driver_id = ? AND is_deleted = 0
                """,
                (driver_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Driver does not exist: {driver_id}")
        return True

    def create_vehicle(self, vehicle):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_vehicles (
                    vehicle_id,
                    rego,
                    type,
                    is_available,
                    pallet_capacity,
                    tub_capacity,
                    trolley_capacity,
                    stillage_capacity,
                    is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vehicle.vehicle_id,
                    vehicle.rego,
                    vehicle.type,
                    int(vehicle.is_available),
                    vehicle.pallet_capacity,
                    vehicle.tub_capacity,
                    vehicle.trolley_capacity,
                    vehicle.stillage_capacity,
                    int(vehicle.is_deleted),
                ),
            )
            connection.commit()
        return self.get_vehicle(vehicle.vehicle_id)

    def create_operator_account(self, account_name, password_hash, password_salt):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO operator_accounts (
                    account_name,
                    password_hash,
                    password_salt,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (account_name, password_hash, password_salt, timestamp, timestamp),
            )
            account_id = cursor.lastrowid
            connection.commit()
        return self.get_operator_account_by_id(account_id)

    def update_operator_account_password(self, account_id, password_hash, password_salt):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE operator_accounts
                SET password_hash = ?, password_salt = ?, updated_at = ?
                WHERE id = ?
                """,
                (password_hash, password_salt, timestamp, account_id),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError("Operator account does not exist")
        return self.get_operator_account_by_id(account_id)

    def update_vehicle(self, vehicle):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_vehicles
                SET
                    rego = ?,
                    type = ?,
                    is_available = ?,
                    pallet_capacity = ?,
                    tub_capacity = ?,
                    trolley_capacity = ?,
                    stillage_capacity = ?
                WHERE vehicle_id = ? AND is_deleted = 0
                """,
                (
                    vehicle.rego,
                    vehicle.type,
                    int(vehicle.is_available),
                    vehicle.pallet_capacity,
                    vehicle.tub_capacity,
                    vehicle.trolley_capacity,
                    vehicle.stillage_capacity,
                    vehicle.vehicle_id,
                ),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Vehicle does not exist: {vehicle.vehicle_id}")
        return self.get_vehicle(vehicle.vehicle_id)

    def delete_vehicle(self, vehicle_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_vehicles
                SET is_deleted = 1, is_available = 0
                WHERE vehicle_id = ? AND is_deleted = 0
                """,
                (vehicle_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")
        return True

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

    def driver_has_final_summary_history(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
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

    def vehicle_has_final_summary_history(self, vehicle_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE vehicle_id = ?
                LIMIT 1
                """,
                (vehicle_id,),
            ).fetchone()
        return row is not None

    def upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no):
        timestamp = self._timestamp()

        with connect(self.db_path) as connection:
            existing = self._fetch_assignment_row(
                connection,
                dispatch_date,
                task_type,
                task_id,
            )
            if existing:
                assignment_id = existing["assignment_id"]
                connection.execute(
                    """
                    UPDATE manual_dispatch_assignments
                    SET driver_id = ?, trip_no = ?, updated_at = ?
                    WHERE dispatch_date = ? AND task_type = ? AND task_id = ?
                    """,
                    (
                        driver_id,
                        trip_no,
                        timestamp,
                        dispatch_date,
                        task_type,
                        task_id,
                    ),
                )
            else:
                assignment_id = self._create_assignment_id(connection)
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
                        dispatch_date,
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
            dispatch_date=dispatch_date,
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
            cursor = connection.execute(
                """
                DELETE FROM manual_dispatch_assignments
                WHERE task_type = ? AND task_id = ?
                """,
                (task_type, task_id),
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

    def remove_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                cursor = connection.execute(
                    """
                    DELETE FROM manual_driver_vehicle_assignments
                    WHERE dispatch_date = ? AND delivery_date = ? AND driver_id = ?
                    """,
                    (dispatch_date, delivery_date, driver_id),
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

    def save_final_trip_summary(self, summary, rows):
        timestamp = self._timestamp()

        with connect(self.db_path) as connection:
            existing_summary = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE dispatch_date = ?
                    AND delivery_date = ?
                    AND driver_id = ?
                    AND status = 'SAVED'
                LIMIT 1
                """,
                (
                    summary["dispatch_date"],
                    summary["delivery_date"],
                    summary["driver_id"],
                ),
            ).fetchone()
            if existing_summary:
                raise ValueError(
                    "Final Summary for this driver, dispatch date, and delivery date has already been saved."
                )

            summary_id = self._create_final_trip_summary_id(connection)
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id,
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    driver_name_snapshot,
                    vehicle_id,
                    vehicle_rego_snapshot,
                    total_pallets,
                    total_loose_bags,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    summary["dispatch_date"],
                    summary["delivery_date"],
                    summary["driver_id"],
                    summary["driver_name_snapshot"],
                    summary.get("vehicle_id"),
                    summary.get("vehicle_rego_snapshot"),
                    summary["total_pallets"],
                    summary["total_loose_bags"],
                    "SAVED",
                    summary.get("generated_at") or timestamp,
                    timestamp,
                    summary.get("saved_by_account_name") or "Unknown",
                    summary.get("saved_by_account_id"),
                ),
            )

            for row in rows:
                row_id = self._create_final_trip_summary_row_id(connection)
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_rows (
                        row_id,
                        summary_id,
                        trip_no,
                        row_no,
                        task_type,
                        task_id,
                        order_id_snapshot,
                        invoice_number_snapshot,
                        company_name_snapshot,
                        suburb_snapshot,
                        delivery_address_snapshot,
                        product_snapshot,
                        product_details_snapshot,
                        estimated_distance_km_from_warehouse_snapshot,
                        pallet_quantity_snapshot,
                        loose_bags_quantity_snapshot,
                        note_snapshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        summary_id,
                        row["trip_no"],
                        row["row_no"],
                        row["task_type"],
                        row["task_id"],
                        row.get("order_id_snapshot"),
                        row.get("invoice_number_snapshot"),
                        row.get("company_name_snapshot"),
                        row.get("suburb_snapshot"),
                        row.get("delivery_address_snapshot"),
                        row.get("product_snapshot"),
                        self._serialize_product_lines(row.get("product_lines_snapshot") or []),
                        row.get("estimated_distance_km_from_warehouse_snapshot"),
                        row["pallet_quantity_snapshot"],
                        row["loose_bags_quantity_snapshot"],
                        row.get("note_snapshot"),
                    ),
                )

                if row["task_type"] == "ORDER":
                    connection.execute(
                        """
                        UPDATE manual_orders
                        SET status = 'FINALIZED'
                        WHERE order_id = ? AND status = 'ACTIVE'
                        """,
                        (row["task_id"],),
                    )
                    connection.execute(
                        """
                        DELETE FROM manual_dispatch_assignments
                        WHERE dispatch_date = ? AND task_type = ? AND task_id = ?
                        """,
                        (
                            summary["dispatch_date"],
                            row["task_type"],
                            row["task_id"],
                        ),
                    )

            connection.commit()

        return self.get_final_trip_summary(summary_id)

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

    def _create_final_trip_summary_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(summary_id, 5) AS INTEGER)), 0) + 1
                AS next_number
            FROM final_trip_summaries
            WHERE summary_id LIKE 'FTS-%'
            """
        ).fetchone()
        return f"FTS-{row['next_number']:03d}"

    def _create_final_trip_summary_row_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(row_id, 5) AS INTEGER)), 0) + 1
                AS next_number
            FROM final_trip_summary_rows
            WHERE row_id LIKE 'FSR-%'
            """
        ).fetchone()
        return f"FSR-{row['next_number']:03d}"

    def _row_to_order(self, row):
        return Order(
            order_id=row["order_id"],
            invoice_number=row["invoice_number"],
            company_name=row["company_name"],
            phone=row["phone"],
            delivery_address=row["delivery_address"],
            suburb=row["suburb"],
            postcode=row["postcode"],
            delivery_date=row["delivery_date"],
            zone=row["zone"],
            urgency=row["urgency"],
            preferred_driver_id=row["preferred_driver_id"],
            pallet_quantity=row["pallet_quantity"],
            loose_bags_quantity=row["loose_bags_quantity"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            note=row["note"],
            status=row["status"],
            product_lines=self._list_order_product_lines(row["order_id"]),
        )

    def _row_to_driver(self, row):
        return Driver(
            driver_id=row["driver_id"],
            name=row["name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            is_available=bool(row["is_available"]),
            preferred_zone=row["preferred_zone"],
            pallet_only=bool(row["pallet_only"]),
            license_no=row["license_no"],
            email=row["email"],
            phone_number=row["phone_number"],
            is_deleted=bool(row["is_deleted"]),
        )

    def _row_to_vehicle(self, row):
        return Vehicle(
            vehicle_id=row["vehicle_id"],
            rego=row["rego"],
            type=row["type"],
            is_available=bool(row["is_available"]),
            pallet_capacity=row["pallet_capacity"],
            tub_capacity=row["tub_capacity"],
            trolley_capacity=row["trolley_capacity"],
            stillage_capacity=row["stillage_capacity"],
            is_deleted=bool(row["is_deleted"]),
        )

    def _row_to_assignment(self, row):
        return ManualDispatchAssignment(
            assignment_id=row["assignment_id"],
            dispatch_date=row["dispatch_date"],
            task_type=row["task_type"],
            task_id=row["task_id"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
        )

    def _row_to_driver_vehicle_assignment(self, row):
        return ManualDriverVehicleAssignment(
            dispatch_date=row["dispatch_date"],
            delivery_date=row["delivery_date"],
            driver_id=row["driver_id"],
            vehicle_id=row["vehicle_id"],
        )

    def _row_to_final_trip_summary(self, row):
        with connect(self.db_path) as connection:
            summary_rows = connection.execute(
                """
                SELECT *
                FROM final_trip_summary_rows
                WHERE summary_id = ?
                ORDER BY
                    CASE trip_no
                        WHEN 'trip1' THEN 1
                        WHEN 'trip2' THEN 2
                        ELSE 9
                    END,
                    row_no
                """,
                (row["summary_id"],),
            ).fetchall()

        trips = []
        for trip_no in ("trip1", "trip2"):
            trip_orders = [
                self._row_to_final_trip_summary_order(summary_row)
                for summary_row in summary_rows
                if summary_row["trip_no"] == trip_no
            ]
            if trip_orders:
                trips.append(FinalTripSummaryTrip(trip_no=trip_no, orders=trip_orders))

        return FinalTripSummary(
            summary_id=row["summary_id"],
            dispatch_date=row["dispatch_date"],
            delivery_date=row["delivery_date"],
            driver_id=row["driver_id"],
            driver_name_snapshot=row["driver_name_snapshot"],
            vehicle_id=row["vehicle_id"],
            vehicle_rego_snapshot=row["vehicle_rego_snapshot"],
            total_pallets=row["total_pallets"],
            total_loose_bags=row["total_loose_bags"],
            status=row["status"],
            generated_at=row["generated_at"],
            saved_at=row["saved_at"],
            saved_by_account_name=row["saved_by_account_name"] or "Unknown",
            saved_by_account_id=row["saved_by_account_id"],
            trips=trips,
        )

    def _row_to_final_trip_summary_order(self, row):
        return FinalTripSummaryOrderSnapshot(
            row_id=row["row_id"],
            trip_no=row["trip_no"],
            row_no=row["row_no"],
            task_type=row["task_type"],
            task_id=row["task_id"],
            order_id_snapshot=row["order_id_snapshot"],
            invoice_number_snapshot=row["invoice_number_snapshot"],
            company_name_snapshot=row["company_name_snapshot"],
            suburb_snapshot=row["suburb_snapshot"],
            delivery_address_snapshot=row["delivery_address_snapshot"],
            product_snapshot=row["product_snapshot"],
            pallet_quantity_snapshot=row["pallet_quantity_snapshot"],
            loose_bags_quantity_snapshot=row["loose_bags_quantity_snapshot"],
            note_snapshot=row["note_snapshot"],
            product_lines_snapshot=self._deserialize_product_lines(
                row["product_details_snapshot"]
                if "product_details_snapshot" in row.keys()
                else "[]"
            ),
            estimated_distance_km_from_warehouse_snapshot=(
                row["estimated_distance_km_from_warehouse_snapshot"]
                if "estimated_distance_km_from_warehouse_snapshot" in row.keys()
                else None
            ),
        )

    def _row_to_operator_account(self, row):
        return OperatorAccountRecord(
            account_id=row["id"],
            account_name=row["account_name"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_location(self, row):
        return OpShopLocation(
            opshop_id=row["opshop_id"],
            name=row["name"],
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status_notes=row["status_notes"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_pickup_schedule(self, row):
        return OpShopPickupSchedule(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            status=row["status"],
            active_flag=bool(row["active_flag"]),
            fortnight_group=row["fortnight_group"],
            review_required=bool(row["review_required"]),
            review_reason=row["review_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name_snapshot=row["default_driver_name_snapshot"],
        )

    def _row_to_opshop_pickup_schedule_candidate(self, row):
        return OpShopPickupScheduleCandidate(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            opshop_name=row["opshop_name"] or "",
            suburb=row["suburb"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            primary_phone=row["primary_phone"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name"],
        )

    def _row_to_opshop_template(self, row):
        return OpShopTemplate(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            run_type=row["run_type"],
            run_day=row["run_day"],
            name=row["name"],
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status_notes=row["status_notes"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name_snapshot"],
            status=row["status"],
            active_flag=bool(row["active_flag"]),
        )

    def _row_to_opshop_pickup_task(self, row):
        return OpShopPickupTask(
            pickup_task_id=row["pickup_task_id"],
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            pickup_date=row["pickup_date"],
            task_type=row["task_type"],
            generated_from=row["generated_from"],
            status=row["status"],
            dispatch_date=row["dispatch_date"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_pickup_board_item(self, row):
        return OpShopPickupBoardItem(
            pickup_task_id=row["pickup_task_id"],
            task_type=row["task_type"],
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            opshop_name=row["opshop_name"] or "",
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            pickup_date=row["pickup_date"],
            dispatch_date=row["dispatch_date"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status=row["status"],
            generated_from=row["generated_from"],
            status_notes=row["status_notes"],
            task_notes=row["task_notes"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
            is_assigned=bool(row["driver_id"] or row["trip_no"]),
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name"],
            assigned_driver_id=row["driver_id"],
            assigned_driver_name=row["assigned_driver_name"],
        )

    def _timestamp(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _replace_order_product_lines(self, connection, order_id, product_lines):
        connection.execute(
            "DELETE FROM order_product_lines WHERE order_id = ?",
            (order_id,),
        )
        for line_no, line in enumerate(product_lines or [], start=1):
            connection.execute(
                """
                INSERT INTO order_product_lines (
                    order_id,
                    line_no,
                    product_name,
                    quantity,
                    unit
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    line_no,
                    line.product_name,
                    line.quantity,
                    line.unit,
                ),
            )

    def _list_order_product_lines(self, order_id):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT product_name, quantity, unit
                FROM order_product_lines
                WHERE order_id = ?
                ORDER BY line_no
                """,
                (order_id,),
            ).fetchall()
        return [
            ProductDetailLine(
                product_name=row["product_name"],
                quantity=row["quantity"],
                unit=row["unit"],
            )
            for row in rows
        ]

    def _serialize_product_lines(self, product_lines):
        return json.dumps(
            [
                {
                    "product_name": line["product_name"]
                    if isinstance(line, dict)
                    else line.product_name,
                    "quantity": line["quantity"]
                    if isinstance(line, dict)
                    else line.quantity,
                    "unit": line["unit"]
                    if isinstance(line, dict)
                    else line.unit,
                }
                for line in product_lines
            ]
        )

    def _deserialize_product_lines(self, serialized):
        try:
            raw_lines = json.loads(serialized or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_lines = []
        return [
            ProductDetailLine(
                product_name=str(line.get("product_name") or ""),
                quantity=int(line.get("quantity") or 0),
                unit=str(line.get("unit") or ""),
            )
            for line in raw_lines
            if isinstance(line, dict)
        ]
