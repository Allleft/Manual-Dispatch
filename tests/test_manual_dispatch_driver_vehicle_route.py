import importlib
import os
import shutil
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import AssignTaskRequest
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class ManualDispatchDriverVehicleRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"driver-vehicle-route-test-{uuid.uuid4().hex}"
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
        self.dispatch_date = "2026-05-05"

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_post_driver_vehicle_with_real_vehicle_returns_200(self):
        response = self._post_driver_vehicle({"vehicle_id": "V002"})

        self.assertEqual(200, response.status_code)
        self.assertEqual("V002", response.json()["vehicle_id"])

    def test_post_driver_vehicle_with_null_vehicle_clears_assignment(self):
        self._post_driver_vehicle({"vehicle_id": "V002"})

        response = self._post_driver_vehicle({"vehicle_id": None})

        self.assertEqual(200, response.status_code)
        self.assertEqual([], self.service.get_board(self.dispatch_date).driver_vehicle_assignments)

    def test_post_driver_vehicle_with_blank_vehicle_clears_assignment(self):
        self._post_driver_vehicle({"vehicle_id": "V002"})

        response = self._post_driver_vehicle({"vehicle_id": ""})

        self.assertEqual(200, response.status_code)
        self.assertEqual([], self.service.get_board(self.dispatch_date).driver_vehicle_assignments)

    def test_post_driver_vehicle_without_vehicle_id_clears_assignment(self):
        self._post_driver_vehicle({"vehicle_id": "V002"})

        response = self._post_driver_vehicle({})

        self.assertEqual(200, response.status_code)
        self.assertEqual([], self.service.get_board(self.dispatch_date).driver_vehicle_assignments)

    def test_invalid_driver_id_still_returns_error(self):
        response = self.client.post(
            "/api/manual-dispatch/driver-vehicle",
            json={
                "dispatch_date": self.dispatch_date,
                "driver_id": "D999",
                "vehicle_id": None,
            },
        )

        self.assertIn(response.status_code, {400, 404})

    def test_invalid_real_vehicle_id_still_returns_error(self):
        response = self._post_driver_vehicle({"vehicle_id": "V999"})

        self.assertIn(response.status_code, {400, 404})

    def test_clearing_vehicle_does_not_remove_task_assignment(self):
        self.service.assign_task(
            AssignTaskRequest(
                dispatch_date=self.dispatch_date,
                task_type="ORDER",
                task_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        self._post_driver_vehicle({"vehicle_id": "V002"})

        response = self._post_driver_vehicle({"vehicle_id": None})

        board = self.service.get_board(self.dispatch_date)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(board.assignments))
        self.assertEqual("ORD-001", board.assignments[0].task_id)

    def _post_driver_vehicle(self, overrides):
        payload = {
            "dispatch_date": self.dispatch_date,
            "driver_id": "D001",
        }
        payload.update(overrides)
        return self.client.post("/api/manual-dispatch/driver-vehicle", json=payload)


if __name__ == "__main__":
    unittest.main()
