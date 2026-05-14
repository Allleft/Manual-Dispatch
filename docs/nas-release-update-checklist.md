# NAS Release Update Checklist

## A. Purpose

Use this checklist to safely update Manual Dispatch Board code on the NAS without losing SQLite business data.

## B. Golden Rule

- Code updates go through Git.
- Business data is protected by SQLite backups.
- Do not manually edit runtime files inside the container.
- Do not update production without a database backup.
- Never replace the production SQLite file with a demo database.

## C. Recommended Environments

- Production: port `8130`.
- Optional test/staging: port `8131` with a separate database path.
- Staging and production must never share the same SQLite file.

Example staging DB path:

```text
/app/data/manual_dispatch_staging.sqlite3
```

## D. Pre-Update Checklist

Before updating:

- Confirm current branch and commit.
- Confirm the app is working before update.
- Confirm no one is actively dispatching.
- Create a SQLite backup.
- Record the backup filename.
- Confirm enough disk space.

Useful commands:

```sh
git branch --show-current
git log -1 --oneline
./tools/backup_sqlite_db.sh
```

## E. Docker / NAS Update Steps

Example commands:

```sh
cd /volume1/docker/manual-dispatch/app
./tools/backup_sqlite_db.sh
git fetch origin
git checkout deployment/nas-internal-office-release
git pull origin deployment/nas-internal-office-release
docker compose down
docker compose up -d --build
```

Do not run multiple replicas. SQLite expects one app instance.

## F. Post-Update Validation

After updating, verify:

- `/health` returns `{"status":"ok"}`.
- `/frontend/` opens.
- Login works.
- Task Pool loads.
- Add Order works.
- Assign works.
- Unassign works.
- Vehicle selection works.
- Generate Final Trip Summary works.
- Save and Export works.
- Excel download works.
- History loads.
- Existing data still exists.
- Backup script still works.

Example checks:

```sh
curl http://127.0.0.1:8130/health
./tools/backup_sqlite_db.sh
```

## G. Rollback Procedure

If an update fails:

1. Stop the app.
2. Checkout the previous known-good commit or tag.
3. Rebuild and restart.
4. If data was corrupted, restore the pre-update database backup.
5. Validate again.

Example:

```sh
docker compose down
git checkout <known-good-commit-or-tag>
docker compose up -d --build
```

Restore only when needed:

```sh
./tools/restore_sqlite_db.sh ./backups/manual_dispatch_YYYYMMDD_HHMMSS.sqlite3
```

## H. Database Migration Warning

If future code changes alter schema:

- Backup first.
- Add migration logic and documentation.
- Test migration on staging or a copy of the database.
- Never replace the production SQLite file with a seeded demo database.

## I. Release Tags

Tag stable office releases:

```sh
git tag release-office-v1
git push origin release-office-v1
```

For later releases:

```text
release-office-v1.1
release-office-v1.2
```

Always record the exact deployed commit.
