# Manual Dispatch Board

Manual Dispatch Board is a small FastAPI + vanilla HTML/CSS/JavaScript app for office staff who manually dispatch delivery Orders to Drivers, Trips, and Vehicles.

It supports a manual workflow:

1. Load a Dispatch Date.
2. Review unassigned Orders in the global Task Pool.
3. Assign Orders to a Driver and `trip1` or `trip2`.
4. Choose a Driver Summary Delivery Date.
5. Choose a Vehicle for a Driver + Dispatch Date + Delivery Date.
6. Generate a locked Final Trip Summary snapshot for that Dispatch Date + Delivery Date.
7. Save and export saved Final Trip Summary history.

This project is intentionally not a route optimizer. It does not automatically select drivers, vehicles, trips, routes, ETAs, or capacity plans.

## Current Status

Current status: Phase 16 on `feature/manual-dispatch-board`.

Implemented focus areas:

- Manual dispatch board backed by SQLite persistence.
- Order lifecycle: Add, Edit, Cancel via soft delete.
- Driver and Vehicle master-data management through the Driver & Vehicle Specification modal.
- Final Trip Summary generation, save/history, and Excel export from saved snapshot records.
- Lightweight database-backed operator login for Final Trip Summary attribution.
- Structured Product Details for Orders, including saved Final Trip Summary snapshots and Excel export.
- Order load validation that allows either Pallets or Bags, never both on the same Order.
- Dispatch Date defaults to the browser's local current date. Demo data may still be dated `2026-05-05`; Task Pool is global, while Driver Summary visibility depends on the selected Driver Summary Delivery Date.

Runtime SQLite database files are local and ignored by Git.

## Features

### Dispatch Board

- Login/register gate using Account Name + Password before the board can be used.
- Logged-in operator badge and Logout button in the page header.
- Dispatch Date board loading for the operational assignment date.
- Driver Summary Delivery Date controls which assigned customer delivery-date Orders are shown inside Driver cards.
- Top-bottom layout:
  - Top: Task Pool.
  - Bottom: Trip Summary.
- Task Pool is a global unassigned active Order pool and is not filtered by Driver Summary Delivery Date.
- Compact Order cards show Invoice #, Company, Suburb, Delivery Date, load quantity, urgency, note preview, and start time.
- Task Pool search, urgency, and optional Delivery Date display filters apply only to visible unassigned Orders; they do not change Task Pool membership.
- Clicking an Order card opens a detail popup.

### Manual Assignment

- Assign Orders to a Driver and `trip1` or `trip2`.
- Reassign Orders by assigning the same Order again to a different Driver/Trip.
- Unassign Orders back to the Task Pool.
- Pending Driver/Trip selections are preserved after assigning another Order.
- Trip Summary groups assigned Orders by Driver and Trip.
- Vehicle selection is stored at Driver + Dispatch Date + Delivery Date level, not per Order.
- Vehicle selection can be cleared back to no selected vehicle.
- Pallet-only and vehicle-capacity hints are display-only and non-blocking.

### Order Lifecycle

- Add Order popup saves new Orders to SQLite.
- Add Order defaults delivery date to the currently selected Dispatch Date.
- Edit Order supports operational fields, including editable Delivery Date for active Orders.
- Add/Edit Order supports Product Details with multiple same-unit product lines.
- Orders use either Pallets or Bags, never both; product-line units must match that Order load unit.
- Order detail popups expose a `Product Detail` view and show `No product details recorded.` for legacy Orders without product lines.
- Editing an assigned Order preserves the existing Driver + Trip assignment.
- Cancel Order uses soft delete with `status = CANCELLED`.
- Cancelled Orders are hidden from Task Pool and normal active exports.
- Assigned Orders must be unassigned before cancellation.
- Physical Delete Order is not implemented.

### Driver & Vehicle Specification

- Driver & Vehicle Specification modal lists Drivers and Vehicles.
- Add, edit, safe delete, and availability toggle are supported for Drivers and Vehicles.
- Availability controls main board visibility:
  - Unavailable Drivers are hidden from Driver dropdowns and empty Trip Summary cards.
  - Unavailable Vehicles are hidden from Choose Vehicle dropdowns.
