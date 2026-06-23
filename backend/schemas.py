from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProductDetailLine:
    product_name: str
    quantity: int
    unit: str


@dataclass
class Order:
    order_id: str
    invoice_number: Optional[str]
    order_no: Optional[str]
    company_name: str
    phone: Optional[str]
    delivery_address: str
    suburb: str
    postcode: str
    delivery_date: str
    zone: str
    urgency: str
    preferred_driver_id: Optional[str]
    pallet_quantity: int
    loose_bags_quantity: int
    start_time: Optional[str]
    end_time: Optional[str]
    note: Optional[str]
    status: str = "ACTIVE"
    product_lines: List[ProductDetailLine] = field(default_factory=list)
    estimated_distance_km_from_warehouse: Optional[float] = None


@dataclass
class Driver:
    driver_id: str
    name: str
    start_time: Optional[str]
    end_time: Optional[str]
    is_available: bool
    preferred_zone: Optional[str]
    pallet_only: bool
    license_no: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    is_deleted: bool = False


@dataclass
class Vehicle:
    vehicle_id: str
    rego: str
    type: str
    is_available: bool
    pallet_capacity: int
    tub_capacity: int
    trolley_capacity: int
    stillage_capacity: int
    is_deleted: bool = False


@dataclass
class ManualDispatchAssignment:
    assignment_id: str
    dispatch_date: str
    task_type: str
    task_id: str
    driver_id: str
    trip_no: str


@dataclass
class ManualDriverVehicleAssignment:
    dispatch_date: str
    delivery_date: str
    driver_id: str
    vehicle_id: str


@dataclass
class OpShopLocation:
    opshop_id: str
    name: str
    suburb: Optional[str]
    street_address: Optional[str]
    area_region: Optional[str]
    primary_contact: Optional[str]
    primary_phone: Optional[str]
    secondary_contact: Optional[str]
    secondary_phone: Optional[str]
    access_type: Optional[str]
    key_required: bool
    trailer_restriction: Optional[str]
    status_notes: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class OpShopCountrysideRouteGroup:
    route_group_id: str
    route_group_name: str
    status: str
    active_flag: bool
    display_order: int
    source_marker: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class OpShopPickupSchedule:
    schedule_id: str
    opshop_id: str
    run_day: Optional[str]
    run_type: str
    pickup_frequency: Optional[str]
    time_window: Optional[str]
    call_before_arrival: bool
    call_timing: Optional[str]
    status: str
    active_flag: bool
    fortnight_group: Optional[str]
    review_required: bool
    review_reason: Optional[str]
    created_at: str
    updated_at: str
    default_driver_id: Optional[str] = None
    default_driver_alias: Optional[str] = None
    default_driver_name_snapshot: Optional[str] = None
    pickup_category: str = "NORMAL"
    route_group_id: Optional[str] = None


@dataclass
class OpShopPickupTask:
    pickup_task_id: str
    schedule_id: Optional[str]
    opshop_id: str
    pickup_date: str
    task_type: str
    generated_from: str
    status: str
    dispatch_date: Optional[str]
    driver_id: Optional[str]
    trip_no: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class EnsureOpShopPickupTasksRequest:
    start_date: str
    days: int = 14


@dataclass
class EnsureOpShopPickupTasksResult:
    window_start: str
    window_end: str
    days: int
    schedules_checked: int
    tasks_created: int
    tasks_existing: int
    schedules_skipped: int
    skip_reasons: Dict[str, int] = field(default_factory=dict)
    warnings: Dict[str, int] = field(default_factory=dict)
    created_tasks: List[OpShopPickupTask] = field(default_factory=list)


@dataclass
class OpShopPickupBoardItem:
    pickup_task_id: str
    task_type: str
    schedule_id: Optional[str]
    opshop_id: str
    opshop_name: str
    suburb: Optional[str]
    street_address: Optional[str]
    area_region: Optional[str]
    pickup_date: str
    dispatch_date: Optional[str]
    run_day: Optional[str]
    run_type: Optional[str]
    pickup_frequency: Optional[str]
    time_window: Optional[str]
    call_before_arrival: bool
    call_timing: Optional[str]
    primary_contact: Optional[str]
    primary_phone: Optional[str]
    secondary_contact: Optional[str]
    secondary_phone: Optional[str]
    access_type: Optional[str]
    key_required: bool
    trailer_restriction: Optional[str]
    status: str
    generated_from: str
    status_notes: Optional[str]
    task_notes: Optional[str]
    driver_id: Optional[str]
    trip_no: Optional[str]
    is_assigned: bool
    default_driver_id: Optional[str] = None
    default_driver_alias: Optional[str] = None
    default_driver_name: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    assigned_to_locked: bool = False
    pickup_category: str = "NORMAL"
    route_group_id: Optional[str] = None
    route_group_name: Optional[str] = None


