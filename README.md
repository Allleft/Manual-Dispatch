# Manual Dispatch Board

## Project Overview

Manual Dispatch Board is a FastAPI + SQLite + vanilla HTML/CSS/JavaScript workflow for office staff who manually dispatch Delivery Orders and OP SHOP pickup work to Drivers.

The board is intentionally manual:

- Top: Task Pool for work that needs attention.
- Bottom: Driver Summary, Trip Summary, and Final Trip Summary.
- Dispatch Date is the operational assignment date.
- Delivery Date is customer/order metadata and the Driver Summary view scope for Delivery Orders.
- OP SHOP pickup dates are their own task dates and are displayed separately from Delivery Order trips.

This project is not a route optimizer. It does not perform auto-dispatch, route optimization, ETA prediction, geocoding, Google Maps routing, CP-SAT planning, automatic trip planning, or automatic driver/vehicle selection.

## Current Status

Current active feature branch: `feature/opshop-pickup`.

The current branch extends the Manual Dispatch Board with an OP SHOP PICKUP workflow while preserving the existing Delivery Order workflow. Implemented capabilities include:

- Database-backed login with operator attribution for Final Trip Summary save/export.
- Global Delivery Order Task Pool with search, urgency, and Delivery Date display filtering.
- Add, edit, cancel, assign, and unassign Delivery Orders.
- Driver Summary filtered by selected Delivery Date without changing Task Pool membership.
- Vehicle selection scoped by `driver_id + dispatch_date + delivery_date`.
- Product Details with pallet/bag exclusivity.
- Historical Final Trip Summary save, history, and Excel export from snapshot data, with OP SHOP pickups retained in a separate section.
- Final Trip Summary suburb-distance sorting using a static local estimate table.
- OP SHOP PICKUP source tables, pickup task records, board payloads, list modals, and Driver Summary display.
- Regular OP SHOP Pickup List for scheduled Regular pickups.
- Oncall OP SHOP Pickup List for office-created Oncall pickup requests.
- OP SHOP Template Management for office-managed Regular and Oncall template add, edit, and soft-disable.
- Regular and Oncall OP SHOP workbook import tools that populate OP SHOP locations and schedules/templates without directly creating pickup tasks.
- CI coverage on Ubuntu and Windows for Python compile/tests, frontend JavaScript syntax, and whitespace checks.
- Office-trial startup, SQLite backup/restore guidance, runtime configuration examples, and NAS/internal deployment notes.

Runtime SQLite databases, backups, local OP SHOP workbooks, and generated outputs are local operational data and remain ignored by Git.

## Core Workflow

1. Log in.
2. Select the Dispatch Date.
3. Review the Task Pool.
4. Use the OP SHOP PICKUP section when OP SHOP work is needed.
5. Use Manage OP SHOP Templates when a Regular schedule source or Oncall request template needs maintenance.
6. Assign Delivery Orders to Driver + `trip1` or `trip2`.
7. Open Regular or Oncall OP SHOP lists, choose assigned drivers, then close the list to apply OP SHOP assignments.
8. Select the Driver Summary Delivery Date.
9. Choose a Vehicle for Driver + Dispatch Date + Delivery Date.
10. Generate the Final Trip Summary, with Delivery trips and OP SHOP pickups kept in separate sections.
11. Save and Export the historical Final Trip Summary snapshot.

## Key Concepts

| Concept | Meaning |
| --- | --- |
| Dispatch Date | Operational board date used for assignments and dispatch-day workflow. |
| Delivery Date | Customer/order delivery date. It is editable for active Orders and scopes Driver Summary visibility for Delivery Orders. |
| Task Pool | Top board area for unassigned Delivery Orders plus OP SHOP list entry cards. |
| OP SHOP PICKUP section | Separate Task Pool section above Delivery Orders. It contains Regular and Oncall OP SHOP list entry cards. |
| Regular OP SHOP Pickup List | Scheduled Regular pickup list for the selected Regular pickup week. |
| Oncall OP SHOP Pickup List | Request-driven list that starts empty and only shows actual Oncall pickup tasks created by office staff. |
| OP SHOP Template Management | Office UI for adding, editing, and soft-disabling Regular and Oncall templates without requiring an importer run. |
| Driver Summary Delivery Date | Date filter that decides which assigned Delivery Orders and OP SHOP pickups appear inside driver cards. |
| Vehicle Assignment Scope | Vehicle selection is stored per `driver_id + dispatch_date + delivery_date`. |
| Final Trip Summary | Generated and saved historical snapshot scoped by `dispatch_date + delivery_date`; Delivery trips and OP SHOP pickups are captured in separate sections. |
| Product Details | Structured product lines attached to an Order and copied into saved Final Trip Summary snapshots. |
| Estimated Distance | Static suburb-level estimated straight-line distance from the Somerton warehouse, used only for Final Trip Summary sorting. |

