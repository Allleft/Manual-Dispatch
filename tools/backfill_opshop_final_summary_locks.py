"""Safely backfill OP SHOP assignments from saved Final Summary snapshots.

Default mode is dry-run. The tool only writes when --apply is explicitly used,
and --apply requires --yes or an interactive APPLY confirmation.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPAIRABLE_STATUS = "WOULD_REPAIR"
REPAIRED_STATUS = "REPAIRED"
STATUS_TYPES = (
    "ALREADY_OK",
    REPAIRABLE_STATUS,
    REPAIRED_STATUS,
    "SKIP_UNSAFE_CONFLICT",
    "SKIP_MISSING_TASK",
    "SKIP_DATE_MISMATCH",
    "SKIP_EMPTY_PICKUP_TASK_ID",
    "SKIP_CANCELLED_OR_COMPLETED",
    "SKIP_DUPLICATE_SAVED_CONFLICT",
)
UNSAFE_STATUSES = {
    "SKIP_UNSAFE_CONFLICT",
    "SKIP_DUPLICATE_SAVED_CONFLICT",
}


def audit_backfill_candidates(
    db_path: str | Path,
    filters: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Build a dry-run report of OP SHOP saved-lock backfill candidates."""

    path = Path(db_path)
    active_filters = _normalize_filters(filters)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = _fetch_snapshot_rows(connection, active_filters)

    duplicate_conflicts = _find_duplicate_saved_conflicts(rows)
    findings = [
        _classify_candidate(row, duplicate_conflicts)
        for row in rows
    ]
    return _build_report(path, "dry-run", active_filters, findings)


def apply_repairs(
    db_path: str | Path,
    candidates: Dict[str, Any] | List[Dict[str, Any]],
    yes: bool = False,
) -> Dict[str, Any]:
    """Apply safe repairs from a dry-run report or candidate list."""

    if not yes:
        raise ValueError("apply_repairs requires yes=True")

    path = Path(db_path)
    findings = (
        list(candidates.get("findings", []))
        if isinstance(candidates, dict)
        else list(candidates)
    )
    filters = (
        candidates.get("filters", {})
        if isinstance(candidates, dict)
        else {}
    )
    applied_findings: List[Dict[str, Any]] = []
    timestamp = _timestamp()

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN")
            for finding in findings:
                if finding["status"] != REPAIRABLE_STATUS:
                    applied_findings.append(dict(finding))
                    continue

                task = _fetch_task(connection, finding["pickup_task_id"])
                assignment = _fetch_assignment(
                    connection,
                    finding["dispatch_date"],
                    finding["pickup_task_id"],
                )
                if not _is_still_safe_to_repair(finding, task, assignment):
                    updated = dict(finding)
                    updated["status"] = "SKIP_UNSAFE_CONFLICT"
                    updated["reason"] = (
                        "Live task or assignment changed after dry-run; "
                        "review manually before retrying."
                    )
                    applied_findings.append(updated)
                    continue

                _repair_task(connection, finding, timestamp)
                _upsert_assignment(connection, finding, timestamp)
                updated = dict(finding)
                updated["status"] = REPAIRED_STATUS
                updated["reason"] = "Backfilled OP SHOP task and assignment from saved summary."
                applied_findings.append(updated)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return _build_report(path, "apply", filters, applied_findings)


