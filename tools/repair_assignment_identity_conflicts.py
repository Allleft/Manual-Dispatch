"""Plan and repair duplicate OP SHOP assignment identities safely.

Dry-run is the default and never opens the target database with SQLite. Apply
requires ``--apply``, ``--yes``, and the exact canonical decision file emitted
by dry-run. H5 indexes remain the responsibility of
``tools/migrate_database_invariants.py``.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.manual_dispatch.logbook_file_service import (  # noqa: E402
    MELBOURNE_TIMEZONE,
)
from tools.maintenance_logbook import (  # noqa: E402
    add_maintenance_logbook_arguments,
    record_maintenance_event,
    resolve_maintenance_actor,
    safe_basename,
)


PLAN_SCHEMA_VERSION = 1
ASSIGNMENT_TABLE = "manual_dispatch_assignments"
TASK_TABLE = "opshop_pickup_tasks"
DRIVER_TABLE = "manual_drivers"
REQUIRED_TABLES = {ASSIGNMENT_TABLE, TASK_TABLE, DRIVER_TABLE}
ASSIGNED_STATUS = "ASSIGNED"
NON_ASSIGNED_STATUSES = {"ACTIVE", "CANCELLED", "COMPLETED"}
ALLOWED_TASK_STATUSES = {ASSIGNED_STATUS, *NON_ASSIGNED_STATUSES}
ALLOWED_TRIPS = {"trip1", "trip2"}
REPAIR_ACTION = "ASSIGNMENT_IDENTITY_REPAIR_COMPLETED"
REPAIR_ENTITY_TYPE = "DATABASE_INVARIANT_REPAIR"


class AssignmentRepairBlockedError(ValueError):
    """Raised when repair cannot proceed without operator intervention."""

    def __init__(self, message: str, report: dict[str, Any] | None = None):
        super().__init__(message)
        self.report = report


def inspect_assignment_identity_conflicts(
    db_path: str | Path,
    *,
    created_at: str | None = None,
    repair_timestamp: str | None = None,
    git_head: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic repair plan without opening the target DB."""
    path = _validated_database_path(db_path)
    created = created_at or _melbourne_timestamp()
    repair_time = repair_timestamp or created
    raw_sha256 = _sha256_file(path)

    with _read_only_database_snapshot(path) as snapshot_path:
        with _read_only_connection(snapshot_path) as connection:
            plan = _build_plan(
                connection,
                database_filename=path.name,
                database_sha256=raw_sha256,
                created_at=created,
                repair_timestamp=repair_time,
                git_head=git_head or _git_head(),
            )
    _seal_plan(plan)
    return plan


def write_repair_plan(plan: dict[str, Any], plan_out: str | Path) -> tuple[Path, str]:
    """Write the canonical JSON decision file and return its file SHA-256."""
    path = Path(plan_out).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_plan_bytes(plan)
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest().upper()


def load_repair_plan(decision_file: str | Path) -> tuple[dict[str, Any], str]:
    """Load and validate the exact canonical plan emitted by this tool."""
    path = Path(decision_file).resolve()
    if not path.is_file():
        raise AssignmentRepairBlockedError("The decision file does not exist.")
    raw = path.read_bytes()
    try:
        plan = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssignmentRepairBlockedError("The decision file is not valid JSON.") from error
    _validate_plan_schema(plan)
    if raw != _canonical_plan_bytes(plan):
        raise AssignmentRepairBlockedError(
            "The decision file is not the exact canonical plan emitted by dry-run."
        )
    return plan, hashlib.sha256(raw).hexdigest().upper()


