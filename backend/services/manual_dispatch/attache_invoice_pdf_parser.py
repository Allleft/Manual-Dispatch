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
PACKAGING_UNITS = {"BAG10", "BAG5", "BAG1.5"}
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
    "Total",
    "UNIT ",
    "web:",
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
PRODUCT_LINE_PATTERN = re.compile(
    r"^(?P<code>[A-Z0-9#-]+)\s+(?P<name>.+?)\s+(?P<quantity>\d+)\s+"
    r"(?P<unit>PALLETS?|PAL|CARTONS?|CTN|BAG10|BAG5|BAG1\.5|BAGS?|DELIVERY)\b",
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

    profile = invoice_profile
    if _is_valid_delivery_profile(delivery_profile):
        profile = delivery_profile

    matching_invoice_postcode = None
    if profile is delivery_profile and _profiles_match(delivery_profile, invoice_profile):
        matching_invoice_postcode = invoice_profile.get("postcode")

    phone = (
        _find_phone(delivery_context)
        or _find_phone(delivery_block)
        or _find_phone(tax_window)
    )
    postcode = (
        profile.get("postcode")
        or matching_invoice_postcode
        or _find_postcode(delivery_context)
        or _find_postcode(tax_window)
    )
    return {
        "company_name": profile.get("company_name"),
        "delivery_address": profile.get("delivery_address"),
        "suburb": profile.get("suburb"),
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
    upper = str(line or "").upper()
    if upper.startswith("UNIT ") and _is_unit_street_address(line):
        return False
    return any(upper.startswith(marker.upper()) for marker in STOP_BLOCK_MARKERS)


def _is_unit_street_address(line):
    return bool(
        re.match(
            r"^UNIT\s+[A-Z]*\d+[A-Z0-9-]*\s*(?:[/,-]\s*)?\d+\b",
            str(line or "").strip(),
            re.IGNORECASE,
        )
    )


def _is_valid_delivery_profile(profile):
    return all(
        profile.get(field)
        for field in ("company_name", "delivery_address", "suburb")
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
    content = [
        line
        for line in block
        if line
        and not _parse_time_instruction(line)[0]
        and not _find_phone([line])
        and not _is_operational_instruction(line)
        and not _is_supplier_or_issuer_line(line)
    ]
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
    pallet_quantity = 0
    last_product = None
    for line in lines:
        if _is_noise_line(line):
            continue
        code = _line_code(line)
        if code in IGNORED_PRODUCT_CODES:
            continue
        if code == "PAL":
            quantity = _parse_pallet_quantity(line)
            pallet_quantity += quantity
            _assign_transport_unit(products, "PALLETS", quantity)
            continue
        if _is_carton_transport_line(line):
            _assign_transport_unit(
                products,
                "CARTONS",
                _parse_carton_quantity(line),
                prefer_carton_product=True,
            )
            continue
        if code in PACKAGING_UNITS:
            if last_product:
                last_product["packaging_code"] = code
                last_product["packaging_quantity"] = _parse_packaging_quantity(line)
            continue

        kg_product = _parse_kg_product_line(line)
        if kg_product:
            products.append(kg_product)
            last_product = kg_product
            continue

        bag_product = _parse_real_bag_product_line(line)
        if bag_product:
            products.append(bag_product)
            last_product = bag_product
            continue

        legacy_product = _parse_legacy_product_line(line)
        if legacy_product:
            unit = legacy_product["unit"]
            if unit in {"PAL", "PALLET", "PALLETS"}:
                pallet_quantity += legacy_product["quantity"]
                product = _new_product(
                    _strip_trailing_order_weight(legacy_product["name"]),
                    source_unit="PALLETS",
                )
                product["transport_unit"] = "PALLETS"
                product["transport_quantity"] = legacy_product["quantity"]
                products.append(product)
                last_product = product
            elif unit in {"CTN", "CARTON", "CARTONS"}:
                product = _new_product(
                    _strip_trailing_order_weight(legacy_product["name"]),
                    source_unit="CARTONS",
                )
                product["transport_unit"] = "CARTONS"
                product["transport_quantity"] = legacy_product["quantity"]
                products.append(product)
                last_product = product
            elif unit in PACKAGING_UNITS:
                if last_product:
                    last_product["packaging_code"] = unit
                    last_product["packaging_quantity"] = legacy_product["quantity"]
                else:
                    product = _new_product(
                        _strip_trailing_order_weight(legacy_product["name"]),
                        legacy_product["quantity"],
                        "BAGS",
                    )
                    products.append(product)
                    last_product = product
            elif unit in {"BAG", "BAGS"}:
                product = _new_product(
                    legacy_product["name"],
                    legacy_product["quantity"],
                    "BAGS",
                )
                products.append(product)
                last_product = product
            continue

    product_lines = []
    loose_bags_quantity = 0
    for product in products:
        transport_quantity = product.get("transport_quantity") or 0
        transport_unit = product.get("transport_unit")
        if transport_quantity > 0 and transport_unit:
            product_lines.append(
                _product_line(product["name"], transport_quantity, transport_unit)
            )
            continue
        bag_quantity = product.get("packaging_quantity") or product.get("source_quantity") or 0
        if bag_quantity > 0:
            loose_bags_quantity += bag_quantity
            product_lines.append(_product_line(product["name"], bag_quantity, "BAGS"))

    return {
        "pallet_quantity": pallet_quantity,
        "loose_bags_quantity": loose_bags_quantity,
        "product_lines": _dedupe_product_lines(product_lines),
    }


def _new_product(name, source_quantity=0, source_unit=None):
    return {
        "name": name,
        "source_quantity": source_quantity,
        "source_unit": source_unit,
        "packaging_code": None,
        "packaging_quantity": 0,
        "transport_unit": None,
        "transport_quantity": 0,
    }


def _assign_transport_unit(products, unit, quantity, prefer_carton_product=False):
    if quantity <= 0:
        return
    candidates = [product for product in products if not product.get("transport_unit")]
    if prefer_carton_product:
        carton_candidates = [
            product
            for product in candidates
            if product.get("packaging_code") == "BAG1.5"
            or "1.5KG" in str(product.get("name") or "").upper().replace(" ", "")
        ]
        if carton_candidates:
            candidates = carton_candidates
    elif unit == "PALLETS":
        packaged_candidates = [
            product
            for product in candidates
            if product.get("packaging_code") in PACKAGING_UNITS
        ]
        if packaged_candidates:
            candidates = packaged_candidates
    if not candidates:
        return
    product = candidates[-1] if prefer_carton_product else candidates[0]
    product["transport_unit"] = unit
    product["transport_quantity"] = quantity


def _is_carton_transport_line(line):
    return bool(re.search(r"\b(?:CTN|CARTONS?)\b", str(line or ""), re.IGNORECASE))


def _parse_carton_quantity(line):
    matches = re.findall(
        r"\b(?:CTN|CARTONS?)\s+(\d+)(?!\.)\b",
        str(line or ""),
        re.IGNORECASE,
    )
    return int(matches[-1]) if matches else 0


def _line_code(line):
    parts = str(line or "").strip().split()
    return parts[0].upper() if parts else ""


def _parse_pallet_quantity(line):
    match = re.search(r"\bPLT\s+(\d+)(?!\.)\b", line, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\bPALLET\s+(\d+)\s*$", line, re.IGNORECASE)
    if match:
        return int(match.group(1))
    numbers = re.findall(r"\b\d+\b", line)
    return int(numbers[-1]) if numbers else 0


def _parse_packaging_quantity(line):
    mcc_match = re.match(
        r"^BAG\d+\s+(?:[\d.]+\s+)*?(\d+)\s+PLASTIC",
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


def _parse_kg_product_line(line):
    parts = str(line or "").split()
    upper_parts = [part.upper() for part in parts]
    if "KG" not in upper_parts:
        return None
    kg_index = upper_parts.index("KG")
    after = parts[kg_index + 1 :]
    if len(after) < 2:
        return None

    if _is_integer(after[0]):
        weight = after[0]
        name_tokens = _strip_trailing_numeric_tokens(after[1:])
    else:
        if not _is_decimal(after[0]):
            return None
        weight = after[-1] if _is_integer(after[-1]) else ""
        name_tokens = after[1:-1] if weight else after[1:]
        name_tokens = _strip_trailing_numeric_tokens(name_tokens)

    name = _strip_trailing_order_weight(" ".join(name_tokens))
    return _new_product(name, source_unit="KG") if name else None


def _parse_real_bag_product_line(line):
    parts = str(line or "").split()
    upper_parts = [part.upper() for part in parts]
    if "BAG" not in upper_parts:
        return None
    bag_index = upper_parts.index("BAG")
    if bag_index + 2 >= len(parts) or not _is_integer(parts[bag_index + 1]):
        return None
    quantity = int(parts[bag_index + 1])
    name_tokens = _strip_trailing_numeric_tokens(parts[bag_index + 2 :])
    name = _clean_product_name(" ".join(name_tokens))
    return _new_product(name, quantity, "BAGS") if name else None


def _parse_legacy_product_line(line):
    match = PRODUCT_LINE_PATTERN.match(line)
    if not match:
        return None
    return {
        "code": match.group("code").upper(),
        "name": _clean_product_name(match.group("name")),
        "quantity": int(match.group("quantity")),
        "unit": match.group("unit").upper(),
    }


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


def _product_line(name, quantity, unit):
    return {
        "product_name": name,
        "quantity": quantity,
        "unit": unit,
    }


def _clean_product_name(value):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    return name


def _strip_trailing_order_weight(value):
    name = _clean_product_name(value)
    return re.sub(r"\s+\d+\s*KG$", "", name, flags=re.IGNORECASE)


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
    code = _line_code(line)
    return (
        code in {"DEL", "FUEL"}
        or code in PACKAGING_UNITS
        or code in {"PAL", "CTN"}
        or _parse_kg_product_line(line) is not None
        or _parse_real_bag_product_line(line) is not None
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
