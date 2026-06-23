# Change Manifest - Stage 4 Scoped Workspace Board APIs

**Task:** Separate Delivery and OP SHOP workspaces
**Completed:** 2026-06-23
**Files modified:** 6
**Files created:** 3
**Files deleted:** 0

## Changes

| Area | Files | Change |
|---|---:|---|
| Scoped response contracts | 1 | Added Delivery board, OP SHOP board, scoped pickup, and vehicle-lock dataclasses. |
| Scoped board services | 2 | Added independently testable Delivery-only and OP SHOP-only board construction. |
| Facade and API | 2 | Added three read-only scoped routes without changing legacy routes. |
| Tests | 1 | Added route shape, side-effect, isolation, lifecycle, and lock coverage. |
| Refactor governance | 3 | Updated scope allowlist, manifest, and session handoff. |

## Scope Compliance

- [x] Changed files are within the approved Stage 4 scoped-board/API scope.
- [x] No frontend, hash route, Workspace Home, or assignment mutation file changed.
- [x] No schema, repository, exporter, migration tool, or dependency changed.
- [x] Legacy `/board`, Final Summary, assignment APIs, and frontend behavior remain intact.
- [x] No runtime database, workbook, backup, output, or environment file was added.

## Domain Boundary Proof

- [x] Delivery board does not call legacy board or Regular OP SHOP ensure logic.
- [x] Delivery assignments contain only `ORDER` tasks.
- [x] OP SHOP board does not query Orders or Delivery vehicle assignments.
- [x] OP SHOP board retains idempotent Regular pickup generation.
- [x] Delivery reserved IDs come only from Delivery Run Sheets.
- [x] OP SHOP reserved IDs come only from OP SHOP Pickup Collections.
- [x] Generated snapshots hide captured tasks without creating saved lock entries.
- [x] Saved Delivery Run Sheets create Delivery vehicle lock entries.

## Drift Check

- Files touched: 9 (within the 20-file high-risk budget).
- New files are limited to two approved scoped services and one targeted test module.
- No unrelated cleanup, abstraction, endpoint mutation, or frontend behavior was added.

## Test Results

- Stage 4 targeted scoped-board tests: 6 passed.
- Legacy board/Final Summary/OP SHOP and workspace regressions: 120 passed.
- Full Python suite: 431 passed.
- Python compileall: `backend`, `tests`, and `tools` passed.
- Frontend JavaScript syntax: all files passed `node --check`.
- `git diff --check` and `git diff --cached --check` passed.
- New failures: none.
