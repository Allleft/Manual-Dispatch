# Manual Dispatch Board

Manual Dispatch Board is a FastAPI, SQLite, and vanilla JavaScript application for office staff to manually coordinate **Order Delivery** and **OP SHOP Pickup** work.

This is a manual operational system. It deliberately does **not** perform automatic dispatch, route optimisation, ETA calculation, geocoding, map integration, automatic driver or vehicle selection, automatic trip planning, or capacity/zone-based blocking.

## What This Branch Delivers

`feature/separate-delivery-and-opshop-workspaces` separates the previous shared workflow into two independent operational workspaces.

| Area | Order Delivery | OP SHOP Pickup |
| --- | --- | --- |
| Task type | `ORDER` | `OPSHOP_PICKUP` |
| Operational snapshot | Delivery Run Sheet | Pickup Collection |
| Generated state | Reserves captured Delivery Orders and the selected vehicle target | Reserves captured pickup tasks |
| Saved state | Locks only Delivery assignments and vehicle changes for the driver/date | Locks only OP SHOP pickup changes for the driver/date |
| Export | Delivery-only workbook | OP SHOP-only workbook |
| Totals | Pallets, loose bags, and vehicle capacity | No Delivery load or capacity totals |

A saved Delivery Run Sheet does not lock OP SHOP Pickup work. A saved Pickup Collection does not lock Delivery work. The same driver/date may therefore have one saved Delivery Run Sheet and one saved Pickup Collection.

Legacy Final Trip Summary records remain available for history and migration compatibility, but new scoped work is performed through the two workspace flows below.

## Workspace Navigation

After login, Home provides the two workspace entry points and checks migration readiness before staff begin scoped work.

### Order Delivery

| Route | Purpose |
| --- | --- |
| `#delivery/task-pool` | Review active unassigned Delivery Orders, filter them, create/edit/cancel orders, import Attache invoices, and assign each order to a driver and trip. |
| `#delivery/trip-summary` | Review Orders by driver and Delivery Date, move Orders between Trip 1 and Trip 2, assign vehicles, and generate a Delivery Run Sheet. |
| `#delivery/run-sheet` | Review current Generated and Saved Delivery Run Sheets, cancel Generated sheets, save, and export. |
| `#delivery/history` | Review Saved Delivery Run Sheet history and re-export immutable snapshots. |

### OP SHOP Pickup

| Route | Purpose |
| --- | --- |
| `#opshop/task-pool/regular` | Review Regular pickup tasks generated from active Regular schedules and apply assignment drafts. |
| `#opshop/task-pool/oncall` | Create and manage request-driven Oncall pickup tasks from active templates. |
| `#opshop/task-pool/countryside` | Assign Countryside route groups, then manage their live pickup tasks and assignment drafts. |
| `#opshop/templates` | Manage Regular/Oncall templates and Countryside route groups and memberships. |
| `#opshop/trip-summary` | Review assigned pickups by driver and Pickup Date, then generate a Pickup Collection. |
| `#opshop/collections` | Review Generated and Saved Pickup Collections, cancel Generated collections, save, and export. |

Workspace navigation is hash-based. Browser refresh, copied links, Back, and Forward retain the active workspace route. Switching between Regular, Oncall, and Countryside preserves pending OP SHOP assignment drafts rather than silently applying or discarding them.

## Dates and Scope

- **Dispatch Date** identifies the operational board session loaded by each workspace.
- **Delivery Date** identifies the day being reviewed in Delivery Trip Summary and Delivery Run Sheets.
- **Pickup Date** identifies the day being reviewed in OP SHOP Trip Summary and Pickup Collections.
- Delivery Orders, OP SHOP tasks, scoped snapshots, locks, histories, and Excel exports are intentionally separated.

## Order Delivery Workflow

1. Open **Order Delivery → Task Pool**.
2. Add a Delivery Order manually, import text-based Attache invoice PDFs, or filter active unassigned Orders by search, urgency, or Delivery Date.
3. Select a Driver and Trip 1 or Trip 2 for each Order and assign it manually.
4. Assigned Orders leave the Task Pool globally and remain unavailable there until staff manually unassign them; Generated/Saved Run Sheet snapshots also reserve captured Orders globally.
5. Open **Trip Summary**, select the Delivery Date, review the driver trips, and select a vehicle where required.
6. Select Generate for a driver/date and confirm the information in the confirmation modal.
7. Generation creates an immutable `GENERATED` Delivery Run Sheet snapshot and reserves its captured Orders and vehicle target.
8. From **Run Sheets**, either cancel an incorrect Generated sheet or save/export it. Cancel Generated removes only the snapshot reservation; the original Order assignments remain in Trip Summary until staff manually unassign them. Saving promotes the same snapshot to `SAVED`; it does not rebuild it from mutable live records.
9. Saved Delivery Run Sheets remain immutable history and can be re-exported from their stored snapshot rows.

