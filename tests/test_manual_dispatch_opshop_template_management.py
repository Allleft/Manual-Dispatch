import importlib
import os
import shutil
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
    CreateOpShopTemplateRequest,
    OpShopPickupTask,
    UpdateOpShopTemplateRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

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

    def test_update_non_identity_fields_keeps_schedule_and_updates_location_and_driver(self):
        original = self.service.create_opshop_template(self._regular_request())

        updated = self.service.update_opshop_template(
            original.schedule_id,
            UpdateOpShopTemplateRequest(primary_phone="0400 333 333", access_type="Side gate", default_driver_id="D001"),
        )

        self.assertEqual(original.schedule_id, updated.schedule_id)
        self.assertEqual("0400 333 333", updated.primary_phone)
        self.assertEqual("Side gate", updated.access_type)
        self.assertEqual("D001", updated.default_driver_id)
        self.assertEqual("John", updated.default_driver_name)

    def test_update_identity_fields_creates_active_target_and_preserves_old_task_source(self):
        original = self.service.create_opshop_template(self._regular_request())
        task = self._task("TASK-001", original)
        self.repository.upsert_opshop_pickup_task(task)

        updated = self.service.update_opshop_template(
            original.schedule_id,
            UpdateOpShopTemplateRequest(name="Moved Op Shop", run_day="TUESDAY"),
        )
        old_schedule = self.repository.get_opshop_pickup_schedule(original.schedule_id)

        self.assertNotEqual(original.schedule_id, updated.schedule_id)
        self.assertEqual("TUESDAY", updated.run_day)
        self.assertFalse(old_schedule.active_flag)
        self.assertEqual("On_Hold", old_schedule.status)
        self.assertEqual(original.schedule_id, self.repository.get_opshop_pickup_task("TASK-001").schedule_id)

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
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)

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


if __name__ == "__main__":
    unittest.main()
