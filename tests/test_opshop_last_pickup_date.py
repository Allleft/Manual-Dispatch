import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    OpShopLocation,
    OpShopPickupCollection,
    OpShopPickupCollectionRowSnapshot,
    OpShopPickupSchedule,
    OpShopPickupTask,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class OpShopLastPickupDateRepositoryContractTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-last-pickup-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_saved_history_batch_semantics_match_sqlite_and_in_memory(self):
        repositories = [
            InMemoryManualDispatchRepository(),
            self._sqlite_repository(),
        ]
        for repository in repositories:
            with self.subTest(repository=type(repository).__name__):
                self._seed_repository_contract(repository)

                self.assertEqual(
                    {
                        "OPSHOP-A": ["2026-06-01", "2026-07-10"],
                        "OPSHOP-B": ["2026-07-08"],
                    },
                    repository.list_saved_opshop_pickup_dates_by_opshop_ids(
                        {"OPSHOP-A", "OPSHOP-B"},
                        "2026-07-24",
                    ),
                )
                self.assertEqual(
                    {},
                    repository.list_saved_opshop_pickup_dates_by_opshop_ids(
                        set(),
                        "2026-07-24",
                    ),
                )
                with self.assertRaisesRegex(ValueError, "valid YYYY-MM-DD"):
                    repository.list_saved_opshop_pickup_dates_by_opshop_ids(
                        {"OPSHOP-A"},
                        "2026-02-31",
                    )

    def _sqlite_repository(self):
        db_path = self.temp_dir / "manual_dispatch.sqlite3"
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "0"}):
            return SQLiteManualDispatchRepository(db_path)

    def _seed_repository_contract(self, repository):
        for opshop_id in ("OPSHOP-A", "OPSHOP-B"):
            repository.upsert_opshop_location(_location(opshop_id, "Shared Name"))
            repository.upsert_opshop_pickup_schedule(_schedule(opshop_id))

        for task_id, opshop_id, pickup_date in (
            ("HISTORY-A-1", "OPSHOP-A", "2026-06-01"),
            ("HISTORY-A-2", "OPSHOP-A", "2026-07-10"),
            ("HISTORY-A-SAME", "OPSHOP-A", "2026-07-24"),
            ("HISTORY-A-FUTURE", "OPSHOP-A", "2026-07-25"),
            ("HISTORY-B-1", "OPSHOP-B", "2026-07-08"),
            ("SCHEDULED-ONLY-A", "OPSHOP-A", "2026-07-17"),
        ):
            repository.upsert_opshop_pickup_task(
                _task(
                    task_id,
                    opshop_id,
                    pickup_date,
                    status=("ACTIVE" if task_id == "SCHEDULED-ONLY-A" else "COMPLETED"),
                )
            )

        collections = [
            _collection(
                "SAVED-A-1",
                "SAVED",
                "2026-06-01",
                [_snapshot("ROW-A-1", "HISTORY-A-1", "2026-06-01")],
            ),
            _collection(
                "SAVED-A-2",
                "SAVED",
                "2026-07-10",
                [
                    _snapshot("ROW-A-2", "HISTORY-A-2", "2026-07-10"),
                    _snapshot("ROW-A-2-DUP", "HISTORY-A-2", "2026-07-10"),
                ],
            ),
            _collection(
                "GENERATED-A",
                "GENERATED",
                "2026-07-17",
                [_snapshot("ROW-A-GENERATED", "SCHEDULED-ONLY-A", "2026-07-17")],
            ),
            _collection(
                "SAVED-A-SAME",
                "SAVED",
                "2026-07-24",
                [_snapshot("ROW-A-SAME", "HISTORY-A-SAME", "2026-07-24")],
            ),
            _collection(
                "SAVED-A-FUTURE",
                "SAVED",
                "2026-07-25",
                [_snapshot("ROW-A-FUTURE", "HISTORY-A-FUTURE", "2026-07-25")],
            ),
            _collection(
                "SAVED-B-1",
                "SAVED",
                "2026-07-08",
                [_snapshot("ROW-B-1", "HISTORY-B-1", "2026-07-08")],
            ),
            _collection(
                "SAVED-INVALID",
                "SAVED",
                "2026-07-09",
                [
                    _snapshot("ROW-UNRESOLVED", "MISSING-TASK", "2026-07-05"),
                    _snapshot("ROW-MALFORMED", "HISTORY-A-2", "2026-02-31"),
                    _snapshot("ROW-NO-TASK", None, "2026-07-04"),
                ],
            ),
        ]
        for collection in collections:
            repository.upsert_opshop_pickup_collection(collection)


