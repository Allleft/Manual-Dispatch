"""Migrate SAVED legacy Final Summaries into independent workspace snapshots.

The default mode is read-only dry-run. Writes require both --apply and --yes.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.maintenance_logbook import (  # noqa: E402
    add_maintenance_logbook_arguments,
    record_maintenance_event,
    resolve_maintenance_actor,
    safe_basename,
    sanitized_failure_metadata,
)


REQUIRED_TABLES = {
    "final_trip_summaries",
    "final_trip_summary_rows",
    "final_trip_summary_opshop_pickup_rows",
    "delivery_run_sheets",
    "delivery_run_sheet_rows",
    "opshop_pickup_collections",
    "opshop_pickup_collection_rows",
}


class MigrationBlockedError(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


@contextlib.contextmanager
def _read_only_database_snapshot(db_path):
    """Copy the database and WAL so inspection never opens the target with SQLite."""
    source_path = Path(db_path).resolve()
    with tempfile.TemporaryDirectory(prefix="manual-dispatch-read-") as temp_dir:
        snapshot_path = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, snapshot_path)
        wal_path = Path(f"{source_path}-wal")
        if wal_path.exists():
            shutil.copy2(wal_path, Path(f"{snapshot_path}-wal"))
        yield snapshot_path


def inspect_migration(db_path: str | Path) -> Dict[str, Any]:
    path = _validated_database_path(db_path)
    with _read_only_database_snapshot(path) as snapshot_path:
        uri = snapshot_path.as_uri() + "?mode=ro"
        with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            return _build_preflight_report(connection, path)


def migrate_legacy_final_summaries(
    db_path: str | Path,
    *,
    apply: bool = False,
    yes: bool = False,
    backup_dir: str | Path | None = None,
) -> Dict[str, Any]:
    path = _validated_database_path(db_path)
    report = inspect_migration(path)
    if not apply:
        return report
    if not yes:
        raise MigrationBlockedError("Apply requires both --apply and --yes.", report)
    _raise_for_preflight_blocks(report)

    backup_path = create_verified_backup(path, backup_dir)
    report["backup_path"] = str(backup_path)

    with sqlite3.connect(path, isolation_level=None) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN IMMEDIATE")
            locked_report = _build_preflight_report(connection, path)
            _raise_for_preflight_blocks(locked_report)
            migrated = _apply_candidates(connection, locked_report)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    final_report = inspect_migration(path)
    final_report["mode"] = "apply"
    final_report["backup_path"] = str(backup_path)
    final_report["applied"] = migrated
    return final_report


def create_verified_backup(
    db_path: str | Path,
    backup_dir: str | Path | None = None,
) -> Path:
    path = _validated_database_path(db_path)
    destination_dir = Path(backup_dir) if backup_dir else path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = _next_available_path(
        destination_dir,
        f"{path.stem}_before_workspace_migration_{timestamp}",
    )

    with sqlite3.connect(path) as source:
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)

    integrity_result = _backup_integrity_result(backup_path)
    if integrity_result.lower() != "ok":
        raise MigrationBlockedError(
            f"Backup integrity check failed for {backup_path}: {integrity_result}"
        )
    return backup_path


def format_console_report(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Legacy Final Summary Workspace Migration",
        f"Database: {report['db_path']}",
        f"Mode: {report['mode']}",
        f"Backup: {report.get('backup_path') or 'not created (dry-run/preflight)'}",
        "",
        "Summary:",
        f"  Saved legacy summaries found: {summary['saved_legacy_summaries']}",
        f"  Generated legacy summaries found: {summary['generated_legacy_summaries']}",
        f"  Delivery Run Sheets to create: {summary['delivery_to_create']}",
        f"  OP SHOP Collections to create: {summary['opshop_to_create']}",
        f"  Already migrated records: {summary['already_migrated']}",
        f"  Conflicts: {summary['conflicts']}",
        f"  Rows skipped: {summary['skipped']}",
    ]
    if report.get("generated_summaries"):
        lines.extend(["", "GENERATED legacy summaries (apply blocker):"])
        for item in report["generated_summaries"]:
            lines.append(
                "  {summary_id} | {dispatch_date} | {delivery_date} | "
                "{driver_id} | {driver_name}".format(**item)
            )
    if report.get("conflicts"):
        lines.extend(["", "Conflicts (apply blocker):"])
        for item in report["conflicts"]:
            lines.append(
                f"  {item['summary_id']} | {item['module']} | {item['reason']}"
            )
    if report.get("skipped"):
        lines.extend(["", "Skipped:"])
        for item in report["skipped"]:
            lines.append(f"  {item['summary_id']} | {item['reason']}")
    if report.get("applied"):
        lines.extend(
            [
                "",
                "Applied:",
                f"  Delivery Run Sheets: {report['applied']['delivery_run_sheets']}",
                f"  Delivery rows: {report['applied']['delivery_rows']}",
                f"  OP SHOP Collections: {report['applied']['opshop_collections']}",
                f"  OP SHOP rows: {report['applied']['opshop_rows']}",
            ]
        )
    return "\n".join(lines)


def _migration_metadata(db_path, report, mode):
    summary = dict((report or {}).get("summary") or {})
    applied = dict((report or {}).get("applied") or {})
    backup_path = (report or {}).get("backup_path")
    metadata = {
        "mode": mode,
        "database_filename": safe_basename(db_path),
        "saved_legacy_summaries": int(
            summary.get("saved_legacy_summaries", 0) or 0
        ),
        "generated_legacy_summaries": int(
            summary.get("generated_legacy_summaries", 0) or 0
        ),
        "delivery_to_create": int(
            applied.get("delivery_run_sheets", summary.get("delivery_to_create", 0))
            or 0
        ),
        "opshop_to_create": int(
            applied.get("opshop_collections", summary.get("opshop_to_create", 0))
            or 0
        ),
        "already_migrated": int(summary.get("already_migrated", 0) or 0),
        "conflicts": int(summary.get("conflicts", 0) or 0),
        "skipped": int(summary.get("skipped", 0) or 0),
        "backup_created": bool(backup_path),
        "backup_filename": safe_basename(backup_path),
    }
    if mode == "apply":
        metadata.update(
            {
                "delivery_run_sheets_created": int(
                    applied.get("delivery_run_sheets", 0) or 0
                ),
                "delivery_rows_created": int(applied.get("delivery_rows", 0) or 0),
                "opshop_collections_created": int(
                    applied.get("opshop_collections", 0) or 0
                ),
                "opshop_rows_created": int(applied.get("opshop_rows", 0) or 0),
            }
        )
    return metadata


def _migration_failure_phase(error, apply):
    if isinstance(error, MigrationBlockedError):
        return "preflight"
    if isinstance(error, OSError):
        return "database_backup" if apply else "inspection"
    if isinstance(error, sqlite3.Error):
        return "database_apply" if apply else "inspection"
    return "database_apply" if apply else "inspection"


def _record_migration_event(args, actor, db_path, result, summary, metadata):
    return record_maintenance_event(
        action=(
            "LEGACY_WORKSPACE_MIGRATION_APPLIED"
            if args.apply
            else "LEGACY_WORKSPACE_MIGRATION_DRY_RUN"
        ),
        result=result,
        workspace="SYSTEM",
        actor=actor,
        entity_type="WORKSPACE_MIGRATION",
        entity_id=safe_basename(db_path),
        summary=summary,
        metadata=metadata,
        logbook_dir=args.logbook_dir,
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    db_path = args.db_path or os.environ.get("MANUAL_DISPATCH_DB_PATH")
    if not db_path:
        print("Database path is required.", file=sys.stderr)
        return 2
    actor = resolve_maintenance_actor(args.actor)
    mode = "apply" if args.apply else "dry-run"
    try:
        report = migrate_legacy_final_summaries(
            db_path,
            apply=args.apply,
            yes=args.yes,
            backup_dir=args.backup_dir,
        )
    except (MigrationBlockedError, OSError, sqlite3.Error) as error:
        error_report = error.report if isinstance(error, MigrationBlockedError) else None
        if error_report:
            print(format_console_report(error_report))
        print(f"Migration blocked: {error}", file=sys.stderr)
        metadata = _migration_metadata(db_path, error_report, mode)
        metadata.update(
            sanitized_failure_metadata(
                error,
                _migration_failure_phase(error, args.apply),
            )
        )
        _record_migration_event(
            args,
            actor,
            db_path,
            "FAILED",
            (
                "Legacy workspace migration apply was blocked by preflight checks."
                if args.apply and isinstance(error, MigrationBlockedError)
                else (
                    "Legacy workspace migration apply failed."
                    if args.apply
                    else "Legacy workspace migration dry-run failed."
                )
            ),
            metadata,
        )
        return 2
    except Exception as error:
        metadata = _migration_metadata(db_path, None, mode)
        metadata.update(
            sanitized_failure_metadata(
                error,
                _migration_failure_phase(error, args.apply),
            )
        )
        _record_migration_event(
            args,
            actor,
            db_path,
            "FAILED",
            (
                "Legacy workspace migration apply failed."
                if args.apply
                else "Legacy workspace migration dry-run failed."
            ),
            metadata,
        )
        raise

    print(format_console_report(report))
    metadata = _migration_metadata(db_path, report, mode)
    if args.apply:
        applied = report.get("applied") or {}
        result = "SUCCESS"
        event_summary = (
            "Legacy workspace migration was applied: "
            f"{applied.get('delivery_run_sheets', 0)} Delivery Run Sheets and "
            f"{applied.get('opshop_collections', 0)} OP SHOP Collections created."
        )
    else:
        summary = report["summary"]
        has_blockers = bool(
            summary.get("generated_legacy_summaries") or summary.get("conflicts")
        )
        result = "PARTIAL" if has_blockers else "SUCCESS"
        event_summary = (
            "Legacy workspace migration dry-run completed with apply blockers "
            "requiring review."
            if has_blockers
            else "Legacy workspace migration dry-run completed with no apply blockers."
        )
    _record_migration_event(
        args,
        actor,
        db_path,
        result,
        event_summary,
        metadata,
    )
    return 0


def _build_preflight_report(connection, path):
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing_tables = sorted(REQUIRED_TABLES - tables)
    conflicts = [
        {
            "summary_id": "schema",
            "module": "schema",
            "reason": f"Missing required table: {table}",
        }
        for table in missing_tables
    ]
    if missing_tables:
        return _report(path, [], [], [], conflicts, [])

    generated = [
        _summary_identity(row)
        for row in connection.execute(
            """
            SELECT summary_id, dispatch_date, delivery_date, driver_id,
                   driver_name_snapshot
            FROM final_trip_summaries
            WHERE status = 'GENERATED'
            ORDER BY summary_id
            """
        ).fetchall()
    ]
    saved_rows = connection.execute(
        """
        SELECT summary.*,
               (SELECT COUNT(*) FROM final_trip_summary_rows row
                WHERE row.summary_id = summary.summary_id) AS delivery_row_count,
               (SELECT COUNT(*) FROM final_trip_summary_opshop_pickup_rows row
                WHERE row.summary_id = summary.summary_id) AS opshop_row_count
        FROM final_trip_summaries summary
        WHERE summary.status = 'SAVED'
        ORDER BY summary.summary_id
        """
    ).fetchall()

    candidates = []
    skipped = []
    for summary in saved_rows:
        if not summary["delivery_row_count"] and not summary["opshop_row_count"]:
            skipped.append(
                {
                    "summary_id": summary["summary_id"],
                    "reason": "No Delivery or OP SHOP snapshot rows.",
                }
            )
            continue
        if summary["delivery_row_count"]:
            _classify_module(
                connection,
                summary,
                "delivery",
                candidates,
                conflicts,
            )
        if summary["opshop_row_count"]:
            _classify_module(
                connection,
                summary,
                "opshop",
                candidates,
                conflicts,
            )

    _append_duplicate_marker_conflicts(connection, conflicts)
    return _report(path, saved_rows, generated, candidates, conflicts, skipped)


def _classify_module(connection, summary, module, candidates, conflicts):
    config = _module_config(module)
    marker_rows = connection.execute(
        f"SELECT * FROM {config['header_table']} WHERE legacy_summary_id = ?",
        (summary["summary_id"],),
    ).fetchall()
    key = (
        summary["dispatch_date"],
        summary["delivery_date"],
        summary["driver_id"],
    )
    if marker_rows:
        marker = marker_rows[0]
        marker_key = (
            marker["dispatch_date"],
            marker[config["date_column"]],
            marker["driver_id"],
        )
        if marker_key != key:
            conflicts.append(
                {
                    "summary_id": summary["summary_id"],
                    "module": module,
                    "reason": "legacy_summary_id points to a different date/driver key.",
                }
            )
        else:
            candidates.append(_candidate(summary, module, "already_migrated"))
        return

    key_row = connection.execute(
        f"""
        SELECT * FROM {config['header_table']}
        WHERE dispatch_date = ? AND {config['date_column']} = ? AND driver_id = ?
        LIMIT 1
        """,
        key,
    ).fetchone()
    if key_row:
        conflicts.append(
            {
                "summary_id": summary["summary_id"],
                "module": module,
                "reason": "A new workspace snapshot already uses this date/driver key.",
            }
        )
        return
    candidates.append(_candidate(summary, module, "create"))


def _append_duplicate_marker_conflicts(connection, conflicts):
    for module in ("delivery", "opshop"):
        config = _module_config(module)
        rows = connection.execute(
            f"""
            SELECT legacy_summary_id, COUNT(*) AS marker_count
            FROM {config['header_table']}
            WHERE legacy_summary_id IS NOT NULL
            GROUP BY legacy_summary_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()
        for row in rows:
            conflicts.append(
                {
                    "summary_id": row["legacy_summary_id"],
                    "module": module,
                    "reason": "Duplicate legacy migration markers detected.",
                }
            )


