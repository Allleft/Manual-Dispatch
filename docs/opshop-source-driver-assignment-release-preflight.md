# OP SHOP Source-Driver Assignment Release Preflight

This document prepares Stage 6D.6F source-driver assignment behavior and the Stage 6D.6G Regular Task Pool for an operator-controlled production release. **Stage 6D.6H does not run a production dry-run or apply.**

## Scope and Behavior

The source workbooks maintain the intended default driver for Regular and Oncall templates. A default is materialized as an actual `OPSHOP_PICKUP` assignment only:

1. by the controlled source-driver backfill for a safely matched, current/future, editable, unassigned task; or
2. when a new Regular or template-derived Oncall task is first created from a template with a valid default driver.

The persisted assignment immediately appears in Current Assignee, Assigned To, and OP SHOP Trip Summary. It is not a frontend pending change and does not require `Apply Assignment Changes`.

The following are not automatic:

- creating an Oncall template does not create a pickup task;
- ad hoc/no-default Oncall tasks remain Unassigned;
- existing user assignments are never replaced by the backfill;
- a persisted manual reassignment or Unassign is not recreated on GET, refresh, route change, or render;
- no route optimization, balancing, auto-dispatch, or automatic reallocation is performed.

`Apply Assignment Changes` remains the persistence boundary for later user-initiated Task Pool edits.

## Matching Safety Rules

`tools/backfill_opshop_source_driver_assignments.py` uses normalized:

- pickup category (`REGULAR` or `ON_CALL`);
- company name;
- suburb;
- street address;
- source sheet/run day.

Company-name-only matching is rejected. A weaker identity is accepted only when the source and template resolve uniquely and share a non-empty matching suburb or address. Apply is refused when any ambiguous match, conflicting default, or unknown driver alias remains.

Approved aliases are:

| Workbook alias | Canonical driver |
| --- | --- |
| `John G` | John Georgiadis |
| `Gavin` | Gavin Fynn |
| `Nonda` | Epaminondas Tsatsoulis |
| `LEE` | Guanlin Li |

Friday-specific Nonda identities and generic/no-fixed-day Gavin identities remain separate even when company and address match.

## Oncall Source-Row Forensics

The workbook contains **73 non-empty source data rows** across MON, TUE, WED, THU, FRI, and Gavin. The backfill intentionally counts **68 operational rows** because it requires `Status=Active` and a non-false `Active_Flag`.

The exact five excluded rows are:

| Sheet | Excel row | Source name | Classification | Exact reason | Default driver? | Code fix? |
| --- | ---: | --- | --- | --- | --- | --- |
| TUE | 6 | AUSSIE VETERANS OP SHOP | `SKIPPED_BY_IMPORTER_RULE` | `Status=On_Hold`; backfill accepts Active rows only. | No, not while On Hold. | No |
| WED | 3 | STRATHALAN OP SHOP **ON HOLD** | `SKIPPED_BY_IMPORTER_RULE` | `Status=On_Hold`; backfill accepts Active rows only. | No, not while On Hold. | No |
| WED | 10 | ST JOHNS OP SHOP | `SKIPPED_BY_IMPORTER_RULE` | `Status=On_Hold`; backfill accepts Active rows only. | No, not while On Hold. | No |
| THU | 20 | UNITING CHURCH OPSHOP | `SKIPPED_BY_IMPORTER_RULE` | `Status=On_Hold`; backfill accepts Active rows only. | No, not while On Hold. | No |
| FRI | 12 | ST CHADS OP SHOP (LONG BEACH) | `SKIPPED_BY_IMPORTER_RULE` | `Status=On_Hold`; backfill accepts Active rows only. | No, not while On Hold. | No |

The complete local ledger generated during Stage 6D.6H accounted for all 73 rows: 68 `VALID_ASSIGNABLE_SOURCE` and five `SKIPPED_BY_IMPORTER_RULE`. It is intentionally kept under ignored `tmp/` and is not committed because it contains office source data.

Overlap verification:

- WE CARE COMMUNITY SERVICES: FRI/Nonda uses run day `FRIDAY`; Gavin uses generic/no-fixed-day.
- YOORALLA OP SHOP: FRI/Nonda uses run day `FRIDAY`; Gavin uses generic/no-fixed-day.
- ST CHADS OP SHOP (LONG BEACH): FRI/Nonda is On Hold and excluded; generic Gavin is Active and remains a distinct valid identity.

No importer or backfill defect was found. The operational count rule is exact and production preflight may proceed to a dry-run after the approval prerequisites below are met.

## Browser UAT Status

