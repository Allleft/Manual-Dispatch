"""Materialize source-backed OP SHOP template defaults and task assignments."""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.repositories.sqlite_manual_dispatch_repository import (  # noqa: E402
    SQLiteManualDispatchRepository,
)
from tools.import_oncall_opshop_pickups_to_db import (  # noqa: E402
    read_oncall_workbook_rows,
)
from tools.import_regular_opshop_pickups_to_db import (  # noqa: E402
    read_regular_workbook_rows,
)
from tools.maintenance_logbook import (  # noqa: E402
    add_maintenance_logbook_arguments,
    record_maintenance_event,
    resolve_maintenance_actor,
    safe_basename,
    sanitized_failure_metadata,
)


DRIVER_ALIAS_TO_NAME = {
    "john g": "John Georgiadis",
    "gavin": "Gavin Fynn",
    "nonda": "Epaminondas Tsatsoulis",
    "lee": "Guanlin Li",
}
BLOCKING_STATUSES = {
    "AMBIGUOUS_SOURCE",
    "AMBIGUOUS_TEMPLATE",
    "AMBIGUOUS_TASK",
    "UNKNOWN_DRIVER_ALIAS",
    "CONFLICTING_DEFAULT",
}
ADDRESS_ABBREVIATIONS = {
    "avenue": "ave",
    "boulevard": "blvd",
    "court": "ct",
    "crescent": "cres",
    "drive": "dr",
    "highway": "hwy",
    "lane": "ln",
    "parade": "pde",
    "place": "pl",
    "road": "rd",
    "street": "st",
    "terrace": "tce",
}


@dataclass(frozen=True)
class SourceRow:
    workbook: str
    sheet: str
    row_number: int
    category: str
    company: str
    suburb: str
    address: str
    run_day: str
    driver_alias: str

    @property
    def full_key(self):
        return identity_key(
            self.category,
            self.company,
            self.suburb,
            self.address,
            self.run_day,
        )

    @property
    def weak_key(self):
        return weak_identity_key(self.category, self.company, self.run_day)


def normalize_text(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def normalize_address(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"\b(unit|suite|shop)\s*(\d+)\b", r"\1 \2", text)
    tokens = normalize_text(text).split()
    normalized = [ADDRESS_ABBREVIATIONS.get(token, token) for token in tokens]
    return " ".join(normalized)


def normalize_run_day(value):
    return normalize_text(value).upper()


def identity_key(category, company, suburb, address, run_day):
    return "|".join(
        (
            str(category or "").upper(),
            normalize_text(company),
            normalize_text(suburb),
            normalize_address(address),
            normalize_run_day(run_day),
        )
    )


def weak_identity_key(category, company, run_day):
    return "|".join(
        (
            str(category or "").upper(),
            normalize_text(company),
            normalize_run_day(run_day),
        )
    )


def load_source_rows(regular_workbook, oncall_workbook):
    sources = []
    inputs = (
        ("REGULAR", Path(regular_workbook), read_regular_workbook_rows),
        ("ON_CALL", Path(oncall_workbook), read_oncall_workbook_rows),
    )
    for category, workbook, reader in inputs:
        for row in reader(workbook):
            if normalize_text(row.get("Status")) != "active":
                continue
            active_flag = normalize_text(row.get("Active_Flag"))
            if active_flag in {"0", "false", "no", "n"}:
                continue
            sources.append(
                SourceRow(
                    workbook=str(workbook),
                    sheet=str(row.get("__sheet_name") or ""),
                    row_number=int(row.get("__row_number") or 0),
                    category=category,
                    company=str(row.get("Op_Shop_Name") or "").strip(),
                    suburb=str(row.get("Suburb") or "").strip(),
                    address=str(row.get("Street_Address") or "").strip(),
                    run_day=str(row.get("__run_day") or "").strip(),
                    driver_alias=str(row.get("Assigned to") or "").strip(),
                )
            )
    return sources


@contextlib.contextmanager
def _read_only_database_snapshot(db_path):
    """Copy the database and WAL so analysis never opens the target with SQLite."""
    source_path = Path(db_path).resolve()
    with tempfile.TemporaryDirectory(prefix="manual-dispatch-read-") as temp_dir:
        snapshot_path = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, snapshot_path)
        wal_path = Path(f"{source_path}-wal")
        if wal_path.exists():
            shutil.copy2(wal_path, Path(f"{snapshot_path}-wal"))
        yield snapshot_path