def _apply_candidates(connection, report):
    applied = {
        "delivery_run_sheets": 0,
        "delivery_rows": 0,
        "opshop_collections": 0,
        "opshop_rows": 0,
    }
    for candidate in report["candidates"]:
        if candidate["action"] != "create":
            continue
        summary = connection.execute(
            "SELECT * FROM final_trip_summaries WHERE summary_id = ?",
            (candidate["summary_id"],),
        ).fetchone()
        if candidate["module"] == "delivery":
            row_count = _insert_delivery_run_sheet(connection, summary)
            applied["delivery_run_sheets"] += 1
            applied["delivery_rows"] += row_count
        else:
            row_count = _insert_opshop_collection(connection, summary)
            applied["opshop_collections"] += 1
            applied["opshop_rows"] += row_count
    return applied


def _insert_delivery_run_sheet(connection, summary):
    run_sheet_id = _deterministic_id("DRS-LEGACY", summary["summary_id"])
    connection.execute(
        """
        INSERT INTO delivery_run_sheets (
            run_sheet_id, dispatch_date, delivery_date, driver_id,
            driver_name_snapshot, vehicle_id, vehicle_rego_snapshot,
            total_pallets, total_loose_bags, status, generated_at, saved_at,
            saved_by_account_name, saved_by_account_id, legacy_summary_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SAVED', ?, ?, ?, ?, ?)
        """,
        (
            run_sheet_id,
            summary["dispatch_date"],
            summary["delivery_date"],
            summary["driver_id"],
            summary["driver_name_snapshot"],
            summary["vehicle_id"],
            summary["vehicle_rego_snapshot"],
            summary["total_pallets"],
            summary["total_loose_bags"],
            summary["generated_at"] or summary["saved_at"],
            summary["saved_at"],
            summary["saved_by_account_name"],
            summary["saved_by_account_id"],
            summary["summary_id"],
        ),
    )
    rows = connection.execute(
        """
        SELECT * FROM final_trip_summary_rows
        WHERE summary_id = ?
        ORDER BY CASE trip_no WHEN 'trip1' THEN 1 WHEN 'trip2' THEN 2 ELSE 9 END,
                 row_no, row_id
        """,
        (summary["summary_id"],),
    ).fetchall()
    for row in rows:
        connection.execute(
            """
            INSERT INTO delivery_run_sheet_rows (
                row_id, run_sheet_id, trip_no, row_no, task_type, task_id,
                order_id_snapshot, invoice_number_snapshot, order_no_snapshot,
                company_name_snapshot, suburb_snapshot, delivery_address_snapshot,
                product_snapshot, product_details_snapshot,
                estimated_distance_km_from_warehouse_snapshot,
                pallet_quantity_snapshot, loose_bags_quantity_snapshot, note_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _deterministic_id("DRR-LEGACY", row["row_id"]),
                run_sheet_id,
                row["trip_no"],
                row["row_no"],
                row["task_type"],
                row["task_id"],
                row["order_id_snapshot"],
                row["invoice_number_snapshot"],
                row["order_no_snapshot"],
                row["company_name_snapshot"],
                row["suburb_snapshot"],
                row["delivery_address_snapshot"],
                row["product_snapshot"],
                row["product_details_snapshot"],
                row["estimated_distance_km_from_warehouse_snapshot"],
                row["pallet_quantity_snapshot"],
                row["loose_bags_quantity_snapshot"],
                row["note_snapshot"],
            ),
        )
    return len(rows)


def _insert_opshop_collection(connection, summary):
    collection_id = _deterministic_id("OPC-LEGACY", summary["summary_id"])
    connection.execute(
        """
        INSERT INTO opshop_pickup_collections (
            collection_id, dispatch_date, pickup_date, driver_id,
            driver_name_snapshot, status, generated_at, saved_at,
            saved_by_account_name, saved_by_account_id, legacy_summary_id
        ) VALUES (?, ?, ?, ?, ?, 'SAVED', ?, ?, ?, ?, ?)
        """,
        (
            collection_id,
            summary["dispatch_date"],
            summary["delivery_date"],
            summary["driver_id"],
            summary["driver_name_snapshot"],
            summary["generated_at"] or summary["saved_at"],
            summary["saved_at"],
            summary["saved_by_account_name"],
            summary["saved_by_account_id"],
            summary["summary_id"],
        ),
    )
    rows = connection.execute(
        """
        SELECT * FROM final_trip_summary_opshop_pickup_rows
        WHERE summary_id = ?
        ORDER BY row_no, row_id
        """,
        (summary["summary_id"],),
    ).fetchall()
    for row in rows:
        connection.execute(
            """
            INSERT INTO opshop_pickup_collection_rows (
                row_id, collection_id, row_no, pickup_task_id_snapshot,
                opshop_name_snapshot, suburb_snapshot, street_address_snapshot,
                area_region_snapshot, pickup_date_snapshot, run_type_snapshot,
                pickup_category_snapshot, route_group_id_snapshot,
                route_group_name_snapshot, pickup_frequency_snapshot,
                time_window_snapshot, call_before_arrival_snapshot,
                call_timing_snapshot, primary_contact_snapshot,
                primary_phone_snapshot, secondary_contact_snapshot,
                secondary_phone_snapshot, access_type_snapshot,
                key_required_snapshot, trailer_restriction_snapshot,
                notes_snapshot, status_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _deterministic_id("OPCR-LEGACY", row["row_id"]),
                collection_id,
                row["row_no"],
                row["pickup_task_id_snapshot"],
                row["opshop_name_snapshot"],
                row["suburb_snapshot"],
                row["street_address_snapshot"],
                row["area_region_snapshot"],
                row["pickup_date_snapshot"],
                row["run_type_snapshot"],
                row["pickup_category_snapshot"],
                row["route_group_id_snapshot"],
                row["route_group_name_snapshot"],
                row["pickup_frequency_snapshot"],
                row["time_window_snapshot"],
                row["primary_contact_snapshot"],
                row["primary_phone_snapshot"],
                row["secondary_contact_snapshot"],
                row["secondary_phone_snapshot"],
                row["access_type_snapshot"],
                row["key_required_snapshot"],
                row["trailer_restriction_snapshot"],
                row["notes_snapshot"],
                row["status_snapshot"],
            ),
        )
    return len(rows)


