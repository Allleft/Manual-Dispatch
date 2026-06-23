# Change Manifest - Stage 5 Scoped Workspace Mutation APIs

**Task:** Separate Delivery and OP SHOP workspaces
**Completed:** 2026-06-24
**Files modified:** 10
**Files created:** 3
**Files deleted:** 0

## Changes

| Area | Files | Change |
|---|---:|---|
| Request contracts | 1 | Added task-type-safe Delivery and OP SHOP mutation request dataclasses. |
| Independent lock helpers | 2 | Added generated/saved key and captured-task reservation checks. |
| Scoped mutation services | 2 | Added Delivery assignment/vehicle and OP SHOP assignment/route-group workflows. |
| Atomic persistence | 2 | Added narrow SQLite and in-memory OP SHOP assignment batch helpers. |
| Facade and API | 2 | Added seven scoped mutation routes without changing legacy routes. |
| Tests | 1 | Added HTTP contracts, lock states, atomicity, isolation, and board refresh coverage. |
| Refactor governance | 3 | Updated scope allowlist, manifest, and session handoff. |

## Scope Compliance

- [x] Changed files are within the approved Stage 5 mutation/API scope.
- [x] No frontend, hash route, Workspace Home, deployment, or migration-apply file changed.
- [x] No database schema, dependency, legacy route, or legacy service behavior changed.
- [x] Legacy `/board`, Final Summary, assignment, vehicle, and OP SHOP routes remain intact.
- [x] No runtime database, workbook, backup, output, or environment file was added.

## Lock and Isolation Proof

- [x] Generated Delivery Run Sheets block captured task changes, target assignments,
  and vehicle assign/clear until cancellation.
- [x] Saved Delivery Run Sheets enforce the same boundaries with a saved-state error.
- [x] Generated and saved OP SHOP Collections block captured pickup changes and target
  assignments without inspecting Delivery state.
- [x] Delivery mutations do not inspect OP SHOP Collections or legacy Final Summary locks.
- [x] OP SHOP mutations do not inspect Delivery Run Sheets or legacy Final Summary locks.
- [x] A saved Delivery Run Sheet does not block OP SHOP assignment.
- [x] A saved OP SHOP Collection does not block Delivery assignment or vehicle selection.

## Transaction Proof

- [x] OP SHOP batch requests preflight every row before persistence.
- [x] Countryside route groups preflight every membership before persistence.
- [x] SQLite task and assignment changes share one transaction and one commit.
- [x] In-memory batch persistence restores task and assignment collections on failure.
- [x] Tests prove an invalid batch row and a reserved route membership cause no partial writes.

## Drift Check

- Files touched: 13 (within the 20-file Stage 5 budget).
- New files are limited to two scoped mutation services and one targeted test module.
- No unrelated cleanup, frontend behavior, schema migration, or exporter change was added.

## Test Results

- Stage 5 targeted scoped-mutation tests: 10 passed.
- Stage 2/4/5 workspace regression set: 22 passed.
- Full Python suite: 441 passed.
- Python compileall: `backend`, `tests`, and `tools` passed.
- Frontend JavaScript syntax: all files passed `node --check`.
- `git diff --check` and `git diff --cached --check` passed.
- New failures: none.
