from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from io import BytesIO
import re

from backend.schemas import DeliveryDocketDocxPreviewItem
from backend.services.manual_dispatch.delivery_import_date import (
    current_melbourne_business_date,
    next_delivery_business_date,
)
from backend.services.manual_dispatch.normalization import (
    clean_optional_text,
    normalize_product_detail_lines,
    quantity_or_default,
)


DOCKET_HEADER_PATTERN = re.compile(r"^DELIVERY\s+DOCKET\s*:\s*(.+)$", re.IGNORECASE)
DATE_PATTERN = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})")
PRODUCT_PATTERN = re.compile(
    r"^(\d+)\s*[Xx]\s*(\d+(?:\.\d+)?)\s*KGS?\s+(.+?)\s*$",
    re.IGNORECASE,
)
TRAILING_WEIGHT_PRODUCT_PATTERN = re.compile(
    r"^(\d+)\s*[Xx]\s+(.+?)\s+(\d+(?:\.\d+)?)\s*KGS?\s*$",
    re.IGNORECASE,
)
PALLET_BREAKDOWN_HEADER_PATTERN = re.compile(
    r"^PURCHASE\s+ORDER\s+NUMBERS\s*&\s*PALLET\s+BREAKDOWN\s*:?$",
    re.IGNORECASE,
)
PALLET_BREAKDOWN_PATTERN = re.compile(
    r"^(\d+)\s+(\d+)\s*PALLETS?\s+(.+?)\s+"
    r"(\d+(?:\.\d+)?)\s*KGS?\s+(\d+)\s*BAGS?\s*$",
    re.IGNORECASE,
)
STREET_PATTERN = re.compile(
    r"\b(?:ROAD|RD|STREET|ST|COURT|CT|AVENUE|AVE|DRIVE|DR|DV|HIGHWAY|HWY|"
    r"LANE|LN|BOULEVARD|BLVD|CRESCENT|CRES|PLACE|PL|WAY)\b",
    re.IGNORECASE,
)
SUBURB_POSTCODE_PATTERN = re.compile(
    r"^(.+?)(?:\s+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT))?\s+(\d{4})$",
    re.IGNORECASE,
)
SUBURB_STATE_PATTERN = re.compile(
    r"^(.+?)\s+(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)$",
    re.IGNORECASE,
)
AU_PHONE_NUMBER = (
    r"(?:\+61[ -]?(?:4\d{2}[ -]?\d{3}[ -]?\d{3}|[2378][ -]?[2-9]\d{3}[ -]?\d{4})|"
    r"04\d{2}[ -]?\d{3}[ -]?\d{3}|"
    r"(?:0[2378]|\(0[2378]\))[ -]?[2-9]\d{3}[ -]?\d{4}|[2-9]\d{3}[ -]\d{4})"
)
INLINE_PHONE_PATTERN = re.compile(
    rf"(?<![A-Z0-9])(?:PHONE|TELEPHONE|MOBILE|TEL|PH|M)\s*[:;]\s*({AU_PHONE_NUMBER})(?!\d)",
    re.IGNORECASE,
)
UNLABELED_INLINE_PHONE_PATTERN = re.compile(
    rf"(?<!\S)({AU_PHONE_NUMBER})(?!\d)"
)
PROFILE_INSTRUCTION_PATTERN = re.compile(
    r"^(?:ENTER\b|ENTRY\b|RING\s+TO\s+ADVISE\b|DROP\s+OFF\s+TO\b|"
    r"DRIVER\s+MUST\b|GO\s+TO\b|MUST\b|PLEASE\b|CALL\b|VIA\b|"
    r"OPEN\b|\d+\s*MINS?\s+PRIOR\s+DELIVERY\b)",
    re.IGNORECASE,
)
INLINE_ANNOTATION_PATTERN = re.compile(r"\*{2,}(.*?)(?:\*{2,}|$)")
PARENTHESIZED_ENTRY_PATTERN = re.compile(r"\(((?:ENTRY|ENTER)\b[^()]*)\)", re.IGNORECASE)
BOOKING_REFERENCE_PATTERN = re.compile(r"\bBOOKING\s*#\s*(\S+)", re.IGNORECASE)
DELIVER_BLOCK_HEADER_PATTERN = re.compile(
    r"^(?:DELIVER(?:Y)?|DROP\s+OFF)\s+TO\s*:?$",
    re.IGNORECASE,
)
ON_FORWARD_BLOCK_HEADER_PATTERN = re.compile(
    r"^ON\s+(?:FWD|FORWARD)\s+TO(?:\s+CUSTOMER)?\s*(?::.*)?$",
    re.IGNORECASE,
)
CONTEXTUAL_TO_PATTERN = re.compile(r"^TO\s*:\s*(.*)$", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WINDOW_PATTERN = re.compile(
    r"\b(?:OPEN\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))"
    r"(?:\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)))?|"
    r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*-\s*"
    r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM)))\b",
    re.IGNORECASE,
)
TIME_SLOT_PATTERN = re.compile(
    r"^(?:[A-Z][A-Z0-9 &./'-]*\s+)?TIME\s+SLOT\s*:\s*(.+)$", re.IGNORECASE
)

