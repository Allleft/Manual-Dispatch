import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.services.manual_dispatch.suburb_distance_service import (
    SUBURB_ALIASES,
    normalize_suburb_name,
)


DELIVERY_AREA_LOCAL = "LOCAL"
DELIVERY_AREA_SOUTHEAST = "SOUTHEAST"
VALID_DELIVERY_AREAS = frozenset(
    {DELIVERY_AREA_LOCAL, DELIVERY_AREA_SOUTHEAST}
)
UNKNOWN_DELIVERY_AREA_WARNING = (
    "Delivery area could not be determined from suburb/postcode. Needs Review."
)
REGION_TO_DELIVERY_AREA = {
    "EAST": DELIVERY_AREA_SOUTHEAST,
    "SOUTH": DELIVERY_AREA_SOUTHEAST,
    "SOUTHEAST": DELIVERY_AREA_SOUTHEAST,
    "NORTH": DELIVERY_AREA_LOCAL,
    "CITY": DELIVERY_AREA_LOCAL,
    "WEST": DELIVERY_AREA_LOCAL,
    "SOUTHWEST": DELIVERY_AREA_LOCAL,
}
DELIVERY_SUBURB_REGION_DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "delivery_suburb_regions.json"
)


@dataclass(frozen=True)
class DeliverySuburbClassification:
    normalized_suburb: str
    postcode: str
    region: str | None
    auto_delivery_area: str | None
    known: bool


def normalize_delivery_postcode(postcode):
    return "".join(str(postcode or "").strip().split())


def canonical_delivery_suburb(suburb):
    normalized = normalize_suburb_name(suburb)
    return SUBURB_ALIASES.get(normalized, normalized)


def canonical_delivery_location(suburb, postcode):
    return (
        canonical_delivery_suburb(suburb),
        normalize_delivery_postcode(postcode),
    )


@lru_cache(maxsize=1)
def _region_lookup():
    payload = json.loads(
        DELIVERY_SUBURB_REGION_DATA_PATH.read_text(encoding="utf-8")
    )
    rows = payload.get("records", []) if isinstance(payload, dict) else payload
    exact = {}
    by_suburb = {}
    canonical_names = {}
    for row in rows:
        suburb = str(row.get("suburb") or "").strip()
        normalized_suburb = normalize_suburb_name(suburb)
        postcode = normalize_delivery_postcode(row.get("postcode"))
        region = str(row.get("region") or "").strip().upper()
        if not normalized_suburb or not postcode or region not in REGION_TO_DELIVERY_AREA:
            raise ValueError("Invalid delivery suburb region record")
        key = (normalized_suburb, postcode)
        if key in exact:
            if exact[key] != region:
                raise ValueError(
                    f"Conflicting delivery suburb region record: {suburb} {postcode}"
                )
            raise ValueError(
                f"Duplicate delivery suburb region record: {suburb} {postcode}"
            )
        exact[key] = region
        by_suburb.setdefault(normalized_suburb, []).append((postcode, region))
        canonical_names.setdefault(normalized_suburb, suburb)
    return exact, by_suburb, canonical_names


def classify_delivery_suburb(suburb, postcode=None):
    canonical_suburb = canonical_delivery_suburb(suburb)
    normalized_postcode = normalize_delivery_postcode(postcode)
    exact, by_suburb, canonical_names = _region_lookup()
    region = None
    if canonical_suburb and normalized_postcode:
        region = exact.get((canonical_suburb, normalized_postcode))
    candidates = by_suburb.get(canonical_suburb, [])
    if region is None and not normalized_postcode and len(candidates) == 1:
        region = candidates[0][1]
    normalized_name = canonical_names.get(
        canonical_suburb,
        " ".join(str(suburb or "").strip().split()),
    )
    return DeliverySuburbClassification(
        normalized_suburb=normalized_name,
        postcode=normalized_postcode,
        region=region,
        auto_delivery_area=REGION_TO_DELIVERY_AREA.get(region),
        known=region is not None,
    )


def validate_delivery_area(delivery_area):
    normalized = str(delivery_area or "").strip().upper()
    if normalized not in VALID_DELIVERY_AREAS:
        raise ValueError("delivery_area must be LOCAL or SOUTHEAST")
    return normalized


def apply_delivery_area_preview(item):
    classification = classify_delivery_suburb(item.suburb, item.postcode)
    item.auto_delivery_region = classification.region
    item.auto_delivery_area = classification.auto_delivery_area
    item.delivery_area_override = None
    item.delivery_area = classification.auto_delivery_area
    item.delivery_area_source = "AUTO"
    warnings = [
        warning
        for warning in list(item.warnings or [])
        if warning != UNKNOWN_DELIVERY_AREA_WARNING
    ]
    if not classification.known:
        warnings.append(UNKNOWN_DELIVERY_AREA_WARNING)
    item.warnings = warnings
    return item


class DeliveryOrderAreaResolver:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def classify(suburb, postcode=None):
        return classify_delivery_suburb(suburb, postcode)

    @staticmethod
    def validate_area(delivery_area):
        return validate_delivery_area(delivery_area)

    def resolve_order(self, order):
        if order is None:
            return None
        classification = self.classify(order.suburb, order.postcode)
        override = self.repository.get_delivery_order_area_override(order.order_id)
        order.auto_delivery_region = classification.region
        order.auto_delivery_area = classification.auto_delivery_area
        order.delivery_area_override = override
        order.delivery_area = override or classification.auto_delivery_area
        order.delivery_area_source = "MANUAL" if override else "AUTO"
        return order

    def set_override(self, order_id, delivery_area, updated_by=None):
        normalized = validate_delivery_area(delivery_area)
        self.repository.set_delivery_order_area_override(
            order_id,
            normalized,
            updated_by=updated_by,
        )
        return self.resolve_order(self.repository.get_order(order_id))

    def clear_override(self, order_id):
        self.repository.clear_delivery_order_area_override(order_id)
        return self.resolve_order(self.repository.get_order(order_id))
