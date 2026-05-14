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

cp "$SOURCE_PATH" "$DESTINATION"

echo "SQLite backup created."
echo "Source: $SOURCE_PATH"
echo "Backup: $DESTINATION"
