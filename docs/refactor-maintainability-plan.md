# Manual Dispatch Maintainability Refactor Plan

## Approved Task

- Source branch: `feature/separate-delivery-and-opshop-workspaces`
- Remote base: `origin/feature/separate-delivery-and-opshop-workspaces`
- Base SHA: `7c60ddf439049069d485480e13ef5c9a78bbf2fa`
- Refactor branch: `refactor/modular-maintainability`
- Isolated worktree: `C:\Users\Albert Fang\Desktop\Delivery V2 Refactor`
- Approved Spec Gate: 2026-07-17

This is a behavior-preserving modular refactor. No intended business, API, database, UI, export, Logbook, or date-scope behavior changes are permitted.

## Non-Change Contracts

- Dispatch Date, Delivery Date, and Pickup Date keep their current scopes.
- Assignment identity, vehicle queues, locks, GENERATED/SAVED/CANCEL lifecycle, and workspace readiness remain unchanged.
- API paths, HTTP methods, request/response fields, status codes, authentication cookies, filenames, and media types remain unchanged.
- SQLite schema, constraints, indexes, query predicates, ordering, conditional updates, row mapping, timestamps, and transaction boundaries remain unchanged.
- Excel sheets, columns, headers, ordering, and sources remain unchanged.
- Logbook action, workspace, result, actor, business-date fields, metadata, failure handling, and best-effort semantics remain unchanged.
- Hash routes, visible text, DOM order, CSS classes, data attributes, ARIA, keyboard/event behavior, modal behavior, and CSS presentation remain unchanged.
- Legacy Final Summary imports, routes, exports, and tests remain available.
- Existing defects are observations only and are not fixed in this refactor.

## Safe Test Environment

- Database: `tmp/manual_dispatch_refactor.sqlite3`
- Logbook: `tmp/refactor-logbook`
- Demo data seeding is disabled for schema capture.
- `data/manual_dispatch.sqlite3` and local business workbooks are never used.

## Baseline Validation

| Check | Result |
|---|---|
| `git diff --check` | PASS |
| `python -m compileall backend tests tools` | PASS |
| `python -m unittest discover -s tests -v` | 652 tests, 90.611s, OK |
| `node --check frontend/app.js` | PASS |
| recursive `node --check` for `frontend/**/*.js` | PASS |

Python 3.13 emits existing `ResourceWarning` messages for unclosed SQLite connections during the passing baseline. They are recorded as an observation and are out of scope.

## Contract Fingerprints

| Contract | Count | SHA-256 |
|---|---:|---|
| FastAPI route path/method entries | 92 | `3165941ce6b027a3024fe82ab70702a36276a7d5f4001626f80a52afaa43917d` |
| `ManualDispatchService` public names/signatures | 93 | `2d897eda0dd20d4f281cab9e90c0ea1d994a41e1b936ae0d906f4f59f75bcf41` |
| SQLite repository public names/signatures | 108 | `fdcf7d0ca3dfa53a026dca7a97cb358d0308c9613eada6039d2afa422d78f805` |
| In-Memory repository public names/signatures | 108 | `fdcf7d0ca3dfa53a026dca7a97cb358d0308c9613eada6039d2afa422d78f805` |
| `createWorkspaceActions` ordered returned names | 78 | `a5c0c3e74c1ef76d26c7967f4c038c6f6317a11fa002b7c42456dc9f0646ddf1` |
| top-level app-state ordered fields | 183 | `8b1d9ae0c1470d603cd3b908927941b9d471394f7bc28d59f7963050e000bec2` |
| canonical workspace routes | 12 | `ff321ae9f5aabfde2b1b1513fcb7defe66485a8a0b9c8086a67edef6556e4c86` |
| Frontend API facade exports | 96 | `070b57b6f76c5c1ced567ebd6ca4761abb499e3e54fe7e9eedd6b58d9269eb80` |
| SQLite schema objects | 22 | `b7d4bc8f8b9e5ade8c4dc259d7138036780743f377b1f6ca5d6082a65686f703` |

SQLite and In-Memory repositories currently expose identical 108-method public contracts.

## API Route Baseline

