# Manual Dispatch Board Phase 10A-1: Add Order

## 1. Summary
Phase 10A-1 adds a minimal Add Order workflow to the Manual Dispatch Board.
Office staff can open an Add New Order popup, enter order details, save the Order through the backend API, and see the new unassigned Order appear in the Task Pool after the board reloads.

This phase only implements Add Order. It does not implement Edit Order, Delete Order, Driver Management, Vehicle Management, import, authentication, automatic assignment, route optimization, ETA, maps, CP-SAT, or blocking rules.

## 2. Add Order Scope
- Added an `Add Order` button near the Task Pool heading.
- Added a read/write `Add New Order` popup card.
- Added frontend API integration for creating Orders.
- Added backend service and repository support for writing to `manual_orders`.
- Added unit tests for create-order behavior and export compatibility after assignment.

## 3. Backend Endpoint
New endpoint:

```text
POST /api/manual-dispatch/orders
```

Existing endpoints remain unchanged:

```text
GET  /api/manual-dispatch/board
POST /api/manual-dispatch/assign
POST /api/manual-dispatch/unassign
POST /api/manual-dispatch/driver-vehicle
GET  /api/manual-dispatch/export-excel
```

The new endpoint creates an Order only. It does not create a manual assignment, does not choose a Driver, does not choose a Trip, and does not choose a Vehicle.

## 4. Popup Card Behavior
- Opens in-place without page navigation.
- Defaults Delivery Date to the currently selected dispatch date.
- Defaults Urgency to `Normal`.
- Defaults Pallet Quantity and Loose Bags Quantity to `0`.
- Preferred Driver is optional and uses the currently loaded driver list.
- Save posts to the backend API and reloads the board on success.
- Cancel closes the popup without saving.
- If save fails, the popup remains open and shows a non-blocking error.

## 5. Form Fields
- Invoice #
- Company Name
- Phone
- Delivery Address
- Suburb
- Postcode
- Delivery Date
- Zone
- Urgency
- Preferred Driver
- Pallet Quantity
- Loose Bags Quantity
- Start Time
- End Time
- Note

## 6. Validation Rules
Backend validation rejects:
- missing `suburb`
- missing `delivery_date`
- negative `pallet_quantity`
- negative `loose_bags_quantity`

Backend defaults:
- blank urgency becomes `Normal`
- blank pallet quantity becomes `0`
- blank loose bags quantity becomes `0`
- blank preferred driver stays empty
- blank invoice number and phone stay empty

The Add Order flow does not reject based on zone, preferred driver mismatch, capacity, driver availability, time window, or vehicle selection.

## 7. SQLite Persistence Behavior
- Created Orders are persisted to `manual_orders`.
- Created Orders are unassigned by default.
- Runtime SQLite database files remain local and ignored by Git.
- Existing assignments and Driver + Dispatch Date vehicle selections are not modified.
- Generated Order IDs use a readable date-based format such as `ORD-20260505-001`.

## 8. Excluded Work
This phase intentionally does not include:
- Edit Order
- Delete Order
- full Order CRUD
- Driver Management
- Vehicle Management
- CSV or Excel import
- authentication/login
- automatic assignment
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- route optimization
- ETA calculation
- geocoding
- Google Maps
- CP-SAT
- blocking rules

## 9. Tests Added
Added `tests/test_manual_dispatch_create_order.py` covering:
- Order creation persists a new Order.
- Created Orders appear in board data.
- Created Orders are unassigned by default.
- Created Orders can be assigned.
- invalid negative quantities are rejected.
- missing suburb and delivery date are rejected.
- created assigned Orders appear in Excel export.
- created unassigned Orders do not appear in Excel export.

## 10. Phase 10A-2 Handoff Notes
Phase 10A-2 can build on this foundation to add Edit Order or richer Order Management if explicitly requested.
Keep the workflow manual and continue to avoid automatic assignment, optimization, and blocking rules unless separately approved.
