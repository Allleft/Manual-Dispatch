from dataclasses import replace
from datetime import timedelta
from hashlib import sha1
from io import BytesIO
import re

from backend.schemas import AttacheInvoicePdfPreviewItem
from backend.services.manual_dispatch.normalization import clean_optional_text


ACCOUNTING_NOISE_PATTERNS = (
    "GST",
    "TOTAL",
    "AMOUNT",
    "BALANCE",
    "BANK",
    "BSB",
    "ACCOUNT",
    "TERMS",
    "TAX",
    "FUEL LEVY",
)

IGNORED_PRODUCT_CODES = {"DEL", "DELIVERY", "FUEL"}
PACKAGING_UNITS = {"BAG10", "BAG5"}
PRODUCT_LINE_PATTERN = re.compile(
    r"^(?P<code>[A-Z0-9#-]+)\s+(?P<name>.+?)\s+(?P<quantity>\d+)\s+"
    r"(?P<unit>PALLETS?|PAL|BAG10|BAG5|BAGS?|DELIVERY)\b",
    re.IGNORECASE,
)


def parse_attache_invoice_pdf_bytes(pdf_bytes, source_filename="invoice.pdf"):
    return parse_attache_invoice_text(
        extract_pdf_text(pdf_bytes),
        source_filename=source_filename,
    )


def extract_pdf_text(pdf_bytes):
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError("PDF parsing dependency is not installed: pypdf") from error

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        text_parts = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:
        raise ValueError("Unable to read Attache invoice PDF text") from error

    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("Attache invoice PDF did not contain extractable text")
    return text


def parse_attache_invoice_text(text, source_filename="invoice.txt"):
    lines = _normalize_lines(text)
    full_text = "\n".join(lines)
    invoice_number = _find_regex(
        full_text,
        r"(?:Invoice\s*(?:No\.?|Number)?|Tax Invoice)\s*[:#]?\s*(\d{5,})",
    )
    invoice_date = _parse_date(
        _find_regex(
            full_text,
            r"(?:Invoice Date|Date)\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
        )
    )
    delivery_date = _parse_delivery_date(full_text)
    if not delivery_date and invoice_date:
        delivery_date = (invoice_date + timedelta(days=1)).isoformat()

    time_instruction, start_time, end_time = _parse_time_instruction(full_text)
    customer_code = _find_regex(full_text, r"Customer Code\s*[:#]?\s*([A-Z0-9-]+)")
    order_no = _find_regex(full_text, r"(?:Order No|PO No|Purchase Order)\s*[:#]?\s*([A-Z0-9-]+)")

    company_name = _find_field(lines, ("Company", "Customer", "Deliver To", "Delivery To"))
    phone = _find_field(lines, ("Phone", "Tel", "Telephone"))
    delivery_address = _find_field(lines, ("Delivery Address", "Address"))
    suburb = _find_field(lines, ("Suburb",))
    postcode = _find_field(lines, ("Postcode", "Post Code"))

    if delivery_address and (not suburb or not postcode):
        delivery_address, inferred_suburb, inferred_postcode = _split_address(delivery_address)
        suburb = suburb or inferred_suburb
        postcode = postcode or inferred_postcode

    product_result = _parse_product_lines(lines)
    note = _build_note(
        lines,
        customer_code=customer_code,
        order_no=order_no,
        time_instruction=time_instruction,
    )
    warnings = _build_warnings(
        invoice_number=invoice_number,
        company_name=company_name,
        delivery_date=delivery_date,
        suburb=suburb,
        product_result=product_result,
    )

    return AttacheInvoicePdfPreviewItem(
        row_id=_row_id(source_filename, invoice_number),
        source_filename=source_filename,
        invoice_number=invoice_number,
        invoice_date=invoice_date.isoformat() if invoice_date else None,
        customer_code=customer_code,
        order_no=order_no,
        company_name=company_name,
        phone=phone,
        delivery_address=delivery_address,
        suburb=suburb,
        postcode=postcode,
        delivery_date=delivery_date,
        zone="",
        urgency="Normal",
        preferred_driver_id="",
        pallet_quantity=product_result["pallet_quantity"],
        loose_bags_quantity=product_result["loose_bags_quantity"],
        start_time=start_time,
        end_time=end_time,
        note=note,
        product_lines=product_result["product_lines"],
        warnings=warnings,
        importable=True,
        selected=True,
    )


def with_duplicate_warning(item):
    warnings = list(item.warnings)
    if "Duplicate invoice number already exists." not in warnings:
        warnings.append("Duplicate invoice number already exists.")
    return replace(
        item,
        warnings=warnings,
        is_duplicate=True,
        importable=False,
        selected=False,
    )


def _normalize_lines(text):
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in str(text or "").replace("\r", "\n").split("\n")
        if re.sub(r"\s+", " ", line).strip()
    ]