| Method | Path |
|---|---|
| POST | `/api/manual-dispatch/assign` |
| POST | `/api/manual-dispatch/auth/login` |
| POST | `/api/manual-dispatch/auth/logout` |
| POST | `/api/manual-dispatch/auth/register` |
| POST | `/api/manual-dispatch/auth/reset-password` |
| GET | `/api/manual-dispatch/board` |
| POST | `/api/manual-dispatch/delivery/assignments` |
| POST | `/api/manual-dispatch/delivery/assignments/unassign` |
| GET | `/api/manual-dispatch/delivery/board` |
| POST | `/api/manual-dispatch/delivery/drivers` |
| DELETE | `/api/manual-dispatch/delivery/drivers/{driver_id}` |
| PATCH | `/api/manual-dispatch/delivery/drivers/{driver_id}` |
| POST | `/api/manual-dispatch/delivery/orders` |
| POST | `/api/manual-dispatch/delivery/orders/import-attache-pdf-commit` |
| POST | `/api/manual-dispatch/delivery/orders/import-attache-pdf-preview` |
| PATCH | `/api/manual-dispatch/delivery/orders/{order_id}` |
| POST | `/api/manual-dispatch/delivery/orders/{order_id}/cancel` |
| GET | `/api/manual-dispatch/delivery/run-sheets` |
| GET | `/api/manual-dispatch/delivery/run-sheets/export-excel` |
| POST | `/api/manual-dispatch/delivery/run-sheets/generated` |
| GET | `/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}` |
| POST | `/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/cancel-generated` |
| GET | `/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/export-excel` |
| POST | `/api/manual-dispatch/delivery/run-sheets/{run_sheet_id}/save` |
| GET | `/api/manual-dispatch/delivery/specifications` |
| GET | `/api/manual-dispatch/delivery/trip-summary` |
| POST | `/api/manual-dispatch/delivery/vehicle-assignments` |
| POST | `/api/manual-dispatch/delivery/vehicle-assignments/clear` |
| POST | `/api/manual-dispatch/delivery/vehicles` |
| DELETE | `/api/manual-dispatch/delivery/vehicles/{vehicle_id}` |
| PATCH | `/api/manual-dispatch/delivery/vehicles/{vehicle_id}` |
| POST | `/api/manual-dispatch/driver-vehicle` |
| POST | `/api/manual-dispatch/drivers` |
| DELETE | `/api/manual-dispatch/drivers/{driver_id}` |
| PATCH | `/api/manual-dispatch/drivers/{driver_id}` |
| GET | `/api/manual-dispatch/export-excel` |
| GET | `/api/manual-dispatch/final-summaries` |
| POST | `/api/manual-dispatch/final-summaries` |
| GET | `/api/manual-dispatch/final-summaries/export-excel` |
| POST | `/api/manual-dispatch/final-summaries/generated` |
| GET | `/api/manual-dispatch/final-summaries/{summary_id}` |
| POST | `/api/manual-dispatch/final-summaries/{summary_id}/cancel-generated` |
| GET | `/api/manual-dispatch/final-summaries/{summary_id}/export-excel` |
| POST | `/api/manual-dispatch/final-summaries/{summary_id}/save` |
| GET | `/api/manual-dispatch/final-summary-dates` |
| POST | `/api/manual-dispatch/opshop-countryside-memberships/{schedule_id}/move` |
| POST | `/api/manual-dispatch/opshop-countryside-memberships/{schedule_id}/remove` |
| GET | `/api/manual-dispatch/opshop-countryside-route-groups` |
| POST | `/api/manual-dispatch/opshop-countryside-route-groups` |
| PATCH | `/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}` |
| POST | `/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/disable` |
| GET | `/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/memberships` |
| POST | `/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/memberships` |
| GET | `/api/manual-dispatch/opshop-pickup-schedules` |
| POST | `/api/manual-dispatch/opshop-pickups` |
| POST | `/api/manual-dispatch/opshop-pickups/countryside-assignments/apply` |
| POST | `/api/manual-dispatch/opshop-pickups/countryside-route-groups/{route_group_id}/assign` |
| GET | `/api/manual-dispatch/opshop-pickups/export-excel` |
| POST | `/api/manual-dispatch/opshop-pickups/generate` |
| POST | `/api/manual-dispatch/opshop-pickups/oncall` |
| POST | `/api/manual-dispatch/opshop-pickups/oncall-assignments/apply` |
| POST | `/api/manual-dispatch/opshop-pickups/weekly-assignments/apply` |
| DELETE | `/api/manual-dispatch/opshop-pickups/{pickup_task_id}` |
| PATCH | `/api/manual-dispatch/opshop-pickups/{pickup_task_id}` |
| GET | `/api/manual-dispatch/opshop-templates` |
| POST | `/api/manual-dispatch/opshop-templates` |
| PATCH | `/api/manual-dispatch/opshop-templates/{schedule_id}` |
| POST | `/api/manual-dispatch/opshop-templates/{schedule_id}/disable` |
| GET | `/api/manual-dispatch/opshop/board` |
| POST | `/api/manual-dispatch/opshop/countryside-route-groups/{route_group_id}/assign` |
| GET | `/api/manual-dispatch/opshop/pickup-collections` |
| GET | `/api/manual-dispatch/opshop/pickup-collections/export-excel` |
| POST | `/api/manual-dispatch/opshop/pickup-collections/generated` |
| GET | `/api/manual-dispatch/opshop/pickup-collections/{collection_id}` |
| POST | `/api/manual-dispatch/opshop/pickup-collections/{collection_id}/cancel-generated` |
| GET | `/api/manual-dispatch/opshop/pickup-collections/{collection_id}/export-excel` |
| POST | `/api/manual-dispatch/opshop/pickup-collections/{collection_id}/save` |
| POST | `/api/manual-dispatch/opshop/pickups/assignments/apply` |
| POST | `/api/manual-dispatch/opshop/pickups/assignments/unassign` |
| GET | `/api/manual-dispatch/opshop/trip-summary` |
| POST | `/api/manual-dispatch/orders` |
| POST | `/api/manual-dispatch/orders/import-attache-pdf-commit` |
| POST | `/api/manual-dispatch/orders/import-attache-pdf-preview` |
| PATCH | `/api/manual-dispatch/orders/{order_id}` |
| POST | `/api/manual-dispatch/orders/{order_id}/cancel` |
| GET | `/api/manual-dispatch/shared/specifications` |
| GET | `/api/manual-dispatch/specifications` |
| POST | `/api/manual-dispatch/unassign` |
| POST | `/api/manual-dispatch/vehicles` |
| DELETE | `/api/manual-dispatch/vehicles/{vehicle_id}` |
| PATCH | `/api/manual-dispatch/vehicles/{vehicle_id}` |
| GET | `/api/manual-dispatch/workspace-migration-status` |

