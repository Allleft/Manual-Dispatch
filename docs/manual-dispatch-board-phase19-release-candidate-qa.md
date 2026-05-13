# Manual Dispatch Board Phase 19: Release Candidate QA

## Summary

Phase 19 is a release-candidate QA pass for the Manual Dispatch Board on `feature/manual-dispatch-board`.

The goal is to verify that the implemented manual dispatch workflow is stable enough for real office trial use. This phase is QA, bug fixing, and documentation only. No new business features, automatic assignment, route optimization, ETA, geocoding, Google Maps, CP-SAT, blocking rules, MySQL/MariaDB, auth redesign, major UI redesign, or Excel import work is included.

## QA Scope

The QA pass covers:

- Login, Register, Logout, and operator attribution.
- Board loading and Dispatch Date behavior.
- Global Task Pool membership and display filters.
- Add, Edit, and Cancel Order lifecycle.
- Product Details and Pallet/Bags exclusivity.
- Manual Assign, Reassign, and Unassign.
- Driver Summary Delivery Date behavior.
- Vehicle selection scoped by Driver + Dispatch Date + Delivery Date.
- Driver & Vehicle Specification modal behavior.
- Final Trip Summary generation.
- Global Save and Export.
- Load History by date.
- FINALIZED Order visibility.
- Excel export from saved Final Trip Summary snapshots.
- Static suburb-level estimated straight-line distance display and sorting.
- Static safety checks for prohibited feature creep.

## Manual Test Checklist

| Area | Result | Notes |
| --- | --- | --- |
| Login / Register / Logout | Pass | Browser smoke created a unique operator account, confirmed login state, logged out, and logged back in. Route-level auth tests also cover invalid password and password reset cases. |
| Board loading | Pass | Browser smoke loaded the board, set a future Dispatch Date, and kept the board usable after reload. |
| Task Pool | Pass | Browser smoke created Orders, confirmed Task Pool visibility, used Delivery Date display filtering, and cleared it. |
| Add Order | Pass | Browser smoke created two Orders through the UI with required fields and Product Details. |
| Edit / Cancel Order | Pass by automated regression | Existing unit/static tests cover editable Delivery Date, Product Details update, assigned-order edit preservation, and Cancel Order rules. No new browser bug was found in this pass. |
| Product Details | Pass | Browser smoke saved pallet and bag Product Details and verified they reached Final Summary / Excel snapshot output. |
| Manual assignment | Pass | Browser smoke assigned one Order to Trip 1 and one Order to Trip 2 for the same driver. |
| Vehicle selection | Pass | Browser smoke selected a Vehicle for Driver + Dispatch Date + Delivery Date before Final Summary generation. |
| Driver & Vehicle Specification | Pass | Browser smoke opened the modal, created temporary QA Driver/Vehicle records through API setup, toggled availability in the modal, closed the modal, and cleaned up the temporary records. |
| Final Trip Summary generation | Pass | Browser smoke generated a read-only Final Trip Summary preview containing Product Details and estimated distance columns. |
| Save and Export | Pass | Browser smoke saved the generated summary, downloaded XLSX, and verified workbook content with `openpyxl`. |
| Load History | Pass | Browser smoke reloaded the board, loaded History by date, and confirmed saved snapshot content and `Saved by` attribution. |
| FINALIZED visibility | Pass | Browser smoke confirmed finalized smoke-test Orders were hidden from Task Pool and editable Driver Summary after reload. |
| Excel export | Pass | Browser smoke verified downloaded workbook includes snapshot data, Product Details, Saved By, and Estimated Distance, and excludes legacy daily run sheet fields. |
| Distance sorting/display | Pass | Unit tests and browser smoke confirmed known suburb distance fields are present; Phase 18 tests cover sort order and unknown fallback. |

## Regression Commands

Commands run during Phase 19:

```powershell
.\tmp\route-test-venv\Scripts\python.exe -m compileall backend
.\tmp\route-test-venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
git diff --check
git diff --stat
git status --short
Get-ChildItem frontend -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
.\tmp\route-test-venv\Scripts\python.exe tools\qa_suburb_distances_from_somerton.py
```

Additional API smoke checks:

- `GET /api/manual-dispatch/board?dispatch_date=2026-05-15`
- `GET /api/manual-dispatch/specifications`
- `GET /api/manual-dispatch/final-summary-dates`
- `GET /api/manual-dispatch/final-summaries?dispatch_date=2031-08-13&delivery_date=2031-08-13`
- `GET /api/manual-dispatch/final-summaries/export-excel?dispatch_date=2031-08-13&delivery_date=2031-08-13`

Browser smoke was run with Playwright Chromium against:

```text
http://127.0.0.1:8141/frontend/
```

Port `8141` was used to avoid a stale local service already occupying `8130`.

## Bugs Found

No application-code bugs were confirmed during this QA pass.

Environment / QA harness observations:

- Playwright Chromium was missing locally and had to be installed before browser smoke could run.
- Headless Chromium launch was blocked inside the sandbox with `EPERM`; the browser smoke had to run outside the sandbox.
- Port `8130` appeared to be occupied by a stale local service during browser testing, so the passing smoke run used clean port `8141`.
- Early smoke-script assertions expected invoice numbers inside Driver Summary assigned cards, but the current UI intentionally shows suburb, delivery date, and load there; the script was corrected.

## Fixes Applied

No application code fixes were required.

QA-only temporary script adjustments were made under `tmp/` and are not committed:

- Exact password label matching for Playwright strict mode.
- Driver Summary assertion changed to match current assigned-card UI.
- Network-failure listener made robust for the installed Playwright Python version.
- Browser smoke target port changed from `8130` to `8141`.

## Known Risks

- This pass is a release-candidate smoke and regression pass, not an exhaustive manual field trial.
- Runtime SQLite data used by browser smoke is local and not committed.
- Static suburb distances remain demo-grade suburb-level estimated straight-line distances, not driving distance, ETA, or route optimization.
- Existing Phase 15 login is lightweight MVP/demo authentication, not production-grade enterprise authentication.
- Browser smoke created and finalized QA Orders in the local runtime database. This affects only local ignored runtime data.

## Excluded Work

Phase 19 intentionally excludes:

- automatic assignment
- automatic driver selection
- automatic vehicle selection
- automatic trip planning
- route optimization
- ETA calculation
- live geocoding
- Google Maps logic
- CP-SAT or other optimization engines
- blocking assignment rules
- MySQL/MariaDB
- auth redesign
- major UI redesign
- Excel import
