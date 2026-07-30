from collections.abc import Callable
from fastapi import (
    APIRouter,
    Body,
    Request,
)
from backend.schemas import (
    CloseDeliveryRunSheetRequest,
    CloseDeliveryRunSheetRowRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
    UpdateOpShopPickupCollectionRowsRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from .common import (
    authenticated_operator_from_request,
    to_http_exception,
    with_logbook_actor,
)


def create_workspace_snapshot_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.get("/workspace-migration-status")
    def get_workspace_migration_status():
        service = get_service()
        return service.get_workspace_migration_status()

    @router.post("/delivery/run-sheets/generated")
    def create_generated_delivery_run_sheet(
        request: GenerateDeliveryRunSheetRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_generated_delivery_run_sheet(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/delivery/run-sheets")
    def list_delivery_run_sheets(
        dispatch_date: str = None,
        delivery_date: str = None,
        status: str = None,
    ):
        service = get_service()
        try:
            return [
                to_dict(run_sheet)
                for run_sheet in service.list_delivery_run_sheets(
                    dispatch_date,
                    delivery_date,
                    status,
                )
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/delivery/run-sheets/{run_sheet_id}")
    def get_delivery_run_sheet(run_sheet_id: str):
        service = get_service()
        try:
            return to_dict(service.get_delivery_run_sheet(run_sheet_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/run-sheets/{run_sheet_id}/save")
    def save_generated_delivery_run_sheet(
        run_sheet_id: str,
        request: SaveGeneratedWorkspaceSnapshotRequest,
        http_request: Request = None,
    ):
        service = get_service()
        identity = authenticated_operator_from_request(http_request)
        request = SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=identity.account_name,
            saved_by_account_id=identity.account_id,
        )
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.save_generated_delivery_run_sheet(run_sheet_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/run-sheets/{run_sheet_id}/cancel-generated")
    def cancel_generated_delivery_run_sheet(run_sheet_id: str, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: {
                    "cancelled": service.cancel_generated_delivery_run_sheet(run_sheet_id)
                },
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/delivery/run-sheets/{run_sheet_id}/closeout")
    def close_saved_delivery_run_sheet(
        run_sheet_id: str,
        payload: object = Body(None),
        http_request: Request = None,
    ):
        service = get_service()
        identity = authenticated_operator_from_request(http_request)
        try:
            if not isinstance(payload, dict):
                raise ValueError("Closeout request body must be an object.")
            if set(payload) != {"rows"}:
                raise ValueError("Closeout request accepts only rows.")
            raw_rows = payload.get("rows")
            if not isinstance(raw_rows, list):
                raise ValueError("rows must be a list.")
            allowed_row_fields = {
                "run_sheet_row_id",
                "outcome",
                "reason_code",
                "note",
                "next_delivery_date",
            }
            rows = []
            for raw_row in raw_rows:
                if not isinstance(raw_row, dict):
                    raise ValueError(
                        "Each closeout row must be an object."
                    )
                if not set(raw_row).issubset(allowed_row_fields):
                    raise ValueError(
                        "Closeout rows accept only outcome fields."
                    )
                rows.append(
                    CloseDeliveryRunSheetRowRequest(
                        run_sheet_row_id=raw_row.get("run_sheet_row_id"),
                        outcome=raw_row.get("outcome"),
                        reason_code=raw_row.get("reason_code"),
                        note=raw_row.get("note"),
                        next_delivery_date=raw_row.get("next_delivery_date"),
                    )
                )
            request = CloseDeliveryRunSheetRequest(rows=rows)
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.close_saved_delivery_run_sheet(
                        run_sheet_id,
                        request,
                        identity,
                    )
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/pickup-collections/generated")
    def create_generated_opshop_pickup_collection(
        request: GenerateOpShopPickupCollectionRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_generated_opshop_pickup_collection(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop/pickup-collections")
    def list_opshop_pickup_collections(
        dispatch_date: str = None,
        pickup_date: str = None,
        status: str = None,
    ):
        service = get_service()
        try:
            return [
                to_dict(collection)
                for collection in service.list_opshop_pickup_collections(
                    dispatch_date,
                    pickup_date,
                    status,
                )
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop/pickup-collections/{collection_id}")
    def get_opshop_pickup_collection(collection_id: str):
        service = get_service()
        try:
            return to_dict(service.get_opshop_pickup_collection(collection_id))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/opshop/pickup-collections/{collection_id}/rows")
    def update_opshop_pickup_collection_rows(
        collection_id: str,
        request: UpdateOpShopPickupCollectionRowsRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.update_opshop_pickup_collection_rows(
                        collection_id,
                        request,
                    )
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/pickup-collections/{collection_id}/save")
    def save_generated_opshop_pickup_collection(
        collection_id: str,
        request: SaveGeneratedWorkspaceSnapshotRequest,
        http_request: Request = None,
    ):
        service = get_service()
        identity = authenticated_operator_from_request(http_request)
        request = SaveGeneratedWorkspaceSnapshotRequest(
            saved_by_account_name=identity.account_name,
            saved_by_account_id=identity.account_id,
        )
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.save_generated_opshop_pickup_collection(collection_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/pickup-collections/{collection_id}/cancel-generated")
    def cancel_generated_opshop_pickup_collection(
        collection_id: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: {
                    "cancelled": service.cancel_generated_opshop_pickup_collection(
                        collection_id
                    )
                },
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    return router