## Public Service Baseline

<details>
<summary>ManualDispatchService public methods and signatures</summary>

- `add_countryside_route_membership(self, route_group_id, request)`
- `apply_countryside_opshop_pickup_assignments(self, request)`
- `apply_oncall_opshop_pickup_assignments(self, request)`
- `apply_opshop_workspace_assignments(self, request)`
- `apply_weekly_opshop_pickup_assignments(self, request)`
- `assign_countryside_route_group_pickups(self, route_group_id, request)`
- `assign_delivery_workspace_order(self, request)`
- `assign_delivery_workspace_vehicle(self, request)`
- `assign_opshop_workspace_countryside_route_group(self, route_group_id, request)`
- `assign_task(self, request)`
- `assign_vehicle_to_driver(self, request)`
- `cancel_delivery_order(self, order_id)`
- `cancel_generated_delivery_run_sheet(self, run_sheet_id)`
- `cancel_generated_final_trip_summary(self, summary_id)`
- `cancel_generated_opshop_pickup_collection(self, collection_id)`
- `cancel_order(self, order_id)`
- `clear_delivery_workspace_vehicle(self, request)`
- `clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None)`
- `create_countryside_route_group(self, request)`
- `create_delivery_driver(self, request)`
- `create_delivery_order(self, request)`
- `create_delivery_vehicle(self, request)`
- `create_driver(self, request)`
- `create_generated_delivery_run_sheet(self, request)`
- `create_generated_final_trip_summary(self, request)`
- `create_generated_opshop_pickup_collection(self, request)`
- `create_oncall_opshop_pickup_task(self, request)`
- `create_opshop_pickup_task(self, request)`
- `create_opshop_template(self, request)`
- `create_order(self, request)`
- `create_vehicle(self, request)`
- `delete_delivery_driver(self, driver_id)`
- `delete_delivery_vehicle(self, vehicle_id)`
- `delete_driver(self, driver_id)`
- `delete_opshop_pickup_task(self, pickup_task_id)`
- `delete_vehicle(self, vehicle_id)`
- `disable_countryside_route_group(self, route_group_id)`
- `disable_opshop_template(self, schedule_id)`
- `ensure_opshop_pickup_tasks_for_window(self, request)`
- `get_board(self, dispatch_date)`
- `get_delivery_run_sheet(self, run_sheet_id)`
- `get_delivery_specifications(self)`
- `get_delivery_trip_summary_board(self, delivery_date)`
- `get_delivery_workspace_board(self, dispatch_date)`
- `get_final_trip_summary(self, summary_id)`
- `get_opshop_pickup_collection(self, collection_id)`
- `get_opshop_pickup_collection_for_export(self, collection_id)`
- `get_opshop_trip_summary_board(self, pickup_date)`
- `get_opshop_workspace_board(self, dispatch_date)`
- `get_saved_delivery_run_sheet_for_export(self, run_sheet_id)`
- `get_saved_final_trip_summary_for_export(self, summary_id)`
- `get_saved_opshop_pickup_collection_for_export(self, collection_id)`
- `get_shared_specifications(self)`
- `get_specifications(self)`
- `get_workspace_migration_status(self)`
- `list_countryside_route_groups(self, include_inactive=False)`
- `list_countryside_route_memberships(self, route_group_id)`
- `list_delivery_run_sheets(self, dispatch_date=None, delivery_date=None, status=None)`
- `list_delivery_run_sheets_for_date_export(self, delivery_date)`
- `list_final_summary_dates(self)`
- `list_final_trip_summaries(self, dispatch_date, delivery_date=None)`
- `list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None)`
- `list_opshop_pickup_collections(self, dispatch_date=None, pickup_date=None, status=None)`
- `list_opshop_pickup_collections_for_date_export(self, pickup_date, dispatch_date=None, status=None)`
- `list_opshop_pickup_schedule_candidates(self, run_type='scheduled')`
- `list_opshop_templates(self, run_type=None, include_inactive=False)`
- `logbook_actor(self, actor)`
- `login_operator_account(self, request)`
- `move_countryside_route_membership(self, schedule_id, request)`
- `record_attache_import_confirmation(self, rows, outcome)`
- `record_delivery_run_sheet_export(self, run_sheet, filename)`
- `record_delivery_run_sheets_daily_export(self, run_sheets, delivery_date, filename)`
- `record_opshop_pickup_collection_export(self, collection, filename)`
- `record_opshop_pickup_collections_daily_export(self, collections, pickup_date, filename, dispatch_date=None, status=None)`
- `register_operator_account(self, request)`
- `remove_countryside_route_membership(self, schedule_id)`
- `reset_operator_password(self, request)`
- `save_final_trip_summary(self, request)`
- `save_generated_delivery_run_sheet(self, run_sheet_id, request)`
- `save_generated_final_trip_summary(self, summary_id, saved_by_account_name, saved_by_account_id=None)`
- `save_generated_opshop_pickup_collection(self, collection_id, request)`
- `unassign_delivery_workspace_order(self, request)`
- `unassign_opshop_workspace_pickup(self, request)`
- `unassign_task(self, request)`
- `update_countryside_route_group(self, route_group_id, request)`
- `update_delivery_driver(self, driver_id, request)`
- `update_delivery_order(self, order_id, request)`
- `update_delivery_vehicle(self, vehicle_id, request)`
- `update_driver(self, driver_id, request)`
- `update_opshop_pickup_task(self, pickup_task_id, request)`
- `update_opshop_template(self, schedule_id, request)`
- `update_order(self, order_id, request)`
- `update_vehicle(self, vehicle_id, request)`

