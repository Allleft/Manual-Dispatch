# Manual Dispatch Board Code Structure

This note maps the current implementation for maintainers reviewing the manual dispatch workflow and its OP SHOP extensions.

This document describes the current OP SHOP-enabled implementation and its stable module boundaries.

## Architecture Boundary

- The Manual Dispatch Board remains a manual office workflow.
- Delivery Orders and OP SHOP pickups share assignment infrastructure through `task_type + task_id`, but remain separate task domains.
- Delivery rows are shown in Driver Summary Trip 1 / Trip 2 and contribute to Delivery totals.
- OP SHOP pickups are shown in the separate driver-level `OP SHOP PICKUPS` section and do not contribute to Delivery totals.
- Final Trip Summary persists Delivery rows and OP SHOP rows in separate snapshot tables and renders/exports them in separate sections.
- Saved Final Summary state hard-locks the associated driver, Dispatch Date, and Delivery Date against new editable assignments or vehicle changes.

## Backend

### Entry Points and API

- `backend/main.py`: FastAPI application entry point and static frontend host.
- `backend/api/manual_dispatch.py`: Thin HTTP route layer for `/api/manual-dispatch`; route paths and response fields are public frontend contracts.
- `backend/schemas.py`: Dataclass request, response, and persistence transfer objects.

### Domain Services

- `backend/services/manual_dispatch_service.py`: Stable service facade used by API routes and tests.
- `backend/services/manual_dispatch/auth_service.py`: Operator registration, login, password hashing, and reset-password behavior.
- `backend/services/manual_dispatch/board_service.py`: Board response assembly, OP SHOP list payloads, assigned pickup payloads, and saved-summary lock exposure.
- `backend/services/manual_dispatch/assignment_service.py`: Order/OP SHOP manual assignment and driver/date vehicle selection, including saved-summary lock rejection.
- `backend/services/manual_dispatch/order_service.py`: Delivery Order create, update, and cancel lifecycle.
- `backend/services/manual_dispatch/specification_service.py`: Driver and Vehicle maintenance.
- `backend/services/manual_dispatch/opshop_pickup_service.py`: Regular task ensuring, Oncall task creation, task edit/cancel/restore, and Regular/Oncall assignment apply.
- `backend/services/manual_dispatch/opshop_template_service.py`: Regular and Oncall template list/create/update/soft-disable behavior.
- `backend/services/manual_dispatch/final_summary_service.py`: Final Summary validation and separate Delivery/OP SHOP snapshot preparation.
- `backend/services/manual_dispatch/final_summary_lock.py`: Shared saved-summary hard-lock check used by assignment and OP SHOP apply flows.
- `backend/services/manual_dispatch/validation.py`: Shared existence and contract validation.
- `backend/services/manual_dispatch/normalization.py`: Shared normalization helpers.

### Exports and Persistence

- `backend/services/final_summary_excel_export_service.py`: Saved Final Trip Summary XLSX export, with Delivery tables and a separate OP SHOP PICKUPS section.
- `backend/services/opshop_pickup_excel_export_service.py`: Independent OP SHOP Run Sheet XLSX export.
- `backend/services/excel_export_service.py`: Existing Delivery-oriented active-assignment export behavior.
- `backend/repositories/sqlite_manual_dispatch_repository.py`: SQLite persistence, schema/bootstrap migration behavior, and transactional snapshot writes.
- `backend/repositories/in_memory_manual_dispatch_repository.py`: In-memory persistence implementation for service tests.
- `backend/db/schema.sql`: Current database table definitions, including OP SHOP and Final Summary OP SHOP snapshot tables.

## Data Separation

| Concern | Persistence |
| --- | --- |
| Delivery Order task data | Existing manual order tables. |
| OP SHOP location/source data | `opshop_locations`, `opshop_pickup_schedules`. |
| Actual OP SHOP pickup tasks | `opshop_pickup_tasks`. |
| Manual assignment | `manual_dispatch_assignments` using `task_type + task_id`. |
| Saved Delivery Final Summary rows | `final_trip_summary_rows`. |
| Saved OP SHOP Final Summary rows | `final_trip_summary_opshop_pickup_rows`. |

