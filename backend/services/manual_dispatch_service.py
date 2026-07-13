import logging
from contextlib import contextmanager
from contextvars import ContextVar

from backend.schemas import ManualDispatchSpecificationResponse
from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.services.manual_dispatch.assignment_service import AssignmentService
from backend.services.manual_dispatch.auth_service import OperatorAuthService
from backend.services.manual_dispatch.board_service import BoardService
from backend.services.manual_dispatch.delivery_run_sheet_service import (
    DeliveryRunSheetService,
)
from backend.services.manual_dispatch.delivery_run_sheet_lock import (
    ensure_order_not_reserved,
)
from backend.services.manual_dispatch.delivery_workspace_board_service import (
    DeliveryWorkspaceBoardService,
)
from backend.services.manual_dispatch.delivery_workspace_mutation_service import (
    DeliveryWorkspaceMutationService,
)
from backend.services.manual_dispatch.final_summary_service import FinalSummaryService
from backend.services.manual_dispatch.id_generation import ManualDispatchIdGenerator
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch.order_service import OrderService
from backend.services.manual_dispatch.opshop_pickup_service import OpShopPickupService
from backend.services.manual_dispatch.opshop_pickup_collection_service import (
    OpShopPickupCollectionService,
)
from backend.services.manual_dispatch.opshop_workspace_board_service import (
    OpShopWorkspaceBoardService,
)
from backend.services.manual_dispatch.opshop_workspace_mutation_service import (
    OpShopWorkspaceMutationService,
)
from backend.services.manual_dispatch.opshop_template_service import OpShopTemplateService
from backend.services.manual_dispatch.specification_service import SpecificationService
from backend.services.manual_dispatch.validation import ManualDispatchValidator
from backend.services.manual_dispatch.workspace_migration_readiness_service import (
    WorkspaceMigrationReadinessService,
)


