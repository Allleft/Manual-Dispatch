# Manual Dispatch Board Phase 14: Final Summary Redesign and Demo Order Reset

## Summary
Phase 14 redesigns the Final Trip Summary controls and refreshes the local demo data set for office-workflow validation.

Implemented behavior:
- Final Trip Summary now has one section-level Save Final Summary button.
- Generated driver final summary cards are read-only display cards and no longer include per-card Save buttons.
- Saved history controls now live inside the Final Trip Summary section.
- History can be loaded by a selected saved summary date.
- A dev-only reset script clears local runtime dispatch data and inserts 20 Victoria demo Orders.

## Final Trip Summary UI Redesign
The Final Trip Summary section now owns its own controls:
- Save Final Summary
- History Date dropdown
- Load History
- Section-level status/error message

The previous top-level Load History button was removed from the main board controls.

## Global Save Final Summary Button
The global Save Final Summary button saves all currently generated, unsaved final summary previews.

Implementation notes:
- The frontend still uses the existing per-driver backend endpoint: `POST /api/manual-dispatch/final-summaries`.
- Each generated driver summary remains a separate backend final summary record.
- Before saving, the frontend checks existing saved summaries for duplicate driver/date records.
- If saving fails, the generated previews stay visible and the error appears in the Final Trip Summary section.
- After saving succeeds, generated cards show `Saved` status and the global Save button is disabled when nothing unsaved remains.

## History Date Dropdown
New backend endpoint:

```text
GET /api/manual-dispatch/final-summary-dates
```

It returns saved final summary dates in descending order:

```json
["2026-05-05"]
```

The frontend uses the selected History Date when loading:

```text
GET /api/manual-dispatch/final-summaries?dispatch_date=YYYY-MM-DD
```

Saved history displays read-only final summary cards inside the Final Trip Summary section.

## Demo Data Reset
The dev-only reset script is:

```text
tools/reset_demo_orders_phase14.py
```

It clears local runtime data only:
- `final_trip_summary_rows`
- `final_trip_summaries`
- `manual_dispatch_assignments`
- `manual_driver_vehicle_assignments`
- `manual_orders`

It retains:
- Drivers
- Vehicles

It inserts 20 ACTIVE demo Orders for Victoria, Australia with `delivery_date = 2026-05-05` and invoice numbers `VIC-1001` through `VIC-1020`.

This script is manual only and does not run on application startup. Runtime SQLite files remain ignored by Git.

## Validation Results
Local reset output:

```text
Orders inserted: 20
Assignments cleared
Driver vehicle selections cleared
Final summaries cleared
Drivers retained: 7
Vehicles retained: 9
```

## Excluded Work
Phase 14 does not add:
- automatic assignment
- automatic driver/vehicle selection
- route optimization
- ETA calculation
- maps or geocoding
- CP-SAT or OR-Tools
- blocking rules
- auth/login
- MySQL/MariaDB
- import/export redesign
