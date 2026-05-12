# Manual Dispatch Board Phase 10A-5: Order Search and Filter

## Summary
- Phase 10A-5 adds frontend-only Task Pool search, urgency, and Delivery Date display filtering.
- Filters apply only to unassigned Orders in the Task Pool.
- Trip Summary, assignments, vehicle selection, backend data, and Excel export behavior are unchanged.

## Scope
- Add a Search Orders input above the Task Pool.
- Add an Urgency filter with `All`, `Normal`, and `Urgent`.
- Add an optional Delivery Date display filter with a clear `All delivery dates` reset.
- Show a compact filter summary count.
- Show `No matching unassigned orders.` when filters produce no Task Pool results.

## Search Fields
Search matches:
- `invoice_number`
- `company_name`
- `suburb`
- `postcode`
- `note`

## Urgency Filter
- `All` shows all unassigned Orders.
- `Normal` shows unassigned Orders with Normal urgency.
- `Urgent` shows unassigned Orders with Urgent urgency.

## Behavior Rules
- Filtering is in-memory frontend state only.
- No backend search endpoint was added.
- No assignment records are changed by filtering.
- The Delivery Date display filter does not change global Task Pool membership.
- Assigned Orders remain visible in Trip Summary even if they do not match the filter.
- No `localStorage` or `sessionStorage` is used.

## Excluded Work
- Backend search
- Pagination
- Advanced filters
- Excel export changes
- Assignment behavior changes
- Automatic assignment
- Blocking rules
- Maps, ETA, routing, geocoding, CP-SAT, or optimization

## Validation
- Run frontend syntax validation with `node --check frontend/app.js`.
- Run backend regression tests to confirm no backend behavior was broken.
- Run static safety checks for storage, maps, routing, ETA, and optimization calls.

## Phase 10B-1 Handoff
- Next planned subphase is Add Driver.
- Keep Preferred Zone hidden from main Trip Summary even when driver management is added.
