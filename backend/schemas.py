from dataclasses import asdict, dataclass
from typing import List, Optional


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


@dataclass
class Driver:
    driver_id: str
    name: str
    start_time: Optional[str]
    end_time: Optional[str]
    is_available: bool
    preferred_zone: Optional[str]
    pallet_only: bool


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
    driver_id: str
    vehicle_id: str


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


@dataclass
class ManualDriverVehicleClearResponse:
    dispatch_date: str
    driver_id: str
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


@dataclass
class FinalTripSummaryTrip:
    trip_no: str
    orders: List[FinalTripSummaryOrderSnapshot]


@dataclass
class FinalTripSummary:
    summary_id: str
    dispatch_date: str
    driver_id: str
    driver_name_snapshot: str
    vehicle_id: Optional[str]
    vehicle_rego_snapshot: Optional[str]
    total_pallets: int
    total_loose_bags: int
    status: str
    generated_at: str
    saved_at: str
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


@dataclass
class UpdateOrderRequest:
    invoice_number: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    zone: Optional[str] = None
    urgency: Optional[str] = None
    preferred_driver_id: Optional[str] = None
    pallet_quantity: Optional[int] = 0
    loose_bags_quantity: Optional[int] = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None


def to_dict(value):
    """Convert dataclass response objects into plain dictionaries for APIs."""
    return asdict(value)
