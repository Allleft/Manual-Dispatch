from contextlib import contextmanager
from backend.repositories.in_memory_manual_dispatch_repository import InMemoryManualDispatchRepository
from backend.services.manual_dispatch.assignment_service import AssignmentService
from backend.services.manual_dispatch.auth_service import OperatorAuthService
from backend.services.manual_dispatch.board_service import BoardService
from backend.services.manual_dispatch.delivery_run_sheet_service import DeliveryRunSheetService
from backend.services.manual_dispatch.delivery_workspace_board_service import DeliveryWorkspaceBoardService
from backend.services.manual_dispatch.delivery_workspace_mutation_service import DeliveryWorkspaceMutationService
from backend.services.manual_dispatch.final_summary_service import FinalSummaryService
from backend.services.manual_dispatch.id_generation import ManualDispatchIdGenerator
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch.order_service import OrderService
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService
from backend.services.manual_dispatch.opshop_pickup_collection_service import OpShopPickupCollectionService
from backend.services.manual_dispatch.opshop_workspace_board_service import OpShopWorkspaceBoardService
from backend.services.manual_dispatch.opshop_workspace_mutation_service import OpShopWorkspaceMutationService
from backend.services.manual_dispatch.opshop_template_service import OpShopTemplateService
from backend.services.manual_dispatch.specification_service import SpecificationService
from backend.services.manual_dispatch.validation import ManualDispatchValidator
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationReadinessService
from backend.services.manual_dispatch.application.attache_import_application_service import AttacheImportApplicationService
from backend.services.manual_dispatch.application.delivery_application_service import DeliveryApplicationService
from backend.services.manual_dispatch.application.legacy_application_service import LegacyApplicationService
from backend.services.manual_dispatch.application.opshop_application_service import OpShopApplicationService
from backend.services.manual_dispatch.application.specification_application_service import SpecificationApplicationService
from backend.services.manual_dispatch.audit.audit_context import AuditContext, LOGBOOK_ACTOR_CONTEXT
from backend.services.manual_dispatch.audit.delivery_event_recorder import DeliveryEventRecorder
from backend.services.manual_dispatch.audit.logbook_recorder import (
    LOGGER,
    LOGBOOK_DATE_FIELDS,
    REJECTED_LOGBOOK_DATE_FIELDS_KEY,
    LogbookRecorder,
    _canonical_failed_logbook_date,
)
from backend.services.manual_dispatch.audit.opshop_event_recorder import OpShopEventRecorder
from backend.services.manual_dispatch.audit.specification_event_recorder import SpecificationEventRecorder


