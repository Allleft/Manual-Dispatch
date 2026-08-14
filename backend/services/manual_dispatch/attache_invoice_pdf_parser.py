from dataclasses import replace
from datetime import date, datetime, timedelta
from hashlib import sha1
from io import BytesIO
import re

from backend.schemas import AttacheInvoicePdfPreviewItem
from backend.services.manual_dispatch.logbook_file_service import MELBOURNE_TIMEZONE
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

CHARGE_CODES = {"DEL", "DELIVERY", "FREIGHT", "FUEL", "LEVY", "SURCHARGE"}
PACKAGING_CODE_PATTERN = re.compile(r"^BAG\d+(?:\.\d+)?$", re.IGNORECASE)
PRODUCT_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9.#/-]{0,39}$", re.IGNORECASE)
PRODUCT_UNITS = {
    "BAG",
    "BAGS",
    "BOX",
    "BOXES",
    "CTN",
    "CARTON",
    "CARTONS",
    "EA",
    "EAC",
    "EACH",
    "KG",
    "KGS",
    "PACK",
    "PACKS",
    "PAL",
    "PALLET",
    "PALLETS",
    "ROLL",
    "ROLLS",
}
OPERATIONAL_NOTE_ANCHORS = (
    "ATTN:",
    "DELIVERY INSTRUCTION",
    "EMAIL INVOICE",
    "ON DELIVERY DOCKET",
    "PAID ",
)
STOP_BLOCK_MARKERS = (
    "ABN",
    "Amt+GST",
    "Code Description",
    "Deliver to:",
    "Disc Price",
    "Email:",
    "Invoice to:",
    "Phone:",
    "Price Per Net",
    "Tax Invoice",
    "UNIT ",
    "web:",
)
TOTAL_STOP_PATTERN = re.compile(
    r"^TOTAL(?:\s*:?\s*$|\s+(?:INVOICE|NET\s+AMOUNT|GST|AMOUNT)\b)",
    re.IGNORECASE,
)
SUPPLIER_ISSUER_MARKERS = (
    "B S L WIPERS",
    "BSL WIPERS",
    "MCC RAGMAN",
    "MELBOURNE CLEANING CLOTHS",
    "SMITHS RAGS",
    "98 102 HUME HIGHWAY",
    "SOMERTON VIC 3062",
)
CHARGE_DESCRIPTION_PATTERN = re.compile(
    r"\b(?:DELIVERY\s*/?\s*FUEL\s+LEVY\s+CHARGE|DELIVERY\s+CHARGE|"
    r"FREIGHT(?:\s+CHARGE)?|FUEL\s+LEVY|SURCHARGE)\b",
    re.IGNORECASE,
)
LINE_ITEM_HEADER_PATTERN = re.compile(
    r"\bCODE\b.*\bDESCRIPTION\b|\bPRICE\s+PER\s+NET\b|\bAMT\+GST\b",
    re.IGNORECASE,
)
LINE_ITEM_FOOTER_PATTERN = re.compile(
    r"^(?:\*?NEW\s+PRODUCT\*?|BANK\s+DETAILS|BSB\s*:|GOODS\s+REMAIN|"
    r"PAID\b|PAYMENT\s+BY|PLEASE\s+NOTE\s+NEW\s+BANK|TERMS\s*:|"
    r"TOTAL(?:\s+INVOICE|\s+NET\s+AMOUNT|\s+GST|\s+AMOUNT)?\b|GST\b)",
    re.IGNORECASE,
)


def current_melbourne_business_date():
    return datetime.now(MELBOURNE_TIMEZONE).date()


