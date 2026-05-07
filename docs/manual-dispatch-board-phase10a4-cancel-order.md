# Manual Dispatch Board Phase 10A-4: Cancel Order

## Summary
- Phase 10A-4 adds manual Order cancellation using a soft-delete status.
- Orders are never physically deleted from SQLite.
- Cancelled Orders are hidden from the Task Pool and excluded from Excel export.
- Manual assignment remains controlled by office staff.

## Scope
- Add `status` support to Orders with `ACTIVE` and `CANCELLED` values.
- Add safe SQLite migration for existing local databases that do not have the `status` column.
- Add backend endpoint `POST /api/manual-dispatch/orders/{order_id}/cancel`.
- Add a `Cancel Order` button to the existing Order detail popup.
- Add backend unit tests for cancellation behavior.

## Backend Behavior
- `create_order` creates Orders with `status = ACTIVE`.
- Board Order lists return active Orders only.
- `get_task("ORDER", order_id)` does not return cancelled Orders, so cancelled Orders cannot be assigned.
- Cancelling an assigned Order is rejected with a clear error: `Order must be unassigned before cancellation`.
- Existing assignments and Driver + Dispatch Date vehicle selections are not modified during cancellation.

## Frontend Behavior
- The read-only Order detail popup now includes `Cancel Order`.
- The user must confirm before cancellation.
- On successful cancellation, the popup closes and the board reloads.
- On failure, a non-blocking error is shown and the current UI remains stable.

## Excel Export
- Excel export still includes assigned Orders only.
- Cancelled Orders are excluded because they are no longer included in the active board Order data.
- No Excel column changes were made in this phase.

## Safe Migration
- Existing SQLite databases are upgraded with:
  - `manual_orders.status TEXT NOT NULL DEFAULT 'ACTIVE'`
- Existing rows default to `ACTIVE`.
- No Orders, assignments, or vehicle selections are wiped or overwritten.

## Excluded Work
- Physical delete
- Auto-unassign on cancellation
- Edit/Delete bulk workflow
- Driver management
- Vehicle management
- CSV/Excel import
- Automatic assignment
- Blocking rules
- Maps, ETA, routing, geocoding, CP-SAT, or optimization

## Tests Added
- Cancelling an unassigned Order succeeds.
- Cancelled Orders disappear from the board.
- Cancelled Orders cannot be assigned.
- Assigned Orders cannot be cancelled until unassigned.
- Cancelled Orders are excluded from Excel export.
- Existing databases without `status` are safely upgraded.
- Existing active Orders remain visible.

## Phase 10A-5 Handoff
- Next phase should add frontend-only Task Pool search and urgency filtering.
- Search/filter should not change backend data, assignments, or export behavior.