## Authentication / Operator Attribution

- Login/register flow is backed by SQLite operator accounts.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, never in plain text.
- Save and Export requires a logged-in operator.
- Saved Final Trip Summaries record the operator account name.
- Forgot Password resets a password using `MANUAL_DISPATCH_ADMIN_RESET_CODE`; it never reveals the old password.
- This is lightweight MVP/demo authentication, not production-grade enterprise auth.

## Delivery Order Workflow

### Task Pool

- Shows active unassigned Delivery Orders globally.
- Search, urgency, and optional Delivery Date filters affect display only.
- Delivery Date filtering does not assign, unassign, or mutate Orders.
- Compact cards show core Order context such as invoice, company, suburb, delivery date, urgency, note preview, timing, and load-unit information.

### Order Lifecycle

- Add Order, Edit Order, and soft-delete Cancel Order flows.
- Delivery Date is editable for active Orders.
- Assigned Orders keep their existing assignment when editable fields change.
- Cancelled/finalized/soft-deleted Orders are excluded from the normal active workflow.
- Order Details uses a read-only form-style layout aligned with Edit Order.

### Product Details and Load Units

- Orders can store multiple Product Detail lines.
- Product Detail display is available from Order detail views.
- One Order uses either Pallets or Bags, never both.
- Product-line units must align with the Order load unit.
- Legacy Orders without product lines remain valid and display `No product details recorded.`

### Manual Assignment

- Assign Delivery Orders to a Driver and `trip1` or `trip2`.
- Reassign by assigning the same Order to another Driver/Trip.
- Unassign Orders back to the Task Pool.
- The workflow remains manual; no optimizer or auto-selection logic is introduced.

## Driver Summary / Trip Summary

- Driver cards remain stable while the Driver Summary Delivery Date changes.
- Delivery Orders render under each driver's `trip1` and `trip2` sections.
- Each driver card shows only assigned Delivery Orders matching the selected Driver Summary Delivery Date.
- If no matching Delivery Orders exist, the card stays visible with an empty state.
- Vehicle selection reflects the current `driver_id + dispatch_date + delivery_date` combination.
- OP SHOP pickups render separately under the driver-level `OP SHOP PICKUPS` section.

## OP SHOP Pickup Workflow

OP SHOP PICKUP is a separate manual task type. It is not stored as a Delivery Order.

### Task Pool OP SHOP Section

- The OP SHOP PICKUP section appears above Delivery Orders.
- It contains two list entry cards:
  - `Regular OP SHOP Pickup List`
  - `Oncall OP SHOP Pickup List`
- `Manage OP SHOP Templates` opens the office-facing template manager for Regular and Oncall template maintenance.
- The list entry cards open modal lists. Standard/Regular OP SHOP pickups are not rendered as dozens of direct Task Pool cards.

### Template Management

- Staff can add, edit, and disable `REGULAR` and `ON_CALL` templates from the `Manage OP SHOP Templates` modal.
- `REGULAR` templates are schedule sources for the Regular OP SHOP Pickup List.
- `ON_CALL` templates are candidates in the Oncall Add Pickup Task dropdown only. Adding or editing an Oncall template does not automatically create an actual pickup task.
- Disable is a soft disable: the schedule is retained with `status = On_Hold` and `active_flag = false`.
- Soft disable removes a template from active candidate/generation sources without deleting existing pickup tasks, historical assignments, or saved Final Trip Summaries.
- Changes to identity fields create/use the updated active schedule while retaining older schedule history for existing pickup tasks.

### Regular OP SHOP Pickup List