def format_console_report(report: Dict[str, Any]) -> str:
    """Format a human-readable backfill report."""

    lines = [
        "OP SHOP Final Summary Lock Backfill",
        f"Database: {report['db_path']}",
        f"Mode: {report['mode']}",
        _format_filters(report.get("filters") or {}),
    ]
    if report["mode"] == "apply":
        lines.extend(
            [
                "",
                "Warning: Make a backup before running with --apply.",
            ]
        )
    lines.extend(
        [
            "",
            "Summary:",
            f"  Checked saved OP SHOP snapshot rows: {report['summary']['checked']}",
            f"  Already OK: {report['summary']['already_ok']}",
            f"  Would repair: {report['summary']['would_repair']}",
            f"  Repaired: {report['summary']['repaired']}",
            f"  Skipped: {report['summary']['skipped']}",
            f"  Unsafe conflicts: {report['summary']['unsafe_conflicts']}",
            "  By status:",
        ]
    )

    for status, count in report["summary"]["by_status"].items():
        if count:
            lines.append(f"    {status}: {count}")

    if not report["findings"]:
        lines.extend(["", "No saved OP SHOP snapshot rows matched the filters."])
        return "\n".join(lines)

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for finding in report["findings"]:
        grouped[finding["status"]].append(finding)

    lines.append("")
    lines.append("Findings by status:")
    for status in STATUS_TYPES:
        group = grouped.get(status)
        if not group:
            continue
        lines.append("")
        lines.append(f"{status} ({len(group)}):")
        for finding in group:
            lines.extend(_format_finding(finding))

    return "\n".join(lines)


def write_json_report(report: Dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    db_path = args.db_path or os.environ.get("MANUAL_DISPATCH_DB_PATH")

    if not db_path:
        print(
            "Database path is required. Set MANUAL_DISPATCH_DB_PATH or pass --db-path.",
            file=sys.stderr,
        )
        return 2

    path = Path(db_path)
    if not path.exists() or not path.is_file():
        print(f"Database path is missing or unreadable: {path}", file=sys.stderr)
        return 2

    if args.apply and not args.yes:
        print("Warning: Make a backup before running with --apply.")
        confirmation = input("Type APPLY to modify the database: ")
        if confirmation != "APPLY":
            print("Apply cancelled.", file=sys.stderr)
            return 2

    filters = {
        "dispatch_date": args.dispatch_date,
        "delivery_date": args.delivery_date,
        "summary_id": args.summary_id,
    }

    try:
        dry_run = audit_backfill_candidates(path, filters)
        report = (
            apply_repairs(path, dry_run, yes=True)
            if args.apply
            else dry_run
        )
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"Could not backfill database: {exc}", file=sys.stderr)
        return 2

    if args.output_json:
        write_json_report(report, args.output_json)

    print(format_console_report(report))
    return 1 if report["summary"]["unsafe_conflicts"] else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Safely backfill live OP SHOP assignments from SAVED Final Summary "
            "OP SHOP snapshot rows. Defaults to dry-run."
        )
    )
    parser.add_argument(
        "--db-path",
        help="SQLite database path. Defaults to MANUAL_DISPATCH_DB_PATH.",
    )
    parser.add_argument("--dispatch-date", help="Optional dispatch date filter.")
    parser.add_argument("--delivery-date", help="Optional delivery date filter.")
    parser.add_argument("--summary-id", help="Optional Final Summary id filter.")
    parser.add_argument("--output-json", help="Optional JSON report output path.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Modify the database. Without this flag the tool is dry-run only.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive confirmation for --apply.",
    )
    return parser


def _fetch_snapshot_rows(
    connection: sqlite3.Connection,
    filters: Dict[str, Optional[str]],
) -> List[sqlite3.Row]:
    where = ["summary.status = 'SAVED'"]
    params: List[str] = []
    if filters.get("dispatch_date"):
        where.append("summary.dispatch_date = ?")
        params.append(filters["dispatch_date"])
    if filters.get("delivery_date"):
        where.append("summary.delivery_date = ?")
        params.append(filters["delivery_date"])
    if filters.get("summary_id"):
        where.append("summary.summary_id = ?")
        params.append(filters["summary_id"])

    sql = f"""
        SELECT
            summary.summary_id,
            summary.dispatch_date,
            summary.delivery_date,
            summary.driver_id AS final_driver_id,
            summary.driver_name_snapshot AS final_driver_name,
            opshop_row.row_id AS snapshot_row_id,
            opshop_row.pickup_task_id_snapshot,
            opshop_row.opshop_name_snapshot,
            opshop_row.pickup_date_snapshot,
            task.pickup_task_id AS task_pickup_task_id,
            task.status AS task_status,
            task.driver_id AS task_driver_id,
            task.trip_no AS task_trip_no,
            task.dispatch_date AS task_dispatch_date,
            task.pickup_date AS task_pickup_date,
            assignment.assignment_id AS assignment_id,
            assignment.driver_id AS assignment_driver_id,
            assignment.trip_no AS assignment_trip_no
        FROM final_trip_summaries summary
        JOIN final_trip_summary_opshop_pickup_rows opshop_row
            ON opshop_row.summary_id = summary.summary_id
        LEFT JOIN opshop_pickup_tasks task
            ON task.pickup_task_id = opshop_row.pickup_task_id_snapshot
        LEFT JOIN manual_dispatch_assignments assignment
            ON assignment.dispatch_date = summary.dispatch_date
            AND assignment.task_type = 'OPSHOP_PICKUP'
            AND assignment.task_id = opshop_row.pickup_task_id_snapshot
        WHERE {" AND ".join(where)}
        ORDER BY
            summary.dispatch_date,
            summary.delivery_date,
            summary.driver_id,
            summary.summary_id,
            opshop_row.row_no,
            opshop_row.row_id
    """
    return connection.execute(sql, params).fetchall()


