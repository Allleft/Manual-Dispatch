from . import FacadeApplicationService


class LegacyApplicationService(FacadeApplicationService):
    """Own legacy application orchestration."""

    def get_board(self, dispatch_date):
        return self.board_service.get_board(dispatch_date)

    def get_specifications(self):
        return self.board_service.get_specifications()

    def get_workspace_migration_status(self):
        return self.workspace_migration_readiness_service.get_status()

    def register_operator_account(self, request):
        return self.auth_service.register_operator_account(request)

    def login_operator_account(self, request):
        return self.auth_service.login_operator_account(request)

    def reset_operator_password(self, request):
        return self.auth_service.reset_operator_password(request)

    def assign_task(self, request):
        rollover_events = []
        before = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        try:
            board = self.assignment_service.assign_task(request, rollover_events)
        except Exception as error:
            self._record_failed_assignment(request, before, error)
            raise
        after = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        if request.task_type == "ORDER":
            self._record_delivery_order_date_rollovers(rollover_events)
            self._record_delivery_assignment_change(
                request.dispatch_date,
                request.task_id,
                before,
                after,
            )
        elif request.task_type == "OPSHOP_PICKUP":
            self._record_opshop_assignment_change(
                request.dispatch_date,
                request.task_id,
                before,
                after,
            )
        return board

    def unassign_task(self, request):
        rollover_events = []
        before = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        try:
            board = self.assignment_service.unassign_task(request, rollover_events)
        except Exception as error:
            self._record_failed_assignment(request, before, error, unassign=True)
            raise
        if before and request.task_type == "ORDER":
            self._record_delivery_assignment_change(
                request.dispatch_date,
                request.task_id,
                before,
                None,
            )
            self._record_delivery_order_date_rollovers(rollover_events)
        elif request.task_type == "ORDER":
            self._record_delivery_order_date_rollovers(rollover_events)
        elif before and request.task_type == "OPSHOP_PICKUP":
            self._record_opshop_assignment_change(
                request.dispatch_date,
                request.task_id,
                before,
                None,
            )
        return board

    def assign_vehicle_to_driver(self, request):
        delivery_date = request.delivery_date or request.dispatch_date
        before = self._vehicle_assignment_snapshot(
            request.dispatch_date,
            delivery_date,
            request.driver_id,
        )
        try:
            board = self.assignment_service.assign_vehicle_to_driver(request)
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
                dispatch_date=request.dispatch_date,
                delivery_date=delivery_date,
                driver=self._driver_name(request.driver_id),
                vehicle=self._vehicle_label(request.vehicle_id),
                metadata={"failure_reason": str(error)},
            )
            raise
        self._record_vehicle_assignment_change(
            request.dispatch_date,
            delivery_date,
            request.driver_id,
            before,
            self._vehicle_assignment_snapshot(
                request.dispatch_date,
                delivery_date,
                request.driver_id,
            ),
        )
        return board

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        effective_delivery_date = delivery_date or dispatch_date
        before = self._vehicle_assignment_snapshot(
            dispatch_date,
            effective_delivery_date,
            driver_id,
        )
        try:
            result = self.assignment_service.clear_driver_vehicle_assignment(
                dispatch_date,
                driver_id,
                delivery_date,
            )
        except Exception as error:
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="VEHICLE_CLEARED",
                entity_type="VEHICLE",
                entity_id=before.get("vehicle_id") if before else None,
                summary=f"Vehicle clear for {self._driver_name(driver_id)} failed.",
                dispatch_date=dispatch_date,
                delivery_date=effective_delivery_date,
                driver=self._driver_name(driver_id),
                vehicle=before.get("vehicle") if before else None,
                metadata={"failure_reason": str(error)},
            )
            raise
        if before:
            self._record_vehicle_assignment_change(
                dispatch_date,
                effective_delivery_date,
                driver_id,
                before,
                None,
            )
        return result

    def create_order(self, request):
        order = self.order_service.create_order(request)
        self._record_order_event("ORDER_CREATED", order)
        return order

    def update_order(self, order_id, request):
        order = self.order_service.update_order(order_id, request)
        self._record_order_event("ORDER_UPDATED", order)
        return order

    def cancel_order(self, order_id):
        order = self.order_service.cancel_order(order_id)
        self._record_order_event("ORDER_CANCELLED", order)
        return order

    def save_final_trip_summary(self, request):
        return self.final_summary_service.save_final_trip_summary(request)

    def create_generated_final_trip_summary(self, request):
        return self.final_summary_service.create_generated_final_trip_summary(request)

    def save_generated_final_trip_summary(
        self,
        summary_id,
        saved_by_account_name,
        saved_by_account_id=None,
    ):
        return self.final_summary_service.save_generated_final_trip_summary(
            summary_id,
            saved_by_account_name,
            saved_by_account_id,
        )

    def cancel_generated_final_trip_summary(self, summary_id):
        return self.final_summary_service.cancel_generated_final_trip_summary(summary_id)

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return self.final_summary_service.list_final_trip_summaries(
            dispatch_date,
            delivery_date,
        )

    def list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return self.final_summary_service.list_generated_final_trip_summaries(
            dispatch_date,
            delivery_date,
        )

    def list_final_summary_dates(self):
        return self.final_summary_service.list_final_summary_dates()

    def get_final_trip_summary(self, summary_id):
        return self.final_summary_service.get_final_trip_summary(summary_id)

    def get_saved_final_trip_summary_for_export(self, summary_id):
        return self.final_summary_service.get_saved_final_trip_summary_for_export(
            summary_id
        )
