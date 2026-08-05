# H5 legacy cutover and database invariants

## Legacy endpoint inventory

The current frontend uses the scoped Delivery and OP SHOP workspace APIs. The
legacy shell is not a routable workspace. Routes are classified as follows:

- A — current frontend use: `/delivery/**`, `/opshop/**`, `/shared/**`,
  `/workspace-migration-status`, authentication routes, and current exports.
  The OP SHOP template and pickup-task routes remain current because the scoped
  pages intentionally reuse those management flows.
- B — compatibility read-only: `GET /board`, `GET /specifications`, legacy Final
  Summary GET/list/date/export routes, legacy Excel exports, and legacy Attaché
  preview. These remain available to authenticated operators.
- C — obsolete mutation: legacy `/assign`, `/unassign`, `/driver-vehicle`, legacy
  Order/Driver/Vehicle create-update-delete routes, legacy Final Summary create,
  generate, save and cancel routes, and legacy Attaché commit. These return 404
  unless `MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS=true` is explicitly set.
- D — maintenance only: `tools/migrate_legacy_final_summaries_to_workspaces.py`,
  `tools/migrate_database_invariants.py`, and the existing audit/backfill tools.

Production keeps `MANUAL_DISPATCH_ENABLE_LEGACY_MUTATIONS=false`. Enabling it
does not bypass authentication and should be limited to a planned compatibility
window. Current workspace writes are unaffected by the flag.

## Constraint design

H5 enforces these service identities after conflict audit:

- Assignment: `task_type + task_id`.
- Driver vehicle selection: `delivery_date + driver_id`.
- Vehicle exclusivity: `delivery_date + vehicle_id`.
- active Delivery Run Sheet: `delivery_date + driver_id`.
- active OP SHOP Collection: `pickup_date + driver_id`.

Dispatch Date is provenance and Task Pool context only. It is not part of a Run
Sheet, Collection, vehicle, or task-assignment service identity. Existing
application/H2 validation remains in place so concurrent conflicts continue to
return controlled API errors instead of relying only on SQLite exceptions.

Fresh databases receive the indexes during initialization. Existing databases
do not receive them during normal startup: they must pass the explicit migration
below. Duplicate rows are reported and never automatically removed.

## Migration workflow

For an existing database, the maintenance order is mandatory:

1. initialize the current schema;
2. dry-run, apply, and recheck the Legacy Workspace Migration;
3. dry-run and apply Assignment Identity Repair from its exact decision file;
4. dry-run, apply, and recheck the H5 Database Invariant Migration;
5. verify integrity, foreign keys, table counts, business state, and smoke tests.

Do not skip directly from Legacy Migration to H5. Assignment Repair treats the
current OP SHOP Task as authoritative, preserves the earliest Assignment source
`dispatch_date`, and removes Assignments for non-ASSIGNED OP SHOP Tasks. Its
dry-run is read-only and writes the complete private decision plan only to the
deployment rehearsal directory:

```powershell
python tools/repair_assignment_identity_conflicts.py `
  --db-path tmp/final-hardening-validation.sqlite3 `
  --plan-out tmp/h5-rehearsal/assignment-repair-plan.json

python tools/repair_assignment_identity_conflicts.py `
  --db-path tmp/final-hardening-validation.sqlite3 `
  --decision-file tmp/h5-rehearsal/assignment-repair-plan.json `
  --backup-dir tmp/h5-rehearsal/backups `
  --logbook-dir tmp/h5-rehearsal/logbook `
  --actor "Deployment Operator" `
  --apply --yes
```

Apply verifies the exact plan, database and row fingerprints, creates and
checks a SQLite Backup API copy, repeats all decisions under `BEGIN IMMEDIATE`,
and commits only if duplicates, integrity, and foreign-key checks all pass. It
does not create H5 indexes.

Never run development validation against the production database. For a QA
database, first run the default read-only audit:

```powershell
python tools/migrate_database_invariants.py `
  --db-path tmp/final-hardening-validation.sqlite3
```

The report prints the resolved absolute path, preflight `integrity_check`, every
conflicting identity, and proposed indexes. Dry-run does not create a backup or
write the target.

Apply requires both confirmation flags:

```powershell
python tools/migrate_database_invariants.py `
  --db-path tmp/final-hardening-validation.sqlite3 `
  --apply `
  --yes
```

Apply refuses missing schema, failed integrity, or unresolved duplicates. It
creates a uniquely named SQLite backup, verifies backup integrity, repeats the
audit under `BEGIN IMMEDIATE`, creates all indexes transactionally, verifies the
indexes and integrity, commits, then runs a final read-only audit.

## Rollback and recovery

If apply fails, the database transaction is rolled back and the verified backup
is retained. Stop the application before recovery. Preserve the failed database
for diagnosis, copy the named pre-H5 backup to a separate recovery path, run
`PRAGMA integrity_check`, and only then replace the intended database according
to the deployment runbook. Backups use a numeric suffix when a timestamp name
already exists and are never silently overwritten.
