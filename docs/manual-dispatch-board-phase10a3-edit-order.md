# Manual Dispatch Board Phase 10A-3: Edit Order

## 1. Summary
Phase 10A-3 adds manual Edit Order support from the existing Order detail popup.
Office staff can open an Order, click Edit, update allowed Order fields, and save changes through the backend API to SQLite.

This phase keeps the workflow manual. It does not add Delete Order, Driver Management, Vehicle Management, import, authentication, automatic assignment, route optimization, ETA, maps, CP-SAT, or blocking rules.

## 2. Edit Order Scope
- Added an Edit button to the read-only Order detail popup.
- Added editable mode inside the same popup.
- Added backend update support for `manual_orders`.
- Added unit tests for validation, assignment preservation, board response updates, Excel export updates, and delivery date protection.
- Existing assignment and vehicle selection records are preserved.

## 3. Backend Endpoint
New endpoint:

```text
PATCH /api/manual-dispatch/orders/{order_id}
```

Existing endpoints remain unchanged:

```text
GET  /api/manual-dispatch/board
POST /api/manual-dispatch/orders
POST /api/manual-dispatch/assign
POST /api/manual-dispatch/unassign
POST /api/manual-dispatch/driver-vehicle
GET  /api/manual-dispatch/export-excel
```

## 4. Editable Fields
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

Delivery Date is editable for active Orders. Changing it updates the Order's customer Delivery Date while preserving any existing Dispatch Date / Driver / Trip assignment.

## 5. Frontend Behavior
- Read-only detail popup now shows `Edit`.
- Edit mode shows `Save Changes` and `Cancel Edit`.
- `Cancel Edit` returns to read-only mode without saving.
- Successful save reloads board data from the backend source of truth.
- Save failure keeps the edit form open and shows a non-blocking error.

## 6. Validation Rules
Backend validation rejects:
- missing `suburb`
- negative `pallet_quantity`
- negative `loose_bags_quantity`

Backend defaults:
- blank urgency becomes `Normal`
- blank preferred driver stays empty
- blank invoice number and phone stay empty
- blank note stays empty

The edit flow does not reject based on zone, preferred driver mismatch, capacity, driver availability, time window, or vehicle selection.

## 7. Assignment Preservation
Editing an assigned Order does not:
- unassign the Order
- change assigned Driver
- change assigned Trip
- change Driver + Dispatch Date vehicle assignment
- store vehicle data on task assignment records

Updated assigned Order fields are visible in board data and Excel export after save.

## 8. Excluded Work
This phase intentionally does not include:
- Delete Order
- Cancel Order
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
Added `tests/test_manual_dispatch_edit_order.py` covering:
- Order fields update.
- missing suburb is rejected.
- negative pallet quantity is rejected.
- negative loose bags quantity is rejected.
- assigned Order remains assigned after edit.
- updated assigned Order appears in board response.
- updated assigned Order appears in Excel export.
- delivery date cannot be modified through the edit service.

## 10. Phase 10A-4 Handoff Notes
Phase 10A-4 can add Cancel Order / soft delete if explicitly approved.
Keep cancellation separate from edit so assignment preservation remains easy to review.
