import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    RegisterOperatorAccountRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
)
from backend.services.manual_dispatch.delivery_run_sheet_lock import (
    is_delivery_run_sheet_finalized,
)
from backend.services.manual_dispatch.opshop_pickup_collection_lock import (
    is_opshop_pickup_collection_finalized,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class WorkspaceServicesTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-services-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.dispatch_date = "2026-05-05"
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Workspace Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delivery_generate_cancel_and_empty_rules(self):
        self._assign_order("ORD-001", "D001", "trip1")
        generated = self._generate_delivery()

        self.assertEqual("GENERATED", generated.status)
        self.assertEqual(["ORDER"], self._delivery_task_types(generated))
        self.assertEqual(2, generated.total_pallets)
        self.assertEqual(0, generated.total_loose_bags)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self._generate_delivery()

        self.assertTrue(
            self.service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        )
        self.assertIsNotNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "ORDER",
                "ORD-001",
            )
        )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.service.get_delivery_run_sheet(generated.run_sheet_id)

        self.service.unassign_task(
            self._unassign_request("ORDER", "ORD-001")
        )
        with self.assertRaisesRegex(ValueError, "assigned Delivery Order"):
            self._generate_delivery()

    def test_in_memory_delivery_run_sheet_reservation_is_global(self):
        service = ManualDispatchService()
        account = service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="In Memory Workspace Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        service.assign_task(
            AssignTaskRequest(
                dispatch_date="2026-05-05",
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        generated = service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date="2026-05-05",
                delivery_date="2026-05-05",
                driver_id="D001",
            )
        )

        self.assertNotIn(
            "ORD-001",
            {
                order.order_id
                for order in service.get_delivery_workspace_board("2026-05-06").orders
            },
        )
        service.cancel_generated_delivery_run_sheet(generated.run_sheet_id)
        self.assertIn(
            "ORD-001",
            {
                order.order_id
                for order in service.get_delivery_workspace_board("2026-05-06").orders
            },
        )

        saved = service.save_generated_delivery_run_sheet(
            service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date="2026-05-05",
                    delivery_date="2026-05-05",
                    driver_id="D001",
                )
            ).run_sheet_id,
            SaveGeneratedWorkspaceSnapshotRequest(
                saved_by_account_name=account.account_name,
                saved_by_account_id=account.account_id,
            ),
        )
        self.assertEqual("SAVED", saved.status)
        self.assertNotIn(
            "ORD-001",
            {
                order.order_id
                for order in service.get_delivery_workspace_board("2026-05-06").orders
            },
        )

    def test_opshop_generate_cancel_and_empty_rules(self):
        self._seed_and_assign_pickup("PICKUP-001")
        generated = self._generate_collection()

        self.assertEqual("GENERATED", generated.status)
        self.assertEqual(["PICKUP-001"], self._pickup_task_ids(generated))
        self.assertTrue(generated.pickups[0].call_before_arrival_snapshot)
        self.assertEqual("30 minutes", generated.pickups[0].call_timing_snapshot)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self._generate_collection()

        self.assertTrue(
            self.service.cancel_generated_opshop_pickup_collection(
                generated.collection_id
            )
        )
        self.assertIsNotNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "OPSHOP_PICKUP",
                "PICKUP-001",
            )
        )

        self.service.unassign_task(
            self._unassign_request("OPSHOP_PICKUP", "PICKUP-001")
        )
        with self.assertRaisesRegex(ValueError, "assigned OP SHOP pickup"):
            self._generate_collection()

    def test_saved_delivery_snapshot_is_immutable_and_lock_is_delivery_only(self):
        self._assign_order("ORD-001", "D001", "trip1")
        generated = self._generate_delivery()
        saved = self.service.save_generated_delivery_run_sheet(
            generated.run_sheet_id,
            self._save_request(),
        )

        self.assertEqual("SAVED", saved.status)
        self.assertTrue(
            is_delivery_run_sheet_finalized(
                self.repository,
                self.dispatch_date,
                "D001",
                self.dispatch_date,
            )
        )
        self.assertFalse(
            is_opshop_pickup_collection_finalized(
                self.repository,
                self.dispatch_date,
                "D001",
                self.dispatch_date,
            )
        )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.save_generated_delivery_run_sheet(
                saved.run_sheet_id,
                self._save_request(),
            )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.cancel_generated_delivery_run_sheet(saved.run_sheet_id)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self._generate_delivery()

        self._seed_and_assign_pickup("PICKUP-AFTER-DELIVERY")
        self.assertIsNotNone(
            self.repository.get_assignment(
                self.dispatch_date,
                "OPSHOP_PICKUP",
                "PICKUP-AFTER-DELIVERY",
            )
        )

    def test_saved_opshop_snapshot_is_immutable_and_does_not_lock_delivery_or_vehicle(self):
        self._seed_and_assign_pickup("PICKUP-001")
        generated = self._generate_collection()
        saved = self.service.save_generated_opshop_pickup_collection(
            generated.collection_id,
            self._save_request(),
        )

        self.assertEqual("SAVED", saved.status)
        self.assertTrue(
            is_opshop_pickup_collection_finalized(
                self.repository,
                self.dispatch_date,
                "D001",
                self.dispatch_date,
            )
        )
        self.assertFalse(
            is_delivery_run_sheet_finalized(
                self.repository,
                self.dispatch_date,
                "D001",
                self.dispatch_date,
            )
        )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.save_generated_opshop_pickup_collection(
                saved.collection_id,
                self._save_request(),
            )
        with self.assertRaisesRegex(ValueError, "Only generated"):
            self.service.cancel_generated_opshop_pickup_collection(
                saved.collection_id
            )

        self._assign_order("ORD-001", "D001", "trip1")
        vehicle_assignment = self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id="D001",
                vehicle_id="V001",
            )
        )
        self.assertEqual("V001", vehicle_assignment.vehicle_id)

    def test_same_driver_date_can_save_delivery_and_opshop_independently(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._seed_and_assign_pickup("PICKUP-001")

        delivery = self.service.save_generated_delivery_run_sheet(
            self._generate_delivery().run_sheet_id,
            self._save_request(),
        )
        collection = self.service.save_generated_opshop_pickup_collection(
            self._generate_collection().collection_id,
            self._save_request(),
        )

        self.assertEqual("SAVED", delivery.status)
        self.assertEqual("SAVED", collection.status)
        self.assertEqual(["ORDER"], self._delivery_task_types(delivery))
        self.assertEqual(["PICKUP-001"], self._pickup_task_ids(collection))

    def test_new_services_do_not_depend_on_legacy_final_summary_locks(self):
        service_paths = [
            Path("backend/services/manual_dispatch/delivery_run_sheet_service.py"),
            Path(
                "backend/services/manual_dispatch/"
                "opshop_pickup_collection_service.py"
            ),
            Path("backend/services/manual_dispatch/delivery_run_sheet_lock.py"),
            Path(
                "backend/services/manual_dispatch/"
                "opshop_pickup_collection_lock.py"
            ),
        ]
        forbidden = {
            "has_saved_final_trip_summary",
            "is_driver_delivery_date_finalized",
            "list_finalized_opshop_pickup_assignments",
        }
        combined_source = "\n".join(
            path.read_text(encoding="utf-8") for path in service_paths
        )
        for name in forbidden:
            self.assertNotIn(name, combined_source)

    def _assign_order(self, order_id, driver_id, trip_no):
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id=order_id,
                driver_id=driver_id,
                trip_no=trip_no,
            )
        )

    def _seed_and_assign_pickup(self, task_id):
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id=f"OPSHOP-{task_id}",
                name="Northside Op Shop",
                suburb="Coburg",
                street_address="1 Sydney Road",
                area_region="North",
                primary_contact="Mary",
                primary_phone="0400 000 001",
                secondary_contact="John",
                secondary_phone="0400 000 002",
                access_type="Rear dock",
                key_required=True,
                trailer_restriction="Small truck only",
                status_notes="Ring first",
                is_active=True,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        schedule_id = f"SCHEDULE-{task_id}"
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id=f"OPSHOP-{task_id}",
                run_day="TUESDAY",
                run_type="ON_CALL",
                pickup_frequency="Weekly",
                time_window="09:00-12:00",
                call_before_arrival=True,
                call_timing="30 minutes",
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
                pickup_category="COUNTRYSIDE",
                route_group_id=None,
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=task_id,
                schedule_id=schedule_id,
                opshop_id=f"OPSHOP-{task_id}",
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date=self.dispatch_date,
                driver_id=None,
                trip_no=None,
                notes="Leave at rear door",
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        return self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                task_id=task_id,
                driver_id="D001",
                trip_no="trip1",
            )
        )

    def _generate_delivery(self):
        return self.service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=self.dispatch_date,
                driver_id="D001",
            )
        )

    def _generate_collection(self):
        return self.service.create_generated_opshop_pickup_collection(
            GenerateOpShopPickupCollectionRequest(
                dispatch_date=self.dispatch_date,
                pickup_date=self.dispatch_date,
                driver_id="D001",
            )
        )

    def _save_request(self):
        return SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
        )

    def _unassign_request(self, task_type, task_id):
        from backend.schemas import UnassignTaskRequest

        return UnassignTaskRequest(
            dispatch_date=self.dispatch_date,
            task_type=task_type,
            task_id=task_id,
        )

    @staticmethod
    def _delivery_task_types(run_sheet):
        return [order.task_type for trip in run_sheet.trips for order in trip.orders]

    @staticmethod
    def _pickup_task_ids(collection):
        return [pickup.pickup_task_id_snapshot for pickup in collection.pickups]


if __name__ == "__main__":
    unittest.main()