</details>

## Public Repository Baseline

Both repository facades expose the following identical public signatures.

<details>
<summary>Repository public methods and signatures</summary>

- `apply_opshop_pickup_assignment_batch(self, dispatch_date, tasks, remove_all_existing=False)`
- `cancel_generated_final_trip_summary(self, summary_id)`
- `cancel_order(self, order_id)`
- `create_driver(self, driver)`
- `create_generated_final_trip_summary(self, summary, rows, opshop_rows=None)`
- `create_operator_account(self, account_name, password_hash, password_salt)`
- `create_order(self, order)`
- `create_vehicle(self, vehicle)`
- `delete_delivery_run_sheet(self, run_sheet_id)`
- `delete_driver(self, driver_id)`
- `delete_generated_delivery_run_sheet(self, run_sheet_id)`
- `delete_generated_opshop_pickup_collection(self, collection_id)`
- `delete_opshop_pickup_collection(self, collection_id)`
- `delete_vehicle(self, vehicle_id)`
- `disable_countryside_route_group(self, route_group_id)`
- `driver_has_active_assignments(self, driver_id)`
- `driver_has_final_summary_history(self, driver_id)`
- `driver_has_vehicle_selection(self, driver_id)`
- `find_assignment_for_task(self, task_type, task_id)`
- `find_countryside_route_group_by_name(self, route_group_name)`
- `find_opshop_pickup_task_by_schedule_and_date(self, schedule_id, pickup_date)`
- `get_assignment(self, dispatch_date, task_type, task_id)`
- `get_countryside_route_group(self, route_group_id)`
- `get_delivery_run_sheet(self, run_sheet_id)`
- `get_delivery_run_sheet_for_driver(self, dispatch_date, delivery_date, driver_id)`
- `get_delivery_run_sheet_reserving_order(self, order_id)`
- `get_driver(self, driver_id)`
- `get_final_trip_summary(self, summary_id)`
- `get_generated_final_trip_summary_for_driver(self, dispatch_date, delivery_date, driver_id)`
- `get_operator_account_by_id(self, account_id)`
- `get_operator_account_by_name(self, account_name)`
- `get_opshop_location(self, opshop_id)`
- `get_opshop_pickup_collection(self, collection_id)`
- `get_opshop_pickup_collection_for_driver(self, dispatch_date, pickup_date, driver_id)`
- `get_opshop_pickup_schedule(self, schedule_id)`
- `get_opshop_pickup_task(self, pickup_task_id)`
- `get_order(self, order_id)`
- `get_task(self, task_type, task_id)`
- `get_vehicle(self, vehicle_id)`
- `get_workspace_migration_status(self)`
- `has_assignment_for_task(self, task_type, task_id)`
- `has_saved_delivery_run_sheet(self, dispatch_date, driver_id, delivery_date)`
- `has_saved_final_trip_summary(self, dispatch_date, driver_id, delivery_date=None)`
- `has_saved_opshop_pickup_collection(self, dispatch_date, driver_id, pickup_date)`
- `insert_opshop_pickup_task(self, task)`
- `list_active_opshop_pickup_schedules(self)`
- `list_assigned_opshop_pickup_board_items(self, dispatch_date)`
- `list_assigned_opshop_pickup_board_items_for_dispatch_and_pickup_date(self, dispatch_date, pickup_date)`
- `list_assigned_opshop_pickup_board_items_for_pickup_date(self, pickup_date)`
- `list_assignments(self, dispatch_date)`
- `list_assignments_for_task(self, task_type, task_id)`
- `list_collectable_opshop_pickup_board_items(self, pickup_date, driver_id, dispatch_date=None)`
- `list_countryside_opshop_pickup_board_items(self, dispatch_date=None)`
- `list_countryside_opshop_pickup_schedule_candidates(self)`
- `list_countryside_route_groups(self, include_inactive=False)`
- `list_delivery_order_assignments_for_delivery_date(self, delivery_date)`
- `list_delivery_run_sheets(self, dispatch_date=None, delivery_date=None, status=None)`
- `list_driver_ids(self)`
- `list_driver_vehicle_assignments(self, dispatch_date)`
- `list_driver_vehicle_assignments_for_delivery_date(self, delivery_date)`
- `list_drivers(self)`
- `list_final_summary_dates(self)`
- `list_final_trip_summaries(self, dispatch_date, delivery_date=None)`
- `list_finalized_opshop_pickup_assignments(self, dispatch_date)`
- `list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None)`
- `list_globally_assigned_delivery_order_assignments(self)`
- `list_globally_assigned_delivery_order_ids(self)`
- `list_globally_unavailable_delivery_order_ids(self)`
- `list_oncall_opshop_pickup_board_items(self, dispatch_date)`
- `list_oncall_opshop_pickup_schedule_candidates(self)`
- `list_opshop_locations(self)`
- `list_opshop_pickup_board_items_for_window(self, start_date, end_date)`
- `list_opshop_pickup_collections(self, dispatch_date=None, pickup_date=None, status=None)`
- `list_opshop_pickup_schedules(self)`
- `list_opshop_pickup_tasks(self)`
- `list_opshop_pickup_tasks_for_window(self, start_date, end_date)`
- `list_opshop_templates(self, run_type=None, include_inactive=False)`
- `list_orders(self, delivery_date=None)`
- `list_reserved_delivery_order_ids(self)`
- `list_scheduled_opshop_pickup_board_items_for_window(self, start_date, end_date)`
- `list_scheduled_opshop_pickup_schedule_candidates(self)`
- `list_specification_drivers(self)`
- `list_specification_vehicles(self)`
- `list_vehicle_ids(self)`
- `list_vehicles(self)`
- `promote_generated_delivery_run_sheet_to_saved(self, run_sheet_id, saved_at, saved_by_account_name, saved_by_account_id)`
- `promote_generated_opshop_pickup_collection_to_saved(self, collection_id, saved_at, saved_by_account_name, saved_by_account_id)`
- `remove_assignment(self, dispatch_date, task_type, task_id)`
- `remove_assignments_for_task(self, task_type, task_id)`
- `remove_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None)`
- `save_final_trip_summary(self, summary, rows, opshop_rows=None)`
- `save_generated_final_trip_summary(self, summary_id, saved_by_account_name, saved_by_account_id)`
- `update_driver(self, driver)`
- `update_operator_account_password(self, account_id, password_hash, password_salt)`
- `update_opshop_pickup_task_assignment_status(self, pickup_task_id, status, driver_id=None, trip_no=None)`
- `update_order(self, order)`
- `update_vehicle(self, vehicle)`
- `upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no)`
- `upsert_countryside_route_group(self, route_group)`
- `upsert_delivery_run_sheet(self, run_sheet)`
- `upsert_delivery_workspace_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id)`
- `upsert_driver_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id)`
- `upsert_opshop_location(self, location)`
- `upsert_opshop_pickup_collection(self, collection)`
- `upsert_opshop_pickup_schedule(self, schedule)`
- `upsert_opshop_pickup_task(self, task)`
- `vehicle_has_current_selection(self, vehicle_id)`
- `vehicle_has_final_summary_history(self, vehicle_id)`

