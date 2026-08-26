from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import shutil
import unittest
import uuid

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopPickupTaskRequest,
    CreateOpShopTemplateRequest,
    Driver,
    GenerateOpShopPickupCollectionRequest,
    OpShopWorkspaceAssignmentBatchRequest,
    OpShopWorkspaceUnassignPickupRequest,
    UpdateOpShopPickupTaskRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService


PICKUP_DATE = "2026-09-07"


class CountrysideTripSequenceTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"countryside-trip-sequence-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reorder_persists_and_trip_summary_reload_matches_for_both_repositories(self):
        for label, repository in self._repositories():
            with self.subTest(repository=label):
                service, task_ids = self._seed_countryside_trip(repository)

                board = service.reorder_countryside_pickup_order(
                    self._reorder_request([task_ids[2], task_ids[0], task_ids[1]])
                )

                self.assertEqual(
                    [task_ids[2], task_ids[0], task_ids[1]],
                    self._countryside_ids(board),
                )
                self.assertEqual(
                    [2, 3, 1],
                    [
                        repository.get_opshop_pickup_task(task_id).trip_sequence
                        for task_id in task_ids
                    ],
                )
                reloaded = service.get_opshop_trip_summary_board(PICKUP_DATE)
                self.assertEqual(
                    [task_ids[2], task_ids[0], task_ids[1]],
                    self._countryside_ids(reloaded),
                )

    def test_duplicate_missing_extra_driver_date_and_category_reject_atomically(self):
        repository = InMemoryManualDispatchRepository()
        service, task_ids = self._seed_countryside_trip(repository)
        service.reorder_countryside_pickup_order(
            self._reorder_request([task_ids[2], task_ids[0], task_ids[1]])
        )
        expected = self._sequence_snapshot(repository, task_ids)

        wrong_driver = self._create_pickup(
            service,
            "Wrong Driver",
            "WERRIBEE",
            driver_id="D002",
        )
        wrong_date = self._create_pickup(
            service,
            "Wrong Date",
            "BENDIGO",
            pickup_date="2026-09-08",
        )
        normal_oncall = self._create_pickup(
            service,
            "Normal Oncall",
            "MELBOURNE",
            pickup_category="NORMAL",
        )
        regular = self._create_pickup(
            service,
            "Regular Pickup",
            "COBURG",
            pickup_category="NORMAL",
            run_type="REGULAR",
        )
        unassigned = self._create_pickup(
            service,
            "Unassigned Country",
            "BALLARAT",
            driver_id=None,
        )

        invalid_orders = (
            [task_ids[0], task_ids[0], task_ids[2]],
            [task_ids[0], task_ids[1]],
            [*task_ids, wrong_driver.pickup_task_id],
            [*task_ids, wrong_date.pickup_task_id],
            [*task_ids, normal_oncall.pickup_task_id],
            [*task_ids, regular.pickup_task_id],
            [*task_ids, unassigned.pickup_task_id],
        )
        for ordered_ids in invalid_orders:
            with self.subTest(ordered_ids=ordered_ids):
                with self.assertRaises(ValueError):
                    service.reorder_countryside_pickup_order(
                        self._reorder_request(ordered_ids)
                    )
                self.assertEqual(
                    expected,
                    self._sequence_snapshot(repository, task_ids),
                )

    def test_generated_and_saved_collection_both_lock_reorder(self):
        repository = InMemoryManualDispatchRepository()
        service, task_ids = self._seed_countryside_trip(repository)
        service.reorder_countryside_pickup_order(
            self._reorder_request([task_ids[2], task_ids[0], task_ids[1]])
        )
        collection = service.create_generated_opshop_pickup_collection(
            GenerateOpShopPickupCollectionRequest(
                dispatch_date=PICKUP_DATE,
                pickup_date=PICKUP_DATE,
                driver_id="D001",
            )
        )

        with self.assertRaisesRegex(ValueError, "Generated|Saved|Collection"):
            service.reorder_countryside_pickup_order(
                self._reorder_request(task_ids)
            )

        collection.status = "SAVED"
        with self.assertRaisesRegex(ValueError, "Generated|Saved|Collection"):
            service.reorder_countryside_pickup_order(
                self._reorder_request(task_ids)
            )

    def test_same_scope_preserves_sequence_and_scope_changes_clear_it(self):
        for label, repository in self._repositories():
            with self.subTest(repository=label):
                service, task_ids = self._seed_countryside_trip(repository)
                service.reorder_countryside_pickup_order(
                    self._reorder_request([task_ids[2], task_ids[0], task_ids[1]])
                )
                task_id = task_ids[2]

                service.apply_opshop_workspace_assignments(
                    OpShopWorkspaceAssignmentBatchRequest(
                        dispatch_date=PICKUP_DATE,
                        assignments=[
                            {"pickup_task_id": task_id, "driver_id": "D001"}
                        ],
                    )
                )
                self.assertEqual(
                    1,
                    repository.get_opshop_pickup_task(task_id).trip_sequence,
                )

                service.apply_opshop_workspace_assignments(
                    OpShopWorkspaceAssignmentBatchRequest(
                        dispatch_date=PICKUP_DATE,
                        assignments=[
                            {"pickup_task_id": task_id, "driver_id": "D002"}
                        ],
                    )
                )
                self.assertIsNone(
                    repository.get_opshop_pickup_task(task_id).trip_sequence
                )

                task = repository.get_opshop_pickup_task(task_id)
                repository.upsert_opshop_pickup_task(
                    replace(task, trip_sequence=9)
                )
                service.unassign_opshop_workspace_pickup(
                    OpShopWorkspaceUnassignPickupRequest(
                        dispatch_date=PICKUP_DATE,
                        pickup_task_id=task_id,
                    )
                )
                self.assertIsNone(
                    repository.get_opshop_pickup_task(task_id).trip_sequence
                )

                service.apply_opshop_workspace_assignments(
                    OpShopWorkspaceAssignmentBatchRequest(
                        dispatch_date=PICKUP_DATE,
                        assignments=[
                            {"pickup_task_id": task_id, "driver_id": "D001"}
                        ],
                    )
                )
                task = repository.get_opshop_pickup_task(task_id)
                repository.upsert_opshop_pickup_task(
                    replace(task, trip_sequence=7)
                )
                service.update_opshop_pickup_task(
                    task_id,
                    UpdateOpShopPickupTaskRequest(
                        dispatch_date=PICKUP_DATE,
                        pickup_date="2026-09-08",
                    ),
                )
                self.assertIsNone(
                    repository.get_opshop_pickup_task(task_id).trip_sequence
                )

    def test_null_sequences_use_existing_deterministic_fallback(self):
        repository = InMemoryManualDispatchRepository()
        service, task_ids = self._seed_countryside_trip(repository)

        board = service.get_opshop_trip_summary_board(PICKUP_DATE)

        self.assertEqual(
            [task_ids[1], task_ids[2], task_ids[0]],
            self._countryside_ids(board),
        )

    def _repositories(self):
        yield "in-memory", InMemoryManualDispatchRepository()
        yield "sqlite", SQLiteManualDispatchRepository(
            self.temp_dir / "manual_dispatch.sqlite3"
        )

    def _seed_countryside_trip(self, repository):
        self._ensure_driver(repository, "D001", "Driver One")
        self._ensure_driver(repository, "D002", "Driver Two")
        service = ManualDispatchService(repository)
        task_ids = [
            self._create_pickup(service, "Country Z", "ZZZZ").pickup_task_id,
            self._create_pickup(service, "Country A", "AAAA").pickup_task_id,
            self._create_pickup(service, "Country M", "MMMM").pickup_task_id,
        ]
        return service, task_ids

    def _create_pickup(
        self,
        service,
        name,
        suburb,
        *,
        pickup_category="COUNTRYSIDE",
        pickup_date=PICKUP_DATE,
        driver_id="D001",
        run_type="ON_CALL",
    ):
        route_group_id = None
        if pickup_category == "COUNTRYSIDE":
            group = service.create_countryside_route_group(
                CreateOpShopCountrysideRouteGroupRequest(
                    route_group_name=f"Route {name}"
                )
            )
            route_group_id = group.route_group_id
        template = service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type=run_type,
                run_day="MONDAY" if run_type == "REGULAR" else None,
                pickup_category=pickup_category,
                route_group_id=route_group_id,
                name=name,
                suburb=suburb,
                street_address=f"1 {name} Road",
                pickup_frequency=(
                    "Weekly" if run_type == "REGULAR" else "On Call"
                ),
            )
        )
        create_task = (
            service.create_opshop_pickup_task
            if run_type == "REGULAR"
            else service.create_oncall_opshop_pickup_task
        )
        return create_task(
            CreateOpShopPickupTaskRequest(
                schedule_id=template.schedule_id,
                pickup_date=pickup_date,
                assigned_driver_id=driver_id,
                dispatch_date=pickup_date,
            )
        )

    @staticmethod
    def _ensure_driver(repository, driver_id, name):
        if repository.get_driver(driver_id):
            return
        repository.create_driver(
            Driver(
                driver_id=driver_id,
                name=name,
                start_time="07:00",
                end_time="15:00",
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
            )
        )

    @staticmethod
    def _reorder_request(ordered_ids):
        return SimpleNamespace(
            pickup_date=PICKUP_DATE,
            driver_id="D001",
            ordered_pickup_task_ids=list(ordered_ids),
        )

    @staticmethod
    def _countryside_ids(board):
        return [
            pickup.pickup_task_id
            for pickup in board.opshop_pickups
            if pickup.pickup_category == "COUNTRYSIDE"
            and pickup.assigned_driver_id == "D001"
        ]

    @staticmethod
    def _sequence_snapshot(repository, task_ids):
        return {
            task_id: repository.get_opshop_pickup_task(task_id).trip_sequence
            for task_id in task_ids
        }


if __name__ == "__main__":
    unittest.main()
