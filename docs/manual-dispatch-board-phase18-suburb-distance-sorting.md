# Phase 18: Suburb Distance Sorting

## Summary

Phase 18 adds static suburb-level estimated straight-line distance support for Final Trip Summary ordering.

- Warehouse origin: `98-102 Hume Hwy, Somerton, VIC, 3062`
- Sorting scope: Final Trip Summary rows only
- Sorting direction: nearest known suburb estimate to farthest
- Same-suburb tie-breaker: Start Time earliest to latest

This is not route optimization, ETA calculation, geocoding, Google Maps, or automatic trip planning.

## Distance Data Source

Distance estimates live in:

- `backend/data/suburb_distances_from_somerton.json`

The table is generated offline by:

- `tools/generate_suburb_distances_from_somerton.py`
- `tools/data/suburb_centroids_from_somerton_curated.json`

The curated source file stores locality-centroid coordinates and a small set of retained Phase 18 compatibility overrides for previously published demo/test estimates.

Centroid provenance is explicit:

```text
Curated manually for demo sorting only.
```

Coordinates were not derived from or copied from an official/open locality dataset in this repository revision.

The generated runtime table now carries dataset-level metadata for:

- warehouse origin,
- centroid source,
- calculation method,
- generation date,
- limitations.

New expanded coverage uses:

```text
Estimated straight-line distance from curated suburb/locality centroid to warehouse via Haversine.
```

The output is a static local suburb-level estimated straight-line distance table prepared for board/demo sorting. It is not a turn-by-turn routing distance, does not calculate ETA, and does not call any external API at runtime.

Each record stores:

- suburb
- state
- postcode when available
- `estimated_distance_km`
- method note

Suburb lookup normalizes:

- leading/trailing whitespace,
- repeated spaces,
- letter casing.

Phase 18 follow-up coverage expands the table from a small demo subset to common Melbourne and regional delivery localities, including examples such as:

- Dandenong South
- Pakenham
- Ballarat Central
- Bendigo
- Footscray
- Northcote
- Box Hill
- Essendon
- Shepparton

Unknown remains a valid fallback for any locality not present in the static table.

## Alias Behavior

Lookup priority is:

1. exact normalized suburb match,
2. alias/canonical fallback,
3. `Unknown`.

Alias examples:

- `Dandenong Sth` -> `Dandenong South`
- `Melbourne CBD` -> `Melbourne`
- `CBD` -> `Melbourne`
- `Tulla` -> `Tullamarine`
- `Ballarat Central` and `Bendigo Central` keep their exact rows when present, with canonical fallback available if those exact rows are removed later.

## Sorting Rules

Final Trip Summary rows sort within each trip section by:

1. Known estimated distance before unknown distance
2. Estimated distance ascending
3. Normalized suburb name for deterministic ordering where needed
4. Start Time ascending for Orders in the same suburb
5. Missing Start Time after valid Start Time in the same suburb
6. Stable fallback using invoice number, then Order ID

Task Pool ordering and Driver Summary ordering are unchanged.

## Snapshot Behavior

Saved Final Trip Summary row snapshots now store:

- `estimated_distance_km_from_warehouse_snapshot`

That keeps history and export output stable even if the static suburb distance file changes later.

Unknown suburbs remain valid:

- UI displays `Unknown`
- Excel export writes `Unknown`
- unknown-distance rows sort after known-distance rows

## Final Summary UI

Generated previews and saved history display:

- `Estimated Distance From Warehouse (km)`

Known values show as a one-decimal kilometre label, such as:

```text
12.4 km
```

Unknown values show:

```text
Unknown
```

## Excel Export

Saved Final Trip Summary export now includes:

- `Estimated Distance From Warehouse (km)`

Excel row ordering matches the saved Final Trip Summary snapshot ordering. Product Details, Dispatch Date, Delivery Date, and Saved By behavior remain unchanged.

## Validation Focus

Phase 18 adds tests for:

- suburb normalization,
- known and unknown lookups,
- expanded Melbourne / regional suburb coverage,
- alias resolution,
- distance sorting,
- same-suburb Start Time sorting,
- unknown-distance rows placed last,
- saved snapshot distance persistence,
- Excel distance column and row order,
- unchanged Phase 15/16 behavior.

The follow-up hardening pass also adds:

- `tools/qa_suburb_distances_from_somerton.py`
- committed-dataset QA checks for required fields, duplicate normalized suburbs, non-negative numeric distances, alphabetical ordering, and known suburb/alias resolution
