# Manual Dispatch Board Data Model

## Phase 1 Status
This document defines the planned data model for the Manual Dispatch Board. Phase 1 does not implement database tables, runtime database connections, backend APIs, frontend UI, or assignment logic.

Manual assignment remains fully controlled by office staff. The MVP must not include automatic driver selection, automatic vehicle selection, automatic trip planning, capacity-based blocking, zone-based blocking, routing, ETA calculation, geocoding, Google Maps logic, CP-SAT, or optimization.

Business hints can be added in a later phase, but they must not block manual assignment unless explicitly approved.

## Planned Entities
The planned Manual Dispatch Board entities are:
- Order
- Driver
- Vehicle
- Manual Dispatch Assignment
- Manual Driver Vehicle Assignment

## Order
Orders are future Task Pool items when they are unassigned.

| Field | Purpose |
| --- | --- |
| `order_id` | Unique Order identifier. |
| `company_name` | Customer or company name for the Order. |
| `delivery_address` | Delivery street address. |
| `suburb` | Suburb displayed on the Order card. |
| `postcode` | Delivery postcode. |
| `delivery_date` | Requested delivery date. |
| `zone` | Planned zone or service area reference. |
| `urgency` | Priority or urgency hint for office staff. |
| `preferred_driver_id` | Optional preferred Driver hint. |
| `pallet_quantity` | Pallet quantity displayed on the Order card. |
| `loose_bags_quantity` | Loose Bags quantity used to understand load type. |
| `start_time` | Optional delivery window start. |
| `end_time` | Optional delivery window end. |
| `note` | Office or delivery note. |

MVP display rule: each Order card shows only `suburb` and `pallet_quantity`. If the Order only has Loose Bags, `pallet_quantity` should display as `0`.

## Driver
Drivers appear as cards in the Driver Summary area.

| Field | Purpose |
| --- | --- |
| `driver_id` | Unique Driver identifier. |
| `name` | Driver display name. |
| `start_time` | Driver availability start time. |
| `end_time` | Driver availability end time. |
| `is_available` | Availability flag for the dispatch date or roster context. |
| `preferred_zone` | Optional zone hint for office staff. |

Driver fields may provide hints, but they must not automatically block manual assignment in the MVP.

## Vehicle
Vehicles are selected from each Driver card through a Choose Vehicle dropdown.

| Field | Purpose |
| --- | --- |
| `vehicle_id` | Unique Vehicle identifier. |
| `rego` | Vehicle registration shown in dropdown options. |
| `type` | Vehicle type or class. |
| `is_available` | Availability flag for the dispatch date or fleet context. |
| `pallet_capacity` | Pallet capacity hint. |
| `tub_capacity` | Tub capacity hint. |
| `trolley_capacity` | Trolley capacity hint. |
| `stillage_capacity` | Stillage capacity hint. |

Capacity fields are hints only in the MVP. They must not create capacity-based blocking unless explicitly approved later.

## Manual Dispatch Assignment
Manual Dispatch Assignment records the office staff decision to assign one task to one Driver and trip on one Dispatch Date.

| Field | Purpose |
| --- | --- |
| `assignment_id` | Unique assignment identifier. |
| `dispatch_date` | Dispatch Date for the assignment. |
| `task_type` | Task category, normally `ORDER` in the MVP. |
| `task_id` | Identifier of the task being assigned. |
| `driver_id` | Selected Driver. |
| `trip_no` | Selected trip, supporting `trip1` and `trip2`. |
| `assigned_at` | Timestamp when the task was assigned. |
| `updated_at` | Timestamp when the assignment was last updated. |

Assignment rules:
- Use `task_type + task_id` instead of hard-coding only `order_id`.
- MVP `task_type` will normally be `ORDER`.
- Future task types may include `PICKUP`, `RETURN`, and `SPECIAL_TASK`.
- `trip_no` supports `trip1` and `trip2`.
- Default trip is `trip1`.
- One task should not be assigned to multiple drivers on the same dispatch date.

## Manual Driver Vehicle Assignment
Manual Driver Vehicle Assignment records the selected Vehicle for a Driver on a Dispatch Date and Driver Summary Delivery Date.

| Field | Purpose |
| --- | --- |
| `dispatch_date` | Dispatch Date for the vehicle choice. |
| `delivery_date` | Driver Summary Delivery Date for the vehicle choice. |
| `driver_id` | Driver receiving the vehicle assignment. |
| `vehicle_id` | Selected Vehicle. |
| `created_at` | Timestamp when the vehicle assignment was created. |
| `updated_at` | Timestamp when the vehicle assignment was last updated. |

Vehicle assignment rules:
- Vehicle selection belongs to Driver + Dispatch Date + Delivery Date.
- Vehicle is not assigned to each individual Order in the MVP.
- Example: John + dispatch date `2026-05-05` + delivery date `2026-05-06` -> ABC123.
- John's `trip1` and `trip2` for the same Dispatch Date + Delivery Date use the same selected vehicle by default.
