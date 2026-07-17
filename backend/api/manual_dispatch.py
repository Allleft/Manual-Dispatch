from fastapi import APIRouter

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
    reject_scoped_fields as _reject_scoped_fields,
    safe_filename_part as _safe_filename_part,
    save_final_trip_summary_request_from_payload as _save_final_trip_summary_request_from_payload,
    set_operator_cookie,
    to_http_exception as _to_http_exception,
    with_logbook_actor,
)
from .manual_dispatch_routes.delivery_routes import create_delivery_router
from .manual_dispatch_routes.export_routes import create_export_router
from .manual_dispatch_routes.legacy_routes import create_legacy_router
from .manual_dispatch_routes.opshop_routes import create_opshop_router
from .manual_dispatch_routes.workspace_snapshot_routes import (
    create_workspace_snapshot_router,
)


router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = ManualDispatchService(SQLiteManualDispatchRepository())


def _get_service():
    return service


def _with_logbook_actor(http_request, callback):
    return with_logbook_actor(service, http_request, callback)


def _current_operator_account_name(http_request):
    return current_operator_account_name(service, http_request)


def _set_operator_cookie(response, identity):
    return set_operator_cookie(service, response, identity)


def _get_compatibility_dependency(name):
    return globals()[name]


# Static export paths must precede parameterized snapshot routes.
create_export_router(_get_service, _get_compatibility_dependency, router)
for route_factory in (
    create_auth_router,
    create_attache_router,
    create_delivery_router,
    create_opshop_router,
    create_workspace_snapshot_router,
    create_legacy_router,
):
    route_factory(_get_service, router)


# Endpoint names were historically module attributes and remain importable.
for route in router.routes:
    globals().setdefault(route.endpoint.__name__, route.endpoint)