### Delivery Orders and Attache Invoice Import

Delivery Orders support manual add, edit, and soft-cancel operations. Delivery Task Pool cards are sorted Urgent-first and support search across identifiers, customer details, address, product, and notes.

`Import Attache Invoices` supports one or more text-based Attache invoice PDFs:

- Uploading a PDF only creates a preview; it does not write to SQLite.
- Staff can correct parsed delivery fields before confirmation.
- Existing invoice-number duplicates are surfaced and are not selected for import by default.
- Confirmed rows use the standard Delivery Order creation path and appear in the Delivery Task Pool.
- Imported product lines use delivery product fields only; invoice accounting totals, GST, and payment information are not imported as delivery items.
- Importing invoices does not change OP SHOP tasks, Pickup Collections, or OP SHOP locks.

### Delivery Run Sheet Locking

- Active Delivery Order assignments reserve those Orders globally from every Delivery Task Pool until staff manually unassign them.
- `GENERATED` Delivery Run Sheets reserve captured Delivery Orders globally and reserve the selected driver/date vehicle target until cancelled or saved.
- Cancelling a `GENERATED` Delivery Run Sheet releases only the snapshot reservation; still-assigned Orders remain hidden from Task Pool and return to their original Trip Summary assignment context.
- `SAVED` Delivery Run Sheets block further Delivery assignment and vehicle changes for their driver/date.
- Delivery locks are enforced by the scoped Delivery services and do not block OP SHOP work.

## OP SHOP Pickup Workflow

1. Open **OP SHOP Pickup → Task Pool** and choose Regular, Oncall, or Countryside.
2. Manage source templates from **Manage Templates** when required.
3. Review or create live pickup tasks, select assignees, and use **Apply Assignment Changes** for pending assignment drafts.
4. Open **Trip Summary**, select the Pickup Date, and review tasks grouped under each driver and category.
5. Select Generate for a driver/date and confirm the Pickup Collection details in the confirmation modal.
6. Generation creates an immutable `GENERATED` Pickup Collection and reserves the captured pickup tasks.
7. From **Pickup Collections**, cancel an incorrect Generated collection or save/export it as a `SAVED` collection.
8. Saved Pickup Collections are immutable history and export from stored snapshot rows rather than live pickup data.

### Regular Pickups

- Regular tasks are ensured from active `REGULAR` schedules for the visible operational week.
- Monday–Thursday Dispatch Dates show the current Monday–Friday pickup week.
- Friday shows Friday plus the following Monday–Friday; weekend Dispatch Dates show the next Monday–Friday.
- Past pickup-date groups are collapsed by default. Current and future date groups are expanded by default and can be toggled without losing the page position.
- Template default-driver information is materialised once when an eligible actual task is created or by the controlled source-driver backfill tool.
- Later manual changes, including an explicit `Unassigned`, remain local drafts until Apply and are not overwritten by refresh or subtype navigation.

### Oncall Pickups

- Oncall templates are sources only; importing or creating a template does not automatically create a live pickup task.
- Staff create a live Oncall task through **Add Pickup Task**.
- Template search matches company name, suburb, and street address.
- A weekday template can provide a matching default Pickup Date. A no-fixed-day template requires staff to select a date.
- A source-backed default driver is applied once on task creation when eligible; ad-hoc or no-default tasks remain Unassigned.

### Countryside Pickups

Countryside is an OP SHOP subcategory, not a third dispatch product:

| Field | Value |
| --- | --- |
| `task_type` | `OPSHOP_PICKUP` |
| `run_type` | `ON_CALL` |
| `pickup_category` | `COUNTRYSIDE` |

- A Countryside workbook sheet represents a route group.
- One OP SHOP location may belong to more than one route group.
- Route groups and memberships are source/template data; importing them does not create live pickup tasks.
- **Assign Route Group** creates or restores one live task for every active membership on the selected Pickup Date and assigns the selected driver.
- Route create/rename/disable and membership add/move/remove operations are available from `#opshop/templates`.
- Historical pickup tasks and saved snapshots are not deleted when route definitions change.

### Pickup Collection Locking

- `GENERATED` Pickup Collections reserve the captured OP SHOP tasks until cancelled or saved.
- `SAVED` Pickup Collections block only OP SHOP pickup mutations for their driver/date.
- Delivery Run Sheet locks and Pickup Collection locks are independent.
- Saved collections are exported from immutable snapshot rows, not mutable live tasks.

## Legacy Final Summary Compatibility and Migration

The legacy Final Trip Summary routes, tables, history, and workbook behavior remain available for compatibility. They are not rewritten or deleted by this branch.

Home performs a read-only workspace migration-readiness check:

