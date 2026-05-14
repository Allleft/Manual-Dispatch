#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_ROOT/.env"
    set +a
fi

DB_PATH=${MANUAL_DISPATCH_DB_PATH:-data/manual_dispatch.sqlite3}
BACKUP_DIR=${MANUAL_DISPATCH_BACKUP_DIR:-backups}

case "$DB_PATH" in
    /*) SOURCE_PATH=$DB_PATH ;;
    *) SOURCE_PATH="$REPO_ROOT/$DB_PATH" ;;
esac

case "$BACKUP_DIR" in
    /*) BACKUP_PATH=$BACKUP_DIR ;;
    *) BACKUP_PATH="$REPO_ROOT/$BACKUP_DIR" ;;
esac

if [ ! -f "$SOURCE_PATH" ]; then
    echo "Runtime database not found: $DB_PATH" >&2
    exit 1
fi

mkdir -p "$BACKUP_PATH"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DESTINATION="$BACKUP_PATH/manual_dispatch_$TIMESTAMP.sqlite3"

if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SOURCE_PATH" ".backup '$DESTINATION'"
    BACKUP_METHOD="sqlite3 .backup"
else
    BACKUP_METHOD="file copy fallback"
    cp "$SOURCE_PATH" "$DESTINATION"

    WAL_SOURCE="$SOURCE_PATH-wal"
    SHM_SOURCE="$SOURCE_PATH-shm"
    if [ -f "$WAL_SOURCE" ] || [ -f "$SHM_SOURCE" ]; then
        echo "WARNING: sqlite3 CLI was not found, and WAL sidecar files are present." >&2
        echo "WARNING: Falling back to copying the database file plus any -wal/-shm sidecar files." >&2
        echo "WARNING: For the safest fallback backup, stop the app before running this script." >&2

        if [ -f "$WAL_SOURCE" ]; then
            cp "$WAL_SOURCE" "$DESTINATION-wal"
        fi
        if [ -f "$SHM_SOURCE" ]; then
            cp "$SHM_SOURCE" "$DESTINATION-shm"
        fi
    else
        echo "WARNING: sqlite3 CLI was not found. Plain file copy backup was used." >&2
        echo "WARNING: If WAL mode is enabled during live writes, install sqlite3 or stop the app before backup." >&2
    fi
fi

echo "SQLite backup created."
echo "Method: $BACKUP_METHOD"
echo "Source: $SOURCE_PATH"
echo "Backup: $DESTINATION"
