import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    EnsureOpShopPickupTasksRequest,
    OpShopLocation,
    OpShopPickupSchedule,
    OpShopPickupTask,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class OpShopPickupGenerationTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.repository.upsert_opshop_location(self._location())
        self.service = ManualDispatchService(self.repository)

    def test_standard_weekly_generates_on_schedule_run_day(self):
        self._add_schedule("SCHED-001", run_day="MONDAY", run_type="STANDARD", frequency="Weekly")

        result = self._generate()

        self.assertEqual(2, result.tasks_created)
        self.assertEqual("2026-05-19", result.window_start)
        self.assertEqual("2026-06-01", result.window_end)
        self.assertEqual(14, result.days)
        self.assertEqual(["2026-05-25", "2026-06-01"], self._pickup_dates())

    def test_standard_weekly_with_explicit_weekday_uses_frequency_day(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="STANDARD",
            frequency="Weekly (Thursday only)",
        )

        result = self._generate()

        self.assertEqual(["2026-05-21", "2026-05-28"], self._pickup_dates())
        self.assertEqual(1, result.warnings["FREQUENCY_WEEKDAY_OVERRIDES_RUN_DAY"])

    def test_standard_two_times_weekly_without_explicit_days_uses_run_day_only(self):
        self._add_schedule(
            "SCHED-001",
            run_day="WEDNESDAY",
            run_type="STANDARD",
            frequency="2x Weekly",
        )

        result = self._generate()

        self.assertEqual(["2026-05-20", "2026-05-27"], self._pickup_dates())
        self.assertEqual(
            1,
            result.warnings["MULTI_WEEKLY_WITHOUT_EXPLICIT_DAYS_USED_RUN_DAY_ONLY"],
        )

    def test_standard_two_times_weekly_with_explicit_days_generates_each_day(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="STANDARD",
            frequency="2 X WEEKLY (WED/FRI)",
        )

        self._generate()

        self.assertEqual(
            ["2026-05-20", "2026-05-22", "2026-05-27", "2026-05-29"],
            self._pickup_dates(),
        )

    def test_standard_fortnightly_group_a_generates_in_anchor_week(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="STANDARD",
            frequency="Fortnightly",
            fortnight_group="A",
        )

        result = self._generate()

        self.assertEqual(["2026-06-01"], self._pickup_dates())
        self.assertEqual(1, result.skip_reasons["FORTNIGHT_GROUP_MISMATCH"])

    def test_standard_fortnightly_group_b_generates_in_next_week(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="STANDARD",
            frequency="Fortnightly",
            fortnight_group="B",
        )

        self._generate()

        self.assertEqual(["2026-05-25"], self._pickup_dates())

    def test_standard_fortnightly_missing_group_does_not_generate(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="STANDARD",
            frequency="Fortnightly",
            fortnight_group=None,
        )

        result = self._generate()

        self.assertEqual(0, result.tasks_created)
        self.assertEqual(1, result.skip_reasons["FORTNIGHT_GROUP_MISSING"])

    def test_regular_weekly_generates_on_schedule_run_day(self):
        self._add_schedule("SCHED-001", run_day="TUESDAY", run_type="REGULAR", frequency="Weekly")

        self._generate()

        self.assertEqual(["2026-05-19", "2026-05-26"], self._pickup_dates())

    def test_regular_weekly_with_explicit_days_generates_each_day(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Weekly (Tuesday & Thursday)",
        )

        self._generate()

        self.assertEqual(
            ["2026-05-19", "2026-05-21", "2026-05-26", "2026-05-28"],
            self._pickup_dates(),
        )

    def test_regular_twice_weekly_with_explicit_days_generates_each_day(self):
        self._add_schedule(
            "SCHED-001",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Twice weekly (Wed & Fri)",
        )

        self._generate()

        self.assertEqual(
            ["2026-05-20", "2026-05-22", "2026-05-27", "2026-05-29"],
            self._pickup_dates(),
        )

    def test_regular_fortnightly_groups_generate_correct_weeks(self):
        self._add_schedule(
            "SCHED-A",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Fortnightly",
            fortnight_group="A",
        )
        self._add_schedule(
            "SCHED-B",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Fortnightly",
            fortnight_group="B",
        )

        self._generate()

        self.assertEqual(["2026-05-25", "2026-06-01"], self._pickup_dates())

    def test_regular_monthly_does_not_generate(self):
        self._add_schedule("SCHED-001", run_day="THURSDAY", run_type="REGULAR", frequency="Monthly")

        result = self._generate()

        self.assertEqual(0, result.tasks_created)
        self.assertEqual(1, result.skip_reasons["MONTHLY_NOT_AUTO_GENERATED"])

    def test_on_call_schedules_never_auto_generate(self):
        self._add_schedule("SCHED-001", run_day="MONDAY", run_type="ON_CALL", frequency="Weekly")
        self._add_schedule(
            "SCHED-002",
            run_day="TUESDAY",
            run_type="ON_CALL",
            frequency="Fortnightly",
            fortnight_group="A",
        )

        result = self._generate()

        self.assertEqual(0, result.tasks_created)
        self.assertEqual(2, result.skip_reasons["ON_CALL_NOT_AUTO_GENERATED"])

    def test_review_required_inactive_and_on_hold_schedules_do_not_generate(self):
        self._add_schedule(
            "SCHED-REVIEW",
            run_day="MONDAY",
            frequency="Weekly",
            review_required=True,
        )
        self._add_schedule(
            "SCHED-INACTIVE",
            run_day="TUESDAY",
            frequency="Weekly",
            active_flag=False,
        )
        self._add_schedule(
            "SCHED-HOLD",
            run_day="WEDNESDAY",
            frequency="Weekly",
            status="On_Hold",
        )

        result = self._generate()

        self.assertEqual(0, result.tasks_created)
        self.assertEqual(1, result.skip_reasons["REVIEW_REQUIRED"])
        self.assertEqual(2, result.skip_reasons["INACTIVE_OR_ON_HOLD"])

    def test_missing_unknown_run_day_and_unknown_frequency_do_not_generate(self):
        self._add_schedule("SCHED-MISSING", run_day=None, frequency="Weekly")
        self._add_schedule("SCHED-UNKNOWN-DAY", run_day="SUNDAY", frequency="Weekly")
        self._add_schedule("SCHED-UNKNOWN-FREQ", run_day="MONDAY", frequency="By request")

        result = self._generate()

        self.assertEqual(0, result.tasks_created)
        self.assertEqual(1, result.skip_reasons["MISSING_RUN_DAY"])
        self.assertEqual(1, result.skip_reasons["UNKNOWN_RUN_DAY"])
        self.assertEqual(1, result.skip_reasons["UNKNOWN_FREQUENCY"])

    def test_same_schedule_and_pickup_date_does_not_duplicate_on_rerun(self):
        self._add_schedule("SCHED-001", run_day="MONDAY", frequency="Weekly")

        first = self._generate()
        second = self._generate()

        self.assertEqual(2, first.tasks_created)
        self.assertEqual(0, second.tasks_created)
        self.assertEqual(2, second.tasks_existing)
        self.assertEqual(2, len(self.repository.list_opshop_pickup_tasks()))

    def test_new_regular_task_with_template_default_creates_actual_assignment(self):
        self._add_schedule(
            "SCHED-DEFAULT",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Weekly",
            default_driver_id="D001",
        )

        self._generate()

        tasks = self.repository.list_opshop_pickup_tasks()
        self.assertEqual(2, len(tasks))
        for task in tasks:
            assignment = self.repository.find_assignment_for_task(
                "OPSHOP_PICKUP",
                task.pickup_task_id,
            )
            self.assertEqual("ASSIGNED", task.status)
            self.assertEqual("D001", task.driver_id)
            self.assertEqual("trip1", task.trip_no)
            self.assertEqual("D001", assignment.driver_id)

    def test_existing_unassigned_regular_task_is_not_reassigned_on_refresh(self):
        self._add_schedule(
            "SCHED-DEFAULT",
            run_day="MONDAY",
            run_type="REGULAR",
            frequency="Weekly",
            default_driver_id="D001",
        )
        self._generate()
        task = self.repository.list_opshop_pickup_tasks()[0]
        self.repository.remove_assignments_for_task("OPSHOP_PICKUP", task.pickup_task_id)
        self.repository.update_opshop_pickup_task_assignment_status(
            task.pickup_task_id,
            "ACTIVE",
            None,
            None,
        )

        self._generate()

        refreshed = self.repository.get_opshop_pickup_task(task.pickup_task_id)
        self.assertEqual("ACTIVE", refreshed.status)
        self.assertIsNone(refreshed.driver_id)
        self.assertIsNone(
            self.repository.find_assignment_for_task(
                "OPSHOP_PICKUP",
                task.pickup_task_id,
            )
        )

    def test_existing_cancelled_task_prevents_regeneration(self):
        self._add_schedule("SCHED-001", run_day="MONDAY", frequency="Weekly")
        self.repository.upsert_opshop_pickup_task(
            self._task(
                "EXISTING-CANCELLED",
                "SCHED-001",
                pickup_date="2026-05-25",
                status="CANCELLED",
            )
        )

        result = self._generate()

        self.assertEqual(1, result.tasks_created)
        self.assertEqual(1, result.tasks_existing)
        self.assertEqual(["2026-05-25", "2026-06-01"], self._pickup_dates())

    def test_generated_task_fields_are_order_independent(self):
        self._add_schedule("SCHED-001", run_day="TUESDAY", run_type="STANDARD", frequency="Weekly")

        self._generate(days=1)
        task = self.repository.list_opshop_pickup_tasks()[0]

        self.assertEqual("OPSHOP_PICKUP", task.task_type)
        self.assertEqual("STANDARD", task.generated_from)
        self.assertEqual("ACTIVE", task.status)
        self.assertEqual(task.pickup_date, task.dispatch_date)
        self.assertIsNone(task.driver_id)
        self.assertIsNone(task.trip_no)
        self.assertEqual([], [order for order in self.repository.list_orders() if order.order_id == task.pickup_task_id])

    def test_sqlite_generation_persists_and_lists_window(self):
        temp_dir = Path.cwd() / "tmp" / f"opshop-generation-test-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True)
        db_path = temp_dir / "manual_dispatch.sqlite3"
        try:
            repository = SQLiteManualDispatchRepository(db_path)
            repository.upsert_opshop_location(self._location())
            repository.upsert_opshop_pickup_schedule(
                self._schedule("SCHED-001", run_day="MONDAY", frequency="Weekly")
            )
            service = ManualDispatchService(repository)

            result = service.ensure_opshop_pickup_tasks_for_window(
                EnsureOpShopPickupTasksRequest(start_date="2026-05-18", days=14)
            )
            tasks = repository.list_opshop_pickup_tasks_for_window(
                "2026-05-19",
                "2026-06-01",
            )

            self.assertEqual(2, result.tasks_created)
            self.assertEqual("2026-05-19", result.window_start)
            self.assertEqual("2026-06-01", result.window_end)
            self.assertEqual(2, len(tasks))
            self.assertEqual(
                "SCHED-001",
                repository.find_opshop_pickup_task_by_schedule_and_date(
                    "SCHED-001",
                    "2026-05-25",
                ).schedule_id,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _generate(self, start_date="2026-05-18", days=14):
        return self.service.ensure_opshop_pickup_tasks_for_window(
            EnsureOpShopPickupTasksRequest(start_date=start_date, days=days)
        )

    def _pickup_dates(self):
        return [
            task.pickup_date
            for task in sorted(
                self.repository.list_opshop_pickup_tasks(),
                key=lambda task: (task.pickup_date, task.pickup_task_id),
            )
        ]

    def _add_schedule(self, schedule_id, **overrides):
        schedule = self._schedule(schedule_id, **overrides)
        self.repository.upsert_opshop_pickup_schedule(schedule)
        return schedule

    def _location(self):
        return OpShopLocation(
            opshop_id="OPSHOP-001",
            name="Northside Op Shop",
            suburb="Coburg",
            street_address="1 Sydney Road",
            area_region="North",
            primary_contact="Mary",
            primary_phone="0400 000 001",
            secondary_contact=None,
            secondary_phone=None,
            access_type="Rear dock",
            key_required=False,
            trailer_restriction=None,
            status_notes=None,
            is_active=True,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
        )

    def _schedule(
        self,
        schedule_id,
        run_day="MONDAY",
        run_type="STANDARD",
        frequency="Weekly",
        active_flag=True,
        status="Active",
        fortnight_group=None,
        review_required=False,
        default_driver_id=None,
    ):
        return OpShopPickupSchedule(
            schedule_id=schedule_id,
            opshop_id="OPSHOP-001",
            run_day=run_day,
            run_type=run_type,
            pickup_frequency=frequency,
            time_window="9-12",
            call_before_arrival=False,
            call_timing=None,
            status=status,
            active_flag=active_flag,
            fortnight_group=fortnight_group,
            review_required=review_required,
            review_reason="Requires review" if review_required else None,
            created_at="2026-05-19T00:00:00+00:00",
            updated_at="2026-05-19T00:00:00+00:00",
            default_driver_id=default_driver_id,
        )

    def _task(self, pickup_task_id, schedule_id, pickup_date, status="ACTIVE"):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=schedule_id,
            opshop_id="OPSHOP-001",
            pickup_date=pickup_date,
            task_type="OPSHOP_PICKUP",
            generated_from="STANDARD",
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
