# Manual Dispatch Board

## Project Overview

Manual Dispatch Board is a FastAPI, SQLite, and vanilla JavaScript application for office staff to manually coordinate two independent workspaces: Order Delivery and OP SHOP Pickup.

The board is a manual office workflow:

- The frontend is a single-page application with hash-routed Delivery and OP SHOP workspaces.
- Order Delivery uses `Task Pool -> Trip Summary -> Delivery Run Sheets`.
- OP SHOP Pickup uses `Task Pool -> Trip Summary -> Pickup Collections`.
- Dispatch Date identifies the operational dispatch session.
- Delivery Date and Pickup Date independently identify the day reviewed inside their workspace.
- Delivery Orders and OP SHOP pickups remain separate task types, scoped boards, snapshots, locks, histories, and exports.
- Legacy Final Trip Summary remains readable for compatibility and migration; it is not the primary scoped workflow.

The current branch includes scoped Delivery Run Sheets, Regular/Oncall/Countryside OP SHOP Task Pools, template and route management, generated/saved Pickup Collections, migration-readiness controls, and legacy Final Summary compatibility tools.

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

1. Log in and choose a workspace from Home.
2. Set the Dispatch Date for the operational board session.
3. In **Order Delivery**, assign Orders in `#delivery/task-pool`, review by driver/date in `#delivery/trip-summary`, then generate, save, cancel, or export independent Delivery Run Sheets.
4. In **OP SHOP Pickup**, choose Regular, Oncall, or Countryside. Source-backed template defaults appear as persisted assignments; later staff assignment edits remain drafts until `Apply Assignment Changes`.
5. Review assigned pickups by driver and Pickup Date in `#opshop/trip-summary`.
6. Generate an independent Pickup Collection for a driver/date.
7. In `#opshop/collections`, review Generated collections, cancel an incorrect Generated collection, or save/export the correct collection.
8. Reopen Saved Pickup Collections from the same page for history and export.

Workspace navigation is hash-based and browser Back/Forward safe. Switching OP SHOP Task Pool subtype does not submit or discard pending assignment drafts.

## Delivery Order Workflow

| Function | Current Behavior |
| --- | --- |
| Task Pool | Shows active unassigned Delivery Orders; search, urgency, and Delivery Date filters change display only. |
| Add / Edit / Cancel | Active Orders can be added and edited; Cancel is a soft removal from normal workflow. |
| Product Details | Orders may contain product lines with Pallets, Bags, or mixed pallet + loose-bag loads. |
| Assign / Unassign | Staff manually assign an Order to a Driver and `trip1` or `trip2`, or return it to the Task Pool. |
| Delivery Date | Delivery Trip Summary filters assigned Delivery Orders by the selected Delivery Date. |
| Trip Display | Delivery Orders remain inside Delivery Trip Summary `Trip 1` and `Trip 2` sections. |
| Generated Lock | Delivery Orders captured by a `GENERATED` Delivery Run Sheet are reserved until cancelled or saved. |
| Saved Lock | A `SAVED` Delivery Run Sheet blocks further Delivery assignment and vehicle changes for that driver/date. |
| Totals | Pallet, loose-bag, and capacity totals count Delivery Orders only. |

Delivery assignment remains entirely manual. OP SHOP work is not stored as a Delivery Order and does not change Delivery totals.

### Attache Invoice PDF Import

`Import Attache Invoices` in the Delivery Orders area lets office staff upload one or more text-based Attache invoice PDFs, preview parsed Delivery Orders, correct fields, and then confirm import.

- Preview is required before import; PDF upload does not write to the database by itself.
- The preview highlights duplicate invoice numbers already present in Manual Dispatch and leaves duplicate rows unselected / not importable by default.
- Staff can edit delivery date, time window, phone, address, suburb, postcode, pallet quantity, loose-bag quantity, and notes before confirming.
- Confirm Import creates standard Delivery Orders through the same `CreateOrderRequest` path as manual entry, so imported Orders appear in the Task Pool like normal Delivery Orders.
- Product lines use the existing `product_name`, `quantity`, and `unit` fields only; invoice accounting lines, GST, totals, and payment details are not imported as delivery product lines.
- PDF import does not change the OP SHOP workspace, Pickup Collections, OP SHOP locks, or OP SHOP exports.

## OP SHOP Pickup Workspace