`final_trip_summary_rows` remains Delivery-only. OP SHOP pickup snapshots are independent and must not be folded into Delivery trip rows or totals.

## Frontend

### Entry, API, and State

- `frontend/app.js`: Browser entry point and orchestration layer; wires action modules to render modules.
- `frontend/js/api/manual-dispatch-api.js`: Centralized API requests.
- `frontend/js/state/app-state.js`: Shared browser state.
- `frontend/js/state/board-state-sync.js`: Board response normalization and state synchronization, including OP SHOP fields and saved-summary hard-lock state.
- `frontend/js/state/selectors.js`: Derived read-only selectors for task visibility, totals, final-summary state, and OP SHOP display filtering.
- `frontend/js/utils/download-utils.js`: Shared browser XLSX response download behavior.
- `frontend/js/utils/date-utils.js`, `format-utils.js`, `dom-utils.js`: Small shared formatting and DOM helpers.

### Delivery and Summary UI

- `frontend/js/render/task-pool-renderer.js`: Task Pool, Delivery Order cards, and OP SHOP entry cards.
- `frontend/js/render/trip-summary-renderer.js`: Driver Summary Delivery trips, separate OP SHOP PICKUPS section, vehicle controls, and final-summary lock presentation.
- `frontend/js/render/final-summary-renderer.js`: Generated and saved Final Summary rendering with independent OP SHOP snapshot section.
- `frontend/js/render/order-modal-renderer.js`: Delivery Order create/detail/edit UI.
- `frontend/js/actions/assignment-actions.js`: Delivery/OP SHOP generic assignment interactions exposed by card workflows.
- `frontend/js/actions/vehicle-actions.js`: Vehicle selection actions.
- `frontend/js/actions/final-summary-actions.js`: Generate, save, history, and Final Summary export orchestration.

### OP SHOP UI

- `frontend/js/render/opshop-pickup-list-modal-renderer.js`: Regular OP SHOP pickup list modal.
- `frontend/js/render/opshop-oncall-pickup-list-modal-renderer.js`: Oncall OP SHOP pickup list modal.
- `frontend/js/render/opshop-pickup-modal-renderer.js`: Read-only OP SHOP pickup details.
- `frontend/js/render/opshop-template-management-modal-renderer.js`: Regular/Oncall template manager.
- `frontend/js/actions/opshop-pickup-actions.js`: Regular list lifecycle, assignment apply, CRUD, and Run Sheet export.
- `frontend/js/actions/opshop-oncall-pickup-actions.js`: Oncall list lifecycle, request-driven creation, and assignment apply.
- `frontend/js/actions/opshop-template-actions.js`: Template CRUD/disable coordination.

## Import Tools

- `tools/import_regular_opshop_pickups_to_db.py`: Imports Regular source workbooks into location and schedule tables; does not directly create pickup tasks.
- `tools/import_oncall_opshop_pickups_to_db.py`: Imports Oncall source workbooks into location and ON_CALL schedule/template tables; does not directly create pickup tasks.

The importer and UI template management can coexist only under a clear office source-of-truth policy; importer execution is not an automatic backup of UI changes.

## Tests

- `tests/test_manual_dispatch_api_contract.py`: Public route characterization.
- `tests/test_manual_dispatch_frontend_static_contract.py`: Frontend module and interaction-contract guards.
- `tests/test_manual_dispatch_final_summary.py` and `tests/test_manual_dispatch_final_summary_export.py`: Separate snapshot sections, totals, history, export, and lock behavior.
- `tests/test_manual_dispatch_opshop_*.py`: OP SHOP foundation, generation, payload, assignment, list management, Run Sheet export, and template management.
- `tests/test_import_*opshop*_to_db.py`: Regular, Oncall, and source import behavior.

## Validation Commands

```powershell
git diff --check
git diff --cached --check
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend tests tools
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

Browser smoke remains local/manual when it requires runtime SQLite data or office-only workbook inputs.
