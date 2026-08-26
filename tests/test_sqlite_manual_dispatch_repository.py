import os
import sqlite3
import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.db.connection import connect, initialize_database
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateOrderRequest,
    UnassignTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class SQLiteManualDispatchRepositoryTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"sqlite-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        previous_seed_flag = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "true"
        try:
            self.repository = SQLiteManualDispatchRepository(self.db_path)
            self.service = ManualDispatchService(self.repository)
        finally:
            if previous_seed_flag is None:
                os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
            else:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_seed_flag

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repository_initializes_schema(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertIn("manual_orders", tables)
        self.assertIn("manual_drivers", tables)
        self.assertIn("manual_vehicles", tables)
        self.assertIn("manual_dispatch_assignments", tables)
        self.assertIn("manual_driver_vehicle_assignments", tables)
        self.assertIn("order_product_lines", tables)
        with sqlite3.connect(self.db_path) as connection:
            order_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(manual_orders)").fetchall()
            }
        self.assertIn("invoice_date", order_columns)

    def test_fresh_product_line_schema_allows_extended_unrestricted_units(self):
        with sqlite3.connect(self.db_path) as connection:
            table_sql = connection.execute(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'table' AND name = 'order_product_lines'
                """
            ).fetchone()[0]

        normalized_sql = " ".join(table_sql.upper().split())
        self.assertNotIn("CHECK(UNIT IN", normalized_sql)
        self.assertIn("PRODUCT_CODE", normalized_sql)
        self.assertIn("PACKAGE_QUANTITY", normalized_sql)
        self.assertIn("PACKAGE_UNIT", normalized_sql)

    def test_existing_product_lines_are_preserved_when_unit_check_is_removed(self):
        legacy_path = self.temp_dir / "legacy_product_lines.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE manual_orders (
                    order_id TEXT PRIMARY KEY,
                    invoice_number TEXT,
                    order_no TEXT,
                    company_name TEXT,
                    phone TEXT,
                    delivery_address TEXT,
                    suburb TEXT NOT NULL,
                    postcode TEXT,
                    delivery_date TEXT,
                    zone TEXT,
                    urgency TEXT,
                    preferred_driver_id TEXT,
                    pallet_quantity INTEGER NOT NULL DEFAULT 0,
                    loose_bags_quantity INTEGER NOT NULL DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    note TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE'
                );
                CREATE TABLE order_product_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    line_no INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit TEXT NOT NULL,
                    UNIQUE(order_id, line_no),
                    CHECK(quantity > 0),
                    CHECK(unit IN ('PALLETS', 'BAGS')),
                    FOREIGN KEY(order_id) REFERENCES manual_orders(order_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX idx_legacy_product_unit
                    ON order_product_lines(unit);
                CREATE TABLE product_line_audit (
                    product_line_id INTEGER NOT NULL,
                    unit TEXT NOT NULL
                );
                CREATE TRIGGER trg_legacy_product_insert
                    AFTER INSERT ON order_product_lines
                    BEGIN
                        INSERT INTO product_line_audit (product_line_id, unit)
                        VALUES (NEW.id, NEW.unit);
                    END;
                INSERT INTO manual_orders (
                    order_id,
                    invoice_number,
                    company_name,
                    suburb,
                    delivery_date,
                    pallet_quantity,
                    loose_bags_quantity,
                    status
                ) VALUES (
                    'ORD-LEGACY-CARTON',
                    'LEGACY-CARTON',
                    'Legacy Product Customer',
                    'Dandenong',
                    '2026-06-05',
                    1,
                    2,
                    'ACTIVE'
                );
                INSERT INTO order_product_lines (
                    id, order_id, line_no, product_name, quantity, unit
                ) VALUES
                    (7, 'ORD-LEGACY-CARTON', 1, 'Existing Pallet Product', 1, 'PALLETS'),
                    (8, 'ORD-LEGACY-CARTON', 2, 'Existing Bag Product', 2, 'BAGS');
                """
            )

        previous_seed_flag = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"
        try:
            initialize_database(legacy_path)
            initialize_database(legacy_path)
        finally:
            if previous_seed_flag is None:
                os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
            else:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_seed_flag

        with sqlite3.connect(legacy_path) as connection:
            table_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'order_product_lines'"
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT id, line_no, product_name, quantity, unit
                FROM order_product_lines
                ORDER BY id
                """
            ).fetchall()
            indexes = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index' AND tbl_name = 'order_product_lines'
                    """
                ).fetchall()
            }
            triggers = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'trigger' AND tbl_name = 'order_product_lines'
                    """
                ).fetchall()
            }
            connection.execute(
                """
                INSERT INTO order_product_lines (
                    order_id,
                    line_no,
                    product_code,
                    product_name,
                    quantity,
                    unit,
                    package_quantity,
                    package_unit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ORD-LEGACY-CARTON",
                    3,
                    "RWIND",
                    "New Kilogram Product",
                    450,
                    "KG",
                    45,
                    "BAG10",
                ),
            )
            foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
            kilogram_audit_rows = connection.execute(
                """
                SELECT unit
                FROM product_line_audit
                WHERE unit = 'KG'
                """
            ).fetchall()

        normalized_sql = " ".join(table_sql.upper().split())
        self.assertNotIn("CHECK(UNIT IN", normalized_sql)
        self.assertIn("PRODUCT_CODE", normalized_sql)
        self.assertIn("PACKAGE_QUANTITY", normalized_sql)
        self.assertIn("PACKAGE_UNIT", normalized_sql)
        self.assertEqual(
            [
                (7, 1, "Existing Pallet Product", 1, "PALLETS"),
                (8, 2, "Existing Bag Product", 2, "BAGS"),
            ],
            rows,
        )
        self.assertIn("idx_legacy_product_unit", indexes)
        self.assertIn("trg_legacy_product_insert", triggers)
        self.assertEqual([("KG",)], kilogram_audit_rows)
        self.assertEqual([], foreign_key_issues)

    def test_connection_uses_wal_and_busy_timeout_for_office_deployment(self):
        with connect(self.db_path) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

        self.assertEqual("wal", journal_mode.lower())
        self.assertEqual(5000, busy_timeout)
        self.assertEqual(1, foreign_keys)

    def test_connection_context_closes_owned_connection(self):
        connection = connect(self.db_path)

        with connection:
            connection.execute("SELECT 1").fetchone()

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1").fetchone()

    def test_seed_data_loads_orders_drivers_and_vehicles(self):
        board = self.service.get_board("2026-05-05")

        self.assertEqual(
            ["Dandenong", "Clayton", "Springvale"],
            [order.suburb for order in board.orders],
        )
        self.assertEqual(
            ["INV-1001", "INV-1002", "INV-1003"],
            [order.invoice_number for order in board.orders],
        )
        self.assertEqual(
            ["0400 000 001", "0400 000 002", "0400 000 003"],
            [order.phone for order in board.orders],
        )
        self.assertEqual(["John", "Tony", "David"], [driver.name for driver in board.drivers])
        self.assertEqual([False, True, False], [driver.pallet_only for driver in board.drivers])
        self.assertEqual(
            ["ABC123", "XYZ888", "MCC001"],
            [vehicle.rego for vehicle in board.vehicles],
        )

    def test_seed_data_is_disabled_when_environment_is_absent(self):
        previous_value = os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
        try:
            db_path = self.temp_dir / "manual_dispatch_default_no_seed.sqlite3"
            service = ManualDispatchService(SQLiteManualDispatchRepository(db_path))
            board = service.get_board("2026-05-05")
        finally:
            if previous_value is not None:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_value

        self.assertEqual([], board.orders)
        self.assertEqual([], board.drivers)
        self.assertEqual([], board.vehicles)

    def test_seed_data_can_be_disabled_by_environment(self):
        previous_value = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "false"
        try:
            db_path = self.temp_dir / "manual_dispatch_no_seed.sqlite3"
            service = ManualDispatchService(SQLiteManualDispatchRepository(db_path))
            board = service.get_board("2026-05-05")
        finally:
            if previous_value is None:
                os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
            else:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_value

        self.assertEqual([], board.orders)
        self.assertEqual([], board.drivers)
        self.assertEqual([], board.vehicles)

    def test_explicit_seed_does_not_overwrite_existing_business_data(self):
        db_path = self.temp_dir / "manual_dispatch_existing_data.sqlite3"
        previous_value = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        try:
            os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "false"
            initialize_database(db_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO manual_orders (
                        order_id,
                        invoice_number,
                        company_name,
                        suburb,
                        delivery_date,
                        pallet_quantity,
                        loose_bags_quantity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "ORD-001",
                        "PRODUCTION-001",
                        "Existing Production Customer",
                        "Geelong",
                        "2026-05-05",
                        9,
                        4,
                    ),
                )

            os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "true"
            initialize_database(db_path)
        finally:
            if previous_value is None:
                os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
            else:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_value

        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                """
                SELECT invoice_number, company_name, suburb,
                       pallet_quantity, loose_bags_quantity
                FROM manual_orders
                WHERE order_id = 'ORD-001'
                """
            ).fetchone()

        self.assertEqual(
            (
                "PRODUCTION-001",
                "Existing Production Customer",
                "Geelong",
                9,
                4,
            ),
            row,
        )

    def test_board_keeps_task_pool_orders_global_across_delivery_dates(self):
        created = self.service.create_order(
            CreateOrderRequest(
                company_name="SQLite Future Delivery Customer",
                suburb="Geelong",
                delivery_date="2026-05-06",
            )
        )

        board_0505 = self.service.get_board("2026-05-05")
        board_0506 = self.service.get_board("2026-05-06")

        self.assertIn(created.order_id, [order.order_id for order in board_0505.orders])
        self.assertIn(created.order_id, [order.order_id for order in board_0506.orders])
        self.assertIn("2026-05-06", {order.delivery_date for order in board_0505.orders})

    def test_existing_database_without_new_columns_is_upgraded(self):
        legacy_path = self.temp_dir / "legacy_manual_dispatch.sqlite3"
        self._create_legacy_database(legacy_path)

        repository = SQLiteManualDispatchRepository(legacy_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        legacy_order = next(order for order in board.orders if order.order_id == "ORD-OLD")
        legacy_driver = next(driver for driver in board.drivers if driver.driver_id == "DOLD")

        self.assertIsNone(legacy_order.invoice_number)
        self.assertIsNone(legacy_order.invoice_date)
        self.assertEqual("002848", legacy_order.order_no)
        self.assertIsNone(legacy_order.phone)
        self.assertFalse(legacy_driver.pallet_only)

        with sqlite3.connect(legacy_path) as connection:
            order_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(manual_orders)").fetchall()
            }
            driver_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(manual_drivers)").fetchall()
            }
            vehicle_assignment_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(manual_driver_vehicle_assignments)"
                ).fetchall()
            }
            final_summary_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(final_trip_summaries)"
                ).fetchall()
            }
            final_summary_row_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(final_trip_summary_rows)"
                ).fetchall()
            }
            final_summary_opshop_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            final_summary_opshop_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(final_trip_summary_opshop_pickup_rows)"
                ).fetchall()
            }
            opshop_schedule_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(opshop_pickup_schedules)"
                ).fetchall()
            }

        self.assertIn("invoice_number", order_columns)
        self.assertIn("invoice_date", order_columns)
        self.assertIn("order_no", order_columns)
        self.assertIn("phone", order_columns)
        self.assertIn("pallet_only", driver_columns)
        self.assertIn("delivery_date", vehicle_assignment_columns)
        self.assertIn("delivery_date", final_summary_columns)
        self.assertIn("product_details_snapshot", final_summary_row_columns)
        self.assertIn("order_no_snapshot", final_summary_row_columns)
        self.assertIn(
            "estimated_distance_km_from_warehouse_snapshot",
            final_summary_row_columns,
        )
        self.assertIn("final_trip_summary_opshop_pickup_rows", final_summary_opshop_tables)
        self.assertIn("opshop_countryside_route_groups", final_summary_opshop_tables)
        self.assertIn("pickup_category", opshop_schedule_columns)
        self.assertIn("route_group_id", opshop_schedule_columns)
        self.assertIn("regular_route_sequence", opshop_schedule_columns)
        self.assertIn("pickup_category_snapshot", final_summary_opshop_columns)
        self.assertIn("route_group_id_snapshot", final_summary_opshop_columns)
        self.assertIn("route_group_name_snapshot", final_summary_opshop_columns)
        with sqlite3.connect(legacy_path) as connection:
            legacy_row = connection.execute(
                """
                SELECT company_name, delivery_date, suburb, invoice_date
                FROM manual_orders
                WHERE order_id = 'ORD-OLD'
                """
            ).fetchone()
            foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(
            ("Legacy Customer", "2026-05-05", "Moorabbin", None),
            legacy_row,
        )
        self.assertEqual([], foreign_key_errors)

    def test_existing_opshop_schedule_receives_route_sequence_column_additively(self):
        legacy_path = self.temp_dir / "legacy_opshop_schedule.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.executescript(
                """
                CREATE TABLE opshop_pickup_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    opshop_id TEXT NOT NULL,
                    run_day TEXT,
                    run_type TEXT NOT NULL,
                    pickup_category TEXT NOT NULL DEFAULT 'NORMAL',
                    route_group_id TEXT,
                    pickup_frequency TEXT,
                    time_window TEXT,
                    call_before_arrival INTEGER NOT NULL DEFAULT 0,
                    call_timing TEXT,
                    status TEXT NOT NULL DEFAULT 'Active',
                    active_flag INTEGER NOT NULL DEFAULT 1,
                    fortnight_group TEXT,
                    review_required INTEGER NOT NULL DEFAULT 0,
                    review_reason TEXT,
                    default_driver_id TEXT,
                    default_driver_alias TEXT,
                    default_driver_name_snapshot TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO opshop_pickup_schedules (
                    schedule_id, opshop_id, run_day, run_type, pickup_category,
                    pickup_frequency, status, active_flag, created_at, updated_at
                ) VALUES (
                    'LEGACY-SCHEDULE', 'LEGACY-OPSHOP', 'MONDAY', 'REGULAR',
                    'NORMAL', 'Weekly', 'Active', 1,
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
                );
                """
            )
            before = connection.execute(
                "SELECT * FROM opshop_pickup_schedules"
            ).fetchone()

        SQLiteManualDispatchRepository(legacy_path)

        with sqlite3.connect(legacy_path) as connection:
            columns = [
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(opshop_pickup_schedules)"
                )
            ]
            business_values = connection.execute(
                """
                SELECT schedule_id, opshop_id, run_day, run_type, pickup_category,
                       route_group_id, pickup_frequency, time_window,
                       call_before_arrival, call_timing, status, active_flag,
                       fortnight_group, review_required, review_reason,
                       default_driver_id, default_driver_alias,
                       default_driver_name_snapshot, created_at, updated_at
                FROM opshop_pickup_schedules
                """
            ).fetchone()
            sequence = connection.execute(
                "SELECT regular_route_sequence FROM opshop_pickup_schedules"
            ).fetchone()[0]
        self.assertIn("regular_route_sequence", columns)
        self.assertEqual(before, business_values)
        self.assertIsNone(sequence)

    def test_existing_opshop_summary_row_without_category_route_values_loads_safely(self):
        with sqlite3.connect(self.db_path) as connection:
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
                    "FTS-LEGACY",
                    "2026-05-05",
                    "2026-05-05",
                    "D001",
                    "John",
                    None,
                    "No vehicle selected",
                    0,
                    0,
                    "SAVED",
                    "2026-05-05T00:00:00Z",
                    "2026-05-05T00:00:00Z",
                    "Unknown",
                    None,
                ),
            )
            connection.execute(
                """
                INSERT INTO final_trip_summary_opshop_pickup_rows (
                    row_id,
                    summary_id,
                    row_no,
                    pickup_task_id_snapshot,
                    opshop_name_snapshot,
                    pickup_date_snapshot,
                    run_type_snapshot,
                    status_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "FSO-LEGACY",
                    "FTS-LEGACY",
                    1,
                    "TASK-LEGACY",
                    "Legacy OP SHOP",
                    "2026-05-05",
                    "ON_CALL",
                    "ASSIGNED",
                ),
            )
            connection.commit()

        summary = self.repository.get_final_trip_summary("FTS-LEGACY")

        self.assertEqual(1, len(summary.opshop_pickups))
        pickup = summary.opshop_pickups[0]
        self.assertIsNone(pickup.pickup_category_snapshot)
        self.assertIsNone(pickup.route_group_id_snapshot)
        self.assertIsNone(pickup.route_group_name_snapshot)

    def test_assign_task_persists_assignment(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        self.assertEqual(1, len(board.assignments))
        self.assertEqual("ORDER", board.assignments[0].task_type)
        self.assertEqual("ORD-001", board.assignments[0].task_id)

    def test_unassign_task_removes_persisted_assignment(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        self.service.unassign_task(
            UnassignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")
        self.assertEqual([], board.assignments)

    def test_assign_vehicle_to_driver_persists_driver_date_vehicle_selection(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        self.assertEqual(1, len(board.driver_vehicle_assignments))
        self.assertEqual("D001", board.driver_vehicle_assignments[0].driver_id)
        self.assertEqual("2026-05-05", board.driver_vehicle_assignments[0].delivery_date)
        self.assertEqual("V002", board.driver_vehicle_assignments[0].vehicle_id)

    def test_vehicle_selection_is_scoped_by_delivery_date(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                delivery_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V001",
            )
        )
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                delivery_date="2026-05-06",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        repository = SQLiteManualDispatchRepository(self.db_path)
        board = ManualDispatchService(repository).get_board("2026-05-05")

        self.assertEqual(
            [("2026-05-05", "V001"), ("2026-05-06", "V002")],
            [
                (assignment.delivery_date, assignment.vehicle_id)
                for assignment in board.driver_vehicle_assignments
                if assignment.driver_id == "D001"
            ],
        )

    def test_vehicle_assignment_does_not_modify_task_assignment_records(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip2",
            )
        )

        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V002",
            )
        )

        board = self.service.get_board("2026-05-05")
        self.assertEqual(1, len(board.assignments))
        self.assertFalse(hasattr(board.assignments[0], "vehicle_id"))

    def test_duplicate_vehicle_assignment_across_drivers_is_rejected(self):
        self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V001",
            )
        )
        with self.assertRaisesRegex(ValueError, "already assigned"):
            self.service.assign_vehicle_to_driver(
                AssignDriverVehicleRequest(
                    dispatch_date="2026-05-05",
                    driver_id="D002",
                    vehicle_id="V001",
                )
            )

        board = self.service.get_board("2026-05-05")
        self.assertEqual(1, len(board.driver_vehicle_assignments))
        self.assertEqual("D001", board.driver_vehicle_assignments[0].driver_id)
        self.assertEqual("V001", board.driver_vehicle_assignments[0].vehicle_id)

    def test_invalid_trip_no_is_rejected_through_service(self):
        with self.assertRaises(ValueError):
            self.service.assign_task(
                AssignTaskRequest(
                    dispatch_date="2026-05-05",
                    task_type="ORDER",
                    task_id="ORD-001",
                    driver_id="D001",
                    trip_no="trip3",
                )
            )

    def test_invalid_vehicle_id_is_rejected_through_service(self):
        with self.assertRaises(ValueError):
            self.service.assign_vehicle_to_driver(
                AssignDriverVehicleRequest(
                    dispatch_date="2026-05-05",
                    driver_id="D001",
                    vehicle_id="V999",
                )
            )

    def _create_legacy_database(self, db_path):
        with sqlite3.connect(db_path) as connection:
            connection.executescript(
                """
                CREATE TABLE manual_orders (
                    order_id TEXT PRIMARY KEY,
                    company_name TEXT,
                    delivery_address TEXT,
                    suburb TEXT NOT NULL,
                    postcode TEXT,
                    delivery_date TEXT,
                    zone TEXT,
                    urgency TEXT,
                    preferred_driver_id TEXT,
                    pallet_quantity INTEGER NOT NULL DEFAULT 0,
                    loose_bags_quantity INTEGER NOT NULL DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    note TEXT
                );

                CREATE TABLE manual_drivers (
                    driver_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    preferred_zone TEXT
                );

                INSERT INTO manual_orders (
                    order_id,
                    company_name,
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
                    note
                ) VALUES (
                    'ORD-OLD',
                    'Legacy Customer',
                    '9 Legacy Street',
                    'Moorabbin',
                    '3189',
                    '2026-05-05',
                    'South East',
                    'Normal',
                    NULL,
                    1,
                    0,
                    '08:00',
                    '10:00',
                    'Legacy row Order No: 002848'
                );

                INSERT INTO manual_drivers (
                    driver_id,
                    name,
                    start_time,
                    end_time,
                    is_available,
                    preferred_zone
                ) VALUES (
                    'DOLD',
                    'Legacy Driver',
                    '08:00',
                    '16:00',
                    1,
                    'South East'
                );
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
