# Manual Dispatch Board

Manual Dispatch Board is a manual office workflow for assigning Orders to Driver + Trip + Vehicle. This repository is currently in Phase 9: Excel Export.

## Current Phase
- Phase: 9
- Status: backend Excel export for assigned Orders
- Frontend now loads board data from the backend API.
- Assign, Unassign, and Choose Vehicle actions now call the backend API.
- SQLite persistence means refresh can preserve assignments and Driver + Dispatch Date vehicle selections.
- Business hints remain non-blocking.
- Export Excel button is available near the Dispatch Date controls.
- Excel export uses backend SQLite assignment data.
- Excel export includes only assigned Orders.
- Empty Drivers and empty Trips are not exported.
- Location column is not included in the export.
- No separate Review Summary UI was added.
- Backend now has SQLite persistence support for demo/master data, manual task assignments, and Driver + Dispatch Date vehicle assignments.
- Runtime SQLite database files are local and ignored by Git.
- No automatic assignment, blocking rules, localStorage, or optimization logic is implemented in this phase.

## Layout Decision
The future Manual Dispatch Board layout must be top-bottom:
- Top: Task Pool
- Bottom: Driver Summary

Do not use a left-right layout unless explicitly requested.

## Future MVP Behavior
- Task Pool shows unassigned Orders.
- Each Order card shows only Suburb and Pallet quantity.
- If an Order only has Loose Bags, Pallet quantity displays as 0.
- Each Order card allows selecting Driver and `trip1` or `trip2`.
- Default trip is `trip1`.
- Assign moves the Order into the selected Driver card.
- Driver Summary shows one card per Driver.
- Each Driver card groups Orders by `trip1` and `trip2`.
- Each Driver card has a Choose Vehicle dropdown.
- Vehicle dropdown options show vehicle rego.
- Vehicle assignment is at Driver + Dispatch Date level.
- Future task types like Pickup should be supported through `task_type` and `task_id`.

## Explicit Non-Goals
This project must not become an optimization engine in the MVP. Do not add:
- auto-assignment
- CP-SAT
- route optimization
- ETA calculation
- geocoding
- Google Maps logic
- automatic driver selection
- automatic vehicle selection
- automatic trip planning

## Documentation
Phase 0 details are documented in `docs/manual-dispatch-board-phase0.md`.
Phase 1 data model details are documented in `docs/manual-dispatch-board-data-model.md`.
Phase 1 schema design notes are documented in `docs/manual-dispatch-board-schema.md`.
Phase 2 frontend skeleton details are documented in `docs/manual-dispatch-board-phase2.md`.
Phase 3 frontend-only assignment behavior is documented in `docs/manual-dispatch-board-phase3.md`.
Phase 4 frontend-only vehicle selection behavior is documented in `docs/manual-dispatch-board-phase4.md`.
Phase 5 backend API skeleton details are documented in `docs/manual-dispatch-board-phase5.md`.
Phase 6 SQLite persistence details are documented in `docs/manual-dispatch-board-phase6.md`.
Phase 7 frontend business hints are documented in `docs/manual-dispatch-board-phase7.md`.
Phase 8 frontend-backend integration is documented in `docs/manual-dispatch-board-phase8.md`.
Phase 9 Excel export is documented in `docs/manual-dispatch-board-phase9.md`.

## Validation
Phase 0 uses document and Git validation only. Functional tests should not be run until test, frontend, or backend implementation files exist.
Phase 1 also uses document and Git validation only because implementation files do not exist yet.
Phase 2 uses frontend syntax validation and static file review only. Real assignment behavior belongs to Phase 3.
Phase 3 uses frontend syntax validation plus manual browser checks. Assignment state is in memory only and is not persisted after refresh.
Phase 4 uses frontend syntax validation plus manual browser checks. Vehicle selection state is in memory only and is not persisted after refresh.
Phase 5 uses Python compile checks, backend service unit tests, frontend syntax validation, and static file review.
Phase 6 uses Python compile checks, backend repository/service unit tests, frontend syntax validation, and static file review. SQLite runtime database files must not be committed.
Phase 7 uses frontend syntax validation, backend regression tests, static file review, and manual browser checks for non-blocking hints.
Phase 8 uses frontend syntax validation, backend regression tests, static safety checks, and browser/manual checks when tooling is available.
Phase 9 uses backend Excel export unit tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
