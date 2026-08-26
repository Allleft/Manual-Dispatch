from datetime import datetime, timezone

from backend.services.manual_dispatch.delivery_suburb_region_service import (
    validate_delivery_area,
)


class InMemoryOrderRepositoryMixin:
    """Order in-memory responsibilities."""

    def list_orders(self, delivery_date=None):
        return [
            order
            for order in self.orders
            if order.status == "ACTIVE"
            and (not delivery_date or order.delivery_date == delivery_date)
        ]

    def get_order(self, order_id):
        return next((order for order in self.orders if order.order_id == order_id), None)

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

    def roll_forward_unassigned_delivery_order_dates(
        self,
        current_date,
        target_date,
        order_id=None,
    ):
        assigned_order_ids = self.list_globally_assigned_delivery_order_ids()
        reserved_order_ids = self.list_reserved_delivery_order_ids()
        changes = []
        for order in sorted(self.orders, key=lambda item: item.order_id):
            if (
                order.status != "ACTIVE"
                or order.delivery_date > current_date
                or (order_id is not None and order.order_id != order_id)
                or order.order_id in assigned_order_ids
                or order.order_id in reserved_order_ids
            ):
                continue
            previous_delivery_date = order.delivery_date
            order.delivery_date = target_date
            changes.append(
                {
                    "order_id": order.order_id,
                    "invoice_number": order.invoice_number,
                    "order_no": order.order_no,
                    "previous_delivery_date": previous_delivery_date,
                    "new_delivery_date": target_date,
                }
            )
        return changes

    def get_delivery_order_area_override(self, order_id):
        record = self.delivery_order_area_overrides.get(order_id)
        return record["delivery_area"] if record else None

    def set_delivery_order_area_override(
        self,
        order_id,
        delivery_area,
        updated_by=None,
    ):
        if not self.get_order(order_id):
            raise ValueError(f"Order does not exist: {order_id}")
        normalized = validate_delivery_area(delivery_area)
        self.delivery_order_area_overrides[order_id] = {
            "delivery_area": normalized,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": updated_by,
        }
        return normalized

    def clear_delivery_order_area_override(self, order_id):
        if not self.get_order(order_id):
            raise ValueError(f"Order does not exist: {order_id}")
        return self.delivery_order_area_overrides.pop(order_id, None) is not None