def _find_field(lines, labels):
    label_pattern = "|".join(re.escape(label) for label in labels)
    inline_pattern = re.compile(rf"^(?:{label_pattern})\s*[:#]\s*(.+)$", re.IGNORECASE)
    header_pattern = re.compile(rf"^(?:{label_pattern})\s*:?\s*$", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = inline_pattern.match(line)
        if match:
            return clean_optional_text(match.group(1))
        if header_pattern.match(line):
            for candidate in lines[index + 1 : index + 4]:
                if ":" not in candidate:
                    return clean_optional_text(candidate)
    return None


def _find_regex(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    return clean_optional_text(match.group(1)) if match else None


def _parse_delivery_date(text):
    raw_date = _find_regex(
        text,
        r"(?:Delivery Date|Deliver(?:y)? On|Required Date)\s*[:#]?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    )
    parsed = _parse_date(raw_date)
    return parsed.isoformat() if parsed else None


def _parse_date(raw_value):
    if not raw_value:
        return None
    text = raw_value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        from datetime import date

        return date.fromisoformat(text)

    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    from datetime import date

    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_time_instruction(text):
    between = re.search(
        r"(DELIVERY BETWEEN\s+([\d:]+)\s*(AM|PM)?\s*-\s*([\d:]+)\s*(AM|PM)?)",
        text,
        re.IGNORECASE,
    )
    if between:
        instruction = re.sub(r"\s+", " ", between.group(1)).strip()
        start_time = _parse_clock_time(between.group(2), between.group(3) or between.group(5))
        end_time = _parse_clock_time(between.group(4), between.group(5) or between.group(3))
        return instruction, start_time, end_time

    opens = re.search(r"(OPENS\s+([\d:]+)\s*(AM|PM)?)", text, re.IGNORECASE)
    if opens:
        instruction = re.sub(r"\s+", " ", opens.group(1)).strip()
        return instruction, _parse_clock_time(opens.group(2), opens.group(3)), None

    return None, None, None


def _parse_clock_time(value, meridiem=None):
    if not value:
        return None
    parts = value.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    suffix = (meridiem or "").upper()
    if suffix == "PM" and hour != 12:
        hour += 12
    if suffix == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _split_address(value):
    text = clean_optional_text(value) or ""
    match = re.match(r"(.+?)[,\s]+([A-Za-z][A-Za-z\s'-]+)\s+(\d{4})$", text)
    if not match:
        return text, None, None
    return (
        clean_optional_text(match.group(1).rstrip(",")),
        clean_optional_text(match.group(2).strip(" ,")),
        clean_optional_text(match.group(3)),
    )


def _parse_product_lines(lines):
    raw_products = []
    pallet_quantity = 0
    for line in lines:
        if _is_noise_line(line):
            continue
        pallet_match = re.match(r"^(?:PAL|PALLET)\s+(?:PALLET\s+)?(\d+)\b", line, re.IGNORECASE)
        if pallet_match:
            pallet_quantity += int(pallet_match.group(1))
            continue
        match = PRODUCT_LINE_PATTERN.match(line)
        if not match:
            continue

        code = match.group("code").upper()
        if code in IGNORED_PRODUCT_CODES:
            continue
        unit = match.group("unit").upper()
        if unit.startswith("DEL"):
            continue
        raw_products.append(
            {
                "code": code,
                "name": _clean_product_name(match.group("name")),
                "quantity": int(match.group("quantity")),
                "unit": unit,
            }
        )

    loose_bags_quantity = 0
    product_lines = []
    for product in raw_products:
        unit = product["unit"]
        if unit in {"PAL", "PALLET", "PALLETS"}:
            quantity = product["quantity"]
            pallet_quantity += quantity
            product_lines.append(_product_line(product["name"], quantity, "PALLETS"))
            continue

        if unit in PACKAGING_UNITS and pallet_quantity > 0:
            product_lines.append(_product_line(product["name"], pallet_quantity, "PALLETS"))
            continue

        if unit in PACKAGING_UNITS or unit in {"BAG", "BAGS"}:
            loose_bags_quantity += product["quantity"]
            product_lines.append(_product_line(product["name"], product["quantity"], "BAGS"))

    return {
        "pallet_quantity": pallet_quantity,
        "loose_bags_quantity": loose_bags_quantity,
        "product_lines": _dedupe_product_lines(product_lines),
    }


def _product_line(name, quantity, unit):
    return {
        "product_name": name,
        "quantity": quantity,
        "unit": unit,
    }


def _clean_product_name(value):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    return name


def _dedupe_product_lines(product_lines):
    merged = {}
    order = []
    for line in product_lines:
        key = (line["product_name"], line["unit"])
        if key not in merged:
            merged[key] = dict(line)
            order.append(key)
            continue
        merged[key]["quantity"] += line["quantity"]
    return [merged[key] for key in order]


def _build_note(lines, customer_code=None, order_no=None, time_instruction=None):
    note_lines = []
    if customer_code:
        note_lines.append(f"Customer Code: {customer_code}")
    if order_no:
        note_lines.append(f"Order No: {order_no}")
    if time_instruction:
        note_lines.append(time_instruction)

    for line in lines:
        normalized = line.strip()
        upper = normalized.upper()
        if _is_noise_line(upper):
            continue
        if any(
            marker in upper
            for marker in (
                "NO VAN",
                "MUST BE TRUCK",
                "EMAIL INVOICE",
                "PRE PAYMENT",
                "PREPAYMENT",
                "CREDIT CARD",
                "DELIVERY INSTRUCTION",
            )
        ):
            if normalized not in note_lines:
                note_lines.append(normalized)

    return "\n".join(note_lines) or None


def _is_noise_line(line):
    upper = str(line or "").upper()
    return any(pattern in upper for pattern in ACCOUNTING_NOISE_PATTERNS)


def _build_warnings(invoice_number, company_name, delivery_date, suburb, product_result):
    warnings = []
    if not invoice_number:
        warnings.append("Invoice number was not found.")
    if not company_name:
        warnings.append("Customer name was not found.")
    if not delivery_date:
        warnings.append("Delivery date could not be inferred.")
    if not suburb:
        warnings.append("Suburb was not found.")
    if (
        product_result["pallet_quantity"] <= 0
        and product_result["loose_bags_quantity"] <= 0
    ):
        warnings.append("No delivery load quantity was found.")
    return warnings


def _row_id(source_filename, invoice_number):
    seed = f"{source_filename}|{invoice_number or ''}"
    return f"ATTACHE-{sha1(seed.encode('utf-8')).hexdigest()[:12]}"
