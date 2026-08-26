import argparse
import collections
import sqlite3
import sys
from pathlib import Path


ROUTE_PLAN = {
    "MONDAY": {
        "John G": [
            "BERWICK OP SHOP",
            "GIVING IT A SECOND CHANCE",
            "PAKENHAM OP SHOP",
            "ROSE STREET OPSHOP",
            "OUR VILLAGE NETWORK (St Kilda mums)",
        ],
        "Gavin": [
            "RSPC FRANKSTON",
            "RSPCA (MORNINGTON)",
            "IMHS CHARITY OPSHOP",
        ],
    },
    "TUESDAY": {
        "John G": [
            "MUSTARD TREE OP SHOP",
            "RSPCA BAYSWATER",
            "NEW COMMUNITY OPSHOP",
            "SALVOS THRIFT SHOP BORONIA",
            "ANGLISS HOSPITAL OPSHOP",
            "RSPCA -FERNTREE GULLY",
            "ST MARTINS COMMUNITY OPSHOP",
        ],
    },
    "WEDNESDAY": {
        "John G": [
            "BERWICK OP SHOP",
            "BK2 BASIC",
            "NARRE WARREN NTH UNITING OPSHOP",
            "WARREN OP SHOP",
            "ENDEAVOUR OP SHOP",
            "OUR VILLAGE NETWORK (St Kilda mums)",
            "SPRINGVALE UNITING CHURCH OP SHOP",
            "RSPCA (BURWOOD ANIMAL SHELTER)",
        ],
        "Nonda": [
            "POSH OPP SHOPPE",
            "RSPCA CAMBERWELL",
            "RSPCA ElSTERWICK",
            "RSPCA south yarra",
            "DIAMOND VALLEY COMMUNITY SUPPORT",
            "RSPCA Highett",
            "NEW TO YOU BANSIC OP SHOP",
        ],
        "Gavin": [
            "RSPCA (TRARALGON)",
            "BUNYIP COMMUNITY OPSHOP",
            "GARFIELD COMMUNITY SHOP",
            "LRH COMMUNITY OPSHOP",
        ],
    },
    "THURSDAY": {
        "John G": [
            "BERWICK OP SHOP",
            "PAKENHAM OP SHOP",
            "GIVING IT A SECOND CHANCE",
            "OPSHOP OF THE CRCA DANDENONG",
            "AUSSIE VETERANS OP SHOP",
            "RSPCA BAYSWATER",
            "MUSTARD TREE OP SHOP",
        ],
        "Nonda": [
            "LARA ANGLICAN OP SHOP",
            "LARA UNITING CHURCH OPSHOP",
            "THE BRIDGE ANGLICAN OP SHOP",
            "GEELONG MUMS",
            "ALL SAINTS OP SHOP",
            "Eco Thrift Op shop",
            "GAWS op shop",
            "WILLIAMSTOWN OP SHOP",
        ],
        "Gavin": ["RSPCA (PEARCEDALE)"],
    },
    "FRIDAY": {
        "Nonda": [
            "POSH OPP SHOPPE",
            "POSH OPP SHOPPE",
            "AMAROO OP SHOP",
            "RSPCA (BURWOOD) animal shelter",
            "RSPCA (BURWOOD OPSHOP)",
            "RSPCA CAMBERWELL",
            "FLEMINGTON ROTARY OP SHOP",
            "VAULTED TREASURES prev. PARISH BARGAIN",
        ],
        "Lee": [
            "UNITING CHURCH OPSHOP",
            "THE PRELOVED PEDLAR OPSHOP",
            "WILDLIFE OPSHOP",
            "TYLDEN/ WOODEND UCA OP SHOP",
            "OPPORTUNITY ON HAMILTON",
            "ST PAULS ANGLICAN OPSHOP",
        ],
        "Gavin": ["BERWICK OP SHOP"],
    },
}

APPROVED_ALIASES = {
    ("MONDAY", "gavin", "rspc frankston"): (
        "OPSHOP-SCHEDULE-09EE775D3022A806",
        "RSPCA FRANKSTON",
    ),
    ("TUESDAY", "john g", "rspca -ferntree gully"): (
        "OPSHOP-SCHEDULE-58945D214FDD89F7",
        "RSPCA FERNTREE GULLY",
    ),
    ("WEDNESDAY", "john g", "endeavour op shop"): (
        "OPSHOP-SCHEDULE-5ACEC937CFC3C29B",
        "ENDEAVOUR OP SHOP/ THE ANDREWS CENTRE",
    ),
    ("WEDNESDAY", "nonda", "rspca elsterwick"): (
        "OPSHOP-SCHEDULE-F380268FCE8D2414",
        "RSPCA ELSTERNWICK",
    ),
    ("THURSDAY", "nonda", "all saints op shop"): (
        "OPSHOP-SCHEDULE-7CE2FADBB984671D",
        "Living Waters Op Shop (ALL SAINTS OP SHOP)",
    ),
    ("FRIDAY", "nonda", "rspca (burwood) animal shelter"): (
        "OPSHOP-SCHEDULE-26DEF66A026DFF7E",
        "RSPCA (BURWOOD ANIMAL SHELTER)",
    ),
}

