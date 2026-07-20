import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.db.connection import initialize_database
from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    DeliveryRunSheet,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetTrip,
    OpShopPickupCollection,
    OpShopPickupCollectionRowSnapshot,
    ProductDetailLine,
)


class WorkspaceSnapshotPersistenceTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-snapshot-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_additive_schema_is_idempotent_and_preserves_legacy_summary(self):
        with sqlite3.connect(self.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id,
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    driver_name_snapshot,
                    total_pallets,
                    total_loose_bags,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "FTS-LEGACY-001",
                    "2026-06-23",
                    "2026-06-24",
                    "D001",
                    "John",
                    2,
                    0,
                    "SAVED",
                    "2026-06-23T08:00:00Z",
                    "2026-06-23T08:05:00Z",
                    "Legacy Operator",
                ),
            )
            connection.execute(
                """
                INSERT INTO final_trip_summary_rows (
                    row_id,
                    summary_id,
                    trip_no,
                    row_no,
                    task_type,
                    task_id,
                    order_id_snapshot,
                    invoice_number_snapshot,
                    company_name_snapshot,
                    suburb_snapshot,
                    pallet_quantity_snapshot,
                    loose_bags_quantity_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "FSR-LEGACY-001",
                    "FTS-LEGACY-001",
                    "trip1",
                    1,
                    "ORDER",
                    "ORD-001",
                    "ORD-001",
                    "INV-1001",
                    "Legacy Customer",
                    "Dandenong",
                    2,
                    0,
                ),
            )
            connection.commit()

        expected_tables = {
            "delivery_run_sheets",
            "delivery_run_sheet_rows",
            "opshop_pickup_collections",
            "opshop_pickup_collection_rows",
        }
        self.assertTrue(expected_tables.issubset(tables))

        initialize_database(self.db_path)
        initialize_database(self.db_path)

        legacy_summary = self.repository.get_final_trip_summary("FTS-LEGACY-001")
        self.assertIsNotNone(legacy_summary)
        self.assertEqual("Legacy Customer", legacy_summary.trips[0].orders[0].company_name_snapshot)

    def test_delivery_and_opshop_snapshots_coexist_for_same_driver_and_date(self):
        run_sheet = self._delivery_run_sheet()
        collection = self._opshop_collection()

        saved_run_sheet = self.repository.upsert_delivery_run_sheet(run_sheet)
        saved_collection = self.repository.upsert_opshop_pickup_collection(collection)

        self.assertEqual("DRS-001", saved_run_sheet.run_sheet_id)
        self.assertEqual("ORDER", saved_run_sheet.trips[0].orders[0].task_type)
        self.assertEqual("INV-1001", saved_run_sheet.trips[0].orders[0].invoice_number_snapshot)
        self.assertEqual("OPC-001", saved_collection.collection_id)
        self.assertEqual(
            "RSPCA CAMBERWELL",
            saved_collection.pickups[0].opshop_name_snapshot,
        )
        self.assertTrue(
            saved_collection.pickups[0].call_before_arrival_snapshot
        )
        self.assertEqual(
            "30 minutes",
            saved_collection.pickups[0].call_timing_snapshot,
        )
        self.assertTrue(
            self.repository.has_saved_delivery_run_sheet(
                "2026-06-23",
                "D001",
                "2026-06-24",
            )
        )
        self.assertTrue(
            self.repository.has_saved_opshop_pickup_collection(
                "2026-06-23",
                "D001",
                "2026-06-24",
            )
        )

        with sqlite3.connect(self.db_path) as connection:
            delivery_rows = connection.execute(
                "SELECT task_type FROM delivery_run_sheet_rows"
            ).fetchall()
            opshop_rows = connection.execute(
                "SELECT pickup_task_id_snapshot FROM opshop_pickup_collection_rows"
            ).fetchall()
            legacy_rows = connection.execute(
                "SELECT COUNT(*) FROM final_trip_summary_rows"
            ).fetchone()[0]

        self.assertEqual([("ORDER",)], delivery_rows)
        self.assertEqual([("OPSHOP-PICKUP-001",)], opshop_rows)
        self.assertEqual(0, legacy_rows)

    def test_existing_pilot_collection_table_adds_call_before_columns(self):
        legacy_path = self.temp_dir / "pilot-without-call-before.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE opshop_pickup_collection_rows (
                    row_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL,
                    row_no INTEGER NOT NULL
                )
                """
            )
            connection.commit()

        initialize_database(legacy_path)
        initialize_database(legacy_path)

        with sqlite3.connect(legacy_path) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(opshop_pickup_collection_rows)"
                ).fetchall()
            }
        self.assertIn("call_before_arrival_snapshot", columns)
        self.assertIn("call_timing_snapshot", columns)
        for column_name in (
            "clothing_kg_snapshot",
            "shoes_kg_snapshot",
            "time_in_snapshot",
            "time_out_snapshot",
            "trolleys_out_to_opshops_snapshot",
            "trolleys_in_to_mcc_snapshot",
            "hard_toys_snapshot",
            "soft_toys_snapshot",
            "black_bags_snapshot",
            "shoe_bags_snapshot",
        ):
            self.assertIn(column_name, columns)

    def test_upsert_replaces_snapshot_children_without_duplicates(self):
        run_sheet = self._delivery_run_sheet()
        collection = self._opshop_collection()
        self.repository.upsert_delivery_run_sheet(run_sheet)
        self.repository.upsert_opshop_pickup_collection(collection)

        run_sheet.trips[0].orders[0].company_name_snapshot = "Updated Customer"
        collection.pickups[0].notes_snapshot = "Updated pickup note"
        self.repository.upsert_delivery_run_sheet(run_sheet)
        self.repository.upsert_opshop_pickup_collection(collection)

        with sqlite3.connect(self.db_path) as connection:
            delivery_count = connection.execute(
                "SELECT COUNT(*) FROM delivery_run_sheet_rows"
            ).fetchone()[0]
            opshop_count = connection.execute(
                "SELECT COUNT(*) FROM opshop_pickup_collection_rows"
            ).fetchone()[0]

        self.assertEqual(1, delivery_count)
        self.assertEqual(1, opshop_count)
        self.assertEqual(
            "Updated Customer",
            self.repository.get_delivery_run_sheet("DRS-001").trips[0].orders[0].company_name_snapshot,
        )
        self.assertEqual(
            "Updated pickup note",
            self.repository.get_opshop_pickup_collection("OPC-001").pickups[0].notes_snapshot,
        )

    def test_in_memory_repository_exposes_matching_independent_contract(self):
        repository = InMemoryManualDispatchRepository()
        repository.upsert_delivery_run_sheet(self._delivery_run_sheet())
        repository.upsert_opshop_pickup_collection(self._opshop_collection())

        self.assertTrue(
            repository.has_saved_delivery_run_sheet(
                "2026-06-23",
                "D001",
                "2026-06-24",
            )
        )
        self.assertTrue(
            repository.has_saved_opshop_pickup_collection(
                "2026-06-23",
                "D001",
                "2026-06-24",
            )
        )

    @staticmethod
    def _delivery_run_sheet():
        return DeliveryRunSheet(
            run_sheet_id="DRS-001",
            dispatch_date="2026-06-23",
            delivery_date="2026-06-24",
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id="V001",
            vehicle_rego_snapshot="ABC123",
            total_pallets=2,
            total_loose_bags=0,
            status="SAVED",
            generated_at="2026-06-23T08:00:00Z",
            saved_at="2026-06-23T08:05:00Z",
            saved_by_account_name="Mandy",
            saved_by_account_id=None,
            legacy_summary_id=None,
            trips=[
                DeliveryRunSheetTrip(
                    trip_no="trip1",
                    orders=[
                        DeliveryRunSheetOrderSnapshot(
                            row_id="DRR-001",
                            trip_no="trip1",
                            row_no=1,
                            task_type="ORDER",
                            task_id="ORD-001",
                            order_id_snapshot="ORD-001",
                            invoice_number_snapshot="INV-1001",
                            order_no_snapshot="002848",
                            company_name_snapshot="Demo Customer A",
                            suburb_snapshot="Dandenong",
                            delivery_address_snapshot="1 Demo Street",
                            product_snapshot="Rags",
                            pallet_quantity_snapshot=2,
                            loose_bags_quantity_snapshot=0,
                            note_snapshot=None,
                            product_lines_snapshot=[
                                ProductDetailLine(
                                    product_name="Rags",
                                    quantity=2,
                                    unit="PALLETS",
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    @staticmethod
    def _opshop_collection():
        return OpShopPickupCollection(
            collection_id="OPC-001",
            dispatch_date="2026-06-23",
            pickup_date="2026-06-24",
            driver_id="D001",
            driver_name_snapshot="John",
            status="SAVED",
            generated_at="2026-06-23T08:00:00Z",
            saved_at="2026-06-23T08:05:00Z",
            saved_by_account_name="Mandy",
            saved_by_account_id=None,
            legacy_summary_id=None,
            pickups=[
                OpShopPickupCollectionRowSnapshot(
                    row_id="OPCR-001",
                    row_no=1,
                    pickup_task_id_snapshot="OPSHOP-PICKUP-001",
                    opshop_name_snapshot="RSPCA CAMBERWELL",
                    suburb_snapshot="CAMBERWELL",
                    street_address_snapshot="527 RIVERSDALE RD",
                    area_region_snapshot=None,
                    pickup_date_snapshot="2026-06-24",
                    run_type_snapshot="REGULAR",
                    pickup_category_snapshot="NORMAL",
                    route_group_id_snapshot=None,
                    route_group_name_snapshot=None,
                    pickup_frequency_snapshot="WEEKLY",
                    time_window_snapshot="09:00-12:00",
                    primary_contact_snapshot="Office",
                    primary_phone_snapshot="03 9000 0000",
                    secondary_contact_snapshot=None,
                    secondary_phone_snapshot=None,
                    access_type_snapshot="Loading zone",
                    key_required_snapshot=False,
                    trailer_restriction_snapshot="No",
                    notes_snapshot="Call before arrival",
                    status_snapshot="ASSIGNED",
                    call_before_arrival_snapshot=True,
                    call_timing_snapshot="30 minutes",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
