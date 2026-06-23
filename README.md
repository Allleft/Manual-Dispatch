# Manual Dispatch Board

## Project Overview

Manual Dispatch Board is a FastAPI, SQLite, and vanilla JavaScript application for office staff to manually coordinate Delivery Orders and OP SHOP pickup work with drivers.

The board is a manual office workflow:

- The frontend is still a single-page board, now split into three hash-based workflow views: `#task-pool`, `#trip-summary`, and `#final-summary`.
- Staff move through `Task Pool -> Trip Summary -> Final Trip Summary` without changing backend workflow or opening separate HTML pages.
- Dispatch Date identifies the operational dispatch session.
- Driver Summary Delivery Date identifies which delivery or pickup day is being reviewed.
- Delivery Orders and OP SHOP pickups share manual driver assignment infrastructure, but remain separate task types and separate summary sections.
- Final Trip Summary stores Delivery rows and OP SHOP pickup rows as separate snapshot sections.

The current branch includes Regular, Oncall, and Countryside OP SHOP pickup workflows, OP SHOP template management, generated/saved Final Summary locking, saved History re-export, and OP SHOP saved-lock audit/backfill tools.

### Explicit Non-Goals

This application does not implement:

- auto-dispatch
- CP-SAT or other optimization planning
- route optimization or route sequencing
- ETA calculation
- geocoding or Google Maps integration
- automatic driver or vehicle selection
- automatic trip planning
- capacity or zone blocking

## Quick Start

These examples use Windows PowerShell from the repository root.

### Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

For local password reset testing, set an admin reset code before startup:

```powershell
$env:MANUAL_DISPATCH_ADMIN_RESET_CODE="replace-with-your-local-admin-reset-code"
```

### Developer Startup

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

- Frontend: `http://127.0.0.1:8000/frontend/`
- Health check: `http://127.0.0.1:8000/health`

### Office Trial Startup

```powershell
.\tools\start_office_trial.ps1
```

Open:

- Frontend: `http://127.0.0.1:8130/frontend/`
- Health check: `http://127.0.0.1:8130/health`

### Local Database Override

The default runtime database is `data/manual_dispatch.sqlite3`. To use a safe local or temporary database:

```powershell
$env:MANUAL_DISPATCH_DB_PATH="data\manual_dispatch_test.sqlite3"
```

For office-style smoke testing with a prepared local DB:

```powershell
$env:MANUAL_DISPATCH_DB_PATH="data\manual_dispatch_full_test.sqlite3"
$env:MANUAL_DISPATCH_SEED_DEMO_DATA="0"
```

Never commit runtime SQLite databases, backups, `.env` files, generated outputs, or real office workbooks.

## Main Workflow

1. Log in.
2. Choose the Dispatch Date for the operational board session.
3. Use the workflow navigation tabs to switch between `Task Pool`, `Trip Summary`, and `Final Trip Summary`.
4. In `Task Pool` (`/frontend/#task-pool`), review unassigned Delivery Orders and use the OP SHOP PICKUP area for Regular, Oncall, Countryside, and template management work.
5. Assign Delivery Orders manually to a Driver and `trip1` or `trip2`.
6. Assign OP SHOP pickups manually in their list modals, then close the modal to apply visible pickup assignments.
7. In `Trip Summary` (`/frontend/#trip-summary`), select the Driver Summary Delivery Date, choose the vehicle for the driver/date combination, review Delivery trips and OP SHOP PICKUPS, then Generate Final Trip Summary.
8. Successful Generate creates a `GENERATED` snapshot and moves the browser to `Final Trip Summary` (`/frontend/#final-summary`) for review.
9. If the generated snapshot is wrong, use `Cancel Generated Summary`; the board returns to `Trip Summary` for editable work.
10. If the generated snapshot is correct, use Save and Export to convert it to `SAVED`, export the workbook, and hard-lock that driver/date.
11. Later, use Final Summary History `Re-export` for saved summaries when the Excel file is needed again.

The three views are frontend-only navigation. They do not change backend routes, assignment APIs, OP SHOP locking, Final Summary snapshot semantics, or Excel export behavior.

## Delivery Order Workflow