- Regular pickups come from active `REGULAR` schedules created in the UI or maintained through an approved workbook import.
- The board ensures and displays the Regular pickup week for the selected Dispatch Date.
- The Regular pickup window follows the office refresh rule:
  - Monday-Thursday Dispatch Dates show the current Monday-Friday week.
  - Friday Dispatch Dates include Friday today plus the following Monday-Friday.
  - Saturday-Sunday Dispatch Dates show the next Monday-Friday week.
- The workbook sheet weekday controls the pickup weekday. Pickup frequency text is display/source metadata and does not expand one row into extra weekdays in this Regular list flow.
- Each list row shows compact information: OP SHOP name, suburb, pickup date, assigned-to dropdown, and Edit when not locked.
- Closing the list applies visible Regular pickup assignments to Driver Summary using `trip1` internally.
- Add/Edit/Delete work at pickup-task level. Delete is a soft cancel, not a hard delete.

### Oncall OP SHOP Pickup List

- Oncall templates come from active `ON_CALL` schedules created in the UI or maintained through an approved workbook import.
- Creating or importing Oncall templates does not create actual pickup tasks.
- The Oncall list is empty until office staff clicks Add Pickup Task and chooses a template.
- Add Pickup Task lets staff choose an imported Oncall template, pickup date, assigned driver, and notes.
- MON/TUE/WED/THU/FRI Oncall templates can default to the matching weekday in the current week window.
- Gavin/no-fixed-day templates require a manually selected pickup date.
- Each created Oncall pickup row shows compact information: OP SHOP name, suburb, pickup date, assigned-to dropdown, and Edit when not locked.
- Closing the list applies visible Oncall pickup assignments to Driver Summary using `trip1` internally.
- Oncall pickups are request-driven. They are not automatically generated from all Oncall templates.

### Driver Summary Boundary

- Assigned OP SHOP pickups appear under each driver in a separate `OP SHOP PICKUPS` section.
- OP SHOP pickups are filtered by `pickup_date` matching the selected Driver Summary Delivery Date.
- OP SHOP pickups are not displayed inside Delivery Order `trip1` or `trip2` groups, even though assignment rows store `trip_no = trip1` for compatibility.
- OP SHOP pickups can be unassigned from Driver Summary when applicable.
- OP SHOP pickups do not affect Delivery Order totals, pallet totals, loose bag totals, or capacity totals.
- Final Trip Summary stores OP SHOP pickups in a separate `OP SHOP PICKUPS` snapshot section and never mixes them into Delivery Order Trip 1 / Trip 2 rows.

## Driver & Vehicle Specification

- Driver and Vehicle specification modal supports add, edit, safe delete, and availability toggles.
- Unavailable Drivers and Vehicles are hidden from operational dropdowns where appropriate.
- Main board refresh stays deferred until the modal closes.
- Vehicle selection belongs to Driver + Dispatch Date + Delivery Date, not to individual Orders or OP SHOP pickups.

## Final Trip Summary

- Generated summaries are scoped by selected Dispatch Date + selected Driver Summary Delivery Date.
- Saved summaries are historical snapshots, not live views of mutable Order/Driver/Vehicle data.
- Saved snapshots do not auto-update after later edits.
- Duplicate saves are rejected for the same Driver + Dispatch Date + Delivery Date.
- Generated-but-unsaved previews remain frontend-memory only and may be lost on refresh.
- Delivery Order Trip 1 / Trip 2 rows continue to support `ORDER` tasks only.
- OP SHOP PICKUP rows are saved independently in the Final Trip Summary `OP SHOP PICKUPS` section.
- Static frontend assets are served with `Cache-Control: no-store` for local/demo reliability.

## Excel Export

- Save and Export writes historical Final Trip Summary data and downloads XLSX output.
- Export uses saved snapshot records, not active assignment rows.
- Export includes Dispatch Date, Delivery Date, Saved By, Product Details, and estimated suburb distance.
- Generated At / Saved At are intentionally excluded from the workbook layout.
- OP SHOP PICKUP rows appear only in a separate `OP SHOP PICKUPS` section of Final Trip Summary export and are not written into Delivery trip tables.
- The independent OP SHOP Pickup Run Sheet export remains available for driver/office operational use.

## OP SHOP Data Model and APIs

OP SHOP data is stored separately from Delivery Orders.

Key OP SHOP tables:

- `opshop_locations`: deduplicated OP SHOP locations.
- `opshop_pickup_schedules`: Regular schedules and Oncall templates linked to locations.
- `opshop_pickup_tasks`: actual OP SHOP pickup tasks for specific dates.
- `final_trip_summary_opshop_pickup_rows`: saved OP SHOP pickup snapshots kept separate from Delivery Order final-summary rows.

Assignment storage:

- `manual_dispatch_assignments` uses `task_type + task_id` and supports both `ORDER` and `OPSHOP_PICKUP`.
- OP SHOP assignments use `task_type = OPSHOP_PICKUP` and `task_id = pickup_task_id`.

Board payload fields include:

- `scheduled_opshop_pickups`: Regular list items for the current Regular pickup week.
- `oncall_opshop_pickups`: created Oncall pickup tasks visible to the Oncall list.
- `assigned_opshop_pickups`: assigned OP SHOP pickups for Driver Summary.

OP SHOP API endpoints include:

- `GET /api/manual-dispatch/opshop-pickup-schedules?run_type=scheduled`
- `GET /api/manual-dispatch/opshop-pickup-schedules?run_type=oncall`
- `GET /api/manual-dispatch/opshop-templates?run_type=REGULAR|ON_CALL&include_inactive=false`
- `POST /api/manual-dispatch/opshop-templates`
- `PATCH /api/manual-dispatch/opshop-templates/{schedule_id}`
- `POST /api/manual-dispatch/opshop-templates/{schedule_id}/disable`
- `POST /api/manual-dispatch/opshop-pickups`
- `POST /api/manual-dispatch/opshop-pickups/oncall`
- `PATCH /api/manual-dispatch/opshop-pickups/{pickup_task_id}`
- `DELETE /api/manual-dispatch/opshop-pickups/{pickup_task_id}`
- `POST /api/manual-dispatch/opshop-pickups/weekly-assignments/apply`
- `POST /api/manual-dispatch/opshop-pickups/oncall-assignments/apply`

## Data Import Tools

The repository includes OP SHOP import tools for local/manual use. The real workbooks and runtime database are not committed to Git.

### Regular OP SHOP Import

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\import_regular_opshop_pickups_to_db.py `
  --file "<path-to-regular-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

Behavior:

- Reads the Regular OP SHOP workbook sheets.
- Imports/updates `opshop_locations` and `opshop_pickup_schedules` as `REGULAR` schedules.
- Uses the workbook sheet as the pickup weekday source.
- Preserves default assigned-driver information from the workbook.
- Creates a timestamped SQLite backup first when the target database already exists.
- Does not directly create `opshop_pickup_tasks`; board loading ensures visible Regular tasks from schedules.

### Oncall OP SHOP Import

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\import_oncall_opshop_pickups_to_db.py `
  --file "<path-to-oncall-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

Behavior:

- Reads MON/TUE/WED/THU/FRI/Gavin sheets.
- Imports/updates `opshop_locations` and `opshop_pickup_schedules` as `ON_CALL` templates.
- MON-FRI sheets store a fixed run day; Gavin templates have no fixed run day unless provided by data.
- Preserves default assigned-driver information from the workbook.
- Reports unresolved Assigned to aliases without crashing.
- Creates a timestamped SQLite backup first when the target database already exists.
- Does not directly create `opshop_pickup_tasks`; office staff create actual Oncall tasks from templates.

### Template Management and Importer Coexistence

- Workbook importer tools remain available for approved bulk source refreshes.
- UI-created templates and workbook-managed templates can coexist in SQLite, but a workbook refresh is not a backup of office changes made through the UI.
- A Regular or Oncall workbook importer run manages schedules for its corresponding run type; active UI-created templates absent from the workbook source may be set to `On_Hold`.
- Before rerunning importers after office-managed template changes, define which source is authoritative and back up the SQLite database.

## Distance Estimation

- Warehouse origin: `98-102 Hume Hwy, Somerton, VIC, 3062`.
- Runtime distance data lives in `backend/data/suburb_distances_from_somerton.json`.
- The current table contains **112** static suburb/locality records.
- Centroid inputs are documented as manually curated for demo sorting only in `tools/data/suburb_centroids_from_somerton_curated.json`.
- Distances are calculated as static suburb-level estimated straight-line distance using Haversine math.
- These values are not driving distance, not ETA, and not route optimization output.
- Unknown or unmapped suburbs fall back to `Unknown` and sort after known distances.
- QA validation is available through `tools/qa_suburb_distances_from_somerton.py`.

