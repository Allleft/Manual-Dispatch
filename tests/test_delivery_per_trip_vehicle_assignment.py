import importlib
import json
import os
import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.errors import DeliveryRunSheetLockedError, StateChangedConflictError
from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (
    AssignDriverVehicleRequest,
    DeliveryWorkspaceAssignOrderRequest, DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest, DeliveryWorkspaceVehicleClearRequest,
)
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationRequiredError
from tests.manual_dispatch_api_test_helpers import authenticate_test_client
from tests.test_delivery_per_trip_persistence import DATE, OLD_RUN_SHEET_DDL, OLD_VEHICLE_DDL, snapshot


class VehicleFixture(unittest.TestCase):
    def build_repository(self):
        return InMemoryManualDispatchRepository()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="delivery-trip-vehicle-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repository = self.build_repository()
        for order_id in ("ORD-001", "ORD-002"):
            order = self.repository.get_order(order_id)
            order.delivery_date = DATE
            self.repository.update_order(order)
        self.logbook = LogbookFileService(self.root / "logbook")
        self.service = ManualDispatchService(self.repository, self.logbook)

    def assign(self, driver="D001", trip="trip1", vehicle="V001", dispatch=None):
        return self.service.assign_delivery_workspace_vehicle(DeliveryWorkspaceVehicleAssignmentRequest(
            dispatch_date=dispatch, delivery_date=DATE, driver_id=driver, vehicle_id=vehicle, trip_no=trip,
        ))

    def clear(self, driver="D001", trip="trip1"):
        return self.service.clear_delivery_workspace_vehicle(DeliveryWorkspaceVehicleClearRequest(
            delivery_date=DATE, driver_id=driver, trip_no=trip,
        ))

    def selected(self, driver="D001", trip="trip1"):
        item = self.repository.get_delivery_trip_vehicle_assignment(DATE, driver, trip)
        return item.vehicle_id if item else None

    def legacy(self):
        return self.repository.upsert_driver_vehicle_assignment(DATE, DATE, "D001", "V001")

    def sheet(self, trip="trip1", status="GENERATED", execution="OPEN", driver="D001"):
        sheet = snapshot(trip_no=trip, status=status, execution_status=execution, driver=driver)
        self.repository.create_delivery_run_sheet(sheet)
        return sheet