| Function | Current Behavior |
| --- | --- |
| Task Pool | Shows active unassigned Delivery Orders; search, urgency, and Delivery Date filters change display only. |
| Add / Edit / Cancel | Active Orders can be added and edited; Cancel is a soft removal from normal workflow. |
| Product Details | Orders may contain product lines with Pallets, Bags, or mixed pallet + loose-bag loads. |
| Assign / Unassign | Staff manually assign an Order to a Driver and `trip1` or `trip2`, or return it to the Task Pool. |
| Delivery Date | Driver Summary filters assigned Delivery Orders by the selected Delivery Date. |
| Trip Display | Delivery Orders remain inside Driver Summary `Trip 1` and `Trip 2` sections. |
| Generated Lock | Delivery Orders captured by a `GENERATED` Final Summary are removed from editable Driver Summary / Task Pool state until cancelled or saved. |
| Saved Lock | A `SAVED` Final Summary blocks further Delivery assignment and vehicle changes for that driver/date. |
| Totals | Pallet, loose-bag, and capacity totals count Delivery Orders only. |

Delivery assignment remains entirely manual. OP SHOP work is not stored as a Delivery Order and does not change Delivery totals.

### Attache Invoice PDF Import

`Import Attache Invoices` in the Delivery Orders area lets office staff upload one or more text-based Attache invoice PDFs, preview parsed Delivery Orders, correct fields, and then confirm import.

- Preview is required before import; PDF upload does not write to the database by itself.
- The preview highlights duplicate invoice numbers already present in Manual Dispatch and leaves duplicate rows unselected / not importable by default.
- Staff can edit delivery date, time window, phone, address, suburb, postcode, pallet quantity, loose-bag quantity, and notes before confirming.
- Confirm Import creates standard Delivery Orders through the same `CreateOrderRequest` path as manual entry, so imported Orders appear in the Task Pool like normal Delivery Orders.
- Product lines use the existing `product_name`, `quantity`, and `unit` fields only; invoice accounting lines, GST, totals, and payment details are not imported as delivery product lines.
- PDF import does not change OP SHOP workflows, Driver Summary OP SHOP sections, generated/saved Final Summary locking, or Final Summary Excel semantics.

## OP SHOP Pickup Workflow

OP SHOP PICKUP is a distinct manual task type. The Task Pool OP SHOP PICKUP section currently shows:

- `Manage OP SHOP Templates`
- `Regular OP SHOP Pickup List`
- `Oncall OP SHOP Pickup List`
- `Countryside OP SHOP Pickup List`

OP SHOP pickups:

- use `task_type = OPSHOP_PICKUP`
- display in Driver Summary under a separate `OP SHOP PICKUPS` section
- never enter Delivery `Trip 1` / `Trip 2` rows
- never affect Delivery pallet, loose-bag, or vehicle capacity totals
- are captured in Final Trip Summary under a separate `OP SHOP PICKUPS` snapshot section

### Template Management

`Manage OP SHOP Templates` is the office-facing entry point for adding, editing, and disabling pickup templates.

| Template Type | Purpose | Actual Pickup Task Creation |
| --- | --- | --- |
| `REGULAR` | Schedule source for the Regular list and its visible pickup week. | Visible regular tasks are ensured from active schedules. |
| `ON_CALL` | Candidate source for office-requested Oncall pickups. | No task is created until staff use Add Pickup Task. |
| `ON_CALL` + `COUNTRYSIDE` | Route-group membership templates for Countryside OP SHOP pickups. | Route group assignment creates actual dated pickup tasks. |

Template rules:

- Regular templates require a weekday.
- Oncall templates may have a weekday or no fixed day.
- Default driver data may be maintained on the template.
- Disable is a soft disable: `status = On_Hold` and `active_flag = false`.
- Disabling a template does not delete existing pickup tasks, assignments already captured in history, or saved Final Summaries.
- An identity-field edit can create/use a new deterministic active schedule while old task references remain historically valid.

### Regular OP SHOP Pickup List

