# Manual Dispatch Board Phase 5

## Summary
Phase 5 adds a backend API skeleton for the Manual Dispatch Board. The backend mirrors the manual workflow only:
- Task -> selected Driver -> selected Trip
- Driver + Dispatch Date -> selected Vehicle

## Backend API Skeleton Scope
The backend uses a FastAPI-style structure with a thin API layer, service layer, in-memory repository, dataclass schemas, and minimal unit tests.

This phase does not connect the frontend to the backend.

## Endpoints Added
- `GET /api/manual-dispatch/board?dispatch_date=YYYY-MM-DD`
- `POST /api/manual-dispatch/assign`
- `POST /api/manual-dispatch/unassign`
- `POST /api/manual-dispatch/driver-vehicle`

## In-Memory Repository Rule
`backend/repositories/in_memory_manual_dispatch_repository.py` holds demo Orders, Drivers, Vehicles, task assignments, and driver vehicle assignments in memory only.

Data resets when the backend process restarts. Database persistence belongs to Phase 6.

## Service Behavior
- `get_board(dispatch_date)` returns board state.
- `assign_task(request)` validates task type, task existence, driver existence, and trip number before creating/updating an in-memory assignment.
- `unassign_task(request)` removes an assignment by `dispatch_date + task_type + task_id` and leaves Orders and vehicle selections unchanged.
- `assign_vehicle_to_driver(request)` validates Driver and Vehicle, then upserts Driver + Dispatch Date vehicle selection.
- Duplicate vehicle usage across Drivers is allowed.
- Vehicle IDs are not stored on individual Order assignment records.

## Validation Commands
- `python -m compileall backend`
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- `Get-Content .\backend\main.py`
- `Get-Content .\backend\api\manual_dispatch.py`
- `Get-Content .\backend\services\manual_dispatch_service.py`
- `Get-Content .\backend\repositories\in_memory_manual_dispatch_repository.py`
- `Get-Content .\backend\schemas.py`
- `Get-Content .\tests\test_manual_dispatch_service.py`
- `Get-Content .\docs\manual-dispatch-board-phase5.md`
- `Get-Content .\README.md`
- `git status --short`
- `git diff --stat`

## Tests Run
Phase 5 adds `tests/test_manual_dispatch_service.py` using Python `unittest`.

The tests cover:
- board demo data
- manual assignment with `task_type + task_id`
- unassign
- Driver + Dispatch Date vehicle assignment
- vehicle assignment remaining separate from task assignments
- invalid trip rejection
- invalid driver rejection

Actual validation results:
- `python -m compileall backend`: local `python` command was unavailable.
- Bundled Python compileall: passed.
- `python -m unittest discover -s tests -v`: local `python` command was unavailable.
- Bundled Python unittest discovery: passed, 7 tests.
- `node --check frontend/app.js`: passed.
- `python -c "from backend.main import app; print(app.title)"`: optional check failed because FastAPI is not installed locally.

## Explicitly Excluded Work
- database connection
- migrations
- persistence
- frontend-backend integration
- algorithm
- route optimization
- ETA
- maps
- geocoding
- automatic selection
- blocking rules

## Phase 6 Handoff Notes
Phase 6 can replace the in-memory repository with database persistence while preserving service behavior and public endpoint shapes. Any database work should keep manual control rules intact and avoid optimization or automatic assignment unless explicitly approved.