Stage 6D.6H used the ignored QA copy `tmp/manual_dispatch_full_test_release_preflight_qa.sqlite3`; it did not open or mutate the source database during browser interactions. The source database SHA256 remained `7A8DD9021FA59B8705B4E578ECDAECCB7B463081C612496B1F9ED9F58984064A` before and after QA.

Completed browser evidence:

- the Regular Task Pool rendered 79 persisted assignments with zero unassigned rows and zero pending changes;
- Current Assignee and Assigned To showed canonical persisted source drivers;
- past date groups defaulted collapsed while the selected Dispatch Date and future groups defaulted expanded;
- collapsing and expanding a date group preserved the settled modal scroll position and caused no server request.

The browser connection timed out during the first manual Regular reassignment check and timed out again after the single allowed clean browser/application restart. Manual reassignment/Unassign persistence, Oncall, Trip Summary, Pickup Collections, Delivery workspace regression, and a complete zero-error console/page-error pass therefore remain **not completed**. This stage must remain blocked for manual UAT completion; automated coverage does not replace these checks.

## Dry-Run Before Apply

Dry-run is mandatory and performs read-only database access. Review the JSON report row by row before considering apply.

Apply must not proceed unless:

- ambiguous count is `0`;
- conflict count is `0`;
- unknown driver alias count is `0`;
- source counts match the approved ledger (`62` Regular and `68` Oncall for the audited workbooks);
- expected task assignment count is manually approved;
- no existing assignment is proposed for replacement;
- backup and restore procedures have been verified;
- the operator explicitly approves apply.

## Production Approval Gate

The operator must record:

- exact Git commit;
- source workbook SHA256 checksums;
- production database SHA256 before apply;
- backup filename, size, integrity result, and restore test evidence;
- reviewed dry-run report path and reviewer;
- approved `--from-date`;
- expected template/task update counts;
- explicit apply approval and timestamp.

## Production Runbook

These commands are templates only. Confirm every placeholder from the active deployment before use.

### 1. Preconditions

- [ ] Deploy commit reviewed and recorded: `<DEPLOY_COMMIT>`.
- [ ] GitHub CI status checked manually.
- [ ] Office-user visual UAT completed.
- [ ] No staff are actively dispatching.
- [ ] Regular and Oncall workbook checksums recorded.
- [ ] Oncall 73/68 result accepted as five On-Hold exclusions.
- [ ] Production dry-run report reviewed and approved.
- [ ] Explicit operator approval obtained before apply.

### 2. Backup

Confirm `<APP_DIRECTORY>`, `<CONTAINER_NAME>`, `<PRODUCTION_DB_PATH>`, and `<BACKUP_DIRECTORY>` from the live deployment. Do not assume examples from older deployment documents are current.

Example host-side preparation:

```sh
cd <APP_DIRECTORY>
timestamp=$(date +%Y%m%d_%H%M%S)
backup=<BACKUP_DIRECTORY>/manual_dispatch_before_source_driver_${timestamp}.sqlite3
mkdir -p <BACKUP_DIRECTORY>
sha256sum <PRODUCTION_DB_PATH> > <BACKUP_DIRECTORY>/production_db_before_${timestamp}.sha256
```

Preferred SQLite online backup when `sqlite3` can access the mounted DB:

```sh
sqlite3 <PRODUCTION_DB_PATH> ".backup '$backup'"
sqlite3 "$backup" "PRAGMA integrity_check;"
stat -c "%n %s bytes" "$backup"
sha256sum "$backup"
```

Container variant, only after confirming paths inside the container:

```sh
docker exec <CONTAINER_NAME> sh -lc 'sqlite3 <PRODUCTION_DB_PATH> ".backup <BACKUP_DIRECTORY>/manual_dispatch_before_source_driver_<TIMESTAMP>.sqlite3"'
```

If SQLite CLI is unavailable, follow the repository NAS backup guidance and stop the service before a fallback file copy when WAL sidecars exist. Never copy only the main DB while live WAL data may be pending.

Restore example for a tested backup:

```sh
sqlite3 <PRODUCTION_DB_PATH> ".restore '$backup'"
sqlite3 <PRODUCTION_DB_PATH> "PRAGMA integrity_check;"
```

Repository helpers may be used where their confirmed environment matches:

```sh
./tools/backup_sqlite_db.sh
./tools/restore_sqlite_db.sh <BACKUP_DIRECTORY>/manual_dispatch_<TIMESTAMP>.sqlite3
```

### 3. Deployment

```sh
cd <APP_DIRECTORY>
git fetch origin
git checkout <DEPLOY_COMMIT>
test "$(git rev-parse HEAD)" = "<DEPLOY_COMMIT>"
```