- The list is generated from active `REGULAR` schedules.
- Monday through Thursday Dispatch Dates show the current Monday-Friday pickup week.
- Friday Dispatch Dates show Friday today plus the following Monday-Friday.
- Saturday and Sunday Dispatch Dates show the next Monday-Friday.
- The source schedule weekday determines the pickup day. Frequency text does not expand one Regular source row into extra weekdays in this list flow.
- Date groups before the selected Dispatch Date are collapsed by default; today/future groups are expanded and can be toggled manually.
- Staff can add, edit, soft-delete, and choose the assigned driver for visible tasks unless the pickup is generated/saved locked or a past pickup date.
- Closing the list applies selected assignments using `trip1` internally for persistence compatibility.
- A cancelled task can be restored by re-adding the same schedule and pickup date; active or assigned duplicates remain prevented.

### Oncall OP SHOP Pickup List

- The list is request-driven and starts empty until an actual Oncall task is added.
- Add Pickup Task uses active `ON_CALL` templates.
- The Add Pickup Task form includes a searchable template filter.
- Template search matches OP SHOP/company name, suburb, and street address.
- Search is case-insensitive and whitespace-normalized.
- If the selected template no longer matches the search, the selected `schedule_id` is cleared.
- Search clears when opening Add, cancelling, saving successfully, or closing the modal.
- Weekday templates can provide a matching default pickup date; no-fixed-day templates require staff to select a pickup date.
- Staff can edit, soft-delete, and select a driver for created Oncall tasks unless generated/saved locked.
- Closing the list applies selected assignments using `trip1` internally.
- Importing or creating an Oncall template never automatically creates an actual pickup task.

### Countryside OP SHOP Pickup List

Countryside pickup is an OP SHOP Oncall subcategory, not a new Delivery workflow or task type.

| Field | Countryside Value |
| --- | --- |
| `task_type` | `OPSHOP_PICKUP` |
| `run_type` | `ON_CALL` |
| `pickup_category` | `COUNTRYSIDE` |

- Each Countryside workbook sheet represents one route group.
- A single OP SHOP location can belong to multiple route groups.
- Duplicate addresses are expected; they reuse the same `opshop_locations` row and create separate route membership schedules.
- Countryside route groups and membership schedules are template/source data only. Importing them does not create actual pickup tasks.
- The Countryside Pickup List is also the route management entry point. There is no separate Task Pool button for managing Countryside routes.
- Inside the Countryside list, staff can create, rename, and soft-disable route groups; add OP SHOP locations to a selected route; move a route membership to another route; or remove a membership from a route.
- Route membership changes are soft schedule/template changes. They do not delete OP SHOP locations, existing pickup tasks, assignments already captured in history, or saved Final Summary snapshots.
- `Assign Route Group` creates or restores one `OPSHOP_PICKUP` task per active route template for the selected pickup date, assigns those tasks to the selected driver, and uses `trip1` for compatibility with the OP SHOP assignment model.
- Assigned Countryside pickups appear in Driver Summary under `OP SHOP PICKUPS`, with Countryside/route group context preserved for snapshots and exports.

### Driver Summary and Lock Boundary

- Assigned OP SHOP pickups appear in a driver-level `OP SHOP PICKUPS` section, not inside Delivery `Trip 1` or `Trip 2`.
- Visibility is filtered by the pickup date matching the selected Driver Summary Delivery Date.
- OP SHOP pickups do not affect Delivery pallet, loose-bag, or capacity totals.
- Generate captures displayed OP SHOP pickups into a persisted `GENERATED` Final Summary snapshot.
- Generated OP SHOP pickups are hidden/locked from editable Driver Summary while the generated snapshot exists, but remain traceable through the OP SHOP pickup task and snapshot data.
- Cancelling a generated summary removes the generated lock and restores editable work for that generated summary.
- Once Save and Export saves a Final Summary for `dispatch_date + delivery_date + driver_id`, that driver/date is hard-locked against Delivery assignment, OP SHOP assignment, and vehicle changes.
- Saved OP SHOP assignments display as locked in OP SHOP lists with Final Summary saved messaging.

### OP SHOP Pickup Run Sheet Export

The backend still provides an independent OP SHOP pickup run sheet export endpoint:

```text
GET /api/manual-dispatch/opshop-pickups/export-excel?dispatch_date=YYYY-MM-DD
```

This export is independent from Final Trip Summary workbooks. It includes OP SHOP pickup operational data and keeps pickup categories separate, including Countryside route group context when present.

