# Manual Dispatch Board

## Project Overview

Manual Dispatch Board is a FastAPI, SQLite, and vanilla JavaScript application for office staff to manually coordinate Delivery Orders and OP SHOP pickup work with drivers.

The board is a manual workflow:

- The Task Pool is shown at the top.
- Driver Summary and Final Trip Summary are shown below.
- Dispatch Date identifies the operational dispatch session.
- Driver Summary Delivery Date identifies which delivery or pickup day is being reviewed.
- Delivery Orders and OP SHOP pickups share manual driver assignment infrastructure, but remain separate task types and separate summary sections.

The current implementation includes the OP SHOP pickup workflow, template management, independent Run Sheet export, and separate Final Summary OP SHOP snapshot section documented below.

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

Never commit runtime SQLite databases, backups, `.env` files, or real office workbooks.

## Main Workflow

1. Log in.
2. Choose the Dispatch Date for the operational board session.
3. Review Delivery Orders in the Task Pool.
4. Use the separate OP SHOP PICKUP area for Regular or Oncall pickup work.
5. Maintain OP SHOP templates through `Manage OP SHOP Templates` when needed.
6. Assign Delivery Orders to a driver and `trip1` or `trip2`.
7. Choose drivers in Regular or Oncall OP SHOP lists and close the list to apply visible pickup assignments.
8. Select the Driver Summary Delivery Date.
9. Choose a vehicle for the driver/date combination.
10. Generate Final Trip Summary to capture Delivery rows and OP SHOP pickups in separate snapshot sections.
11. Save and Export to persist history and hard-lock the saved driver/date.

## Delivery Order Workflow

| Function | Current Behavior |
| --- | --- |
| Task Pool | Shows active unassigned Delivery Orders; search, urgency, and Delivery Date filters change display only. |
| Add / Edit / Cancel | Active Orders can be added and edited; Cancel is a soft removal from normal workflow. |
| Product Details | Orders may contain product lines; one Order uses Pallets or Bags, never both. |
| Assign / Unassign | Staff manually assign an Order to a Driver and `trip1` or `trip2`, or return it to the Task Pool. |
| Delivery Date | Driver Summary filters assigned Delivery Orders by the selected Delivery Date. |
| Trip Display | Delivery Orders remain inside Driver Summary `Trip 1` and `Trip 2` sections. |
| Totals | Pallet, loose-bag, and capacity totals count Delivery Orders only. |

Delivery assignment remains entirely manual. OP SHOP work is not stored as a Delivery Order and does not change Delivery totals.

## OP SHOP Pickup Workflow

OP SHOP PICKUP is a distinct manual task type. The Task Pool shows an `OP SHOP PICKUP` section above Delivery Orders with:

- `Regular OP SHOP Pickup List`
- `Oncall OP SHOP Pickup List`
- `Manage OP SHOP Templates`
- `Export OP SHOP Run Sheet`

### Template Management

`Manage OP SHOP Templates` is the office-facing entry point for adding, editing, and disabling pickup templates.

| Template Type | Purpose | Actual Pickup Task Creation |
| --- | --- | --- |
| `REGULAR` | Schedule source for the Regular list and its visible pickup week. | Visible regular tasks are ensured from active schedules. |
| `ON_CALL` | Candidate source for office-requested Oncall pickups. | No task is created until staff use Add Pickup Task. |
| `ON_CALL` + `COUNTRYSIDE` | Route-group membership templates for Countryside OP SHOP pickups. | No task is created by import; future staff-created pickup tasks still use `OPSHOP_PICKUP`. |

Template rules:

- Regular templates require a weekday.
- Oncall templates may have a weekday or no fixed day.
- Default driver data may be maintained on the template.
- Disable is a soft disable: `status = On_Hold` and `active_flag = false`.
- Disabling a template does not delete existing pickup tasks, assignments already captured in history, or saved Final Summaries.
- An identity-field edit can create/use a new deterministic active schedule while old task references remain historically valid.

### Countryside OP SHOP Route Groups

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
- The Countryside Pickup List lets staff filter by route group, create actual pickup tasks from Countryside templates, choose an assigned driver, and close the list to apply those assignments.
- Countryside remains outside Delivery Order totals, vehicle capacity totals, Delivery Trip 1 / Trip 2 rows, and Delivery-style automation.

### Regular OP SHOP Pickup List

