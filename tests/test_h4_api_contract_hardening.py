import importlib
import unittest
from unittest.mock import patch

from backend.errors import StateChangedConflictError
from backend.schemas import (
    AssignTaskRequest,
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopPickupTaskRequest,
    CreateOpShopTemplateRequest,
    CreateOrderRequest,
    DeliveryWorkspaceAssignOrderRequest,
    GenerateDeliveryRunSheetRequest,
    RegisterOperatorAccountRequest,
    UpdateDriverRequest,
    UpdateOpShopCountrysideRouteGroupRequest,
    UpdateOpShopPickupTaskRequest,
    UpdateOpShopTemplateRequest,
    UpdateOrderRequest,
    UpdateVehicleRequest,
)
from backend.services.manual_dispatch.normalization import SQLITE_INTEGER_MAX
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class _NoopLogbook:
    def record(self, **_entry):
        return None


class H4PartialPatchServiceContractTest(unittest.TestCase):
    def setUp(self):
        self.service = ManualDispatchService(logbook=_NoopLogbook())

    def test_order_patch_preserves_omitted_fields_and_applies_null_zero_and_empty(self):
        existing = self.service.repository.get_order("ORD-001")

        updated = self.service.update_order(
            existing.order_id,
            UpdateOrderRequest(
                phone=None,
                company_name="",
                pallet_quantity=0,
            ),
        )

        self.assertEqual(existing.suburb, updated.suburb)
        self.assertEqual(existing.delivery_date, updated.delivery_date)
        self.assertEqual(existing.loose_bags_quantity, updated.loose_bags_quantity)
        self.assertIsNone(updated.phone)
        self.assertEqual("", updated.company_name)
        self.assertEqual(0, updated.pallet_quantity)

    def test_order_patch_rejects_null_or_empty_required_fields(self):
        for request, message in (
            (UpdateOrderRequest(suburb=None), "suburb is required"),
            (UpdateOrderRequest(suburb="  "), "suburb is required"),
            (UpdateOrderRequest(delivery_date=None), "delivery_date is required"),
            (UpdateOrderRequest(pallet_quantity=None), "pallet_quantity cannot be null"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.service.update_order("ORD-001", request)

    def test_legacy_complete_order_dto_remains_accepted_by_service_facade(self):
        updated = self.service.update_order(
            "ORD-001",
            CreateOrderRequest(
                suburb="Coburg",
                delivery_date="2026-07-23",
            ),
        )

        self.assertEqual("Coburg", updated.suburb)
        self.assertEqual("2026-07-23", updated.delivery_date)

    def test_driver_and_vehicle_patch_preserve_omitted_and_apply_false_zero_and_null(self):
        driver = self.service.update_driver(
            "D002",
            UpdateDriverRequest(pallet_only=False, email=None),
        )
        vehicle = self.service.update_vehicle(
            "V001",
            UpdateVehicleRequest(
                is_available=False,
                pallet_capacity=0,
                type=None,
            ),
        )

        self.assertEqual("Tony", driver.name)
        self.assertFalse(driver.pallet_only)
        self.assertIsNone(driver.email)
        self.assertEqual("ABC123", vehicle.rego)
        self.assertFalse(vehicle.is_available)
        self.assertEqual(0, vehicle.pallet_capacity)
        self.assertEqual("", vehicle.type)

    def test_non_nullable_boolean_and_capacity_reject_explicit_null(self):
        for callback, message in (
            (
                lambda: self.service.update_driver(
                    "D001",
                    UpdateDriverRequest(is_available=None),
                ),
                "is_available cannot be null",
            ),
            (
                lambda: self.service.update_vehicle(
                    "V001",
                    UpdateVehicleRequest(pallet_capacity=None),
                ),
                "pallet_capacity cannot be null",
            ),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    callback()

    def test_opshop_patch_models_are_presence_aware(self):
        template = self.service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type="ON_CALL",
                name="H4 Patch Shop",
                primary_phone="0400 111 111",
                call_before_arrival=True,
            )
        )
        updated_template = self.service.update_opshop_template(
            template.schedule_id,
            UpdateOpShopTemplateRequest(primary_phone=None),
        )
        self.assertEqual(template.name, updated_template.name)
        self.assertTrue(updated_template.call_before_arrival)
        self.assertIsNone(updated_template.primary_phone)

        task = self.service.create_oncall_opshop_pickup_task(
            CreateOpShopPickupTaskRequest(
                schedule_id=template.schedule_id,
                pickup_date="2026-07-20",
                notes="Keep me",
            )
        )
        preserved = self.service.update_opshop_pickup_task(
            task.pickup_task_id,
            UpdateOpShopPickupTaskRequest(),
        )
        cleared = self.service.update_opshop_pickup_task(
            task.pickup_task_id,
            UpdateOpShopPickupTaskRequest(notes=None),
        )
        self.assertEqual("Keep me", preserved.notes)
        self.assertIsNone(cleared.notes)

        route_group = self.service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(
                route_group_name="H4 Route",
                display_order=7,
                source_marker="seed",
            )
        )
        updated_group = self.service.update_countryside_route_group(
            route_group.route_group_id,
            UpdateOpShopCountrysideRouteGroupRequest(
                active_flag=False,
                display_order=0,
                source_marker=None,
            ),
        )
        self.assertEqual("H4 Route", updated_group.route_group_name)
        self.assertFalse(updated_group.active_flag)
        self.assertEqual(0, updated_group.display_order)
        self.assertIsNone(updated_group.source_marker)

    def test_external_dates_reject_impossible_values(self):
        invalid_dates = ("2026-02-29", "2026-13-01", "2026-04-31", "abcd-ef-gh")
        for value in invalid_dates:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.service.create_order(
                        CreateOrderRequest(suburb="Coburg", delivery_date=value)
                    )
                with self.assertRaises(ValueError):
                    self.service.get_board(value)
                with self.assertRaises(ValueError):
                    self.service.assign_task(
                        AssignTaskRequest(
                            dispatch_date=value,
                            task_type="ORDER",
                            task_id="ORD-001",
                            driver_id="D001",
                            trip_no="trip1",
                        )
                    )

    def test_sqlite_integer_fields_reject_overflow(self):
        overflow = SQLITE_INTEGER_MAX + 1
        for callback in (
            lambda: self.service.update_order(
                "ORD-001",
                UpdateOrderRequest(pallet_quantity=overflow),
            ),
            lambda: self.service.update_vehicle(
                "V001",
                UpdateVehicleRequest(pallet_capacity=overflow),
            ),
            lambda: self.service.create_countryside_route_group(
                CreateOpShopCountrysideRouteGroupRequest(
                    route_group_name="Overflow Route",
                    display_order=overflow,
                )
            ),
        ):
            with self.subTest(callback=callback):
                with self.assertRaises(ValueError):
                    callback()

    def test_delivery_dispatch_date_is_provenance_not_run_sheet_identity(self):
        self.service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date="2026-05-01",
                order_id="ORD-001",
                driver_id="D001",
                trip_no="trip1",
            )
        )
        generated = self.service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date="2026-05-01",
                delivery_date="2026-05-05",
                driver_id="D001",
            )
        )

        self.assertEqual("2026-05-01", generated.dispatch_date)
        self.assertEqual("2026-05-05", generated.delivery_date)
        with self.assertRaisesRegex(StateChangedConflictError, "already exists"):
            self.service.create_generated_delivery_run_sheet(
                GenerateDeliveryRunSheetRequest(
                    dispatch_date="2026-05-02",
                    delivery_date="2026-05-05",
                    driver_id="D001",
                )
            )


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class H4ApiErrorAndUploadContractTest(unittest.TestCase):
    def setUp(self):
        self.service = ManualDispatchService(logbook=_NoopLogbook())
        self.account = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="H4 API Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        authenticate_test_client(self.client, self.service, self.account)

    def tearDown(self):
        self.api_module.service = self.original_service

    def test_error_status_contract(self):
        anonymous_app = FastAPI()
        anonymous_app.include_router(self.api_module.router)
        anonymous = TestClient(anonymous_app)
        self.assertEqual(
            401,
            anonymous.patch(
                "/api/manual-dispatch/delivery/orders/ORD-001",
                json={"note": "blocked"},
            ).status_code,
        )

        malformed = self.client.patch(
            "/api/manual-dispatch/delivery/orders/ORD-001",
            json={"delivery_date": "2026-02-29"},
        )
        missing = self.client.patch(
            "/api/manual-dispatch/delivery/orders/ORD-MISSING",
            json={"note": "missing"},
        )
        validation = self.client.patch(
            "/api/manual-dispatch/delivery/orders/ORD-001",
            json={"pallet_quantity": "not-an-integer"},
        )
        with patch.object(
            self.service,
            "update_delivery_order",
            side_effect=StateChangedConflictError("state changed"),
        ):
            conflict = self.client.patch(
                "/api/manual-dispatch/delivery/orders/ORD-001",
                json={"note": "conflict"},
            )

        self.assertEqual(400, malformed.status_code)
        self.assertEqual(404, missing.status_code)
        self.assertEqual(409, conflict.status_code)
        self.assertEqual(422, validation.status_code)

        defect_app = FastAPI()
        defect_app.include_router(self.api_module.router)
        defect_client = TestClient(defect_app, raise_server_exceptions=False)
        authenticate_test_client(defect_client, self.service, self.account)
        with patch.object(
            self.service,
            "update_delivery_order",
            side_effect=RuntimeError("unexpected defect"),
        ):
            defect = defect_client.patch(
                "/api/manual-dispatch/delivery/orders/ORD-001",
                json={"note": "defect"},
            )
        self.assertEqual(500, defect.status_code)

    def test_impossible_query_dates_are_controlled_400(self):
        requests = (
            ("/api/manual-dispatch/delivery/board", {"dispatch_date": "2026-04-31"}),
            (
                "/api/manual-dispatch/delivery/trip-summary",
                {"delivery_date": "2026-07-20", "dispatch_date": "2026-13-01"},
            ),
            ("/api/manual-dispatch/opshop/trip-summary", {"pickup_date": "2026-02-29"}),
            ("/api/manual-dispatch/board", {"dispatch_date": "abcd-ef-gh"}),
        )
        for path, params in requests:
            with self.subTest(path=path, params=params):
                self.assertEqual(400, self.client.get(path, params=params).status_code)

    def test_api_patch_accepts_zero_false_and_null_without_overwriting_omitted(self):
        response = self.client.patch(
            "/api/manual-dispatch/delivery/vehicles/V001",
            json={"is_available": False, "pallet_capacity": 0, "type": None},
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ABC123", payload["rego"])
        self.assertFalse(payload["is_available"])
        self.assertEqual(0, payload["pallet_capacity"])
        self.assertEqual("", payload["type"])

    def test_api_integer_overflow_is_controlled_400(self):
        response = self.client.patch(
            "/api/manual-dispatch/delivery/vehicles/V001",
            json={"pallet_capacity": SQLITE_INTEGER_MAX + 1},
        )
        self.assertEqual(400, response.status_code)

    def test_attache_upload_validation_and_limits(self):
        endpoint = "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview"
        missing = self.client.post(endpoint)
        empty = self.client.post(
            endpoint,
            files={"files": ("empty.pdf", b"", "application/pdf")},
        )
        unsupported = self.client.post(
            endpoint,
            files={"files": ("invoice.txt", b"not pdf", "text/plain")},
        )
        malformed = self.client.post(
            endpoint,
            files={"files": ("invoice.pdf", b"not pdf", "application/pdf")},
        )
        with patch(
            "backend.api.manual_dispatch_routes.attache_routes.MAX_ATTACHE_PDF_FILE_BYTES",
            4,
        ):
            oversized = self.client.post(
                endpoint,
                files={"files": ("large.pdf", b"12345", "application/pdf")},
            )
        with patch(
            "backend.api.manual_dispatch_routes.attache_routes.MAX_ATTACHE_PDF_FILES",
            1,
        ):
            too_many = self.client.post(
                endpoint,
                files=[
                    ("files", ("one.pdf", b"%PDF-one", "application/pdf")),
                    ("files", ("two.pdf", b"%PDF-two", "application/pdf")),
                ],
            )
        with patch(
            "backend.api.manual_dispatch_routes.attache_routes.MAX_ATTACHE_IMPORT_ROWS",
            1,
        ):
            too_many_rows = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
                json={"rows": [{}, {}]},
            )

        self.assertEqual(422, missing.status_code)
        self.assertEqual(400, empty.status_code)
        self.assertEqual(400, unsupported.status_code)
        self.assertEqual(400, malformed.status_code)
        self.assertEqual(413, oversized.status_code)
        self.assertEqual(413, too_many.status_code)
        self.assertEqual(413, too_many_rows.status_code)


if __name__ == "__main__":
    unittest.main()
