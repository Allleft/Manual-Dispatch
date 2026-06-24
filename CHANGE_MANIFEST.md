# Change Manifest - Stage 6A Workspace Frontend Shell

**Task:** Separate Delivery and OP SHOP workspaces
**Completed:** 2026-06-24
**Files modified:** 10
**Files created:** 6
**Files deleted:** 0

## Changes

| Area | Files | Change |
|---|---:|---|
| Workspace routing | 2 | Added authenticated hash routing, Home default, and legacy redirects. |
| Scoped read client/state | 3 | Added five scoped GET clients and independent workspace state/loading errors. |
| Workspace renderers | 5 | Added Home, header navigation, Delivery, and OP SHOP read-only presentation. |
| Visual shell | 2 | Added single-page mount point and responsive white blue/green workspace styling. |
| Auth boundary | 2 | Added post-auth Home navigation and protected both application shells. |
| Tests | 1 | Added route, endpoint isolation, source boundary, and title contract coverage. |
| Refactor governance | 3 | Updated scope allowlist, manifest, and session handoff. |

## Scope Compliance

- [x] Changed files are within the approved Stage 6A frontend/read-only scope.
- [x] No backend schema, service, route, migration, exporter, or deployment file changed.
- [x] No scoped or legacy mutation action is wired into the new workspace shell.
- [x] Legacy renderers and actions remain available in source for later controlled reuse.
- [x] No dependency, runtime database, workbook, backup, screenshot, or output was added.

## Routing and Read Boundary Proof

- [x] Login success opens `#home`; invalid/empty hashes resolve safely to Home.
- [x] All nine workspace child routes are refreshable hash routes.
- [x] Three legacy hashes replace to their approved Delivery equivalents.
- [x] Home returns before any scoped board request.
- [x] Delivery loader contains no OP SHOP board/collection call.
- [x] OP SHOP loader contains no Delivery board/run-sheet call.
- [x] New workspace source contains no legacy board or Final Summary endpoint call.
- [x] Delivery renderer contains no OP SHOP labels or payload fields.
- [x] OP SHOP renderer contains no Delivery order, invoice, load, vehicle, or trip fields.

## Browser QA

- [x] Real UI login opens Workspace Home.
- [x] Both workspace cards navigate to the correct scoped page.
- [x] Every required route renders and survives refresh.
- [x] Request logging proves Delivery and OP SHOP boards do not cross-load.
- [x] Legacy hashes and invalid hashes redirect correctly.
- [x] Logout hides workspace content and returns to the login gate.
- [x] Browser console errors: 0.

## Drift Check

- Files touched: 16 (within the 20-file Stage 6A budget).
- New files are limited to the approved read-only action/renderers and targeted test.
- No unrelated cleanup, mutation UI, backend behavior, or deployment change was added.

## Test Results

- Stage 6A frontend shell tests: 10 passed.
- Existing frontend static contracts: 24 passed.
- Python compile check: passed for `backend`, `tests`, and `tools`.
- Full Python test suite: 451 passed.
- Frontend JavaScript syntax checks: passed for `frontend/app.js` and every
  `frontend/**/*.js` file.
- Git whitespace checks: working tree and staged diff checks passed.
