from threading import Lock

from fastapi import APIRouter, Depends, Request

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.excel_export_service import build_manual_dispatch_excel
from backend.services.delivery_run_sheet_excel_export_service import (
    build_delivery_run_sheet_excel,
    build_delivery_run_sheets_excel,
)
from backend.services.final_summary_excel_export_service import build_final_summary_excel
from backend.services.opshop_pickup_excel_export_service import (
    build_opshop_pickup_run_sheet_excel,
)
from backend.services.opshop_pickup_collection_excel_export_service import (
    build_opshop_pickup_collection_excel,
    build_opshop_pickup_collections_excel,
)
from backend.services.manual_dispatch_service import ManualDispatchService

from .manual_dispatch_routes.attache_routes import create_attache_router
from .manual_dispatch_routes.auth_routes import create_auth_router
from .manual_dispatch_routes.common import (
    ALLOW_REGISTRATION_ENV,
    OPERATOR_COOKIE_MAX_AGE_SECONDS,
    OPERATOR_COOKIE_NAME,
    OPERATOR_COOKIE_SECRET_ENV,
    REGISTRATION_DISABLED_MESSAGE,
    assign_driver_vehicle_request_from_payload as _assign_driver_vehicle_request_from_payload,
    current_operator_account_name,
    final_summary_export_filename as _final_summary_export_filename,
    is_env_flag_enabled as _is_env_flag_enabled,
    operator_cookie_secret as _operator_cookie_secret,
    operator_cookie_signature as _operator_cookie_signature,
    require_authenticated_operator,
    reject_scoped_fields as _reject_scoped_fields,
    safe_filename_part as _safe_filename_part,
    save_final_trip_summary_request_from_payload as _save_final_trip_summary_request_from_payload,
    set_operator_cookie,
    to_http_exception as _to_http_exception,
    with_logbook_actor,
)
from .manual_dispatch_routes.delivery_routes import create_delivery_router
from .manual_dispatch_routes.delivery_docket_routes import create_delivery_docket_router
from .manual_dispatch_routes.export_routes import create_export_router
from .manual_dispatch_routes.legacy_routes import create_legacy_router
from .manual_dispatch_routes.opshop_routes import create_opshop_router
from .manual_dispatch_routes.workspace_snapshot_routes import (
    create_workspace_snapshot_router,
)


router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = None
_service_lock = Lock()


def _get_service():
    global service
    if service is None:
        with _service_lock:
            if service is None:
                service = ManualDispatchService(SQLiteManualDispatchRepository())
    return service


def _with_logbook_actor(http_request, callback):
    return with_logbook_actor(_get_service(), http_request, callback)


def _current_operator_account_name(http_request):
    return current_operator_account_name(_get_service(), http_request)


def _set_operator_cookie(response, identity):
    return set_operator_cookie(_get_service(), response, identity)


def _require_authenticated_operator(http_request: Request):
    return require_authenticated_operator(_get_service(), http_request)


def _get_compatibility_dependency(name):
    return globals()[name]


protected_router = APIRouter(
    prefix="/api/manual-dispatch",
    dependencies=[Depends(_require_authenticated_operator)],
)

# Static export paths must precede parameterized snapshot routes.
create_export_router(_get_service, _get_compatibility_dependency, protected_router)
create_auth_router(_get_service, router, _require_authenticated_operator)
for route_factory in (
    create_attache_router,
    create_delivery_docket_router,
    create_delivery_router,
    create_opshop_router,
    create_workspace_snapshot_router,
    create_legacy_router,
):
    route_factory(_get_service, protected_router)
router.routes.extend(protected_router.routes)


# Endpoint names were historically module attributes and remain importable.
for route in router.routes:
    endpoint = getattr(route, "endpoint", None)
    if endpoint is not None:
        globals().setdefault(endpoint.__name__, endpoint)
