from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from io import BytesIO
import re

from backend.schemas import DeliveryDocketDocxPreviewItem
from backend.services.manual_dispatch.logbook_file_service import MELBOURNE_TIMEZONE
from backend.services.manual_dispatch.normalization import clean_optional_text


DOCKET_HEADER_PATTERN = re.compile(r"^DELIVERY\s+DOCKET\s*:\s*(.+)$", re.IGNORECASE)
DATE_PATTERN = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})")
PRODUCT_PATTERN = re.compile(
    r"^(\d+)\s*[Xx]\s*(\d+(?:\.\d+)?)\s*KGS?\s+(.+?)\s*$",
    re.IGNORECASE,
)
STREET_PATTERN = re.compile(
    r"\b(?:ROAD|RD|STREET|ST|COURT|CT|AVENUE|AVE|DRIVE|DR|HIGHWAY|HWY|"
    r"LANE|LN|BOULEVARD|BLVD|CRESCENT|CRES|PLACE|PL)\b",
    re.IGNORECASE,
)
SUBURB_POSTCODE_PATTERN = re.compile(
    r"^(.+?)(?:\s+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT))?\s+(\d{4})$",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"^(?:PHONE|PH|TEL|TELEPHONE|MOBILE)\s*:\s*(.+)$",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WINDOW_PATTERN = re.compile(
    r"\bOPEN\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*-\s*"
    r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\b",
    re.IGNORECASE,
)
TIME_SLOT_PATTERN = re.compile(r"^TIME\s+SLOT\s*:\s*(.+)$", re.IGNORECASE)


def current_melbourne_business_date():
    return datetime.now(MELBOURNE_TIMEZONE).date()


def extract_delivery_docket_docx_text(docx_bytes):
    try:
        from docx import Document
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as error:
        raise ValueError("DOCX parsing dependency is not installed: python-docx") from error

    try:
        document = Document(BytesIO(docx_bytes))
        parts = []
        for child in document.element.body.iterchildren():
            if isinstance(child, CT_P):
                text = Paragraph(child, document).text.strip()
                if text:
                    parts.append(text)
            elif isinstance(child, CT_Tbl):
                table = Table(child, document)
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            text = paragraph.text.strip()
                            if text:
                                parts.append(text)
    except Exception as error:
        raise ValueError("Unable to read Delivery Docket DOCX text") from error

    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("Delivery Docket DOCX did not contain extractable text")
    return text


def parse_delivery_docket_docx_bytes(
    docx_bytes,
    source_filename="delivery-docket.docx",
    import_date=None,
):
    return parse_delivery_docket_text(
        extract_delivery_docket_docx_text(docx_bytes),
        source_filename=source_filename,
        import_date=import_date,
    )


def parse_delivery_docket_text(
    text,
    source_filename="delivery-docket.txt",
    import_date=None,
):
    lines = _normalize_lines(text)
    docket_number, docket_reference = _parse_docket_header(lines)
    invoice_number = docket_reference if re.fullmatch(r"\d{6}", docket_reference or "") else None
    invoice_date = _parse_labeled_date(lines, "DATED")
    order_no = _parse_order_number(lines)
    deliver_block = _collect_block(lines, "DELIVER")
    on_forward_block = _collect_block(lines, "ON_FORWARD")
    deliver_profile = _profile_from_block(deliver_block)
    on_forward_profile = _profile_from_block(on_forward_block)
    delivery_mode = "ON_FORWARD" if on_forward_profile.get("company_name") else "DIRECT"
    company_name = (
        on_forward_profile.get("company_name")
        or deliver_profile.get("company_name")
    )
    phone = on_forward_profile.get("phone") or deliver_profile.get("phone")

    time_slot = _find_time_slot(lines)
    delivery_date = _date_from_time_slot(time_slot)
    if not delivery_date:
        delivery_date = (_resolve_import_date(import_date) + timedelta(days=1)).isoformat()
    delivery_window = _find_delivery_window(deliver_block)
    start_time, end_time = _times_from_schedule(time_slot, delivery_window)

    products, product_warnings, fractional_product = _parse_products(lines)
    pallet_quantity = _parse_load_quantity(lines, "PALLET")
    carton_quantity = _parse_load_quantity(lines, "CARTON")
    explicit_loose_bags = _parse_loose_bags(lines)
    loose_bags_quantity = explicit_loose_bags
    if pallet_quantity == 0 and carton_quantity == 0:
        loose_bags_quantity += sum(line["package_quantity"] for line in products)

    note = _build_note(
        lines,
        docket_number=docket_number,
        docket_reference=docket_reference,
        deliver_profile=deliver_profile,
        on_forward_profile=on_forward_profile,
        time_slot=time_slot,
        delivery_window=delivery_window,
    )
    warnings = list(product_warnings)
    if not products:
        warnings.append("No product lines were found; review the docket before import.")
    required_values = (
        (docket_number, "Delivery Docket number was not found."),
        (company_name, "Customer company was not found."),
        (deliver_profile.get("delivery_address"), "Deliver To street address was not found."),
        (deliver_profile.get("suburb"), "Deliver To suburb was not found."),
        (delivery_date, "Delivery date was not resolved."),
    )
    missing_required = False
    for value, warning in required_values:
        if not value:
            warnings.append(warning)
            missing_required = True
    if not any((pallet_quantity, loose_bags_quantity, carton_quantity)):
        warnings.append("No pallet, loose bag, or carton load was found.")
        missing_required = True

    return DeliveryDocketDocxPreviewItem(
        row_id=_row_id(source_filename, docket_number),
        source_filename=source_filename,
        docket_number=docket_number,
        docket_reference=docket_reference,
        delivery_mode=delivery_mode,
        invoice_number=invoice_number,
        invoice_date=invoice_date.isoformat() if invoice_date else None,
        order_no=order_no,
        company_name=company_name,
        phone=phone,
        delivery_address=deliver_profile.get("delivery_address"),
        suburb=deliver_profile.get("suburb"),
        postcode=deliver_profile.get("postcode"),
        delivery_date=delivery_date,
        zone="",
        urgency="Normal",
        preferred_driver_id="",
        pallet_quantity=pallet_quantity,
        loose_bags_quantity=loose_bags_quantity,
        carton_quantity=carton_quantity,
        start_time=start_time,
        end_time=end_time,
        note=note,
        product_lines=products,
        warnings=list(dict.fromkeys(warnings)),
        importable=not (fractional_product or missing_required),
        selected=not (fractional_product or missing_required),
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


def _parse_docket_header(lines):
    headers = []
    for index, line in enumerate(lines):
        match = DOCKET_HEADER_PATTERN.match(line)
        if match:
            headers.append((index, match.group(1).strip()))
    if not headers:
        return None, None
    index, raw = next(((i, value) for i, value in headers if "/" in value), headers[0])
    if "/" not in raw:
        return clean_optional_text(raw if raw != "073" else None), None
    docket_number, reference = (part.strip() for part in raw.split("/", 1))
    if reference.upper().startswith("NEWWAY") and index + 1 < len(lines):
        continuation = lines[index + 1]
        if not _starts_new_section(continuation):
            reference = f"{reference} {continuation}".strip()
    return clean_optional_text(docket_number), clean_optional_text(reference)


def _starts_new_section(line):
    upper = str(line or "").upper()
    return bool(
        DOCKET_HEADER_PATTERN.match(str(line or ""))
        or upper.startswith((
            "DATED", "DELIVER", "ON FWD", "EMAIL", "ORDER", "STOCK",
            "TOTAL", "TIME SLOT", "BOOKING", "SCT REFERENCE", "INVOICE TO FOLLOW",
        ))
    )


def _parse_labeled_date(lines, label):
    for line in lines:
        if not re.match(rf"^{re.escape(label)}\s*:", line, re.IGNORECASE):
            continue
        match = DATE_PATTERN.search(line)
        return _parse_date(match.group(1)) if match else None
    return None


def _parse_date(raw_value):
    if not raw_value:
        return None
    value = raw_value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", value)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_order_number(lines):
    for line in lines:
        match = re.match(r"^ORDER\s+(?:NUMBER|NO)\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            return clean_optional_text(match.group(1))
    return None


def _collect_block(lines, kind):
    if kind == "DELIVER":
        header_pattern = re.compile(r"^DELIVER\s+TO\s*:?$", re.IGNORECASE)
    else:
        header_pattern = re.compile(
            r"^ON\s+FWD\s+TO(?:\s+CUSTOMER)?\s*:?$",
            re.IGNORECASE,
        )
    collecting = False
    block = []
    for line in lines:
        if header_pattern.match(line):
            collecting = True
            continue
        if not collecting:
            continue
        if _block_stops(line, kind):
            break
        block.append(line)
    return block


def _block_stops(line, kind):
    upper = str(line or "").upper()
    if kind == "DELIVER" and re.match(r"^ON\s+FWD\s+TO", upper):
        return True
    return bool(
        PRODUCT_PATTERN.match(str(line or ""))
        or re.search(r"\b\d+\s*(?:X\s*)?(?:PALLETS?|CARTONS?|LOOSE\s+BAGS?)\b", upper)
        or upper.startswith((
            "DELIVERY DOCKET", "DATED:", "EMAIL ", "EMAIL TO BOOK", "ORDER NUMBER",
            "ORDER NO", "STOCK:", "TOTAL:", "TIME SLOT:", "BOOKING #",
            "SCT REFERENCE", "INVOICE TO FOLLOW", "TRADING AS ",
        ))
    )


def _profile_from_block(block):
    if not block:
        return {}
    company_name = None
    phone = None
    address = None
    suburb = None
    postcode = None
    site = None
    store = None
    entry = None
    contact = None
    address_index = None

    for index, line in enumerate(block):
        upper = line.upper()
        phone_match = PHONE_PATTERN.match(line)
        if phone_match:
            phone = clean_optional_text(phone_match.group(1))
            continue
        if re.match(r"^(?:ATTN?|CONTACT)\s*:", line, re.IGNORECASE):
            contact = clean_optional_text(line.split(":", 1)[1])
            continue
        if upper.startswith("STORE "):
            store = clean_optional_text(line[6:])
            continue
        if upper.startswith("ENTRY "):
            entry = clean_optional_text(line[6:])
            continue
        if company_name is None:
            company_name = clean_optional_text(WINDOW_PATTERN.sub("", line).strip(" -"))
            continue
        if address is None and STREET_PATTERN.search(line) and not upper.startswith(("C/O ", "C/-")):
            address = clean_optional_text(line.upper())
            address_index = index
            continue
        if address is None and site is None and not upper.startswith(("C/O ", "C/-")):
            site = clean_optional_text(line.upper())

    if address_index is not None:
        for line in block[address_index + 1 :]:
            upper = line.upper()
            if PHONE_PATTERN.match(line) or upper.startswith(("ENTRY ", "STORE ")):
                continue
            match = SUBURB_POSTCODE_PATTERN.match(line)
            if match:
                suburb = clean_optional_text(_strip_state(match.group(1)).upper())
                postcode = match.group(2)
                break
            if re.fullmatch(r"\d{4}", line):
                postcode = line
                continue
            if not any(character.isdigit() for character in line) and not STREET_PATTERN.search(line):
                suburb = clean_optional_text(_strip_state(line).upper())
                break

    return {
        "company_name": company_name.upper() if company_name else None,
        "phone": phone,
        "delivery_address": address,
        "suburb": suburb,
        "postcode": postcode,
        "site": site,
        "store": store,
        "entry": entry,
        "contact": contact.upper() if contact else None,
        "raw": block,
    }


def _strip_state(value):
    return re.sub(r"\s+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)$", "", value.strip(), flags=re.IGNORECASE)


def _find_time_slot(lines):
    for line in lines:
        match = TIME_SLOT_PATTERN.match(line)
        if match:
            return clean_optional_text(match.group(1))
    return None


def _date_from_time_slot(time_slot):
    match = DATE_PATTERN.search(time_slot or "")
    parsed = _parse_date(match.group(1)) if match else None
    return parsed.isoformat() if parsed else None


def _find_delivery_window(deliver_block):
    for line in deliver_block:
        match = WINDOW_PATTERN.search(line)
        if match:
            return f"OPEN {match.group(1).upper().replace(' ', '')}-{match.group(2).upper().replace(' ', '')}"
    return None


def _times_from_schedule(time_slot, delivery_window):
    if time_slot:
        match = re.search(r"@\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)", time_slot, re.IGNORECASE)
        if match:
            return _parse_clock_time(match.group(1)), None
    if delivery_window:
        match = WINDOW_PATTERN.search(delivery_window)
        if match:
            return _parse_clock_time(match.group(1)), _parse_clock_time(match.group(2))
    return None, None


def _parse_clock_time(value):
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", value.strip(), re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _parse_products(lines):
    products = []
    warnings = []
    fractional = False
    for line in lines:
        match = PRODUCT_PATTERN.match(line)
        if not match:
            continue
        count = int(match.group(1))
        try:
            weight = Decimal(match.group(2))
        except InvalidOperation:
            continue
        actual = Decimal(count) * weight
        if actual != actual.to_integral_value():
            fractional = True
            warnings.append(
                f"Product actual quantity is fractional ({actual} KG) and cannot be imported safely."
            )
            quantity = float(actual)
        else:
            quantity = int(actual)
        weight_label = format(weight.normalize(), "f")
        if "." in weight_label:
            weight_label = weight_label.rstrip("0").rstrip(".")
        products.append({
            "product_code": None,
            "product_name": clean_optional_text(match.group(3).upper()),
            "quantity": quantity,
            "unit": "KG",
            "package_quantity": count,
            "package_unit": f"BAG{weight_label}",
        })
    return products, warnings, fractional


def _parse_load_quantity(lines, singular):
    total = 0
    pattern = re.compile(rf"\b(\d+)\s*(?:X\s*)?{singular}S?\b", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if match:
            total += int(match.group(1))
    return total


def _parse_loose_bags(lines):
    total = 0
    pattern = re.compile(r"\b(\d+)\s*(?:X\s*)?LOOSE\s+BAGS?\b", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if match:
            total += int(match.group(1))
    return total


def _build_note(
    lines,
    docket_number,
    docket_reference,
    deliver_profile,
    on_forward_profile,
    time_slot,
    delivery_window,
):
    note_lines = []
    if docket_number:
        note_lines.append(f"Delivery Docket: {docket_number}")
    if docket_reference:
        note_lines.append(f"Docket Reference: {docket_reference}")
    if deliver_profile.get("company_name"):
        note_lines.append(f"Deliver To: {deliver_profile['company_name']}")
    for raw in deliver_profile.get("raw", []):
        upper = raw.upper()
        if upper.startswith(("C/O ", "C/-")) and upper != deliver_profile.get("company_name"):
            note_lines.append(upper)
    if deliver_profile.get("site"):
        note_lines.append(f"Site: {deliver_profile['site']}")
    if deliver_profile.get("store"):
        note_lines.append(f"Store: {deliver_profile['store'].upper()}")
    if deliver_profile.get("entry"):
        note_lines.append(f"Entry: {deliver_profile['entry'].upper()}")
    if on_forward_profile.get("company_name"):
        note_lines.append(f"On Forward To: {on_forward_profile['company_name']}")
        address_parts = _forward_address_parts(on_forward_profile)
        if address_parts:
            note_lines.append(f"On Forward Address: {' / '.join(address_parts)}")
    if on_forward_profile.get("contact"):
        note_lines.append(f"Contact: {on_forward_profile['contact']}")
    if on_forward_profile.get("phone"):
        note_lines.append(f"Phone: {on_forward_profile['phone']}")

    operational_lines = _before_supplier_footer(lines)
    for line in operational_lines:
        for email in EMAIL_PATTERN.findall(line):
            note_lines.append(f"Booking Email: {email.lower()}")
        sct_match = re.match(r"^SCT\s+REFERENCE\s*#?\s*(.+)$", line, re.IGNORECASE)
        if sct_match:
            note_lines.append(f"SCT Reference: {sct_match.group(1).strip()}")
        booking_match = re.match(r"^BOOKING\s*#\s*(.+)$", line, re.IGNORECASE)
        if booking_match:
            note_lines.append(f"Booking #: {booking_match.group(1).strip()}")
    if delivery_window:
        note_lines.append(f"Delivery Window: {delivery_window}")
    if time_slot:
        note_lines.append(f"Time Slot: {time_slot.upper()}")
    return "\n".join(dict.fromkeys(note_lines)) or None


def _forward_address_parts(profile):
    parts = []
    company = profile.get("company_name")
    for line in profile.get("raw", []):
        upper = line.upper()
        if upper == company or PHONE_PATTERN.match(line) or re.match(r"^(?:ATTN?|CONTACT)\s*:", line, re.IGNORECASE):
            continue
        parts.append(upper)
    return parts


def _before_supplier_footer(lines):
    result = []
    for line in lines:
        upper = line.upper()
        if upper.startswith(("INVOICE TO FOLLOW", "TRADING AS ")):
            break
        result.append(line)
    return result


def _resolve_import_date(import_date):
    if import_date is None:
        return current_melbourne_business_date()
    if isinstance(import_date, datetime):
        return import_date.date()
    if isinstance(import_date, date):
        return import_date
    return date.fromisoformat(str(import_date))


def _row_id(source_filename, docket_number):
    identity = f"{source_filename}|{docket_number or ''}"
    return f"DOCKET-{sha1(identity.encode('utf-8')).hexdigest()[:12]}"
