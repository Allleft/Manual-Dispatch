"""Audit saved Final Summary OP SHOP snapshot rows against live assignments.

This tool is intentionally read-only. It reports historical inconsistencies
that can exist in local office/test SQLite databases from older OP SHOP flows.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ISSUE_TYPES = (
    "OK",
    "EMPTY_PICKUP_TASK_ID",
    "MISSING_TASK",
    "TASK_NOT_ASSIGNED",
    "TASK_DRIVER_MISMATCH",
    "MISSING_ASSIGNMENT",
    "ASSIGNMENT_DRIVER_MISMATCH",
    "TRIP_MISMATCH",
    "PICKUP_DATE_MISMATCH",
)


def audit_database(
    db_path: str | Path,
    dispatch_date: Optional[str] = None,
    delivery_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a read-only audit report for saved OP SHOP final summary locks."""

    path = Path(db_path)
    filters = {
        "dispatch_date": dispatch_date,
        "delivery_date": delivery_date,
    }
    findings: List[Dict[str, Any]] = []

    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = _fetch_snapshot_rows(connection, dispatch_date, delivery_date)

    for row in rows:
        findings.extend(_classify_row(row))

    by_type = Counter(finding["type"] for finding in findings)
    issue_count = sum(
        count for issue_type, count in by_type.items() if issue_type != "OK"
    )
    ok_count = by_type.get("OK", 0)

    return {
        "db_path": str(path),
        "filters": filters,
        "summary": {
            "checked": len(rows),
            "ok": ok_count,
            "issues": issue_count,
            "by_type": {issue_type: by_type.get(issue_type, 0) for issue_type in ISSUE_TYPES},
        },
        "findings": findings,
    }


def format_console_report(report: Dict[str, Any]) -> str:
    """Format a human-readable audit report."""

    lines = [
        "OP SHOP Final Summary Lock Audit",
        f"Database: {report['db_path']}",
        _format_filters(report.get("filters") or {}),
        "",
        "Summary:",
        f"  Checked saved OP SHOP snapshot rows: {report['summary']['checked']}",
        f"  OK rows: {report['summary']['ok']}",
        f"  Issue findings: {report['summary']['issues']}",
        "  By type:",
    ]

    for issue_type, count in report["summary"]["by_type"].items():
        if count:
            lines.append(f"    {issue_type}: {count}")

    issue_findings = [
        finding for finding in report["findings"] if finding["type"] != "OK"
    ]
    if not issue_findings:
        lines.extend(["", "No critical mismatches found."])
        return "\n".join(lines)

    lines.append("")
    lines.append("Findings by issue type:")
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for finding in issue_findings:
        grouped.setdefault(finding["type"], []).append(finding)

    for issue_type in ISSUE_TYPES:
        group = grouped.get(issue_type)
        if not group or issue_type == "OK":
            continue
        lines.append("")
        lines.append(f"{issue_type} ({len(group)}):")
        for finding in group:
            lines.extend(_format_finding(finding))

    return "\n".join(lines)


def write_json_report(report: Dict[str, Any], path: str | Path) -> None:
    """Write the audit report as JSON."""

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

    try:
        report = audit_database(
            path,
            dispatch_date=args.dispatch_date,
            delivery_date=args.delivery_date,
        )
    except sqlite3.Error as exc:
        print(f"Could not audit database: {exc}", file=sys.stderr)
        return 2

    if args.output_json:
        write_json_report(report, args.output_json)

    print(format_console_report(report))
    return 1 if report["summary"]["issues"] else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit for saved Final Summary OP SHOP snapshot rows "
            "versus live OP SHOP task/assignment state."
        )
    )
    parser.add_argument(
        "--db-path",
        help="SQLite database path. Defaults to MANUAL_DISPATCH_DB_PATH.",
    )
    parser.add_argument("--dispatch-date", help="Optional dispatch date filter.")
    parser.add_argument("--delivery-date", help="Optional delivery date filter.")
    parser.add_argument("--output-json", help="Optional JSON report output path.")
    return parser


