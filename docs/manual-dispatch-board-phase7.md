# Manual Dispatch Board Phase 7

## Summary
Phase 7 adds frontend-only business hints to help office staff make manual dispatch decisions.
The Manual Dispatch Board remains a manual office workflow.

This phase does not connect the frontend to the backend.
The frontend continues to use in-memory demo data.

## Business Hints Added
- Order urgency badge: `Urgent` or `Normal`.
- Order zone badge.
- Order delivery time window.
- Order note when present.
- Preferred driver hint when an Order has `preferred_driver_id`.
- Preferred driver mismatch hint after a different Driver is selected.
- Zone mismatch hint when selected Driver preferred zone differs from Order zone.
- Outside driver hours hint when Order window is outside Driver hours.
- Driver availability hint.
- Driver preferred zone hint.
- Selected vehicle capacity summary.
- Non-blocking capacity warning when assigned pallets exceed selected vehicle pallet capacity.

## Non-Blocking Rule
All hints are display-only.
They must not prevent Assign, Unassign, Driver selection, Trip selection, or Vehicle selection.

Phase 7 does not add:
- automatic driver selection.
- automatic vehicle selection.
- automatic trip planning.
- capacity-based blocking.
- zone-based blocking.
- preferred-driver blocking.
- urgency-based blocking.

## UI Behavior
- Task Pool still shows unassigned Orders.
- Order cards still prominently show Suburb and Pallet quantity.
- Assign flow is unchanged: select Driver, select `trip1` or `trip2`, click Assign.
- Unassign flow is unchanged: click Unassign to return the Order to Task Pool.
- Vehicle selection remains in memory and stays visible after Assign/Unassign re-render.
- Refresh clears frontend in-memory assignments and vehicle selections.
- Trip 2 remains below Trip 1 inside each Driver card.

## Driver And Trip Load Summaries
Each Driver card shows:
- total pallets assigned.
- total loose bags assigned.

Each Trip section shows:
- pallets in the trip.
- loose bags in the trip.

Totals update after Assign and Unassign.

## Vehicle Capacity Hint Behavior
After a vehicle is selected, the Driver card shows its pallet capacity.
If assigned pallets exceed the selected vehicle capacity, the UI shows:
`Capacity warning: assigned pallets exceed selected vehicle pallet capacity.`

This warning is non-blocking.
The user can still assign Orders manually.

## Validation Commands
- `python -m compileall backend`
- bundled Python `-m compileall backend` if normal `python` is unavailable.
- `python -m unittest discover -s tests -v`
- bundled Python `-m unittest discover -s tests -v` if normal `python` is unavailable.
- `node --check frontend/app.js`
- `Get-Content .\frontend\index.html`
- `Get-Content .\frontend\styles.css`
- `Get-Content .\frontend\app.js`
- `Get-Content .\docs\manual-dispatch-board-phase7.md`
- `Get-Content .\README.md`
- `git status --short`
- `git diff --stat`

## Tests Run
Test results are recorded in the Phase 7 completion report after validation commands are run.

## Explicitly Excluded Work
- frontend-backend integration.
- localStorage.
- new database migrations.
- MySQL/MariaDB.
- automatic assignment.
- automatic driver selection.
- automatic vehicle selection.
- automatic trip planning.
- route optimization.
- ETA calculation.
- maps.
- geocoding.
- CP-SAT.
- capacity blocking.
- zone blocking.
- dispatch optimization algorithm.

## Phase 8 Handoff Notes
Phase 8 may add review/export behavior.
Any review/export feature should preserve the manual workflow and must not introduce optimization or automatic assignment unless explicitly approved.
