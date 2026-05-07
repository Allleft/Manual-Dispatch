# Manual Dispatch Board Phase 12C: Specification Modal Rebuild

## Summary
Phase 12C rebuilds the Driver & Vehicle Specification modal frontend architecture so the modal shell, tabs, error banner, and table panel are stable. The main goal is to prevent availability checkbox changes from rebuilding the modal or resetting table scroll position.

## Why The Modal Was Rebuilt
The previous modal implementation used one `renderSpecificationModal()` function that cleared and rebuilt the entire modal. Even after deferring board reloads, several modal-only paths could still replace the table DOM and reset scroll. Phase 12C separates the modal shell from tab panel rendering.

## Stable Shell / Panel Design
The modal is now split into these responsibilities:
- `renderSpecificationShell()` creates the backdrop, card, header, tabs, persistent error banner, and `#specification-panel` container.
- `renderSpecificationPanel({ preserveScroll })` replaces only the current tab panel content when row sets or forms change.
- `setSpecificationTab(tabName)` updates tab button state and renders only the selected panel.
- `showSpecificationError(message)` updates `#specification-error` directly without rebuilding the modal.
- `loadSpecificationsIntoState()` fetches specifications into state without touching the main board.

## Availability Checkbox Behavior
Driver and Vehicle availability checkboxes now update without rendering the modal or panel:
- The checkbox changes immediately.
- Only the clicked checkbox is disabled while the PATCH request is in flight.
- On success, the matching local Driver or Vehicle item is updated and `specificationDirty` is set to `true`.
- On failure, the checkbox and local state are rolled back and the persistent error banner is updated in place.
- No success or failure path calls `renderSpecificationModal()`, `renderSpecificationPanel()`, `loadSpecificationsIntoState()`, or `loadBoard()`.

## Deferred Board Refresh
The main board is still refreshed only when the modal closes and `specificationDirty` is true. This keeps availability visibility changes from flickering the board during modal work while still applying Driver/Vehicle availability to the main board after close.

## Scroll Preservation
Availability changes do not rebuild the table, so scroll naturally remains in place. Add, Edit, and Delete operations may refresh the panel because row sets or forms change, but `renderSpecificationPanel({ preserveScroll: true })` captures and restores the active table scroll position.

## Validation Results
- `node --check frontend/app.js`: passed.
- `python -m compileall backend`: passed using the bundled Python runtime.
- `python -m unittest discover -s tests -v`: passed using the bundled Python runtime. The suite ran 88 tests with 7 existing FastAPI TestClient skips.
- Static safety checks found no `localStorage`, `sessionStorage`, geolocation, Google Maps, CP-SAT, geocoding, route, or optimization calls.
- `git status --short` and `git diff --stat`: run before commit to confirm the Phase 12C file set.

## Excluded Work
Phase 12C does not change or add:
- backend API behavior
- database schema
- Assign / Unassign behavior
- Order CRUD
- vehicle selection behavior
- Final Trip Summary behavior
- Excel export behavior
- automatic assignment
- maps, ETA, routing, geocoding, CP-SAT, or optimization
- authentication
- MySQL or MariaDB
