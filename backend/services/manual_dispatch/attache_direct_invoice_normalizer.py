from datetime import date, datetime, timedelta
import re

from backend.schemas import AttacheInvoicePdfPreviewItem
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    attache_preview_row_id,
    build_attache_preview_warnings,
    current_melbourne_business_date,
    normalize_attache_structured_product_rows,
)
from backend.services.manual_dispatch.normalization import clean_optional_text


INVOICE_NUMBER_PATTERN = re.compile(r"^\d{1,20}$")
DIRECT_SOURCE_NAME = "Attaché Direct"


class AttacheDirectInvoicePayloadError(ValueError):
    pass


def normalize_direct_attache_invoice(
    payload,
    *,
    expected_invoice_number=None,
    import_date=None,
):
    if not isinstance(payload, dict):
        raise AttacheDirectInvoicePayloadError(
            "Attaché lookup returned an invalid response."
        )
    invoice_number = str(payload.get("invoice_number") or "").strip()
    if not INVOICE_NUMBER_PATTERN.fullmatch(invoice_number):
        raise AttacheDirectInvoicePayloadError(
            "Attaché lookup returned an invalid invoice number."
        )
    if expected_invoice_number is not None and invoice_number != str(
        expected_invoice_number
    ).strip():
        raise AttacheDirectInvoicePayloadError(
            "Attaché lookup returned a different invoice number."
        )

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        raise AttacheDirectInvoicePayloadError(
            "Attaché lookup returned invalid product lines."
        )
    try:
        product_result = normalize_attache_structured_product_rows(raw_lines)
    except ValueError as error:
        raise AttacheDirectInvoicePayloadError(str(error)) from error

    invoice_date = _optional_iso_date(payload.get("invoice_date"), "invoice_date")
    delivery_date = _optional_iso_date(
        payload.get("delivery_date"),
        "delivery_date",
    )
    if not delivery_date:
        delivery_date = (_resolve_import_date(import_date) + timedelta(days=1)).isoformat()

    address_lines = payload.get("delivery_address_lines") or []
    if not isinstance(address_lines, (list, tuple)):
        raise AttacheDirectInvoicePayloadError(
            "Attaché lookup returned an invalid delivery address."
        )
    delivery_address = clean_optional_text(
        ", ".join(
            value
            for value in (
                clean_optional_text(line)
                for line in address_lines
            )
            if value
        )
    )
    customer_name = clean_optional_text(
        payload.get("delivery_description")
    ) or clean_optional_text(payload.get("customer_name"))
    customer_code = clean_optional_text(payload.get("customer_code"))
    suburb = clean_optional_text(payload.get("suburb"))
    postcode = clean_optional_text(payload.get("postcode"))
    order_no = clean_optional_text(payload.get("order_reference")) or clean_optional_text(
        payload.get("invoice_order_number")
    )
    warnings = build_attache_preview_warnings(
        invoice_number=invoice_number,
        company_name=customer_name,
        delivery_date=delivery_date,
        suburb=suburb,
        product_result=product_result,
    )

    return AttacheInvoicePdfPreviewItem(
        row_id=attache_preview_row_id(DIRECT_SOURCE_NAME, invoice_number),
        source_filename=DIRECT_SOURCE_NAME,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        customer_code=customer_code,
        order_no=order_no,
        company_name=customer_name,
        phone=None,
        delivery_address=delivery_address,
        suburb=suburb,
        postcode=postcode,
        delivery_date=delivery_date,
        zone="",
        urgency="Normal",
        preferred_driver_id="",
        pallet_quantity=product_result["pallet_quantity"],
        loose_bags_quantity=product_result["loose_bags_quantity"],
        carton_quantity=product_result["carton_quantity"],
        start_time=None,
        end_time=None,
        note=None,
        product_lines=product_result["product_lines"],
        warnings=warnings,
        importable=True,
        selected=True,
    )


def _optional_iso_date(value, field_name):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as error:
        raise AttacheDirectInvoicePayloadError(
            f"Attaché lookup returned an invalid {field_name}."
        ) from error


def _resolve_import_date(value):
    if value is None:
        return current_melbourne_business_date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as error:
        raise AttacheDirectInvoicePayloadError(
            "Direct Attaché import date is invalid."
        ) from error
