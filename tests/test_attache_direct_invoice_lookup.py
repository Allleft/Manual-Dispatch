from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
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
    AttacheBridgeInvoiceBatchTooLargeError,
    AttacheBridgeInvoiceNotFoundError,
    AttacheBridgeInvoiceTooLargeError,
    AttacheBridgeMalformedResponseError,
    AttacheBridgeTimeoutError,
    AttacheBridgeUnavailableError,
    MAX_BRIDGE_BATCH_RESPONSE_BYTES,
    normalize_attache_from_date,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import CreateOrderRequest, RegisterOperatorAccountRequest
from backend.services.manual_dispatch.attache_direct_invoice_normalizer import (
    AttacheDirectInvoicePayloadError,
    normalize_direct_attache_invoice,
)
from backend.services.manual_dispatch.attache_current_future_payment_eligibility import (
    CURRENT_FUTURE_SOURCE,
    ELIGIBILITY_PROOF_TTL_SECONDS,
    EligibilitySnapshotError,
    PAYMENT_NOT_REQUIRED,
    PAYMENT_PAID_IN_FULL,
    PAYMENT_REQUIRED,
    PAYMENT_UNKNOWN,
    classify_payment_eligibility,
    create_eligibility_proof,
    normalize_terms_description,
    verify_eligibility_snapshot,
)
from backend.api.manual_dispatch_routes.common import operator_cookie_secret
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

    def test_batch_lookup_uses_bounded_authenticated_request_and_closes_response(self):
        invoice = deepcopy(DIRECT_INVOICE_PAYLOAD)
        invoice.update(
            {
                "terms_description": "C.O.D.",
                "outstanding_balance": 0,
            }
        )
        response = _Response(
            json.dumps(
                {"from_date": "2026-08-18", "invoices": [invoice]}
            ).encode("utf-8")
        )
        captured = {"calls": 0}

        def opener(request, timeout):
            captured["calls"] += 1
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

        invoices = client.lookup_invoices_from_date("2026-08-18")

        self.assertEqual([invoice], invoices)
        self.assertEqual(1, captured["calls"])
        self.assertEqual(
            "http://bridge.internal:8787/v1/invoices?from_date=2026-08-18",
            captured["request"].full_url,
        )
        self.assertEqual(
            "bridge-secret",
            captured["request"].get_header("X-attache-bridge-token"),
        )
        self.assertEqual(2.5, captured["timeout"])
        self.assertTrue(response.closed)

    def test_batch_lookup_rejects_malformed_scope_items_dates_lines_and_duplicates(self):
        valid = deepcopy(DIRECT_INVOICE_PAYLOAD)
        duplicate = deepcopy(valid)
        payloads = (
            b"not-json",
            json.dumps([]).encode(),
            json.dumps({"from_date": "2026-08-19", "invoices": []}).encode(),
            json.dumps({"from_date": "2026-08-18"}).encode(),
            json.dumps({"from_date": "2026-08-18", "invoices": {}}).encode(),
            json.dumps({"from_date": "2026-08-18", "invoices": ["bad"]}).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "invoice_number": "18 A"}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "invoice_date": "2026-02-30"}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "invoice_date": "2026-08-17"}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "lines": {}}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "terms_description": 30}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "outstanding_balance": "0.00"}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [{**valid, "outstanding_balance": True}],
                }
            ).encode(),
            json.dumps(
                {
                    "from_date": "2026-08-18",
                    "invoices": [valid, duplicate],
                }
            ).encode(),
        )
        for payload in payloads:
            with self.subTest(payload=payload[:40]):
                response = _Response(payload)
                client = AttacheBridgeClient(
                    AttacheBridgeClientConfig(
                        base_url="http://bridge.internal:8787",
                        api_token="secret",
                    ),
                    opener=lambda request, timeout, value=response: value,
                )
                with self.assertRaises(AttacheBridgeMalformedResponseError):
                    client.lookup_invoices_from_date("2026-08-18")
                self.assertTrue(response.closed)

        for invalid in ("", "2026-8-18", "20260818", "2026-02-30", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_attache_from_date(invalid)

    def test_batch_lookup_enforces_response_bound_and_maps_safe_failures(self):
        class OversizedResponse:
            def __init__(self):
                self.closed = False
                self.requested_size = None

            def read(self, size=-1):
                self.requested_size = size
                return b"x" * size

            def close(self):
                self.closed = True

        response = OversizedResponse()
        client = AttacheBridgeClient(
            AttacheBridgeClientConfig(
                base_url="http://bridge.internal:8787",
                api_token="secret",
            ),
            opener=lambda request, timeout: response,
        )
        with self.assertRaises(AttacheBridgeMalformedResponseError):
            client.lookup_invoices_from_date("2026-08-18")
        self.assertEqual(
            MAX_BRIDGE_BATCH_RESPONSE_BYTES + 1,
            response.requested_size,
        )
        self.assertTrue(response.closed)

        cases = (
            (413, "invoice_batch_limit_exceeded", AttacheBridgeInvoiceBatchTooLargeError),
            (422, "invoice_too_large", AttacheBridgeInvoiceTooLargeError),
            (504, "odbc_timeout", AttacheBridgeTimeoutError),
            (503, "bridge_unavailable", AttacheBridgeUnavailableError),
        )
        for status, code, expected in cases:
            with self.subTest(code=code):
                body = json.dumps(
                    {"detail": {"code": code, "message": "private ODBC detail"}}
                ).encode()

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
                with self.assertRaises(expected) as raised:
                    client.lookup_invoices_from_date("2026-08-18")
                self.assertNotIn("private", str(raised.exception))

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


class AttacheCurrentFuturePaymentEligibilityTest(unittest.TestCase):
    def test_proof_canonicalizes_numeric_values_and_binds_every_snapshot_field(self):
        row = SimpleNamespace(
            source=CURRENT_FUTURE_SOURCE, invoice_number="186001",
            customer_code="QA", terms_description="C.O.D.",
            outstanding_balance=0, issued_at=2000000000,
            expires_at=2000000000 + ELIGIBILITY_PROOF_TTL_SECONDS,
        )
        secret = operator_cookie_secret()
        row.eligibility_proof = create_eligibility_proof(
            row, from_date="2026-09-07", secret=secret,
        )
        row.outstanding_balance = 0.0
        snapshot = verify_eligibility_snapshot(
            row, from_date="2026-09-07", secret=secret, now=row.issued_at,
        )
        self.assertEqual("0", snapshot["outstanding_balance"])
        for field, value in (
            ("source", "attache-direct"), ("invoice_number", "186002"),
            ("customer_code", "QA2"), ("terms_description", "30 DAYS"),
            ("outstanding_balance", 0.01), ("issued_at", row.issued_at + 1),
            ("expires_at", row.expires_at + 1),
        ):
            with self.subTest(field=field), self.assertRaises(EligibilitySnapshotError):
                verify_eligibility_snapshot(
                    SimpleNamespace(**{**vars(row), field: value}),
                    from_date="2026-09-07", secret=secret, now=row.issued_at,
                )
        for now in (row.issued_at - 1, row.expires_at, row.expires_at + 1):
            with self.subTest(now=now), self.assertRaises(EligibilitySnapshotError):
                verify_eligibility_snapshot(
                    row, from_date="2026-09-07", secret=secret, now=now,
                )

    def test_terms_normalization_is_conservative(self):
        self.assertEqual("30 DAYS", normalize_terms_description(" 30 days "))
        self.assertEqual("C.O.D.", normalize_terms_description(" c.o.d. "))
        self.assertEqual("C.O.D.", normalize_terms_description(" COD "))
        self.assertEqual("14 DAYS", normalize_terms_description(" 14 days "))
        self.assertIsNone(normalize_terms_description("  "))
        self.assertIsNone(normalize_terms_description(None))
        self.assertEqual("C O D", normalize_terms_description("C O D"))

    def test_payment_eligibility_matrix_fails_closed(self):
        cases = (
            ("30 DAYS", None, PAYMENT_NOT_REQUIRED),
            ("30 DAYS", 500, PAYMENT_NOT_REQUIRED),
            ("C.O.D.", 0, PAYMENT_PAID_IN_FULL),
            ("COD", -27.5, PAYMENT_PAID_IN_FULL),
            ("C.O.D.", 0.004, PAYMENT_PAID_IN_FULL),
            ("C.O.D.", 0.005, PAYMENT_PAID_IN_FULL),
            ("C.O.D.", 0.01, PAYMENT_REQUIRED),
            ("C.O.D.", 500, PAYMENT_REQUIRED),
            ("C.O.D.", None, PAYMENT_UNKNOWN),
            ("C.O.D.", float("nan"), PAYMENT_UNKNOWN),
            ("C.O.D.", True, PAYMENT_UNKNOWN),
            ("14 DAYS", 0, PAYMENT_UNKNOWN),
            (None, 0, PAYMENT_UNKNOWN),
        )
        for terms, balance, expected in cases:
            with self.subTest(terms=terms, balance=balance):
                self.assertEqual(
                    expected,
                    classify_payment_eligibility(terms, balance),
                )


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

    def _batch_lookup(self, result):
        bridge_client = Mock()
        if isinstance(result, Exception):
            bridge_client.lookup_invoices_from_date.side_effect = result
        else:
            bridge_client.lookup_invoices_from_date.return_value = result
        return patch(
            "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
            return_value=bridge_client,
        ), bridge_client

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
            self.assertNotIn("eligibility_proof", row)
            self.assertNotIn("issued_at", row)
            self.assertNotIn("expires_at", row)
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

    def test_current_future_preview_uses_one_melbourne_date_and_keeps_duplicates_visible(self):
        self.service.create_delivery_order(
            CreateOrderRequest(
                invoice_number="185479",
                company_name="EXISTING CUSTOMER",
                delivery_address="1 EXISTING ROAD",
                suburb="HALLAM",
                postcode="3803",
                delivery_date="2026-09-03",
            )
        )
        duplicate_payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        duplicate_payload.update(
            {
                "invoice_date": "2026-09-02",
                "terms_description": "C.O.D.",
                "outstanding_balance": 203.5,
            }
        )
        ready_payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
        ready_payload.update(
            {
                "invoice_number": "185480",
                "invoice_date": "2026-09-04",
                "order_reference": "PO-185480",
                "terms_description": "30 DAYS",
                "outstanding_balance": 500,
            }
        )
        lookup_patch, bridge_client = self._batch_lookup(
            [duplicate_payload, ready_payload]
        )
        with (
            patch.object(manual_dispatch_api, "service", self.service),
            lookup_patch,
            patch(
                "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                return_value=date(2026, 9, 2),
            ) as date_provider,
            patch.object(
                self.service,
                "record_attache_import_confirmation",
            ) as record_confirmation,
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            response = self.client.post(
                "/api/manual-dispatch/delivery/orders/"
                "import-attache-current-future-preview"
            )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("2026-09-02", body["from_date"])
        self.assertEqual(["185479", "185480"], [row["invoice_number"] for row in body["rows"]])
        self.assertTrue(body["rows"][0]["is_duplicate"])
        self.assertFalse(body["rows"][0]["importable"])
        self.assertFalse(body["rows"][0]["selected"])
        self.assertEqual("PAYMENT_REQUIRED", body["rows"][0]["payment_eligibility"])
        self.assertEqual(203.5, body["rows"][0]["outstanding_balance"])
        self.assertFalse(body["rows"][1]["is_duplicate"])
        self.assertTrue(body["rows"][1]["importable"])
        self.assertTrue(body["rows"][1]["selected"])
        self.assertEqual("30 DAYS", body["rows"][1]["terms_description"])
        self.assertEqual("NOT_REQUIRED", body["rows"][1]["payment_eligibility"])
        self.assertEqual("2026-09-03", body["rows"][0]["delivery_date"])
        self.assertEqual("2026-09-03", body["rows"][1]["delivery_date"])
        self.assertEqual(1, len(self.repository.list_orders()))
        date_provider.assert_called_once_with()
        bridge_client.lookup_invoices_from_date.assert_called_once_with("2026-09-02")
        record_confirmation.assert_not_called()

    def test_current_future_preview_payment_eligibility_matrix_fails_closed(self):
        cases = (
            ("30 DAYS", None, "NOT_REQUIRED", True),
            (" 30 days ", 500, "NOT_REQUIRED", True),
            ("C.O.D.", 0, "PAID_IN_FULL", True),
            ("C.O.D.", -27.5, "PAID_IN_FULL", True),
            ("COD", 0.004, "PAID_IN_FULL", True),
            ("c.o.d.", 0.005, "PAID_IN_FULL", True),
            ("C.O.D.", 0.01, "PAYMENT_REQUIRED", False),
            ("C.O.D.", 500, "PAYMENT_REQUIRED", False),
            ("C.O.D.", None, "UNKNOWN", False),
            ("14 DAYS", 0, "UNKNOWN", False),
            (None, 0, "UNKNOWN", False),
        )
        payloads = []
        for index, (terms, balance, _status, _importable) in enumerate(cases):
            payload = deepcopy(DIRECT_INVOICE_PAYLOAD)
            payload.update(
                {
                    "invoice_number": str(186000 + index),
                    "invoice_date": "2026-09-04",
                    "terms_description": terms,
                    "outstanding_balance": balance,
                }
            )
            payloads.append(payload)

        lookup_patch, bridge_client = self._batch_lookup(payloads)
        with (
            patch.object(manual_dispatch_api, "service", self.service),
            lookup_patch,
            patch(
                "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                return_value=date(2026, 9, 2),
            ),
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            response = self.client.post(
                "/api/manual-dispatch/delivery/orders/"
                "import-attache-current-future-preview"
            )

        self.assertEqual(200, response.status_code, response.text)
        rows = response.json()["rows"]
        self.assertEqual(len(cases), len(rows))
        for row, (terms, balance, status, importable) in zip(rows, cases):
            with self.subTest(terms=terms, balance=balance):
                self.assertEqual(status, row["payment_eligibility"])
                self.assertEqual(importable, row["importable"])
                self.assertEqual(importable, row["selected"])
                if importable:
                    self.assertFalse(any(
                        "payment eligibility" in warning.lower()
                        or "payment is required" in warning.lower()
                        for warning in row["warnings"]
                    ))
                else:
                    self.assertTrue(row["warnings"])
        self.assertEqual("30 DAYS", rows[1]["terms_description"])
        self.assertEqual("C.O.D.", rows[4]["terms_description"])
        bridge_client.lookup_invoices_from_date.assert_called_once_with(
            "2026-09-02"
        )
        self.assertEqual([], self.repository.list_orders())

    def test_current_future_preview_empty_and_safe_error_contracts(self):
        with patch.object(manual_dispatch_api, "service", self.service):
            authenticate_test_client(self.client, self.service, self.identity)
            lookup_patch, _bridge_client = self._batch_lookup([])
            with (
                lookup_patch,
                patch(
                    "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                    return_value=date(2026, 9, 2),
                ),
            ):
                empty = self.client.post(
                    "/api/manual-dispatch/delivery/orders/"
                    "import-attache-current-future-preview"
                )
            self.assertEqual(
                {"from_date": "2026-09-02", "rows": []},
                empty.json(),
            )

            cases = (
                (
                    AttacheBridgeInvoiceBatchTooLargeError("private count"),
                    413,
                    "invoice_batch_limit_exceeded",
                ),
                (
                    AttacheBridgeInvoiceTooLargeError("private line count"),
                    422,
                    "invoice_too_large",
                ),
                (AttacheBridgeTimeoutError("private timeout"), 504, "bridge_timeout"),
                (
                    AttacheBridgeMalformedResponseError("private payload"),
                    502,
                    "bridge_invalid_response",
                ),
                (
                    AttacheBridgeUnavailableError("private unavailable"),
                    503,
                    "bridge_unavailable",
                ),
            )
            for error, status, code in cases:
                with self.subTest(code=code):
                    lookup_patch, _bridge_client = self._batch_lookup(error)
                    with (
                        lookup_patch,
                        patch(
                            "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                            return_value=date(2026, 9, 2),
                        ),
                    ):
                        response = self.client.post(
                            "/api/manual-dispatch/delivery/orders/"
                            "import-attache-current-future-preview"
                        )
                    self.assertEqual(status, response.status_code, response.text)
                    self.assertEqual(code, response.json()["detail"]["code"])
                    self.assertNotIn("private", response.text)

    def test_current_future_commit_rechecks_duplicates_and_never_calls_bridge(self):
        row = {
            "row_id": "ATTACHE-CURRENT-185480",
            "source_filename": "Attaché Direct",
            "selected": True,
            "importable": True,
            "is_duplicate": False,
            "invoice_number": "185480",
            "invoice_date": "2026-09-02",
            "order_no": "PO-185480",
            "company_name": "CURRENT FUTURE CUSTOMER",
            "delivery_address": "1 TEST ROAD",
            "suburb": "HALLAM",
            "postcode": "3803",
            "delivery_date": "2026-09-03",
            "pallet_quantity": 0,
            "loose_bags_quantity": 0,
            "carton_quantity": 0,
            "product_lines": [],
            "terms_description": "30 DAYS",
            "outstanding_balance": None,
        }
        self.service.create_delivery_order(
            CreateOrderRequest(
                invoice_number="185480",
                company_name="RACE WINNER",
                delivery_address="2 EXISTING ROAD",
                suburb="HALLAM",
                postcode="3803",
                delivery_date="2026-09-03",
            )
        )
        unique_row = {
            **row,
            "row_id": "ATTACHE-CURRENT-185481",
            "invoice_number": "185481",
            "order_no": "PO-185481",
        }
        duplicate_row = {
            **unique_row,
            "row_id": "ATTACHE-CURRENT-DUPLICATE",
        }
        payment_required_row = {
            **unique_row,
            "row_id": "ATTACHE-CURRENT-PAYMENT",
            "invoice_number": "185482",
            "terms_description": "C.O.D.",
            "outstanding_balance": 0.01,
            "payment_eligibility": "PAID_IN_FULL",
        }
        unknown_terms_row = {
            **unique_row,
            "row_id": "ATTACHE-CURRENT-TERMS",
            "invoice_number": "185483",
            "terms_description": "14 DAYS",
            "outstanding_balance": 0,
            "payment_eligibility": "PAID_IN_FULL",
        }
        unresolved_balance_row = {
            **unique_row,
            "row_id": "ATTACHE-CURRENT-BALANCE",
            "invoice_number": "185484",
            "terms_description": "C.O.D.",
            "outstanding_balance": None,
            "payment_eligibility": "PAID_IN_FULL",
        }
        issued_at = int(time.time())
        rows = [row, unique_row, duplicate_row, payment_required_row,
                unknown_terms_row, unresolved_balance_row]
        for candidate in rows:
            candidate.update(
                source=CURRENT_FUTURE_SOURCE, customer_code="DIRECT01",
                issued_at=issued_at,
                expires_at=issued_at + ELIGIBILITY_PROOF_TTL_SECONDS,
            )
            candidate["eligibility_proof"] = create_eligibility_proof(
                SimpleNamespace(**candidate), from_date="2026-09-02",
                secret=operator_cookie_secret(),
            )
        with (
            patch.object(manual_dispatch_api, "service", self.service),
            patch(
                "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
                side_effect=AssertionError("commit must not access Attaché"),
            ),
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            response = self.client.post(
                "/api/manual-dispatch/delivery/orders/"
                "import-attache-current-future-commit",
                json={
                    "from_date": "2026-09-02",
                    "rows": [
                        row,
                        unique_row,
                        duplicate_row,
                        payment_required_row,
                        unknown_terms_row,
                        unresolved_balance_row,
                    ]
                },
            )
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual(1, response.json()["imported_count"])
            self.assertEqual(5, response.json()["skipped_count"])
            skipped_reasons = {
                skipped["row_id"]: skipped["reason"]
                for skipped in response.json()["skipped_rows"]
            }
            self.assertIn("Duplicate", skipped_reasons[row["row_id"]])
            self.assertIn("Duplicate", skipped_reasons[duplicate_row["row_id"]])
            self.assertIn(
                "payment is required",
                skipped_reasons[payment_required_row["row_id"]],
            )
            self.assertIn(
                "terms are unsupported",
                skipped_reasons[unknown_terms_row["row_id"]],
            )
            self.assertIn(
                "balance is unavailable",
                skipped_reasons[unresolved_balance_row["row_id"]],
            )
            imported = next(
                order
                for order in self.repository.list_orders()
                if order.invoice_number == "185481"
            )
            self.assertEqual("ACTIVE", imported.status)
            self.assertEqual(
                [],
                self.repository.list_assignments_for_task(
                    "ORDER",
                    imported.order_id,
                ),
            )
            for invoice_number in ("185482", "185483", "185484"):
                self.assertFalse(any(
                    order.invoice_number == invoice_number
                    for order in self.repository.list_orders()
                ))

            overflow_rows = [
                {
                    **row,
                    "row_id": f"ATTACHE-CURRENT-{index}",
                    "invoice_number": f"9{index:05d}",
                }
                for index in range(201)
            ]
            overflow = self.client.post(
                "/api/manual-dispatch/delivery/orders/"
                "import-attache-current-future-commit",
                json={"rows": overflow_rows},
            )
            self.assertEqual(413, overflow.status_code, overflow.text)

    def _current_future_payment_preview(self, payment_cases):
        payloads = []
        for index, (terms, balance) in enumerate(payment_cases):
            payloads.append({
                **deepcopy(DIRECT_INVOICE_PAYLOAD),
                "invoice_number": str(186000 + index),
                "invoice_date": "2026-09-07",
                "terms_description": terms,
                "outstanding_balance": balance,
            })
        lookup_patch, bridge = self._batch_lookup(payloads)
        with lookup_patch, patch(
            "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
            return_value=date(2026, 9, 7),
        ):
            response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-current-future-preview",
            )
        self.assertEqual(200, response.status_code, response.text)
        bridge.lookup_invoices_from_date.assert_called_once_with("2026-09-07")
        return response.json()

    def test_current_future_commit_rejects_tampered_and_expired_preview_proofs(self):
        with (
            patch.object(manual_dispatch_api, "service", self.service),
            patch(
                "backend.services.manual_dispatch.attache_current_future_payment_eligibility.time.time",
                return_value=2000000000,
            ),
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            preview = self._current_future_payment_preview([
                ("C.O.D.", 203.5), ("30 DAYS", None),
                ("14 DAYS", None), ("C.O.D.", None),
            ])
            unpaid, ready, unknown, unresolved = preview["rows"]
            self.assertEqual("PAYMENT_REQUIRED", unpaid["payment_eligibility"])
            self.assertEqual(900, ready["expires_at"] - ready["issued_at"])
            self.assertRegex(ready["eligibility_proof"], r"^[0-9a-f]{64}$")
            cases = [
                ("forced selection", unpaid, {}, {}, False),
                ("positive balance changed to zero", unpaid, {"outstanding_balance": 0}, {}, True),
                ("COD changed to terms", unpaid, {"terms_description": "30 DAYS"}, {}, True),
                ("invoice identity", ready, {"invoice_number": "199999"}, {}, True),
                ("customer identity", ready, {"customer_code": "OTHER"}, {}, True),
                ("source", ready, {"source": "attache-direct"}, {}, True),
                ("from date", ready, {}, {"from_date": "2026-09-08"}, True),
                ("missing from date", ready, {}, {"from_date": None}, True),
                ("issued at", ready, {"issued_at": ready["issued_at"] + 1}, {}, True),
                ("expires at", ready, {"expires_at": ready["expires_at"] + 900}, {}, True),
                ("missing proof", ready, {"eligibility_proof": None}, {}, True),
                ("malformed proof", ready, {"eligibility_proof": "not-a-proof"}, {}, True),
                ("invalid signature", ready, {"eligibility_proof": "0" * 64}, {}, True),
                ("proof swapped from ready invoice", unpaid,
                 {"eligibility_proof": ready["eligibility_proof"], "outstanding_balance": 0}, {}, True),
                ("unknown terms selected", unknown, {}, {}, False),
                ("unresolved balance selected", unresolved, {}, {}, False),
            ]
            other_source = {**ready, "source": "attache-direct"}
            other_source["eligibility_proof"] = create_eligibility_proof(
                SimpleNamespace(**other_source), from_date=preview["from_date"],
                secret=operator_cookie_secret(),
            )
            cases.append(("signed for another source", other_source, {}, {}, True))
            with patch(
                "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
                side_effect=AssertionError("commit must not access Attaché"),
            ) as bridge_factory:
                for label, original, changes, wrapper, needs_refresh in cases:
                    with self.subTest(case=label):
                        submitted = {
                            **original, "selected": True, "importable": True,
                            "can_import": True, "payment_eligibility": "PAID_IN_FULL",
                            **changes,
                        }
                        if label == "missing proof":
                            submitted.pop("eligibility_proof")
                        response = self.client.post(
                            "/api/manual-dispatch/delivery/orders/import-attache-current-future-commit",
                            json={"from_date": preview["from_date"], "rows": [submitted], **wrapper},
                        )
                        self.assertEqual(200, response.status_code, response.text)
                        self.assertEqual(0, response.json()["imported_count"])
                        skipped = response.json()["skipped_rows"]
                        self.assertEqual(1, len(skipped))
                        self.assertEqual(needs_refresh, skipped[0].get("refresh_required", False))
                        if needs_refresh:
                            self.assertIn("Refresh Today & Future Invoices", skipped[0]["reason"])
                        self.assertEqual([], self.repository.list_orders())
                with patch(
                    "backend.services.manual_dispatch.attache_current_future_payment_eligibility.time.time",
                    return_value=ready["expires_at"],
                ):
                    expired = self.client.post(
                        "/api/manual-dispatch/delivery/orders/import-attache-current-future-commit",
                        json={"from_date": preview["from_date"], "rows": [ready]},
                    )
                self.assertEqual(200, expired.status_code, expired.text)
                self.assertEqual(0, expired.json()["imported_count"])
                self.assertTrue(expired.json()["skipped_rows"][0]["refresh_required"])
                self.assertIn("expired", expired.json()["skipped_rows"][0]["reason"])
                self.assertEqual([], self.repository.list_orders())
                bridge_factory.assert_not_called()

    def test_current_future_verified_ready_snapshots_commit_and_preserve_duplicate_checks(self):
        with patch.object(manual_dispatch_api, "service", self.service):
            authenticate_test_client(self.client, self.service, self.identity)
            preview = self._current_future_payment_preview([
                ("30 DAYS", None), ("C.O.D.", 0), ("C.O.D.", -27.5), ("30 DAYS", 500),
            ])
            self.assertEqual([], self.repository.list_orders())
            self.service.create_delivery_order(CreateOrderRequest(
                invoice_number="186003", company_name="RACE WINNER",
                delivery_address="2 EXISTING ROAD", suburb="HALLAM",
                postcode="3803", delivery_date="2026-09-08",
            ))
            rows = preview["rows"]
            rows[0]["note"] = "Local preview edit"
            rows[1]["outstanding_balance"] = 0.0
            rows.append({**rows[0], "row_id": "SAME-PAYLOAD-DUPLICATE"})
            with patch(
                "backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client",
                side_effect=AssertionError("commit must not access Attaché"),
            ) as bridge_factory:
                result = self.client.post(
                    "/api/manual-dispatch/delivery/orders/import-attache-current-future-commit",
                    json={"from_date": preview["from_date"], "rows": rows},
                )
                bridge_factory.assert_not_called()
            self.assertEqual(200, result.status_code, result.text)
            self.assertEqual(3, result.json()["imported_count"])
            self.assertEqual(2, result.json()["skipped_count"])
            self.assertTrue(all("Duplicate" in row["reason"] for row in result.json()["skipped_rows"]))
            self.assertEqual(4, len(self.repository.list_orders()))
            imported = result.json()["created_orders"]
            self.assertEqual("Local preview edit", imported[0]["note"])
            self.assertTrue(all(order["status"] == "ACTIVE" for order in imported))


if __name__ == "__main__":
    unittest.main()
