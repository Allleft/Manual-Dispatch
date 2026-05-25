from backend.services.manual_dispatch.normalization import (
    bool_or_default,
    clean_optional_text,
    clean_required_text,
    load_unit_for_quantities,
    normalize_product_detail_lines,
    quantity_or_default,
)
from backend.services.manual_dispatch.suburb_distance_service import (
    get_estimated_distance_km,
    sort_orders_by_suburb_distance_then_start_time,
)


class FinalSummaryService:
    def __init__(self, repository, validator):
        self.repository = repository
        self.validator = validator

    def save_final_trip_summary(self, request):
        dispatch_date = clean_required_text(request.dispatch_date, "dispatch_date")
        delivery_date = clean_required_text(
            getattr(request, "delivery_date", None) or dispatch_date,
            "delivery_date",
        )
        driver_id = clean_required_text(request.driver_id, "driver_id")
        self.validator.validate_driver_exists(driver_id)
        saved_by_account = self.validator.validate_saved_by_account(
            request.saved_by_account_name,
            request.saved_by_account_id,
        )

        vehicle_id = clean_optional_text(request.vehicle_id)
        if vehicle_id:
            self.validator.validate_vehicle_exists(vehicle_id)

        if self.repository.has_saved_final_trip_summary(
            dispatch_date,
            driver_id,
            delivery_date,
        ):
            raise ValueError(
                "Final Summary for this driver, dispatch date, and delivery date has already been saved."
            )

        rows = self._normalize_final_summary_rows(request.trips, delivery_date)
        opshop_rows = self._normalize_final_summary_opshop_rows(
            getattr(request, "opshop_pickups", None) or [],
            delivery_date,
        )

        summary = {
            "dispatch_date": dispatch_date,
            "delivery_date": delivery_date,
            "driver_id": driver_id,
            "driver_name_snapshot": clean_required_text(
                request.driver_name_snapshot,
                "driver_name_snapshot",
            ),
            "vehicle_id": vehicle_id,
            "vehicle_rego_snapshot": clean_optional_text(
                request.vehicle_rego_snapshot
            )
            or "No vehicle selected",
            "total_pallets": sum(row["pallet_quantity_snapshot"] for row in rows),
            "total_loose_bags": sum(
                row["loose_bags_quantity_snapshot"] for row in rows
            ),
            "generated_at": clean_optional_text(request.generated_at),
            "saved_by_account_name": saved_by_account.account_name,
            "saved_by_account_id": saved_by_account.account_id,
        }
        return self.repository.save_final_trip_summary(summary, rows, opshop_rows)

    def list_final_trip_summaries(self, dispatch_date, delivery_date=None):
        dispatch_date = clean_required_text(dispatch_date, "dispatch_date")
        delivery_date = clean_optional_text(delivery_date)
        return self.repository.list_final_trip_summaries(dispatch_date, delivery_date)

    def list_final_summary_dates(self):
        return self.repository.list_final_summary_dates()

    def get_final_trip_summary(self, summary_id):
        summary_id = clean_required_text(summary_id, "summary_id")
        summary = self.repository.get_final_trip_summary(summary_id)
        if not summary:
            raise ValueError(f"Final Trip Summary does not exist: {summary_id}")
        return summary

    def _normalize_final_summary_rows(self, trips, delivery_date):
        if not isinstance(trips, list):
            raise ValueError("trips must be a list")

        normalized_rows = []
        row_no = 1
        for trip in trips:
            if not isinstance(trip, dict):
                raise ValueError("Each trip must be an object")

            trip_no = clean_required_text(trip.get("trip_no"), "trip_no")
            self.validator.validate_trip_no(trip_no)

            orders = trip.get("orders") or []
            if not isinstance(orders, list):
                raise ValueError("trip orders must be a list")

            for order_snapshot in orders:
                if not isinstance(order_snapshot, dict):
                    raise ValueError("Each final summary Order row must be an object")

                task_type = clean_required_text(
                    order_snapshot.get("task_type") or "ORDER",
                    "task_type",
                )
                task_id = clean_required_text(
                    order_snapshot.get("task_id")
                    or order_snapshot.get("order_id")
                    or order_snapshot.get("order_id_snapshot"),
                    "task_id",
                )
                self.validator.validate_task_type(task_type)
                if task_type != "ORDER":
                    raise ValueError("Final Trip Summary currently supports ORDER tasks only")
                task = self.repository.get_task(task_type, task_id)
                if not task:
                    raise ValueError(f"Task does not exist: {task_type} {task_id}")
                if (
                    task_type == "ORDER"
                    and getattr(task, "delivery_date", None) != delivery_date
                ):
                    raise ValueError(
                        "Final Summary rows must match the selected delivery date"
                    )

                pallet_quantity_snapshot = quantity_or_default(
                    order_snapshot.get("pallet_quantity_snapshot")
                    if "pallet_quantity_snapshot" in order_snapshot
                    else order_snapshot.get("pallet_quantity"),
                    "pallet_quantity_snapshot",
                )
                loose_bags_quantity_snapshot = quantity_or_default(
                    order_snapshot.get("loose_bags_quantity_snapshot")
                    if "loose_bags_quantity_snapshot" in order_snapshot
                    else order_snapshot.get("loose_bags_quantity"),
                    "loose_bags_quantity_snapshot",
                )
                load_unit = load_unit_for_quantities(
                    pallet_quantity_snapshot,
                    loose_bags_quantity_snapshot,
                )
                product_line_payload = (
                    order_snapshot.get("product_lines_snapshot")
                    if "product_lines_snapshot" in order_snapshot
                    else order_snapshot.get("product_lines")
                )
                if product_line_payload is None and getattr(task, "product_lines", None):
                    product_line_payload = [
                        {
                            "product_name": line.product_name,
                            "quantity": line.quantity,
                            "unit": line.unit,
                        }
                        for line in task.product_lines
                    ]
                product_lines_snapshot = normalize_product_detail_lines(
                    product_line_payload or [],
                    load_unit,
                    "product_lines_snapshot",
                )
                suburb_snapshot = clean_optional_text(
                    order_snapshot.get("suburb_snapshot")
                    or order_snapshot.get("suburb")
                ) or ""
                estimated_distance = order_snapshot.get(
                    "estimated_distance_km_from_warehouse_snapshot"
                )
                if estimated_distance in ("", None):
                    estimated_distance = order_snapshot.get(
                        "estimated_distance_km_from_warehouse"
                    )
                if estimated_distance in ("", None):
                    estimated_distance = get_estimated_distance_km(suburb_snapshot)
                if estimated_distance not in ("", None):
                    estimated_distance = float(estimated_distance)

                normalized_rows.append(
                    {
                        "trip_no": trip_no,
                        "row_no": row_no,
                        "task_type": task_type,
                        "task_id": task_id,
                        "order_id_snapshot": clean_optional_text(
                            order_snapshot.get("order_id_snapshot")
                            or order_snapshot.get("order_id")
                        )
                        or task_id,
                        "invoice_number_snapshot": clean_optional_text(
                            order_snapshot.get("invoice_number_snapshot")
                            or order_snapshot.get("invoice_number")
                        ),
                        "company_name_snapshot": clean_optional_text(
                            order_snapshot.get("company_name_snapshot")
                            or order_snapshot.get("company_name")
                        )
                        or "",
                        "suburb_snapshot": suburb_snapshot,
                        "delivery_address_snapshot": clean_optional_text(
                            order_snapshot.get("delivery_address_snapshot")
                            or order_snapshot.get("delivery_address")
                        )
                        or "",
                        "product_snapshot": clean_optional_text(
                            order_snapshot.get("product_snapshot")
                            or order_snapshot.get("product")
                        ),
                        "product_lines_snapshot": [
                            {
                                "product_name": line.product_name,
                                "quantity": line.quantity,
                                "unit": line.unit,
                            }
                            for line in product_lines_snapshot
                        ],
                        "pallet_quantity_snapshot": pallet_quantity_snapshot,
                        "loose_bags_quantity_snapshot": loose_bags_quantity_snapshot,
                        "note_snapshot": clean_optional_text(
                            order_snapshot.get("note_snapshot")
                            or order_snapshot.get("note")
                        ),
                        "estimated_distance_km_from_warehouse_snapshot": estimated_distance,
                        "_sort_start_time": clean_optional_text(
                            order_snapshot.get("start_time_snapshot")
                            or order_snapshot.get("start_time")
                            or getattr(task, "start_time", None)
                        ),
                    }
                )
                row_no += 1

        sorted_rows = []
        row_no = 1
        for trip_no in ("trip1", "trip2"):
            trip_rows = [
                row for row in normalized_rows if row["trip_no"] == trip_no
            ]
            for row in sort_orders_by_suburb_distance_then_start_time(trip_rows):
                row["row_no"] = row_no
                sorted_rows.append(row)
                row_no += 1

        return sorted_rows

    def _normalize_final_summary_opshop_rows(self, pickups, delivery_date):
        if not isinstance(pickups, list):
            raise ValueError("opshop_pickups must be a list")

        normalized_rows = []
        for row_no, pickup_snapshot in enumerate(pickups, start=1):
            if not isinstance(pickup_snapshot, dict):
                raise ValueError("Each final summary OP SHOP pickup row must be an object")

            task_type = clean_optional_text(pickup_snapshot.get("task_type")) or "OPSHOP_PICKUP"
            self.validator.validate_task_type(task_type)
            if task_type != "OPSHOP_PICKUP":
                raise ValueError("Final Summary OP SHOP pickup rows must use OPSHOP_PICKUP tasks")

            pickup_task_id = clean_required_text(
                pickup_snapshot.get("pickup_task_id_snapshot")
                or pickup_snapshot.get("pickup_task_id")
                or pickup_snapshot.get("task_id"),
                "pickup_task_id",
            )
            task = self.repository.get_opshop_pickup_task(pickup_task_id)
            if not task:
                raise ValueError(f"Task does not exist: OPSHOP_PICKUP {pickup_task_id}")
            if getattr(task, "pickup_date", None) != delivery_date:
                raise ValueError(
                    "Final Summary OP SHOP pickups must match the selected delivery date"
                )

            notes = clean_optional_text(
                pickup_snapshot.get("notes_snapshot") or pickup_snapshot.get("notes")
            )
            if not notes:
                note_parts = [
                    clean_optional_text(pickup_snapshot.get("status_notes")),
                    clean_optional_text(pickup_snapshot.get("task_notes")),
                ]
                notes = "\n".join(part for part in note_parts if part) or None

            normalized_rows.append(
                {
                    "row_no": row_no,
                    "pickup_task_id_snapshot": pickup_task_id,
                    "opshop_name_snapshot": clean_optional_text(
                        pickup_snapshot.get("opshop_name_snapshot")
                        or pickup_snapshot.get("opshop_name")
                    )
                    or pickup_task_id,
                    "suburb_snapshot": clean_optional_text(
                        pickup_snapshot.get("suburb_snapshot")
                        or pickup_snapshot.get("suburb")
                    ),
                    "street_address_snapshot": clean_optional_text(
                        pickup_snapshot.get("street_address_snapshot")
                        or pickup_snapshot.get("street_address")
                    ),
                    "area_region_snapshot": clean_optional_text(
                        pickup_snapshot.get("area_region_snapshot")
                        or pickup_snapshot.get("area_region")
                    ),
                    "pickup_date_snapshot": delivery_date,
                    "run_type_snapshot": clean_optional_text(
                        pickup_snapshot.get("run_type_snapshot")
                        or pickup_snapshot.get("run_type")
                    ),
                    "pickup_frequency_snapshot": clean_optional_text(
                        pickup_snapshot.get("pickup_frequency_snapshot")
                        or pickup_snapshot.get("pickup_frequency")
                    ),
                    "time_window_snapshot": clean_optional_text(
                        pickup_snapshot.get("time_window_snapshot")
                        or pickup_snapshot.get("time_window")
                    ),
                    "primary_contact_snapshot": clean_optional_text(
                        pickup_snapshot.get("primary_contact_snapshot")
                        or pickup_snapshot.get("primary_contact")
                    ),
                    "primary_phone_snapshot": clean_optional_text(
                        pickup_snapshot.get("primary_phone_snapshot")
                        or pickup_snapshot.get("primary_phone")
                    ),
                    "secondary_contact_snapshot": clean_optional_text(
                        pickup_snapshot.get("secondary_contact_snapshot")
                        or pickup_snapshot.get("secondary_contact")
                    ),
                    "secondary_phone_snapshot": clean_optional_text(
                        pickup_snapshot.get("secondary_phone_snapshot")
                        or pickup_snapshot.get("secondary_phone")
                    ),
                    "access_type_snapshot": clean_optional_text(
                        pickup_snapshot.get("access_type_snapshot")
                        or pickup_snapshot.get("access_type")
                    ),
                    "key_required_snapshot": bool_or_default(
                        pickup_snapshot.get("key_required_snapshot")
                        if "key_required_snapshot" in pickup_snapshot
                        else pickup_snapshot.get("key_required"),
                        False,
                    ),
                    "trailer_restriction_snapshot": clean_optional_text(
                        pickup_snapshot.get("trailer_restriction_snapshot")
                        or pickup_snapshot.get("trailer_restriction")
                    ),
                    "notes_snapshot": notes,
                    "status_snapshot": clean_optional_text(
                        pickup_snapshot.get("status_snapshot")
                        or pickup_snapshot.get("status")
                        or getattr(task, "status", None)
                    )
                    or "ASSIGNED",
                }
            )

        return normalized_rows
