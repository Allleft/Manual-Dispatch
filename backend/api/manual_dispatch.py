import os
from hashlib import sha1
from typing import List

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.schemas import (
    AddCountrysideRouteMembershipRequest,
    ApplyCountrysideOpShopPickupAssignmentsRequest,
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignCountrysideRouteGroupRequest,
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    AttacheInvoicePdfPreviewResponse,
    CommitAttacheInvoicePdfImportRequest,
    CreateOpShopCountrysideRouteGroupRequest,
    CreateDriverRequest,
    CreateOrderRequest,
    CreateOpShopPickupTaskRequest,
    CreateOpShopTemplateRequest,
    CreateVehicleRequest,
    DeliveryWorkspaceAssignOrderRequest,
    DeliveryWorkspaceUnassignOrderRequest,
    DeliveryWorkspaceVehicleAssignmentRequest,
    DeliveryWorkspaceVehicleClearRequest,
    EnsureOpShopPickupTasksRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
    LoginOperatorAccountRequest,
    MoveCountrysideRouteMembershipRequest,
    OpShopWorkspaceAssignmentBatchRequest,
    OpShopWorkspaceUnassignPickupRequest,
    RegisterOperatorAccountRequest,
    ResetOperatorPasswordRequest,
    SaveFinalTripSummaryRequest,
    SaveGeneratedWorkspaceSnapshotRequest,
    UnassignTaskRequest,
    UpdateOpShopCountrysideRouteGroupRequest,
    UpdateDriverRequest,
    UpdateOpShopPickupTaskRequest,
    UpdateOpShopTemplateRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
    to_dict,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.excel_export_service import build_manual_dispatch_excel
from backend.services.delivery_run_sheet_excel_export_service import (
    build_delivery_run_sheet_excel,
    build_delivery_run_sheets_excel,
)
from backend.services.final_summary_excel_export_service import build_final_summary_excel
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.manual_dispatch.workspace_migration_readiness_service import (
    WorkspaceMigrationRequiredError,
)
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    parse_attache_invoice_pdf_bytes,
    with_duplicate_warning,
)
from backend.services.opshop_pickup_excel_export_service import (
    build_opshop_pickup_run_sheet_excel,
)
from backend.services.opshop_pickup_collection_excel_export_service import (
    build_opshop_pickup_collection_excel,
)

router = APIRouter(prefix="/api/manual-dispatch", tags=["manual-dispatch"])
service = ManualDispatchService(SQLiteManualDispatchRepository())
ALLOW_REGISTRATION_ENV = "MANUAL_DISPATCH_ALLOW_REGISTRATION"
REGISTRATION_DISABLED_MESSAGE = "Registration is disabled. Please contact an administrator."


@router.get("/board")
def get_board(dispatch_date: str):
    return to_dict(service.get_board(dispatch_date))


@router.get("/workspace-migration-status")
def get_workspace_migration_status():
    return service.get_workspace_migration_status()


@router.get("/delivery/board")
def get_delivery_workspace_board(dispatch_date: str):
    try:
        return to_dict(service.get_delivery_workspace_board(dispatch_date))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop/board")
def get_opshop_workspace_board(dispatch_date: str):
    try:
        return to_dict(service.get_opshop_workspace_board(dispatch_date))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/shared/specifications")
def get_shared_specifications():
    return to_dict(service.get_shared_specifications())


@router.get("/delivery/specifications")
def get_delivery_specifications():
    return to_dict(service.get_delivery_specifications())