DELIVERY_DOCKET_REQUIRED_WARNINGS = (
    ("docket_number", "Delivery Docket number was not found."),
    ("company_name", "Customer company was not found."),
    ("delivery_address", "Deliver To street address was not found."),
    ("suburb", "Deliver To suburb was not found."),
    ("delivery_date", "Delivery date was not resolved."),
)
DELIVERY_DOCKET_LOAD_WARNING = "No pallet, loose bag, or carton load was found."
DELIVERY_DOCKET_INVALID_LOAD_WARNING = (
    "Delivery load quantities must be whole non-negative numbers."
)
DELIVERY_DOCKET_DUPLICATE_WARNING = "Duplicate invoice number already exists."
DELIVERY_DOCKET_FRACTIONAL_PRODUCT_WARNING_PREFIX = (
    "Product actual quantity is fractional ("
)
DELIVERY_DOCKET_INVALID_PRODUCT_WARNING = (
    "Product line data is invalid and must be corrected before import."
)


@dataclass(frozen=True)
class DeliveryDocketValidationResult:
    warnings: list[str]
    blocking_warnings: list[str]
    importable: bool
    selected: bool


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
    lines = _before_supplier_footer(_normalize_lines(text))
    docket_number, docket_reference = _parse_docket_header(lines)
    invoice_match = re.fullmatch(r"(?:INVOICE\s*#\s*)?(\d{6})", docket_reference or "", re.IGNORECASE)
    invoice_number = invoice_match.group(1) if invoice_match else None
    invoice_date = _parse_labeled_date(lines, "DATED")
    order_no = _parse_order_number(lines)
    sections = _delivery_sections(lines)
    deliver_block = _collect_block(lines, "PHYSICAL_DELIVERY", sections)
    on_forward_block = _collect_block(lines, "ON_FORWARD", sections)
    deliver_profile = _profile_from_block(deliver_block)
    on_forward_profile = _profile_from_block(on_forward_block)
    has_final_section = any(kind in {"ON_FORWARD", "AMBIGUOUS_FORWARD"} for kind in sections.values())
    delivery_mode = "ON_FORWARD" if has_final_section else "DIRECT"
    company_name = (
        on_forward_profile.get("company_name")
        if has_final_section else deliver_profile.get("company_name")
    )
    phone = on_forward_profile.get("phone") or deliver_profile.get("phone")

    time_slot = _find_time_slot(lines)
    delivery_date = next_delivery_business_date(import_date).isoformat()
    delivery_window = _find_delivery_window(deliver_block)
    start_time, end_time = _times_from_schedule(time_slot, delivery_window)

    products, product_warnings, _fractional_product = _parse_products(lines)
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
    item = DeliveryDocketDocxPreviewItem(
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
        importable=True,
        selected=True,
    )
    return apply_delivery_docket_validation(item)