- Main board refresh is deferred until the specification modal closes.
- Preferred Zone can be stored in specifications but remains hidden from the main dispatch board.

### Final Trip Summary

- Generate creates a locked frontend snapshot from a Driver's current assigned Orders for the selected Driver Summary Delivery Date and selected Vehicle.
- Generated snapshots preserve Driver name, vehicle rego, trip grouping, totals, Product Details, and Order row details at generation time.
- Generated Orders are unassigned through the backend API and hidden from Task Pool in the same browser session.
- Generated-but-unsaved Final Trip Summary snapshots are frontend-memory only and can be lost on refresh.
- One global Save and Export button saves all generated unsaved summaries.
- Save and Export requires a logged-in operator account.
- Saved Final Trip Summaries are persisted to SQLite as historical snapshots.
- Saved summaries record the logged-in account name as the operator attribution.
- Saving marks included Orders as `FINALIZED`.
- `FINALIZED` Orders are hidden from Task Pool and editable Trip Summary.
- Saved history can be loaded by History Date in the Final Trip Summary section.
- Saved summaries do not update when live Orders, Drivers, or Vehicles are later edited.
- Duplicate saved summaries for the same Driver + Dispatch Date + Delivery Date are rejected.
- Final Trip Summary Excel export uses saved snapshot fields, includes Dispatch Date, Delivery Date, `Saved By`, `Product Details`, and excludes Generated At / Saved At.
- The older active-assignment Excel export route remains in the backend for compatibility, but it is not exposed as a top-level frontend button.

### Operator Accounts

- Operator accounts are stored in SQLite.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, not plain text.
- Login returns account identity only: account id and account name.
- Forgot Password resets the password; it does not recover or reveal the old password.
- Password reset requires an administrator reset code from `MANUAL_DISPATCH_ADMIN_RESET_CODE`.
- Raw passwords, password hashes, and salts are not displayed, exported, logged, or returned by the API.
- This is lightweight MVP/demo login, not production enterprise authentication.

## Project Structure

- `backend/`: FastAPI app, API routes, schemas, services, SQLite repository, schema initialization, and Excel export services.
- `frontend/`: Static board UI served by FastAPI at `/frontend/`; implemented with plain HTML, CSS, and JavaScript.
- `docs/`: Phase notes and design documentation for data model, API/persistence, UI behavior, and final summaries.
- `tests/`: Python unittest coverage for service, repository, lifecycle, final summary, export, and route-level behavior.
- `tools/`: Manual development utilities, including demo Order reset tooling.
- `requirements.txt`: Runtime Python dependencies: FastAPI, Uvicorn, and openpyxl.
- `requirements-dev.txt`: Development/test dependencies for route-level API tests and browser smoke tests.

For a more detailed developer map, see [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md).

## Getting Started

These commands assume PowerShell on Windows from the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For the full validation suite, including FastAPI `TestClient` route tests and Playwright browser smoke tests, install development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the backend and static frontend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open the board:

```text
http://127.0.0.1:8000/frontend/
```

The app creates or migrates the local SQLite database at:

```text
data/manual_dispatch.sqlite3
```

That database is runtime data and is ignored by Git.

### Browser Test Dependency

```powershell
python -m playwright install chromium
```

For local-only browser installs inside an ignored workspace folder, set `PLAYWRIGHT_BROWSERS_PATH` to a path under `tmp/` before installing.

### Local Admin Reset Code

Forgot Password uses a local environment variable:

```powershell
$env:MANUAL_DISPATCH_ADMIN_RESET_CODE="replace-with-your-local-admin-reset-code"
```

The reset code must not be committed. If it is not set, password reset is disabled.

## Validation / Tests

Recommended checks:

