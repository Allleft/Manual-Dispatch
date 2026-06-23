# Legacy Final Summary Workspace Migration

This runbook migrates legacy `SAVED` Final Trip Summary snapshots into the
independent workspace snapshot tables:

- Delivery rows become a saved Delivery Run Sheet.
- OP SHOP rows become a saved OP SHOP Pickup Collection.
- A mixed legacy summary creates both records with the same
  `legacy_summary_id`.

The migration is additive. It does not update or delete legacy Final Summary
headers, Delivery rows, OP SHOP rows, live orders, pickups, or assignments.

## Before You Start

1. Stop the office app and confirm no staff member is dispatching.
2. Record the deployed commit and the target SQLite path.
3. Deploy the version containing the independent workspace schema and start it
   once, or otherwise run the normal database initialization. The new snapshot
   tables must exist before migration.
4. Keep only one app or maintenance process connected to the SQLite database.
5. Run the dry-run first. Do not proceed while it reports a blocker.

Never commit the office SQLite database or generated backups to Git.

## Dry Run

Dry-run is the default and opens the database read-only. It creates no backup
and performs no database writes.

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3"
```

Review the reported counts and details for:

- saved legacy summaries;
- legacy `GENERATED` summaries;
- Delivery Run Sheets and OP SHOP Collections to create;
- records already migrated;
- conflicts;
- skipped summaries and reasons.

## Apply

Apply requires both `--apply` and `--yes`. Supplying only one flag does not
allow migration writes.

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3" `
  --apply --yes
```

Before migration writes, the tool:

1. repeats preflight checks;
2. creates a timestamped SQLite backup in `data\backups\` by default;
3. runs `PRAGMA integrity_check` against that backup and requires `ok`;
4. begins one SQLite transaction for all new snapshot writes;
5. repeats preflight under the write lock;
6. commits all records together or rolls all migration writes back.

Use `--backup-dir "<path>"` to place the backup elsewhere. The exact backup path
is printed in the apply report.

## Hard Blocks

Apply stops before creating the backup or writing migration records when:

- any legacy Final Summary still has `status = GENERATED`;
- a Delivery Run Sheet or OP SHOP Collection already owns the same
  dispatch/date/driver key without the matching `legacy_summary_id`;
- a matching marker points to another dispatch/date/driver key;
- duplicate legacy migration markers are detected;
- required workspace snapshot tables are missing.

Resolve every reported item and rerun dry-run. The tool never overwrites a
manually created workspace snapshot and never converts a legacy generated
summary to saved.

## Historical Snapshot Rules

- Only legacy summaries with `status = SAVED` are migration candidates.
- `generated_at` uses the legacy generated time, falling back to `saved_at`.
- Existing Delivery and OP SHOP snapshot fields are copied without live-data
  enrichment.
- Legacy OP SHOP rows do not contain call-before fields, so migrated rows use
  `call_before_arrival_snapshot = false` and
  `call_timing_snapshot = null`.
- A successful rerun is idempotent: matching `legacy_summary_id` records and
  their child rows are left unchanged.

## Verification

After apply:

1. confirm the report has no conflicts and shows the expected applied counts;
2. run the tool again in dry-run mode and confirm all migrated modules report
   as already migrated;
3. verify saved Delivery Run Sheet and OP SHOP Collection history through the
   independent APIs or repository checks used for the deployment;
4. verify legacy Final Summary History still loads and exports unchanged;
5. retain the timestamped backup until office acceptance is complete.

## Rollback

If office validation fails:

1. stop the app and confirm no process is writing to SQLite;
2. preserve the failed database separately for investigation;
3. restore the exact backup path printed by the migration, using the existing
   restore tool:

```powershell
.\tools\restore_sqlite_db.ps1 -BackupPath .\data\backups\<backup-file>.sqlite3
```

4. restart one app instance and validate `/health` plus legacy Final Summary
   History before reopening dispatch work.

Because the backup is created before workspace migration writes, restoring it
returns the database to the pre-migration state.
