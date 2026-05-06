from fastapi import APIRouter, HTTPException

from backend.schemas import (
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    UnassignTaskRequest,
    to_dict,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch_service import ManualDispatchService

router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = ManualDispatchService(SQLiteManualDispatchRepository())


@router.get("/board")
def get_board(dispatch_date: str):
    return to_dict(service.get_board(dispatch_date))


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
def assign_driver_vehicle(request: AssignDriverVehicleRequest):
    try:
        return to_dict(service.assign_vehicle_to_driver(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


def _to_http_exception(error):
    message = str(error)
    status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)
