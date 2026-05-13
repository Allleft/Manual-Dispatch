# Phase 18: Suburb Distance Sorting

## Summary

Phase 18 adds suburb-level estimated warehouse distance support for Final Trip Summary ordering.

- Warehouse origin: `98-102 Hume Hwy, Somerton, VIC, 3062`
- Sorting scope: Final Trip Summary rows only
- Sorting direction: nearest known suburb estimate to farthest
- Same-suburb tie-breaker: Start Time earliest to latest

This is not route optimization, ETA calculation, geocoding, Google Maps, or automatic trip planning.

## Distance Data Source

Distance estimates live in:

- `backend/data/suburb_distances_from_somerton.json`

The data is a static local suburb-level estimate table prepared for board/demo sorting. It is not a turn-by-turn routing distance and does not call any external API.

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
- distance sorting,
- same-suburb Start Time sorting,
- unknown-distance rows placed last,
- saved snapshot distance persistence,
- Excel distance column and row order,
- unchanged Phase 15/16 behavior.
