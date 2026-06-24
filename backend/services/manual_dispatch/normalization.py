from datetime import date
import re

from backend.schemas import ProductDetailLine


ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_PRODUCT_DETAIL_UNITS = {"PALLETS", "BAGS", "CARTONS"}


def clean_optional_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_required_text(value, field_name):
    text = clean_optional_text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def clean_required_iso_date(value, field_name):
    text = clean_required_text(value, field_name)
    if not ISO_DATE_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must use YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid YYYY-MM-DD date") from error
    return text


def clean_optional_iso_date(value, field_name):
    text = clean_optional_text(value)
    if text is None:
        return None
    return clean_required_iso_date(text, field_name)


def quantity_or_default(value, field_name):
    if value in (None, ""):
        return 0
    try:
        quantity = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a whole number") from error
    if quantity < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return quantity


def load_unit_for_quantities(pallet_quantity, loose_bags_quantity):
    if pallet_quantity > 0 and loose_bags_quantity > 0:
        return "MIXED"
    if pallet_quantity > 0:
        return "PALLETS"
    if loose_bags_quantity > 0:
        return "BAGS"
    return None


def normalize_product_detail_lines(product_lines, load_unit, field_name="product_lines"):
    if product_lines in (None, ""):
        return []
    if not isinstance(product_lines, list):
        raise ValueError(f"{field_name} must be a list")

    normalized_lines = []
    for index, line in enumerate(product_lines, start=1):
        if not isinstance(line, dict):
            raise ValueError(f"{field_name} item {index} must be an object")

        product_name = clean_required_text(
            line.get("product_name") or line.get("description"),
            f"{field_name} item {index} product_name",
        )
        quantity = quantity_or_default(
            line.get("quantity"),
            f"{field_name} item {index} quantity",
        )
        if quantity <= 0:
            raise ValueError(f"{field_name} item {index} quantity must be greater than 0")

        unit = clean_required_text(
            line.get("unit"),
            f"{field_name} item {index} unit",
        ).upper()
        if unit not in VALID_PRODUCT_DETAIL_UNITS:
            raise ValueError(
                f"{field_name} item {index} unit must be PALLETS, BAGS, or CARTONS"
            )

        normalized_lines.append(
            ProductDetailLine(
                product_name=product_name,
                quantity=quantity,
                unit=unit,
            )
        )

    if any(line.unit == "CARTONS" for line in normalized_lines) and load_unit not in {
        "PALLETS",
        "MIXED",
    }:
        raise ValueError("Product detail CARTONS requires a pallet quantity.")
    if normalized_lines and not load_unit:
        raise ValueError("Product detail unit must align with the Order pallet or bag quantity")
    allowed_units = {
        "PALLETS": {"PALLETS", "CARTONS"},
        "BAGS": {"BAGS"},
        "MIXED": VALID_PRODUCT_DETAIL_UNITS,
    }.get(load_unit, set())
    if (
        normalized_lines
        and any(line.unit not in allowed_units for line in normalized_lines)
    ):
        raise ValueError("Product detail unit must align with the Order pallet or bag quantity")
    return normalized_lines


def bool_or_default(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