@dataclass
class OpShopWorkspacePickupItem:
    pickup_task_id: str
    task_type: str
    schedule_id: Optional[str]
    opshop_id: str
    opshop_name: str
    suburb: Optional[str]
    street_address: Optional[str]
    area_region: Optional[str]
    pickup_date: str
    dispatch_date: Optional[str]
    run_day: Optional[str]
    run_type: Optional[str]
    pickup_frequency: Optional[str]
    time_window: Optional[str]
    call_before_arrival: bool
    call_timing: Optional[str]
    primary_contact: Optional[str]
    primary_phone: Optional[str]
    secondary_contact: Optional[str]
    secondary_phone: Optional[str]
    access_type: Optional[str]
    key_required: bool
    trailer_restriction: Optional[str]
    status: str
    generated_from: str
    status_notes: Optional[str]
    task_notes: Optional[str]
    driver_id: Optional[str]
    is_assigned: bool
    default_driver_id: Optional[str]
    default_driver_alias: Optional[str]
    default_driver_name: Optional[str]
    assigned_driver_id: Optional[str]
    assigned_driver_name: Optional[str]
    assigned_to_locked: bool
    pickup_category: str
    route_group_id: Optional[str]
    route_group_name: Optional[str]


@dataclass
class OpShopPickupScheduleCandidate:
    schedule_id: str
    opshop_id: str
    opshop_name: str
    suburb: Optional[str]
    run_day: Optional[str]
    run_type: str
    pickup_frequency: Optional[str]
    time_window: Optional[str]
    primary_phone: Optional[str]
    default_driver_id: Optional[str] = None
    default_driver_alias: Optional[str] = None
    default_driver_name: Optional[str] = None
    pickup_category: str = "NORMAL"
    route_group_id: Optional[str] = None
    route_group_name: Optional[str] = None


@dataclass
class OpShopTemplate:
    schedule_id: str
    opshop_id: str
    run_type: str
    run_day: Optional[str]
    name: str
    suburb: Optional[str]
    street_address: Optional[str]
    area_region: Optional[str]
    primary_contact: Optional[str]
    primary_phone: Optional[str]
    secondary_contact: Optional[str]
    secondary_phone: Optional[str]
    pickup_frequency: Optional[str]
    time_window: Optional[str]
    call_before_arrival: bool
    call_timing: Optional[str]
    access_type: Optional[str]
    key_required: bool
    trailer_restriction: Optional[str]
    status_notes: Optional[str]
    default_driver_id: Optional[str]
    default_driver_alias: Optional[str]
    default_driver_name: Optional[str]
    status: str
    active_flag: bool
    pickup_category: str = "NORMAL"
    route_group_id: Optional[str] = None
    route_group_name: Optional[str] = None


@dataclass
class CreateOpShopTemplateRequest:
    run_type: Optional[str] = None
    run_day: Optional[str] = None
    name: Optional[str] = None
    suburb: Optional[str] = None
    street_address: Optional[str] = None
    area_region: Optional[str] = None
    primary_contact: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_contact: Optional[str] = None
    secondary_phone: Optional[str] = None
    pickup_frequency: Optional[str] = None
    time_window: Optional[str] = None
    call_before_arrival: Optional[bool] = None
    call_timing: Optional[str] = None
    access_type: Optional[str] = None
    key_required: Optional[bool] = None
    trailer_restriction: Optional[str] = None
    status_notes: Optional[str] = None
    default_driver_id: Optional[str] = None
    pickup_category: Optional[str] = None
    route_group_id: Optional[str] = None


@dataclass
class UpdateOpShopTemplateRequest(CreateOpShopTemplateRequest):
    pass


