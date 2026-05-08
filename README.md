# Manual Dispatch Board

Manual Dispatch Board is a manual office workflow for assigning Orders to Driver + Trip + Vehicle. This repository now includes Driver & Vehicle Specification master-data management.

## Current Phase
- Phase: 14
- Status: Final Trip Summary Redesign and Demo Order Reset
- Frontend now loads board data from the backend API.
- Assign, Unassign, and Choose Vehicle actions now call the backend API.
- SQLite persistence means refresh can preserve assignments and Driver + Dispatch Date vehicle selections.
- Add Order popup card is available.
- New Orders are saved to SQLite.
- New Orders appear in Task Pool after the board reloads.
- Newly added Orders are not exported until assigned.
- Order detail popup now supports Edit mode.
- Order edits are saved to SQLite.
- Delivery Date is read-only during edit to avoid cross-date assignment complexity.
- Editing an assigned Order keeps the existing Driver + Trip assignment unchanged.
- Order detail popup now supports Cancel Order.
- Cancel Order is a soft delete using `status = CANCELLED`.
- Cancelled Orders are hidden from the Task Pool and excluded from Excel export.
- Assigned Orders must be unassigned before cancellation.
- Task Pool now has frontend-only Order search.
- Task Pool now has frontend-only Urgency filtering.
- Search/filter affects only unassigned Orders and does not hide assigned Orders in Trip Summary.
- Driver cards can generate a locked Final Trip Summary snapshot from current assigned Orders.
- Generate captures the Driver, selected vehicle rego, trip grouping, totals, and Order table rows before unassigning.
- Generated Orders are unassigned through the existing backend API and removed from editable Trip Summary.
- Generated Orders are hidden from Task Pool in the same browser session using frontend memory.
- Final Trip Summary snapshots are read-only and do not auto-update from later board changes.
- Final Trip Summary snapshots can now be saved to SQLite.
- Final Trip Summary now uses one global Save Final Summary button for all generated unsaved summaries.
- Per-driver Final Trip Summary cards are read-only display cards and no longer include individual Save buttons.
- Load History now lives inside the Final Trip Summary section.
- Final Summary History can be loaded by a selected saved history date.
- Saved Final Trip Summary rows store snapshot data rather than live Order, Driver, or Vehicle references.
- Saved Final Trip Summary history can be loaded by dispatch date.
- Saving a Final Trip Summary marks included Orders as `FINALIZED`.
- `FINALIZED` Orders are hidden from Task Pool and editable Trip Summary.
- Saved Final Trip Summaries are historical snapshots and do not update when live Orders, Drivers, or Vehicles change later.
- Duplicate saved Final Trip Summaries for the same Driver and Dispatch Date are rejected.
- Final Trip Summary save is transactional so failed saves do not partially finalize Orders.
- Generated-but-unsaved summaries are still frontend memory only.
- Local demo Orders were reset to 20 Victoria Orders dated `2026-05-05`.
- The Phase 14 reset script is manual/dev-only and preserves Driver and Vehicle master data.
- Driver & Vehicle Specification modal is available from the top board controls.
- Drivers can be added, edited, safely deleted, and marked available/unavailable.
- Vehicles can be added, edited, safely deleted, and marked available/unavailable.
- Driver & Vehicle Specification now uses a stable modal shell, tabs, error banner, and panel rendering architecture.
- Driver & Vehicle Specification changes refresh the modal immediately and defer the main board reload until the modal closes.
- Unavailable Drivers are hidden from the main Driver dropdown and Trip Summary.
- Unavailable Vehicles are hidden from the Choose Vehicle dropdown.
- Preferred Zone remains hidden from the main dispatch board.
- Business hints remain non-blocking.
- Order cards are now compact and show Invoice #, Company, Suburb, urgency, note preview, and start time.
- Clicking an Order card opens a read-only full detail popup.
- Invoice # and Phone are supported in the Order data model.
- The lower section is now labelled Trip Summary.
- Preferred Zone is hidden on the frontend.
- Pallet-only driver and vehicle capacity exceptions are display-only and non-blocking.
- Pending Driver/Trip selections are preserved after assigning another Order.
- Export Excel button is available near the Dispatch Date controls.
- Excel export uses backend SQLite assignment data.
- Excel export includes only assigned Orders.
- Empty Drivers and empty Trips are not exported.
- Location column is not included in the export.
- No separate Review Summary UI was added.
- Physical Delete Order is not implemented; cancellation is soft delete only.
- Driver and Vehicle management is available through the Driver & Vehicle Specification modal.
- Backend now has SQLite persistence support for demo/master data, manual task assignments, and Driver + Dispatch Date vehicle assignments.
- Runtime SQLite database files are local and ignored by Git.
- No automatic assignment, blocking rules, localStorage, or optimization logic is implemented in this phase.

