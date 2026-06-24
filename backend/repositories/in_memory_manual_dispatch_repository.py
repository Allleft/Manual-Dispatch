from copy import deepcopy
from dataclasses import replace

from backend.schemas import (
    DeliveryRunSheet,
    Driver,
    FinalTripSummary,
    FinalTripSummaryOpShopPickupSnapshot,
    FinalTripSummaryOrderSnapshot,
    FinalTripSummaryTrip,
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
    Order,
    OpShopPickupBoardItem,
    OpShopPickupCollection,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupScheduleCandidate,
    OpShopPickupTask,
    OpShopTemplate,
    OperatorAccountRecord,
    ProductDetailLine,
    Vehicle,
)


class InMemoryManualDispatchRepository:
    """Temporary in-memory data store for Phase 5.

    This is not persistence. Data resets whenever the backend process restarts.
    """

    def __init__(self):
        self.orders = [
            Order(
                order_id="ORD-001",
                invoice_number="INV-1001",
                order_no=None,
                company_name="Demo Customer A",
                phone="0400 000 001",
                delivery_address="1 Demo Street",
                suburb="Dandenong",
                postcode="3175",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=2,
                loose_bags_quantity=0,
                start_time=None,
                end_time=None,
                note=None,
            ),
            Order(
                order_id="ORD-002",
                invoice_number="INV-1002",
                order_no=None,
                company_name="Demo Customer B",
                phone="0400 000 002",
                delivery_address="2 Demo Street",
                suburb="Clayton",
                postcode="3168",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=0,
                loose_bags_quantity=12,
                start_time=None,
                end_time=None,
                note="Loose Bags only",
            ),
            Order(
                order_id="ORD-003",
                invoice_number="INV-1003",
                order_no=None,
                company_name="Demo Customer C",
                phone="0400 000 003",
                delivery_address="3 Demo Street",
                suburb="Springvale",
                postcode="3171",
                delivery_date="2026-05-05",
                zone="South East",
                urgency="normal",
                preferred_driver_id=None,
                pallet_quantity=3,
                loose_bags_quantity=0,
                start_time=None,
                end_time=None,
                note=None,
            ),
        ]
        self.drivers = [
            Driver(
                driver_id="D001",
                name="John",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
                license_no="LIC-D001",
                email="john@example.com",
                phone_number="0400 100 001",
            ),
            Driver(
                driver_id="D002",
                name="Tony",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=True,
                license_no="LIC-D002",
                email="tony@example.com",
                phone_number="0400 100 002",
            ),
            Driver(
                driver_id="D003",
                name="David",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
                license_no="LIC-D003",
                email="david@example.com",
                phone_number="0400 100 003",
            ),
        ]
        self.vehicles = [
            Vehicle(
                vehicle_id="V001",
                rego="ABC123",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
            Vehicle(
                vehicle_id="V002",
                rego="XYZ888",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
            Vehicle(
                vehicle_id="V003",
                rego="MCC001",
                type="truck",
                is_available=True,
                pallet_capacity=0,
                tub_capacity=0,
                trolley_capacity=0,
                stillage_capacity=0,
            ),
        ]
        self.assignments = []
        self.driver_vehicle_assignments = []
        self.final_trip_summaries = []
        self.delivery_run_sheets = []
        self.opshop_pickup_collections = []
        self.operator_accounts = []
        self.opshop_locations = []
        self.opshop_countryside_route_groups = []
        self.opshop_pickup_schedules = []
        self.opshop_pickup_tasks = []
        self._next_assignment_number = 1
        self._next_final_summary_number = 1
        self._next_final_summary_row_number = 1
        self._next_final_summary_opshop_row_number = 1
        self._next_operator_account_id = 1

    def list_orders(self, delivery_date=None):
        return [
            order
            for order in self.orders
            if order.status == "ACTIVE"
            and (not delivery_date or order.delivery_date == delivery_date)
        ]

    def list_drivers(self):
        return [
            driver
            for driver in self.drivers
            if driver.is_available and not driver.is_deleted
        ]

    def list_vehicles(self):
        return [
            vehicle
            for vehicle in self.vehicles
            if vehicle.is_available and not vehicle.is_deleted
        ]

    def list_specification_drivers(self):
        return [driver for driver in self.drivers if not driver.is_deleted]

    def list_specification_vehicles(self):
        return [vehicle for vehicle in self.vehicles if not vehicle.is_deleted]

    def list_driver_ids(self):
        return [driver.driver_id for driver in self.drivers]

    def list_vehicle_ids(self):
        return [vehicle.vehicle_id for vehicle in self.vehicles]

    def list_assignments(self, dispatch_date):
        return [
            assignment
            for assignment in self.assignments
            if assignment.dispatch_date == dispatch_date
            and (
                (
                    assignment.task_type == "ORDER"
                    and self.get_order(assignment.task_id)
                    and self.get_order(assignment.task_id).status == "ACTIVE"
                )
                or (
                    assignment.task_type == "OPSHOP_PICKUP"
                    and self.get_opshop_pickup_task(assignment.task_id)
                    and self.get_opshop_pickup_task(assignment.task_id).status == "ASSIGNED"
                )
            )
        ]

    def list_assigned_opshop_pickup_board_items(self, dispatch_date):
        items = []
        for assignment in self.assignments:
            if assignment.dispatch_date != dispatch_date or assignment.task_type != "OPSHOP_PICKUP":
                continue
            task = self.get_opshop_pickup_task(assignment.task_id)
            if not task or task.status != "ASSIGNED":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            item = self._opshop_pickup_board_item(task, schedule, location)
            item.dispatch_date = assignment.dispatch_date
            item.driver_id = assignment.driver_id
            item.trip_no = assignment.trip_no
            item.is_assigned = True
            items.append(item)

        return sorted(
            items,
            key=lambda item: (
                item.driver_id or "",
                item.trip_no or "",
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_driver_vehicle_assignments(self, dispatch_date):
        return [
            assignment
            for assignment in self.driver_vehicle_assignments
            if assignment.dispatch_date == dispatch_date
        ]

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return [
            summary
            for summary in self.final_trip_summaries
            if summary.dispatch_date == dispatch_date
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "SAVED"
        ]

    def list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return [
            summary
            for summary in self.final_trip_summaries
            if summary.dispatch_date == dispatch_date
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "GENERATED"
        ]

    def list_final_summary_dates(self):
        return sorted(
            {
                summary.dispatch_date
                for summary in self.final_trip_summaries
                if summary.status == "SAVED"
            },
            reverse=True,
        )

    def list_finalized_opshop_pickup_assignments(self, dispatch_date):
        finalized = {}
        summaries = sorted(
            [
                summary
                for summary in self.final_trip_summaries
                if summary.dispatch_date == dispatch_date and summary.status == "SAVED"
            ],
            key=lambda summary: (summary.saved_at or "", summary.summary_id),
            reverse=True,
        )
        for summary in summaries:
            driver = self.get_driver(summary.driver_id)
            driver_name = driver.name if driver else summary.driver_name_snapshot
            for pickup in summary.opshop_pickups or []:
                pickup_task_id = pickup.pickup_task_id_snapshot
                if not pickup_task_id or pickup_task_id in finalized:
                    continue
                finalized[pickup_task_id] = {
                    "pickup_task_id": pickup_task_id,
                    "dispatch_date": summary.dispatch_date,
                    "delivery_date": summary.delivery_date,
                    "driver_id": summary.driver_id,
                    "driver_name": driver_name,
                    "summary_id": summary.summary_id,
                    "saved_at": summary.saved_at,
                }
        return finalized

    def has_saved_final_trip_summary(self, dispatch_date, driver_id, delivery_date=None):
        return any(
            summary.dispatch_date == dispatch_date
            and summary.driver_id == driver_id
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "SAVED"
            for summary in self.final_trip_summaries
        )

    def get_final_trip_summary(self, summary_id):
        return next(
            (
                summary
                for summary in self.final_trip_summaries
                if summary.summary_id == summary_id
            ),
            None,
        )

    def get_order(self, order_id):
        return next((order for order in self.orders if order.order_id == order_id), None)

    def get_driver(self, driver_id):
        return next(
            (driver for driver in self.drivers if driver.driver_id == driver_id),
            None,
        )

    def get_vehicle(self, vehicle_id):
        return next(
            (vehicle for vehicle in self.vehicles if vehicle.vehicle_id == vehicle_id),
            None,
        )

    def get_operator_account_by_name(self, account_name):
        normalized_name = str(account_name or "").strip().lower()
        return next(
            (
                account
                for account in self.operator_accounts
                if account.account_name.lower() == normalized_name
            ),
            None,
        )

    def get_operator_account_by_id(self, account_id):
        return next(
            (
                account
                for account in self.operator_accounts
                if account.account_id == account_id
            ),
            None,
        )

    def get_generated_final_trip_summary_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        return next(
            (
                summary
                for summary in self.final_trip_summaries
                if summary.dispatch_date == dispatch_date
                and summary.delivery_date == delivery_date
                and summary.driver_id == driver_id
                and summary.status == "GENERATED"
            ),
            None,
        )

    def get_workspace_migration_status(self):
        generated = [
            summary
            for summary in self.final_trip_summaries
            if summary.status == "GENERATED"
        ]
        delivery_unmigrated_ids = []
        opshop_unmigrated_ids = []
        for summary in self.final_trip_summaries:
            if summary.status != "SAVED":
                continue
            has_delivery_rows = any(
                trip.orders for trip in (summary.trips or [])
            )
            has_opshop_rows = bool(summary.opshop_pickups or [])
            delivery_marker_count = sum(
                run_sheet.legacy_summary_id == summary.summary_id
                for run_sheet in self.delivery_run_sheets
            )
            opshop_marker_count = sum(
                collection.legacy_summary_id == summary.summary_id
                for collection in self.opshop_pickup_collections
            )
            if has_delivery_rows and delivery_marker_count != 1:
                delivery_unmigrated_ids.append(summary.summary_id)
            if has_opshop_rows and opshop_marker_count != 1:
                opshop_unmigrated_ids.append(summary.summary_id)

        generated_count = len(generated)
        delivery_unmigrated_ids.sort()
        opshop_unmigrated_ids.sort()
        return {
            "delivery_ready": not generated_count and not delivery_unmigrated_ids,
            "opshop_ready": not generated_count and not opshop_unmigrated_ids,
            "legacy_generated_summary_count": generated_count,
            "delivery_unmigrated_summary_count": len(delivery_unmigrated_ids),
            "opshop_unmigrated_summary_count": len(opshop_unmigrated_ids),
            "delivery_unmigrated_summary_ids": delivery_unmigrated_ids,
            "opshop_unmigrated_summary_ids": opshop_unmigrated_ids,
        }

    def list_delivery_run_sheets(
        self,
        dispatch_date=None,
        delivery_date=None,
        status=None,
    ):
        return [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if (not dispatch_date or run_sheet.dispatch_date == dispatch_date)
            and (not delivery_date or run_sheet.delivery_date == delivery_date)
            and (not status or run_sheet.status == status)
        ]

    def get_delivery_run_sheet(self, run_sheet_id):
        return next(
            (
                run_sheet
                for run_sheet in self.delivery_run_sheets
                if run_sheet.run_sheet_id == run_sheet_id
            ),
            None,
        )

    def get_delivery_run_sheet_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        return next(
            (
                run_sheet
                for run_sheet in self.delivery_run_sheets
                if run_sheet.dispatch_date == dispatch_date
                and run_sheet.delivery_date == delivery_date
                and run_sheet.driver_id == driver_id
            ),
            None,
        )

    def has_saved_delivery_run_sheet(self, dispatch_date, driver_id, delivery_date):
        run_sheet = self.get_delivery_run_sheet_for_driver(
            dispatch_date,
            delivery_date,
            driver_id,
        )
        return bool(run_sheet and run_sheet.status == "SAVED")

    def upsert_delivery_run_sheet(self, run_sheet):
        duplicate = next(
            (
                existing
                for existing in self.delivery_run_sheets
                if existing.run_sheet_id != run_sheet.run_sheet_id
                and existing.dispatch_date == run_sheet.dispatch_date
                and existing.delivery_date == run_sheet.delivery_date
                and existing.driver_id == run_sheet.driver_id
            ),
            None,
        )
        if duplicate:
            raise ValueError(
                "Delivery Run Sheet already exists for this driver and delivery date."
            )
        self.delivery_run_sheets = [
            existing
            for existing in self.delivery_run_sheets
            if existing.run_sheet_id != run_sheet.run_sheet_id
        ]
        self.delivery_run_sheets.append(run_sheet)
        return run_sheet

    def promote_generated_delivery_run_sheet_to_saved(
        self,
        run_sheet_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        for index, run_sheet in enumerate(self.delivery_run_sheets):
            if run_sheet.run_sheet_id != run_sheet_id or run_sheet.status != "GENERATED":
                continue
            self.delivery_run_sheets[index] = replace(
                run_sheet,
                status="SAVED",
                saved_at=saved_at,
                saved_by_account_name=saved_by_account_name,
                saved_by_account_id=saved_by_account_id,
            )
            return True
        return False

    def delete_generated_delivery_run_sheet(self, run_sheet_id):
        before_count = len(self.delivery_run_sheets)
        self.delivery_run_sheets = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if not (
                run_sheet.run_sheet_id == run_sheet_id
                and run_sheet.status == "GENERATED"
            )
        ]
        return len(self.delivery_run_sheets) != before_count

    def delete_delivery_run_sheet(self, run_sheet_id):
        before_count = len(self.delivery_run_sheets)
        self.delivery_run_sheets = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if run_sheet.run_sheet_id != run_sheet_id
        ]
        return len(self.delivery_run_sheets) != before_count

    def list_opshop_pickup_collections(
        self,
        dispatch_date=None,
        pickup_date=None,
        status=None,
    ):
        return [
            collection
            for collection in self.opshop_pickup_collections
            if (not dispatch_date or collection.dispatch_date == dispatch_date)
            and (not pickup_date or collection.pickup_date == pickup_date)
            and (not status or collection.status == status)
        ]

    def get_opshop_pickup_collection(self, collection_id):
        return next(
            (
                collection
                for collection in self.opshop_pickup_collections
                if collection.collection_id == collection_id
            ),
            None,
        )

    def get_opshop_pickup_collection_for_driver(
        self,
        dispatch_date,
        pickup_date,
        driver_id,
    ):
        return next(
            (
                collection
                for collection in self.opshop_pickup_collections
                if collection.dispatch_date == dispatch_date
                and collection.pickup_date == pickup_date
                and collection.driver_id == driver_id
            ),
            None,
        )

    def has_saved_opshop_pickup_collection(self, dispatch_date, driver_id, pickup_date):
        collection = self.get_opshop_pickup_collection_for_driver(
            dispatch_date,
            pickup_date,
            driver_id,
        )
        return bool(collection and collection.status == "SAVED")

    def upsert_opshop_pickup_collection(self, collection):
        duplicate = next(
            (
                existing
                for existing in self.opshop_pickup_collections
                if existing.collection_id != collection.collection_id
                and existing.dispatch_date == collection.dispatch_date
                and existing.pickup_date == collection.pickup_date
                and existing.driver_id == collection.driver_id
            ),
            None,
        )
        if duplicate:
            raise ValueError(
                "OP SHOP Pickup Collection already exists for this driver and pickup date."
            )
        self.opshop_pickup_collections = [
            existing
            for existing in self.opshop_pickup_collections
            if existing.collection_id != collection.collection_id
        ]
        self.opshop_pickup_collections.append(collection)
        return collection

    def promote_generated_opshop_pickup_collection_to_saved(
        self,
        collection_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        for index, collection in enumerate(self.opshop_pickup_collections):
            if (
                collection.collection_id != collection_id
                or collection.status != "GENERATED"
            ):
                continue
            self.opshop_pickup_collections[index] = replace(
                collection,
                status="SAVED",
                saved_at=saved_at,
                saved_by_account_name=saved_by_account_name,
                saved_by_account_id=saved_by_account_id,
            )
            return True
        return False

    def delete_generated_opshop_pickup_collection(self, collection_id):
        before_count = len(self.opshop_pickup_collections)
        self.opshop_pickup_collections = [
            collection
            for collection in self.opshop_pickup_collections
            if not (
                collection.collection_id == collection_id
                and collection.status == "GENERATED"
            )
        ]
        return len(self.opshop_pickup_collections) != before_count

    def delete_opshop_pickup_collection(self, collection_id):
        before_count = len(self.opshop_pickup_collections)
        self.opshop_pickup_collections = [
            collection
            for collection in self.opshop_pickup_collections
            if collection.collection_id != collection_id
        ]
        return len(self.opshop_pickup_collections) != before_count

    def list_opshop_locations(self):
        return sorted(self.opshop_locations, key=lambda location: location.opshop_id)

    def get_opshop_location(self, opshop_id):
        return next(
            (
                location
                for location in self.opshop_locations
                if location.opshop_id == opshop_id
            ),
            None,
        )

    def upsert_opshop_location(self, location):
        for index, existing in enumerate(self.opshop_locations):
            if existing.opshop_id == location.opshop_id:
                self.opshop_locations[index] = location
                return location
        self.opshop_locations.append(location)
        return location

    def list_countryside_route_groups(self, include_inactive=False):
        groups = [
            group
            for group in self.opshop_countryside_route_groups
            if include_inactive or (group.active_flag and group.status == "Active")
        ]
        return sorted(
            groups,
            key=lambda group: (
                group.display_order,
                group.route_group_name.lower(),
                group.route_group_id,
            ),
        )

    def get_countryside_route_group(self, route_group_id):
        return next(
            (
                group
                for group in self.opshop_countryside_route_groups
                if group.route_group_id == route_group_id
            ),
            None,
        )

    def find_countryside_route_group_by_name(self, route_group_name):
        normalized = _normalize_text_key(route_group_name)
        return next(
            (
                group
                for group in self.opshop_countryside_route_groups
                if _normalize_text_key(group.route_group_name) == normalized
            ),
            None,
        )

    def upsert_countryside_route_group(self, route_group):
        for index, existing in enumerate(self.opshop_countryside_route_groups):
            if existing.route_group_id == route_group.route_group_id:
                self.opshop_countryside_route_groups[index] = route_group
                return route_group
        self.opshop_countryside_route_groups.append(route_group)
        return route_group

    def disable_countryside_route_group(self, route_group_id):
        group = self.get_countryside_route_group(route_group_id)
        if not group:
            return None
        group.status = "On_Hold"
        group.active_flag = False
        return group

    def list_opshop_pickup_schedules(self):
        return sorted(
            self.opshop_pickup_schedules,
            key=lambda schedule: schedule.schedule_id,
        )

    def list_active_opshop_pickup_schedules(self):
        return [
            schedule
            for schedule in self.list_opshop_pickup_schedules()
            if schedule.active_flag and schedule.status == "Active"
        ]

    def list_scheduled_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "REGULAR"
                and schedule.pickup_category == "NORMAL"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=None,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.run_day or "",
                candidate.schedule_id,
            ),
        )

    def list_oncall_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "ON_CALL"
                and schedule.pickup_category == "NORMAL"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=None,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.run_day or "ZZZ",
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.schedule_id,
            ),
        )

    def list_countryside_opshop_pickup_schedule_candidates(self):
        candidates = []
        for schedule in self.list_opshop_pickup_schedules():
            if not (
                schedule.active_flag
                and schedule.status == "Active"
                and schedule.run_type == "ON_CALL"
                and schedule.pickup_category == "COUNTRYSIDE"
            ):
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            if not route_group or not route_group.active_flag or route_group.status != "Active":
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            candidates.append(
                OpShopPickupScheduleCandidate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    opshop_name=location.name if location else "",
                    suburb=location.suburb if location else None,
                    run_day=schedule.run_day,
                    run_type=schedule.run_type,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    primary_phone=location.primary_phone if location else None,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=route_group.route_group_name,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.route_group_name or "",
                candidate.opshop_name or "",
                candidate.suburb or "",
                candidate.schedule_id,
            ),
        )

    def list_opshop_templates(self, run_type=None, include_inactive=False):
        templates = []
        for schedule in self.list_opshop_pickup_schedules():
            if run_type and schedule.run_type != run_type:
                continue
            if not include_inactive and not (
                schedule.active_flag and schedule.status == "Active"
            ):
                continue
            location = self.get_opshop_location(schedule.opshop_id)
            if not location:
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            templates.append(
                OpShopTemplate(
                    schedule_id=schedule.schedule_id,
                    opshop_id=schedule.opshop_id,
                    run_type=schedule.run_type,
                    run_day=schedule.run_day,
                    name=location.name,
                    suburb=location.suburb,
                    street_address=location.street_address,
                    area_region=location.area_region,
                    primary_contact=location.primary_contact,
                    primary_phone=location.primary_phone,
                    secondary_contact=location.secondary_contact,
                    secondary_phone=location.secondary_phone,
                    pickup_frequency=schedule.pickup_frequency,
                    time_window=schedule.time_window,
                    call_before_arrival=schedule.call_before_arrival,
                    call_timing=schedule.call_timing,
                    access_type=location.access_type,
                    key_required=location.key_required,
                    trailer_restriction=location.trailer_restriction,
                    status_notes=location.status_notes,
                    default_driver_id=schedule.default_driver_id,
                    default_driver_alias=schedule.default_driver_alias,
                    default_driver_name=schedule.default_driver_name_snapshot,
                    status=schedule.status,
                    active_flag=schedule.active_flag,
                    pickup_category=schedule.pickup_category,
                    route_group_id=schedule.route_group_id,
                    route_group_name=route_group.route_group_name if route_group else None,
                )
            )
        return sorted(
            templates,
            key=lambda template: (
                template.run_type,
                template.name,
                template.suburb or "",
                template.run_day or "ZZZ",
                template.schedule_id,
            ),
        )

    def get_opshop_pickup_schedule(self, schedule_id):
        return next(
            (
                schedule
                for schedule in self.opshop_pickup_schedules
                if schedule.schedule_id == schedule_id
            ),
            None,
        )

    def upsert_opshop_pickup_schedule(self, schedule):
        for index, existing in enumerate(self.opshop_pickup_schedules):
            if existing.schedule_id == schedule.schedule_id:
                self.opshop_pickup_schedules[index] = schedule
                return schedule
        self.opshop_pickup_schedules.append(schedule)
        return schedule

    def list_opshop_pickup_tasks(self):
        return sorted(
            self.opshop_pickup_tasks,
            key=lambda task: task.pickup_task_id,
        )

    def list_opshop_pickup_tasks_for_window(self, start_date, end_date):
        return sorted(
            [
                task
                for task in self.opshop_pickup_tasks
                if start_date <= task.pickup_date <= end_date
            ],
            key=lambda task: (task.pickup_date, task.pickup_task_id),
        )

    def list_opshop_pickup_board_items_for_window(self, start_date, end_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status != "ACTIVE":
                continue
            if not (start_date <= task.pickup_date <= end_date):
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_scheduled_opshop_pickup_board_items_for_window(self, start_date, end_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if not (start_date <= task.pickup_date <= end_date):
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "REGULAR":
                continue
            if schedule.pickup_category != "NORMAL":
                continue
            if not schedule.active_flag or schedule.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_oncall_opshop_pickup_board_items(self, dispatch_date):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if task.pickup_date < dispatch_date:
                continue
            if task.generated_from != "ON_CALL":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL":
                continue
            if schedule.pickup_category != "NORMAL":
                continue
            if not schedule.active_flag or schedule.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def list_countryside_opshop_pickup_board_items(self, dispatch_date=None):
        items = []
        for task in self.opshop_pickup_tasks:
            if task.status not in {"ACTIVE", "ASSIGNED"}:
                continue
            if dispatch_date and task.pickup_date < dispatch_date:
                continue
            if task.generated_from != "ON_CALL":
                continue
            schedule = self.get_opshop_pickup_schedule(task.schedule_id)
            if not schedule or schedule.run_type != "ON_CALL":
                continue
            if schedule.pickup_category != "COUNTRYSIDE":
                continue
            route_group = self.get_countryside_route_group(schedule.route_group_id)
            if not route_group or not route_group.active_flag or route_group.status != "Active":
                continue
            location = self.get_opshop_location(task.opshop_id)
            items.append(self._opshop_pickup_board_item(task, schedule, location))

        return sorted(
            items,
            key=lambda item: (
                item.pickup_date,
                item.route_group_name or "",
                item.suburb or "",
                item.opshop_name or "",
                item.pickup_task_id,
            ),
        )

    def find_opshop_pickup_task_by_schedule_and_date(self, schedule_id, pickup_date):
        return next(
            (
                task
                for task in self.opshop_pickup_tasks
                if task.schedule_id == schedule_id and task.pickup_date == pickup_date
            ),
            None,
        )

    def get_opshop_pickup_task(self, pickup_task_id):
        return next(
            (
                task
                for task in self.opshop_pickup_tasks
                if task.pickup_task_id == pickup_task_id
            ),
            None,
        )

    def insert_opshop_pickup_task(self, task):
        if self.get_opshop_pickup_task(task.pickup_task_id):
            raise ValueError(f"OP SHOP pickup task already exists: {task.pickup_task_id}")
        self.opshop_pickup_tasks.append(task)
        return task

    def upsert_opshop_pickup_task(self, task):
        for index, existing in enumerate(self.opshop_pickup_tasks):
            if existing.pickup_task_id == task.pickup_task_id:
                self.opshop_pickup_tasks[index] = task
                return task
        self.opshop_pickup_tasks.append(task)
        return task

    def update_opshop_pickup_task_assignment_status(
        self,
        pickup_task_id,
        status,
        driver_id=None,
        trip_no=None,
    ):
        task = self.get_opshop_pickup_task(pickup_task_id)
        if not task:
            return None
        task.status = status
        task.driver_id = driver_id
        task.trip_no = trip_no
        task.updated_at = "2026-05-19T00:00:00+00:00"
        return task

    def apply_opshop_pickup_assignment_batch(
        self,
        dispatch_date,
        tasks,
        remove_all_existing=False,
    ):
        original_tasks = deepcopy(self.opshop_pickup_tasks)
        original_assignments = deepcopy(self.assignments)
        try:
            for task in tasks:
                self.upsert_opshop_pickup_task(task)
                if remove_all_existing:
                    self.remove_assignments_for_task(
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                    )
                if task.driver_id:
                    self.upsert_assignment(
                        dispatch_date,
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                        task.driver_id,
                        "trip1",
                    )
                else:
                    self.remove_assignment(
                        dispatch_date,
                        "OPSHOP_PICKUP",
                        task.pickup_task_id,
                    )
        except Exception:
            self.opshop_pickup_tasks = original_tasks
            self.assignments = original_assignments
            raise
        return [self.get_opshop_pickup_task(task.pickup_task_id) for task in tasks]

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            order = self.get_order(task_id)
            return order if order and order.status == "ACTIVE" else None
        if task_type == "OPSHOP_PICKUP":
            task = self.get_opshop_pickup_task(task_id)
            return task if task and task.status == "ACTIVE" else None
        return None

    def _opshop_pickup_board_item(self, task, schedule, location):
        return OpShopPickupBoardItem(
            pickup_task_id=task.pickup_task_id,
            task_type=task.task_type,
            schedule_id=task.schedule_id,
            opshop_id=task.opshop_id,
            opshop_name=location.name if location else "",
            suburb=location.suburb if location else None,
            street_address=location.street_address if location else None,
            area_region=location.area_region if location else None,
            pickup_date=task.pickup_date,
            dispatch_date=task.dispatch_date,
            run_day=schedule.run_day if schedule else None,
            run_type=schedule.run_type if schedule else None,
            pickup_frequency=schedule.pickup_frequency if schedule else None,
            time_window=schedule.time_window if schedule else None,
            call_before_arrival=schedule.call_before_arrival if schedule else False,
            call_timing=schedule.call_timing if schedule else None,
            primary_contact=location.primary_contact if location else None,
            primary_phone=location.primary_phone if location else None,
            secondary_contact=location.secondary_contact if location else None,
            secondary_phone=location.secondary_phone if location else None,
            access_type=location.access_type if location else None,
            key_required=location.key_required if location else False,
            trailer_restriction=location.trailer_restriction if location else None,
            status=task.status,
            generated_from=task.generated_from,
            status_notes=location.status_notes if location else None,
            task_notes=task.notes,
            driver_id=task.driver_id,
            trip_no=task.trip_no,
            is_assigned=bool(task.driver_id or task.trip_no),
            default_driver_id=schedule.default_driver_id if schedule else None,
            default_driver_alias=schedule.default_driver_alias if schedule else None,
            default_driver_name=schedule.default_driver_name_snapshot if schedule else None,
            assigned_driver_id=task.driver_id,
            assigned_driver_name=self.get_driver(task.driver_id).name if task.driver_id and self.get_driver(task.driver_id) else None,
            pickup_category=schedule.pickup_category if schedule else "NORMAL",
            route_group_id=schedule.route_group_id if schedule else None,
            route_group_name=self.get_countryside_route_group(schedule.route_group_id).route_group_name if schedule and schedule.route_group_id and self.get_countryside_route_group(schedule.route_group_id) else None,
        )

    def create_order(self, order):
        if self.get_order(order.order_id):
            raise ValueError(f"Order already exists: {order.order_id}")
        self.orders.append(order)
        return order

    def update_order(self, order):
        for index, existing in enumerate(self.orders):
            if existing.order_id == order.order_id:
                self.orders[index] = order
                return order
        raise ValueError(f"Order does not exist: {order.order_id}")

    def cancel_order(self, order_id):
        order = self.get_order(order_id)
        if not order:
            raise ValueError(f"Order does not exist: {order_id}")
        order.status = "CANCELLED"
        return order

    def create_driver(self, driver):
        if self.get_driver(driver.driver_id):
            raise ValueError(f"Driver already exists: {driver.driver_id}")
        self.drivers.append(driver)
        return driver

    def update_driver(self, driver):
        for index, existing in enumerate(self.drivers):
            if existing.driver_id == driver.driver_id and not existing.is_deleted:
                self.drivers[index] = driver
                return driver
        raise ValueError(f"Driver does not exist: {driver.driver_id}")

    def delete_driver(self, driver_id):
        driver = self.get_driver(driver_id)
        if not driver or driver.is_deleted:
            raise ValueError(f"Driver does not exist: {driver_id}")
        driver.is_deleted = True
        driver.is_available = False
        return True

    def create_vehicle(self, vehicle):
        if self.get_vehicle(vehicle.vehicle_id):
            raise ValueError(f"Vehicle already exists: {vehicle.vehicle_id}")
        self.vehicles.append(vehicle)
        return vehicle

    def create_operator_account(self, account_name, password_hash, password_salt):
        if self.get_operator_account_by_name(account_name):
            raise ValueError("Account name already exists")
        account = OperatorAccountRecord(
            account_id=self._next_operator_account_id,
            account_name=account_name,
            password_hash=password_hash,
            password_salt=password_salt,
            created_at="in-memory",
            updated_at="in-memory",
        )
        self._next_operator_account_id += 1
        self.operator_accounts.append(account)
        return account

    def update_operator_account_password(self, account_id, password_hash, password_salt):
        account = self.get_operator_account_by_id(account_id)
        if not account:
            raise ValueError("Operator account does not exist")
        account.password_hash = password_hash
        account.password_salt = password_salt
        account.updated_at = "in-memory"
        return account

    def update_vehicle(self, vehicle):
        for index, existing in enumerate(self.vehicles):
            if existing.vehicle_id == vehicle.vehicle_id and not existing.is_deleted:
                self.vehicles[index] = vehicle
                return vehicle
        raise ValueError(f"Vehicle does not exist: {vehicle.vehicle_id}")

    def delete_vehicle(self, vehicle_id):
        vehicle = self.get_vehicle(vehicle_id)
        if not vehicle or vehicle.is_deleted:
            raise ValueError(f"Vehicle does not exist: {vehicle_id}")
        vehicle.is_deleted = True
        vehicle.is_available = False
        return True

    def has_assignment_for_task(self, task_type, task_id):
        return any(
            assignment.task_type == task_type and assignment.task_id == task_id
            for assignment in self.assignments
        )

    def driver_has_active_assignments(self, driver_id):
        return any(assignment.driver_id == driver_id for assignment in self.assignments)

    def driver_has_vehicle_selection(self, driver_id):
        return any(
            assignment.driver_id == driver_id
            for assignment in self.driver_vehicle_assignments
        )

    def driver_has_final_summary_history(self, driver_id):
        return any(
            summary.driver_id == driver_id for summary in self.final_trip_summaries
        )

    def vehicle_has_current_selection(self, vehicle_id):
        return any(
            assignment.vehicle_id == vehicle_id
            for assignment in self.driver_vehicle_assignments
        )

    def vehicle_has_final_summary_history(self, vehicle_id):
        return any(
            summary.vehicle_id == vehicle_id for summary in self.final_trip_summaries
        )

    def upsert_assignment(self, dispatch_date, task_type, task_id, driver_id, trip_no):
        existing = self.get_assignment(dispatch_date, task_type, task_id)
        if existing:
            existing.driver_id = driver_id
            existing.trip_no = trip_no
            return existing

        assignment = ManualDispatchAssignment(
            assignment_id=self._create_assignment_id(),
            dispatch_date=dispatch_date,
            task_type=task_type,
            task_id=task_id,
            driver_id=driver_id,
            trip_no=trip_no,
        )
        self.assignments.append(assignment)
        return assignment

    def get_assignment(self, dispatch_date, task_type, task_id):
        return next(
            (
                assignment
                for assignment in self.assignments
                if assignment.dispatch_date == dispatch_date
                and assignment.task_type == task_type
                and assignment.task_id == task_id
            ),
            None,
        )

    def find_assignment_for_task(self, task_type, task_id):
        return next(
            (
                assignment
                for assignment in self.assignments
                if assignment.task_type == task_type
                and assignment.task_id == task_id
            ),
            None,
        )

    def remove_assignment(self, dispatch_date, task_type, task_id):
        before_count = len(self.assignments)
        self.assignments = [
            assignment
            for assignment in self.assignments
            if not (
                assignment.dispatch_date == dispatch_date
                and assignment.task_type == task_type
                and assignment.task_id == task_id
            )
        ]
        return len(self.assignments) != before_count

    def remove_assignments_for_task(self, task_type, task_id):
        before_count = len(self.assignments)
        self.assignments = [
            assignment
            for assignment in self.assignments
            if not (
                assignment.task_type == task_type
                and assignment.task_id == task_id
            )
        ]
        return len(self.assignments) != before_count

    def upsert_driver_vehicle_assignment(self, dispatch_date, delivery_date, driver_id, vehicle_id):
        existing = next(
            (
                assignment
                for assignment in self.driver_vehicle_assignments
                if assignment.dispatch_date == dispatch_date
                and assignment.delivery_date == delivery_date
                and assignment.driver_id == driver_id
            ),
            None,
        )
        if existing:
            existing.vehicle_id = vehicle_id
            return existing

        assignment = ManualDriverVehicleAssignment(
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )
        self.driver_vehicle_assignments.append(assignment)
        return assignment

    def remove_driver_vehicle_assignment(self, dispatch_date, driver_id, delivery_date=None):
        before_count = len(self.driver_vehicle_assignments)
        self.driver_vehicle_assignments = [
            assignment
            for assignment in self.driver_vehicle_assignments
            if not (
                assignment.dispatch_date == dispatch_date
                and assignment.driver_id == driver_id
                and (not delivery_date or assignment.delivery_date == delivery_date)
            )
        ]
        return len(self.driver_vehicle_assignments) != before_count

    def save_final_trip_summary(self, summary, rows, opshop_rows=None):
        if self.has_saved_final_trip_summary(
            summary["dispatch_date"], summary["driver_id"], summary.get("delivery_date")
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        self._remove_generated_final_trip_summary_for_driver(
            summary["dispatch_date"],
            summary.get("delivery_date") or summary["dispatch_date"],
            summary["driver_id"],
        )
        final_summary = self._build_final_trip_summary(summary, rows, opshop_rows, "SAVED")
        self.final_trip_summaries.append(final_summary)
        self._finalize_order_rows(final_summary.dispatch_date, rows)
        return final_summary

    def create_generated_final_trip_summary(self, summary, rows, opshop_rows=None):
        if self.has_saved_final_trip_summary(
            summary["dispatch_date"], summary["driver_id"], summary.get("delivery_date")
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        self._remove_generated_final_trip_summary_for_driver(
            summary["dispatch_date"],
            summary.get("delivery_date") or summary["dispatch_date"],
            summary["driver_id"],
        )
        final_summary = self._build_final_trip_summary(summary, rows, opshop_rows, "GENERATED")
        self.final_trip_summaries.append(final_summary)
        return final_summary

    def save_generated_final_trip_summary(self, summary_id, saved_by_account_name, saved_by_account_id):
        summary = self.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        if summary.status != "GENERATED":
            raise ValueError("Only generated Final Trip Summaries can be saved.")
        if self.has_saved_final_trip_summary(
            summary.dispatch_date,
            summary.driver_id,
            summary.delivery_date,
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        summary.status = "SAVED"
        summary.saved_at = "in-memory"
        summary.saved_by_account_name = saved_by_account_name or "Unknown"
        summary.saved_by_account_id = saved_by_account_id
        rows = [
            {
                "task_type": order.task_type,
                "task_id": order.task_id,
            }
            for trip in summary.trips
            for order in trip.orders
        ]
        self._finalize_order_rows(summary.dispatch_date, rows)
        return summary

    def cancel_generated_final_trip_summary(self, summary_id):
        summary = self.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        if summary.status != "GENERATED":
            raise ValueError("Only generated Final Trip Summaries can be cancelled.")

        for trip in summary.trips or []:
            for order in trip.orders or []:
                if order.task_type != "ORDER" or not order.task_id:
                    continue
                existing_order = self.get_order(order.task_id)
                if existing_order and existing_order.status != "CANCELLED":
                    existing_order.status = "ACTIVE"
                self.upsert_assignment(
                    summary.dispatch_date,
                    "ORDER",
                    order.task_id,
                    summary.driver_id,
                    trip.trip_no,
                )

        self.final_trip_summaries = [
            existing
            for existing in self.final_trip_summaries
            if existing.summary_id != summary_id
        ]
        return True

    def _build_final_trip_summary(self, summary, rows, opshop_rows=None, status="SAVED"):
        summary_id = self._create_final_summary_id()
        opshop_rows = opshop_rows or []
        trips = []
        for trip_no in ("trip1", "trip2"):
            trip_orders = []
            for row in rows:
                if row["trip_no"] != trip_no:
                    continue
                trip_orders.append(
                    FinalTripSummaryOrderSnapshot(
                        row_id=self._create_final_summary_row_id(),
                        trip_no=row["trip_no"],
                        row_no=row["row_no"],
                        task_type=row["task_type"],
                        task_id=row["task_id"],
                        order_id_snapshot=row.get("order_id_snapshot"),
                        invoice_number_snapshot=row.get("invoice_number_snapshot"),
                        order_no_snapshot=row.get("order_no_snapshot"),
                        company_name_snapshot=row.get("company_name_snapshot"),
                        suburb_snapshot=row.get("suburb_snapshot"),
                        delivery_address_snapshot=row.get("delivery_address_snapshot"),
                        product_snapshot=row.get("product_snapshot"),
                        pallet_quantity_snapshot=row["pallet_quantity_snapshot"],
                        loose_bags_quantity_snapshot=row["loose_bags_quantity_snapshot"],
                        note_snapshot=row.get("note_snapshot"),
                        product_lines_snapshot=[
                            ProductDetailLine(
                                product_name=line.get("product_name") or "",
                                quantity=int(line.get("quantity") or 0),
                                unit=line.get("unit") or "",
                            )
                            for line in (row.get("product_lines_snapshot") or [])
                        ],
                        estimated_distance_km_from_warehouse_snapshot=row.get(
                            "estimated_distance_km_from_warehouse_snapshot"
                        ),
                    )
                )
            if trip_orders:
                trips.append(FinalTripSummaryTrip(trip_no=trip_no, orders=trip_orders))

        opshop_pickups = [
            FinalTripSummaryOpShopPickupSnapshot(
                row_id=self._create_final_summary_opshop_row_id(),
                row_no=row["row_no"],
                pickup_task_id_snapshot=row["pickup_task_id_snapshot"],
                opshop_name_snapshot=row["opshop_name_snapshot"],
                suburb_snapshot=row.get("suburb_snapshot"),
                street_address_snapshot=row.get("street_address_snapshot"),
                area_region_snapshot=row.get("area_region_snapshot"),
                pickup_date_snapshot=row["pickup_date_snapshot"],
                run_type_snapshot=row.get("run_type_snapshot"),
                pickup_frequency_snapshot=row.get("pickup_frequency_snapshot"),
                time_window_snapshot=row.get("time_window_snapshot"),
                primary_contact_snapshot=row.get("primary_contact_snapshot"),
                primary_phone_snapshot=row.get("primary_phone_snapshot"),
                secondary_contact_snapshot=row.get("secondary_contact_snapshot"),
                secondary_phone_snapshot=row.get("secondary_phone_snapshot"),
                access_type_snapshot=row.get("access_type_snapshot"),
                key_required_snapshot=bool(row.get("key_required_snapshot")),
                trailer_restriction_snapshot=row.get("trailer_restriction_snapshot"),
                notes_snapshot=row.get("notes_snapshot"),
                status_snapshot=row["status_snapshot"],
                pickup_category_snapshot=row.get("pickup_category_snapshot"),
                route_group_id_snapshot=row.get("route_group_id_snapshot"),
                route_group_name_snapshot=row.get("route_group_name_snapshot"),
            )
            for row in opshop_rows
        ]

        saved_at = summary.get("saved_at") or summary.get("generated_at") or "in-memory"
        return FinalTripSummary(
            summary_id=summary_id,
            dispatch_date=summary["dispatch_date"],
            delivery_date=summary.get("delivery_date") or summary["dispatch_date"],
            driver_id=summary["driver_id"],
            driver_name_snapshot=summary["driver_name_snapshot"],
            vehicle_id=summary.get("vehicle_id"),
            vehicle_rego_snapshot=summary.get("vehicle_rego_snapshot"),
            total_pallets=summary["total_pallets"],
            total_loose_bags=summary["total_loose_bags"],
            status=status,
            generated_at=summary.get("generated_at") or saved_at,
            saved_at=saved_at,
            saved_by_account_name=summary.get("saved_by_account_name") or "Unknown",
            saved_by_account_id=summary.get("saved_by_account_id"),
            trips=trips,
            opshop_pickups=opshop_pickups,
        )

    def _finalize_order_rows(self, dispatch_date, rows):
        for row in rows:
            if row["task_type"] == "ORDER":
                order = self.get_order(row["task_id"])
                if order and order.status == "ACTIVE":
                    order.status = "FINALIZED"
                self.remove_assignment(dispatch_date, row["task_type"], row["task_id"])

    def _remove_generated_final_trip_summary_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        self.final_trip_summaries = [
            summary
            for summary in self.final_trip_summaries
            if not (
                summary.dispatch_date == dispatch_date
                and summary.delivery_date == delivery_date
                and summary.driver_id == driver_id
                and summary.status == "GENERATED"
            )
        ]

    def _create_assignment_id(self):
        assignment_id = f"A-{self._next_assignment_number:03d}"
        self._next_assignment_number += 1
        return assignment_id

    def _create_final_summary_id(self):
        summary_id = f"FTS-{self._next_final_summary_number:03d}"
        self._next_final_summary_number += 1
        return summary_id

    def _create_final_summary_row_id(self):
        row_id = f"FSR-{self._next_final_summary_row_number:03d}"
        self._next_final_summary_row_number += 1
        return row_id

    def _create_final_summary_opshop_row_id(self):
        row_id = f"FSO-{self._next_final_summary_opshop_row_number:03d}"
        self._next_final_summary_opshop_row_number += 1
        return row_id


def _normalize_text_key(value):
    return " ".join(str(value or "").strip().lower().split())
