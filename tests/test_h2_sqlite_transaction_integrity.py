import os
import shutil
import sqlite3
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch

from backend.api.manual_dispatch_routes.common import to_http_exception
from backend.db.connection import _BorrowedConnection
from backend.errors import StateChangedConflictError
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignCountrysideRouteGroupRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    DeliveryWorkspaceVehicleClearRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    OpShopWorkspaceAssignmentBatchRequest,
    OpShopWorkspaceUnassignPickupRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class H2SQLiteTransactionPrimitiveTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"h2-transaction-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        previous_seed = os.environ.get("MANUAL_DISPATCH_SEED_DEMO_DATA")
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "true"
        try:
            self.repository = SQLiteManualDispatchRepository(self.db_path)
        finally:
            if previous_seed is None:
                os.environ.pop("MANUAL_DISPATCH_SEED_DEMO_DATA", None)
            else:
                os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = previous_seed

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nested_repository_calls_borrow_one_real_connection(self):
        with patch(
            "backend.db.connection.sqlite3.connect",
            wraps=sqlite3.connect,
        ) as connect_spy:
            with self.repository._immediate_transaction():
                self.repository.list_assignments_for_task("ORDER", "ORD-H2")
                self.repository.upsert_assignment(
                    "2026-07-15",
                    "ORDER",
                    "ORD-H2",
                    "D001",
                    "trip1",
                )
                self.repository.find_assignment_for_task("ORDER", "ORD-H2")

        self.assertEqual(1, connect_spy.call_count)

    def test_inner_commit_is_deferred_and_outer_exception_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            with self.repository._immediate_transaction():
                self.repository.upsert_assignment(
                    "2026-07-15",
                    "ORDER",
                    "ORD-H2",
                    "D001",
                    "trip1",
                )
                raise RuntimeError("injected failure")

        self.assertIsNone(
            self.repository.find_assignment_for_task("ORDER", "ORD-H2")
        )

    def test_outer_commit_persists_nested_repository_write(self):
        with self.repository._immediate_transaction():
            self.repository.upsert_assignment(
                "2026-07-15",
                "ORDER",
                "ORD-H2",
                "D001",
                "trip1",
            )

        assignment = self.repository.find_assignment_for_task("ORDER", "ORD-H2")
        self.assertEqual("2026-07-15", assignment.dispatch_date)
        self.assertEqual("D001", assignment.driver_id)

    def test_transaction_body_busy_maps_to_conflict_and_rolls_back(self):
        original_execute = _BorrowedConnection.execute

        def fail_after_assignment_insert(connection, sql, parameters=()):
            result = original_execute(connection, sql, parameters)
            if "INSERT INTO manual_dispatch_assignments" in str(sql):
                raise sqlite3.OperationalError("database is locked")
            return result

        with patch.object(_BorrowedConnection, "execute", fail_after_assignment_insert):
            with self.assertRaisesRegex(
                StateChangedConflictError,
                "State changed; refresh and retry",
            ):
                with self.repository._immediate_transaction():
                    self.repository.upsert_assignment(
                        "2026-07-15",
                        "ORDER",
                        "ORD-H2",
                        "D001",
                        "trip1",
                    )

        self.assertIsNone(
            self.repository.find_assignment_for_task("ORDER", "ORD-H2")
        )

    def test_concurrent_delivery_generate_has_one_winner_and_one_conflict(self):
        self._assign_seed_order_with_cross_dispatch_date()
        services = [
            ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
            for _ in range(2)
        ]
        barrier = Barrier(2)

        def generate(service):
            barrier.wait()
            try:
                return service.create_generated_delivery_run_sheet(
                    GenerateDeliveryRunSheetRequest(
                        dispatch_date="2026-07-20",
                        delivery_date="2026-05-05",
                        driver_id="D001",
                    )
                )
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(generate, services))

        winners = [result for result in results if not isinstance(result, Exception)]
        conflicts = [
            result for result in results if isinstance(result, StateChangedConflictError)
        ]
        self.assertEqual(1, len(winners))
        self.assertEqual(1, len(conflicts))
        self.assertEqual("2026-07-20", winners[0].dispatch_date)
        self.assertEqual(["ORD-001"], [row.task_id for row in winners[0].trips[0].orders])

        with sqlite3.connect(self.db_path) as connection:
            header_count = connection.execute(
                "SELECT COUNT(*) FROM delivery_run_sheets "
                "WHERE delivery_date = ? AND driver_id = ?",
                ("2026-05-05", "D001"),
            ).fetchone()[0]
            child_count = connection.execute(
                "SELECT COUNT(*) FROM delivery_run_sheet_rows"
            ).fetchone()[0]
        self.assertEqual(1, header_count)
        self.assertGreater(child_count, 0)
        assignment = self.repository.find_assignment_for_task("ORDER", "ORD-001")
        self.assertEqual("2026-07-15", assignment.dispatch_date)

    def test_delivery_generate_child_failure_rolls_back_header_and_rows(self):
        service = self._assign_seed_order_with_cross_dispatch_date()
        original_execute = _BorrowedConnection.execute

        def fail_first_child_insert(connection, sql, parameters=()):
            if "INSERT INTO delivery_run_sheet_rows" in str(sql):
                raise RuntimeError("injected delivery child failure")
            return original_execute(connection, sql, parameters)

        with patch.object(_BorrowedConnection, "execute", fail_first_child_insert):
            with self.assertRaisesRegex(RuntimeError, "injected delivery child failure"):
                service.create_generated_delivery_run_sheet(
                    GenerateDeliveryRunSheetRequest(
                        dispatch_date="2026-07-20",
                        delivery_date="2026-05-05",
                        driver_id="D001",
                    )
                )

        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(
                0, connection.execute("SELECT COUNT(*) FROM delivery_run_sheets").fetchone()[0]
            )
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT COUNT(*) FROM delivery_run_sheet_rows"
                ).fetchone()[0],
            )

    def test_assign_vs_generate_revalidates_after_generate_commit(self):
        self._assign_seed_order_with_cross_dispatch_date()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        run_sheet, conflict = self._generate_wins_against(
            lambda: mutation_service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date="2026-07-20",
                    order_id="ORD-002",
                    driver_id="D001",
                    trip_no="trip1",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertIsNone(self.repository.find_assignment_for_task("ORDER", "ORD-002"))
        self.assertEqual(["ORD-001"], [row.task_id for row in run_sheet.trips[0].orders])

    def test_reassign_vs_generate_revalidates_after_generate_commit(self):
        self._assign_seed_order_with_cross_dispatch_date()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        run_sheet, conflict = self._generate_wins_against(
            lambda: mutation_service.assign_delivery_workspace_order(
                DeliveryWorkspaceAssignOrderRequest(
                    dispatch_date="2026-07-20",
                    order_id="ORD-001",
                    driver_id="D002",
                    trip_no="trip2",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertEqual("D001", self.repository.find_assignment_for_task("ORDER", "ORD-001").driver_id)
        self.assertEqual(["ORD-001"], [row.task_id for row in run_sheet.trips[0].orders])

    def test_unassign_vs_generate_revalidates_after_generate_commit(self):
        self._assign_seed_order_with_cross_dispatch_date()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        run_sheet, conflict = self._generate_wins_against(
            lambda: mutation_service.unassign_delivery_workspace_order(
                DeliveryWorkspaceUnassignOrderRequest(
                    dispatch_date="2026-07-20",
                    order_id="ORD-001",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertIsNotNone(self.repository.find_assignment_for_task("ORDER", "ORD-001"))
        self.assertEqual(["ORD-001"], [row.task_id for row in run_sheet.trips[0].orders])

    def test_vehicle_assign_vs_generate_revalidates_after_generate_commit(self):
        self._assign_seed_order_with_cross_dispatch_date()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        run_sheet, conflict = self._generate_wins_against(
            lambda: mutation_service.assign_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleAssignmentRequest(
                    dispatch_date="2026-07-20",
                    delivery_date="2026-05-05",
                    driver_id="D001",
                    vehicle_id="V001",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertIsNone(run_sheet.vehicle_id)
        self.assertEqual([], self.repository.list_driver_vehicle_assignments_for_delivery_date("2026-05-05"))

    def test_vehicle_clear_vs_generate_revalidates_after_generate_commit(self):
        service = self._assign_seed_order_with_cross_dispatch_date()
        service.assign_delivery_workspace_vehicle(
            DeliveryWorkspaceVehicleAssignmentRequest(
                dispatch_date="2026-07-15",
                delivery_date="2026-05-05",
                driver_id="D001",
                vehicle_id="V001",
            )
        )
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        run_sheet, conflict = self._generate_wins_against(
            lambda: mutation_service.clear_delivery_workspace_vehicle(
                DeliveryWorkspaceVehicleClearRequest(
                    dispatch_date="2026-07-20",
                    delivery_date="2026-05-05",
                    driver_id="D001",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertEqual("V001", run_sheet.vehicle_id)
        self.assertEqual(
            "V001",
            self.repository.list_driver_vehicle_assignments_for_delivery_date("2026-05-05")[0].vehicle_id,
        )

    def test_state_changed_conflict_maps_to_http_409(self):
        error = to_http_exception(StateChangedConflictError("refresh and retry"))
        self.assertEqual(409, error.status_code)
        self.assertEqual("refresh and retry", error.detail)

    def test_opshop_assign_vs_generate_revalidates_after_generate_commit(self):
        self._seed_assigned_opshop_pickup()
        self._seed_unassigned_opshop_pickup()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        collection, conflict = self._generate_opshop_wins_against(
            lambda: mutation_service.apply_opshop_workspace_assignments(
                OpShopWorkspaceAssignmentBatchRequest(
                    dispatch_date="2026-07-20",
                    assignments=[
                        {"pickup_task_id": "H2-PICKUP-2", "driver_id": "D001"}
                    ],
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        self.assertIsNone(
            self.repository.find_assignment_for_task("OPSHOP_PICKUP", "H2-PICKUP-2")
        )
        self.assertEqual(
            ["H2-PICKUP"],
            [row.pickup_task_id_snapshot for row in collection.pickups],
        )

    def test_opshop_unassign_vs_generate_revalidates_after_generate_commit(self):
        self._seed_assigned_opshop_pickup()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        collection, conflict = self._generate_opshop_wins_against(
            lambda: mutation_service.unassign_opshop_workspace_pickup(
                OpShopWorkspaceUnassignPickupRequest(
                    dispatch_date="2026-07-20",
                    pickup_task_id="H2-PICKUP",
                )
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP", "H2-PICKUP"
        )
        self.assertEqual("D001", assignment.driver_id)
        self.assertEqual(
            ["H2-PICKUP"],
            [row.pickup_task_id_snapshot for row in collection.pickups],
        )

    def test_countryside_route_group_vs_generate_revalidates_atomically(self):
        self._seed_assigned_opshop_pickup()
        self._seed_countryside_route_group_for_existing_pickup()
        mutation_service = ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
        collection, conflict = self._generate_opshop_wins_against(
            lambda: mutation_service.assign_opshop_workspace_countryside_route_group(
                "H2-ROUTE-GROUP",
                AssignCountrysideRouteGroupRequest(
                    dispatch_date="2026-07-20",
                    pickup_date="2026-07-06",
                    assigned_driver_id="D002",
                    notes="H2 route race",
                ),
            )
        )
        self.assertIsInstance(conflict, StateChangedConflictError)
        assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP", "H2-PICKUP"
        )
        self.assertEqual("D001", assignment.driver_id)
        self.assertEqual("D001", self.repository.get_opshop_pickup_task("H2-PICKUP").driver_id)
        self.assertEqual(
            ["H2-PICKUP"],
            [row.pickup_task_id_snapshot for row in collection.pickups],
        )

    def test_countryside_route_group_mid_batch_failure_rolls_back_every_row(self):
        service = self._seed_assigned_opshop_pickup()
        self._seed_countryside_route_group_for_existing_pickup()
        original_execute = _BorrowedConnection.execute
        task_write_count = 0

        def fail_second_task_write(connection, sql, parameters=()):
            nonlocal task_write_count
            if "INSERT INTO opshop_pickup_tasks" in str(sql):
                task_write_count += 1
                if task_write_count == 2:
                    raise RuntimeError("injected route-group batch failure")
            return original_execute(connection, sql, parameters)

        with patch.object(_BorrowedConnection, "execute", fail_second_task_write):
            with self.assertRaisesRegex(RuntimeError, "injected route-group batch failure"):
                service.assign_opshop_workspace_countryside_route_group(
                    "H2-ROUTE-GROUP",
                    AssignCountrysideRouteGroupRequest(
                        dispatch_date="2026-07-20",
                        pickup_date="2026-07-06",
                        assigned_driver_id="D002",
                        notes="H2 rollback proof",
                    ),
                )

        original_assignment = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP", "H2-PICKUP"
        )
        self.assertEqual("D001", original_assignment.driver_id)
        self.assertEqual("D001", self.repository.get_opshop_pickup_task("H2-PICKUP").driver_id)
        generated_task_id = self.repository.find_opshop_pickup_task_by_schedule_and_date(
            "H2-SCHEDULE-2", "2026-07-06"
        )
        self.assertIsNone(generated_task_id)

    def test_concurrent_opshop_generate_has_one_winner_and_one_conflict(self):
        self._seed_assigned_opshop_pickup()
        services = [
            ManualDispatchService(SQLiteManualDispatchRepository(self.db_path))
            for _ in range(2)
        ]
        barrier = Barrier(2)

        def generate(service):
            barrier.wait()
            try:
                return service.create_generated_opshop_pickup_collection(
                    GenerateOpShopPickupCollectionRequest(
                        dispatch_date="2026-07-20",
                        pickup_date="2026-07-06",
                        driver_id="D001",
                    )
                )
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(generate, services))

        winners = [result for result in results if not isinstance(result, Exception)]
        conflicts = [
            result for result in results if isinstance(result, StateChangedConflictError)
        ]
        self.assertEqual(1, len(winners))
        self.assertEqual(1, len(conflicts))
        self.assertEqual(["H2-PICKUP"], [row.pickup_task_id_snapshot for row in winners[0].pickups])
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(
                1,
                connection.execute(
                    "SELECT COUNT(*) FROM opshop_pickup_collections "
                    "WHERE pickup_date = ? AND driver_id = ?",
                    ("2026-07-06", "D001"),
                ).fetchone()[0],
            )
            self.assertGreater(
                connection.execute(
                    "SELECT COUNT(*) FROM opshop_pickup_collection_rows"
                ).fetchone()[0],
                0,
            )

    def test_opshop_generate_child_failure_rolls_back_header_and_rows(self):
        service = self._seed_assigned_opshop_pickup()
        original_execute = _BorrowedConnection.execute

        def fail_first_child_insert(connection, sql, parameters=()):
            if "INSERT INTO opshop_pickup_collection_rows" in str(sql):
                raise RuntimeError("injected opshop child failure")
            return original_execute(connection, sql, parameters)

        with patch.object(_BorrowedConnection, "execute", fail_first_child_insert):
            with self.assertRaisesRegex(RuntimeError, "injected opshop child failure"):
                service.create_generated_opshop_pickup_collection(
                    GenerateOpShopPickupCollectionRequest(
                        dispatch_date="2026-07-20",
                        pickup_date="2026-07-06",
                        driver_id="D001",
                    )
                )

        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT COUNT(*) FROM opshop_pickup_collections"
                ).fetchone()[0],
            )
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT COUNT(*) FROM opshop_pickup_collection_rows"
                ).fetchone()[0],
            )

    def _assign_seed_order_with_cross_dispatch_date(self):
        service = ManualDispatchService(self.repository)
        service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date="2026-07-15",
                order_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        return service

    def _generate_wins_against(self, mutation):
        generation_service = ManualDispatchService(
            SQLiteManualDispatchRepository(self.db_path)
        )
        entered_snapshot_build = Event()
        release_snapshot_build = Event()
        original_build = generation_service.delivery_run_sheet_service._build_trips

        def gated_build(*args, **kwargs):
            entered_snapshot_build.set()
            if not release_snapshot_build.wait(5):
                raise RuntimeError("test coordination timed out")
            return original_build(*args, **kwargs)

        generation_service.delivery_run_sheet_service._build_trips = gated_build

        def generate():
            return generation_service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date="2026-07-20",
                    delivery_date="2026-05-05",
                    driver_id="D001",
                )
            )

        def mutate():
            try:
                return mutation()
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            generated_future = executor.submit(generate)
            self.assertTrue(entered_snapshot_build.wait(5))
            mutation_future = executor.submit(mutate)
            release_snapshot_build.set()
            return generated_future.result(), mutation_future.result()

    def _generate_opshop_wins_against(self, mutation):
        generation_service = ManualDispatchService(
            SQLiteManualDispatchRepository(self.db_path)
        )
        entered_snapshot_build = Event()
        release_snapshot_build = Event()
        original_build = generation_service.opshop_pickup_collection_service._build_pickups

        def gated_build(*args, **kwargs):
            entered_snapshot_build.set()
            if not release_snapshot_build.wait(5):
                raise RuntimeError("test coordination timed out")
            return original_build(*args, **kwargs)

        generation_service.opshop_pickup_collection_service._build_pickups = gated_build

        def generate():
            return generation_service.create_generated_opshop_pickup_collection(
                GenerateOpShopPickupCollectionRequest(
                    dispatch_date="2026-07-20",
                    pickup_date="2026-07-06",
                    driver_id="D001",
                )
            )

        def mutate():
            try:
                return mutation()
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            generated_future = executor.submit(generate)
            self.assertTrue(entered_snapshot_build.wait(5))
            mutation_future = executor.submit(mutate)
            release_snapshot_build.set()
            return generated_future.result(), mutation_future.result()

    def _seed_unassigned_opshop_pickup(self):
        source = self.repository.get_opshop_pickup_task("H2-PICKUP")
        self.repository.upsert_opshop_pickup_task(
            replace(
                source,
                pickup_task_id="H2-PICKUP-2",
                status="ACTIVE",
                dispatch_date=None,
                driver_id=None,
                trip_no=None,
            )
        )

    def _seed_countryside_route_group_for_existing_pickup(self):
        timestamp = "2026-07-05T00:00:00+00:00"
        self.repository.upsert_countryside_route_group(
            OpShopCountrysideRouteGroup(
                route_group_id="H2-ROUTE-GROUP",
                route_group_name="H2 Route",
                status="Active",
                active_flag=True,
                display_order=1,
                source_marker="H2_TEST",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        schedule = self.repository.get_opshop_pickup_schedule("H2-SCHEDULE")
        self.repository.upsert_opshop_pickup_schedule(
            replace(
                schedule,
                pickup_category="COUNTRYSIDE",
                route_group_id="H2-ROUTE-GROUP",
            )
        )
        self.repository.upsert_opshop_pickup_schedule(
            replace(
                schedule,
                schedule_id="H2-SCHEDULE-2",
                pickup_category="COUNTRYSIDE",
                route_group_id="H2-ROUTE-GROUP",
            )
        )

    def _seed_assigned_opshop_pickup(self):
        timestamp = "2026-07-05T00:00:00+00:00"
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="H2-OPSHOP",
                name="H2 OP SHOP",
                suburb="MELBOURNE",
                street_address="1 H2 STREET",
                area_region="QA",
                primary_contact="QA",
                primary_phone="0400 000 000",
                secondary_contact=None,
                secondary_phone=None,
                access_type="Front door",
                key_required=False,
                trailer_restriction="No",
                status_notes="QA only",
                is_active=True,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id="H2-SCHEDULE",
                opshop_id="H2-OPSHOP",
                run_day="MONDAY",
                run_type="ON_CALL",
                pickup_frequency="Weekly",
                time_window="09:00-12:00",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at=timestamp,
                updated_at=timestamp,
                default_driver_id=None,
                default_driver_name_snapshot=None,
                pickup_category="NORMAL",
                route_group_id=None,
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id="H2-PICKUP",
                schedule_id="H2-SCHEDULE",
                opshop_id="H2-OPSHOP",
                pickup_date="2026-07-06",
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ASSIGNED",
                dispatch_date="2026-07-06",
                driver_id="D001",
                trip_no="trip1",
                notes="H2 QA",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        self.repository.upsert_assignment(
            "2026-07-05",
            "OPSHOP_PICKUP",
            "H2-PICKUP",
            "D001",
            "trip1",
        )
        return ManualDispatchService(self.repository)


if __name__ == "__main__":
    unittest.main()