## Layout Decision
The future Manual Dispatch Board layout must be top-bottom:
- Top: Task Pool
- Bottom: Trip Summary

Do not use a left-right layout unless explicitly requested.

## Future MVP Behavior
- Task Pool shows unassigned Orders.
- Each Order card shows only Suburb and Pallet quantity.
- If an Order only has Loose Bags, Pallet quantity displays as 0.
- Each Order card allows selecting Driver and `trip1` or `trip2`.
- Default trip is `trip1`.
- Assign moves the Order into the selected Driver card.
- Trip Summary currently shows one card per Driver.
- Each Trip Summary card groups Orders by `trip1` and `trip2`.
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
Phase 10A-0 Order card UI refinement is documented in `docs/manual-dispatch-board-phase10a0-ui-refinement.md`.
Phase 10A-1 Add Order is documented in `docs/manual-dispatch-board-phase10a1-add-order.md`.
Phase 10A-3 Edit Order is documented in `docs/manual-dispatch-board-phase10a3-edit-order.md`.
Phase 10A-4 Cancel Order is documented in `docs/manual-dispatch-board-phase10a4-cancel-order.md`.
Phase 10A-5 Order Search and Filter is documented in `docs/manual-dispatch-board-phase10a5-order-filter.md`.
Final Trip Summary snapshot behavior is documented in `docs/manual-dispatch-board-final-trip-summary.md`.
Phase 10G Final Trip Summary persistence is documented in `docs/manual-dispatch-board-phase10g-final-summary-persistence.md`.
Phase 13 Final Trip Summary closed-loop stabilization is documented in `docs/manual-dispatch-board-phase13-final-summary-closed-loop.md`.
Phase 14 Final Trip Summary redesign and demo reset is documented in `docs/manual-dispatch-board-phase14-final-summary-redesign.md`.
Driver & Vehicle Specification is documented in `docs/manual-dispatch-board-driver-vehicle-specification.md`.
Phase 12 UI stability and deferred specification refresh is documented in `docs/manual-dispatch-board-phase12-ui-stability.md`.
Phase 12C Driver & Vehicle Specification modal rebuild is documented in `docs/manual-dispatch-board-phase12c-specification-modal-rebuild.md`.

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
Phase 10A-0 uses backend schema/migration tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 10A-1 uses backend create-order tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 10A-3 uses backend edit-order tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 10A-4 uses backend cancel-order tests, safe migration checks, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 10A-5 uses frontend syntax validation, backend regression tests, static safety checks, and browser/manual checks when tooling is available.
Phase 10G uses backend final-summary persistence tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 13 uses backend final-summary closed-loop tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 14 uses backend final-summary date tests, backend regression tests, frontend syntax validation, static safety checks, and manual browser checks when tooling is available. The local demo reset script must not commit runtime SQLite files.
Phase 10B/C uses backend driver/vehicle specification tests, backend regression tests, frontend syntax validation, static safety checks, and browser/manual checks when tooling is available.
Phase 12 uses frontend syntax validation, backend regression tests, static safety checks, and browser/manual checks when tooling is available.
Phase 12C uses frontend syntax validation, backend regression tests when available, static safety checks, and browser/manual checks when tooling is available.