def _connect_read_only(db_path):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_database_state(db_path, from_date):
    with _read_only_database_snapshot(db_path) as snapshot_path, contextlib.closing(
        _connect_read_only(snapshot_path)
    ) as connection:
        drivers = connection.execute(
            """
            SELECT driver_id, name
            FROM manual_drivers
            WHERE COALESCE(is_deleted, 0) = 0
            """
        ).fetchall()
        templates = connection.execute(
            """
            SELECT s.*, l.name AS opshop_name, l.suburb, l.street_address
            FROM opshop_pickup_schedules AS s
            JOIN opshop_locations AS l ON l.opshop_id = s.opshop_id
            WHERE s.active_flag = 1
              AND lower(s.status) = 'active'
              AND s.pickup_category = 'NORMAL'
              AND s.run_type IN ('REGULAR', 'ON_CALL')
            """
        ).fetchall()
        tasks = connection.execute(
            """
            SELECT *
            FROM opshop_pickup_tasks
            WHERE pickup_date >= ?
            """,
            (from_date,),
        ).fetchall()
        assignments = connection.execute(
            """
            SELECT *
            FROM manual_dispatch_assignments
            WHERE task_type = 'OPSHOP_PICKUP'
            ORDER BY updated_at DESC, assigned_at DESC, assignment_id DESC
            """
        ).fetchall()
        reservations = connection.execute(
            """
            SELECT c.status, r.pickup_task_id_snapshot
            FROM opshop_pickup_collections AS c
            JOIN opshop_pickup_collection_rows AS r
              ON r.collection_id = c.collection_id
            WHERE c.status IN ('GENERATED', 'SAVED')
              AND r.pickup_task_id_snapshot IS NOT NULL
            """
        ).fetchall()
    return {
        "drivers": [dict(row) for row in drivers],
        "templates": [dict(row) for row in templates],
        "tasks": [dict(row) for row in tasks],
        "assignments": [dict(row) for row in assignments],
        "reservations": [dict(row) for row in reservations],
    }


def _base_record(source, driver_name=None, driver_id=None):
    return {
        "source_workbook": source.workbook,
        "source_sheet": source.sheet,
        "source_row_number": source.row_number,
        "source_category": source.category,
        "source_company": source.company,
        "source_suburb": source.suburb,
        "source_address": source.address,
        "source_run_day": source.run_day or None,
        "source_driver_alias": source.driver_alias,
        "resolved_canonical_driver": driver_name,
        "resolved_driver_id": driver_id,
        "matching_key": source.full_key,
        "match_method": None,
        "schedule_id": None,
        "existing_template_default_driver": None,
        "proposed_template_default_driver": driver_id,
        "matched_task_ids": [],
        "matched_task_count": 0,
        "pickup_task_id": None,
        "existing_task_driver": None,
        "proposed_task_driver": driver_id,
        "result_status": None,
    }


