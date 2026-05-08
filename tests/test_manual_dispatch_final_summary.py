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
    SaveFinalTripSummaryRequest,
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

    def test_save_final_summary_persists_snapshot_rows(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self._assign_vehicle("D001", "V002")

        summary = self.service.save_final_trip_summary(self._summary_request())

        self.assertTrue(summary.summary_id.startswith("FTS-"))
        self.assertEqual("John", summary.driver_name_snapshot)
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

    def test_saving_final_summary_marks_orders_finalized_and_clears_assignments(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        board = self.service.get_board(self.dispatch_date)

        self.assertNotIn("ORD-001", [order.order_id for order in board.orders])
        self.assertEqual([], board.assignments)

        with self.assertRaises(ValueError):
            self._assign_order("ORD-001", "D001", "trip1")

    def test_duplicate_final_summary_for_same_driver_and_date_is_rejected(self):
        self._assign_order("ORD-001", "D001", "trip1")
        self.service.save_final_trip_summary(self._summary_request())

        with self.assertRaisesRegex(
            ValueError,
            "Final Summary for this driver and dispatch date has already been saved.",
        ):
            self.service.save_final_trip_summary(self._summary_request())

        summaries = self.service.list_final_trip_summaries(self.dispatch_date)
        self.assertEqual(1, len(summaries))

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

    def test_save_final_summary_rejects_empty_snapshot(self):
        with self.assertRaises(ValueError):
            self.service.save_final_trip_summary(
                SaveFinalTripSummaryRequest(
                    dispatch_date=self.dispatch_date,
                    driver_id="D001",
                    driver_name_snapshot="John",
                    vehicle_id=None,
                    vehicle_rego_snapshot=None,
                    total_pallets=0,
                    total_loose_bags=0,
                    generated_at="2026-05-05T00:00:00Z",
                    trips=[],
                )
            )

    def test_repository_save_failure_rolls_back_summary_and_finalized_orders(self):
        self._assign_order("ORD-001", "D001", "trip1")
        summary = {
            "dispatch_date": self.dispatch_date,
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

    def _assign_vehicle(self, driver_id, vehicle_id):
        return self.service.assign_vehicle_to_driver(
            AssignDriverVehicleRequest(
                dispatch_date=self.dispatch_date,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
            )
        )

    def _summary_request(self, trips=None):
        return SaveFinalTripSummaryRequest(
            dispatch_date=self.dispatch_date,
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id="V002",
            vehicle_rego_snapshot="XYZ888",
            total_pallets=2,
            total_loose_bags=0,
            generated_at="2026-05-05T00:00:00Z",
            trips=trips
            if trips is not None
            else [self._trip_payload("trip1", [self._order_payload("ORD-001")])],
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
        self.assertNotIn("ORD-001", [order.order_id for order in board.orders])

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
            "Final Summary for this driver and dispatch date has already been saved.",
            second_response.json()["detail"],
        )

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
            "driver_id": "D001",
            "driver_name_snapshot": "John",
            "vehicle_id": None,
            "vehicle_rego_snapshot": "No vehicle selected",
            "total_pallets": order.pallet_quantity,
            "total_loose_bags": order.loose_bags_quantity,
            "generated_at": "2026-05-05T00:00:00Z",
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
