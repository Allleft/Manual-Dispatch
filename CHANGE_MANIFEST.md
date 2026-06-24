# Change Manifest - Stage 6A.1 Workspace Safety Hardening

**Task:** Workspace migration safety, lifecycle atomicity, strict dates, and stale request protection
**Completed:** 2026-06-24
**Files modified:** 17
**Files created:** 2
**Files deleted:** 0

## Changes

| Area | Files | Change |
|---|---:|---|
| Migration readiness | 5 | Added exact legacy snapshot/marker inspection, typed guard service, facade guards, and status API. |
| Atomic lifecycle | 4 | Added conditional GENERATED-only Save/Cancel repository operations for both domains. |
| Date/race safety | 3 | Applied strict ISO generate/list validation and normalized duplicate Generate races. |
| Frontend request safety | 6 | Added migration status Home UX, independent request versions, and removed unused shared-spec reads. |
| Regression tests | 2 | Added backend/API atomicity/readiness coverage and real Node promise-interleaving tests. |
| Refactor governance | 3 | Updated allowlist, manifest, and session handoff. |

## Exact Migration Status Contract

```json
{
  "delivery_ready": true,
  "opshop_ready": true,
  "legacy_generated_summary_count": 0,
  "delivery_unmigrated_summary_count": 0,
  "opshop_unmigrated_summary_count": 0,
  "delivery_unmigrated_summary_ids": [],
  "opshop_unmigrated_summary_ids": []
}
```

## Guarded Scoped Routes

- `GET /api/manual-dispatch/delivery/board`
- `GET /api/manual-dispatch/opshop/board`
- `POST /api/manual-dispatch/delivery/assignments`
- `POST /api/manual-dispatch/delivery/assignments/unassign`
- `POST /api/manual-dispatch/delivery/vehicle-assignments`
- `POST /api/manual-dispatch/delivery/vehicle-assignments/clear`
- `POST /api/manual-dispatch/opshop/pickups/assignments/apply`
- `POST /api/manual-dispatch/opshop/pickups/assignments/unassign`
- `POST /api/manual-dispatch/opshop/countryside-route-groups/{route_group_id}/assign`
- `POST /api/manual-dispatch/delivery/run-sheets/generated`
- `GET /api/manual-dispatch/delivery/run-sheets`
- `POST /api/manual-dispatch/opshop/pickup-collections/generated`
- `GET /api/manual-dispatch/opshop/pickup-collections`

## Boundary Proof

- [x] Migration status is read-only and no real database migration was run.
- [x] Legacy `/board`, Final Summary routes/tables/locks/frontend, and exports are unchanged.
- [x] Shared specifications and the migration tool are not guarded.
- [x] Save changes only a GENERATED header and preserves all child snapshot rows.
- [x] Cancel cannot delete a snapshot already promoted to SAVED.
- [x] Repeated Save cannot replace saved metadata or child rows.
- [x] Duplicate Generate races return stable validation conflicts, not HTTP 500.
- [x] Stale Delivery/OP SHOP responses cannot write data, errors, loading state, or final renders.
- [x] Run Sheet/History and Collection/History do not request shared specifications.
- [x] No Stage 6B mutation UI was wired.
- [x] No schema, deployment, dependency, runtime database, backup, or output file changed.

## Browser QA

- [x] Clean temporary DB enabled both workspace cards.
- [x] Legacy SAVED OP SHOP snapshot disabled only OP SHOP.
- [x] Legacy board and Final Summary list remained HTTP 200 while scoped OP SHOP returned 409.
- [x] Matching independent marker restored both workspaces to ready.
- [x] History pages loaded with shared specifications deliberately unavailable.
- [x] Browser console errors: 0.
- [x] Temporary script/database/WAL/SHM artifacts removed.

## Drift Check

- Files touched: 19 (within the 20-file Stage 6A.1 budget).
- Product/test files: 16; governance files: 3.
- No unrelated cleanup or mutation UI was added.

## Test Results

- Stage 6A.1 focused backend/frontend tests: 23 passed.
- Existing workspace backend regression subset after backend changes: 31 passed.
- Full Python test suite: 464 passed.
- Python compile check: passed for `backend`, `tests`, and `tools`.
- Frontend JavaScript syntax checks: passed for `frontend/app.js` and every `frontend/**/*.js` file.
- Git working-tree and staged whitespace checks: passed.
