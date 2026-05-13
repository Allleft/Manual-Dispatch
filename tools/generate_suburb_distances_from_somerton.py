import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "tools" / "data" / "suburb_centroids_from_somerton_curated.json"
OUTPUT_PATH = ROOT / "backend" / "data" / "suburb_distances_from_somerton.json"
EARTH_RADIUS_KM = 6371.0088


def haversine_km(origin_latitude, origin_longitude, latitude, longitude):
    origin_latitude_radians = radians(origin_latitude)
    latitude_radians = radians(latitude)
    latitude_delta = latitude_radians - origin_latitude_radians
    longitude_delta = radians(longitude - origin_longitude)
    chord = (
        sin(latitude_delta / 2) ** 2
        + cos(origin_latitude_radians)
        * cos(latitude_radians)
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(chord))


def build_rows():
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    warehouse = source["warehouse"]
    generated_rows = []

    for record in sorted(source["records"], key=lambda row: row["suburb"].casefold()):
        override = record.get("estimated_distance_km_override")
        if override is None:
            distance = haversine_km(
                warehouse["latitude"],
                warehouse["longitude"],
                record["latitude"],
                record["longitude"],
            )
            method_note = source["method_note"]
        else:
            distance = float(override)
            method_note = record.get(
                "method_note",
                "Retained static Phase 18 compatibility estimate from the existing suburb table; still a local estimate, not routing distance or ETA.",
            )

        generated_rows.append(
            {
                "suburb": record["suburb"],
                "state": record["state"],
                "postcode": record.get("postcode"),
                "estimated_distance_km": round(float(distance), 1),
                "method_note": method_note,
            }
        )

    return generated_rows


def main():
    rows = build_rows()
    OUTPUT_PATH.write_text(
        json.dumps(rows, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} suburb distance records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
