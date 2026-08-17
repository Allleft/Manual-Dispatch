from backend.services.manual_dispatch.delivery_run_sheet_lock import ensure_order_not_reserved
from . import FacadeApplicationService


class DeliveryApplicationService(FacadeApplicationService):
    """Own delivery application orchestration."""

    def get_delivery_workspace_board(self, dispatch_date):
        self._ensure_workspace_ready("delivery")
        return self.delivery_workspace_board_service.get_board(dispatch_date)

    def classify_delivery_area(self, request):
        self._ensure_workspace_ready("delivery")
        return self.delivery_order_area_resolver.classify(
            request.suburb,
            request.postcode,
        )

    def get_delivery_trip_summary_board(self, delivery_date):
        self._ensure_workspace_ready("delivery")
        return self.delivery_workspace_board_service.get_trip_summary_board(
            delivery_date
        )

    def assign_delivery_workspace_order(self, request):
        self._ensure_workspace_ready("delivery")
        before = self._assignment_snapshot(
            request.dispatch_date,
            "ORDER",
            request.order_id,
        )
        try:
            board = self.delivery_workspace_mutation_service.assign_order(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="ORDER_REASSIGNED" if before else "ORDER_ASSIGNED",
                entity_type="ORDER",
                entity_id=self._order_entity_id_by_id(request.order_id),
                summary=(
                    f"Order {self._order_entity_id_by_id(request.order_id)} "
                    "assignment failed."
                ),
                dispatch_date=request.dispatch_date or self._order_delivery_date(request.order_id),
                delivery_date=self._order_delivery_date(request.order_id),
                driver=self._driver_name(request.driver_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        after = self._assignment_snapshot(
            request.dispatch_date,
            "ORDER",
            request.order_id,
        )
        self._record_delivery_assignment_change(
            request.dispatch_date,
            request.order_id,
            before,
            after,
        )
        return board

    def unassign_delivery_workspace_order(self, request):
        self._ensure_workspace_ready("delivery")
        before = self._assignment_snapshot(
            request.dispatch_date,
            "ORDER",
            request.order_id,
        )
        try:
            board = self.delivery_workspace_mutation_service.unassign_order(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="ORDER_UNASSIGNED",
                entity_type="ORDER",
                entity_id=self._order_entity_id_by_id(request.order_id),
                summary=(
                    f"Order {self._order_entity_id_by_id(request.order_id)} "
                    "unassignment failed."
                ),
                dispatch_date=request.dispatch_date or self._order_delivery_date(request.order_id),
                delivery_date=self._order_delivery_date(request.order_id),
                driver=before.get("driver") if before else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if before:
            self._record_delivery_assignment_change(
                request.dispatch_date,
                request.order_id,
                before,
                None,
            )
        return board

    def assign_delivery_workspace_vehicle(self, request):
        self._ensure_workspace_ready("delivery")
        before = self._vehicle_assignment_snapshot(
            request.dispatch_date,
            request.delivery_date,
            request.driver_id,
        )
        try:
            board = self.delivery_workspace_mutation_service.assign_vehicle(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="VEHICLE_CHANGED" if before else "VEHICLE_ASSIGNED",
                entity_type="VEHICLE",
                entity_id=request.vehicle_id,
                summary=(
                    f"Vehicle {self._vehicle_label(request.vehicle_id)} assignment "
                    f"to {self._driver_name(request.driver_id)} failed."
                ),
                dispatch_date=request.dispatch_date or request.delivery_date,
                delivery_date=request.delivery_date,
                driver=self._driver_name(request.driver_id),
                vehicle=self._vehicle_label(request.vehicle_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        after = self._vehicle_assignment_snapshot(
            request.dispatch_date,
            request.delivery_date,
            request.driver_id,
        )
        self._record_vehicle_assignment_change(
            request.dispatch_date,
            request.delivery_date,
            request.driver_id,
            before,
            after,
        )
        return board

    def clear_delivery_workspace_vehicle(self, request):
        self._ensure_workspace_ready("delivery")
        before = self._vehicle_assignment_snapshot(
            request.dispatch_date,
            request.delivery_date,
            request.driver_id,
        )
        try:
            board = self.delivery_workspace_mutation_service.clear_vehicle(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="VEHICLE_CLEARED",
                entity_type="VEHICLE",
                entity_id=before.get("vehicle_id") if before else None,
                summary=(
                    f"Vehicle clear for {self._driver_name(request.driver_id)} "
                    "failed."
                ),
                dispatch_date=request.dispatch_date or request.delivery_date,
                delivery_date=request.delivery_date,
                driver=self._driver_name(request.driver_id),
                vehicle=before.get("vehicle") if before else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if before:
            self._record_vehicle_assignment_change(
                request.dispatch_date,
                request.delivery_date,
                request.driver_id,
                before,
                None,
            )
        return board

    def create_generated_delivery_run_sheet(self, request):
        self._ensure_workspace_ready("delivery")
        try:
            run_sheet = self.delivery_run_sheet_service.create_generated(request)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="DELIVERY_RUN_SHEET_GENERATED",
                entity_type="DELIVERY_RUN_SHEET",
                summary="Delivery Run Sheet generation failed.",
                dispatch_date=request.dispatch_date or request.delivery_date,
                delivery_date=request.delivery_date,
                driver=self._driver_name(request.driver_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_delivery_run_sheet_event(
            "DELIVERY_RUN_SHEET_GENERATED",
            run_sheet,
        )
        return run_sheet

    def list_delivery_run_sheets(
        self,
        dispatch_date=None,
        delivery_date=None,
        status=None,
    ):
        self._ensure_workspace_ready("delivery")
        return self.delivery_run_sheet_service.list(
            dispatch_date,
            delivery_date,
            status,
        )

    def get_delivery_run_sheet(self, run_sheet_id):
        return self.delivery_run_sheet_service.get(run_sheet_id)

    def save_generated_delivery_run_sheet(self, run_sheet_id, request):
        self._ensure_workspace_ready("delivery")
        try:
            run_sheet = self.delivery_run_sheet_service.save_generated(
                run_sheet_id,
                request,
            )
        except Exception as error:
            current = self.repository.get_delivery_run_sheet(run_sheet_id)
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="DELIVERY_RUN_SHEET_SAVED",
                entity_type="DELIVERY_RUN_SHEET",
                entity_id=run_sheet_id,
                summary=f"Delivery Run Sheet {run_sheet_id} save failed.",
                dispatch_date=current.dispatch_date if current else None,
                delivery_date=current.delivery_date if current else None,
                driver=self._driver_name(current.driver_id) if current else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_delivery_run_sheet_event(
            "DELIVERY_RUN_SHEET_SAVED",
            run_sheet,
        )
        return run_sheet

    def close_saved_delivery_run_sheet(
        self,
        run_sheet_id,
        request,
        operator_identity,
    ):
        self._ensure_workspace_ready("delivery")
        current = self.repository.get_delivery_run_sheet(run_sheet_id)
        try:
            run_sheet = self.delivery_run_sheet_service.close_saved(
                run_sheet_id,
                request,
                operator_identity,
            )
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="DELIVERY_RUN_SHEET_CLOSED",
                entity_type="DELIVERY_RUN_SHEET",
                entity_id=run_sheet_id,
                summary=f"Delivery Run Sheet {run_sheet_id} closeout failed.",
                dispatch_date=current.dispatch_date if current else None,
                delivery_date=current.delivery_date if current else None,
                driver=(
                    current.driver_name_snapshot
                    if current
                    else None
                ),
                run_sheet_id=run_sheet_id,
                metadata={"failure_reason": str(error)},
            )
            raise
        self.delivery_event_recorder.record_delivery_run_sheet_closeout(run_sheet)
        return run_sheet

    def cancel_generated_delivery_run_sheet(self, run_sheet_id):
        self._ensure_workspace_ready("delivery")
        current = self.repository.get_delivery_run_sheet(run_sheet_id)
        try:
            cancelled = self.delivery_run_sheet_service.cancel_generated(run_sheet_id)
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="DELIVERY_RUN_SHEET_CANCELLED",
                entity_type="DELIVERY_RUN_SHEET",
                entity_id=run_sheet_id,
                summary=f"Delivery Run Sheet {run_sheet_id} cancellation failed.",
                dispatch_date=current.dispatch_date if current else None,
                delivery_date=current.delivery_date if current else None,
                driver=self._driver_name(current.driver_id) if current else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if current:
            self._record_delivery_run_sheet_event(
                "DELIVERY_RUN_SHEET_CANCELLED",
                current,
            )
        return cancelled

    def get_saved_delivery_run_sheet_for_export(self, run_sheet_id):
        return self.delivery_run_sheet_service.get_saved_for_export(run_sheet_id)

    def list_delivery_run_sheets_for_date_export(self, delivery_date):
        return self.delivery_run_sheet_service.list_for_date_export(delivery_date)

    def record_delivery_run_sheet_export(self, run_sheet, filename):
        return self._facade.delivery_event_recorder.record_delivery_run_sheet_export(run_sheet, filename)

    def record_delivery_run_sheets_daily_export(
        self,
        run_sheets,
        delivery_date,
        filename,
    ):
        return self._facade.delivery_event_recorder.record_delivery_run_sheets_daily_export(run_sheets, delivery_date, filename)

    def create_delivery_order(self, request):
        self._ensure_workspace_ready("delivery")
        requested_area = request.delivery_area
        if requested_area is not None:
            requested_area = self.delivery_order_area_resolver.validate_area(
                requested_area
            )
        order = self.order_service.create_order(request)
        self._record_order_event("ORDER_CREATED", order)
        if requested_area is not None:
            before = {
                "delivery_area": order.delivery_area,
                "delivery_area_override": order.delivery_area_override,
                "delivery_area_source": order.delivery_area_source,
            }
            order = self.delivery_order_area_resolver.set_override(
                order.order_id,
                requested_area,
                updated_by=self._current_logbook_actor(),
            )
            self._record_delivery_order_area_change(before, order)
        return order

    def update_delivery_order(self, order_id, request):
        self._ensure_workspace_ready("delivery")
        ensure_order_not_reserved(self.repository, None, order_id)
        existing = self.delivery_order_area_resolver.resolve_order(
            self.repository.get_order(order_id)
        )
        before = None
        if existing:
            before = {
                "delivery_area": existing.delivery_area,
                "delivery_area_override": existing.delivery_area_override,
                "delivery_area_source": existing.delivery_area_source,
            }
        order = self.order_service.update_order(order_id, request)
        self._record_order_event("ORDER_UPDATED", order)
        if (
            before
            and before["delivery_area_override"] is not None
            and order.delivery_area_override is None
        ):
            self._record_delivery_order_area_change(before, order)
        return order

    def update_delivery_order_area(self, order_id, request):
        self._ensure_workspace_ready("delivery")
        ensure_order_not_reserved(self.repository, None, order_id)
        existing = self.delivery_order_area_resolver.resolve_order(
            self.repository.get_order(order_id)
        )
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")
        before = {
            "delivery_area": existing.delivery_area,
            "delivery_area_override": existing.delivery_area_override,
            "delivery_area_source": existing.delivery_area_source,
        }
        if request.delivery_area is None:
            if existing.delivery_area_override is None:
                return existing
            updated = self.delivery_order_area_resolver.clear_override(order_id)
        else:
            requested_area = self.delivery_order_area_resolver.validate_area(
                request.delivery_area
            )
            if requested_area == existing.delivery_area:
                return existing
            updated = self.delivery_order_area_resolver.set_override(
                order_id,
                requested_area,
                updated_by=self._current_logbook_actor(),
            )
        self._record_delivery_order_area_change(before, updated)
        return updated

    def cancel_delivery_order(self, order_id):
        self._ensure_workspace_ready("delivery")
        ensure_order_not_reserved(self.repository, None, order_id)
        order = self.order_service.cancel_order(order_id)
        self._record_order_event("ORDER_CANCELLED", order)
        return order