@dataclass
class CreateOpShopCountrysideRouteGroupRequest:
    route_group_name: Optional[str] = None
    display_order: Optional[int] = None
    source_marker: Optional[str] = None


@dataclass
class UpdateOpShopCountrysideRouteGroupRequest:
    route_group_name: Optional[str] = None
    display_order: Optional[int] = None
    status: Optional[str] = None
    active_flag: Optional[bool] = None
    source_marker: Optional[str] = None


@dataclass
class AddCountrysideRouteMembershipRequest:
    name: Optional[str] = None
    suburb: Optional[str] = None
    street_address: Optional[str] = None
    area_region: Optional[str] = None
    primary_contact: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_contact: Optional[str] = None
    secondary_phone: Optional[str] = None
    pickup_frequency: Optional[str] = None
    time_window: Optional[str] = None
    call_before_arrival: Optional[bool] = None
    call_timing: Optional[str] = None
    access_type: Optional[str] = None
    key_required: Optional[bool] = None
    trailer_restriction: Optional[str] = None
    status_notes: Optional[str] = None
    default_driver_id: Optional[str] = None


@dataclass
class MoveCountrysideRouteMembershipRequest:
    target_route_group_id: Optional[str] = None


@dataclass
class CreateOpShopPickupTaskRequest:
    schedule_id: Optional[str] = None
    pickup_date: Optional[str] = None
    notes: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    dispatch_date: Optional[str] = None


@dataclass
class UpdateOpShopPickupTaskRequest:
    pickup_date: Optional[str] = None
    notes: Optional[str] = None
    dispatch_date: Optional[str] = None


@dataclass
class ApplyWeeklyOpShopPickupAssignmentsRequest:
    dispatch_date: str
    assignments: List[dict] = field(default_factory=list)


@dataclass
class ApplyOncallOpShopPickupAssignmentsRequest:
    dispatch_date: str
    assignments: List[dict] = field(default_factory=list)


@dataclass
class ApplyCountrysideOpShopPickupAssignmentsRequest:
    dispatch_date: str
    assignments: List[dict] = field(default_factory=list)


@dataclass
class AssignCountrysideRouteGroupRequest:
    dispatch_date: str
    pickup_date: str
    assigned_driver_id: str
    notes: Optional[str] = None


@dataclass
class ManualDispatchBoardResponse:
    dispatch_date: str
    orders: List[Order]
    drivers: List[Driver]
    vehicles: List[Vehicle]
    assignments: List[ManualDispatchAssignment]
    driver_vehicle_assignments: List[ManualDriverVehicleAssignment]
    opshop_pickups: List[OpShopPickupBoardItem] = field(default_factory=list)
    assigned_opshop_pickups: List[OpShopPickupBoardItem] = field(default_factory=list)
    scheduled_opshop_pickups: List[OpShopPickupBoardItem] = field(default_factory=list)
    oncall_opshop_pickups: List[OpShopPickupBoardItem] = field(default_factory=list)
    countryside_route_groups: List[OpShopCountrysideRouteGroup] = field(default_factory=list)
    countryside_opshop_pickups: List[OpShopPickupBoardItem] = field(default_factory=list)
    opshop_regular_list_window_start: Optional[str] = None
    opshop_regular_list_window_end: Optional[str] = None
    finalized_driver_delivery_dates: List[dict] = field(default_factory=list)
    generated_final_trip_summaries: List[dict] = field(default_factory=list)


@dataclass
class DeliveryVehicleAssignmentLock:
    dispatch_date: str
    delivery_date: str
    driver_id: str
    run_sheet_id: str


@dataclass
class DeliveryWorkspaceBoardResponse:
    dispatch_date: str
    orders: List[Order]
    drivers: List[Driver]
    vehicles: List[Vehicle]
    assignments: List[ManualDispatchAssignment]
    driver_vehicle_assignments: List[ManualDriverVehicleAssignment]
    saved_vehicle_assignment_locks: List[DeliveryVehicleAssignmentLock]


@dataclass
class OpShopWorkspaceBoardResponse:
    dispatch_date: str
    opshop_pickups: List[OpShopWorkspacePickupItem]
    drivers: List[Driver]
    templates: List[OpShopTemplate]
    countryside_route_groups: List[OpShopCountrysideRouteGroup]


