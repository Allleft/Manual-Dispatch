from datetime import datetime, timezone
import json
from backend.db.connection import get_database_path, initialize_database
from backend.schemas import ProductDetailLine

class SQLiteRepositoryBase:
    """Base persistence responsibilities."""

    def __init__(self, db_path=None):
        self.db_path = get_database_path(db_path)
        initialize_database(self.db_path)

    def _timestamp(self):
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

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
