"""Shared validation contract for Manual Dispatch System Logbook tools."""

from __future__ import annotations

import re


LOGBOOK_FILENAME_PATTERN = "manual_dispatch_logbook_*.txt"
LOGBOOK_FILENAME_REGEX = re.compile(
    r"^manual_dispatch_logbook_([0-9]{4})-(0[1-9]|1[0-2])\.txt$"
)

REQUIRED_FIELDS = (
    "time",
    "result",
    "workspace",
    "actor",
    "action",
    "entity_type",
    "entity_id",
    "summary",
    "dispatch_date",
    "delivery_date",
    "pickup_date",
    "driver",
    "vehicle",
    "run_sheet_id",
    "collection_id",
    "metadata",
)
NON_EMPTY_STRING_FIELDS = (
    "time",
    "result",
    "workspace",
    "actor",
    "action",
    "summary",
)
NULLABLE_STRING_FIELDS = (
    "entity_type",
    "entity_id",
    "dispatch_date",
    "delivery_date",
    "pickup_date",
    "driver",
    "vehicle",
    "run_sheet_id",
    "collection_id",
)
DATE_FIELDS = ("dispatch_date", "delivery_date", "pickup_date")

ALLOWED_RESULTS = frozenset({"SUCCESS", "PARTIAL", "FAILED"})
ALLOWED_WORKSPACES = frozenset({"DELIVERY", "OPSHOP", "SYSTEM"})

INCIDENT_ANNOTATION_ACTION = "LOGBOOK_TEST_DATA_ANNOTATED"
INTEGRITY_INCIDENT_ANNOTATION_ACTION = "LOGBOOK_INTEGRITY_INCIDENT_ANNOTATED"
INCIDENT_ANNOTATION_ACTIONS = frozenset(
    {
        INCIDENT_ANNOTATION_ACTION,
        INTEGRITY_INCIDENT_ANNOTATION_ACTION,
    }
)
KNOWN_ACTIONS = frozenset(
    {
        "ORDER_CREATED",
        "ORDER_UPDATED",
        "ORDER_CANCELLED",
        "ORDER_DELIVERY_AREA_OVERRIDDEN",
        "ORDER_DELIVERY_AREA_OVERRIDE_CLEARED",
        "ORDER_DELIVERY_DATE_ROLLED_FORWARD",
        "ORDER_ASSIGNED",
        "ORDER_REASSIGNED",
        "ORDER_UNASSIGNED",
        "VEHICLE_ASSIGNED",
        "VEHICLE_CHANGED",
        "VEHICLE_CLEARED",
        "DELIVERY_RUN_SHEET_GENERATED",
        "DELIVERY_RUN_SHEET_CANCELLED",
        "DELIVERY_RUN_SHEET_SAVED",
        "DELIVERY_RUN_SHEET_EXPORTED",
        "DELIVERY_RUN_SHEETS_DAILY_EXPORTED",
        "DELIVERY_RUN_SHEET_CLOSED",
        "DELIVERY_ORDER_DELIVERED",
        "DELIVERY_ORDER_RETURNED_TO_POOL",
        "ATTACHE_IMPORT_CONFIRMED",
        "OPSHOP_TASK_CREATED",
        "OPSHOP_TASK_UPDATED",
        "OPSHOP_TASK_CANCELLED",
        "OPSHOP_TASK_ASSIGNED",
        "OPSHOP_TASK_REASSIGNED",
        "OPSHOP_TASK_UNASSIGNED",
        "COUNTRYSIDE_ROUTE_GROUP_ASSIGNED",
        "PICKUP_COLLECTION_GENERATED",
        "PICKUP_COLLECTION_CANCELLED",
        "PICKUP_COLLECTION_SAVED",
        "PICKUP_COLLECTION_WEIGHT_SHEET_UPDATED",
        "PICKUP_COLLECTION_EXPORTED",
        "PICKUP_COLLECTIONS_DAILY_EXPORTED",
        "REGULAR_TEMPLATE_CREATED",
        "REGULAR_TEMPLATE_UPDATED",
        "REGULAR_TEMPLATE_DISABLED",
        "ONCALL_TEMPLATE_CREATED",
        "ONCALL_TEMPLATE_UPDATED",
        "ONCALL_TEMPLATE_DISABLED",
        "COUNTRYSIDE_ROUTE_GROUP_CREATED",
        "COUNTRYSIDE_ROUTE_GROUP_RENAMED",
        "COUNTRYSIDE_ROUTE_GROUP_DISABLED",
        "COUNTRYSIDE_MEMBERSHIP_ADDED",
        "COUNTRYSIDE_MEMBERSHIP_MOVED",
        "COUNTRYSIDE_MEMBERSHIP_REMOVED",
        "REGULAR_WORKBOOK_IMPORT_COMPLETED",
        "ONCALL_WORKBOOK_IMPORT_COMPLETED",
        "COUNTRYSIDE_WORKBOOK_IMPORT_COMPLETED",
        "DUPLICATE_OPSHOP_LOCATION_REPAIR_COMPLETED",
        "SOURCE_DRIVER_BACKFILL_DRY_RUN",
        "SOURCE_DRIVER_BACKFILL_APPLIED",
        "LEGACY_WORKSPACE_MIGRATION_DRY_RUN",
        "LEGACY_WORKSPACE_MIGRATION_APPLIED",
        "ASSIGNMENT_IDENTITY_REPAIR_COMPLETED",
        *INCIDENT_ANNOTATION_ACTIONS,
    }
)