</details>

## Frontend Action Baseline

Factory parameters (5): `state`, `renderWorkspace`, `api = DEFAULT_API`, `confirmAction = defaultConfirmAction`, `navigateWorkspaceRoute = null`.

<details>
<summary>Returned action names</summary>

- `addDeliveryAttacheImportProductLine`
- `addDeliveryOrderProductLine`
- `backDeliveryAttacheImportToFiles`
- `cancelActiveDeliveryOrder`
- `cancelDeliveryDriverForm`
- `applyDeliveryOrderAssignment`
- `applyOpShopAssignmentChanges`
- `assignCountrysideRouteGroup`
- `cancelDeliveryRunSheet`
- `cancelDeliveryOrderEdit`
- `cancelDeliveryVehicleForm`
- `clearDeliveryTaskPoolFilters`
- `clearDeliveryAttacheImportSelection`
- `cancelOpShopPickupCollection`
- `closeDeliveryGenerationConfirmation`
- `closeOpShopGenerationConfirmation`
- `closeDeliveryAttacheImport`
- `closeDeliveryOrderModal`
- `closeDeliverySpecifications`
- `commitDeliveryAttacheImport`
- `deleteDeliveryDriver`
- `deleteDeliveryVehicle`
- `exportDeliveryRunSheet`
- `exportDeliveryRunSheets`
- `exportOpShopPickupCollection`
- `exportOpShopPickupCollections`
- `confirmGenerateDeliveryRunSheet`
- `confirmGenerateOpShopPickupCollection`
- `generateDeliveryRunSheet`
- `generateOpShopPickupCollection`
- `loadWorkspaceRoute`
- `moveDeliveryOrderToTrip`
- `openAddDeliveryOrder`
- `openDeliveryAttacheImport`
- `openDeliveryOrderDetail`
- `openDeliverySpecifications`
- `previewDeliveryAttacheImport`
- `resetDeliveryVehicleTransientState`
- `removeDeliveryOrderProductLine`
- `removeDeliveryAttacheImportProductLine`
- `removeDeliveryAttacheImportFile`
- `saveDeliveryRunSheet`
- `saveDeliveryDriver`
- `saveDeliveryOrderForm`
- `saveDeliveryVehicle`
- `saveOpShopPickupCollection`
- `setDeliverySpecificationTab`
- `startAddDeliveryDriver`
- `startAddDeliveryVehicle`
- `startEditDeliveryDriver`
- `startEditDeliveryOrder`
- `startEditDeliveryVehicle`
- `selectAllReadyDeliveryAttacheRows`
- `toggleDeliveryAttacheImportRow`
- `toggleDeliveryAttacheImportExpanded`
- `toggleDeliveryDriverAvailability`
- `toggleDeliveryVehicleAvailability`
- `unassignDeliveryOrder`
- `unassignOpShopPickup`
- `updateCountrysideRouteGroupDraft`
- `updateDeliveryAssignmentDraft`
- `updateDeliveryAttacheImportFiles`
- `updateDeliveryAttacheImportProductLine`
- `updateDeliveryAttacheImportRow`
- `updateDeliveryDriverForm`
- `updateDeliveryOrderForm`
- `updateDeliveryOrderProductLine`
- `updateDeliverySavedHistoryDate`
- `updateDeliveryTaskPoolFilter`
- `updateDeliveryTripSummaryDate`
- `updateDeliveryVehicleSelection`
- `updateDeliveryVehicleForm`
- `updateDispatchDate`
- `updateOpShopSavedHistoryDate`
- `updateOpShopAssignmentDraft`
- `updateOpShopTaskPoolView`
- `updateOpShopTripSummaryDate`
- `toggleRegularOpShopDateGroup`

