from backend.db.connection import connect
from backend.schemas import ProductDetailLine

class SQLiteOrderRepositoryMixin:
    """Order persistence responsibilities."""

    def list_orders(self, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM manual_orders
                    WHERE status = 'ACTIVE' AND delivery_date = ?
                    ORDER BY order_id
                    """,
                    (delivery_date,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM manual_orders WHERE status = 'ACTIVE' ORDER BY order_id"
                ).fetchall()
        return [self._row_to_order(row) for row in rows]

    def get_order(self, order_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM manual_orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
        return self._row_to_order(row) if row else None

    def create_order(self, order):
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_orders (
                    order_id,
                    invoice_number,
                    order_no,
                    company_name,
                    phone,
                    delivery_address,
                    suburb,
                    postcode,
                    delivery_date,
                    zone,
                    urgency,
                    preferred_driver_id,
                    pallet_quantity,
                    loose_bags_quantity,
                    carton_quantity,
                    start_time,
                    end_time,
                    note,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_id,
                    order.invoice_number,
                    order.order_no,
                    order.company_name,
                    order.phone,
                    order.delivery_address,
                    order.suburb,
                    order.postcode,
                    order.delivery_date,
                    order.zone,
                    order.urgency,
                    order.preferred_driver_id,
                    order.pallet_quantity,
                    order.loose_bags_quantity,
                    order.carton_quantity,
                    order.start_time,
                    order.end_time,
                    order.note,
                    order.status,
                ),
            )
            self._replace_order_product_lines(connection, order.order_id, order.product_lines)
            connection.commit()
        return self.get_order(order.order_id)

    def update_order(self, order):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE manual_orders
                SET
                    invoice_number = ?,
                    order_no = ?,
                    company_name = ?,
                    phone = ?,
                    delivery_address = ?,
                    suburb = ?,
                    postcode = ?,
                    delivery_date = ?,
                    zone = ?,
                    urgency = ?,
                    preferred_driver_id = ?,
                    pallet_quantity = ?,
                    loose_bags_quantity = ?,
                    carton_quantity = ?,
                    start_time = ?,
                    end_time = ?,
                    note = ?,
                    status = ?
                WHERE order_id = ?
                """,
                (
                    order.invoice_number,
                    order.order_no,
                    order.company_name,
                    order.phone,
                    order.delivery_address,
                    order.suburb,
                    order.postcode,
                    order.delivery_date,
                    order.zone,
                    order.urgency,
                    order.preferred_driver_id,
                    order.pallet_quantity,
                    order.loose_bags_quantity,
                    order.carton_quantity,
                    order.start_time,
                    order.end_time,
                    order.note,
                    order.status,
                    order.order_id,
                ),
            )
            self._replace_order_product_lines(connection, order.order_id, order.product_lines)
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Order does not exist: {order.order_id}")
        return self.get_order(order.order_id)

    def cancel_order(self, order_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                "UPDATE manual_orders SET status = 'CANCELLED' WHERE order_id = ?",
                (order_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError(f"Order does not exist: {order_id}")
        return self.get_order(order_id)

    def _replace_order_product_lines(self, connection, order_id, product_lines):
        connection.execute(
            "DELETE FROM order_product_lines WHERE order_id = ?",
            (order_id,),
        )
        for line_no, line in enumerate(product_lines or [], start=1):
            connection.execute(
                """
                INSERT INTO order_product_lines (
                    order_id,
                    line_no,
                    product_name,
                    quantity,
                    unit,
                    product_code,
                    package_quantity,
                    package_unit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    line_no,
                    line.product_name,
                    line.quantity,
                    line.unit,
                    line.product_code,
                    line.package_quantity,
                    line.package_unit,
                ),
            )

    def _list_order_product_lines(self, order_id):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    product_name,
                    quantity,
                    unit,
                    product_code,
                    package_quantity,
                    package_unit
                FROM order_product_lines
                WHERE order_id = ?
                ORDER BY line_no
                """,
                (order_id,),
            ).fetchall()
        return [
            ProductDetailLine(
                product_name=row["product_name"],
                quantity=row["quantity"],
                unit=row["unit"],
                product_code=row["product_code"],
                package_quantity=row["package_quantity"],
                package_unit=row["package_unit"],
            )
            for row in rows
        ]