OP SHOP Pickup is an independent manual workspace:

```text
OP SHOP Pickup
  Task Pool
    Regular
    Oncall
    Countryside
    Manage Templates
  Trip Summary
    Pickup-date review by driver
    Generate Pickup Collection
  Pickup Collections
    Generated collections
    Saved collections / history
    Export
```

Canonical routes are `#opshop/task-pool/regular`, `#opshop/task-pool/oncall`, `#opshop/task-pool/countryside`, `#opshop/templates`, `#opshop/trip-summary`, and `#opshop/collections`.

OP SHOP pickups:

- use `task_type = OPSHOP_PICKUP`
- display only in the OP SHOP Trip Summary and Pickup Collection workflow
- never enter Delivery Task Pool, Delivery Trip Summary, or Delivery Run Sheet rows
- never affect Delivery pallet, loose-bag, or vehicle capacity totals
- are captured in independent OP SHOP Pickup Collection snapshot rows

### Template Management

`Manage Templates` (`#opshop/templates`) is the office-facing entry point for Regular/Oncall template CRUD and Countryside route-group/membership management.

| Template Type | Purpose | Actual Pickup Task Creation |
| --- | --- | --- |
| `REGULAR` | Schedule source for the Regular list and its visible pickup week. | Visible regular tasks are ensured from active schedules. |
| `ON_CALL` | Candidate source for office-requested Oncall pickups. | No task is created until staff use Add Pickup Task. |
| `ON_CALL` + `COUNTRYSIDE` | Route-group membership templates for Countryside OP SHOP pickups. | Route group assignment creates actual dated pickup tasks. |

Template rules:

- Regular templates require a weekday.
- Oncall templates may have a weekday or no fixed day.
- Default driver data may be maintained on the template. For source-backed templates, that default is materialized once as an actual task assignment when an eligible task is created or through the controlled backfill tool.
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
- Staff can add, view, edit, and soft-delete visible tasks unless the pickup is locked.
- Persisted source-backed assignments immediately appear in Current Assignee, Assigned To, and OP SHOP Trip Summary without creating a pending draft.
- Later staff assignment changes are local drafts until `Apply Assignment Changes` is clicked. A persisted manual reassignment or explicit `Unassigned` always wins and is not replaced on refresh or navigation.
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
- Staff can add, view, edit, and soft-delete created Oncall tasks unless locked.
- Assignment changes remain local drafts until `Apply Assignment Changes` is clicked.
- A task created from a template with a source-backed default driver receives that actual assignment once at creation. An ad hoc/no-default Oncall task remains Unassigned.
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
- Countryside Task Pool remains operational: it assigns route groups and manages live pickup task drafts.
- `Manage Templates` contains route management: create, rename, and soft-disable groups; add/move/remove memberships; and inspect route-template detail.
- Route membership changes are soft schedule/template changes. They do not delete OP SHOP locations, existing pickup tasks, assignments already captured in history, or saved Final Summary snapshots.
- `Assign Route Group` creates or restores one `OPSHOP_PICKUP` task per active route template for the selected pickup date, assigns those tasks to the selected driver, and uses `trip1` for compatibility with the OP SHOP assignment model.
- Assigned Countryside pickups appear in OP SHOP Trip Summary with route-group context preserved for snapshots and exports.

### Trip Summary and Collection Lock Boundary

- OP SHOP Trip Summary groups assigned pickups by driver and category for the selected Pickup Date.
- Generate creates an independent `GENERATED` Pickup Collection snapshot and reserves its captured pickup tasks.
- Cancelling a Generated Pickup Collection removes that generated snapshot and restores editable pickup work.
- Saving a Pickup Collection locks only OP SHOP pickup mutations for its driver/date; it does not lock Delivery Orders or Delivery vehicles.
- Delivery Run Sheet locks and OP SHOP Pickup Collection locks are independent.
- Saved history and export read immutable Pickup Collection snapshots, not live mutable pickup tasks.

### OP SHOP Pickup Run Sheet Export

The backend still provides an independent OP SHOP pickup run sheet export endpoint:

```text
GET /api/manual-dispatch/opshop-pickups/export-excel?dispatch_date=YYYY-MM-DD
```

This legacy operational run-sheet export remains independent from Delivery Run Sheets and Pickup Collection exports. It includes OP SHOP operational data and Countryside route-group context when present.