</details>

## State and Route Baseline

<details>
<summary>Top-level app-state fields</summary>

- `dispatchDate`
- `driverSummaryDeliveryDate`
- `activeBoardView`
- `workspaceRoute`
- `activeWorkspace`
- `workspaceMigrationStatus`
- `isWorkspaceMigrationStatusLoading`
- `workspaceMigrationStatusError`
- `deliveryBoard`
- `deliveryRunSheets`
- `deliverySavedHistoryDate`
- `deliverySavedHistoryRunSheets`
- `deliveryTripSummaryBoard`
- `deliveryTripSummaryRunSheets`
- `deliveryTripSummaryDate`
- `opshopBoard`
- `opshopPickupCollections`
- `opshopSavedHistoryDate`
- `opshopSavedHistoryCollections`
- `opshopTripSummaryBoard`
- `opshopTripSummaryCollections`
- `opshopTaskPoolView`
- `opshopTaskPoolReturnRoute`
- `opshopTripSummaryDate`
- `sharedSpecifications`
- `isDeliveryWorkspaceLoading`
- `deliveryWorkspaceError`
- `deliveryActionError`
- `deliveryBusyActionKeys`
- `deliveryGenerationConfirmation`
- `deliveryAssignmentDrafts`
- `deliveryVehicleDrafts`
- `deliveryVehicleClaims`
- `deliveryVehicleClaimSequence`
- `deliveryVehicleErrors`
- `deliveryVehiclePendingKeys`
- `deliveryTaskPoolFilters`
- `deliveryOrderDetailId`
- `deliveryOrderDetailReadOnly`
- `deliveryOrderForm`
- `deliveryOrderFormMode`
- `deliveryOrderModalError`
- `deliveryAttacheImportState`
- `deliverySpecifications`
- `deliverySpecificationModalOpen`
- `deliverySpecificationTab`
- `deliveryDriverForm`
- `deliveryDriverEditingId`
- `deliveryVehicleForm`
- `deliveryVehicleEditingId`
- `deliverySpecificationError`
- `deliverySpecificationBusyKey`
- `isOpShopWorkspaceLoading`
- `opshopWorkspaceError`
- `opshopActionError`
- `opshopBusyActionKeys`
- `opshopGenerationConfirmation`
- `opshopAssignmentDrafts`
- `countrysideRouteGroupDrafts`
- `accountName`
- `accountId`
- `isLoggedIn`
- `authMode`
- `loginError`
- `registerError`
- `authSuccessMessage`
- `resetError`
- `isAuthLoading`
- `isLoading`
- `isSaving`
- `errorMessage`
- `orders`
- `drivers`
- `vehicles`
- `assignments`
- `driverVehicleAssignments`
- `finalizedDriverDeliveryDates`
- `opshopPickups`
- `assignedOpShopPickups`
- `scheduledOpShopPickups`
- `oncallOpShopPickups`
- `countrysideOpShopPickups`
- `countrysideRouteGroups`
- `opshopRegularListWindowStart`
- `opshopRegularListWindowEnd`
- `opshopPickupAssignedDriverSelections`
- `oncallOpShopPickupAssignedDriverSelections`
- `countrysideOpShopPickupAssignedDriverSelections`
- `oncallOpShopPickupTemplateFilter`
- `isOncallOpShopPickupTemplatePickerOpen`
- `collapsedRegularOpShopPickupDates`
- `collapsedOncallOpShopPickupDates`
- `collapsedCountrysideOpShopPickupRouteGroups`
- `opshopPickupScheduleCandidates`
- `oncallOpShopPickupScheduleCandidates`
- `countrysideOpShopPickupScheduleCandidates`
- `countrysideRouteMemberships`
- `opshopTemplates`
- `isOpShopPickupListOpen`
- `isOncallOpShopPickupListOpen`
- `isCountrysideOpShopPickupListOpen`
- `isOpShopTemplateManagementOpen`
- `isOpShopPickupListLoading`
- `isOncallOpShopPickupListLoading`
- `isCountrysideOpShopPickupListLoading`
- `isOpShopPickupSaving`
- `isOncallOpShopPickupSaving`
- `isCountrysideOpShopPickupSaving`
- `isOpShopTemplateLoading`
- `isOpShopTemplateSaving`
- `opshopPickupListError`
- `oncallOpShopPickupListError`
- `countrysideOpShopPickupListError`
- `countrysideRouteManagementError`
- `opshopTemplateError`
- `opshopPickupFormMode`
- `oncallOpShopPickupFormMode`
- `countrysideOpShopPickupFormMode`
- `opshopPickupEditingTaskId`
- `oncallOpShopPickupEditingTaskId`
- `countrysideOpShopPickupEditingTaskId`
- `opshopPickupForm`
- `oncallOpShopPickupForm`
- `countrysideOpShopPickupForm`
- `isCountrysideRouteFormOpen`
- `countrysideRouteFormMode`
- `countrysideRouteForm`
- `countrysideRouteTemplateFormMode`
- `countrysideRouteTemplateForm`
- `countrysideRouteTemplateEditingScheduleId`
- `countrysideRouteTemplateMoveTargetRouteGroupId`
- `activeCountrysideRouteTemplateDetailId`
- `isCountrysideRouteTemplateSaving`
- `selectedCountrysideRouteGroupId`
- `opshopTemplateActiveTab`
- `opshopTemplateIncludeInactive`
- `opshopTemplateFormMode`
- `opshopTemplateEditingScheduleId`
- `opshopTemplateForm`
- `pendingSelections`
- `taskPoolSearch`
- `urgencyFilter`
- `taskPoolDeliveryDateFilter`
- `finalTripSummaries`
- `generatedTaskKeys`
- `isSavingFinalSummaries`
- `finalSummaryGlobalSaveError`
- `finalSummaryGlobalSaveSuccess`
- `finalSummaryDates`
- `historyDate`
- `finalSummaryHistory`
- `isHistoryLoading`
- `isReExportingFinalSummaryId`
- `historyLoaded`
- `historyError`
- `isSpecificationModalOpen`
- `specificationDrivers`
- `specificationVehicles`
- `specificationError`
- `specificationLoading`
- `specificationSaving`
- `specificationActiveTab`
- `specificationDirty`
- `driverSpecificationForm`
- `driverSpecificationEditingId`
- `vehicleSpecificationForm`
- `vehicleSpecificationEditingId`
- `activeOrderDetailId`
- `activeOpShopPickupDetailId`
- `isProductDetailOpen`
- `isAddOrderOpen`
- `isAttacheInvoiceImportOpen`
- `isAttacheInvoiceImportPreviewing`
- `isAttacheInvoiceImportCommitting`
- `attacheInvoiceImportFiles`
- `attacheInvoiceImportRows`
- `attacheInvoiceImportError`
- `attacheInvoiceImportSuccess`
- `addOrderError`
- `addOrderForm`
- `isOrderEditMode`
- `orderEditError`
- `orderEditForm`