class ManualDispatchService:
    """Stable facade for Manual Dispatch API routes and tests."""

    def __init__(self, repository=None, logbook=None):
        self.repository = repository or InMemoryManualDispatchRepository()
        self.logbook = logbook or LogbookFileService()
        self.opshop_pickup_service = OpShopPickupService(self.repository)
        self.board_service = BoardService(
            self.repository,
            self.opshop_pickup_service,
        )
        self.validator = ManualDispatchValidator(self.repository)
        self.opshop_template_service = OpShopTemplateService(
            self.repository,
            self.validator,
        )
        self.id_generator = ManualDispatchIdGenerator(self.repository)
        self.auth_service = OperatorAuthService(self.repository)
        self.assignment_service = AssignmentService(
            self.repository,
            self.validator,
            self.board_service,
        )
        self.order_service = OrderService(self.repository, self.id_generator)
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
        self.delivery_run_sheet_service = DeliveryRunSheetService(
            self.repository,
            self.validator,
        )
        self.opshop_pickup_collection_service = OpShopPickupCollectionService(
            self.repository,
            self.validator,
        )
        self.delivery_workspace_board_service = DeliveryWorkspaceBoardService(
            self.repository
        )
        self.opshop_workspace_board_service = OpShopWorkspaceBoardService(
            self.repository,
            self.opshop_pickup_service,
        )
        self.delivery_workspace_mutation_service = DeliveryWorkspaceMutationService(
            self.repository,
            self.validator,
            self.delivery_workspace_board_service,
        )
        self.opshop_workspace_mutation_service = OpShopWorkspaceMutationService(
            self.repository,
            self.validator,
            self.opshop_workspace_board_service,
        )
        self.workspace_migration_readiness_service = (
            WorkspaceMigrationReadinessService(self.repository)
        )
        self.audit_context = AuditContext()
        self.logbook_recorder = LogbookRecorder(self)
        self.delivery_event_recorder = DeliveryEventRecorder(self)
        self.opshop_event_recorder = OpShopEventRecorder(self)
        self.specification_event_recorder = SpecificationEventRecorder(self)
        self.delivery_application_service = DeliveryApplicationService(self)
        self.opshop_application_service = OpShopApplicationService(self)
        self.specification_application_service = SpecificationApplicationService(self)
        self.legacy_application_service = LegacyApplicationService(self)
        self.attache_import_application_service = AttacheImportApplicationService(self)

    @contextmanager
    def logbook_actor(self, actor):
        with self.audit_context.actor(actor):
            yield

    def get_board(self, dispatch_date):
        return self.legacy_application_service.get_board(dispatch_date)

    def get_specifications(self):
        return self.legacy_application_service.get_specifications()

    def get_delivery_workspace_board(self, dispatch_date):
        return self.delivery_application_service.get_delivery_workspace_board(dispatch_date)

    def get_delivery_trip_summary_board(self, delivery_date):
        return self.delivery_application_service.get_delivery_trip_summary_board(delivery_date)

    def get_opshop_workspace_board(self, dispatch_date):
        return self.opshop_application_service.get_opshop_workspace_board(dispatch_date)

    def get_opshop_trip_summary_board(self, pickup_date):
        return self.opshop_application_service.get_opshop_trip_summary_board(pickup_date)

    def get_workspace_migration_status(self):
        return self.legacy_application_service.get_workspace_migration_status()

    def get_shared_specifications(self):
        return self.specification_application_service.get_shared_specifications()

    def get_delivery_specifications(self):
        return self.specification_application_service.get_delivery_specifications()

    def assign_delivery_workspace_order(self, request):
        return self.delivery_application_service.assign_delivery_workspace_order(request)

    def unassign_delivery_workspace_order(self, request):
        return self.delivery_application_service.unassign_delivery_workspace_order(request)

    def assign_delivery_workspace_vehicle(self, request):
        return self.delivery_application_service.assign_delivery_workspace_vehicle(request)

    def clear_delivery_workspace_vehicle(self, request):
        return self.delivery_application_service.clear_delivery_workspace_vehicle(request)

    def apply_opshop_workspace_assignments(self, request):
        return self.opshop_application_service.apply_opshop_workspace_assignments(request)

    def unassign_opshop_workspace_pickup(self, request):
        return self.opshop_application_service.unassign_opshop_workspace_pickup(request)

    def assign_opshop_workspace_countryside_route_group(
        self,
        route_group_id,
        request,
    ):
        return self.opshop_application_service.assign_opshop_workspace_countryside_route_group(route_group_id, request)

    def create_generated_delivery_run_sheet(self, request):
        return self.delivery_application_service.create_generated_delivery_run_sheet(request)

    def list_delivery_run_sheets(
        self,
        dispatch_date=None,
        delivery_date=None,
        status=None,
    ):
        return self.delivery_application_service.list_delivery_run_sheets(dispatch_date, delivery_date, status)

    def get_delivery_run_sheet(self, run_sheet_id):
        return self.delivery_application_service.get_delivery_run_sheet(run_sheet_id)

    def save_generated_delivery_run_sheet(self, run_sheet_id, request):
        return self.delivery_application_service.save_generated_delivery_run_sheet(run_sheet_id, request)

    def cancel_generated_delivery_run_sheet(self, run_sheet_id):
        return self.delivery_application_service.cancel_generated_delivery_run_sheet(run_sheet_id)

    def get_saved_delivery_run_sheet_for_export(self, run_sheet_id):
        return self.delivery_application_service.get_saved_delivery_run_sheet_for_export(run_sheet_id)

    def list_delivery_run_sheets_for_date_export(self, delivery_date):
        return self.delivery_application_service.list_delivery_run_sheets_for_date_export(delivery_date)

    def create_generated_opshop_pickup_collection(self, request):
        return self.opshop_application_service.create_generated_opshop_pickup_collection(request)

    def list_opshop_pickup_collections(
        self,
        dispatch_date=None,
        pickup_date=None,
        status=None,
    ):
        return self.opshop_application_service.list_opshop_pickup_collections(dispatch_date, pickup_date, status)

    def get_opshop_pickup_collection(self, collection_id):
        return self.opshop_application_service.get_opshop_pickup_collection(collection_id)

    def update_opshop_pickup_collection_rows(self, collection_id, request):
        return self.opshop_application_service.update_opshop_pickup_collection_rows(
            collection_id,
            request,
        )

    def save_generated_opshop_pickup_collection(self, collection_id, request):
        return self.opshop_application_service.save_generated_opshop_pickup_collection(collection_id, request)

    def cancel_generated_opshop_pickup_collection(self, collection_id):
        return self.opshop_application_service.cancel_generated_opshop_pickup_collection(collection_id)

    def get_opshop_pickup_collection_for_export(self, collection_id):
        return self.opshop_application_service.get_opshop_pickup_collection_for_export(collection_id)

    def get_saved_opshop_pickup_collection_for_export(self, collection_id):
        return self.opshop_application_service.get_saved_opshop_pickup_collection_for_export(collection_id)

    def list_opshop_pickup_collections_for_date_export(
        self,
        pickup_date,
        dispatch_date=None,
        status=None,
    ):
        return self.opshop_application_service.list_opshop_pickup_collections_for_date_export(pickup_date, dispatch_date, status)

    def _ensure_workspace_ready(self, workspace):
        return self.workspace_migration_readiness_service.ensure_ready(workspace)

    def _record_logbook(self, **entry):
        return self.logbook_recorder._record_logbook(**entry)

    @staticmethod
    def _current_logbook_actor():
        return LOGBOOK_ACTOR_CONTEXT.get() or "Unknown"

    def _record_failed_logbook(self, **entry):
        return self.logbook_recorder._record_failed_logbook(**entry)

    def _record_order_event(self, action, order):
        return self.delivery_event_recorder._record_order_event(action, order)

    def _record_delivery_assignment_change(
        self,
        dispatch_date,
        order_id,
        before,
        after,
    ):
        return self.delivery_event_recorder._record_delivery_assignment_change(dispatch_date, order_id, before, after)

    def _record_opshop_assignment_change(
        self,
        dispatch_date,
        pickup_task_id,
        before,
        after,
    ):
        return self.opshop_event_recorder._record_opshop_assignment_change(dispatch_date, pickup_task_id, before, after)

    def _record_vehicle_assignment_change(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
        before,
        after,
    ):
        return self.delivery_event_recorder._record_vehicle_assignment_change(dispatch_date, delivery_date, driver_id, before, after)

    @staticmethod
    def _delivery_run_sheet_counts(run_sheet):
        return DeliveryEventRecorder._delivery_run_sheet_counts(run_sheet)

    @staticmethod
    def _opshop_collection_counts(collection):
        return OpShopEventRecorder._opshop_collection_counts(collection)

    def record_delivery_run_sheet_export(self, run_sheet, filename):
        return self.delivery_application_service.record_delivery_run_sheet_export(run_sheet, filename)

    def record_delivery_run_sheets_daily_export(
        self,
        run_sheets,
        delivery_date,
        filename,
    ):
        return self.delivery_application_service.record_delivery_run_sheets_daily_export(run_sheets, delivery_date, filename)

    def record_opshop_pickup_collection_export(self, collection, filename):
        return self.opshop_application_service.record_opshop_pickup_collection_export(collection, filename)

    def record_opshop_pickup_collections_daily_export(
        self,
        collections,
        pickup_date,
        filename,
        dispatch_date=None,
        status=None,
    ):
        return self.opshop_application_service.record_opshop_pickup_collections_daily_export(collections, pickup_date, filename, dispatch_date, status)

    def record_attache_import_confirmation(self, rows, outcome):
        return self.attache_import_application_service.record_attache_import_confirmation(rows, outcome)

    def _record_delivery_run_sheet_event(self, action, run_sheet, actor=None):
        return self.delivery_event_recorder._record_delivery_run_sheet_event(action, run_sheet, actor)

    def _record_opshop_collection_event(self, action, collection, actor=None):
        return self.opshop_event_recorder._record_opshop_collection_event(action, collection, actor)

    def _record_opshop_task_event(self, action, task):
        return self.opshop_event_recorder._record_opshop_task_event(action, task)

    def _record_failed_assignment(self, request, before, error, unassign=False):
        return self.delivery_event_recorder._record_failed_assignment(request, before, error, unassign)

    def _assignment_snapshot(self, _dispatch_date, task_type, task_id):
        return self.delivery_event_recorder._assignment_snapshot(_dispatch_date, task_type, task_id)

    def _assignment_log_metadata(self, snapshot):
        return self.delivery_event_recorder._assignment_log_metadata(snapshot)

    def _assignment_label(self, snapshot):
        return self.delivery_event_recorder._assignment_label(snapshot)

    def _vehicle_assignment_snapshot(self, _dispatch_date, delivery_date, driver_id):
        return self.delivery_event_recorder._vehicle_assignment_snapshot(_dispatch_date, delivery_date, driver_id)

    def _driver_name(self, driver_id):
        return self.specification_event_recorder._driver_name(driver_id)

    def _vehicle_label(self, vehicle_id):
        return self.specification_event_recorder._vehicle_label(vehicle_id)

    def _order_entity_id(self, order):
        return self.delivery_event_recorder._order_entity_id(order)

    def _order_entity_id_by_id(self, order_id):
        return self.delivery_event_recorder._order_entity_id_by_id(order_id)

    def _order_delivery_date(self, order_id):
        return self.delivery_event_recorder._order_delivery_date(order_id)

    def _opshop_pickup_name(self, pickup_task_id):
        return self.opshop_event_recorder._opshop_pickup_name(pickup_task_id)

    def _opshop_pickup_date(self, pickup_task_id):
        return self.opshop_event_recorder._opshop_pickup_date(pickup_task_id)

    def _opshop_assignment_pickup_date(self, assignments):
        return self.opshop_event_recorder._opshop_assignment_pickup_date(assignments)

    def _route_group_name(self, route_group_id):
        return self.opshop_event_recorder._route_group_name(route_group_id)

    @staticmethod
    def _trip_label(trip_no):
        return DeliveryEventRecorder._trip_label(trip_no)

    def register_operator_account(self, request):
        return self.legacy_application_service.register_operator_account(request)

    def login_operator_account(self, request):
        return self.legacy_application_service.login_operator_account(request)

    def reset_operator_password(self, request):
        return self.legacy_application_service.reset_operator_password(request)

    def assign_task(self, request):
        return self.legacy_application_service.assign_task(request)

    def unassign_task(self, request):
        return self.legacy_application_service.unassign_task(request)

    def assign_vehicle_to_driver(self, request):
        return self.legacy_application_service.assign_vehicle_to_driver(request)

    def clear_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        return self.legacy_application_service.clear_driver_vehicle_assignment(dispatch_date, driver_id, delivery_date)

    def create_order(self, request):
        return self.legacy_application_service.create_order(request)

    def update_order(self, order_id, request):
        return self.legacy_application_service.update_order(order_id, request)

    def cancel_order(self, order_id):
        return self.legacy_application_service.cancel_order(order_id)

    def create_delivery_order(self, request):
        return self.delivery_application_service.create_delivery_order(request)

    def update_delivery_order(self, order_id, request):
        return self.delivery_application_service.update_delivery_order(order_id, request)

    def cancel_delivery_order(self, order_id):
        return self.delivery_application_service.cancel_delivery_order(order_id)

    def ensure_opshop_pickup_tasks_for_window(self, request):
        return self.opshop_application_service.ensure_opshop_pickup_tasks_for_window(request)

    def list_opshop_pickup_schedule_candidates(self, run_type="scheduled"):
        return self.opshop_application_service.list_opshop_pickup_schedule_candidates(run_type)

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        return self.opshop_application_service.list_opshop_templates(run_type, include_inactive)

    def list_countryside_route_groups(self, include_inactive=False):
        return self.opshop_application_service.list_countryside_route_groups(include_inactive)

    @staticmethod
    def _template_business_snapshot(template):
        return OpShopEventRecorder._template_business_snapshot(template)

    def _find_opshop_template(self, schedule_id):
        return self.opshop_event_recorder._find_opshop_template(schedule_id)

    @staticmethod
    def _template_category(template):
        return OpShopEventRecorder._template_category(template)

    def _record_template_event(
        self,
        suffix,
        template,
        before=None,
        after=None,
    ):
        return self.opshop_event_recorder._record_template_event(suffix, template, before, after)

    def create_countryside_route_group(self, request):
        return self.opshop_application_service.create_countryside_route_group(request)

    def update_countryside_route_group(self, route_group_id, request):
        return self.opshop_application_service.update_countryside_route_group(route_group_id, request)

    def disable_countryside_route_group(self, route_group_id):
        return self.opshop_application_service.disable_countryside_route_group(route_group_id)

    def list_countryside_route_memberships(self, route_group_id):
        return self.opshop_application_service.list_countryside_route_memberships(route_group_id)

    def add_countryside_route_membership(self, route_group_id, request):
        return self.opshop_application_service.add_countryside_route_membership(route_group_id, request)

    def remove_countryside_route_membership(self, schedule_id):
        return self.opshop_application_service.remove_countryside_route_membership(schedule_id)

    def move_countryside_route_membership(self, schedule_id, request):
        return self.opshop_application_service.move_countryside_route_membership(schedule_id, request)

    def create_opshop_template(self, request):
        return self.opshop_application_service.create_opshop_template(request)

    def update_opshop_template(self, schedule_id, request):
        return self.opshop_application_service.update_opshop_template(schedule_id, request)

    def disable_opshop_template(self, schedule_id):
        return self.opshop_application_service.disable_opshop_template(schedule_id)

    def create_opshop_pickup_task(self, request):
        return self.opshop_application_service.create_opshop_pickup_task(request)

    def create_oncall_opshop_pickup_task(self, request):
        return self.opshop_application_service.create_oncall_opshop_pickup_task(request)

    def update_opshop_pickup_task(self, pickup_task_id, request):
        return self.opshop_application_service.update_opshop_pickup_task(pickup_task_id, request)

    def delete_opshop_pickup_task(self, pickup_task_id):
        return self.opshop_application_service.delete_opshop_pickup_task(pickup_task_id)

    def apply_weekly_opshop_pickup_assignments(self, request):
        return self.opshop_application_service.apply_weekly_opshop_pickup_assignments(request)

    def apply_oncall_opshop_pickup_assignments(self, request):
        return self.opshop_application_service.apply_oncall_opshop_pickup_assignments(request)

    def apply_countryside_opshop_pickup_assignments(self, request):
        return self.opshop_application_service.apply_countryside_opshop_pickup_assignments(request)

    def assign_countryside_route_group_pickups(self, route_group_id, request):
        return self.opshop_application_service.assign_countryside_route_group_pickups(route_group_id, request)

    def create_driver(self, request):
        return self.specification_application_service.create_driver(request)

    def update_driver(self, driver_id, request):
        return self.specification_application_service.update_driver(driver_id, request)

    def delete_driver(self, driver_id):
        return self.specification_application_service.delete_driver(driver_id)

    def create_vehicle(self, request):
        return self.specification_application_service.create_vehicle(request)

    def update_vehicle(self, vehicle_id, request):
        return self.specification_application_service.update_vehicle(vehicle_id, request)

    def delete_vehicle(self, vehicle_id):
        return self.specification_application_service.delete_vehicle(vehicle_id)

    def create_delivery_driver(self, request):
        return self.specification_application_service.create_delivery_driver(request)

    def update_delivery_driver(self, driver_id, request):
        return self.specification_application_service.update_delivery_driver(driver_id, request)

    def delete_delivery_driver(self, driver_id):
        return self.specification_application_service.delete_delivery_driver(driver_id)

    def create_delivery_vehicle(self, request):
        return self.specification_application_service.create_delivery_vehicle(request)

    def update_delivery_vehicle(self, vehicle_id, request):
        return self.specification_application_service.update_delivery_vehicle(vehicle_id, request)

    def delete_delivery_vehicle(self, vehicle_id):
        return self.specification_application_service.delete_delivery_vehicle(vehicle_id)

    def _ensure_driver_not_used_by_delivery_run_sheet(self, driver_id):
        return self.specification_application_service._ensure_driver_not_used_by_delivery_run_sheet(driver_id)

    def _ensure_vehicle_not_used_by_delivery_run_sheet(self, vehicle_id):
        return self.specification_application_service._ensure_vehicle_not_used_by_delivery_run_sheet(vehicle_id)

    def save_final_trip_summary(self, request):
        return self.legacy_application_service.save_final_trip_summary(request)

    def create_generated_final_trip_summary(self, request):
        return self.legacy_application_service.create_generated_final_trip_summary(request)

    def save_generated_final_trip_summary(
        self,
        summary_id,
        saved_by_account_name,
        saved_by_account_id=None,
    ):
        return self.legacy_application_service.save_generated_final_trip_summary(summary_id, saved_by_account_name, saved_by_account_id)

    def cancel_generated_final_trip_summary(self, summary_id):
        return self.legacy_application_service.cancel_generated_final_trip_summary(summary_id)

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return self.legacy_application_service.list_final_trip_summaries(dispatch_date, delivery_date)

    def list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return self.legacy_application_service.list_generated_final_trip_summaries(dispatch_date, delivery_date)

    def list_final_summary_dates(self):
        return self.legacy_application_service.list_final_summary_dates()

    def get_final_trip_summary(self, summary_id):
        return self.legacy_application_service.get_final_trip_summary(summary_id)

    def get_saved_final_trip_summary_for_export(self, summary_id):
        return self.legacy_application_service.get_saved_final_trip_summary_for_export(summary_id)
