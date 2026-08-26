from . import FacadeAuditRecorder


class DeliveryEventRecorder(FacadeAuditRecorder):
    """Record delivery event recorder events without changing semantics."""

    def _record_order_event(self, action, order):
        if not order:
            return
        label = self._order_entity_id(order)
        verb = {
            "ORDER_CREATED": "created",
            "ORDER_UPDATED": "updated",
            "ORDER_CANCELLED": "cancelled",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action=action,
            entity_type="ORDER",
            entity_id=label,
            summary=f"Order {label} was {verb}.",
            delivery_date=order.delivery_date,
            metadata={
                "order_id": order.order_id,
                "invoice_number": order.invoice_number,
                "order_no": order.order_no,
                "company_name": order.company_name,
                "suburb": order.suburb,
                "pallet_quantity": order.pallet_quantity,
                "loose_bags_quantity": order.loose_bags_quantity,
            },
        )

    def record_delivery_order_date_rollovers(self, rollovers):
        for change in rollovers or []:
            order_id = change["order_id"]
            label = (
                change.get("invoice_number")
                or change.get("order_no")
                or order_id
            )
            previous_date = change["previous_delivery_date"]
            new_date = change["new_delivery_date"]
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                actor="System",
                action="ORDER_DELIVERY_DATE_ROLLED_FORWARD",
                entity_type="ORDER",
                entity_id=label,
                summary=(
                    f"Order {label} Delivery Date was automatically rolled forward "
                    f"from {previous_date} to {new_date}."
                ),
                delivery_date=new_date,
                metadata={
                    "order_id": order_id,
                    "invoice_number": change.get("invoice_number"),
                    "order_no": change.get("order_no"),
                    "previous_delivery_date": previous_date,
                    "new_delivery_date": new_date,
                    "reason": "unassigned_daily_rollover",
                },
            )

    def record_delivery_order_area_change(self, before, order):
        if not order:
            return
        before = dict(before or {})
        cleared = order.delivery_area_override is None
        action = (
            "ORDER_DELIVERY_AREA_OVERRIDE_CLEARED"
            if cleared
            else "ORDER_DELIVERY_AREA_OVERRIDDEN"
        )
        label = self._order_entity_id(order)
        if cleared:
            summary = (
                f"Order {label} Delivery Area override was cleared; automatic "
                f"area is {order.auto_delivery_area or 'Needs Review'}."
            )
        else:
            summary = (
                f"Order {label} moved from "
                f"{before.get('delivery_area') or 'Needs Review'} to "
                f"{order.delivery_area}."
            )
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action=action,
            entity_type="ORDER",
            entity_id=label,
            summary=summary,
            delivery_date=order.delivery_date,
            metadata={
                "order_id": order.order_id,
                "previous_effective_area": before.get("delivery_area"),
                "new_effective_area": order.delivery_area,
                "auto_delivery_area": order.auto_delivery_area,
                "auto_delivery_region": order.auto_delivery_region,
                "previous_override_area": before.get("delivery_area_override"),
                "new_override_area": order.delivery_area_override,
                "delivery_area_source": order.delivery_area_source,
                "suburb": order.suburb,
                "postcode": order.postcode,
            },
        )

    def _record_delivery_assignment_change(
        self,
        dispatch_date,
        order_id,
        before,
        after,
    ):
        if before == after:
            return
        order = self.repository.get_order(order_id) if order_id else None
        entity_id = self._order_entity_id(order) if order else order_id
        dispatch_date = (
            (after or before or {}).get("dispatch_date")
            or dispatch_date
            or (order.delivery_date if order else None)
        )
        metadata = {
            "before": self._assignment_log_metadata(before),
            "after": self._assignment_log_metadata(after),
            "order_id": order_id,
        }
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="ORDER_UNASSIGNED",
                entity_type="ORDER",
                entity_id=entity_id,
                summary=(
                    f"Order {entity_id} was unassigned from "
                    f"{self._assignment_label(before)}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=order.delivery_date if order else None,
                driver=before.get("driver"),
                metadata=metadata,
            )
            return
        if not after:
            return
        if before:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="ORDER_REASSIGNED",
                entity_type="ORDER",
                entity_id=entity_id,
                summary=(
                    f"Order {entity_id} was reassigned from "
                    f"{self._assignment_label(before)} to "
                    f"{self._assignment_label(after)}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=order.delivery_date if order else None,
                driver=after.get("driver"),
                metadata=metadata,
            )
            return
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="ORDER_ASSIGNED",
            entity_type="ORDER",
            entity_id=entity_id,
            summary=(
                f"Order {entity_id} was assigned to "
                f"{self._assignment_label(after)}."
            ),
            dispatch_date=dispatch_date,
            delivery_date=order.delivery_date if order else None,
            driver=after.get("driver"),
            metadata=metadata,
        )

    def _record_vehicle_assignment_change(
        self,
        dispatch_date,
        delivery_date,
        driver_id,
        before,
        after,
    ):
        if before == after:
            return
        driver = self._driver_name(driver_id)
        dispatch_date = (
            (after or before or {}).get("dispatch_date")
            or dispatch_date
            or delivery_date
        )
        metadata = {"before": before or {}, "after": after or {}}
        if before and not after:
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                action="VEHICLE_CLEARED",
                entity_type="VEHICLE",
                entity_id=before.get("vehicle_id"),
                summary=(
                    f"Vehicle {before.get('vehicle')} was cleared from {driver} "
                    f"for delivery date {delivery_date}."
                ),
                dispatch_date=dispatch_date,
                delivery_date=delivery_date,
                driver=driver,
                vehicle=before.get("vehicle"),
                metadata=metadata,
            )
            return
        if not after:
            return
        action = "VEHICLE_CHANGED" if before else "VEHICLE_ASSIGNED"
        if before:
            summary = (
                f"Vehicle for {driver} on delivery date {delivery_date} was "
                f"changed from {before.get('vehicle')} to {after.get('vehicle')}."
            )
        else:
            summary = (
                f"Vehicle {after.get('vehicle')} was assigned to {driver} "
                f"for delivery date {delivery_date}."
            )
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action=action,
            entity_type="VEHICLE",
            entity_id=after.get("vehicle_id"),
            summary=summary,
            dispatch_date=dispatch_date,
            delivery_date=delivery_date,
            driver=driver,
            vehicle=after.get("vehicle"),
            metadata=metadata,
        )

    @staticmethod
    def _delivery_run_sheet_counts(run_sheet):
        return (
            sum(len(trip.orders) for trip in run_sheet.trips),
            {trip.trip_no: len(trip.orders) for trip in run_sheet.trips},
        )

    def record_delivery_run_sheet_export(self, run_sheet, filename):
        order_count, trip_counts = self._delivery_run_sheet_counts(run_sheet)
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="DELIVERY_RUN_SHEET_EXPORTED",
            entity_type="DELIVERY_RUN_SHEET",
            entity_id=run_sheet.run_sheet_id,
            summary=(
                "Delivery Run Sheet Excel export was generated for "
                f"{run_sheet.driver_name_snapshot} on {run_sheet.delivery_date}."
            ),
            dispatch_date=run_sheet.dispatch_date,
            delivery_date=run_sheet.delivery_date,
            driver=run_sheet.driver_name_snapshot,
            vehicle=run_sheet.vehicle_rego_snapshot,
            run_sheet_id=run_sheet.run_sheet_id,
            metadata={
                "export_scope": "single",
                "status": run_sheet.status,
                "order_count": order_count,
                "trip1_count": trip_counts.get("trip1", 0),
                "trip2_count": trip_counts.get("trip2", 0),
                "filename": filename,
            },
        )

    def record_delivery_run_sheets_daily_export(
        self,
        run_sheets,
        delivery_date,
        filename,
    ):
        statuses = [str(run_sheet.status or "").upper() for run_sheet in run_sheets]
        run_sheet_label = "Run Sheet" if len(run_sheets) == 1 else "Run Sheets"
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            action="DELIVERY_RUN_SHEETS_DAILY_EXPORTED",
            entity_type="DELIVERY_RUN_SHEET_BATCH",
            entity_id=delivery_date,
            summary=(
                "Daily Delivery Run Sheets Excel export was generated for "
                f"{delivery_date} with {len(run_sheets)} {run_sheet_label}."
            ),
            delivery_date=delivery_date,
            metadata={
                "export_scope": "daily",
                "run_sheet_count": len(run_sheets),
                "saved_count": statuses.count("SAVED"),
                "generated_count": statuses.count("GENERATED"),
                "filename": filename,
            },
        )

    def record_delivery_run_sheet_closeout(self, run_sheet):
        outcomes_by_row_id = {
            outcome.run_sheet_row_id: outcome
            for outcome in run_sheet.outcomes
        }
        snapshots_by_row_id = {
            order.row_id: order
            for trip in run_sheet.trips
            for order in trip.orders
        }
        summary = run_sheet.closeout_summary
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            actor=run_sheet.closed_by_account_name,
            action="DELIVERY_RUN_SHEET_CLOSED",
            entity_type="DELIVERY_RUN_SHEET",
            entity_id=run_sheet.run_sheet_id,
            summary=(
                f"Delivery Run Sheet was closed for "
                f"{run_sheet.driver_name_snapshot} on {run_sheet.delivery_date}: "
                f"{summary.delivered_count} delivered and "
                f"{summary.returned_to_pool_count} returned to pool."
            ),
            dispatch_date=run_sheet.dispatch_date,
            delivery_date=run_sheet.delivery_date,
            driver=run_sheet.driver_name_snapshot,
            vehicle=run_sheet.vehicle_rego_snapshot,
            run_sheet_id=run_sheet.run_sheet_id,
            metadata={
                "run_sheet_id": run_sheet.run_sheet_id,
                "delivery_date": run_sheet.delivery_date,
                "driver": run_sheet.driver_name_snapshot,
                "delivered_count": summary.delivered_count,
                "returned_to_pool_count": summary.returned_to_pool_count,
                "operator": run_sheet.closed_by_account_name,
                "timestamp": run_sheet.closed_at,
            },
        )
        for row_id, outcome in outcomes_by_row_id.items():
            snapshot = snapshots_by_row_id.get(row_id)
            previous_trip = snapshot.trip_no if snapshot else None
            action = (
                "DELIVERY_ORDER_DELIVERED"
                if outcome.outcome == "DELIVERED"
                else "DELIVERY_ORDER_RETURNED_TO_POOL"
            )
            metadata = {
                "order_id": outcome.order_id,
                "run_sheet_id": run_sheet.run_sheet_id,
                "previous_driver": run_sheet.driver_name_snapshot,
                "previous_trip": previous_trip,
                "previous_delivery_date": run_sheet.delivery_date,
            }
            if outcome.outcome == "RETURN_TO_POOL":
                metadata.update(
                    {
                        "next_delivery_date": outcome.next_delivery_date,
                        "reason_code": outcome.reason_code,
                        "note": outcome.note,
                    }
                )
            self._record_logbook(
                result="SUCCESS",
                workspace="DELIVERY",
                actor=run_sheet.closed_by_account_name,
                action=action,
                entity_type="ORDER",
                entity_id=outcome.order_id,
                summary=(
                    f"Delivery Order {outcome.order_id} was "
                    f"{'delivered' if outcome.outcome == 'DELIVERED' else 'returned to the Delivery Task Pool'}."
                ),
                dispatch_date=run_sheet.dispatch_date,
                delivery_date=(
                    outcome.next_delivery_date
                    if outcome.outcome == "RETURN_TO_POOL"
                    else run_sheet.delivery_date
                ),
                driver=run_sheet.driver_name_snapshot,
                run_sheet_id=run_sheet.run_sheet_id,
                metadata=metadata,
            )

    def record_attache_import_confirmation(self, rows, outcome):
        rows = list(rows or [])
        if not rows:
            return
        imported_count = int(outcome.get("imported_count") or 0)
        skipped_count = int(outcome.get("skipped_count") or 0)
        order_label = "order" if imported_count == 1 else "orders"
        row_label = "row" if skipped_count == 1 else "rows"
        if imported_count and skipped_count:
            result = "PARTIAL"
            summary = (
                f"Attach\u00e9 import confirmed: {imported_count} {order_label} imported "
                f"and {skipped_count} {row_label} skipped."
            )
        elif imported_count:
            result = "SUCCESS"
            summary = (
                f"Attach\u00e9 import confirmed: {imported_count} {order_label} imported."
            )
        else:
            result = "FAILED"
            summary = (
                "Attach\u00e9 import confirmed but no orders were imported; "
                f"{skipped_count} {row_label} skipped."
            )

        source_filenames = []
        for row in rows:
            raw_name = getattr(row, "source_filename", None)
            if not raw_name:
                continue
            basename = str(raw_name).replace("\\", "/").rsplit("/", 1)[-1]
            if basename and basename not in source_filenames:
                source_filenames.append(basename)

        duplicate_row_ids = {
            getattr(row, "row_id", None)
            or getattr(row, "invoice_number", None)
            or getattr(row, "source_filename", None)
            or "row"
            for row in rows
            if bool(getattr(row, "is_duplicate", False))
        }
        duplicate_count = len(duplicate_row_ids)
        for skipped in outcome.get("skipped_rows") or []:
            if (
                "duplicate" in str(skipped.get("reason") or "").lower()
                and skipped.get("row_id") not in duplicate_row_ids
            ):
                duplicate_count += 1
        unselected_count = sum(
            not bool(getattr(row, "selected", False))
            for row in rows
        )
        metadata = {
            "selected_count": sum(
                bool(getattr(row, "selected", False))
                for row in rows
            ),
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "duplicate_count": duplicate_count,
            "invalid_count": max(
                skipped_count - unselected_count - duplicate_count,
                0,
            ),
            "source_file_count": len(source_filenames),
            "source_filenames": source_filenames[:20],
            "source_filenames_truncated": len(source_filenames) > 20,
        }
        if result == "FAILED":
            metadata["failure_reason"] = "No orders were imported"
        self._record_logbook(
            result=result,
            workspace="DELIVERY",
            action="ATTACHE_IMPORT_CONFIRMED",
            entity_type="ATTACHE_IMPORT_BATCH",
            entity_id=None,
            summary=summary,
            metadata=metadata,
        )

    def _record_delivery_run_sheet_event(self, action, run_sheet, actor=None):
        order_count, trip_counts = self._delivery_run_sheet_counts(run_sheet)
        verb = {
            "DELIVERY_RUN_SHEET_GENERATED": "generated",
            "DELIVERY_RUN_SHEET_CANCELLED": "cancelled",
            "DELIVERY_RUN_SHEET_SAVED": "saved",
        }.get(action, "updated")
        self._record_logbook(
            result="SUCCESS",
            workspace="DELIVERY",
            actor=actor,
            action=action,
            entity_type="DELIVERY_RUN_SHEET",
            entity_id=run_sheet.run_sheet_id,
            summary=(
                f"Delivery Run Sheet was {verb} for "
                f"{run_sheet.driver_name_snapshot} on {run_sheet.delivery_date} "
                f"with {order_count} orders."
            ),
            dispatch_date=run_sheet.dispatch_date,
            delivery_date=run_sheet.delivery_date,
            driver=run_sheet.driver_name_snapshot,
            vehicle=run_sheet.vehicle_rego_snapshot,
            run_sheet_id=run_sheet.run_sheet_id,
            metadata={
                "order_count": order_count,
                "trip1_count": trip_counts.get("trip1", 0),
                "trip2_count": trip_counts.get("trip2", 0),
                "total_pallets": run_sheet.total_pallets,
                "total_loose_bags": run_sheet.total_loose_bags,
                "status": run_sheet.status,
            },
        )

    def _record_failed_assignment(self, request, before, error, unassign=False):
        if request.task_type == "ORDER":
            self._record_failed_logbook(
                workspace="DELIVERY",
                action="ORDER_UNASSIGNED" if unassign else (
                    "ORDER_REASSIGNED" if before else "ORDER_ASSIGNED"
                ),
                entity_type="ORDER",
                entity_id=self._order_entity_id_by_id(request.task_id),
                summary=f"Order {self._order_entity_id_by_id(request.task_id)} assignment failed.",
                dispatch_date=request.dispatch_date,
                delivery_date=self._order_delivery_date(request.task_id),
                driver=self._driver_name(getattr(request, "driver_id", None)),
                metadata={"failure_reason": str(error)},
            )
            return
        if request.task_type == "OPSHOP_PICKUP":
            self._record_failed_logbook(
                workspace="OPSHOP",
                action="OPSHOP_TASK_UNASSIGNED" if unassign else (
                    "OPSHOP_TASK_REASSIGNED" if before else "OPSHOP_TASK_ASSIGNED"
                ),
                entity_type="OPSHOP_PICKUP",
                entity_id=request.task_id,
                summary=(
                    f"OP SHOP pickup {self._opshop_pickup_name(request.task_id)} "
                    "assignment failed."
                ),
                dispatch_date=request.dispatch_date,
                pickup_date=self._opshop_pickup_date(request.task_id),
                driver=self._driver_name(getattr(request, "driver_id", None)),
                metadata={"failure_reason": str(error)},
            )

    def _assignment_snapshot(self, _dispatch_date, task_type, task_id):
        if not task_type or not task_id:
            return None
        assignment = self.repository.find_assignment_for_task(
            task_type, task_id
        )
        if not assignment:
            return None
        return {
            "dispatch_date": assignment.dispatch_date,
            "driver_id": assignment.driver_id,
            "driver": self._driver_name(assignment.driver_id),
            "trip_no": assignment.trip_no,
            "trip": self._trip_label(assignment.trip_no),
        }

    def _assignment_log_metadata(self, snapshot):
        if not snapshot:
            return None
        return {
            "dispatch_date": snapshot.get("dispatch_date"),
            "driver_id": snapshot.get("driver_id"),
            "driver": snapshot.get("driver"),
            "trip": snapshot.get("trip_no"),
        }

    def _assignment_label(self, snapshot):
        if not snapshot:
            return "Unassigned"
        return f"{snapshot.get('driver') or 'Unknown'} / {snapshot.get('trip') or 'Trip'}"

    def _vehicle_assignment_snapshot(self, _dispatch_date, delivery_date, driver_id):
        if not delivery_date or not driver_id:
            return None
        assignments = self.repository.list_driver_vehicle_assignments_for_delivery_date(
            delivery_date
        )
        assignment = next(
            (
                item
                for item in assignments
                if item.driver_id == driver_id
            ),
            None,
        )
        if not assignment:
            return None
        return {
            "dispatch_date": assignment.dispatch_date,
            "vehicle_id": assignment.vehicle_id,
            "vehicle": self._vehicle_label(assignment.vehicle_id),
        }

    def _order_entity_id(self, order):
        if not order:
            return None
        return order.invoice_number or order.order_no or order.order_id

    def _order_entity_id_by_id(self, order_id):
        order = self.repository.get_order(order_id) if order_id else None
        return self._order_entity_id(order) or order_id

    def _order_delivery_date(self, order_id):
        order = self.repository.get_order(order_id) if order_id else None
        return order.delivery_date if order else None

    @staticmethod
    def _trip_label(trip_no):
        labels = {"trip1": "Trip 1", "trip2": "Trip 2"}
        return labels.get(trip_no, trip_no)