def analyze_backfill(regular_workbook, oncall_workbook, db_path, from_date):
    sources = load_source_rows(regular_workbook, oncall_workbook)
    state = load_database_state(db_path, from_date)
    driver_by_name = {
        normalize_text(driver["name"]): driver for driver in state["drivers"]
    }
    templates_by_full = defaultdict(list)
    templates_by_weak = defaultdict(list)
    for template in state["templates"]:
        full_key = identity_key(
            template["run_type"],
            template["opshop_name"],
            template["suburb"],
            template["street_address"],
            template["run_day"],
        )
        weak_key = weak_identity_key(
            template["run_type"],
            template["opshop_name"],
            template["run_day"],
        )
        templates_by_full[full_key].append(template)
        templates_by_weak[weak_key].append(template)

    sources_by_full = defaultdict(list)
    sources_by_weak = defaultdict(list)
    for source in sources:
        sources_by_full[source.full_key].append(source)
        sources_by_weak[source.weak_key].append(source)

    assignments_by_task = {}
    for assignment in state["assignments"]:
        assignments_by_task.setdefault(assignment["task_id"], assignment)
    reservations = {
        row["pickup_task_id_snapshot"]: row["status"]
        for row in state["reservations"]
    }
    tasks_by_schedule = defaultdict(list)
    for task in state["tasks"]:
        tasks_by_schedule[task["schedule_id"]].append(task)

    records = []
    matched_templates = {}
    candidate_matches = []
    for source in sources:
        alias_key = normalize_text(source.driver_alias)
        canonical_name = DRIVER_ALIAS_TO_NAME.get(alias_key)
        driver = driver_by_name.get(normalize_text(canonical_name)) if canonical_name else None
        record = _base_record(
            source,
            canonical_name if driver else None,
            driver["driver_id"] if driver else None,
        )
        if not driver:
            record["result_status"] = "UNKNOWN_DRIVER_ALIAS"
            records.append(record)
            continue

        duplicate_sources = sources_by_full[source.full_key]
        if len(duplicate_sources) > 1:
            driver_aliases = {normalize_text(item.driver_alias) for item in duplicate_sources}
            record["result_status"] = (
                "CONFLICTING_DEFAULT" if len(driver_aliases) > 1 else "AMBIGUOUS_SOURCE"
            )
            records.append(record)
            continue

        candidates = templates_by_full[source.full_key]
        match_method = "EXACT_IDENTITY"
        if not candidates:
            weak_sources = sources_by_weak[source.weak_key]
            weak_templates = templates_by_weak[source.weak_key]
            safe_weak_templates = [
                template
                for template in weak_templates
                if (
                    normalize_text(template["suburb"]) == normalize_text(source.suburb)
                    and bool(normalize_text(source.suburb))
                )
                or (
                    normalize_address(template["street_address"])
                    == normalize_address(source.address)
                    and bool(normalize_address(source.address))
                )
            ]
            if len(weak_sources) == 1 and len(safe_weak_templates) == 1:
                candidates = safe_weak_templates
                match_method = "UNIQUE_WEAK_IDENTITY"

        if not candidates:
            record["result_status"] = "UNMATCHED_TEMPLATE"
            records.append(record)
            continue
        if len(candidates) > 1:
            record["result_status"] = "AMBIGUOUS_TEMPLATE"
            records.append(record)
            continue
        candidate_matches.append((source, driver, candidates[0], match_method, record))

    matches_by_schedule = defaultdict(list)
    for match in candidate_matches:
        matches_by_schedule[match[2]["schedule_id"]].append(match)

    for source, driver, template, match_method, record in candidate_matches:
        if len(matches_by_schedule[template["schedule_id"]]) > 1:
            record["result_status"] = "AMBIGUOUS_SOURCE"
            records.append(record)
            continue
        schedule_id = template["schedule_id"]
        matched_templates[schedule_id] = True
        record.update(
            {
                "match_method": match_method,
                "schedule_id": schedule_id,
                "existing_template_default_driver": template["default_driver_id"],
                "proposed_template_default_driver": driver["driver_id"],
            }
        )
        template_record = dict(record)
        template_record["result_status"] = (
            "ALREADY_CORRECT"
            if template["default_driver_id"] == driver["driver_id"]
            else "TEMPLATE_WILL_UPDATE"
        )
        records.append(template_record)

        schedule_tasks = tasks_by_schedule.get(schedule_id, [])
        if not schedule_tasks:
            task_record = dict(record)
            task_record["result_status"] = "UNMATCHED_TASK"
            records.append(task_record)
            continue
        task_ids = [task["pickup_task_id"] for task in schedule_tasks]
        for task in schedule_tasks:
            task_record = dict(record)
            task_record.update(
                {
                    "matched_task_ids": task_ids,
                    "matched_task_count": len(task_ids),
                    "pickup_task_id": task["pickup_task_id"],
                    "existing_task_driver": task["driver_id"],
                }
            )
            assignment = assignments_by_task.get(task["pickup_task_id"])
            existing_driver = assignment["driver_id"] if assignment else task["driver_id"]
            task_record["existing_task_driver"] = existing_driver
            if assignment or task["driver_id"]:
                task_record["result_status"] = "EXISTING_ASSIGNMENT_PRESERVED"
            elif reservations.get(task["pickup_task_id"]) == "SAVED":
                task_record["result_status"] = "SAVED_LOCK_SKIPPED"
            elif reservations.get(task["pickup_task_id"]) == "GENERATED":
                task_record["result_status"] = "GENERATED_LOCK_SKIPPED"
            elif task["status"] == "ACTIVE":
                task_record["result_status"] = "TASK_WILL_ASSIGN"
            elif task["status"] == "ASSIGNED":
                task_record["result_status"] = "AMBIGUOUS_TASK"
            else:
                task_record["result_status"] = "UNMATCHED_TASK"
            records.append(task_record)

    for template in state["templates"]:
        if template["schedule_id"] in matched_templates:
            continue
        records.append(
            {
                "source_workbook": None,
                "source_sheet": None,
                "source_row_number": None,
                "source_category": template["run_type"],
                "source_company": template["opshop_name"],
                "source_suburb": template["suburb"],
                "source_address": template["street_address"],
                "source_run_day": template["run_day"],
                "source_driver_alias": None,
                "resolved_canonical_driver": None,
                "resolved_driver_id": None,
                "matching_key": identity_key(
                    template["run_type"],
                    template["opshop_name"],
                    template["suburb"],
                    template["street_address"],
                    template["run_day"],
                ),
                "match_method": None,
                "schedule_id": template["schedule_id"],
                "existing_template_default_driver": template["default_driver_id"],
                "proposed_template_default_driver": None,
                "matched_task_ids": [],
                "matched_task_count": 0,
                "pickup_task_id": None,
                "existing_task_driver": None,
                "proposed_task_driver": None,
                "result_status": "UNMATCHED_SOURCE",
            }
        )

    status_counts = Counter(record["result_status"] for record in records)
    summary = {
        "regular_source_rows": sum(source.category == "REGULAR" for source in sources),
        "oncall_source_rows": sum(source.category == "ON_CALL" for source in sources),
        "matched_templates": len(matched_templates),
        "templates_to_update": status_counts["TEMPLATE_WILL_UPDATE"],
        "tasks_to_assign": status_counts["TASK_WILL_ASSIGN"],
        "already_correct": status_counts["ALREADY_CORRECT"],
        "existing_assignments_preserved": status_counts[
            "EXISTING_ASSIGNMENT_PRESERVED"
        ],
        "unmatched": sum(
            status_counts[status]
            for status in ("UNMATCHED_SOURCE", "UNMATCHED_TEMPLATE", "UNMATCHED_TASK")
        ),
        "ambiguous": sum(
            status_counts[status]
            for status in ("AMBIGUOUS_SOURCE", "AMBIGUOUS_TEMPLATE", "AMBIGUOUS_TASK")
        ),
        "generated_lock_skipped": status_counts["GENERATED_LOCK_SKIPPED"],
        "saved_lock_skipped": status_counts["SAVED_LOCK_SKIPPED"],
        "conflicts": status_counts["CONFLICTING_DEFAULT"],
        "unknown_driver_aliases": status_counts["UNKNOWN_DRIVER_ALIAS"],
        "blocking_findings": sum(status_counts[status] for status in BLOCKING_STATUSES),
    }
    return {"summary": summary, "records": records}


