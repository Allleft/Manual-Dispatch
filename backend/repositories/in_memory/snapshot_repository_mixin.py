from dataclasses import replace
from backend.schemas import (
    FinalTripSummary,
    FinalTripSummaryOpShopPickupSnapshot,
    FinalTripSummaryOrderSnapshot,
    FinalTripSummaryTrip,
    ProductDetailLine,
)

class InMemorySnapshotRepositoryMixin:
    """Snapshot in-memory responsibilities."""

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return [
            summary
            for summary in self.final_trip_summaries
            if summary.dispatch_date == dispatch_date
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "SAVED"
        ]

    def list_generated_final_trip_summaries(self, dispatch_date, delivery_date=None):
        return [
            summary
            for summary in self.final_trip_summaries
            if summary.dispatch_date == dispatch_date
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "GENERATED"
        ]

    def list_final_summary_dates(self):
        return sorted(
            {
                summary.dispatch_date
                for summary in self.final_trip_summaries
                if summary.status == "SAVED"
            },
            reverse=True,
        )

    def list_finalized_opshop_pickup_assignments(self, dispatch_date):
        finalized = {}
        summaries = sorted(
            [
                summary
                for summary in self.final_trip_summaries
                if summary.dispatch_date == dispatch_date and summary.status == "SAVED"
            ],
            key=lambda summary: (summary.saved_at or "", summary.summary_id),
            reverse=True,
        )
        for summary in summaries:
            driver = self.get_driver(summary.driver_id)
            driver_name = driver.name if driver else summary.driver_name_snapshot
            for pickup in summary.opshop_pickups or []:
                pickup_task_id = pickup.pickup_task_id_snapshot
                if not pickup_task_id or pickup_task_id in finalized:
                    continue
                finalized[pickup_task_id] = {
                    "pickup_task_id": pickup_task_id,
                    "dispatch_date": summary.dispatch_date,
                    "delivery_date": summary.delivery_date,
                    "driver_id": summary.driver_id,
                    "driver_name": driver_name,
                    "summary_id": summary.summary_id,
                    "saved_at": summary.saved_at,
                }
        return finalized

    def has_saved_final_trip_summary(self, dispatch_date, driver_id, delivery_date=None):
        return any(
            summary.dispatch_date == dispatch_date
            and summary.driver_id == driver_id
            and (not delivery_date or summary.delivery_date == delivery_date)
            and summary.status == "SAVED"
            for summary in self.final_trip_summaries
        )

    def get_final_trip_summary(self, summary_id):
        return next(
            (
                summary
                for summary in self.final_trip_summaries
                if summary.summary_id == summary_id
            ),
            None,
        )

    def get_generated_final_trip_summary_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        return next(
            (
                summary
                for summary in self.final_trip_summaries
                if summary.dispatch_date == dispatch_date
                and summary.delivery_date == delivery_date
                and summary.driver_id == driver_id
                and summary.status == "GENERATED"
            ),
            None,
        )

    def list_delivery_run_sheets(
        self,
        dispatch_date=None,
        delivery_date=None,
        status=None,
    ):
        return [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if (not dispatch_date or run_sheet.dispatch_date == dispatch_date)
            and (not delivery_date or run_sheet.delivery_date == delivery_date)
            and (not status or run_sheet.status == status)
        ]

    def list_reserved_delivery_order_ids(self):
        return {
            order.task_id
            for run_sheet in self.delivery_run_sheets
            if run_sheet.status in {"GENERATED", "SAVED"}
            for trip in run_sheet.trips
            for order in trip.orders
            if order.task_type == "ORDER" and order.task_id
        }

    def list_globally_assigned_delivery_order_ids(self):
        return {
            assignment.task_id
            for assignment in self.assignments
            if assignment.task_type == "ORDER" and assignment.task_id
        }

    def list_globally_assigned_delivery_order_assignments(self):
        return [
            assignment
            for assignment in self.assignments
            if assignment.task_type == "ORDER" and assignment.task_id
        ]

    def list_globally_unavailable_delivery_order_ids(self):
        return (
            self.list_globally_assigned_delivery_order_ids()
            | self.list_reserved_delivery_order_ids()
        )

    def get_delivery_run_sheet_reserving_order(self, order_id):
        reserving_sheets = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if run_sheet.status in {"GENERATED", "SAVED"}
            and any(
                order.task_type == "ORDER" and order.task_id == order_id
                for trip in run_sheet.trips
                for order in trip.orders
            )
        ]
        return next(
            (
                run_sheet
                for run_sheet in sorted(
                    reserving_sheets,
                    key=lambda item: (
                        0 if item.status == "SAVED" else 1,
                        item.generated_at or "",
                        item.run_sheet_id,
                    ),
                )
            ),
            None,
        )

    def get_delivery_run_sheet(self, run_sheet_id):
        return next(
            (
                run_sheet
                for run_sheet in self.delivery_run_sheets
                if run_sheet.run_sheet_id == run_sheet_id
            ),
            None,
        )

    def get_delivery_run_sheet_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        matches = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if run_sheet.delivery_date == delivery_date
            and run_sheet.driver_id == driver_id
        ]
        if len(matches) > 1:
            raise ValueError(
                "Delivery Run Sheet integrity error for "
                f"{delivery_date}:{driver_id}: expected at most one active document."
            )
        return matches[0] if matches else None

    def has_saved_delivery_run_sheet(self, dispatch_date, driver_id, delivery_date):
        run_sheet = self.get_delivery_run_sheet_for_driver(
            dispatch_date,
            delivery_date,
            driver_id,
        )
        return bool(run_sheet and run_sheet.status == "SAVED")

    def upsert_delivery_run_sheet(self, run_sheet):
        duplicate = next(
            (
                existing
                for existing in self.delivery_run_sheets
                if existing.run_sheet_id != run_sheet.run_sheet_id
                and existing.delivery_date == run_sheet.delivery_date
                and existing.driver_id == run_sheet.driver_id
            ),
            None,
        )
        if duplicate:
            raise ValueError(
                "Delivery Run Sheet already exists for this driver and delivery date."
            )
        self.delivery_run_sheets = [
            existing
            for existing in self.delivery_run_sheets
            if existing.run_sheet_id != run_sheet.run_sheet_id
        ]
        self.delivery_run_sheets.append(run_sheet)
        return run_sheet

    def promote_generated_delivery_run_sheet_to_saved(
        self,
        run_sheet_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        for index, run_sheet in enumerate(self.delivery_run_sheets):
            if run_sheet.run_sheet_id != run_sheet_id or run_sheet.status != "GENERATED":
                continue
            self.delivery_run_sheets[index] = replace(
                run_sheet,
                status="SAVED",
                saved_at=saved_at,
                saved_by_account_name=saved_by_account_name,
                saved_by_account_id=saved_by_account_id,
            )
            return True
        return False

    def delete_generated_delivery_run_sheet(self, run_sheet_id):
        before_count = len(self.delivery_run_sheets)
        self.delivery_run_sheets = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if not (
                run_sheet.run_sheet_id == run_sheet_id
                and run_sheet.status == "GENERATED"
            )
        ]
        return len(self.delivery_run_sheets) != before_count

    def delete_delivery_run_sheet(self, run_sheet_id):
        before_count = len(self.delivery_run_sheets)
        self.delivery_run_sheets = [
            run_sheet
            for run_sheet in self.delivery_run_sheets
            if run_sheet.run_sheet_id != run_sheet_id
        ]
        return len(self.delivery_run_sheets) != before_count

    def list_opshop_pickup_collections(
        self,
        dispatch_date=None,
        pickup_date=None,
        status=None,
    ):
        return [
            collection
            for collection in self.opshop_pickup_collections
            if (not dispatch_date or collection.dispatch_date == dispatch_date)
            and (not pickup_date or collection.pickup_date == pickup_date)
            and (not status or collection.status == status)
        ]

    def get_opshop_pickup_collection(self, collection_id):
        return next(
            (
                collection
                for collection in self.opshop_pickup_collections
                if collection.collection_id == collection_id
            ),
            None,
        )

    def get_opshop_pickup_collection_for_driver(
        self,
        dispatch_date,
        pickup_date,
        driver_id,
    ):
        matches = [
            collection
            for collection in self.opshop_pickup_collections
            if collection.pickup_date == pickup_date
            and collection.driver_id == driver_id
        ]
        if len(matches) > 1:
            raise ValueError(
                "OP SHOP Pickup Collection integrity error for "
                f"{pickup_date}:{driver_id}: expected at most one active document."
            )
        return matches[0] if matches else None

    def has_saved_opshop_pickup_collection(self, dispatch_date, driver_id, pickup_date):
        collection = self.get_opshop_pickup_collection_for_driver(
            dispatch_date,
            pickup_date,
            driver_id,
        )
        return bool(collection and collection.status == "SAVED")

    def upsert_opshop_pickup_collection(self, collection):
        duplicate = next(
            (
                existing
                for existing in self.opshop_pickup_collections
                if existing.collection_id != collection.collection_id
                and existing.pickup_date == collection.pickup_date
                and existing.driver_id == collection.driver_id
            ),
            None,
        )
        if duplicate:
            raise ValueError(
                "OP SHOP Pickup Collection already exists for this driver and pickup date."
            )
        self.opshop_pickup_collections = [
            existing
            for existing in self.opshop_pickup_collections
            if existing.collection_id != collection.collection_id
        ]
        self.opshop_pickup_collections.append(collection)
        return collection

    def promote_generated_opshop_pickup_collection_to_saved(
        self,
        collection_id,
        saved_at,
        saved_by_account_name,
        saved_by_account_id,
    ):
        for index, collection in enumerate(self.opshop_pickup_collections):
            if (
                collection.collection_id != collection_id
                or collection.status != "GENERATED"
            ):
                continue
            self.opshop_pickup_collections[index] = replace(
                collection,
                status="SAVED",
                saved_at=saved_at,
                saved_by_account_name=saved_by_account_name,
                saved_by_account_id=saved_by_account_id,
            )
            return True
        return False

    def delete_generated_opshop_pickup_collection(self, collection_id):
        before_count = len(self.opshop_pickup_collections)
        self.opshop_pickup_collections = [
            collection
            for collection in self.opshop_pickup_collections
            if not (
                collection.collection_id == collection_id
                and collection.status == "GENERATED"
            )
        ]
        return len(self.opshop_pickup_collections) != before_count

    def delete_opshop_pickup_collection(self, collection_id):
        before_count = len(self.opshop_pickup_collections)
        self.opshop_pickup_collections = [
            collection
            for collection in self.opshop_pickup_collections
            if collection.collection_id != collection_id
        ]
        return len(self.opshop_pickup_collections) != before_count

    def driver_has_final_summary_history(self, driver_id):
        return any(
            summary.driver_id == driver_id for summary in self.final_trip_summaries
        )

    def vehicle_has_final_summary_history(self, vehicle_id):
        return any(
            summary.vehicle_id == vehicle_id for summary in self.final_trip_summaries
        )

    def save_final_trip_summary(self, summary, rows, opshop_rows=None):
        if self.has_saved_final_trip_summary(
            summary["dispatch_date"], summary["driver_id"], summary.get("delivery_date")
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        self._remove_generated_final_trip_summary_for_driver(
            summary["dispatch_date"],
            summary.get("delivery_date") or summary["dispatch_date"],
            summary["driver_id"],
        )
        final_summary = self._build_final_trip_summary(summary, rows, opshop_rows, "SAVED")
        self.final_trip_summaries.append(final_summary)
        self._finalize_order_rows(final_summary.dispatch_date, rows)
        return final_summary

    def create_generated_final_trip_summary(self, summary, rows, opshop_rows=None):
        if self.has_saved_final_trip_summary(
            summary["dispatch_date"], summary["driver_id"], summary.get("delivery_date")
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        self._remove_generated_final_trip_summary_for_driver(
            summary["dispatch_date"],
            summary.get("delivery_date") or summary["dispatch_date"],
            summary["driver_id"],
        )
        final_summary = self._build_final_trip_summary(summary, rows, opshop_rows, "GENERATED")
        self.final_trip_summaries.append(final_summary)
        return final_summary

    def save_generated_final_trip_summary(self, summary_id, saved_by_account_name, saved_by_account_id):
        summary = self.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        if summary.status != "GENERATED":
            raise ValueError("Only generated Final Trip Summaries can be saved.")
        if self.has_saved_final_trip_summary(
            summary.dispatch_date,
            summary.driver_id,
            summary.delivery_date,
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        summary.status = "SAVED"
        summary.saved_at = "in-memory"
        summary.saved_by_account_name = saved_by_account_name or "Unknown"
        summary.saved_by_account_id = saved_by_account_id
        rows = [
            {
                "task_type": order.task_type,
                "task_id": order.task_id,
            }
            for trip in summary.trips
            for order in trip.orders
        ]
        self._finalize_order_rows(summary.dispatch_date, rows)
        return summary

    def cancel_generated_final_trip_summary(self, summary_id):
        summary = self.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        if summary.status != "GENERATED":
            raise ValueError("Only generated Final Trip Summaries can be cancelled.")

        for trip in summary.trips or []:
            for order in trip.orders or []:
                if order.task_type != "ORDER" or not order.task_id:
                    continue
                existing_order = self.get_order(order.task_id)
                if existing_order and existing_order.status != "CANCELLED":
                    existing_order.status = "ACTIVE"
                self.upsert_assignment(
                    summary.dispatch_date,
                    "ORDER",
                    order.task_id,
                    summary.driver_id,
                    trip.trip_no,
                )

        self.final_trip_summaries = [
            existing
            for existing in self.final_trip_summaries
            if existing.summary_id != summary_id
        ]
        return True

    def _build_final_trip_summary(self, summary, rows, opshop_rows=None, status="SAVED"):
        summary_id = self._create_final_summary_id()
        opshop_rows = opshop_rows or []
        trips = []
        for trip_no in ("trip1", "trip2"):
            trip_orders = []
            for row in rows:
                if row["trip_no"] != trip_no:
                    continue
                trip_orders.append(
                    FinalTripSummaryOrderSnapshot(
                        row_id=self._create_final_summary_row_id(),
                        trip_no=row["trip_no"],
                        row_no=row["row_no"],
                        task_type=row["task_type"],
                        task_id=row["task_id"],
                        order_id_snapshot=row.get("order_id_snapshot"),
                        invoice_number_snapshot=row.get("invoice_number_snapshot"),
                        order_no_snapshot=row.get("order_no_snapshot"),
                        company_name_snapshot=row.get("company_name_snapshot"),
                        suburb_snapshot=row.get("suburb_snapshot"),
                        delivery_address_snapshot=row.get("delivery_address_snapshot"),
                        product_snapshot=row.get("product_snapshot"),
                        pallet_quantity_snapshot=row["pallet_quantity_snapshot"],
                        loose_bags_quantity_snapshot=row["loose_bags_quantity_snapshot"],
                        note_snapshot=row.get("note_snapshot"),
                        product_lines_snapshot=[
                            ProductDetailLine(
                                product_name=line.get("product_name") or "",
                                quantity=int(line.get("quantity") or 0),
                                unit=line.get("unit") or "",
                            )
                            for line in (row.get("product_lines_snapshot") or [])
                        ],
                        estimated_distance_km_from_warehouse_snapshot=row.get(
                            "estimated_distance_km_from_warehouse_snapshot"
                        ),
                    )
                )
            if trip_orders:
                trips.append(FinalTripSummaryTrip(trip_no=trip_no, orders=trip_orders))

        opshop_pickups = [
            FinalTripSummaryOpShopPickupSnapshot(
                row_id=self._create_final_summary_opshop_row_id(),
                row_no=row["row_no"],
                pickup_task_id_snapshot=row["pickup_task_id_snapshot"],
                opshop_name_snapshot=row["opshop_name_snapshot"],
                suburb_snapshot=row.get("suburb_snapshot"),
                street_address_snapshot=row.get("street_address_snapshot"),
                area_region_snapshot=row.get("area_region_snapshot"),
                pickup_date_snapshot=row["pickup_date_snapshot"],
                run_type_snapshot=row.get("run_type_snapshot"),
                pickup_frequency_snapshot=row.get("pickup_frequency_snapshot"),
                time_window_snapshot=row.get("time_window_snapshot"),
                primary_contact_snapshot=row.get("primary_contact_snapshot"),
                primary_phone_snapshot=row.get("primary_phone_snapshot"),
                secondary_contact_snapshot=row.get("secondary_contact_snapshot"),
                secondary_phone_snapshot=row.get("secondary_phone_snapshot"),
                access_type_snapshot=row.get("access_type_snapshot"),
                key_required_snapshot=bool(row.get("key_required_snapshot")),
                trailer_restriction_snapshot=row.get("trailer_restriction_snapshot"),
                notes_snapshot=row.get("notes_snapshot"),
                status_snapshot=row["status_snapshot"],
                pickup_category_snapshot=row.get("pickup_category_snapshot"),
                route_group_id_snapshot=row.get("route_group_id_snapshot"),
                route_group_name_snapshot=row.get("route_group_name_snapshot"),
            )
            for row in opshop_rows
        ]

        saved_at = summary.get("saved_at") or summary.get("generated_at") or "in-memory"
        return FinalTripSummary(
            summary_id=summary_id,
            dispatch_date=summary["dispatch_date"],
            delivery_date=summary.get("delivery_date") or summary["dispatch_date"],
            driver_id=summary["driver_id"],
            driver_name_snapshot=summary["driver_name_snapshot"],
            vehicle_id=summary.get("vehicle_id"),
            vehicle_rego_snapshot=summary.get("vehicle_rego_snapshot"),
            total_pallets=summary["total_pallets"],
            total_loose_bags=summary["total_loose_bags"],
            status=status,
            generated_at=summary.get("generated_at") or saved_at,
            saved_at=saved_at,
            saved_by_account_name=summary.get("saved_by_account_name") or "Unknown",
            saved_by_account_id=summary.get("saved_by_account_id"),
            trips=trips,
            opshop_pickups=opshop_pickups,
        )

    def _finalize_order_rows(self, dispatch_date, rows):
        for row in rows:
            if row["task_type"] == "ORDER":
                order = self.get_order(row["task_id"])
                if order and order.status == "ACTIVE":
                    order.status = "FINALIZED"
                self.remove_assignment(dispatch_date, row["task_type"], row["task_id"])

    def _remove_generated_final_trip_summary_for_driver(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
    ):
        self.final_trip_summaries = [
            summary
            for summary in self.final_trip_summaries
            if not (
                summary.dispatch_date == dispatch_date
                and summary.delivery_date == delivery_date
                and summary.driver_id == driver_id
                and summary.status == "GENERATED"
            )
        ]

    def _create_final_summary_id(self):
        summary_id = f"FTS-{self._next_final_summary_number:03d}"
        self._next_final_summary_number += 1
        return summary_id

    def _create_final_summary_row_id(self):
        row_id = f"FSR-{self._next_final_summary_row_number:03d}"
        self._next_final_summary_row_number += 1
        return row_id

    def _create_final_summary_opshop_row_id(self):
        row_id = f"FSO-{self._next_final_summary_opshop_row_number:03d}"
        self._next_final_summary_opshop_row_number += 1
        return row_id
