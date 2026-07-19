from collections.abc import Callable
from fastapi import (
    APIRouter,
    Body,
    Request,
)
from backend.schemas import (
    AddCountrysideRouteMembershipRequest,
    ApplyCountrysideOpShopPickupAssignmentsRequest,
    ApplyOncallOpShopPickupAssignmentsRequest,
    ApplyWeeklyOpShopPickupAssignmentsRequest,
    AssignCountrysideRouteGroupRequest,
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopPickupTaskRequest,
    CreateOpShopTemplateRequest,
    EnsureOpShopPickupTasksRequest,
    MoveCountrysideRouteMembershipRequest,
    OpShopWorkspaceAssignmentBatchRequest,
    OpShopWorkspaceUnassignPickupRequest,
    UpdateOpShopCountrysideRouteGroupRequest,
    UpdateOpShopPickupTaskRequest,
    UpdateOpShopTemplateRequest,
    to_dict,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from .common import (
    reject_scoped_fields,
    to_http_exception,
    with_logbook_actor,
)


def create_opshop_router(
    get_service: Callable[[], ManualDispatchService],
    router: APIRouter = None,
) -> APIRouter:
    router = router or APIRouter()

    @router.get("/opshop/board")
    def get_opshop_workspace_board(dispatch_date: str):
        service = get_service()
        try:
            return to_dict(service.get_opshop_workspace_board(dispatch_date))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop/trip-summary")
    def get_opshop_trip_summary_board(pickup_date: str, dispatch_date: str = None):
        service = get_service()
        try:
            # dispatch_date remains an optional legacy query parameter only.
            return to_dict(service.get_opshop_trip_summary_board(pickup_date))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/pickups/assignments/apply")
    def apply_opshop_workspace_assignments(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type", "trip_no"})
            request = OpShopWorkspaceAssignmentBatchRequest(
                dispatch_date=payload.get("dispatch_date"),
                assignments=payload.get("assignments") or [],
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.apply_opshop_workspace_assignments(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/pickups/assignments/unassign")
    def unassign_opshop_workspace_pickup(
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type", "trip_no"})
            request = OpShopWorkspaceUnassignPickupRequest(
                dispatch_date=payload.get("dispatch_date"),
                pickup_task_id=payload.get("pickup_task_id"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.unassign_opshop_workspace_pickup(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop/countryside-route-groups/{route_group_id}/assign")
    def assign_opshop_workspace_countryside_route_group(
        route_group_id: str,
        http_request: Request = None,
        payload: dict = Body(...),
    ):
        service = get_service()
        try:
            reject_scoped_fields(payload, {"task_type", "trip_no"})
            request = AssignCountrysideRouteGroupRequest(
                dispatch_date=payload.get("dispatch_date"),
                pickup_date=payload.get("pickup_date"),
                assigned_driver_id=payload.get("assigned_driver_id"),
                notes=payload.get("notes"),
            )
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.assign_opshop_workspace_countryside_route_group(
                        route_group_id,
                        request,
                    )
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/generate")
    def generate_opshop_pickups(request: EnsureOpShopPickupTasksRequest):
        service = get_service()
        try:
            return to_dict(service.ensure_opshop_pickup_tasks_for_window(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop-pickup-schedules")
    def list_opshop_pickup_schedules(
        run_type: str = "scheduled",
        pickup_category: str = None,
    ):
        service = get_service()
        try:
            resolved_run_type = "countryside" if (pickup_category or "").upper() == "COUNTRYSIDE" else run_type
            return [
                to_dict(candidate)
                for candidate in service.list_opshop_pickup_schedule_candidates(resolved_run_type)
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop-countryside-route-groups")
    def list_opshop_countryside_route_groups(include_inactive: bool = False):
        service = get_service()
        try:
            return [
                to_dict(route_group)
                for route_group in service.list_countryside_route_groups(include_inactive)
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-countryside-route-groups")
    def create_opshop_countryside_route_group(
        request: CreateOpShopCountrysideRouteGroupRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_countryside_route_group(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/opshop-countryside-route-groups/{route_group_id}")
    def update_opshop_countryside_route_group(
        route_group_id: str,
        request: UpdateOpShopCountrysideRouteGroupRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.update_countryside_route_group(route_group_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-countryside-route-groups/{route_group_id}/disable")
    def disable_opshop_countryside_route_group(
        route_group_id: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.disable_countryside_route_group(route_group_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop-countryside-route-groups/{route_group_id}/memberships")
    def list_opshop_countryside_route_memberships(route_group_id: str):
        service = get_service()
        try:
            return [
                to_dict(template)
                for template in service.list_countryside_route_memberships(route_group_id)
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-countryside-route-groups/{route_group_id}/memberships")
    def add_opshop_countryside_route_membership(
        route_group_id: str,
        request: AddCountrysideRouteMembershipRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.add_countryside_route_membership(route_group_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-countryside-memberships/{schedule_id}/remove")
    def remove_opshop_countryside_route_membership(
        schedule_id: str,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.remove_countryside_route_membership(schedule_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-countryside-memberships/{schedule_id}/move")
    def move_opshop_countryside_route_membership(
        schedule_id: str,
        request: MoveCountrysideRouteMembershipRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.move_countryside_route_membership(schedule_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.get("/opshop-templates")
    def list_opshop_templates(run_type: str = None, include_inactive: bool = False):
        service = get_service()
        try:
            return [
                to_dict(template)
                for template in service.list_opshop_templates(run_type, include_inactive)
            ]
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-templates")
    def create_opshop_template(
        request: CreateOpShopTemplateRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_opshop_template(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/opshop-templates/{schedule_id}")
    def update_opshop_template(
        schedule_id: str,
        request: UpdateOpShopTemplateRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.update_opshop_template(schedule_id, request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-templates/{schedule_id}/disable")
    def disable_opshop_template(schedule_id: str, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.disable_opshop_template(schedule_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups")
    def create_opshop_pickup(
        request: CreateOpShopPickupTaskRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_opshop_pickup_task(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/oncall")
    def create_oncall_opshop_pickup(
        request: CreateOpShopPickupTaskRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.create_oncall_opshop_pickup_task(request)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.patch("/opshop-pickups/{pickup_task_id}")
    def update_opshop_pickup(
        pickup_task_id: str,
        request: UpdateOpShopPickupTaskRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.update_opshop_pickup_task(pickup_task_id, request)
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.delete("/opshop-pickups/{pickup_task_id}")
    def delete_opshop_pickup(pickup_task_id: str, http_request: Request = None):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(service.delete_opshop_pickup_task(pickup_task_id)),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/weekly-assignments/apply")
    def apply_weekly_opshop_pickup_assignments(request: ApplyWeeklyOpShopPickupAssignmentsRequest):
        service = get_service()
        try:
            return to_dict(service.apply_weekly_opshop_pickup_assignments(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/oncall-assignments/apply")
    def apply_oncall_opshop_pickup_assignments(request: ApplyOncallOpShopPickupAssignmentsRequest):
        service = get_service()
        try:
            return to_dict(service.apply_oncall_opshop_pickup_assignments(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/countryside-assignments/apply")
    def apply_countryside_opshop_pickup_assignments(
        request: ApplyCountrysideOpShopPickupAssignmentsRequest,
    ):
        service = get_service()
        try:
            return to_dict(service.apply_countryside_opshop_pickup_assignments(request))
        except ValueError as error:
            raise to_http_exception(error) from error

    @router.post("/opshop-pickups/countryside-route-groups/{route_group_id}/assign")
    def assign_countryside_route_group_pickups(
        route_group_id: str,
        request: AssignCountrysideRouteGroupRequest,
        http_request: Request = None,
    ):
        service = get_service()
        try:
            return with_logbook_actor(
                service,
                http_request,
                lambda: to_dict(
                    service.assign_countryside_route_group_pickups(
                        route_group_id,
                        request,
                    )
                ),
            )
        except ValueError as error:
            raise to_http_exception(error) from error

    return router
