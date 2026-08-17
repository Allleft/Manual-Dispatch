import importlib
import unittest

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.schemas import (
    DeliveryRunSheet,
    DeliveryRunSheetOrderSnapshot,
    DeliveryRunSheetTrip,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class RecordingLogbook:
    def __init__(self):
        self.entries = []

    def record(self, **entry):
        self.entries.append(entry)


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class DeliveryAreaApiTest(unittest.TestCase):
    def setUp(self):
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.previous_service = self.api_module.service
        self.repository = InMemoryManualDispatchRepository()
        self.logbook = RecordingLogbook()
        self.service = ManualDispatchService(self.repository, self.logbook)
        self.api_module.service = self.service
        self.app = FastAPI()
        self.app.include_router(self.api_module.router)
        self.client = TestClient(self.app)
        authenticate_test_client(
            self.client,
            self.service,
            account_name="Delivery Area Operator",
        )

    def tearDown(self):
        self.client.close()
        self.api_module.service = self.previous_service

    def test_classification_preview_known_and_unknown(self):
        known = self.client.post(
            "/api/manual-dispatch/delivery/area-classification",
            json={"suburb": "Dandenong Sth", "postcode": "3175"},
        )
        unknown = self.client.post(
            "/api/manual-dispatch/delivery/area-classification",
            json={"suburb": "Unconfigured Test Suburb", "postcode": "3999"},
        )

        self.assertEqual(200, known.status_code, known.text)
        self.assertEqual("SOUTHEAST", known.json()["delivery_area"])
        self.assertEqual("SOUTHEAST", known.json()["auto_delivery_region"])
        self.assertTrue(known.json()["known"])
        self.assertEqual(200, unknown.status_code, unknown.text)
        self.assertIsNone(unknown.json()["delivery_area"])
        self.assertFalse(unknown.json()["known"])

    def test_override_set_overwrite_clear_and_logbook_actor(self):
        before_company = self.repository.get_order("ORD-001").company_name

        local = self._patch("ORD-001", "LOCAL")
        southeast = self._patch("ORD-001", "SOUTHEAST")
        automatic = self._patch("ORD-001", None)

        self.assertEqual(200, local.status_code, local.text)
        self.assertEqual("LOCAL", local.json()["delivery_area_override"])
        self.assertEqual("LOCAL", local.json()["delivery_area"])
        self.assertEqual("MANUAL", local.json()["delivery_area_source"])
        self.assertEqual("SOUTHEAST", local.json()["auto_delivery_area"])
        self.assertEqual("SOUTHEAST", southeast.json()["delivery_area_override"])
        self.assertIsNone(automatic.json()["delivery_area_override"])
        self.assertEqual("SOUTHEAST", automatic.json()["delivery_area"])
        self.assertEqual("AUTO", automatic.json()["delivery_area_source"])
        self.assertEqual(before_company, self.repository.get_order("ORD-001").company_name)

        self.assertEqual(
            [
                "ORDER_DELIVERY_AREA_OVERRIDDEN",
                "ORDER_DELIVERY_AREA_OVERRIDDEN",
                "ORDER_DELIVERY_AREA_OVERRIDE_CLEARED",
            ],
            [entry["action"] for entry in self.logbook.entries[-3:]],
        )
        last = self.logbook.entries[-1]
        self.assertEqual("Delivery Area Operator", last["actor"])
        self.assertEqual("SOUTHEAST", last["metadata"]["new_effective_area"])
        self.assertIsNone(last["metadata"]["new_override_area"])
        self.assertEqual("Dandenong", last["metadata"]["suburb"])
        self.assertEqual("3175", last["metadata"]["postcode"])

    def test_validation_missing_auth_and_run_sheet_lock(self):
        invalid = self._patch("ORD-001", "EAST")
        missing = self._patch("MISSING-ORDER", "LOCAL")
        anonymous = TestClient(self.app)
        unauthenticated = anonymous.patch(
            "/api/manual-dispatch/delivery/orders/ORD-001/delivery-area",
            json={"delivery_area": "LOCAL"},
        )
        anonymous.close()

        self.assertEqual(400, invalid.status_code, invalid.text)
        self.assertEqual(404, missing.status_code, missing.text)
        self.assertEqual(401, unauthenticated.status_code, unauthenticated.text)

        self.repository.delivery_run_sheets.append(self._reserved_run_sheet("ORD-001"))
        locked = self._patch("ORD-001", "LOCAL")
        self.assertEqual(409, locked.status_code, locked.text)
        self.assertIn("already been generated", locked.json()["detail"])

    def _patch(self, order_id, delivery_area):
        return self.client.patch(
            f"/api/manual-dispatch/delivery/orders/{order_id}/delivery-area",
            json={"delivery_area": delivery_area},
        )

    @staticmethod
    def _reserved_run_sheet(order_id):
        return DeliveryRunSheet(
            run_sheet_id="DRS-AREA-LOCK",
            dispatch_date="2026-05-05",
            delivery_date="2026-05-05",
            driver_id="D001",
            driver_name_snapshot="John",
            vehicle_id=None,
            vehicle_rego_snapshot=None,
            total_pallets=2,
            total_loose_bags=0,
            status="GENERATED",
            generated_at="2026-05-04T10:00:00+10:00",
            saved_at=None,
            saved_by_account_name=None,
            saved_by_account_id=None,
            legacy_summary_id=None,
            trips=[
                DeliveryRunSheetTrip(
                    trip_no="trip1",
                    orders=[
                        DeliveryRunSheetOrderSnapshot(
                            row_id="ROW-AREA-1",
                            trip_no="trip1",
                            row_no=1,
                            task_type="ORDER",
                            task_id=order_id,
                            order_id_snapshot=order_id,
                            invoice_number_snapshot="INV-1001",
                            order_no_snapshot=None,
                            company_name_snapshot="Demo Customer A",
                            suburb_snapshot="Dandenong",
                            delivery_address_snapshot="1 Demo Street",
                            product_snapshot=None,
                            pallet_quantity_snapshot=2,
                            loose_bags_quantity_snapshot=0,
                            note_snapshot=None,
                        )
                    ],
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