def apply_assignment_identity_repair(
    db_path: str | Path,
    *,
    decision_file: str | Path,
    apply: bool = False,
    yes: bool = False,
    backup_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Apply an exact, unblocked repair plan in one verified transaction."""
    if not apply or not yes or not decision_file:
        raise AssignmentRepairBlockedError(
            "Apply requires --apply, --yes, and --decision-file."
        )

    path = _validated_database_path(db_path)
    plan, decision_file_sha256 = load_repair_plan(decision_file)
    _raise_for_plan_blockers(plan)
    if plan["database_filename"] != path.name:
        raise AssignmentRepairBlockedError(
            "The decision file targets a different database filename."
        )

    with _read_only_database_snapshot(path) as snapshot_path:
        with _read_only_connection(snapshot_path) as connection:
            if _plan_is_already_applied(connection, plan):
                return _already_repaired_report(path, plan, decision_file_sha256)
            current = _build_plan(
                connection,
                database_filename=path.name,
                database_sha256=_sha256_file(path),
                created_at=plan["created_at"],
                repair_timestamp=plan["repair_timestamp"],
                git_head=plan["git_head"],
            )
            _validate_plan_matches_current(plan, current)

    backup_path = create_verified_repair_backup(path, backup_dir)
    rows_deleted = 0
    rows_updated = 0
    try:
        with contextlib.closing(
            sqlite3.connect(path, isolation_level=None)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                locked = _build_plan(
                    connection,
                    database_filename=path.name,
                    database_sha256=_sha256_file(path),
                    created_at=plan["created_at"],
                    repair_timestamp=plan["repair_timestamp"],
                    git_head=plan["git_head"],
                )
                _validate_plan_matches_current(plan, locked)
                for index, group in enumerate(plan["groups"]):
                    updated, deleted = _apply_group(connection, group)
                    rows_updated += updated
                    rows_deleted += deleted
                    _after_group_applied(connection, group, index)

                duplicate_groups = _duplicate_identity_rows(connection)
                if duplicate_groups:
                    raise AssignmentRepairBlockedError(
                        "Duplicate assignment identities remain after repair."
                    )
                foreign_key_violations = _foreign_key_violation_count(connection)
                if foreign_key_violations:
                    raise AssignmentRepairBlockedError(
                        "Foreign-key violations remain after repair."
                    )
                integrity = _integrity_result(connection)
                if integrity.lower() != "ok":
                    raise AssignmentRepairBlockedError(
                        "Database integrity failed after repair."
                    )
                if rows_deleted != plan["expected_rows_deleted"]:
                    raise AssignmentRepairBlockedError(
                        "Actual deleted-row count differs from the decision file."
                    )
                if rows_updated != plan["expected_rows_updated"]:
                    raise AssignmentRepairBlockedError(
                        "Actual updated-row count differs from the decision file."
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    except Exception:
        raise

    final_plan = inspect_assignment_identity_conflicts(path)
    if final_plan["duplicate_group_count"] != 0:
        raise AssignmentRepairBlockedError(
            "Post-commit audit found duplicate assignment identities."
        )
    if final_plan["integrity_check"].lower() != "ok":
        raise AssignmentRepairBlockedError("Post-commit integrity audit failed.")
    if final_plan["foreign_key_violation_count"]:
        raise AssignmentRepairBlockedError("Post-commit foreign-key audit failed.")

    return {
        "mode": "apply",
        "already_repaired": False,
        "database_filename": path.name,
        "backup_path": str(backup_path),
        "backup_filename": backup_path.name,
        "repair_plan_sha256": decision_file_sha256,
        "duplicate_groups_repaired": plan["duplicate_group_count"],
        "assigned_groups_merged": plan["assigned_groups"],
        "non_active_groups_cleared": plan["non_assigned_groups"],
        "rows_deleted": rows_deleted,
        "rows_updated": rows_updated,
        "rows_inserted": 0,
        "duplicate_group_count": final_plan["duplicate_group_count"],
        "integrity_check": final_plan["integrity_check"],
        "foreign_key_violation_count": final_plan["foreign_key_violation_count"],
    }


def create_verified_repair_backup(
    db_path: str | Path,
    backup_dir: str | Path | None = None,
) -> Path:
    """Create a non-overwriting SQLite Backup API copy and verify it."""
    path = _validated_database_path(db_path)
    destination_dir = Path(backup_dir) if backup_dir else path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(MELBOURNE_TIMEZONE).strftime("%Y%m%d_%H%M%S")
    backup_path = _next_available_path(
        destination_dir.resolve(),
        f"{path.stem}_before_assignment_identity_repair_{timestamp}",
    )
    with contextlib.closing(sqlite3.connect(path)) as source:
        with contextlib.closing(sqlite3.connect(backup_path)) as destination:
            source.backup(destination)
    with _read_only_connection(backup_path) as connection:
        integrity = _integrity_result(connection)
        foreign_key_violations = _foreign_key_violation_count(connection)
    if integrity.lower() != "ok" or foreign_key_violations:
        raise AssignmentRepairBlockedError(
            "The pre-repair backup did not pass integrity validation."
        )
    return backup_path


def format_console_report(report: dict[str, Any]) -> str:
    """Format aggregate-only output; never print Task IDs or raw rows."""
    if report.get("mode") == "apply":
        lines = [
            "Manual Dispatch Assignment Identity Repair",
            "Mode: apply",
            f"Already repaired: {str(bool(report['already_repaired'])).lower()}",
            f"Duplicate groups repaired: {report['duplicate_groups_repaired']}",
            f"Assigned groups merged: {report['assigned_groups_merged']}",
            f"Non-active groups cleared: {report['non_active_groups_cleared']}",
            f"Rows deleted: {report['rows_deleted']}",
            f"Rows updated: {report['rows_updated']}",
            f"Rows inserted: {report['rows_inserted']}",
            f"Duplicate groups after repair: {report['duplicate_group_count']}",
            f"Integrity: {report['integrity_check']}",
            f"Foreign-key violations: {report['foreign_key_violation_count']}",
            f"Backup: {report.get('backup_filename') or 'not created (already repaired)'}",
            f"Repair plan SHA-256: {report['repair_plan_sha256']}",
        ]
        return "\n".join(lines)

    lines = [
        "Manual Dispatch Assignment Identity Repair",
        "Mode: dry-run",
        f"Database filename: {report['database_filename']}",
        f"Database SHA-256: {report['database_sha256']}",
        f"Database logical SHA-256: {report['database_logical_sha256']}",
        f"Assignment logical SHA-256: {report['assignment_table_logical_sha256']}",
        f"Integrity: {report['integrity_check']}",
        f"Foreign-key violations: {report['foreign_key_violation_count']}",
        f"Duplicate groups: {report['duplicate_group_count']}",
        f"Rows involved: {report['rows_in_duplicate_groups']}",
        f"ASSIGNED groups with complete current Task state: {report['assigned_groups']}",
        "ASSIGNED groups requiring driver/trip normalization: "
        f"{report['assigned_groups_requiring_driver_trip_normalization']}",
        "ASSIGNED groups already matching current Task state: "
        f"{report['assigned_groups_already_matching_current_task_state']}",
        f"Non-active groups: {report['non_assigned_groups']}",
        f"Blocked groups: {report['blocked_groups']}",
        f"Global blockers: {report['global_blocker_count']}",
        f"Expected rows deleted: {report['expected_rows_deleted']}",
        f"Expected rows updated: {report['expected_rows_updated']}",
        f"Repair plan payload SHA-256: {report['plan_payload_sha256']}",
    ]
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply:
        if not args.yes or not args.decision_file:
            print(
                "Repair blocked: apply requires --apply, --yes, and --decision-file.",
                file=sys.stderr,
            )
            return 2
        if args.plan_out:
            print("Repair blocked: --plan-out is dry-run only.", file=sys.stderr)
            return 2
        try:
            report = apply_assignment_identity_repair(
                args.db_path,
                decision_file=args.decision_file,
                apply=True,
                yes=True,
                backup_dir=args.backup_dir,
            )
        except (AssignmentRepairBlockedError, OSError, sqlite3.Error) as error:
            print(f"Repair blocked: {error}", file=sys.stderr)
            return 2
        print(format_console_report(report))
        if not report["already_repaired"]:
            recorded = _record_repair_event(
                report,
                actor=resolve_maintenance_actor(args.actor),
                logbook_dir=args.logbook_dir,
            )
            if not recorded:
                print("Repair completed but maintenance event recording failed.", file=sys.stderr)
                return 2
        return 0

    if args.yes or args.decision_file:
        print(
            "Repair blocked: --yes and --decision-file require --apply.",
            file=sys.stderr,
        )
        return 2
    try:
        plan = inspect_assignment_identity_conflicts(args.db_path)
        plan_sha256 = hashlib.sha256(_canonical_plan_bytes(plan)).hexdigest().upper()
        if args.plan_out:
            _, plan_sha256 = write_repair_plan(plan, args.plan_out)
    except (AssignmentRepairBlockedError, OSError, sqlite3.Error) as error:
        print(f"Repair blocked: {error}", file=sys.stderr)
        return 2
    print(format_console_report(plan))
    print(f"Repair plan file SHA-256: {plan_sha256}")
    if plan["blocked_groups"] or plan["global_blocker_count"]:
        return 2
    return 0


def _build_plan(
    connection: sqlite3.Connection,
    *,
    database_filename: str,
    database_sha256: str,
    created_at: str,
    repair_timestamp: str,
    git_head: str,
) -> dict[str, Any]:
    tables = _table_names(connection)
    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        raise AssignmentRepairBlockedError(
            "Required Assignment repair schema is missing."
        )

    integrity = _integrity_result(connection)
    foreign_key_violations = _foreign_key_violation_count(connection)
    external_references = _assignment_external_references(connection, tables)
    global_blockers: list[str] = []
    if integrity.lower() != "ok":
        global_blockers.append("INTEGRITY_CHECK_FAILED")
    if foreign_key_violations:
        global_blockers.append("FOREIGN_KEY_VIOLATIONS")
    if external_references:
        global_blockers.append("ASSIGNMENT_ID_EXTERNAL_REFERENCES")

    groups: list[dict[str, Any]] = []
    for identity in _duplicate_identity_rows(connection):
        rows = connection.execute(
            """
            SELECT *
            FROM manual_dispatch_assignments
            WHERE task_type = ? AND task_id = ?
            ORDER BY assignment_id
            """,
            (identity["task_type"], identity["task_id"]),
        ).fetchall()
        groups.append(
            _plan_group(
                connection,
                identity["task_type"],
                identity["task_id"],
                rows,
                repair_timestamp,
                force_block=bool(global_blockers),
            )
        )

    assigned = [group for group in groups if group["decision"] == "MERGE_TO_CURRENT_TASK_STATE"]
    non_assigned = [
        group
        for group in groups
        if group["decision"] == "DELETE_ALL_NON_ACTIVE_ASSIGNMENTS"
    ]
    blocked = [group for group in groups if group["decision"] == "BLOCKED"]
    blocked_categories: dict[str, int] = {}
    for group in blocked:
        category = group["blocked_category"]
        blocked_categories[category] = blocked_categories.get(category, 0) + 1

    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "mode": "dry-run",
        "database_filename": database_filename,
        "database_sha256": database_sha256,
        "database_logical_sha256": _database_logical_sha256(connection),
        "assignment_table_logical_sha256": _table_logical_sha256(
            connection, ASSIGNMENT_TABLE
        ),
        "created_at": created_at,
        "repair_timestamp": repair_timestamp,
        "git_head": git_head,
        "integrity_check": integrity,
        "foreign_key_violation_count": foreign_key_violations,
        "assignment_external_reference_count": len(external_references),
        "global_blocker_count": len(global_blockers),
        "global_blocker_categories": sorted(global_blockers),
        "duplicate_group_count": len(groups),
        "rows_in_duplicate_groups": sum(group["candidate_row_count"] for group in groups),
        "expected_rows_deleted": sum(len(group["delete_assignment_ids"]) for group in groups),
        "expected_rows_updated": sum(
            1 for group in assigned if group["canonical_row_update_required"]
        ),
        "expected_rows_inserted": 0,
        "assigned_groups": len(assigned),
        "assigned_groups_requiring_driver_trip_normalization": sum(
            1 for group in assigned if group["driver_trip_normalization_required"]
        ),
        "assigned_groups_already_matching_current_task_state": sum(
            1 for group in assigned if not group["driver_trip_normalization_required"]
        ),
        "non_assigned_groups": len(non_assigned),
        "blocked_groups": len(blocked),
        "blocked_group_categories": blocked_categories,
        "already_repaired": len(groups) == 0 and not global_blockers,
        "groups": groups,
    }
    return plan


def _plan_group(
    connection: sqlite3.Connection,
    task_type: str,
    task_id: str,
    rows: list[sqlite3.Row],
    repair_timestamp: str,
    *,
    force_block: bool,
) -> dict[str, Any]:
    row_dicts = [_row_dict(row) for row in rows]
    candidate_hashes = [_object_sha256(row) for row in row_dicts]
    base = {
        "task_type": task_type,
        "task_id": task_id,
        "task_row_sha256": None,
        "assignment_group_sha256": _object_sha256(row_dicts),
        "task_status": None,
        "task_dispatch_date": None,
        "task_driver_id": None,
        "task_trip_no": None,
        "decision": "BLOCKED",
        "decision_reason": "The group cannot be repaired automatically.",
        "blocked_category": None,
        "canonical_assignment_id": None,
        "canonical_dispatch_date": None,
        "canonical_assigned_at": None,
        "canonical_updated_at": None,
        "canonical_driver_id": None,
        "canonical_trip_no": None,
        "canonical_row_update_required": False,
        "driver_trip_normalization_required": False,
        "delete_assignment_ids": [],
        "candidate_row_count": len(rows),
        "candidate_row_sha256": candidate_hashes,
    }
    if force_block:
        return _block_group(base, "GLOBAL_PREFLIGHT_BLOCKER")
    if task_type != "OPSHOP_PICKUP":
        return _block_group(base, "UNSUPPORTED_TASK_TYPE")

    task_rows = connection.execute(
        "SELECT * FROM opshop_pickup_tasks WHERE pickup_task_id = ?",
        (task_id,),
    ).fetchall()
    if len(task_rows) != 1:
        return _block_group(base, "MISSING_OR_DUPLICATE_TASK")
    task = _row_dict(task_rows[0])
    base.update(
        {
            "task_row_sha256": _object_sha256(task),
            "task_status": task.get("status"),
            "task_dispatch_date": task.get("dispatch_date"),
            "task_driver_id": task.get("driver_id"),
            "task_trip_no": task.get("trip_no"),
        }
    )

    if task.get("status") not in ALLOWED_TASK_STATUSES:
        return _block_group(base, "INVALID_TASK_STATUS")
    parsed_rows: list[
        tuple[date, datetime | None, datetime | None, dict[str, Any]]
    ] = []
    seen_dates: set[str] = set()
    for row in row_dicts:
        parsed_date = _parse_iso_date(row.get("dispatch_date"))
        if parsed_date is None:
            return _block_group(base, "INVALID_ASSIGNMENT_DISPATCH_DATE")
        if row["dispatch_date"] in seen_dates:
            return _block_group(base, "DUPLICATE_ASSIGNMENT_DISPATCH_DATE")
        seen_dates.add(row["dispatch_date"])
        assigned_at = _parse_iso_timestamp(row.get("assigned_at"))
        if row.get("assigned_at") not in (None, "") and assigned_at is None:
            return _block_group(base, "INVALID_ASSIGNMENT_ASSIGNED_AT")
        updated_at = _parse_iso_timestamp(row.get("updated_at"))
        if row.get("updated_at") not in (None, "") and updated_at is None:
            return _block_group(base, "INVALID_ASSIGNMENT_UPDATED_AT")
        parsed_rows.append((parsed_date, assigned_at, updated_at, row))

    assigned_awareness = {
        _timestamp_is_aware(assigned_at)
        for _, assigned_at, _, _ in parsed_rows
        if assigned_at is not None
    }
    updated_awareness = {
        _timestamp_is_aware(updated_at)
        for _, _, updated_at, _ in parsed_rows
        if updated_at is not None
    }
    if len(assigned_awareness) > 1 or len(updated_awareness) > 1:
        return _block_group(base, "MIXED_ASSIGNMENT_TIMESTAMP_TIMEZONES")

    canonical = min(
        parsed_rows,
        key=lambda item: (
            item[0],
            item[1] is None,
            _timestamp_order_key(item[1]) if item[1] is not None else datetime.max,
            str(item[3]["assignment_id"]),
        ),
    )[3]
    assigned_values = [
        (assigned_at, row["assigned_at"])
        for _, assigned_at, _, row in parsed_rows
        if assigned_at is not None
    ]
    updated_values = [
        (updated_at, row["updated_at"])
        for _, _, updated_at, row in parsed_rows
        if updated_at is not None
    ]
    merged_assigned_at = (
        min(assigned_values, key=lambda item: _timestamp_order_key(item[0]))[1]
        if assigned_values
        else canonical.get("assigned_at")
    )

    if task["status"] in NON_ASSIGNED_STATUSES:
        base.update(
            {
                "decision": "DELETE_ALL_NON_ACTIVE_ASSIGNMENTS",
                "decision_reason": "The current OP SHOP Task is not ASSIGNED.",
                "delete_assignment_ids": [row["assignment_id"] for row in row_dicts],
            }
        )
        return base

    if not str(task.get("driver_id") or "").strip():
        return _block_group(base, "ASSIGNED_TASK_MISSING_DRIVER")
    if task.get("trip_no") not in ALLOWED_TRIPS:
        return _block_group(base, "ASSIGNED_TASK_INVALID_TRIP")
    if _parse_iso_date(task.get("dispatch_date")) is None:
        return _block_group(base, "ASSIGNED_TASK_INVALID_DISPATCH_DATE")
    driver_exists = connection.execute(
        "SELECT 1 FROM manual_drivers WHERE driver_id = ? LIMIT 1",
        (task["driver_id"],),
    ).fetchone()
    if driver_exists is None:
        return _block_group(base, "ASSIGNED_TASK_DRIVER_NOT_FOUND")

    driver_trip_normalization = (
        canonical.get("driver_id") != task["driver_id"]
        or canonical.get("trip_no") != task["trip_no"]
    )
    if driver_trip_normalization:
        merged_updated_at = repair_timestamp
    elif updated_values:
        merged_updated_at = max(
            updated_values,
            key=lambda item: _timestamp_order_key(item[0]),
        )[1]
    else:
        merged_updated_at = canonical.get("updated_at")

    final_values = {
        "driver_id": task["driver_id"],
        "trip_no": task["trip_no"],
        "assigned_at": merged_assigned_at,
        "updated_at": merged_updated_at,
    }
    update_required = any(canonical.get(key) != value for key, value in final_values.items())
    base.update(
        {
            "decision": "MERGE_TO_CURRENT_TASK_STATE",
            "decision_reason": (
                "The canonical Assignment is aligned to the authoritative current "
                "OP SHOP Task while preserving the earliest source date."
            ),
            "canonical_assignment_id": canonical["assignment_id"],
            "canonical_dispatch_date": canonical["dispatch_date"],
            "canonical_assigned_at": merged_assigned_at,
            "canonical_updated_at": merged_updated_at,
            "canonical_driver_id": task["driver_id"],
            "canonical_trip_no": task["trip_no"],
            "canonical_row_update_required": update_required,
            "driver_trip_normalization_required": driver_trip_normalization,
            "delete_assignment_ids": [
                row["assignment_id"]
                for row in row_dicts
                if row["assignment_id"] != canonical["assignment_id"]
            ],
        }
    )
    return base


def _apply_group(connection: sqlite3.Connection, group: dict[str, Any]) -> tuple[int, int]:
    if group["decision"] == "BLOCKED":
        raise AssignmentRepairBlockedError("The decision file contains blocked groups.")
    rows_updated = 0
    if group["decision"] == "MERGE_TO_CURRENT_TASK_STATE":
        if group["canonical_row_update_required"]:
            cursor = connection.execute(
                """
                UPDATE manual_dispatch_assignments
                SET driver_id = ?, trip_no = ?, assigned_at = ?, updated_at = ?
                WHERE assignment_id = ?
                """,
                (
                    group["canonical_driver_id"],
                    group["canonical_trip_no"],
                    group["canonical_assigned_at"],
                    group["canonical_updated_at"],
                    group["canonical_assignment_id"],
                ),
            )
            if cursor.rowcount != 1:
                raise AssignmentRepairBlockedError(
                    "A canonical Assignment changed during apply."
                )
            rows_updated = 1
    rows_deleted = 0
    for assignment_id in group["delete_assignment_ids"]:
        cursor = connection.execute(
            "DELETE FROM manual_dispatch_assignments WHERE assignment_id = ?",
            (assignment_id,),
        )
        if cursor.rowcount != 1:
            raise AssignmentRepairBlockedError(
                "An Assignment candidate changed during apply."
            )
        rows_deleted += 1
    return rows_updated, rows_deleted


def _after_group_applied(_connection, _group, _index):
    """Test seam used to prove transaction rollback after a partial apply."""


def _block_group(group: dict[str, Any], category: str) -> dict[str, Any]:
    group["decision"] = "BLOCKED"
    group["blocked_category"] = category
    group["decision_reason"] = "Automatic repair stopped by a fail-closed rule."
    return group


def _validate_plan_matches_current(
    expected: dict[str, Any], current: dict[str, Any]
) -> None:
    comparisons = (
        "database_logical_sha256",
        "assignment_table_logical_sha256",
        "integrity_check",
        "foreign_key_violation_count",
        "assignment_external_reference_count",
        "global_blocker_count",
        "duplicate_group_count",
        "rows_in_duplicate_groups",
        "expected_rows_deleted",
        "expected_rows_updated",
        "assigned_groups",
        "non_assigned_groups",
        "blocked_groups",
        "groups",
    )
    if any(expected.get(key) != current.get(key) for key in comparisons):
        raise AssignmentRepairBlockedError(
            "The database no longer matches the exact repair decision file."
        )


def _plan_is_already_applied(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> bool:
    if _duplicate_identity_rows(connection):
        return False
    tables = _table_names(connection)
    if (
        _integrity_result(connection).lower() != "ok"
        or _foreign_key_violation_count(connection)
        or _assignment_external_references(connection, tables)
    ):
        return False
    if not plan["groups"]:
        return (
            _database_logical_sha256(connection)
            == plan["database_logical_sha256"]
            and _table_logical_sha256(connection, ASSIGNMENT_TABLE)
            == plan["assignment_table_logical_sha256"]
        )
    for group in plan["groups"]:
        task = connection.execute(
            "SELECT * FROM opshop_pickup_tasks WHERE pickup_task_id = ?",
            (group["task_id"],),
        ).fetchone()
        if task is None or _object_sha256(_row_dict(task)) != group["task_row_sha256"]:
            return False
        rows = connection.execute(
            """
            SELECT * FROM manual_dispatch_assignments
            WHERE task_type = ? AND task_id = ?
            ORDER BY assignment_id
            """,
            (group["task_type"], group["task_id"]),
        ).fetchall()
        if group["decision"] == "DELETE_ALL_NON_ACTIVE_ASSIGNMENTS":
            if rows:
                return False
            continue
        if group["decision"] != "MERGE_TO_CURRENT_TASK_STATE" or len(rows) != 1:
            return False
        row = _row_dict(rows[0])
        expected_values = {
            "assignment_id": group["canonical_assignment_id"],
            "dispatch_date": group["canonical_dispatch_date"],
            "task_type": group["task_type"],
            "task_id": group["task_id"],
            "driver_id": group["canonical_driver_id"],
            "trip_no": group["canonical_trip_no"],
            "assigned_at": group["canonical_assigned_at"],
            "updated_at": group["canonical_updated_at"],
        }
        if any(row.get(key) != value for key, value in expected_values.items()):
            return False
    return True


def _already_repaired_report(
    path: Path,
    plan: dict[str, Any],
    decision_file_sha256: str,
) -> dict[str, Any]:
    with _read_only_database_snapshot(path) as snapshot_path:
        with _read_only_connection(snapshot_path) as connection:
            integrity = _integrity_result(connection)
            foreign_keys = _foreign_key_violation_count(connection)
    return {
        "mode": "apply",
        "already_repaired": True,
        "database_filename": path.name,
        "backup_path": None,
        "backup_filename": None,
        "repair_plan_sha256": decision_file_sha256,
        "duplicate_groups_repaired": 0,
        "assigned_groups_merged": 0,
        "non_active_groups_cleared": 0,
        "rows_deleted": 0,
        "rows_updated": 0,
        "rows_inserted": 0,
        "duplicate_group_count": 0,
        "integrity_check": integrity,
        "foreign_key_violation_count": foreign_keys,
    }


def _raise_for_plan_blockers(plan: dict[str, Any]) -> None:
    if plan["blocked_groups"] or plan["global_blocker_count"]:
        raise AssignmentRepairBlockedError(
            "The decision file contains unresolved fail-closed blockers."
        )


def _record_repair_event(report, *, actor, logbook_dir) -> bool:
    metadata = {
        "mode": "apply",
        "database_filename": report["database_filename"],
        "backup_filename": report["backup_filename"],
        "duplicate_groups_repaired": report["duplicate_groups_repaired"],
        "assigned_groups_merged": report["assigned_groups_merged"],
        "non_active_groups_cleared": report["non_active_groups_cleared"],
        "rows_deleted": report["rows_deleted"],
        "rows_updated": report["rows_updated"],
        "repair_plan_sha256": report["repair_plan_sha256"],
        "integrity_check": report["integrity_check"],
        "foreign_key_violation_count": report["foreign_key_violation_count"],
    }
    return record_maintenance_event(
        action=REPAIR_ACTION,
        result="SUCCESS",
        workspace="SYSTEM",
        actor=actor,
        entity_type=REPAIR_ENTITY_TYPE,
        entity_id=safe_basename(report["database_filename"]),
        summary="Assignment identity conflicts were repaired successfully.",
        metadata=metadata,
        logbook_dir=logbook_dir,
    )


def _assignment_external_references(
    connection: sqlite3.Connection, tables: set[str]
) -> list[str]:
    references: set[str] = set()
    for table in sorted(tables):
        if table != ASSIGNMENT_TABLE:
            columns = connection.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            ).fetchall()
            if any(str(row["name"]).casefold() == "assignment_id" for row in columns):
                references.add(f"column:{table}")
        foreign_keys = connection.execute(
            f"PRAGMA foreign_key_list({_quote_identifier(table)})"
        ).fetchall()
        if any(str(row["table"]) == ASSIGNMENT_TABLE for row in foreign_keys):
            references.add(f"foreign-key:{table}")

    schema_rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE type IN ('trigger', 'view') AND sql IS NOT NULL
        """
    ).fetchall()
    for row in schema_rows:
        if ASSIGNMENT_TABLE.casefold() in str(row["sql"]).casefold():
            references.add(f"{row['type']}:{row['name']}")
    return sorted(references)