Build/restart according to the confirmed deployment process, for example:

```sh
docker compose down
docker compose up -d --build
```

Then verify:

```sh
curl http://127.0.0.1:<PORT>/health
```

Confirm the running process/container uses `<PRODUCTION_DB_PATH>` and that no QA/test DB is mounted. Keep one app instance for SQLite.

### 4. Production Dry-Run

Run from the deployed application environment with confirmed paths:

```sh
python tools/backfill_opshop_source_driver_assignments.py \
  --regular-workbook "<PRODUCTION_REGULAR_WORKBOOK_PATH>" \
  --oncall-workbook "<PRODUCTION_ONCALL_WORKBOOK_PATH>" \
  --db-path "<PRODUCTION_DB_PATH>" \
  --from-date "<APPROVED_FROM_DATE_YYYY-MM-DD>" \
  --dry-run \
  --report-path "<DRY_RUN_REPORT_PATH>"
```

Review the terminal totals and every report record. **Do not continue automatically from dry-run to apply.** Obtain the separate approval gate above.

### 5. Production Apply

> **DO NOT RUN UNTIL THE DRY-RUN REPORT IS APPROVED.**

Command template only:

```sh
python tools/backfill_opshop_source_driver_assignments.py \
  --regular-workbook "<PRODUCTION_REGULAR_WORKBOOK_PATH>" \
  --oncall-workbook "<PRODUCTION_ONCALL_WORKBOOK_PATH>" \
  --db-path "<PRODUCTION_DB_PATH>" \
  --from-date "<APPROVED_FROM_DATE_YYYY-MM-DD>" \
  --apply \
  --report-path "<APPLY_REPORT_PATH>"
```

The tool must refuse blocking findings and creates a timestamped backup before writes. A failed operation must be treated as incomplete until the report, database integrity, and UI are inspected.

After a successful approved apply:

```sh
python tools/backfill_opshop_source_driver_assignments.py \
  --regular-workbook "<PRODUCTION_REGULAR_WORKBOOK_PATH>" \
  --oncall-workbook "<PRODUCTION_ONCALL_WORKBOOK_PATH>" \
  --db-path "<PRODUCTION_DB_PATH>" \
  --from-date "<APPROVED_FROM_DATE_YYYY-MM-DD>" \
  --dry-run \
  --report-path "<POST_APPLY_DRY_RUN_REPORT_PATH>"

sqlite3 <PRODUCTION_DB_PATH> "PRAGMA integrity_check;"
sha256sum <PRODUCTION_DB_PATH> > <BACKUP_DIRECTORY>/production_db_after_<TIMESTAMP>.sha256
```

Post-apply dry-run must show `TEMPLATE_WILL_UPDATE=0` and `TASK_WILL_ASSIGN=0`.

### 6. Rollback

If results differ from the approved report:

1. stop the service;
2. preserve the unexpected database and reports for diagnosis;
3. restore the verified pre-apply SQLite backup;
4. run `PRAGMA integrity_check`;
5. restart the service;
6. verify assignments match the pre-apply state.

Example:

```sh
cd <APP_DIRECTORY>
docker compose down
sqlite3 <PRODUCTION_DB_PATH> ".restore '<BACKUP_FILE>'"
sqlite3 <PRODUCTION_DB_PATH> "PRAGMA integrity_check;"
docker compose up -d
```

### 7. Post-Apply Smoke Checklist

- [ ] Regular Current Assignee and Assigned To show approved canonical drivers.
- [ ] Oncall Current Assignee and Assigned To show approved canonical drivers.
- [ ] OP SHOP Trip Summary places pickups under the correct driver/date/category.
- [ ] No unexpected assignment replacement occurred.
- [ ] Manually Unassign one approved test task; refresh and confirm it remains Unassigned.
- [ ] Generated/Saved Pickup Collection locks remain intact.
- [ ] Delivery Task Pool, Trip Summary, and Run Sheets still work.
- [ ] Browser console/page errors are `0`.

Follow [the OP SHOP workspace smoke checklist](opshop-workspace-smoke-test-checklist.md) and [the NAS release update checklist](nas-release-update-checklist.md).

## Rollback Principle

Rollback restores the verified pre-apply SQLite backup and the previously deployed known-good commit. Do not attempt to reverse assignments manually row by row in production; preserve reports and the unexpected DB for investigation.

## Stage 6D.6H Statement

Stage 6D.6H performed documentation correction, source-row audit, and partial copied-database UAT only. **No production dry-run or production apply was executed.**
