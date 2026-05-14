#!/usr/bin/env sh
set -eu

FORCE=false
if [ "${1:-}" = "--force" ]; then
    FORCE=true
    shift
fi

if [ $# -lt 1 ]; then
    echo "Usage: ./tools/restore_sqlite_db.sh [--force] <backup-path>" >&2
    exit 1
fi

BACKUP_INPUT=$1
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

case "$BACKUP_INPUT" in
    /*) BACKUP_SOURCE=$BACKUP_INPUT ;;
    *) BACKUP_SOURCE="$REPO_ROOT/$BACKUP_INPUT" ;;
esac

case "$DB_PATH" in
    /*) TARGET_PATH=$DB_PATH ;;
    *) TARGET_PATH="$REPO_ROOT/$DB_PATH" ;;
esac

case "$BACKUP_DIR" in
    /*) BACKUP_OUTPUT_DIR=$BACKUP_DIR ;;
    *) BACKUP_OUTPUT_DIR="$REPO_ROOT/$BACKUP_DIR" ;;
esac

if [ ! -f "$BACKUP_SOURCE" ]; then
    echo "Backup file not found: $BACKUP_INPUT" >&2
    exit 1
fi

echo "Stop the Manual Dispatch app before restoring a database."
echo "Backup source: $BACKUP_SOURCE"
echo "Restore target: $TARGET_PATH"

if [ "$FORCE" != "true" ]; then
    printf "Restore this backup over the runtime database? Type YES to continue: "
    read -r ANSWER
    if [ "$ANSWER" != "YES" ]; then
        echo "Restore cancelled."
        exit 1
    fi
fi

mkdir -p "$(dirname "$TARGET_PATH")"
mkdir -p "$BACKUP_OUTPUT_DIR"

if [ -f "$TARGET_PATH" ]; then
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BEFORE_RESTORE="$BACKUP_OUTPUT_DIR/manual_dispatch_before_restore_$TIMESTAMP.sqlite3"
    cp "$TARGET_PATH" "$BEFORE_RESTORE"
    echo "Current runtime database backed up before restore:"
    echo "$BEFORE_RESTORE"
fi

cp "$BACKUP_SOURCE" "$TARGET_PATH"

echo "SQLite database restored."
echo "Runtime database: $TARGET_PATH"
