import os
import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from backend.db.connection import initialize_database
from backend.db import delivery_per_trip
from backend.db.delivery_per_trip import (
    DeliveryPerTripMigrationError,
    delivery_per_trip_schema_status,
    inspect_delivery_per_trip_migration,
    migrate_delivery_per_trip,
)
from backend.db.invariants import INVARIANT_INDEX_DEFINITIONS, LEGACY_INVARIANT_INDEX_DEFINITIONS
from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import DeliveryRunSheet, DeliveryRunSheetOrderSnapshot, DeliveryRunSheetTrip
from backend.services.manual_dispatch.workspace_migration_readiness_service import (
    WorkspaceMigrationReadinessService, WorkspaceMigrationRequiredError,
)
from tools.migrate_delivery_per_trip import main as migration_main


DATE = "2026-09-15"
OLD_VEHICLE_DDL = """CREATE TABLE IF NOT EXISTS manual_driver_vehicle_assignments (
    dispatch_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    PRIMARY KEY(dispatch_date, delivery_date, driver_id),
    FOREIGN KEY(driver_id) REFERENCES manual_drivers(driver_id),
    FOREIGN KEY(vehicle_id) REFERENCES manual_vehicles(vehicle_id)
);"""
OLD_RUN_SHEET_DDL = """CREATE TABLE IF NOT EXISTS delivery_run_sheets (
    run_sheet_id TEXT PRIMARY KEY,
    dispatch_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    driver_name_snapshot TEXT NOT NULL,
    vehicle_id TEXT,
    vehicle_rego_snapshot TEXT,
    total_pallets INTEGER NOT NULL DEFAULT 0,
    total_loose_bags INTEGER NOT NULL DEFAULT 0,
    total_cartons INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    saved_at TEXT,
    saved_by_account_name TEXT,
    saved_by_account_id INTEGER,
    legacy_summary_id TEXT,
    execution_status TEXT NOT NULL DEFAULT 'OPEN',
    closed_at TEXT,
    closed_by_account_id INTEGER,
    closed_by_account_name TEXT,
    UNIQUE(dispatch_date, delivery_date, driver_id),
    CHECK(status IN ('GENERATED', 'SAVED')),
    CHECK(execution_status IN ('OPEN', 'CLOSED')),
    FOREIGN KEY(saved_by_account_id) REFERENCES operator_accounts(id)
);"""


def snapshot(identity="DRS-1", trip_no=None, status="GENERATED", execution_status="OPEN", driver="D001"):
    scopes = (trip_no,) if trip_no else ("trip1", "trip2")
    trips = []
    for number, scope in enumerate(scopes, 1):
        row = DeliveryRunSheetOrderSnapshot(
            row_id=f"{identity}-ROW-{number}", trip_no=scope, row_no=number,
            task_type="ORDER", task_id=f"ORD-00{number}", order_id_snapshot=f"ORD-00{number}",
            invoice_number_snapshot=f"INV-{number}", order_no_snapshot="000123",
            company_name_snapshot="Historical Customer", suburb_snapshot="Dandenong",
            delivery_address_snapshot="Original address", product_snapshot="Original product",
            pallet_quantity_snapshot=2, loose_bags_quantity_snapshot=0, note_snapshot="Original note",
        )
        trips.append(DeliveryRunSheetTrip(scope, [row]))
    return DeliveryRunSheet(
        run_sheet_id=identity, dispatch_date="2026-09-14", delivery_date=DATE, driver_id=driver,
        driver_name_snapshot="Original Driver", vehicle_id="V001", vehicle_rego_snapshot="ORIGINAL",
        total_pallets=2 * len(scopes), total_loose_bags=0, status=status,
        generated_at="2026-09-14T08:00:00Z", saved_at="2026-09-14T09:00:00Z" if status == "SAVED" else None,
        saved_by_account_name="Fixture" if status == "SAVED" else None,
        saved_by_account_id=None, legacy_summary_id=None, trips=trips,
        execution_status=execution_status,
        closed_at="2026-09-15T16:00:00Z" if execution_status == "CLOSED" else None,
        trip_no=trip_no,
    )