@dataclass
class DeliveryWorkspaceAssignOrderRequest:
    dispatch_date: Optional[str] = None
    order_id: Optional[str] = None
    driver_id: Optional[str] = None
    trip_no: Optional[str] = None


@dataclass
class DeliveryWorkspaceUnassignOrderRequest:
    dispatch_date: Optional[str] = None
    order_id: Optional[str] = None


@dataclass
class DeliveryWorkspaceVehicleAssignmentRequest:
    dispatch_date: Optional[str] = None
    delivery_date: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None


@dataclass
class DeliveryWorkspaceVehicleClearRequest:
    dispatch_date: Optional[str] = None
    delivery_date: Optional[str] = None
    driver_id: Optional[str] = None


@dataclass
class OpShopWorkspaceAssignmentBatchRequest:
    dispatch_date: Optional[str] = None
    assignments: List[dict] = field(default_factory=list)


@dataclass
class OpShopWorkspaceUnassignPickupRequest:
    dispatch_date: Optional[str] = None
    pickup_task_id: Optional[str] = None


@dataclass
class AssignTaskRequest:
    dispatch_date: str
    task_type: str
    task_id: str
    driver_id: str
    trip_no: str


@dataclass
class UnassignTaskRequest:
    dispatch_date: str
    task_type: str
    task_id: str


@dataclass
class AssignDriverVehicleRequest:
    dispatch_date: str
    driver_id: str
    vehicle_id: Optional[str] = None
    delivery_date: Optional[str] = None


@dataclass
class ManualDriverVehicleClearResponse:
    dispatch_date: str
    driver_id: str
    delivery_date: Optional[str] = None
    vehicle_id: Optional[str] = None
    cleared: bool = True


@dataclass
class FinalTripSummaryOrderSnapshot:
    row_id: Optional[str]
    trip_no: str
    row_no: int
    task_type: str
    task_id: str
    order_id_snapshot: str
    invoice_number_snapshot: Optional[str]
    company_name_snapshot: str
    suburb_snapshot: str
    delivery_address_snapshot: str
    product_snapshot: Optional[str]
    pallet_quantity_snapshot: int
    loose_bags_quantity_snapshot: int
    note_snapshot: Optional[str]
    order_no_snapshot: Optional[str] = None
    product_lines_snapshot: List[ProductDetailLine] = field(default_factory=list)
    estimated_distance_km_from_warehouse_snapshot: Optional[float] = None


@dataclass
class FinalTripSummaryTrip:
    trip_no: str
    orders: List[FinalTripSummaryOrderSnapshot]


@dataclass
class FinalTripSummaryOpShopPickupSnapshot:
    row_id: Optional[str]
    row_no: int
    pickup_task_id_snapshot: str
    opshop_name_snapshot: str
    suburb_snapshot: Optional[str]
    street_address_snapshot: Optional[str]
    area_region_snapshot: Optional[str]
    pickup_date_snapshot: str
    run_type_snapshot: Optional[str]
    pickup_frequency_snapshot: Optional[str]
    time_window_snapshot: Optional[str]
    primary_contact_snapshot: Optional[str]
    primary_phone_snapshot: Optional[str]
    secondary_contact_snapshot: Optional[str]
    secondary_phone_snapshot: Optional[str]
    access_type_snapshot: Optional[str]
    key_required_snapshot: bool
    trailer_restriction_snapshot: Optional[str]
    notes_snapshot: Optional[str]
    status_snapshot: str
    pickup_category_snapshot: Optional[str] = None
    route_group_id_snapshot: Optional[str] = None
    route_group_name_snapshot: Optional[str] = None


@dataclass
class FinalTripSummary:
    summary_id: str
    dispatch_date: str
    delivery_date: str
    driver_id: str
    driver_name_snapshot: str
    vehicle_id: Optional[str]
    vehicle_rego_snapshot: Optional[str]
    total_pallets: int
    total_loose_bags: int
    status: str
    generated_at: str
    saved_at: str
    saved_by_account_name: str
    saved_by_account_id: Optional[int]
    trips: List[FinalTripSummaryTrip]
    opshop_pickups: List[FinalTripSummaryOpShopPickupSnapshot] = field(default_factory=list)


