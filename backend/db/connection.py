import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "manual_dispatch.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEED_DEMO_DATA_ENV = "MANUAL_DISPATCH_SEED_DEMO_DATA"


def get_database_path(db_path=None):
    if db_path:
        return Path(db_path)

    configured_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
    if configured_path:
        return Path(configured_path)

    return DEFAULT_DB_PATH


def connect(db_path=None):
    database_path = get_database_path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(db_path=None):
    with connect(db_path) as connection:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        schema_statements, seed_statements = _split_schema_and_seed(schema)
        connection.executescript(schema_statements)
        _ensure_manual_dispatch_columns(connection)
        if _is_env_flag_enabled(SEED_DEMO_DATA_ENV, default=True):
            connection.executescript(seed_statements)
        connection.commit()


def _split_schema_and_seed(schema):
    seed_start = schema.find("INSERT OR IGNORE INTO")
    if seed_start == -1:
        return schema, ""
    return schema[:seed_start], schema[seed_start:]


def _is_env_flag_enabled(name, default=False):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _ensure_manual_dispatch_columns(connection):
    _ensure_column(connection, "manual_orders", "invoice_number", "TEXT")
    _ensure_column(connection, "manual_orders", "phone", "TEXT")
    _ensure_column(connection, "manual_orders", "status", "TEXT NOT NULL DEFAULT 'ACTIVE'")
    _ensure_column(
        connection,
        "manual_drivers",
        "pallet_only",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(connection, "manual_drivers", "license_no", "TEXT")
    _ensure_column(connection, "manual_drivers", "email", "TEXT")
    _ensure_column(connection, "manual_drivers", "phone_number", "TEXT")
    _ensure_column(
        connection,
        "manual_drivers",
        "is_deleted",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "manual_vehicles",
        "is_deleted",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(connection, "manual_driver_vehicle_assignments", "delivery_date", "TEXT")
    connection.execute(
        """
        UPDATE manual_driver_vehicle_assignments
        SET delivery_date = dispatch_date
        WHERE delivery_date IS NULL OR TRIM(delivery_date) = ''
        """
    )
    _ensure_driver_vehicle_assignment_key(connection)
    _ensure_column(connection, "final_trip_summaries", "delivery_date", "TEXT")
    connection.execute(
        """
        UPDATE final_trip_summaries
        SET delivery_date = dispatch_date
        WHERE delivery_date IS NULL OR TRIM(delivery_date) = ''
        """
    )
    _ensure_column(
        connection,
        "final_trip_summaries",
        "saved_by_account_name",
        "TEXT NOT NULL DEFAULT 'Unknown'",
    )
    _ensure_column(
        connection,
        "final_trip_summaries",
        "saved_by_account_id",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "final_trip_summary_rows",
        "product_details_snapshot",
        "TEXT NOT NULL DEFAULT '[]'",
    )
    _ensure_column(
        connection,
        "final_trip_summary_rows",
        "estimated_distance_km_from_warehouse_snapshot",
        "REAL",
    )
    _ensure_column(
        connection,
        "final_trip_summary_opshop_pickup_rows",
        "pickup_category_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "final_trip_summary_opshop_pickup_rows",
        "route_group_id_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "final_trip_summary_opshop_pickup_rows",
        "route_group_name_snapshot",
        "TEXT",
    )
    _ensure_column(connection, "opshop_pickup_schedules", "default_driver_id", "TEXT")
    _ensure_column(connection, "opshop_pickup_schedules", "default_driver_alias", "TEXT")
    _ensure_column(
        connection,
        "opshop_pickup_schedules",
        "default_driver_name_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "opshop_pickup_schedules",
        "pickup_category",
        "TEXT NOT NULL DEFAULT 'NORMAL'",
    )
    _ensure_column(connection, "opshop_pickup_schedules", "route_group_id", "TEXT")
    connection.execute(
        """
        UPDATE opshop_pickup_schedules
        SET pickup_category = 'NORMAL'
        WHERE pickup_category IS NULL OR TRIM(pickup_category) = ''
        """
    )


def _ensure_column(connection, table_name, column_name, column_definition):
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _ensure_driver_vehicle_assignment_key(connection):
    primary_key_columns = [
        row["name"]
        for row in sorted(
            connection.execute(
                "PRAGMA table_info(manual_driver_vehicle_assignments)"
            ).fetchall(),
            key=lambda item: item["pk"],
        )
        if row["pk"]
    ]
    if primary_key_columns == ["dispatch_date", "delivery_date", "driver_id"]:
        return

    connection.execute(
        """
        ALTER TABLE manual_driver_vehicle_assignments
        RENAME TO manual_driver_vehicle_assignments_legacy
        """
    )
    connection.execute(
        """
        CREATE TABLE manual_driver_vehicle_assignments (
            dispatch_date TEXT NOT NULL,
            delivery_date TEXT NOT NULL,
            driver_id TEXT NOT NULL,
            vehicle_id TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            PRIMARY KEY(dispatch_date, delivery_date, driver_id),
            FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id),
            FOREIGN KEY(vehicle_id) REFERENCES manual_vehicles(vehicle_id)
        )
        """
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO manual_driver_vehicle_assignments (
            dispatch_date,
            delivery_date,
            driver_id,
            vehicle_id,
            created_at,
            updated_at
        )
        SELECT
            dispatch_date,
            COALESCE(NULLIF(TRIM(delivery_date), ''), dispatch_date),
            driver_id,
            vehicle_id,
            created_at,
            updated_at
        FROM manual_driver_vehicle_assignments_legacy
        """
    )
    connection.execute("DROP TABLE manual_driver_vehicle_assignments_legacy")
