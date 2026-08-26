import json
import shutil
import unittest
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignTaskRequest,
    DeliveryRunSheet,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetTrip,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    Driver,
    Order,
    UnassignTaskRequest,
)
from backend.services.manual_dispatch.delivery_import_date import next_weekday_after
from backend.services.manual_dispatch.delivery_order_date_rollover_service import (
    DeliveryOrderDateRolloverService,
)
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService
from tools.check_logbook_integrity import check_logbook_integrity
from tools.logbook_contract import KNOWN_ACTIONS


ROLLOVER_ACTION = "ORDER_DELIVERY_DATE_ROLLED_FORWARD"


class _CapturingLogbook:
    def __init__(self):
        self.entries = []

    def record(self, **entry):
        self.entries.append(entry)


class DeliveryOrderDateRolloverTest(unittest.TestCase):
    def setUp(self):
        self.temp_root = Path.cwd() / "tmp" / f"delivery-rollover-{uuid.uuid4().hex}"
        self.temp_root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_next_weekday_after_is_deterministic_for_every_weekend_edge(self):
        cases = {
            date(2026, 8, 24): date(2026, 8, 25),
            date(2026, 8, 25): date(2026, 8, 26),
            date(2026, 8, 27): date(2026, 8, 28),
            date(2026, 8, 28): date(2026, 8, 31),
            date(2026, 8, 29): date(2026, 8, 31),
            date(2026, 8, 30): date(2026, 8, 31),
        }
        for current_date, expected in cases.items():
            with self.subTest(current_date=current_date):
                self.assertEqual(expected, next_weekday_after(current_date))

    def test_repository_parity_uses_catch_up_and_protects_ineligible_orders(self):
        for label, repository in self._repositories():
            with self.subTest(repository=label):
                for order in (
                    self._order("TODAY", "2026-08-25"),
                    self._order("PAST", "2026-08-20"),
                    self._order("FUTURE", "2026-08-26"),
                    self._order("ASSIGNED", "2026-08-24"),
                    self._order("RESERVED", "2026-08-24"),
                    self._order("CANCELLED", "2026-08-24", status="CANCELLED"),
                    self._order("FINALIZED", "2026-08-24", status="FINALIZED"),
                ):
                    repository.create_order(order)
                repository.upsert_assignment(
                    "2026-08-01",
                    "ORDER",
                    "ASSIGNED",
                    "D001",
                    "trip1",
                )
                repository.upsert_delivery_run_sheet(self._reserved_run_sheet("RESERVED"))

                changes = DeliveryOrderDateRolloverService(
                    repository,
                    today_provider=lambda: date(2026, 8, 25),
                ).roll_forward_eligible_unassigned_delivery_orders()

                self.assertEqual(
                    {"PAST", "TODAY"},
                    {change["order_id"] for change in changes},
                )
                self.assertEqual("2026-08-26", repository.get_order("TODAY").delivery_date)
                self.assertEqual("2026-08-26", repository.get_order("PAST").delivery_date)
                self.assertEqual("2026-08-26", repository.get_order("FUTURE").delivery_date)
                self.assertEqual("2026-08-24", repository.get_order("ASSIGNED").delivery_date)
                self.assertEqual("2026-08-24", repository.get_order("RESERVED").delivery_date)
                self.assertEqual("2026-08-24", repository.get_order("CANCELLED").delivery_date)
                self.assertEqual("2026-08-24", repository.get_order("FINALIZED").delivery_date)

    def test_repository_parity_is_idempotent_and_rolls_back_failures(self):
        for label, repository in self._repositories():
            with self.subTest(repository=label):
                repository.create_order(self._order("ROLLBACK", "2026-08-25"))
                service = DeliveryOrderDateRolloverService(
                    repository,
                    today_provider=lambda: date(2026, 8, 25),
                )
                original = repository.roll_forward_unassigned_delivery_order_dates

                def update_then_fail(*args, **kwargs):
                    original(*args, **kwargs)
                    raise RuntimeError("injected rollover failure")

                with patch.object(
                    repository,
                    "roll_forward_unassigned_delivery_order_dates",
                    side_effect=update_then_fail,
                ):
                    with self.assertRaisesRegex(RuntimeError, "injected rollover failure"):
                        service.roll_forward_eligible_unassigned_delivery_orders()
                self.assertEqual("2026-08-25", repository.get_order("ROLLBACK").delivery_date)

                first = service.roll_forward_eligible_unassigned_delivery_orders()
                second = service.roll_forward_eligible_unassigned_delivery_orders()
                self.assertEqual(1, len(first))
                self.assertEqual([], second)
                self.assertEqual("2026-08-26", repository.get_order("ROLLBACK").delivery_date)

    def test_board_rolls_persisted_date_once_and_records_one_system_event(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(replace(repository.get_order("ORD-001"), delivery_date="2026-08-25"))
        for order_id in ("ORD-002", "ORD-003"):
            repository.update_order(
                replace(repository.get_order(order_id), delivery_date="2026-09-01")
            )
        logbook = _CapturingLogbook()
        service = self._service(repository, logbook, date(2026, 8, 25))

        first = service.get_delivery_workspace_board("2026-08-01")
        second = service.get_delivery_workspace_board("2026-08-01")

        self.assertEqual("2026-08-26", repository.get_order("ORD-001").delivery_date)
        self.assertEqual(
            "2026-08-26",
            next(order.delivery_date for order in first.orders if order.order_id == "ORD-001"),
        )
        self.assertEqual(
            "2026-08-26",
            next(order.delivery_date for order in second.orders if order.order_id == "ORD-001"),
        )
        entries = [entry for entry in logbook.entries if entry["action"] == ROLLOVER_ACTION]
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("System", entry["actor"])
        self.assertEqual("2026-08-26", entry["delivery_date"])
        self.assertEqual("2026-08-25", entry["metadata"]["previous_delivery_date"])
        self.assertEqual("2026-08-26", entry["metadata"]["new_delivery_date"])
        self.assertEqual("unassigned_daily_rollover", entry["metadata"]["reason"])
        self.assertIn(ROLLOVER_ACTION, KNOWN_ACTIONS)

    def test_workspace_assignment_rolls_stale_order_inside_authoritative_path(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(replace(repository.get_order("ORD-001"), delivery_date="2026-08-25"))
        service = self._service(repository, _CapturingLogbook(), date(2026, 8, 26))

        service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date="2026-08-01",
                order_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )

        self.assertEqual("2026-08-27", repository.get_order("ORD-001").delivery_date)
        self.assertIsNotNone(repository.find_assignment_for_task("ORDER", "ORD-001"))
        self.assertEqual(
            ["ORD-001"],
            [
                assignment.task_id
                for assignment in repository.list_delivery_order_assignments_for_delivery_date(
                    "2026-08-27"
                )
            ],
        )
        self.assertEqual(
            [],
            repository.list_delivery_order_assignments_for_delivery_date("2026-08-25"),
        )

    def test_workspace_unassign_rolls_newly_unassigned_order_and_returned_board(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(replace(repository.get_order("ORD-001"), delivery_date="2026-08-25"))
        repository.upsert_assignment(
            "2026-08-01",
            "ORDER",
            "ORD-001",
            "D001",
            "trip1",
        )
        service = self._service(repository, _CapturingLogbook(), date(2026, 8, 27))

        board = service.unassign_delivery_workspace_order(
            DeliveryWorkspaceUnassignOrderRequest(
                dispatch_date="2026-08-01",
                order_id="ORD-001",
            )
        )

        self.assertIsNone(repository.find_assignment_for_task("ORDER", "ORD-001"))
        self.assertEqual("2026-08-28", repository.get_order("ORD-001").delivery_date)
        self.assertEqual(
            "2026-08-28",
            next(order.delivery_date for order in board.orders if order.order_id == "ORD-001"),
        )

    def test_workspace_unassign_on_friday_rolls_to_monday(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(replace(repository.get_order("ORD-001"), delivery_date="2026-08-28"))
        repository.upsert_assignment(
            "2026-08-01",
            "ORDER",
            "ORD-001",
            "D001",
            "trip1",
        )
        service = self._service(repository, _CapturingLogbook(), date(2026, 8, 28))

        service.unassign_delivery_workspace_order(
            DeliveryWorkspaceUnassignOrderRequest(
                dispatch_date="2026-08-01",
                order_id="ORD-001",
            )
        )

        self.assertEqual("2026-08-31", repository.get_order("ORD-001").delivery_date)

    def test_legacy_assignment_and_unassign_paths_use_the_same_rollover_rule(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(replace(repository.get_order("ORD-001"), delivery_date="2026-08-25"))
        service = self._service(repository, _CapturingLogbook(), date(2026, 8, 26))

        service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-08-01",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        self.assertEqual("2026-08-27", repository.get_order("ORD-001").delivery_date)
        service.delivery_order_date_rollover_service.today_provider = lambda: date(2026, 8, 28)
        service.unassign_task(
            UnassignTaskRequest(
                dispatch_date="2026-08-01",
                task_type="ORDER",
                task_id="ORD-001",
            )
        )
        self.assertEqual("2026-08-31", repository.get_order("ORD-001").delivery_date)

    def test_workspace_assignment_and_unassign_have_sqlite_inmemory_parity(self):
        for label, repository in self._repositories():
            with self.subTest(repository=label):
                repository.create_order(self._order("WORKSPACE", "2026-08-25"))
                service = self._service(
                    repository,
                    _CapturingLogbook(),
                    date(2026, 8, 26),
                )
                service.assign_delivery_workspace_order(
                    DeliveryWorkspaceAssignOrderRequest(
                        dispatch_date="2026-08-01",
                        order_id="WORKSPACE",
                        driver_id="D001",
                        trip_no="trip1",
                    )
                )
                self.assertEqual(
                    "2026-08-27",
                    repository.get_order("WORKSPACE").delivery_date,
                )

                service.delivery_order_date_rollover_service.today_provider = (
                    lambda: date(2026, 8, 28)
                )
                board = service.unassign_delivery_workspace_order(
                    DeliveryWorkspaceUnassignOrderRequest(
                        dispatch_date="2026-08-01",
                        order_id="WORKSPACE",
                    )
                )
                self.assertEqual(
                    "2026-08-31",
                    repository.get_order("WORKSPACE").delivery_date,
                )
                self.assertEqual(
                    "2026-08-31",
                    next(
                        order.delivery_date
                        for order in board.orders
                        if order.order_id == "WORKSPACE"
                    ),
                )

    def test_rollover_logbook_event_passes_the_existing_integrity_contract(self):
        repository = InMemoryManualDispatchRepository()
        repository.update_order(
            replace(repository.get_order("ORD-001"), delivery_date="2026-08-25")
        )
        for order_id in ("ORD-002", "ORD-003"):
            repository.update_order(
                replace(repository.get_order(order_id), delivery_date="2026-09-01")
            )
        logbook_dir = self.temp_root / "logbook"
        service = self._service(
            repository,
            LogbookFileService(logbook_dir),
            date(2026, 8, 25),
        )

        service.get_delivery_workspace_board("2026-08-01")

        result = check_logbook_integrity(logbook_dir)
        self.assertTrue(result.ok, msg=[issue.to_dict() for issue in result.issues])
        logbook_file = next(logbook_dir.glob("manual_dispatch_logbook_*.txt"))
        entries = [
            json.loads(line)
            for line in logbook_file.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(1, len(entries))
        self.assertEqual(ROLLOVER_ACTION, entries[0]["action"])
        self.assertEqual("System", entries[0]["actor"])
        self.assertIsInstance(entries[0]["time"], str)

    def _repositories(self):
        in_memory = InMemoryManualDispatchRepository()
        in_memory.orders.clear()
        sqlite = SQLiteManualDispatchRepository(self.temp_root / "manual_dispatch.sqlite3")
        sqlite.create_driver(
            Driver(
                driver_id="D001",
                name="John",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
            )
        )
        return [("in-memory", in_memory), ("sqlite", sqlite)]

    @staticmethod
    def _service(repository, logbook, current_date):
        service = ManualDispatchService(repository, logbook=logbook)
        service.delivery_order_date_rollover_service.today_provider = (
            lambda: current_date
        )
        return service

    @staticmethod
    def _order(order_id, delivery_date, status="ACTIVE"):
        return Order(
            order_id=order_id,
            invoice_number=f"INV-{order_id}",
            order_no=None,
            company_name=f"Customer {order_id}",
            phone=None,
            delivery_address="1 Test Street",
            suburb="Coburg",
            postcode="3058",
            delivery_date=delivery_date,
            zone="North",
            urgency="Normal",
            preferred_driver_id=None,
            pallet_quantity=1,
            loose_bags_quantity=0,
            start_time=None,
            end_time=None,
            note=None,
            status=status,
        )

    @staticmethod
    def _reserved_run_sheet(order_id):
        return DeliveryRunSheet(
            run_sheet_id=f"RUN-{order_id}",
            dispatch_date="2026-08-01",
            delivery_date="2026-08-24",
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id=None,
            vehicle_rego_snapshot=None,
            total_pallets=1,
            total_loose_bags=0,
            status="GENERATED",
            generated_at="2026-08-24T00:00:00+00:00",
            saved_at=None,
            saved_by_account_name=None,
            saved_by_account_id=None,
            legacy_summary_id=None,
            trips=[
                DeliveryRunSheetTrip(
                    trip_no="trip1",
                    orders=[
                        DeliveryRunSheetOrderSnapshot(
                            row_id=f"ROW-{order_id}",
                            trip_no="trip1",
                            row_no=1,
                            task_type="ORDER",
                            task_id=order_id,
                            order_id_snapshot=order_id,
                            invoice_number_snapshot=f"INV-{order_id}",
                            order_no_snapshot=None,
                            company_name_snapshot="Reserved Customer",
                            suburb_snapshot="Coburg",
                            delivery_address_snapshot="1 Test Street",
                            product_snapshot=None,
                            pallet_quantity_snapshot=1,
                            loose_bags_quantity_snapshot=0,
                            note_snapshot=None,
                        )
                    ],
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