- Any legacy Final Summary with `status = GENERATED` blocks both scoped workspaces.
- A legacy `SAVED` summary that does not have the required independent workspace record blocks only the affected workspace.
- Normal application traffic never migrates records automatically.

Use the migration tool during an approved maintenance window to copy legacy `SAVED` Final Summary snapshots into independent workspace history.

```powershell
# Dry run: read-only, no backup and no writes
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3"

# Apply: explicit double confirmation, timestamped backup, one transaction
.\tmp\route-test-venv\Scripts\python.exe .\tools\migrate_legacy_final_summaries_to_workspaces.py `
  --db-path "data\manual_dispatch.sqlite3" `
  --apply --yes
```

The migration is additive and idempotent. It does not delete or rewrite legacy Final Summary headers, legacy rows, live Orders, live pickups, or assignments. See [the migration runbook](docs/separate-delivery-and-opshop-workspaces-migration.md) before applying it.

## Data Model

| Table | Responsibility |
| --- | --- |
| `manual_dispatch_assignments` | Assignment records keyed by `task_type + task_id`, supporting `ORDER` and `OPSHOP_PICKUP`. |
| `opshop_locations` | Deduplicated OP SHOP location records. |
| `opshop_pickup_schedules` | Regular schedules, Oncall templates, and Countryside route memberships. |
| `opshop_pickup_tasks` | Actual dated OP SHOP pickup work. |
| `opshop_countryside_route_groups` | Countryside route-group definitions. |
| `delivery_run_sheets` / `delivery_run_sheet_rows` | Independent Generated/Saved Delivery Run Sheet snapshots. |
| `opshop_pickup_collections` / `opshop_pickup_collection_rows` | Independent Generated/Saved OP SHOP Pickup Collection snapshots. |
| `final_trip_summaries` and child tables | Legacy Final Summary compatibility/history data. |

## Code Structure

```text
backend/
  api/manual_dispatch.py                         # HTTP routes
  repositories/                                  # SQLite and in-memory persistence
  services/manual_dispatch/
    delivery_workspace_board_service.py
    delivery_workspace_mutation_service.py
    delivery_run_sheet_service.py
    delivery_run_sheet_lock.py
    opshop_workspace_board_service.py
    opshop_workspace_mutation_service.py
    opshop_pickup_collection_service.py
    opshop_pickup_collection_lock.py
    logbook_file_service.py                         # Append-only JSON Lines System Logbook
    workspace_migration_readiness_service.py
  services/*_excel_export_service.py             # Snapshot-only workbook exporters

frontend/
  app.js                                         # Authenticated workspace hash routing
  js/actions/workspace-actions.js                # Scoped workspace workflows
  js/render/delivery-workspace-renderer.js       # Delivery UI
  js/render/opshop-workspace-renderer.js         # OP SHOP UI
  js/render/workspace-home-renderer.js           # Home/readiness UI
  js/render/workspace-navigation-renderer.js     # Header navigation

tools/
  migrate_legacy_final_summaries_to_workspaces.py
  import_regular_opshop_pickups_to_db.py
  import_oncall_opshop_pickups_to_db.py
  import_countryside_opshop_pickups_to_db.py
  backfill_opshop_source_driver_assignments.py
  read_logbook.py                                # Read-only System Logbook query CLI

tests/
  test_logbook_reader.py                         # Reader and frontend logout static contracts
  test_workspace_*.py                            # Scoped APIs, locks, snapshots, migration, and frontend shell contracts
```

The workspace renderers do not call the API directly. API calls are centralised in `frontend/js/api/manual-dispatch-api.js`; shared state is in `frontend/js/state/`; workflow behavior belongs in `frontend/js/actions/`; rendering belongs in `frontend/js/render/`.

## Quick Start

Examples below use Windows PowerShell from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

# Optional: use a safe local test database instead of the runtime database.
$env:MANUAL_DISPATCH_DB_PATH="data\manual_dispatch_test.sqlite3"

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

- Frontend: `http://127.0.0.1:8000/frontend/`
- Health check: `http://127.0.0.1:8000/health`

For the office-trial configuration:

```powershell
.\tools\start_office_trial.ps1
```

## Import and Maintenance Tools

Real office workbooks are local inputs and must not be committed.

### Regular and Oncall workbook imports

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\import_regular_opshop_pickups_to_db.py `
  --file "<path-to-regular-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"

.\tmp\route-test-venv\Scripts\python.exe .\tools\import_oncall_opshop_pickups_to_db.py `
  --file "<path-to-oncall-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

These import/update source schedules and templates. They do not create all future live Oncall tasks automatically.

### Countryside workbook import

```powershell
.\tmp\route-test-venv\Scripts\python.exe .\tools\import_countryside_opshop_pickups_to_db.py `
  --file "<path-to-countryside-opshop-workbook.xlsx>" `
  --db-path "data\manual_dispatch.sqlite3"
```

