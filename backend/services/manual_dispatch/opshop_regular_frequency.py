"""Pure recurrence parsing for Regular OP SHOP pickup schedules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


WEEKDAY_ORDER = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")
WEEKDAY_TOKEN_MAP = {
    "mon": "MONDAY",
    "monday": "MONDAY",
    "tue": "TUESDAY",
    "tues": "TUESDAY",
    "tuesday": "TUESDAY",
    "wed": "WEDNESDAY",
    "wednesday": "WEDNESDAY",
    "thu": "THURSDAY",
    "thur": "THURSDAY",
    "thurs": "THURSDAY",
    "thursday": "THURSDAY",
    "fri": "FRIDAY",
    "friday": "FRIDAY",
}
WEEKDAY_PATTERN = re.compile(
    r"\b(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday)\b",
    re.IGNORECASE,
)
MULTI_WEEKLY_PATTERN = re.compile(
    r"\b(?:2\s*x|twice|two\s+times)\s+weekly\b",
    re.IGNORECASE,
)
MONTHLY_PATTERN = re.compile(
    r"monthly\s*\(\s*(\d+)(?:st|nd|rd|th)?\s+"
    r"(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegularPickupFrequencyRule:
    frequency_type: str
    interval_weeks: Optional[int]
    explicit_weekdays: Tuple[str, ...]
    occurrences_per_week: Optional[float]
    monthly_ordinal: Optional[int]
    monthly_weekday: Optional[str]
    raw_text: str


def parse_regular_pickup_frequency(value) -> RegularPickupFrequencyRule:
    raw_text = " ".join(str(value or "").strip().split())
    normalized = raw_text.lower().replace("_", " ")
    weekdays = _extract_weekdays(normalized)
    if not normalized:
        return _rule("UNKNOWN", raw_text)

    if "month" in normalized:
        match = MONTHLY_PATTERN.search(normalized)
        if not match:
            return _rule("UNKNOWN", raw_text, explicit_weekdays=weekdays)
        return _rule(
            "MONTHLY",
            raw_text,
            explicit_weekdays=weekdays,
            monthly_ordinal=int(match.group(1)),
            monthly_weekday=WEEKDAY_TOKEN_MAP[match.group(2).lower()],
        )

    if "fortnight" in normalized or "f/night" in normalized or "fnight" in normalized:
        return _rule(
            "FORTNIGHTLY",
            raw_text,
            interval_weeks=2,
            explicit_weekdays=weekdays,
            occurrences_per_week=0.5,
        )

    if MULTI_WEEKLY_PATTERN.search(normalized) or (
        "week" in normalized and len(weekdays) == 2
    ):
        return _rule(
            "TWICE_WEEKLY",
            raw_text,
            interval_weeks=1,
            explicit_weekdays=weekdays,
            occurrences_per_week=2,
        )

    if "week" in normalized:
        return _rule(
            "WEEKLY",
            raw_text,
            interval_weeks=1,
            explicit_weekdays=weekdays,
            occurrences_per_week=1,
        )

    return _rule("UNKNOWN", raw_text, explicit_weekdays=weekdays)


def _extract_weekdays(value: str) -> Tuple[str, ...]:
    weekdays = {
        WEEKDAY_TOKEN_MAP[match.lower()]
        for match in WEEKDAY_PATTERN.findall(value or "")
    }
    return tuple(day for day in WEEKDAY_ORDER if day in weekdays)


def _rule(
    frequency_type,
    raw_text,
    *,
    interval_weeks=None,
    explicit_weekdays=(),
    occurrences_per_week=None,
    monthly_ordinal=None,
    monthly_weekday=None,
):
    return RegularPickupFrequencyRule(
        frequency_type=frequency_type,
        interval_weeks=interval_weeks,
        explicit_weekdays=tuple(explicit_weekdays),
        occurrences_per_week=occurrences_per_week,
        monthly_ordinal=monthly_ordinal,
        monthly_weekday=monthly_weekday,
        raw_text=raw_text,
    )
