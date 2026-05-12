# Manual Dispatch Board Phase 12: UI Stability and Deferred Specification Refresh

## Summary
Phase 12 improves the Driver & Vehicle Specification modal stability. Driver and Vehicle master-data changes now refresh the modal list only while the modal remains open. The main Manual Dispatch Board reloads once when the modal closes if a specification change occurred.

## Scope
- Added a frontend `specificationDirty` flag.
- Deferred main board refresh until the specification modal closes.
- Kept Driver and Vehicle add, edit, delete, and availability changes inside the modal flow.
- Preserved existing backend API behavior and database schema.

## Deferred Board Refresh Behavior
When the Driver & Vehicle Specification modal opens, `specificationDirty` resets to `false`. After a successful Driver or Vehicle change, the flag becomes `true` and only the specifications list is reloaded.

When the modal closes, the frontend checks `specificationDirty`. If it is `true`, the modal closes first and then the board reloads once for the current dispatch date. If it is `false`, the board does not reload.

## Modal-Only Refresh
These actions now reload specifications only while the modal stays open:
- Add Driver
- Edit Driver
- Delete Driver
- Toggle Driver availability
- Add Vehicle
- Edit Vehicle
- Delete Vehicle
- Toggle Vehicle availability

The page behind the modal may show the previous board state until the modal closes. This is intentional to avoid flicker during repeated modal edits.

## Board Reload On Close
Closing the modal applies the latest availability visibility to the main board:
- Unavailable Drivers are hidden from the Driver dropdown and empty Trip Summary cards.
- Unavailable Vehicles are hidden from the Choose Vehicle dropdown.
- Assign, Unassign, vehicle clearing, final summaries, Excel export, and Order CRUD behavior are unchanged.

## Validation Results
- `python -m compileall backend`: passed using the bundled Python runtime.
- `python -m unittest discover -s tests -v`: passed using the bundled Python runtime. The suite ran 88 tests with 7 existing FastAPI TestClient skips.
- `node --check frontend/app.js`: passed.
- Static safety checks found no `localStorage`, `sessionStorage`, geolocation, Google Maps, CP-SAT, geocoding, route, or optimization calls.
- `git status --short` and `git diff --stat`: run before commit to confirm the Phase 12 file set.

## Excluded Work
Phase 12 does not add or change:
- backend API behavior
- database schema
- automatic assignment
- automatic driver or vehicle selection
- route optimization
- ETA calculation
- geocoding or maps
- CP-SAT or optimization logic
- blocking rules
- authentication
- MySQL or MariaDB

## Notes
This is a frontend stability polish phase. It preserves existing user changes to the Specification modal layout and scroll behavior.