```powershell
python -m compileall backend tests
python -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

The test suite uses temporary SQLite databases for automated tests. Do not commit runtime databases, cache folders, generated Excel files, or temporary logs.

## Demo Data

The repository includes seed/demo data for local development. Recent demo reset tooling creates 20 Victoria Orders dated `2026-05-05` while preserving Driver and Vehicle master data.

The Dispatch Date input now defaults to the browser's local current date. Task Pool is global for active unassigned Orders, so demo Orders can still appear even when their customer Delivery Date differs from the Dispatch Date. Use the Task Pool Delivery Date filter when you want a narrower visible queue; Driver Summary and Final Trip Summary use their separate Driver Summary Delivery Date, so select `2026-05-05` there when working with the seeded demo Orders.

The demo reset script is manual/dev-only and must not run automatically on app startup.

## Non-Goals

Manual Dispatch Board is a manual office workflow tool, not an optimization engine.

Do not add these unless explicitly requested:

- auto-assignment
- CP-SAT
- route optimization
- ETA calculation
- geocoding
- Google Maps logic
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- automatic route sequencing
- capacity-based blocking
- zone-based blocking
- external auth providers
- role-based access control
- MySQL/MariaDB

## Documentation / Phase Notes

### Data Model and Governance

- [Phase 0 governance](docs/manual-dispatch-board-phase0.md)
- [Data model direction](docs/manual-dispatch-board-data-model.md)
- [Schema design](docs/manual-dispatch-board-schema.md)

### Backend, API, Persistence, and Export

- [Phase 5 backend API skeleton](docs/manual-dispatch-board-phase5.md)
- [Phase 6 SQLite persistence](docs/manual-dispatch-board-phase6.md)
- [Phase 8 frontend/backend integration](docs/manual-dispatch-board-phase8.md)
- [Phase 9 Excel export](docs/manual-dispatch-board-phase9.md)

### Frontend Board Behavior

- [Phase 2 frontend skeleton](docs/manual-dispatch-board-phase2.md)
- [Phase 3 manual assignment flow](docs/manual-dispatch-board-phase3.md)
- [Phase 4 vehicle selection](docs/manual-dispatch-board-phase4.md)
- [Driver Summary Delivery Date behavior](docs/manual-dispatch-board-driver-summary-delivery-date.md)
- [Phase 7 business hints](docs/manual-dispatch-board-phase7.md)
- [Phase 10A-0 compact Order card UI](docs/manual-dispatch-board-phase10a0-ui-refinement.md)

### Order Lifecycle

- [Phase 10A-1 Add Order](docs/manual-dispatch-board-phase10a1-add-order.md)
- [Phase 10A-3 Edit Order](docs/manual-dispatch-board-phase10a3-edit-order.md)
- [Phase 10A-4 Cancel Order](docs/manual-dispatch-board-phase10a4-cancel-order.md)
- [Phase 10A-5 Order search and filter](docs/manual-dispatch-board-phase10a5-order-filter.md)

### Final Trip Summary

- [Frontend snapshot behavior](docs/manual-dispatch-board-final-trip-summary.md)
- [Global Final Summary save](docs/manual-dispatch-board-global-final-summary-save.md)
- [Phase 10G Final Summary persistence](docs/manual-dispatch-board-phase10g-final-summary-persistence.md)
- [Phase 13 closed-loop stabilization](docs/manual-dispatch-board-phase13-final-summary-closed-loop.md)
- [Phase 14 redesign and demo reset](docs/manual-dispatch-board-phase14-final-summary-redesign.md)
- [Phase 14B save and export polish](docs/manual-dispatch-board-phase14b-final-summary-save-export.md)
- [Phase 15 login and operator attribution](docs/manual-dispatch-board-phase15-login-final-summary-operator.md)
- [Phase 16 Product Details and load-unit exclusivity](docs/manual-dispatch-board-phase16-product-details.md)

### Driver, Vehicle, and UI Stability

- [Driver & Vehicle Specification](docs/manual-dispatch-board-driver-vehicle-specification.md)
- [Phase 12 deferred specification refresh](docs/manual-dispatch-board-phase12-ui-stability.md)
- [Phase 12C specification modal rebuild](docs/manual-dispatch-board-phase12c-specification-modal-rebuild.md)
