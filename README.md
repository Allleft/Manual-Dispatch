# Manual Dispatch Board

Manual Dispatch Board is a manual office workflow for assigning Orders to Driver + Trip + Vehicle. This repository is currently in Phase 2: static frontend page skeleton only.

## Current Phase
- Phase: 2
- Status: static frontend skeleton only
- No backend API, database tables, runtime database connection, assignment logic, persistence, or optimization logic is implemented in this phase.

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

## Validation
Phase 0 uses document and Git validation only. Functional tests should not be run until test, frontend, or backend implementation files exist.
Phase 1 also uses document and Git validation only because implementation files do not exist yet.
Phase 2 uses frontend syntax validation and static file review only. Real assignment behavior belongs to Phase 3.
