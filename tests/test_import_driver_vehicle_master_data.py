import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from tools.import_driver_vehicle_master_data import (
    import_driver_vehicle_master_data,
)


class DriverVehicleMasterDataImportToolTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"master-import-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.source_db = self.temp_dir / "source.sqlite3"
        self.target_data_dir = self.temp_dir / "data"
        self.target_data_dir.mkdir()
        self.target_db = self.target_data_dir / "manual_dispatch.sqlite3"
        self._create_database(self.source_db)
        self._create_database(self.target_db)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_import_inserts_missing_and_skips_existing_by_default(self):
        self._insert_driver(self.source_db, "D001", "Alice Driver")
        self._insert_driver(self.source_db, "D002", "Source Existing Driver")
        self._insert_driver(self.target_db, "D002", "Target Existing Driver")
        self._insert_vehicle(self.source_db, "V001", "SRC001")
        self._insert_vehicle(self.source_db, "V002", "SRC002")
        self._insert_vehicle(self.target_db, "V002", "TGT002")

        result = import_driver_vehicle_master_data(self.source_db, self.target_db)

        self.assertEqual(1, result["drivers_inserted"])
        self.assertEqual(1, result["drivers_skipped"])
        self.assertEqual(0, result["drivers_updated"])
        self.assertEqual(1, result["vehicles_inserted"])
        self.assertEqual(1, result["vehicles_skipped"])
        self.assertEqual(0, result["vehicles_updated"])
        self.assertEqual("Alice Driver", self._get_driver_name("D001"))
        self.assertEqual("Target Existing Driver", self._get_driver_name("D002"))
        self.assertEqual("SRC001", self._get_vehicle_rego("V001"))
        self.assertEqual("TGT002", self._get_vehicle_rego("V002"))
        self.assertTrue(Path(result["target_backup"]).exists())
        self.assertEqual(self.temp_dir / "backups", Path(result["target_backup"]).parent)

    def test_import_updates_existing_when_overwrite_flag_is_used(self):
        self._insert_driver(self.source_db, "D002", "Source Existing Driver")
        self._insert_driver(self.target_db, "D002", "Target Existing Driver")
        self._insert_vehicle(self.source_db, "V002", "SRC002")
        self._insert_vehicle(self.target_db, "V002", "TGT002")

        result = import_driver_vehicle_master_data(
            self.source_db,
            self.target_db,
            overwrite_existing=True,
        )

        self.assertEqual(0, result["drivers_inserted"])
        self.assertEqual(0, result["drivers_skipped"])
        self.assertEqual(1, result["drivers_updated"])
        self.assertEqual(0, result["vehicles_inserted"])
        self.assertEqual(0, result["vehicles_skipped"])
        self.assertEqual(1, result["vehicles_updated"])
        self.assertEqual("Source Existing Driver", self._get_driver_name("D002"))
        self.assertEqual("SRC002", self._get_vehicle_rego("V002"))
        self.assertTrue(Path(result["target_backup"]).exists())

    def test_import_rolls_back_target_changes_if_import_fails(self):
        self._insert_driver(self.source_db, "D001", "Alice Driver")
        with sqlite3.connect(self.source_db) as connection:
            connection.execute("DROP TABLE manual_vehicles")

        with self.assertRaises(ValueError):
            import_driver_vehicle_master_data(self.source_db, self.target_db)

        with sqlite3.connect(self.target_db) as connection:
            driver_count = connection.execute(
                "SELECT COUNT(*) FROM manual_drivers"
            ).fetchone()[0]

        self.assertEqual(0, driver_count)

    def _create_database(self, db_path):
        with sqlite3.connect(db_path) as connection:
            connection.executescript(
                """
                CREATE TABLE manual_drivers (
                    driver_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    license_no TEXT,
                    email TEXT,
                    phone_number TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    preferred_zone TEXT,
                    pallet_only INTEGER NOT NULL DEFAULT 0,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE manual_vehicles (
                    vehicle_id TEXT PRIMARY KEY,
                    rego TEXT NOT NULL,
                    type TEXT,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    pallet_capacity INTEGER NOT NULL DEFAULT 0,
                    tub_capacity INTEGER NOT NULL DEFAULT 0,
                    trolley_capacity INTEGER NOT NULL DEFAULT 0,
                    stillage_capacity INTEGER NOT NULL DEFAULT 0,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def _insert_driver(self, db_path, driver_id, name):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_drivers (
                    driver_id,
                    name,
                    license_no,
                    email,
                    phone_number,
                    start_time,
                    end_time,
                    is_available,
                    preferred_zone,
                    pallet_only,
                    is_deleted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    driver_id,
                    name,
                    f"LIC-{driver_id}",
                    f"{driver_id.lower()}@example.com",
                    "0400 000 000",
                    "08:00",
                    "17:00",
                    1,
                    "North",
                    0,
                    0,
                ),
            )

    def _insert_vehicle(self, db_path, vehicle_id, rego):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_vehicles (
                    vehicle_id,
                    rego,
                    type,
                    is_available,
                    pallet_capacity,
                    tub_capacity,
                    trolley_capacity,
                    stillage_capacity,
                    is_deleted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (vehicle_id, rego, "Truck", 1, 12, 0, 0, 0, 0),
            )

    def _get_driver_name(self, driver_id):
        with sqlite3.connect(self.target_db) as connection:
            return connection.execute(
                "SELECT name FROM manual_drivers WHERE driver_id = ?",
                (driver_id,),
            ).fetchone()[0]

    def _get_vehicle_rego(self, vehicle_id):
        with sqlite3.connect(self.target_db) as connection:
            return connection.execute(
                "SELECT rego FROM manual_vehicles WHERE vehicle_id = ?",
                (vehicle_id,),
            ).fetchone()[0]


if __name__ == "__main__":
    unittest.main()
