# OP SHOP Workspace Smoke Test Checklist

Use this checklist for the current independent OP SHOP Pickup workspace. It covers canonical routing, Task Pool parity, template/route management, Pickup Collection lifecycle, export, and Delivery isolation.

## Safety Rules

- Never run destructive QA against `data/manual_dispatch.sqlite3` or an office/NAS runtime database.
- Start from a SQLite backup copy under ignored `tmp/`.
- Confirm the effective DB path before opening the browser.
- Do not commit copied databases, logs, downloads, screenshots, traces, or helper scripts.

## Prepare a Safe QA Copy

Expected source test database:

```text
data/manual_dispatch_full_test.sqlite3
```

Create a WAL-safe copy with Python's SQLite backup API:

```powershell
$sourceDb = (Resolve-Path ".\data\manual_dispatch_full_test.sqlite3").Path
$qaDb = Join-Path (Resolve-Path ".\tmp").Path "manual_dispatch_full_test_opshop_qa.sqlite3"
Remove-Item -LiteralPath $qaDb -Force -ErrorAction SilentlyContinue
.\tmp\route-test-venv\Scripts\python.exe -c "import sqlite3, sys; from pathlib import Path; source = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True); target = sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()" $sourceDb $qaDb
```

The source connection is read-only. Stop immediately if `$qaDb` does not resolve under this repository's `tmp` directory.

Run migration preflight on the copy. If scoped workspace readiness requires legacy saved summaries to be migrated, apply only to the copied DB:

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path .\tmp\manual_dispatch_full_test_opshop_qa.sqlite3

.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path .\tmp\manual_dispatch_full_test_opshop_qa.sqlite3 `
  --apply --yes
```

## Start and Verify the QA Instance

`tools/start_office_trial.ps1` and `backend/db/connection.py` both honor `MANUAL_DISPATCH_DB_PATH`.

```powershell
$env:MANUAL_DISPATCH_DB_PATH = (Resolve-Path ".\tmp\manual_dispatch_full_test_opshop_qa.sqlite3").Path
$env:MANUAL_DISPATCH_SEED_DEMO_DATA = "0"
.\tools\start_office_trial.ps1 -Port 8138
```

Expected startup output includes:

```text
Database path: ...\tmp\manual_dispatch_full_test_opshop_qa.sqlite3
Open:
http://127.0.0.1:8138/frontend/
```

Verify:

- `http://127.0.0.1:8138/health` returns healthy status.
- `MANUAL_DISPATCH_DB_PATH` resolves to the `tmp` copy.
- `PRAGMA database_list` against the QA connection points to the same copied path.

Stop if any path points to the normal runtime database.

## Baseline Data

Confirm the copy contains:

- active drivers
- Regular schedules
- Oncall templates
- Countryside route groups and memberships
- OP SHOP pickup tasks
- no unexpected `GENERATED` Pickup Collections before lifecycle testing

Record the Dispatch Date and the driver/template/route names used.

## Canonical Routing

Open each route directly, refresh, and copy it into a second browser tab:

- `#opshop/task-pool/regular`
- `#opshop/task-pool/oncall`
- `#opshop/task-pool/countryside`
- `#opshop/templates`
- `#opshop/trip-summary`
- `#opshop/collections`
- `#opshop/history`

Verify legacy normalization:

| Input | Expected canonical route |
| --- | --- |
| `#opshop` | `#opshop/task-pool/regular` |
| `#opshop/task-pool` | `#opshop/task-pool/regular` |
| `#opshop/regular` | `#opshop/task-pool/regular` |
| `#opshop/oncall` | `#opshop/task-pool/oncall` |
| `#opshop/countryside` | `#opshop/task-pool/countryside` |
| malformed `#opshop/task-pool/*` | `#opshop/task-pool/regular` |

Use browser Back and Forward between all three Task Pool subtypes. Confirm the subtype and URL remain synchronized and no full-page reload occurs.

## Source Assignments and Manual Drafts

1. Confirm a source-backed current/future Regular task immediately shows its persisted driver in Current Assignee and Assigned To.
2. Confirm the same task appears in OP SHOP Trip Summary without clicking Apply and does not increase pending changes.
3. Change one assignment but do not Apply, and set another pickup explicitly to `Unassigned`.
4. Navigate Oncall -> Countryside -> browser Back to Regular.
5. Confirm both manual drafts remain, including the explicit empty selection.
6. Click `Apply Assignment Changes` and verify only changed rows persist.
7. Refresh and confirm persisted manual reassignment/Unassign remains and is not recreated from the template default.
8. Confirm past, unavailable-driver, Generated, and Saved-lock targets remain protected.

## Regular Task Operations

- View pickup detail.
- Edit allowed date/notes fields.
- Soft-delete an eligible task.
- Re-add the same schedule/date and confirm cancelled-task restore semantics.
- Confirm past and reserved tasks do not expose active destructive controls.
- Confirm closing an operation modal does not apply assignment drafts.

## Oncall Task Operations

1. Click `Add Pickup Task`.
2. Select an active Oncall template and Pickup Date.
3. Save and confirm the live task appears.
4. For a defaulted template, confirm the live task immediately has its actual assignment and no pending draft.
5. View detail, edit, assign through draft/Apply, unassign, and soft-delete; refresh after Unassign and confirm it remains Unassigned.
6. Confirm template import/create alone never creates an actual Oncall task.

## Countryside Task and Route Operations

### Task Pool

