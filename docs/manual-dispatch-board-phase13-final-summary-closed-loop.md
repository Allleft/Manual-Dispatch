# Manual Dispatch Board Phase 13: Final Trip Summary Closed Loop Stabilization

## Summary
- Phase 13 stabilizes the existing Final Trip Summary closed-loop workflow.
- Office staff can generate a locked frontend preview, save it to SQLite, and later load saved history.
- Saved summaries are historical snapshots and do not render from live Order, Driver, or Vehicle records.

## Closed-Loop Workflow
1. Assign Orders manually to Driver + Trip + Vehicle.
2. Click `Generate` on a Driver card.
3. The frontend captures a locked snapshot of that Driver's current assigned Orders.
4. The frontend clears those editable assignments through the existing unassign API.
5. Click `Save Final Summary`.
6. The backend saves the snapshot to SQLite.
7. Included Orders are marked `FINALIZED`.
8. Active assignment rows for those Orders are removed.
9. `Load History` shows saved summaries for the selected dispatch date.

## Generate Behavior
- Generate is frontend-preview-only.
- It captures Driver name, selected vehicle rego, Order row details, totals, and Trip 1 / Trip 2 grouping before assignments are cleared.
- Empty trips are not shown.
- Generated Orders are hidden from the Task Pool for the current browser session using frontend memory.
- Unsaved generated previews may disappear after browser refresh.

## Save Behavior
- `POST /api/manual-dispatch/final-summaries` saves the snapshot.
- Save requires at least one Order row.
- Save uses snapshot row data, not live lookups for history rendering.
- SQLite save is transactional: if row persistence fails, summary rows, `FINALIZED` status updates, and assignment removals are rolled back together.

## FINALIZED Order Behavior
- `ACTIVE` Orders remain available for the Task Pool and editable Trip Summary.
- `CANCELLED` Orders stay hidden from active dispatch views.
- `FINALIZED` Orders are hidden from the Task Pool and editable Trip Summary.
- Finalized Orders are only visible through saved Final Trip Summary history.

## Load History Behavior
- `GET /api/manual-dispatch/final-summaries?dispatch_date=YYYY-MM-DD` returns saved summaries for that date.
- History cards are read-only.
- History does not include Assign, Unassign, Driver dropdown, Trip dropdown, vehicle dropdown, Edit, Delete, or Cancel controls.

## Snapshot Integrity
- Saved history displays `driver_name_snapshot`, `vehicle_rego_snapshot`, and row snapshot fields.
- Later edits to Orders, Drivers, or Vehicles do not change saved history.
- This preserves the Final Trip Summary as a historical record.

## Duplicate Save Rule
- A Driver can have only one saved Final Trip Summary per dispatch date.
- Duplicate save attempts are rejected with:
  `Final Summary for this driver and dispatch date has already been saved.`
- Saved summaries are not overwritten or duplicated.

## Validation Results
- Added repository/service coverage for duplicate save rejection.
- Added repository transaction rollback coverage for partial failure.
- Added coverage for Trip 1 + Trip 2 grouping and empty trip omission.
- Added optional FastAPI route tests for final summary save/history; they safely skip when TestClient is unavailable.

## Explicitly Excluded Work
- Print Final Summary
- PDF export
- Final Summary Excel export
- Void Final Summary
- Restore Finalized Orders
- Unlock or Regenerate saved summaries
- Login/auth
- Route optimization, ETA, maps, geocoding, CP-SAT, or automatic assignment

## Phase 14 Handoff
- A later phase can add controlled void/regenerate behavior if office review requires it.
- A later phase can add print/PDF/export workflows for saved final summaries.
- A later phase can add stronger history search and filtering.
