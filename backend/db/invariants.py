LEGACY_INVARIANT_INDEX_DEFINITIONS = (
    {
        "name": "idx_manual_dispatch_assignments_task_identity",
        "table": "manual_dispatch_assignments",
        "columns": ("task_type", "task_id"),
        "where": None,
    },
    {
        "name": "idx_manual_driver_vehicle_driver_identity",
        "table": "manual_driver_vehicle_assignments",
        "columns": ("delivery_date", "driver_id"),
        "where": None,
    },
    {
        "name": "idx_manual_driver_vehicle_vehicle_identity",
        "table": "manual_driver_vehicle_assignments",
        "columns": ("delivery_date", "vehicle_id"),
        "where": None,
    },
    {
        "name": "idx_delivery_run_sheets_active_identity",
        "table": "delivery_run_sheets",
        "columns": ("delivery_date", "driver_id"),
        "where": "status IN ('GENERATED', 'SAVED')",
    },
    {
        "name": "idx_opshop_pickup_collections_active_identity",
        "table": "opshop_pickup_collections",
        "columns": ("pickup_date", "driver_id"),
        "where": "status IN ('GENERATED', 'SAVED')",
    },
)

INVARIANT_INDEX_DEFINITIONS = (
    LEGACY_INVARIANT_INDEX_DEFINITIONS[0],
    {
        **LEGACY_INVARIANT_INDEX_DEFINITIONS[1],
        "where": "trip_no IS NULL",
    },
    {
        **LEGACY_INVARIANT_INDEX_DEFINITIONS[2],
        "where": "trip_no IS NULL",
    },
    {
        **LEGACY_INVARIANT_INDEX_DEFINITIONS[3],
        "where": "trip_no IS NULL",
    },
    LEGACY_INVARIANT_INDEX_DEFINITIONS[4],
    {
        "name": "idx_manual_driver_vehicle_trip_driver_identity",
        "table": "manual_driver_vehicle_assignments",
        "columns": ("delivery_date", "driver_id", "trip_no"),
        "where": "trip_no IS NOT NULL",
    },
    {
        "name": "idx_manual_driver_vehicle_trip_vehicle_identity",
        "table": "manual_driver_vehicle_assignments",
        "columns": ("delivery_date", "vehicle_id", "trip_no"),
        "where": "trip_no IS NOT NULL",
    },
    {
        "name": "idx_delivery_run_sheets_trip_identity",
        "table": "delivery_run_sheets",
        "columns": ("delivery_date", "driver_id", "trip_no"),
        "where": "trip_no IS NOT NULL",
    },
)

REQUIRED_INVARIANT_TABLES = {
    definition["table"] for definition in INVARIANT_INDEX_DEFINITIONS
}


def audit_database_invariants(connection):
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing_tables = sorted(REQUIRED_INVARIANT_TABLES - existing_tables)
    conflicts = []
    conflicts.extend(
        {
            "invariant": "required_schema",
            "table": table_name,
            "identity": {},
            "duplicate_count": 0,
        }
        for table_name in missing_tables
    )
    for definition in invariant_index_definitions(connection):
        if definition["table"] in missing_tables:
            continue
        columns = table_columns(connection, definition["table"])
        if not set(definition["columns"]).issubset(columns):
            conflicts.append({
                "invariant": "required_schema",
                "table": definition["table"],
                "identity": {},
                "duplicate_count": 0,
            })
            continue
        conflicts.extend(_duplicate_conflicts(connection, definition))
    if "trip_no" in table_columns(connection, "delivery_run_sheets"):
        overlaps = connection.execute(
            """
            SELECT delivery_date, driver_id, COUNT(*) AS duplicate_count
            FROM delivery_run_sheets
            GROUP BY delivery_date, driver_id
            HAVING SUM(trip_no IS NULL) > 0 AND SUM(trip_no IS NOT NULL) > 0
            """
        ).fetchall()
        conflicts.extend({
            "invariant": "delivery_run_sheet_scope_overlap",
            "table": "delivery_run_sheets",
            "identity": {"delivery_date": row["delivery_date"], "driver_id": row["driver_id"]},
            "duplicate_count": row["duplicate_count"],
        } for row in overlaps)
    return {
        "conflicts": conflicts,
        "missing_indexes": missing_invariant_indexes(connection),
    }


def create_invariant_indexes(connection):
    for definition in invariant_index_definitions(connection):
        columns = ", ".join(definition["columns"])
        where_clause = (
            f" WHERE {definition['where']}" if definition["where"] else ""
        )
        connection.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {definition['name']} "
            f"ON {definition['table']} ({columns}){where_clause}"
        )


def missing_invariant_indexes(connection):
    return [
        definition["name"]
        for definition in invariant_index_definitions(connection)
        if not index_matches_definition(connection, definition)
    ]


def table_columns(connection, table):
    return {row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def invariant_index_definitions(connection):
    if all("trip_no" in table_columns(connection, table) for table in (
        "manual_driver_vehicle_assignments", "delivery_run_sheets"
    )):
        return INVARIANT_INDEX_DEFINITIONS
    return LEGACY_INVARIANT_INDEX_DEFINITIONS


def index_matches_definition(connection, definition):
    import re

    name = definition["name"]
    row = next((row for row in connection.execute(
        f'PRAGMA index_list("{definition["table"]}")'
    ) if row["name"] == name), None)
    if row is None or not row["unique"]:
        return False
    columns = tuple(row["name"] for row in connection.execute(f'PRAGMA index_info("{name}")'))
    if columns != definition["columns"]:
        return False
    keys = [row for row in connection.execute(f'PRAGMA index_xinfo("{name}")') if row["key"]]
    if any(row["desc"] or row["coll"] != "BINARY" for row in keys):
        return False
    sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
    ).fetchone()
    match = re.search(r"\bWHERE\s+(.+)$", (sql_row["sql"] or "") if sql_row else "", re.I | re.S)
    predicate = match.group(1).strip().rstrip(";") if match else None
    normalize = lambda value: re.sub(r"\s+", "", value or "").casefold()
    return bool(row["partial"]) == bool(definition["where"]) and normalize(predicate) == normalize(definition["where"])


def _duplicate_conflicts(connection, definition):
    columns = definition["columns"]
    select_columns = ", ".join(columns)
    where_clause = f" WHERE {definition['where']}" if definition["where"] else ""
    rows = connection.execute(
        f"SELECT {select_columns}, COUNT(*) AS duplicate_count "
        f"FROM {definition['table']}{where_clause} "
        f"GROUP BY {select_columns} HAVING COUNT(*) > 1 "
        f"ORDER BY {select_columns}"
    ).fetchall()
    return [
        {
            "invariant": definition["name"],
            "table": definition["table"],
            "identity": {column: row[column] for column in columns},
            "duplicate_count": row["duplicate_count"],
        }
        for row in rows
    ]