INTENTIONALLY_UNCONFIGURED_SCHEDULE_IDS = {
    "OPSHOP-SCHEDULE-D73155D810582A05",
}


def normalize_text(value):
    return " ".join(str(value or "").strip().casefold().split())


def audit_route_sequence(db_path):
    path = _validated_database_path(db_path)
    uri = path.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return _audit_connection(connection, path)


def apply_route_sequence(db_path, *, yes=False):
    if not yes:
        raise ValueError("Explicit confirmation is required to apply route sequence")
    path = _validated_database_path(db_path)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        report = _audit_connection(connection, path)
        if not report["can_apply"]:
            raise ValueError("Route sequence mapping validation failed")
        rows_updated = 0
        for mapping in report["mappings"]:
            cursor = connection.execute(
                """
                UPDATE opshop_pickup_schedules
                SET regular_route_sequence = ?
                WHERE schedule_id = ?
                """,
                (mapping["sequence"], mapping["schedule_id"]),
            )
            rows_updated += cursor.rowcount
        if rows_updated != 65:
            raise ValueError(
                f"Expected to update 65 mapped schedules, updated {rows_updated}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {
        **report,
        "applied": True,
        "rows_updated": rows_updated,
    }


def format_report(report):
    lines = [
        f"Database: {report['db_path']}",
        f"Mode: {'APPLY' if report.get('applied') else 'DRY RUN'}",
    ]
    for mapping in report["mappings"]:
        lines.append(
            "{day} | {driver} | {sequence} | {schedule_id} | {actual_name}"
            .format(**mapping)
        )
    lines.extend(
        [
            "",
            f"Requested positions: {report['requested_positions']}",
            f"Strict matches: {report['strict_matches']}",
            f"Approved aliases: {report['approved_alias_matches']}",
            f"Resolved schedules: {report['resolved_schedules']}",
            f"Unresolved positions: {len(report['issues'])}",
            "Intentionally unconfigured: "
            + ", ".join(report["intentionally_unconfigured"] or ["None"]),
        ]
    )
    if report["issues"]:
        lines.append("Issues:")
        lines.extend(f"- {issue}" for issue in report["issues"])
    return "\n".join(lines)


