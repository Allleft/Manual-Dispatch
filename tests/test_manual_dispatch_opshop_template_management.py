import importlib
import os
import shutil
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CreateOpShopTemplateRequest,
    OpShopPickupTask,
    UpdateOpShopTemplateRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class OpShopTemplateManagementTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.service = ManualDispatchService(self.repository)

    def test_create_regular_template_creates_location_and_candidate_and_requires_day(self):
        template = self.service.create_opshop_template(self._regular_request())

        self.assertEqual("REGULAR", template.run_type)
        self.assertEqual("MONDAY", template.run_day)
        self.assertEqual(1, len(self.repository.list_opshop_locations()))
        self.assertEqual(
            [template.schedule_id],
            [item.schedule_id for item in self.service.list_opshop_pickup_schedule_candidates()],
        )
        with self.assertRaisesRegex(ValueError, "requires run_day"):
            self.service.create_opshop_template(self._regular_request(run_day=None, name="No Day"))

    def test_create_oncall_template_is_candidate_but_not_pickup_task(self):
        template = self.service.create_opshop_template(self._oncall_request())

        self.assertEqual("ON_CALL", template.run_type)
        self.assertIsNone(template.run_day)
        self.assertEqual(
            [template.schedule_id],
            [item.schedule_id for item in self.service.list_opshop_pickup_schedule_candidates("oncall")],
        )
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_duplicate_create_reuses_schedule_and_disabled_template_reactivates(self):
        first = self.service.create_opshop_template(self._regular_request())
        duplicate = self.service.create_opshop_template(self._regular_request())
        self.service.disable_opshop_template(first.schedule_id)
        restored = self.service.create_opshop_template(self._regular_request())

        self.assertEqual(first.schedule_id, duplicate.schedule_id)
        self.assertEqual(first.schedule_id, restored.schedule_id)
        self.assertEqual(1, len(self.repository.list_opshop_pickup_schedules()))
        self.assertTrue(restored.active_flag)
        self.assertEqual("Active", restored.status)

    def test_update_location_and_operational_details_keeps_location_and_schedule_identity(self):
        original = self.service.create_opshop_template(self._regular_request())
        original_schedule = self.repository.get_opshop_pickup_schedule(
            original.schedule_id
        )
        original_schedule.regular_route_sequence = 4
        self.repository.upsert_opshop_pickup_schedule(original_schedule)

        updated = self.service.update_opshop_template(
            original.schedule_id,
            UpdateOpShopTemplateRequest(
                name="Northside Community Op Shop",
                suburb="Upper Coburg",
                street_address="2 Sydney Road",
                area_region="North East",
                primary_contact="Maria",
                primary_phone="0400 333 333",
                secondary_contact="Sam",
                secondary_phone="0400 444 444",
                call_before_arrival=False,
                call_timing="On approach",
                access_type="Side gate",
                key_required=False,
                trailer_restriction="Van only",
                status_notes="Use loading bay",
                default_driver_id="D001",
            ),
        )

        self.assertEqual(original.opshop_id, updated.opshop_id)
        self.assertEqual(original.schedule_id, updated.schedule_id)
        self.assertEqual("Northside Community Op Shop", updated.name)
        self.assertEqual("Upper Coburg", updated.suburb)
        self.assertEqual("2 Sydney Road", updated.street_address)
        self.assertEqual("North East", updated.area_region)
        self.assertEqual("Maria", updated.primary_contact)
        self.assertEqual("0400 333 333", updated.primary_phone)
        self.assertEqual("Sam", updated.secondary_contact)
        self.assertEqual("0400 444 444", updated.secondary_phone)
        self.assertFalse(updated.call_before_arrival)
        self.assertEqual("On approach", updated.call_timing)
        self.assertEqual("Side gate", updated.access_type)
        self.assertFalse(updated.key_required)
        self.assertEqual("Van only", updated.trailer_restriction)
        self.assertEqual("Use loading bay", updated.status_notes)
        self.assertEqual("D001", updated.default_driver_id)
        self.assertEqual("John", updated.default_driver_name)
        self.assertEqual(4, updated.regular_route_sequence)

    def test_update_schedule_identity_fields_creates_active_target_and_preserves_old_task_source(self):
        original = self.service.create_opshop_template(self._regular_request())
        original_schedule = self.repository.get_opshop_pickup_schedule(
            original.schedule_id
        )
        original_schedule.regular_route_sequence = 3
        self.repository.upsert_opshop_pickup_schedule(original_schedule)
        task = self._task("TASK-001", original)
        self.repository.upsert_opshop_pickup_task(task)

        updated = self.service.update_opshop_template(
            original.schedule_id,
            UpdateOpShopTemplateRequest(name="Moved Op Shop", run_day="TUESDAY"),
        )
        old_schedule = self.repository.get_opshop_pickup_schedule(original.schedule_id)

        self.assertNotEqual(original.schedule_id, updated.schedule_id)
        self.assertEqual(original.opshop_id, updated.opshop_id)
        self.assertEqual("TUESDAY", updated.run_day)
        self.assertFalse(old_schedule.active_flag)
        self.assertEqual("On_Hold", old_schedule.status)
        self.assertEqual(3, old_schedule.regular_route_sequence)
        self.assertIsNone(updated.regular_route_sequence)
        self.assertEqual(original.schedule_id, self.repository.get_opshop_pickup_task("TASK-001").schedule_id)

    def test_suburb_edit_preserves_generated_task_assignment_and_trip_summary_row(self):
        pickup_date = "2026-05-25"
        original = self.service.create_opshop_template(
            self._regular_request(
                name="Rose Street Opshop",
                suburb="FERNTREE GULLY",
                street_address="1 Rose Street",
                primary_contact="John",
            )
        )
        initial_board = self.service.get_opshop_workspace_board(pickup_date)
        original_task = next(
            pickup
            for pickup in initial_board.opshop_pickups
            if pickup.opshop_id == original.opshop_id
            and pickup.pickup_date == pickup_date
        )
        self.assertTrue(original_task.is_assigned)
        assignment_before = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            original_task.pickup_task_id,
        )
        self.assertIsNotNone(assignment_before)

        updated = self.service.update_opshop_template(
            original.schedule_id,
            UpdateOpShopTemplateRequest(suburb="UPPER FERNTREE GULLY"),
        )
        self.service.get_opshop_workspace_board(pickup_date)

        relevant_tasks = [
            task
            for task in self.repository.list_opshop_pickup_tasks()
            if (
                self.repository.get_opshop_location(task.opshop_id)
                and self.repository.get_opshop_location(task.opshop_id).name
                == "Rose Street Opshop"
            )
            and task.pickup_date == pickup_date
        ]
        relevant_summary_rows = [
            pickup
            for pickup in self.service.get_opshop_trip_summary_board(
                pickup_date
            ).opshop_pickups
            if pickup.opshop_name == "Rose Street Opshop"
        ]
        assignment_after = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            original_task.pickup_task_id,
        )

        self.assertEqual(original.opshop_id, updated.opshop_id)
        self.assertEqual(original.schedule_id, updated.schedule_id)
        self.assertEqual(
            [original_task.pickup_task_id],
            [task.pickup_task_id for task in relevant_tasks],
        )
        self.assertEqual(
            [original_task.pickup_task_id],
            [pickup.pickup_task_id for pickup in relevant_summary_rows],
        )
        self.assertEqual("UPPER FERNTREE GULLY", relevant_summary_rows[0].suburb)
        self.assertEqual(assignment_before, assignment_after)

    def test_disable_soft_disables_template_without_deleting_tasks_or_candidates_history(self):
        template = self.service.create_opshop_template(self._regular_request())
        self.repository.upsert_opshop_pickup_task(self._task("TASK-001", template))

        disabled = self.service.disable_opshop_template(template.schedule_id)

        self.assertFalse(disabled.active_flag)
        self.assertEqual("On_Hold", disabled.status)
        self.assertEqual([], self.service.list_opshop_pickup_schedule_candidates())
        self.assertIsNotNone(self.repository.get_opshop_pickup_task("TASK-001"))
        inactive = self.service.list_opshop_templates("REGULAR", include_inactive=True)
        self.assertEqual([template.schedule_id], [item.schedule_id for item in inactive])

    def test_unknown_default_driver_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Driver does not exist"):
            self.service.create_opshop_template(
                self._regular_request(default_driver_id="MISSING")
            )

    def _regular_request(self, **overrides):
        fields = {
            "run_type": "REGULAR",
            "run_day": "MONDAY",
            "name": "Northside Op Shop",
            "suburb": "Coburg",
            "street_address": "1 Sydney Road",
            "area_region": "North",
            "primary_contact": "Mary",
            "primary_phone": "0400 000 001",
            "pickup_frequency": "Weekly",
            "time_window": "09:00-12:00",
            "call_before_arrival": True,
            "call_timing": "30 minutes",
            "access_type": "Rear dock",
            "key_required": True,
            "trailer_restriction": "Small truck only",
            "status_notes": "Ring first",
            "default_driver_id": "D001",
        }
        fields.update(overrides)
        return CreateOpShopTemplateRequest(**fields)

    def _oncall_request(self):
        return CreateOpShopTemplateRequest(
            run_type="ON_CALL",
            run_day=None,
            name="Gavin Donation Centre",
            suburb="Preston",
            street_address="4 High Street",
            pickup_frequency="On Call",
            default_driver_id="D001",
        )

    def _task(self, pickup_task_id, template):
        return OpShopPickupTask(
            pickup_task_id=pickup_task_id,
            schedule_id=template.schedule_id,
            opshop_id=template.opshop_id,
            pickup_date="2026-05-25",
            task_type="OPSHOP_PICKUP",
            generated_from="MANUAL",
            status="ACTIVE",
            dispatch_date="2026-05-25",
            driver_id=None,
            trip_no=None,
            notes=None,
            created_at="2026-05-25T00:00:00+00:00",
            updated_at="2026-05-25T00:00:00+00:00",
        )


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class OpShopTemplateManagementRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-template-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        authenticate_test_client(
            self.client,
            self.service,
            getattr(self, "account", None),
        )

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_template_create_list_update_and_disable_endpoints(self):
        payload = {
            "run_type": "REGULAR",
            "run_day": "MONDAY",
            "name": "Route Test Shop",
            "suburb": "Coburg",
            "street_address": "7 Test Road",
            "pickup_frequency": "Weekly",
            "time_window": "09:00-12:00",
            "default_driver_id": "D001",
        }
        created = self.client.post("/api/manual-dispatch/opshop-templates", json=payload)
        schedule_id = created.json()["schedule_id"]
        listed = self.client.get("/api/manual-dispatch/opshop-templates", params={"run_type": "REGULAR"})
        updated = self.client.patch(
            f"/api/manual-dispatch/opshop-templates/{schedule_id}",
            json={"primary_phone": "0400 777 777"},
        )
        disabled = self.client.post(f"/api/manual-dispatch/opshop-templates/{schedule_id}/disable")
        inactive = self.client.get(
            "/api/manual-dispatch/opshop-templates",
            params={"run_type": "REGULAR", "include_inactive": "true"},
        )

        self.assertEqual(200, created.status_code)
        self.assertEqual([schedule_id], [item["schedule_id"] for item in listed.json()])
        self.assertEqual("0400 777 777", updated.json()["primary_phone"])
        self.assertFalse(disabled.json()["active_flag"])
        self.assertEqual([schedule_id], [item["schedule_id"] for item in inactive.json()])

    def test_sqlite_location_patch_preserves_live_task_and_assignment_identity(self):
        pickup_date = "2026-05-25"
        created = self.client.post(
            "/api/manual-dispatch/opshop-templates",
            json={
                "run_type": "REGULAR",
                "run_day": "MONDAY",
                "name": "Rose Street Opshop",
                "suburb": "FERNTREE GULLY",
                "street_address": "1 Rose Street",
                "primary_contact": "John",
                "pickup_frequency": "Weekly",
                "default_driver_id": "D001",
            },
        )
        self.assertEqual(200, created.status_code)
        original = created.json()
        initial_board = self.service.get_opshop_workspace_board(pickup_date)
        original_task = next(
            pickup
            for pickup in initial_board.opshop_pickups
            if pickup.opshop_id == original["opshop_id"]
            and pickup.pickup_date == pickup_date
        )
        self.assertTrue(original_task.is_assigned)
        assignment_before = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            original_task.pickup_task_id,
        )
        self.assertIsNotNone(assignment_before)

        updated = self.client.patch(
            f"/api/manual-dispatch/opshop-templates/{original['schedule_id']}",
            json={"suburb": "UPPER FERNTREE GULLY"},
        )
        self.assertEqual(200, updated.status_code)
        self.service.get_opshop_workspace_board(pickup_date)

        relevant_tasks = [
            task
            for task in self.repository.list_opshop_pickup_tasks()
            if (
                self.repository.get_opshop_location(task.opshop_id)
                and self.repository.get_opshop_location(task.opshop_id).name
                == "Rose Street Opshop"
            )
            and task.pickup_date == pickup_date
        ]
        summary = self.client.get(
            "/api/manual-dispatch/opshop/trip-summary",
            params={"pickup_date": pickup_date},
        )
        self.assertEqual(200, summary.status_code)
        relevant_summary_rows = [
            pickup
            for pickup in summary.json()["opshop_pickups"]
            if pickup["opshop_name"] == "Rose Street Opshop"
        ]
        assignment_after = self.repository.find_assignment_for_task(
            "OPSHOP_PICKUP",
            original_task.pickup_task_id,
        )

        self.assertEqual(original["opshop_id"], updated.json()["opshop_id"])
        self.assertEqual(original["schedule_id"], updated.json()["schedule_id"])
        self.assertEqual(
            [original_task.pickup_task_id],
            [task.pickup_task_id for task in relevant_tasks],
        )
        self.assertEqual(
            [original_task.pickup_task_id],
            [pickup["pickup_task_id"] for pickup in relevant_summary_rows],
        )
        self.assertEqual(
            "UPPER FERNTREE GULLY",
            relevant_summary_rows[0]["suburb"],
        )
        self.assertEqual(assignment_before, assignment_after)


if __name__ == "__main__":
    unittest.main()