The current Task Pool UI does not show a dedicated run sheet export button. Use this endpoint only through an approved office workflow or tool path.

## Final Trip Summary

Final Trip Summary is a historical snapshot for a driver, Dispatch Date, and Driver Summary Delivery Date.

| Scenario | Snapshot Content | Totals |
| --- | --- | --- |
| Delivery-only | Delivery Orders in Trip 1 / Trip 2. | Delivery totals only. |
| OP SHOP-only | Separate `OP SHOP PICKUPS` section; no Delivery rows. | Zero pallets and zero loose bags. |
| Mixed | Delivery rows in Trip 1 / Trip 2 plus a separate `OP SHOP PICKUPS` section. | Delivery totals only. |

### Generate / GENERATED Snapshot

- Generate persists a `status = GENERATED` Final Summary snapshot.
- `GENERATED` summaries are restored after browser refresh/restart.
- Delivery rows remain in `Trip 1` / `Trip 2`.
- OP SHOP rows are captured only in the independent `OP SHOP PICKUPS` snapshot section.
- The OP SHOP snapshot stores category context (`NORMAL` or `COUNTRYSIDE`), `run_type`, and route group id/name when applicable.
- Delivery Orders captured by Generate are removed from editable Driver Summary / Task Pool state according to the current workflow.
- OP SHOP pickups captured by Generate remain traceable and locked as generated.
- `GENERATED` summaries should not appear as normal History items and should not show History `Re-export`.

### Cancel Generated Summary

- `Cancel Generated Summary` is available only for `GENERATED` summaries.
- Cancelling restores Delivery editable assignment state for that generated summary and removes generated locks.
- Cancelling a generated summary does not change saved summaries.
- `SAVED` summaries cannot be cancelled.

### Save and Export / SAVED Hard Lock

- Save and Export converts a generated summary to `status = SAVED`.
- Save and Export records the logged-in operator and exports the Final Summary workbook.
- Saved history loads stored snapshot rows rather than current mutable task data.
- Duplicate saves for the same driver, Dispatch Date, and Delivery Date are rejected.
- After save, that driver/date cannot receive new Delivery Orders, Regular pickups, Oncall pickups, Countryside pickups, or vehicle changes.

### Final Summary History Re-export

- Final Summary History shows `SAVED` summaries.
- `Re-export` is available for `SAVED` summaries from History.
- Re-export uses the saved snapshot only.
- Re-export does not regenerate, unlock, modify assignments, modify OP SHOP tasks, update `saved_at`, update `saved_by`, or create duplicate summaries.
- `GENERATED` summaries are not normal History items and do not show History `Re-export`.

### Excel Boundary

- Final Trip Summary XLSX contains Delivery trip tables and, when present, a separate `OP SHOP PICKUPS` section.
- The Final Summary `OP SHOP PICKUPS` section includes Category and Route Group columns where applicable.
- OP SHOP pickup rows never enter Delivery Trip 1 / Trip 2 tables.
- OP SHOP pickups never contribute to Delivery totals.
- Saved-summary re-export uses the saved snapshot, not live mutable board data.

## Data Model / APIs

### Key Tables

| Table | Purpose |
| --- | --- |
| `manual_dispatch_assignments` | Manual assignment records keyed by `task_type + task_id`, supporting `ORDER` and `OPSHOP_PICKUP`. |
| `opshop_locations` | Deduplicated OP SHOP location records. |
| `opshop_countryside_route_groups` | Countryside route group records, with workbook-backed and UI-created sources able to coexist. |
| `opshop_pickup_schedules` | Regular schedules, Oncall templates, and Countryside route memberships linked to locations. |
| `opshop_pickup_tasks` | Actual dated OP SHOP pickup tasks. |
| `final_trip_summaries` | Final Summary header rows with `GENERATED` / `SAVED` status and driver/date lock source. |
| `final_trip_summary_rows` | Delivery Order Trip 1 / Trip 2 snapshot rows only. |
| `final_trip_summary_opshop_pickup_rows` | Separate OP SHOP pickup snapshot rows. |

### Board OP SHOP Fields