def _audit_connection(connection, path):
    rows = connection.execute(
        """
        SELECT
            schedule.schedule_id,
            schedule.opshop_id,
            location.name AS opshop_name,
            location.suburb,
            schedule.run_day,
            schedule.default_driver_id,
            schedule.default_driver_alias,
            schedule.default_driver_name_snapshot,
            schedule.regular_route_sequence
        FROM opshop_pickup_schedules AS schedule
        JOIN opshop_locations AS location
            ON location.opshop_id = schedule.opshop_id
        WHERE schedule.active_flag = 1
          AND schedule.status = 'Active'
          AND schedule.run_type = 'REGULAR'
          AND COALESCE(schedule.pickup_category, 'NORMAL') = 'NORMAL'
        ORDER BY schedule.schedule_id
        """
    ).fetchall()
    rows_by_id = {row["schedule_id"]: row for row in rows}
    mappings = []
    issues = []
    used_ids = set()
    strict_matches = 0
    approved_alias_matches = 0

    for day, driver_routes in ROUTE_PLAN.items():
        for driver, requested_names in driver_routes.items():
            candidates = [
                row
                for row in rows
                if row["run_day"] == day and _driver_matches(row, driver)
            ]
            candidates_by_name = collections.defaultdict(list)
            for row in candidates:
                candidates_by_name[normalize_text(row["opshop_name"])].append(row)
            for name_rows in candidates_by_name.values():
                name_rows.sort(key=lambda row: row["schedule_id"])
            requested_counts = collections.Counter(
                normalize_text(name) for name in requested_names
            )
            occurrences = collections.Counter()

            for sequence, requested_name in enumerate(requested_names, start=1):
                normalized_name = normalize_text(requested_name)
                alias_key = (day, normalize_text(driver), normalized_name)
                match_type = "STRICT"
                if alias_key in APPROVED_ALIASES:
                    schedule_id, expected_actual_name = APPROVED_ALIASES[alias_key]
                    row = rows_by_id.get(schedule_id)
                    if not row:
                        issues.append(
                            f"{day}/{driver}/{sequence} approved alias schedule is missing: {schedule_id}"
                        )
                        continue
                    if row not in candidates:
                        issues.append(
                            f"{day}/{driver}/{sequence} approved alias is outside its route group: {schedule_id}"
                        )
                        continue
                    if normalize_text(row["opshop_name"]) != normalize_text(expected_actual_name):
                        issues.append(
                            f"{day}/{driver}/{sequence} approved alias actual name changed: {schedule_id}"
                        )
                        continue
                    match_type = "APPROVED_ALIAS"
                    approved_alias_matches += 1
                else:
                    occurrences[normalized_name] += 1
                    name_rows = candidates_by_name.get(normalized_name, [])
                    expected_count = requested_counts[normalized_name]
                    if len(name_rows) != expected_count:
                        issues.append(
                            f"{day}/{driver}/{sequence} {requested_name!r} expected "
                            f"{expected_count} exact schedule(s), found {len(name_rows)}"
                        )
                        continue
                    row = name_rows[occurrences[normalized_name] - 1]
                    schedule_id = row["schedule_id"]
                    strict_matches += 1

                if schedule_id in used_ids:
                    issues.append(
                        f"{day}/{driver}/{sequence} schedule reused: {schedule_id}"
                    )
                    continue
                used_ids.add(schedule_id)
                mappings.append(
                    {
                        "day": day,
                        "driver": driver,
                        "sequence": sequence,
                        "schedule_id": schedule_id,
                        "opshop_id": row["opshop_id"],
                        "requested_name": requested_name,
                        "actual_name": row["opshop_name"],
                        "suburb": row["suburb"],
                        "match_type": match_type,
                    }
                )

    extra_ids = set(rows_by_id) - used_ids
    unexpected_extra_ids = extra_ids - INTENTIONALLY_UNCONFIGURED_SCHEDULE_IDS
    if unexpected_extra_ids:
        issues.append(
            "Unexpected active REGULAR/NORMAL schedules: "
            + ", ".join(sorted(unexpected_extra_ids))
        )
    intentionally_unconfigured = sorted(
        extra_ids & INTENTIONALLY_UNCONFIGURED_SCHEDULE_IDS
    )
    for schedule_id in intentionally_unconfigured:
        if rows_by_id[schedule_id]["regular_route_sequence"] is not None:
            issues.append(
                f"Intentionally unconfigured schedule must remain NULL: {schedule_id}"
            )

    requested_positions = sum(
        len(names) for drivers in ROUTE_PLAN.values() for names in drivers.values()
    )
    if requested_positions != 65:
        issues.append(f"Route plan must contain 65 positions, found {requested_positions}")
    if len(mappings) != 65:
        issues.append(f"Expected 65 resolved schedules, found {len(mappings)}")
    if strict_matches != 59:
        issues.append(f"Expected 59 strict matches, found {strict_matches}")
    if approved_alias_matches != 6:
        issues.append(
            f"Expected 6 approved aliases, found {approved_alias_matches}"
        )

    return {
        "db_path": str(path),
        "applied": False,
        "can_apply": not issues,
        "requested_positions": requested_positions,
        "strict_matches": strict_matches,
        "approved_alias_matches": approved_alias_matches,
        "resolved_schedules": len(mappings),
        "mappings": mappings,
        "intentionally_unconfigured": intentionally_unconfigured,
        "issues": issues,
    }


def _driver_matches(row, driver):
    expected = normalize_text(driver)
    return expected in {
        normalize_text(row["default_driver_id"]),
        normalize_text(row["default_driver_alias"]),
        normalize_text(row["default_driver_name_snapshot"]),
    }


def _validated_database_path(db_path):
    if not db_path:
        raise ValueError("Explicit --db-path is required")
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ValueError(f"Database path is missing or unreadable: {path}")
    return path


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Audit or apply the approved REGULAR OP SHOP route sequence. "
            "Defaults to read-only dry-run."
        )
    )
    parser.add_argument("--db-path", required=True, help="Explicit SQLite database path.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply sequence values after complete validation.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive confirmation for --apply.",
    )
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.apply and not args.yes:
        confirmation = input("Type APPLY to modify the database: ")
        if confirmation != "APPLY":
            print("Apply cancelled.", file=sys.stderr)
            return 2
    try:
        report = (
            apply_route_sequence(args.db_path, yes=True)
            if args.apply
            else audit_route_sequence(args.db_path)
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Could not configure REGULAR OP SHOP route sequence: {error}", file=sys.stderr)
        return 2
    print(format_report(report))
    return 0 if report["can_apply"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