- Select an active route group, Pickup Date, and Driver.
- Assign Route Group and confirm its live tasks appear.
- View/edit an eligible Countryside task.
- Use assignment drafts and Apply.
- From Trip Summary, use route-group unassign where available and confirm all group tasks leave that driver.

### Manage Templates

- Create, rename, and soft-disable a route group.
- Add a route membership.
- Open route-template detail.
- Move the membership to another group.
- Remove the membership.
- Confirm historical tasks and collections remain intact.

## Regular and Oncall Template Management

From each originating subtype, open `Manage Templates` and verify Back returns to that subtype.

- Add/edit/soft-disable a Regular template.
- Add/edit/soft-disable an Oncall template.
- Set a default driver.
- Enable `Show disabled templates` and confirm soft-disabled rows remain visible.
- Confirm text fields support continuous typing without focus loss.

## Trip Summary

- Select the Pickup Date.
- Confirm pickups group by driver and by Regular, Oncall, and Countryside category.
- Confirm route-group context is visible for Countryside.
- Confirm no Delivery Orders, pallets, loose bags, vehicle capacity, or Delivery trip rows appear.
- Confirm Generated/Saved lock messages match current collection state.

## Generated Pickup Collection

1. Assign at least one pickup to a driver/date.
2. Generate Pickup Collection.
3. Confirm captured tasks leave editable Task Pool/Trip Summary state.
4. Refresh the browser and confirm Generated state persists.
5. Restart the QA app and confirm it still persists.
6. Open Pickup Collections and confirm the Generated snapshot rows.
7. Cancel Generated and confirm editable tasks return.

## Saved Pickup Collection and Export

1. Generate again for the same prepared driver/date.
2. Save the Generated Pickup Collection.
3. Refresh and restart the QA app.
4. Confirm Saved history and lock persist.
5. Confirm assignment/unassign/task mutation for the saved driver/date is blocked.
6. Export and inspect the workbook.
7. Confirm only OP SHOP rows are present and category/route data is sensible.
8. Keep the downloaded workbook outside git and delete it after QA.

## Saved Pickup Collection History

1. Open `#opshop/history` directly and confirm the Saved History tab is active.
2. Select the actual Pickup Date of the saved collection. Do not use its Dispatch Date as the search date.
3. Confirm every result is `SAVED` and the list shows distinct records even when their Workspace/Dispatch Dates differ.
4. Confirm each result renders the full `DAILY OP SHOP COLLECTIONS - WEIGHT SHEET` snapshot with all stored pickup rows and columns.
5. Confirm Generated, Saved, Saved by, Workspace date, Pickup date, Driver, and Status metadata are visible.
6. Confirm the only record action is `Export Excel`; History must not show Generate, Save Collection, Cancel Generated, assignment, unassignment, editing, or daily batch export.
7. Change Pickup Date rapidly twice and confirm the last selected date wins; an older response must not replace results, loading, error, or route state.
8. Select a date with no saved records and confirm the History empty state is shown without changing Task Pool, Trip Summary, or ordinary Collections state.

## Delivery Regression

- Open `#delivery/task-pool`.
- Open `#delivery/trip-summary`.
- Open `#delivery/run-sheet` and `#delivery/history` directly.
- In Delivery Saved History, select the actual Delivery Date, confirm full DAILY RUN SHEET snapshots from any Workspace/Dispatch Date, and confirm per-record Export Excel is the only action.
- Confirm Order assignment, trip grouping, vehicle controls, totals, and Run Sheet lifecycle remain available.
- Confirm OP SHOP drafts/templates/collections do not appear in Delivery state.

## Database Verification

Run against the copied QA DB only.

```sql
SELECT pickup_task_id, pickup_date, status, driver_id, trip_no
FROM opshop_pickup_tasks
WHERE pickup_task_id = :pickup_task_id;

SELECT dispatch_date, task_type, task_id, driver_id, trip_no
FROM manual_dispatch_assignments
WHERE task_type = 'OPSHOP_PICKUP'
  AND task_id = :pickup_task_id;

SELECT collection_id, dispatch_date, pickup_date, driver_id, status,
       generated_at, saved_at
FROM opshop_pickup_collections
WHERE collection_id = :collection_id;

SELECT collection_id, row_no, pickup_task_id_snapshot,
       opshop_name_snapshot, pickup_date_snapshot,
       pickup_category_snapshot, route_group_name_snapshot
FROM opshop_pickup_collection_rows
WHERE collection_id = :collection_id
ORDER BY row_no;
```

## Browser Quality

- Console errors: `0`
- Uncaught promise errors: `0`
- No accidental full-page reloads
- No stale route/date response replaces current state
- Rapid History date changes keep only the latest Delivery/Pickup Date results, loading state, and error state
- No draft reset during subtype navigation

## Cleanup

Stop the QA server, then remove local-only artifacts if no longer needed:

```powershell
Remove-Item -LiteralPath .\tmp\manual_dispatch_full_test_opshop_qa.sqlite3 -Force
Get-ChildItem -LiteralPath .\tmp\backups -Filter "manual_dispatch_full_test_opshop_qa_before_workspace_migration_*.sqlite3" |
  Remove-Item -Force
Remove-Item -LiteralPath .\tmp\opshop_workspace_real_data_qa.log -Force -ErrorAction SilentlyContinue
```

Finally run:

```powershell
git status --short
git diff --check
```

Confirm no database, export, log, screenshot, trace, or temporary QA script is staged.