def backup_database(db_path):
    db_path = Path(db_path)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_before_opshop_driver_backfill_{stamp}.sqlite3"
    source = sqlite3.connect(db_path)
    try:
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()
    return backup_path


def apply_backfill(analysis, db_path):
    if analysis["summary"]["blocking_findings"]:
        raise ValueError("Backfill blocked by ambiguous, conflicting, or unknown source rows")
    backup_path = backup_database(db_path)
    repository = SQLiteManualDispatchRepository(db_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    for record in analysis["records"]:
        if record["result_status"] != "TEMPLATE_WILL_UPDATE":
            continue
        schedule = repository.get_opshop_pickup_schedule(record["schedule_id"])
        driver = repository.get_driver(record["resolved_driver_id"])
        repository.upsert_opshop_pickup_schedule(
            replace(
                schedule,
                default_driver_id=driver.driver_id,
                default_driver_alias=record["source_driver_alias"],
                default_driver_name_snapshot=driver.name,
                updated_at=timestamp,
            )
        )

    tasks_by_dispatch_date = defaultdict(list)
    for record in analysis["records"]:
        if record["result_status"] != "TASK_WILL_ASSIGN":
            continue
        task = repository.get_opshop_pickup_task(record["pickup_task_id"])
        tasks_by_dispatch_date[task.dispatch_date or task.pickup_date].append(
            replace(
                task,
                status="ASSIGNED",
                driver_id=record["resolved_driver_id"],
                trip_no="trip1",
                updated_at=timestamp,
            )
        )
    for dispatch_date, tasks in tasks_by_dispatch_date.items():
        repository.apply_opshop_pickup_assignment_batch(dispatch_date, tasks)
    return backup_path


def write_report(report_path, analysis, mode, backup_path=None):
    payload = {
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backup_path": str(backup_path) if backup_path else None,
        **analysis,
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_summary(summary):
    labels = (
        ("Regular source rows", "regular_source_rows"),
        ("Oncall source rows", "oncall_source_rows"),
        ("Matched templates", "matched_templates"),
        ("Templates to update", "templates_to_update"),
        ("Tasks to assign", "tasks_to_assign"),
        ("Already correct", "already_correct"),
        ("Existing assignments preserved", "existing_assignments_preserved"),
        ("Unmatched", "unmatched"),
        ("Ambiguous", "ambiguous"),
        ("Generated lock skipped", "generated_lock_skipped"),
        ("Saved lock skipped", "saved_lock_skipped"),
        ("Conflicts", "conflicts"),
        ("Unknown driver aliases", "unknown_driver_aliases"),
    )
    for label, key in labels:
        print(f"{label}: {summary[key]}")


def _backfill_common_metadata(args, mode, *, backup_path=None, report_created=False):
    return {
        "mode": mode,
        "database_filename": safe_basename(args.db_path),
        "regular_workbook_filename": safe_basename(args.regular_workbook),
        "oncall_workbook_filename": safe_basename(args.oncall_workbook),
        "report_filename": safe_basename(args.report_path),
        "from_date": args.from_date,
        "backup_created": bool(backup_path),
        "backup_filename": safe_basename(backup_path),
        "report_created": bool(report_created),
    }


def _backfill_success_metadata(
    args,
    summary,
    mode,
    *,
    backup_path=None,
    report_created=False,
):
    metadata = _backfill_common_metadata(
        args,
        mode,
        backup_path=backup_path,
        report_created=report_created,
    )
    if mode == "dry-run":
        for key in (
            "regular_source_rows",
            "oncall_source_rows",
            "matched_templates",
            "templates_to_update",
            "tasks_to_assign",
            "already_correct",
            "existing_assignments_preserved",
            "unmatched",
            "ambiguous",
            "generated_lock_skipped",
            "saved_lock_skipped",
            "conflicts",
            "unknown_driver_aliases",
            "blocking_findings",
        ):
            metadata[key] = int(summary.get(key, 0) or 0)
    else:
        metadata.update(
            {
                "regular_source_rows": int(summary.get("regular_source_rows", 0) or 0),
                "oncall_source_rows": int(summary.get("oncall_source_rows", 0) or 0),
                "matched_templates": int(summary.get("matched_templates", 0) or 0),
                "templates_updated": int(summary.get("templates_to_update", 0) or 0),
                "tasks_assigned": int(summary.get("tasks_to_assign", 0) or 0),
                "already_correct": int(summary.get("already_correct", 0) or 0),
                "existing_assignments_preserved": int(
                    summary.get("existing_assignments_preserved", 0) or 0
                ),
                "generated_lock_skipped": int(
                    summary.get("generated_lock_skipped", 0) or 0
                ),
                "saved_lock_skipped": int(
                    summary.get("saved_lock_skipped", 0) or 0
                ),
                "blocking_findings": int(
                    summary.get("blocking_findings", 0) or 0
                ),
            }
        )
    return metadata


def _backfill_failure_metadata(
    args,
    mode,
    error,
    phase,
    *,
    summary=None,
    backup_path=None,
    report_created=False,
):
    metadata = _backfill_common_metadata(
        args,
        mode,
        backup_path=backup_path,
        report_created=report_created,
    )
    if summary:
        for key in (
            "blocking_findings",
            "ambiguous",
            "conflicts",
            "unknown_driver_aliases",
        ):
            metadata[key] = int(summary.get(key, 0) or 0)
    metadata.update(sanitized_failure_metadata(error, phase))
    return metadata


def _record_backfill_event(args, actor, action, result, summary, metadata):
    return record_maintenance_event(
        action=action,
        result=result,
        workspace="OPSHOP",
        actor=actor,
        entity_type="OPSHOP_SOURCE_DRIVER_BACKFILL",
        entity_id=args.from_date,
        summary=summary,
        metadata=metadata,
        logbook_dir=args.logbook_dir,
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regular-workbook", required=True)
    parser.add_argument("--oncall-workbook", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--from-date", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report-path", required=True)
    add_maintenance_logbook_arguments(parser)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    actor = resolve_maintenance_actor(args.actor)
    mode = "dry-run" if args.dry_run else "apply"
    action = (
        "SOURCE_DRIVER_BACKFILL_DRY_RUN"
        if args.dry_run
        else "SOURCE_DRIVER_BACKFILL_APPLIED"
    )
    analysis = None
    backup_path = None
    report_created = False
    event_recorded = False
    phase = "analysis"

    try:
        analysis = analyze_backfill(
            args.regular_workbook,
            args.oncall_workbook,
            args.db_path,
            args.from_date,
        )
        summary = analysis["summary"]
        if args.apply and summary["blocking_findings"]:
            phase = "report_write"
            write_report(args.report_path, analysis, mode)
            report_created = True
            print_summary(summary)
            metadata = _backfill_common_metadata(
                args,
                mode,
                report_created=True,
            )
            for key in (
                "blocking_findings",
                "ambiguous",
                "conflicts",
                "unknown_driver_aliases",
            ):
                metadata[key] = int(summary.get(key, 0) or 0)
            metadata.update(
                {
                    "failure_phase": "preflight",
                    "error_type": "BackfillBlocked",
                }
            )
            _record_backfill_event(
                args,
                actor,
                action,
                "FAILED",
                "OP SHOP source-driver backfill apply was blocked by unresolved findings.",
                metadata,
            )
            event_recorded = True
            raise SystemExit("Apply refused because blocking findings remain")

        if args.apply:
            phase = "database_apply"
            backup_path = apply_backfill(analysis, args.db_path)

        phase = "report_write"
        write_report(args.report_path, analysis, mode, backup_path)
        report_created = True
        phase = "console_output"
        print_summary(summary)

        if args.dry_run:
            has_blockers = int(summary.get("blocking_findings", 0) or 0) > 0
            result = "PARTIAL" if has_blockers else "SUCCESS"
            event_summary = (
                "OP SHOP source-driver backfill dry-run completed with blocking "
                "findings requiring review."
                if has_blockers
                else (
                    "OP SHOP source-driver backfill dry-run completed with no "
                    "blocking findings."
                )
            )
        else:
            result = "SUCCESS"
            event_summary = (
                "OP SHOP source-driver backfill was applied: "
                f"{summary['templates_to_update']} template defaults updated and "
                f"{summary['tasks_to_assign']} Pickup Tasks assigned."
            )

        _record_backfill_event(
            args,
            actor,
            action,
            result,
            event_summary,
            _backfill_success_metadata(
                args,
                summary,
                mode,
                backup_path=backup_path,
                report_created=report_created,
            ),
        )
        event_recorded = True
        return 0
    except Exception as error:
        if not event_recorded:
            summary = analysis["summary"] if analysis else None
            _record_backfill_event(
                args,
                actor,
                action,
                "FAILED",
                (
                    "OP SHOP source-driver backfill apply failed."
                    if args.apply
                    else "OP SHOP source-driver backfill dry-run failed."
                ),
                _backfill_failure_metadata(
                    args,
                    mode,
                    error,
                    phase,
                    summary=summary,
                    backup_path=backup_path,
                    report_created=report_created,
                ),
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
