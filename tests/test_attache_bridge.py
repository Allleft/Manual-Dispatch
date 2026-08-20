from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient

from attache_bridge.config import (
    AttacheBridgeConfig,
    AttacheBridgeConfigurationError,
)
from attache_bridge.main import create_app
from attache_bridge.repository import (
    CUSTOMER_INVOICE_DOCUMENT_TYPE,
    DETAIL_SQL,
    DOCNUM_METADATA_SQL,
    HEADER_SQL,
    HEADER_EXTENSION2_SQL,
    HEADER_EXTENSION_SQL,
    HISTORICAL_HEADER_SQL,
    MAX_INVOICE_LINES,
    AttacheInvoiceDataError,
    AttacheInvoiceAmbiguousError,
    AttacheInvoiceNotFoundError,
    AttacheInvoiceRepository,
    AttacheInvoiceTooLargeError,
    AttacheOdbcAuthenticationError,
    AttacheOdbcAuthorizationError,
    AttacheOdbcTimeoutError,
    AttacheOdbcUnavailableError,
    normalize_invoice_number,
)


_DEFAULT_METADATA_DESCRIPTION = object()
_DEFAULT_QUERY_ROWS = object()


class FakeOdbcError(RuntimeError):
    pass


def _header(**overrides):
    values = {
        "doctype": 1,
        "internaldocnum": 196405,
        "docnum": "  185479",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _historical_header(**overrides):
    values = {
        "doctype": 1,
        "internaldocnum": 196405,
        "docnum": "  185479",
        "docdate": "10/08/2026",
        "deliverdate": None,
        "code": "ROTTHO",
        "name": "ROTARY TOOLS",
        "deliverydescription": "ROTARY TOOLS",
        "deliveryaddr1": "1/44 MAHONEYS RD",
        "deliverysuburb": "THOMASTOWN VIC",
        "refer": "45954",
        # These known non-delivery values are deliberately available on the
        # fake row so tests catch any accidental fallback to them.
        "postcode": "3061",
        "deliverycountry": "OPENS 830AM",
        "deliverystate": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _header_extension(**overrides):
    values = {
        "doctype": 1,
        "internaldocnum": 196405,
        "deliverypostcode": "3074",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _header_extension2(**overrides):
    values = {
        "doctype": 1,
        "internaldocnum": 196405,
        "deliveryaddr2": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _detail(line_number, code, description, quantity, unit=None):
    return SimpleNamespace(
        doctype=1,
        internaldocnum=196405,
        linenum=line_number,
        qtyorder=quantity,
        qtybackorder=0,
        qtyinv=quantity,
        packagenum=None,
        code=code,
        description=description,
        unitdescription=unit,
    )


class FakeCursor:
    def __init__(
        self,
        headers=None,
        historical_headers=_DEFAULT_QUERY_ROWS,
        header_extensions=_DEFAULT_QUERY_ROWS,
        header_extensions2=_DEFAULT_QUERY_ROWS,
        details=None,
        metadata_description=_DEFAULT_METADATA_DESCRIPTION,
        headers_by_candidate=None,
        fail_stage=None,
        error=None,
    ):
        self.headers = list(headers or [])
        self.historical_headers = (
            [_historical_header()]
            if historical_headers is _DEFAULT_QUERY_ROWS
            else list(historical_headers or [])
        )
        self.header_extensions = (
            [_header_extension()]
            if header_extensions is _DEFAULT_QUERY_ROWS
            else list(header_extensions or [])
        )
        self.header_extensions2 = (
            [_header_extension2()]
            if header_extensions2 is _DEFAULT_QUERY_ROWS
            else list(header_extensions2 or [])
        )
        self.details = list(details or [])
        self.metadata_description = (
            [("docnum", str, 9, 9, None, None, True)]
            if metadata_description is _DEFAULT_METADATA_DESCRIPTION
            else metadata_description
        )
        self.headers_by_candidate = {
            candidate: list(rows)
            for candidate, rows in (headers_by_candidate or {}).items()
        }
        self.fail_stage = fail_stage
        self.error = error or FakeOdbcError("HY000", "synthetic ODBC failure")
        self.executed = []
        self.mode = None
        self._description = None
        self.current_headers = []
        self.columns_calls = 0
        self.timeout_set_attempts = 0
        self.legacy_cursor_timeout = None
        self.header_execute_index = 0
        self.closed = False

    def _raise_for(self, stage):
        if self.fail_stage == stage:
            raise self.error

    @property
    def description(self):
        self._raise_for("metadata_description_start")
        return self._description

    @property
    def timeout(self):
        return self.legacy_cursor_timeout

    @timeout.setter
    def timeout(self, value):
        self.timeout_set_attempts += 1
        self._raise_for("timeout_configuration_start")
        self.legacy_cursor_timeout = value

    def columns(self, **kwargs):
        self.columns_calls += 1
        raise AssertionError(f"cursor.columns must not be called: {kwargs}")

    def execute(self, sql, *params):
        if sql == DOCNUM_METADATA_SQL:
            self._raise_for("metadata_execute_start")
        elif sql == HEADER_SQL:
            candidate_stage = f"candidate_{self.header_execute_index}_start"
            self._raise_for(candidate_stage)
            self.header_execute_index += 1
        elif sql == HISTORICAL_HEADER_SQL:
            self._raise_for("historical_header_start")
        elif sql == HEADER_EXTENSION_SQL:
            self._raise_for("header_extension_start")
        elif sql == HEADER_EXTENSION2_SQL:
            self._raise_for("header_extension2_start")
        elif sql == DETAIL_SQL:
            self._raise_for("detail_execute_start")
        self.executed.append((sql, params))
        if sql == DOCNUM_METADATA_SQL:
            self.mode = "metadata"
            self._description = self.metadata_description
        elif sql == HEADER_SQL:
            self.mode = "header"
            candidate = params[1]
            self.current_headers = self.headers_by_candidate.get(
                candidate,
                [
                    header
                    for header in self.headers
                    if getattr(header, "docnum", None) == candidate
                ],
            )
        elif sql == HISTORICAL_HEADER_SQL:
            self.mode = "historical_header"
        elif sql == HEADER_EXTENSION_SQL:
            self.mode = "header_extension"
        elif sql == HEADER_EXTENSION2_SQL:
            self.mode = "header_extension2"
        elif sql == DETAIL_SQL:
            self.mode = "detail"
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")
        return self

    def fetchmany(self, size):
        if self.mode == "header":
            rows = self.current_headers
        elif self.mode == "historical_header":
            rows = self.historical_headers
        elif self.mode == "header_extension":
            rows = self.header_extensions
        elif self.mode == "header_extension2":
            rows = self.header_extensions2
        elif self.mode == "detail":
            rows = self.details
        else:
            raise AssertionError("fetchmany is not valid for metadata discovery")
        return rows[:size]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor, fail_stage=None, error=None):
        self.fake_cursor = cursor
        self.fail_stage = fail_stage
        self.error = error or FakeOdbcError("HY000", "synthetic ODBC failure")
        self._timeout = None
        self.closed = False

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        if self.fail_stage == "timeout_configuration_start":
            raise self.error
        self._timeout = value

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


class FakeConnectionFactory:
    def __init__(self, cursor, fail_stage=None, error=None):
        self.connection = FakeConnection(cursor, fail_stage, error)
        self.fail_stage = fail_stage
        self.error = error or FakeOdbcError("HY000", "synthetic ODBC failure")
        self.calls = []

    def __call__(self, connection_string, timeout):
        self.calls.append((connection_string, timeout))
        if self.fail_stage == "connection_start":
            raise self.error
        return self.connection


class AttacheBridgeRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.config = AttacheBridgeConfig(
            connection_string="DSN=FAKE_READ_ONLY",
            api_token="test-token",
            connection_timeout_seconds=3,
            query_timeout_seconds=4,
        )
        self.details = [
            _detail(1, "RWORK", "WORKSHOP MIX #29", 300, "KG"),
            _detail(2, "BAG10", "PLASTIC BAG 10 kg", 30, "EAC"),
            _detail(3, "PAL", "PALLET", 1, "EAC"),
            _detail(4, "DEL", "DELIVERY /FUEL LEVY CHARGE", 1, "EAC"),
        ]

    def _repository(
        self,
        headers=None,
        historical_headers=_DEFAULT_QUERY_ROWS,
        header_extensions=_DEFAULT_QUERY_ROWS,
        header_extensions2=_DEFAULT_QUERY_ROWS,
        details=None,
        metadata_description=_DEFAULT_METADATA_DESCRIPTION,
        headers_by_candidate=None,
        fail_stage=None,
        error=None,
    ):
        effective_fail_stage = fail_stage or (
            "metadata_execute_start" if error is not None else None
        )
        cursor = FakeCursor(
            headers=headers,
            historical_headers=historical_headers,
            header_extensions=header_extensions,
            header_extensions2=header_extensions2,
            details=self.details if details is None else details,
            metadata_description=metadata_description,
            headers_by_candidate=headers_by_candidate,
            fail_stage=effective_fail_stage,
            error=error,
        )
        factory = FakeConnectionFactory(
            cursor,
            fail_stage=effective_fail_stage,
            error=error,
        )
        return AttacheInvoiceRepository(self.config, factory), cursor, factory

    def test_invoice_number_validation_accepts_padded_input_and_rejects_other_text(self):
        self.assertEqual("185479", normalize_invoice_number("  185479  "))
        for invalid in ("", "18 5479", "185479x", "-185479", "1" * 21):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_invoice_number(invalid)

    def test_zero_row_metadata_builds_bounded_exact_equality_candidates(self):
        repository, cursor, factory = self._repository(headers=[_header()])

        normal = repository.lookup_invoice("185479")
        self.assertEqual("185479", normal.invoice_number)
        self.assertEqual(
            (DOCNUM_METADATA_SQL, ()),
            cursor.executed[0],
        )
        header_candidates = [
            params[1]
            for sql, params in cursor.executed
            if sql == HEADER_SQL
        ]
        self.assertEqual(
            ["185479", " 185479", "  185479", "   185479"],
            header_candidates,
        )
        self.assertEqual(0, cursor.columns_calls)
        self.assertEqual([("DSN=FAKE_READ_ONLY", 3)], factory.calls)
        self.assertEqual(4, factory.connection.timeout)
        self.assertEqual(0, cursor.timeout_set_attempts)

    def test_success_tracks_every_stage_and_dynamic_candidate_count(self):
        repository, _cursor, _factory = self._repository(headers=[_header()])

        with self.assertLogs("attache_bridge.repository", level="INFO") as captured:
            repository.lookup_invoice("185479")

        rendered = "\n".join(captured.output)
        expected_stages = (
            "config_loaded",
            "connection_start",
            "connection_opened",
            "timeout_configuration_start",
            "timeout_configuration_done",
            "metadata_execute_start",
            "metadata_execute_done",
            "metadata_description_start",
            "metadata_description_done",
            "candidate_0_start",
            "candidate_0_done",
            "candidate_1_start",
            "candidate_1_done",
            "candidate_2_start",
            "candidate_2_done",
            "candidate_3_start",
            "candidate_3_done",
            "identity_resolved",
            "historical_header_start",
            "historical_header_done",
            "header_extension_start",
            "header_extension_done",
            "header_extension2_start",
            "header_extension2_done",
            "detail_execute_start",
            "detail_execute_done",
            "lookup_complete",
        )
        positions = [rendered.index(f"stage={stage}") for stage in expected_stages]
        self.assertEqual(sorted(positions), positions)
        self.assertRegex(rendered, r"elapsed_ms=\d+")

        narrower_repository, _cursor, _factory = self._repository(
            headers=[_header(docnum=" 185479")],
            metadata_description=[
                ("docnum", str, 7, 7, None, None, True)
            ],
        )
        with self.assertLogs("attache_bridge.repository", level="INFO") as captured:
            narrower_repository.lookup_invoice("185479")
        narrower_rendered = "\n".join(captured.output)
        self.assertIn("stage=candidate_1_done", narrower_rendered)
        self.assertNotIn("stage=candidate_2_start", narrower_rendered)

    def test_every_odbc_failure_stage_is_logged_without_business_or_secret_data(self):
        stages = (
            "connection_start",
            "timeout_configuration_start",
            "metadata_execute_start",
            "metadata_description_start",
            "candidate_0_start",
            "candidate_1_start",
            "candidate_2_start",
            "candidate_3_start",
            "historical_header_start",
            "header_extension_start",
            "header_extension2_start",
            "detail_execute_start",
        )
        secret_text = (
            "DSN=PRIVATE;UID=hidden-user;PWD=hidden-password;"
            "token=hidden-token;address=1 PRIVATE STREET"
        )
        for stage in stages:
            with self.subTest(stage=stage):
                repository, _cursor, _factory = self._repository(
                    headers=[_header()],
                    fail_stage=stage,
                    error=FakeOdbcError("HY000", -300, secret_text),
                )
                with self.assertLogs(
                    "attache_bridge.repository",
                    level="INFO",
                ) as captured:
                    with self.assertRaises(AttacheOdbcUnavailableError):
                        repository.lookup_invoice("185479")
                rendered = "\n".join(captured.output)
                self.assertIn(f"stage={stage}", rendered)
                self.assertRegex(rendered, r"elapsed_ms=\d+")
                self.assertIn("exception_class=FakeOdbcError", rendered)
                self.assertIn("sqlstate=HY000", rendered)
                self.assertIn("native_code=-300", rendered)
                for secret in (
                    "DSN=PRIVATE",
                    "hidden-user",
                    "hidden-password",
                    "hidden-token",
                    "1 PRIVATE STREET",
                    "1 TEST STREET",
                    "ROTARY TOOLS",
                    "185479",
                    secret_text,
                ):
                    self.assertNotIn(secret, rendered)

    def test_immediate_hyt00_timeout_setter_failure_keeps_stage_and_timing(self):
        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            fail_stage="timeout_configuration_start",
            error=FakeOdbcError("HYT00", -301, "PWD=hidden-password"),
        )

        with self.assertLogs("attache_bridge.repository", level="INFO") as captured:
            with self.assertRaises(AttacheOdbcTimeoutError):
                repository.lookup_invoice("185479")

        rendered = "\n".join(captured.output)
        self.assertIn("stage=timeout_configuration_start", rendered)
        self.assertRegex(rendered, r"elapsed_ms=\d+")
        self.assertIn("sqlstate=HYT00", rendered)
        self.assertIn("native_code=-301", rendered)
        self.assertNotIn("hidden-password", rendered)

    def test_customer_invoice_doctype_is_explicit_and_restricts_header_lookup(self):
        self.assertEqual(1, CUSTOMER_INVOICE_DOCUMENT_TYPE)
        repository, cursor, _factory = self._repository(headers=[_header()])

        repository.lookup_invoice("185479")

        header_calls = [
            params for sql, params in cursor.executed if sql == HEADER_SQL
        ]
        self.assertEqual(4, len(header_calls))
        self.assertTrue(
            all(
                params[0] == CUSTOMER_INVOICE_DOCUMENT_TYPE
                for params in header_calls
            )
        )

    def test_identity_and_historical_object_contracts_use_verified_fields(self):
        normalized_header_sql = " ".join(HEADER_SQL.upper().split())
        normalized_metadata_sql = " ".join(DOCNUM_METADATA_SQL.upper().split())
        normalized_historical_sql = " ".join(
            HISTORICAL_HEADER_SQL.upper().split()
        )
        normalized_extension_sql = " ".join(
            HEADER_EXTENSION_SQL.upper().split()
        )
        normalized_extension2_sql = " ".join(
            HEADER_EXTENSION2_SQL.upper().split()
        )
        self.assertEqual(
            "SELECT DOCTYPE, INTERNALDOCNUM, DOCNUM FROM ADMIN.INVOICEHEADER "
            "WHERE DOCTYPE = ? AND DOCNUM = ?",
            normalized_header_sql,
        )
        self.assertEqual(
            "SELECT DOCNUM FROM ADMIN.INVOICEHEADER WHERE 1 = 0",
            normalized_metadata_sql,
        )
        self.assertEqual(
            "SELECT DOCTYPE, INTERNALDOCNUM, DOCNUM, DOCDATE, DELIVERDATE, "
            "CODE, NAME, DELIVERYDESCRIPTION, DELIVERYADDR1, DELIVERYSUBURB, "
            "REFER FROM ADMIN.INVOICE_HEADER WHERE DOCTYPE = ? "
            "AND INTERNALDOCNUM = ?",
            normalized_historical_sql,
        )
        self.assertEqual(
            "SELECT DOCTYPE, INTERNALDOCNUM, DELIVERYPOSTCODE FROM "
            "ADMIN.INVOICEHEADEREXTENSION WHERE DOCTYPE = ? "
            "AND INTERNALDOCNUM = ?",
            normalized_extension_sql,
        )
        self.assertEqual(
            "SELECT DOCTYPE, INTERNALDOCNUM, DELIVERYADDR2 FROM "
            "ADMIN.INVOICEHEADEREXTENSION2 WHERE DOCTYPE = ? "
            "AND INTERNALDOCNUM = ?",
            normalized_extension2_sql,
        )
        self.assertNotIn("ADMIN.INVOICE_HEADER", normalized_header_sql)
        self.assertNotIn("ADMIN.INVOICE_HEADER", normalized_metadata_sql)
        for nonexistent_identity_field in (
            "DELIVERYDESCRIPTION",
            "DELIVERYADDR1",
            "DELIVERYADDR2",
            "DELIVERYSUBURB",
            "STATE",
            "POSTCODE",
            "INVORDERNUM",
        ):
            self.assertNotIn(nonexistent_identity_field, normalized_header_sql)

        repository, cursor, _factory = self._repository(headers=[_header()])
        repository.lookup_invoice("185479")

        self.assertEqual(0, cursor.columns_calls)

    def test_found_invoice_maps_historical_header_extensions_and_qtyinv_details(self):
        repository, cursor, _factory = self._repository(headers=[_header()])
        record = repository.lookup_invoice("185479")
        payload = record.to_public_dict()

        self.assertEqual(
            {
                "invoice_number",
                "invoice_date",
                "delivery_date",
                "customer_code",
                "customer_name",
                "order_reference",
                "invoice_order_number",
                "delivery_description",
                "delivery_address_lines",
                "suburb",
                "state",
                "postcode",
                "lines",
            },
            set(payload),
        )
        self.assertEqual("2026-08-10", payload["invoice_date"])
        self.assertIsNone(payload["delivery_date"])
        self.assertEqual("ROTTHO", payload["customer_code"])
        self.assertEqual("ROTARY TOOLS", payload["customer_name"])
        self.assertEqual("ROTARY TOOLS", payload["delivery_description"])
        self.assertEqual("45954", payload["order_reference"])
        self.assertIsNone(payload["invoice_order_number"])
        self.assertEqual(["1/44 MAHONEYS RD"], payload["delivery_address_lines"])
        self.assertEqual("THOMASTOWN VIC", payload["suburb"])
        self.assertIsNone(payload["state"])
        self.assertEqual("3074", payload["postcode"])
        self.assertNotEqual("3061", payload["postcode"])
        self.assertNotIn("7/44 MAHONEYS ROAD", payload["delivery_address_lines"])
        self.assertEqual([1, 2, 3, 4], [line["line_number"] for line in payload["lines"]])
        self.assertEqual(300, payload["lines"][0]["quantity_invoiced"])
        self.assertEqual(300, payload["lines"][0]["quantity_ordered"])
        self.assertEqual(0, payload["lines"][0]["quantity_backordered"])

        header_calls = [
            (sql, params)
            for sql, params in cursor.executed
            if sql == HEADER_SQL
        ]
        detail_calls = [
            (sql, params)
            for sql, params in cursor.executed
            if sql == DETAIL_SQL
        ]
        self.assertEqual(4, len(header_calls))
        self.assertIn((HEADER_SQL, (1, "  185479")), header_calls)
        self.assertEqual(
            [(HISTORICAL_HEADER_SQL, (1, 196405))],
            [call for call in cursor.executed if call[0] == HISTORICAL_HEADER_SQL],
        )
        self.assertEqual(
            [(HEADER_EXTENSION_SQL, (1, 196405))],
            [call for call in cursor.executed if call[0] == HEADER_EXTENSION_SQL],
        )
        self.assertEqual(
            [(HEADER_EXTENSION2_SQL, (1, 196405))],
            [call for call in cursor.executed if call[0] == HEADER_EXTENSION2_SQL],
        )
        self.assertEqual([(DETAIL_SQL, (1, 196405))], detail_calls)
        self.assertIn("WHERE doctype = ?", DETAIL_SQL)
        self.assertIn("AND internaldocnum = ?", DETAIL_SQL)
        self.assertIn("ORDER BY linenum", DETAIL_SQL)

    def test_optional_extension_rows_can_be_missing_or_add_address_line_two(self):
        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            header_extensions=[],
            header_extensions2=[],
        )
        payload = repository.lookup_invoice("185479").to_public_dict()
        self.assertEqual(["1/44 MAHONEYS RD"], payload["delivery_address_lines"])
        self.assertIsNone(payload["postcode"])

        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            header_extensions2=[_header_extension2(deliveryaddr2="REAR ENTRY")],
        )
        payload = repository.lookup_invoice("185479").to_public_dict()
        self.assertEqual(
            ["1/44 MAHONEYS RD", "REAR ENTRY"],
            payload["delivery_address_lines"],
        )

    def test_required_historical_header_and_unique_extension_rows_are_validated(self):
        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            historical_headers=[],
        )
        with self.assertRaises(AttacheInvoiceDataError):
            repository.lookup_invoice("185479")

        for extension_field, duplicate_rows in (
            ("header_extensions", [_header_extension(), _header_extension()]),
            ("header_extensions2", [_header_extension2(), _header_extension2()]),
        ):
            with self.subTest(extension_field=extension_field):
                repository, _cursor, _factory = self._repository(
                    headers=[_header()],
                    **{extension_field: duplicate_rows},
                )
                with self.assertRaises(AttacheInvoiceDataError):
                    repository.lookup_invoice("185479")

    def test_no_candidate_match_is_not_found(self):
        repository, _cursor, _factory = self._repository(headers=[])
        with self.assertRaises(AttacheInvoiceNotFoundError):
            repository.lookup_invoice("185479")

    def test_candidate_with_multiple_rows_is_immediately_ambiguous(self):
        repository, _cursor, _factory = self._repository(
            headers=[_header(), _header(internaldocnum=196406)]
        )
        with self.assertRaises(AttacheInvoiceAmbiguousError):
            repository.lookup_invoice("185479")

    def test_distinct_documents_across_candidates_are_ambiguous(self):
        repository, cursor, _factory = self._repository(
            headers_by_candidate={
                " 185479": [_header(docnum=" 185479")],
                "  185479": [
                    _header(docnum="  185479", internaldocnum=196406)
                ],
            }
        )

        with self.assertRaises(AttacheInvoiceAmbiguousError):
            repository.lookup_invoice("185479")

        attempted = [
            params[1]
            for sql, params in cursor.executed
            if sql == HEADER_SQL
        ]
        self.assertEqual(["185479", " 185479", "  185479"], attempted)

    def test_duplicate_document_identity_across_candidates_is_not_ambiguous(self):
        repository, cursor, _factory = self._repository(
            headers_by_candidate={
                "185479": [_header(docnum="185479")],
                "  185479": [_header(docnum="  185479")],
            }
        )

        record = repository.lookup_invoice("185479")

        self.assertEqual(196405, record.internal_document_number)
        attempted = [
            params[1]
            for sql, params in cursor.executed
            if sql == HEADER_SQL
        ]
        self.assertEqual(
            ["185479", " 185479", "  185479", "   185479"],
            attempted,
        )

    def test_missing_or_malformed_description_is_controlled(self):
        malformed_descriptions = (
            None,
            [],
            [("docnum",)],
            [("wrong_column", str, 9, 9, None, None, True)],
            [
                ("docnum", str, 9, 9, None, None, True),
                ("other", str, 9, 9, None, None, True),
            ],
        )
        for description in malformed_descriptions:
            with self.subTest(description=description):
                repository, cursor, factory = self._repository(
                    headers=[_header()],
                    metadata_description=description,
                )
                with self.assertRaises(AttacheInvoiceDataError):
                    repository.lookup_invoice("185479")
                self.assertEqual(0, cursor.columns_calls)
                self.assertTrue(cursor.closed)
                self.assertTrue(factory.connection.closed)

    def test_invalid_or_unreasonable_description_width_is_controlled(self):
        for width in (None, "invalid", True, 0, -1, 9.5, 65):
            with self.subTest(width=width):
                repository, cursor, factory = self._repository(
                    headers=[_header()],
                    metadata_description=[
                        ("docnum", str, width, width, None, None, True)
                    ],
                )
                with self.assertRaises(AttacheInvoiceDataError):
                    repository.lookup_invoice("185479")
                self.assertEqual(0, cursor.columns_calls)
                self.assertTrue(cursor.closed)
                self.assertTrue(factory.connection.closed)

        repository, cursor, _factory = self._repository(
            headers=[_header()],
            metadata_description=[
                ("docnum", str, 5, 5, None, None, True)
            ],
        )
        with self.assertRaises(AttacheInvoiceDataError):
            repository.lookup_invoice("185479")
        self.assertEqual(0, cursor.columns_calls)

    def test_detail_row_limit_accepts_500_and_rejects_501_without_truncation(self):
        allowed_details = [
            _detail(index, f"ITEM{index}", "TEST PRODUCT", 1, "EACH")
            for index in range(1, MAX_INVOICE_LINES + 1)
        ]
        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            details=allowed_details,
        )
        self.assertEqual(
            MAX_INVOICE_LINES,
            len(repository.lookup_invoice("185479").lines),
        )

        excessive_details = allowed_details + [
            _detail(MAX_INVOICE_LINES + 1, "ITEM501", "TEST PRODUCT", 1, "EACH")
        ]
        repository, cursor, factory = self._repository(
            headers=[_header()],
            details=excessive_details,
        )
        with self.assertRaises(AttacheInvoiceTooLargeError):
            repository.lookup_invoice("185479")
        self.assertTrue(cursor.closed)
        self.assertTrue(factory.connection.closed)

    def test_missing_configuration_fails_before_connecting(self):
        config = AttacheBridgeConfig(connection_string="", api_token="")
        cursor = FakeCursor(headers=[_header()])
        factory = FakeConnectionFactory(cursor)
        repository = AttacheInvoiceRepository(config, factory)
        with self.assertRaises(AttacheBridgeConfigurationError):
            repository.lookup_invoice("185479")
        self.assertEqual([], factory.calls)

    def test_timeout_authentication_authorization_and_unavailable_are_safe(self):
        cases = (
            (FakeOdbcError("HYT00", "fake-secret"), AttacheOdbcTimeoutError),
            (FakeOdbcError("HYT01", "fake-secret"), AttacheOdbcTimeoutError),
            (
                FakeOdbcError("28000", "fake-secret"),
                AttacheOdbcAuthenticationError,
            ),
            (
                FakeOdbcError("42501", "fake-secret"),
                AttacheOdbcAuthorizationError,
            ),
            (
                RuntimeError("driver timeout while PWD=fake-secret"),
                AttacheOdbcUnavailableError,
            ),
            (
                AttributeError(
                    "'pyodbc.Cursor' object has no attribute 'timeout' fake-secret"
                ),
                AttacheOdbcUnavailableError,
            ),
            (
                FakeOdbcError("HYT00 extra", "fake-secret"),
                AttacheOdbcUnavailableError,
            ),
            (
                RuntimeError("driver failed fake-secret"),
                AttacheOdbcUnavailableError,
            ),
        )
        for error, expected in cases:
            with self.subTest(expected=expected.__name__):
                repository, _cursor, _factory = self._repository(
                    headers=[_header()],
                    error=error,
                )
                with self.assertRaises(expected) as raised:
                    repository.lookup_invoice("185479")
                self.assertNotIn("fake-secret", str(raised.exception))

    def test_sqlstate_extraction_is_defensive_and_never_stringifies_objects(self):
        class MustNotStringify:
            def __str__(self):
                raise AssertionError("diagnostics must not stringify arbitrary args")

        repository, _cursor, _factory = self._repository(
            headers=[_header()],
            fail_stage="connection_start",
            error=FakeOdbcError(MustNotStringify(), "PWD=hidden-password"),
        )

        with self.assertLogs("attache_bridge.repository", level="INFO") as captured:
            with self.assertRaises(AttacheOdbcUnavailableError):
                repository.lookup_invoice("185479")

        rendered = "\n".join(captured.output)
        self.assertIn("sqlstate=unknown", rendered)
        self.assertIn("native_code=unknown", rendered)
        self.assertNotIn("hidden-password", rendered)

    def test_connection_and_cursor_are_closed_on_success_and_failure(self):
        repository, cursor, factory = self._repository(headers=[_header()])
        repository.lookup_invoice("185479")
        self.assertTrue(cursor.closed)
        self.assertTrue(factory.connection.closed)

    def test_non_finite_quantity_and_invalid_keys_are_controlled_data_errors(self):
        invalid_details = [
            _detail(1, "RWORK", "WORKSHOP MIX", "NaN", "KG")
        ]
        repository, cursor, factory = self._repository(
            headers=[_header()],
            details=invalid_details,
        )
        with self.assertRaises(AttacheInvoiceDataError):
            repository.lookup_invoice("185479")
        self.assertTrue(cursor.closed)
        self.assertTrue(factory.connection.closed)

        repository, _cursor, _factory = self._repository(
            headers=[_header(internaldocnum="not-an-integer")]
        )
        with self.assertRaises(AttacheInvoiceDataError):
            repository.lookup_invoice("185479")

        repository, cursor, factory = self._repository(headers=[])
        with self.assertRaises(AttacheInvoiceNotFoundError):
            repository.lookup_invoice("185479")
        self.assertTrue(cursor.closed)
        self.assertTrue(factory.connection.closed)

    def test_sql_surface_is_select_only_and_cannot_accept_request_sql(self):
        sql_statements = (
            DOCNUM_METADATA_SQL,
            HEADER_SQL,
            HISTORICAL_HEADER_SQL,
            HEADER_EXTENSION_SQL,
            HEADER_EXTENSION2_SQL,
            DETAIL_SQL,
        )
        for sql in sql_statements:
            normalized = " ".join(sql.upper().split())
            self.assertTrue(normalized.startswith("SELECT "))
            for write_verb in (
                "INSERT ",
                "UPDATE ",
                "DELETE ",
                "CREATE ",
                "ALTER ",
                "DROP ",
                "EXEC ",
                "EXECUTE ",
            ):
                self.assertNotIn(write_verb, normalized)
        self.assertNotIn("185479", HEADER_SQL)
        self.assertNotIn("%", HEADER_SQL)
        self.assertNotIn("LIKE", HEADER_SQL.upper())
        self.assertNotIn("TRIM(", HEADER_SQL.upper())
        self.assertNotIn("ADMIN.INVOICE_HEADER", HEADER_SQL.upper())
        combined_sql = "\n".join(sql_statements).upper()
        self.assertNotIn("ADMIN.DELIVERYADDRESS", combined_sql)
        self.assertNotIn("DELIVERYCOUNTRY", combined_sql)
        self.assertNotIn("DELIVERYSTATE", combined_sql)