class DeliveryPerTripVehicleDomainTest(VehicleFixture):
    def test_same_driver_same_vehicle_both_trips(self):
        self.assign()
        self.assign(trip="trip2")
        self.assertEqual(["V001", "V001"], [self.selected(trip=trip) for trip in ("trip1", "trip2")])

    def test_same_driver_different_vehicles_both_trips(self):
        self.assign()
        self.assign(trip="trip2", vehicle="V002")
        self.assertEqual("V001", self.selected())
        self.assertEqual("V002", self.selected(trip="trip2"))

    def test_same_trip_other_driver_conflicts(self):
        self.assign()
        with self.assertRaisesRegex(StateChangedConflictError, "already assigned.*trip1"):
            self.assign(driver="D002")
        self.assertIsNone(self.selected("D002"))

    def test_cross_trip_other_driver_same_vehicle_allowed(self):
        self.assign()
        self.assign(driver="D002", trip="trip2")
        self.assertEqual("V001", self.selected("D002", "trip2"))

    def test_dispatch_provenance_cannot_bypass_conflict(self):
        self.assign(dispatch="2026-09-01")
        with self.assertRaises(StateChangedConflictError):
            self.assign(driver="D002", dispatch="2026-09-02")

    def test_clear_preserves_sibling_trip(self):
        self.assign()
        self.assign(trip="trip2")
        self.clear()
        self.assertIsNone(self.selected())
        self.assertEqual("V001", self.selected(trip="trip2"))

    def test_update_preserves_sibling_trip(self):
        self.assign()
        self.assign(trip="trip2", vehicle="V002")
        self.assign(trip="trip2", vehicle="V003")
        self.assertEqual("V001", self.selected())
        self.assertEqual("V003", self.selected(trip="trip2"))

    def test_null_has_no_trip_fallback_or_board_selection(self):
        self.legacy()
        self.assertIsNone(self.selected())
        board = self.service.get_delivery_trip_summary_board(DATE)
        self.assertEqual([], board.driver_vehicle_assignments)
        self.assertEqual([None], [row.trip_no for row in board.legacy_driver_vehicle_assignments])

    def test_trip_writes_and_clear_leave_null_untouched(self):
        self.legacy()
        before = self.repository.list_delivery_vehicle_assignments()
        self.assign(vehicle="V002")
        self.assign(trip="trip2", vehicle="V003")
        self.clear()
        self.assertIsNone(self.selected())
        self.assertEqual("V003", self.selected(trip="trip2"))
        self.assertEqual(before, [row for row in self.repository.list_delivery_vehicle_assignments() if row.trip_no is None])

    def test_missing_empty_and_invalid_trip_rejected_assign_and_clear(self):
        for trip in (None, "", "trip3", "arbitrary"):
            with self.subTest(trip=trip):
                with self.assertRaises(ValueError):
                    self.assign(trip=trip)
                with self.assertRaises(ValueError):
                    self.clear(trip=trip)
        self.assertEqual([], self.repository.list_delivery_vehicle_assignments())

    def test_missing_driver_and_vehicle_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.assign(driver="MISSING")
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.assign(vehicle="MISSING")

    def test_generated_trip1_lock_blocks_only_trip1(self):
        self.sheet()
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.assign()
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.clear()
        self.assign(trip="trip2", vehicle="V002")
        self.clear(trip="trip2")

    def test_saved_open_trip1_lock_blocks_only_trip1(self):
        self.sheet(status="SAVED")
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.assign()
        self.assign(trip="trip2", vehicle="V002")
        locks = self.service.get_delivery_trip_summary_board(DATE).saved_vehicle_assignment_locks
        self.assertEqual(["trip1"], [lock.trip_no for lock in locks])

    def test_saved_closed_trip2_lock_blocks_only_trip2(self):
        self.sheet(trip="trip2", status="SAVED", execution="CLOSED")
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.assign(trip="trip2")
        self.assign()
        locks = self.service.get_delivery_trip_summary_board(DATE).saved_vehicle_assignment_locks
        self.assertEqual(["trip2"], [lock.trip_no for lock in locks])

    def test_legacy_combined_locks_both_trips_in_every_lifecycle(self):
        for status, execution in (("GENERATED", "OPEN"), ("SAVED", "OPEN"), ("SAVED", "CLOSED")):
            with self.subTest(status=status, execution=execution):
                if isinstance(self.repository, InMemoryManualDispatchRepository):
                    self.repository.delivery_run_sheets = []
                else:
                    with closing(sqlite3.connect(self.repository.db_path)) as connection, connection:
                        connection.execute("DELETE FROM delivery_run_sheet_rows")
                        connection.execute("DELETE FROM delivery_run_sheets")
                self.sheet(trip=None, status=status, execution=execution)
                for trip in ("trip1", "trip2"):
                    with self.assertRaises(DeliveryRunSheetLockedError):
                        self.assign(trip=trip)
                    with self.assertRaises(DeliveryRunSheetLockedError):
                        self.clear(trip=trip)

    def test_other_driver_lock_isolated_and_frozen_vehicle_reserved_by_trip(self):
        self.sheet(driver="D002")
        self.assign(vehicle="V002")
        self.assign(trip="trip2")
        with self.assertRaises(StateChangedConflictError):
            self.assign()

    def test_order_target_and_source_guards_respect_trip(self):
        self.sheet()
        self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
            order_id="ORD-002", driver_id="D001", trip_no="trip2",
        ))
        self.service.unassign_delivery_workspace_order(DeliveryWorkspaceUnassignOrderRequest(order_id="ORD-002"))
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                order_id="ORD-002", driver_id="D001", trip_no="trip1",
            ))
        self.repository.upsert_assignment(DATE, "ORDER", "ORD-002", "D001", "trip1")
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                order_id="ORD-002", driver_id="D002", trip_no="trip2",
            ))

    def test_order_reservation_and_legacy_wildcard_guard_preserved(self):
        self.sheet(trip=None)
        for order_id in ("ORD-001", "ORD-002"):
            with self.assertRaises(DeliveryRunSheetLockedError):
                self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                    order_id=order_id, driver_id="D001", trip_no="trip2",
                ))

    def test_unavailable_driver_vehicle_changes_and_existing_order_allowed(self):
        self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
            order_id="ORD-001", driver_id="D001", trip_no="trip1",
        ))
        self.repository.update_driver(replace(self.repository.get_driver("D001"), is_available=False))
        self.assign()
        self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
            order_id="ORD-001", driver_id="D001", trip_no="trip2",
        ))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
                order_id="ORD-002", driver_id="D001", trip_no="trip1",
            ))

    def test_legacy_enabled_vehicle_method_requires_trip_and_obeys_locks(self):
        with self.assertRaisesRegex(ValueError, "trip_no"):
            self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(DATE, "D001", "V001"))
        self.sheet()
        with self.assertRaises(DeliveryRunSheetLockedError):
            self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(DATE, "D001", "V002", DATE, "trip1"))
        result = self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(DATE, "D001", "V002", DATE, "trip2"))
        self.assertEqual("trip2", result.trip_no)
        with self.assertRaisesRegex(ValueError, "trip_no"):
            self.service.clear_driver_vehicle_assignment(DATE, "D001")

    def test_legacy_enabled_vehicle_method_obeys_same_trip_conflict(self):
        self.assign()
        with self.assertRaises(StateChangedConflictError):
            self.service.assign_vehicle_to_driver(AssignDriverVehicleRequest(DATE, "D002", "V001", DATE, "trip1"))

    def test_board_keeps_both_records_in_deterministic_order(self):
        self.assign(trip="trip2", vehicle="V002")
        self.assign()
        board = self.service.get_delivery_trip_summary_board(DATE)
        self.assertEqual([("D001", "trip1", "V001"), ("D001", "trip2", "V002")],
                         [(row.driver_id, row.trip_no, row.vehicle_id) for row in board.driver_vehicle_assignments])
        self.assertEqual([], board.legacy_driver_vehicle_assignments)

    def test_workspace_board_update_preserves_dispatch_provenance(self):
        self.assign(dispatch="2026-09-01")
        response = self.assign(vehicle="V002", dispatch="2026-09-02")
        self.assertEqual("2026-09-01", response.driver_vehicle_assignments[0].dispatch_date)
        self.assertEqual("V002", response.driver_vehicle_assignments[0].vehicle_id)
        self.sheet(status="SAVED")
        locks = self.service.get_delivery_workspace_board("2026-09-02").saved_vehicle_assignment_locks
        self.assertEqual(["trip1"], [lock.trip_no for lock in locks])

    def test_global_lock_projection_does_not_broaden_unavailable_driver_roster(self):
        self.repository.update_driver(replace(self.repository.get_driver("D002"), is_available=False))
        self.sheet(driver="D002", status="SAVED")
        board = self.service.get_delivery_workspace_board("2026-09-02")
        self.assertNotIn("D002", [driver.driver_id for driver in board.drivers])
        self.assertEqual(["D002"], [lock.driver_id for lock in board.saved_vehicle_assignment_locks])

    def test_vehicle_logbook_events_include_selected_trip(self):
        self.assign(trip="trip2")
        self.assign(trip="trip2", vehicle="V002")
        self.clear(trip="trip2")
        rows = [json.loads(line) for path in (self.root / "logbook").rglob("*.txt")
                for line in path.read_text(encoding="utf-8").splitlines()]
        events = [row for row in rows if row.get("action", "").startswith("VEHICLE_")]
        self.assertEqual(3, len(events))
        self.assertEqual({"trip2"}, {row["metadata"]["trip_no"] for row in events})

    def test_legacy_repository_projection_of_equal_trips_remains_readable(self):
        self.assign()
        self.assign(trip="trip2")
        self.assertEqual("V001", self.repository.list_driver_vehicle_assignments_for_delivery_date(DATE)[0].vehicle_id)
        self.repository.upsert_driver_vehicle_assignment(DATE, DATE, "D001", "V002")
        self.assertEqual(["V002", "V002"], [self.selected(trip=trip) for trip in ("trip1", "trip2")])
        self.assertEqual([], [row for row in self.repository.list_delivery_vehicle_assignments() if row.trip_no is None])

    def test_legacy_repository_projection_rejects_divergent_and_partial_trips(self):
        self.assign()
        before = self.repository.list_delivery_vehicle_assignments()
        with self.assertRaises(StateChangedConflictError):
            self.repository.list_driver_vehicle_assignments_for_delivery_date(DATE)
        self.assertEqual(before, self.repository.list_delivery_vehicle_assignments())
        self.assign(trip="trip2", vehicle="V002")
        before = self.repository.list_delivery_vehicle_assignments()
        for operation in (
            lambda: self.repository.upsert_driver_vehicle_assignment(DATE, DATE, "D001", "V003"),
            lambda: self.repository.list_driver_vehicle_assignments_for_delivery_date(DATE),
        ):
            with self.assertRaises(StateChangedConflictError):
                operation()
        self.assertEqual(before, self.repository.list_delivery_vehicle_assignments())

    def test_historical_null_fixture_remains_visible_as_legacy_only(self):
        self.legacy()
        self.repository.upsert_driver_vehicle_assignment(DATE, DATE, "D001", "V002")
        board = self.service.get_delivery_trip_summary_board(DATE)
        self.assertEqual([], board.driver_vehicle_assignments)
        self.assertEqual("V002", board.legacy_driver_vehicle_assignments[0].vehicle_id)
        self.assertIsNone(self.selected())
        self.repository.remove_driver_vehicle_assignment(DATE, "D001", DATE)
        self.assertEqual([], self.repository.list_delivery_vehicle_assignments())

    def test_day_service_entrypoints_are_retired(self):
        self.assertFalse(hasattr(self.service, "assign_delivery_day_vehicle"))
        self.assertFalse(hasattr(self.service, "clear_delivery_day_vehicle"))


