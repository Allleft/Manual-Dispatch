# Manual Dispatch Board Phase 10G: Persist Final Trip Summary and Load History

## Summary
- Phase 10G makes Final Trip Summary a closed manual workflow.
- Generated summaries remain locked snapshots, but they can now be saved to SQLite.
- Saved summaries are loaded through History and do not change when live Orders, Drivers, or Vehicles are edited later.

## Workflow
1. Office staff manually assigns Orders to Driver + Trip + Vehicle.
2. User clicks `Generate` on a Driver card.
3. Frontend captures a locked snapshot before clearing editable assignments.
4. User clicks `Save Final Summary`.
5. Backend stores the snapshot in SQLite.
6. Included Orders are marked `FINALIZED`.
7. Finalized Orders are excluded from Task Pool and editable Trip Summary.
8. User clicks `Load History` to view saved read-only summaries by dispatch date.

## SQLite Tables
- `final_trip_summaries`
- `final_trip_summary_rows`

## Snapshot Fields
- Summary rows store snapshot values such as invoice number, company name, suburb, delivery address, product, pallet quantity, loose bags quantity, and note.
- Driver name and vehicle rego are also stored as snapshots.
- Saved summaries do not render from live Order, Driver, or Vehicle rows.

## Order Status
- `manual_orders.status` now supports:
  - `ACTIVE`
  - `CANCELLED`
  - `FINALIZED`
- `FINALIZED` Orders are not assignable through the manual assignment service.
- `FINALIZED` Orders do not appear in the board Task Pool.

## API Endpoints
- `POST /api/manual-dispatch/final-summaries`
- `GET /api/manual-dispatch/final-summaries?dispatch_date=YYYY-MM-DD`
- `GET /api/manual-dispatch/final-summaries/{summary_id}`

## Frontend Behavior
- Generated in-session summaries show `Save Final Summary`.
- Saved summaries show `Saved` and remain read-only.
- `Load History` retrieves saved summaries for the selected dispatch date.
- Clicking a saved history item displays its locked snapshot.
- No Assign, Unassign, dropdown, edit, or cancel controls are included in saved summaries.

## Persistence Rules
- Saving a Final Trip Summary marks included Orders as `FINALIZED`.
- Saving removes any active assignment rows for included Orders.
- Finalized Orders remain available only through saved history in this phase.
- Generated-but-unsaved summaries are still frontend memory only.

## Explicitly Excluded Work
- Automatic assignment
- Route optimization
- ETA calculation
- Maps or geocoding
- CP-SAT or OR-Tools
- Blocking rules
- Authentication
- MySQL or MariaDB
- Lock/unlock workflow
- Editing saved Final Trip Summaries

## Validation
- `python -m compileall backend`
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- Static checks for no `localStorage`, `sessionStorage`, geolocation, Google Maps, routing, ETA, or optimization logic.

## Phase 10G Handoff
- A later phase can add lock/unlock or archival review workflow if required.
- A later phase can add stronger history browsing/search controls.
- A later phase can decide whether finalized Orders should support controlled reopen behavior.