@dataclass
class SaveFinalTripSummaryRequest:
    dispatch_date: str
    driver_id: str
    driver_name_snapshot: str
    vehicle_id: Optional[str]
    vehicle_rego_snapshot: Optional[str]
    total_pallets: int
    total_loose_bags: int
    generated_at: Optional[str]
    trips: List[dict]
    opshop_pickups: List[dict] = field(default_factory=list)
    delivery_date: Optional[str] = None
    saved_by_account_name: Optional[str] = None
    saved_by_account_id: Optional[int] = None


@dataclass
class DeliveryRunSheetOrderSnapshot:
    row_id: str
    trip_no: str
    row_no: int
    task_type: str
    task_id: str
    order_id_snapshot: Optional[str]
    invoice_number_snapshot: Optional[str]
    order_no_snapshot: Optional[str]
    company_name_snapshot: Optional[str]
    suburb_snapshot: Optional[str]
    delivery_address_snapshot: Optional[str]
    product_snapshot: Optional[str]
    pallet_quantity_snapshot: int
    loose_bags_quantity_snapshot: int
    note_snapshot: Optional[str]
    product_lines_snapshot: List[ProductDetailLine] = field(default_factory=list)
    estimated_distance_km_from_warehouse_snapshot: Optional[float] = None


@dataclass
class DeliveryRunSheetTrip:
    trip_no: str
    orders: List[DeliveryRunSheetOrderSnapshot] = field(default_factory=list)


@dataclass
class DeliveryRunSheet:
    run_sheet_id: str
    dispatch_date: str
    delivery_date: str
    driver_id: str
    driver_name_snapshot: str
    vehicle_id: Optional[str]
    vehicle_rego_snapshot: Optional[str]
    total_pallets: int
    total_loose_bags: int
    status: str
    generated_at: str
    saved_at: Optional[str]
    saved_by_account_name: Optional[str]
    saved_by_account_id: Optional[int]
    legacy_summary_id: Optional[str]
    trips: List[DeliveryRunSheetTrip] = field(default_factory=list)


@dataclass
class OpShopPickupCollectionRowSnapshot:
    row_id: str
    row_no: int
    pickup_task_id_snapshot: Optional[str]
    opshop_name_snapshot: Optional[str]
    suburb_snapshot: Optional[str]
    street_address_snapshot: Optional[str]
    area_region_snapshot: Optional[str]
    pickup_date_snapshot: Optional[str]
    run_type_snapshot: Optional[str]
    pickup_category_snapshot: Optional[str]
    route_group_id_snapshot: Optional[str]
    route_group_name_snapshot: Optional[str]
    pickup_frequency_snapshot: Optional[str]
    time_window_snapshot: Optional[str]
    primary_contact_snapshot: Optional[str]
    primary_phone_snapshot: Optional[str]
    secondary_contact_snapshot: Optional[str]
    secondary_phone_snapshot: Optional[str]
    access_type_snapshot: Optional[str]
    key_required_snapshot: bool
    trailer_restriction_snapshot: Optional[str]
    notes_snapshot: Optional[str]
    status_snapshot: Optional[str]
    call_before_arrival_snapshot: bool = False
    call_timing_snapshot: Optional[str] = None


@dataclass
class GenerateDeliveryRunSheetRequest:
    dispatch_date: Optional[str] = None
    delivery_date: Optional[str] = None
    driver_id: Optional[str] = None


@dataclass
class GenerateOpShopPickupCollectionRequest:
    dispatch_date: Optional[str] = None
    pickup_date: Optional[str] = None
    driver_id: Optional[str] = None


@dataclass
class SaveGeneratedWorkspaceSnapshotRequest:
    saved_by_account_name: Optional[str] = None
    saved_by_account_id: Optional[int] = None


@dataclass
class OpShopPickupCollection:
    collection_id: str
    dispatch_date: str
    pickup_date: str
    driver_id: str
    driver_name_snapshot: str
    status: str
    generated_at: str
    saved_at: Optional[str]
    saved_by_account_name: Optional[str]
    saved_by_account_id: Optional[int]
    legacy_summary_id: Optional[str]
    pickups: List[OpShopPickupCollectionRowSnapshot] = field(default_factory=list)