def _classify_candidate(
    row: sqlite3.Row,
    duplicate_conflicts: set[str],
) -> Dict[str, Any]:
    finding = _base_finding(row)
    pickup_task_id = _clean(row["pickup_task_id_snapshot"])

    if not pickup_task_id:
        return _with_status(
            finding,
            "SKIP_EMPTY_PICKUP_TASK_ID",
            "Snapshot row has no pickup task id.",
        )
    if pickup_task_id in duplicate_conflicts:
        return _with_status(
            finding,
            "SKIP_DUPLICATE_SAVED_CONFLICT",
            "Same pickup task appears in saved summaries for different driver/date values.",
        )
    if not row["final_driver_id"]:
        return _with_status(
            finding,
            "SKIP_UNSAFE_CONFLICT",
            "Saved Final Summary has no driver_id.",
        )
    if row["pickup_date_snapshot"] != row["delivery_date"]:
        return _with_status(
            finding,
            "SKIP_DATE_MISMATCH",
            "Snapshot pickup date does not match Final Summary delivery date.",
        )
    if not row["task_pickup_task_id"]:
        return _with_status(
            finding,
            "SKIP_MISSING_TASK",
            "Snapshot references a task not present in opshop_pickup_tasks.",
        )
    if row["task_pickup_date"] != row["pickup_date_snapshot"]:
        return _with_status(
            finding,
            "SKIP_DATE_MISMATCH",
            "Live task pickup date does not match snapshot pickup date.",
        )
    if row["task_status"] in {"CANCELLED", "COMPLETED"}:
        return _with_status(
            finding,
            "SKIP_CANCELLED_OR_COMPLETED",
            "Live task is CANCELLED or COMPLETED and will not be repaired.",
        )
    if row["task_status"] not in {"ACTIVE", "ASSIGNED"}:
        return _with_status(
            finding,
            "SKIP_UNSAFE_CONFLICT",
            "Live task status is not safe to repair.",
        )
    if row["task_driver_id"] and row["task_driver_id"] != row["final_driver_id"]:
        return _with_status(
            finding,
            "SKIP_UNSAFE_CONFLICT",
            "Live task is assigned to a different driver.",
        )
    if row["task_trip_no"] and row["task_trip_no"] != "trip1":
        return _with_status(
            finding,
            "SKIP_UNSAFE_CONFLICT",
            "Live task has a non-trip1 trip number.",
        )
    if row["assignment_id"]:
        if row["assignment_driver_id"] != row["final_driver_id"]:
            return _with_status(
                finding,
                "SKIP_UNSAFE_CONFLICT",
                "Existing assignment belongs to a different driver.",
            )
        if row["assignment_trip_no"] != "trip1":
            return _with_status(
                finding,
                "SKIP_UNSAFE_CONFLICT",
                "Existing assignment has a non-trip1 trip number.",
            )

    is_task_ok = (
        row["task_status"] == "ASSIGNED"
        and row["task_driver_id"] == row["final_driver_id"]
        and row["task_trip_no"] == "trip1"
        and row["task_dispatch_date"] == row["dispatch_date"]
    )
    is_assignment_ok = (
        bool(row["assignment_id"])
        and row["assignment_driver_id"] == row["final_driver_id"]
        and row["assignment_trip_no"] == "trip1"
    )
    if is_task_ok and is_assignment_ok:
        return _with_status(finding, "ALREADY_OK", "Live OP SHOP lock is already intact.")

    return _with_status(
        finding,
        REPAIRABLE_STATUS,
        "Would restore task status/driver/trip and OP SHOP assignment from saved summary.",
    )


