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