- The list is generated from active `REGULAR` schedules.
- Monday through Thursday Dispatch Dates show the current Monday-Friday pickup week.
- Friday Dispatch Dates show Friday today plus the following Monday-Friday.
- Saturday and Sunday Dispatch Dates show the next Monday-Friday.
- The source schedule weekday determines the pickup day. Frequency text does not expand one Regular source row into extra weekdays in this list flow.
- Staff can add, edit, soft-delete, and choose the assigned driver for visible tasks.
- Closing the list applies selected assignments using `trip1` internally for persistence compatibility.
- A cancelled task can be restored by re-adding the same schedule and pickup date; active or assigned duplicates remain prevented.

### Oncall OP SHOP Pickup List

- The list is request-driven and starts empty until an actual Oncall task is added.
- Add Pickup Task uses active `ON_CALL` templates.
- Weekday templates can provide a matching default pickup date; no-fixed-day templates require staff to select a pickup date.
- Staff can edit, soft-delete, and select a driver for created Oncall tasks.
- Closing the list applies selected assignments using `trip1` internally.
- Importing or creating an Oncall template never automatically creates an actual pickup task.

### Countryside OP SHOP Pickup List

- The list is request-driven like Oncall, but templates are filtered from `ON_CALL` schedules with `pickup_category = COUNTRYSIDE`.
- Staff can filter by Countryside route group before choosing a template.
- Add Pickup Task creates an actual `OPSHOP_PICKUP` task only when office staff select a template and pickup date.
- Closing the list applies selected driver assignments using the same OP SHOP pickup assignment boundary as Oncall.
- Assigned Countryside pickups appear in Driver Summary under `OP SHOP PICKUPS`, with Countryside/route group context.
- A full Manage Countryside Routes UI and route-group-specific Run Sheet polish are not implemented in this phase.

### Driver Summary and Lock Boundary

- Assigned OP SHOP pickups appear in a driver-level `OP SHOP PICKUPS` section, not inside Delivery `Trip 1` or `Trip 2`.
- Visibility is filtered by the pickup date matching the selected Driver Summary Delivery Date.
- OP SHOP pickups do not affect Delivery pallet, loose-bag, or capacity totals.
- Generating Final Trip Summary captures the displayed OP SHOP pickups and clears their editable assignments from Driver Summary.
- Once Save and Export has saved a Final Summary for `dispatch_date + delivery_date + driver_id`, that driver/date is hard-locked against Delivery assignment, OP SHOP assignment, and vehicle changes.

### OP SHOP Run Sheet Export

`Export OP SHOP Run Sheet` provides an independent XLSX for operational pickup work. It includes OP SHOP pickup data grouped for office/driver use, with unassigned visible pickups separated where applicable.

This export is independent from the Final Trip Summary workbook and does not turn OP SHOP pickups into Delivery rows.

## Final Trip Summary

Final Trip Summary is a saved historical snapshot for a driver, Dispatch Date, and Driver Summary Delivery Date.

| Scenario | Snapshot Content | Totals |
| --- | --- | --- |
| Delivery-only | Delivery Orders in Trip 1 / Trip 2. | Delivery totals only. |
| OP SHOP-only | Separate `OP SHOP PICKUPS` section; no Delivery rows. | Zero pallets and zero loose bags. |
| Mixed | Delivery rows in Trip 1 / Trip 2 plus a separate `OP SHOP PICKUPS` section. | Delivery totals only. |

### Generate Behavior

- Generate captures current Delivery Order assignments and OP SHOP pickup assignments for the selected driver/date.
- Delivery rows remain in `Trip 1` / `Trip 2`.
- OP SHOP rows are captured only in the independent `OP SHOP PICKUPS` snapshot section.
- Captured editable assignments are cleared from Driver Summary after generation.
- Generated-but-unsaved previews live in frontend memory and can be lost on refresh.

### Save and Export Hard Lock

- Save and Export persists snapshot data and records the logged-in operator.
- Saved history loads stored snapshot rows rather than current mutable task data.
- Duplicate saves for the same driver, Dispatch Date, and Delivery Date are rejected.
- After save, that driver/date cannot receive new Delivery Orders, Regular pickups, Oncall pickups, or vehicle changes.

### Excel Boundary

