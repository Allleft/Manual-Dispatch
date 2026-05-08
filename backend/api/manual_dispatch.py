from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateDriverRequest,
    CreateOrderRequest,
    CreateVehicleRequest,
    SaveFinalTripSummaryRequest,
    UnassignTaskRequest,
    UpdateDriverRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
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
def list_final_trip_summaries(dispatch_date: str):
    try:
        return [to_dict(summary) for summary in service.list_final_trip_summaries(dispatch_date)]
    except ValueError as error:
        raise _to_http_exception(error) from error


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
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id") or None,
    )


def _save_final_trip_summary_request_from_payload(payload):
    payload = payload or {}
    return SaveFinalTripSummaryRequest(
        dispatch_date=payload.get("dispatch_date"),
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
    )


def _to_http_exception(error):
    message = str(error)
    status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)
