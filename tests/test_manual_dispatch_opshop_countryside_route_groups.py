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
    ApplyCountrysideOpShopPickupAssignmentsRequest,
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopTemplateRequest,
    CreateOpShopPickupTaskRequest,
    OpShopPickupTask,
    RegisterOperatorAccountRequest,
    SaveFinalTripSummaryRequest,
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

    def test_apply_countryside_assignments_assigns_countryside_pickups_only(self):
        group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="Apply Route")
        )
        countryside_template = self._create_countryside_template(group.route_group_id)
        countryside_task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id=countryside_template.schedule_id,
                pickup_date="2026-05-25",
            )
        )
        normal_template = self.service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type="ON_CALL",
                name="Normal Oncall Shop",
                suburb="Geelong",
                street_address="1 Normal Road",
                pickup_frequency="On Call",
            )
        )
        normal_task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id=normal_template.schedule_id,
                pickup_date="2026-05-25",
            )
        )

        board = self.service.apply_countryside_opshop_pickup_assignments(
            ApplyCountrysideOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-25",
                assignments=[
                    {"pickup_task_id": countryside_task.pickup_task_id, "driver_id": "D001"},
                    {"pickup_task_id": normal_task.pickup_task_id, "driver_id": "D001"},
                ],
            )
        )

        updated_countryside = self.repository.get_opshop_pickup_task(
            countryside_task.pickup_task_id
        )
        updated_normal = self.repository.get_opshop_pickup_task(normal_task.pickup_task_id)
        assignment = self.repository.get_assignment(
            "2026-05-25",
            "OPSHOP_PICKUP",
            countryside_task.pickup_task_id,
        )

        self.assertEqual("ASSIGNED", updated_countryside.status)
        self.assertEqual("D001", updated_countryside.driver_id)
        self.assertEqual("trip1", updated_countryside.trip_no)
        self.assertEqual("ACTIVE", updated_normal.status)
        self.assertIsNone(updated_normal.driver_id)
        self.assertEqual("OPSHOP_PICKUP", assignment.task_type)
        self.assertIn(
            countryside_task.pickup_task_id,
            [item.pickup_task_id for item in board.countryside_opshop_pickups],
        )

    def test_apply_countryside_assignments_skips_saved_summary_driver_date(self):
        group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="Locked Route")
        )
        template = self._create_countryside_template(group.route_group_id)
        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id=template.schedule_id,
                pickup_date="2026-05-25",
            )
        )
        self._save_final_summary_lock("D001", "2026-05-25")

        self.service.apply_countryside_opshop_pickup_assignments(
            ApplyCountrysideOpShopPickupAssignmentsRequest(
                dispatch_date="2026-05-25",
                assignments=[{"pickup_task_id": task.pickup_task_id, "driver_id": "D001"}],
            )
        )

        updated = self.repository.get_opshop_pickup_task(task.pickup_task_id)
        self.assertEqual("ACTIVE", updated.status)
        self.assertIsNone(updated.driver_id)
        self.assertIsNone(
            self.repository.get_assignment("2026-05-25", "OPSHOP_PICKUP", task.pickup_task_id)
        )

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

    def _save_final_summary_lock(self, driver_id, delivery_date):
        account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=f"Lock Tester {driver_id} {delivery_date}",
                password="secret123",
                confirm_password="secret123",
            )
        )
        return self.service.save_final_trip_summary(
            SaveFinalTripSummaryRequest(
                dispatch_date="2026-05-25",
                delivery_date=delivery_date,
                driver_id=driver_id,
                driver_name_snapshot=driver_id,
                vehicle_id=None,
                vehicle_rego_snapshot="No vehicle selected",
                total_pallets=0,
                total_loose_bags=0,
                generated_at="2026-05-25T00:00:00+00:00",
                saved_by_account_name=account.account_name,
                saved_by_account_id=account.account_id,
                trips=[],
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
        created_task = self.client.post(
            "/api/manual-dispatch/opshop-pickups/oncall",
            json={
                "schedule_id": template.json()["schedule_id"],
                "pickup_date": "2026-05-25",
            },
        )
        applied = self.client.post(
            "/api/manual-dispatch/opshop-pickups/countryside-assignments/apply",
            json={
                "dispatch_date": "2026-05-25",
                "assignments": [
                    {
                        "pickup_task_id": created_task.json()["pickup_task_id"],
                        "driver_id": "D001",
                    }
                ],
            },
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
        self.assertEqual(200, created_task.status_code)
        self.assertEqual(200, applied.status_code)
        self.assertEqual(
            [created_task.json()["pickup_task_id"]],
            [item["pickup_task_id"] for item in applied.json()["countryside_opshop_pickups"]],
        )
        self.assertEqual(400, disabled.status_code)
        self.assertEqual([route_group_id], [item["route_group_id"] for item in inactive.json()])


if __name__ == "__main__":
    unittest.main()
