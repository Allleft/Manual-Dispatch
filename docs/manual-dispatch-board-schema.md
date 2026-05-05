# Manual Dispatch Board Schema Design

## Phase 1 Status
This document describes the planned schema shape only. It is not a runtime migration, does not create database tables, and does not introduce a database connection.

The Manual Dispatch Board remains a manual workflow. The schema supports office staff choices; it must not introduce automatic driver selection, automatic vehicle selection, automatic trip planning, capacity-based blocking, zone-based blocking, route sequencing, ETA calculation, maps, CP-SAT, or optimization.

## Logical Tables
The planned schema contains these logical tables or equivalent persisted entities:
- `orders`
- `drivers`
- `vehicles`
- `manual_dispatch_assignments`
- `manual_driver_vehicle_assignments`

## `orders`
Planned fields:

| Field | Requirement |
| --- | --- |
| `order_id` | Primary identifier. |
| `company_name` | Planned descriptive field. |
| `delivery_address` | Planned descriptive field. |
| `suburb` | Required for MVP card display. |
| `postcode` | Planned descriptive field. |
| `delivery_date` | Planned scheduling field. |
| `zone` | Planned hint field. |
| `urgency` | Planned hint field. |
| `preferred_driver_id` | Optional Driver hint. |
| `pallet_quantity` | Required for MVP card display; display `0` for Loose Bags only. |
| `loose_bags_quantity` | Planned load detail field. |
| `start_time` | Optional delivery window start. |
| `end_time` | Optional delivery window end. |
| `note` | Optional note. |

## `drivers`
Planned fields:

| Field | Requirement |
| --- | --- |
| `driver_id` | Primary identifier. |
| `name` | Required display field. |
| `start_time` | Optional availability start. |
| `end_time` | Optional availability end. |
| `is_available` | Availability hint. |
| `preferred_zone` | Zone hint. |

## `vehicles`
Planned fields:

| Field | Requirement |
| --- | --- |
| `vehicle_id` | Primary identifier. |
| `rego` | Required dropdown display field. |
| `type` | Vehicle type or class. |
| `is_available` | Availability hint. |
| `pallet_capacity` | Capacity hint only. |
| `tub_capacity` | Capacity hint only. |
| `trolley_capacity` | Capacity hint only. |
| `stillage_capacity` | Capacity hint only. |

## `manual_dispatch_assignments`
Planned fields and constraints:

| Field | Requirement |
| --- | --- |
| `assignment_id` | Primary key. |
| `dispatch_date` | Required. |
| `task_type` | Required; MVP normally uses `ORDER`. |
| `task_id` | Required. |
| `driver_id` | Required. |
| `trip_no` | Required; supports `trip1` and `trip2`; default `trip1`. |
| `assigned_at` | Assignment timestamp. |
| `updated_at` | Last update timestamp. |

Recommended constraints:
- Primary key on `assignment_id`.
- Required values for `dispatch_date`, `task_type`, `task_id`, `driver_id`, and `trip_no`.
- Default `trip_no` is `trip1`, the logical equivalent of trip number 1.
- Unique constraint on `dispatch_date + task_type + task_id`.

The unique constraint prevents one task from being assigned to multiple drivers on the same dispatch date.

## `manual_driver_vehicle_assignments`
Planned fields and constraints:

| Field | Requirement |
| --- | --- |
| `id` | Primary key. |
| `dispatch_date` | Required. |
| `driver_id` | Required. |
| `vehicle_id` | Required. |
| `created_at` | Creation timestamp. |
| `updated_at` | Last update timestamp. |

Recommended constraints:
- Primary key on `id`.
- Required values for `dispatch_date`, `driver_id`, and `vehicle_id`.
- Unique constraint on `dispatch_date + driver_id`.

The unique constraint keeps vehicle assignment at Driver + Dispatch Date level. Vehicle is not assigned to each individual Order in the MVP.

## Future Task Types
Assignments use `task_type + task_id` so future tasks can be added without redesigning assignment records.

Planned task types may include:
- `ORDER`
- `PICKUP`
- `RETURN`
- `SPECIAL_TASK`

## Manual Control Rules
- Office staff manually choose Driver, Trip, and Vehicle.
- Business hints may be added later, but hints must not block manual assignment unless explicitly approved.
- Capacity, zone, availability, and preferred Driver fields are planning or hint fields only in the MVP.
