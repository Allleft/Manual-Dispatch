# Manual Dispatch Board Phase 6

## Summary
Phase 6 adds SQLite persistence support to the Manual Dispatch Board backend.
The backend can now store demo/master data, manual task assignments, and Driver + Dispatch Date vehicle selections in a local SQLite database.

This remains a backend persistence phase only. The frontend is not connected to the backend yet.

## SQLite Persistence Scope
- Runtime database path defaults to `data/manual_dispatch.sqlite3`.
- `MANUAL_DISPATCH_DB_PATH` can override the runtime database path.
- Runtime database files are local artifacts and must not be committed.
- SQLite uses Python standard library `sqlite3`.
- No SQLAlchemy, MySQL/MariaDB connector, routing, map, geocoding, OR-Tools, or optimization dependency is added.

## Tables Added
- `manual_orders`
- `manual_drivers`
- `manual_vehicles`
- `manual_dispatch_assignments`
- `manual_driver_vehicle_assignments`

Manual task assignments continue to use `task_type + task_id`.
For the MVP, `task_type` is normally `ORDER`.

Vehicle assignment remains separate from task assignment:
- Vehicle is assigned at Driver + Dispatch Date level.
- Vehicle is not assigned to each Order.
- Vehicle is not assigned to each Trip.
- A driver's `trip1` and `trip2` share the same selected vehicle by default.

## Runtime DB File Rule
Runtime database files are ignored by Git:
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `data/*.sqlite`
- `data/*.sqlite3`
- `data/*.db`

The backend creates the parent data folder automatically when the runtime database path is used.

## Seed Data Behavior
Demo seed data matches earlier frontend/backend phases:
- Orders: `ORD-001` Dandenong, `ORD-002` Clayton, `ORD-003` Springvale.
- Drivers: `D001` John, `D002` Tony, `D003` David.
- Vehicles: `V001` ABC123, `V002` XYZ888, `V003` MCC001.

Seed data uses `INSERT OR IGNORE`.
Startup does not wipe assignments, reset vehicle selections, or delete existing rows.

## Repository Behavior
`SQLiteManualDispatchRepository` implements the same repository behavior expected by `ManualDispatchService`:
- list demo/master data.
- list assignments by dispatch date.
- list driver vehicle assignments by dispatch date.
- validate task, driver, and vehicle existence through service calls.
- upsert manual task assignment by `dispatch_date + task_type + task_id`.
- remove manual task assignment idempotently.
- upsert Driver + Dispatch Date vehicle assignment.

The repository preserves manual control:
- no automatic assignment.
- no automatic vehicle selection.
- no capacity blocking.
- no zone blocking.
- no preferred driver, urgency, time window, duplicate vehicle, or missing vehicle blocking.

## Tests Added
`tests/test_sqlite_manual_dispatch_repository.py` covers:
- schema initialization.
- seed data loading.
- persisted task assignment.
- assignment read after creating a new repository with the same DB path.
- persisted unassign.
- persisted Driver + Dispatch Date vehicle selection.
- vehicle assignment staying separate from task assignment records.
- duplicate vehicle selection across drivers.
- invalid `trip_no` rejection through service.
- invalid `vehicle_id` rejection through service.

Existing Phase 5 service tests remain in place and must continue to pass.

## Validation Results
- `python -m compileall backend`: not run successfully because normal `python` is not available in PATH in this environment.
- Bundled Python `-m compileall backend`: passed.
- `python -m unittest discover -s tests -v`: not run successfully because normal `python` is not available in PATH in this environment.
- Bundled Python `-m unittest discover -s tests -v`: passed, 16 tests.
- `node --check frontend/app.js`: passed.

## Explicitly Excluded Work
- frontend-backend integration.
- MySQL/MariaDB production DB.
- automatic assignment.
- route optimization.
- ETA calculation.
- maps.
- geocoding.
- capacity blocking.
- zone blocking.
- driver auto-selection.
- vehicle auto-selection.
- frontend localStorage.

## Phase 7 Handoff Notes
Phase 7 may add business hints, but hints must remain non-blocking unless explicitly approved.
The Manual Dispatch Board remains a manual office workflow, not an optimization engine.