## Project Structure

- `backend/`: FastAPI app, manual-dispatch APIs, schemas, services, repositories, database bootstrap, and Excel export logic.
- `frontend/`: Static HTML/CSS/JavaScript app, modular renderers/actions/state/selectors, and the `frontend/app.js` entry point.
- `docs/`: Focused feature, phase, NAS, and office-trial documentation.
- `tests/`: Service, repository, API, static frontend, export, auth, product, OP SHOP, and distance QA coverage.
- `tools/`: Local utility scripts, office-trial startup/backup/restore scripts, OP SHOP import scripts, demo data reset tooling, and distance dataset QA/generation helpers.
- `requirements.txt`: Runtime Python dependencies.
- `requirements-dev.txt`: Route-test and browser-smoke development dependencies.

See [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md) for a deeper implementation map. That document may lag newer OP SHOP modules; use the code and tests as the current source of truth for OP SHOP details.

## Getting Started

These commands assume Windows PowerShell from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Configure local password-reset support before starting the server:

```powershell
$env:MANUAL_DISPATCH_ADMIN_RESET_CODE="replace-with-your-local-admin-reset-code"
```

For office trial use, start the app with:

```powershell
.\tools\start_office_trial.ps1
```

The default office-trial URL is:

```text
http://127.0.0.1:8130/frontend/
```

For developer startup without the helper script:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/frontend/
```

Create an end-of-day SQLite backup with:

```powershell
.\tools\backup_sqlite_db.ps1
```

Restore from a known-good backup with:

```powershell
.\tools\restore_sqlite_db.ps1 -BackupPath .\backups\<backup-file>.sqlite3
```

Local environment notes:

- Do not commit `.env`.
- `.env.example` may contain placeholders only.
- Runtime SQLite files are generated locally and ignored by Git.
- Backup files under `backups/` are generated locally and ignored by Git.
- The local database path is `data/manual_dispatch.sqlite3` unless `MANUAL_DISPATCH_DB_PATH` overrides it.
- `.env` can set `MANUAL_DISPATCH_DB_PATH`, `MANUAL_DISPATCH_HOST`, and `MANUAL_DISPATCH_PORT` for local startup scripts.

## NAS / Internal Office Deployment

Deployment preparation for NAS/internal-domain office use is documented under `docs/`.

Key deployment docs:

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)

Quick Docker Compose flow:

```powershell
Copy-Item .env.nas.example .env
docker compose up -d --build
```

Open:

```text
http://NAS_IP:8130/frontend/
```

The NAS deployment keeps the frontend and API same-origin through FastAPI, stores SQLite on the NAS local volume, and does not expose the app to the public internet by default.

## Validation / Tests

GitHub CI runs on pushes and pull requests for `main` and `feature/opshop-pickup`, plus manual `workflow_dispatch`. CI includes Ubuntu and Windows jobs covering:

- Python dependency installation.
- `python -m compileall backend tests tools`
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- syntax checks for every `frontend/**/*.js` file.
- `git diff --check`

Fast local checks for this branch commonly use:

```powershell
git diff --check
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

Useful targeted OP SHOP test modules include:

- `tests.test_import_regular_opshop_pickups_to_db`
- `tests.test_import_oncall_opshop_pickups_to_db`
- `tests.test_manual_dispatch_opshop_foundation`
- `tests.test_import_opshop_sheet1_to_db`
- `tests.test_manual_dispatch_opshop_pickup_generation`
- `tests.test_manual_dispatch_opshop_board_payload`
- `tests.test_manual_dispatch_opshop_assignment`
- `tests.test_manual_dispatch_opshop_pickup_list_management`
- `tests.test_manual_dispatch_opshop_template_management`
- `tests.test_manual_dispatch_frontend_static_contract`

