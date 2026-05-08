# Manual Dispatch Board Phase 14B: Final Summary Save and Export

## Summary

Phase 14B polishes the Final Trip Summary workflow so office staff use one clear action:

1. Generate locked Final Trip Summary previews from Driver cards.
2. Click **Save and Export** in the Final Trip Summary section.
3. Save all unsaved generated summaries to SQLite.
4. Export an Excel workbook from the saved Final Trip Summary snapshots.

The workflow remains manual. No automatic assignment, routing, ETA, maps, CP-SAT, blocking rules, auth, or MySQL behavior is included.

## UI Changes

- The old top-level **Export Excel** button was removed from the Dispatch Date control area.
- The Final Trip Summary section now has one global **Save and Export** button.
- Individual driver Final Trip Summary cards remain read-only and do not include per-card save buttons.
- History Date and Load History controls live on the right side of the Final Trip Summary control row.
- The frontend no longer shows the section text `Locked generated snapshots. They do not auto-update from later board changes.`
- The frontend no longer shows the card kicker `Locked snapshot`; generated cards keep a simple `Locked` badge.

## Save and Export Behavior

The global **Save and Export** button:

- Is disabled when there are no unsaved generated Final Trip Summary previews.
- Shows `Saving and Exporting...` while running.
- Saves unsaved summaries sequentially with the existing `POST /api/manual-dispatch/final-summaries` endpoint.
- Stops and shows the backend error if any save fails.
- Exports only after all saves succeed.
- Shows `Final Summary saved and exported.` on success.
- Reloads the board after success so finalized Orders stay out of the active Task Pool and editable Trip Summary.

If a duplicate summary exists for the same Driver and Dispatch Date, the backend error is shown inside the Final Trip Summary section and no export is attempted.

## Final Summary Excel Export

New endpoint:

`GET /api/manual-dispatch/final-summaries/export-excel?dispatch_date=YYYY-MM-DD`

The export uses saved snapshot data from:

- `final_trip_summaries`
- `final_trip_summary_rows`

It does not use live Order, Driver, or Vehicle records, so saved history remains stable after later master-data edits.

Workbook behavior:

- One worksheet per saved Driver summary.
- Sheet names use Driver snapshot names, safely truncated for Excel.
- Empty export creates a useful workbook message instead of failing.

Each worksheet includes:

- Date
- Driver
- Rego #
- Total Pallets
- Total Loose Bags
- Trip 1 / Trip 2 sections only when those trips have Orders
- Columns: No., Customer Name, Suburb, Invoice #, Product, Pallets

The export does not include:

- Generated At
- Saved At
- Daily run sheet signature/loading fields
- Active assignment export columns

## Driver Summary Cleanup

Before saving, a generated unsaved preview may still lock that driver from generating a duplicate preview.

After **Save and Export** succeeds, the stale Driver Summary warning is removed. The saved result remains visible in Final Trip Summary and Load History.

## Validation

Phase 14B validation covers:

- Backend compile checks.
- Backend regression tests.
- Final Summary Excel export tests.
- Frontend JavaScript syntax checks.
- Static safety checks for forbidden browser/storage/routing/optimization additions.

## Excluded Work

Phase 14B does not add:

- Final Summary PDF export
- Final Summary print layout
- Void / unlock / regenerate saved summary workflow
- Automatic assignment
- Route optimization
- ETA
- Maps or geocoding
- CP-SAT or OR-Tools
- Auth/login
- MySQL/MariaDB
