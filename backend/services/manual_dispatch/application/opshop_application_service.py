from . import FacadeApplicationService


class OpShopApplicationService(FacadeApplicationService):
    """Own opshop application orchestration."""

    def get_opshop_workspace_board(self, dispatch_date):
        self._ensure_workspace_ready("opshop")
        return self.opshop_workspace_board_service.get_board(dispatch_date)

    def get_opshop_trip_summary_board(self, pickup_date):
        self._ensure_workspace_ready("opshop")
        return self.opshop_workspace_board_service.get_trip_summary_board(
            pickup_date
        )

    def apply_opshop_workspace_assignments(self, request):
        self._ensure_workspace_ready("opshop")
        before_by_task_id = {
            item.get("pickup_task_id"): self._assignment_snapshot(
                request.dispatch_date,
                "OPSHOP_PICKUP",
                item.get("pickup_task_id"),
            )
            for item in request.assignments or []
            if isinstance(item, dict)
        }
        try:
            board = self.opshop_workspace_mutation_service.apply_assignments(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="OPSHOP_TASK_ASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=None,
                summary="OP SHOP pickup assignment update failed.",
                dispatch_date=request.dispatch_date or self._opshop_assignment_pickup_date(request.assignments),
                pickup_date=self._opshop_assignment_pickup_date(request.assignments),
                metadata={"failure_reason": str(error)},
            )
            raise
        for item in request.assignments or []:
            if not isinstance(item, dict):
                continue
            pickup_task_id = item.get("pickup_task_id")
            self._record_opshop_assignment_change(
                request.dispatch_date,
                pickup_task_id,
                before_by_task_id.get(pickup_task_id),
                self._assignment_snapshot(
                    request.dispatch_date,
                    "OPSHOP_PICKUP",
                    pickup_task_id,
                ),
            )
        return board

    def unassign_opshop_workspace_pickup(self, request):
        self._ensure_workspace_ready("opshop")
        before = self._assignment_snapshot(
            request.dispatch_date,
            "OPSHOP_PICKUP",
            request.pickup_task_id,
        )
        try:
            board = self.opshop_workspace_mutation_service.unassign_pickup(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="OPSHOP_TASK_UNASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=request.pickup_task_id,
                summary=(
                    f"OP SHOP pickup {self._opshop_pickup_name(request.pickup_task_id)} "
                    "unassignment failed."
                ),
                dispatch_date=request.dispatch_date or self._opshop_pickup_date(request.pickup_task_id),
                pickup_date=self._opshop_pickup_date(request.pickup_task_id),
                driver=before.get("driver") if before else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if before:
            self._record_opshop_assignment_change(
                request.dispatch_date,
                request.pickup_task_id,
                before,
                None,
            )
        return board

    def assign_opshop_workspace_countryside_route_group(
        self,
        route_group_id,
        request,
    ):
        self._ensure_workspace_ready("opshop")
        try:
            board = self.opshop_workspace_mutation_service.assign_countryside_route_group(
                route_group_id,
                request,
            )
        except Exception as error:
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="COUNTRYSIDE_ROUTE_GROUP_ASSIGNED",
                entity_type="COUNTRYSIDE_ROUTE_GROUP",
                entity_id=route_group_id,
                summary=(
                    f"Countryside route group {self._route_group_name(route_group_id)} "
                    "assignment failed."
                ),
                dispatch_date=request.dispatch_date,
                pickup_date=request.pickup_date,
                driver=self._driver_name(request.assigned_driver_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_ROUTE_GROUP_ASSIGNED",
            entity_type="COUNTRYSIDE_ROUTE_GROUP",
            entity_id=route_group_id,
            summary=(
                f"Countryside route group {self._route_group_name(route_group_id)} "
                f"was assigned to {self._driver_name(request.assigned_driver_id)} "
                f"for pickup date {request.pickup_date}."
            ),
            dispatch_date=request.dispatch_date,
            pickup_date=request.pickup_date,
            driver=self._driver_name(request.assigned_driver_id),
            metadata={
                "route_group_id": route_group_id,
                "route_group_name": self._route_group_name(route_group_id),
            },
        )
        return board

    def create_generated_opshop_pickup_collection(self, request):
        self._ensure_workspace_ready("opshop")
        try:
            collection = self.opshop_pickup_collection_service.create_generated(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="PICKUP_COLLECTION_GENERATED",
                entity_type="OPSHOP_PICKUP_COLLECTION",
                summary="OP SHOP Pickup Collection generation failed.",
                dispatch_date=request.dispatch_date or request.pickup_date,
                pickup_date=request.pickup_date,
                driver=self._driver_name(request.driver_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_opshop_collection_event(
            "PICKUP_COLLECTION_GENERATED",
            collection,
        )
        return collection

    def list_opshop_pickup_collections(
        self,
        dispatch_date=None,
        pickup_date=None,
        status=None,
    ):
        self._ensure_workspace_ready("opshop")
        return self.opshop_pickup_collection_service.list(
            dispatch_date,
            pickup_date,
            status,
        )

    def get_opshop_pickup_collection(self, collection_id):
        return self.opshop_pickup_collection_service.get(collection_id)

    def save_generated_opshop_pickup_collection(self, collection_id, request):
        self._ensure_workspace_ready("opshop")
        try:
            collection = self.opshop_pickup_collection_service.save_generated(
                collection_id,
                request,
            )
        except Exception as error:
            current = self.repository.get_opshop_pickup_collection(collection_id)
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="PICKUP_COLLECTION_SAVED",
                entity_type="OPSHOP_PICKUP_COLLECTION",
                entity_id=collection_id,
                summary=f"OP SHOP Pickup Collection {collection_id} save failed.",
                dispatch_date=current.dispatch_date if current else None,
                pickup_date=current.pickup_date if current else None,
                driver=self._driver_name(current.driver_id) if current else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_opshop_collection_event(
            "PICKUP_COLLECTION_SAVED",
            collection,
        )
        return collection

    def cancel_generated_opshop_pickup_collection(self, collection_id):
        self._ensure_workspace_ready("opshop")
        current = self.repository.get_opshop_pickup_collection(collection_id)
        try:
            cancelled = self.opshop_pickup_collection_service.cancel_generated(
                collection_id
            )
        except Exception as error:
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="PICKUP_COLLECTION_CANCELLED",
                entity_type="OPSHOP_PICKUP_COLLECTION",
                entity_id=collection_id,
                summary=f"OP SHOP Pickup Collection {collection_id} cancellation failed.",
                dispatch_date=current.dispatch_date if current else None,
                pickup_date=current.pickup_date if current else None,
                driver=self._driver_name(current.driver_id) if current else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if current:
            self._record_opshop_collection_event(
                "PICKUP_COLLECTION_CANCELLED",
                current,
            )
        return cancelled

    def get_opshop_pickup_collection_for_export(self, collection_id):
        return self.opshop_pickup_collection_service.get_for_export(
            collection_id
        )

    def get_saved_opshop_pickup_collection_for_export(self, collection_id):
        return self.get_opshop_pickup_collection_for_export(collection_id)

    def list_opshop_pickup_collections_for_date_export(
        self,
        pickup_date,
        dispatch_date=None,
        status=None,
    ):
        return self.opshop_pickup_collection_service.list_for_date_export(
            pickup_date,
            dispatch_date,
            status,
        )

    def record_opshop_pickup_collection_export(self, collection, filename):
        return self._facade.opshop_event_recorder.record_opshop_pickup_collection_export(collection, filename)

    def record_opshop_pickup_collections_daily_export(
        self,
        collections,
        pickup_date,
        filename,
        dispatch_date=None,
        status=None,
    ):
        return self._facade.opshop_event_recorder.record_opshop_pickup_collections_daily_export(collections, pickup_date, filename, dispatch_date, status)

    def ensure_opshop_pickup_tasks_for_window(self, request):
        return self.opshop_pickup_service.ensure_opshop_pickup_tasks_for_window(request)

    def list_opshop_pickup_schedule_candidates(self, run_type="scheduled"):
        return self.opshop_pickup_service.list_opshop_pickup_schedule_candidates(run_type)

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        return self.opshop_template_service.list_opshop_templates(
            run_type,
            include_inactive,
        )

    def list_countryside_route_groups(self, include_inactive=False):
        return self.opshop_template_service.list_countryside_route_groups(
            include_inactive
        )

    def create_countryside_route_group(self, request):
        route_group = self.opshop_template_service.create_countryside_route_group(
            request
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_ROUTE_GROUP_CREATED",
            entity_type="COUNTRYSIDE_ROUTE_GROUP",
            entity_id=route_group.route_group_id,
            summary=(
                f"Countryside route group {route_group.route_group_name} was created."
            ),
            metadata={
                "route_group_name": route_group.route_group_name,
                "active": bool(route_group.active_flag),
            },
        )
        return route_group

    def update_countryside_route_group(self, route_group_id, request):
        existing = self.repository.get_countryside_route_group(route_group_id)
        before_name = existing.route_group_name if existing else None
        route_group = self.opshop_template_service.update_countryside_route_group(
            route_group_id,
            request,
        )
        if before_name != route_group.route_group_name:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="COUNTRYSIDE_ROUTE_GROUP_RENAMED",
                entity_type="COUNTRYSIDE_ROUTE_GROUP",
                entity_id=route_group.route_group_id,
                summary=(
                    f"Countryside route group {before_name} was renamed to "
                    f"{route_group.route_group_name}."
                ),
                metadata={
                    "before": {"route_group_name": before_name},
                    "after": {
                        "route_group_name": route_group.route_group_name,
                    },
                },
            )
        return route_group

    def disable_countryside_route_group(self, route_group_id):
        existing = self.repository.get_countryside_route_group(route_group_id)
        before_name = existing.route_group_name if existing else None
        previous_active = bool(existing.active_flag) if existing else None
        route_group = self.opshop_template_service.disable_countryside_route_group(
            route_group_id
        )
        if previous_active and not route_group.active_flag:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="COUNTRYSIDE_ROUTE_GROUP_DISABLED",
                entity_type="COUNTRYSIDE_ROUTE_GROUP",
                entity_id=route_group.route_group_id,
                summary=(
                    f"Countryside route group {before_name} was disabled."
                ),
                metadata={
                    "route_group_name": before_name,
                    "previous_active": previous_active,
                    "new_active": bool(route_group.active_flag),
                },
            )
        return route_group

    def list_countryside_route_memberships(self, route_group_id):
        return self.opshop_template_service.list_countryside_route_memberships(
            route_group_id
        )

    def add_countryside_route_membership(self, route_group_id, request):
        template = self.opshop_template_service.add_countryside_route_membership(
            route_group_id,
            request,
        )
        route_group = self.repository.get_countryside_route_group(
            template.route_group_id
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_MEMBERSHIP_ADDED",
            entity_type="COUNTRYSIDE_MEMBERSHIP",
            entity_id=template.schedule_id,
            summary=(
                f"OP SHOP template {template.name} was added to countryside "
                f"route group {route_group.route_group_name}."
            ),
            metadata={
                "schedule_id": template.schedule_id,
                "company_name": template.name,
                "suburb": template.suburb,
                "route_group_id": route_group.route_group_id,
                "route_group_name": route_group.route_group_name,
            },
        )
        return template

    def remove_countryside_route_membership(self, schedule_id):
        existing = self._find_opshop_template(schedule_id)
        before = self._template_business_snapshot(existing) if existing else {}
        route_group = self.repository.get_countryside_route_group(
            before.get("route_group_id")
        )
        template = self.opshop_template_service.remove_countryside_route_membership(
            schedule_id
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_MEMBERSHIP_REMOVED",
            entity_type="COUNTRYSIDE_MEMBERSHIP",
            entity_id=schedule_id,
            summary=(
                f"OP SHOP template {before.get('name')} was removed from "
                f"countryside route group {route_group.route_group_name}."
            ),
            metadata={
                "schedule_id": schedule_id,
                "company_name": before.get("name"),
                "suburb": before.get("suburb"),
                "route_group_id": route_group.route_group_id,
                "route_group_name": route_group.route_group_name,
            },
        )
        return template

    def move_countryside_route_membership(self, schedule_id, request):
        existing = self._find_opshop_template(schedule_id)
        before = self._template_business_snapshot(existing) if existing else {}
        source_group = self.repository.get_countryside_route_group(
            before.get("route_group_id")
        )
        template = self.opshop_template_service.move_countryside_route_membership(
            schedule_id,
            request,
        )
        target_group = self.repository.get_countryside_route_group(
            template.route_group_id
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_MEMBERSHIP_MOVED",
            entity_type="COUNTRYSIDE_MEMBERSHIP",
            entity_id=template.schedule_id,
            summary=(
                f"OP SHOP template {template.name} was moved from route group "
                f"{source_group.route_group_name} to route group "
                f"{target_group.route_group_name}."
            ),
            metadata={
                "schedule_id": template.schedule_id,
                "company_name": template.name,
                "before": {
                    "route_group_id": source_group.route_group_id,
                    "route_group_name": source_group.route_group_name,
                },
                "after": {
                    "route_group_id": target_group.route_group_id,
                    "route_group_name": target_group.route_group_name,
                },
            },
        )
        return template

    def create_opshop_template(self, request):
        template = self.opshop_template_service.create_opshop_template(request)
        self._record_template_event("CREATED", template)
        return template

    def update_opshop_template(self, schedule_id, request):
        existing = self._find_opshop_template(schedule_id)
        before = self._template_business_snapshot(existing) if existing else {}
        template = self.opshop_template_service.update_opshop_template(
            schedule_id,
            request,
        )
        after = self._template_business_snapshot(template)
        self._record_template_event("UPDATED", template, before, after)
        return template

    def disable_opshop_template(self, schedule_id):
        existing = self._find_opshop_template(schedule_id)
        before = {
            "status": existing.status if existing else None,
            "active_flag": existing.active_flag if existing else None,
        }
        template = self.opshop_template_service.disable_opshop_template(schedule_id)
        if before["active_flag"] and not template.active_flag:
            self._record_template_event("DISABLED", template, before=before)
        return template

    def create_opshop_pickup_task(self, request):
        task = self.opshop_pickup_service.create_opshop_pickup_task(request)
        self._record_opshop_task_event("OPSHOP_TASK_CREATED", task)
        return task

    def create_oncall_opshop_pickup_task(self, request):
        task = self.opshop_pickup_service.create_oncall_opshop_pickup_task(request)
        self._record_opshop_task_event("OPSHOP_TASK_CREATED", task)
        return task

    def update_opshop_pickup_task(self, pickup_task_id, request):
        task = self.opshop_pickup_service.update_opshop_pickup_task(
            pickup_task_id,
            request,
        )
        self._record_opshop_task_event("OPSHOP_TASK_UPDATED", task)
        return task

    def delete_opshop_pickup_task(self, pickup_task_id):
        task = self.opshop_pickup_service.delete_opshop_pickup_task(pickup_task_id)
        self._record_opshop_task_event("OPSHOP_TASK_CANCELLED", task)
        return task

    def apply_weekly_opshop_pickup_assignments(self, request):
        self.opshop_pickup_service.apply_weekly_assignments(request)
        return self.board_service.get_board(request.dispatch_date)

    def apply_oncall_opshop_pickup_assignments(self, request):
        self.opshop_pickup_service.apply_oncall_assignments(request)
        return self.board_service.get_board(request.dispatch_date)

    def apply_countryside_opshop_pickup_assignments(self, request):
        self.opshop_pickup_service.apply_countryside_assignments(request)
        return self.board_service.get_board(request.dispatch_date)

    def assign_countryside_route_group_pickups(self, route_group_id, request):
        self.opshop_pickup_service.assign_countryside_route_group_pickups(
            route_group_id,
            request,
        )
        board = self.board_service.get_board(request.dispatch_date)
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="COUNTRYSIDE_ROUTE_GROUP_ASSIGNED",
            entity_type="COUNTRYSIDE_ROUTE_GROUP",
            entity_id=route_group_id,
            summary=(
                f"Countryside route group {self._route_group_name(route_group_id)} "
                f"was assigned to {self._driver_name(request.assigned_driver_id)} "
                f"for pickup date {request.pickup_date}."
            ),
            dispatch_date=request.dispatch_date,
            pickup_date=request.pickup_date,
            driver=self._driver_name(request.assigned_driver_id),
            metadata={
                "route_group_id": route_group_id,
                "route_group_name": self._route_group_name(route_group_id),
            },
        )
        return board
