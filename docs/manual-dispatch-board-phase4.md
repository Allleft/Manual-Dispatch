# Manual Dispatch Board Phase 4

## Scope
Phase 4 implements frontend-only, in-memory Vehicle selection for each Driver card. Vehicle assignment is tracked at Driver + Dispatch Date level and does not belong to individual Orders or Trips.

## Files Changed
- `frontend/app.js`
- `frontend/index.html`
- `frontend/styles.css`
- `README.md`
- `docs/manual-dispatch-board-phase4.md`

## Frontend-Only Vehicle Selection
The board state now includes `driverVehicleAssignments` and a fixed demo `dispatchDate`.

Example vehicle assignment shape:

```js
{
  dispatch_date: "2026-05-05",
  driver_id: "DRV-001",
  vehicle_id: "VEH-002"
}
```

Order assignment records remain separate and do not store `vehicle_id`.

## Driver + Dispatch Date Rule
- Vehicle selection belongs to Driver + Dispatch Date.
- Vehicle is not assigned to each individual Order.
- Vehicle is not assigned to each individual Trip.
- A Driver's Trip 1 and Trip 2 use the same selected vehicle by default.

Example:

```text
John + 2026-05-05 -> XYZ888
```

This means John's Trip 1 and Trip 2 both use XYZ888 for the current in-memory session.

## Re-Render Behavior
- Selecting a vehicle updates `state.driverVehicleAssignments`.
- The selected rego remains visible after assigning an Order.
- The selected rego remains visible after unassigning an Order.
- Vehicle selections clear after page refresh because Phase 4 does not persist state.
- Duplicate vehicle selections across drivers are allowed.
- If the same vehicle is manually selected for more than one Driver, a non-blocking hint may appear.

## Trip Layout
Driver card trip sections are stacked vertically:
- Trip 1 appears above Trip 2.
- Trip 2 appears below Trip 1.
- Each Trip section uses the full Driver card width.

## Intentionally Excluded
- backend API
- database runtime connection
- persistence
- localStorage
- migrations
- automatic vehicle selection
- automatic driver selection
- automatic trip planning
- capacity-based blocking
- zone-based blocking
- route optimization
- ETA calculation
- geocoding
- Google Maps logic
- CP-SAT
- dispatch algorithm

## Validation Results
- `node --check frontend/app.js`: passed.
- `Get-Content .\frontend\index.html`: passed.
- `Get-Content .\frontend\styles.css`: passed.
- `Get-Content .\frontend\app.js`: passed.
- `Get-Content .\docs\manual-dispatch-board-phase4.md`: passed.
- `Get-Content .\README.md`: passed.
- `git status --short`: showed only expected Phase 4 files before commit.
- `git diff --stat`: reviewed Phase 4 file changes.

Manual browser validation passed with local `file://` loading:
- Task Pool demo Orders rendered.
- Driver Summary demo Drivers rendered.
- Assign still moved Dandenong to John -> Trip 2.
- Unassign returned Dandenong to Task Pool.
- Trip 2 appeared below Trip 1 inside the Driver card.
- John vehicle selection updated to XYZ888.
- Selected vehicle stayed visible after Assign.
- Selected vehicle stayed visible after Unassign.
- Selected vehicle cleared after page refresh.
- No backend or persistence request was made.
- No automatic vehicle selection occurred.
