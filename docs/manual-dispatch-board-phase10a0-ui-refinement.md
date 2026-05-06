# Manual Dispatch Board Phase 10A-0

## Summary
Phase 10A-0 refines the current Manual Dispatch Board before full Order Management work begins.
It keeps the workflow manual and focuses on compact Order cards, read-only Order details, Trip Summary wording, non-blocking exceptions, and pending Driver/Trip selection stability.

## Order Card Compact Layout
- Order cards now use a compact two-column layout.
- The left side shows Invoice #, Company Name, Suburb, Normal/Urgent, Note preview, and Start Time.
- The right side keeps Driver, Trip, and Assign controls.
- Long notes are truncated on the card.
- Large warning/hint rows were removed from Order cards.

## Detail Popup Behavior
- Clicking an Order card opens a read-only detail popup.
- The popup shows Order ID, Invoice #, Company Name, Phone, Delivery Address, Suburb, Postcode, Delivery Date, Zone, Urgency, Preferred Driver, Pallet Quantity, Loose Bags Quantity, Start Time, End Time, and Note.
- The popup has a Close button.
- Dropdowns and buttons inside the compact card do not open the popup accidentally.
- Edit Order is not implemented in this phase.

## New Order Fields
Orders now support:
- `invoice_number`
- `phone`

These fields are additive in the backend board response.
SQLite initialization safely adds missing columns to existing local databases without wiping data.

## Trip Summary Rename
- The lower section title is now Trip Summary.
- Existing driver-based cards remain in place to preserve Driver + Dispatch Date vehicle selection and current Assign/Unassign behavior.
- Trip 1 remains above Trip 2.

## Preferred Zone Hidden On Frontend
- Driver Preferred Zone is no longer displayed in the frontend.
- Zone mismatch warning rows were removed from Order cards.
- Backend schema and SQLite storage still keep `preferred_zone` for future use.

## Exception Behavior
Exceptions are compact, display-only messages inside Trip Summary cards.
They do not block manual assignment.

Supported exceptions:
- `Exception: Driver only handles pallet orders`
- `Exception: Assigned pallets exceed selected vehicle capacity`

Driver `pallet_only` is additive backend data.
New demo seed data marks Tony as pallet-only.
Existing migrated drivers default to `pallet_only = false`.

## Pending Selection Bug Fix
- Frontend now tracks pending Driver/Trip selections in memory by Order ID.
- Assigning one Order no longer resets selections for other unassigned Orders.
- The assigned Order's pending selection is cleared after successful assignment.
- No `localStorage` or `sessionStorage` is used.

## Tests And Validation
Recommended validation:
- `python -m compileall backend`
- `python -m unittest discover -s tests -v`
- `node --check frontend/app.js`
- static checks for no `localStorage`, `sessionStorage`, maps, geolocation, ETA, route, or optimization logic.

If normal `python` is unavailable, use:
- `.\.venv\Scripts\python.exe`

## Excluded Work
- Add Order.
- Edit Order.
- Delete Order.
- Driver Management.
- Vehicle Management.
- CSV/Excel import.
- authentication or login.
- automatic assignment.
- automatic driver selection.
- automatic vehicle selection.
- automatic trip planning.
- route optimization.
- ETA calculation.
- geocoding.
- Google Maps logic.
- CP-SAT.
- capacity-based blocking.
- zone-based blocking.
- preferred-driver blocking.
- urgency-based blocking.

## Phase 10A Handoff Notes
Future Order Management work can add Add/Edit/Delete flows using the expanded Order fields.
Those features should keep the current manual assignment workflow and avoid introducing automatic assignment or optimization behavior unless explicitly approved.