LOGGER = logging.getLogger(__name__)
LOGBOOK_ACTOR_CONTEXT = ContextVar("manual_dispatch_logbook_actor", default=None)


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

    @contextmanager
    def logbook_actor(self, actor):
        token = LOGBOOK_ACTOR_CONTEXT.set(actor or None)
        try:
            yield
        finally:
            LOGBOOK_ACTOR_CONTEXT.reset(token)

    def get_board(self, dispatch_date):
        return self.board_service.get_board(dispatch_date)

    def get_specifications(self):
        return self.board_service.get_specifications()

    def get_delivery_workspace_board(self, dispatch_date):
        self._ensure_workspace_ready("delivery")
        return self.delivery_workspace_board_service.get_board(dispatch_date)

    def get_delivery_trip_summary_board(self, dispatch_date, delivery_date):
        self._ensure_workspace_ready("delivery")
        return self.delivery_workspace_board_service.get_trip_summary_board(
            dispatch_date,
            delivery_date
        )

    def get_opshop_workspace_board(self, dispatch_date):
        self._ensure_workspace_ready("opshop")
        return self.opshop_workspace_board_service.get_board(dispatch_date)

    def get_opshop_trip_summary_board(self, dispatch_date, pickup_date):
        self._ensure_workspace_ready("opshop")
        return self.opshop_workspace_board_service.get_trip_summary_board(
            dispatch_date,
            pickup_date
        )

    def get_workspace_migration_status(self):
        return self.workspace_migration_readiness_service.get_status()

    def get_shared_specifications(self):
        return ManualDispatchSpecificationResponse(
            drivers=self.repository.list_specification_drivers(),
            vehicles=self.repository.list_specification_vehicles(),
        )

    def get_delivery_specifications(self):
        return self.get_shared_specifications()

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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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
                dispatch_date=request.dispatch_date,
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

    def _ensure_workspace_ready(self, workspace):
        return self.workspace_migration_readiness_service.ensure_ready(workspace)

    def _record_logbook(self, **entry):
        try:
            actor = entry.pop("actor", None) or self._current_logbook_actor()
            self.logbook.record(actor=actor, **entry)
        except Exception:
            LOGGER.exception("Failed to record Manual Dispatch logbook entry")

    @staticmethod
    def _current_logbook_actor():
        return LOGBOOK_ACTOR_CONTEXT.get() or "Unknown"

    def _record_failed_logbook(self, **entry):
        metadata = dict(entry.pop("metadata", {}) or {})
        metadata.setdefault("failure_reason", "Operation failed")
        self._record_logbook(result="FAILED", metadata=metadata, **entry)

    def _record_order_event(self, action, order):
        if not order:
            return
        label = self._order_entity_id(order)
        verb = {
            "ORDER_CREATED": "created",
            "ORDER_UPDATED": "updated",
            "ORDER_CANCELLED": "cancelled",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action=action,
            entity_type="ORDER",
            entity_id=label,
            summary=f"Order {label} was {verb}.",
            delivery_date=order.delivery_date,
            metadata={
                "order_id": order.order_id,
                "invoice_number": order.invoice_number,
                "order_no": order.order_no,
                "company_name": order.company_name,
                "suburb": order.suburb,
                "pallet_quantity": order.pallet_quantity,
                "loose_bags_quantity": order.loose_bags_quantity,
            },
        )

    def _record_delivery_assignment_change(
        self,
        dispatch_date,
        order_id,
        before,
        after,
    ):
        if before == after:
            return
        order = self.repository.get_order(order_id) if order_id else None
        entity_id = self._order_entity_id(order) if order else order_id
        metadata = {
            "before": self._assignment_log_metadata(before),
            "after": self._assignment_log_metadata(after),
            "order_id": order_id,
        }
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="ORDER_UNASSIGNED",
                entity_type="ORDER",
                entity_id=entity_id,
                summary=(
                    f"Order {entity_id} was unassigned from "
                    f"{self._assignment_label(before)}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=order.delivery_date if order else None,
                driver=before.get("driver"),
                metadata=metadata,
            )
            return
        if not after:
            return
        if before:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="ORDER_REASSIGNED",
                entity_type="ORDER",
                entity_id=entity_id,
                summary=(
                    f"Order {entity_id} was reassigned from "
                    f"{self._assignment_label(before)} to "
                    f"{self._assignment_label(after)}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=order.delivery_date if order else None,
                driver=after.get("driver"),
                metadata=metadata,
            )
            return
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="ORDER_ASSIGNED",
            entity_type="ORDER",
            entity_id=entity_id,
            summary=(
                f"Order {entity_id} was assigned to "
                f"{self._assignment_label(after)}."
            ),
            dispatch_date=dispatch_date,
            delivery_date=order.delivery_date if order else None,
            driver=after.get("driver"),
            metadata=metadata,
        )

    def _record_opshop_assignment_change(
        self,
        dispatch_date,
        pickup_task_id,
        before,
        after,
    ):
        if before == after:
            return
        pickup_name = self._opshop_pickup_name(pickup_task_id)
        pickup_date = self._opshop_pickup_date(pickup_task_id)
        metadata = {
            "before": self._assignment_log_metadata(before),
            "after": self._assignment_log_metadata(after),
        }
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="OPSHOP_TASK_UNASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=pickup_task_id,
                summary=(
                    f"OP SHOP pickup {pickup_name} was unassigned from "
                    f"{self._assignment_label(before)}."
                ),
                dispatch_date=dispatch_date,
                pickup_date=pickup_date,
                driver=before.get("driver"),
                metadata=metadata,
            )
            return
        if not after:
            return
        if before:
            self._record_logbook(
                result="SUCCESS",
                workspace="OPSHOP",
                action="OPSHOP_TASK_REASSIGNED",
                entity_type="OPSHOP_PICKUP",
                entity_id=pickup_task_id,
                summary=(
                    f"OP SHOP pickup {pickup_name} was reassigned from "
                    f"{self._assignment_label(before)} to "
                    f"{self._assignment_label(after)}."
                ),
                dispatch_date=dispatch_date,
                pickup_date=pickup_date,
                driver=after.get("driver"),
                metadata=metadata,
            )
            return
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="OPSHOP_TASK_ASSIGNED",
            entity_type="OPSHOP_PICKUP",
            entity_id=pickup_task_id,
            summary=(
                f"OP SHOP pickup {pickup_name} was assigned to "
                f"{self._assignment_label(after)}."
            ),
            dispatch_date=dispatch_date,
            pickup_date=pickup_date,
            driver=after.get("driver"),
            metadata=metadata,
        )

    def _record_vehicle_assignment_change(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
        before,
        after,
    ):
        if before == after:
            return
        driver = self._driver_name(driver_id)
        metadata = {"before": before or {}, "after": after or {}}
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="VEHICLE_CLEARED",
                entity_type="VEHICLE",
                entity_id=before.get("vehicle_id"),
                summary=(
                    f"Vehicle {before.get('vehicle')} was cleared from {driver} "
                    f"for delivery date {delivery_date}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=delivery_date,
                driver=driver,
                vehicle=before.get("vehicle"),
                metadata=metadata,
            )
            return
        if not after:
            return
        action = "VEHICLE_CHANGED" if before else "VEHICLE_ASSIGNED"
        if before:
            summary = (
                f"Vehicle for {driver} on delivery date {delivery_date} was "
                f"changed from {before.get('vehicle')} to {after.get('vehicle')}."
            )
        else:
            summary = (
                f"Vehicle {after.get('vehicle')} was assigned to {driver} "
                f"for delivery date {delivery_date}."
            )
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action=action,
            entity_type="VEHICLE",
            entity_id=after.get("vehicle_id"),
            summary=summary,
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver=driver,
            vehicle=after.get("vehicle"),
            metadata=metadata,
        )

    @staticmethod
    def _delivery_run_sheet_counts(run_sheet):
        return (
            sum(len(trip.orders) for trip in run_sheet.trips),
            {trip.trip_no: len(trip.orders) for trip in run_sheet.trips},
        )

    @staticmethod
    def _opshop_collection_counts(collection):
        counts = {"REGULAR": 0, "ON_CALL": 0, "COUNTRYSIDE": 0}
        for pickup in collection.pickups:
            category = str(pickup.pickup_category_snapshot or "").upper()
            run_type = str(pickup.run_type_snapshot or "").upper()
            if category == "COUNTRYSIDE":
                counts["COUNTRYSIDE"] += 1
            elif run_type == "REGULAR":
                counts["REGULAR"] += 1
            else:
                counts["ON_CALL"] += 1
        return counts

    def record_delivery_run_sheet_export(self, run_sheet, filename):
        order_count, trip_counts = self._delivery_run_sheet_counts(run_sheet)
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="DELIVERY_RUN_SHEET_EXPORTED",
            entity_type="DELIVERY_RUN_SHEET",
            entity_id=run_sheet.run_sheet_id,
            summary=(
                "Delivery Run Sheet Excel export was generated for "
                f"{run_sheet.driver_name_snapshot} on {run_sheet.delivery_date}."
            ),
            dispatch_date=run_sheet.dispatch_date,
            delivery_date=run_sheet.delivery_date,
            driver=run_sheet.driver_name_snapshot,
            vehicle=run_sheet.vehicle_rego_snapshot,
            run_sheet_id=run_sheet.run_sheet_id,
            metadata={
                "export_scope": "single",
                "status": run_sheet.status,
                "order_count": order_count,
                "trip1_count": trip_counts.get("trip1", 0),
                "trip2_count": trip_counts.get("trip2", 0),
                "filename": filename,
            },
        )

    def record_delivery_run_sheets_daily_export(
        self,
        run_sheets,
        delivery_date,
        filename,
    ):
        statuses = [str(run_sheet.status or "").upper() for run_sheet in run_sheets]
        run_sheet_label = "Run Sheet" if len(run_sheets) == 1 else "Run Sheets"
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="DELIVERY_RUN_SHEETS_DAILY_EXPORTED",
            entity_type="DELIVERY_RUN_SHEET_BATCH",
            entity_id=delivery_date,
            summary=(
                "Daily Delivery Run Sheets Excel export was generated for "
                f"{delivery_date} with {len(run_sheets)} {run_sheet_label}."
            ),
            delivery_date=delivery_date,
            metadata={
                "export_scope": "daily",
                "run_sheet_count": len(run_sheets),
                "saved_count": statuses.count("SAVED"),
                "generated_count": statuses.count("GENERATED"),
                "filename": filename,
            },
        )

    def record_opshop_pickup_collection_export(self, collection, filename):
        counts = self._opshop_collection_counts(collection)
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="PICKUP_COLLECTION_EXPORTED",
            entity_type="PICKUP_COLLECTION",
            entity_id=collection.collection_id,
            summary=(
                "OP SHOP Pickup Collection Excel export was generated for "
                f"{collection.driver_name_snapshot} on {collection.pickup_date}."
            ),
            dispatch_date=collection.dispatch_date,
            pickup_date=collection.pickup_date,
            driver=collection.driver_name_snapshot,
            collection_id=collection.collection_id,
            metadata={
                "export_scope": "single",
                "status": collection.status,
                "pickup_count": len(collection.pickups),
                "regular_count": counts["REGULAR"],
                "oncall_count": counts["ON_CALL"],
                "countryside_count": counts["COUNTRYSIDE"],
                "filename": filename,
            },
        )

    def record_opshop_pickup_collections_daily_export(
        self,
        collections,
        pickup_date,
        filename,
        dispatch_date=None,
        status=None,
    ):
        statuses = [str(collection.status or "").upper() for collection in collections]
        metadata = {
            "export_scope": "daily",
            "collection_count": len(collections),
            "saved_count": statuses.count("SAVED"),
            "generated_count": statuses.count("GENERATED"),
            "filename": filename,
        }
        if status is not None:
            metadata["status_filter"] = status
        if dispatch_date is not None:
            metadata["dispatch_date_filter"] = dispatch_date
        collection_label = (
            "Collection" if len(collections) == 1 else "Collections"
        )
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action="PICKUP_COLLECTIONS_DAILY_EXPORTED",
            entity_type="PICKUP_COLLECTION_BATCH",
            entity_id=pickup_date,
            summary=(
                "Daily OP SHOP Pickup Collections Excel export was generated for "
                f"{pickup_date} with {len(collections)} {collection_label}."
            ),
            pickup_date=pickup_date,
            dispatch_date=dispatch_date,
            metadata=metadata,
        )

    def record_attache_import_confirmation(self, rows, outcome):
        rows = list(rows or [])
        if not rows:
            return
        imported_count = int(outcome.get("imported_count") or 0)
        skipped_count = int(outcome.get("skipped_count") or 0)
        order_label = "order" if imported_count == 1 else "orders"
        row_label = "row" if skipped_count == 1 else "rows"
        if imported_count and skipped_count:
            result = "PARTIAL"
            summary = (
                f"Attach\u00e9 import confirmed: {imported_count} {order_label} imported "
                f"and {skipped_count} {row_label} skipped."
            )
        elif imported_count:
            result = "SUCCESS"
            summary = (
                f"Attach\u00e9 import confirmed: {imported_count} {order_label} imported."
            )
        else:
            result = "FAILED"
            summary = (
                "Attach\u00e9 import confirmed but no orders were imported; "
                f"{skipped_count} {row_label} skipped."
            )

        source_filenames = []
        for row in rows:
            raw_name = getattr(row, "source_filename", None)
            if not raw_name:
                continue
            basename = str(raw_name).replace("\\", "/").rsplit("/", 1)[-1]
            if basename and basename not in source_filenames:
                source_filenames.append(basename)

        duplicate_row_ids = {
            getattr(row, "row_id", None)
            or getattr(row, "invoice_number", None)
            or getattr(row, "source_filename", None)
            or "row"
            for row in rows
            if bool(getattr(row, "is_duplicate", False))
        }
        duplicate_count = len(duplicate_row_ids)
        for skipped in outcome.get("skipped_rows") or []:
            if (
                "duplicate" in str(skipped.get("reason") or "").lower()
                and skipped.get("row_id") not in duplicate_row_ids
            ):
                duplicate_count += 1
        unselected_count = sum(
            not bool(getattr(row, "selected", False))
            for row in rows
        )
        metadata = {
            "selected_count": sum(
                bool(getattr(row, "selected", False))
                for row in rows
            ),
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "duplicate_count": duplicate_count,
            "invalid_count": max(
                skipped_count - unselected_count - duplicate_count,
                0,
            ),
            "source_file_count": len(source_filenames),
            "source_filenames": source_filenames[:20],
            "source_filenames_truncated": len(source_filenames) > 20,
        }
        if result == "FAILED":
            metadata["failure_reason"] = "No orders were imported"
        self._record_logbook(
            result=result,
            workspace="DELIVERY",
            action="ATTACHE_IMPORT_CONFIRMED",
            entity_type="ATTACHE_IMPORT_BATCH",
            entity_id=None,
            summary=summary,
            metadata=metadata,
        )

    def _record_delivery_run_sheet_event(self, action, run_sheet, actor=None):
        order_count, trip_counts = self._delivery_run_sheet_counts(run_sheet)
        verb = {
            "DELIVERY_RUN_SHEET_GENERATED": "generated",
            "DELIVERY_RUN_SHEET_CANCELLED": "cancelled",
            "DELIVERY_RUN_SHEET_SAVED": "saved",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            actor=actor,
            action=action,
            entity_type="DELIVERY_RUN_SHEET",
            entity_id=run_sheet.run_sheet_id,
            summary=(
                f"Delivery Run Sheet was {verb} for "
                f"{run_sheet.driver_name_snapshot} on {run_sheet.delivery_date} "
                f"with {order_count} orders."
            ),
            dispatch_date=run_sheet.dispatch_date,
            delivery_date=run_sheet.delivery_date,
            driver=run_sheet.driver_name_snapshot,
            vehicle=run_sheet.vehicle_rego_snapshot,
            run_sheet_id=run_sheet.run_sheet_id,
            metadata={
                "order_count": order_count,
                "trip1_count": trip_counts.get("trip1", 0),
                "trip2_count": trip_counts.get("trip2", 0),
                "total_pallets": run_sheet.total_pallets,
                "total_loose_bags": run_sheet.total_loose_bags,
                "status": run_sheet.status,
            },
        )

    def _record_opshop_collection_event(self, action, collection, actor=None):
        counts = self._opshop_collection_counts(collection)
        pickup_count = len(collection.pickups)
        verb = {
            "PICKUP_COLLECTION_GENERATED": "generated",
            "PICKUP_COLLECTION_CANCELLED": "cancelled",
            "PICKUP_COLLECTION_SAVED": "saved",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            actor=actor,
            action=action,
            entity_type="OPSHOP_PICKUP_COLLECTION",
            entity_id=collection.collection_id,
            summary=(
                f"Pickup Collection was {verb} for "
                f"{collection.driver_name_snapshot} on {collection.pickup_date} "
                f"with {pickup_count} pickup tasks."
            ),
            dispatch_date=collection.dispatch_date,
            pickup_date=collection.pickup_date,
            driver=collection.driver_name_snapshot,
            collection_id=collection.collection_id,
            metadata={
                "pickup_count": pickup_count,
                "regular_count": counts["REGULAR"],
                "oncall_count": counts["ON_CALL"],
                "countryside_count": counts["COUNTRYSIDE"],
                "status": collection.status,
            },
        )

    def _record_opshop_task_event(self, action, task):
        if not task:
            return
        name = self._opshop_pickup_name(task.pickup_task_id)
        verb = {
            "OPSHOP_TASK_CREATED": "created",
            "OPSHOP_TASK_UPDATED": "updated",
            "OPSHOP_TASK_CANCELLED": "cancelled",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action=action,
            entity_type="OPSHOP_PICKUP",
            entity_id=task.pickup_task_id,
            summary=f"OP SHOP pickup {name} was {verb}.",
            dispatch_date=task.dispatch_date,
            pickup_date=task.pickup_date,
            driver=self._driver_name(task.driver_id),
            metadata={
                "pickup_task_id": task.pickup_task_id,
                "schedule_id": task.schedule_id,
                "status": task.status,
                "generated_from": task.generated_from,
            },
        )

    def _record_failed_assignment(self, request, before, error, unassign=False):
        if request.task_type == "ORDER":
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="ORDER_UNASSIGNED" if unassign else (
                    "ORDER_REASSIGNED" if before else "ORDER_ASSIGNED"
                ),
                entity_type="ORDER",
                entity_id=self._order_entity_id_by_id(request.task_id),
                summary=f"Order {self._order_entity_id_by_id(request.task_id)} assignment failed.",
                dispatch_date=request.dispatch_date,
                delivery_date=self._order_delivery_date(request.task_id),
                driver=self._driver_name(getattr(request, "driver_id", None)),
                metadata={"failure_reason": str(error)},
            )
            return
        if request.task_type == "OPSHOP_PICKUP":
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="OPSHOP_TASK_UNASSIGNED" if unassign else (
                    "OPSHOP_TASK_REASSIGNED" if before else "OPSHOP_TASK_ASSIGNED"
                ),
                entity_type="OPSHOP_PICKUP",
                entity_id=request.task_id,
                summary=(
                    f"OP SHOP pickup {self._opshop_pickup_name(request.task_id)} "
                    "assignment failed."
                ),
                dispatch_date=request.dispatch_date,
                pickup_date=self._opshop_pickup_date(request.task_id),
                driver=self._driver_name(getattr(request, "driver_id", None)),
                metadata={"failure_reason": str(error)},
            )

    def _assignment_snapshot(self, dispatch_date, task_type, task_id):
        if not dispatch_date or not task_type or not task_id:
            return None
        assignment = self.repository.get_assignment(
            dispatch_date,
            task_type,
            task_id,
        )
        if not assignment:
            return None
        return {
            "driver_id": assignment.driver_id,
            "driver": self._driver_name(assignment.driver_id),
            "trip_no": assignment.trip_no,
            "trip": self._trip_label(assignment.trip_no),
        }

    def _assignment_log_metadata(self, snapshot):
        if not snapshot:
            return None
        return {
            "driver_id": snapshot.get("driver_id"),
            "driver": snapshot.get("driver"),
            "trip": snapshot.get("trip_no"),
        }

    def _assignment_label(self, snapshot):
        if not snapshot:
            return "Unassigned"
        return f"{snapshot.get('driver') or 'Unknown'} / {snapshot.get('trip') or 'Trip'}"

    def _vehicle_assignment_snapshot(self, dispatch_date, delivery_date, driver_id):
        if not dispatch_date or not delivery_date or not driver_id:
            return None
        assignment = next(
            (
                item
                for item in self.repository.list_driver_vehicle_assignments(
                    dispatch_date
                )
                if item.delivery_date == delivery_date
                and item.driver_id == driver_id
            ),
            None,
        )
        if not assignment:
            return None
        return {
            "vehicle_id": assignment.vehicle_id,
            "vehicle": self._vehicle_label(assignment.vehicle_id),
        }

    def _driver_name(self, driver_id):
        if not driver_id:
            return None
        driver = self.repository.get_driver(driver_id)
        return driver.name if driver else driver_id

    def _vehicle_label(self, vehicle_id):
        if not vehicle_id:
            return None
        vehicle = self.repository.get_vehicle(vehicle_id)
        return vehicle.rego if vehicle else vehicle_id

    def _order_entity_id(self, order):
        if not order:
            return None
        return order.invoice_number or order.order_no or order.order_id

    def _order_entity_id_by_id(self, order_id):
        order = self.repository.get_order(order_id) if order_id else None
        return self._order_entity_id(order) or order_id

    def _order_delivery_date(self, order_id):
        order = self.repository.get_order(order_id) if order_id else None
        return order.delivery_date if order else None

    def _opshop_pickup_name(self, pickup_task_id):
        task = (
            self.repository.get_opshop_pickup_task(pickup_task_id)
            if pickup_task_id
            else None
        )
        location = self.repository.get_opshop_location(task.opshop_id) if task else None
        return location.name if location else (pickup_task_id or "Unknown")

    def _opshop_pickup_date(self, pickup_task_id):
        task = (
            self.repository.get_opshop_pickup_task(pickup_task_id)
            if pickup_task_id
            else None
        )
        return task.pickup_date if task else None

    def _route_group_name(self, route_group_id):
        route_group = (
            self.repository.get_countryside_route_group(route_group_id)
            if route_group_id
            else None
        )
        return route_group.route_group_name if route_group else route_group_id

    @staticmethod
    def _trip_label(trip_no):
        labels = {"trip1": "Trip 1", "trip2": "Trip 2"}
        return labels.get(trip_no, trip_no)

    def register_operator_account(self, request):
        return self.auth_service.register_operator_account(request)

    def login_operator_account(self, request):
        return self.auth_service.login_operator_account(request)

    def reset_operator_password(self, request):
        return self.auth_service.reset_operator_password(request)

    def assign_task(self, request):
        before = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        try:
            board = self.assignment_service.assign_task(request)
        except Exception as error:
            self._record_failed_assignment(request, before, error)
            raise
        after = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        if request.task_type == "ORDER":
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
        before = self._assignment_snapshot(
            request.dispatch_date,
            request.task_type,
            request.task_id,
        )
        try:
            board = self.assignment_service.unassign_task(request)
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

    def create_delivery_order(self, request):
        self._ensure_workspace_ready("delivery")
        order = self.order_service.create_order(request)
        self._record_order_event("ORDER_CREATED", order)
        return order

    def update_delivery_order(self, order_id, request):
        self._ensure_workspace_ready("delivery")
        ensure_order_not_reserved(self.repository, None, order_id)
        order = self.order_service.update_order(order_id, request)
        self._record_order_event("ORDER_UPDATED", order)
        return order

    def cancel_delivery_order(self, order_id):
        self._ensure_workspace_ready("delivery")
        ensure_order_not_reserved(self.repository, None, order_id)
        order = self.order_service.cancel_order(order_id)
        self._record_order_event("ORDER_CANCELLED", order)
        return order

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

    @staticmethod
    def _template_business_snapshot(template):
        fields = (
            "run_type",
            "run_day",
            "name",
            "suburb",
            "street_address",
            "area_region",
            "primary_contact",
            "primary_phone",
            "secondary_contact",
            "secondary_phone",
            "pickup_frequency",
            "time_window",
            "call_before_arrival",
            "call_timing",
            "access_type",
            "key_required",
            "trailer_restriction",
            "status_notes",
            "default_driver_id",
            "default_driver_name",
            "pickup_category",
            "route_group_id",
        )
        return {field: getattr(template, field, None) for field in fields}

    def _find_opshop_template(self, schedule_id):
        return next(
            (
                template
                for template in self.opshop_template_service.list_opshop_templates(
                    include_inactive=True
                )
                if template.schedule_id == schedule_id
            ),
            None,
        )

    @staticmethod
    def _template_category(template):
        if str(template.run_type or "").upper() == "REGULAR":
            return "REGULAR", "Regular"
        return "ONCALL", "Oncall"

    def _record_template_event(
        self,
        suffix,
        template,
        before=None,
        after=None,
    ):
        action_category, label = self._template_category(template)
        metadata = {
            "pickup_category": template.run_type,
            "company_name": template.name,
            "suburb": template.suburb,
            "run_day": template.run_day,
            "default_driver": template.default_driver_name,
        }
        if before is not None and after is not None:
            changed = [
                field
                for field in before
                if before.get(field) != after.get(field)
            ]
            if not changed:
                return
            metadata = {
                "pickup_category": template.run_type,
                "before": {field: before[field] for field in changed},
                "after": {field: after[field] for field in changed},
            }
        elif suffix == "DISABLED":
            metadata.update(
                {
                    "previous_status": before.get("status"),
                    "new_status": template.status,
                }
            )
        metadata = {key: value for key, value in metadata.items() if value is not None}
        verb = {
            "CREATED": "created",
            "UPDATED": "updated",
            "DISABLED": "disabled",
        }[suffix]
        self._record_logbook(
            result="SUCCESS",
            workspace="OPSHOP",
            action=f"{action_category}_TEMPLATE_{suffix}",
            entity_type="OPSHOP_TEMPLATE",
            entity_id=template.schedule_id,
            summary=f"{label} OP SHOP template for {template.name} was {verb}.",
            metadata=metadata,
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

    def create_delivery_driver(self, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.create_driver(request)

    def update_delivery_driver(self, driver_id, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.update_driver(driver_id, request)

    def delete_delivery_driver(self, driver_id):
        self._ensure_workspace_ready("delivery")
        self._ensure_driver_not_used_by_delivery_run_sheet(driver_id)
        return self.specification_service.delete_driver(driver_id)

    def create_delivery_vehicle(self, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.create_vehicle(request)

    def update_delivery_vehicle(self, vehicle_id, request):
        self._ensure_workspace_ready("delivery")
        return self.specification_service.update_vehicle(vehicle_id, request)

    def delete_delivery_vehicle(self, vehicle_id):
        self._ensure_workspace_ready("delivery")
        self._ensure_vehicle_not_used_by_delivery_run_sheet(vehicle_id)
        return self.specification_service.delete_vehicle(vehicle_id)

    def _ensure_driver_not_used_by_delivery_run_sheet(self, driver_id):
        if any(
            run_sheet.driver_id == driver_id
            for run_sheet in self.repository.list_delivery_run_sheets()
        ):
            raise ValueError(
                "Driver has Delivery Run Sheet history and cannot be deleted. "
                "Set Availability off instead."
            )

    def _ensure_vehicle_not_used_by_delivery_run_sheet(self, vehicle_id):
        if any(
            run_sheet.vehicle_id == vehicle_id
            for run_sheet in self.repository.list_delivery_run_sheets()
        ):
            raise ValueError(
                "Vehicle has Delivery Run Sheet history and cannot be deleted. "
                "Set Availability off instead."
            )

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