def _duplicate_identity_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT task_type, task_id, COUNT(*) AS duplicate_count
        FROM manual_dispatch_assignments
        GROUP BY task_type, task_id
        HAVING COUNT(*) > 1
        ORDER BY task_type, task_id
        """
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _database_logical_sha256(connection: sqlite3.Connection) -> str:
    objects = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    payload: list[dict[str, Any]] = []
    for row in objects:
        item = _row_dict(row)
        if row["type"] == "table":
            item["rows"] = _table_rows(connection, row["name"])
        payload.append(item)
    return _object_sha256(payload)


def _table_logical_sha256(connection: sqlite3.Connection, table: str) -> str:
    return _object_sha256(_table_rows(connection, table))


def _table_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = [_row_dict(row) for row in connection.execute(
        f"SELECT * FROM {_quote_identifier(table)}"
    ).fetchall()]
    return sorted(rows, key=_canonical_json)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _seal_plan(plan: dict[str, Any]) -> None:
    plan["plan_payload_sha256"] = _plan_payload_sha256(plan)


def _validate_plan_schema(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise AssignmentRepairBlockedError("The decision file root must be an object.")
    required = {
        "schema_version",
        "mode",
        "database_filename",
        "database_sha256",
        "database_logical_sha256",
        "assignment_table_logical_sha256",
        "created_at",
        "repair_timestamp",
        "git_head",
        "duplicate_group_count",
        "rows_in_duplicate_groups",
        "expected_rows_deleted",
        "expected_rows_updated",
        "assigned_groups",
        "non_assigned_groups",
        "blocked_groups",
        "global_blocker_count",
        "groups",
        "plan_payload_sha256",
    }
    if required - set(plan):
        raise AssignmentRepairBlockedError("The decision file schema is incomplete.")
    if plan["schema_version"] != PLAN_SCHEMA_VERSION or plan["mode"] != "dry-run":
        raise AssignmentRepairBlockedError("The decision file schema version is unsupported.")
    if not isinstance(plan["groups"], list):
        raise AssignmentRepairBlockedError("The decision file groups field is invalid.")
    if plan["duplicate_group_count"] != len(plan["groups"]):
        raise AssignmentRepairBlockedError("The decision file group count is invalid.")
    if plan["plan_payload_sha256"] != _plan_payload_sha256(plan):
        raise AssignmentRepairBlockedError("The decision file payload SHA-256 is invalid.")


def _plan_payload_sha256(plan: dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("plan_payload_sha256", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest().upper()


def _canonical_plan_bytes(plan: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            _json_value(plan),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _object_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest().upper()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _timestamp_is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _timestamp_order_key(value: datetime) -> datetime:
    if _timestamp_is_aware(value):
        return value.astimezone(MELBOURNE_TIMEZONE).replace(tzinfo=None)
    return value


def _integrity_result(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return str(row[0] if row else "no integrity result")


def _foreign_key_violation_count(connection: sqlite3.Connection) -> int:
    return len(connection.execute("PRAGMA foreign_key_check").fetchall())


@contextlib.contextmanager
def _read_only_database_snapshot(db_path: str | Path):
    source_path = Path(db_path).resolve()
    with tempfile.TemporaryDirectory(prefix="manual-dispatch-assignment-repair-") as temp_dir:
        snapshot_path = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, snapshot_path)
        wal_path = Path(f"{source_path}-wal")
        if wal_path.exists():
            shutil.copy2(wal_path, Path(f"{snapshot_path}-wal"))
        yield snapshot_path


@contextlib.contextmanager
def _read_only_connection(path: str | Path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def _validated_database_path(db_path: str | Path) -> Path:
    if not db_path:
        raise AssignmentRepairBlockedError("An explicit --db-path is required.")
    path = Path(db_path).resolve()
    if not path.is_file():
        raise AssignmentRepairBlockedError("The explicit database path does not exist.")
    return path


def _next_available_path(directory: Path, stem: str) -> Path:
    candidate = directory / f"{stem}.sqlite3"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}.sqlite3"
        counter += 1
    return candidate


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _melbourne_timestamp() -> str:
    return datetime.now(MELBOURNE_TIMEZONE).isoformat(timespec="seconds")


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply deterministic OP SHOP Assignment identity repair. "
            "Defaults to read-only dry-run."
        )
    )
    parser.add_argument("--db-path", required=True, help="Explicit SQLite path.")
    parser.add_argument("--plan-out", help="Dry-run JSON decision file output.")
    parser.add_argument("--decision-file", help="Exact dry-run plan required by apply.")
    parser.add_argument(
        "--backup-dir",
        help="Apply backup destination. Defaults to <db-directory>/backups.",
    )
    parser.add_argument("--apply", action="store_true", help="Enable repair writes.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required non-interactive confirmation for --apply.",
    )
    add_maintenance_logbook_arguments(parser)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
