from datetime import datetime, timezone

from backend.schemas import (
    DeliveryOrderLookupAssignment,
    DeliveryOrderStatusLookup,
    DeliveryOrderStatusMatch,
)


STATUS_LABELS = {
    "UNASSIGNED": "Unassigned / In Task Pool",
    "ASSIGNED": "Assigned",
    "RUN_SHEET_GENERATED": "Run Sheet Generated",
    "RUN_SHEET_SAVED_OPEN": "Run Sheet Saved / Awaiting Closeout",
    "RETURNED_TO_POOL": "Returned to Task Pool",
    "DELIVERED": "Delivered",
    "CANCELLED": "Cancelled",
    "FINALIZED": "Finalized / Legacy History",
}


def _history_key(record):
    value = record.recorded_at or record.closed_at or record.saved_at or record.generated_at
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        timestamp = datetime.min.replace(tzinfo=timezone.utc)
    # Equal clock readings must follow lifecycle dates, not random Run Sheet IDs.
    return timestamp, record.delivery_date, record.run_sheet_id, record.trip_no, record.row_no, record.row_id


class DeliveryOrderStatusLookupService:
    """Resolve current lifecycle from persisted facts, never from an operational board."""

    def __init__(self, repository):
        self.repository = repository

    def lookup(self, invoice_number):
        invoice_number = (invoice_number or "").strip()
        if not invoice_number:
            raise ValueError("Invoice number is required.")
        with self.repository.delivery_order_lookup_snapshot():
            orders = [self._resolve(order) for order in
                      self.repository.find_orders_by_invoice_number(invoice_number)]
        return DeliveryOrderStatusLookup(invoice_number, len(orders), orders)

    def _resolve(self, order):
        history = sorted(
            self.repository.list_delivery_run_sheet_history_for_order(order.order_id),
            key=_history_key, reverse=True,
        )
        open_rows = [row for row in history if row.execution_status == "OPEN"
                     and row.status in {"GENERATED", "SAVED"}]
        if len(open_rows) > 1:
            raise ValueError("Delivery Run Sheet integrity error: multiple open rows for Order.")
        active_sheet = open_rows[0] if open_rows else None
        closeouts = [row for row in history if row.status == "SAVED"
                     and row.execution_status == "CLOSED" and row.outcome]
        latest_closeout = closeouts[0] if closeouts else None
        current_assignment = self.repository.find_assignment_for_task("ORDER", order.order_id)
        assignment = None
        if current_assignment:
            driver = self.repository.get_driver(current_assignment.driver_id)
            assignment = DeliveryOrderLookupAssignment(
                dispatch_date=current_assignment.dispatch_date,
                driver_id=current_assignment.driver_id,
                driver_name=driver.name if driver else None,
                trip_no=current_assignment.trip_no,
            )

        if order.status == "CANCELLED":
            status = "CANCELLED"
        elif active_sheet:
            status = ("RUN_SHEET_GENERATED" if active_sheet.status == "GENERATED"
                      else "RUN_SHEET_SAVED_OPEN")
        elif order.status == "ACTIVE" and assignment:
            status = "ASSIGNED"
        elif order.status == "FINALIZED":
            status = ("DELIVERED" if latest_closeout and latest_closeout.outcome == "DELIVERED"
                      else "FINALIZED")
        elif order.status == "ACTIVE":
            status = ("RETURNED_TO_POOL" if latest_closeout
                      and latest_closeout.outcome == "RETURN_TO_POOL" else "UNASSIGNED")
        else:
            raise ValueError("Delivery Order integrity error: unsupported persisted status.")
        return DeliveryOrderStatusMatch(
            order_id=order.order_id, current_status=status, status_label=STATUS_LABELS[status],
            order=order, assignment=assignment, active_run_sheet=active_sheet,
            latest_closeout=latest_closeout, run_sheet_history=history,
        )
