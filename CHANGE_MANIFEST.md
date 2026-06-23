# Change Manifest - Workspace Snapshot Persistence Pilot

**Task:** Separate Delivery and OP SHOP workspaces
**Completed:** 2026-06-23
**Files modified:** 4
**Files created:** 6
**Files deleted:** 0

## Changes

| File | Change | Notes |
|---|---|---|
| `backend/db/schema.sql` | Schema | Added four additive snapshot tables and independent uniqueness constraints. |
| `backend/schemas.py` | Models | Added independent Delivery Run Sheet and OP SHOP Pickup Collection snapshots. |
| `backend/repositories/sqlite_manual_dispatch_repository.py` | Persistence | Added transactional CRUD and child-row hydration for both snapshot modules. |
| `backend/repositories/in_memory_manual_dispatch_repository.py` | Persistence | Added matching in-memory repository contract. |
| `tests/test_workspace_snapshot_persistence.py` | Tests | Covers idempotency, legacy readability, coexistence, replacement, and parity. |
| `docs/separate-delivery-and-opshop-workspaces-spec.md` | Governance | Persisted the approved task boundary and acceptance criteria. |
| `.refactor-scope-allowlist` | Governance | Defines the pilot's allowed file set. |
| `.refactor-session.md` | Handoff | Records progress and the next atomic batch. |
| `OBSERVATIONS.md` | Governance | Records out-of-scope observations without acting on them. |
| `CHANGE_MANIFEST.md` | Governance | Records scope and verification evidence for this pilot. |

## Scope Compliance

- [x] Every modified file is required by the approved persistence pilot or refactor protocol.
- [x] No dependency was added, removed, or upgraded.
- [x] No existing table, API route, response field, or frontend behavior was changed.
- [x] No runtime database, workbook, backup, output, or local environment file was added.
- [x] Legacy Final Summary tables and repository behavior remain intact.

## Test Results

- Before: 54 repository and legacy Final Summary tests passed.
- Targeted after: 58 tests passed, including 4 new independent persistence tests.
- Full after: 399 tests passed.
- Frontend JavaScript syntax: all files passed `node --check`.
- Python compile check: `backend`, `tests`, and `tools` passed.
- New failures: none.
- Pre-existing failures: none observed in the targeted baseline.
