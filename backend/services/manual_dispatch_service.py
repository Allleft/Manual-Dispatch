from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.services.manual_dispatch.assignment_service import AssignmentService
from backend.services.manual_dispatch.auth_service import OperatorAuthService
from backend.services.manual_dispatch.board_service import BoardService
from backend.services.manual_dispatch.final_summary_service import FinalSummaryService
from backend.services.manual_dispatch.id_generation import ManualDispatchIdGenerator
from backend.services.manual_dispatch.order_service import OrderService
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService
from backend.services.manual_dispatch.specification_service import SpecificationService
from backend.services.manual_dispatch.validation import ManualDispatchValidator


class ManualDispatchService:
    """Stable facade for Manual Dispatch API routes and tests."""

    def __init__(self, repository=None):
        self.repository = repository or InMemoryManualDispatchRepository()
        self.board_service = BoardService(self.repository)
        self.validator = ManualDispatchValidator(self.repository)
        self.id_generator = ManualDispatchIdGenerator(self.repository)
        self.auth_service = OperatorAuthService(self.repository)
        self.assignment_service = AssignmentService(
            self.repository,
            self.validator,
            self.board_service,
        )
        self.order_service = OrderService(self.repository, self.id_generator)
        self.opshop_pickup_service = OpShopPickupService(self.repository)
        self.specification_service = SpecificationService(
            self.repository,
            self.validator,
            self.id_generator,
            self.board_service,
        )
        self.final_summary_service = FinalSummaryService(
            self.repository,
            self.validator,
        )

    def get_board(self, dispatch_date):
        return self.board_service.get_board(dispatch_date)

    def get_specifications(self):
        return self.board_service.get_specifications()

    def register_operator_account(self, request):
        return self.auth_service.register_operator_account(request)

    def login_operator_account(self, request):
        return self.auth_service.login_operator_account(request)

    def reset_operator_password(self, request):
        return self.auth_service.reset_operator_password(request)

    def assign_task(self, request):
        return self.assignment_service.assign_task(request)

    def unassign_task(self, request):
        return self.assignment_service.unassign_task(request)

    def assign_vehicle_to_driver(self, request):
        return self.assignment_service.assign_vehicle_to_driver(request)

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        return self.assignment_service.clear_driver_vehicle_assignment(
            dispatch_date,
            driver_id,
            delivery_date,
        )

    def create_order(self, request):
        return self.order_service.create_order(request)

    def update_order(self, order_id, request):
        return self.order_service.update_order(order_id, request)

    def cancel_order(self, order_id):
        return self.order_service.cancel_order(order_id)

    def ensure_opshop_pickup_tasks_for_window(self, request):
        return self.opshop_pickup_service.ensure_opshop_pickup_tasks_for_window(request)

    def create_driver(self, request):
        return self.specification_service.create_driver(request)

    def update_driver(self, driver_id, request):
        return self.specification_service.update_driver(driver_id, request)

    def delete_driver(self, driver_id):
        return self.specification_service.delete_driver(driver_id)

    def create_vehicle(self, request):
        return self.specification_service.create_vehicle(request)

    def update_vehicle(self, vehicle_id, request):
        return self.specification_service.update_vehicle(vehicle_id, request)

    def delete_vehicle(self, vehicle_id):
        return self.specification_service.delete_vehicle(vehicle_id)

    def save_final_trip_summary(self, request):
        return self.final_summary_service.save_final_trip_summary(request)

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return self.final_summary_service.list_final_trip_summaries(
            dispatch_date,
            delivery_date,
        )

    def list_final_summary_dates(self):
        return self.final_summary_service.list_final_summary_dates()

    def get_final_trip_summary(self, summary_id):
        return self.final_summary_service.get_final_trip_summary(summary_id)