def validate_delivery_docket_import_row(row):
    product_warnings = _delivery_docket_product_warnings(
        _delivery_docket_row_value(row, "product_lines", [])
    )
    required_warnings = [
        warning
        for field_name, warning in DELIVERY_DOCKET_REQUIRED_WARNINGS
        if not clean_optional_text(_delivery_docket_row_value(row, field_name))
    ]
    load_warnings = _delivery_docket_load_warnings(row)
    duplicate_warnings = (
        [DELIVERY_DOCKET_DUPLICATE_WARNING]
        if bool(_delivery_docket_row_value(row, "is_duplicate", False))
        else []
    )
    blocking_warnings = list(dict.fromkeys([
        *product_warnings,
        *required_warnings,
        *load_warnings,
        *duplicate_warnings,
    ]))
    unmanaged_warnings = [
        warning
        for warning in list(_delivery_docket_row_value(row, "warnings", []) or [])
        if not _is_delivery_docket_validation_warning(warning)
    ]
    warnings = list(dict.fromkeys([
        *product_warnings,
        *unmanaged_warnings,
        *required_warnings,
        *load_warnings,
        *duplicate_warnings,
    ]))
    importable = not blocking_warnings
    return DeliveryDocketValidationResult(
        warnings=warnings,
        blocking_warnings=blocking_warnings,
        importable=importable,
        selected=bool(_delivery_docket_row_value(row, "selected", False)) and importable,
    )


def apply_delivery_docket_validation(item):
    validation = validate_delivery_docket_import_row(item)
    item.warnings = validation.warnings
    item.importable = validation.importable
    item.selected = validation.selected
    return item


def with_duplicate_warning(item):
    duplicate = replace(
        item,
        is_duplicate=True,
    )
    return apply_delivery_docket_validation(duplicate)


def _delivery_docket_row_value(row, field_name, default=None):
    if isinstance(row, dict):
        return row.get(field_name, default)
    return getattr(row, field_name, default)


def _delivery_docket_load_warnings(row):
    quantities = []
    try:
        for field_name in (
            "pallet_quantity",
            "loose_bags_quantity",
            "carton_quantity",
        ):
            quantities.append(quantity_or_default(
                _delivery_docket_row_value(row, field_name),
                field_name,
            ))
    except ValueError:
        return [DELIVERY_DOCKET_INVALID_LOAD_WARNING]
    if not any(quantity > 0 for quantity in quantities):
        return [DELIVERY_DOCKET_LOAD_WARNING]
    return []


def _delivery_docket_product_warnings(product_lines):
    fractional_warnings = []
    if isinstance(product_lines, list):
        for line in product_lines:
            if not isinstance(line, dict):
                continue
            quantity = _decimal_or_none(line.get("quantity"))
            if quantity is None or quantity == quantity.to_integral_value():
                continue
            quantity_label = format(quantity.normalize(), "f")
            fractional_warnings.append(
                f"{DELIVERY_DOCKET_FRACTIONAL_PRODUCT_WARNING_PREFIX}"
                f"{quantity_label} KG) and cannot be imported safely."
            )
    try:
        normalize_product_detail_lines(product_lines)
    except ValueError as error:
        if not (
            fractional_warnings
            and "quantity must be a whole number" in str(error)
        ):
            return [*fractional_warnings, DELIVERY_DOCKET_INVALID_PRODUCT_WARNING]
    return fractional_warnings


def _decimal_or_none(value):
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return quantity if quantity.is_finite() else None


