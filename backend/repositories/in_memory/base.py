from contextlib import contextmanager
from copy import deepcopy

from backend.schemas import (
    Driver,
    Order,
    Vehicle,
)

class InMemoryRepositoryBase:
    """Base in-memory responsibilities."""

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
        self.delivery_order_area_overrides = {}
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

    @contextmanager
    def _immediate_transaction(self):
        snapshot = deepcopy(self.__dict__)
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise
