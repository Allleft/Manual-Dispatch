import os
import re
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from backend.db.invariants import create_invariant_indexes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "manual_dispatch.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEED_DEMO_DATA_ENV = "MANUAL_DISPATCH_SEED_DEMO_DATA"
_ACTIVE_CONNECTIONS = ContextVar(
    "manual_dispatch_active_sqlite_connections",
    default={},
)


class _BorrowedConnection:
    """Keep nested repository helpers inside an owning transaction."""

    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def execute(self, sql, parameters=()):
        if str(sql).strip().upper().startswith("BEGIN"):
            return self
        return self._connection.execute(sql, parameters)

    def commit(self):
        return None

    def close(self):
        return None

    def rollback(self):
        return self._connection.rollback()


class _ManagedConnection:
    """Close an owned SQLite connection when its context exits."""

    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return self._connection.__exit__(exc_type, exc_value, traceback)
        finally:
            self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        return self._connection.close()


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

    active_connection = _ACTIVE_CONNECTIONS.get().get(_connection_key(database_path))
    if active_connection is not None:
        return _BorrowedConnection(active_connection)

    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return _ManagedConnection(connection)


def has_active_connection(db_path=None):
    database_path = get_database_path(db_path)
    return _connection_key(database_path) in _ACTIVE_CONNECTIONS.get()


@contextmanager
def borrow_connection(db_path, connection):
    key = _connection_key(get_database_path(db_path))
    active_connections = dict(_ACTIVE_CONNECTIONS.get())
    if key in active_connections:
        raise RuntimeError(f"SQLite connection is already active for {key}")
    active_connections[key] = connection
    token = _ACTIVE_CONNECTIONS.set(active_connections)
    try:
        yield
    finally:
        _ACTIVE_CONNECTIONS.reset(token)


def _connection_key(database_path):
    return str(Path(database_path).resolve()).casefold()


def initialize_database(db_path=None):
    with connect(db_path) as connection:
        is_fresh_database = not _table_exists(connection, "manual_orders")
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        schema_statements, seed_statements = _split_schema_and_seed(schema)
        connection.executescript(schema_statements)
        _ensure_manual_dispatch_columns(connection)
        if is_fresh_database:
            create_invariant_indexes(connection)
        if _is_env_flag_enabled(SEED_DEMO_DATA_ENV, default=False):
            connection.executescript(seed_statements)
        connection.commit()


