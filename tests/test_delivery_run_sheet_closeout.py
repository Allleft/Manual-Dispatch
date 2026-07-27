import importlib
import os
import shutil
import sqlite3
import threading
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from backend.db.connection import initialize_database
from backend.errors import StateChangedConflictError
from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CloseDeliveryRunSheetRequest,
    CloseDeliveryRunSheetRowRequest,
    Driver,
    GenerateDeliveryRunSheetRequest,
    OperatorAccountIdentity,
    Order,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


DELIVERY_DATE = "2026-07-28"
NEXT_DELIVERY_DATE = "2026-07-29"


class RecordingLogbook:
    def __init__(self, fail=False):
        self.entries = []
        self.fail = fail

    def record(self, **entry):
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.entries.append(entry)


class FailingOutcomeInMemoryRepository(InMemoryManualDispatchRepository):
    def insert_delivery_run_sheet_outcomes(self, outcomes):
        super().insert_delivery_run_sheet_outcomes(outcomes)
        raise RuntimeError("injected outcome persistence failure")


class FailingOutcomeSQLiteRepository(SQLiteManualDispatchRepository):
    def insert_delivery_run_sheet_outcomes(self, outcomes):
        super().insert_delivery_run_sheet_outcomes(outcomes)
        raise RuntimeError("injected outcome persistence failure")


class DeliveryRunSheetCloseoutTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"closeout-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normal_two_delivered_two_returned_has_repository_parity(self):
        repositories = (
            InMemoryManualDispatchRepository(),
            SQLiteManualDispatchRepository(self.temp_dir / "parity.sqlite3"),
        )
        for repository in repositories:
            with self.subTest(repository=type(repository).__name__):
                service, identity, run_sheet, logbook = self._build_saved_sheet(
                    repository
                )
                original_snapshot = [
                    (
                        row.row_id,
                        row.row_no,
                        row.trip_no,
                        row.order_id_snapshot,
                        row.company_name_snapshot,
                    )
                    for trip in run_sheet.trips
                    for row in trip.orders
                ]
                self.assertEqual(
                    {"CLOSE-ORD-1", "CLOSE-ORD-2", "CLOSE-ORD-3", "CLOSE-ORD-4"},
                    repository.list_reserved_delivery_order_ids(),
                )

                closed = service.close_saved_delivery_run_sheet(
                    run_sheet.run_sheet_id,
                    self._valid_request(run_sheet),
                    identity,
                )

                self.assertEqual("CLOSED", closed.execution_status)
                self.assertEqual(2, closed.closeout_summary.delivered_count)
                self.assertEqual(2, closed.closeout_summary.returned_to_pool_count)
                self.assertEqual(4, len(closed.outcomes))
                self.assertEqual(
                    "Left at reception",
                    next(
                        outcome.note
                        for outcome in closed.outcomes
                        if outcome.order_id == "CLOSE-ORD-1"
                    ),
                )
                self.assertEqual(set(), repository.list_reserved_delivery_order_ids())
                self.assertEqual(
                    set(),
                    repository.list_globally_assigned_delivery_order_ids(),
                )
                for order_number in (1, 2):
                    self.assertEqual(
                        "FINALIZED",
                        repository.get_order(f"CLOSE-ORD-{order_number}").status,
                    )
                for order_number in (3, 4):
                    returned = repository.get_order(f"CLOSE-ORD-{order_number}")
                    self.assertEqual("ACTIVE", returned.status)
                    self.assertEqual(NEXT_DELIVERY_DATE, returned.delivery_date)
                self.assertEqual(
                    {"CLOSE-ORD-3", "CLOSE-ORD-4"},
                    {
                        order.order_id
                        for order in repository.list_orders(NEXT_DELIVERY_DATE)
                    },
                )
                self.assertEqual(
                    original_snapshot,
                    [
                        (
                            row.row_id,
                            row.row_no,
                            row.trip_no,
                            row.order_id_snapshot,
                            row.company_name_snapshot,
                        )
                        for trip in closed.trips
                        for row in trip.orders
                    ],
                )
                self.assertEqual(
                    run_sheet.run_sheet_id,
                    service.get_saved_delivery_run_sheet_for_export(
                        run_sheet.run_sheet_id
                    ).run_sheet_id,
                )
                self.assertIn(
                    run_sheet.run_sheet_id,
                    {
                        item.run_sheet_id
                        for item in service.list_delivery_run_sheets(
                            delivery_date=DELIVERY_DATE,
                            status="SAVED",
                        )
                    },
                )
                actions = [entry["action"] for entry in logbook.entries]
                self.assertIn("DELIVERY_RUN_SHEET_CLOSED", actions)
                self.assertEqual(2, actions.count("DELIVERY_ORDER_DELIVERED"))
                self.assertEqual(
                    2,
                    actions.count("DELIVERY_ORDER_RETURNED_TO_POOL"),
                )

                before_repeat = self._business_snapshot(repository, closed.run_sheet_id)
                successful_audits_before = sum(
                    entry["result"] == "SUCCESS" for entry in logbook.entries
                )
                with self.assertRaises(StateChangedConflictError):
                    service.close_saved_delivery_run_sheet(
                        closed.run_sheet_id,
                        self._valid_request(closed),
                        identity,
                    )
                different_request = self._replace_request_row(
                    closed,
                    0,
                    outcome="RETURN_TO_POOL",
                    reason_code="TIME_RAN_OUT",
                    note="Changed after close",
                    next_delivery_date=NEXT_DELIVERY_DATE,
                )
                with self.assertRaises(StateChangedConflictError):
                    service.close_saved_delivery_run_sheet(
                        closed.run_sheet_id,
                        different_request,
                        identity,
                    )
                self.assertEqual(
                    before_repeat,
                    self._business_snapshot(repository, closed.run_sheet_id),
                )
                self.assertEqual(
                    successful_audits_before,
                    sum(
                        entry["result"] == "SUCCESS"
                        for entry in logbook.entries
                    ),
                )

    def test_validation_matrix_changes_nothing(self):
        cases = {
            "missing_row": lambda sheet: CloseDeliveryRunSheetRequest(
                rows=self._valid_request(sheet).rows[:-1]
            ),
            "duplicate_row": lambda sheet: CloseDeliveryRunSheetRequest(
                rows=[
                    self._valid_request(sheet).rows[0],
                    self._valid_request(sheet).rows[0],
                    *self._valid_request(sheet).rows[2:],
                ]
            ),
            "foreign_row": lambda sheet: replace(
                self._valid_request(sheet),
                rows=[
                    replace(
                        self._valid_request(sheet).rows[0],
                        run_sheet_row_id="FOREIGN-ROW",
                    ),
                    *self._valid_request(sheet).rows[1:],
                ],
            ),
            "invalid_outcome": lambda sheet: self._replace_request_row(
                sheet, 0, outcome="PARTIAL"
            ),
            "delivered_next_date": lambda sheet: self._replace_request_row(
                sheet, 0, next_delivery_date=NEXT_DELIVERY_DATE
            ),
            "missing_reason": lambda sheet: self._replace_request_row(
                sheet, 2, reason_code=None
            ),
            "invalid_reason": lambda sheet: self._replace_request_row(
                sheet, 2, reason_code="NOT_ALLOWED"
            ),
            "missing_next_date": lambda sheet: self._replace_request_row(
                sheet, 2, next_delivery_date=None
            ),
            "other_without_note": lambda sheet: self._replace_request_row(
                sheet, 2, reason_code="OTHER", note=None
            ),
            "same_next_date": lambda sheet: self._replace_request_row(
                sheet, 2, next_delivery_date=DELIVERY_DATE
            ),
            "earlier_next_date": lambda sheet: self._replace_request_row(
                sheet, 2, next_delivery_date="2026-07-27"
            ),
        }
        for name, request_factory in cases.items():
            with self.subTest(case=name):
                repository = InMemoryManualDispatchRepository()
                service, identity, run_sheet, _ = self._build_saved_sheet(repository)
                before = self._business_snapshot(repository, run_sheet.run_sheet_id)
                with self.assertRaises(ValueError):
                    service.close_saved_delivery_run_sheet(
                        run_sheet.run_sheet_id,
                        request_factory(run_sheet),
                        identity,
                    )
                self.assertEqual(
                    before,
                    self._business_snapshot(repository, run_sheet.run_sheet_id),
                )

    def test_generated_and_drifted_sheets_conflict_without_mutation(self):
        repository = InMemoryManualDispatchRepository()
        service, identity, run_sheet, _ = self._build_generated_sheet(repository)
        self.assertEqual(
            {"CLOSE-ORD-1", "CLOSE-ORD-2", "CLOSE-ORD-3", "CLOSE-ORD-4"},
            repository.list_reserved_delivery_order_ids(),
        )
        before = self._business_snapshot(repository, run_sheet.run_sheet_id)
        with self.assertRaises(StateChangedConflictError):
            service.close_saved_delivery_run_sheet(
                run_sheet.run_sheet_id,
                self._valid_request(run_sheet),
                identity,
            )
        self.assertEqual(
            before,
            self._business_snapshot(repository, run_sheet.run_sheet_id),
        )

        drift_cases = {
            "cancelled_order": lambda candidate: candidate.update_order(
                replace(candidate.get_order("CLOSE-ORD-4"), status="CANCELLED")
            ),
            "missing_assignment": lambda candidate: (
                candidate.remove_assignments_for_task("ORDER", "CLOSE-ORD-4")
            ),
            "driver_mismatch": lambda candidate: candidate.upsert_assignment(
                DELIVERY_DATE,
                "ORDER",
                "CLOSE-ORD-4",
                "OTHER-DRIVER",
                "trip2",
            ),
            "trip_mismatch": lambda candidate: candidate.upsert_assignment(
                DELIVERY_DATE,
                "ORDER",
                "CLOSE-ORD-4",
                "CLOSE-DRIVER",
                "trip1",
            ),
        }
        for name, mutate in drift_cases.items():
            with self.subTest(drift=name):
                candidate = InMemoryManualDispatchRepository()
                (
                    candidate_service,
                    candidate_identity,
                    candidate_sheet,
                    _,
                ) = self._build_saved_sheet(candidate)
                mutate(candidate)
                before = self._business_snapshot(
                    candidate,
                    candidate_sheet.run_sheet_id,
                )
                with self.assertRaises(StateChangedConflictError):
                    candidate_service.close_saved_delivery_run_sheet(
                        candidate_sheet.run_sheet_id,
                        self._valid_request(candidate_sheet),
                        candidate_identity,
                    )
                self.assertEqual(
                    before,
                    self._business_snapshot(
                        candidate,
                        candidate_sheet.run_sheet_id,
                    ),
                )

    def test_non_order_snapshot_conflicts_without_mutation(self):
        repository = InMemoryManualDispatchRepository()
        service, identity, run_sheet, _ = self._build_saved_sheet(repository)
        run_sheet.trips[0].orders[0] = replace(
            run_sheet.trips[0].orders[0],
            task_type="OPSHOP_PICKUP",
        )
        before = self._business_snapshot(repository, run_sheet.run_sheet_id)
        with self.assertRaises(StateChangedConflictError):
            service.close_saved_delivery_run_sheet(
                run_sheet.run_sheet_id,
                self._valid_request(run_sheet),
                identity,
            )
        self.assertEqual(
            before,
            self._business_snapshot(repository, run_sheet.run_sheet_id),
        )

    def test_failure_injection_rolls_back_all_business_state(self):
        repositories = (
            FailingOutcomeInMemoryRepository(),
            FailingOutcomeSQLiteRepository(
                self.temp_dir / "failure-injection.sqlite3"
            ),
        )
        for repository in repositories:
            with self.subTest(repository=type(repository).__name__):
                service, identity, run_sheet, _ = self._build_saved_sheet(repository)
                before = self._business_snapshot(repository, run_sheet.run_sheet_id)
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    service.close_saved_delivery_run_sheet(
                        run_sheet.run_sheet_id,
                        self._valid_request(run_sheet),
                        identity,
                    )
                self.assertEqual(
                    before,
                    self._business_snapshot(repository, run_sheet.run_sheet_id),
                )

    def test_audit_failure_does_not_rollback_closeout(self):
        repository = InMemoryManualDispatchRepository()
        logbook = RecordingLogbook(fail=True)
        service, identity, run_sheet, _ = self._build_saved_sheet(
            repository,
            logbook=logbook,
        )
        closed = service.close_saved_delivery_run_sheet(
            run_sheet.run_sheet_id,
            self._valid_request(run_sheet),
            identity,
        )
        self.assertEqual("CLOSED", closed.execution_status)
        self.assertEqual(
            "FINALIZED",
            repository.get_order("CLOSE-ORD-1").status,
        )

    def test_sqlite_concurrent_closeout_has_one_winner_and_one_conflict(self):
        db_path = self.temp_dir / "concurrent.sqlite3"
        repository = SQLiteManualDispatchRepository(db_path)
        service, identity, run_sheet, _ = self._build_saved_sheet(repository)
        services = (
            service,
            ManualDispatchService(
                SQLiteManualDispatchRepository(db_path),
                logbook=RecordingLogbook(),
            ),
        )
        barrier = threading.Barrier(2)
        results = []

        def close(candidate_service):
            barrier.wait()
            try:
                candidate_service.close_saved_delivery_run_sheet(
                    run_sheet.run_sheet_id,
                    self._valid_request(run_sheet),
                    identity,
                )
                results.append("closed")
            except StateChangedConflictError:
                results.append("conflict")

        threads = [
            threading.Thread(target=close, args=(candidate_service,))
            for candidate_service in services
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(["closed", "conflict"], results)
        stored = repository.get_delivery_run_sheet(run_sheet.run_sheet_id)
        self.assertEqual("CLOSED", stored.execution_status)
        self.assertEqual(4, len(stored.outcomes))

    def test_legacy_run_sheets_migrate_open_and_outcome_table_is_created(self):
        legacy_path = self.temp_dir / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE delivery_run_sheets (
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
                    UNIQUE(dispatch_date, delivery_date, driver_id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO delivery_run_sheets (
                    run_sheet_id, dispatch_date, delivery_date, driver_id,
                    driver_name_snapshot, status, generated_at
                ) VALUES ('LEGACY-DRS', '2026-07-28', '2026-07-28',
                    'D-LEGACY', 'Legacy Driver', 'SAVED', '2026-07-28T00:00:00Z')
                """
            )
            connection.commit()

        initialize_database(legacy_path)
        initialize_database(legacy_path)
        with sqlite3.connect(legacy_path) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(delivery_run_sheets)"
                )
            }
            execution_status = connection.execute(
                """
                SELECT execution_status
                FROM delivery_run_sheets
                WHERE run_sheet_id = 'LEGACY-DRS'
                """
            ).fetchone()[0]
            outcome_table = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                    AND name = 'delivery_run_sheet_outcomes'
                """
            ).fetchone()
        self.assertTrue(
            {
                "execution_status",
                "closed_at",
                "closed_by_account_id",
                "closed_by_account_name",
            }.issubset(columns)
        )
        self.assertEqual("OPEN", execution_status)
        self.assertIsNotNone(outcome_table)
        migrated = SQLiteManualDispatchRepository(
            legacy_path
        ).get_delivery_run_sheet("LEGACY-DRS")
        self.assertEqual("OPEN", migrated.execution_status)
        self.assertEqual([], migrated.outcomes)

    def _build_saved_sheet(self, repository, logbook=None):
        service, identity, run_sheet, logbook = self._build_generated_sheet(
            repository,
            logbook=logbook,
        )
        run_sheet = service.save_generated_delivery_run_sheet(
            run_sheet.run_sheet_id,
            SaveGeneratedWorkspaceSnapshotRequest(
                saved_by_account_name=identity.account_name,
                saved_by_account_id=identity.account_id,
            ),
        )
        return service, identity, run_sheet, logbook

    def _build_generated_sheet(self, repository, logbook=None):
        self._reset_repository(repository)
        logbook = logbook or RecordingLogbook()
        service = ManualDispatchService(repository, logbook=logbook)
        repository.create_driver(
            Driver(
                driver_id="CLOSE-DRIVER",
                name="Closeout Driver",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
            )
        )
        for number in range(1, 5):
            repository.create_order(
                Order(
                    order_id=f"CLOSE-ORD-{number}",
                    invoice_number=f"CLOSE-INV-{number}",
                    order_no=None,
                    company_name=f"Closeout Customer {number}",
                    phone=None,
                    delivery_address=f"{number} Test Street",
                    suburb="Dandenong",
                    postcode="3175",
                    delivery_date=DELIVERY_DATE,
                    zone="South East",
                    urgency="normal",
                    preferred_driver_id=None,
                    pallet_quantity=number,
                    loose_bags_quantity=0,
                    start_time=None,
                    end_time=None,
                    note=None,
                )
            )
            repository.upsert_assignment(
                DELIVERY_DATE,
                "ORDER",
                f"CLOSE-ORD-{number}",
                "CLOSE-DRIVER",
                "trip1" if number <= 2 else "trip2",
            )
        account = service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Closeout Operator",
                password="secret123",
                confirm_password="secret123",
            )
        )
        identity = OperatorAccountIdentity(
            account_id=account.account_id,
            account_name=account.account_name,
        )
        run_sheet = service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date=DELIVERY_DATE,
                delivery_date=DELIVERY_DATE,
                driver_id="CLOSE-DRIVER",
            )
        )
        return service, identity, run_sheet, logbook

    @staticmethod
    def _reset_repository(repository):
        if isinstance(repository, InMemoryManualDispatchRepository):
            repository.orders = []
            repository.drivers = []
            repository.vehicles = []
            repository.assignments = []
            repository.driver_vehicle_assignments = []
            repository.final_trip_summaries = []
            repository.delivery_run_sheets = []
            repository.operator_accounts = []

    @staticmethod
    def _valid_request(run_sheet):
        snapshots = [
            row
            for trip in run_sheet.trips
            for row in trip.orders
        ]
        rows = []
        for index, snapshot in enumerate(snapshots):
            if index < 2:
                rows.append(
                    CloseDeliveryRunSheetRowRequest(
                        run_sheet_row_id=snapshot.row_id,
                        outcome="DELIVERED",
                        note="Left at reception" if index == 0 else None,
                    )
                )
            else:
                rows.append(
                    CloseDeliveryRunSheetRowRequest(
                        run_sheet_row_id=snapshot.row_id,
                        outcome="RETURN_TO_POOL",
                        reason_code=(
                            "CUSTOMER_UNAVAILABLE"
                            if index == 2
                            else "TIME_RAN_OUT"
                        ),
                        note="Retry requested" if index == 2 else None,
                        next_delivery_date=NEXT_DELIVERY_DATE,
                    )
                )
        return CloseDeliveryRunSheetRequest(rows=rows)

    def _replace_request_row(self, run_sheet, index, **changes):
        request = self._valid_request(run_sheet)
        request.rows[index] = replace(request.rows[index], **changes)
        return request

    @staticmethod
    def _business_snapshot(repository, run_sheet_id):
        run_sheet = repository.get_delivery_run_sheet(run_sheet_id)
        return {
            "orders": sorted(
                (
                    order.order_id,
                    order.status,
                    order.delivery_date,
                )
                for order in (
                    repository.get_order(f"CLOSE-ORD-{number}")
                    for number in range(1, 5)
                )
                if order
            ),
            "assignments": sorted(
                (
                    assignment.task_id,
                    assignment.driver_id,
                    assignment.trip_no,
                )
                for assignment in (
                    repository.list_globally_assigned_delivery_order_assignments()
                )
            ),
            "execution_status": run_sheet.execution_status,
            "outcomes": sorted(
                (
                    outcome.run_sheet_row_id,
                    outcome.outcome,
                    outcome.next_delivery_date,
                )
                for outcome in run_sheet.outcomes
            ),
        }


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class DeliveryRunSheetCloseoutApiTest(unittest.TestCase):
    _build_saved_sheet = DeliveryRunSheetCloseoutTest._build_saved_sheet
    _build_generated_sheet = DeliveryRunSheetCloseoutTest._build_generated_sheet
    _reset_repository = staticmethod(
        DeliveryRunSheetCloseoutTest._reset_repository
    )
    _valid_request = staticmethod(DeliveryRunSheetCloseoutTest._valid_request)

    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"closeout-api-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "api.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        (
            self.service,
            self.identity,
            self.run_sheet,
            self.logbook,
        ) = self._build_saved_sheet(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_auth_errors_spoof_protection_and_operator_attribution(self):
        path = (
            "/api/manual-dispatch/delivery/run-sheets/"
            f"{self.run_sheet.run_sheet_id}/closeout"
        )
        payload = {
            "rows": [
                {
                    "run_sheet_row_id": row.run_sheet_row_id,
                    "outcome": row.outcome,
                    "reason_code": row.reason_code,
                    "note": row.note,
                    "next_delivery_date": row.next_delivery_date,
                }
                for row in self._valid_request(self.run_sheet).rows
            ]
        }
        self.assertEqual(401, self.client.post(path, json=payload).status_code)
        authenticate_test_client(self.client, self.service, self.identity)
        spoofed = {
            **payload,
            "closed_by_account_name": "Spoofed Operator",
        }
        self.assertEqual(400, self.client.post(path, json=spoofed).status_code)
        self.assertEqual(
            404,
            self.client.post(
                "/api/manual-dispatch/delivery/run-sheets/MISSING/closeout",
                json={"rows": []},
            ).status_code,
        )
        response = self.client.post(path, json=payload)
        self.assertEqual(200, response.status_code)
        self.assertEqual("CLOSED", response.json()["execution_status"])
        self.assertEqual(
            self.identity.account_name,
            response.json()["closed_by_account_name"],
        )
        self.assertEqual(409, self.client.post(path, json=payload).status_code)

    def test_api_rejects_malformed_and_client_derived_row_identity(self):
        authenticate_test_client(self.client, self.service, self.identity)
        path = (
            "/api/manual-dispatch/delivery/run-sheets/"
            f"{self.run_sheet.run_sheet_id}/closeout"
        )
        self.assertEqual(400, self.client.post(path, json=[]).status_code)
        payload = {
            "rows": [
                {
                    "run_sheet_row_id": row.run_sheet_row_id,
                    "outcome": row.outcome,
                    "order_id": "SPOOFED",
                }
                for row in self._valid_request(self.run_sheet).rows
            ]
        }
        self.assertEqual(400, self.client.post(path, json=payload).status_code)
