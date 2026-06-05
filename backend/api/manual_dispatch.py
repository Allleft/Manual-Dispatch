import os

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from backend.schemas import (
    AddCountrysideRouteMembershipRequest,
    ApplyCountrysideOpShopPickupAssignmentsRequest,
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignCountrysideRouteGroupRequest,
    AssignDriverVehicleRequest,
    AssignTaskRequest,
    CreateOpShopCountrysideRouteGroupRequest,
    CreateDriverRequest,
    CreateOrderRequest,
    CreateOpShopPickupTaskRequest,
    CreateOpShopTemplateRequest,
    CreateVehicleRequest,
    EnsureOpShopPickupTasksRequest,
    LoginOperatorAccountRequest,
    MoveCountrysideRouteMembershipRequest,
    RegisterOperatorAccountRequest,
    ResetOperatorPasswordRequest,
    SaveFinalTripSummaryRequest,
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
from backend.services.final_summary_excel_export_service import build_final_summary_excel
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.opshop_pickup_excel_export_service import (
    build_opshop_pickup_run_sheet_excel,
)

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
    status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)


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