def _fetch_snapshot_rows(
    connection: sqlite3.Connection,
    dispatch_date: Optional[str],
    delivery_date: Optional[str],
) -> List[sqlite3.Row]:
    where = ["summary.status = 'SAVED'"]
    params: List[str] = []
    if dispatch_date:
        where.append("summary.dispatch_date = ?")
        params.append(dispatch_date)
    if delivery_date:
        where.append("summary.delivery_date = ?")
        params.append(delivery_date)

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


def _classify_row(row: sqlite3.Row) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    pickup_task_id = _clean(row["pickup_task_id_snapshot"])

    if not pickup_task_id:
        return [_finding(row, "EMPTY_PICKUP_TASK_ID")]

    if not row["task_pickup_task_id"]:
        findings.append(_finding(row, "MISSING_TASK"))
    else:
        if row["task_status"] != "ASSIGNED":
            findings.append(_finding(row, "TASK_NOT_ASSIGNED"))
        if row["task_driver_id"] != row["final_driver_id"]:
            findings.append(_finding(row, "TASK_DRIVER_MISMATCH"))
        if not row["task_trip_no"]:
            findings.append(_finding(row, "TRIP_MISMATCH"))

    if not row["assignment_id"]:
        findings.append(_finding(row, "MISSING_ASSIGNMENT"))
    else:
        if row["assignment_driver_id"] != row["final_driver_id"]:
            findings.append(_finding(row, "ASSIGNMENT_DRIVER_MISMATCH"))
        if (
            row["task_trip_no"]
            and row["assignment_trip_no"]
            and row["assignment_trip_no"] != row["task_trip_no"]
        ):
            findings.append(_finding(row, "TRIP_MISMATCH"))

    if row["pickup_date_snapshot"] != row["delivery_date"]:
        findings.append(_finding(row, "PICKUP_DATE_MISMATCH"))
    if row["task_pickup_date"] and row["task_pickup_date"] != row["pickup_date_snapshot"]:
        findings.append(_finding(row, "PICKUP_DATE_MISMATCH"))

    if findings:
        return findings
    return [_finding(row, "OK")]


def _finding(row: sqlite3.Row, issue_type: str) -> Dict[str, Any]:
    return {
        "type": issue_type,
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
        "task_pickup_date": row["task_pickup_date"],
        "assignment_driver_id": row["assignment_driver_id"],
        "assignment_trip_no": row["assignment_trip_no"],
        "recommended_action": _recommended_action(issue_type),
    }


def _recommended_action(issue_type: str) -> str:
    if issue_type == "OK":
        return "No action needed."
    if issue_type == "MISSING_TASK":
        return "Snapshot references a task not present in opshop_pickup_tasks."
    if issue_type in {"TASK_DRIVER_MISMATCH", "ASSIGNMENT_DRIVER_MISMATCH"}:
        return "Review manually before backfill; do not auto-correct."
    if issue_type in {"TASK_NOT_ASSIGNED", "MISSING_ASSIGNMENT", "TRIP_MISMATCH"}:
        return (
            "Historical cleared assignment. Board overlay may display locked state, "
            "but live task should be reviewed before production use."
        )
    if issue_type == "PICKUP_DATE_MISMATCH":
        return "Review pickup date mismatch before any manual backfill."
    if issue_type == "EMPTY_PICKUP_TASK_ID":
        return "Snapshot row has no pickup task id; review the saved summary snapshot."
    return "Review manually before any backfill."


def _format_filters(filters: Dict[str, Any]) -> str:
    active = {key: value for key, value in filters.items() if value}
    if not active:
        return "Filters: none"
    return "Filters: " + ", ".join(f"{key}={value}" for key, value in active.items())


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
        f"    recommended action: {finding['recommended_action']}",
    ]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
