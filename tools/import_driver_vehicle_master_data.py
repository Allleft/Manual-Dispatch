import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DRIVER_COLUMNS = [
    "driver_id",
    "name",
    "license_no",
    "email",
    "phone_number",
    "start_time",
    "end_time",
    "is_available",
    "preferred_zone",
    "pallet_only",
    "is_deleted",
]

VEHICLE_COLUMNS = [
    "vehicle_id",
    "rego",
    "type",
    "is_available",
    "pallet_capacity",
    "tub_capacity",
    "trolley_capacity",
    "stillage_capacity",
    "is_deleted",
]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Import Driver and Vehicle master data from an old Manual Dispatch "
            "SQLite database into the current database."
        )
    )
    parser.add_argument("--source-db", required=True, help="Old SQLite DB or backup path")
    parser.add_argument("--target-db", required=True, help="Current NAS SQLite DB path")
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Update existing Driver/Vehicle rows in the target database",
    )
    args = parser.parse_args()

    result = import_driver_vehicle_master_data(
        source_db=Path(args.source_db),
        target_db=Path(args.target_db),
        overwrite_existing=args.overwrite_existing,
    )
    print_import_report(result)


def import_driver_vehicle_master_data(source_db, target_db, overwrite_existing=False):
    source_db = Path(source_db)
    target_db = Path(target_db)
    _validate_database_file(source_db, "source")
    _validate_database_file(target_db, "target")

    backup_path = _backup_target_database(target_db)
    result = {
        "source_db": str(source_db.resolve()),
        "target_db": str(target_db.resolve()),
        "target_backup": str(backup_path.resolve()),
        "drivers_inserted": 0,
        "drivers_skipped": 0,
        "drivers_updated": 0,
        "vehicles_inserted": 0,
        "vehicles_skipped": 0,
        "vehicles_updated": 0,
        "overwrite_existing": overwrite_existing,
    }

    try:
        with sqlite3.connect(source_db) as source_connection:
            source_connection.row_factory = sqlite3.Row
            _assert_columns_exist(source_connection, "manual_drivers", DRIVER_COLUMNS)
            _assert_columns_exist(source_connection, "manual_vehicles", VEHICLE_COLUMNS)
            source_drivers = _fetch_rows(source_connection, "manual_drivers", DRIVER_COLUMNS)
            source_vehicles = _fetch_rows(
                source_connection,
                "manual_vehicles",
                VEHICLE_COLUMNS,
            )

        target_connection = sqlite3.connect(target_db)
        try:
            target_connection.row_factory = sqlite3.Row
            target_connection.execute("PRAGMA foreign_keys = ON")
            _assert_columns_exist(target_connection, "manual_drivers", DRIVER_COLUMNS)
            _assert_columns_exist(target_connection, "manual_vehicles", VEHICLE_COLUMNS)

            with target_connection:
                driver_counts = _import_rows(
                    target_connection,
                    table_name="manual_drivers",
                    columns=DRIVER_COLUMNS,
                    primary_key="driver_id",
                    rows=source_drivers,
                    overwrite_existing=overwrite_existing,
                )
                vehicle_counts = _import_rows(
                    target_connection,
                    table_name="manual_vehicles",
                    columns=VEHICLE_COLUMNS,
                    primary_key="vehicle_id",
                    rows=source_vehicles,
                    overwrite_existing=overwrite_existing,
                )
        finally:
            target_connection.close()
    except Exception:
        # The target backup has already been created. The target transaction rolls
        # back automatically when an exception escapes the `with target_connection`.
        raise

    result.update(
        {
            "drivers_inserted": driver_counts["inserted"],
            "drivers_skipped": driver_counts["skipped"],
            "drivers_updated": driver_counts["updated"],
            "vehicles_inserted": vehicle_counts["inserted"],
            "vehicles_skipped": vehicle_counts["skipped"],
            "vehicles_updated": vehicle_counts["updated"],
        }
    )
    return result


def print_import_report(result):
    print("Driver/Vehicle master data import complete.")
    print(f"Source DB: {result['source_db']}")
    print(f"Target DB: {result['target_db']}")
    print(f"Target backup: {result['target_backup']}")
    print(f"Drivers inserted: {result['drivers_inserted']}")
    print(f"Drivers skipped: {result['drivers_skipped']}")
    if result["overwrite_existing"]:
        print(f"Drivers updated: {result['drivers_updated']}")
    print(f"Vehicles inserted: {result['vehicles_inserted']}")
    print(f"Vehicles skipped: {result['vehicles_skipped']}")
    if result["overwrite_existing"]:
        print(f"Vehicles updated: {result['vehicles_updated']}")


def _validate_database_file(path, label):
    if not path.exists():
        raise FileNotFoundError(f"{label} database not found: {path}")
    if not path.is_file():
        raise ValueError(f"{label} database path is not a file: {path}")


def _backup_target_database(target_db):
    backup_dir = target_db.resolve().parents[1] / "backups"
    if target_db.resolve().parent.name != "data":
        backup_dir = Path.cwd() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = _next_available_backup_path(
        backup_dir,
        f"manual_dispatch_before_driver_vehicle_import_{timestamp}",
    )
    with sqlite3.connect(target_db) as source_connection:
        with sqlite3.connect(backup_path) as backup_connection:
            source_connection.backup(backup_connection)
    return backup_path


def _next_available_backup_path(backup_dir, stem):
    backup_path = backup_dir / f"{stem}.sqlite3"
    if not backup_path.exists():
        return backup_path

    counter = 1
    while True:
        candidate = backup_dir / f"{stem}_{counter}.sqlite3"
        if not candidate.exists():
            return candidate
        counter += 1


def _assert_columns_exist(connection, table_name, required_columns):
    table_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    missing_columns = [column for column in required_columns if column not in table_columns]
    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {', '.join(missing_columns)}"
        )


def _fetch_rows(connection, table_name, columns):
    column_sql = ", ".join(columns)
    return [
        dict(row)
        for row in connection.execute(
            f"SELECT {column_sql} FROM {table_name} ORDER BY {columns[0]}"
        ).fetchall()
    ]


def _import_rows(
    connection,
    table_name,
    columns,
    primary_key,
    rows,
    overwrite_existing=False,
):
    counts = {"inserted": 0, "skipped": 0, "updated": 0}
    non_key_columns = [column for column in columns if column != primary_key]
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = (
        f"INSERT INTO {table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    update_sql = (
        f"UPDATE {table_name} "
        f"SET {', '.join(f'{column} = ?' for column in non_key_columns)} "
        f"WHERE {primary_key} = ?"
    )

    for row in rows:
        row_id = row[primary_key]
        existing = connection.execute(
            f"SELECT 1 FROM {table_name} WHERE {primary_key} = ?",
            (row_id,),
        ).fetchone()
        values = [row[column] for column in columns]

        if not existing:
            connection.execute(insert_sql, values)
            counts["inserted"] += 1
        elif overwrite_existing:
            update_values = [row[column] for column in non_key_columns] + [row_id]
            connection.execute(update_sql, update_values)
            counts["updated"] += 1
        else:
            counts["skipped"] += 1

    return counts


if __name__ == "__main__":
    main()
