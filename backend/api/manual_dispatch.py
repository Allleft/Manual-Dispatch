from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateOrderRequest,
    UnassignTaskRequest,
    UpdateOrderRequest,
    to_dict,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.excel_export_service import build_manual_dispatch_excel
from backend.services.manual_dispatch_service import ManualDispatchService

router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = ManualDispatchService(SQLiteManualDispatchRepository())


@router.get("/board")
def get_board(dispatch_date: str):
    return to_dict(service.get_board(dispatch_date))


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


def _assign_driver_vehicle_request_from_payload(payload):
    payload = payload or {}
    return AssignDriverVehicleRequest(
        dispatch_date=payload.get("dispatch_date"),
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id") or None,
    )


def _to_http_exception(error):
    message = str(error)
    status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)
