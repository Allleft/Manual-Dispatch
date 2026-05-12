# Manual Dispatch Board Phase 9

## Summary
Phase 9 adds Excel export for the current Manual Dispatch Board assignments.
The export is backend-generated and uses the SQLite-backed board data for the selected Dispatch Date.

This phase does not add a separate Review Summary UI.
The Manual Dispatch Board remains a manual office workflow.

## Excel Export Scope
- Adds an Export Excel button near the Dispatch Date controls.
- Adds a backend Excel export endpoint.
- Generates an `.xlsx` workbook for the selected Dispatch Date.
- Exports assigned `ORDER` tasks only.
- Keeps Assign, Unassign, Choose Vehicle, and business hint behavior unchanged.

## Export Endpoint
- `GET /api/manual-dispatch/export-excel?dispatch_date=YYYY-MM-DD`

The endpoint returns a downloadable workbook with a filename such as:
- `manual-dispatch-2026-05-05.xlsx`

Existing endpoints are unchanged:
- `GET /api/manual-dispatch/board`
- `POST /api/manual-dispatch/assign`
- `POST /api/manual-dispatch/unassign`
- `POST /api/manual-dispatch/driver-vehicle`

## Export Button Behavior
- The frontend uses the currently selected Dispatch Date.
- The frontend requests the backend export endpoint.
- The browser downloads the generated `.xlsx` file.
- If export fails, the page shows a non-blocking error message.
- The frontend does not generate Excel files.
- No `localStorage` or `sessionStorage` is used.

## Export Columns
The workbook uses these columns in this order:
1. Dispatch Date
2. Driver Name
3. Vehicle Rego
4. Trip
5. Order ID
6. Company Name
7. Delivery Address
8. Suburb
9. Postcode
10. Zone
11. Urgency
12. Preferred Driver
13. Pallet Quantity
14. Loose Bags Quantity
15. Start Time
16. End Time
17. Note

There is no Location column.

## Empty Driver And Trip Exclusion Rules
- One row is exported per assigned Order.
- Unassigned Orders are not exported.
- Empty Drivers are not exported.
- Empty Trips are not exported.
- Blank trip header rows are not created.
- If no Orders are assigned, the workbook still downloads with the header row only.

## Persistence Behavior
The export reads the current backend board data for the selected Dispatch Date.
Assignments and Driver + Dispatch Date vehicle selections come from SQLite persistence.

Vehicle selection remains separate from task assignment:
- `dispatch_date + driver_id -> vehicle_id`
- `vehicle_id` is not stored on task assignment records.

## Tests Added
Phase 9 adds backend unit tests for Excel export generation.
The tests verify:
- expected headers.
- no Location column.
- assigned Orders are exported.
- unassigned Orders are not exported.
- Driver Name and Vehicle Rego are included.
- empty Drivers and empty Trips are not exported.
- no vehicle selected renders a clear vehicle value.
- sort order uses Driver Name, Trip, then Order ID.

## Validation Commands
- `python -m compileall backend`
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- `Get-Content .\frontend\index.html`
- `Get-Content .\frontend\styles.css`
- `Get-Content .\frontend\app.js`
- `Get-Content .\backend\api\manual_dispatch.py`
- `Get-Content .\backend\services\excel_export_service.py`
- `Get-Content .\docs\manual-dispatch-board-phase9.md`
- `Get-Content .\README.md`
- `Get-Content .\requirements.txt`
- `git status --short`
- `git diff --stat`

## Explicitly Excluded Work
- separate Review Summary UI.
- CSV import.
- Excel import.
- login or authentication.
- production deployment.
- MySQL/MariaDB.
- automatic assignment.
- automatic driver selection.
- automatic vehicle selection.
- automatic trip planning.
- route optimization.
- ETA calculation.
- geocoding.
- Google Maps logic.
- CP-SAT.
- capacity-based blocking.
- zone-based blocking.
- preferred-driver blocking.
- urgency-based blocking.
- dispatch optimization algorithm.

## Phase 10 Handoff Notes
Future phases may add review/export refinements, operational reporting, or future task-type extensions.
Those changes should continue using `task_type + task_id` and must preserve the manual workflow unless explicitly approved.