def _report(path, saved_rows, generated, candidates, conflicts, skipped):
    return {
        "db_path": str(path),
        "mode": "dry-run",
        "backup_path": None,
        "summary": {
            "saved_legacy_summaries": len(saved_rows),
            "generated_legacy_summaries": len(generated),
            "delivery_to_create": sum(
                item["module"] == "delivery" and item["action"] == "create"
                for item in candidates
            ),
            "opshop_to_create": sum(
                item["module"] == "opshop" and item["action"] == "create"
                for item in candidates
            ),
            "already_migrated": sum(
                item["action"] == "already_migrated" for item in candidates
            ),
            "conflicts": len(conflicts),
            "skipped": len(skipped),
        },
        "generated_summaries": generated,
        "candidates": candidates,
        "conflicts": conflicts,
        "skipped": skipped,
    }


def _raise_for_preflight_blocks(report):
    if report["generated_summaries"]:
        raise MigrationBlockedError(
            "Legacy GENERATED Final Summaries must be cancelled or resolved first.",
            report,
        )
    if report["conflicts"]:
        raise MigrationBlockedError(
            "Migration conflicts must be resolved before apply.",
            report,
        )


def _candidate(summary, module, action):
    return {
        "summary_id": summary["summary_id"],
        "module": module,
        "action": action,
        "dispatch_date": summary["dispatch_date"],
        "operational_date": summary["delivery_date"],
        "driver_id": summary["driver_id"],
    }


