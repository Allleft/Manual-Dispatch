from backend.db.connection import connect
from backend.schemas import (
    DeliveryRunSheet,
    DeliveryRunSheetCloseoutSummary,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetOutcome,
    DeliveryRunSheetTrip,
    Driver,
    FinalTripSummary,
    FinalTripSummaryOpShopPickupSnapshot,
    FinalTripSummaryOrderSnapshot,
    FinalTripSummaryTrip,
    ManualDispatchAssignment,
    ManualDriverVehicleAssignment,
    Order,
    OpShopCountrysideRouteGroup,
    OpShopLocation,
    OpShopPickupBoardItem,
    OpShopPickupCollection,
    OpShopPickupCollectionRowSnapshot,
    OpShopPickupSchedule,
    OpShopPickupScheduleCandidate,
    OpShopPickupTask,
    OpShopTemplate,
    OperatorAccountRecord,
    Vehicle,
)

class SQLiteRowMapperMixin:
    """Row Mappers persistence responsibilities."""

    def _row_to_order(self, row):
        return Order(
            order_id=row["order_id"],
            invoice_number=row["invoice_number"],
            order_no=row["order_no"] if "order_no" in row.keys() else None,
            company_name=row["company_name"],
            phone=row["phone"],
            delivery_address=row["delivery_address"],
            suburb=row["suburb"],
            postcode=row["postcode"],
            delivery_date=row["delivery_date"],
            zone=row["zone"],
            urgency=row["urgency"],
            preferred_driver_id=row["preferred_driver_id"],
            pallet_quantity=row["pallet_quantity"],
            loose_bags_quantity=row["loose_bags_quantity"],
            carton_quantity=row["carton_quantity"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            note=row["note"],
            status=row["status"],
            product_lines=self._list_order_product_lines(row["order_id"]),
        )

    def _row_to_driver(self, row):
        return Driver(
            driver_id=row["driver_id"],
            name=row["name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            is_available=bool(row["is_available"]),
            preferred_zone=row["preferred_zone"],
            pallet_only=bool(row["pallet_only"]),
            license_no=row["license_no"],
            email=row["email"],
            phone_number=row["phone_number"],
            is_deleted=bool(row["is_deleted"]),
        )

    def _row_to_vehicle(self, row):
        return Vehicle(
            vehicle_id=row["vehicle_id"],
            rego=row["rego"],
            type=row["type"],
            is_available=bool(row["is_available"]),
            pallet_capacity=row["pallet_capacity"],
            tub_capacity=row["tub_capacity"],
            trolley_capacity=row["trolley_capacity"],
            stillage_capacity=row["stillage_capacity"],
            is_deleted=bool(row["is_deleted"]),
        )

    def _row_to_assignment(self, row):
        return ManualDispatchAssignment(
            assignment_id=row["assignment_id"],
            dispatch_date=row["dispatch_date"],
            task_type=row["task_type"],
            task_id=row["task_id"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
        )

    def _row_to_driver_vehicle_assignment(self, row):
        return ManualDriverVehicleAssignment(
            dispatch_date=row["dispatch_date"],
            delivery_date=row["delivery_date"],
            driver_id=row["driver_id"],
            vehicle_id=row["vehicle_id"],
        )

    def _row_to_final_trip_summary(self, row):
        with connect(self.db_path) as connection:
            summary_rows = connection.execute(
                """
                SELECT *
                FROM final_trip_summary_rows
                WHERE summary_id = ?
                ORDER BY
                    CASE trip_no
                        WHEN 'trip1' THEN 1
                        WHEN 'trip2' THEN 2
                        ELSE 9
                    END,
                    row_no
                """,
                (row["summary_id"],),
            ).fetchall()
            opshop_rows = connection.execute(
                """
                SELECT *
                FROM final_trip_summary_opshop_pickup_rows
                WHERE summary_id = ?
                ORDER BY row_no, row_id
                """,
                (row["summary_id"],),
            ).fetchall()

        trips = []
        for trip_no in ("trip1", "trip2"):
            trip_orders = [
                self._row_to_final_trip_summary_order(summary_row)
                for summary_row in summary_rows
                if summary_row["trip_no"] == trip_no
            ]
            if trip_orders:
                trips.append(FinalTripSummaryTrip(trip_no=trip_no, orders=trip_orders))

        return FinalTripSummary(
            summary_id=row["summary_id"],
            dispatch_date=row["dispatch_date"],
            delivery_date=row["delivery_date"],
            driver_id=row["driver_id"],
            driver_name_snapshot=row["driver_name_snapshot"],
            vehicle_id=row["vehicle_id"],
            vehicle_rego_snapshot=row["vehicle_rego_snapshot"],
            total_pallets=row["total_pallets"],
            total_loose_bags=row["total_loose_bags"],
            total_cartons=_row_value(row, "total_cartons") or 0,
            status=row["status"],
            generated_at=row["generated_at"],
            saved_at=row["saved_at"],
            saved_by_account_name=row["saved_by_account_name"] or "Unknown",
            saved_by_account_id=row["saved_by_account_id"],
            trips=trips,
            opshop_pickups=[
                self._row_to_final_trip_summary_opshop_pickup(opshop_row)
                for opshop_row in opshop_rows
            ],
        )

    def _row_to_final_trip_summary_order(self, row):
        return FinalTripSummaryOrderSnapshot(
            row_id=row["row_id"],
            trip_no=row["trip_no"],
            row_no=row["row_no"],
            task_type=row["task_type"],
            task_id=row["task_id"],
            order_id_snapshot=row["order_id_snapshot"],
            invoice_number_snapshot=row["invoice_number_snapshot"],
            order_no_snapshot=(
                row["order_no_snapshot"] if "order_no_snapshot" in row.keys() else None
            ),
            company_name_snapshot=row["company_name_snapshot"],
            suburb_snapshot=row["suburb_snapshot"],
            delivery_address_snapshot=row["delivery_address_snapshot"],
            product_snapshot=row["product_snapshot"],
            pallet_quantity_snapshot=row["pallet_quantity_snapshot"],
            loose_bags_quantity_snapshot=row["loose_bags_quantity_snapshot"],
            carton_quantity_snapshot=_row_value(row, "carton_quantity_snapshot") or 0,
            note_snapshot=row["note_snapshot"],
            product_lines_snapshot=self._deserialize_product_lines(
                row["product_details_snapshot"]
                if "product_details_snapshot" in row.keys()
                else "[]"
            ),
            estimated_distance_km_from_warehouse_snapshot=(
                row["estimated_distance_km_from_warehouse_snapshot"]
                if "estimated_distance_km_from_warehouse_snapshot" in row.keys()
                else None
            ),
        )

    def _row_to_final_trip_summary_opshop_pickup(self, row):
        return FinalTripSummaryOpShopPickupSnapshot(
            row_id=row["row_id"],
            row_no=row["row_no"],
            pickup_task_id_snapshot=row["pickup_task_id_snapshot"],
            opshop_name_snapshot=row["opshop_name_snapshot"],
            suburb_snapshot=row["suburb_snapshot"],
            street_address_snapshot=row["street_address_snapshot"],
            area_region_snapshot=row["area_region_snapshot"],
            pickup_date_snapshot=row["pickup_date_snapshot"],
            run_type_snapshot=row["run_type_snapshot"],
            pickup_frequency_snapshot=row["pickup_frequency_snapshot"],
            time_window_snapshot=row["time_window_snapshot"],
            primary_contact_snapshot=row["primary_contact_snapshot"],
            primary_phone_snapshot=row["primary_phone_snapshot"],
            secondary_contact_snapshot=row["secondary_contact_snapshot"],
            secondary_phone_snapshot=row["secondary_phone_snapshot"],
            access_type_snapshot=row["access_type_snapshot"],
            key_required_snapshot=bool(row["key_required_snapshot"]),
            trailer_restriction_snapshot=row["trailer_restriction_snapshot"],
            notes_snapshot=row["notes_snapshot"],
            status_snapshot=row["status_snapshot"],
            pickup_category_snapshot=_row_value(row, "pickup_category_snapshot"),
            route_group_id_snapshot=_row_value(row, "route_group_id_snapshot"),
            route_group_name_snapshot=_row_value(row, "route_group_name_snapshot"),
        )

    def _row_to_delivery_run_sheet(self, row):
        with connect(self.db_path) as connection:
            sheet_rows = connection.execute(
                """
                SELECT *
                FROM delivery_run_sheet_rows
                WHERE run_sheet_id = ?
                ORDER BY
                    CASE trip_no WHEN 'trip1' THEN 1 WHEN 'trip2' THEN 2 ELSE 9 END,
                    row_no
                """,
                (row["run_sheet_id"],),
            ).fetchall()
            outcome_rows = connection.execute(
                """
                SELECT *
                FROM delivery_run_sheet_outcomes
                WHERE run_sheet_id = ?
                ORDER BY recorded_at, outcome_id
                """,
                (row["run_sheet_id"],),
            ).fetchall()

        trips = []
        for trip_no in ("trip1", "trip2"):
            orders = [
                DeliveryRunSheetOrderSnapshot(
                    row_id=sheet_row["row_id"],
                    trip_no=sheet_row["trip_no"],
                    row_no=sheet_row["row_no"],
                    task_type=sheet_row["task_type"],
                    task_id=sheet_row["task_id"],
                    order_id_snapshot=sheet_row["order_id_snapshot"],
                    invoice_number_snapshot=sheet_row["invoice_number_snapshot"],
                    order_no_snapshot=sheet_row["order_no_snapshot"],
                    company_name_snapshot=sheet_row["company_name_snapshot"],
                    suburb_snapshot=sheet_row["suburb_snapshot"],
                    delivery_address_snapshot=sheet_row["delivery_address_snapshot"],
                    product_snapshot=sheet_row["product_snapshot"],
                    pallet_quantity_snapshot=sheet_row["pallet_quantity_snapshot"],
                    loose_bags_quantity_snapshot=sheet_row["loose_bags_quantity_snapshot"],
                    carton_quantity_snapshot=sheet_row["carton_quantity_snapshot"],
                    note_snapshot=sheet_row["note_snapshot"],
                    product_lines_snapshot=self._deserialize_product_lines(
                        sheet_row["product_details_snapshot"]
                    ),
                    estimated_distance_km_from_warehouse_snapshot=sheet_row[
                        "estimated_distance_km_from_warehouse_snapshot"
                    ],
                )
                for sheet_row in sheet_rows
                if sheet_row["trip_no"] == trip_no
            ]
            if orders:
                trips.append(DeliveryRunSheetTrip(trip_no=trip_no, orders=orders))

        outcomes = [
            DeliveryRunSheetOutcome(
                outcome_id=outcome_row["outcome_id"],
                run_sheet_id=outcome_row["run_sheet_id"],
                run_sheet_row_id=outcome_row["run_sheet_row_id"],
                order_id=outcome_row["order_id"],
                outcome=outcome_row["outcome"],
                reason_code=outcome_row["reason_code"],
                note=outcome_row["note"],
                next_delivery_date=outcome_row["next_delivery_date"],
                recorded_at=outcome_row["recorded_at"],
                recorded_by_account_id=outcome_row["recorded_by_account_id"],
                recorded_by_account_name=outcome_row[
                    "recorded_by_account_name"
                ],
            )
            for outcome_row in outcome_rows
        ]
        return DeliveryRunSheet(
            run_sheet_id=row["run_sheet_id"],
            dispatch_date=row["dispatch_date"],
            delivery_date=row["delivery_date"],
            driver_id=row["driver_id"],
            driver_name_snapshot=row["driver_name_snapshot"],
            vehicle_id=row["vehicle_id"],
            vehicle_rego_snapshot=row["vehicle_rego_snapshot"],
            total_pallets=row["total_pallets"],
            total_loose_bags=row["total_loose_bags"],
            total_cartons=row["total_cartons"],
            status=row["status"],
            generated_at=row["generated_at"],
            saved_at=row["saved_at"],
            saved_by_account_name=row["saved_by_account_name"],
            saved_by_account_id=row["saved_by_account_id"],
            legacy_summary_id=row["legacy_summary_id"],
            trips=trips,
            execution_status=_row_value(row, "execution_status") or "OPEN",
            closed_at=_row_value(row, "closed_at"),
            closed_by_account_id=_row_value(row, "closed_by_account_id"),
            closed_by_account_name=_row_value(row, "closed_by_account_name"),
            outcomes=outcomes,
            closeout_summary=DeliveryRunSheetCloseoutSummary(
                delivered_count=sum(
                    outcome.outcome == "DELIVERED" for outcome in outcomes
                ),
                returned_to_pool_count=sum(
                    outcome.outcome == "RETURN_TO_POOL" for outcome in outcomes
                ),
            ),
        )

    def _row_to_opshop_pickup_collection(self, row):
        with connect(self.db_path) as connection:
            pickup_rows = connection.execute(
                """
                SELECT *
                FROM opshop_pickup_collection_rows
                WHERE collection_id = ?
                ORDER BY row_no, row_id
                """,
                (row["collection_id"],),
            ).fetchall()

        pickups = [
            OpShopPickupCollectionRowSnapshot(
                row_id=pickup_row["row_id"],
                row_no=pickup_row["row_no"],
                pickup_task_id_snapshot=pickup_row["pickup_task_id_snapshot"],
                opshop_name_snapshot=pickup_row["opshop_name_snapshot"],
                suburb_snapshot=pickup_row["suburb_snapshot"],
                street_address_snapshot=pickup_row["street_address_snapshot"],
                area_region_snapshot=pickup_row["area_region_snapshot"],
                pickup_date_snapshot=pickup_row["pickup_date_snapshot"],
                run_type_snapshot=pickup_row["run_type_snapshot"],
                pickup_category_snapshot=pickup_row["pickup_category_snapshot"],
                route_group_id_snapshot=pickup_row["route_group_id_snapshot"],
                route_group_name_snapshot=pickup_row["route_group_name_snapshot"],
                pickup_frequency_snapshot=pickup_row["pickup_frequency_snapshot"],
                time_window_snapshot=pickup_row["time_window_snapshot"],
                call_before_arrival_snapshot=bool(
                    pickup_row["call_before_arrival_snapshot"]
                ),
                call_timing_snapshot=pickup_row["call_timing_snapshot"],
                primary_contact_snapshot=pickup_row["primary_contact_snapshot"],
                primary_phone_snapshot=pickup_row["primary_phone_snapshot"],
                secondary_contact_snapshot=pickup_row["secondary_contact_snapshot"],
                secondary_phone_snapshot=pickup_row["secondary_phone_snapshot"],
                access_type_snapshot=pickup_row["access_type_snapshot"],
                key_required_snapshot=bool(pickup_row["key_required_snapshot"]),
                trailer_restriction_snapshot=pickup_row["trailer_restriction_snapshot"],
                notes_snapshot=pickup_row["notes_snapshot"],
                status_snapshot=pickup_row["status_snapshot"],
                clothing_kg_snapshot=pickup_row["clothing_kg_snapshot"],
                shoes_kg_snapshot=pickup_row["shoes_kg_snapshot"],
                time_in_snapshot=pickup_row["time_in_snapshot"],
                time_out_snapshot=pickup_row["time_out_snapshot"],
                trolleys_out_to_opshops_snapshot=(
                    pickup_row["trolleys_out_to_opshops_snapshot"]
                ),
                trolleys_in_to_mcc_snapshot=(
                    pickup_row["trolleys_in_to_mcc_snapshot"]
                ),
                hard_toys_snapshot=pickup_row["hard_toys_snapshot"],
                soft_toys_snapshot=pickup_row["soft_toys_snapshot"],
                black_bags_snapshot=pickup_row["black_bags_snapshot"],
                shoe_bags_snapshot=pickup_row["shoe_bags_snapshot"],
            )
            for pickup_row in pickup_rows
        ]
        return OpShopPickupCollection(
            collection_id=row["collection_id"],
            dispatch_date=row["dispatch_date"],
            pickup_date=row["pickup_date"],
            driver_id=row["driver_id"],
            driver_name_snapshot=row["driver_name_snapshot"],
            status=row["status"],
            generated_at=row["generated_at"],
            saved_at=row["saved_at"],
            saved_by_account_name=row["saved_by_account_name"],
            saved_by_account_id=row["saved_by_account_id"],
            legacy_summary_id=row["legacy_summary_id"],
            pickups=pickups,
        )

    def _row_to_operator_account(self, row):
        return OperatorAccountRecord(
            account_id=row["id"],
            account_name=row["account_name"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_location(self, row):
        return OpShopLocation(
            opshop_id=row["opshop_id"],
            name=row["name"],
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status_notes=row["status_notes"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_countryside_route_group(self, row):
        return OpShopCountrysideRouteGroup(
            route_group_id=row["route_group_id"],
            route_group_name=row["route_group_name"],
            status=row["status"],
            active_flag=bool(row["active_flag"]),
            display_order=int(row["display_order"] or 0),
            source_marker=row["source_marker"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_pickup_schedule(self, row):
        return OpShopPickupSchedule(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            status=row["status"],
            active_flag=bool(row["active_flag"]),
            fortnight_group=row["fortnight_group"],
            review_required=bool(row["review_required"]),
            review_reason=row["review_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name_snapshot=row["default_driver_name_snapshot"],
            pickup_category=_row_value(row, "pickup_category", "NORMAL") or "NORMAL",
            route_group_id=_row_value(row, "route_group_id"),
        )

    def _row_to_opshop_pickup_schedule_candidate(self, row):
        return OpShopPickupScheduleCandidate(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            opshop_name=row["opshop_name"] or "",
            suburb=row["suburb"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            primary_phone=row["primary_phone"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name"],
            pickup_category=_row_value(row, "pickup_category", "NORMAL") or "NORMAL",
            route_group_id=_row_value(row, "route_group_id"),
            route_group_name=_row_value(row, "route_group_name"),
        )

    def _row_to_opshop_template(self, row):
        return OpShopTemplate(
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            run_type=row["run_type"],
            run_day=row["run_day"],
            name=row["name"],
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status_notes=row["status_notes"],
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name_snapshot"],
            status=row["status"],
            active_flag=bool(row["active_flag"]),
            pickup_category=_row_value(row, "pickup_category", "NORMAL") or "NORMAL",
            route_group_id=_row_value(row, "route_group_id"),
            route_group_name=_row_value(row, "route_group_name"),
        )

    def _row_to_opshop_pickup_task(self, row):
        return OpShopPickupTask(
            pickup_task_id=row["pickup_task_id"],
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            pickup_date=row["pickup_date"],
            task_type=row["task_type"],
            generated_from=row["generated_from"],
            status=row["status"],
            dispatch_date=row["dispatch_date"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_opshop_pickup_board_item(self, row):
        return OpShopPickupBoardItem(
            pickup_task_id=row["pickup_task_id"],
            task_type=row["task_type"],
            schedule_id=row["schedule_id"],
            opshop_id=row["opshop_id"],
            opshop_name=row["opshop_name"] or "",
            suburb=row["suburb"],
            street_address=row["street_address"],
            area_region=row["area_region"],
            pickup_date=row["pickup_date"],
            dispatch_date=row["dispatch_date"],
            run_day=row["run_day"],
            run_type=row["run_type"],
            pickup_frequency=row["pickup_frequency"],
            time_window=row["time_window"],
            call_before_arrival=bool(row["call_before_arrival"]),
            call_timing=row["call_timing"],
            primary_contact=row["primary_contact"],
            primary_phone=row["primary_phone"],
            secondary_contact=row["secondary_contact"],
            secondary_phone=row["secondary_phone"],
            access_type=row["access_type"],
            key_required=bool(row["key_required"]),
            trailer_restriction=row["trailer_restriction"],
            status=row["status"],
            generated_from=row["generated_from"],
            status_notes=row["status_notes"],
            task_notes=row["task_notes"],
            driver_id=row["driver_id"],
            trip_no=row["trip_no"],
            is_assigned=bool(row["driver_id"] or row["trip_no"]),
            default_driver_id=row["default_driver_id"],
            default_driver_alias=row["default_driver_alias"],
            default_driver_name=row["default_driver_name"],
            assigned_driver_id=row["driver_id"],
            assigned_driver_name=row["assigned_driver_name"],
            pickup_category=_row_value(row, "pickup_category", "NORMAL") or "NORMAL",
            route_group_id=_row_value(row, "route_group_id"),
            route_group_name=_row_value(row, "route_group_name"),
        )


def _row_value(row, column_name, default=None):
    return row[column_name] if column_name in row.keys() else default