@dataclass
class OperatorAccountRecord:
    account_id: int
    account_name: str
    password_hash: str
    password_salt: str
    created_at: str
    updated_at: str


@dataclass
class OperatorAccountIdentity:
    account_id: int
    account_name: str


@dataclass
class RegisterOperatorAccountRequest:
    account_name: Optional[str] = None
    password: Optional[str] = None
    confirm_password: Optional[str] = None


@dataclass
class LoginOperatorAccountRequest:
    account_name: Optional[str] = None
    password: Optional[str] = None


@dataclass
class ResetOperatorPasswordRequest:
    account_name: Optional[str] = None
    admin_reset_code: Optional[str] = None
    new_password: Optional[str] = None
    confirm_password: Optional[str] = None


@dataclass
class CreateOrderRequest:
    invoice_number: Optional[str] = None
    order_no: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    delivery_date: Optional[str] = None
    zone: Optional[str] = None
    urgency: Optional[str] = None
    preferred_driver_id: Optional[str] = None
    pallet_quantity: Optional[int] = 0
    loose_bags_quantity: Optional[int] = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None
    product_lines: Optional[List[dict]] = None


@dataclass
class UpdateOrderRequest:
    invoice_number: Optional[str] = None
    order_no: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    delivery_date: Optional[str] = None
    zone: Optional[str] = None
    urgency: Optional[str] = None
    preferred_driver_id: Optional[str] = None
    pallet_quantity: Optional[int] = 0
    loose_bags_quantity: Optional[int] = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None
    product_lines: Optional[List[dict]] = None


@dataclass
class AttacheInvoicePdfPreviewItem:
    row_id: str
    source_filename: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    customer_code: Optional[str] = None
    order_no: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    delivery_date: Optional[str] = None
    zone: Optional[str] = None
    urgency: Optional[str] = "Normal"
    preferred_driver_id: Optional[str] = None
    pallet_quantity: int = 0
    loose_bags_quantity: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None
    product_lines: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_duplicate: bool = False
    importable: bool = True
    selected: bool = True


@dataclass
class AttacheInvoicePdfPreviewResponse:
    rows: List[AttacheInvoicePdfPreviewItem]


@dataclass
class CommitAttacheInvoicePdfImportRow:
    row_id: Optional[str] = None
    source_filename: Optional[str] = None
    selected: bool = True
    importable: bool = True
    is_duplicate: bool = False
    invoice_number: Optional[str] = None
    order_no: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    delivery_date: Optional[str] = None
    zone: Optional[str] = None
    urgency: Optional[str] = "Normal"
    preferred_driver_id: Optional[str] = None
    pallet_quantity: Optional[int] = 0
    loose_bags_quantity: Optional[int] = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None
    product_lines: Optional[List[dict]] = None


@dataclass
class CommitAttacheInvoicePdfImportRequest:
    rows: List[CommitAttacheInvoicePdfImportRow] = field(default_factory=list)


@dataclass
class CreateDriverRequest:
    name: Optional[str] = None
    license_no: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_available: Optional[bool] = True
    pallet_only: Optional[bool] = False
    preferred_zone: Optional[str] = None


@dataclass
class UpdateDriverRequest:
    name: Optional[str] = None
    license_no: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_available: Optional[bool] = True
    pallet_only: Optional[bool] = False
    preferred_zone: Optional[str] = None


@dataclass
class CreateVehicleRequest:
    rego: Optional[str] = None
    type: Optional[str] = None
    is_available: Optional[bool] = True
    pallet_capacity: Optional[int] = 0
    tub_capacity: Optional[int] = 0
    trolley_capacity: Optional[int] = 0
    stillage_capacity: Optional[int] = 0


@dataclass
class UpdateVehicleRequest:
    rego: Optional[str] = None
    type: Optional[str] = None
    is_available: Optional[bool] = True
    pallet_capacity: Optional[int] = 0
    tub_capacity: Optional[int] = 0
    trolley_capacity: Optional[int] = 0
    stillage_capacity: Optional[int] = 0


@dataclass
class ManualDispatchSpecificationResponse:
    drivers: List[Driver]
    vehicles: List[Vehicle]


def to_dict(value):
    """Convert dataclass response objects into plain dictionaries for APIs."""
    return asdict(value)
