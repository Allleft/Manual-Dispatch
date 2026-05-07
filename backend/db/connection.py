import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "manual_dispatch.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


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

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path=None):
    with connect(db_path) as connection:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        schema_statements, seed_statements = _split_schema_and_seed(schema)
        connection.executescript(schema_statements)
        _ensure_manual_dispatch_columns(connection)
        connection.executescript(seed_statements)
        connection.commit()


def _split_schema_and_seed(schema):
    seed_start = schema.find("INSERT OR IGNORE INTO")
    if seed_start == -1:
        return schema, ""
    return schema[:seed_start], schema[seed_start:]


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


def _ensure_column(connection, table_name, column_name, column_definition):
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
