from collections.abc import Callable
from fastapi import (
    APIRouter,
    Request,
)
from fastapi.responses import Response
from backend.services.manual_dispatch_service import ManualDispatchService
from .common import (
    final_summary_export_filename,
    safe_filename_part,
    to_http_exception,
    with_logbook_actor,
)


def create_export_router(
    get_service: Callable[[], ManualDispatchService],
    get_dependency: Callable[[str], Callable],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.get("/export-excel")
    def export_excel(dispatch_date: str):
        service = get_service()
        workbook_bytes = get_dependency("build_manual_dispatch_excel")(
            service.get_board(dispatch_date),
            dispatch_date,
        )
        filename = f"manual-dispatch-{dispatch_date}.xlsx"
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/opshop-pickups/export-excel")
    def export_opshop_pickups_excel(dispatch_date: str):
        service = get_service()
        workbook_bytes = get_dependency("build_opshop_pickup_run_sheet_excel")(
            service.get_board(dispatch_date),
            dispatch_date,
        )
        filename = f"opshop-pickup-run-sheet-{dispatch_date}.xlsx"
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/delivery/run-sheets/export-excel")
    def export_delivery_run_sheets_excel(
        delivery_date: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            run_sheets = service.list_delivery_run_sheets_for_date_export(delivery_date)
            workbook_bytes = get_dependency("build_delivery_run_sheets_excel")(run_sheets, delivery_date)
        except ValueError as error:
            raise to_http_exception(error) from error

        filename = f"Daily_Run_Sheets_{safe_filename_part(delivery_date)}.xlsx"
        with_logbook_actor(
            service,
            http_request,
            lambda: service.record_delivery_run_sheets_daily_export(
                run_sheets,
                delivery_date,
                filename,
            ),
        )
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/delivery/run-sheets/{run_sheet_id}/export-excel")
    def export_delivery_run_sheet_excel(
        run_sheet_id: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            run_sheet = service.get_saved_delivery_run_sheet_for_export(run_sheet_id)
        except ValueError as error:
            raise to_http_exception(error) from error

        workbook_bytes = get_dependency("build_delivery_run_sheet_excel")(run_sheet)
        filename = (
            f"Delivery_Run_Sheet_{safe_filename_part(run_sheet.delivery_date)}_"
            f"{safe_filename_part(run_sheet.driver_name_snapshot)}.xlsx"
        )
        with_logbook_actor(
            service,
            http_request,
            lambda: service.record_delivery_run_sheet_export(run_sheet, filename),
        )
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/opshop/pickup-collections/export-excel")
    def export_opshop_pickup_collections_excel(
        pickup_date: str,
        dispatch_date: str = None,
        status: str = None,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            collections = service.list_opshop_pickup_collections_for_date_export(
                pickup_date,
                dispatch_date,
                status,
            )
            workbook_bytes = get_dependency("build_opshop_pickup_collections_excel")(
                collections,
                pickup_date,
            )
        except ValueError as error:
            raise to_http_exception(error) from error

        filename = f"Daily_OPSHOP_Collections_{safe_filename_part(pickup_date)}.xlsx"
        with_logbook_actor(
            service,
            http_request,
            lambda: service.record_opshop_pickup_collections_daily_export(
                collections,
                pickup_date,
                filename,
                status=status,
            ),
        )
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/opshop/pickup-collections/{collection_id}/export-excel")
    def export_opshop_pickup_collection_excel(
        collection_id: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            collection = service.get_opshop_pickup_collection_for_export(
                collection_id
            )
        except ValueError as error:
            raise to_http_exception(error) from error

        workbook_bytes = get_dependency("build_opshop_pickup_collection_excel")(collection)
        filename = (
            f"OPSHOP_Pickup_Collection_{safe_filename_part(collection.pickup_date)}_"
            f"{safe_filename_part(collection.driver_name_snapshot)}.xlsx"
        )
        with_logbook_actor(
            service,
            http_request,
            lambda: service.record_opshop_pickup_collection_export(
                collection,
                filename,
            ),
        )
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/final-summaries/export-excel")
    def export_final_trip_summaries_excel(dispatch_date: str, delivery_date: str = None):
        service = get_service()
        try:
            summaries = service.list_final_trip_summaries(dispatch_date, delivery_date)
        except ValueError as error:
            raise to_http_exception(error) from error

        workbook_bytes = get_dependency("build_final_summary_excel")(summaries, dispatch_date, delivery_date)
        filename = f"final-trip-summary-{dispatch_date}.xlsx"
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/final-summaries/{summary_id}/export-excel")
    def export_saved_final_trip_summary_excel(summary_id: str):
        service = get_service()
        try:
            summary = service.get_saved_final_trip_summary_for_export(summary_id)
        except ValueError as error:
            raise to_http_exception(error) from error

        workbook_bytes = get_dependency("build_final_summary_excel")(
            [summary],
            summary.dispatch_date,
            summary.delivery_date,
        )
        filename = final_summary_export_filename(summary)
        return Response(
            content=workbook_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
