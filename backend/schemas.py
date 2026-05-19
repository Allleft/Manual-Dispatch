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
class ManualDispatchBoardResponse:
    dispatch_date: str
    orders: List[Order]
    drivers: List[Driver]
    vehicles: List[Vehicle]
    assignments: List[ManualDispatchAssignment]
    driver_vehicle_assignments: List[ManualDriverVehicleAssignment]


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
    product_lines_snapshot: List[ProductDetailLine] = field(default_factory=list)
    estimated_distance_km_from_warehouse_snapshot: Optional[float] = None


@dataclass
class FinalTripSummaryTrip:
    trip_no: str
    orders: List[FinalTripSummaryOrderSnapshot]


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
    delivery_date: Optional[str] = None
    saved_by_account_name: Optional[str] = None
    saved_by_account_id: Optional[int] = None


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
