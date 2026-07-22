"""Audit and apply H5 SQLite service-identity constraints.

The default mode is a read-only dry-run. Writes require both --apply and --yes.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.invariants import (
    audit_database_invariants,
    create_invariant_indexes,
    missing_invariant_indexes,
)


class InvariantMigrationBlockedError(ValueError):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


def inspect_database_invariants(db_path):
    path = _validated_database_path(db_path)
    with _read_only_database_snapshot(path) as snapshot_path:
        with _read_only_connection(snapshot_path) as connection:
            report = audit_database_invariants(connection)
            report.update(
                {
                    "db_path": str(path),
                    "mode": "dry-run",
                    "backup_path": None,
                    "integrity_before": _integrity_result(connection),
                    "integrity_after": None,
                }
            )
            return report


def migrate_database_invariants(
    db_path,
    *,
    apply=False,
    yes=False,
    backup_dir=None,
):
    path = _validated_database_path(db_path)
    report = inspect_database_invariants(path)
    _raise_for_preflight_blocks(report)
    if not apply:
        return report
    if not yes:
        raise InvariantMigrationBlockedError(
            "Apply requires both --apply and --yes.",
            report,
        )

    backup_path = create_verified_invariant_backup(path, backup_dir)
    try:
        with contextlib.closing(sqlite3.connect(path, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                connection.execute("BEGIN IMMEDIATE")
                locked_report = audit_database_invariants(connection)
                if locked_report["conflicts"]:
                    raise InvariantMigrationBlockedError(
                        "Invariant conflicts appeared after preflight; apply was stopped.",
                        locked_report,
                    )
                create_invariant_indexes(connection)
                missing = missing_invariant_indexes(connection)
                if missing:
                    raise RuntimeError(
                        f"Invariant indexes were not created: {', '.join(missing)}"
                    )
                integrity_after_apply = _integrity_result(connection)
                if integrity_after_apply.lower() != "ok":
                    raise RuntimeError(
                        f"Post-apply integrity check failed: {integrity_after_apply}"
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    except Exception:
        raise

    final_report = inspect_database_invariants(path)
    final_report.update(
        {
            "mode": "apply",
            "backup_path": str(backup_path),
            "integrity_before": report["integrity_before"],
            "integrity_after": final_report["integrity_before"],
        }
    )
    return final_report


def create_verified_invariant_backup(db_path, backup_dir=None):
    path = _validated_database_path(db_path)
    destination_dir = Path(backup_dir) if backup_dir else path.parent / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = _next_available_path(
        destination_dir,
        f"{path.stem}_before_h5_invariants_{timestamp}",
    )
    with contextlib.closing(sqlite3.connect(path)) as source:
        with contextlib.closing(sqlite3.connect(backup_path)) as destination:
            source.backup(destination)
    with _read_only_connection(backup_path) as connection:
        integrity = _integrity_result(connection)
    if integrity.lower() != "ok":
        raise InvariantMigrationBlockedError(
            f"Backup integrity check failed for {backup_path}: {integrity}"
        )
    return backup_path


def format_console_report(report):
    lines = [
        "Manual Dispatch H5 Database Invariant Migration",
        f"Database: {report['db_path']}",
        f"Mode: {report['mode']}",
        f"Integrity before: {report['integrity_before']}",
        f"Integrity after: {report.get('integrity_after') or 'not run (dry-run)'}",
        f"Backup: {report.get('backup_path') or 'not created (dry-run)'}",
        f"Conflicts: {len(report['conflicts'])}",
        f"Missing indexes: {len(report['missing_indexes'])}",
    ]
    for conflict in report["conflicts"]:
        lines.append(
            f"  CONFLICT {conflict['invariant']}: "
            f"{conflict['identity']} ({conflict['duplicate_count']} rows)"
        )
    for index_name in report["missing_indexes"]:
        lines.append(f"  PROPOSED CREATE UNIQUE INDEX {index_name}")
    return "\n".join(lines)


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        report = migrate_database_invariants(
            args.db_path,
            apply=args.apply,
            yes=args.yes,
            backup_dir=args.backup_dir,
        )
    except (InvariantMigrationBlockedError, OSError, sqlite3.Error) as error:
        if getattr(error, "report", None):
            print(format_console_report(error.report))
        print(f"Migration blocked: {error}")
        return 2
    print(format_console_report(report))
    return 0


@contextlib.contextmanager
def _read_only_database_snapshot(db_path):
    source_path = Path(db_path).resolve()
    with tempfile.TemporaryDirectory(prefix="manual-dispatch-h5-read-") as temp_dir:
        snapshot_path = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, snapshot_path)
        wal_path = Path(f"{source_path}-wal")
        if wal_path.exists():
            shutil.copy2(wal_path, Path(f"{snapshot_path}-wal"))
        yield snapshot_path


@contextlib.contextmanager
def _read_only_connection(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def _integrity_result(connection):
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return str(row[0] if row else "no integrity result")


def _raise_for_preflight_blocks(report):
    if report["integrity_before"].lower() != "ok":
        raise InvariantMigrationBlockedError(
            f"Preflight integrity check failed: {report['integrity_before']}",
            report,
        )
    if report["conflicts"]:
        raise InvariantMigrationBlockedError(
            "Duplicate conflicts must be resolved before apply.",
            report,
        )


def _validated_database_path(db_path):
    if not db_path:
        raise InvariantMigrationBlockedError("An explicit --db-path is required.")
    path = Path(db_path).resolve()
    if not path.exists() or not path.is_file():
        raise InvariantMigrationBlockedError(
            f"Database path is missing or unreadable: {path}"
        )
    return path


def _next_available_path(directory, stem):
    candidate = directory / f"{stem}.sqlite3"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}.sqlite3"
        counter += 1
    return candidate


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Audit and apply Manual Dispatch H5 service-identity constraints. "
            "Defaults to read-only dry-run."
        )
    )
    parser.add_argument("--db-path", required=True, help="Explicit SQLite path.")
    parser.add_argument(
        "--backup-dir",
        help="Optional backup destination. Defaults to <db-directory>/backups.",
    )
    parser.add_argument("--apply", action="store_true", help="Enable writes.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required non-interactive confirmation for --apply.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
