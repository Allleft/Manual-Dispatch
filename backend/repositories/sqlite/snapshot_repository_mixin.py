from datetime import date

from backend.db.connection import connect


def _parse_iso_date(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.isoformat() == value else None

class SQLiteSnapshotRepositoryMixin:
    """Snapshot persistence responsibilities."""

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND delivery_date = ? AND status = 'SAVED'
                    ORDER BY saved_at DESC, summary_id
                    """,
                    (dispatch_date, delivery_date),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND status = 'SAVED'
                    ORDER BY saved_at DESC, summary_id
                    """,
                    (dispatch_date,),
                ).fetchall()
        return [self._row_to_final_trip_summary(row) for row in rows]

    def list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND delivery_date = ? AND status = 'GENERATED'
                    ORDER BY generated_at DESC, summary_id
                    """,
                    (dispatch_date, delivery_date),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND status = 'GENERATED'
                    ORDER BY generated_at DESC, summary_id
                    """,
                    (dispatch_date,),
                ).fetchall()
        return [self._row_to_final_trip_summary(row) for row in rows]

    def list_final_summary_dates(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT dispatch_date
                FROM final_trip_summaries
                WHERE status = 'SAVED'
                ORDER BY dispatch_date DESC
                """
            ).fetchall()
        return [row["dispatch_date"] for row in rows]

    def list_finalized_opshop_pickup_assignments(self, dispatch_date):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    opshop_row.pickup_task_id_snapshot AS pickup_task_id,
                    summary.dispatch_date,
                    summary.delivery_date,
                    summary.driver_id,
                    COALESCE(driver.name, summary.driver_name_snapshot) AS driver_name,
                    summary.summary_id,
                    summary.saved_at
                FROM final_trip_summary_opshop_pickup_rows opshop_row
                JOIN final_trip_summaries summary
                    ON summary.summary_id = opshop_row.summary_id
                LEFT JOIN manual_drivers driver
                    ON driver.driver_id = summary.driver_id
                WHERE summary.dispatch_date = ?
                    AND summary.status = 'SAVED'
                    AND opshop_row.pickup_task_id_snapshot IS NOT NULL
                    AND opshop_row.pickup_task_id_snapshot != ''
                ORDER BY summary.saved_at DESC, summary.summary_id DESC, opshop_row.row_no DESC
                """,
                (dispatch_date,),
            ).fetchall()

        finalized = {}
        for row in rows:
            pickup_task_id = row["pickup_task_id"]
            if pickup_task_id in finalized:
                continue
            finalized[pickup_task_id] = {
                "pickup_task_id": pickup_task_id,
                "dispatch_date": row["dispatch_date"],
                "delivery_date": row["delivery_date"],
                "driver_id": row["driver_id"],
                "driver_name": row["driver_name"],
                "summary_id": row["summary_id"],
                "saved_at": row["saved_at"],
            }
        return finalized

    def has_saved_final_trip_summary(self, dispatch_date, driver_id, delivery_date=None):
        with connect(self.db_path) as connection:
            if delivery_date:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM final_trip_summaries
                    WHERE dispatch_date = ?
                        AND delivery_date = ?
                        AND driver_id = ?
                        AND status = 'SAVED'
                    LIMIT 1
                    """,
                    (dispatch_date, delivery_date, driver_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM final_trip_summaries
                    WHERE dispatch_date = ? AND driver_id = ? AND status = 'SAVED'
                    LIMIT 1
                    """,
                    (dispatch_date, driver_id),
                ).fetchone()
        return row is not None

    def get_final_trip_summary(self, summary_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM final_trip_summaries
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchone()
        return self._row_to_final_trip_summary(row) if row else None

    def get_generated_final_trip_summary_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM final_trip_summaries
                WHERE dispatch_date = ?
                    AND delivery_date = ?
                    AND driver_id = ?
                    AND status = 'GENERATED'
                LIMIT 1
                """,
                (dispatch_date, delivery_date, driver_id),
            ).fetchone()
        return self._row_to_final_trip_summary(row) if row else None

    def list_delivery_run_sheets(
        self,
        dispatch_date=None,
        delivery_date=None,
        status=None,
    ):
        clauses = []
        parameters = []
        if dispatch_date:
            clauses.append("dispatch_date = ?")
            parameters.append(dispatch_date)
        if delivery_date:
            clauses.append("delivery_date = ?")
            parameters.append(delivery_date)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM delivery_run_sheets
                {where_clause}
                ORDER BY delivery_date DESC, generated_at DESC, run_sheet_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_delivery_run_sheet(row) for row in rows]

    def list_reserved_delivery_order_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT run_sheet_row.task_id
                FROM delivery_run_sheet_rows run_sheet_row
                JOIN delivery_run_sheets run_sheet
                    ON run_sheet.run_sheet_id = run_sheet_row.run_sheet_id
                WHERE run_sheet.status IN ('GENERATED', 'SAVED')
                    AND run_sheet_row.task_type = 'ORDER'
                    AND run_sheet_row.task_id IS NOT NULL
                    AND run_sheet_row.task_id != ''
                ORDER BY run_sheet_row.task_id
                """
            ).fetchall()
        return {row["task_id"] for row in rows}

    def list_globally_assigned_delivery_order_ids(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT task_id
                FROM manual_dispatch_assignments
                WHERE task_type = 'ORDER'
                    AND task_id IS NOT NULL
                    AND task_id != ''
                ORDER BY task_id
                """
            ).fetchall()
        return {row["task_id"] for row in rows}

    def list_globally_assigned_delivery_order_assignments(self):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_dispatch_assignments
                WHERE task_type = 'ORDER'
                    AND task_id IS NOT NULL
                    AND task_id != ''
                ORDER BY dispatch_date, task_id, assignment_id
                """
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    def list_globally_unavailable_delivery_order_ids(self):
        return (
            self.list_globally_assigned_delivery_order_ids()
            | self.list_reserved_delivery_order_ids()
        )

    def get_delivery_run_sheet_reserving_order(self, order_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT run_sheet.*
                FROM delivery_run_sheets run_sheet
                JOIN delivery_run_sheet_rows run_sheet_row
                    ON run_sheet_row.run_sheet_id = run_sheet.run_sheet_id
                WHERE run_sheet.status IN ('GENERATED', 'SAVED')
                    AND run_sheet_row.task_type = 'ORDER'
                    AND run_sheet_row.task_id = ?
                ORDER BY
                    CASE run_sheet.status
                        WHEN 'SAVED' THEN 0
                        ELSE 1
                    END,
                    run_sheet.generated_at DESC,
                    run_sheet.run_sheet_id
                LIMIT 1
                """,
                (order_id,),
            ).fetchone()
        return self._row_to_delivery_run_sheet(row) if row else None

    def get_delivery_run_sheet(self, run_sheet_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM delivery_run_sheets WHERE run_sheet_id = ?",
                (run_sheet_id,),
            ).fetchone()
        return self._row_to_delivery_run_sheet(row) if row else None

    def get_delivery_run_sheet_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM delivery_run_sheets
                WHERE delivery_date = ? AND driver_id = ?
                ORDER BY dispatch_date, run_sheet_id
                """,
                (delivery_date, driver_id),
            ).fetchall()
        if len(rows) > 1:
            raise ValueError(
                "Delivery Run Sheet integrity error for "
                f"{delivery_date}:{driver_id}: expected at most one active document."
            )
        return self._row_to_delivery_run_sheet(rows[0]) if rows else None

    def has_saved_delivery_run_sheet(self, dispatch_date, driver_id, delivery_date):
        run_sheet = self.get_delivery_run_sheet_for_driver(
            dispatch_date,
            delivery_date,
            driver_id,
        )
        return bool(run_sheet and run_sheet.status == "SAVED")

    def upsert_delivery_run_sheet(self, run_sheet):
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                """
                SELECT run_sheet_id
                FROM delivery_run_sheets
                WHERE delivery_date = ?
                    AND driver_id = ?
                    AND run_sheet_id != ?
                ORDER BY dispatch_date, run_sheet_id
                LIMIT 1
                """,
                (
                    run_sheet.delivery_date,
                    run_sheet.driver_id,
                    run_sheet.run_sheet_id,
                ),
            ).fetchone()
            if duplicate:
                connection.rollback()
                raise ValueError(
                    "Delivery Run Sheet already exists for this driver "
                    "and delivery date."
                )
            connection.execute(
                """
                INSERT INTO delivery_run_sheets (
                    run_sheet_id,
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    driver_name_snapshot,
                    vehicle_id,
                    vehicle_rego_snapshot,
                    total_pallets,
                    total_loose_bags,
                    total_cartons,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id,
                    legacy_summary_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_sheet_id) DO UPDATE SET
                    dispatch_date = excluded.dispatch_date,
                    delivery_date = excluded.delivery_date,
                    driver_id = excluded.driver_id,
                    driver_name_snapshot = excluded.driver_name_snapshot,
                    vehicle_id = excluded.vehicle_id,
                    vehicle_rego_snapshot = excluded.vehicle_rego_snapshot,
                    total_pallets = excluded.total_pallets,
                    total_loose_bags = excluded.total_loose_bags,
                    total_cartons = excluded.total_cartons,
                    status = excluded.status,
                    generated_at = excluded.generated_at,
                    saved_at = excluded.saved_at,
                    saved_by_account_name = excluded.saved_by_account_name,
                    saved_by_account_id = excluded.saved_by_account_id,
                    legacy_summary_id = excluded.legacy_summary_id
                """,
                (
                    run_sheet.run_sheet_id,
                    run_sheet.dispatch_date,
                    run_sheet.delivery_date,
                    run_sheet.driver_id,
                    run_sheet.driver_name_snapshot,
                    run_sheet.vehicle_id,
                    run_sheet.vehicle_rego_snapshot,
                    run_sheet.total_pallets,
                    run_sheet.total_loose_bags,
                    run_sheet.total_cartons,
                    run_sheet.status,
                    run_sheet.generated_at,
                    run_sheet.saved_at,
                    run_sheet.saved_by_account_name,
                    run_sheet.saved_by_account_id,
                    run_sheet.legacy_summary_id,
                ),
            )
            connection.execute(
                "DELETE FROM delivery_run_sheet_rows WHERE run_sheet_id = ?",
                (run_sheet.run_sheet_id,),
            )
            for trip in run_sheet.trips:
                for order in trip.orders:
                    connection.execute(
                        """
                        INSERT INTO delivery_run_sheet_rows (
                            row_id,
                            run_sheet_id,
                            trip_no,
                            row_no,
                            task_type,
                            task_id,
                            order_id_snapshot,
                            invoice_number_snapshot,
                            order_no_snapshot,
                            company_name_snapshot,
                            suburb_snapshot,
                            delivery_address_snapshot,
                            product_snapshot,
                            product_details_snapshot,
                            estimated_distance_km_from_warehouse_snapshot,
                            pallet_quantity_snapshot,
                            loose_bags_quantity_snapshot,
                            carton_quantity_snapshot,
                            note_snapshot
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            order.row_id,
                            run_sheet.run_sheet_id,
                            trip.trip_no,
                            order.row_no,
                            order.task_type,
                            order.task_id,
                            order.order_id_snapshot,
                            order.invoice_number_snapshot,
                            order.order_no_snapshot,
                            order.company_name_snapshot,
                            order.suburb_snapshot,
                            order.delivery_address_snapshot,
                            order.product_snapshot,
                            self._serialize_product_lines(order.product_lines_snapshot),
                            order.estimated_distance_km_from_warehouse_snapshot,
                            order.pallet_quantity_snapshot,
                            order.loose_bags_quantity_snapshot,
                            order.carton_quantity_snapshot,
                            order.note_snapshot,
                        ),
                    )
            connection.commit()
        return self.get_delivery_run_sheet(run_sheet.run_sheet_id)

    def promote_generated_delivery_run_sheet_to_saved(
        self,
        run_sheet_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE delivery_run_sheets
                SET status = 'SAVED',
                    saved_at = ?,
                    saved_by_account_name = ?,
                    saved_by_account_id = ?
                WHERE run_sheet_id = ? AND status = 'GENERATED'
                """,
                (
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id,
                    run_sheet_id,
                ),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_generated_delivery_run_sheet(self, run_sheet_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM delivery_run_sheets
                WHERE run_sheet_id = ? AND status = 'GENERATED'
                """,
                (run_sheet_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_delivery_run_sheet(self, run_sheet_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM delivery_run_sheets WHERE run_sheet_id = ?",
                (run_sheet_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def list_opshop_pickup_collections(
        self,
        dispatch_date=None,
        pickup_date=None,
        status=None,
    ):
        clauses = []
        parameters = []
        if dispatch_date:
            clauses.append("dispatch_date = ?")
            parameters.append(dispatch_date)
        if pickup_date:
            clauses.append("pickup_date = ?")
            parameters.append(pickup_date)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM opshop_pickup_collections
                {where_clause}
                ORDER BY pickup_date DESC, generated_at DESC, collection_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_opshop_pickup_collection(row) for row in rows]

    def list_saved_opshop_pickup_dates_by_opshop_ids(
        self,
        opshop_ids,
        before_date,
    ):
        requested_ids = sorted({opshop_id for opshop_id in opshop_ids if opshop_id})
        if not requested_ids:
            return {}
        parsed_before_date = _parse_iso_date(before_date)
        if parsed_before_date is None:
            raise ValueError("before_date must be a valid YYYY-MM-DD date.")

        placeholders = ", ".join("?" for _ in requested_ids)
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT
                    task.opshop_id AS opshop_id,
                    collection_row.pickup_date_snapshot AS pickup_date
                FROM opshop_pickup_collections AS collection
                JOIN opshop_pickup_collection_rows AS collection_row
                    ON collection_row.collection_id = collection.collection_id
                JOIN opshop_pickup_tasks AS task
                    ON task.pickup_task_id = collection_row.pickup_task_id_snapshot
                WHERE collection.status = 'SAVED'
                    AND task.opshop_id IN ({placeholders})
                    AND collection_row.pickup_date_snapshot IS NOT NULL
                    AND collection_row.pickup_date_snapshot < ?
                ORDER BY task.opshop_id, collection_row.pickup_date_snapshot
                """,
                (*requested_ids, parsed_before_date.isoformat()),
            ).fetchall()

        dates_by_opshop_id = {}
        for row in rows:
            parsed_pickup_date = _parse_iso_date(row["pickup_date"])
            if parsed_pickup_date is None or parsed_pickup_date >= parsed_before_date:
                continue
            dates_by_opshop_id.setdefault(row["opshop_id"], []).append(
                parsed_pickup_date.isoformat()
            )
        return dates_by_opshop_id

    def get_opshop_pickup_collection(self, collection_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM opshop_pickup_collections WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()
        return self._row_to_opshop_pickup_collection(row) if row else None

    def get_opshop_pickup_collection_for_driver(
        self,
        dispatch_date,
        pickup_date,
        driver_id,
    ):
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_collections
                WHERE pickup_date = ? AND driver_id = ?
                ORDER BY dispatch_date, collection_id
                """,
                (pickup_date, driver_id),
            ).fetchall()
        if len(rows) > 1:
            raise ValueError(
                "OP SHOP Pickup Collection integrity error for "
                f"{pickup_date}:{driver_id}: expected at most one active document."
            )
        return self._row_to_opshop_pickup_collection(rows[0]) if rows else None

    def has_saved_opshop_pickup_collection(self, dispatch_date, driver_id, pickup_date):
        collection = self.get_opshop_pickup_collection_for_driver(
            dispatch_date,
            pickup_date,
            driver_id,
        )
        return bool(collection and collection.status == "SAVED")

    def upsert_opshop_pickup_collection(self, collection):
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                """
                SELECT collection_id
                FROM opshop_pickup_collections
                WHERE pickup_date = ?
                    AND driver_id = ?
                    AND collection_id != ?
                ORDER BY dispatch_date, collection_id
                LIMIT 1
                """,
                (
                    collection.pickup_date,
                    collection.driver_id,
                    collection.collection_id,
                ),
            ).fetchone()
            if duplicate:
                connection.rollback()
                raise ValueError(
                    "OP SHOP Pickup Collection already exists for this driver "
                    "and pickup date."
                )
            connection.execute(
                """
                INSERT INTO opshop_pickup_collections (
                    collection_id,
                    dispatch_date,
                    pickup_date,
                    driver_id,
                    driver_name_snapshot,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id,
                    legacy_summary_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_id) DO UPDATE SET
                    dispatch_date = excluded.dispatch_date,
                    pickup_date = excluded.pickup_date,
                    driver_id = excluded.driver_id,
                    driver_name_snapshot = excluded.driver_name_snapshot,
                    status = excluded.status,
                    generated_at = excluded.generated_at,
                    saved_at = excluded.saved_at,
                    saved_by_account_name = excluded.saved_by_account_name,
                    saved_by_account_id = excluded.saved_by_account_id,
                    legacy_summary_id = excluded.legacy_summary_id
                """,
                (
                    collection.collection_id,
                    collection.dispatch_date,
                    collection.pickup_date,
                    collection.driver_id,
                    collection.driver_name_snapshot,
                    collection.status,
                    collection.generated_at,
                    collection.saved_at,
                    collection.saved_by_account_name,
                    collection.saved_by_account_id,
                    collection.legacy_summary_id,
                ),
            )
            connection.execute(
                "DELETE FROM opshop_pickup_collection_rows WHERE collection_id = ?",
                (collection.collection_id,),
            )
            for pickup in collection.pickups:
                connection.execute(
                    """
                    INSERT INTO opshop_pickup_collection_rows (
                        row_id,
                        collection_id,
                        row_no,
                        pickup_task_id_snapshot,
                        opshop_name_snapshot,
                        suburb_snapshot,
                        street_address_snapshot,
                        area_region_snapshot,
                        pickup_date_snapshot,
                        run_type_snapshot,
                        pickup_category_snapshot,
                        route_group_id_snapshot,
                        route_group_name_snapshot,
                        pickup_frequency_snapshot,
                        time_window_snapshot,
                        call_before_arrival_snapshot,
                        call_timing_snapshot,
                        primary_contact_snapshot,
                        primary_phone_snapshot,
                        secondary_contact_snapshot,
                        secondary_phone_snapshot,
                        access_type_snapshot,
                        key_required_snapshot,
                        trailer_restriction_snapshot,
                        notes_snapshot,
                        status_snapshot,
                        clothing_kg_snapshot,
                        shoes_kg_snapshot,
                        time_in_snapshot,
                        time_out_snapshot,
                        trolleys_out_to_opshops_snapshot,
                        trolleys_in_to_mcc_snapshot,
                        hard_toys_snapshot,
                        soft_toys_snapshot,
                        black_bags_snapshot,
                        shoe_bags_snapshot
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        pickup.row_id,
                        collection.collection_id,
                        pickup.row_no,
                        pickup.pickup_task_id_snapshot,
                        pickup.opshop_name_snapshot,
                        pickup.suburb_snapshot,
                        pickup.street_address_snapshot,
                        pickup.area_region_snapshot,
                        pickup.pickup_date_snapshot,
                        pickup.run_type_snapshot,
                        pickup.pickup_category_snapshot,
                        pickup.route_group_id_snapshot,
                        pickup.route_group_name_snapshot,
                        pickup.pickup_frequency_snapshot,
                        pickup.time_window_snapshot,
                        int(bool(pickup.call_before_arrival_snapshot)),
                        pickup.call_timing_snapshot,
                        pickup.primary_contact_snapshot,
                        pickup.primary_phone_snapshot,
                        pickup.secondary_contact_snapshot,
                        pickup.secondary_phone_snapshot,
                        pickup.access_type_snapshot,
                        int(bool(pickup.key_required_snapshot)),
                        pickup.trailer_restriction_snapshot,
                        pickup.notes_snapshot,
                        pickup.status_snapshot,
                        pickup.clothing_kg_snapshot,
                        pickup.shoes_kg_snapshot,
                        pickup.time_in_snapshot,
                        pickup.time_out_snapshot,
                        pickup.trolleys_out_to_opshops_snapshot,
                        pickup.trolleys_in_to_mcc_snapshot,
                        pickup.hard_toys_snapshot,
                        pickup.soft_toys_snapshot,
                        pickup.black_bags_snapshot,
                        pickup.shoe_bags_snapshot,
                    ),
                )
            connection.commit()
        return self.get_opshop_pickup_collection(collection.collection_id)

    def update_opshop_pickup_collection_rows(
        self,
        collection_id,
        updated_rows,
    ):
        row_ids = [row.row_id for row in updated_rows]
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("Duplicate OP SHOP Pickup Collection row update.")
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            collection = connection.execute(
                """
                SELECT status
                FROM opshop_pickup_collections
                WHERE collection_id = ?
                """,
                (collection_id,),
            ).fetchone()
            if not collection:
                connection.rollback()
                raise ValueError(
                    f"OP SHOP Pickup Collection does not exist: {collection_id}"
                )
            if collection["status"] != "GENERATED":
                connection.rollback()
                raise ValueError(
                    "Only generated OP SHOP Pickup Collections can be updated."
                )
            if row_ids:
                placeholders = ", ".join("?" for _ in row_ids)
                matches = connection.execute(
                    f"""
                    SELECT row_id
                    FROM opshop_pickup_collection_rows
                    WHERE collection_id = ?
                        AND row_id IN ({placeholders})
                    """,
                    (collection_id, *row_ids),
                ).fetchall()
                if len(matches) != len(row_ids):
                    connection.rollback()
                    raise ValueError(
                        "OP SHOP Pickup Collection row does not belong to this collection."
                    )
            for row in updated_rows:
                connection.execute(
                    """
                    UPDATE opshop_pickup_collection_rows
                    SET clothing_kg_snapshot = ?,
                        shoes_kg_snapshot = ?,
                        time_in_snapshot = ?,
                        time_out_snapshot = ?,
                        trolleys_out_to_opshops_snapshot = ?,
                        trolleys_in_to_mcc_snapshot = ?,
                        hard_toys_snapshot = ?,
                        soft_toys_snapshot = ?,
                        black_bags_snapshot = ?,
                        shoe_bags_snapshot = ?
                    WHERE collection_id = ? AND row_id = ?
                    """,
                    (
                        row.clothing_kg_snapshot,
                        row.shoes_kg_snapshot,
                        row.time_in_snapshot,
                        row.time_out_snapshot,
                        row.trolleys_out_to_opshops_snapshot,
                        row.trolleys_in_to_mcc_snapshot,
                        row.hard_toys_snapshot,
                        row.soft_toys_snapshot,
                        row.black_bags_snapshot,
                        row.shoe_bags_snapshot,
                        collection_id,
                        row.row_id,
                    ),
                )
            connection.commit()
        return self.get_opshop_pickup_collection(collection_id)

    def promote_generated_opshop_pickup_collection_to_saved(
        self,
        collection_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE opshop_pickup_collections
                SET status = 'SAVED',
                    saved_at = ?,
                    saved_by_account_name = ?,
                    saved_by_account_id = ?
                WHERE collection_id = ? AND status = 'GENERATED'
                """,
                (
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id,
                    collection_id,
                ),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_generated_opshop_pickup_collection(self, collection_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM opshop_pickup_collections
                WHERE collection_id = ? AND status = 'GENERATED'
                """,
                (collection_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_opshop_pickup_collection(self, collection_id):
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM opshop_pickup_collections WHERE collection_id = ?",
                (collection_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def driver_has_final_summary_history(self, driver_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE driver_id = ?
                LIMIT 1
                """,
                (driver_id,),
            ).fetchone()
        return row is not None

    def vehicle_has_final_summary_history(self, vehicle_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE vehicle_id = ?
                LIMIT 1
                """,
                (vehicle_id,),
            ).fetchone()
        return row is not None

    def save_final_trip_summary(self, summary, rows, opshop_rows=None):
        timestamp = self._timestamp()
        opshop_rows = opshop_rows or []

        with connect(self.db_path) as connection:
            existing_summary = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE dispatch_date = ?
                    AND delivery_date = ?
                    AND driver_id = ?
                    AND status = 'SAVED'
                LIMIT 1
                """,
                (
                    summary["dispatch_date"],
                    summary["delivery_date"],
                    summary["driver_id"],
                ),
            ).fetchone()
            if existing_summary:
                raise ValueError(
                    "Final Summary for this driver, dispatch date, and delivery date has already been saved."
                )

            self._delete_generated_final_trip_summary_for_driver(
                connection,
                summary["dispatch_date"],
                summary["delivery_date"],
                summary["driver_id"],
            )

            summary_id = self._create_final_trip_summary_id(connection)
            connection.execute(
                """
                INSERT INTO final_trip_summaries (
                    summary_id,
                    dispatch_date,
                    delivery_date,
                    driver_id,
                    driver_name_snapshot,
                    vehicle_id,
                    vehicle_rego_snapshot,
                    total_pallets,
                    total_loose_bags,
                    total_cartons,
                    status,
                    generated_at,
                    saved_at,
                    saved_by_account_name,
                    saved_by_account_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    summary["dispatch_date"],
                    summary["delivery_date"],
                    summary["driver_id"],
                    summary["driver_name_snapshot"],
                    summary.get("vehicle_id"),
                    summary.get("vehicle_rego_snapshot"),
                    summary["total_pallets"],
                    summary["total_loose_bags"],
                    summary.get("total_cartons", 0),
                    "SAVED",
                    summary.get("generated_at") or timestamp,
                    timestamp,
                    summary.get("saved_by_account_name") or "Unknown",
                    summary.get("saved_by_account_id"),
                ),
            )

            for row in rows:
                row_id = self._create_final_trip_summary_row_id(connection)
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_rows (
                        row_id,
                        summary_id,
                        trip_no,
                        row_no,
                        task_type,
                        task_id,
                        order_id_snapshot,
                        invoice_number_snapshot,
                        order_no_snapshot,
                        company_name_snapshot,
                        suburb_snapshot,
                        delivery_address_snapshot,
                        product_snapshot,
                        product_details_snapshot,
                        estimated_distance_km_from_warehouse_snapshot,
                        pallet_quantity_snapshot,
                        loose_bags_quantity_snapshot,
                        carton_quantity_snapshot,
                        note_snapshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        summary_id,
                        row["trip_no"],
                        row["row_no"],
                        row["task_type"],
                        row["task_id"],
                        row.get("order_id_snapshot"),
                        row.get("invoice_number_snapshot"),
                        row.get("order_no_snapshot"),
                        row.get("company_name_snapshot"),
                        row.get("suburb_snapshot"),
                        row.get("delivery_address_snapshot"),
                        row.get("product_snapshot"),
                        self._serialize_product_lines(row.get("product_lines_snapshot") or []),
                        row.get("estimated_distance_km_from_warehouse_snapshot"),
                        row["pallet_quantity_snapshot"],
                        row["loose_bags_quantity_snapshot"],
                        row.get("carton_quantity_snapshot", 0),
                        row.get("note_snapshot"),
                    ),
                )

                if row["task_type"] == "ORDER":
                    connection.execute(
                        """
                        UPDATE manual_orders
                        SET status = 'FINALIZED'
                        WHERE order_id = ? AND status = 'ACTIVE'
                        """,
                        (row["task_id"],),
                    )
                    connection.execute(
                        """
                        DELETE FROM manual_dispatch_assignments
                        WHERE dispatch_date = ? AND task_type = ? AND task_id = ?
                        """,
                        (
                            summary["dispatch_date"],
                            row["task_type"],
                            row["task_id"],
                        ),
                    )

            for row in opshop_rows:
                row_id = self._create_final_trip_summary_opshop_row_id(connection)
                connection.execute(
                    """
                    INSERT INTO final_trip_summary_opshop_pickup_rows (
                        row_id,
                        summary_id,
                        row_no,
                        pickup_task_id_snapshot,
                        opshop_name_snapshot,
                        suburb_snapshot,
                        street_address_snapshot,
                        area_region_snapshot,
                        pickup_date_snapshot,
                        run_type_snapshot,
                        pickup_category_snapshot,
                        route_group_id_snapshot,
                        route_group_name_snapshot,
                        pickup_frequency_snapshot,
                        time_window_snapshot,
                        primary_contact_snapshot,
                        primary_phone_snapshot,
                        secondary_contact_snapshot,
                        secondary_phone_snapshot,
                        access_type_snapshot,
                        key_required_snapshot,
                        trailer_restriction_snapshot,
                        notes_snapshot,
                        status_snapshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        summary_id,
                        row["row_no"],
                        row["pickup_task_id_snapshot"],
                        row["opshop_name_snapshot"],
                        row.get("suburb_snapshot"),
                        row.get("street_address_snapshot"),
                        row.get("area_region_snapshot"),
                        row["pickup_date_snapshot"],
                        row.get("run_type_snapshot"),
                        row.get("pickup_category_snapshot"),
                        row.get("route_group_id_snapshot"),
                        row.get("route_group_name_snapshot"),
                        row.get("pickup_frequency_snapshot"),
                        row.get("time_window_snapshot"),
                        row.get("primary_contact_snapshot"),
                        row.get("primary_phone_snapshot"),
                        row.get("secondary_contact_snapshot"),
                        row.get("secondary_phone_snapshot"),
                        row.get("access_type_snapshot"),
                        int(bool(row.get("key_required_snapshot"))),
                        row.get("trailer_restriction_snapshot"),
                        row.get("notes_snapshot"),
                        row["status_snapshot"],
                    ),
                )

            connection.commit()

        return self.get_final_trip_summary(summary_id)

    def create_generated_final_trip_summary(self, summary, rows, opshop_rows=None):
        timestamp = self._timestamp()
        opshop_rows = opshop_rows or []

        with connect(self.db_path) as connection:
            existing_saved = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE dispatch_date = ?
                    AND delivery_date = ?
                    AND driver_id = ?
                    AND status = 'SAVED'
                LIMIT 1
                """,
                (
                    summary["dispatch_date"],
                    summary["delivery_date"],
                    summary["driver_id"],
                ),
            ).fetchone()
            if existing_saved:
                raise ValueError(
                    "Final Summary for this driver, dispatch date, and delivery date has already been saved."
                )

            self._delete_generated_final_trip_summary_for_driver(
                connection,
                summary["dispatch_date"],
                summary["delivery_date"],
                summary["driver_id"],
            )
            summary_id = self._insert_final_trip_summary_snapshot(
                connection,
                summary,
                rows,
                opshop_rows,
                "GENERATED",
                timestamp,
            )
            connection.commit()

        return self.get_final_trip_summary(summary_id)

    def save_generated_final_trip_summary(
        self,
        summary_id,
        saved_by_account_name,
        saved_by_account_id,
    ):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            summary_row = connection.execute(
                """
                SELECT *
                FROM final_trip_summaries
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchone()
            if not summary_row:
                raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
            if summary_row["status"] != "GENERATED":
                raise ValueError("Only generated Final Trip Summaries can be saved.")

            existing_saved = connection.execute(
                """
                SELECT 1
                FROM final_trip_summaries
                WHERE dispatch_date = ?
                    AND delivery_date = ?
                    AND driver_id = ?
                    AND status = 'SAVED'
                    AND summary_id != ?
                LIMIT 1
                """,
                (
                    summary_row["dispatch_date"],
                    summary_row["delivery_date"],
                    summary_row["driver_id"],
                    summary_id,
                ),
            ).fetchone()
            if existing_saved:
                raise ValueError(
                    "Final Summary for this driver, dispatch date, and delivery date has already been saved."
                )

            connection.execute(
                """
                UPDATE final_trip_summaries
                SET status = 'SAVED',
                    saved_at = ?,
                    saved_by_account_name = ?,
                    saved_by_account_id = ?
                WHERE summary_id = ?
                """,
                (
                    timestamp,
                    saved_by_account_name or "Unknown",
                    saved_by_account_id,
                    summary_id,
                ),
            )
            order_rows = connection.execute(
                """
                SELECT task_type, task_id
                FROM final_trip_summary_rows
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchall()
            for row in order_rows:
                if row["task_type"] != "ORDER":
                    continue
                connection.execute(
                    """
                    UPDATE manual_orders
                    SET status = 'FINALIZED'
                    WHERE order_id = ? AND status = 'ACTIVE'
                    """,
                    (row["task_id"],),
                )
                connection.execute(
                    """
                    DELETE FROM manual_dispatch_assignments
                    WHERE dispatch_date = ? AND task_type = 'ORDER' AND task_id = ?
                    """,
                    (summary_row["dispatch_date"], row["task_id"]),
                )
            connection.commit()

        return self.get_final_trip_summary(summary_id)

    def cancel_generated_final_trip_summary(self, summary_id):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            summary_row = connection.execute(
                """
                SELECT *
                FROM final_trip_summaries
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchone()
            if not summary_row:
                raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
            if summary_row["status"] != "GENERATED":
                raise ValueError("Only generated Final Trip Summaries can be cancelled.")

            order_rows = connection.execute(
                """
                SELECT trip_no, task_type, task_id
                FROM final_trip_summary_rows
                WHERE summary_id = ?
                ORDER BY row_no
                """,
                (summary_id,),
            ).fetchall()
            for row in order_rows:
                if row["task_type"] != "ORDER" or not row["task_id"]:
                    continue
                connection.execute(
                    """
                    UPDATE manual_orders
                    SET status = 'ACTIVE'
                    WHERE order_id = ? AND status != 'CANCELLED'
                    """,
                    (row["task_id"],),
                )
                connection.execute(
                    """
                    INSERT INTO manual_dispatch_assignments (
                        assignment_id,
                        dispatch_date,
                        task_type,
                        task_id,
                        driver_id,
                        trip_no,
                        assigned_at,
                        updated_at
                    ) VALUES (?, ?, 'ORDER', ?, ?, ?, ?, ?)
                    ON CONFLICT(dispatch_date, task_type, task_id)
                    DO UPDATE SET
                        driver_id = excluded.driver_id,
                        trip_no = excluded.trip_no,
                        updated_at = excluded.updated_at
                    """,
                    (
                        self._create_assignment_id(connection),
                        summary_row["dispatch_date"],
                        row["task_id"],
                        summary_row["driver_id"],
                        row["trip_no"],
                        timestamp,
                        timestamp,
                    ),
                )

            connection.execute(
                "DELETE FROM final_trip_summary_rows WHERE summary_id = ?",
                (summary_id,),
            )
            connection.execute(
                "DELETE FROM final_trip_summary_opshop_pickup_rows WHERE summary_id = ?",
                (summary_id,),
            )
            connection.execute(
                "DELETE FROM final_trip_summaries WHERE summary_id = ?",
                (summary_id,),
            )
            connection.commit()

        return True

    def _insert_final_trip_summary_snapshot(
        self,
        connection,
        summary,
        rows,
        opshop_rows,
        status,
        timestamp,
    ):
        summary_id = self._create_final_trip_summary_id(connection)
        saved_at = timestamp if status == "SAVED" else (summary.get("generated_at") or timestamp)
        connection.execute(
            """
            INSERT INTO final_trip_summaries (
                summary_id,
                dispatch_date,
                delivery_date,
                driver_id,
                driver_name_snapshot,
                vehicle_id,
                vehicle_rego_snapshot,
                total_pallets,
                total_loose_bags,
                total_cartons,
                status,
                generated_at,
                saved_at,
                saved_by_account_name,
                saved_by_account_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary_id,
                summary["dispatch_date"],
                summary["delivery_date"],
                summary["driver_id"],
                summary["driver_name_snapshot"],
                summary.get("vehicle_id"),
                summary.get("vehicle_rego_snapshot"),
                summary["total_pallets"],
                summary["total_loose_bags"],
                summary.get("total_cartons", 0),
                status,
                summary.get("generated_at") or timestamp,
                saved_at,
                summary.get("saved_by_account_name") or "Unknown",
                summary.get("saved_by_account_id"),
            ),
        )

        for row in rows:
            row_id = self._create_final_trip_summary_row_id(connection)
            connection.execute(
                """
                INSERT INTO final_trip_summary_rows (
                    row_id,
                    summary_id,
                    trip_no,
                    row_no,
                    task_type,
                    task_id,
                    order_id_snapshot,
                    invoice_number_snapshot,
                    order_no_snapshot,
                    company_name_snapshot,
                    suburb_snapshot,
                    delivery_address_snapshot,
                    product_snapshot,
                    product_details_snapshot,
                    estimated_distance_km_from_warehouse_snapshot,
                    pallet_quantity_snapshot,
                    loose_bags_quantity_snapshot,
                    carton_quantity_snapshot,
                    note_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    summary_id,
                    row["trip_no"],
                    row["row_no"],
                    row["task_type"],
                    row["task_id"],
                    row.get("order_id_snapshot"),
                    row.get("invoice_number_snapshot"),
                    row.get("order_no_snapshot"),
                    row.get("company_name_snapshot"),
                    row.get("suburb_snapshot"),
                    row.get("delivery_address_snapshot"),
                    row.get("product_snapshot"),
                    self._serialize_product_lines(row.get("product_lines_snapshot") or []),
                    row.get("estimated_distance_km_from_warehouse_snapshot"),
                    row["pallet_quantity_snapshot"],
                    row["loose_bags_quantity_snapshot"],
                    row.get("carton_quantity_snapshot", 0),
                    row.get("note_snapshot"),
                ),
            )

        for row in opshop_rows:
            row_id = self._create_final_trip_summary_opshop_row_id(connection)
            connection.execute(
                """
                INSERT INTO final_trip_summary_opshop_pickup_rows (
                    row_id,
                    summary_id,
                    row_no,
                    pickup_task_id_snapshot,
                    opshop_name_snapshot,
                    suburb_snapshot,
                    street_address_snapshot,
                    area_region_snapshot,
                    pickup_date_snapshot,
                    run_type_snapshot,
                    pickup_category_snapshot,
                    route_group_id_snapshot,
                    route_group_name_snapshot,
                    pickup_frequency_snapshot,
                    time_window_snapshot,
                    primary_contact_snapshot,
                    primary_phone_snapshot,
                    secondary_contact_snapshot,
                    secondary_phone_snapshot,
                    access_type_snapshot,
                    key_required_snapshot,
                    trailer_restriction_snapshot,
                    notes_snapshot,
                    status_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    summary_id,
                    row["row_no"],
                    row["pickup_task_id_snapshot"],
                    row["opshop_name_snapshot"],
                    row.get("suburb_snapshot"),
                    row.get("street_address_snapshot"),
                    row.get("area_region_snapshot"),
                    row["pickup_date_snapshot"],
                    row.get("run_type_snapshot"),
                    row.get("pickup_category_snapshot"),
                    row.get("route_group_id_snapshot"),
                    row.get("route_group_name_snapshot"),
                    row.get("pickup_frequency_snapshot"),
                    row.get("time_window_snapshot"),
                    row.get("primary_contact_snapshot"),
                    row.get("primary_phone_snapshot"),
                    row.get("secondary_contact_snapshot"),
                    row.get("secondary_phone_snapshot"),
                    row.get("access_type_snapshot"),
                    int(bool(row.get("key_required_snapshot"))),
                    row.get("trailer_restriction_snapshot"),
                    row.get("notes_snapshot"),
                    row["status_snapshot"],
                ),
            )
        return summary_id

    def _delete_generated_final_trip_summary_for_driver(
        self,
        connection,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        generated_rows = connection.execute(
            """
            SELECT summary_id
            FROM final_trip_summaries
            WHERE dispatch_date = ?
                AND delivery_date = ?
                AND driver_id = ?
                AND status = 'GENERATED'
            """,
            (dispatch_date, delivery_date, driver_id),
        ).fetchall()
        for row in generated_rows:
            summary_id = row["summary_id"]
            connection.execute(
                "DELETE FROM final_trip_summary_rows WHERE summary_id = ?",
                (summary_id,),
            )
            connection.execute(
                "DELETE FROM final_trip_summary_opshop_pickup_rows WHERE summary_id = ?",
                (summary_id,),
            )
            connection.execute(
                "DELETE FROM final_trip_summaries WHERE summary_id = ?",
                (summary_id,),
            )

    def _create_final_trip_summary_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(summary_id, 5) AS INTEGER)), 0) + 1
                AS next_number
            FROM final_trip_summaries
            WHERE summary_id LIKE 'FTS-%'
            """
        ).fetchone()
        return f"FTS-{row['next_number']:03d}"

    def _create_final_trip_summary_row_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(row_id, 5) AS INTEGER)), 0) + 1
                AS next_number
            FROM final_trip_summary_rows
            WHERE row_id LIKE 'FSR-%'
            """
        ).fetchone()
        return f"FSR-{row['next_number']:03d}"

    def _create_final_trip_summary_opshop_row_id(self, connection):
        row = connection.execute(
            """
            SELECT COALESCE(MAX(CAST(SUBSTR(row_id, 5) AS INTEGER)), 0) + 1
                AS next_number
            FROM final_trip_summary_opshop_pickup_rows
            WHERE row_id LIKE 'FSO-%'
            """
        ).fetchone()
        return f"FSO-{row['next_number']:03d}"