Distance QA remains available through:

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\qa_suburb_distances_from_somerton.py
```

`frontend/overrides.js` does not currently exist. If it is added later, validate it with:

```powershell
node --check frontend/overrides.js
```

## Demo Data / Local Data

- Demo Orders may still use dated sample records such as `2026-05-05`.
- Dispatch Date defaults to the browser's local current date.
- Because Delivery Order Task Pool membership is global, future Delivery Date Orders can still appear before their Delivery Date when they are active and unassigned.
- Driver Summary and Final Trip Summary remain controlled by the selected Driver Summary Delivery Date.
- Real OP SHOP workbooks are local/manual inputs and should not be committed unless they are intentionally anonymized fixtures.
- Runtime SQLite data is local and should not be committed.

## Documentation Index

### Data Model and Schema

- [Data model direction](docs/manual-dispatch-board-data-model.md)
- [Schema design](docs/manual-dispatch-board-schema.md)

### Backend / API / Persistence

- [Phase 5 backend API skeleton](docs/manual-dispatch-board-phase5.md)
- [Phase 6 SQLite persistence](docs/manual-dispatch-board-phase6.md)
- [Phase 8 frontend/backend integration](docs/manual-dispatch-board-phase8.md)
- [Phase 9 Excel export](docs/manual-dispatch-board-phase9.md)

### Order Lifecycle

- [Phase 10A-1 Add Order](docs/manual-dispatch-board-phase10a1-add-order.md)
- [Phase 10A-3 Edit Order](docs/manual-dispatch-board-phase10a3-edit-order.md)
- [Phase 10A-4 Cancel Order](docs/manual-dispatch-board-phase10a4-cancel-order.md)
- [Phase 10A-5 Order search and filter](docs/manual-dispatch-board-phase10a5-order-filter.md)
- [Phase 16 Product Details and load-unit exclusivity](docs/manual-dispatch-board-phase16-product-details.md)
- [Phase 17 Order Details UI alignment](docs/manual-dispatch-board-phase17-order-details-ui.md)

### Driver / Vehicle Specification

- [Driver Summary Delivery Date behavior](docs/manual-dispatch-board-driver-summary-delivery-date.md)
- [Driver & Vehicle Specification](docs/manual-dispatch-board-driver-vehicle-specification.md)
- [Phase 12 deferred specification refresh](docs/manual-dispatch-board-phase12-ui-stability.md)
- [Phase 12C specification modal rebuild](docs/manual-dispatch-board-phase12c-specification-modal-rebuild.md)

### Final Trip Summary

- [Frontend snapshot behavior](docs/manual-dispatch-board-final-trip-summary.md)
- [Global Final Summary save](docs/manual-dispatch-board-global-final-summary-save.md)
- [Phase 10G Final Summary persistence](docs/manual-dispatch-board-phase10g-final-summary-persistence.md)
- [Phase 13 closed-loop stabilization](docs/manual-dispatch-board-phase13-final-summary-closed-loop.md)
- [Phase 14 redesign and demo reset](docs/manual-dispatch-board-phase14-final-summary-redesign.md)
- [Phase 14B save and export polish](docs/manual-dispatch-board-phase14b-final-summary-save-export.md)
- [Phase 15 login and operator attribution](docs/manual-dispatch-board-phase15-login-final-summary-operator.md)
- [Phase 18 suburb distance sorting](docs/manual-dispatch-board-phase18-suburb-distance-sorting.md)
- [Phase 19 release candidate QA](docs/manual-dispatch-board-phase19-release-candidate-qa.md)
- [Phase 20 office trial deployment and backup](docs/manual-dispatch-board-phase20-office-trial-deployment.md)
- [Office trial checklist](docs/manual-dispatch-board-office-trial-checklist.md)

### NAS / Office Deployment

- [NAS and internal DNS deployment](docs/nas-cpanel-internal-dns-deployment.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
- [NAS deployment validation checklist](docs/nas-deployment-validation-checklist.md)

### UI Stability / Refactor Notes

- [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md)
- [Phase 0 governance](docs/manual-dispatch-board-phase0.md)
- [Phase 2 frontend skeleton](docs/manual-dispatch-board-phase2.md)
- [Phase 3 manual assignment flow](docs/manual-dispatch-board-phase3.md)
- [Phase 4 vehicle selection](docs/manual-dispatch-board-phase4.md)
- [Phase 7 business hints](docs/manual-dispatch-board-phase7.md)
- [Phase 10A-0 compact Order card UI](docs/manual-dispatch-board-phase10a0-ui-refinement.md)

## Explicit Non-Goals

Manual Dispatch Board remains a manual dispatch workflow. It does not claim or implement:

- auto-dispatch
- CP-SAT
- route optimization
- ETA calculation
- live geocoding
- Google Maps logic
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- capacity blocking
- zone blocking
- production-grade enterprise authentication
