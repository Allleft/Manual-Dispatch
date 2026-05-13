import json
from functools import lru_cache
from math import inf
from pathlib import Path


WAREHOUSE_ORIGIN = "98-102 Hume Hwy, Somerton, VIC, 3062"
DISTANCE_DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "suburb_distances_from_somerton.json"
)
SUBURB_ALIASES = {
    "ballarat central": "ballarat",
    "bendigo central": "bendigo",
    "cbd": "melbourne",
    "dandenong sth": "dandenong south",
    "melbourne cbd": "melbourne",
    "tulla": "tullamarine",
}


def normalize_suburb_name(suburb):
    return " ".join(str(suburb or "").strip().split()).casefold()


@lru_cache(maxsize=1)
def _distance_lookup():
    payload = json.loads(DISTANCE_DATA_PATH.read_text(encoding="utf-8"))
    rows = payload.get("records", []) if isinstance(payload, dict) else payload
    return {
        normalize_suburb_name(row.get("suburb")): float(row["estimated_distance_km"])
        for row in rows
        if normalize_suburb_name(row.get("suburb"))
        and row.get("estimated_distance_km") is not None
    }


def get_estimated_distance_km(suburb):
    normalized = normalize_suburb_name(suburb)
    if not normalized:
        return None
    lookup = _distance_lookup()
    exact_distance = lookup.get(normalized)
    if exact_distance is not None:
        return exact_distance

    canonical_suburb = SUBURB_ALIASES.get(normalized)
    if canonical_suburb:
        return lookup.get(canonical_suburb)
    return None


def sort_orders_by_suburb_distance_then_start_time(orders):
    return sorted(list(orders or []), key=_distance_sort_key)


def _distance_sort_key(order):
    distance = _extract_value(
        order,
        "estimated_distance_km_from_warehouse_snapshot",
        "estimated_distance_km_from_warehouse",
    )
    if distance in ("", None):
        distance = get_estimated_distance_km(
            _extract_value(order, "suburb_snapshot", "suburb")
        )

    normalized_suburb = normalize_suburb_name(
        _extract_value(order, "suburb_snapshot", "suburb")
    )
    normalized_start_time = _normalize_time_value(
        _extract_value(order, "start_time_snapshot", "start_time", "_sort_start_time")
    )
    invoice_number = str(
        _extract_value(order, "invoice_number_snapshot", "invoice_number") or ""
    ).casefold()
    order_id = str(
        _extract_value(order, "order_id_snapshot", "order_id", "task_id") or ""
    ).casefold()

    known_distance = distance not in ("", None)
    distance_value = float(distance) if known_distance else inf
    has_start_time = normalized_start_time is not None

    return (
        0 if known_distance else 1,
        distance_value,
        normalized_suburb,
        0 if has_start_time else 1,
        normalized_start_time or "",
        invoice_number,
        order_id,
    )


def _normalize_time_value(value):
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return text
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def _extract_value(order, *keys):
    if isinstance(order, dict):
        for key in keys:
            if key in order:
                return order.get(key)
        return None
    for key in keys:
        if hasattr(order, key):
            return getattr(order, key)
    return None
