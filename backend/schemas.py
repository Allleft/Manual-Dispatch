from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class Order:
    order_id: str
    company_name: str
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


@dataclass
class Driver:
    driver_id: str
    name: str
    start_time: Optional[str]
    end_time: Optional[str]
    is_available: bool
    preferred_zone: Optional[str]


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
    vehicle_id: str


def to_dict(value):
    """Convert dataclass response objects into plain dictionaries for APIs."""
    return asdict(value)
