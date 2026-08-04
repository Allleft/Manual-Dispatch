"""Safely consolidate duplicate normalized OP SHOP physical locations.

The tool defaults to a read-only audit. Applying a repair requires an explicit
canonical location, one or more duplicate IDs, and confirmation. Live schedule
and task references are moved without changing their IDs; immutable collection
and Final Summary snapshots are only counted and are never rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.import_regular_opshop_pickups_to_db import location_key_from_values  # noqa: E402
from tools.maintenance_logbook import (  # noqa: E402
    add_maintenance_logbook_arguments,
    record_maintenance_event,
    resolve_maintenance_actor,
    safe_basename,
)


def audit_duplicate_locations(db_path):
    """Return every duplicate normalized OP SHOP physical-location group."""

    path = Path(db_path)
    with _connect_read_only(path) as connection:
        groups = _duplicate_groups(connection)
        findings = [
            _describe_group(connection, key, locations)
            for key, locations in sorted(groups.items())
        ]
    return {
        "mode": "dry-run",
        "db_path": str(path),
        "duplicate_group_count": len(findings),
        "groups": findings,
    }


def plan_location_repair(db_path, canonical_opshop_id, duplicate_opshop_ids):
    """Build a fail-closed repair plan for one normalized identity group."""

    path = Path(db_path)
    with _connect_read_only(path) as connection:
        return _build_repair_plan(
            connection,
            path,
            canonical_opshop_id,
            duplicate_opshop_ids,
        )


def apply_location_repair(
    db_path,
    canonical_opshop_id,
    duplicate_opshop_ids,
    *,
    yes=False,
    actor=None,
    logbook_dir=None,
):
    """Apply an audited repair atomically after creating a verified backup."""

    if not yes:
        raise ValueError("apply_location_repair requires yes=True")

    path = Path(db_path)
    dry_run = plan_location_repair(
        path,
        canonical_opshop_id,
        duplicate_opshop_ids,
    )
    if not dry_run["can_apply"]:
        raise ValueError("Repair cannot be applied: " + "; ".join(dry_run["conflicts"]))
    if dry_run["already_repaired"]:
        return {**dry_run, "mode": "apply", "backup_path": None, "applied": False}

    backup_path = backup_database(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        plan = _build_repair_plan(
            connection,
            path,
            canonical_opshop_id,
            duplicate_opshop_ids,
        )
        if not plan["can_apply"]:
            raise ValueError(
                "Repair became unsafe after dry-run: " + "; ".join(plan["conflicts"])
            )

        duplicate_ids = plan["existing_duplicate_opshop_ids"]
        placeholders = ",".join("?" for _ in duplicate_ids)
        schedule_cursor = connection.execute(
            "UPDATE opshop_pickup_schedules SET opshop_id = ? "
            f"WHERE opshop_id IN ({placeholders})",
            (canonical_opshop_id, *duplicate_ids),
        )
        task_cursor = connection.execute(
            "UPDATE opshop_pickup_tasks SET opshop_id = ? "
            f"WHERE opshop_id IN ({placeholders})",
            (canonical_opshop_id, *duplicate_ids),
        )

        remaining = _remaining_opshop_references(connection, duplicate_ids)
        if remaining:
            raise ValueError(
                "Duplicate locations still have references after migration: "
                + json.dumps(remaining, sort_keys=True)
            )

        delete_cursor = connection.execute(
            f"DELETE FROM opshop_locations WHERE opshop_id IN ({placeholders})",
            duplicate_ids,
        )
        if delete_cursor.rowcount != len(duplicate_ids):
            raise ValueError("Not every selected duplicate location was deleted")

        foreign_key_rows = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        if foreign_key_rows:
            raise ValueError(f"foreign_key_check failed: {foreign_key_rows}")
        integrity_rows = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        if integrity_rows != ["ok"]:
            raise ValueError(f"integrity_check failed: {integrity_rows}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = {
        **plan,
        "mode": "apply",
        "backup_path": str(backup_path),
        "applied": True,
        "rows_updated": {
            "opshop_pickup_schedules": schedule_cursor.rowcount,
            "opshop_pickup_tasks": task_cursor.rowcount,
        },
        "locations_deleted": delete_cursor.rowcount,
        "integrity_check": integrity_rows,
        "foreign_key_check": foreign_key_rows,
    }
    record_maintenance_event(
        action="DUPLICATE_OPSHOP_LOCATION_REPAIR_COMPLETED",
        result="SUCCESS",
        workspace="OPSHOP",
        actor=resolve_maintenance_actor(actor),
        entity_type="OPSHOP_LOCATION",
        entity_id=canonical_opshop_id,
        summary=(
            "Duplicate OP SHOP physical location repair completed: "
            f"{len(duplicate_ids)} duplicate location(s) consolidated."
        ),
        metadata={
            "mode": "apply",
            "database_filename": safe_basename(path),
            "backup_filename": safe_basename(backup_path),
            "canonical_opshop_id": canonical_opshop_id,
            "duplicate_location_count": len(duplicate_ids),
            "schedules_migrated": schedule_cursor.rowcount,
            "tasks_migrated": task_cursor.rowcount,
            "locations_deleted": delete_cursor.rowcount,
        },
        logbook_dir=logbook_dir,
    )
    return result


def backup_database(db_path):
    """Create and verify a SQLite backup beside the target database."""

    path = Path(db_path)
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = (
        backup_dir
        / f"manual_dispatch_before_regular_opshop_duplicate_repair_{timestamp}.sqlite3"
    )
    source = sqlite3.connect(path)
    try:
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    with _connect_read_only(backup_path) as check:
        integrity = [row[0] for row in check.execute("PRAGMA integrity_check")]
        foreign_keys = [tuple(row) for row in check.execute("PRAGMA foreign_key_check")]
    if integrity != ["ok"] or foreign_keys:
        raise ValueError(
            f"Backup verification failed: integrity={integrity}, foreign_keys={foreign_keys}"
        )
    return backup_path


def format_report(report):
    lines = [
        "Duplicate OP SHOP Location Repair",
        f"Database: {report['db_path']}",
        f"Mode: {report['mode']}",
    ]
    if "duplicate_group_count" in report:
        lines.append(f"Duplicate groups: {report['duplicate_group_count']}")
        for group in report["groups"]:
            lines.extend(_format_group(group))
        return "\n".join(lines)

    lines.extend(
        [
            f"Normalized key: {report.get('normalized_key')}",
            f"Canonical opshop_id: {report['canonical_opshop_id']}",
            "Duplicate opshop_id(s): "
            + ", ".join(report["requested_duplicate_opshop_ids"]),
            f"Already repaired: {'yes' if report['already_repaired'] else 'no'}",
            f"Can apply: {'yes' if report['can_apply'] else 'no'}",
            f"Schedules affected: {report['schedules_affected']}",
            f"Tasks affected: {report['tasks_affected']}",
            f"Assignments preserved: {report['assignments_preserved']}",
            f"History snapshots preserved: {report['history_snapshots_preserved']}",
            f"Rows to delete: {report['locations_to_delete']}",
        ]
    )
    if report["conflicts"]:
        lines.append("Conflicts:")
        lines.extend(f"  - {conflict}" for conflict in report["conflicts"])
    else:
        lines.append("Conflicts: none")
    if report.get("backup_path"):
        lines.append(f"Backup: {report['backup_path']}")
    if report.get("rows_updated"):
        for table, count in report["rows_updated"].items():
            lines.append(f"Updated {table}: {count}")
        lines.append(f"Deleted opshop_locations: {report['locations_deleted']}")
    return "\n".join(lines)


def _build_repair_plan(connection, path, canonical_opshop_id, duplicate_opshop_ids):
    canonical_id = str(canonical_opshop_id or "").strip()
    requested_duplicates = sorted(
        {
            str(value or "").strip()
            for value in duplicate_opshop_ids or []
            if str(value or "").strip()
        }
    )
    if not canonical_id:
        raise ValueError("canonical_opshop_id is required")
    if not requested_duplicates:
        raise ValueError("At least one duplicate opshop_id is required")
    if canonical_id in requested_duplicates:
        raise ValueError("Canonical opshop_id cannot also be a duplicate opshop_id")

    selected_ids = [canonical_id, *requested_duplicates]
    rows = connection.execute(
        "SELECT * FROM opshop_locations "
        f"WHERE opshop_id IN ({','.join('?' for _ in selected_ids)})",
        selected_ids,
    ).fetchall()
    by_id = {row["opshop_id"]: dict(row) for row in rows}
    if canonical_id not in by_id:
        raise ValueError(f"Canonical OP SHOP location does not exist: {canonical_id}")

    existing_duplicates = [value for value in requested_duplicates if value in by_id]
    missing_duplicates = [value for value in requested_duplicates if value not in by_id]
    canonical_key = _location_key(by_id[canonical_id])
    conflicts = []
    for duplicate_id in existing_duplicates:
        duplicate_key = _location_key(by_id[duplicate_id])
        if duplicate_key != canonical_key:
            conflicts.append(
                f"{duplicate_id} has normalized key {duplicate_key!r}, expected {canonical_key!r}"
            )

    schedule_rows = connection.execute(
        "SELECT * FROM opshop_pickup_schedules "
        f"WHERE opshop_id IN ({','.join('?' for _ in selected_ids)}) "
        "ORDER BY run_day, run_type, pickup_category, schedule_id",
        selected_ids,
    ).fetchall()
    slots = defaultdict(list)
    for row in schedule_rows:
        slots[
            (
                row["run_day"] or "",
                row["run_type"] or "",
                row["pickup_category"] or "NORMAL",
            )
        ].append(dict(row))
    for slot, schedules in slots.items():
        location_ids = {schedule["opshop_id"] for schedule in schedules}
        if len(location_ids) > 1:
            conflicts.append(
                "Schedule slot conflict "
                f"{slot}: "
                + ", ".join(schedule["schedule_id"] for schedule in schedules)
            )

    schedule_ids = [row["schedule_id"] for row in schedule_rows]
    if schedule_ids:
        task_duplicates = connection.execute(
            "SELECT schedule_id, pickup_date, COUNT(*) AS count "
            "FROM opshop_pickup_tasks "
            f"WHERE schedule_id IN ({','.join('?' for _ in schedule_ids)}) "
            "GROUP BY schedule_id, pickup_date HAVING COUNT(*) > 1",
            schedule_ids,
        ).fetchall()
        for row in task_duplicates:
            conflicts.append(
                "Duplicate task identity for schedule/date "
                f"{row['schedule_id']} {row['pickup_date']}: {row['count']} rows"
            )

    affected_tasks = []
    if existing_duplicates:
        affected_tasks = connection.execute(
            "SELECT pickup_task_id FROM opshop_pickup_tasks "
            f"WHERE opshop_id IN ({','.join('?' for _ in existing_duplicates)})",
            existing_duplicates,
        ).fetchall()
    task_ids = [row["pickup_task_id"] for row in affected_tasks]
    assignments = _count_task_references(
        connection,
        "manual_dispatch_assignments",
        "task_id",
        task_ids,
        extra_where="task_type = 'OPSHOP_PICKUP'",
    )
    collection_snapshots = _count_task_references(
        connection,
        "opshop_pickup_collection_rows",
        "pickup_task_id_snapshot",
        task_ids,
    )
    final_snapshots = _count_task_references(
        connection,
        "final_trip_summary_opshop_pickup_rows",
        "pickup_task_id_snapshot",
        task_ids,
    )

    unknown_references = _unknown_direct_opshop_references(
        connection,
        existing_duplicates,
    )
    if unknown_references:
        conflicts.append(
            "Unhandled direct opshop_id references: "
            + json.dumps(unknown_references, sort_keys=True)
        )

    return {
        "mode": "dry-run",
        "db_path": str(path),
        "normalized_key": canonical_key,
        "canonical_opshop_id": canonical_id,
        "requested_duplicate_opshop_ids": requested_duplicates,
        "existing_duplicate_opshop_ids": existing_duplicates,
        "missing_duplicate_opshop_ids": missing_duplicates,
        "already_repaired": not existing_duplicates,
        "can_apply": not conflicts,
        "locations": [by_id[value] for value in selected_ids if value in by_id],
        "schedules": [dict(row) for row in schedule_rows],
        "schedules_affected": sum(
            1 for row in schedule_rows if row["opshop_id"] in existing_duplicates
        ),
        "tasks_affected": len(affected_tasks),
        "assignments_preserved": assignments,
        "history_snapshots_preserved": collection_snapshots + final_snapshots,
        "collection_snapshots_preserved": collection_snapshots,
        "final_snapshots_preserved": final_snapshots,
        "locations_to_delete": len(existing_duplicates),
        "rows_to_update": {
            "opshop_pickup_schedules": sum(
                1 for row in schedule_rows if row["opshop_id"] in existing_duplicates
            ),
            "opshop_pickup_tasks": len(affected_tasks),
        },
        "conflicts": conflicts,
    }


def _duplicate_groups(connection):
    groups = defaultdict(list)
    for row in connection.execute("SELECT * FROM opshop_locations ORDER BY opshop_id"):
        groups[_location_key(row)].append(dict(row))
    return {key: rows for key, rows in groups.items() if len(rows) > 1}


def _describe_group(connection, key, locations):
    ids = [location["opshop_id"] for location in locations]
    schedules = connection.execute(
        "SELECT * FROM opshop_pickup_schedules "
        f"WHERE opshop_id IN ({','.join('?' for _ in ids)}) "
        "ORDER BY opshop_id, run_day, run_type, schedule_id",
        ids,
    ).fetchall()
    task_counts = {
        opshop_id: connection.execute(
            "SELECT COUNT(*) FROM opshop_pickup_tasks WHERE opshop_id = ?",
            (opshop_id,),
        ).fetchone()[0]
        for opshop_id in ids
    }
    assignment_counts = {}
    snapshot_counts = {}
    for opshop_id in ids:
        task_ids = [
            row[0]
            for row in connection.execute(
                "SELECT pickup_task_id FROM opshop_pickup_tasks WHERE opshop_id = ?",
                (opshop_id,),
            )
        ]
        assignment_counts[opshop_id] = _count_task_references(
            connection,
            "manual_dispatch_assignments",
            "task_id",
            task_ids,
            extra_where="task_type = 'OPSHOP_PICKUP'",
        )
        snapshot_counts[opshop_id] = _count_task_references(
            connection,
            "opshop_pickup_collection_rows",
            "pickup_task_id_snapshot",
            task_ids,
        ) + _count_task_references(
            connection,
            "final_trip_summary_opshop_pickup_rows",
            "pickup_task_id_snapshot",
            task_ids,
        )
    return {
        "normalized_key": key,
        "locations": locations,
        "schedules": [dict(row) for row in schedules],
        "task_counts": task_counts,
        "assignment_counts": assignment_counts,
        "immutable_snapshot_counts": snapshot_counts,
    }


def _format_group(group):
    lines = ["", f"Normalized key: {group['normalized_key']}"]
    for location in group["locations"]:
        opshop_id = location["opshop_id"]
        lines.append(
            "  "
            f"{opshop_id}: {location['name']} | {location['suburb']} | "
            f"{location['street_address']} | active={location['is_active']} | "
            f"tasks={group['task_counts'][opshop_id]} | "
            f"assignments={group['assignment_counts'][opshop_id]} | "
            f"immutable_snapshots={group['immutable_snapshot_counts'][opshop_id]}"
        )
    for schedule in group["schedules"]:
        lines.append(
            "    schedule "
            f"{schedule['schedule_id']}: {schedule['opshop_id']} "
            f"{schedule['run_day']} {schedule['run_type']} "
            f"{schedule['pickup_category']} active={schedule['active_flag']}"
        )
    return lines


def _location_key(row):
    return location_key_from_values(row["name"], row["suburb"], row["street_address"])


def _connect_read_only(path):
    connection = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_columns(connection, table):
    return [row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _count_task_references(connection, table, column, task_ids, extra_where=None):
    if not task_ids:
        return 0
    where = [f'"{column}" IN ({",".join("?" for _ in task_ids)})']
    if extra_where:
        where.append(extra_where)
    return connection.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE ' + " AND ".join(where),
        task_ids,
    ).fetchone()[0]


def _unknown_direct_opshop_references(connection, duplicate_ids):
    if not duplicate_ids:
        return {}
    allowed = {"opshop_locations", "opshop_pickup_schedules", "opshop_pickup_tasks"}
    references = {}
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    for table in tables:
        if table in allowed or "opshop_id" not in _table_columns(connection, table):
            continue
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table}" '
            f'WHERE opshop_id IN ({",".join("?" for _ in duplicate_ids)})',
            duplicate_ids,
        ).fetchone()[0]
        if count:
            references[table] = count
    return references


def _remaining_opshop_references(connection, duplicate_ids):
    references = _unknown_direct_opshop_references(connection, duplicate_ids)
    for table in ("opshop_pickup_schedules", "opshop_pickup_tasks"):
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table}" '
            f'WHERE opshop_id IN ({",".join("?" for _ in duplicate_ids)})',
            duplicate_ids,
        ).fetchone()[0]
        if count:
            references[table] = count
    return references


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Audit or safely consolidate duplicate normalized OP SHOP physical locations. "
            "Defaults to read-only dry-run."
        )
    )
    parser.add_argument(
        "--db-path",
        help="SQLite database path. Defaults to MANUAL_DISPATCH_DB_PATH.",
    )
    parser.add_argument(
        "--canonical-opshop-id",
        help="Canonical location to retain for an explicit repair plan.",
    )
    parser.add_argument(
        "--opshop-id",
        action="append",
        dest="duplicate_opshop_ids",
        help="Duplicate location to migrate/delete; repeat for multiple IDs.",
    )
    parser.add_argument("--output-json", help="Optional path for the full JSON report.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the explicit repair. Without this flag the tool is read-only.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive confirmation for --apply.",
    )
    add_maintenance_logbook_arguments(parser)
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    db_path = args.db_path or os.environ.get("MANUAL_DISPATCH_DB_PATH")
    if not db_path:
        print("Database path is required.", file=sys.stderr)
        return 2
    path = Path(db_path)
    if not path.is_file():
        print(f"Database path is missing or unreadable: {path}", file=sys.stderr)
        return 2

    explicit_plan = bool(args.canonical_opshop_id or args.duplicate_opshop_ids)
    if explicit_plan and not (args.canonical_opshop_id and args.duplicate_opshop_ids):
        print(
            "Both --canonical-opshop-id and at least one --opshop-id are required.",
            file=sys.stderr,
        )
        return 2
    if args.apply and not explicit_plan:
        print("--apply requires an explicit canonical and duplicate selection.", file=sys.stderr)
        return 2
    if args.apply and not args.yes:
        confirmation = input("Type APPLY to modify the database: ")
        if confirmation != "APPLY":
            print("Apply cancelled.", file=sys.stderr)
            return 2

    try:
        if explicit_plan:
            report = (
                apply_location_repair(
                    path,
                    args.canonical_opshop_id,
                    args.duplicate_opshop_ids,
                    yes=True,
                    actor=args.actor,
                    logbook_dir=args.logbook_dir,
                )
                if args.apply
                else plan_location_repair(
                    path,
                    args.canonical_opshop_id,
                    args.duplicate_opshop_ids,
                )
            )
        else:
            report = audit_duplicate_locations(path)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Could not repair duplicate OP SHOP locations: {error}", file=sys.stderr)
        return 2

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(format_report(report))
    if "conflicts" in report and report["conflicts"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
