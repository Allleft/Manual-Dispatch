from datetime import datetime, timezone

from backend.db.connection import connect, get_database_path, initialize_database
from backend.schemas import (
    Driver,
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
    Order,
    Vehicle,
)


class SQLiteManualDispatchRepository:
    """SQLite-backed repository for Phase 6 manual dispatch persistence."""

    def __init__(self, db_path=None):
        self.db_path = get_database_path(db_path)
        initialize_database(self.db_path)

    def list_orders(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM manual_orders ORDER BY order_id"
            ).fetchall()
        return [self._row_to_order(row) for row in rows]

    def list_drivers(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM manual_drivers ORDER BY driver_id"
            ).fetchall()
        return [self._row_to_driver(row) for row in rows]

    def list_vehicles(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM manual_vehicles ORDER BY vehicle_id"
            ).fetchall()
        return [self._row_to_vehicle(row) for row in rows]

    def list_assignments(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE dispatch_date = ?
                ORDER BY assignment_id
                """,
                (dispatch_date,),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_driver_vehicle_assignments(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_driver_vehicle_assignments
                WHERE dispatch_date = ?
                ORDER BY driver_id
                """,
                (dispatch_date,),
            ).fetchall()
        return [self._row_to_driver_vehicle_assignment(row) for row in rows]

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

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            return self.get_order(task_id)
        return None

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

    def upsert_driver_vehicle_assignment(self, dispatch_date, driver_id, vehicle_id):
        timestamp = self._timestamp()

        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_driver_vehicle_assignments (
                    dispatch_date,
                    driver_id,
                    vehicle_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(dispatch_date, driver_id)
                DO UPDATE SET
                    vehicle_id = excluded.vehicle_id,
                    updated_at = excluded.updated_at
                """,
                (dispatch_date, driver_id, vehicle_id, timestamp, timestamp),
            )
            connection.commit()

        return ManualDriverVehicleAssignment(
            dispatch_date=dispatch_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )

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

    def _row_to_order(self, row):
        return Order(
            order_id=row["order_id"],
            company_name=row["company_name"],
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
        )

    def _row_to_driver(self, row):
        return Driver(
            driver_id=row["driver_id"],
            name=row["name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            is_available=bool(row["is_available"]),
            preferred_zone=row["preferred_zone"],
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
            driver_id=row["driver_id"],
            vehicle_id=row["vehicle_id"],
        )

    def _timestamp(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
