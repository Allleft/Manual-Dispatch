import unittest

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import OpShopLocation, OpShopPickupSchedule, OpShopPickupTask
from backend.services.manual_dispatch.opshop_regular_frequency import (
    parse_regular_pickup_frequency,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class RegularPickupFrequencyParserTest(unittest.TestCase):
    def test_supported_source_values_preserve_raw_text_and_normalize_rules(self):
        cases = {
            " Weekly  ": ("WEEKLY", (), 1),
            "Fortnight": ("FORTNIGHTLY", (), 0.5),
            "2x Weekly": ("TWICE_WEEKLY", (), 2),
            "2 X WEEKLY (WED/FRI)": (
                "TWICE_WEEKLY",
                ("WEDNESDAY", "FRIDAY"),
                2,
            ),
            "Twice weekly (Monday & Thursday)": (
                "TWICE_WEEKLY",
                ("MONDAY", "THURSDAY"),
                2,
            ),
            "Weekly (Tuesday & Thursday)": (
                "TWICE_WEEKLY",
                ("TUESDAY", "THURSDAY"),
                2,
            ),
            "Monthly (1st Thursday)": ("MONTHLY", ("THURSDAY",), None),
            "": ("UNKNOWN", (), None),
        }

        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                rule = parse_regular_pickup_frequency(raw_value)
                self.assertEqual(expected[0], rule.frequency_type)
                self.assertEqual(expected[1], rule.explicit_weekdays)
                self.assertEqual(expected[2], rule.occurrences_per_week)
                self.assertEqual(" ".join(raw_value.strip().split()), rule.raw_text)

        monthly = parse_regular_pickup_frequency("Monthly (1st Thursday)")
        self.assertEqual(1, monthly.monthly_ordinal)
        self.assertEqual("THURSDAY", monthly.monthly_weekday)


class RegularOpShopPickupGenerationTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.repository.upsert_opshop_location(self._location())
        self.service = ManualDispatchService(self.repository)

    def test_weekly_and_explicit_weekly_generate_only_their_source_slots(self):
        self._add_schedule("MON", "MONDAY", "Weekly")
        self._add_schedule("THU", "THURSDAY", "Weekly (Thursday only)")

        result = self._generate("2026-05-18")

        self.assertEqual(2, result.tasks_created)
        self.assertEqual(["2026-05-18", "2026-05-21"], self._pickup_dates())

    def test_real_workbook_multi_weekly_pattern_is_two_source_slots_not_four(self):
        self._add_schedule("OUR-VILLAGE-MON", "MONDAY", "2x Weekly")
        self._add_schedule("OUR-VILLAGE-WED", "WEDNESDAY", "2x Weekly")

        first_board = self.service.get_opshop_workspace_board("2026-05-18")
        second_board = self.service.get_opshop_workspace_board("2026-05-18")

        self.assertEqual(
            ["2026-05-18", "2026-05-20"],
            [
                pickup.pickup_date
                for pickup in first_board.opshop_pickups
                if pickup.opshop_id == "OPSHOP-001"
            ],
        )
        self.assertEqual(2, len(second_board.opshop_pickups))
        self.assertEqual(2, len(self.repository.list_opshop_pickup_tasks()))

    def test_explicit_twice_weekly_group_validates_companion_rows(self):
        self._add_schedule(
            "PAKENHAM-MON",
            "MONDAY",
            "Twice weekly (Monday & Thursday)",
        )
        self._add_schedule(
            "PAKENHAM-THU",
            "THURSDAY",
            "Twice weekly (Monday & Thursday)",
        )

        result = self._generate("2026-05-18")

        self.assertEqual(["2026-05-18", "2026-05-21"], self._pickup_dates())
        self.assertNotIn("FREQUENCY_SOURCE_CONFLICT", result.warnings)

    def test_generic_twice_weekly_missing_companion_warns_without_guessing(self):
        self._add_schedule("ONLY-MON", "MONDAY", "2x Weekly")

        result = self._generate("2026-05-18")

        self.assertEqual(["2026-05-18"], self._pickup_dates())
        self.assertEqual(1, result.warnings["MISSING_SECOND_WEEKLY_SLOT"])

    def test_explicit_weekdays_conflict_reports_and_uses_source_rows_only(self):
        self._add_schedule(
            "CONFLICT-MON",
            "MONDAY",
            "Twice weekly (Monday & Thursday)",
        )
        self._add_schedule("CONFLICT-WED", "WEDNESDAY", "2x Weekly")

        result = self._generate("2026-05-18")

        self.assertEqual(["2026-05-18", "2026-05-20"], self._pickup_dates())
        self.assertGreaterEqual(result.warnings["FREQUENCY_SOURCE_CONFLICT"], 1)

    def test_duplicate_active_slot_is_deduplicated_and_reported(self):
        self._add_schedule("MON-A", "MONDAY", "Weekly")
        self._add_schedule("MON-B", "MONDAY", "Weekly")

        result = self._generate("2026-05-18")

        self.assertEqual(["2026-05-18"], self._pickup_dates())
        self.assertEqual(1, result.warnings["DUPLICATE_ACTIVE_SCHEDULE_SLOT"])
        self.assertEqual(1, result.skip_reasons["DUPLICATE_ACTIVE_SCHEDULE_SLOT"])

    def test_fortnight_uses_shared_anchor_and_alternates_weeks(self):
        self._add_schedule("FORTNIGHT-MON", "MONDAY", "Fortnight")

        first = self._generate("2026-05-18")
        second = self._generate("2026-05-25")
        third = self._generate("2026-06-01")

        self.assertEqual(1, first.tasks_created)
        self.assertEqual(0, second.tasks_created)
        self.assertEqual(1, third.tasks_created)
        self.assertEqual(["2026-05-18", "2026-06-01"], self._pickup_dates())

    def test_monthly_first_thursday_generates_only_matching_ordinal(self):
        self._add_schedule(
            "MONTHLY-THU",
            "THURSDAY",
            "Monthly (1st Thursday)",
        )

        first = self._generate("2026-06-01")
        second = self._generate("2026-06-08")

        self.assertEqual(1, first.tasks_created)
        self.assertEqual(0, second.tasks_created)
        self.assertEqual(["2026-06-04"], self._pickup_dates())

    def test_blank_and_unknown_frequency_never_generate(self):
        self._add_schedule("BLANK", "MONDAY", "")
        self._add_schedule("UNKNOWN", "TUESDAY", "Whenever needed")

        result = self._generate("2026-05-18")

        self.assertEqual([], self._pickup_dates())
        self.assertEqual(1, result.skip_reasons["MISSING_PICKUP_FREQUENCY"])
        self.assertEqual(1, result.skip_reasons["UNKNOWN_FREQUENCY"])

    def test_refresh_preserves_manual_unassign_and_cancelled_task(self):
        self._add_schedule(
            "DEFAULT-MON",
            "MONDAY",
            "Weekly",
            default_driver_id="D001",
        )
        self._add_schedule("CANCELLED-WED", "WEDNESDAY", "Weekly")
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "EXISTING-CANCELLED",
                "CANCELLED-WED",
                "2026-05-20",
                status="CANCELLED",
            )
        )

        self._generate("2026-05-18")
        assigned = self.repository.find_opshop_pickup_task_by_schedule_and_date(
            "DEFAULT-MON",
            "2026-05-18",
        )
        self.repository.remove_assignments_for_task(
            "OPSHOP_PICKUP",
            assigned.pickup_task_id,
        )
        self.repository.update_opshop_pickup_task_assignment_status(
            assigned.pickup_task_id,
            "ACTIVE",
            None,
            None,
        )

        second = self._generate("2026-05-18")
        refreshed = self.repository.get_opshop_pickup_task(assigned.pickup_task_id)

        self.assertEqual(0, second.tasks_created)
        self.assertEqual("ACTIVE", refreshed.status)
        self.assertIsNone(refreshed.driver_id)
        self.assertIsNone(
            self.repository.find_assignment_for_task(
                "OPSHOP_PICKUP",
                assigned.pickup_task_id,
            )
        )
        cancelled = self.repository.get_opshop_pickup_task("EXISTING-CANCELLED")
        self.assertEqual("CANCELLED", cancelled.status)

    def _generate(self, dispatch_date):
        return self.service.opshop_pickup_service.ensure_regular_opshop_pickup_tasks_for_week(dispatch_date)

    def _add_schedule(
        self,
        schedule_id,
        run_day,
        frequency,
        *,
        default_driver_id=None,
    ):
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id="OPSHOP-001",
                run_day=run_day,
                run_type="REGULAR",
                pickup_frequency=frequency,
                time_window="9-12",
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason="WORKBOOK_IMPORT",
                created_at="2026-05-19T00:00:00+00:00",
                updated_at="2026-05-19T00:00:00+00:00",
                default_driver_id=default_driver_id,
                pickup_category="NORMAL",
            )
        )

    def _pickup_dates(self):
        return sorted(
            task.pickup_date
            for task in self.repository.list_opshop_pickup_tasks()
        )

    @staticmethod
    def _location():
        return OpShopLocation(
            opshop_id="OPSHOP-001",
            name="OUR VILLAGE NETWORK (St Kilda mums)",
            suburb="CLAYTON",
            street_address="14 Winterton Road",
            area_region="Metro",
            primary_contact=None,
            primary_phone=None,
            secondary_contact=None,
            secondary_phone=None,
            access_type=None,
            key_required=False,
            trailer_restriction=None,
            status_notes=None,
            is_active=True,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )

    @staticmethod
    def _task(pickup_task_id, schedule_id, pickup_date, status="ACTIVE"):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=schedule_id,
            opshop_id="OPSHOP-001",
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="REGULAR",
            status=status,
            dispatch_date=pickup_date,
            driver_id=None,
            trip_no=None,
            notes=None,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
