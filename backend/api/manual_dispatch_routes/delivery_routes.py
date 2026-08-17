from collections.abc import Callable
from fastapi import (
    APIRouter,
    Body,
    Request,
)
from backend.schemas import (
    CreateDriverRequest,
    CreateOrderRequest,
    CreateVehicleRequest,
    DeliveryAreaClassificationRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    DeliveryWorkspaceVehicleClearRequest,
    UpdateDriverRequest,
    UpdateDeliveryOrderAreaRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.manual_dispatch.normalization import clean_optional_iso_date
from .common import (
    reject_scoped_fields,
    to_http_exception,
    with_logbook_actor,
)


def create_delivery_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.get("/delivery/board")
    def get_delivery_workspace_board(dispatch_date: str):
        service = get_service()
        try:
            return to_dict(service.get_delivery_workspace_board(dispatch_date))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/delivery/trip-summary")
    def get_delivery_trip_summary_board(delivery_date: str, dispatch_date: str = None):
        service = get_service()
        try:
            # dispatch_date remains an optional legacy query parameter only.
            clean_optional_iso_date(dispatch_date, "dispatch_date")
            return to_dict(service.get_delivery_trip_summary_board(delivery_date))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/shared/specifications")
    def get_shared_specifications():
        service = get_service()
        return to_dict(service.get_shared_specifications())

    @router.get("/delivery/specifications")
    def get_delivery_specifications():
        service = get_service()
        return to_dict(service.get_delivery_specifications())

    @router.post("/delivery/area-classification")
    def classify_delivery_area(request: DeliveryAreaClassificationRequest):
        service = get_service()
        try:
            classification = service.classify_delivery_area(request)
            return {
                "normalized_suburb": classification.normalized_suburb,
                "postcode": classification.postcode,
                "auto_delivery_region": classification.region,
                "auto_delivery_area": classification.auto_delivery_area,
                "delivery_area_override": None,
                "delivery_area": classification.auto_delivery_area,
                "delivery_area_source": "AUTO",
                "known": classification.known,
            }
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/drivers")
    def create_delivery_driver(request: CreateDriverRequest):
        service = get_service()
        try:
            return to_dict(service.create_delivery_driver(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/delivery/drivers/{driver_id}")
    def update_delivery_driver(driver_id: str, request: UpdateDriverRequest):
        service = get_service()
        try:
            return to_dict(service.update_delivery_driver(driver_id, request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.delete("/delivery/drivers/{driver_id}")
    def delete_delivery_driver(driver_id: str):
        service = get_service()
        try:
            return to_dict(service.delete_delivery_driver(driver_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/vehicles")
    def create_delivery_vehicle(request: CreateVehicleRequest):
        service = get_service()
        try:
            return to_dict(service.create_delivery_vehicle(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/delivery/vehicles/{vehicle_id}")
    def update_delivery_vehicle(vehicle_id: str, request: UpdateVehicleRequest):
        service = get_service()
        try:
            return to_dict(service.update_delivery_vehicle(vehicle_id, request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.delete("/delivery/vehicles/{vehicle_id}")
    def delete_delivery_vehicle(vehicle_id: str):
        service = get_service()
        try:
            return to_dict(service.delete_delivery_vehicle(vehicle_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/orders")
    def create_delivery_order(request: CreateOrderRequest, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_delivery_order(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/delivery/orders/{order_id}")
    def update_delivery_order(
        order_id: str,
        request: UpdateOrderRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.update_delivery_order(order_id, request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/orders/{order_id}/cancel")
    def cancel_delivery_order(order_id: str, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.cancel_delivery_order(order_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/delivery/orders/{order_id}/delivery-area")
    def update_delivery_order_area(
        order_id: str,
        request: UpdateDeliveryOrderAreaRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.update_delivery_order_area(order_id, request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/assignments")
    def assign_delivery_workspace_order(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type"})
            request = DeliveryWorkspaceAssignOrderRequest(
                dispatch_date=payload.get("dispatch_date"),
                order_id=payload.get("order_id"),
                driver_id=payload.get("driver_id"),
                trip_no=payload.get("trip_no"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.assign_delivery_workspace_order(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/assignments/unassign")
    def unassign_delivery_workspace_order(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type"})
            request = DeliveryWorkspaceUnassignOrderRequest(
                dispatch_date=payload.get("dispatch_date"),
                order_id=payload.get("order_id"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.unassign_delivery_workspace_order(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/vehicle-assignments")
    def assign_delivery_workspace_vehicle(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type"})
            request = DeliveryWorkspaceVehicleAssignmentRequest(
                dispatch_date=payload.get("dispatch_date"),
                delivery_date=payload.get("delivery_date"),
                driver_id=payload.get("driver_id"),
                vehicle_id=payload.get("vehicle_id"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.assign_delivery_workspace_vehicle(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/vehicle-assignments/clear")
    def clear_delivery_workspace_vehicle(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type"})
            request = DeliveryWorkspaceVehicleClearRequest(
                dispatch_date=payload.get("dispatch_date"),
                delivery_date=payload.get("delivery_date"),
                driver_id=payload.get("driver_id"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.clear_delivery_workspace_vehicle(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    return router
