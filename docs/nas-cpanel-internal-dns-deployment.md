# NAS and Internal DNS Deployment

## Overview

For office deployment, the NAS or office server is the application server. FastAPI serves both the static frontend and the API from the same app instance.

Recommended access pattern:

```text
Office PCs -> browser -> NAS URL -> FastAPI app -> SQLite
```

Office computers should access the board only through a browser. SQLite must stay on the NAS local volume and must not be opened directly from client computers or a shared folder.

## Recommended Architecture

- Application server: Synology NAS or office server.
- App process: one FastAPI/Uvicorn instance.
- Frontend: served from `/frontend/` by FastAPI.
- API: served from `/api/manual-dispatch/...` by the same FastAPI app.
- Health check: `/health`.
- Database: SQLite file on NAS local storage, for example `/app/data/manual_dispatch.sqlite3`.

Do not run multiple app replicas by default because SQLite is the database.

## cPanel Role

cPanel should not host the frontend separately and should not be treated as the main application server.

cPanel may help with DNS/domain management if that fits the office network, but the app itself should run on the NAS or office server.

Prefer internal-only options:

- Local router DNS.
- Synology DNS Server.
- Internal host override.
- NAS reverse proxy with an internal hostname.

Avoid exposing the private NAS service to the public internet.

## Internal Access Options

Direct NAS IP:

```text
http://NAS_IP:8130/frontend/
```

Internal DNS with port:

```text
http://dispatch.example.com.au:8130/frontend/
```

NAS reverse proxy:

```text
http://dispatch.example.com.au/frontend/
```

## Synology Reverse Proxy Notes

If using Synology reverse proxy:

- Source hostname: internal dispatch domain.
- Source port: `80` or `443`.
- Destination host: `127.0.0.1` or the Docker/container service.
- Destination port: `8130`.

Keep these paths same-origin:

- `/frontend/`
- `/api/manual-dispatch/`
- `/health`

Do not split the frontend onto cPanel while pointing API calls to the NAS. The app is designed to be same-origin friendly.

## Docker Compose Deployment

Copy `.env.nas.example` to `.env` on the NAS and set strong, independent reset
and authentication-cookie secrets:

```sh
cp .env.nas.example .env
```

Required NAS defaults:

```text
MANUAL_DISPATCH_DB_PATH=/app/data/manual_dispatch.sqlite3
MANUAL_DISPATCH_HOST=0.0.0.0
MANUAL_DISPATCH_PORT=8130
MANUAL_DISPATCH_AUTH_COOKIE_SECRET=<strong-random-secret>
MANUAL_DISPATCH_AUTH_COOKIE_SECURE=false
MANUAL_DISPATCH_ALLOW_REGISTRATION=false
MANUAL_DISPATCH_SEED_DEMO_DATA=false
```

Start the app:

```sh
docker compose up -d --build
```

Open:

```text
http://NAS_IP:8130/frontend/
```

## First Account Setup

Registration is disabled by default in the NAS example.

For first account setup:

1. Temporarily set `MANUAL_DISPATCH_ALLOW_REGISTRATION=true` in `.env`.
2. Restart the app.
3. Register the initial operator account from the browser.
4. Set `MANUAL_DISPATCH_ALLOW_REGISTRATION=false`.
5. Restart the app again.

Password reset still works when `MANUAL_DISPATCH_ADMIN_RESET_CODE` is configured.
The cookie secret is required by Docker Compose and must remain stable across
restarts. Set `MANUAL_DISPATCH_AUTH_COOKIE_SECURE=true` when the NAS is exposed
to browsers through an HTTPS reverse proxy; keep it `false` for direct HTTP.

## Backup Notes

Create daily backups:

```sh
./tools/backup_sqlite_db.sh
```

Backups are stored under:

```text
backups/
```

The backup script is WAL-safe when the `sqlite3` CLI is available. It uses SQLite's `.backup` command, which is preferred for live SQLite databases.

If `sqlite3` is not available, the script falls back to file copy. When WAL sidecar files are present, it copies the main database plus `-wal` and `-shm` files and prints a warning. For the safest fallback file-copy backup, stop the app first.

Consider copying backups to another NAS folder or an external backup target. Do not commit backup files to Git.

Stop the app before restoring a database:

```sh
./tools/restore_sqlite_db.sh ./backups/manual_dispatch_YYYYMMDD_HHMMSS.sqlite3
```

After creating a backup, periodically test restore on a staging database or separate copy. Do not test restores against the active production SQLite file while office users are dispatching.

## One-Off Driver and Vehicle Master Data Import

If the NAS database was created with `MANUAL_DISPATCH_SEED_DEMO_DATA=false`, the Driver and Vehicle tables may start empty. If an older SQLite database or backup contains the correct Driver and Vehicle master data, import only those records instead of restoring the whole old database.

Use:

```sh
python tools/import_driver_vehicle_master_data.py \
  --source-db ./backups/old_manual_dispatch.sqlite3 \
  --target-db ./data/manual_dispatch.sqlite3
```

The import tool only reads:

- `manual_drivers`
- `manual_vehicles`

It does not import Orders, assignments, Final Trip Summaries, or operator accounts.

Default behavior:

- Insert missing Drivers/Vehicles.
- Skip existing Driver/Vehicle IDs.
- Create a timestamped target backup before importing.

To update existing Driver/Vehicle rows from the old database, explicitly add:

```sh
--overwrite-existing
```

Before importing:

- Stop the app or make sure no one is dispatching.
- Confirm the source backup is the correct old database.
- Confirm the current NAS database has been backed up.
- Prefer testing the import on a copied database first.

## Security Notes

- Do not port-forward `8130` to the public internet.
- Do not expose the app publicly without additional production security work.
- Use VPN for remote access if remote access is needed.
- Use strong operator passwords.
- Use a strong admin reset code.
- Disable registration after account setup.
- Keep the SQLite file on NAS local storage.

## Explicit Non-Goals

This deployment does not add:

- Automatic assignment.
- Route optimization.
- ETA calculation.
- Google Maps.
- Live geocoding.
- CP-SAT.
- Automatic driver selection.
- Automatic vehicle selection.
- Public internet hosting.