- Final Trip Summary XLSX contains Delivery trip tables and, when present, a separate `OP SHOP PICKUPS` section.
- OP SHOP pickup rows never enter Delivery Trip 1 / Trip 2 tables.
- OP SHOP pickups never contribute to Delivery totals.
- The separate OP SHOP Run Sheet export remains available for pickup operations.

## Data Model / APIs

### Key Tables

| Table | Purpose |
| --- | --- |
| `manual_dispatch_assignments` | Manual assignment records keyed by `task_type + task_id`, supporting `ORDER` and `OPSHOP_PICKUP`. |
| `opshop_locations` | Deduplicated OP SHOP location records. |
| `opshop_countryside_route_groups` | Countryside route group records, with workbook-backed and UI-created sources able to coexist. |
| `opshop_pickup_schedules` | Regular schedules, Oncall templates, and Countryside route memberships linked to locations. |
| `opshop_pickup_tasks` | Actual dated OP SHOP pickup tasks. |
| `final_trip_summaries` | Saved summary header and driver/date lock source. |
| `final_trip_summary_rows` | Delivery Order Trip 1 / Trip 2 snapshot rows only. |
| `final_trip_summary_opshop_pickup_rows` | Separate saved OP SHOP pickup snapshot rows. |

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
| Orders | `POST /api/manual-dispatch/orders`, `PATCH /api/manual-dispatch/orders/{order_id}`, `POST /api/manual-dispatch/orders/{order_id}/cancel` |
| Assignment | `POST /api/manual-dispatch/assign`, `POST /api/manual-dispatch/unassign` |
| Driver / Vehicle | `GET /api/manual-dispatch/specifications`, `POST/PATCH/DELETE /api/manual-dispatch/drivers...`, `POST/PATCH/DELETE /api/manual-dispatch/vehicles...`, `POST /api/manual-dispatch/driver-vehicle` |
| OP SHOP Templates | `GET/POST /api/manual-dispatch/opshop-templates`, `PATCH /api/manual-dispatch/opshop-templates/{schedule_id}`, `POST /api/manual-dispatch/opshop-templates/{schedule_id}/disable` |
| OP SHOP Countryside Route Groups | `GET/POST /api/manual-dispatch/opshop-countryside-route-groups`, `PATCH /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}`, `POST /api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/disable` |
| OP SHOP Pickups | `GET /api/manual-dispatch/opshop-pickup-schedules`, `POST /api/manual-dispatch/opshop-pickups`, `POST /api/manual-dispatch/opshop-pickups/oncall`, `PATCH/DELETE /api/manual-dispatch/opshop-pickups/{pickup_task_id}`, `POST /api/manual-dispatch/opshop-pickups/weekly-assignments/apply`, `POST /api/manual-dispatch/opshop-pickups/oncall-assignments/apply`, `POST /api/manual-dispatch/opshop-pickups/countryside-assignments/apply` |
| Final Summaries | `POST/GET /api/manual-dispatch/final-summaries`, `GET /api/manual-dispatch/final-summaries/{summary_id}`, `GET /api/manual-dispatch/final-summary-dates` |
| Exports | `GET /api/manual-dispatch/final-summaries/export-excel`, `GET /api/manual-dispatch/opshop-pickups/export-excel` |

## Import Tools

The repository provides importer tools for approved local bulk refreshes. Real workbooks remain local inputs and are not required repository files.

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

### Targeted OP SHOP Modules

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
- `tests.test_manual_dispatch_final_summary`
- `tests.test_manual_dispatch_final_summary_export`
- `tests.test_manual_dispatch_frontend_static_contract`

### CI and Manual Smoke

The GitHub Actions workflow runs Ubuntu and Windows jobs for the automated Python suite, frontend JavaScript syntax checks, and `git diff --check` on configured stable/feature branch triggers and relevant pull requests.

Local/manual smoke remains necessary for workflows depending on runtime data or browser interaction, including:

- Template Add/Edit/Disable and continuous typing.
- Regular and Oncall list interaction.
- OP SHOP assignment and independent Run Sheet export.
- Final Summary generation, separate OP SHOP snapshot section, Save and Export hard lock, and history display.
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
- [Office trial deployment and backup](docs/manual-dispatch-board-phase20-office-trial-deployment.md)
- [Office trial checklist](docs/manual-dispatch-board-office-trial-checklist.md)

### NAS / Internal Deployment

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)
