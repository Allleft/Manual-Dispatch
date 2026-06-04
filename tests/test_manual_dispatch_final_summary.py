import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateOrderRequest,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
    RegisterOperatorAccountRequest,
    SaveFinalTripSummaryRequest,
    UpdateOrderRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class ManualDispatchFinalSummaryTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"final-summary-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.dispatch_date = "2026-05-05"
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Mandy",
                password="secret123",
                confirm_password="secret123",
            )
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repository_initializes_final_summary_tables(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertIn("final_trip_summaries", tables)
        self.assertIn("final_trip_summary_rows", tables)
        self.assertIn("final_trip_summary_opshop_pickup_rows", tables)

    def test_save_final_summary_persists_snapshot_rows(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._assign_vehicle("D001", "V002")

        summary = self.service.save_final_trip_summary(self._summary_request())

        self.assertTrue(summary.summary_id.startswith("FTS-"))
        self.assertEqual(self.dispatch_date, summary.delivery_date)
        self.assertEqual("John", summary.driver_name_snapshot)
        self.assertEqual("Mandy", summary.saved_by_account_name)
        self.assertEqual("XYZ888", summary.vehicle_rego_snapshot)
        self.assertEqual(1, len(summary.trips))
        self.assertEqual("trip1", summary.trips[0].trip_no)
        self.assertEqual("ORD-001", summary.trips[0].orders[0].task_id)
        self.assertEqual("Demo Customer A", summary.trips[0].orders[0].company_name_snapshot)

    def test_save_final_summary_preserves_trip_grouping_and_skips_empty_trips(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._assign_order("ORD-003", "D001", "trip2")

        summary = self.service.save_final_trip_summary(
            self._summary_request(
                trips=[
                    self._trip_payload("trip1", [self._order_payload("ORD-001")]),
                    self._trip_payload("trip2", [self._order_payload("ORD-003")]),
                ]
            )
        )

        self.assertEqual(["trip1", "trip2"], [trip.trip_no for trip in summary.trips])
        self.assertEqual("ORD-001", summary.trips[0].orders[0].task_id)
        self.assertEqual("ORD-003", summary.trips[1].orders[0].task_id)

    def test_save_final_summary_does_not_persist_empty_trips(self):
        self._assign_order("ORD-001", "D001", "trip1")

        summary = self.service.save_final_trip_summary(
            self._summary_request(
                trips=[
                    self._trip_payload("trip1", [self._order_payload("ORD-001")]),
                    self._trip_payload("trip2", []),
                ]
            )
        )

        self.assertEqual(["trip1"], [trip.trip_no for trip in summary.trips])

    def test_saved_summary_can_be_loaded_by_history_after_repository_reopens(self):
        self._assign_order("ORD-001", "D001", "trip1")
        saved = self.service.save_final_trip_summary(self._summary_request())

        reloaded_service = ManualDispatchService(
            SQLiteManualDispatchRepository(self.db_path)
        )
        summaries = reloaded_service.list_final_trip_summaries(self.dispatch_date)
        detail = reloaded_service.get_final_trip_summary(saved.summary_id)

        self.assertEqual([saved.summary_id], [summary.summary_id for summary in summaries])
        self.assertEqual("ORD-001", detail.trips[0].orders[0].task_id)

    def test_saved_summary_dates_are_listed_newest_first(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        future_order = self.service.create_order(
            CreateOrderRequest(
                company_name="Future Summary Customer",
                suburb="Richmond",
                delivery_date="2026-05-06",
                pallet_quantity=1,
            )
        )
        self.service.save_final_trip_summary(
            SaveFinalTripSummaryRequest(
                dispatch_date="2026-05-06",
                delivery_date="2026-05-06",
                driver_id="D002",
                driver_name_snapshot="Tony",
                vehicle_id=None,
                vehicle_rego_snapshot="No vehicle selected",
                total_pallets=1,
                total_loose_bags=0,
                generated_at="2026-05-06T00:00:00Z",
                saved_by_account_name=self.account.account_name,
                saved_by_account_id=self.account.account_id,
                trips=[
                    self._trip_payload(
                        "trip1",
                        [self._order_payload(future_order.order_id)],
                    )
                ],
            )
        )

        self.assertEqual(
            ["2026-05-06", "2026-05-05"],
            self.service.list_final_summary_dates(),
        )

    def test_saving_final_summary_marks_orders_finalized_and_clears_assignments(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        board = self.service.get_board(self.dispatch_date)

        self.assertNotIn("ORD-001", [order.order_id for order in board.orders])
        self.assertEqual([], board.assignments)

        with self.assertRaises(ValueError):
            self._assign_order("ORD-001", "D001", "trip1")

    def test_saved_final_summary_blocks_new_order_assignment_and_vehicle_changes_for_driver_date(self):
        self.service.save_final_trip_summary(
            self._summary_request(trips=[])
        )
        same_date_order = self.service.create_order(
            CreateOrderRequest(
                company_name="Locked Driver Customer",
                suburb="Coburg",
                delivery_date=self.dispatch_date,
                pallet_quantity=1,
            )
        )
        next_date_order = self.service.create_order(
            CreateOrderRequest(
                company_name="Next Day Customer",
                suburb="Coburg",
                delivery_date="2026-05-06",
                pallet_quantity=1,
            )
        )

        with self.assertRaisesRegex(ValueError, "Final Trip Summary has already been saved"):
            self._assign_order(same_date_order.order_id, "D001", "trip1")
        with self.assertRaisesRegex(ValueError, "Final Trip Summary has already been saved"):
            self._assign_vehicle("D001", "V002")

        other_driver_assignment = self._assign_order(same_date_order.order_id, "D002", "trip1")
        next_date_assignment = self._assign_order(next_date_order.order_id, "D001", "trip1")
        self.assertEqual("D002", other_driver_assignment.driver_id)
        self.assertEqual("D001", next_date_assignment.driver_id)

    def test_duplicate_final_summary_for_same_driver_dispatch_and_delivery_date_is_rejected(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        with self.assertRaisesRegex(
            ValueError,
            "Final Summary for this driver, dispatch date, and delivery date has already been saved.",
        ):
            self.service.save_final_trip_summary(self._summary_request())

        summaries = self.service.list_final_trip_summaries(self.dispatch_date)
        self.assertEqual(1, len(summaries))

    def test_same_driver_and_dispatch_date_can_save_different_delivery_dates(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())
        future_order = self.service.create_order(
            CreateOrderRequest(
                company_name="Different Delivery Date Customer",
                suburb="Geelong",
                delivery_date="2026-05-06",
                pallet_quantity=2,
            )
        )

        second = self.service.save_final_trip_summary(
            self._summary_request(
                delivery_date="2026-05-06",
                trips=[
                    self._trip_payload(
                        "trip1",
                        [self._order_payload(future_order.order_id)],
                    )
                ],
            )
        )

        summaries = self.service.list_final_trip_summaries(self.dispatch_date)

        self.assertEqual("2026-05-06", second.delivery_date)
        self.assertEqual(2, len(summaries))

    def test_final_summary_rejects_rows_from_another_delivery_date(self):
        future_order = self.service.create_order(
            CreateOrderRequest(
                company_name="Wrong Date Customer",
                suburb="Ballarat",
                delivery_date="2026-05-06",
                pallet_quantity=1,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Final Summary rows must match the selected delivery date",
        ):
            self.service.save_final_trip_summary(
                self._summary_request(
                    trips=[
                        self._trip_payload(
                            "trip1",
                            [self._order_payload(future_order.order_id)],
                        )
                    ],
                )
            )

    def test_final_summary_uses_assigned_order_after_delivery_date_edit(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.update_order(
            "ORD-001",
            UpdateOrderRequest(
                invoice_number="INV-1001",
                company_name="Demo Customer A",
                phone="0400 000 001",
                delivery_address="1 Demo Street",
                suburb="Dandenong",
                postcode="3175",
                delivery_date="2026-05-06",
                zone="South East",
                urgency="Urgent",
                preferred_driver_id="D001",
                pallet_quantity=2,
                loose_bags_quantity=0,
                start_time="08:00",
                end_time="12:00",
                note="Call before delivery",
            ),
        )

        summary = self.service.save_final_trip_summary(
            self._summary_request(
                delivery_date="2026-05-06",
                trips=[
                    self._trip_payload(
                        "trip1",
                        [self._order_payload("ORD-001")],
                    )
                ],
            )
        )

        self.assertEqual("2026-05-06", summary.delivery_date)
        self.assertEqual("ORD-001", summary.trips[0].orders[0].task_id)

    def test_saved_snapshot_does_not_change_after_live_data_edits(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._assign_vehicle("D001", "V002")
        saved = self.service.save_final_trip_summary(self._summary_request())

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE manual_orders SET company_name = ? WHERE order_id = ?",
                ("Edited Customer", "ORD-001"),
            )
            connection.execute(
                "UPDATE manual_drivers SET name = ? WHERE driver_id = ?",
                ("Edited Driver", "D001"),
            )
            connection.execute(
                "UPDATE manual_vehicles SET rego = ? WHERE vehicle_id = ?",
                ("EDIT123", "V002"),
            )
            connection.commit()

        detail = self.service.get_final_trip_summary(saved.summary_id)

        self.assertEqual("John", detail.driver_name_snapshot)
        self.assertEqual("XYZ888", detail.vehicle_rego_snapshot)
        self.assertEqual("Demo Customer A", detail.trips[0].orders[0].company_name_snapshot)

    def test_save_final_summary_allows_empty_order_only_snapshot(self):
        summary = self.service.save_final_trip_summary(
            SaveFinalTripSummaryRequest(
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                driver_name_snapshot="John",
                vehicle_id=None,
                vehicle_rego_snapshot=None,
                total_pallets=0,
                total_loose_bags=0,
                generated_at="2026-05-05T00:00:00Z",
                saved_by_account_name=self.account.account_name,
                saved_by_account_id=self.account.account_id,
                trips=[],
            )
        )

        self.assertEqual([], summary.trips)
        self.assertEqual(0, summary.total_pallets)
        self.assertEqual(0, summary.total_loose_bags)
        self.assertEqual("SAVED", summary.status)

    def test_save_and_load_opshop_only_summary_uses_separate_snapshot_rows(self):
        self._seed_opshop_pickup("TASK-OPSHOP-001")
        self.repository.upsert_assignment(
            self.dispatch_date,
            "OPSHOP_PICKUP",
            "TASK-OPSHOP-001",
            "D001",
            "trip1",
        )

        saved = self.service.save_final_trip_summary(
            self._summary_request(
                trips=[],
                opshop_pickups=[self._opshop_payload("TASK-OPSHOP-001")],
            )
        )
        reloaded = self.service.get_final_trip_summary(saved.summary_id)

        self.assertEqual([], reloaded.trips)
        self.assertEqual(1, len(reloaded.opshop_pickups))
        self.assertEqual("Northside Op Shop", reloaded.opshop_pickups[0].opshop_name_snapshot)
        self.assertEqual(0, reloaded.total_pallets)
        self.assertEqual(0, reloaded.total_loose_bags)

        with sqlite3.connect(self.db_path) as connection:
            order_rows = connection.execute(
                "SELECT COUNT(*) FROM final_trip_summary_rows WHERE summary_id = ?",
                (saved.summary_id,),
            ).fetchone()[0]
            opshop_rows = connection.execute(
                "SELECT COUNT(*) FROM final_trip_summary_opshop_pickup_rows WHERE summary_id = ?",
                (saved.summary_id,),
            ).fetchone()[0]
        self.assertEqual(0, order_rows)
        self.assertEqual(1, opshop_rows)
        task = self.repository.get_opshop_pickup_task("TASK-OPSHOP-001")
        assignment = self.repository.get_assignment(
            self.dispatch_date,
            "OPSHOP_PICKUP",
            "TASK-OPSHOP-001",
        )
        self.assertEqual("ASSIGNED", task.status)
        self.assertEqual("D001", task.driver_id)
        self.assertEqual("trip1", task.trip_no)
        self.assertIsNotNone(assignment)
        self.assertEqual("D001", assignment.driver_id)
        self.assertEqual("trip1", assignment.trip_no)

    def test_save_and_load_countryside_opshop_summary_snapshots_category_and_route_group(self):
        self._seed_opshop_pickup(
            "TASK-COUNTRYSIDE-001",
            run_type="ON_CALL",
            pickup_category="COUNTRYSIDE",
            route_group_id="CRG-FINAL",
            route_group_name="Gippsland Route",
        )

        saved = self.service.save_final_trip_summary(
            self._summary_request(
                trips=[],
                opshop_pickups=[
                    self._opshop_payload("TASK-COUNTRYSIDE-001", run_type="ON_CALL")
                ],
                total_pallets=0,
                total_loose_bags=0,
            )
        )
        reloaded = self.service.get_final_trip_summary(saved.summary_id)
        pickup = reloaded.opshop_pickups[0]

        self.assertEqual([], reloaded.trips)
        self.assertEqual(0, reloaded.total_pallets)
        self.assertEqual(0, reloaded.total_loose_bags)
        self.assertEqual("COUNTRYSIDE", pickup.pickup_category_snapshot)
        self.assertEqual("CRG-FINAL", pickup.route_group_id_snapshot)
        self.assertEqual("Gippsland Route", pickup.route_group_name_snapshot)

    def test_mixed_summary_keeps_opshop_out_of_delivery_totals_and_rows(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._seed_opshop_pickup("TASK-OPSHOP-001")

        saved = self.service.save_final_trip_summary(
            self._summary_request(opshop_pickups=[self._opshop_payload("TASK-OPSHOP-001")])
        )

        self.assertEqual(2, saved.total_pallets)
        self.assertEqual(0, saved.total_loose_bags)
        self.assertEqual(["ORD-001"], [order.task_id for order in saved.trips[0].orders])
        self.assertEqual(["TASK-OPSHOP-001"], [pickup.pickup_task_id_snapshot for pickup in saved.opshop_pickups])

        with sqlite3.connect(self.db_path) as connection:
            delivery_task_types = [
                row[0]
                for row in connection.execute(
                    "SELECT task_type FROM final_trip_summary_rows WHERE summary_id = ?",
                    (saved.summary_id,),
                ).fetchall()
            ]
        self.assertEqual(["ORDER"], delivery_task_types)

    def test_mixed_summary_keeps_regular_oncall_and_countryside_opshop_separate(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._seed_opshop_pickup("TASK-REGULAR-001")
        self._seed_opshop_pickup(
            "TASK-ONCALL-001",
            run_type="ON_CALL",
            pickup_category="NORMAL",
        )
        self._seed_opshop_pickup(
            "TASK-COUNTRYSIDE-001",
            run_type="ON_CALL",
            pickup_category="COUNTRYSIDE",
            route_group_id="CRG-FINAL",
            route_group_name="Gippsland Route",
        )

        saved = self.service.save_final_trip_summary(
            self._summary_request(
                opshop_pickups=[
                    self._opshop_payload("TASK-REGULAR-001"),
                    self._opshop_payload("TASK-ONCALL-001", run_type="ON_CALL"),
                    self._opshop_payload("TASK-COUNTRYSIDE-001", run_type="ON_CALL"),
                ]
            )
        )

        self.assertEqual(2, saved.total_pallets)
        self.assertEqual(0, saved.total_loose_bags)
        self.assertEqual(["ORD-001"], [order.task_id for order in saved.trips[0].orders])
        self.assertEqual(
            ["REGULAR", "ON_CALL", "COUNTRYSIDE"],
            [pickup.pickup_category_snapshot for pickup in saved.opshop_pickups],
        )
        self.assertEqual("Gippsland Route", saved.opshop_pickups[2].route_group_name_snapshot)

    def test_save_final_summary_rejects_missing_saved_by_account_name(self):
        self._assign_order("ORD-001", "D001", "trip1")

        with self.assertRaisesRegex(ValueError, "saved_by_account_name is required"):
            self.service.save_final_trip_summary(
                SaveFinalTripSummaryRequest(
                    dispatch_date=self.dispatch_date,
                    driver_id="D001",
                    driver_name_snapshot="John",
                    vehicle_id=None,
                    vehicle_rego_snapshot=None,
                    total_pallets=2,
                    total_loose_bags=0,
                    generated_at="2026-05-05T00:00:00Z",
                    trips=[self._trip_payload("trip1", [self._order_payload("ORD-001")])],
                )
            )

    def test_save_final_summary_rejects_unknown_saved_by_account_name(self):
        self._assign_order("ORD-001", "D001", "trip1")

        with self.assertRaisesRegex(
            ValueError,
            "saved_by_account_name must reference a registered account",
        ):
            self.service.save_final_trip_summary(
                SaveFinalTripSummaryRequest(
                    dispatch_date=self.dispatch_date,
                    driver_id="D001",
                    driver_name_snapshot="John",
                    vehicle_id=None,
                    vehicle_rego_snapshot=None,
                    total_pallets=2,
                    total_loose_bags=0,
                    generated_at="2026-05-05T00:00:00Z",
                    saved_by_account_name="Unknown Operator",
                    trips=[self._trip_payload("trip1", [self._order_payload("ORD-001")])],
                )
            )

    def test_repository_save_failure_rolls_back_summary_and_finalized_orders(self):
        self._assign_order("ORD-001", "D001", "trip1")
        summary = {
            "dispatch_date": self.dispatch_date,
            "delivery_date": self.dispatch_date,
            "driver_id": "D001",
            "driver_name_snapshot": "John",
            "vehicle_id": None,
            "vehicle_rego_snapshot": "No vehicle selected",
            "total_pallets": 2,
            "total_loose_bags": 0,
            "generated_at": "2026-05-05T00:00:00Z",
        }
        rows = [
            {
                "trip_no": "trip1",
                "row_no": 1,
                "task_type": "ORDER",
                "task_id": "ORD-001",
                "order_id_snapshot": "ORD-001",
                "invoice_number_snapshot": "INV-1001",
                "company_name_snapshot": "Demo Customer A",
                "suburb_snapshot": "Dandenong",
                "delivery_address_snapshot": "1 Demo Street",
                "product_snapshot": "",
                "pallet_quantity_snapshot": 2,
                "loose_bags_quantity_snapshot": 0,
                "note_snapshot": "Call before delivery",
            },
            {
                "trip_no": "trip2",
                "task_type": "ORDER",
                "task_id": "ORD-003",
            },
        ]

        with self.assertRaises(KeyError):
            self.repository.save_final_trip_summary(summary, rows)

        board = self.service.get_board(self.dispatch_date)
        self.assertIn("ORD-001", [order.order_id for order in board.orders])
        self.assertEqual(["ORD-001"], [assignment.task_id for assignment in board.assignments])
        self.assertEqual([], self.service.list_final_trip_summaries(self.dispatch_date))

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

    def _assign_vehicle(self, driver_id, vehicle_id, delivery_date=None):
        return self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                delivery_date=delivery_date or self.dispatch_date,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
            )
        )

    def _summary_request(
        self,
        trips=None,
        delivery_date=None,
        opshop_pickups=None,
        total_pallets=2,
        total_loose_bags=0,
    ):
        return SaveFinalTripSummaryRequest(
            dispatch_date=self.dispatch_date,
            delivery_date=delivery_date or self.dispatch_date,
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id="V002",
            vehicle_rego_snapshot="XYZ888",
            total_pallets=total_pallets,
            total_loose_bags=total_loose_bags,
            generated_at="2026-05-05T00:00:00Z",
            saved_by_account_name=self.account.account_name,
            saved_by_account_id=self.account.account_id,
            trips=trips
            if trips is not None
            else [self._trip_payload("trip1", [self._order_payload("ORD-001")])],
            opshop_pickups=opshop_pickups or [],
        )

    def _trip_payload(self, trip_no, orders):
        return {"trip_no": trip_no, "orders": orders}

    def _order_payload(self, order_id):
        order = self.repository.get_order(order_id)
        return {
            "task_type": "ORDER",
            "task_id": order_id,
            "order_id": order_id,
            "invoice_number": order.invoice_number,
            "company_name": order.company_name,
            "suburb": order.suburb,
            "delivery_address": order.delivery_address,
            "product": "",
            "pallet_quantity": order.pallet_quantity,
            "loose_bags_quantity": order.loose_bags_quantity,
            "note": order.note,
        }

    def _seed_opshop_pickup(
        self,
        task_id,
        run_type="REGULAR",
        pickup_category="NORMAL",
        route_group_id=None,
        route_group_name=None,
    ):
        if route_group_id:
            self.repository.upsert_countryside_route_group(
                OpShopCountrysideRouteGroup(
                    route_group_id=route_group_id,
                    route_group_name=route_group_name or "Unknown Route Group",
                    status="Active",
                    active_flag=True,
                    display_order=1,
                    source_marker="TEST",
                    created_at="2026-05-05T00:00:00+00:00",
                    updated_at="2026-05-05T00:00:00+00:00",
                )
            )
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="OPSHOP-FINAL",
                name="Northside Op Shop",
                suburb="Coburg",
                street_address="1 Sydney Road",
                area_region="North",
                primary_contact="Mary",
                primary_phone="0400 700 001",
                secondary_contact=None,
                secondary_phone=None,
                access_type="Rear dock",
                key_required=True,
                trailer_restriction="Small truck only",
                status_notes="Ring first",
                is_active=True,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        schedule_id = f"SCHED-{task_id}"
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id="OPSHOP-FINAL",
                run_day="TUESDAY",
                run_type=run_type,
                pickup_frequency="Weekly",
                time_window="09:00-12:00",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
                pickup_category=pickup_category,
                route_group_id=route_group_id,
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id=task_id,
                schedule_id=schedule_id,
                opshop_id="OPSHOP-FINAL",
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from=run_type,
                status="ASSIGNED",
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                trip_no="trip1",
                notes="Leave at rear door",
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )

    def _opshop_payload(self, task_id, run_type="REGULAR"):
        return {
            "task_type": "OPSHOP_PICKUP",
            "pickup_task_id": task_id,
            "opshop_name": "Northside Op Shop",
            "suburb": "Coburg",
            "street_address": "1 Sydney Road",
            "area_region": "North",
            "pickup_date": self.dispatch_date,
            "run_type": run_type,
            "pickup_frequency": "Weekly",
            "time_window": "09:00-12:00",
            "primary_contact": "Mary",
            "primary_phone": "0400 700 001",
            "access_type": "Rear dock",
            "key_required": True,
            "trailer_restriction": "Small truck only",
            "task_notes": "Leave at rear door",
            "status": "ASSIGNED",
        }


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class ManualDispatchFinalSummaryRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"final-summary-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Mandy",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service

        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        self.dispatch_date = "2026-05-05"

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_final_summary_api_saves_and_lists_history(self):
        self._assign_order("ORD-001", "D001", "trip1")

        response = self.client.post(
            "/api/manual-dispatch/final-summaries",
            json=self._summary_payload(),
        )

        self.assertEqual(200, response.status_code)
        saved_payload = response.json()
        self.assertTrue(saved_payload["summary_id"].startswith("FTS-"))
        self.assertEqual(self.dispatch_date, saved_payload["delivery_date"])
        self.assertEqual("Mandy", saved_payload["saved_by_account_name"])

        history_response = self.client.get(
            "/api/manual-dispatch/final-summaries",
            params={"dispatch_date": self.dispatch_date},
        )
        board = self.service.get_board(self.dispatch_date)

        self.assertEqual(200, history_response.status_code)
        self.assertEqual(
            [saved_payload["summary_id"]],
            [item["summary_id"] for item in history_response.json()],
        )
        self.assertEqual("Mandy", history_response.json()[0]["saved_by_account_name"])
        self.assertNotIn("ORD-001", [order.order_id for order in board.orders])

    def test_final_summary_api_rejects_missing_saved_by_account_name(self):
        self._assign_order("ORD-001", "D001", "trip1")
        payload = self._summary_payload()
        payload.pop("saved_by_account_name")
        payload.pop("saved_by_account_id")

        response = self.client.post(
            "/api/manual-dispatch/final-summaries",
            json=payload,
        )

        self.assertEqual(400, response.status_code)
        self.assertIn("saved_by_account_name is required", response.json()["detail"])

    def test_final_summary_api_rejects_duplicate_driver_date_summary(self):
        self._assign_order("ORD-001", "D001", "trip1")
        first_response = self.client.post(
            "/api/manual-dispatch/final-summaries",
            json=self._summary_payload(),
        )
        second_response = self.client.post(
            "/api/manual-dispatch/final-summaries",
            json=self._summary_payload(),
        )

        self.assertEqual(200, first_response.status_code)
        self.assertEqual(400, second_response.status_code)
        self.assertIn(
            "Final Summary for this driver, dispatch date, and delivery date has already been saved.",
            second_response.json()["detail"],
        )

    def test_final_summary_dates_api_returns_saved_dates(self):
        self._assign_order("ORD-001", "D001", "trip1")
        save_response = self.client.post(
            "/api/manual-dispatch/final-summaries",
            json=self._summary_payload(),
        )
        dates_response = self.client.get("/api/manual-dispatch/final-summary-dates")

        self.assertEqual(200, save_response.status_code)
        self.assertEqual(200, dates_response.status_code)
        self.assertEqual([self.dispatch_date], dates_response.json())

    def test_final_summary_api_saves_opshop_snapshot_section(self):
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id="OPSHOP-ROUTE",
                name="Route Op Shop",
                suburb="Coburg",
                street_address="4 Route Road",
                area_region=None,
                primary_contact=None,
                primary_phone="0400 555 111",
                secondary_contact=None,
                secondary_phone=None,
                access_type=None,
                key_required=False,
                trailer_restriction=None,
                status_notes=None,
                is_active=True,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id="TASK-ROUTE",
                schedule_id=None,
                opshop_id="OPSHOP-ROUTE",
                pickup_date=self.dispatch_date,
                task_type="OPSHOP_PICKUP",
                generated_from="MANUAL",
                status="ASSIGNED",
                dispatch_date=self.dispatch_date,
                driver_id="D001",
                trip_no="trip1",
                notes=None,
                created_at="2026-05-05T00:00:00+00:00",
                updated_at="2026-05-05T00:00:00+00:00",
            )
        )
        payload = self._summary_payload()
        payload["trips"] = []
        payload["total_pallets"] = 0
        payload["opshop_pickups"] = [
            {
                "task_type": "OPSHOP_PICKUP",
                "pickup_task_id": "TASK-ROUTE",
                "opshop_name": "Route Op Shop",
                "suburb": "Coburg",
                "street_address": "4 Route Road",
                "pickup_date": self.dispatch_date,
                "status": "ASSIGNED",
            }
        ]

        response = self.client.post("/api/manual-dispatch/final-summaries", json=payload)

        self.assertEqual(200, response.status_code)
        self.assertEqual("TASK-ROUTE", response.json()["opshop_pickups"][0]["pickup_task_id_snapshot"])
        self.assertEqual([], response.json()["trips"])

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

    def _summary_payload(self):
        order = self.repository.get_order("ORD-001")
        return {
            "dispatch_date": self.dispatch_date,
            "delivery_date": self.dispatch_date,
            "driver_id": "D001",
            "driver_name_snapshot": "John",
            "vehicle_id": None,
            "vehicle_rego_snapshot": "No vehicle selected",
            "total_pallets": order.pallet_quantity,
            "total_loose_bags": order.loose_bags_quantity,
            "generated_at": "2026-05-05T00:00:00Z",
            "saved_by_account_name": self.account.account_name,
            "saved_by_account_id": self.account.account_id,
            "trips": [
                {
                    "trip_no": "trip1",
                    "orders": [
                        {
                            "task_type": "ORDER",
                            "task_id": order.order_id,
                            "order_id_snapshot": order.order_id,
                            "invoice_number_snapshot": order.invoice_number,
                            "company_name_snapshot": order.company_name,
                            "suburb_snapshot": order.suburb,
                            "delivery_address_snapshot": order.delivery_address,
                            "product_snapshot": "",
                            "pallet_quantity_snapshot": order.pallet_quantity,
                            "loose_bags_quantity_snapshot": order.loose_bags_quantity,
                            "note_snapshot": order.note,
                        }
                    ],
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