def _table_exists(connection, table_name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


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
    _ensure_order_product_line_units(connection)
    _ensure_column(connection, "manual_orders", "invoice_number", "TEXT")
    _ensure_column(connection, "manual_orders", "order_no", "TEXT")
    _ensure_column(connection, "manual_orders", "phone", "TEXT")
    _ensure_column(connection, "manual_orders", "status", "TEXT NOT NULL DEFAULT 'ACTIVE'")
    _ensure_column(
        connection,
        "manual_orders",
        "carton_quantity",
        "INTEGER NOT NULL DEFAULT 0",
    )
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
        "order_no_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "final_trip_summary_rows",
        "estimated_distance_km_from_warehouse_snapshot",
        "REAL",
    )
    _ensure_column(
        connection,
        "final_trip_summaries",
        "total_cartons",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "final_trip_summary_rows",
        "carton_quantity_snapshot",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "delivery_run_sheets",
        "total_cartons",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "delivery_run_sheet_rows",
        "carton_quantity_snapshot",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "delivery_run_sheets",
        "execution_status",
        "TEXT NOT NULL DEFAULT 'OPEN'",
    )
    _ensure_column(connection, "delivery_run_sheets", "closed_at", "TEXT")
    _ensure_column(
        connection,
        "delivery_run_sheets",
        "closed_by_account_id",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "delivery_run_sheets",
        "closed_by_account_name",
        "TEXT",
    )
    connection.execute(
        """
        UPDATE delivery_run_sheets
        SET execution_status = 'OPEN'
        WHERE execution_status IS NULL OR TRIM(execution_status) = ''
        """
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
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "call_before_arrival_snapshot",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "call_timing_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "clothing_kg_snapshot",
        "REAL",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "shoes_kg_snapshot",
        "REAL",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "time_in_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "time_out_snapshot",
        "TEXT",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "trolleys_out_to_opshops_snapshot",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "trolleys_in_to_mcc_snapshot",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "hard_toys_snapshot",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "soft_toys_snapshot",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "black_bags_snapshot",
        "INTEGER",
    )
    _ensure_column(
        connection,
        "opshop_pickup_collection_rows",
        "shoe_bags_snapshot",
        "INTEGER",
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
    _backfill_manual_order_numbers(connection)


def _ensure_order_product_line_units(connection):
    table_row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'order_product_lines'
        """
    ).fetchone()
    table_sql = table_row["sql"] if table_row else ""
    if not table_sql:
        return

    base_columns = {
        "id",
        "order_id",
        "line_no",
        "product_name",
        "quantity",
        "unit",
    }
    expected_columns = base_columns | {
        "product_code",
        "package_quantity",
        "package_unit",
    }
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(order_product_lines)").fetchall()
    }
    has_restricted_unit_check = "CHECK(UNITIN" in re.sub(
        r"\s+",
        "",
        table_sql.upper(),
    )
    if expected_columns.issubset(existing_columns) and not has_restricted_unit_check:
        return
    if not base_columns.issubset(existing_columns) or not existing_columns.issubset(
        expected_columns
    ):
        raise RuntimeError(
            "Cannot safely migrate order_product_lines with unexpected columns"
        )

    schema_objects = [
        row["sql"]
        for row in connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE tbl_name = 'order_product_lines'
                AND type IN ('index', 'trigger')
                AND sql IS NOT NULL
            ORDER BY type, name
            """
        ).fetchall()
    ]
    row_count = connection.execute(
        "SELECT COUNT(*) FROM order_product_lines"
    ).fetchone()[0]

    connection.execute("SAVEPOINT migrate_order_product_line_units")
    try:
        connection.execute("DROP TABLE IF EXISTS order_product_lines__new")
        connection.execute(
            """
            CREATE TABLE order_product_lines__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                line_no INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                product_code TEXT,
                package_quantity INTEGER,
                package_unit TEXT,
                UNIQUE(order_id, line_no),
                CHECK(quantity > 0),
                CHECK(length(TRIM(unit)) BETWEEN 1 AND 20),
                CHECK(product_code IS NULL OR length(product_code) <= 40),
                CHECK(package_quantity IS NULL OR package_quantity >= 0),
                CHECK(package_unit IS NULL OR length(package_unit) <= 20),
                FOREIGN KEY(order_id) REFERENCES manual_orders(order_id)
                    ON DELETE CASCADE
            )
            """
        )
        product_code_expression = (
            "product_code" if "product_code" in existing_columns else "NULL"
        )
        package_quantity_expression = (
            "package_quantity" if "package_quantity" in existing_columns else "NULL"
        )
        package_unit_expression = (
            "package_unit" if "package_unit" in existing_columns else "NULL"
        )
        connection.execute(
            f"""
            INSERT INTO order_product_lines__new (
                id,
                order_id,
                line_no,
                product_name,
                quantity,
                unit,
                product_code,
                package_quantity,
                package_unit
            )
            SELECT
                id,
                order_id,
                line_no,
                product_name,
                quantity,
                unit,
                {product_code_expression},
                {package_quantity_expression},
                {package_unit_expression}
            FROM order_product_lines
            ORDER BY id
            """
        )
        copied_count = connection.execute(
            "SELECT COUNT(*) FROM order_product_lines__new"
        ).fetchone()[0]
        if copied_count != row_count:
            raise RuntimeError("order_product_lines migration did not copy every row")

        connection.execute("DROP TABLE order_product_lines")
        connection.execute(
            "ALTER TABLE order_product_lines__new RENAME TO order_product_lines"
        )
        for schema_object_sql in schema_objects:
            connection.execute(schema_object_sql)

        foreign_key_issues = connection.execute(
            "PRAGMA foreign_key_check(order_product_lines)"
        ).fetchall()
        if foreign_key_issues:
            raise RuntimeError("order_product_lines migration failed foreign key validation")
        connection.execute("RELEASE SAVEPOINT migrate_order_product_line_units")
    except Exception:
        connection.execute("ROLLBACK TO SAVEPOINT migrate_order_product_line_units")
        connection.execute("RELEASE SAVEPOINT migrate_order_product_line_units")
        raise


def _ensure_column(connection, table_name, column_name, column_definition):
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _backfill_manual_order_numbers(connection):
    try:
        rows = connection.execute(
            """
            SELECT order_id, note
            FROM manual_orders
            WHERE (order_no IS NULL OR TRIM(order_no) = '')
                AND note IS NOT NULL
                AND TRIM(note) != ''
            """
        ).fetchall()
    except sqlite3.Error:
        return

    for row in rows:
        order_no = _extract_order_no_from_note(row["note"])
        if not order_no:
            continue
        try:
            connection.execute(
                """
                UPDATE manual_orders
                SET order_no = ?
                WHERE order_id = ?
                    AND (order_no IS NULL OR TRIM(order_no) = '')
                """,
                (order_no, row["order_id"]),
            )
        except sqlite3.Error:
            continue


def _extract_order_no_from_note(note):
    match = re.search(
        r"\bOrder\s*(?:No\.?|#)?\s*:?\s*([A-Za-z0-9][A-Za-z0-9_-]*)",
        str(note or ""),
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


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