@router.post("/delivery/drivers")
def create_delivery_driver(request: CreateDriverRequest):
    try:
        return to_dict(service.create_delivery_driver(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/delivery/drivers/{driver_id}")
def update_delivery_driver(driver_id: str, request: UpdateDriverRequest):
    try:
        return to_dict(service.update_delivery_driver(driver_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.delete("/delivery/drivers/{driver_id}")
def delete_delivery_driver(driver_id: str):
    try:
        return to_dict(service.delete_delivery_driver(driver_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/vehicles")
def create_delivery_vehicle(request: CreateVehicleRequest):
    try:
        return to_dict(service.create_delivery_vehicle(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/delivery/vehicles/{vehicle_id}")
def update_delivery_vehicle(vehicle_id: str, request: UpdateVehicleRequest):
    try:
        return to_dict(service.update_delivery_vehicle(vehicle_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.delete("/delivery/vehicles/{vehicle_id}")
def delete_delivery_vehicle(vehicle_id: str):
    try:
        return to_dict(service.delete_delivery_vehicle(vehicle_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/orders")
def create_delivery_order(request: CreateOrderRequest):
    try:
        return to_dict(service.create_delivery_order(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/delivery/orders/{order_id}")
def update_delivery_order(order_id: str, request: UpdateOrderRequest):
    try:
        return to_dict(service.update_delivery_order(order_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/orders/{order_id}/cancel")
def cancel_delivery_order(order_id: str):
    try:
        return to_dict(service.cancel_delivery_order(order_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/orders/import-attache-pdf-preview")
async def preview_delivery_attache_invoice_pdf_import(files: List[UploadFile] = File(...)):
    return to_dict(await _preview_attache_invoice_pdf_import(files))


@router.post("/delivery/orders/import-attache-pdf-commit")
def commit_delivery_attache_invoice_pdf_import(
    request: CommitAttacheInvoicePdfImportRequest,
):
    try:
        service._ensure_workspace_ready("delivery")
        return _commit_attache_invoice_pdf_import(request, service.create_delivery_order)
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/assignments")
def assign_delivery_workspace_order(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type"})
        request = DeliveryWorkspaceAssignOrderRequest(
            dispatch_date=payload.get("dispatch_date"),
            order_id=payload.get("order_id"),
            driver_id=payload.get("driver_id"),
            trip_no=payload.get("trip_no"),
        )
        return to_dict(service.assign_delivery_workspace_order(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/assignments/unassign")
def unassign_delivery_workspace_order(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type"})
        request = DeliveryWorkspaceUnassignOrderRequest(
            dispatch_date=payload.get("dispatch_date"),
            order_id=payload.get("order_id"),
        )
        return to_dict(service.unassign_delivery_workspace_order(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/vehicle-assignments")
def assign_delivery_workspace_vehicle(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type"})
        request = DeliveryWorkspaceVehicleAssignmentRequest(
            dispatch_date=payload.get("dispatch_date"),
            delivery_date=payload.get("delivery_date"),
            driver_id=payload.get("driver_id"),
            vehicle_id=payload.get("vehicle_id"),
        )
        return to_dict(service.assign_delivery_workspace_vehicle(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/vehicle-assignments/clear")
def clear_delivery_workspace_vehicle(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type"})
        request = DeliveryWorkspaceVehicleClearRequest(
            dispatch_date=payload.get("dispatch_date"),
            delivery_date=payload.get("delivery_date"),
            driver_id=payload.get("driver_id"),
        )
        return to_dict(service.clear_delivery_workspace_vehicle(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop/pickups/assignments/apply")
def apply_opshop_workspace_assignments(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type", "trip_no"})
        request = OpShopWorkspaceAssignmentBatchRequest(
            dispatch_date=payload.get("dispatch_date"),
            assignments=payload.get("assignments") or [],
        )
        return to_dict(service.apply_opshop_workspace_assignments(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop/pickups/assignments/unassign")
def unassign_opshop_workspace_pickup(payload: dict = Body(...)):
    try:
        _reject_scoped_fields(payload, {"task_type", "trip_no"})
        request = OpShopWorkspaceUnassignPickupRequest(
            dispatch_date=payload.get("dispatch_date"),
            pickup_task_id=payload.get("pickup_task_id"),
        )
        return to_dict(service.unassign_opshop_workspace_pickup(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop/countryside-route-groups/{route_group_id}/assign")
def assign_opshop_workspace_countryside_route_group(
    route_group_id: str,
    payload: dict = Body(...),
):
    try:
        _reject_scoped_fields(payload, {"task_type", "trip_no"})
        request = AssignCountrysideRouteGroupRequest(
            dispatch_date=payload.get("dispatch_date"),
            pickup_date=payload.get("pickup_date"),
            assigned_driver_id=payload.get("assigned_driver_id"),
            notes=payload.get("notes"),
        )
        return to_dict(
            service.assign_opshop_workspace_countryside_route_group(
                route_group_id,
                request,
            )
        )
    except ValueError as error:
        raise _to_http_exception(error) from error


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


@router.post("/orders/import-attache-pdf-preview")
async def preview_attache_invoice_pdf_import(files: List[UploadFile] = File(...)):
    return to_dict(await _preview_attache_invoice_pdf_import(files))


@router.post("/orders/import-attache-pdf-commit")
def commit_attache_invoice_pdf_import(request: CommitAttacheInvoicePdfImportRequest):
    return _commit_attache_invoice_pdf_import(request, service.create_order)


def _commit_attache_invoice_pdf_import(request, create_order):
    created_orders = []
    skipped_rows = []
    existing_invoice_numbers = _existing_invoice_numbers()

    for row in request.rows or []:
        row_id = row.row_id or row.invoice_number or row.source_filename or "row"
        if not row.selected:
            skipped_rows.append({"row_id": row_id, "reason": "Row was not selected for import."})
            continue
        if not row.importable or row.is_duplicate:
            skipped_rows.append({"row_id": row_id, "reason": "Row is not importable."})
            continue
        if row.invoice_number and row.invoice_number in existing_invoice_numbers:
            skipped_rows.append({"row_id": row_id, "reason": "Duplicate invoice number already exists."})
            continue

        try:
            created = create_order(
                CreateOrderRequest(
                    invoice_number=row.invoice_number,
                    order_no=row.order_no,
                    company_name=row.company_name,
                    phone=row.phone,
                    delivery_address=row.delivery_address,
                    suburb=row.suburb,
                    postcode=row.postcode,
                    delivery_date=row.delivery_date,
                    zone=row.zone,
                    urgency=row.urgency,
                    preferred_driver_id=row.preferred_driver_id,
                    pallet_quantity=row.pallet_quantity,
                    loose_bags_quantity=row.loose_bags_quantity,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    note=row.note,
                    product_lines=row.product_lines,
                )
            )
            created_orders.append(to_dict(created))
            if created.invoice_number:
                existing_invoice_numbers.add(created.invoice_number)
        except WorkspaceMigrationRequiredError:
            raise
        except ValueError as error:
            skipped_rows.append({"row_id": row_id, "reason": str(error)})

    return {
        "created_orders": created_orders,
        "skipped_rows": skipped_rows,
        "imported_count": len(created_orders),
        "skipped_count": len(skipped_rows),
    }


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
def list_opshop_pickup_schedules(
    run_type: str = "scheduled",
    pickup_category: str = None,
):
    try:
        resolved_run_type = "countryside" if (pickup_category or "").upper() == "COUNTRYSIDE" else run_type
        return [
            to_dict(candidate)
            for candidate in service.list_opshop_pickup_schedule_candidates(resolved_run_type)
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop-countryside-route-groups")
def list_opshop_countryside_route_groups(include_inactive: bool = False):
    try:
        return [
            to_dict(route_group)
            for route_group in service.list_countryside_route_groups(include_inactive)
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-countryside-route-groups")
def create_opshop_countryside_route_group(
    request: CreateOpShopCountrysideRouteGroupRequest,
):
    try:
        return to_dict(service.create_countryside_route_group(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/opshop-countryside-route-groups/{route_group_id}")
def update_opshop_countryside_route_group(
    route_group_id: str,
    request: UpdateOpShopCountrysideRouteGroupRequest,
):
    try:
        return to_dict(service.update_countryside_route_group(route_group_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-countryside-route-groups/{route_group_id}/disable")
def disable_opshop_countryside_route_group(route_group_id: str):
    try:
        return to_dict(service.disable_countryside_route_group(route_group_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop-countryside-route-groups/{route_group_id}/memberships")
def list_opshop_countryside_route_memberships(route_group_id: str):
    try:
        return [
            to_dict(template)
            for template in service.list_countryside_route_memberships(route_group_id)
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-countryside-route-groups/{route_group_id}/memberships")
def add_opshop_countryside_route_membership(
    route_group_id: str,
    request: AddCountrysideRouteMembershipRequest,
):
    try:
        return to_dict(service.add_countryside_route_membership(route_group_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-countryside-memberships/{schedule_id}/remove")
def remove_opshop_countryside_route_membership(schedule_id: str):
    try:
        return to_dict(service.remove_countryside_route_membership(schedule_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-countryside-memberships/{schedule_id}/move")
def move_opshop_countryside_route_membership(
    schedule_id: str,
    request: MoveCountrysideRouteMembershipRequest,
):
    try:
        return to_dict(service.move_countryside_route_membership(schedule_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop-templates")
def list_opshop_templates(run_type: str = None, include_inactive: bool = False):
    try:
        return [
            to_dict(template)
            for template in service.list_opshop_templates(run_type, include_inactive)
        ]
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-templates")
def create_opshop_template(request: CreateOpShopTemplateRequest):
    try:
        return to_dict(service.create_opshop_template(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.patch("/opshop-templates/{schedule_id}")
def update_opshop_template(schedule_id: str, request: UpdateOpShopTemplateRequest):
    try:
        return to_dict(service.update_opshop_template(schedule_id, request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-templates/{schedule_id}/disable")
def disable_opshop_template(schedule_id: str):
    try:
        return to_dict(service.disable_opshop_template(schedule_id))
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


@router.get("/opshop-pickups/export-excel")
def export_opshop_pickups_excel(dispatch_date: str):
    workbook_bytes = build_opshop_pickup_run_sheet_excel(
        service.get_board(dispatch_date),
        dispatch_date,
    )
    filename = f"opshop-pickup-run-sheet-{dispatch_date}.xlsx"
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/opshop-pickups/countryside-assignments/apply")
def apply_countryside_opshop_pickup_assignments(
    request: ApplyCountrysideOpShopPickupAssignmentsRequest,
):
    try:
        return to_dict(service.apply_countryside_opshop_pickup_assignments(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop-pickups/countryside-route-groups/{route_group_id}/assign")
def assign_countryside_route_group_pickups(
    route_group_id: str,
    request: AssignCountrysideRouteGroupRequest,
):
    try:
        return to_dict(service.assign_countryside_route_group_pickups(route_group_id, request))
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


@router.post("/delivery/run-sheets/generated")
def create_generated_delivery_run_sheet(request: GenerateDeliveryRunSheetRequest):
    try:
        return to_dict(service.create_generated_delivery_run_sheet(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/delivery/run-sheets")
def list_delivery_run_sheets(
    dispatch_date: str = None,
    delivery_date: str = None,
    status: str = None,
):
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
        raise _to_http_exception(error) from error


@router.get("/delivery/run-sheets/export-excel")
def export_delivery_run_sheets_excel(delivery_date: str):
    try:
        run_sheets = service.list_delivery_run_sheets_for_date_export(delivery_date)
        workbook_bytes = build_delivery_run_sheets_excel(run_sheets, delivery_date)
    except ValueError as error:
        raise _to_http_exception(error) from error

    filename = f"Daily_Run_Sheets_{_safe_filename_part(delivery_date)}.xlsx"
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/delivery/run-sheets/{run_sheet_id}")
def get_delivery_run_sheet(run_sheet_id: str):
    try:
        return to_dict(service.get_delivery_run_sheet(run_sheet_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/run-sheets/{run_sheet_id}/save")
def save_generated_delivery_run_sheet(
    run_sheet_id: str,
    request: SaveGeneratedWorkspaceSnapshotRequest,
):
    try:
        return to_dict(
            service.save_generated_delivery_run_sheet(run_sheet_id, request)
        )
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/delivery/run-sheets/{run_sheet_id}/cancel-generated")
def cancel_generated_delivery_run_sheet(run_sheet_id: str):
    try:
        return {
            "cancelled": service.cancel_generated_delivery_run_sheet(run_sheet_id)
        }
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/delivery/run-sheets/{run_sheet_id}/export-excel")
def export_delivery_run_sheet_excel(run_sheet_id: str):
    try:
        run_sheet = service.get_saved_delivery_run_sheet_for_export(run_sheet_id)
    except ValueError as error:
        raise _to_http_exception(error) from error

    workbook_bytes = build_delivery_run_sheet_excel(run_sheet)
    filename = (
        f"Delivery_Run_Sheet_{_safe_filename_part(run_sheet.delivery_date)}_"
        f"{_safe_filename_part(run_sheet.driver_name_snapshot)}.xlsx"
    )
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/opshop/pickup-collections/generated")
def create_generated_opshop_pickup_collection(
    request: GenerateOpShopPickupCollectionRequest,
):
    try:
        return to_dict(service.create_generated_opshop_pickup_collection(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop/pickup-collections")
def list_opshop_pickup_collections(
    dispatch_date: str = None,
    pickup_date: str = None,
    status: str = None,
):
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
        raise _to_http_exception(error) from error


@router.get("/opshop/pickup-collections/{collection_id}")
def get_opshop_pickup_collection(collection_id: str):
    try:
        return to_dict(service.get_opshop_pickup_collection(collection_id))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop/pickup-collections/{collection_id}/save")
def save_generated_opshop_pickup_collection(
    collection_id: str,
    request: SaveGeneratedWorkspaceSnapshotRequest,
):
    try:
        return to_dict(
            service.save_generated_opshop_pickup_collection(collection_id, request)
        )
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/opshop/pickup-collections/{collection_id}/cancel-generated")
def cancel_generated_opshop_pickup_collection(collection_id: str):
    try:
        return {
            "cancelled": service.cancel_generated_opshop_pickup_collection(
                collection_id
            )
        }
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/opshop/pickup-collections/{collection_id}/export-excel")
def export_opshop_pickup_collection_excel(collection_id: str):
    try:
        collection = service.get_saved_opshop_pickup_collection_for_export(
            collection_id
        )
    except ValueError as error:
        raise _to_http_exception(error) from error

    workbook_bytes = build_opshop_pickup_collection_excel(collection)
    filename = (
        f"OPSHOP_Pickup_Collection_{_safe_filename_part(collection.pickup_date)}_"
        f"{_safe_filename_part(collection.driver_name_snapshot)}.xlsx"
    )
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/final-summaries")
def save_final_trip_summary(payload: dict = Body(...)):
    request = _save_final_trip_summary_request_from_payload(payload)
    try:
        return to_dict(service.save_final_trip_summary(request))
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.post("/final-summaries/generated")
def create_generated_final_trip_summary(payload: dict = Body(...)):
    request = _save_final_trip_summary_request_from_payload(payload)
    try:
        return to_dict(service.create_generated_final_trip_summary(request))
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


@router.post("/final-summaries/{summary_id}/save")
def save_generated_final_trip_summary(summary_id: str, payload: dict = Body(...)):
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
        raise _to_http_exception(error) from error


@router.post("/final-summaries/{summary_id}/cancel-generated")
def cancel_generated_final_trip_summary(summary_id: str):
    try:
        return {"cancelled": service.cancel_generated_final_trip_summary(summary_id)}
    except ValueError as error:
        raise _to_http_exception(error) from error


@router.get("/final-summaries/{summary_id}/export-excel")
def export_saved_final_trip_summary_excel(summary_id: str):
    try:
        summary = service.get_saved_final_trip_summary_for_export(summary_id)
    except ValueError as error:
        raise _to_http_exception(error) from error

    workbook_bytes = build_final_summary_excel(
        [summary],
        summary.dispatch_date,
        summary.delivery_date,
    )
    filename = _final_summary_export_filename(summary)
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        opshop_pickups=payload.get("opshop_pickups") or [],
        saved_by_account_name=payload.get("saved_by_account_name"),
        saved_by_account_id=payload.get("saved_by_account_id"),
    )


def _to_http_exception(error):
    message = str(error)
    if isinstance(error, WorkspaceMigrationRequiredError):
        status_code = 409
    else:
        status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)


def _reject_scoped_fields(payload, forbidden_fields):
    for field_name in forbidden_fields:
        if field_name in (payload or {}):
            raise ValueError(f"Scoped workspace request does not accept {field_name}")


def _existing_invoice_numbers():
    return {
        order.invoice_number
        for order in service.repository.list_orders()
        if order.invoice_number
    }


async def _preview_attache_invoice_pdf_import(files):
    rows = []
    existing_invoice_numbers = _existing_invoice_numbers()

    for uploaded_file in files:
        filename = uploaded_file.filename or "invoice.pdf"
        try:
            parsed = parse_attache_invoice_pdf_bytes(
                await uploaded_file.read(),
                source_filename=filename,
            )
            if parsed.invoice_number and parsed.invoice_number in existing_invoice_numbers:
                parsed = with_duplicate_warning(parsed)
            rows.append(parsed)
        except ValueError as error:
            rows.append(
                _failed_attache_preview_row(
                    filename,
                    str(error),
                )
            )

    return AttacheInvoicePdfPreviewResponse(rows=rows)


def _failed_attache_preview_row(source_filename, message):
    from backend.schemas import AttacheInvoicePdfPreviewItem

    return AttacheInvoicePdfPreviewItem(
        row_id=f"ATTACHE-FAILED-{sha1(source_filename.encode('utf-8')).hexdigest()[:12]}",
        source_filename=source_filename,
        warnings=[message],
        importable=False,
        selected=False,
    )


def _final_summary_export_filename(summary):
    driver_name = _safe_filename_part(summary.driver_name_snapshot or summary.driver_id)
    return (
        f"Final_Trip_Summary_{_safe_filename_part(summary.summary_id)}_"
        f"{_safe_filename_part(summary.delivery_date)}_{driver_name}.xlsx"
    )


def _safe_filename_part(value):
    text = str(value or "").strip() or "Summary"
    safe_characters = []
    for character in text:
        if character.isalnum() or character in {"-", "_"}:
            safe_characters.append(character)
        elif character.isspace():
            safe_characters.append("_")
    safe = "".join(safe_characters).strip("_")
    return safe or "Summary"


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
