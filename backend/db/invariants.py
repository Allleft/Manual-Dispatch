INVARIANT_INDEX_DEFINITIONS = (
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
    for definition in INVARIANT_INDEX_DEFINITIONS:
        if definition["table"] in missing_tables:
            continue
        conflicts.extend(_duplicate_conflicts(connection, definition))
    return {
        "conflicts": conflicts,
        "missing_indexes": missing_invariant_indexes(connection),
    }


def create_invariant_indexes(connection):
    for definition in INVARIANT_INDEX_DEFINITIONS:
        columns = ", ".join(definition["columns"])
        where_clause = (
            f" WHERE {definition['where']}" if definition["where"] else ""
        )
        connection.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {definition['name']} "
            f"ON {definition['table']} ({columns}){where_clause}"
        )


def missing_invariant_indexes(connection):
    existing = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    return [
        definition["name"]
        for definition in INVARIANT_INDEX_DEFINITIONS
        if definition["name"] not in existing
    ]


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
