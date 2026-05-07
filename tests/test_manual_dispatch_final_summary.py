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

    def _summary_request(self):
        return SaveFinalTripSummaryRequest(
            dispatch_date=self.dispatch_date,
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id="V002",
            vehicle_rego_snapshot="XYZ888",
            total_pallets=2,
            total_loose_bags=0,
            generated_at="2026-05-05T00:00:00Z",
            trips=[
                {
                    "trip_no": "trip1",
                    "orders": [
                        {
                            "task_type": "ORDER",
                            "task_id": "ORD-001",
                            "order_id": "ORD-001",
                            "invoice_number": "INV-1001",
                            "company_name": "Demo Customer A",
                            "suburb": "Dandenong",
                            "delivery_address": "1 Demo Street",
                            "product": "",
                            "pallet_quantity": 2,
                            "loose_bags_quantity": 0,
                            "note": "Call before delivery",
                        }
                    ],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
