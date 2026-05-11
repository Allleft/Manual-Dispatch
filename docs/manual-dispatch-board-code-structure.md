# Manual Dispatch Board Code Structure

This note maps the current implementation after the structure cleanup. It is intended for developers reviewing or extending the manual dispatch workflow.

Active refactor branch: `refactor/manual-dispatch-structure`.

## Backend

- `backend/main.py`: FastAPI application entry point. It includes the Manual Dispatch router and serves the static frontend.
- `backend/api/manual_dispatch.py`: Public HTTP route layer for `/api/manual-dispatch`. Route paths and response fields are kept stable for the frontend.
- `backend/services/manual_dispatch_service.py`: Stable service facade used by API routes and tests. It delegates to domain services while preserving the public service methods.
- `backend/services/manual_dispatch/auth_service.py`: Operator account registration, login, password hashing, and reset-password logic.
- `backend/services/manual_dispatch/board_service.py`: Board and specification list response assembly.
- `backend/services/manual_dispatch/assignment_service.py`: Assign, unassign, driver-date vehicle selection, and vehicle clearing behavior.
- `backend/services/manual_dispatch/order_service.py`: Create, update, and cancel order lifecycle behavior.
- `backend/services/manual_dispatch/specification_service.py`: Driver and Vehicle add/edit/delete/availability behavior.
- `backend/services/manual_dispatch/final_summary_service.py`: Saved Final Trip Summary validation, snapshot row normalization, history loading, and duplicate checks.
- `backend/services/manual_dispatch/validation.py`: Shared task, driver, vehicle, trip, availability, and saved-by account validation.
- `backend/services/manual_dispatch/normalization.py`: Shared text, boolean, and quantity normalization helpers.
- `backend/services/manual_dispatch/id_generation.py`: Order, Driver, and Vehicle ID generation helpers.
- `backend/services/excel_export_service.py`: Legacy active-assignment Excel export builder kept for backend compatibility.
- `backend/services/final_summary_excel_export_service.py`: Saved Final Trip Summary snapshot Excel export builder.
- `backend/repositories/sqlite_manual_dispatch_repository.py`: SQLite persistence, migrations, row mapping, and transactional final summary save behavior.
- `backend/repositories/in_memory_manual_dispatch_repository.py`: In-memory repository used by service-level tests.
- `backend/schemas.py`: Dataclass request, response, and persistence transfer objects.

## Frontend

- `frontend/index.html`: Static DOM shell for the board, modal roots, login root, and Final Trip Summary controls.
- `frontend/app.js`: Main browser entry point. It owns application state, render functions, and user actions.
- `frontend/js/api/manual-dispatch-api.js`: Fetch wrapper and Manual Dispatch API client functions.
- `frontend/js/utils/date-utils.js`: Browser-local date formatting helper used for the default Dispatch Date.
- `frontend/styles.css`: Board, modal, and Final Trip Summary styling.

## Tests

- `tests/test_manual_dispatch_api_contract.py`: Characterization test that keeps public Manual Dispatch API routes stable.
- `tests/test_manual_dispatch_frontend_static_contract.py`: Static contract checks for the frontend module entry point and import paths.
- `tests/test_manual_dispatch_auth.py`: Operator account, login, and reset-password service/API tests.
- `tests/test_manual_dispatch_final_summary.py`: Final Trip Summary persistence, duplicate, transactional, and finalized-order behavior.
- `tests/test_manual_dispatch_final_summary_export.py`: Saved Final Trip Summary Excel export behavior.
- Other `tests/test_manual_dispatch_*.py` files cover order lifecycle, vehicle selection, Excel compatibility export, and service/repository basics.

## Validation Commands

```powershell
python -m compileall backend tests
python -m unittest discover -s tests -v
node --check frontend/app.js
node --check frontend/js/api/manual-dispatch-api.js
node --check frontend/js/utils/date-utils.js
git diff --check
```

If the local `python` command is unavailable, run the same commands with the active virtual environment's Python executable.
