class ManualDispatchIdGenerator:
    def __init__(self, repository):
        self.repository = repository

    def generate_order_id(self, delivery_date):
        date_token = "".join(character for character in delivery_date if character.isdigit())
        if not date_token:
            raise ValueError("delivery_date must include a date value")

        prefix = f"ORD-{date_token}-"
        highest_number = 0
        for order in self.repository.list_orders():
            if not order.order_id.startswith(prefix):
                continue
            suffix = order.order_id.replace(prefix, "", 1)
            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        next_number = highest_number + 1
        order_id = f"{prefix}{next_number:03d}"
        while self.repository.get_order(order_id):
            next_number += 1
            order_id = f"{prefix}{next_number:03d}"
        return order_id

    def generate_driver_id(self):
        return self._generate_prefixed_id("D", self.repository.list_driver_ids())

    def generate_vehicle_id(self):
        return self._generate_prefixed_id("V", self.repository.list_vehicle_ids())

    def _generate_prefixed_id(self, prefix, existing_ids):
        highest_number = 0
        for identifier in existing_ids:
            if not identifier.startswith(prefix):
                continue
            suffix = identifier.replace(prefix, "", 1)
            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        next_number = highest_number + 1
        return f"{prefix}{next_number:03d}"
