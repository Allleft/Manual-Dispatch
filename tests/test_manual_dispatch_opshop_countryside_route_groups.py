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
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopTemplateRequest,
    OpShopPickupTask,
    UpdateOpShopCountrysideRouteGroupRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class CountrysideRouteGroupServiceTest(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryManualDispatchRepository()
        self.service = ManualDispatchService(self.repository)

    def test_route_group_create_update_disable_is_soft(self):
        created = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(
                route_group_name="  Bendigo Run  ",
                display_order=10,
            )
        )
        updated = self.service.update_countryside_route_group(
            created.route_group_id,
            UpdateOpShopCountrysideRouteGroupRequest(
                route_group_name="Bendigo and Echuca Run",
                display_order=2,
            ),
        )
        disabled = self.service.disable_countryside_route_group(created.route_group_id)

        self.assertEqual(created.route_group_id, updated.route_group_id)
        self.assertEqual("Bendigo and Echuca Run", updated.route_group_name)
        self.assertEqual(2, updated.display_order)
        self.assertFalse(disabled.active_flag)
        self.assertEqual("On_Hold", disabled.status)
        self.assertEqual(
            [created.route_group_id],
            [
                group.route_group_id
                for group in self.service.list_countryside_route_groups(
                    include_inactive=True
                )
            ],
        )

    def test_create_countryside_template_is_oncall_category_candidate_only(self):
        group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="Albury Route")
        )

        template = self.service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type="ON_CALL",
                pickup_category="COUNTRYSIDE",
                route_group_id=group.route_group_id,
                name="Albury Op Shop",
                suburb="Albury",
                street_address="1 David Street",
                pickup_frequency="On Call",
            )
        )
        countryside_candidates = self.service.list_opshop_pickup_schedule_candidates(
            "countryside"
        )

        self.assertEqual("ON_CALL", template.run_type)
        self.assertEqual("COUNTRYSIDE", template.pickup_category)
        self.assertEqual(group.route_group_id, template.route_group_id)
        self.assertEqual(group.route_group_name, template.route_group_name)
        self.assertEqual([], self.service.list_opshop_pickup_schedule_candidates("oncall"))
        self.assertEqual([template.schedule_id], [item.schedule_id for item in countryside_candidates])
        self.assertEqual(group.route_group_name, countryside_candidates[0].route_group_name)
        self.assertEqual([], self.repository.list_opshop_pickup_tasks())

    def test_countryside_validation_and_multiple_groups_for_same_location(self):
        first_group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="North Route")
        )
        second_group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="South Route")
        )

        first = self._create_countryside_template(first_group.route_group_id)
        second = self._create_countryside_template(second_group.route_group_id)

        self.assertEqual(1, len(self.repository.list_opshop_locations()))
        self.assertNotEqual(first.schedule_id, second.schedule_id)
        self.assertEqual(
            {first_group.route_group_id, second_group.route_group_id},
            {
                schedule.route_group_id
                for schedule in self.repository.list_opshop_pickup_schedules()
            },
        )
        with self.assertRaisesRegex(ValueError, "cannot use COUNTRYSIDE"):
            self.service.create_opshop_template(
                CreateOpShopTemplateRequest(
                    run_type="REGULAR",
                    run_day="MONDAY",
                    pickup_category="COUNTRYSIDE",
                    route_group_id=first_group.route_group_id,
                    name="Bad Regular",
                )
            )
        with self.assertRaisesRegex(ValueError, "active route group"):
            self.service.create_opshop_template(
                CreateOpShopTemplateRequest(
                    run_type="ON_CALL",
                    pickup_category="COUNTRYSIDE",
                    route_group_id="MISSING",
                    name="Missing Group",
                )
            )

    def test_disable_route_group_rejects_active_pickup_tasks(self):
        group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="Task Route")
        )
        template = self._create_countryside_template(group.route_group_id)
        self.repository.upsert_opshop_pickup_task(
            OpShopPickupTask(
                pickup_task_id="COUNTRY-TASK-001",
                schedule_id=template.schedule_id,
                opshop_id=template.opshop_id,
                pickup_date="2026-05-25",
                task_type="OPSHOP_PICKUP",
                generated_from="ON_CALL",
                status="ACTIVE",
                dispatch_date="2026-05-25",
                driver_id=None,
                trip_no=None,
                notes=None,
                created_at="2026-05-25T00:00:00+00:00",
                updated_at="2026-05-25T00:00:00+00:00",
            )
        )

        with self.assertRaisesRegex(ValueError, "active pickup tasks"):
            self.service.disable_countryside_route_group(group.route_group_id)

    def test_board_response_includes_countryside_safe_defaults(self):
        board = self.service.get_board("2026-05-18")

        self.assertEqual([], board.countryside_route_groups)
        self.assertEqual([], board.countryside_opshop_pickups)

    def _create_countryside_template(self, route_group_id):
        return self.service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type="ON_CALL",
                pickup_category="COUNTRYSIDE",
                route_group_id=route_group_id,
                name="Shared Country Shop",
                suburb="Euroa",
                street_address="1 Clifton Street",
                pickup_frequency="On Call",
            )
        )


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class CountrysideRouteGroupRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"opshop-countryside-route-test-{uuid.uuid4().hex}"
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

    def test_route_group_endpoints_and_countryside_candidate_endpoint(self):
        created = self.client.post(
            "/api/manual-dispatch/opshop-countryside-route-groups",
            json={"route_group_name": "API Route", "display_order": 3},
        )
        route_group_id = created.json()["route_group_id"]
        updated = self.client.patch(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}",
            json={"route_group_name": "API Route Updated"},
        )
        template = self.client.post(
            "/api/manual-dispatch/opshop-templates",
            json={
                "run_type": "ON_CALL",
                "pickup_category": "COUNTRYSIDE",
                "route_group_id": route_group_id,
                "name": "API Countryside Shop",
                "suburb": "Bendigo",
                "street_address": "1 Route Road",
                "pickup_frequency": "On Call",
            },
        )
        candidates = self.client.get(
            "/api/manual-dispatch/opshop-pickup-schedules",
            params={"run_type": "countryside"},
        )
        candidates_by_category = self.client.get(
            "/api/manual-dispatch/opshop-pickup-schedules",
            params={"pickup_category": "COUNTRYSIDE"},
        )
        disabled = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{route_group_id}/disable"
        )
        inactive = self.client.get(
            "/api/manual-dispatch/opshop-countryside-route-groups",
            params={"include_inactive": "true"},
        )

        self.assertEqual(200, created.status_code)
        self.assertEqual("API Route Updated", updated.json()["route_group_name"])
        self.assertEqual("COUNTRYSIDE", template.json()["pickup_category"])
        self.assertEqual([template.json()["schedule_id"]], [item["schedule_id"] for item in candidates.json()])
        self.assertEqual(candidates.json(), candidates_by_category.json())
        self.assertFalse(disabled.json()["active_flag"])
        self.assertEqual([route_group_id], [item["route_group_id"] for item in inactive.json()])


if __name__ == "__main__":
    unittest.main()
