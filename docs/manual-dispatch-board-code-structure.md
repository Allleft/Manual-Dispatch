# Manual Dispatch Board Code Structure

This guide maps the current independent Order Delivery and OP SHOP Pickup workspaces. Earlier phase documents remain implementation history; this file describes the active architecture.

## Architecture Boundary

| Concern | Order Delivery | OP SHOP Pickup |
| --- | --- | --- |
| Scoped board | `GET /api/manual-dispatch/delivery/board` | `GET /api/manual-dispatch/opshop/board` |
| Planning view | Delivery Trip Summary | OP SHOP Trip Summary |
| Snapshot | Delivery Run Sheet | Pickup Collection |
| Rows | Delivery Orders grouped by trip | OP SHOP pickups grouped by category/route |
| Totals | Pallets and loose bags | No Delivery totals |
| Lock | Delivery assignment and vehicle for driver/date | OP SHOP assignment for driver/date |
| Export | Delivery Run Sheet workbook | Pickup Collection workbook |

The two modules may use the same driver and date independently. A saved Delivery Run Sheet does not lock OP SHOP, and a saved Pickup Collection does not lock Delivery or vehicle selection.

Legacy Final Trip Summary tables, routes, services, and exports remain readable for compatibility and migration only. New scoped workflow code must not write OP SHOP rows into Delivery rows or totals.

## Business Date Ownership

- Dispatch Date scopes Task Pool operations and remains assignment/document/logbook provenance. A legacy Trip Summary query may still supply it, but scoped reads ignore it.
- Delivery Date alone scopes Delivery Trip Summary, driver/trip grouping, vehicle assignment, Run Sheet candidates, active locks, document lists, and date exports.
- Pickup Date alone scopes OP SHOP Trip Summary, driver grouping, Pickup Collection candidates, active locks, document lists, and date exports.
- Assignment identity is `task_type + task_id`; repositories reject corrupt duplicate rows rather than choosing or deleting one. Reassignment updates the one real assignment and preserves its origin Dispatch Date.
- Vehicle identity is `delivery_date + driver_id`. Delivery Run Sheet active identity is `delivery_date + driver_id`; Pickup Collection active identity is `pickup_date + driver_id`.
- `GENERATED` and `SAVED` locks apply across Dispatch Dates for the same service-date identity.

SQLite and in-memory repositories implement the same global lookup and mutation contracts. Snapshot rows keep their stored `dispatch_date` for audit provenance even though the current UI Dispatch Date is not a Trip Summary filter.

## Backend

### Entry and Route Layer

- `backend/main.py`: FastAPI entry point and static frontend host.
- `backend/api/manual_dispatch.py`: public `/api/manual-dispatch` route layer. Scoped routes delegate to the independent services below; legacy routes remain available.
- `backend/schemas.py`: request, response, and snapshot dataclasses.
- `backend/services/manual_dispatch_service.py`: stable facade used by route handlers and tests.

### Scoped Boards and Mutations

- `delivery_workspace_board_service.py`: Delivery-only orders, assignments, drivers, vehicles, and saved vehicle locks.
- `opshop_workspace_board_service.py`: OP SHOP-only Regular/Oncall/Countryside pickups, drivers, templates, and active route groups. It ensures visible Regular tasks idempotently.
- `delivery_workspace_mutation_service.py`: scoped Delivery assignment, unassignment, and vehicle mutations.
- `opshop_workspace_mutation_service.py`: scoped OP SHOP batch assignment, unassignment, and Countryside route-group assignment.
- `workspace_migration_readiness_service.py`: blocks scoped writes until legacy saved snapshots are represented by validated independent records.

### Independent Snapshot Lifecycles

- `delivery_run_sheet_service.py` and `delivery_run_sheet_lock.py`: generate/save/cancel/read Delivery Run Sheets and enforce Delivery-only locks.
- `opshop_pickup_collection_service.py` and `opshop_pickup_collection_lock.py`: generate/save/cancel/read Pickup Collections and enforce OP SHOP-only locks.
- `delivery_run_sheet_excel_export_service.py`: exports saved Delivery snapshots.
- `opshop_pickup_collection_excel_export_service.py`: exports saved OP SHOP snapshots.

Generated snapshots reserve captured tasks. Saved snapshots are immutable history. Lifecycle transitions use conditional repository writes so stale or duplicate requests cannot silently replace saved data.

### OP SHOP Source and Task Services

- `opshop_pickup_service.py`: Regular task ensuring, Oncall task creation, pickup edit/cancel/restore, and legacy list assignment compatibility.
- `opshop_template_service.py`: Regular/Oncall template CRUD and soft-disable behavior.
- Countryside route-group and membership APIs reuse existing service/repository validation and preserve historical tasks/snapshots.
- `opshop_pickup_excel_export_service.py`: legacy independent operational OP SHOP Run Sheet export; it is separate from Pickup Collection export.

### Persistence

| Data | Tables |
| --- | --- |
| Delivery source/tasks | existing manual order tables |
| OP SHOP locations/templates/tasks | `opshop_locations`, `opshop_pickup_schedules`, `opshop_pickup_tasks` |
| Countryside groups | `opshop_countryside_route_groups` |
| Active assignments | `manual_dispatch_assignments` |
| Delivery snapshots | `delivery_run_sheets`, `delivery_run_sheet_rows` |
| OP SHOP snapshots | `opshop_pickup_collections`, `opshop_pickup_collection_rows` |
| Legacy compatibility | `final_trip_summaries`, `final_trip_summary_rows`, `final_trip_summary_opshop_pickup_rows` |

