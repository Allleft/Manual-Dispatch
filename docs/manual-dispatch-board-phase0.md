# Manual Dispatch Board Phase 0

## MVP Summary
Manual Dispatch Board is a manual office workflow for assigning unassigned Orders to a selected Driver, Trip, and Driver-level Vehicle for a Dispatch Date. Phase 0 creates only governance, documentation, Git setup, and validation rules.

## Layout Decision
The Manual Dispatch Board layout must be top-bottom:
- Top: Task Pool
- Bottom: Driver Summary

This layout is locked for the MVP unless explicitly changed later.

## Manual-Only Rule
This version is manual only. Staff choose the Driver, choose `trip1` or `trip2`, and click Assign. The system must not automatically choose drivers, vehicles, trips, groups, routes, or sequences in the MVP.

## Future MVP Behavior
- Task Pool shows unassigned Orders.
- Each Order card shows only Suburb and Pallet quantity.
- If the Order only has Loose Bags, Pallet quantity should display as 0.
- Each Order card allows selecting Driver and `trip1` or `trip2`.
- Default trip is `trip1`.
- Assign moves the Order into the selected Driver card.
- Driver Summary shows one card per Driver.
- Each Driver card groups Orders by `trip1` and `trip2`.
- Each Driver card has a Choose Vehicle dropdown.
- Vehicle dropdown options show rego.
- Vehicle assignment is at Driver + Dispatch Date level.
- Future task types like Pickup should be supported through `task_type` and `task_id`.

## Planned Data Entities
- Order
- Driver
- Vehicle
- Manual Dispatch Assignment
- Manual Driver Vehicle Assignment

Recommended assignment fields:
- `task_type`
- `task_id`
- `driver_id`
- `trip_no`
- `dispatch_date`

Future task types may include:
- `ORDER`
- `PICKUP`
- `RETURN`
- `SPECIAL_TASK`

## Phase Outline
- Phase 0: governance, documentation, baseline checks only. No UI, backend, or database implementation.
- Phase 1: data model planning and schema design.
- Phase 2: page skeleton.
- Phase 3: frontend manual assignment flow.
- Phase 4: vehicle selection logic.
- Phase 5: backend API.
- Phase 6: database persistence.
- Phase 7: business hints.
- Phase 8: review/export.
- Phase 9: future Pickup/task extension.

## Not Allowed In This MVP
- auto-assignment algorithm
- CP-SAT
- route optimization
- ETA calculation
- geocoding
- Google Maps integration
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- capacity-based blocking
- zone-based blocking
- automatic order grouping
- automatic route sequencing

## Phase 0 Validation
Required validation commands:
- `Get-Content .\AGENTS.md`
- `Get-Content .\README.md`
- `Get-Content .\docs\manual-dispatch-board-phase0.md`
- `git status --short`

Functional tests are not required in Phase 0 when no `tests/`, `frontend/`, or `backend/` implementation files exist.
