# Manual Dispatch Board: Global Final Summary Save

## Summary
Final Trip Summary saving is a section-level action. The dispatch board uses one global `Save Final Summary` button for the whole Final Trip Summary section instead of a Save button on each driver summary card.

## Global Save Button Behavior
The global button saves all currently generated, unsaved Final Trip Summary previews.

Frontend behavior:
- The button is disabled when there are no generated unsaved summaries.
- The button shows `Saving...` while the save loop is running.
- Unsaved summaries are saved sequentially through the existing backend endpoint.
- Saved summaries replace their generated preview in `state.finalTripSummaries`.
- Saved cards show the `Saved` badge.
- When all generated summaries are already saved, the global button is disabled again.

Existing backend endpoint used:

```text
POST /api/manual-dispatch/final-summaries
```

The backend model remains per driver summary. The frontend global button simply coordinates multiple per-driver saves.

## Per-Card Save Removal
Generated driver final summary cards are read-only display cards.

Cards keep:
- Locked / Saved badge
- Dispatch Date
- Delivery Date
- Driver
- Rego #
- Total Pallets
- Total Loose Bags
- Trip 1 / Trip 2 tables

Cards do not include:
- Save Final Summary button
- Driver dropdown
- Trip dropdown
- Assign / Unassign controls
- Choose Vehicle dropdown
- Edit / Delete / Cancel controls

## Unsaved vs Saved Summaries
An unsaved summary is any generated preview without `summary_id`.

The global save action collects:

```javascript
Object.values(state.finalTripSummaries).filter((summary) => !summary.summary_id)
```

Saved summaries have `summary_id` from SQLite and are shown as locked historical records.

## Duplicate Save Handling
Before saving, the frontend checks existing saved final summaries for the relevant dispatch date, delivery date, and driver IDs.

If a duplicate exists, the Final Trip Summary section shows:

```text
Unable to save Final Trip Summary. Final Summary for this driver, dispatch date, and delivery date has already been saved.
```

The page does not crash, generated previews remain visible, and nothing is silently overwritten.

## Partial Save Behavior
The frontend saves summaries sequentially using the existing per-driver endpoint. If one save succeeds and a later save fails:
- Saved summaries remain marked `Saved`.
- Remaining unsaved summaries stay visible.
- A clear section-level error is shown.
- No client-side rollback is attempted because the backend API is not batch-transactional.

## Validation
Recommended checks:

```powershell
node --check frontend/app.js
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
git status --short
git diff --stat
```

## Excluded Work
This feature does not add:
- automatic assignment
- automatic driver or vehicle selection
- route optimization
- ETA calculation
- maps or geocoding
- CP-SAT or OR-Tools
- blocking rules
- auth/login
- MySQL/MariaDB
