import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.manual_dispatch.suburb_distance_service import (  # noqa: E402
    get_estimated_distance_km,
    normalize_suburb_name,
)


DATASET_PATH = ROOT / "backend" / "data" / "suburb_distances_from_somerton.json"
REQUIRED_ROW_FIELDS = {
    "suburb",
    "state",
    "postcode",
    "estimated_distance_km",
    "method_note",
}
KNOWN_SUBURBS = (
    "Somerton",
    "Dandenong South",
    "Pakenham",
    "Ballarat Central",
    "Bendigo",
    "Footscray",
    "Northcote",
    "Box Hill",
    "Essendon",
    "Shepparton",
)
KNOWN_ALIASES = (
    "Dandenong Sth",
    "Melbourne CBD",
    "CBD",
)


def load_dataset(path=DATASET_PATH):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Distance dataset must be an object with metadata and records.")
    return payload


def validate_dataset(payload=None):
    dataset = payload or load_dataset()
    metadata = dataset.get("metadata") or {}
    records = dataset.get("records")
    errors = []

    for field in (
        "warehouse_origin",
        "centroid_source",
        "calculation_method",
        "date_generated",
        "limitations",
    ):
        if not metadata.get(field):
            errors.append(f"metadata.{field} is required")

    if not isinstance(records, list):
        errors.append("records must be a list")
        records = []

    normalized_suburbs = []
    for index, row in enumerate(records):
        missing_fields = REQUIRED_ROW_FIELDS.difference(row.keys())
        if missing_fields:
            errors.append(
                f"records[{index}] missing fields: {', '.join(sorted(missing_fields))}"
            )

        normalized = normalize_suburb_name(row.get("suburb"))
        if not normalized:
            errors.append(f"records[{index}].suburb is required")
        normalized_suburbs.append(normalized)

        distance = row.get("estimated_distance_km")
        if not isinstance(distance, (int, float)) or isinstance(distance, bool):
            errors.append(f"records[{index}].estimated_distance_km must be numeric")
        elif distance < 0:
            errors.append(f"records[{index}].estimated_distance_km must be non-negative")

    duplicates = sorted(
        suburb
        for suburb in set(normalized_suburbs)
        if suburb and normalized_suburbs.count(suburb) > 1
    )
    if duplicates:
        errors.append(f"duplicate normalized suburbs: {', '.join(duplicates)}")

    sorted_suburbs = sorted(normalized_suburbs)
    if normalized_suburbs != sorted_suburbs:
        errors.append("records must be sorted alphabetically by normalized suburb")

    for suburb in KNOWN_SUBURBS:
        if get_estimated_distance_km(suburb) is None:
            errors.append(f"known suburb does not resolve: {suburb}")

    for alias in KNOWN_ALIASES:
        if get_estimated_distance_km(alias) is None:
            errors.append(f"known alias does not resolve: {alias}")

    if get_estimated_distance_km("Definitely Unmapped Demo Ridge") is not None:
        errors.append("unknown suburb fallback must remain None")

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "records": len(records),
        "known_suburbs": len(KNOWN_SUBURBS),
        "known_aliases": len(KNOWN_ALIASES),
    }


def main():
    result = validate_dataset()
    print(json.dumps({"result": "passed", **result}, indent=2))


if __name__ == "__main__":
    main()
