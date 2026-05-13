# Manual Dispatch Board

## Project Overview

Manual Dispatch Board is a FastAPI + vanilla HTML/CSS/JavaScript workflow for office staff who manually dispatch delivery Orders to Drivers, Trips, and Vehicles.

The board is intentionally manual:

- Top: global Task Pool for active unassigned Orders.
- Bottom: Driver Summary / Trip Summary / Final Trip Summary.
- Dispatch Date is the operational assignment date.
- Delivery Date is customer/order metadata and the Driver Summary view scope.

This project is not a route optimizer. It does not perform auto-assignment, ETA prediction, geocoding, Google Maps routing, automatic trip planning, or automatic driver/vehicle selection.

## Current Status

Current status: **Phase 19: Release Candidate QA** on `feature/manual-dispatch-board`.

Implemented capabilities now include:

- Database-backed login with operator attribution for Final Trip Summary save/export.
- Global Task Pool with search, urgency, and Delivery Date display filtering.
- Driver Summary filtered by selected Delivery Date without changing Task Pool membership.
- Vehicle selection scoped by `driver_id + dispatch_date + delivery_date`.
- Product Details with pallet/bag exclusivity.
- Historical Final Trip Summary save, history, and Excel export from snapshot data.
- Final Trip Summary suburb-distance sorting using a static local estimate table.
- Distance dataset provenance, QA validation, and explicit non-optimization wording.
- Phase 19 release-candidate QA validating the full manual dispatch workflow before office trial use.

Phase 19 does not add automatic assignment or optimization. It focuses on regression checks, browser smoke testing, documentation, and small targeted fixes if QA finds a real bug.

Runtime SQLite database files are local development data and remain ignored by Git.

## Core Workflow

1. Log in.
2. Select the Dispatch Date.
3. Review the global Task Pool.
4. Filter or search Orders if needed.
5. Assign Orders to Driver + Trip.
6. Select the Driver Summary Delivery Date.
7. Choose a Vehicle for Driver + Dispatch Date + Delivery Date.
8. Generate the Final Trip Summary.
9. Save and Export the historical snapshot.

## Key Concepts

| Concept | Meaning |
| --- | --- |
| Dispatch Date | Operational board date used for assignments and dispatch-day workflow. |
| Delivery Date | Customer/order delivery date. It is editable for active Orders and also scopes Driver Summary visibility. |
| Task Pool | Global active unassigned Order pool. It is not controlled by Dispatch Date or Driver Summary Delivery Date membership rules. |
| Driver Summary Delivery Date | The date filter that decides which already-assigned Orders appear inside driver cards. |
| Vehicle Assignment Scope | Vehicle selection is stored per `driver_id + dispatch_date + delivery_date`. |
| Final Trip Summary | A generated and then saved historical snapshot scoped by `dispatch_date + delivery_date`. |
| Product Details | Structured product lines attached to an Order and copied into saved Final Trip Summary snapshots. |
| Estimated Distance | Static suburb-level estimated straight-line distance from the Somerton warehouse, used only for Final Trip Summary sorting. |

## Features

### Authentication / Operator Attribution

- Login/register flow backed by SQLite operator accounts.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes, never in plain text.
- Save and Export requires a logged-in operator.
- Saved Final Trip Summaries record the operator account name.
- Forgot Password resets a password using `MANUAL_DISPATCH_ADMIN_RESET_CODE`; it never reveals the old password.
- This is lightweight MVP/demo authentication, not production-grade enterprise auth.

### Task Pool

- Shows active unassigned Orders globally.
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

### Driver & Vehicle Specification

- Driver and Vehicle specification modal supports add, edit, safe delete, and availability toggles.
- Unavailable Drivers and Vehicles are hidden from operational dropdowns where appropriate.
- Main board refresh stays deferred until the modal closes.

### Manual Assignment

- Assign Orders to a Driver and `trip1` or `trip2`.
- Reassign by assigning the same Order to another Driver/Trip.
- Unassign Orders back to the Task Pool.
- The workflow remains manual; no optimizer or auto-selection logic is introduced.