`sqlite_manual_dispatch_repository.py` and `in_memory_manual_dispatch_repository.py` expose matching contracts. `backend/db/schema.sql` and additive initialization in `backend/db/connection.py` keep older SQLite databases readable.

## Frontend

### Routing and Orchestration

- `frontend/app.js`: parses/normalizes hash routes, derives active workspace/subtype, wires actions to renderers, and orchestrates route loads.
- `workspace-home-renderer.js` and `workspace-navigation-renderer.js`: choose and navigate independent workspaces.
- `workspace-actions.js`: scoped reads/mutations, stale-response guards, draft state, lifecycle actions, and normal hash navigation callbacks.
- `app-state.js`: scoped boards, histories, drafts, busy keys, and modal state.
- `selectors.js`: read-only derived lookup helpers.

Canonical OP SHOP routes are:

- `#opshop/task-pool/regular`
- `#opshop/task-pool/oncall`
- `#opshop/task-pool/countryside`
- `#opshop/templates`
- `#opshop/trip-summary`
- `#opshop/collections`
- `#opshop/history`

The route is the subtype source of truth. Subtype-only navigation reuses the loaded scoped board, so browser Back/Forward and explicit empty-string assignment drafts remain intact.

### OP SHOP Workspace UI

- `opshop-workspace-renderer.js`: Task Pool, Trip Summary, Templates page, Generated/Saved Pickup Collections, and an independent Saved History page that reuses the full Weight Sheet in export-only mode.
- `opshop-template-management-modal-renderer.js` + `opshop-template-actions.js`: shared Regular/Oncall template forms reused inline at `#opshop/templates`.
- `opshop-countryside-pickup-list-modal-renderer.js` + `opshop-countryside-pickup-actions.js`: shared Countryside route-group/membership management and live pickup task forms.
- `opshop-pickup-list-modal-renderer.js` / `opshop-pickup-actions.js`: Regular live-task add/edit/delete forms.
- `opshop-oncall-pickup-list-modal-renderer.js` / `opshop-oncall-pickup-actions.js`: request-driven Oncall create/edit/delete forms.
- `opshop-pickup-modal-renderer.js`: read-only live pickup detail.
- `opshop-workspace-modal-utils.js`: adapts the scoped OP SHOP board to reused task-operation modals without replacing scoped board state.

Persisted source-backed assignments come from controlled backfill or initial template-derived task creation and are authoritative in the scoped board. Assignment dropdown changes made later by staff write to `opshopAssignmentDrafts` until `Apply Assignment Changes`; own-property checks preserve explicit `Unassigned` values. Board loading/rendering never recreates a manually cleared assignment from a template default.

### Delivery Workspace UI

- `delivery-workspace-renderer.js`: Delivery Task Pool, Trip Summary, Run Sheets, and an independent Saved History page that reuses the full DAILY RUN SHEET paper in export-only mode.
- `workspace-actions.js` loads Trip Summary and Saved History only by their service date (`delivery_date` or `pickup_date`), keeps Dispatch Date as provenance metadata, and guards stale responses by route, workspace, and service date rather than the current Dispatch Date.
- Vehicle autosave queues are keyed and validated by Delivery Date plus Driver. A Dispatch Date change does not invalidate a valid queue response for the unchanged Delivery Date.
- Delivery-specific state and actions remain independent from OP SHOP subtype, template, route, and collection state.

## Import and Migration Tools

- `import_regular_opshop_pickups_to_db.py`: locations + Regular schedules only.
- `import_oncall_opshop_pickups_to_db.py`: locations + Oncall templates only; no actual tasks.
- `import_countryside_opshop_pickups_to_db.py`: workbook-backed route groups and memberships only; no actual tasks.
- `backfill_opshop_source_driver_assignments.py`: dry-run-first strict source identity audit; apply updates safe template defaults and eligible unassigned tasks while preserving existing assignments and locks.
- `migrate_legacy_final_summaries_to_workspaces.py`: dry-run by default; apply requires confirmation, creates a verified backup, and copies legacy saved snapshots into independent histories without deleting legacy data.

## Test Boundaries

- `tests/test_workspace_frontend_shell.py`: canonical routes, scoped state, interaction wiring, stale-response safety, template/route/task parity, persisted source assignments, and manual drafts.
- `tests/test_workspace_scoped_boards.py`: independent board payloads and Regular ensure behavior.
- `tests/test_workspace_scoped_mutations.py`: module-only mutations and locks.
- `tests/test_workspace_services.py`: independent lifecycle semantics.
- `tests/test_workspace_snapshot_persistence.py`: additive schema and immutable snapshot persistence.
- `tests/test_workspace_safety_hardening.py`: migration readiness and guarded lifecycle routes.
- `tests/test_workspace_api_and_exports.py`: route contracts and independent workbooks.

## Validation

```powershell
git diff --check
git diff --cached --check
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

Use [the current OP SHOP workspace checklist](opshop-workspace-smoke-test-checklist.md) for browser and copied-database QA.
