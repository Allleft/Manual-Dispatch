import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from backend.errors import StateChangedConflictError

from backend.schemas import (
    DeliveryRunSheet,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetTrip,
    ProductDetailLine,
)
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date,
    clean_optional_text,
    clean_required_iso_date,
    clean_required_text,
)
from backend.services.manual_dispatch.transaction import immediate_transactional


class DeliveryRunSheetService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    @immediate_transactional
    def create_generated(self, request):
        delivery_date = clean_required_iso_date(request.delivery_date, "delivery_date")
        dispatch_date = (
            clean_optional_iso_date(request.dispatch_date, "dispatch_date")
            or delivery_date
        )
        driver_id = clean_required_text(request.driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)

        existing = self.repository.get_delivery_run_sheet_for_driver(
            dispatch_date,
            delivery_date,
            driver_id,
        )
        if existing:
            raise StateChangedConflictError(
                "Delivery Run Sheet already exists for this driver and delivery date."
            )

        trips = self._build_trips(delivery_date, driver_id)
        if not trips:
            raise ValueError("At least one assigned Delivery Order is required.")

        driver = self.repository.get_driver(driver_id)
        vehicle_id, vehicle_rego = self._vehicle_snapshot(
            delivery_date,
            driver_id,
        )
        orders = [order for trip in trips for order in trip.orders]
        run_sheet = DeliveryRunSheet(
            run_sheet_id=f"DRS-{uuid4().hex.upper()}",
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver_id=driver_id,
            driver_name_snapshot=driver.name,
            vehicle_id=vehicle_id,
            vehicle_rego_snapshot=vehicle_rego,
            total_pallets=sum(order.pallet_quantity_snapshot for order in orders),
            total_loose_bags=sum(
                order.loose_bags_quantity_snapshot for order in orders
            ),
            status="GENERATED",
            generated_at=_timestamp(),
            saved_at=None,
            saved_by_account_name=None,
            saved_by_account_id=None,
            legacy_summary_id=None,
            trips=trips,
        )
        try:
            return self.repository.upsert_delivery_run_sheet(run_sheet)
        except sqlite3.IntegrityError as error:
            if not _is_delivery_run_sheet_key_conflict(error):
                raise
            raise StateChangedConflictError(
                "Delivery Run Sheet already exists for this driver and delivery date."
            ) from error

    def list(self, dispatch_date=None, delivery_date=None, status=None):
        return self.repository.list_delivery_run_sheets(
            clean_optional_iso_date(dispatch_date, "dispatch_date"),
            clean_optional_iso_date(delivery_date, "delivery_date"),
            clean_optional_text(status).upper() if clean_optional_text(status) else None,
        )

    def get(self, run_sheet_id):
        run_sheet_id = clean_required_text(run_sheet_id, "run_sheet_id")
        run_sheet = self.repository.get_delivery_run_sheet(run_sheet_id)
        if not run_sheet:
            raise ValueError(f"Delivery Run Sheet does not exist: {run_sheet_id}")
        return run_sheet

    def save_generated(self, run_sheet_id, request):
        account = self.validator.validate_saved_by_account(
            request.saved_by_account_name,
            request.saved_by_account_id,
        )
        promoted = self.repository.promote_generated_delivery_run_sheet_to_saved(
            clean_required_text(run_sheet_id, "run_sheet_id"),
            _timestamp(),
            account.account_name,
            account.account_id,
        )
        if promoted:
            return self.get(run_sheet_id)
        self._raise_transition_error(run_sheet_id, "saved")

    def cancel_generated(self, run_sheet_id):
        run_sheet_id = clean_required_text(run_sheet_id, "run_sheet_id")
        cancelled = self.repository.delete_generated_delivery_run_sheet(run_sheet_id)
        if cancelled:
            return True
        self._raise_transition_error(run_sheet_id, "cancelled")

    def get_saved_for_export(self, run_sheet_id):
        run_sheet = self.get(run_sheet_id)
        if run_sheet.status != "SAVED":
            raise ValueError("Only saved Delivery Run Sheets can be exported.")
        return run_sheet

    def list_for_date_export(self, delivery_date):
        delivery_date = clean_required_iso_date(delivery_date, "delivery_date")
        run_sheets = [
            run_sheet
            for run_sheet in self.repository.list_delivery_run_sheets(
                delivery_date=delivery_date
            )
            if run_sheet.status in {"GENERATED", "SAVED"}
            and any(trip.orders for trip in run_sheet.trips)
        ]
        if not run_sheets:
            raise ValueError(
                "No Generated or Saved Delivery Run Sheets are available for this Delivery Date."
            )
        return run_sheets

    def _raise_transition_error(self, run_sheet_id, action):
        current = self.repository.get_delivery_run_sheet(run_sheet_id)
        if not current:
            raise ValueError(f"Delivery Run Sheet does not exist: {run_sheet_id}")
        past_tense = "saved" if action == "saved" else "cancelled"
        raise ValueError(
            f"Only generated Delivery Run Sheets can be {past_tense}."
        )

    def _build_trips(self, delivery_date, driver_id):
        assignments = [
            assignment
            for assignment in (
                self.repository.list_delivery_order_assignments_for_delivery_date(
                    delivery_date
                )
            )
            if assignment.driver_id == driver_id
            and assignment.trip_no in {"trip1", "trip2"}
        ]
        trips = []
        row_no = 1
        for trip_no in ("trip1", "trip2"):
            orders = []
            for assignment in assignments:
                if assignment.trip_no != trip_no:
                    continue
                order = self.repository.get_order(assignment.task_id)
                if (
                    not order
                    or order.status != "ACTIVE"
                    or order.delivery_date != delivery_date
                ):
                    continue
                orders.append(
                    DeliveryRunSheetOrderSnapshot(
                        row_id=f"DRR-{uuid4().hex.upper()}",
                        trip_no=trip_no,
                        row_no=row_no,
                        task_type="ORDER",
                        task_id=order.order_id,
                        order_id_snapshot=order.order_id,
                        invoice_number_snapshot=order.invoice_number,
                        order_no_snapshot=order.order_no,
                        company_name_snapshot=order.company_name,
                        suburb_snapshot=order.suburb,
                        delivery_address_snapshot=order.delivery_address,
                        product_snapshot=None,
                        pallet_quantity_snapshot=order.pallet_quantity,
                        loose_bags_quantity_snapshot=order.loose_bags_quantity,
                        note_snapshot=order.note,
                        product_lines_snapshot=[
                            ProductDetailLine(
                                product_name=line.product_name,
                                quantity=line.quantity,
                                unit=line.unit,
                            )
                            for line in order.product_lines
                        ],
                        estimated_distance_km_from_warehouse_snapshot=(
                            order.estimated_distance_km_from_warehouse
                        ),
                    )
                )
                row_no += 1
            if orders:
                trips.append(DeliveryRunSheetTrip(trip_no=trip_no, orders=orders))
        return trips

    def _vehicle_snapshot(self, delivery_date, driver_id):
        assignment = next(
            (
                item
                for item in (
                    self.repository.list_driver_vehicle_assignments_for_delivery_date(
                        delivery_date
                    )
                )
                if item.driver_id == driver_id
            ),
            None,
        )
        if not assignment:
            return None, None
        vehicle = self.repository.get_vehicle(assignment.vehicle_id)
        return assignment.vehicle_id, vehicle.rego if vehicle else None


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _is_delivery_run_sheet_key_conflict(error):
    return (
        "UNIQUE constraint failed: delivery_run_sheets.dispatch_date, "
        "delivery_run_sheets.delivery_date, delivery_run_sheets.driver_id"
    ) in str(error)
