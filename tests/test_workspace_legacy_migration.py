import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from tools.migrate_legacy_final_summaries_to_workspaces import (
    MigrationBlockedError,
    inspect_migration,
    migrate_legacy_final_summaries,
)


class WorkspaceLegacyMigrationTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"workspace-legacy-migration-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.backup_dir = self.temp_dir / "backups"
        self.repository = SQLiteManualDispatchRepository(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_dry_run_is_read_only_and_reports_candidates(self):
        self._seed_summary("FTS-DRY", delivery_rows=1, opshop_rows=1)
        # Dry-run must be semantically read-only. Avoid byte-for-byte SQLite
        # comparisons here because journal/WAL bookkeeping can change without
        # mutating legacy summaries or creating workspace snapshots.
        before_legacy = self._legacy_snapshot("FTS-DRY")
        before_workspace_counts = self._workspace_counts()

        report = migrate_legacy_final_summaries(self.db_path)

        self.assertEqual("dry-run", report["mode"])
        self.assertIsNone(report["backup_path"])
        self.assertEqual(1, report["summary"]["delivery_to_create"])
        self.assertEqual(1, report["summary"]["opshop_to_create"])
        self.assertEqual(before_legacy, self._legacy_snapshot("FTS-DRY"))
        self.assertEqual(before_workspace_counts, self._workspace_counts())

    def test_apply_requires_apply_and_yes(self):
        self._seed_summary("FTS-FLAGS", delivery_rows=1)

        with self.assertRaisesRegex(
            MigrationBlockedError,
            "Apply requires both --apply and --yes",
        ):
            migrate_legacy_final_summaries(self.db_path, apply=True)

        self.assertFalse(self.backup_dir.exists())
        self.assertEqual(0, self._count("delivery_run_sheets"))

    def test_apply_creates_verified_backup_before_writes(self):
        self._seed_summary("FTS-BACKUP", delivery_rows=1)

        report = self._apply()

        backup_path = Path(report["backup_path"])
        self.assertTrue(backup_path.is_file())
        with sqlite3.connect(backup_path) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM delivery_run_sheets").fetchone()[0])
        self.assertEqual(1, self._count("delivery_run_sheets"))

    def test_backup_integrity_failure_blocks_all_writes(self):
        self._seed_summary("FTS-BAD-BACKUP", delivery_rows=1)

        with patch(
            "tools.migrate_legacy_final_summaries_to_workspaces._backup_integrity_result",
            return_value="database disk image is malformed",
        ):
            with self.assertRaisesRegex(MigrationBlockedError, "Backup integrity check failed"):
                self._apply()

        self.assertEqual(0, self._count("delivery_run_sheets"))
        self.assertEqual(1, self._count("final_trip_summaries"))

    def test_delivery_only_summary_preserves_snapshot_fields(self):
        self._seed_summary(
            "FTS-DELIVERY",
            delivery_rows=1,
            generated_at="2026-06-23T08:00:00Z",
        )

        report = self._apply()

        self.assertEqual(1, report["applied"]["delivery_run_sheets"])
        self.assertEqual(1, report["applied"]["delivery_rows"])
        header = self._one("delivery_run_sheets")
        row = self._one("delivery_run_sheet_rows")
        self.assertEqual("FTS-DELIVERY", header["legacy_summary_id"])
        self.assertEqual("SAVED", header["status"])
        self.assertEqual("2026-06-23T08:00:00Z", header["generated_at"])
        self.assertEqual(3, header["total_pallets"])
        self.assertEqual(4, header["total_loose_bags"])
        self.assertEqual("ORDER", row["task_type"])
        self.assertEqual("ORD-FTS-DELIVERY-1", row["task_id"])
        self.assertEqual('[{"product_name":"Rags","quantity":3,"unit":"PALLETS"}]', row["product_details_snapshot"])
        self.assertEqual(18.75, row["estimated_distance_km_from_warehouse_snapshot"])

    def test_opshop_only_summary_preserves_snapshot_and_defaults_call_fields(self):
        self._seed_summary("FTS-OPSHOP", opshop_rows=1)

        report = self._apply()

        self.assertEqual(1, report["applied"]["opshop_collections"])
        self.assertEqual(1, report["applied"]["opshop_rows"])
        header = self._one("opshop_pickup_collections")
        row = self._one("opshop_pickup_collection_rows")
        self.assertEqual("FTS-OPSHOP", header["legacy_summary_id"])
        self.assertEqual("SAVED", header["status"])
        self.assertEqual("OPSHOP-PICKUP-FTS-OPSHOP-1", row["pickup_task_id_snapshot"])
        self.assertEqual("COUNTRYSIDE", row["pickup_category_snapshot"])
        self.assertEqual("ROUTE-GROUP-1", row["route_group_id_snapshot"])
        self.assertEqual("Long access and status notes", row["notes_snapshot"])
        self.assertEqual(0, row["call_before_arrival_snapshot"])
        self.assertIsNone(row["call_timing_snapshot"])

    def test_mixed_summary_creates_both_modules_with_shared_marker(self):
        self._seed_summary("FTS-MIXED", delivery_rows=2, opshop_rows=2)

        report = self._apply()

        self.assertEqual(1, report["applied"]["delivery_run_sheets"])
        self.assertEqual(2, report["applied"]["delivery_rows"])
        self.assertEqual(1, report["applied"]["opshop_collections"])
        self.assertEqual(2, report["applied"]["opshop_rows"])
        self.assertEqual(
            "FTS-MIXED",
            self._one("delivery_run_sheets")["legacy_summary_id"],
        )
        self.assertEqual(
            "FTS-MIXED",
            self._one("opshop_pickup_collections")["legacy_summary_id"],
        )

    def test_generated_at_falls_back_to_saved_at(self):
        self._seed_summary(
            "FTS-FALLBACK",
            delivery_rows=1,
            generated_at=None,
            saved_at="2026-06-23T09:15:00Z",
        )

        self._apply()

        self.assertEqual(
            "2026-06-23T09:15:00Z",
            self._one("delivery_run_sheets")["generated_at"],
        )

    def test_rerun_is_idempotent(self):
        self._seed_summary("FTS-IDEMPOTENT", delivery_rows=2, opshop_rows=2)

        first_report = self._apply()
        first_counts = self._workspace_counts()
        second_report = self._apply()

        self.assertEqual(1, first_report["applied"]["delivery_run_sheets"])
        self.assertEqual(1, first_report["applied"]["opshop_collections"])
        self.assertEqual(0, second_report["applied"]["delivery_run_sheets"])
        self.assertEqual(0, second_report["applied"]["opshop_collections"])
        self.assertEqual(2, second_report["summary"]["already_migrated"])
        self.assertEqual(first_counts, self._workspace_counts())

    def test_existing_workspace_key_without_marker_blocks_entire_apply(self):
        self._seed_summary("FTS-CONFLICT", delivery_rows=1, opshop_rows=1)
        self._insert_manual_delivery_run_sheet()

        report = inspect_migration(self.db_path)
        self.assertEqual(1, report["summary"]["conflicts"])
        with self.assertRaisesRegex(MigrationBlockedError, "conflicts must be resolved"):
            self._apply()

        self.assertEqual(1, self._count("delivery_run_sheets"))
        self.assertEqual(0, self._count("opshop_pickup_collections"))
        self.assertFalse(self.backup_dir.exists())

    def test_marker_with_wrong_key_blocks_entire_apply(self):
        self._seed_summary("FTS-WRONG-MARKER", delivery_rows=1)
        self._insert_manual_delivery_run_sheet(
            legacy_summary_id="FTS-WRONG-MARKER",
            delivery_date="2026-07-01",
        )

        report = inspect_migration(self.db_path)

        self.assertEqual(1, report["summary"]["conflicts"])
        self.assertIn("different date/driver key", report["conflicts"][0]["reason"])
        with self.assertRaises(MigrationBlockedError):
            self._apply()

    def test_duplicate_legacy_markers_block_entire_apply(self):
        self._seed_summary("FTS-DUPLICATE-MARKER", delivery_rows=1)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DROP INDEX idx_delivery_run_sheets_legacy_summary")
        self._insert_manual_delivery_run_sheet(
            legacy_summary_id="FTS-DUPLICATE-MARKER",
        )
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO delivery_run_sheets (
                    run_sheet_id, dispatch_date, delivery_date, driver_id,
                    driver_name_snapshot, total_pallets, total_loose_bags,
                    status, generated_at, saved_at, saved_by_account_name,
                    legacy_summary_id
                ) VALUES ('DRS-DUPLICATE', '2026-06-23', '2026-06-25',
                          'DRIVER-2', 'Other Driver', 0, 0, 'SAVED',
                          '2026-06-23T07:00:00Z', '2026-06-23T07:05:00Z',
                          'Office', 'FTS-DUPLICATE-MARKER')
                """
            )
            connection.commit()

        report = inspect_migration(self.db_path)

        self.assertTrue(
            any(
                conflict["reason"] == "Duplicate legacy migration markers detected."
                for conflict in report["conflicts"]
            )
        )
        with self.assertRaises(MigrationBlockedError):
            self._apply()
        self.assertEqual(2, self._count("delivery_run_sheets"))

    def test_generated_summary_blocks_all_saved_candidates(self):
        self._seed_summary("FTS-SAVED", delivery_rows=1)
        self._seed_summary(
            "FTS-GENERATED",
            status="GENERATED",
            delivery_rows=1,
            delivery_date="2026-06-25",
        )

        report = inspect_migration(self.db_path)
        self.assertEqual(1, report["summary"]["generated_legacy_summaries"])
        with self.assertRaisesRegex(MigrationBlockedError, "GENERATED Final Summaries"):
            self._apply()

        self.assertEqual(0, self._count("delivery_run_sheets"))
        self.assertFalse(self.backup_dir.exists())

    def test_transaction_rolls_back_both_modules_on_failure(self):
        self._seed_summary("FTS-ROLLBACK", delivery_rows=1, opshop_rows=1)

        with patch(
            "tools.migrate_legacy_final_summaries_to_workspaces._insert_opshop_collection",
            side_effect=RuntimeError("simulated OP SHOP migration failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated OP SHOP"):
                self._apply()

        self.assertEqual(0, self._count("delivery_run_sheets"))
        self.assertEqual(0, self._count("delivery_run_sheet_rows"))
        self.assertEqual(0, self._count("opshop_pickup_collections"))
        self.assertEqual(0, self._count("opshop_pickup_collection_rows"))
        self.assertTrue(any(self.backup_dir.glob("*.sqlite3")))

    def test_legacy_tables_and_repository_read_remain_unchanged(self):
        self._seed_summary("FTS-UNCHANGED", delivery_rows=1, opshop_rows=1)
        before = self._legacy_snapshot("FTS-UNCHANGED")

        self._apply()

        after = self._legacy_snapshot("FTS-UNCHANGED")
        self.assertEqual(before, after)
        loaded = self.repository.get_final_trip_summary("FTS-UNCHANGED")
        self.assertIsNotNone(loaded)
        self.assertEqual("Legacy Driver", loaded.driver_name_snapshot)
        self.assertEqual("Legacy Customer 1", loaded.trips[0].orders[0].company_name_snapshot)
        self.assertEqual("Legacy OP SHOP 1", loaded.opshop_pickups[0].opshop_name_snapshot)

    def _apply(self):
        return migrate_legacy_final_summaries(
            self.db_path,
            apply=True,
            yes=True,
            backup_dir=self.backup_dir,
        )

    def _seed_summary(
        self,
        summary_id,
        *,
        status="SAVED",
        delivery_rows=0,
        opshop_rows=0,
        dispatch_date="2026-06-23",
        delivery_date="2026-06-24",
        generated_at="2026-06-23T08:00:00Z",
        saved_at="2026-06-23T08:05:00Z",
    ):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id, dispatch_date, delivery_date, driver_id,
                    driver_name_snapshot, vehicle_id, vehicle_rego_snapshot,
                    total_pallets, total_loose_bags, status, generated_at,
                    saved_at, saved_by_account_name, saved_by_account_id
                ) VALUES (?, ?, ?, 'DRIVER-1', 'Legacy Driver', 'VEHICLE-1',
                          'ABC123', 3, 4, ?, ?, ?, 'Legacy Operator', NULL)
                """,
                (
                    summary_id,
                    dispatch_date,
                    delivery_date,
                    status,
                    generated_at,
                    saved_at,
                ),
            )
            for row_no in range(1, delivery_rows + 1):
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_rows (
                        row_id, summary_id, trip_no, row_no, task_type, task_id,
                        order_id_snapshot, invoice_number_snapshot, order_no_snapshot,
                        company_name_snapshot, suburb_snapshot, delivery_address_snapshot,
                        product_snapshot, product_details_snapshot,
                        estimated_distance_km_from_warehouse_snapshot,
                        pallet_quantity_snapshot, loose_bags_quantity_snapshot,
                        note_snapshot
                    ) VALUES (?, ?, ?, ?, 'ORDER', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"FSR-{summary_id}-{row_no}",
                        summary_id,
                        "trip1" if row_no % 2 else "trip2",
                        row_no,
                        f"ORD-{summary_id}-{row_no}",
                        f"ORD-{summary_id}-{row_no}",
                        f"INV-{row_no}",
                        f"ORDER-{row_no}",
                        f"Legacy Customer {row_no}",
                        "Dandenong",
                        "1 Legacy Street",
                        "Rags",
                        '[{"product_name":"Rags","quantity":3,"unit":"PALLETS"}]',
                        18.75,
                        3,
                        4,
                        "Legacy delivery note",
                    ),
                )
            for row_no in range(1, opshop_rows + 1):
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_opshop_pickup_rows (
                        row_id, summary_id, row_no, pickup_task_id_snapshot,
                        opshop_name_snapshot, suburb_snapshot, street_address_snapshot,
                        area_region_snapshot, pickup_date_snapshot, run_type_snapshot,
                        pickup_category_snapshot, route_group_id_snapshot,
                        route_group_name_snapshot, pickup_frequency_snapshot,
                        time_window_snapshot, primary_contact_snapshot,
                        primary_phone_snapshot, secondary_contact_snapshot,
                        secondary_phone_snapshot, access_type_snapshot,
                        key_required_snapshot, trailer_restriction_snapshot,
                        notes_snapshot, status_snapshot
                    ) VALUES (?, ?, ?, ?, ?, 'BENALLA', '57 BRIDGE STREET',
                              'NORTH EAST', ?, 'ON_CALL', 'COUNTRYSIDE',
                              'ROUTE-GROUP-1', 'YARRAWONGA', 'ON CALL',
                              '09:00-12:00', 'Jan', '03 5000 0000', 'Alex',
                              '0400 000 000', 'Loading zone', 1, 'No trailer',
                              'Long access and status notes', 'ASSIGNED')
                    """,
                    (
                        f"FSOP-{summary_id}-{row_no}",
                        summary_id,
                        row_no,
                        f"OPSHOP-PICKUP-{summary_id}-{row_no}",
                        f"Legacy OP SHOP {row_no}",
                        delivery_date,
                    ),
                )
            connection.commit()

    def _insert_manual_delivery_run_sheet(
        self,
        *,
        legacy_summary_id=None,
        delivery_date="2026-06-24",
    ):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO delivery_run_sheets (
                    run_sheet_id, dispatch_date, delivery_date, driver_id,
                    driver_name_snapshot, total_pallets, total_loose_bags,
                    status, generated_at, saved_at, saved_by_account_name,
                    legacy_summary_id
                ) VALUES ('DRS-MANUAL', '2026-06-23', ?, 'DRIVER-1',
                          'Manual Driver', 0, 0, 'SAVED',
                          '2026-06-23T07:00:00Z', '2026-06-23T07:05:00Z',
                          'Office', ?)
                """,
                (delivery_date, legacy_summary_id),
            )
            connection.commit()

    def _legacy_snapshot(self, summary_id):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            header = dict(
                connection.execute(
                    "SELECT * FROM final_trip_summaries WHERE summary_id = ?",
                    (summary_id,),
                ).fetchone()
            )
            delivery = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM final_trip_summary_rows WHERE summary_id = ? ORDER BY row_id",
                    (summary_id,),
                ).fetchall()
            ]
            opshop = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM final_trip_summary_opshop_pickup_rows WHERE summary_id = ? ORDER BY row_id",
                    (summary_id,),
                ).fetchall()
            ]
        return header, delivery, opshop

    def _workspace_counts(self):
        return {
            table: self._count(table)
            for table in (
                "delivery_run_sheets",
                "delivery_run_sheet_rows",
                "opshop_pickup_collections",
                "opshop_pickup_collection_rows",
            )
        }

    def _count(self, table):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def _one(self, table):
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(f"SELECT * FROM {table}").fetchone()


if __name__ == "__main__":
    unittest.main()
