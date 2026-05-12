# Manual Dispatch Board Phase 3

## Scope
Phase 3 implements frontend-only in-memory manual assignment behavior. It does not add backend APIs, database connections, persistence, migrations, automatic assignment, route optimization, ETA calculation, geocoding, Google Maps logic, CP-SAT, or dispatch algorithms.

## Files Changed
- `frontend/app.js`
- `frontend/index.html`
- `frontend/styles.css`
- `README.md`
- `docs/manual-dispatch-board-phase3.md`

## Frontend-Only State
The board uses a simple in-memory state object in `frontend/app.js`:
- `orders`
- `drivers`
- `vehicles`
- `assignments`

Assignments use `task_type + task_id` instead of hard-coding only `order_id`, so future task types can be added later.

Example assignment shape:

```js
{
  assignment_id: "A-001",
  task_type: "ORDER",
  task_id: "ORD-001",
  driver_id: "DRV-001",
  trip_no: "trip1"
}
```

## Assign Behavior
- Task Pool renders only unassigned Orders.
- Each Order card shows only Suburb and Pallet quantity as Order data.
- Loose Bags-only Orders display `Pallet: 0`.
- Each Order card has Driver selector, Trip selector, and Assign button.
- Driver selector starts with `Select driver`.
- Assign is disabled until a driver is selected.
- Trip defaults to `trip1`.
- Clicking Assign adds an in-memory assignment, removes the Order from Task Pool, and renders it under the selected Driver and Trip.

## Unassign Behavior
- Assigned Orders render inside Driver Summary trip groups.
- Each assigned Order has an Unassign button.
- Clicking Unassign removes the in-memory assignment and returns the Order to Task Pool.
- When returned to Task Pool, the Order card uses the default `trip1` selection again.

## Vehicle Dropdown
- Each Driver card keeps a Choose Vehicle dropdown.
- Vehicle options show rego values.
- Vehicle selection is frontend-only visual behavior in Phase 3.
- No automatic vehicle selection is implemented.

## Intentionally Excluded
- backend API
- database runtime connection
- persistence
- migrations
- automatic assignment
- CP-SAT
- route optimization
- ETA calculation
- geocoding
- Google Maps logic
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- capacity-based blocking
- zone-based blocking
- real dispatch algorithm

## Validation Results
- `node --check frontend/app.js`: passed.
- `Get-Content .\frontend\index.html`: passed.
- `Get-Content .\frontend\styles.css`: passed.
- `Get-Content .\frontend\app.js`: passed.
- `Get-Content .\docs\manual-dispatch-board-phase3.md`: passed.
- `Get-Content .\README.md`: passed.
- `git status --short`: showed only expected Phase 3 files before commit.
- `git diff --stat`: reviewed Phase 3 file changes.

Manual browser validation passed with local `file://` loading:
- Task Pool showed demo Orders.
- Driver Summary showed demo Drivers.
- `trip1` was the default trip.
- Assign enabled only after selecting a Driver.
- Assign moved Dandenong to John -> Trip 2.
- Unassign returned Dandenong to Task Pool.
- Refresh cleared in-memory assignments.
- No backend or persistence request was made.
