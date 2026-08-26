from datetime import date, datetime, timedelta
import os
import re

from backend.services.manual_dispatch.logbook_file_service import MELBOURNE_TIMEZONE


TEST_MODE_ENV = "MANUAL_DISPATCH_TEST_MODE"
TEST_BUSINESS_DATE_ENV = "MANUAL_DISPATCH_TEST_BUSINESS_DATE"


def current_melbourne_business_date():
    if _is_env_flag_enabled(os.environ.get(TEST_MODE_ENV)):
        fixed_date = os.environ.get(TEST_BUSINESS_DATE_ENV)
        if fixed_date:
            return date.fromisoformat(fixed_date)
    return datetime.now(MELBOURNE_TIMEZONE).date()


def next_delivery_business_date(import_date=None):
    return next_weekday_after(_resolve_import_date(import_date))


def next_weekday_after(value):
    candidate = _resolve_import_date(value) + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _resolve_import_date(value):
    if value is None:
        return current_melbourne_business_date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
        if match:
            day, month, year = (int(part) for part in match.groups())
            if year < 100:
                year += 2000
            try:
                return date(year, month, day)
            except ValueError:
                pass
    raise ValueError("import_date must be a valid date")


def _is_env_flag_enabled(raw_value):
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}
