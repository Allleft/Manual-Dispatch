import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "manual_dispatch.sqlite3"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_database_path(db_path=None):
    if db_path:
        return Path(db_path)

    configured_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
    if configured_path:
        return Path(configured_path)

    return DEFAULT_DB_PATH


def connect(db_path=None):
    database_path = get_database_path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path=None):
    with connect(db_path) as connection:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)
        connection.commit()