The importer manages workbook-backed route groups and memberships while preserving UI-created route groups and memberships.

### Source-driver backfill

`tools/backfill_opshop_source_driver_assignments.py` is a controlled maintenance tool for materialising approved source-driver defaults. Start with a dry run, resolve ambiguity or unknown alias reports, back up SQLite, and only then use its explicit apply mode.

## System Logbook

The System Logbook is file-based runtime audit data. There is no frontend Logbook page and no logbook database table. Files use JSON Lines format, with one valid JSON object per non-blank line.

The default directory is `data/logbook/`, and monthly files are named `manual_dispatch_logbook_YYYY-MM.txt`. Set `MANUAL_DISPATCH_LOGBOOK_DIR` to override the directory. During normal application operation, these files are append-only. `data/logbook/` is gitignored, and logbook writing is best-effort so a logging failure does not block Delivery or OP SHOP business operations.

Logbook files may contain operational names, order identifiers, customer or company names, driver names, vehicle registrations, and OP SHOP information. Treat them as private runtime data: do not commit them, attach them to public issues, or share them without appropriate access controls.

`tools/read_logbook.py` is a read-only query tool. It resolves the directory from `--logbook-dir`, then `MANUAL_DISPATCH_LOGBOOK_DIR`, then `data/logbook/`. By default it reads all matching monthly files, returns matching entries in chronological order, applies no hidden result limit, and prints concise text. Use `--format jsonl` for JSON Lines output. Malformed lines produce a filename-and-line warning on stderr while the query continues.

Available filters are `--date-from`, `--date-to`, `--workspace`, `--actor`, `--action`, `--result`, `--driver`, `--entity-id`, and `--search`; use `--limit` only when an explicit result cap is wanted. Date boundaries are inclusive. Run `tools\read_logbook.py --help` for the complete command reference.

```powershell
.\tmp\route-test-venv\Scripts\python.exe tools\read_logbook.py

.\tmp\route-test-venv\Scripts\python.exe tools\read_logbook.py `
  --workspace DELIVERY `
  --actor "Office Operator"

.\tmp\route-test-venv\Scripts\python.exe tools\read_logbook.py `
  --date-from 2026-07-01 `
  --date-to 2026-07-31 `
  --entity-id 184068

.\tmp\route-test-venv\Scripts\python.exe tools\read_logbook.py `
  --action PICKUP_COLLECTION_SAVED `
  --format jsonl
```

## Runtime Data and Repository Hygiene

Never commit runtime or office data:

- `.env` files;
- `data/*.sqlite`, `data/*.sqlite3`, and SQLite `-wal` / `-shm` files;
- backups and generated workbook outputs;
- real customer or OP SHOP workbooks;
- editor, cache, dependency, and temporary test files.

`AGENTS.md` is intentionally tracked because it is the shared project governance document for architecture, testing, release, and SQLite safety. Personal singular `AGENT.md` scratch notes and one-off refactor handoff artifacts are ignored by `.gitignore` and must not replace `AGENTS.md`.

Before database imports, maintenance tools, NAS updates, or migration apply operations, create and verify a SQLite backup. Keep one application or maintenance process connected to the office SQLite database by default.

## Validation

Run the relevant focused checks during normal changes. For System Logbook changes, run:

```powershell
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_logbook_file_service -v
.\tmp\route-test-venv\Scripts\python.exe -m unittest tests.test_logbook_reader -v
```

Before a release or when requested, run the full local suite:

```powershell
git diff --check
git diff --cached --check
python -m compileall backend tests tools
python -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

Key workspace coverage is in:

- `tests/test_workspace_api_and_exports.py`
- `tests/test_workspace_services.py`
- `tests/test_workspace_scoped_boards.py`
- `tests/test_workspace_scoped_mutations.py`
- `tests/test_workspace_snapshot_persistence.py`
- `tests/test_workspace_legacy_migration.py`
- `tests/test_workspace_safety_hardening.py`
- `tests/test_workspace_frontend_shell.py`
- `tests/test_opshop_pickup_collection_generation.py`

Browser smoke testing remains necessary for route navigation, assignment drafts, confirmation modals, Generated → Saved lifecycle, saved history/export, and office data workflows.

## Further Documentation

- [Separate Delivery and OP SHOP Workspaces specification](docs/separate-delivery-and-opshop-workspaces-spec.md)
- [Legacy Final Summary workspace migration runbook](docs/separate-delivery-and-opshop-workspaces-migration.md)
- [OP SHOP workspace smoke-test checklist](docs/opshop-workspace-smoke-test-checklist.md)
- [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md)
- [OP SHOP source-driver assignment release preflight](docs/opshop-source-driver-assignment-release-preflight.md)
- [NAS release update checklist](docs/nas-release-update-checklist.md)
