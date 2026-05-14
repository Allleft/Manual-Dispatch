# NAS Deployment Validation Checklist

Use this checklist before office users rely on the NAS deployment.

## Deployment Checks

- Docker Compose config is valid.
- Docker image builds successfully.
- Container starts.
- Only one app instance is running.
- Persistent `./data:/app/data` volume is mounted.
- Persistent `./backups:/app/backups` volume is mounted.

## Health and Access Checks

- `/health` returns `{"status":"ok"}`.
- `/frontend/` opens.
- `/api/manual-dispatch/board?dispatch_date=YYYY-MM-DD` returns JSON.
- Direct NAS IP access works from at least two office computers.
- Internal DNS access works if configured.
- Reverse proxy preserves same-origin paths if configured:
  - `/frontend/`
  - `/api/manual-dispatch/`
  - `/health`

## Account Setup Checks

- First account setup procedure is documented.
- Registration can be temporarily enabled with `MANUAL_DISPATCH_ALLOW_REGISTRATION=true`.
- Registration disabled behavior is verified when set to `false`.
- Login works.
- Password reset works when `MANUAL_DISPATCH_ADMIN_RESET_CODE` is configured.

## Manual Dispatch Workflow Checks

- Task Pool loads.
- Add Order works.
- Edit Order works.
- Cancel Order works.
- Driver & Vehicle Specification modal works.
- Assign works.
- Unassign works.
- Vehicle selection works.
- Final Summary generation works.
- Save and Export works.
- Excel download works.
- History loads.
- Existing data still exists after restart.

## Backup and Restore Checks

- `./tools/backup_sqlite_db.sh` creates a timestamped backup.
- Backup files are stored under `backups/`.
- Restore dry-run process is understood.
- Staff know to stop the app before restore.
- Staff know not to delete `data/manual_dispatch.sqlite3`.

## Safety Checks

- No public port-forwarding for `8130`.
- No public internet exposure without additional production security.
- No SQLite file sharing from client computers.
- No staging and production sharing the same SQLite file.
- Demo seed data is disabled for NAS deployment unless explicitly needed.
- Registration is disabled after initial account setup.
