from collections.abc import Callable
from fastapi import (
    APIRouter,
    Body,
    Request,
)
from backend.schemas import (
    AssignTaskRequest,
    CreateDriverRequest,
    CreateOrderRequest,
    CreateVehicleRequest,
    UnassignTaskRequest,
    UpdateDriverRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from .common import (
    assign_driver_vehicle_request_from_payload,
    save_final_trip_summary_request_from_payload,
    to_http_exception,
    with_logbook_actor,
)


def create_legacy_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.get("/board")
    def get_board(dispatch_date: str):
        service = get_service()
        return to_dict(service.get_board(dispatch_date))

    @router.get("/specifications")
    def get_specifications():
        service = get_service()
        return to_dict(service.get_specifications())

    @router.post("/assign")
    def assign_task(request: AssignTaskRequest, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.assign_task(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/unassign")
    def unassign_task(request: UnassignTaskRequest, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.unassign_task(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/driver-vehicle")
    def assign_driver_vehicle(http_request: Request = None, payload: dict = Body(...)):
        service = get_service()
        request = assign_driver_vehicle_request_from_payload(payload)
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.assign_vehicle_to_driver(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/orders")
    def create_order(request: CreateOrderRequest, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_order(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/orders/{order_id}")
    def update_order(order_id: str, request: UpdateOrderRequest, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.update_order(order_id, request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/orders/{order_id}/cancel")
    def cancel_order(order_id: str, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.cancel_order(order_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/drivers")
    def create_driver(request: CreateDriverRequest):
        service = get_service()
        try:
            return to_dict(service.create_driver(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/drivers/{driver_id}")
    def update_driver(driver_id: str, request: UpdateDriverRequest):
        service = get_service()
        try:
            return to_dict(service.update_driver(driver_id, request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.delete("/drivers/{driver_id}")
    def delete_driver(driver_id: str):
        service = get_service()
        try:
            return to_dict(service.delete_driver(driver_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/vehicles")
    def create_vehicle(request: CreateVehicleRequest):
        service = get_service()
        try:
            return to_dict(service.create_vehicle(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/vehicles/{vehicle_id}")
    def update_vehicle(vehicle_id: str, request: UpdateVehicleRequest):
        service = get_service()
        try:
            return to_dict(service.update_vehicle(vehicle_id, request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.delete("/vehicles/{vehicle_id}")
    def delete_vehicle(vehicle_id: str):
        service = get_service()
        try:
            return to_dict(service.delete_vehicle(vehicle_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/final-summaries")
    def save_final_trip_summary(payload: dict = Body(...)):
        service = get_service()
        request = save_final_trip_summary_request_from_payload(payload)
        try:
            return to_dict(service.save_final_trip_summary(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/final-summaries/generated")
    def create_generated_final_trip_summary(payload: dict = Body(...)):
        service = get_service()
        request = save_final_trip_summary_request_from_payload(payload)
        try:
            return to_dict(service.create_generated_final_trip_summary(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/final-summaries")
    def list_final_trip_summaries(dispatch_date: str, delivery_date: str = None):
        service = get_service()
        try:
            return [
                to_dict(summary)
                for summary in service.list_final_trip_summaries(
                    dispatch_date,
                    delivery_date,
                )
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/final-summary-dates")
    def list_final_summary_dates():
        service = get_service()
        return service.list_final_summary_dates()

    @router.post("/final-summaries/{summary_id}/save")
    def save_generated_final_trip_summary(summary_id: str, payload: dict = Body(...)):
        service = get_service()
        payload = payload or {}
        try:
            return to_dict(
                service.save_generated_final_trip_summary(
                    summary_id,
                    payload.get("saved_by_account_name"),
                    payload.get("saved_by_account_id"),
                )
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/final-summaries/{summary_id}/cancel-generated")
    def cancel_generated_final_trip_summary(summary_id: str):
        service = get_service()
        try:
            return {"cancelled": service.cancel_generated_final_trip_summary(summary_id)}
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/final-summaries/{summary_id}")
    def get_final_trip_summary(summary_id: str):
        service = get_service()
        try:
            return to_dict(service.get_final_trip_summary(summary_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    return router