def parse_attache_invoice_pdf_bytes(
    pdf_bytes,
    source_filename="invoice.pdf",
    import_date=None,
):
    return parse_attache_invoice_text(
        extract_pdf_text(pdf_bytes),
        source_filename=source_filename,
        import_date=import_date,
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


def parse_attache_invoice_text(text, source_filename="invoice.txt", import_date=None):
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
    if not delivery_date:
        delivery_date = (_resolve_import_date(import_date) + timedelta(days=1)).isoformat()

    time_instruction, start_time, end_time = _parse_time_instruction(full_text)
    customer_code = _parse_customer_code(lines)
    order_no = _parse_order_no(lines)
    customer_profile = _parse_customer_profile(lines)

    company_name = customer_profile.get("company_name") or _find_field(lines, ("Company",))
    phone = customer_profile.get("phone") or _find_field(lines, ("Phone", "Tel", "Telephone"))
    delivery_address = customer_profile.get("delivery_address") or _find_field(lines, ("Delivery Address", "Address"))
    suburb = customer_profile.get("suburb") or _find_field(lines, ("Suburb",))
    postcode = customer_profile.get("postcode") or _find_field(lines, ("Postcode", "Post Code"))

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
        carton_quantity=product_result["carton_quantity"],
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


def _is_order_no_date_header(line):
    compact = re.sub(r"[^A-Z0-9]+", "", str(line or "").upper())
    return compact == "ORDERNODATE"


def _find_order_no_date_row(lines):
    for index, line in enumerate(lines):
        if not _is_order_no_date_header(line) or index + 1 >= len(lines):
            continue
        parts = lines[index + 1].split()
        if len(parts) >= 3 and _looks_like_date(parts[0]):
            return {
                "customer_code": clean_optional_text(parts[1]),
                "order_no": clean_optional_text(parts[2]),
            }
    return {}


def _is_customer_code_noise(value):
    upper = str(value or "").strip().upper()
    return (
        not upper
        or upper in {"CODE", "DATE"}
        or upper.startswith("CODE DESCRIPTION")
        or " DESCRIPTION " in f" {upper} "
    )


def _parse_customer_code(lines):
    inline = _find_regex("\n".join(lines), r"Customer Code\s*[:#]\s*([A-Z0-9-]+)")
    if inline:
        return inline
    order_no_date_customer_code = _find_order_no_date_row(lines).get("customer_code")
    if order_no_date_customer_code:
        return order_no_date_customer_code
    header_value = _find_field(lines, ("Customer Code",))
    if header_value and not _is_customer_code_noise(header_value):
        return header_value.split()[0]
    for index, line in enumerate(lines):
        if (
            line.strip().upper() == "CUSTOMER"
            and index + 2 < len(lines)
            and lines[index + 1].strip().upper() == "CODE"
        ):
            candidate = clean_optional_text(lines[index + 2])
            if candidate and not _is_customer_code_noise(candidate):
                return candidate.split()[0]
    return None


def _parse_order_no(lines):
    inline = _find_regex(
        "\n".join(lines),
        r"(?:Order No|PO No|Purchase Order)\s*[:#]\s*([A-Z0-9-]+)",
    )
    if inline:
        return inline
    order_no_date_row = _find_order_no_date_row(lines)
    if order_no_date_row.get("order_no"):
        return order_no_date_row["order_no"]
    for index, line in enumerate(lines):
        if line.strip().upper() == "ORDER NO" and index + 1 < len(lines):
            candidate = clean_optional_text(lines[index + 1])
            if candidate and not _looks_like_date(candidate):
                return candidate.split()[0]
    return None


def _parse_customer_profile(lines):
    invoice_block = _collect_block(lines, "Invoice to:")
    delivery_block = _collect_block(lines, "Deliver to:")
    delivery_context = _collect_delivery_context_window(lines)
    tax_window = _collect_tax_invoice_window(lines)

    invoice_profile = _profile_from_address_block(invoice_block)
    delivery_profile = _profile_from_address_block(delivery_block)

    matching_invoice_postcode = None
    uses_invoice_address_fallback = not (
        delivery_profile.get("delivery_address")
        and delivery_profile.get("suburb")
    )
    if uses_invoice_address_fallback or _profiles_match(
        delivery_profile,
        invoice_profile,
    ):
        matching_invoice_postcode = invoice_profile.get("postcode")

    phone = (
        _find_phone(delivery_context)
        or _find_phone(delivery_block)
        or _find_phone(tax_window)
    )
    postcode = (
        delivery_profile.get("postcode")
        or matching_invoice_postcode
        or _find_postcode(delivery_context)
        or _find_postcode(tax_window)
    )
    return {
        "company_name": (
            invoice_profile.get("company_name")
            or delivery_profile.get("company_name")
        ),
        "delivery_address": (
            delivery_profile.get("delivery_address")
            or invoice_profile.get("delivery_address")
        ),
        "suburb": (
            delivery_profile.get("suburb")
            or invoice_profile.get("suburb")
        ),
        "postcode": postcode,
        "phone": phone,
    }


def _collect_block(lines, header):
    header_upper = header.upper()
    block = []
    collecting = False
    for line in lines:
        if line.upper() == header_upper:
            collecting = True
            continue
        if not collecting:
            continue
        if _is_stop_marker(line):
            break
        block.append(line)
    return block


def _collect_delivery_context_window(lines, max_lines=20):
    for index, line in enumerate(lines):
        if line.upper() != "DELIVER TO:":
            continue
        window = []
        for candidate in lines[index + 1 : index + 1 + max_lines]:
            upper = candidate.upper()
            if upper.startswith(("PRICE PER NET", "AMT+GST", "CODE DESCRIPTION")):
                break
            window.append(candidate)
        return window
    return []


def _collect_tax_invoice_window(lines):
    window = []
    collecting = False
    for line in lines:
        if line.upper() == "TAX INVOICE":
            collecting = True
            continue
        if not collecting:
            continue
        if line.upper().startswith("PRICE PER NET") or line.upper().startswith("AMT+GST"):
            break
        window.append(line)
    return window


def _is_stop_marker(line):
    text = str(line or "").strip()
    upper = text.upper()
    if upper.startswith("UNIT ") and _is_unit_street_address(text):
        return False
    if TOTAL_STOP_PATTERN.match(text):
        return True
    return any(upper.startswith(marker.upper()) for marker in STOP_BLOCK_MARKERS)


def _is_unit_street_address(line):
    return bool(
        re.match(
            r"^UNIT\s+[A-Z]*\d+[A-Z0-9-]*\s*(?:[/,-]\s*)?\d+\b",
            str(line or "").strip(),
            re.IGNORECASE,
        )
    )


def _profiles_match(left, right):
    for field in ("company_name", "delivery_address"):
        left_value = _normalize_profile_value(left.get(field))
        right_value = _normalize_profile_value(right.get(field))
        if not left_value or left_value != right_value:
            return False
    left_suburb = _normalize_profile_value(left.get("suburb"))
    right_suburb = _normalize_profile_value(right.get("suburb"))
    return not (left_suburb and right_suburb and left_suburb != right_suburb)


def _normalize_profile_value(value):
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _profile_from_address_block(block):
    content = []
    metadata_value_may_follow = False
    for line in block:
        text = str(line or "").strip()
        if not text:
            continue
        if re.match(
            r"^(?:ORDER\s+(?:NO|NUMBER)|PO\s+(?:NO|NUMBER)|PURCHASE\s+ORDER)\s*:?#?\s*$",
            text,
            re.IGNORECASE,
        ):
            metadata_value_may_follow = True
            continue
        if metadata_value_may_follow:
            metadata_value_may_follow = False
            if re.fullmatch(r"[A-Z0-9./-]+", text, re.IGNORECASE):
                continue
        if (
            _parse_time_instruction(text)[0]
            or _find_phone([text])
            or _is_operational_instruction(text)
            or _is_supplier_or_issuer_line(text)
        ):
            continue
        content.append(text)
    if not content:
        return {}

    company_name = content[0]
    postcode = _find_postcode(content)
    suburb = None
    address_lines = []
    for line in content[1:]:
        if _is_supplier_or_issuer_line(line):
            break
        if _is_postcode_line(line):
            if address_lines and suburb:
                break
            continue
        suburb_postcode_match = re.match(r"^(.+?)[,\s]+(\d{4})$", line)
        if suburb_postcode_match:
            suburb = suburb_postcode_match.group(1).strip(" ,")
            postcode = postcode or suburb_postcode_match.group(2)
            if address_lines:
                break
            continue
        if postcode and not suburb and _looks_like_suburb_line(line):
            suburb = line
            continue
        if postcode and suburb and address_lines:
            break
        address_lines.append(line)

    if not suburb and address_lines:
        address_line, inferred_suburb, inferred_postcode = _split_address(address_lines[-1])
        if inferred_suburb:
            address_lines[-1] = address_line
            suburb = inferred_suburb
            postcode = postcode or inferred_postcode

    if (
        not suburb
        and len(address_lines) >= 2
        and _looks_like_suburb_line(address_lines[-1])
    ):
        suburb = address_lines.pop().strip(" ,")

    return {
        "company_name": clean_optional_text(company_name),
        "delivery_address": clean_optional_text(", ".join(address_lines)),
        "suburb": clean_optional_text(str(suburb or "").strip(" ,")),
        "postcode": clean_optional_text(postcode),
    }


def _find_phone(lines):
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("PHONE:"):
            continue
        if _is_phone_like_line(stripped):
            return clean_optional_text(stripped)
    return None


def _is_phone_like_line(line):
    stripped = str(line or "").strip()
    digits = re.sub(r"\D", "", stripped)
    if len(digits) < 8:
        return False
    if stripped.upper().startswith(("PHONE:", "TEL:", "TELEPHONE:", "MOBILE:")):
        return True
    return bool(re.fullmatch(r"[()0-9 +.-]+", stripped))


def _is_supplier_or_issuer_line(line):
    text = str(line or "").strip()
    upper = text.upper()
    if upper.startswith(("ABN", "EMAIL:", "WEB:")):
        return True
    normalized = re.sub(r"[^A-Z0-9]+", " ", upper)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return any(marker in normalized for marker in SUPPLIER_ISSUER_MARKERS)


def _find_postcode(lines):
    for line in lines:
        if _is_postcode_line(line):
            return line.strip()
    for line in lines:
        text = str(line or "").strip()
        if (
            not text
            or _is_phone_like_line(text)
            or _is_supplier_or_issuer_line(text)
            or _is_stop_marker(text)
        ):
            continue
        match = re.fullmatch(r"(.+?)[,\s]+(\d{4})", text)
        if match and _looks_like_suburb_line(match.group(1).strip(" ,")):
            return match.group(2)
    return None


def _is_postcode_line(line):
    return bool(re.fullmatch(r"\d{4}", str(line or "").strip()))


def _looks_like_date(value):
    return bool(
        re.match(
            r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            str(value or "").strip(),
        )
    )


def _looks_like_suburb_line(line):
    text = str(line or "").strip()
    return bool(text) and not any(character.isdigit() for character in text)


def _is_operational_instruction(line):
    upper = str(line or "").upper()
    return any(
        marker in upper
        for marker in (
            "NO VAN",
            "MUST BE TRUCK",
            "EMAIL INVOICE",
            "CREDIT CARD",
            "PRE PAYMENT",
        )
    )


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
    products = []
    warnings = []
    pallet_quantity = 0
    carton_quantity = 0
    explicit_loose_bags = 0
    packaging_bags = 0
    preceding_product = None
    pending_packet = None

    for line, classification in _line_item_rows(lines):
        category = classification["category"]
        if pending_packet is not None and category != "PACKET_SUMMARY":
            _apply_packet_packaging(pending_packet, None, warnings)
            pending_packet = None
        if category == "PRODUCT":
            preceding_product = classification["product"]
            products.append(preceding_product)
            if str(preceding_product.get("package_unit") or "").upper() == "BAG":
                packaging_bags += int(preceding_product.get("package_quantity") or 0)
            continue
        if category == "PACKAGING":
            packaging_bags += classification["quantity"]
            if preceding_product is not None:
                preceding_product["package_quantity"] = classification["quantity"]
                preceding_product["package_unit"] = classification["unit"]
            else:
                warnings.append(_unknown_row_warning(line))
            preceding_product = None
            continue
        if category == "PACKET_DESCRIPTOR":
            if preceding_product is None:
                warnings.append(_unknown_row_warning(line))
            else:
                pending_packet = {
                    "product": preceding_product,
                    **classification,
                }
            preceding_product = None
            continue
        if category == "PACKET_SUMMARY":
            if pending_packet is None:
                warnings.append(_unknown_row_warning(line))
            else:
                _apply_packet_packaging(
                    pending_packet,
                    classification["quantity"],
                    warnings,
                )
                pending_packet = None
            continue
        preceding_product = None
        if category == "LOAD":
            load_kind = classification["load_kind"]
            if load_kind == "PALLET":
                pallet_quantity += classification["quantity"]
            elif load_kind == "CARTON":
                carton_quantity += classification["quantity"]
            elif load_kind == "LOOSE_BAG":
                explicit_loose_bags += classification["quantity"]
            continue
        if category == "UNKNOWN":
            warnings.append(_unknown_row_warning(line))

    if pending_packet is not None:
        _apply_packet_packaging(pending_packet, None, warnings)

    loose_bags_quantity = explicit_loose_bags
    if pallet_quantity == 0 and carton_quantity == 0:
        loose_bags_quantity += packaging_bags

    return {
        "pallet_quantity": pallet_quantity,
        "loose_bags_quantity": loose_bags_quantity,
        "carton_quantity": carton_quantity,
        "product_lines": products,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _line_item_rows(lines):
    rows = []
    header_seen = False
    in_table = False
    for line in lines:
        normalized = str(line or "").strip()
        if LINE_ITEM_HEADER_PATTERN.search(normalized):
            header_seen = True
            continue
        if (in_table or header_seen) and LINE_ITEM_FOOTER_PATTERN.search(normalized):
            if in_table:
                break
            continue

        classification = _classify_invoice_row(normalized)
        if classification["category"] != "UNKNOWN":
            in_table = True
            rows.append((normalized, classification))
            continue
        if in_table and _looks_like_unknown_item_row(normalized):
            rows.append((normalized, classification))
    return rows


def _classify_invoice_row(line):
    packet_summary = _parse_packet_summary_row(line)
    if packet_summary:
        return {"category": "PACKET_SUMMARY", **packet_summary}
    code = _line_code(line)
    if _is_charge_row(code, line):
        return {"category": "CHARGE"}
    packaging = _parse_packaging_row(code, line)
    if packaging:
        return {"category": "PACKAGING", **packaging}
    packet_descriptor = _parse_packet_descriptor_row(code, line)
    if packet_descriptor:
        return {"category": "PACKET_DESCRIPTOR", **packet_descriptor}
    load = _parse_load_row(code, line)
    if load:
        return {"category": "LOAD", **load}
    product = _parse_product_row(code, line)
    if product:
        return {"category": "PRODUCT", "product": product}
    return {"category": "UNKNOWN"}


def _is_charge_row(code, line):
    return code in CHARGE_CODES or bool(CHARGE_DESCRIPTION_PATTERN.search(str(line or "")))


def _parse_packaging_row(code, line):
    if not PACKAGING_CODE_PATTERN.fullmatch(code):
        return None
    if "PLASTIC BAG" not in str(line or "").upper():
        return None
    quantity = _parse_packaging_quantity(line)
    if quantity <= 0:
        return None
    return {"quantity": quantity, "unit": code}


def _parse_packet_summary_row(line):
    match = re.fullmatch(r"\s*(\d+)\s*(?:PACKETS?|PKT)\s*", str(line or ""), re.IGNORECASE)
    if not match or int(match.group(1)) <= 0:
        return None
    return {"quantity": int(match.group(1))}


def _parse_packet_descriptor_row(code, line):
    if code != "PKT":
        return None
    text = str(line or "")
    phrase = re.search(r"\bPIECES\s+(?:IN\s+A|PER)\s+PACKET\b", text, re.IGNORECASE)
    if not phrase:
        return None

    before_phrase = text[: phrase.start()]
    encoded_match = re.search(r"\bPKT(\d+)\s*$", before_phrase, re.IGNORECASE)
    pieces_match = re.search(r"(\d+)\s*$", before_phrase)
    pieces_per_packet = None
    encoded_packet_digits = None
    if encoded_match:
        encoded_packet_digits = encoded_match.group(1)
    elif pieces_match and int(pieces_match.group(1)) > 0:
        pieces_per_packet = int(pieces_match.group(1))

    after_phrase = text[phrase.end() :]
    quantity_match = re.search(
        r"\b(\d+)\s*(?:PKT|PACKETS?)\b",
        after_phrase,
        re.IGNORECASE,
    )
    package_quantity = int(quantity_match.group(1)) if quantity_match else None
    return {
        "pieces_per_packet": pieces_per_packet,
        "package_quantity": package_quantity,
        "encoded_packet_digits": encoded_packet_digits,
    }


def _apply_packet_packaging(packet, summary_quantity, warnings):
    descriptor_quantity = packet.get("package_quantity")
    if (
        descriptor_quantity is not None
        and summary_quantity is not None
        and descriptor_quantity != summary_quantity
    ):
        warnings.append(
            "Packet quantity mismatch: "
            f"descriptor says {descriptor_quantity}; summary says {summary_quantity}."
        )

    package_quantity = descriptor_quantity or summary_quantity
    pieces_per_packet = packet.get("pieces_per_packet")
    encoded_packet_digits = packet.get("encoded_packet_digits")
    if pieces_per_packet is None and encoded_packet_digits:
        summary_prefix = str(summary_quantity or "")
        if (
            summary_prefix
            and encoded_packet_digits.startswith(summary_prefix)
            and len(encoded_packet_digits) > len(summary_prefix)
        ):
            pieces_per_packet = int(encoded_packet_digits[len(summary_prefix) :])
        elif len(encoded_packet_digits) <= 3:
            pieces_per_packet = int(encoded_packet_digits)

    if package_quantity and pieces_per_packet:
        packet["product"]["package_quantity"] = package_quantity
        packet["product"]["package_unit"] = f"PKT{pieces_per_packet}"
        return

    warnings.append("Packet packaging details require review.")


def _parse_load_row(code, line):
    upper = str(line or "").upper()
    if code == "PAL" and ("PALLET" in upper or "PLT" in upper):
        return _load_row("PALLET", _parse_named_load_quantity(upper, "PALLETS?"))
    if code == "CTN" and ("CARTON" in upper or "CTN" in upper):
        return _load_row("CARTON", _parse_named_load_quantity(upper, "CARTONS?"))
    if (
        code in {"LBAG", "LOOSEBAG", "LOOSE-BAG"}
        or (code == "BAG" and "LOOSE" in upper)
    ) and "PLASTIC BAG" not in upper:
        return _load_row(
            "LOOSE_BAG",
            _parse_named_load_quantity(upper, r"LOOSE\s+BAGS?"),
        )
    return None


def _load_row(load_kind, quantity):
    if quantity <= 0:
        return None
    return {"load_kind": load_kind, "quantity": quantity}


def _parse_named_load_quantity(line, label_pattern):
    before = re.search(rf"(?<!\d)(\d+)\s*{label_pattern}\b", line, re.IGNORECASE)
    if before and int(before.group(1)) > 0:
        return int(before.group(1))
    after = re.search(rf"\b{label_pattern}\s+(\d+)\b", line, re.IGNORECASE)
    return int(after.group(1)) if after else 0


def _line_code(line):
    parts = str(line or "").strip().split()
    return parts[0].upper() if parts else ""


def _parse_pallet_quantity(line):
    return _parse_named_load_quantity(str(line or ""), "PALLETS?")


def _parse_packaging_quantity(line):
    mcc_match = re.match(
        r"^BAG\d+(?:\.\d+)?\s+(?:[\d.]+\s+)*?(\d+)\s*PLASTIC",
        line,
        re.IGNORECASE,
    )
    if mcc_match:
        return int(mcc_match.group(1))
    smiths_match = re.search(r"PLASTIC BAG\s+\d+\s*kg\s+(\d+)\s*$", line, re.IGNORECASE)
    if smiths_match:
        return int(smiths_match.group(1))
    numbers = re.findall(r"\b\d+\b", line)
    return int(numbers[-1]) if numbers else 0


def _parse_product_row(code, line):
    if (
        not PRODUCT_CODE_PATTERN.fullmatch(code)
        or code in CHARGE_CODES
        or PACKAGING_CODE_PATTERN.fullmatch(code)
        or code in {"PAL", "CTN", "LBAG", "LOOSEBAG", "LOOSE-BAG"}
    ):
        return None
    compact = _parse_compact_product_row(code, line)
    if compact:
        return compact

    parts = str(line or "").split()
    upper_parts = [part.upper() for part in parts]
    for unit_index in range(1, len(parts)):
        unit = upper_parts[unit_index]
        if unit not in PRODUCT_UNITS:
            continue
        parsed = _parse_product_around_unit(code, parts, unit_index, unit)
        if parsed:
            return parsed

    legacy_units = "|".join(sorted(PRODUCT_UNITS, key=len, reverse=True))
    legacy = re.match(
        rf"^{re.escape(code)}\s+(.+?)\s+(\d+)\s+({legacy_units})\b",
        str(line or ""),
        re.IGNORECASE,
    )
    if not legacy:
        return None
    return _product_line(code, legacy.group(1), int(legacy.group(2)), legacy.group(3))


def _parse_compact_product_row(code, line):
    remainder = str(line or "")[len(code) :].strip()
    unit_pattern = "|".join(sorted(PRODUCT_UNITS, key=len, reverse=True))
    leading_unit = re.match(
        rf"^({unit_pattern})(\d+)(?=[A-Z])(.+)$",
        remainder,
        re.IGNORECASE,
    )
    if leading_unit:
        name_tokens = _strip_trailing_numeric_tokens(leading_unit.group(3).split())
        name = _clean_product_name(" ".join(name_tokens))
        if name:
            return _product_line(
                code,
                name,
                int(leading_unit.group(2)),
                leading_unit.group(1),
            )

    leading_quantity = re.match(r"^(\d+)(?=[A-Z])(.+)$", remainder, re.IGNORECASE)
    if leading_quantity:
        payload = leading_quantity.group(2).split()
        for unit_index in range(len(payload) - 1, 0, -1):
            unit = payload[unit_index].upper()
            if unit not in PRODUCT_UNITS:
                continue
            if not payload[unit_index + 1 :] or not _is_decimal(payload[unit_index + 1]):
                continue
            name = _clean_product_name(" ".join(payload[:unit_index]))
            if name:
                return _product_line(
                    code,
                    name,
                    int(leading_quantity.group(1)),
                    unit,
                )

    match = re.match(
        r"^(\d+)(?=[A-Z])(.+?)(?:\d[\d.,]*)+(KG|BAG|ROLL|PACK|BOX|CTN)\s*$",
        remainder,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _product_line(code, match.group(2), int(match.group(1)), match.group(3))


def _parse_product_around_unit(code, parts, unit_index, unit):
    after = parts[unit_index + 1 :]
    if not after:
        return None
    inline_product = _parse_inline_quantity_after_financials(after)
    if inline_product:
        quantity, name = inline_product
        product = _product_line(code, name, quantity, unit)
        if product["unit"] in {"BAG", "BAGS"}:
            product["package_quantity"] = quantity
            product["package_unit"] = "BAG"
        return product
    if _is_integer(after[0]):
        quantity = int(after[0])
        name_tokens = _strip_trailing_numeric_tokens(after[1:])
    elif _is_decimal(after[0]) and len(after) >= 3 and _is_integer(after[-1]):
        quantity = int(after[-1])
        name_tokens = list(after[1:-1])
        while name_tokens and _is_decimal(name_tokens[0]):
            name_tokens.pop(0)
    elif _is_decimal(after[0]) and len(after) >= 3:
        quantity_index = next(
            (
                index
                for index, token in enumerate(after)
                if index > 0
                and _is_integer(token)
                and any(not _is_decimal(candidate) for candidate in after[index + 1 :])
            ),
            None,
        )
        if quantity_index is None:
            return None
        quantity = int(after[quantity_index])
        name_tokens = list(after[quantity_index + 1 :])
    else:
        return None
    name = _clean_product_name(" ".join(name_tokens))
    if not name or quantity <= 0:
        return None
    return _product_line(code, name, quantity, unit)


def _parse_inline_quantity_after_financials(tokens):
    for index in range(3, len(tokens)):
        if not all(_is_decimal(token) for token in tokens[:index]):
            break
        match = re.fullmatch(r"(\d+)(?=[A-Z])(.+)", tokens[index], re.IGNORECASE)
        if not match or int(match.group(1)) <= 0:
            continue
        name = _clean_product_name(" ".join([match.group(2), *tokens[index + 1 :]]))
        if name:
            return int(match.group(1)), name
    return None


def _resolve_import_date(value):
    if value is None:
        return current_melbourne_business_date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError("import_date must be a valid date")
    return parsed


def _strip_trailing_numeric_tokens(tokens):
    cleaned = list(tokens)
    while cleaned and (_is_decimal(cleaned[-1]) or _is_money(cleaned[-1])):
        cleaned.pop()
    return cleaned


def _is_integer(value):
    return bool(re.fullmatch(r"\d+", str(value or "")))


def _is_decimal(value):
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", str(value or "").replace(",", "")))


def _is_money(value):
    return bool(re.fullmatch(r"\$?\d[\d,]*(?:\.\d+)?", str(value or "")))


def _product_line(code, name, quantity, unit):
    return {
        "product_name": _clean_product_name(name),
        "quantity": quantity,
        "unit": _canonical_product_unit(unit),
        "product_code": code,
        "package_quantity": None,
        "package_unit": None,
    }


def _canonical_product_unit(unit):
    normalized = str(unit or "").upper()
    return "EACH" if normalized == "EAC" else normalized


def _clean_product_name(value):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    name = re.sub(
        r"\b(SHTS)\s*[xX]\s*(\d+)\s*(ROLLS?)\b",
        r"\1 x \2 \3",
        name,
        flags=re.IGNORECASE,
    )
    return name


def _strip_trailing_order_weight(value):
    name = _clean_product_name(value)
    return re.sub(r"\s+\d+\s*KG$", "", name, flags=re.IGNORECASE)


def _looks_like_unknown_item_row(line):
    parts = str(line or "").split()
    if len(parts) < 2 or not PRODUCT_CODE_PATTERN.fullmatch(parts[0]):
        return False
    return any(re.search(r"[A-Za-z]", part) for part in parts[1:])


def _unknown_row_warning(line):
    context = re.sub(r"\$?\b\d[\d,.]*\b", "", str(line or ""))
    context = re.sub(r"\s+", " ", context).strip(" -:/")
    context = context[:120] or _line_code(line) or "unrecognised row"
    return f"Unclassified invoice item: {context}"


def _build_note(lines, customer_code=None, order_no=None, time_instruction=None):
    note_lines = []
    if customer_code:
        note_lines.append(f"Customer Code: {customer_code}")
    if time_instruction:
        note_lines.append(time_instruction)

    for line in _extract_operational_note_blocks(lines):
        if line not in note_lines:
            note_lines.append(line)

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


def _extract_operational_note_blocks(lines):
    note_lines = []
    collecting = False
    remaining_lines = 0
    for line in lines:
        normalized = str(line or "").strip()
        upper = normalized.upper()
        is_anchor = any(marker in upper for marker in OPERATIONAL_NOTE_ANCHORS)
        if is_anchor:
            collecting = True
            remaining_lines = 12
        elif collecting and _is_operational_note_stop(normalized):
            collecting = False
            remaining_lines = 0
            continue

        if not collecting:
            continue
        formatted = _format_operational_note_line(normalized)
        if formatted and formatted not in note_lines:
            note_lines.append(formatted)
        remaining_lines -= 1
        if remaining_lines <= 0:
            collecting = False
    return note_lines


def _is_operational_note_stop(line):
    upper = str(line or "").strip().upper()
    if _is_customer_email_line(line):
        return False
    if (
        not upper
        or _is_operational_note_supplier_stop(line)
        or upper.startswith(
            (
                "ACCOUNT:",
                "AMT+GST",
                "BSB:",
                "CODE DESCRIPTION",
                "GOODS REMAIN",
                "PAYMENT BY",
                "PLEASE NOTE NEW BANK ACC DETAILS",
                "PRICE PER NET",
                "TERMS:",
                "TOTAL",
            )
        )
        or _looks_like_product_or_transport_line(line)
    ):
        return True
    return False


def _is_operational_note_supplier_stop(line):
    text = str(line or "").strip()
    upper = text.upper()
    if upper.startswith(("ABN", "EMAIL:", "WEB:")) or "@TEAMSAUSTRALIA.COM.AU" in upper:
        return True
    normalized = re.sub(r"[^A-Z0-9]+", " ", upper)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return any(
        marker in normalized
        for marker in (
            "B S L WIPERS",
            "BSL WIPERS",
            "MCC RAGMAN",
            "MELBOURNE CLEANING CLOTHS",
            "SMITHS RAGS",
            "98 102 HUME HIGHWAY",
        )
    )


def _looks_like_product_or_transport_line(line):
    classification = _classify_invoice_row(str(line or ""))
    if classification["category"] != "CHARGE":
        return classification["category"] != "UNKNOWN"
    code = _line_code(line)
    return code in {"DEL", "FREIGHT", "FUEL", "SURCHARGE"} or bool(
        CHARGE_DESCRIPTION_PATTERN.search(str(line or ""))
    )


def _is_customer_email_line(line):
    text = str(line or "").strip()
    return bool(
        re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text)
    ) and not _is_operational_note_supplier_stop(text)


def _format_operational_note_line(line):
    text = str(line or "").strip()
    if _is_customer_email_line(text):
        return f"[{text}](mailto:{text})"
    return text


def _is_noise_line(line):
    upper = str(line or "").upper()
    return any(pattern in upper for pattern in ACCOUNTING_NOISE_PATTERNS)


def _build_warnings(invoice_number, company_name, delivery_date, suburb, product_result):
    warnings = list(product_result.get("warnings") or [])
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