def _find_duplicate_saved_conflicts(rows: List[sqlite3.Row]) -> set[str]:
    signatures_by_task: Dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        pickup_task_id = _clean(row["pickup_task_id_snapshot"])
        if not pickup_task_id:
            continue
        signatures_by_task[pickup_task_id].add(
            (row["final_driver_id"], row["delivery_date"])
        )
    return {
        pickup_task_id
        for pickup_task_id, signatures in signatures_by_task.items()
        if len(signatures) > 1
    }


def _is_still_safe_to_repair(
    finding: Dict[str, Any],
    task: Optional[sqlite3.Row],
    assignment: Optional[sqlite3.Row],
) -> bool:
    if not task:
        return False
    if task["pickup_date"] != finding["pickup_date_snapshot"]:
        return False
    if task["status"] not in {"ACTIVE", "ASSIGNED"}:
        return False
    if task["driver_id"] and task["driver_id"] != finding["final_summary_driver_id"]:
        return False
    if task["trip_no"] and task["trip_no"] != "trip1":
        return False
    if assignment:
        if assignment["driver_id"] != finding["final_summary_driver_id"]:
            return False
        if assignment["trip_no"] != "trip1":
            return False
    return True


def _repair_task(
    connection: sqlite3.Connection,
    finding: Dict[str, Any],
    timestamp: str,
) -> None:
    connection.execute(
        """
        UPDATE opshop_pickup_tasks
        SET
            status = 'ASSIGNED',
            driver_id = ?,
            trip_no = 'trip1',
            dispatch_date = ?,
            updated_at = ?
        WHERE pickup_task_id = ?
        """,
        (
            finding["final_summary_driver_id"],
            finding["dispatch_date"],
            timestamp,
            finding["pickup_task_id"],
        ),
    )