class SQLiteDeliveryPerTripVehicleDomainTest(DeliveryPerTripVehicleDomainTest):
    def build_repository(self):
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            return SQLiteManualDispatchRepository(self.root / "db.sqlite3")

    def race(self, trips):
        repositories = [SQLiteManualDispatchRepository(self.repository.db_path) for _ in range(2)]
        barrier = Barrier(2)
        def claim(index):
            service = ManualDispatchService(repositories[index], LogbookFileService(self.root / f"race-log-{index}"))
            barrier.wait(timeout=10)
            try:
                service.assign_delivery_workspace_vehicle(DeliveryWorkspaceVehicleAssignmentRequest(
                    delivery_date=DATE, dispatch_date=f"2026-09-0{index + 1}", driver_id=f"D00{index + 1}",
                    trip_no=trips[index], vehicle_id="V001",
                ))
                return "success"
            except StateChangedConflictError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(claim, range(2)))

    def test_two_sqlite_connections_same_trip_exactly_one_winner(self):
        self.assertEqual(["conflict", "success"], sorted(self.race(("trip1", "trip1"))))
        self.assertEqual(1, len(self.repository.list_delivery_trip_vehicle_assignments(DATE)))

    def test_two_sqlite_connections_cross_trip_both_win(self):
        self.assertEqual(["success", "success"], self.race(("trip1", "trip2")))
        self.assertEqual(2, len(self.repository.list_delivery_trip_vehicle_assignments(DATE)))

    def test_old_schema_orders_and_legacy_reads_remain_usable(self):
        path = self.root / "old-schema.sqlite3"
        schema = (Path(__file__).resolve().parents[1] / "backend/db/schema.sql").read_text(encoding="utf-8")
        for table, ddl in (("manual_driver_vehicle_assignments", OLD_VEHICLE_DDL), ("delivery_run_sheets", OLD_RUN_SHEET_DDL)):
            schema = re.sub(rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\n\);", ddl, schema, flags=re.S)
        with closing(sqlite3.connect(path)) as connection:
            connection.executescript(schema)
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            repository = SQLiteManualDispatchRepository(path)
        order = repository.get_order("ORD-001")
        order.delivery_date = DATE
        repository.update_order(order)
        service = ManualDispatchService(repository, LogbookFileService(self.root / "old-logbook"))
        service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(
            order_id="ORD-001", driver_id="D001", trip_no="trip2",
        ))
        repository.upsert_driver_vehicle_assignment(DATE, DATE, "D001", "V001")
        board = service.get_delivery_trip_summary_board(DATE)
        self.assertEqual("trip2", board.assignments[0].trip_no)
        self.assertEqual([], board.driver_vehicle_assignments)
        self.assertEqual("V001", board.legacy_driver_vehicle_assignments[0].vehicle_id)
        with self.assertRaises(WorkspaceMigrationRequiredError):
            service.assign_delivery_workspace_vehicle(DeliveryWorkspaceVehicleAssignmentRequest(
                delivery_date=DATE, driver_id="D001", vehicle_id="V002", trip_no="trip1",
            ))

    def test_unique_backstop_becomes_business_conflict(self):
        with patch.object(self.repository, "upsert_delivery_trip_vehicle_assignment",
                          side_effect=sqlite3.IntegrityError("UNIQUE constraint failed: manual_driver_vehicle_assignments.delivery_date")):
            with self.assertRaises(StateChangedConflictError):
                self.assign()

    def test_schema_readiness_is_a_distinct_error(self):
        with closing(sqlite3.connect(self.repository.db_path)) as connection, connection:
            connection.execute("UPDATE manual_dispatch_schema_capabilities SET version=99")
        with self.assertRaises(WorkspaceMigrationRequiredError):
            self.assign()