### Driver Summary / Trip Summary

- Driver cards remain stable while the Driver Summary Delivery Date changes.
- Each driver card shows only assigned Orders matching the selected Driver Summary Delivery Date.
- If no matching Orders exist, the card stays visible with an empty state.
- Vehicle selection reflects the current `driver_id + dispatch_date + delivery_date` combination.

### Final Trip Summary

- Generated summaries are scoped by selected Dispatch Date + selected Driver Summary Delivery Date.
- Saved summaries are historical snapshots, not live views of mutable Order/Driver/Vehicle data.
- Saved snapshots do not auto-update after later edits.
- Duplicate saves are rejected for the same Driver + Dispatch Date + Delivery Date.
- Generated-but-unsaved previews remain frontend-memory only and may be lost on refresh.
- Static frontend assets are served with `Cache-Control: no-store` for local/demo reliability.

### Excel Export

- Save and Export writes historical Final Trip Summary data and downloads XLSX output.
- Export uses saved snapshot records, not active assignment rows.
- Export includes Dispatch Date, Delivery Date, Saved By, Product Details, and estimated suburb distance.
- Generated At / Saved At are intentionally excluded from the workbook layout.

### Suburb Distance Sorting

- Final Trip Summary Orders sort by known estimated distance ascending.
- Same-suburb Orders sort by Start Time earliest to latest.
- Unknown-distance suburbs appear after known-distance suburbs.
- Unknown values display as `Unknown` rather than breaking summary generation.

## Distance Estimation

- Warehouse origin: `98-102 Hume Hwy, Somerton, VIC, 3062`.
- Runtime distance data lives in `backend/data/suburb_distances_from_somerton.json`.
- The current table contains **112** static suburb/locality records.
- Centroid inputs are documented as **manually curated for demo sorting only** in `tools/data/suburb_centroids_from_somerton_curated.json`.
- Distances are calculated as static suburb-level estimated straight-line distance using Haversine math.
- The current centroid set is not claimed to be official/open dataset-derived.
- These values are not driving distance, not ETA, and not route optimization output.
- Unknown or unmapped suburbs fall back to `Unknown` and sort after known distances.
- QA validation is available through `tools/qa_suburb_distances_from_somerton.py`.

## Project Structure

- `backend/`: FastAPI app, manual-dispatch APIs, schemas, services, repositories, database bootstrap, and Excel export logic.
- `frontend/`: Static HTML/CSS/JavaScript app, modular renderers/actions/state/selectors, and the `frontend/app.js` entry point.
- `docs/`: Focused feature and phase documentation.
- `tests/`: Service, repository, API, static frontend, export, auth, product, and distance QA coverage.
- `tools/`: Local utility scripts, demo data reset tooling, and distance dataset QA/generation helpers.
- `requirements.txt`: Runtime Python dependencies.
- `requirements-dev.txt`: Route-test and browser-smoke development dependencies.

See [Manual Dispatch Board code structure](docs/manual-dispatch-board-code-structure.md) for a deeper implementation map.

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

Run the app:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/frontend/
```

Local environment notes:

- Do not commit `.env`.
- `.env.example` may contain placeholders only.
- Runtime SQLite files are generated locally and ignored by Git.
- The local database path is `data/manual_dispatch.sqlite3`.

## Validation / Tests

Repository validation currently uses:

```powershell
git diff --check
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe tools\qa_suburb_distances_from_somerton.py
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

`frontend/overrides.js` does not currently exist. If it is added later, validate it with:

```powershell
node --check frontend/overrides.js
```

## Demo Data / Local Data

- Demo Orders may still use dated sample records such as `2026-05-05`.
- Dispatch Date defaults to the browser's local current date.
- Because Task Pool is global, future Delivery Date Orders can still appear before their Delivery Date when they are active and unassigned.
- Driver Summary and Final Trip Summary remain controlled by the selected Driver Summary Delivery Date.
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

- auto-assignment
- CP-SAT
- route optimization
- ETA calculation
- live geocoding
- Google Maps logic
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- production-grade authentication
