from backend.schemas import Order
from backend.services.manual_dispatch.normalization import (
    clean_optional_iso_date,
    clean_optional_text,
    clean_required_iso_date,
    clean_required_text,
    normalize_product_detail_lines,
    quantity_or_default,
)
from backend.services.manual_dispatch.delivery_suburb_region_service import (
    DeliveryOrderAreaResolver,
    canonical_delivery_location,
)
from backend.services.manual_dispatch.transaction import immediate_transactional


class OrderService:
    def __init__(self, repository, id_generator, area_resolver=None):
        self.repository = repository
        self.id_generator = id_generator
        self.area_resolver = area_resolver or DeliveryOrderAreaResolver(repository)

    def create_order(self, request):
        suburb = clean_required_text(request.suburb, "suburb")
        delivery_date = clean_required_iso_date(
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
        carton_quantity = quantity_or_default(
            request.carton_quantity,
            "carton_quantity",
        )
        product_lines = normalize_product_detail_lines(request.product_lines)

        order = Order(
            order_id=self.id_generator.generate_order_id(delivery_date),
            invoice_number=clean_optional_text(request.invoice_number),
            order_no=clean_optional_text(request.order_no),
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
            carton_quantity=carton_quantity,
            start_time=clean_optional_text(request.start_time),
            end_time=clean_optional_text(request.end_time),
            note=clean_optional_text(request.note),
            status="ACTIVE",
            product_lines=product_lines,
            invoice_date=clean_optional_iso_date(request.invoice_date, "invoice_date"),
        )
        return self.area_resolver.resolve_order(self.repository.create_order(order))

    @immediate_transactional
    def update_order(self, order_id, request):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        fields = _provided_fields(request)
        suburb = (
            clean_required_text(request.suburb, "suburb")
            if "suburb" in fields
            else existing.suburb
        )
        delivery_date = (
            clean_required_iso_date(request.delivery_date, "delivery_date")
            if "delivery_date" in fields
            else existing.delivery_date
        )
        pallet_quantity = (
            _patch_quantity(request.pallet_quantity, "pallet_quantity")
            if "pallet_quantity" in fields
            else existing.pallet_quantity
        )
        loose_bags_quantity = (
            _patch_quantity(request.loose_bags_quantity, "loose_bags_quantity")
            if "loose_bags_quantity" in fields
            else existing.loose_bags_quantity
        )
        carton_quantity = (
            _patch_quantity(request.carton_quantity, "carton_quantity")
            if "carton_quantity" in fields
            else existing.carton_quantity
        )
        product_lines_payload = request.product_lines
        if "product_lines" not in fields:
            product_lines_payload = [
                {
                    "product_name": line.product_name,
                    "quantity": line.quantity,
                    "unit": line.unit,
                    "product_code": line.product_code,
                    "package_quantity": line.package_quantity,
                    "package_unit": line.package_unit,
                }
                for line in existing.product_lines
            ]
        product_lines = normalize_product_detail_lines(product_lines_payload)

        order = Order(
            order_id=existing.order_id,
            invoice_number=_optional_patch_text(request, fields, "invoice_number", existing.invoice_number),
            order_no=_optional_patch_text(request, fields, "order_no", existing.order_no),
            company_name=_optional_patch_text(request, fields, "company_name", existing.company_name) or "",
            phone=_optional_patch_text(request, fields, "phone", existing.phone),
            delivery_address=_optional_patch_text(request, fields, "delivery_address", existing.delivery_address) or "",
            suburb=suburb,
            postcode=_optional_patch_text(request, fields, "postcode", existing.postcode) or "",
            delivery_date=delivery_date,
            zone=_optional_patch_text(request, fields, "zone", existing.zone) or "",
            urgency=_optional_patch_text(request, fields, "urgency", existing.urgency) or "Normal",
            preferred_driver_id=_optional_patch_text(
                request,
                fields,
                "preferred_driver_id",
                existing.preferred_driver_id,
            ),
            pallet_quantity=pallet_quantity,
            loose_bags_quantity=loose_bags_quantity,
            carton_quantity=carton_quantity,
            start_time=_optional_patch_text(request, fields, "start_time", existing.start_time),
            end_time=_optional_patch_text(request, fields, "end_time", existing.end_time),
            note=_optional_patch_text(request, fields, "note", existing.note),
            status=existing.status,
            product_lines=product_lines,
            invoice_date=(
                clean_optional_iso_date(request.invoice_date, "invoice_date")
                if "invoice_date" in fields
                else existing.invoice_date
            ),
        )
        location_changed = canonical_delivery_location(
            existing.suburb,
            existing.postcode,
        ) != canonical_delivery_location(order.suburb, order.postcode)
        updated = self.repository.update_order(order)
        if location_changed:
            self.repository.clear_delivery_order_area_override(order_id)
        return self.area_resolver.resolve_order(updated)

    def cancel_order(self, order_id):
        existing = self.repository.get_order(order_id)
        if not existing:
            raise ValueError(f"Order does not exist: {order_id}")

        if existing.status == "CANCELLED":
            return existing

        if self.repository.has_assignment_for_task("ORDER", order_id):
            raise ValueError("Order must be unassigned before cancellation")

        return self.repository.cancel_order(order_id)


def _optional_patch_text(request, fields, field_name, existing_value):
    if field_name not in fields:
        return existing_value
    return clean_optional_text(getattr(request, field_name))


def _provided_fields(request):
    model_fields_set = getattr(request, "model_fields_set", None)
    if model_fields_set is not None:
        return model_fields_set
    return vars(request).keys()


def _patch_quantity(value, field_name):
    if value is None:
        raise ValueError(f"{field_name} cannot be null")
    return quantity_or_default(value, field_name)
