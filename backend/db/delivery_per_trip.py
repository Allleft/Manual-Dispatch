"""Explicit, FK-safe Delivery persistence upgrade. Startup never invokes apply."""

import json
import re
import sqlite3
import tempfile
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from backend.db.invariants import (
    INVARIANT_INDEX_DEFINITIONS,
    audit_database_invariants,
    index_matches_definition,
    table_columns,
)


CAPABILITY = "delivery_per_trip"
CAPABILITY_VERSION = 1
CAPABILITY_TABLE = "manual_dispatch_schema_capabilities"
TABLES = ("manual_driver_vehicle_assignments", "delivery_run_sheets")
SNAPSHOT_TABLES = (
    "delivery_run_sheets", "delivery_run_sheet_rows", "delivery_run_sheet_outcomes"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_DDL = """
    CREATE TABLE IF NOT EXISTS manual_dispatch_schema_capabilities (
        capability TEXT PRIMARY KEY,
        version INTEGER NOT NULL CHECK(version > 0)
    )
"""


class DeliveryPerTripMigrationError(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


def _primary_key(connection, table):
    return tuple(row["name"] for row in sorted(
        connection.execute(f'PRAGMA table_info("{table}")'), key=lambda row: row["pk"]
    ) if row["pk"])


def _per_trip_schema_issues(connection):
    issues = []
    for table in TABLES:
        columns = {row["name"]: row for row in connection.execute(f'PRAGMA table_info("{table}")')}
        expected_columns, expected_pk = _canonical_shape(table)
        missing = sorted(expected_columns - columns.keys())
        if missing:
            issues.append(f"{table}: missing columns {', '.join(missing)}")
        if _primary_key(connection, table) != expected_pk:
            issues.append(f"{table}: incorrect primary key")
        if "trip_no" in columns:
            if columns["trip_no"]["notnull"] or columns["trip_no"]["type"].upper() != "TEXT":
                issues.append(f"{table}: trip_no must be nullable TEXT")
            ddl = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()["sql"]
            trip_check = re.search(
                r"CHECK\(trip_noISNULLORtrip_noIN\(([^)]*)\)\)", re.sub(r"\s+", "", ddl), re.I
            )
            if trip_check is None or trip_check.group(1) != "'trip1','trip2'":
                issues.append(f"{table}: missing trip_no value constraint")
    for definition in INVARIANT_INDEX_DEFINITIONS:
        if definition["table"] in TABLES and not index_matches_definition(connection, definition):
            issues.append(f"{definition['name']}: missing or incorrect index definition")
    for row in connection.execute('PRAGMA index_list("delivery_run_sheets")'):
        if row["unique"]:
            columns = tuple(item["name"] for item in connection.execute(
                f'PRAGMA index_info("{row["name"]}")'
            ))
            if columns == ("dispatch_date", "delivery_date", "driver_id"):
                issues.append("delivery_run_sheets: obsolete table uniqueness")
    return issues


def delivery_per_trip_schema_status(connection):
    issues = _per_trip_schema_issues(connection)
    version = None
    capability_columns = table_columns(connection, CAPABILITY_TABLE)
    if {"capability", "version"}.issubset(capability_columns) and _primary_key(connection, CAPABILITY_TABLE) == ("capability",):
        row = connection.execute(
            f"SELECT version FROM {CAPABILITY_TABLE} WHERE capability = ?", (CAPABILITY,)
        ).fetchone()
        version = row["version"] if row else None
    if version != CAPABILITY_VERSION:
        issues.append("delivery_per_trip: missing or unsupported capability version")
    return {"ready": not issues, "version": version, "issues": issues}


def mark_per_trip_schema_ready(connection):
    issues = _per_trip_schema_issues(connection)
    if issues:
        raise DeliveryPerTripMigrationError(
            "Per-trip schema validation failed.",
            {"ready": False, "issues": issues},
        )
    audit = audit_database_invariants(connection)
    if audit["conflicts"]:
        raise DeliveryPerTripMigrationError("Per-trip identity audit failed.", audit)
    connection.execute(CAPABILITY_DDL)
    connection.execute(
        f"INSERT INTO {CAPABILITY_TABLE} (capability, version) VALUES (?, ?) "
        "ON CONFLICT(capability) DO UPDATE SET version = excluded.version",
        (CAPABILITY, CAPABILITY_VERSION),
    )
    status = delivery_per_trip_schema_status(connection)
    if not status["ready"]:
        raise DeliveryPerTripMigrationError("Per-trip schema validation failed.", status)


def _validated_path(db_path):
    path = Path(db_path).resolve()
    protected = ("data", "482", "release", "docs/instruction-book")
    if any(path.is_relative_to((PROJECT_ROOT / name).resolve()) for name in protected):
        raise DeliveryPerTripMigrationError("Migration refuses protected business paths; use an isolated copy.")
    if not path.is_file():
        raise DeliveryPerTripMigrationError("An existing, explicit isolated SQLite fixture is required.")
    return path


def _read_only_connection(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _records(connection, table):
    return sorted(
        (dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')),
        key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False),
    )


def _table_ddl(table):
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\n\);", schema, re.S
    )
    if not match:
        raise RuntimeError(f"Missing canonical table definition: {table}")
    return match.group(0).rstrip(";")


@lru_cache(maxsize=2)
def _canonical_shape(table):
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(_table_ddl(table))
        return frozenset(table_columns(connection, table)), _primary_key(connection, table)


def _preflight(connection):
    status = delivery_per_trip_schema_status(connection)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    fk_errors = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
    conflicts = []
    if integrity != "ok" or fk_errors:
        conflicts.append("Database integrity or foreign keys are invalid.")
    if status["ready"]:
        conflicts.extend(audit_database_invariants(connection)["conflicts"])
        return {"already_ready": True, "capability": status, "conflicts": conflicts,
                "vehicle_classification": [], "integrity_check": integrity,
                "foreign_key_errors": fk_errors}
    for table in TABLES:
        columns = table_columns(connection, table)
        if "trip_no" in columns:
            conflicts.append(f"{table}: partial/invalid per-trip schema; do not guess a repair.")
        temp_table = table + "__per_trip_new"
        if table_columns(connection, temp_table):
            conflicts.append(f"Unexpected migration table: {temp_table}")
    if _primary_key(connection, TABLES[0]) != ("dispatch_date", "delivery_date", "driver_id"):
        conflicts.append("Expected the pre-feature three-column vehicle primary key.")
    required = set(SNAPSHOT_TABLES) | {TABLES[0], "manual_orders", "manual_dispatch_assignments"}
    for table in required:
        if not table_columns(connection, table):
            conflicts.append(f"Missing required table: {table}")
    if conflicts:
        return {"already_ready": False, "capability": status, "conflicts": conflicts,
                "vehicle_classification": [], "integrity_check": integrity,
                "foreign_key_errors": fk_errors}
    conflicts.extend(audit_database_invariants(connection)["conflicts"])
    for table in TABLES:
        # Reject unrecognised columns instead of dropping custom historical data.
        expected_columns = _canonical_shape(table)[0] - {"trip_no"}
        if table_columns(connection, table) != expected_columns:
            conflicts.append(f"{table}: unexpected old columns; explicit review is required.")
        allowed_indexes = {
            definition["name"] for definition in INVARIANT_INDEX_DEFINITIONS
            if definition["table"] == table
        }
        allowed_indexes.add("idx_delivery_run_sheets_legacy_summary")
        for index in connection.execute(f'PRAGMA index_list("{table}")'):
            if not index["unique"] or index["origin"] == "pk" or index["name"] in allowed_indexes:
                continue
            columns = tuple(row["name"] for row in connection.execute(f'PRAGMA index_info("{index["name"]}")'))
            if table == "delivery_run_sheets" and index["origin"] == "u" and columns == ("dispatch_date", "delivery_date", "driver_id"):
                continue
            conflicts.append(f"{table}: unrecognised unique constraint {index['name']}; explicit review is required.")
    if conflicts:
        return {"already_ready": False, "capability": status, "conflicts": conflicts,
                "vehicle_classification": [], "integrity_check": integrity,
                "foreign_key_errors": fk_errors}
    sheets = _records(connection, "delivery_run_sheets")
    if table_columns(connection, "final_trip_summaries") and table_columns(connection, "final_trip_summary_rows"):
        unresolved = connection.execute("""
            SELECT summary.summary_id
            FROM final_trip_summaries summary
            WHERE summary.status IN ('GENERATED', 'SAVED')
                AND EXISTS (SELECT 1 FROM final_trip_summary_rows WHERE summary_id = summary.summary_id)
                AND (summary.status = 'GENERATED' OR NOT EXISTS (
                    SELECT 1 FROM delivery_run_sheets sheet
                    WHERE sheet.legacy_summary_id = summary.summary_id AND sheet.status = 'SAVED'
                        AND sheet.dispatch_date = summary.dispatch_date
                        AND sheet.delivery_date = summary.delivery_date AND sheet.driver_id = summary.driver_id
                        AND (SELECT COUNT(*) FROM delivery_run_sheet_rows WHERE run_sheet_id = sheet.run_sheet_id)
                            = (SELECT COUNT(*) FROM final_trip_summary_rows WHERE summary_id = summary.summary_id)
                ))
        """).fetchall()
        conflicts.extend(f"Unresolved legacy Delivery Final Trip Summary: {row['summary_id']}" for row in unresolved)
    vehicles = _records(connection, TABLES[0])
    orders = {row["order_id"]: row for row in _records(connection, "manual_orders")}
    active_trips = {}
    for assignment in _records(connection, "manual_dispatch_assignments"):
        if assignment["task_type"] != "ORDER":
            continue
        order = orders.get(assignment["task_id"])
        if order is None or assignment["trip_no"] not in ("trip1", "trip2"):
            conflicts.append(f"Inconsistent Delivery assignment: {assignment['assignment_id']}")
            continue
        if order["status"] == "ACTIVE":
            identity = order["delivery_date"], assignment["driver_id"]
            active_trips.setdefault(identity, set()).add(assignment["trip_no"])
    classification = []
    for vehicle in vehicles:
        identity = vehicle["delivery_date"], vehicle["driver_id"]
        frozen = [sheet for sheet in sheets if (sheet["delivery_date"], sheet["driver_id"]) == identity]
        if frozen:
            if any(sheet["vehicle_id"] != vehicle["vehicle_id"] for sheet in frozen):
                conflicts.append(f"Vehicle selection contradicts frozen Run Sheet: {identity}")
            trip_nos = []
            reason = "legacy_run_sheet"
        else:
            trip_nos = sorted(active_trips.get(identity, set()))
            reason = "active_delivery_orders" if trip_nos else "no_active_delivery_orders"
        classification.append({**vehicle, "seed_trips": trip_nos, "reason": reason})
    return {"already_ready": False, "capability": status, "conflicts": conflicts,
            "vehicle_classification": classification, "integrity_check": integrity,
            "foreign_key_errors": fk_errors}


def inspect_delivery_per_trip_migration(db_path):
    path = _validated_path(db_path)
    with closing(_read_only_connection(path)) as connection:
        connection.execute("BEGIN")
        return {"db_path": str(path), "mode": "dry-run", **_preflight(connection)}


def _rebuild_parent(connection, table):
    columns = tuple(row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")'))
    objects = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE tbl_name = ? "
        "AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY type, name", (table,)
    ).fetchall()
    invariant_names = {item["name"] for item in INVARIANT_INDEX_DEFINITIONS}
    temp_table = table + "__per_trip_new"
    ddl = _table_ddl(table).replace(
        f"CREATE TABLE IF NOT EXISTS {table}", f"CREATE TABLE {temp_table}", 1
    )
    connection.execute(ddl)
    names = ", ".join(f'"{name}"' for name in columns)
    connection.execute(f'INSERT INTO "{temp_table}" ({names}) SELECT {names} FROM "{table}"')
    connection.execute(f'DROP TABLE "{table}"')
    connection.execute(f'ALTER TABLE "{temp_table}" RENAME TO "{table}"')
    for row in objects:
        if row["name"] not in invariant_names:
            connection.execute(row["sql"])


def _verify_preservation(connection, before, vehicles, classification):
    for table, records in before.items():
        after = _records(connection, table)
        if table == "delivery_run_sheets":
            if any(row["trip_no"] is not None for row in after):
                raise RuntimeError("Migration changed legacy Run Sheet scope.")
            after = [{key: value for key, value in row.items() if key != "trip_no"} for row in after]
        if after != records:
            raise RuntimeError(f"Migration changed snapshot content: {table}")
    carryover = [row for row in _records(connection, TABLES[0]) if row["trip_no"] is None]
    carryover = [{key: value for key, value in row.items() if key != "trip_no"} for row in carryover]
    if carryover != vehicles:
        raise RuntimeError("Migration changed legacy vehicle carryover.")
    expected_seeds = [
        {**{key: row[key] for key in vehicles[0]}, "trip_no": trip_no}
        for row in classification for trip_no in row["seed_trips"]
    ]
    expected_seeds.sort(key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
    actual_seeds = [row for row in _records(connection, TABLES[0]) if row["trip_no"] is not None]
    if actual_seeds != expected_seeds:
        raise RuntimeError("Migration changed classified vehicle seeds.")


def migrate_delivery_per_trip(db_path, *, apply=False, yes=False):
    path = _validated_path(db_path)
    report = inspect_delivery_per_trip_migration(path)
    if report["conflicts"]:
        raise DeliveryPerTripMigrationError("Per-trip migration preflight failed.", report)
    if not apply or report["already_ready"]:
        return report
    if not yes:
        raise DeliveryPerTripMigrationError("Apply requires both --apply and --yes.", report)
    backup_path = None
    with closing(sqlite3.connect(path, isolation_level=None, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        # FK must be disabled before BEGIN: dropping a parent must not CASCADE.
        connection.execute("PRAGMA foreign_keys = OFF")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0]:
            raise RuntimeError("Could not disable foreign keys before migration.")
        connection.execute("BEGIN IMMEDIATE")
        try:
            locked = _preflight(connection)
            if locked["conflicts"]:
                raise DeliveryPerTripMigrationError("Locked preflight failed.", locked)
            if locked["already_ready"]:
                connection.rollback()
                return {"db_path": str(path), "mode": "dry-run", **locked}
            # Backup from an independent reader while this connection owns the write lock.
            descriptor, backup_name = tempfile.mkstemp(prefix=path.stem + "-pre-trip-", suffix=".sqlite3", dir=path.parent)
            import os
            os.close(descriptor)
            backup_path = Path(backup_name)
            with closing(_read_only_connection(path)) as source, closing(sqlite3.connect(backup_path)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Migration backup failed integrity_check.")
            before = {table: _records(connection, table) for table in SNAPSHOT_TABLES}
            vehicles = _records(connection, TABLES[0])
            for table in TABLES:
                _rebuild_parent(connection, table)
            for row in locked["vehicle_classification"]:
                for trip_no in row["seed_trips"]:
                    connection.execute(
                        "INSERT INTO manual_driver_vehicle_assignments "
                        "(dispatch_date, delivery_date, driver_id, vehicle_id, trip_no, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (row["dispatch_date"], row["delivery_date"], row["driver_id"], row["vehicle_id"],
                         trip_no, row["created_at"], row["updated_at"]),
                    )
            for definition in INVARIANT_INDEX_DEFINITIONS:
                if definition["table"] in TABLES:
                    connection.execute(
                        f"CREATE UNIQUE INDEX {definition['name']} ON {definition['table']} "
                        f"({', '.join(definition['columns'])}) WHERE {definition['where']}"
                    )
            _verify_preservation(connection, before, vehicles, locked["vehicle_classification"])
            if list(connection.execute("PRAGMA foreign_key_check")):
                raise RuntimeError("Migration foreign_key_check failed.")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Migration integrity_check failed.")
            mark_per_trip_schema_ready(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
    final = inspect_delivery_per_trip_migration(path)
    return {**final, "mode": "apply", "backup_path": str(backup_path),
            "vehicle_classification": locked["vehicle_classification"]}
