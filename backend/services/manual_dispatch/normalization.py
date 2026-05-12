from datetime import date
import re


ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def bool_or_default(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
