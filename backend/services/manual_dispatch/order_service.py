from backend.schemas import Order
from backend.services.manual_dispatch.normalization import (
    clean_optional_text,
    clean_required_text,
    quantity_or_default,
)


class OrderService:
    def __init__(self, repository, id_generator):
        self.repository = repository
        self.id_generator = id_generator

    def create_order(self, request):
        suburb = clean_required_text(request.suburb, "suburb")
        delivery_date = clean_required_text(
            request.delivery_date,
            "delivery_date",
        )
        pallet_quantity = quantity_or_default(
            request.pallet_quantity,
            "pallet_quantity",
        )
        loose_bags_quantity = quantity_or_default(
            request.loose_bags_quantity,
            "loose_bags_quantity",
        )

        order = Order(
            order_id=self.id_generator.generate_order_id(delivery_date),
            invoice_number=clean_optional_text(request.invoice_number),
            company_name=clean_optional_text(request.company_name) or "",
            phone=clean_optional_text(request.phone),
            delivery_address=clean_optional_text(request.delivery_address) or "",
            suburb=suburb,
            postcode=clean_optional_text(request.postcode) or "",
            delivery_date=delivery_date,
            zone=clean_optional_text(request.zone) or "",
            urgency=clean_optional_text(request.urgency) or "Normal",
            preferred_driver_id=clean_optional_text(request.preferred_driver_id),
            pallet_quantity=pallet_quantity,
            loose_bags_quantity=loose_bags_quantity,
            start_time=clean_optional_text(request.start_time),
            end_time=clean_optional_text(request.end_time),
            note=clean_optional_text(request.note),
            status="ACTIVE",
        )
        return self.repository.create_order(order)

    def update_order(self, order_id, request):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        suburb = clean_required_text(request.suburb, "suburb")
        pallet_quantity = quantity_or_default(
            request.pallet_quantity,
            "pallet_quantity",
        )
        loose_bags_quantity = quantity_or_default(
            request.loose_bags_quantity,
            "loose_bags_quantity",
        )

        order = Order(
            order_id=existing.order_id,
            invoice_number=clean_optional_text(request.invoice_number),
            company_name=clean_optional_text(request.company_name) or "",
            phone=clean_optional_text(request.phone),
            delivery_address=clean_optional_text(request.delivery_address) or "",
            suburb=suburb,
            postcode=clean_optional_text(request.postcode) or "",
            delivery_date=existing.delivery_date,
            zone=clean_optional_text(request.zone) or "",
            urgency=clean_optional_text(request.urgency) or "Normal",
            preferred_driver_id=clean_optional_text(request.preferred_driver_id),
            pallet_quantity=pallet_quantity,
            loose_bags_quantity=loose_bags_quantity,
            start_time=clean_optional_text(request.start_time),
            end_time=clean_optional_text(request.end_time),
            note=clean_optional_text(request.note),
            status=existing.status,
        )
        return self.repository.update_order(order)

    def cancel_order(self, order_id):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        if existing.status == "CANCELLED":
            return existing

        if self.repository.has_assignment_for_task("ORDER", order_id):
            raise ValueError("Order must be unassigned before cancellation")

        return self.repository.cancel_order(order_id)