def _summary_identity(row):
    return {
        "summary_id": row["summary_id"],
        "dispatch_date": row["dispatch_date"],
        "delivery_date": row["delivery_date"],
        "driver_id": row["driver_id"],
        "driver_name": row["driver_name_snapshot"],
    }


def _module_config(module):
    if module == "delivery":
        return {
            "header_table": "delivery_run_sheets",
            "date_column": "delivery_date",
        }
    return {
        "header_table": "opshop_pickup_collections",
        "date_column": "pickup_date",
    }


def _deterministic_id(prefix, source_id):
    digest = hashlib.sha1(str(source_id).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _backup_integrity_result(backup_path):
    with sqlite3.connect(backup_path) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    return str(row[0] if row else "no integrity result")


def _next_available_path(directory, stem):
    candidate = directory / f"{stem}.sqlite3"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}.sqlite3"
        counter += 1
    return candidate


def _validated_database_path(db_path):
    path = Path(db_path).resolve()
    if not path.exists() or not path.is_file():
        raise MigrationBlockedError(f"Database path is missing or unreadable: {path}")
    return path


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Migrate SAVED legacy Final Summaries into independent Delivery Run "
            "Sheets and OP SHOP Pickup Collections. Defaults to dry-run."
        )
    )
    parser.add_argument(
        "--db-path",
        help="SQLite path. Defaults to MANUAL_DISPATCH_DB_PATH.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Optional backup destination. Defaults to <db-directory>/backups.",
    )
    parser.add_argument("--apply", action="store_true", help="Enable migration writes.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required non-interactive confirmation for --apply.",
    )
    add_maintenance_logbook_arguments(parser)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
