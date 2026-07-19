class InMemoryLegacyRepositoryMixin:
    """Legacy in-memory responsibilities."""

    def get_workspace_migration_status(self):
        generated = [
            summary
            for summary in self.final_trip_summaries
            if summary.status == "GENERATED"
        ]
        delivery_unmigrated_ids = []
        opshop_unmigrated_ids = []
        for summary in self.final_trip_summaries:
            if summary.status != "SAVED":
                continue
            delivery_row_count = sum(
                len(trip.orders) for trip in (summary.trips or [])
            )
            has_delivery_rows = delivery_row_count > 0
            has_opshop_rows = bool(summary.opshop_pickups or [])
            opshop_row_count = len(summary.opshop_pickups or [])
            valid_delivery_marker_count = sum(
                run_sheet.legacy_summary_id == summary.summary_id
                and run_sheet.status == "SAVED"
                and run_sheet.dispatch_date == summary.dispatch_date
                and run_sheet.delivery_date == summary.delivery_date
                and run_sheet.driver_id == summary.driver_id
                and sum(len(trip.orders) for trip in (run_sheet.trips or []))
                == delivery_row_count
                for run_sheet in self.delivery_run_sheets
            )
            valid_opshop_marker_count = sum(
                collection.legacy_summary_id == summary.summary_id
                and collection.status == "SAVED"
                and collection.dispatch_date == summary.dispatch_date
                and collection.pickup_date == summary.delivery_date
                and collection.driver_id == summary.driver_id
                and len(collection.pickups or []) == opshop_row_count
                for collection in self.opshop_pickup_collections
            )
            if has_delivery_rows and valid_delivery_marker_count != 1:
                delivery_unmigrated_ids.append(summary.summary_id)
            if has_opshop_rows and valid_opshop_marker_count != 1:
                opshop_unmigrated_ids.append(summary.summary_id)

        generated_count = len(generated)
        delivery_unmigrated_ids.sort()
        opshop_unmigrated_ids.sort()
        return {
            "delivery_ready": not generated_count and not delivery_unmigrated_ids,
            "opshop_ready": not generated_count and not opshop_unmigrated_ids,
            "legacy_generated_summary_count": generated_count,
            "delivery_unmigrated_summary_count": len(delivery_unmigrated_ids),
            "opshop_unmigrated_summary_count": len(opshop_unmigrated_ids),
            "delivery_unmigrated_summary_ids": delivery_unmigrated_ids,
            "opshop_unmigrated_summary_ids": opshop_unmigrated_ids,
        }

    def get_task(self, task_type, task_id):
        if task_type == "ORDER":
            order = self.get_order(task_id)
            return order if order and order.status == "ACTIVE" else None
        if task_type == "OPSHOP_PICKUP":
            task = self.get_opshop_pickup_task(task_id)
            return task if task and task.status == "ACTIVE" else None
        return None
