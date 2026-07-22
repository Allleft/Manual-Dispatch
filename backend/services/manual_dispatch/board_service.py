from backend.schemas import ManualDispatchBoardResponse, ManualDispatchSpecificationResponse
from backend.services.manual_dispatch.final_summary_lock import (
    is_driver_delivery_date_finalized,
)
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService
from backend.services.manual_dispatch.normalization import clean_required_iso_date
from backend.services.manual_dispatch.suburb_distance_service import (
    get_estimated_distance_km,
)


class BoardService:
    def __init__(self, repository, opshop_pickup_service=None):
        self.repository = repository
        self.opshop_pickup_service = opshop_pickup_service or OpShopPickupService(
            repository
        )

    def get_board(self, dispatch_date):
        dispatch_date = clean_required_iso_date(dispatch_date, "dispatch_date")
        scheduled_generation = self.opshop_pickup_service.ensure_regular_opshop_pickup_tasks_for_week(
            dispatch_date
        )
        generated_summaries = self.repository.list_generated_final_trip_summaries(
            dispatch_date
        )
        generated_task_keys = self._task_keys_from_final_summaries(generated_summaries)
        orders = self.repository.list_orders()
        orders = [
            order
            for order in orders
            if ("ORDER", order.order_id) not in generated_task_keys
        ]
        for order in orders:
            order.estimated_distance_km_from_warehouse = get_estimated_distance_km(
                order.suburb
            )

        scheduled_pickups = self.repository.list_scheduled_opshop_pickup_board_items_for_window(
            scheduled_generation.window_start,
            scheduled_generation.window_end,
        )
        for pickup in scheduled_pickups:
            pickup.assigned_to_locked = pickup.pickup_date < dispatch_date
        oncall_pickups = self.repository.list_oncall_opshop_pickup_board_items(
            dispatch_date
        )
        for pickup in oncall_pickups:
            pickup.assigned_to_locked = pickup.pickup_date < dispatch_date
        countryside_pickups = self.repository.list_countryside_opshop_pickup_board_items(
            dispatch_date
        )
        for pickup in countryside_pickups:
            pickup.assigned_to_locked = pickup.pickup_date < dispatch_date
        assignments = [
            assignment
            for assignment in self.repository.list_assignments(dispatch_date)
            if not self._is_finalized_assignment(dispatch_date, assignment)
            and (assignment.task_type, assignment.task_id) not in generated_task_keys
        ]
        assigned_pickups = [
            pickup
            for pickup in self.repository.list_assigned_opshop_pickup_board_items(
                dispatch_date
            )
            if not is_driver_delivery_date_finalized(
                self.repository,
                dispatch_date,
                pickup.driver_id,
                pickup.pickup_date,
            )
            and ("OPSHOP_PICKUP", pickup.pickup_task_id) not in generated_task_keys
        ]
        finalized_driver_delivery_dates = [
            {
                "driver_id": summary.driver_id,
                "delivery_date": summary.delivery_date,
            }
            for summary in self.repository.list_final_trip_summaries(dispatch_date)
            if summary.status == "SAVED"
        ]
        finalized_opshop_assignments = (
            self.repository.list_finalized_opshop_pickup_assignments(dispatch_date)
        )
        self._apply_finalized_opshop_pickup_assignments(
            [scheduled_pickups, oncall_pickups, countryside_pickups],
            finalized_opshop_assignments,
        )

        return ManualDispatchBoardResponse(
            dispatch_date=dispatch_date,
            orders=orders,
            drivers=self.repository.list_drivers(),
            vehicles=self.repository.list_vehicles(),
            assignments=assignments,
            driver_vehicle_assignments=self.repository.list_driver_vehicle_assignments(
                dispatch_date
            ),
            opshop_pickups=[],
            assigned_opshop_pickups=assigned_pickups,
            scheduled_opshop_pickups=scheduled_pickups,
            oncall_opshop_pickups=oncall_pickups,
            countryside_route_groups=self.repository.list_countryside_route_groups(),
            countryside_opshop_pickups=countryside_pickups,
            opshop_regular_list_window_start=scheduled_generation.window_start,
            opshop_regular_list_window_end=scheduled_generation.window_end,
            finalized_driver_delivery_dates=finalized_driver_delivery_dates,
            generated_final_trip_summaries=generated_summaries,
        )

    def get_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )

    def _is_finalized_assignment(self, dispatch_date, assignment):
        if assignment.task_type == "ORDER":
            task = self.repository.get_order(assignment.task_id)
            delivery_date = task.delivery_date if task else None
        elif assignment.task_type == "OPSHOP_PICKUP":
            task = self.repository.get_opshop_pickup_task(assignment.task_id)
            delivery_date = task.pickup_date if task else None
        else:
            return False
        return bool(
            delivery_date
            and is_driver_delivery_date_finalized(
                self.repository,
                dispatch_date,
                assignment.driver_id,
                delivery_date,
            )
        )

    def _apply_finalized_opshop_pickup_assignments(self, pickup_lists, finalized_assignments):
        for pickups in pickup_lists:
            for pickup in pickups:
                finalized = finalized_assignments.get(pickup.pickup_task_id)
                if not finalized or finalized.get("delivery_date") != pickup.pickup_date:
                    continue
                driver_id = finalized.get("driver_id")
                if not driver_id:
                    continue
                pickup.assigned_driver_id = driver_id
                pickup.assigned_driver_name = finalized.get("driver_name") or pickup.assigned_driver_name
                if not pickup.driver_id:
                    pickup.driver_id = driver_id
                pickup.is_assigned = True
                pickup.assigned_to_locked = True

    def _task_keys_from_final_summaries(self, summaries):
        task_keys = set()
        for summary in summaries:
            for trip in summary.trips or []:
                for order in trip.orders or []:
                    if order.task_type and order.task_id:
                        task_keys.add((order.task_type, order.task_id))
            for pickup in summary.opshop_pickups or []:
                if pickup.pickup_task_id_snapshot:
                    task_keys.add(("OPSHOP_PICKUP", pickup.pickup_task_id_snapshot))
        return task_keys