</details>

Canonical workspace routes:
- `home`
- `delivery/task-pool`
- `delivery/trip-summary`
- `delivery/run-sheet`
- `delivery/history`
- `opshop/task-pool/regular`
- `opshop/task-pool/oncall`
- `opshop/task-pool/countryside`
- `opshop/trip-summary`
- `opshop/templates`
- `opshop/collections`
- `opshop/history`

## Logbook Action Baseline

- `ATTACHE_IMPORT_CONFIRMED`
- `COUNTRYSIDE_MEMBERSHIP_ADDED`
- `COUNTRYSIDE_MEMBERSHIP_MOVED`
- `COUNTRYSIDE_MEMBERSHIP_REMOVED`
- `COUNTRYSIDE_ROUTE_GROUP_ASSIGNED`
- `COUNTRYSIDE_ROUTE_GROUP_CREATED`
- `COUNTRYSIDE_ROUTE_GROUP_DISABLED`
- `COUNTRYSIDE_ROUTE_GROUP_RENAMED`
- `DELIVERY_RUN_SHEETS_DAILY_EXPORTED`
- `DELIVERY_RUN_SHEET_CANCELLED`
- `DELIVERY_RUN_SHEET_EXPORTED`
- `DELIVERY_RUN_SHEET_GENERATED`
- `DELIVERY_RUN_SHEET_SAVED`
- `ONCALL_TEMPLATE_CREATED`
- `ONCALL_TEMPLATE_DISABLED`
- `ONCALL_TEMPLATE_UPDATED`
- `OPSHOP_TASK_ASSIGNED`
- `OPSHOP_TASK_CANCELLED`
- `OPSHOP_TASK_CREATED`
- `OPSHOP_TASK_REASSIGNED`
- `OPSHOP_TASK_UNASSIGNED`
- `OPSHOP_TASK_UPDATED`
- `ORDER_ASSIGNED`
- `ORDER_CANCELLED`
- `ORDER_CREATED`
- `ORDER_REASSIGNED`
- `ORDER_UNASSIGNED`
- `ORDER_UPDATED`
- `PICKUP_COLLECTIONS_DAILY_EXPORTED`
- `PICKUP_COLLECTION_CANCELLED`
- `PICKUP_COLLECTION_EXPORTED`
- `PICKUP_COLLECTION_GENERATED`
- `PICKUP_COLLECTION_SAVED`
- `REGULAR_TEMPLATE_CREATED`
- `REGULAR_TEMPLATE_DISABLED`
- `REGULAR_TEMPLATE_UPDATED`
- `VEHICLE_ASSIGNED`
- `VEHICLE_CHANGED`
- `VEHICLE_CLEARED`

## Largest Source Files Before Refactor

