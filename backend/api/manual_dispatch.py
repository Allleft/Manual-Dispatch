import os

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from backend.schemas import (
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateDriverRequest,
    CreateOrderRequest,
    CreateOpShopPickupTaskRequest,
    CreateVehicleRequest,
    EnsureOpShopPickupTasksRequest,
    LoginOperatorAccountRequest,
    RegisterOperatorAccountRequest,
    ResetOperatorPasswordRequest,
    SaveFinalTripSummaryRequest,
    UnassignTaskRequest,
    UpdateDriverRequest,
    UpdateOpShopPickupTaskRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
    to_dict,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.excel_export_service import build_manual_dispatch_excel
from backend.services.final_summary_excel_export_service import build_final_summary_excel
from backend.services.manual_dispatch_service import ManualDispatchService

router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = ManualDispatchService(SQLiteManualDispatchRepository())
ALLOW_REGISTRATION_ENV = "MANUAL_DISPATCH_ALLOW_REGISTRATION"
REGISTRATION_DISABLED_MESSAGE = "Registration is disabled. Please contact an administrator."


@router.get("/board")
def get_board(dispatch_date: str):
    return to_dict(service.get_board(dispatch_date))


@router.get("/specifications")
def get_specifications():
    return to_dict(service.get_specifications())


@router.get("/export-excel")
def export_excel(dispatch_date: str):
    workbook_bytes = build_manual_dispatch_excel(
        service.get_board(dispatch_date),
        dispatch_date,
    )
    filename = f"manual-dispatch-{dispatch_date}.xlsx"
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/auth/register")
def register_operator_account(request: RegisterOperatorAccountRequest):
    if not _is_env_flag_enabled(ALLOW_REGISTRATION_ENV, default=True):
        raise HTTPException(status_code=403, detail=REGISTRATION_DISABLED_MESSAGE)

    try:
        return to_dict(service.register_operator_account(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/auth/login")
def login_operator_account(request: LoginOperatorAccountRequest):
    try:
        return to_dict(service.login_operator_account(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/auth/reset-password")
def reset_operator_password(request: ResetOperatorPasswordRequest):
    try:
        return to_dict(service.reset_operator_password(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/assign")
def assign_task(request: AssignTaskRequest):
    try:
        return to_dict(service.assign_task(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/unassign")
def unassign_task(request: UnassignTaskRequest):
    try:
        return to_dict(service.unassign_task(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/driver-vehicle")
def assign_driver_vehicle(payload: dict = Body(...)):
    request = _assign_driver_vehicle_request_from_payload(payload)
    try:
        return to_dict(service.assign_vehicle_to_driver(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/orders")
def create_order(request: CreateOrderRequest):
    try:
        return to_dict(service.create_order(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/orders/{order_id}")
def update_order(order_id: str, request: UpdateOrderRequest):
    try:
        return to_dict(service.update_order(order_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    try:
        return to_dict(service.cancel_order(order_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups/generate")
def generate_opshop_pickups(request: EnsureOpShopPickupTasksRequest):
    try:
        return to_dict(service.ensure_opshop_pickup_tasks_for_window(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop-pickup-schedules")
def list_opshop_pickup_schedules(run_type: str = "scheduled"):
    try:
        return [
            to_dict(candidate)
            for candidate in service.list_opshop_pickup_schedule_candidates(run_type)
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups")
def create_opshop_pickup(request: CreateOpShopPickupTaskRequest):
    try:
        return to_dict(service.create_opshop_pickup_task(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups/oncall")
def create_oncall_opshop_pickup(request: CreateOpShopPickupTaskRequest):
    try:
        return to_dict(service.create_oncall_opshop_pickup_task(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/opshop-pickups/{pickup_task_id}")
def update_opshop_pickup(pickup_task_id: str, request: UpdateOpShopPickupTaskRequest):
    try:
        return to_dict(service.update_opshop_pickup_task(pickup_task_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.delete("/opshop-pickups/{pickup_task_id}")
def delete_opshop_pickup(pickup_task_id: str):
    try:
        return to_dict(service.delete_opshop_pickup_task(pickup_task_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups/weekly-assignments/apply")
def apply_weekly_opshop_pickup_assignments(request: ApplyWeeklyOpShopPickupAssignmentsRequest):
    try:
        return to_dict(service.apply_weekly_opshop_pickup_assignments(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups/oncall-assignments/apply")
def apply_oncall_opshop_pickup_assignments(request: ApplyOncallOpShopPickupAssignmentsRequest):
    try:
        return to_dict(service.apply_oncall_opshop_pickup_assignments(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/drivers")
def create_driver(request: CreateDriverRequest):
    try:
        return to_dict(service.create_driver(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/drivers/{driver_id}")
def update_driver(driver_id: str, request: UpdateDriverRequest):
    try:
        return to_dict(service.update_driver(driver_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.delete("/drivers/{driver_id}")
def delete_driver(driver_id: str):
    try:
        return to_dict(service.delete_driver(driver_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/vehicles")
def create_vehicle(request: CreateVehicleRequest):
    try:
        return to_dict(service.create_vehicle(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: str, request: UpdateVehicleRequest):
    try:
        return to_dict(service.update_vehicle(vehicle_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str):
    try:
        return to_dict(service.delete_vehicle(vehicle_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/final-summaries")
def save_final_trip_summary(payload: dict = Body(...)):
    request = _save_final_trip_summary_request_from_payload(payload)
    try:
        return to_dict(service.save_final_trip_summary(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/final-summaries")
def list_final_trip_summaries(dispatch_date: str, delivery_date: str = None):
    try:
        return [
            to_dict(summary)
            for summary in service.list_final_trip_summaries(
                dispatch_date,
                delivery_date,
            )
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/final-summaries/export-excel")
def export_final_trip_summaries_excel(dispatch_date: str, delivery_date: str = None):
    try:
        summaries = service.list_final_trip_summaries(dispatch_date, delivery_date)
    except ValueError as error:
        raise _to_http_exception(error) from error

    workbook_bytes = build_final_summary_excel(summaries, dispatch_date, delivery_date)
    filename = f"final-trip-summary-{dispatch_date}.xlsx"
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/final-summary-dates")
def list_final_summary_dates():
    return service.list_final_summary_dates()


@router.get("/final-summaries/{summary_id}")
def get_final_trip_summary(summary_id: str):
    try:
        return to_dict(service.get_final_trip_summary(summary_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


def _assign_driver_vehicle_request_from_payload(payload):
    payload = payload or {}
    return AssignDriverVehicleRequest(
        dispatch_date=payload.get("dispatch_date"),
        delivery_date=payload.get("delivery_date"),
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id") or None,
    )


def _save_final_trip_summary_request_from_payload(payload):
    payload = payload or {}
    return SaveFinalTripSummaryRequest(
        dispatch_date=payload.get("dispatch_date"),
        delivery_date=payload.get("delivery_date"),
        driver_id=payload.get("driver_id"),
        driver_name_snapshot=payload.get("driver_name_snapshot")
        or payload.get("driver_name"),
        vehicle_id=payload.get("vehicle_id") or None,
        vehicle_rego_snapshot=payload.get("vehicle_rego_snapshot")
        or payload.get("vehicle_rego"),
        total_pallets=payload.get("total_pallets") or 0,
        total_loose_bags=payload.get("total_loose_bags") or 0,
        generated_at=payload.get("generated_at"),
        trips=payload.get("trips") or [],
        saved_by_account_name=payload.get("saved_by_account_name"),
        saved_by_account_id=payload.get("saved_by_account_id"),
    )


def _to_http_exception(error):
    message = str(error)
    status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)


def _is_env_flag_enabled(name, default=False):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
