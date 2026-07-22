import contextlib
import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.api.manual_dispatch_routes.common import ENABLE_LEGACY_MUTATIONS_ENV
from backend.db.connection import initialize_database
from backend.db.invariants import INVARIANT_INDEX_DEFINITIONS
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client
from tools.migrate_database_invariants import (
    InvariantMigrationBlockedError,
    inspect_database_invariants,
    migrate_database_invariants,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class H5LegacyMutationCutoverTest(unittest.TestCase):
    @unittest.skipIf(TestClient is None, "FastAPI TestClient is unavailable")
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"h5-legacy-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self.db_path = self.temp_dir / "legacy-cutover.sqlite3"
        with patch.dict(
            os.environ,
            {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"},
        ):
            initialize_database(self.db_path)
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        authenticate_test_client(self.client, self.service)

    def tearDown(self):
        self.api_module.service = self.original_service
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_mutations_are_default_disabled_but_reads_remain(self):
        mutation_routes = (
            ("POST", "/api/manual-dispatch/assign"),
            ("POST", "/api/manual-dispatch/unassign"),
            ("POST", "/api/manual-dispatch/driver-vehicle"),
            ("POST", "/api/manual-dispatch/orders"),
            ("PATCH", "/api/manual-dispatch/orders/ORD-001"),
            ("POST", "/api/manual-dispatch/orders/ORD-001/cancel"),
            ("POST", "/api/manual-dispatch/drivers"),
            ("PATCH", "/api/manual-dispatch/drivers/D001"),
            ("DELETE", "/api/manual-dispatch/drivers/D001"),
            ("POST", "/api/manual-dispatch/vehicles"),
            ("PATCH", "/api/manual-dispatch/vehicles/V001"),
            ("DELETE", "/api/manual-dispatch/vehicles/V001"),
            ("POST", "/api/manual-dispatch/final-summaries"),
            ("POST", "/api/manual-dispatch/final-summaries/generated"),
            ("POST", "/api/manual-dispatch/final-summaries/FTS-1/save"),
            ("POST", "/api/manual-dispatch/final-summaries/FTS-1/cancel-generated"),
            ("POST", "/api/manual-dispatch/orders/import-attache-pdf-commit"),
        )
        with patch.dict(os.environ, {ENABLE_LEGACY_MUTATIONS_ENV: "false"}):
            for method, path in mutation_routes:
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, path, json={})
                    self.assertEqual(404, response.status_code)
                    self.assertEqual(
                        "Legacy mutation endpoint is disabled.",
                        response.json()["detail"],
                    )

            board = self.client.get(
                "/api/manual-dispatch/board",
                params={"dispatch_date": "2026-04-06"},
            )
            summaries = self.client.get(
                "/api/manual-dispatch/final-summaries",
                params={"dispatch_date": "2026-04-06"},
            )

        self.assertEqual(200, board.status_code)
        self.assertEqual(200, summaries.status_code)

    def test_explicit_enable_restores_legacy_mutation_compatibility(self):
        with patch.dict(os.environ, {ENABLE_LEGACY_MUTATIONS_ENV: "true"}):
            response = self.client.post(
                "/api/manual-dispatch/assign",
                json={
                    "dispatch_date": "2026-04-06",
                    "task_type": "ORDER",
                    "task_id": "ORD-001",
                    "driver_id": "D001",
                    "trip_no": "trip1",
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("ORD-001", response.json()["task_id"])

    def test_current_workspace_mutations_are_unaffected(self):
        with patch.dict(os.environ, {ENABLE_LEGACY_MUTATIONS_ENV: "false"}):
            response = self.client.post(
                "/api/manual-dispatch/delivery/assignments",
                json={
                    "dispatch_date": "2026-04-06",
                    "order_id": "ORD-001",
                    "driver_id": "D001",
                    "trip_no": "trip1",
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("ORD-001", response.json()["assignments"][0]["task_id"])

    def test_deployment_examples_keep_legacy_mutations_disabled(self):
        for path in (".env.example", ".env.nas.example", "docker-compose.yml"):
            with self.subTest(path=path):
                content = Path(path).read_text(encoding="utf-8")
                self.assertIn("MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS", content)
                self.assertIn("false", content)


class H5DatabaseInvariantMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"h5-invariants-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self.db_path = self.temp_dir / "pre-migration.sqlite3"
        with patch.dict(
            os.environ,
            {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"},
        ):
            initialize_database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fresh_database_has_all_service_identity_constraints(self):
        report = inspect_database_invariants(self.db_path)

        self.assertEqual("ok", report["integrity_before"])
        self.assertEqual([], report["conflicts"])
        self.assertEqual([], report["missing_indexes"])

    def test_dry_run_is_read_only_and_reports_proposed_indexes(self):
        self._drop_invariant_indexes()
        before = self.db_path.read_bytes()

        report = migrate_database_invariants(self.db_path)

        self.assertEqual("dry-run", report["mode"])
        self.assertIsNone(report["backup_path"])
        self.assertEqual(
            {item["name"] for item in INVARIANT_INDEX_DEFINITIONS},
            set(report["missing_indexes"]),
        )
        self.assertEqual(before, self.db_path.read_bytes())

    def test_apply_requires_yes_and_creates_verified_non_overwriting_backup(self):
        self._drop_invariant_indexes()
        with self.assertRaisesRegex(
            InvariantMigrationBlockedError,
            "Apply requires both --apply and --yes",
        ):
            migrate_database_invariants(self.db_path, apply=True)

        first = migrate_database_invariants(self.db_path, apply=True, yes=True)
        first_backup = Path(first["backup_path"])
        second = migrate_database_invariants(self.db_path, apply=True, yes=True)
        second_backup = Path(second["backup_path"])

        self.assertTrue(first_backup.exists())
        self.assertTrue(second_backup.exists())
        self.assertNotEqual(first_backup, second_backup)
        self.assertEqual("ok", first["integrity_before"])
        self.assertEqual("ok", first["integrity_after"])
        self.assertEqual([], first["missing_indexes"])
        with self._connection(first_backup) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

    def test_duplicate_audit_reports_conflicts_and_apply_refuses_to_delete(self):
        self._drop_invariant_indexes()
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT INTO manual_dispatch_assignments (
                    assignment_id, dispatch_date, task_type, task_id,
                    driver_id, trip_no
                ) VALUES (?, ?, 'ORDER', 'ORD-001', ?, 'trip1')
                """,
                (
                    ("H5-DUPLICATE-1", "2026-04-06", "D001"),
                    ("H5-DUPLICATE-2", "2026-04-07", "D002"),
                ),
            )

        report = inspect_database_invariants(self.db_path)

        self.assertTrue(
            any(
                conflict["invariant"]
                == "idx_manual_dispatch_assignments_task_identity"
                for conflict in report["conflicts"]
            )
        )
        with self.assertRaisesRegex(
            InvariantMigrationBlockedError,
            "Duplicate conflicts must be resolved",
        ):
            migrate_database_invariants(self.db_path, apply=True, yes=True)
        self.assertFalse((self.temp_dir / "backups").exists())
        with self._connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) FROM manual_dispatch_assignments
                WHERE task_type = 'ORDER' AND task_id = 'ORD-001'
                """
            ).fetchone()[0]
        self.assertEqual(2, count)

    def test_apply_failure_rolls_back_indexes_and_leaves_recoverable_backup(self):
        self._drop_invariant_indexes()

        def fail_after_first_index(connection):
            definition = INVARIANT_INDEX_DEFINITIONS[0]
            connection.execute(
                f"CREATE UNIQUE INDEX {definition['name']} "
                f"ON {definition['table']} ({', '.join(definition['columns'])})"
            )
            raise RuntimeError("simulated invariant migration failure")

        with patch(
            "tools.migrate_database_invariants.create_invariant_indexes",
            side_effect=fail_after_first_index,
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated invariant"):
                migrate_database_invariants(self.db_path, apply=True, yes=True)

        report = inspect_database_invariants(self.db_path)
        backups = list((self.temp_dir / "backups").glob("*.sqlite3"))
        self.assertEqual(
            {item["name"] for item in INVARIANT_INDEX_DEFINITIONS},
            set(report["missing_indexes"]),
        )
        self.assertEqual(1, len(backups))
        with self._connection(backups[0]) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

    def test_constraints_use_business_dates_not_dispatch_provenance(self):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO manual_dispatch_assignments (
                    assignment_id, dispatch_date, task_type, task_id,
                    driver_id, trip_no
                ) VALUES ('H5-ASSIGNMENT-1', '2026-04-06', 'ORDER', 'ORD-001',
                          'D001', 'trip1')
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO manual_dispatch_assignments (
                        assignment_id, dispatch_date, task_type, task_id,
                        driver_id, trip_no
                    ) VALUES ('H5-ASSIGNMENT-2', '2026-04-07', 'ORDER', 'ORD-001',
                              'D002', 'trip1')
                    """
                )
            self._assert_run_sheet_identity_constraint(connection)
            self._assert_collection_identity_constraint(connection)
            self._assert_vehicle_identity_constraints(connection)

    def _assert_run_sheet_identity_constraint(self, connection):
        self._insert_run_sheet(connection, "H5-RUN-1", "2026-04-06")
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_run_sheet(connection, "H5-RUN-2", "2026-04-07")

    def _assert_collection_identity_constraint(self, connection):
        self._insert_collection(connection, "H5-COLLECTION-1", "2026-04-06")
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_collection(connection, "H5-COLLECTION-2", "2026-04-07")

    def _assert_vehicle_identity_constraints(self, connection):
        connection.execute(
            """
            INSERT INTO manual_driver_vehicle_assignments (
                dispatch_date, delivery_date, driver_id, vehicle_id
            ) VALUES ('2026-04-06', '2026-04-08', 'D001', 'V001')
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO manual_driver_vehicle_assignments (
                    dispatch_date, delivery_date, driver_id, vehicle_id
                ) VALUES ('2026-04-07', '2026-04-08', 'D001', 'V002')
                """
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO manual_driver_vehicle_assignments (
                    dispatch_date, delivery_date, driver_id, vehicle_id
                ) VALUES ('2026-04-07', '2026-04-08', 'D002', 'V001')
                """
            )

    def _insert_run_sheet(self, connection, run_sheet_id, dispatch_date):
        connection.execute(
            """
            INSERT INTO delivery_run_sheets (
                run_sheet_id, dispatch_date, delivery_date, driver_id,
                driver_name_snapshot, status, generated_at
            ) VALUES (?, ?, '2026-04-09', 'D001', 'Driver One',
                      'GENERATED', '2026-04-01T00:00:00')
            """,
            (run_sheet_id, dispatch_date),
        )

    def _insert_collection(self, connection, collection_id, dispatch_date):
        connection.execute(
            """
            INSERT INTO opshop_pickup_collections (
                collection_id, dispatch_date, pickup_date, driver_id,
                driver_name_snapshot, status, generated_at
            ) VALUES (?, ?, '2026-04-10', 'D001', 'Driver One',
                      'GENERATED', '2026-04-01T00:00:00')
            """,
            (collection_id, dispatch_date),
        )

    def _drop_invariant_indexes(self):
        with self._connection() as connection:
            for definition in INVARIANT_INDEX_DEFINITIONS:
                connection.execute(f"DROP INDEX {definition['name']}")

    @contextlib.contextmanager
    def _connection(self, path=None):
        with contextlib.closing(sqlite3.connect(path or self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
