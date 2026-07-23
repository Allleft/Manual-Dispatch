from datetime import date
import re

from backend.schemas import ProductDetailLine


ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRODUCT_CODE_MAX_LENGTH = 40
PRODUCT_UNIT_MAX_LENGTH = 20
PRODUCT_UNIT_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9./_-]*$")
SQLITE_INTEGER_MAX = 2**63 - 1


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
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number")
    try:
        quantity = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{field_name} must be a whole number") from error
    if not isinstance(value, str) and quantity != value:
        raise ValueError(f"{field_name} must be a whole number")
    if quantity < 0:
        raise ValueError(f"{field_name} cannot be negative")
    if quantity > SQLITE_INTEGER_MAX:
        raise ValueError(f"{field_name} cannot exceed {SQLITE_INTEGER_MAX}")
    return quantity


def load_unit_for_quantities(pallet_quantity, loose_bags_quantity):
    if pallet_quantity > 0 and loose_bags_quantity > 0:
        return "MIXED"
    if pallet_quantity > 0:
        return "PALLETS"
    if loose_bags_quantity > 0:
        return "BAGS"
    return None


def normalize_product_detail_lines(product_lines, load_unit=None, field_name="product_lines"):
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

        unit = _bounded_code(
            line.get("unit"),
            f"{field_name} item {index} unit",
            PRODUCT_UNIT_MAX_LENGTH,
            required=True,
        )
        product_code = _bounded_code(
            line.get("product_code"),
            f"{field_name} item {index} product_code",
            PRODUCT_CODE_MAX_LENGTH,
        )
        package_quantity = _optional_quantity(
            line.get("package_quantity"),
            f"{field_name} item {index} package_quantity",
        )
        package_unit = _bounded_code(
            line.get("package_unit"),
            f"{field_name} item {index} package_unit",
            PRODUCT_UNIT_MAX_LENGTH,
        )
        if (package_quantity is None) != (package_unit is None):
            raise ValueError(
                f"{field_name} item {index} package_quantity and package_unit must be provided together"
            )

        normalized_lines.append(
            ProductDetailLine(
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                product_code=product_code,
                package_quantity=package_quantity,
                package_unit=package_unit,
            )
        )

    return normalized_lines


def _bounded_code(value, field_name, max_length, required=False):
    text = clean_optional_text(value)
    if text is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    normalized = text.upper()
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    if not PRODUCT_UNIT_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} contains unsupported characters")
    return normalized


def _optional_quantity(value, field_name):
    if value in (None, ""):
        return None
    return quantity_or_default(value, field_name)


def bool_or_default(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
