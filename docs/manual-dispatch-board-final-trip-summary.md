# Manual Dispatch Board Final Trip Summary

## Summary
- Final Trip Summary is a locked frontend-memory snapshot generated from a Driver's current editable Trip Summary for the selected Driver Summary Delivery Date.
- It is read-only and does not auto-update after later board changes.
- It uses existing assignment data and existing unassign API calls during Generate.
- Phase 10G adds optional SQLite persistence for saved Final Trip Summary snapshots.

## Generate Behavior
1. User clicks `Generate` on a Driver card.
2. Frontend collects that Driver's current assignments for the selected Dispatch Date whose Orders match the selected Driver Summary Delivery Date.
3. If there are no assigned Orders, no summary is generated.
4. Frontend builds and stores a locked snapshot before calling unassign.
5. Frontend calls `POST /api/manual-dispatch/unassign` for each generated Order.
6. Frontend reloads board data.
7. Editable Trip Summary no longer shows those Orders.
8. Locked Final Trip Summary still shows the generated Orders from the snapshot.

## Snapshot Rule
- Final Trip Summary must not render from live board state.
- Snapshot data is stored in `state.finalTripSummaries`.
- Later Assign, Unassign, Edit Order, or Vehicle changes do not change an existing locked summary.
- A Driver can have one locked Final Trip Summary per Dispatch Date + Delivery Date in this phase.

## Session Limitation
- Generated-but-unsaved Final Trip Summary previews are frontend-memory only.
- Refresh may clear generated unsaved previews.
- Generated Orders are hidden from Task Pool in the same session using `state.generatedTaskKeys`.
- Saving a Final Trip Summary marks included Orders as `FINALIZED`.
- Saved summaries can be loaded through History after refresh.

## Final Summary Header
Each locked block shows:
- Dispatch Date
- Delivery Date
- Driver
- Rego #
- Locked

## Excluded Header Fields
Final Trip Summary does not show:
- DAILY RUN SHEET
- Start Time
- TIME LOADING STARTED
- TIME LOADING COMPLETE
- KG'S
- COD
- CQ
- TIME IN
- TIME OUT
- PRINT NAME
- COMMENTS SIGNATURE
- NO. # PALLETS RETURNED / RETEND

## Trip Display Rules
- Preserve Trip 1 / Trip 2 grouping from the snapshot.
- Show only trips with Orders.
- Do not show empty trips.
- Editable Trip Summary also shows only trips that currently contain assigned Orders.
- Drivers with no editable assigned Orders show a small empty state.

## Final Table Columns
1. No.
2. Customer Name
3. Suburb
4. Invoice #
5. Product
6. Pallets

## Column Rules
- `No.` starts from 1 within each Driver snapshot across displayed trips.
- `Customer Name` comes from `order.company_name`.
- `Suburb` comes from `order.suburb`.
- `Invoice #` comes from `order.invoice_number`.
- `Product` remains blank unless a real product field exists.
- `Pallets` comes from `order.pallet_quantity`.
- Loose-bag-only Orders show Pallets as `0`.

## Read-Only Rule
Final Trip Summary does not include:
- Driver dropdown
- Trip dropdown
- Assign button
- Unassign button
- Choose Vehicle dropdown
- Edit button
- Delete or Cancel controls

## Excluded Work
- Excel export changes
- Lock/unlock workflow
- Batch unassign endpoint
- Add/Edit/Delete Order changes
- Vehicle selection changes
- Automatic assignment
- Blocking rules
- Maps, ETA, routing, geocoding, CP-SAT, or optimization

## Future Handoff
- A later phase can add a lock/unlock workflow if office review requires it.
- A later phase can add controlled reopen behavior for `FINALIZED` Orders if office review requires it.