class DeliveryPerTripVehicleApiTest(VehicleFixture):
    def build_repository(self):
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            return SQLiteManualDispatchRepository(self.root / "db.sqlite3")

    def setUp(self):
        super().setUp()
        self.api = importlib.import_module("backend.api.manual_dispatch")
        previous = self.api.service
        self.api.service = self.service
        self.addCleanup(setattr, self.api, "service", previous)
        app = FastAPI()
        app.include_router(self.api.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        authenticate_test_client(self.client, self.service)

    def post(self, trip="trip1", driver="D001", vehicle="V001", **extra):
        return self.client.post("/api/manual-dispatch/delivery/vehicle-assignments", json={
            "delivery_date": DATE, "driver_id": driver, "vehicle_id": vehicle, "trip_no": trip, **extra,
        })

    def test_assign_both_trips_clear_one_get_boards_serialize_trip(self):
        self.assertEqual(200, self.post().status_code)
        response = self.post("trip2", vehicle="V002")
        self.assertEqual(200, response.status_code)
        self.assertEqual(["trip1", "trip2"], [row["trip_no"] for row in response.json()["driver_vehicle_assignments"]])
        for path, params in (("trip-summary", {"delivery_date": DATE}), ("board", {"dispatch_date": DATE})):
            board = self.client.get(f"/api/manual-dispatch/delivery/{path}", params=params)
            self.assertEqual(200, board.status_code)
            self.assertEqual(2, len(board.json()["driver_vehicle_assignments"]))
        cleared = self.client.post("/api/manual-dispatch/delivery/vehicle-assignments/clear", json={
            "delivery_date": DATE, "driver_id": "D001", "trip_no": "trip1",
        })
        self.assertEqual(200, cleared.status_code)
        self.assertEqual(["trip2"], [row["trip_no"] for row in cleared.json()["driver_vehicle_assignments"]])

    def test_direct_api_same_trip_conflict_cross_trip_allowed(self):
        self.assertEqual(200, self.post(dispatch_date="2026-09-01").status_code)
        conflict = self.post(driver="D002", dispatch_date="2026-09-02")
        self.assertEqual(409, conflict.status_code)
        self.assertEqual("state_changed_conflict", conflict.headers["X-Manual-Dispatch-Error-Code"])
        self.assertIn("already assigned", conflict.json()["detail"])
        self.assertEqual(200, self.post("trip2", "D002").status_code)

    def test_missing_and_invalid_trip_rejected_on_both_endpoints(self):
        for path in ("", "/clear"):
            for trip in (None, "", "trip3"):
                payload = {"delivery_date": DATE, "driver_id": "D001", "vehicle_id": "V001", "trip_no": trip}
                self.assertEqual(400, self.client.post("/api/manual-dispatch/delivery/vehicle-assignments" + path, json=payload).status_code)
            self.assertEqual(400, self.client.post("/api/manual-dispatch/delivery/vehicle-assignments" + path,
                             json={"delivery_date": DATE, "driver_id": "D001", "vehicle_id": "V001"}).status_code)

    def test_locked_and_migration_conflicts_have_distinct_codes(self):
        self.sheet()
        response = self.post()
        self.assertEqual(409, response.status_code)
        self.assertEqual("delivery_run_sheet_locked", response.headers["X-Manual-Dispatch-Error-Code"])
        with closing(sqlite3.connect(self.repository.db_path)) as connection, connection:
            connection.execute("UPDATE manual_dispatch_schema_capabilities SET version=99")
        response = self.post("trip2")
        self.assertEqual(409, response.status_code)
        self.assertEqual("workspace_migration_required", response.headers["X-Manual-Dispatch-Error-Code"])
        self.assertIn("X-Manual-Dispatch-Error-Code", response.headers["Access-Control-Expose-Headers"])

    def test_day_endpoints_are_retired_without_vehicle_writes(self):
        for suffix in ("", "/clear"):
            response = self.client.post("/api/manual-dispatch/delivery/day-vehicle-assignments" + suffix, json={
                "delivery_date": DATE, "driver_id": "D001", "vehicle_id": "V001",
            })
            self.assertEqual(404, response.status_code)
        self.assertEqual([], self.repository.list_delivery_vehicle_assignments())

    def test_legacy_disabled_stays_disabled_enabled_requires_trip(self):
        payload = {"dispatch_date": DATE, "delivery_date": DATE, "driver_id": "D001", "vehicle_id": "V001"}
        with patch.dict(os.environ, {"MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS": "false"}):
            self.assertEqual(404, self.client.post("/api/manual-dispatch/driver-vehicle", json=payload).status_code)
        with patch.dict(os.environ, {"MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS": "true"}):
            self.assertEqual(400, self.client.post("/api/manual-dispatch/driver-vehicle", json=payload).status_code)
            response = self.client.post("/api/manual-dispatch/driver-vehicle", json={**payload, "trip_no": "trip1"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("trip1", response.json()["trip_no"])


if __name__ == "__main__":
    unittest.main()
