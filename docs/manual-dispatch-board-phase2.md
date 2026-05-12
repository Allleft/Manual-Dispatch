# Manual Dispatch Board Phase 2

## Scope
Phase 2 creates a static frontend skeleton for the Manual Dispatch Board. It is visual structure only and does not implement real assignment behavior.

## Files Created
- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

## Skeleton Behavior
- The page clearly identifies itself as the Manual Dispatch Board.
- The layout is top-bottom:
  - Top: Task Pool
  - Bottom: Driver Summary
- Task Pool renders static demo Orders:
  - Dandenong, Pallet 2
  - Clayton, Pallet 0 because it only has Loose Bags
  - Springvale, Pallet 3
- Each Order card shows only Suburb and Pallet quantity as order data.
- Each Order card visually includes a Driver selector, a Trip selector, and an Assign button.
- Trip selector options are `trip1` and `trip2`, with `trip1` selected by default.
- Assign buttons are disabled placeholders in Phase 2.
- Driver Summary renders static cards for John, Tony, and David.
- Each Driver card includes a Choose Vehicle dropdown and visual Trip 1 / Trip 2 groups.
- Vehicle dropdown options show rego values: ABC123, XYZ888, and MCC001.

## Intentionally Not Implemented
- backend API
- database runtime connection
- migrations
- real assignment persistence
- Assign behavior
- Unassign behavior
- auto-assignment
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

## Validation
Phase 2 validation should include:
- `node --check frontend/app.js`
- `Get-Content .\frontend\index.html`
- `Get-Content .\frontend\styles.css`
- `Get-Content .\frontend\app.js`
- `git status --short`
- `git diff --stat`

Functional tests are not required because this phase only creates static frontend skeleton files and no `tests/` folder exists yet.