| Lines | File |
|---:|---|
| 6904 | `frontend/styles.css` |
| 4262 | `backend/repositories/sqlite_manual_dispatch_repository.py` |
| 2644 | `frontend/js/actions/workspace-actions.js` |
| 2548 | `frontend/js/render/delivery-workspace-renderer.js` |
| 2053 | `backend/services/manual_dispatch_service.py` |
| 1936 | `backend/repositories/in_memory_manual_dispatch_repository.py` |
| 1627 | `frontend/js/render/opshop-workspace-renderer.js` |
| 1571 | `frontend/js/render/opshop-countryside-pickup-list-modal-renderer.js` |
| 1503 | `backend/api/manual_dispatch.py` |
| 1353 | `frontend/app.js` |
| 1064 | `backend/services/manual_dispatch/attache_invoice_pdf_parser.py` |
| 1004 | `backend/services/manual_dispatch/opshop_pickup_service.py` |
| 972 | `backend/schemas.py` |
| 926 | `frontend/js/render/opshop-oncall-pickup-list-modal-renderer.js` |
| 916 | `frontend/js/api/manual-dispatch-api.js` |
| 740 | `frontend/js/actions/opshop-countryside-pickup-actions.js` |
| 734 | `frontend/js/render/opshop-pickup-list-modal-renderer.js` |
| 699 | `frontend/js/actions/final-summary-actions.js` |
| 688 | `frontend/js/render/order-modal-renderer.js` |
| 586 | `frontend/js/render/task-pool-renderer.js` |
| 578 | `frontend/js/render/trip-summary-renderer.js` |
| 566 | `frontend/js/utils/opshop-workspace-modal-utils.js` |
| 524 | `backend/services/manual_dispatch/final_summary_service.py` |
| 516 | `frontend/js/render/final-summary-renderer.js` |
| 505 | `backend/services/manual_dispatch/opshop_template_service.py` |
| 492 | `frontend/js/actions/opshop-oncall-pickup-actions.js` |
| 419 | `frontend/js/render/attache-invoice-import-modal-renderer.js` |
| 415 | `backend/db/connection.py` |
| 388 | `frontend/js/actions/specification-actions.js` |
| 349 | `frontend/js/render/opshop-template-management-modal-renderer.js` |
| 340 | `frontend/js/actions/opshop-pickup-actions.js` |
| 322 | `frontend/js/actions/order-actions.js` |
| 285 | `frontend/js/state/selectors.js` |
| 263 | `backend/services/opshop_pickup_excel_export_service.py` |
| 263 | `backend/services/delivery_run_sheet_excel_export_service.py` |
| 260 | `backend/services/manual_dispatch/opshop_workspace_mutation_service.py` |
| 251 | `backend/services/final_summary_excel_export_service.py` |
| 249 | `frontend/js/actions/opshop-template-actions.js` |
| 243 | `frontend/js/actions/auth-actions.js` |
| 237 | `frontend/js/render/auth-renderer.js` |

## Implemented Module Structure

1. `backend/api/manual_dispatch.py` remains the stable facade; `backend/api/manual_dispatch_routes/` owns shared helpers and bounded route groups.
2. `ManualDispatchService(repository=None, logbook=None)` remains the stable 93-method facade; five application services and five audit components own orchestration.
3. SQLite and In-Memory repositories remain stable 108-method facades; matching mixins own cohesive persistence concerns.
4. `createWorkspaceActions` keeps its five parameters and ordered 78-action return contract; 18 modules own context, guards, loaders, reset, and bounded workflows.
5. `renderDeliveryWorkspace(root, options)` remains stable; 10 Delivery modules own page sections, documents, history, modals, and utilities.
6. `renderOpShopWorkspace(root, options)` remains stable; 10 OP SHOP modules own page sections, subtype renderers, collections, history, templates, and utilities.
7. `manual-dispatch-api.js` remains the 96-export barrel; shared, Delivery, OP SHOP, and legacy modules own the original request implementations.
8. `app-state.js`, `selectors.js`, `frontend/styles.css`, and maintenance tools remain unchanged. State splitting risked shared-object order/reference contracts, and no safe, clear tool-helper duplication justified a CLI refactor.

Child modules do not import their compatibility facade. API, action, and renderer dependency graphs are acyclic.

## Atomic Commit Sequence

1. `10aec55 docs: record maintainability refactor baseline`
2. `7cc0815 test: capture behavior before modular refactor`
3. `1a768c0 refactor(api): split manual dispatch route modules`
4. `0b47b61 refactor(service): separate application and audit orchestration`
5. `1ba8977 refactor(repository): separate persistence concerns`
6. `4f48da5 refactor(frontend): modularize workspace action orchestration`
7. `2431a0c refactor(frontend): split delivery workspace renderer`
8. `5fc3c26 refactor(frontend): split opshop workspace renderer`
9. `ec704fd refactor(frontend): organize manual dispatch api modules`
10. The final documentation commit uses `docs: update architecture after modular refactor`.

## Implementation Verification

- Characterization coverage added five tests; the full suite is 657 tests.
- Every structural phase passed focused tests and a 657-test full regression before commit.
- The 92-route, 93-Service-method, 108/108-Repository-method, 78-action, 183-state-field, 12-route, 22-schema-object, and 96-frontend-API-export fingerprints remain unchanged.
- Delivery owns 97 renderer child functions; OP SHOP owns 61; both graphs are acyclic.
- The frontend API split preserves 102/102 function bodies after export-only helper declarations and retains the 96-export digest.
- No dependencies, schema objects, SQL, CSS, environment variables, public routes, business dates, Excel formats, Logbook contracts, or runtime data changed.

## Batch Guardrails

- High-risk batch budget: at most 20 changed files; drift check after 10 files.
- Each phase runs targeted tests, full tests, `git diff --check`, dependency audit, new-file audit, and scope audit before commit.
- No phase may add dependencies, modify `AGENTS.md`, touch runtime/business data, or include unrelated formatting.
- New behavior or more than 50 lines of net-new logic requires a human checkpoint.

## Acceptance and Rollback

- Contract counts, names, signatures, hashes, schema objects, routes, state fields, actions, strings, and browser flows are compared before and after.
- All existing and new tests must pass in the isolated environment.
- Browser smoke covers Delivery, OP SHOP, cross-workspace independence, navigation, refresh, logout stale-response behavior, and migration readiness.
- Every phase is independently revertible with `git revert <phase-commit>`.
- The final branch must be clean, pushed, and proposed as an unmerged Draft PR.