class DeliveryPerTripPersistenceTest(unittest.TestCase):
    def setUp(self):
        parent = Path.cwd() / "tmp"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="per-trip-stage1-", dir=parent)
        self.directory = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        self.db_path = self.directory / "fresh.sqlite3"
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            self.sqlite = SQLiteManualDispatchRepository(self.db_path)
        self.memory = InMemoryManualDispatchRepository()

    def repositories(self):
        return (self.sqlite, self.memory)

    @contextmanager
    def connection(self, path=None):
        with closing(sqlite3.connect(path or self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection

    def records(self, connection, table):
        return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]

    def old_database(self, trips=(), sheet=None, outcomes=False):
        path = self.directory / f"old-{len(list(self.directory.glob('old-*')))}.sqlite3"
        schema = (Path.cwd() / "backend/db/schema.sql").read_text(encoding="utf-8")
        schema = re.sub(r"CREATE TABLE IF NOT EXISTS manual_dispatch_schema_capabilities \(.*?\n\);", "", schema, flags=re.S)
        for table, old in (("manual_driver_vehicle_assignments", OLD_VEHICLE_DDL), ("delivery_run_sheets", OLD_RUN_SHEET_DDL)):
            schema = re.sub(rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\n\);", old, schema, flags=re.S)
        with self.connection(path) as connection:
            connection.executescript(schema)
            connection.execute("UPDATE manual_orders SET delivery_date = ?", (DATE,))
            for definition in LEGACY_INVARIANT_INDEX_DEFINITIONS:
                where = f" WHERE {definition['where']}" if definition["where"] else ""
                connection.execute(f"CREATE UNIQUE INDEX {definition['name']} ON {definition['table']} ({', '.join(definition['columns'])}){where}")
            connection.execute(
                "INSERT INTO manual_driver_vehicle_assignments VALUES (?, ?, 'D001', 'V001', 'original-created', 'original-updated')",
                ("2026-09-14", DATE),
            )
            for index, trip in enumerate(trips, 1):
                connection.execute(
                    "INSERT INTO manual_dispatch_assignments (assignment_id, dispatch_date, task_type, task_id, driver_id, trip_no) "
                    "VALUES (?, '2026-09-13', 'ORDER', ?, 'D001', ?)",
                    (f"A-FIXTURE-{index}", f"ORD-00{index}", trip),
                )
            if sheet:
                columns = [row["name"] for row in connection.execute("PRAGMA table_info(delivery_run_sheets)")]
                connection.execute(
                    f"INSERT INTO delivery_run_sheets ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    [getattr(sheet, name) for name in columns],
                )
                if outcomes:
                    connection.execute("INSERT INTO operator_accounts VALUES (1, 'Fixture', 'test-only-hash', 'test-only-salt', 'old', 'old')")
                for trip in sheet.trips:
                    for row in trip.orders:
                        connection.execute(
                            "INSERT INTO delivery_run_sheet_rows "
                            "(row_id, run_sheet_id, trip_no, row_no, task_id, order_id_snapshot, invoice_number_snapshot, "
                            "company_name_snapshot, product_details_snapshot, pallet_quantity_snapshot) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (row.row_id, sheet.run_sheet_id, row.trip_no, row.row_no, row.task_id, row.order_id_snapshot,
                             row.invoice_number_snapshot, row.company_name_snapshot,
                             '[ {"product_name":"Historical Rags", "quantity":2, "unit":"PALLETS"} ]', 2),
                        )
                        if outcomes:
                            connection.execute("UPDATE manual_orders SET status = 'FINALIZED' WHERE order_id = ?", (row.task_id,))
                            connection.execute(
                                "INSERT INTO delivery_run_sheet_outcomes "
                                "(outcome_id, run_sheet_id, run_sheet_row_id, order_id, outcome, recorded_at, recorded_by_account_id, recorded_by_account_name) "
                                "VALUES (?, ?, ?, ?, 'DELIVERED', 'original-recorded', 1, 'Fixture')",
                                (row.row_id + "-OUTCOME", sheet.run_sheet_id, row.row_id, row.task_id),
                            )
        return path

    def test_fresh_columns_and_nullable_models(self):
        with self.connection() as connection:
            for table in ("manual_driver_vehicle_assignments", "delivery_run_sheets"):
                columns = {row["name"]: row for row in connection.execute(f"PRAGMA table_info({table})")}
                self.assertIn("trip_no", columns)
                self.assertFalse(columns["trip_no"]["notnull"])
        self.assertIsNone(snapshot().trip_no)

    def test_fresh_indexes_have_exact_columns_predicates_and_uniqueness(self):
        with self.connection() as connection:
            for definition in INVARIANT_INDEX_DEFINITIONS:
                if definition["table"] not in ("manual_driver_vehicle_assignments", "delivery_run_sheets"):
                    continue
                columns = tuple(row["name"] for row in connection.execute(f"PRAGMA index_info({definition['name']})"))
                self.assertEqual(definition["columns"], columns)
                sql = connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (definition["name"],)).fetchone()[0]
                self.assertIn("CREATE UNIQUE INDEX", sql)
                self.assertTrue(sql.endswith("WHERE " + definition["where"]))

    def test_fresh_capability(self):
        self.assertEqual({"ready": True, "version": 1, "issues": []}, self.sqlite.get_delivery_per_trip_schema_status())

    def test_invalid_schema_cannot_publish_capability_without_outer_transaction(self):
        with closing(sqlite3.connect(self.db_path, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("DELETE FROM manual_dispatch_schema_capabilities")
            connection.execute("DROP INDEX idx_delivery_run_sheets_trip_identity")
            with self.assertRaisesRegex(DeliveryPerTripMigrationError, "schema validation failed"):
                delivery_per_trip.mark_per_trip_schema_ready(connection)
            self.assertIsNone(connection.execute(
                "SELECT version FROM manual_dispatch_schema_capabilities WHERE capability = 'delivery_per_trip'"
            ).fetchone())
            self.assertFalse(connection.in_transaction)

    def test_invalid_data_cannot_publish_capability_without_outer_transaction(self):
        self.sqlite.create_delivery_run_sheet(snapshot())
        with closing(sqlite3.connect(self.db_path, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("DELETE FROM manual_dispatch_schema_capabilities")
            columns = [row["name"] for row in connection.execute("PRAGMA table_info(delivery_run_sheets)")]
            conflicting = snapshot("DRS-OVERLAP", "trip1")
            connection.execute(
                f"INSERT INTO delivery_run_sheets ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                [getattr(conflicting, name) for name in columns],
            )
            with self.assertRaisesRegex(DeliveryPerTripMigrationError, "identity audit failed"):
                delivery_per_trip.mark_per_trip_schema_ready(connection)
            self.assertIsNone(connection.execute(
                "SELECT version FROM manual_dispatch_schema_capabilities WHERE capability = 'delivery_per_trip'"
            ).fetchone())
            self.assertFalse(connection.in_transaction)

    def test_old_schema_remains_old_until_explicit_apply(self):
        path = self.old_database()
        repository = SQLiteManualDispatchRepository(path)
        self.assertFalse(repository.get_delivery_per_trip_schema_status()["ready"])
        repository.upsert_delivery_workspace_vehicle_assignment("2026-09-14", DATE, "D001", "V002")
        self.assertEqual("V002", repository.list_driver_vehicle_assignments_for_delivery_date(DATE)[0].vehicle_id)
        with self.connection(path) as connection:
            self.assertNotIn("trip_no", {row["name"] for row in connection.execute("PRAGMA table_info(delivery_run_sheets)")})

    def test_old_schema_rejects_per_trip_write_and_future_gate(self):
        repository = SQLiteManualDispatchRepository(self.old_database())
        with self.assertRaisesRegex(ValueError, "migration is required"):
            repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", "trip1")
        with self.assertRaises(WorkspaceMigrationRequiredError):
            WorkspaceMigrationReadinessService(repository).ensure_per_trip_ready()
        self.assertTrue(repository.get_workspace_migration_status()["opshop_ready"])

    def test_dry_run_does_not_change_old_database(self):
        path = self.old_database(("trip1",))
        before = path.read_bytes()
        report = migrate_delivery_per_trip(path)
        self.assertEqual(["trip1"], report["vehicle_classification"][0]["seed_trips"])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.directory.glob("*-pre-trip-*")))

    def test_apply_requires_yes(self):
        with self.assertRaisesRegex(DeliveryPerTripMigrationError, "--apply and --yes"):
            migrate_delivery_per_trip(self.old_database(), apply=True)

    def assert_classification(self, trips, expected):
        path = self.old_database(trips)
        report = migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertEqual(expected, report["vehicle_classification"][0]["seed_trips"])
        with self.connection(path) as connection:
            rows = list(connection.execute("SELECT * FROM manual_driver_vehicle_assignments ORDER BY trip_no"))
            self.assertEqual([None, *expected], [row["trip_no"] for row in rows])
            self.assertTrue(all(row["vehicle_id"] == "V001" for row in rows))
            self.assertTrue(all(row["created_at"] == "original-created" and row["updated_at"] == "original-updated" for row in rows))
            self.assertTrue(delivery_per_trip_schema_status(connection)["ready"])

    def test_vehicle_trip1_only_classification(self):
        self.assert_classification(("trip1",), ["trip1"])

    def test_vehicle_trip2_only_classification(self):
        self.assert_classification(("trip2",), ["trip2"])

    def test_vehicle_both_trip_classification(self):
        self.assert_classification(("trip1", "trip2"), ["trip1", "trip2"])

    def test_vehicle_no_active_order_classification(self):
        self.assert_classification((), [])

    def test_non_active_orders_do_not_seed_vehicle_trips(self):
        path = self.old_database(("trip1", "trip2"))
        with self.connection(path) as connection:
            connection.execute("UPDATE manual_orders SET status = 'FINALIZED' WHERE order_id = 'ORD-001'")
            connection.execute("UPDATE manual_orders SET status = 'CANCELLED' WHERE order_id = 'ORD-002'")
        report = migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertEqual([], report["vehicle_classification"][0]["seed_trips"])
        self.assertEqual([], SQLiteManualDispatchRepository(path).list_delivery_trip_vehicle_assignments(DATE))

    def test_legacy_generated_saved_closed_are_not_split_or_seeded(self):
        for status, execution in (("GENERATED", "OPEN"), ("SAVED", "OPEN"), ("SAVED", "CLOSED")):
            with self.subTest(status=status, execution=execution):
                sheet = snapshot(status=status, execution_status=execution)
                path = self.old_database(("trip1", "trip2"), sheet)
                report = migrate_delivery_per_trip(path, apply=True, yes=True)
                self.assertEqual([], report["vehicle_classification"][0]["seed_trips"])
                loaded = SQLiteManualDispatchRepository(path).get_delivery_run_sheet(sheet.run_sheet_id)
                self.assertIsNone(loaded.trip_no)
                self.assertEqual(["trip1", "trip2"], [trip.trip_no for trip in loaded.trips])

    def test_single_trip_legacy_still_has_null_header(self):
        sheet = snapshot()
        sheet.trips = sheet.trips[:1]
        path = self.old_database(sheet=sheet)
        migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertIsNone(SQLiteManualDispatchRepository(path).get_delivery_run_sheet(sheet.run_sheet_id).trip_no)

    def test_closed_snapshots_rows_outcomes_and_ids_survive_cascade(self):
        path = self.old_database(sheet=snapshot(status="SAVED", execution_status="CLOSED"), outcomes=True)
        tables = ("delivery_run_sheets", "delivery_run_sheet_rows", "delivery_run_sheet_outcomes")
        with self.connection(path) as connection:
            before = {table: self.records(connection, table) for table in tables}
        migrate_delivery_per_trip(path, apply=True, yes=True)
        with self.connection(path) as connection:
            for table in tables:
                after = self.records(connection, table)
                if table == "delivery_run_sheets":
                    after = [{key: value for key, value in row.items() if key != "trip_no"} for row in after]
                self.assertEqual(before[table], after)
            self.assertEqual([], list(connection.execute("PRAGMA foreign_key_check")))
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            for table in tables[1:]:
                self.assertTrue(all("__per_trip_new" not in row["table"] for row in connection.execute(f"PRAGMA foreign_key_list({table})")))

    def test_migration_idempotent_does_not_reseed_after_clear(self):
        path = self.old_database(("trip1", "trip2"))
        migrate_delivery_per_trip(path, apply=True, yes=True)
        repository = SQLiteManualDispatchRepository(path)
        repository.remove_delivery_trip_vehicle_assignment(DATE, "D001", "trip1")
        before = path.read_bytes()
        second = migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertTrue(second["already_ready"])
        self.assertIsNone(repository.get_delivery_trip_vehicle_assignment(DATE, "D001", "trip1"))
        self.assertEqual(before, path.read_bytes())

    def test_repeated_startup_preserves_pk_and_both_vehicle_rows(self):
        path = self.old_database(("trip1", "trip2"))
        migrate_delivery_per_trip(path, apply=True, yes=True)
        with self.connection(path) as connection:
            before = self.records(connection, "manual_driver_vehicle_assignments")
        for _ in range(3):
            initialize_database(path)
        with self.connection(path) as connection:
            pk = [row["name"] for row in sorted(connection.execute("PRAGMA table_info(manual_driver_vehicle_assignments)"), key=lambda row: row["pk"]) if row["pk"]]
            self.assertEqual(["dispatch_date", "delivery_date", "driver_id", "trip_no"], pk)
            self.assertEqual(before, self.records(connection, "manual_driver_vehicle_assignments"))

    def test_partial_trip_schema_is_not_reverse_rebuilt(self):
        path = self.old_database()
        with self.connection(path) as connection:
            connection.execute("ALTER TABLE manual_driver_vehicle_assignments ADD COLUMN trip_no TEXT")
        with self.assertRaisesRegex(RuntimeError, "Unexpected per-trip vehicle schema"):
            initialize_database(path)
        with self.connection(path) as connection:
            self.assertIn("trip_no", {row["name"] for row in connection.execute("PRAGMA table_info(manual_driver_vehicle_assignments)")})

    def test_transaction_rollback_after_parent_drop_preserves_original(self):
        path = self.old_database(("trip1",), snapshot(status="SAVED", execution_status="CLOSED"), outcomes=True)
        before = path.read_bytes()
        with patch("backend.db.delivery_per_trip._verify_preservation", side_effect=RuntimeError("induced failure")):
            with self.assertRaisesRegex(RuntimeError, "induced failure"):
                migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertEqual(before, path.read_bytes())
        with self.connection(path) as connection:
            self.assertNotIn("trip_no", {row["name"] for row in connection.execute("PRAGMA table_info(delivery_run_sheets)")})
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM delivery_run_sheet_outcomes").fetchone()[0])
            self.assertEqual([], list(connection.execute("PRAGMA foreign_key_check")))

    def test_preflight_rejects_inconsistent_vehicle_evidence_without_writes(self):
        path = self.old_database(sheet=replace(snapshot(), vehicle_id="V002"))
        before = path.read_bytes()
        with self.assertRaises(DeliveryPerTripMigrationError) as caught:
            migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertTrue(any("contradicts" in str(item) for item in caught.exception.report["conflicts"]))
        self.assertEqual(before, path.read_bytes())

    def test_migration_preserves_opshop_schema_and_readiness(self):
        path = self.old_database(("trip1",))
        repository = SQLiteManualDispatchRepository(path)
        with self.connection(path) as connection:
            before = [tuple(row) for row in connection.execute("SELECT type, name, sql FROM sqlite_master WHERE name LIKE 'opshop_%' OR name LIKE 'idx_opshop_%' ORDER BY name")]
        ready = repository.get_workspace_migration_status()["opshop_ready"]
        migrate_delivery_per_trip(path, apply=True, yes=True)
        with self.connection(path) as connection:
            self.assertEqual(before, [tuple(row) for row in connection.execute("SELECT type, name, sql FROM sqlite_master WHERE name LIKE 'opshop_%' OR name LIKE 'idx_opshop_%' ORDER BY name")])
        self.assertEqual(ready, repository.get_workspace_migration_status()["opshop_ready"])

    def test_wrong_index_columns_or_predicate_do_not_pass_readiness(self):
        definition = next(item for item in INVARIANT_INDEX_DEFINITIONS if item["name"] == "idx_manual_driver_vehicle_trip_vehicle_identity")
        for columns, predicate in (("delivery_date, driver_id, trip_no", "trip_no IS NOT NULL"),
                                   ("delivery_date, vehicle_id, trip_no", "trip_no IS NULL"),
                                   ("delivery_date, vehicle_id COLLATE NOCASE, trip_no", "trip_no IS NOT NULL"),
                                   ("delivery_date, vehicle_id DESC, trip_no", "trip_no IS NOT NULL")):
            with self.connection() as connection:
                connection.execute(f"DROP INDEX {definition['name']}")
                connection.execute(f"CREATE UNIQUE INDEX {definition['name']} ON {definition['table']} ({columns}) WHERE {predicate}")
            self.assertFalse(self.sqlite.get_delivery_per_trip_schema_status()["ready"])
            with self.assertRaisesRegex(ValueError, "migration is required"):
                self.sqlite.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", "trip1")

    def test_trip_run_sheets_coexist_and_lookup_is_explicit(self):
        for repository in self.repositories():
            repository.create_delivery_run_sheet(snapshot("DRS-TRIP1", "trip1"))
            repository.create_delivery_run_sheet(snapshot("DRS-TRIP2", "trip2"))
            self.assertEqual(2, len(repository.list_delivery_run_sheets(delivery_date=DATE)))
            self.assertEqual("trip2", repository.get_delivery_run_sheet_for_driver("other-dispatch", DATE, "D001", "trip2").trip_no)
            with self.assertRaisesRegex(ValueError, "Explicit trip_no"):
                repository.get_delivery_run_sheet_for_driver(DATE, DATE, "D001")

    def test_duplicate_same_trip_cannot_bypass_with_dispatch_date(self):
        for repository in self.repositories():
            repository.create_delivery_run_sheet(snapshot("DRS-A", "trip1"))
            with self.assertRaisesRegex(ValueError, "already exists"):
                repository.create_delivery_run_sheet(replace(snapshot("DRS-B", "trip1"), dispatch_date="2026-09-10"))

    def test_legacy_then_trip1_overlap_rejected(self):
        self.assert_overlap("trip1", legacy_first=True)

    def test_legacy_then_trip2_overlap_rejected(self):
        self.assert_overlap("trip2", legacy_first=True)

    def test_trip_then_legacy_overlap_rejected(self):
        self.assert_overlap("trip1", legacy_first=False)

    def assert_overlap(self, trip, legacy_first):
        for repository in self.repositories():
            legacy, scoped = snapshot("LEGACY"), snapshot("SCOPED", trip)
            repository.create_delivery_run_sheet(legacy if legacy_first else scoped)
            with self.assertRaisesRegex(ValueError, "already exists"):
                repository.create_delivery_run_sheet(scoped if legacy_first else legacy)

    def test_saved_snapshot_cannot_be_overwritten(self):
        self.assert_immutable("SAVED", "OPEN")

    def test_closed_snapshot_cannot_be_overwritten(self):
        self.assert_immutable("SAVED", "CLOSED")

    def test_generated_legacy_snapshot_cannot_be_overwritten(self):
        self.assert_immutable("GENERATED", "OPEN", scope=None)

    def assert_immutable(self, status, execution, scope="trip1"):
        for repository in self.repositories():
            original = snapshot(status=status, execution_status=execution, trip_no=scope)
            repository.create_delivery_run_sheet(original)
            original.vehicle_rego_snapshot = "MUTATED INPUT"
            read = repository.get_delivery_run_sheet(original.run_sheet_id)
            self.assertEqual("ORIGINAL", read.vehicle_rego_snapshot)
            read.trips[0].orders[0].company_name_snapshot = "MUTATED READ"
            with self.assertRaisesRegex(ValueError, "immutable"):
                repository.upsert_delivery_run_sheet(read)
            stored = repository.get_delivery_run_sheet(original.run_sheet_id)
            self.assertEqual("Historical Customer", stored.trips[0].orders[0].company_name_snapshot)

    def test_new_header_row_scope_mismatch_rejected(self):
        for repository in self.repositories():
            invalid = snapshot(trip_no="trip1")
            invalid.trips[0].orders[0].trip_no = "trip2"
            with self.assertRaises(ValueError):
                repository.create_delivery_run_sheet(invalid)
            with self.assertRaises(ValueError):
                repository.create_delivery_run_sheet(replace(snapshot(trip_no="trip1"), trips=[]))

    def test_same_driver_same_vehicle_across_trips_allowed(self):
        for repository in self.repositories():
            for trip in ("trip1", "trip2"):
                assignment, conflict = repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", trip)
                self.assertIsNone(conflict)
                self.assertEqual(trip, assignment.trip_no)
            self.assertEqual(2, len(repository.list_delivery_trip_vehicle_assignments(DATE)))

    def test_same_trip_vehicle_rejected_for_other_driver_and_dispatch(self):
        for repository in self.repositories():
            repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", "trip1")
            assignment, conflict = repository.upsert_delivery_trip_vehicle_assignment("2026-09-01", DATE, "D002", "V001", "trip1")
            self.assertIsNone(assignment)
            self.assertEqual("D001", conflict)
            self.assertIsNone(repository.get_delivery_trip_vehicle_assignment(DATE, "D002", "trip1"))

    def test_different_trip_same_vehicle_for_other_driver_allowed(self):
        for repository in self.repositories():
            repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", "trip1")
            assignment, conflict = repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D002", "V001", "trip2")
            self.assertIsNone(conflict)
            self.assertEqual("D002", assignment.driver_id)

    def test_vehicle_scope_required_and_not_null(self):
        for repository in self.repositories():
            for invalid in (None, "", "trip3"):
                with self.assertRaises(ValueError):
                    repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", invalid)
            self.assertEqual([], repository.list_delivery_trip_vehicle_assignments(DATE))

    def test_clear_trip_does_not_use_null_fallback_or_touch_sibling(self):
        for repository in self.repositories():
            repository.upsert_delivery_workspace_vehicle_assignment(DATE, DATE, "D001", "V001")
            self.assertIsNone(repository.get_delivery_trip_vehicle_assignment(DATE, "D001", "trip1"))
            for trip in ("trip1", "trip2"):
                repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", trip)
            self.assertTrue(repository.remove_delivery_trip_vehicle_assignment(DATE, "D001", "trip1"))
            self.assertIsNone(repository.get_delivery_trip_vehicle_assignment(DATE, "D001", "trip1"))
            self.assertIsNotNone(repository.get_delivery_trip_vehicle_assignment(DATE, "D001", "trip2"))

    def test_legacy_day_adapter_rejects_divergent_trip_selections(self):
        for repository in self.repositories():
            repository.upsert_delivery_workspace_vehicle_assignment(DATE, DATE, "D001", "V001")
            repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V002", "trip2")
            with self.assertRaisesRegex(ValueError, "Explicit trip_no"):
                repository.list_driver_vehicle_assignments_for_delivery_date(DATE)
            with self.assertRaises(ValueError):
                repository.upsert_delivery_workspace_vehicle_assignment(DATE, DATE, "D001", "V001")

    def test_current_day_adapter_preserves_equal_migration_projection(self):
        path = self.old_database(("trip1", "trip2"))
        migrate_delivery_per_trip(path, apply=True, yes=True)
        repository = SQLiteManualDispatchRepository(path)
        repository.upsert_delivery_workspace_vehicle_assignment("other", DATE, "D001", "V002")
        self.assertEqual("V002", repository.list_driver_vehicle_assignments_for_delivery_date(DATE)[0].vehicle_id)
        self.assertEqual(["V002", "V002"], [row.vehicle_id for row in repository.list_delivery_trip_vehicle_assignments(DATE)])

    def test_db_indexes_enforce_trip_vehicle_and_legacy_null_uniqueness(self):
        with self.connection() as connection:
            connection.execute("INSERT INTO manual_driver_vehicle_assignments (dispatch_date,delivery_date,driver_id,vehicle_id,trip_no) VALUES (?,?,'D001','V001','trip1')", (DATE, DATE))
            for driver, vehicle in (("D001", "V002"), ("D002", "V001")):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO manual_driver_vehicle_assignments (dispatch_date,delivery_date,driver_id,vehicle_id,trip_no) VALUES ('other',?,?,?,'trip1')", (DATE, driver, vehicle))
            connection.execute("INSERT INTO manual_driver_vehicle_assignments (dispatch_date,delivery_date,driver_id,vehicle_id) VALUES (?,?,'D001','V001')", (DATE, DATE))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO manual_driver_vehicle_assignments (dispatch_date,delivery_date,driver_id,vehicle_id) VALUES ('other',?,'D001','V001')", (DATE,))

    def test_concurrent_same_trip_claim_has_one_winner(self):
        def claim(driver):
            repository = SQLiteManualDispatchRepository(self.db_path)
            return repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, driver, "V001", "trip1")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ("D001", "D002")))
        self.assertEqual(1, sum(assignment is not None for assignment, _ in results))
        self.assertEqual(1, sum(conflict is not None for _, conflict in results))

    def test_partial_legacy_database_startup_does_not_mark_capability(self):
        path = self.directory / "partial-legacy.sqlite3"
        with self.connection(path) as connection:
            connection.executescript(OLD_RUN_SHEET_DDL)
        initialize_database(path)
        initialize_database(path)
        with self.connection(path) as connection:
            self.assertNotIn("trip_no", {row["name"] for row in connection.execute("PRAGMA table_info(delivery_run_sheets)")})
            self.assertFalse(delivery_per_trip_schema_status(connection)["ready"])

    def test_unsupported_capability_version_is_not_downgraded(self):
        with self.connection() as connection:
            connection.execute("UPDATE manual_dispatch_schema_capabilities SET version = 99")
        before = self.db_path.read_bytes()
        self.assertFalse(self.sqlite.get_delivery_per_trip_schema_status()["ready"])
        self.assertTrue(self.sqlite.get_workspace_migration_status()["delivery_ready"])
        with self.assertRaises(DeliveryPerTripMigrationError):
            migrate_delivery_per_trip(self.db_path, apply=True, yes=True)
        self.assertEqual(before, self.db_path.read_bytes())

    def test_capability_checks_required_columns_and_run_sheet_primary_key(self):
        with self.connection() as connection:
            connection.execute("ALTER TABLE delivery_run_sheets RENAME COLUMN vehicle_rego_snapshot TO wrong_rego_column")
            status = delivery_per_trip_schema_status(connection)
            self.assertTrue(any("missing columns vehicle_rego_snapshot" in issue for issue in status["issues"]))
            connection.execute("DROP TABLE delivery_run_sheets")
            connection.execute(delivery_per_trip._table_ddl("delivery_run_sheets").replace("run_sheet_id TEXT PRIMARY KEY", "run_sheet_id TEXT"))
            for definition in INVARIANT_INDEX_DEFINITIONS:
                if definition["table"] == "delivery_run_sheets":
                    connection.execute(f"CREATE UNIQUE INDEX {definition['name']} ON delivery_run_sheets ({', '.join(definition['columns'])}) WHERE {definition['where']}")
            status = delivery_per_trip_schema_status(connection)
            self.assertIn("delivery_run_sheets: incorrect primary key", status["issues"])

    def test_capability_checks_trip_nullable_type_and_allowed_values(self):
        original = delivery_per_trip._table_ddl("manual_driver_vehicle_assignments")
        for wrong_ddl, issue in (
            (original.replace("trip_no TEXT,", "trip_no TEXT NOT NULL,"), "nullable TEXT"),
            (original.replace("trip_no TEXT,", "trip_no INTEGER,"), "nullable TEXT"),
            (original.replace("CHECK(trip_no IS NULL OR trip_no IN ('trip1', 'trip2')),", ""), "value constraint"),
            (original.replace("'trip1', 'trip2'", "'TRIP1', 'TRIP2'"), "value constraint"),
        ):
            with self.subTest(issue=issue):
                with self.connection() as connection:
                    connection.execute("DROP TABLE manual_driver_vehicle_assignments")
                    connection.execute(wrong_ddl)
                    for definition in INVARIANT_INDEX_DEFINITIONS:
                        if definition["table"] == "manual_driver_vehicle_assignments":
                            connection.execute(f"CREATE UNIQUE INDEX {definition['name']} ON manual_driver_vehicle_assignments ({', '.join(definition['columns'])}) WHERE {definition['where']}")
                    status = delivery_per_trip_schema_status(connection)
                    self.assertFalse(status["ready"])
                    self.assertTrue(any(issue in item for item in status["issues"]))

    def test_unknown_old_unique_constraint_blocks_preflight_without_writes(self):
        path = self.old_database(("trip1",))
        with self.connection(path) as connection:
            connection.execute("CREATE UNIQUE INDEX custom_day_identity ON delivery_run_sheets (delivery_date, driver_id)")
        before = path.read_bytes()
        with self.assertRaises(DeliveryPerTripMigrationError) as caught:
            migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertTrue(any("custom_day_identity" in str(item) for item in caught.exception.report["conflicts"]))
        self.assertEqual(before, path.read_bytes())

    def test_missing_old_columns_fail_preflight_with_a_report_without_writes(self):
        path = self.old_database(("trip1",))
        with self.connection(path) as connection:
            connection.execute("ALTER TABLE delivery_run_sheets RENAME COLUMN legacy_summary_id TO unknown_marker")
        before = path.read_bytes()
        with self.assertRaises(DeliveryPerTripMigrationError) as caught:
            migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertTrue(any("unexpected old columns" in str(item) for item in caught.exception.report["conflicts"]))
        self.assertEqual(before, path.read_bytes())

    def test_unresolved_legacy_final_summary_blocks_vehicle_inference(self):
        for state in ("GENERATED", "SAVED"):
            path = self.old_database(("trip1", "trip2"))
            with self.connection(path) as connection:
                connection.execute(
                    "INSERT INTO final_trip_summaries (summary_id, dispatch_date, delivery_date, driver_id, driver_name_snapshot, status, saved_at) "
                    "VALUES ('OLD-SUMMARY', ?, ?, 'D001', 'Original Driver', ?, 'original-saved')", (DATE, DATE, state)
                )
                connection.execute(
                    "INSERT INTO final_trip_summary_rows (row_id, summary_id, trip_no, row_no, task_type, task_id) "
                    "VALUES ('OLD-SUMMARY-ROW', 'OLD-SUMMARY', 'trip1', 1, 'ORDER', 'ORD-001')"
                )
            before = path.read_bytes()
            with self.assertRaises(DeliveryPerTripMigrationError) as caught:
                migrate_delivery_per_trip(path, apply=True, yes=True)
            self.assertTrue(any("Unresolved legacy Delivery Final Trip Summary" in str(item) for item in caught.exception.report["conflicts"]))
            self.assertEqual(before, path.read_bytes())

    def test_seed_verification_failure_rolls_back_and_backup_is_recoverable(self):
        path = self.old_database(("trip1",))
        before = path.read_bytes()
        verify = delivery_per_trip._verify_preservation

        def damage_seed(connection, snapshots, vehicles, classification):
            connection.execute("UPDATE manual_driver_vehicle_assignments SET vehicle_id = 'V002' WHERE trip_no = 'trip1'")
            verify(connection, snapshots, vehicles, classification)

        with patch("backend.db.delivery_per_trip._verify_preservation", side_effect=damage_seed):
            with self.assertRaisesRegex(RuntimeError, "classified vehicle seeds"):
                migrate_delivery_per_trip(path, apply=True, yes=True)
        self.assertEqual(before, path.read_bytes())
        backups = list(self.directory.glob(path.stem + "-pre-trip-*.sqlite3"))
        self.assertEqual(1, len(backups))
        with self.connection(backups[0]) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertNotIn("trip_no", {row["name"] for row in connection.execute("PRAGMA table_info(manual_driver_vehicle_assignments)")})
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM manual_driver_vehicle_assignments").fetchone()[0])

    def test_order_reservation_lookup_rejects_multiple_trip_headers(self):
        for repository in self.repositories():
            with self.subTest(repository=type(repository).__name__):
                repository.create_delivery_run_sheet(snapshot("TRIP-1", "trip1"))
                repository.create_delivery_run_sheet(snapshot("TRIP-2", "trip2"))
                with self.assertRaisesRegex(ValueError, "reservation integrity error"):
                    repository.get_delivery_run_sheet_reserving_order("ORD-001")

    def test_order_reservation_lookup_ignores_closed_trip_history(self):
        for repository in self.repositories():
            with self.subTest(repository=type(repository).__name__):
                repository.create_delivery_run_sheet(snapshot(
                    "CLOSED-TRIP", "trip1", status="SAVED", execution_status="CLOSED"
                ))
                repository.create_delivery_run_sheet(snapshot("OPEN-TRIP", "trip2"))
                self.assertEqual(
                    "OPEN-TRIP",
                    repository.get_delivery_run_sheet_reserving_order("ORD-001").run_sheet_id,
                )

    def test_snapshot_list_lookup_and_reservation_reads_do_not_mutate_storage(self):
        for repository in self.repositories():
            repository.create_delivery_run_sheet(snapshot(status="SAVED", trip_no="trip1"))
            reads = [repository.list_delivery_run_sheets()[0],
                     repository.get_delivery_run_sheet_reserving_order("ORD-001"),
                     repository.get_delivery_run_sheet_for_driver(None, DATE, "D001", "trip1")]
            for read in reads:
                read.trips[0].orders[0].task_type = "OPSHOP_PICKUP"
            self.assertEqual("ORDER", repository.get_delivery_run_sheet("DRS-1").trips[0].orders[0].task_type)

    def test_global_snapshot_row_and_legacy_marker_uniqueness_parity(self):
        for repository in self.repositories():
            original = snapshot("ORIGINAL", status="SAVED")
            original.legacy_summary_id = "OLD-SUMMARY"
            repository.create_delivery_run_sheet(original)
            duplicate = snapshot("DUPLICATE", "trip1", driver="D002")
            duplicate.trips[0].orders[0].row_id = original.trips[0].orders[0].row_id
            with self.assertRaises((ValueError, sqlite3.IntegrityError)):
                repository.create_delivery_run_sheet(duplicate)
            self.assertIsNone(repository.get_delivery_run_sheet("DUPLICATE"))
            duplicate = replace(snapshot("DUPLICATE-MARKER", driver="D002"), legacy_summary_id="OLD-SUMMARY")
            with self.assertRaises((ValueError, sqlite3.IntegrityError)):
                repository.create_delivery_run_sheet(duplicate)

    def test_per_trip_vehicle_lock_preserves_sibling_scope_and_snapshot(self):
        for repository in self.repositories():
            for index, (state, execution) in enumerate((("GENERATED", "OPEN"), ("SAVED", "OPEN"), ("SAVED", "CLOSED"))):
                day = f"2026-09-{15 + index}"
                repository.upsert_delivery_trip_vehicle_assignment(day, day, "D001", "V001", "trip1")
                sheet = replace(snapshot(f"LOCK-{index}", "trip1", state, execution), delivery_date=day)
                repository.create_delivery_run_sheet(sheet)
                with self.assertRaisesRegex(ValueError, "locks"):
                    repository.upsert_delivery_trip_vehicle_assignment("other", day, "D001", "V002", "trip1")
                with self.assertRaisesRegex(ValueError, "locks"):
                    repository.remove_delivery_trip_vehicle_assignment(day, "D001", "trip1")
                self.assertEqual("D001", repository.upsert_delivery_trip_vehicle_assignment(day, day, "D002", "V001", "trip1")[1])
                self.assertIsNone(repository.upsert_delivery_trip_vehicle_assignment(day, day, "D001", "V001", "trip2")[1])
                self.assertEqual(state == "SAVED", repository.has_saved_delivery_run_sheet("other", "D001", day, "trip1"))
                self.assertFalse(repository.has_saved_delivery_run_sheet("other", "D001", day, "trip2"))
                self.assertEqual("ORIGINAL", repository.get_delivery_run_sheet(sheet.run_sheet_id).vehicle_rego_snapshot)

    def test_legacy_combined_vehicle_lock_covers_both_explicit_trips(self):
        for repository in self.repositories():
            repository.create_delivery_run_sheet(snapshot(status="SAVED"))
            for trip in ("trip1", "trip2"):
                with self.assertRaisesRegex(ValueError, "locks"):
                    repository.upsert_delivery_trip_vehicle_assignment(DATE, DATE, "D001", "V001", trip)
                with self.assertRaisesRegex(ValueError, "locks"):
                    repository.remove_delivery_trip_vehicle_assignment(DATE, "D001", trip)

    def test_protected_path_is_refused_before_any_sqlite_open(self):
        with patch("backend.db.delivery_per_trip.sqlite3.connect") as connect:
            with self.assertRaisesRegex(DeliveryPerTripMigrationError, "protected business paths"):
                migrate_delivery_per_trip(Path.cwd() / "data/manual_dispatch.sqlite3", apply=True, yes=True)
            connect.assert_not_called()

    def test_cli_dry_run_and_apply_on_new_fixture(self):
        path = self.old_database(("trip1",))
        with patch("builtins.print"):
            self.assertEqual(0, migration_main(["--db-path", str(path)]))
            self.assertEqual(0, migration_main(["--db-path", str(path), "--apply", "--yes"]))
        self.assertTrue(inspect_delivery_per_trip_migration(path)["already_ready"])


if __name__ == "__main__":
    unittest.main()
