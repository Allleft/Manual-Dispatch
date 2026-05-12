# Manual Dispatch Board Driver & Vehicle Specification

## Summary
- Phase 10B/C-1 adds a Driver & Vehicle Specification modal.
- The modal manages manual master data for Drivers and Vehicles without leaving the dispatch board.
- This is not an automatic assignment feature and does not add optimization, routing, ETA, maps, or blocking rules.

## Modal Behavior
- The top controls include `Driver & Vehicle Specification`.
- Clicking the button opens a large modal with two tabs:
  - Drivers
  - Vehicles
- Each tab lists current non-deleted master records and provides Add, Edit, Delete, and Availability controls.
- The modal stays open after save/delete when practical and refreshes both specification data and the main board.

## Driver Fields
- Availability
- Driver ID
- Name
- License No
- Email
- Phone Number
- Start Time
- End Time
- Pallet Only
- Preferred Zone

Preferred Zone is editable in the specification modal but remains hidden from the main dispatch board and Trip Summary.

## Vehicle Fields
- Availability
- Vehicle ID
- Rego
- Type
- Pallet Capacity
- Tub Capacity
- Trolley Capacity
- Stillage Capacity

## Availability Behavior
- Unavailable Drivers are hidden from the main Driver dropdown and Trip Summary cards.
- Unavailable Vehicles are hidden from the Choose Vehicle dropdown.
- A Driver with active assigned Orders cannot be made unavailable until the Orders are unassigned or finalized.
- A Vehicle currently selected by a Driver cannot be made unavailable until that selection is cleared.
- Availability does not trigger automatic reassignment or automatic vehicle replacement.

## Add/Edit/Delete Behavior
- New Driver IDs are generated as readable IDs such as `D004`, `D005`, and so on.
- New Vehicle IDs are generated as readable IDs such as `V004`, `V005`, and so on.
- Delete uses safe soft delete through `is_deleted = 1`.
- Deleted Drivers and Vehicles are hidden from the specification modal and main board.
- Delete is rejected when active assignment, vehicle selection, or saved Final Trip Summary history would make hiding the record unsafe.

## Main Board Filtering
- The board endpoint returns only available, non-deleted Drivers and Vehicles.
- The specifications endpoint returns available and unavailable records, excluding soft-deleted records.
- Orders and existing manual workflow behavior remain unchanged.

## Backend Endpoints
- `GET /api/manual-dispatch/specifications`
- `POST /api/manual-dispatch/drivers`
- `PATCH /api/manual-dispatch/drivers/{driver_id}`
- `DELETE /api/manual-dispatch/drivers/{driver_id}`
- `POST /api/manual-dispatch/vehicles`
- `PATCH /api/manual-dispatch/vehicles/{vehicle_id}`
- `DELETE /api/manual-dispatch/vehicles/{vehicle_id}`

## Tests
- `tests/test_driver_vehicle_specification.py` covers specification loading, create/edit/delete behavior, availability filtering, safety rejections, and assignment/vehicle selection regression.

## Explicitly Excluded Work
- Automatic assignment
- Automatic driver or vehicle selection
- Route optimization
- ETA calculation
- Maps or geocoding
- CP-SAT or OR-Tools
- Blocking rules
- Authentication
- Excel import
- MySQL or MariaDB