The current Task Pool UI does not show a dedicated run sheet export button. Use this endpoint only through an approved office workflow or tool path.

## Legacy Final Trip Summary Compatibility

Final Trip Summary is retained as historical compatibility for pre-workspace records and migration. New scoped work uses Delivery Run Sheets and OP SHOP Pickup Collections instead.

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
| `delivery_run_sheets` / `delivery_run_sheet_rows` | Independent generated/saved Delivery snapshots. |
| `opshop_pickup_collections` / `opshop_pickup_collection_rows` | Independent generated/saved OP SHOP snapshots. |

### Scoped OP SHOP Board Fields

| Response Field | Purpose |
| --- | --- |
| `dispatch_date` | Current OP SHOP board context. |
| `opshop_pickups` | Combined live Regular, Oncall, and Countryside tasks; generated/saved reserved tasks are excluded from editable state. |
| `drivers` | Current drivers available to OP SHOP assignment controls. |
| `templates` | Active OP SHOP template context used by the workspace. |
| `countryside_route_groups` | Active Countryside route groups available to Task Pool and management views. |

### API Groups

| Group | Routes |
| --- | --- |
| Board / Delivery Export | `GET /api/manual-dispatch/board`, `GET /api/manual-dispatch/export-excel` |
| Workspace Boards | `GET /api/manual-dispatch/delivery/board`, `GET /api/manual-dispatch/opshop/board`, `GET /api/manual-dispatch/workspace-migration-status` |
| Scoped Delivery | `/api/manual-dispatch/delivery/assignments...`, `/api/manual-dispatch/delivery/vehicle-assignments...`, `/api/manual-dispatch/delivery/run-sheets...` |
| Scoped OP SHOP | `/api/manual-dispatch/opshop/pickups/assignments...`, `/api/manual-dispatch/opshop/countryside-route-groups/{route_group_id}/assign`, `/api/manual-dispatch/opshop/pickup-collections...` |
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

### OP SHOP Source-Driver Assignment Backfill

`tools/backfill_opshop_source_driver_assignments.py` safely materializes approved Regular/Oncall workbook driver defaults into template defaults and eligible current/future task assignments.

- It matches category + normalized company + suburb + address + run day; company-only matching is rejected.
- Existing task assignments always win. Generated/Saved, cancelled, historical, and non-editable tasks are not reassigned.
- Dry-run is mandatory before apply. Apply is blocked by ambiguous matches, conflicting defaults, or unknown aliases.
- The tool is not route optimization or automatic balancing. It applies office-maintained source intent once at controlled backfill/task-creation time.
- A later persisted manual reassignment or Unassign is never recreated by board loading, refresh, navigation, or rendering.

See [OP SHOP source-driver assignment release preflight](docs/opshop-source-driver-assignment-release-preflight.md) before any production dry-run or apply.

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

- OP SHOP canonical route, refresh, Back/Forward, and assignment-draft preservation checks.
- Regular/Oncall/Countryside Task Pool CRUD and assignment Apply.
- Regular/Oncall template CRUD plus Countryside route/membership management.
- OP SHOP Trip Summary -> Generate -> Cancel Generated Pickup Collection.
- OP SHOP Trip Summary -> Generate -> Save/Export Pickup Collection.
- Saved Pickup Collection persistence and history export.
- OP SHOP saved-lock audit/backfill review.
- Template Add/Edit/Disable and continuous typing.
- Runtime SQLite backup/import checks using approved local workbook sources.

## Documentation Index

Some earlier phase documents predate the independent workspaces and should be read as implementation history. For current OP SHOP behavior, prefer this README, the workspace specification, the current smoke checklist, code, and automated tests.

### Architecture and Data

- [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md)
- [OP SHOP source-driver assignment release preflight](docs/opshop-source-driver-assignment-release-preflight.md)
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
- [Current OP SHOP workspace smoke test checklist](docs/opshop-workspace-smoke-test-checklist.md)
- [Legacy OP SHOP / Final Summary compatibility checklist](docs/opshop-final-summary-smoke-test-checklist.md)
- [Office trial deployment and backup](docs/manual-dispatch-board-phase20-office-trial-deployment.md)
- [Office trial checklist](docs/manual-dispatch-board-office-trial-checklist.md)

### NAS / Internal Deployment

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)
