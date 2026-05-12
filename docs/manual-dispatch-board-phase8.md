# Manual Dispatch Board Phase 8

## Summary
Phase 8 connects the frontend Manual Dispatch Board to the backend API and SQLite persistence.
The backend API is now the frontend source of truth for board data, manual task assignments, and Driver + Dispatch Date vehicle selections.

The Manual Dispatch Board remains a manual office workflow.

## Frontend-Backend Integration Scope
- Page load calls the backend board endpoint.
- Dispatch Date changes reload the board from the backend.
- Assign, Unassign, and Choose Vehicle actions call backend API endpoints first.
- Successful mutations re-fetch the board so the UI reflects SQLite state.
- The frontend no longer uses static Orders, Drivers, or Vehicles as the source of truth.
- No `localStorage` or `sessionStorage` is used.
- If the backend is unavailable, the UI shows a clear error and Retry button.

## API Calls Used By Frontend
- `GET /api/manual-dispatch/board?dispatch_date=YYYY-MM-DD`
- `POST /api/manual-dispatch/assign`
- `POST /api/manual-dispatch/unassign`
- `POST /api/manual-dispatch/driver-vehicle`

Frontend request payloads continue to use `task_type + task_id`.
For the MVP, `task_type` is `ORDER`.

Vehicle selection remains separate from task assignment:
- `dispatch_date + driver_id -> vehicle_id`
- `vehicle_id` is not stored on task assignments.

## SQLite Persistence Behavior
Assignments and Driver + Dispatch Date vehicle selections are persisted through the backend SQLite repository.
Refreshing the page can preserve assignments and selected vehicles because the frontend reloads backend board data.

Runtime SQLite database files remain local and ignored by Git.

## Refresh Persistence Behavior
Expected behavior:
- Assign an Order, refresh, and the Order remains under the selected Driver and Trip.
- Unassign an Order, refresh, and the Order remains in the Task Pool.
- Choose a Vehicle, refresh, and the selected vehicle remains visible for that Driver and Dispatch Date.

## Error And Loading Behavior
- Loading state appears while board data is requested.
- Saving state appears while Assign, Unassign, or Choose Vehicle calls are in flight.
- API failures show a non-blocking error message.
- The page does not silently fall back to static demo data.
- Retry reloads the current Dispatch Date from the backend.

## Static Serving And CORS Notes
`backend/main.py` now:
- mounts `frontend/` under `/frontend`.
- redirects `/` to `/frontend/`.
- enables simple development-friendly CORS for local `file://` and browser testing.

API route paths under `/api/manual-dispatch/*` are unchanged.

## Validation Commands
- `python -m compileall backend`
- bundled Python `-m compileall backend` if normal `python` is unavailable.
- `python -m unittest discover -s tests -v`
- bundled Python `-m unittest discover -s tests -v` if normal `python` is unavailable.
- `node --check frontend/app.js`
- `Get-Content .\frontend\index.html`
- `Get-Content .\frontend\styles.css`
- `Get-Content .\frontend\app.js`
- `Get-Content .\docs\manual-dispatch-board-phase8.md`
- `Get-Content .\README.md`
- `git status --short`
- `git diff --stat`

## Tests Run
- `python -m compileall backend`: not run successfully because normal `python` is not available in PATH in this environment.
- Bundled Python `-m compileall backend`: passed.
- `python -m unittest discover -s tests -v`: not run successfully because normal `python` is not available in PATH in this environment.
- Bundled Python `-m unittest discover -s tests -v`: passed, 16 tests.
- `node --check frontend/app.js`: passed.
- Optional FastAPI app import was not successful because `fastapi` is not installed in the local validation environment.
- Browser validation was not run because backend runtime dependencies and browser automation tooling are unavailable locally.

## Explicitly Excluded Work
- review/export features.
- CSV/Excel import.
- authentication or login.
- production deployment.
- localStorage.
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
- preferred-driver blocking.
- urgency-based blocking.
- dispatch optimization algorithm.

## Phase 9 Handoff Notes
Phase 9 may extend future task types such as Pickup, Return, or Special Task.
Any task extension should continue using `task_type + task_id` and preserve the manual workflow.