def _is_delivery_docket_validation_warning(warning):
    text = str(warning or "")
    return bool(
        text in {
            *(item[1] for item in DELIVERY_DOCKET_REQUIRED_WARNINGS),
            DELIVERY_DOCKET_LOAD_WARNING,
            DELIVERY_DOCKET_INVALID_LOAD_WARNING,
            DELIVERY_DOCKET_DUPLICATE_WARNING,
            DELIVERY_DOCKET_INVALID_PRODUCT_WARNING,
        }
        or text.startswith(DELIVERY_DOCKET_FRACTIONAL_PRODUCT_WARNING_PREFIX)
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
    if reference.upper().startswith(("NEWAY", "NEWWAY")) and index + 1 < len(lines):
        continuation = lines[index + 1]
        if not _starts_new_section(continuation):
            reference = f"{reference} {continuation}".strip()
    return clean_optional_text(docket_number), clean_optional_text(reference)


def _starts_new_section(line):
    upper = str(line or "").upper()
    return bool(
        _block_heading_kind(line)
        or CONTEXTUAL_TO_PATTERN.match(str(line or ""))
        or PALLET_BREAKDOWN_HEADER_PATTERN.match(str(line or ""))
        or TIME_SLOT_PATTERN.match(str(line or ""))
        or _is_supplier_footer(line)
        or DOCKET_HEADER_PATTERN.match(str(line or ""))
        or upper.startswith((
            "DATED", "EMAIL", "ORDER", "STOCK",
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
    purchase_orders = {match.group(1) for match in _pallet_breakdown_rows(lines).values()}
    if len(purchase_orders) == 1:
        return purchase_orders.pop()
    return None


def _delivery_sections(lines):
    sections = {
        index: kind for index, line in enumerate(lines)
        if (kind := _block_heading_kind(line))
    }
    for index, line in enumerate(lines):
        match = CONTEXTUAL_TO_PATTERN.match(line)
        if not match or not any(
            position < index and kind == "PHYSICAL_DELIVERY"
            for position, kind in sections.items()
        ):
            continue
        company, _phone = _profile_line(match.group(1))
        if not company or SUBURB_POSTCODE_PATTERN.match(company) or SUBURB_STATE_PATTERN.match(company):
            sections[index] = "AMBIGUOUS_FORWARD"
            continue
        if not _is_company_line(company):
            continue
        physical = _profile_from_block(_collect_block(lines[:index], "PHYSICAL_DELIVERY", sections))
        following = []
        for candidate in lines[index + 1:]:
            if _block_stops(candidate, "ON_FORWARD"):
                break
            following.append(candidate)
        final = _profile_from_block([company, *following])
        resolved = all(
            profile.get(field)
            for profile in (physical, final)
            for field in ("company_name", "delivery_address", "suburb")
        )
        sections[index] = "ON_FORWARD" if resolved else "AMBIGUOUS_FORWARD"
    return sections


def _collect_block(lines, kind, sections):
    collecting = False
    block = []
    for index, line in enumerate(lines):
        heading_kind = sections.get(index)
        if heading_kind == kind:
            collecting = True
            contextual = CONTEXTUAL_TO_PATTERN.match(line)
            if contextual:
                block.append(contextual.group(1))
            continue
        if not collecting:
            continue
        if heading_kind or _block_stops(line, kind):
            break
        block.append(line)
    return block


def _block_stops(line, kind):
    upper = str(line or "").upper()
    heading_kind = _block_heading_kind(line)
    if heading_kind and heading_kind != kind:
        return True
    return bool(
        PRODUCT_PATTERN.match(str(line or ""))
        or TRAILING_WEIGHT_PRODUCT_PATTERN.match(str(line or ""))
        or PALLET_BREAKDOWN_HEADER_PATTERN.match(str(line or ""))
        or CONTEXTUAL_TO_PATTERN.match(str(line or ""))
        or TIME_SLOT_PATTERN.match(str(line or ""))
        or _is_supplier_footer(line)
        or re.search(r"\b\d+\s*(?:X\s*)?(?:PALLETS?|CARTONS?|LOOSE\s+BAGS?)\b", upper)
        or upper.startswith((
            "DELIVERY DOCKET", "DATED:", "EMAIL ", "EMAIL TO BOOK", "ORDER NUMBER",
            "ORDER NO", "STOCK:", "TOTAL:", "TIME SLOT:", "BOOKING #",
            "SCT REFERENCE", "INVOICE TO FOLLOW", "TRADING AS ",
        ))
    )


def _block_heading_kind(line):
    text = str(line or "").strip()
    if DELIVER_BLOCK_HEADER_PATTERN.match(text):
        return "PHYSICAL_DELIVERY"
    if ON_FORWARD_BLOCK_HEADER_PATTERN.match(text):
        return "ON_FORWARD"
    return None


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

    for index, raw_line in enumerate(block):
        line, inline_phone = _profile_line(raw_line)
        inline_contact = _contact_from_line(raw_line)
        if inline_contact:
            contact = contact or inline_contact
            phone = phone or inline_phone
            continue
        if line and _is_instruction_line(line):
            if line.upper().startswith("ENTRY "):
                entry = clean_optional_text(line[6:])
            continue
        if inline_phone and phone is None:
            phone = inline_phone
        if not line:
            continue
        upper = line.upper()
        if re.match(r"^(?:ATTN?|CONTACT)\s*:", line, re.IGNORECASE):
            continue
        if upper.startswith("STORE "):
            store = clean_optional_text(line[6:])
            continue
        if address is None and _is_street_line(line):
            address = clean_optional_text(line.upper())
            address_index = index
            continue
        if company_name is None:
            candidate = clean_optional_text(WINDOW_PATTERN.sub("", line).strip(" -"))
            if address_index is None and _is_company_line(candidate):
                company_name = candidate
            continue
        if address is None and site is None and not upper.startswith(("C/O ", "C/-")):
            site = clean_optional_text(line.upper())

    if address_index is not None:
        for raw_line in block[address_index + 1 :]:
            line, _inline_phone = _profile_line(raw_line)
            if not line:
                continue
            upper = line.upper()
            if (
                _is_instruction_line(line) or upper.startswith("STORE ")
                or _contact_from_line(raw_line)
                or re.match(r"^(?:ATTN?|CONTACT)\s*:", line, re.IGNORECASE)
            ):
                continue
            if re.fullmatch(r"\d{4}", line):
                postcode = line
                continue
            locality, local_postcode = _parse_locality(line)
            if locality:
                suburb, postcode = locality, local_postcode or postcode
                break

    if address and suburb is None:
        address, suburb, inline_postcode = _split_inline_address(address)
        postcode = postcode or inline_postcode

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


def _profile_line(value):
    line = INLINE_ANNOTATION_PATTERN.sub(" ", str(value or ""))
    line = PARENTHESIZED_ENTRY_PATTERN.sub(" ", line)
    line = BOOKING_REFERENCE_PATTERN.sub(" ", line)
    line = re.sub(r"\s+", " ", line).strip()
    phone_match = INLINE_PHONE_PATTERN.search(line)
    if not phone_match:
        phone_match = UNLABELED_INLINE_PHONE_PATTERN.search(line)
        prefix = line[:phone_match.start()].strip() if phone_match else ""
        if not phone_match or not (
            not prefix or _is_suburb_text(prefix)
            or re.match(r"^(?:ATTN?\s*:|CONTACT\s*:|CALL\s+)", prefix, re.IGNORECASE)
        ):
            return clean_optional_text(line), None
    suffix = line[phone_match.end():].strip()
    if suffix and not _is_instruction_line(suffix):
        return clean_optional_text(line), None
    content = clean_optional_text(line[:phone_match.start()].rstrip(" ,;-/"))
    phone = clean_optional_text(phone_match.group(1))
    return content, phone


def _contact_from_line(value):
    line, phone = _profile_line(value)
    if not line:
        return None
    match = re.match(r"^(?:ATTN?|CONTACT)\s*:\s*(.+)$", line, re.IGNORECASE)
    if not match and phone:
        match = re.match(r"^CALL\s+(.+)$", line, re.IGNORECASE)
        if not match and re.search(r"\bM\s*[:;]", str(value), re.IGNORECASE):
            match = re.fullmatch(r"([A-Z][A-Z .'-]*)", line, re.IGNORECASE)
    name = match.group(1).strip() if match else ""
    if re.fullmatch(r"[A-Z][A-Z .'-]*", name, re.IGNORECASE):
        return name.upper()
    return None


def _is_street_line(line):
    text = str(line or "")
    return bool(
        STREET_PATTERN.search(text) and re.search(r"\d", text)
        and not text.upper().startswith(("C/O ", "C/-"))
        and not _is_instruction_line(text)
    )


def _is_company_line(line):
    text = str(line or "")
    return bool(
        re.search(r"[A-Z]", text, re.IGNORECASE)
        and not _is_instruction_line(text) and not _is_street_line(text)
        and not EMAIL_PATTERN.search(text) and ":" not in text
        and not _block_heading_kind(text)
        and not SUBURB_POSTCODE_PATTERN.match(text)
        and not SUBURB_STATE_PATTERN.match(text)
    )


def _parse_locality(line):
    match = SUBURB_POSTCODE_PATTERN.match(line)
    leading_postcode = re.fullmatch(r"(\d{4})\s+(.+)", line)
    locality = _strip_state(
        leading_postcode.group(2) if leading_postcode else match.group(1) if match else line
    )
    if not _is_suburb_text(locality) or STREET_PATTERN.search(locality):
        return None, None
    postcode = leading_postcode.group(1) if leading_postcode else match.group(2) if match else None
    return locality.upper(), postcode


def _is_instruction_line(line):
    return bool(PROFILE_INSTRUCTION_PATTERN.match(str(line or "").lstrip("* ")))


def _is_suburb_text(value):
    text = str(value or "").strip().upper()
    return bool(
        re.fullmatch(r"[A-Z][A-Z '\-]*", text)
        and not _is_instruction_line(text)
        and text not in {
            "VIC", "NSW", "QLD", "SA", "WA", "TAS", "NT", "ACT",
            "NORTH", "SOUTH", "EAST", "WEST", "NTH", "STH", "N", "S", "E", "W",
        }
    )


def _split_inline_address(address):
    matches = list(STREET_PATTERN.finditer(address))
    if not matches or _is_instruction_line(address):
        return address, None, None
    street = address[:matches[-1].end()].strip()
    if not any(character.isdigit() for character in street):
        return address, None, None
    tail = address[matches[-1].end():].strip(" ,")
    suburb, postcode = _parse_locality(tail)
    if not suburb:
        return address, None, None
    return street, suburb, postcode


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
            start_time, end_time = _window_match_times(match)
            normalized = f"OPEN {start_time.upper().replace(' ', '')}"
            if end_time:
                normalized += f"-{end_time.upper().replace(' ', '')}"
            return normalized
    return None


def _times_from_schedule(time_slot, delivery_window):
    if time_slot:
        match = re.search(
            r"@\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)"
            r"(?:\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?))?\s*$",
            time_slot, re.IGNORECASE,
        )
        if match:
            start, end = (part.strip() if part else None for part in match.groups())
            if end and not re.search(r"AM|PM", start, re.IGNORECASE):
                meridiem = re.search(r"AM|PM", end, re.IGNORECASE)
                if meridiem:
                    start += meridiem.group(0)
            return _parse_clock_time(start), _parse_clock_time(end) if end else None
    if delivery_window:
        match = WINDOW_PATTERN.search(delivery_window)
        if match:
            start_time, end_time = _window_match_times(match)
            return (
                _parse_clock_time(start_time),
                _parse_clock_time(end_time) if end_time else None,
            )
    return None, None


def _window_match_times(match):
    return match.group(1) or match.group(3), match.group(2) or match.group(4)


def _parse_clock_time(value):
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", value.strip(), re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").upper()
    if minute > 59 or (meridiem and not 1 <= hour <= 12) or (not meridiem and hour > 23):
        return None
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _parse_products(lines):
    products = []
    warnings = []
    fractional = False
    breakdown = _pallet_breakdown_rows(lines)
    for index, line in enumerate(lines):
        match = PRODUCT_PATTERN.match(line)
        trailing = TRAILING_WEIGHT_PRODUCT_PATTERN.match(line) if not match else None
        if match:
            count, weight_text, description = match.groups()
        elif trailing:
            count, description, weight_text = trailing.groups()
        elif index in breakdown:
            _po, _pallets, description, weight_text, count = breakdown[index].groups()
        else:
            continue
        count = int(count)
        try:
            weight = Decimal(weight_text)
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
            "product_name": clean_optional_text(description.upper()),
            "quantity": quantity,
            "unit": "KG",
            "package_quantity": count,
            "package_unit": f"BAG{weight_label}",
        })
    return products, warnings, fractional


def _pallet_breakdown_rows(lines):
    rows = {}
    collecting = False
    for index, line in enumerate(lines):
        if PALLET_BREAKDOWN_HEADER_PATTERN.match(line):
            collecting = True
            continue
        if not collecting:
            continue
        match = PALLET_BREAKDOWN_PATTERN.match(line)
        if match:
            rows[index] = match
        elif _starts_new_section(line) or PRODUCT_PATTERN.match(line) or TRAILING_WEIGHT_PRODUCT_PATTERN.match(line):
            collecting = False
    return rows


def _parse_load_quantity(lines, singular):
    pattern = re.compile(rf"^(\d+)\s*(?:X\s*)?{singular}S?\s*$", re.IGNORECASE)
    explicit_totals = []
    standalone = []
    for index, line in enumerate(lines):
        total_line = re.match(r"^TOTAL\s*:\s*(.*)$", line, re.IGNORECASE)
        match = pattern.match(total_line.group(1) if total_line else line)
        if match:
            is_total = total_line or (index > 0 and re.fullmatch(r"TOTAL\s*:", lines[index - 1], re.IGNORECASE))
            (explicit_totals if is_total else standalone).append(int(match.group(1)))
    # Totals supersede summaries; a standalone summary supersedes breakdown rows.
    if explicit_totals:
        return explicit_totals[0]
    if standalone:
        return sum(standalone)
    if singular == "PALLET":
        return sum(int(match.group(2)) for match in _pallet_breakdown_rows(lines).values())
    return 0


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
    if deliver_profile.get("delivery_address"):
        address_parts = [
            deliver_profile[key]
            for key in ("delivery_address", "suburb", "postcode")
            if deliver_profile.get(key)
        ]
        note_lines.append(f"Deliver To Address: {' / '.join(address_parts)}")
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
    contact = on_forward_profile.get("contact") or deliver_profile.get("contact")
    if contact:
        note_lines.append(f"Contact: {contact}")
    if on_forward_profile.get("phone"):
        note_lines.append(f"Phone: {on_forward_profile['phone']}")

    operational_lines = _before_supplier_footer(lines)
    for line in operational_lines:
        for entry_instruction in PARENTHESIZED_ENTRY_PATTERN.findall(line):
            note_lines.append(entry_instruction.upper())
        if _block_heading_kind(line) == "ON_FORWARD" and ":" in line:
            annotation = clean_optional_text(line.split(":", 1)[1])
            if annotation:
                note_lines.append(f"On Forward Note: {annotation.upper()}")
        else:
            for annotation in INLINE_ANNOTATION_PATTERN.findall(line):
                if annotation.strip():
                    note_lines.append(f"Annotation: {annotation.strip().upper()}")
        if _is_instruction_line(line):
            if not (
                line.upper().startswith("ENTRY ")
                and line[6:].upper() == str(deliver_profile.get("entry") or "").upper()
            ):
                note_lines.append(line.upper())
        for email in EMAIL_PATTERN.findall(line):
            note_lines.append(f"Booking Email: {email.lower()}")
        sct_match = re.match(r"^SCT\s+REFERENCE\s*#?\s*(.+)$", line, re.IGNORECASE)
        if sct_match:
            note_lines.append(f"SCT Reference: {sct_match.group(1).strip()}")
        booking_match = BOOKING_REFERENCE_PATTERN.search(line)
        if booking_match:
            note_lines.append(f"Booking #: {booking_match.group(1).strip()}")
    purchase_orders = list(dict.fromkeys(
        match.group(1) for match in _pallet_breakdown_rows(lines).values()
    ))
    if purchase_orders:
        note_lines.append(f"Purchase Orders: {', '.join(purchase_orders)}")
    if delivery_window:
        note_lines.append(f"Delivery Window: {delivery_window}")
    if time_slot:
        note_lines.append(f"Time Slot: {time_slot.upper()}")
    return "\n".join(dict.fromkeys(note_lines)) or None


def _forward_address_parts(profile):
    parts = []
    company = profile.get("company_name")
    suburb = profile.get("suburb")
    for raw_line in profile.get("raw", []):
        line, inline_phone = _profile_line(raw_line)
        if not line or _is_instruction_line(line) or _contact_from_line(raw_line):
            continue
        upper = line.upper()
        if upper == company or re.match(r"^(?:ATTN?|CONTACT)\s*:", line, re.IGNORECASE):
            continue
        if inline_phone and not (
            upper == suburb
            or _strip_state(upper) == suburb
            or SUBURB_POSTCODE_PATTERN.match(line)
            or SUBURB_STATE_PATTERN.match(line)
        ):
            continue
        parts.append(upper)
    return parts


def _before_supplier_footer(lines):
    result = []
    for line in lines:
        if _is_supplier_footer(line):
            break
        result.append(line)
    return result


def _is_supplier_footer(line):
    text = str(line or "")
    return bool(
        re.match(r"^(?:INVOICE\s+TO\s+FOLLOW|TRADING\s+AS)\b", text, re.IGNORECASE)
        or (
            re.match(r"^(?:MCC\b|SMITHS\s+RAGS\b|MELBOURNE\s+CLEANING\s+CLOTHS\b)", text, re.IGNORECASE)
            and INLINE_PHONE_PATTERN.search(text)
        )
    )


def _row_id(source_filename, docket_number):
    identity = f"{source_filename}|{docket_number or ''}"
    return f"DOCKET-{sha1(identity.encode('utf-8')).hexdigest()[:12]}"
