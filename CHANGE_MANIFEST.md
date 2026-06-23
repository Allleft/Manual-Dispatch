# Change Manifest - Stage 3 Legacy Workspace Migration

**Task:** Separate Delivery and OP SHOP workspaces
**Completed:** 2026-06-23
**Files modified:** 4
**Files created:** 3
**Files deleted:** 0

## Changes

| Area | Files | Change |
|---|---:|---|
| Migration tool | 1 | Added read-only dry-run plus guarded, backed-up, atomic apply. |
| Migration tests | 1 | Added real SQLite coverage for mapping, blockers, rollback, and idempotency. |
| Operator documentation | 2 | Added migration/rollback runbook and README commands. |
| Refactor governance | 3 | Updated scope allowlist, manifest, and session handoff. |

## Scope Compliance

- [x] Changed files are within the approved Stage 3 migration/documentation scope.
- [x] No frontend, scoped board API, workspace route, or assignment file changed.
- [x] No schema, repository, domain service, exporter, or dependency changed.
- [x] Legacy Final Summary tables, APIs, services, exports, and live rows remain intact.
- [x] No runtime database, workbook, backup, output, or environment file was added.

## Safety Contract

- [x] Default mode opens SQLite read-only and performs no writes.
- [x] Apply requires both `--apply` and `--yes`.
- [x] A timestamped SQLite backup must pass `PRAGMA integrity_check` before writes.
- [x] Legacy `GENERATED` summaries and all detected conflicts block the entire apply.
- [x] All migration writes occur in one transaction and roll back together.
- [x] Matching `legacy_summary_id` markers are skipped unchanged on rerun.
- [x] Historical OP SHOP rows are not enriched from mutable live records.

## Drift Check

- Files touched: 7 (within the 20-file high-risk budget).
- New code is limited to one migration tool and one targeted test module.
- No unrelated cleanup, abstraction, endpoint, or user-facing behavior was added.

## Test Results

- Stage 3 targeted migration tests: 15 passed.
- Legacy Final Summary/API and workspace regression tests: 66 passed.
- Full Python suite: 425 passed.
- Python compileall: `backend`, `tests`, and `tools` passed.
- Frontend JavaScript syntax: all files passed `node --check`.
- `git diff --check` and `git diff --cached --check` passed.
- New failures: none.