class AttacheBridgeHttpTest(unittest.TestCase):
    def setUp(self):
        self.config = AttacheBridgeConfig(
            connection_string="DSN=FAKE_READ_ONLY",
            api_token="test-token",
        )

    def _client(self, repository):
        return TestClient(
            create_app(
                config_provider=lambda: self.config,
                repository_factory=lambda _config: repository,
            )
        )

    def test_health_does_not_connect_and_reports_configuration(self):
        class UnexpectedRepository:
            def lookup_invoice(self, _invoice_number):
                raise AssertionError("health must not query ODBC")

        with self._client(UnexpectedRepository()) as client:
            self.assertEqual(
                {"status": "ok", "configured": True},
                client.get("/health").json(),
            )

    def test_lookup_requires_token_and_returns_typed_record(self):
        class Repository:
            def lookup_invoice(self, invoice_number):
                self.invoice_number = invoice_number
                return SimpleNamespace(
                    to_public_dict=lambda: {
                        "invoice_number": invoice_number,
                        "lines": [],
                    }
                )

        repository = Repository()
        with self._client(repository) as client:
            denied = client.get("/v1/invoices/185479")
            self.assertEqual(401, denied.status_code)
            invalid = client.get(
                "/v1/invoices/185479",
                headers={"X-Attache-Bridge-Token": "wrong-token"},
            )
            self.assertEqual(401, invalid.status_code)
            response = client.get(
                "/v1/invoices/185479",
                headers={"X-Attache-Bridge-Token": "test-token"},
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("185479", response.json()["invoice_number"])
        self.assertEqual("185479", repository.invoice_number)

    def test_invoice_too_large_is_a_controlled_non_partial_response(self):
        class Repository:
            def lookup_invoice(self, _invoice_number):
                raise AttacheInvoiceTooLargeError("private row-count detail")

        with self._client(Repository()) as client:
            response = client.get(
                "/v1/invoices/185479",
                headers={"X-Attache-Bridge-Token": "test-token"},
            )
        self.assertEqual(422, response.status_code)
        self.assertEqual("invoice_too_large", response.json()["detail"]["code"])
        self.assertNotIn("private", response.text)

    def test_safe_http_errors_do_not_expose_underlying_secrets(self):
        class Repository:
            def lookup_invoice(self, _invoice_number):
                raise AttacheOdbcUnavailableError("PWD=fake-secret")

        with self._client(Repository()) as client:
            response = client.get(
                "/v1/invoices/185479",
                headers={"X-Attache-Bridge-Token": "test-token"},
            )
        self.assertEqual(503, response.status_code)
        self.assertEqual("bridge_unavailable", response.json()["detail"]["code"])
        self.assertNotIn("fake-secret", response.text)

        class UnexpectedRepository:
            def lookup_invoice(self, _invoice_number):
                raise RuntimeError("unexpected PWD=other-secret")

        with self._client(UnexpectedRepository()) as client:
            response = client.get(
                "/v1/invoices/185479",
                headers={"X-Attache-Bridge-Token": "test-token"},
            )
        self.assertEqual(503, response.status_code)
        self.assertEqual("bridge_unavailable", response.json()["detail"]["code"])
        self.assertNotIn("other-secret", response.text)

    def test_missing_configuration_is_controlled_and_health_remains_available(self):
        self.config = AttacheBridgeConfig(connection_string="", api_token="")
        secret_config = AttacheBridgeConfig(
            connection_string="DSN=fake;PWD=hidden-password",
            api_token="hidden-token",
        )
        self.assertNotIn("hidden-password", repr(secret_config))
        self.assertNotIn("hidden-token", repr(secret_config))
        with self._client(SimpleNamespace()) as client:
            self.assertEqual(
                {"status": "ok", "configured": False},
                client.get("/health").json(),
            )
            response = client.get("/v1/invoices/185479")
        self.assertEqual(503, response.status_code)
        self.assertEqual("bridge_not_configured", response.json()["detail"]["code"])


if __name__ == "__main__":
    unittest.main()