| Response Field | Purpose |
| --- | --- |
| `scheduled_opshop_pickups` | Regular list tasks for the active Regular window. |
| `oncall_opshop_pickups` | Actual created Oncall tasks visible in the Oncall list. |
| `countryside_route_groups` | Active Countryside route groups available to the Countryside pickup list. |
| `countryside_opshop_pickups` | Actual created Countryside pickup tasks visible in the Countryside list. |
| `assigned_opshop_pickups` | Assigned pickup items used in Driver Summary. |
| `opshop_regular_list_window_start` / `opshop_regular_list_window_end` | Display window for the Regular list. |
| `finalized_driver_delivery_dates` | Saved-summary hard-lock information for frontend interaction guards. |

### API Groups

| Group | Routes |
| --- | --- |
| Board / Delivery Export | `GET /api/manual-dispatch/board`, `GET /api/manual-dispatch/export-excel` |
| Auth | `POST /api/manual-dispatch/auth/register`, `POST /api/manual-dispatch/auth/login`, `POST /api/manual-dispatch/auth/reset-password` |
| Orders | `POST /api/manual-dispatch/orders`, `POST /api/manual-dispatch/orders/import-attache-pdf-preview`, `POST /api/manual-dispatch/orders/import-attache-pdf-commit`, `PATCH /api/manual-dispatch/orders/{order_id}`, `POST /api/manual-dispatch/orders/{order_id}/cancel` |
| Assignment | `POST /api/manual-dispatch/assign`, `POST /api/manual-dispatch/unassign` |
| Driver / Vehicle | `GET /api/manual-dispatch/specifications`, `POST/PATCH/DELETE /api/manual-dispatch/drivers...`, `POST/PATCH/DELETE /api/manual-dispatch/vehicles...`, `POST /api/manual-dispatch/driver-vehicle` |
| OP SHOP Templates | `GET/POST /api/manual-dispatch/opshop-templates`, `PATCH /api/manual-dispatch/opshop-templates/{schedule_id}`, `POST /api/manual-dispatch/opshop-templates/{schedule_id}/disable` |
| OP SHOP Countryside Route Groups | `GET/POST /api/manual-dispatch/opshop-countryside-route-groups`, `PATCH /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}`, `POST /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/disable`, `GET/POST /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/memberships`, `POST /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/assign`, `POST /api/manual-dispatch/opshop-countryside-memberships/{schedule_id}/move`, `POST /api/manual-dispatch/opshop-countryside-memberships/{schedule_id}/remove` |
| OP SHOP Pickups | `GET /api/manual-dispatch/opshop-pickup-schedules`, `POST /api/manual-dispatch/opshop-pickups`, `POST /api/manual-dispatch/opshop-pickups/oncall`, `PATCH/DELETE /api/manual-dispatch/opshop-pickups/{pickup_task_id}`, `GET /api/manual-dispatch/opshop-pickups/export-excel`, `POST /api/manual-dispatch/opshop-pickups/weekly-assignments/apply`, `POST /api/manual-dispatch/opshop-pickups/oncall-assignments/apply`, `POST /api/manual-dispatch/opshop-pickups/countryside-assignments/apply`, `POST /api/manual-dispatch/opshop-pickups/countryside-route-groups/{route_group_id}/assign` |
| Final Summaries | `POST /api/manual-dispatch/final-summaries`, `POST /api/manual-dispatch/final-summaries/generated`, `GET /api/manual-dispatch/final-summaries`, `GET /api/manual-dispatch/final-summary-dates`, `POST /api/manual-dispatch/final-summaries/{summary_id}/save`, `POST /api/manual-dispatch/final-summaries/{summary_id}/cancel-generated`, `GET /api/manual-dispatch/final-summaries/{summary_id}`, `GET /api/manual-dispatch/final-summaries/{summary_id}/export-excel`, `GET /api/manual-dispatch/final-summaries/export-excel` |

## Import / Maintenance Tools

The repository provides importer and maintenance tools for approved local bulk refreshes. Real workbooks remain local inputs and are not required repository files.

