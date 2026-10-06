from backend.db.connection import connect
from backend.db.delivery_per_trip import delivery_per_trip_schema_status
from backend.db.invariants import table_columns

class SQLiteLegacyRepositoryMixin:
    """Legacy persistence responsibilities."""

    def get_delivery_per_trip_schema_status(self):
        with connect(self.db_path) as connection:
            return delivery_per_trip_schema_status(connection)

    def require_delivery_per_trip_schema(self):
        status = self.get_delivery_per_trip_schema_status()
        if not status["ready"]:
            raise ValueError("Per-trip Delivery schema migration is required.")
        return status

    def get_workspace_migration_status(self):
        with connect(self.db_path) as connection:
            schema_status = delivery_per_trip_schema_status(connection)
            legacy_scope = (
                "AND run_sheet.trip_no IS NULL"
                if "trip_no" in table_columns(connection, "delivery_run_sheets") else ""
            )
            rows = connection.execute(
                f"""
                SELECT
                    summary.summary_id,
                    summary.status,
                    EXISTS (
                        SELECT 1
                        FROM final_trip_summary_rows delivery_row
                        WHERE delivery_row.summary_id = summary.summary_id
                    ) AS has_delivery_rows,
                    (
                        SELECT COUNT(*)
                        FROM final_trip_summary_rows delivery_row
                        WHERE delivery_row.summary_id = summary.summary_id
                    ) AS delivery_row_count,
                    EXISTS (
                        SELECT 1
                        FROM final_trip_summary_opshop_pickup_rows opshop_row
                        WHERE opshop_row.summary_id = summary.summary_id
                    ) AS has_opshop_rows,
                    (
                        SELECT COUNT(*)
                        FROM final_trip_summary_opshop_pickup_rows opshop_row
                        WHERE opshop_row.summary_id = summary.summary_id
                    ) AS opshop_row_count,
                    (
                        SELECT COUNT(*)
                        FROM delivery_run_sheets run_sheet
                        WHERE run_sheet.legacy_summary_id = summary.summary_id
                            AND run_sheet.status = 'SAVED'
                            AND run_sheet.dispatch_date = summary.dispatch_date
                            AND run_sheet.delivery_date = summary.delivery_date
                            AND run_sheet.driver_id = summary.driver_id
                            {legacy_scope}
                            AND (
                                SELECT COUNT(*)
                                FROM delivery_run_sheet_rows run_sheet_row
                                WHERE run_sheet_row.run_sheet_id = run_sheet.run_sheet_id
                            ) = (
                                SELECT COUNT(*)
                                FROM final_trip_summary_rows delivery_row
                                WHERE delivery_row.summary_id = summary.summary_id
                            )
                    ) AS valid_delivery_marker_count,
                    (
                        SELECT COUNT(*)
                        FROM opshop_pickup_collections collection
                        WHERE collection.legacy_summary_id = summary.summary_id
                            AND collection.status = 'SAVED'
                            AND collection.dispatch_date = summary.dispatch_date
                            AND collection.pickup_date = summary.delivery_date
                            AND collection.driver_id = summary.driver_id
                            AND (
                                SELECT COUNT(*)
                                FROM opshop_pickup_collection_rows collection_row
                                WHERE collection_row.collection_id = collection.collection_id
                            ) = (
                                SELECT COUNT(*)
                                FROM final_trip_summary_opshop_pickup_rows opshop_row
                                WHERE opshop_row.summary_id = summary.summary_id
                            )
                    ) AS valid_opshop_marker_count
                FROM final_trip_summaries summary
                WHERE summary.status IN ('GENERATED', 'SAVED')
                ORDER BY summary.summary_id
                """
            ).fetchall()

        generated_count = sum(row["status"] == "GENERATED" for row in rows)
        delivery_unmigrated_ids = [
            row["summary_id"]
            for row in rows
            if row["status"] == "SAVED"
            and row["has_delivery_rows"]
            and row["valid_delivery_marker_count"] != 1
        ]
        opshop_unmigrated_ids = [
            row["summary_id"]
            for row in rows
            if row["status"] == "SAVED"
            and row["has_opshop_rows"]
            and row["valid_opshop_marker_count"] != 1
        ]
        return {
            "delivery_ready": not generated_count and not delivery_unmigrated_ids,
            "opshop_ready": not generated_count and not opshop_unmigrated_ids,
            "legacy_generated_summary_count": generated_count,
            "delivery_unmigrated_summary_count": len(delivery_unmigrated_ids),
            "opshop_unmigrated_summary_count": len(opshop_unmigrated_ids),
            "delivery_unmigrated_summary_ids": delivery_unmigrated_ids,
            "opshop_unmigrated_summary_ids": opshop_unmigrated_ids,
            "delivery_per_trip_schema": schema_status,
            "delivery_per_trip_ready": (
                schema_status["ready"] and not generated_count and not delivery_unmigrated_ids
            ),
        }

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            order = self.get_order(task_id)
            return order if order and order.status == "ACTIVE" else None
        if task_type == "OPSHOP_PICKUP":
            task = self.get_opshop_pickup_task(task_id)
            return task if task and task.status == "ACTIVE" else None
        return None
