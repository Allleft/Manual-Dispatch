from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3

from backend.db.connection import (
    borrow_connection,
    connect,
    get_database_path,
    has_active_connection,
    initialize_database,
)
from backend.errors import StateChangedConflictError
from backend.schemas import ProductDetailLine


class SQLiteRepositoryBase:
    """Base persistence responsibilities."""

    def __init__(self, db_path=None):
        self.db_path = get_database_path(db_path)
        initialize_database(self.db_path)

    def _timestamp(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @contextmanager
    def _immediate_transaction(self):
        if has_active_connection(self.db_path):
            yield
            return
        connection = connect(self.db_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            with borrow_connection(self.db_path, connection):
                try:
                    yield
                except Exception:
                    connection.rollback()
                    raise
                else:
                    connection.commit()
        except sqlite3.OperationalError as error:
            if connection.in_transaction:
                connection.rollback()
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                raise StateChangedConflictError(
                    "State changed; refresh and retry."
                ) from error
            raise
        finally:
            connection.close()

    def _serialize_product_lines(self, product_lines):
        return json.dumps(
            [
                {
                    "product_name": line["product_name"]
                    if isinstance(line, dict)
                    else line.product_name,
                    "quantity": line["quantity"]
                    if isinstance(line, dict)
                    else line.quantity,
                    "unit": line["unit"]
                    if isinstance(line, dict)
                    else line.unit,
                }
                for line in product_lines
            ]
        )

    def _deserialize_product_lines(self, serialized):
        try:
            raw_lines = json.loads(serialized or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_lines = []
        return [
            ProductDetailLine(
                product_name=str(line.get("product_name") or ""),
                quantity=int(line.get("quantity") or 0),
                unit=str(line.get("unit") or ""),
            )
            for line in raw_lines
            if isinstance(line, dict)
        ]