### Regular Workbook Import

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\import_regular_opshop_pickups_to_db.py `
  --file "<path-to-regular-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

- Imports/updates `opshop_locations` and `opshop_pickup_schedules` as `REGULAR` source schedules.
- Uses workbook sheet weekday as the Regular pickup weekday.
- Preserves default driver source information.
- Makes a timestamped SQLite backup first when the target database exists.
- Does not directly create pickup tasks.

### Oncall Workbook Import

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\import_oncall_opshop_pickups_to_db.py `
  --file "<path-to-oncall-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

- Imports/updates `opshop_locations` and `opshop_pickup_schedules` as `ON_CALL` templates.
- Stores weekday templates and no-fixed-day templates as provided by source data.
- Reports unresolved assigned-driver aliases without aborting the entire import.
- Makes a timestamped SQLite backup first when the target database exists.
- Does not create actual Oncall pickup tasks.

### Countryside Workbook Import

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\import_countryside_opshop_pickups_to_db.py `
  --file "<path-to-countryside-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

- Imports every workbook sheet as a Countryside route group.
- Imports active rows as `ON_CALL` schedules with `pickup_category = COUNTRYSIDE`.
- Reuses duplicate OP SHOP locations by name, suburb, and street address while allowing the same location to belong to multiple route groups.
- Makes a timestamped SQLite backup first when the target database exists.
- Reports unresolved assigned-driver aliases without aborting the import.
- Does not create actual pickup tasks.
- Reruns manage workbook-backed Countryside route groups and memberships only; UI-created route groups and memberships remain office-managed.

### UI and Importer Coexistence

- Excel importers remain available for authorized bulk source refreshes.
- UI-created templates and imported templates may coexist, but the importer is not an automatic backup of office UI edits.
- A subsequent importer run manages only its workbook-backed schedule source and may soft-disable workbook-backed templates absent from that source.
- UI-created templates remain office-managed and should not be soft-disabled merely because they are absent from a workbook.
- Before any source refresh, establish which source is authoritative and back up the SQLite database.

### OP SHOP Saved-Lock Audit

The audit tool is read-only. It checks saved Final Summary OP SHOP snapshot rows against live OP SHOP tasks and assignments.

```powershell
$env:MANUAL_DISPATCH_DB_PATH="C:\Users\Albert Fang\Desktop\Delivery V2\data\manual_dispatch_full_test.sqlite3"
.\tmp\route-test-venv\Scripts\python.exe .\tools\audit_opshop_final_summary_locks.py
```

### OP SHOP Saved-Lock Backfill

The backfill tool defaults to dry-run. It only modifies SQLite when `--apply --yes` is provided.

Dry-run:

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\backfill_opshop_final_summary_locks.py
```

Apply:

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\backfill_opshop_final_summary_locks.py --apply --yes
```

Use the backfill tool carefully:

- Back up the SQLite database before `--apply`.
- Start with a test database.
- Audit and review dry-run output before applying.
- Do not apply to the real office database without confirming the findings and rollback plan.

### Legacy Final Summary Workspace Migration

The workspace migration tool copies legacy `SAVED` Final Summary snapshots into
independent Delivery Run Sheet and OP SHOP Pickup Collection history. It does
not delete or modify legacy Final Summary history.

Always run dry-run first:

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3"
```

Apply requires explicit double confirmation:

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3" `
  --apply --yes