class OpShopLastPickupDateBoardServiceTest(unittest.TestCase):
    def test_board_uses_one_batch_and_each_regular_row_uses_its_own_date(self):
        repository = InMemoryManualDispatchRepository()
        for opshop_id in ("OPSHOP-A", "OPSHOP-B"):
            repository.upsert_opshop_location(_location(opshop_id, "Shared Name"))
            repository.upsert_opshop_pickup_schedule(
                _schedule(opshop_id, run_day="FRIDAY")
            )

        for task_id, pickup_date in (
            ("HISTORY-A-15", "2026-07-15"),
            ("HISTORY-A-25", "2026-07-25"),
        ):
            repository.upsert_opshop_pickup_task(
                _task(task_id, "OPSHOP-A", pickup_date, status="COMPLETED")
            )
            repository.upsert_opshop_pickup_collection(
                _collection(
                    f"SAVED-{task_id}",
                    "SAVED",
                    pickup_date,
                    [_snapshot(f"ROW-{task_id}", task_id, pickup_date)],
                )
            )

        service = ManualDispatchService(repository)
        with patch.object(
            repository,
            "list_saved_opshop_pickup_dates_by_opshop_ids",
            wraps=repository.list_saved_opshop_pickup_dates_by_opshop_ids,
        ) as batch_lookup:
            board = service.get_opshop_workspace_board("2026-07-24")

        self.assertEqual(1, batch_lookup.call_count)
        regular = {
            (pickup.opshop_id, pickup.pickup_date): pickup.last_pickup_date
            for pickup in board.opshop_pickups
            if pickup.run_type == "REGULAR"
        }
        self.assertEqual(
            {
                ("OPSHOP-A", "2026-07-24"): "2026-07-15",
                ("OPSHOP-A", "2026-07-31"): "2026-07-25",
                ("OPSHOP-B", "2026-07-24"): None,
                ("OPSHOP-B", "2026-07-31"): None,
            },
            regular,
        )
        payload = to_dict(board)
        self.assertTrue(
            all("last_pickup_date" in pickup for pickup in payload["opshop_pickups"])
        )


def _location(opshop_id, name):
    return OpShopLocation(
        opshop_id=opshop_id,
        name=name,
        suburb="COBURG",
        street_address=f"{opshop_id} Test Street",
        area_region="NORTH",
        primary_contact="Test Contact",
        primary_phone="0400 000 000",
        secondary_contact=None,
        secondary_phone=None,
        access_type=None,
        key_required=False,
        trailer_restriction=None,
        status_notes=None,
        is_active=True,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _schedule(opshop_id, run_day="MONDAY"):
    return OpShopPickupSchedule(
        schedule_id=f"SCHEDULE-{opshop_id}",
        opshop_id=opshop_id,
        run_day=run_day,
        run_type="REGULAR",
        pickup_frequency="Weekly",
        time_window="09:00-12:00",
        call_before_arrival=False,
        call_timing=None,
        status="Active",
        active_flag=True,
        fortnight_group=None,
        review_required=False,
        review_reason=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _task(task_id, opshop_id, pickup_date, status="ACTIVE"):
    return OpShopPickupTask(
        pickup_task_id=task_id,
        schedule_id=f"SCHEDULE-{opshop_id}",
        opshop_id=opshop_id,
        pickup_date=pickup_date,
        task_type="OPSHOP_PICKUP",
        generated_from="REGULAR",
        status=status,
        dispatch_date=pickup_date,
        driver_id=None,
        trip_no=None,
        notes=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _collection(collection_id, status, pickup_date, pickups):
    for row_no, pickup in enumerate(pickups, start=1):
        pickup.row_no = row_no
    return OpShopPickupCollection(
        collection_id=collection_id,
        dispatch_date=pickup_date,
        pickup_date=pickup_date,
        driver_id=f"DRIVER-{collection_id}",
        driver_name_snapshot="Test Driver",
        status=status,
        generated_at="2026-01-01T00:00:00+00:00",
        saved_at=("2026-01-01T01:00:00+00:00" if status == "SAVED" else None),
        saved_by_account_name=("Tester" if status == "SAVED" else None),
        saved_by_account_id=None,
        legacy_summary_id=None,
        pickups=pickups,
    )


def _snapshot(row_id, task_id, pickup_date):
    return OpShopPickupCollectionRowSnapshot(
        row_id=row_id,
        row_no=1,
        pickup_task_id_snapshot=task_id,
        opshop_name_snapshot="Synthetic OP SHOP",
        suburb_snapshot="COBURG",
        street_address_snapshot="1 Test Street",
        area_region_snapshot="NORTH",
        pickup_date_snapshot=pickup_date,
        run_type_snapshot="REGULAR",
        pickup_category_snapshot="NORMAL",
        route_group_id_snapshot=None,
        route_group_name_snapshot=None,
        pickup_frequency_snapshot="Weekly",
        time_window_snapshot="09:00-12:00",
        primary_contact_snapshot=None,
        primary_phone_snapshot=None,
        secondary_contact_snapshot=None,
        secondary_phone_snapshot=None,
        access_type_snapshot=None,
        key_required_snapshot=False,
        trailer_restriction_snapshot=None,
        notes_snapshot=None,
        status_snapshot="ASSIGNED",
    )


if __name__ == "__main__":
    unittest.main()
