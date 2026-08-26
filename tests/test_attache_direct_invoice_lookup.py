from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from backend.integrations.attache_bridge_client import (
    AttacheBridgeAmbiguousInvoiceError,
    AttacheBridgeClient,
    AttacheBridgeClientConfig,
    AttacheBridgeConfigurationError,
    AttacheBridgeInvoiceNotFoundError,
    AttacheBridgeInvoiceTooLargeError,
    AttacheBridgeMalformedResponseError,
    AttacheBridgeTimeoutError,
    AttacheBridgeUnavailableError,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import RegisterOperatorAccountRequest
from backend.services.manual_dispatch.attache_direct_invoice_normalizer import (
    AttacheDirectInvoicePayloadError,
    normalize_direct_attache_invoice,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client

from backend.api import manual_dispatch as manual_dispatch_api
from backend.main import app
from tools.smoke_test_attache_bridge import build_smoke_summary_lines


DIRECT_INVOICE_PAYLOAD = {
    "invoice_number": "185479",
    "invoice_date": "2026-08-18",
    "delivery_date": None,
    "customer_code": "DIRECT01",
    "customer_name": "DIRECT LOOKUP CUSTOMER",
    "order_reference": "PO-185479",
    "invoice_order_number": "SO-185479",
    "delivery_description": "DIRECT LOOKUP CUSTOMER",
    "delivery_address_lines": ["1 TEST ROAD"],
    "suburb": "HALLAM",
    "state": "VIC",
    "postcode": "3803",
    "lines": [
        {
            "line_number": 1,
            "code": "RWORK",
            "description": "COLOUR WORKSHOP RAGS",
            "unit": "KG",
            "quantity_invoiced": 300,
            "quantity_ordered": 300,
            "quantity_backordered": 0,
            "package_number": None,
        },
        {
            "line_number": 2,
            "code": "BAG10",
            "description": "PLASTIC BAG 10 KG",
            "unit": "EACH",
            "quantity_invoiced": 30,
            "quantity_ordered": 30,
            "quantity_backordered": 0,
            "package_number": None,
        },
        {
            "line_number": 3,
            "code": "RWCOTT",
            "description": "WHITE COTTON RAGS",
            "unit": "KG",
            "quantity_invoiced": 200,
            "quantity_ordered": 200,
            "quantity_backordered": 0,
            "package_number": None,
        },
        {
            "line_number": 4,
            "code": "BAG10",
            "description": "PLASTIC BAG 10 KG",
            "unit": "EACH",
            "quantity_invoiced": 20,
            "quantity_ordered": 20,
            "quantity_backordered": 0,
            "package_number": None,
        },
        {
            "line_number": 5,
            "code": "PAL",
            "description": "PALLET",
            "unit": "EACH",
            "quantity_invoiced": 1,
            "quantity_ordered": 1,
            "quantity_backordered": 0,
            "package_number": None,
        },
        {
            "line_number": 6,
            "code": "DEL",
            "description": "DELIVERY CHARGE",
            "unit": "EACH",
            "quantity_invoiced": 1,
            "quantity_ordered": 1,
            "quantity_backordered": 0,
            "package_number": None,
        },
    ],
}


class _Response:
    def __init__(self, payload):
        self._payload = BytesIO(payload)
        self.closed = False

    def read(self, size=-1):
        return self._payload.read(size)

    def close(self):
        self.closed = True


class AttacheBridgeClientTest(unittest.TestCase):
    def test_lookup_uses_bounded_authenticated_request_and_closes_response(self):
        response = _Response(json.dumps(DIRECT_INVOICE_PAYLOAD).encode("utf-8"))
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return response

        client = AttacheBridgeClient(
            AttacheBridgeClientConfig(
                base_url="http://bridge.internal:8787/",
                api_token="bridge-secret",
                timeout_seconds=2.5,
            ),
            opener=opener,
        )

        payload = client.lookup_invoice(" 185479 ")

        self.assertEqual("185479", payload["invoice_number"])
        self.assertEqual(
            "http://bridge.internal:8787/v1/invoices/185479",
            captured["request"].full_url,
        )
        self.assertEqual(
            "bridge-secret",
            captured["request"].get_header("X-attache-bridge-token"),
        )
        self.assertEqual(2.5, captured["timeout"])
        self.assertTrue(response.closed)
        self.assertNotIn("bridge-secret", repr(client.config))

    def test_lookup_maps_bridge_failures_without_exposing_response_details(self):
        cases = (
            (404, "invoice_not_found", AttacheBridgeInvoiceNotFoundError),
            (409, "multiple_invoice_matches", AttacheBridgeAmbiguousInvoiceError),
            (422, "invoice_too_large", AttacheBridgeInvoiceTooLargeError),
            (504, "odbc_timeout", AttacheBridgeTimeoutError),
            (503, "odbc_authorization_failed", AttacheBridgeUnavailableError),
        )
        for status, code, expected_error in cases:
            with self.subTest(status=status, code=code):
                body = json.dumps(
                    {
                        "detail": {
                            "code": code,
                            "message": "sensitive ODBC detail",
                        }
                    }
                ).encode("utf-8")

                def opener(request, timeout, *, response_body=body):
                    raise HTTPError(
                        request.full_url,
                        status,
                        "bridge failure",
                        {},
                        BytesIO(response_body),
                    )

                client = AttacheBridgeClient(
                    AttacheBridgeClientConfig(
                        base_url="http://bridge.internal:8787",
                        api_token="secret",
                    ),
                    opener=opener,
                )
                with self.assertRaises(expected_error) as raised:
                    client.lookup_invoice("185479")
                self.assertNotIn("sensitive ODBC detail", str(raised.exception))

    def test_lookup_rejects_malformed_or_mismatched_payloads(self):
        for payload in (
            b"not-json",
            json.dumps({"invoice_number": "185479", "lines": {}}).encode(),
            json.dumps({"invoice_number": "999999", "lines": []}).encode(),
        ):
            with self.subTest(payload=payload[:20]):
                client = AttacheBridgeClient(
                    AttacheBridgeClientConfig(
                        base_url="http://bridge.internal:8787",
                        api_token="secret",
                    ),
                    opener=lambda request, timeout, value=payload: _Response(value),
                )
                with self.assertRaises(AttacheBridgeMalformedResponseError):
                    client.lookup_invoice("185479")

    def test_configuration_is_optional_until_direct_lookup_is_requested(self):
        with self.assertRaises(AttacheBridgeConfigurationError):
            AttacheBridgeClientConfig.from_environment({})

    def test_smoke_summary_is_whitelisted_and_single_line(self):
        payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        payload["customer_name"] = "DIRECT\nLOOKUP\x1b CUSTOMER"
        payload["delivery_address_lines"] = ["PRIVATE ADDRESS"]
        payload["connection_string"] = "DSN=private;PWD=secret"

        rendered = "\n".join(build_smoke_summary_lines(payload))

        self.assertIn("ATTACHE_BRIDGE_SMOKE_LOOKUP_OK", rendered)
        self.assertIn("Invoice Number: 185479", rendered)
        self.assertIn("Customer Name: DIRECT LOOKUP CUSTOMER", rendered)
        self.assertIn("Line 1: RWORK | COLOUR WORKSHOP RAGS | qtyinv=300", rendered)
        self.assertNotIn("PRIVATE ADDRESS", rendered)
        self.assertNotIn("PWD=secret", rendered)
        self.assertNotIn("\x1b", rendered)


class AttacheDirectInvoiceNormalizerTest(unittest.TestCase):
    def test_structured_invoice_reuses_pdf_product_packaging_and_load_rules(self):
        payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        payload["delivery_date"] = "2026-08-10"
        row = normalize_direct_attache_invoice(
            payload,
            expected_invoice_number="185479",
            import_date=date(2026, 8, 21),
        )

        self.assertEqual("185479", row.invoice_number)
        self.assertEqual("2026-08-18", row.invoice_date)
        self.assertEqual("2026-08-24", row.delivery_date)
        self.assertEqual("PO-185479", row.order_no)
        self.assertEqual("DIRECT LOOKUP CUSTOMER", row.company_name)
        self.assertEqual("1 TEST ROAD", row.delivery_address)
        self.assertEqual("HALLAM", row.suburb)
        self.assertEqual("3803", row.postcode)
        self.assertEqual(1, row.pallet_quantity)
        self.assertEqual(0, row.loose_bags_quantity)
        self.assertEqual(0, row.carton_quantity)
        self.assertEqual(2, len(row.product_lines))
        self.assertEqual(
            [
                ("RWORK", 300, 30, "BAG10"),
                ("RWCOTT", 200, 20, "BAG10"),
            ],
            [
                (
                    product["product_code"],
                    product["quantity"],
                    product["package_quantity"],
                    product["package_unit"],
                )
                for product in row.product_lines
            ],
        )
        self.assertFalse(any(product["product_code"] == "DEL" for product in row.product_lines))
        self.assertEqual([], row.warnings)

    def test_historical_delivery_snapshot_uses_delivery_name_raw_suburb_and_postcode(self):
        payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        payload.update(
            {
                "customer_name": "BILLING CUSTOMER",
                "delivery_description": "ROTARY TOOLS",
                "delivery_address_lines": ["1/44 MAHONEYS RD"],
                "suburb": "THOMASTOWN VIC",
                "state": None,
                "postcode": "3074",
            }
        )

        row = normalize_direct_attache_invoice(
            payload,
            expected_invoice_number="185479",
            import_date=date(2026, 8, 19),
        )

        self.assertEqual("ROTARY TOOLS", row.company_name)
        self.assertEqual("1/44 MAHONEYS RD", row.delivery_address)
        self.assertEqual("THOMASTOWN VIC", row.suburb)
        self.assertEqual("3074", row.postcode)

    def test_invalid_structured_payload_is_controlled(self):
        payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        payload["lines"] = "not-a-list"
        with self.assertRaises(AttacheDirectInvoicePayloadError):
            normalize_direct_attache_invoice(payload)


class AttacheDirectInvoiceApiTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"attache-direct-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(self.temp_dir / "logbook")
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.identity = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Attaché Direct Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        if self.previous_logbook_dir is None:
            os.environ.pop("MANUAL_DISPATCH_LOGBOOK_DIR", None)
        else:
            os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = self.previous_logbook_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _lookup(self, result):
        bridge_client = Mock()
        if isinstance(result, Exception):
            bridge_client.lookup_invoice.side_effect = result
        else:
            bridge_client.lookup_invoice.return_value = result
        return patch(
            "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
            return_value=bridge_client,
        )

    def test_missing_bridge_configuration_does_not_block_application_or_other_import_routes(self):
        bridge_environment = {
            "ATTACHE_BRIDGE_URL": "",
            "ATTACHE_BRIDGE_API_TOKEN": "",
            "ATTACHE_BRIDGE_TIMEOUT_SECONDS": "",
        }
        with patch.dict(os.environ, bridge_environment):
            self.assertEqual(200, self.client.get("/health").status_code)
            route_paths = {route.path for route in app.routes}
        self.assertIn(
            "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
            route_paths,
        )
        self.assertIn(
            "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
            route_paths,
        )

    def test_direct_preview_is_authenticated_normalized_and_commits_through_existing_path(self):
        payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        payload["delivery_date"] = "2026-08-10"
        with (
            patch.object(manual_dispatch_api, "service", self.service),
            self._lookup(payload),
            patch(
                "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                return_value=date(2026, 8, 21),
            ),
        ):
            unauthenticated = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                json={"invoice_number": "185479"},
            )
            self.assertEqual(401, unauthenticated.status_code)

            authenticate_test_client(self.client, self.service, self.identity)
            preview = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                json={"invoice_number": "185479"},
            )
            self.assertEqual(200, preview.status_code, preview.text)
            row = preview.json()["rows"][0]
            self.assertEqual("Attaché Direct", row["source_filename"])
            self.assertEqual("2026-08-24", row["delivery_date"])
            self.assertEqual("SOUTHEAST", row["auto_delivery_region"])
            self.assertEqual("SOUTHEAST", row["delivery_area"])
            self.assertEqual("AUTO", row["delivery_area_source"])
            self.assertFalse(row["is_duplicate"])
            self.assertEqual([], self.repository.list_orders())

            commit = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
                json={"rows": [row]},
            )
            self.assertEqual(200, commit.status_code, commit.text)
            self.assertEqual(1, commit.json()["imported_count"])

            duplicate = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                json={"invoice_number": "185479"},
            )
            self.assertEqual(200, duplicate.status_code, duplicate.text)
            duplicate_row = duplicate.json()["rows"][0]
            self.assertTrue(duplicate_row["is_duplicate"])
            self.assertFalse(duplicate_row["importable"])
            self.assertFalse(duplicate_row["selected"])
            self.assertIn(
                "Duplicate invoice number already exists.",
                duplicate_row["warnings"],
            )

    def test_direct_preview_returns_safe_status_specific_errors(self):
        cases = (
            (
                AttacheBridgeInvoiceNotFoundError("Invoice 185479 was not found in Attaché."),
                404,
                "invoice_not_found",
            ),
            (
                AttacheBridgeAmbiguousInvoiceError("Multiple invoices matched."),
                409,
                "multiple_invoice_matches",
            ),
            (
                AttacheBridgeInvoiceTooLargeError(
                    "Attaché invoice exceeds the supported product-line limit. "
                    "No partial preview was created."
                ),
                422,
                "invoice_too_large",
            ),
            (AttacheBridgeTimeoutError("lookup timed out"), 504, "bridge_timeout"),
            (
                AttacheBridgeUnavailableError("private upstream failure"),
                503,
                "bridge_unavailable",
            ),
            (
                AttacheBridgeConfigurationError("private config failure"),
                503,
                "bridge_unavailable",
            ),
            (
                AttacheBridgeMalformedResponseError("private payload failure"),
                502,
                "bridge_invalid_response",
            ),
        )
        with patch.object(manual_dispatch_api, "service", self.service):
            authenticate_test_client(self.client, self.service, self.identity)
            for error, expected_status, expected_code in cases:
                with self.subTest(expected_code=expected_code), self._lookup(error):
                    response = self.client.post(
                        "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                        json={"invoice_number": "185479"},
                    )
                    self.assertEqual(expected_status, response.status_code, response.text)
                    detail = response.json()["detail"]
                    self.assertEqual(expected_code, detail["code"])
                    self.assertNotIn("private", detail["message"])
                    if expected_status >= 500:
                        self.assertIn("Import Attaché PDF", detail["message"])

    def test_direct_preview_rejects_invalid_invoice_before_bridge_call(self):
        with patch.object(manual_dispatch_api, "service", self.service):
            authenticate_test_client(self.client, self.service, self.identity)
            with self._lookup(deepcopy(DIRECT_INVOICE_PAYLOAD)) as factory:
                for invoice_number in ("", "18 5479", "ABC"):
                    with self.subTest(invoice_number=invoice_number):
                        response = self.client.post(
                            "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                            json={"invoice_number": invoice_number},
                        )
                        self.assertEqual(400, response.status_code, response.text)
                factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