```

Apply creates and integrity-checks a timestamped SQLite backup before running
all migration writes in one transaction. Any legacy `GENERATED` summary or
workspace key/marker conflict blocks the entire apply. Successful reruns are
idempotent and create no duplicate headers or child rows.

See [Legacy Final Summary Workspace Migration](docs/separate-delivery-and-opshop-workspaces-migration.md)
for preflight, verification, and rollback steps.

## Deployment / Backup

### Office Trial

Start the local office-trial server with:

```powershell
.\tools\start_office_trial.ps1
```

Create an end-of-day SQLite backup with:

```powershell
.\tools\backup_sqlite_db.ps1
```

Restore a known-good backup with:

```powershell
.\tools\restore_sqlite_db.ps1 -BackupPath .\backups\<backup-file>.sqlite3
```

### NAS Deployment

NAS/internal office guidance is maintained in:

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)

Quick Docker Compose setup:

```powershell
Copy-Item .env.nas.example .env
docker compose up -d --build
```

The normal NAS configuration serves the API and frontend same-origin and stores SQLite on NAS local storage.

### Runtime Data Safety

Do not commit:

- `data/*.sqlite` or `data/*.sqlite3`
- SQLite `-wal` or `-shm` files
- `backups/`
- `outputs/`
- `.env`
- real office/customer workbooks
- `task_plan.md`, `findings.md`, or `progress.md`

Back up SQLite before importer runs, backfill apply runs, NAS updates, or office database maintenance.

## Validation / Tests

### Full Local Validation

```powershell
git diff --check
git diff --cached --check
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

### Targeted Modules

```powershell
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_manual_dispatch_final_summary -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_manual_dispatch_final_summary_export -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_manual_dispatch_frontend_static_contract -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_manual_dispatch_api_contract -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_audit_opshop_final_summary_locks -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_backfill_opshop_final_summary_locks -v
```

Important OP SHOP modules include:

- `tests.test_import_regular_opshop_pickups_to_db`
- `tests.test_import_oncall_opshop_pickups_to_db`
- `tests.test_import_countryside_opshop_pickups_to_db`
- `tests.test_manual_dispatch_opshop_foundation`
- `tests.test_manual_dispatch_opshop_pickup_generation`
- `tests.test_manual_dispatch_opshop_board_payload`
- `tests.test_manual_dispatch_opshop_assignment`
- `tests.test_manual_dispatch_opshop_pickup_list_management`
- `tests.test_manual_dispatch_opshop_pickup_run_sheet_export`
- `tests.test_manual_dispatch_opshop_template_management`
- `tests.test_manual_dispatch_opshop_countryside_route_groups`

### CI and Manual Smoke

The GitHub Actions workflow runs Ubuntu and Windows jobs for the automated Python suite, frontend JavaScript syntax checks, and `git diff --check` on configured stable/feature branch triggers and relevant pull requests.

Local/manual smoke remains necessary for workflows depending on runtime data or browser interaction, including:

- Oncall Add Pickup Task template search by company name, suburb, and address.
- Regular OP SHOP assign -> Generate -> Cancel Generated Summary.
- Oncall OP SHOP assign -> Generate -> Save and Export.
- Countryside Assign Route Group -> Generate -> Save and Export.
- Saved Final Summary History Re-export.
- OP SHOP saved-lock audit/backfill review.
- Template Add/Edit/Disable and continuous typing.
- Runtime SQLite backup/import checks using approved local workbook sources.

## Documentation Index

Some earlier phase documents predate the OP SHOP branch and should be read as implementation history. For current OP SHOP and Final Summary behavior, prefer this README, the current code, and automated tests.

### Architecture and Data

- [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md)
- [Data model direction](docs/manual-dispatch-board-data-model.md)
- [Schema design](docs/manual-dispatch-board-schema.md)

### Delivery and Driver Workflow

- [Driver Summary Delivery Date behavior](docs/manual-dispatch-board-driver-summary-delivery-date.md)
- [Driver & Vehicle Specification](docs/manual-dispatch-board-driver-vehicle-specification.md)
- [Add Order](docs/manual-dispatch-board-phase10a1-add-order.md)
- [Edit Order](docs/manual-dispatch-board-phase10a3-edit-order.md)
- [Cancel Order](docs/manual-dispatch-board-phase10a4-cancel-order.md)
- [Product Details and load-unit exclusivity](docs/manual-dispatch-board-phase16-product-details.md)

### Final Summary and Office Trial

- [Final Trip Summary foundation](docs/manual-dispatch-board-final-trip-summary.md)
- [Global Final Summary save](docs/manual-dispatch-board-global-final-summary-save.md)
- [Final Summary save and export polish](docs/manual-dispatch-board-phase14b-final-summary-save-export.md)
- [Login and operator attribution](docs/manual-dispatch-board-phase15-login-final-summary-operator.md)
- [Suburb distance sorting](docs/manual-dispatch-board-phase18-suburb-distance-sorting.md)
- [OP SHOP / Final Summary smoke test checklist](docs/opshop-final-summary-smoke-test-checklist.md)
- [Office trial deployment and backup](docs/manual-dispatch-board-phase20-office-trial-deployment.md)
- [Office trial checklist](docs/manual-dispatch-board-office-trial-checklist.md)

### NAS / Internal Deployment

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)
