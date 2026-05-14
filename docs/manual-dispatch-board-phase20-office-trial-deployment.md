# Manual Dispatch Board Phase 20: Office Trial Deployment and Backup

## Purpose

Phase 20 prepares Manual Dispatch Board for office trial use after Phase 19 release-candidate QA. This phase focuses on local startup, SQLite backup, restore instructions, runtime configuration, and office operating checklists.

This phase does not add automatic assignment, route optimization, ETA, maps, geocoding, CP-SAT, MySQL/MariaDB, auth redesign, major UI redesign, order import, or new dispatch logic.

## Start the App

Run these commands from the repository root in Windows PowerShell:

```powershell
.\tools\start_office_trial.ps1
```

Default startup values:

- Host: `127.0.0.1`
- Port: `8130`
- Browser URL: `http://127.0.0.1:8130/frontend/`
- Runtime SQLite database: `data/manual_dispatch.sqlite3`

Optional parameters:

```powershell
.\tools\start_office_trial.ps1 -Port 8131
.\tools\start_office_trial.ps1 -Host 127.0.0.1 -Port 8130
```

If the port is already in use, the script prints a clear message and suggests another port. It does not kill unknown processes.

The script checks Python environments before startup. It prefers `.venv\Scripts\python.exe` when that environment has the required FastAPI/Uvicorn runtime support. If that local virtual environment exists but is not usable, the script skips it and tries the local route-test environment or Python on `PATH`.

## Stop the App

In the PowerShell window running the backend, press:

```text
Ctrl+C
```

Wait for Uvicorn to stop before closing the terminal.

## Runtime Configuration

Runtime settings can be configured with environment variables or a local `.env` file.

Example values are documented in `.env.example`:

```text
MANUAL_DISPATCH_DB_PATH=data/manual_dispatch.sqlite3
MANUAL_DISPATCH_HOST=127.0.0.1
MANUAL_DISPATCH_PORT=8130
MANUAL_DISPATCH_ADMIN_RESET_CODE=replace-with-your-local-admin-reset-code
```

Do not commit a real `.env` file. Do not commit real reset codes, passwords, or secrets.

## Database Location

The default runtime SQLite database is:

```text
data/manual_dispatch.sqlite3
```

Runtime database files are local operational data and are ignored by Git.

## Backup the Database

Create a timestamped backup:

```powershell
.\tools\backup_sqlite_db.ps1
```

Default behavior:

- Source: `data/manual_dispatch.sqlite3`
- Backup folder: `backups/`
- Filename format: `manual_dispatch_YYYYMMDD_HHMMSS.sqlite3`
- Existing backups are not overwritten.

If the runtime database is missing, the script reports:

```text
Runtime database not found: data/manual_dispatch.sqlite3
```

Backup files under `backups/` are ignored by Git.

## Restore the Database

Restore from a known-good backup:

```powershell
.\tools\restore_sqlite_db.ps1 -BackupPath .\backups\manual_dispatch_YYYYMMDD_HHMMSS.sqlite3
```

Restore behavior:

- Confirms the target runtime database path.
- Prompts for `YES` unless `-Force` is supplied.
- Creates a before-restore backup of the current runtime database if one exists.
- Copies the selected backup to `data/manual_dispatch.sqlite3`.
- Never deletes backup files.

Use restore only when the office trial machine is not actively being used for dispatching.

## Daily Checklist

Before use:

- Start backend with `.\tools\start_office_trial.ps1`.
- Open `http://127.0.0.1:8130/frontend/`.
- Log in.
- Confirm Dispatch Date.
- Confirm Drivers and Vehicles are available.
- Confirm Task Pool loads.

During use:

- Add Orders.
- Assign Orders to Drivers and Trips.
- Choose Vehicles.
- Generate Final Trip Summary.
- Save and Export.
- Confirm Excel downloads.
- Load History if needed.

After use:

- Run `.\tools\backup_sqlite_db.ps1`.
- Confirm a timestamped backup file exists under `backups/`.
- Do not delete the runtime database.
- Stop the backend with `Ctrl+C` if the machine is no longer in use.

## Emergency Recovery Notes

- If the board will not start, check whether another process is already using the configured port.
- If the runtime database is missing, restore from the latest known-good backup.
- If the wrong backup is restored, use the automatically created `manual_dispatch_before_restore_*.sqlite3` backup to recover the previous runtime database.
- Keep multiple dated backups during the office trial.
- Do not edit SQLite files manually while the backend is running.

## Known Limitations

- Manual Dispatch Board remains a manual workflow.
- No automatic route optimization, ETA, maps, geocoding, CP-SAT, automatic driver selection, or automatic vehicle selection exists.
- SQLite is file-based and must be backed up.
- Office trial use should stay on one primary machine unless a shared deployment is explicitly configured later.
- The MVP login system is lightweight and not production-grade enterprise authentication.

## Excluded Work

Phase 20 intentionally excludes:

- Automatic assignment.
- Route optimization.
- ETA calculation.
- Google Maps or geocoding.
- CP-SAT or optimization engines.
- MySQL/MariaDB migration.
- Auth redesign.
- Major UI redesign.
- Order import.
- New dispatch logic.