def _upsert_assignment(
    connection: sqlite3.Connection,
    finding: Dict[str, Any],
    timestamp: str,
) -> None:
    assignment = _fetch_assignment(
        connection,
        finding["dispatch_date"],
        finding["pickup_task_id"],
    )
    if assignment:
        connection.execute(
            """
            UPDATE manual_dispatch_assignments
            SET driver_id = ?, trip_no = 'trip1', updated_at = ?
            WHERE dispatch_date = ?
                AND task_type = 'OPSHOP_PICKUP'
                AND task_id = ?
            """,
            (
                finding["final_summary_driver_id"],
                timestamp,
                finding["dispatch_date"],
                finding["pickup_task_id"],
            ),
        )
        return

    connection.execute(
        """
        INSERT INTO manual_dispatch_assignments (
            assignment_id,
            dispatch_date,
            task_type,
            task_id,
            driver_id,
            trip_no,
            assigned_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _create_assignment_id(connection),
            finding["dispatch_date"],
            "OPSHOP_PICKUP",
            finding["pickup_task_id"],
            finding["final_summary_driver_id"],
            "trip1",
            timestamp,
            timestamp,
        ),
    )


def _fetch_task(connection: sqlite3.Connection, pickup_task_id: str) -> Optional[sqlite3.Row]:
    return connection.execute(
        """
        SELECT *
        FROM opshop_pickup_tasks
        WHERE pickup_task_id = ?
        """,
        (pickup_task_id,),
    ).fetchone()


def _fetch_assignment(
    connection: sqlite3.Connection,
    dispatch_date: str,
    pickup_task_id: str,
) -> Optional[sqlite3.Row]:
    return connection.execute(
        """
        SELECT *
        FROM manual_dispatch_assignments
        WHERE dispatch_date = ?
            AND task_type = 'OPSHOP_PICKUP'
            AND task_id = ?
        """,
        (dispatch_date, pickup_task_id),
    ).fetchone()


def _create_assignment_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        """
        SELECT COALESCE(MAX(CAST(SUBSTR(assignment_id, 3) AS INTEGER)), 0) + 1
            AS next_number
        FROM manual_dispatch_assignments
        WHERE assignment_id LIKE 'A-%'
        """
    ).fetchone()
    return f"A-{row['next_number']:03d}"


def _build_report(
    db_path: Path,
    mode: str,
    filters: Dict[str, Optional[str]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    by_status = Counter(finding["status"] for finding in findings)
    unsafe_conflicts = sum(by_status.get(status, 0) for status in UNSAFE_STATUSES)
    skipped = sum(
        count
        for status, count in by_status.items()
        if status.startswith("SKIP_")
    )
    return {
        "db_path": str(db_path),
        "mode": mode,
        "filters": filters,
        "summary": {
            "checked": len(findings),
            "already_ok": by_status.get("ALREADY_OK", 0),
            "would_repair": by_status.get(REPAIRABLE_STATUS, 0),
            "repaired": by_status.get(REPAIRED_STATUS, 0),
            "skipped": skipped,
            "unsafe_conflicts": unsafe_conflicts,
            "by_status": {
                status: by_status.get(status, 0)
                for status in STATUS_TYPES
            },
        },
        "findings": findings,
    }


def _base_finding(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "summary_id": row["summary_id"],
        "dispatch_date": row["dispatch_date"],
        "delivery_date": row["delivery_date"],
        "final_summary_driver_id": row["final_driver_id"],
        "final_summary_driver_name": row["final_driver_name"],
        "snapshot_row_id": row["snapshot_row_id"],
        "pickup_task_id": row["pickup_task_id_snapshot"],
        "opshop_name_snapshot": row["opshop_name_snapshot"],
        "pickup_date_snapshot": row["pickup_date_snapshot"],
        "task_status": row["task_status"],
        "task_driver_id": row["task_driver_id"],
        "task_trip_no": row["task_trip_no"],
        "task_dispatch_date": row["task_dispatch_date"],
        "task_pickup_date": row["task_pickup_date"],
        "assignment_driver_id": row["assignment_driver_id"],
        "assignment_trip_no": row["assignment_trip_no"],
    }


def _with_status(
    finding: Dict[str, Any],
    status: str,
    reason: str,
) -> Dict[str, Any]:
    updated = dict(finding)
    updated["status"] = status
    updated["reason"] = reason
    return updated


def _format_finding(finding: Dict[str, Any]) -> List[str]:
    return [
        f"  - summary_id: {finding['summary_id']}",
        f"    dispatch_date: {finding['dispatch_date']}",
        f"    delivery_date: {finding['delivery_date']}",
        f"    final summary driver_id: {finding['final_summary_driver_id']}",
        f"    pickup_task_id: {finding['pickup_task_id']}",
        f"    opshop_name_snapshot: {finding['opshop_name_snapshot']}",
        (
            "    live task: "
            f"status={finding['task_status']} "
            f"driver_id={finding['task_driver_id']} "
            f"trip_no={finding['task_trip_no']} "
            f"pickup_date={finding['task_pickup_date']}"
        ),
        (
            "    assignment: "
            f"driver_id={finding['assignment_driver_id']} "
            f"trip_no={finding['assignment_trip_no']}"
        ),
        f"    reason: {finding['reason']}",
    ]


def _format_filters(filters: Dict[str, Any]) -> str:
    active = {key: value for key, value in filters.items() if value}
    if not active:
        return "Filters: none"
    return "Filters: " + ", ".join(f"{key}={value}" for key, value in active.items())


def _normalize_filters(
    filters: Optional[Dict[str, Optional[str]]],
) -> Dict[str, Optional[str]]:
    filters = filters or {}
    return {
        "dispatch_date": filters.get("dispatch_date"),
        "delivery_date": filters.get("delivery_date"),
        "summary_id": filters.get("summary_id"),
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
