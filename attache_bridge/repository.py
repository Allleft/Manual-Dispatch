from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
import re
import time

from .config import AttacheBridgeConfig, AttacheBridgeConfigurationError


LOGGER = logging.getLogger(__name__)

# Attaché Accounts uses document type 1 for Customer Invoices. Other document
# classes may reuse a visible document number and must not enter this workflow.
CUSTOMER_INVOICE_DOCUMENT_TYPE = 1
MAX_DOCNUM_COLUMN_SIZE = 64
MAX_INVOICE_LINES = 500
INVOICE_NUMBER_PATTERN = re.compile(r"^\d{1,20}$")
ODBC_SQLSTATE_PATTERN = re.compile(r"^[A-Z0-9]{5}$")
SAFE_EXCEPTION_CLASS_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

HEADER_SQL = """
SELECT
    doctype,
    internaldocnum,
    docnum
FROM admin.invoiceheader
WHERE doctype = ?
  AND docnum = ?
""".strip()

HISTORICAL_HEADER_SQL = """
SELECT
    doctype,
    internaldocnum,
    docnum,
    docdate,
    deliverdate,
    code,
    name,
    deliverydescription,
    deliveryaddr1,
    deliverysuburb,
    refer
FROM admin.invoice_header
WHERE doctype = ?
  AND internaldocnum = ?
""".strip()

HEADER_EXTENSION_SQL = """
SELECT
    doctype,
    internaldocnum,
    deliverypostcode
FROM admin.invoiceheaderextension
WHERE doctype = ?
  AND internaldocnum = ?
""".strip()

HEADER_EXTENSION2_SQL = """
SELECT
    doctype,
    internaldocnum,
    deliveryaddr2
FROM admin.invoiceheaderextension2
WHERE doctype = ?
  AND internaldocnum = ?
""".strip()

DOCNUM_METADATA_SQL = """
SELECT docnum
FROM admin.invoiceheader
WHERE 1 = 0
""".strip()

DETAIL_SQL = """
SELECT
    doctype,
    internaldocnum,
    linenum,
    qtyorder,
    qtybackorder,
    qtyinv,
    packagenum,
    code,
    description,
    unitdescription
FROM admin.invoicedetailproduct
WHERE doctype = ?
  AND internaldocnum = ?
ORDER BY linenum
""".strip()


class AttacheInvoiceNotFoundError(LookupError):
    pass


class AttacheInvoiceAmbiguousError(LookupError):
    pass


class AttacheOdbcTimeoutError(RuntimeError):
    pass


class AttacheOdbcAuthenticationError(RuntimeError):
    pass


class AttacheOdbcAuthorizationError(RuntimeError):
    pass


class AttacheOdbcUnavailableError(RuntimeError):
    pass


class AttacheInvoiceDataError(RuntimeError):
    pass


class AttacheInvoiceTooLargeError(AttacheInvoiceDataError):
    pass


class _OdbcLookupDiagnostics:
    def __init__(self):
        self._started_at = time.perf_counter()
        self.stage = "lookup_start"

    @property
    def elapsed_ms(self):
        return max(0, int((time.perf_counter() - self._started_at) * 1000))

    def mark(self, stage):
        self.stage = stage
        LOGGER.info(
            "Attaché ODBC lookup stage=%s elapsed_ms=%d",
            self.stage,
            self.elapsed_ms,
        )

    def log_failure(self, error):
        sqlstate, native_code = _safe_odbc_diagnostics(error)
        LOGGER.warning(
            "Attaché ODBC failure stage=%s elapsed_ms=%d "
            "exception_class=%s sqlstate=%s native_code=%s",
            self.stage,
            self.elapsed_ms,
            _safe_exception_class(error),
            sqlstate or "unknown",
            native_code if native_code is not None else "unknown",
        )


@dataclass(frozen=True)
class AttacheInvoiceLine:
    line_number: int
    code: str
    description: str
    unit: str | None
    quantity_invoiced: int | float
    quantity_ordered: int | float | None
    quantity_backordered: int | float | None
    package_number: int | float | str | None

    def to_dict(self):
        return {
            "line_number": self.line_number,
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "quantity_invoiced": self.quantity_invoiced,
            "quantity_ordered": self.quantity_ordered,
            "quantity_backordered": self.quantity_backordered,
            "package_number": self.package_number,
        }


@dataclass(frozen=True)
class AttacheInvoiceRecord:
    doctype: int
    internal_document_number: int
    invoice_number: str
    invoice_date: str | None
    delivery_date: str | None
    customer_code: str | None
    customer_name: str | None
    order_reference: str | None
    invoice_order_number: str | None
    delivery_description: str | None
    delivery_address_lines: tuple[str, ...]
    suburb: str | None
    state: str | None
    postcode: str | None
    lines: tuple[AttacheInvoiceLine, ...]

    def to_public_dict(self):
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "delivery_date": self.delivery_date,
            "customer_code": self.customer_code,
            "customer_name": self.customer_name,
            "order_reference": self.order_reference,
            "invoice_order_number": self.invoice_order_number,
            "delivery_description": self.delivery_description,
            "delivery_address_lines": list(self.delivery_address_lines),
            "suburb": self.suburb,
            "state": self.state,
            "postcode": self.postcode,
            "lines": [line.to_dict() for line in self.lines],
        }


def normalize_invoice_number(value):
    invoice_number = str(value or "").strip()
    if not INVOICE_NUMBER_PATTERN.fullmatch(invoice_number):
        raise ValueError("Invoice number must contain digits only.")
    return invoice_number


def create_pyodbc_connection(connection_string, timeout=5):
    try:
        import pyodbc
    except ImportError as error:
        raise AttacheBridgeConfigurationError(
            "The Attaché ODBC dependency is not installed."
        ) from error
    return pyodbc.connect(
        connection_string,
        autocommit=True,
        timeout=timeout,
    )


class AttacheInvoiceRepository:
    def __init__(self, config: AttacheBridgeConfig, connection_factory=None):
        self.config = config
        self.connection_factory = connection_factory or create_pyodbc_connection

    def lookup_invoice(self, invoice_number):
        diagnostics = _OdbcLookupDiagnostics()
        normalized_invoice_number = normalize_invoice_number(invoice_number)
        self.config.require_configured()
        diagnostics.mark("config_loaded")
        connection = None
        cursor = None
        try:
            diagnostics.mark("connection_start")
            connection = self.connection_factory(
                self.config.connection_string,
                timeout=self.config.connection_timeout_seconds,
            )
            diagnostics.mark("connection_opened")
            diagnostics.mark("timeout_configuration_start")
            connection.timeout = self.config.query_timeout_seconds
            cursor = connection.cursor()
            diagnostics.mark("timeout_configuration_done")

            diagnostics.mark("metadata_execute_start")
            cursor.execute(DOCNUM_METADATA_SQL)
            diagnostics.mark("metadata_execute_done")
            diagnostics.mark("metadata_description_start")
            max_docnum_width = self._docnum_max_width(cursor.description)
            diagnostics.mark("metadata_description_done")

            matching_headers = {}
            for candidate_index, candidate in enumerate(
                _docnum_candidates(
                    normalized_invoice_number,
                    max_docnum_width,
                )
            ):
                diagnostics.mark(f"candidate_{candidate_index}_start")
                cursor.execute(
                    HEADER_SQL,
                    CUSTOMER_INVOICE_DOCUMENT_TYPE,
                    candidate,
                )
                candidate_rows = list(cursor.fetchmany(2))
                diagnostics.mark(f"candidate_{candidate_index}_done")
                if len(candidate_rows) > 1:
                    raise AttacheInvoiceAmbiguousError(normalized_invoice_number)
                if not candidate_rows:
                    continue
                header = candidate_rows[0]
                identity = (
                    _required_integer(
                        _row_value(header, "doctype", 0),
                        "header doctype",
                    ),
                    _required_integer(
                        _row_value(header, "internaldocnum", 1),
                        "header internal document number",
                    ),
                )
                matching_headers.setdefault(identity, header)
                if len(matching_headers) > 1:
                    raise AttacheInvoiceAmbiguousError(normalized_invoice_number)

            if not matching_headers:
                raise AttacheInvoiceNotFoundError(normalized_invoice_number)
            doctype, internal_document_number = next(iter(matching_headers))
            diagnostics.mark("identity_resolved")

            diagnostics.mark("historical_header_start")
            cursor.execute(
                HISTORICAL_HEADER_SQL,
                doctype,
                internal_document_number,
            )
            historical_header_rows = list(cursor.fetchmany(2))
            diagnostics.mark("historical_header_done")
            historical_header = _required_single_row(
                historical_header_rows,
                "Attaché historical invoice header is unavailable or invalid.",
            )
            _validate_row_identity(
                historical_header,
                doctype,
                internal_document_number,
                "historical header",
            )

            diagnostics.mark("header_extension_start")
            cursor.execute(
                HEADER_EXTENSION_SQL,
                doctype,
                internal_document_number,
            )
            header_extension_rows = list(cursor.fetchmany(2))
            diagnostics.mark("header_extension_done")
            header_extension = _optional_single_row(
                header_extension_rows,
                "Attaché invoice header extension is invalid.",
            )
            if header_extension is not None:
                _validate_row_identity(
                    header_extension,
                    doctype,
                    internal_document_number,
                    "header extension",
                )

            diagnostics.mark("header_extension2_start")
            cursor.execute(
                HEADER_EXTENSION2_SQL,
                doctype,
                internal_document_number,
            )
            header_extension2_rows = list(cursor.fetchmany(2))
            diagnostics.mark("header_extension2_done")
            header_extension2 = _optional_single_row(
                header_extension2_rows,
                "Attaché invoice header extension 2 is invalid.",
            )
            if header_extension2 is not None:
                _validate_row_identity(
                    header_extension2,
                    doctype,
                    internal_document_number,
                    "header extension 2",
                )

            diagnostics.mark("detail_execute_start")
            cursor.execute(DETAIL_SQL, doctype, internal_document_number)
            detail_rows = list(cursor.fetchmany(MAX_INVOICE_LINES + 1))
            diagnostics.mark("detail_execute_done")
            if len(detail_rows) > MAX_INVOICE_LINES:
                raise AttacheInvoiceTooLargeError(
                    "Attaché invoice exceeds the supported product-line limit."
                )
            record = self._record_from_rows(
                historical_header,
                header_extension,
                header_extension2,
                detail_rows,
                normalized_invoice_number,
            )
            diagnostics.mark("lookup_complete")
            return record
        except (
            AttacheBridgeConfigurationError,
            AttacheInvoiceNotFoundError,
            AttacheInvoiceAmbiguousError,
            AttacheInvoiceDataError,
        ):
            raise
        except Exception as error:
            diagnostics.log_failure(error)
            raise _safe_odbc_error(error) from None
        finally:
            _close_quietly(cursor)
            _close_quietly(connection)

    @staticmethod
    def _docnum_max_width(description):
        try:
            if description is None or len(description) != 1:
                raise ValueError
            column = description[0]
            if len(column) < 4:
                raise ValueError
            column_name = str(column[0] or "").strip().lower()
            size = column[3]
        except (IndexError, KeyError, TypeError, ValueError):
            raise AttacheInvoiceDataError(
                "Unable to resolve Attaché invoice number metadata."
            ) from None
        if column_name != "docnum" or isinstance(size, bool):
            raise AttacheInvoiceDataError(
                "Attaché invoice number metadata is invalid."
            )
        try:
            numeric_size = Decimal(str(size))
        except Exception as error:
            raise AttacheInvoiceDataError(
                "Attaché invoice number metadata is invalid."
            ) from error
        if (
            not numeric_size.is_finite()
            or numeric_size != numeric_size.to_integral_value()
        ):
            raise AttacheInvoiceDataError(
                "Attaché invoice number metadata is invalid."
            )
        max_width = int(numeric_size)
        if not 1 <= max_width <= MAX_DOCNUM_COLUMN_SIZE:
            raise AttacheInvoiceDataError(
                "Attaché invoice number metadata is outside the supported range."
            )
        return max_width

    @staticmethod
    def _record_from_rows(
        historical_header,
        header_extension,
        header_extension2,
        detail_rows,
        requested_invoice_number,
    ):
        address_lines = tuple(
            value
            for value in (
                _clean_text(
                    _row_value(historical_header, "deliveryaddr1", 8)
                ),
                (
                    _clean_text(
                        _row_value(header_extension2, "deliveryaddr2", 2)
                    )
                    if header_extension2 is not None
                    else None
                ),
            )
            if value
        )
        lines = tuple(
            AttacheInvoiceLine(
                line_number=_required_integer(
                    _row_value(row, "linenum", 2),
                    "detail line number",
                ),
                quantity_ordered=_json_number(_row_value(row, "qtyorder", 3)),
                quantity_backordered=_json_number(
                    _row_value(row, "qtybackorder", 4)
                ),
                quantity_invoiced=_json_number(
                    _row_value(row, "qtyinv", 5),
                    required=True,
                ),
                package_number=_json_number_or_text(
                    _row_value(row, "packagenum", 6)
                ),
                code=_clean_text(_row_value(row, "code", 7)) or "",
                description=_clean_text(_row_value(row, "description", 8)) or "",
                unit=_clean_text(_row_value(row, "unitdescription", 9)),
            )
            for row in detail_rows
        )
        stored_invoice_number = (
            _clean_text(_row_value(historical_header, "docnum", 2))
            or requested_invoice_number
        )
        return AttacheInvoiceRecord(
            doctype=_required_integer(
                _row_value(historical_header, "doctype", 0),
                "header doctype",
            ),
            internal_document_number=_required_integer(
                _row_value(historical_header, "internaldocnum", 1),
                "header internal document number",
            ),
            invoice_number=stored_invoice_number,
            invoice_date=_iso_date(
                _row_value(historical_header, "docdate", 3)
            ),
            delivery_date=_iso_date(
                _row_value(historical_header, "deliverdate", 4)
            ),
            customer_code=_clean_text(
                _row_value(historical_header, "code", 5)
            ),
            customer_name=_clean_text(
                _row_value(historical_header, "name", 6)
            ),
            delivery_description=_clean_text(
                _row_value(historical_header, "deliverydescription", 7)
            ),
            delivery_address_lines=address_lines,
            suburb=_clean_text(
                _row_value(historical_header, "deliverysuburb", 9)
            ),
            state=None,
            postcode=(
                _clean_text(
                    _row_value(header_extension, "deliverypostcode", 2)
                )
                if header_extension is not None
                else None
            ),
            order_reference=_clean_text(
                _row_value(historical_header, "refer", 10)
            ),
            invoice_order_number=None,
            lines=lines,
        )


def _required_single_row(rows, message):
    if len(rows) != 1:
        raise AttacheInvoiceDataError(message)
    return rows[0]


def _optional_single_row(rows, message):
    if len(rows) > 1:
        raise AttacheInvoiceDataError(message)
    return rows[0] if rows else None


def _validate_row_identity(row, doctype, internal_document_number, label):
    row_identity = (
        _required_integer(_row_value(row, "doctype", 0), f"{label} doctype"),
        _required_integer(
            _row_value(row, "internaldocnum", 1),
            f"{label} internal document number",
        ),
    )
    if row_identity != (doctype, internal_document_number):
        raise AttacheInvoiceDataError(
            f"Attaché returned an inconsistent {label} record."
        )


def _row_value(row, name, index):
    if hasattr(row, name):
        return getattr(row, name)
    if isinstance(row, dict):
        if name in row:
            return row[name]
        if name.upper() in row:
            return row[name.upper()]
    try:
        return row[index]
    except (IndexError, KeyError, TypeError) as error:
        raise AttacheInvoiceDataError(
            "Attaché returned an incomplete invoice record."
        ) from error


def _docnum_candidates(invoice_number, max_width):
    if len(invoice_number) > max_width:
        raise AttacheInvoiceDataError(
            "Invoice number exceeds the Attaché docnum column width."
        )
    return tuple(
        (" " * leading_spaces) + invoice_number
        for leading_spaces in range(max_width - len(invoice_number) + 1)
    )


def _clean_text(value):
    text = str(value or "").strip()
    return text or None


def _iso_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text in {"00/00/0000", "0000-00-00"}:
        return None
    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    raise AttacheInvoiceDataError("Attaché returned an invalid invoice date.")


def _json_number(value, required=False):
    if value in (None, ""):
        if required:
            raise AttacheInvoiceDataError(
                "Attaché returned a product line without invoiced quantity."
            )
        return None
    try:
        number = Decimal(str(value))
    except Exception as error:
        raise AttacheInvoiceDataError(
            "Attaché returned an invalid product quantity."
        ) from error
    if not number.is_finite():
        raise AttacheInvoiceDataError(
            "Attaché returned an invalid product quantity."
        )
    return int(number) if number == number.to_integral_value() else float(number)


def _required_integer(value, field_name):
    if isinstance(value, bool):
        raise AttacheInvoiceDataError(
            f"Attaché returned an invalid {field_name}."
        )
    try:
        number = Decimal(str(value))
    except Exception as error:
        raise AttacheInvoiceDataError(
            f"Attaché returned an invalid {field_name}."
        ) from error
    if not number.is_finite() or number != number.to_integral_value():
        raise AttacheInvoiceDataError(
            f"Attaché returned an invalid {field_name}."
        )
    return int(number)


def _json_number_or_text(value):
    if value in (None, ""):
        return None
    try:
        return _json_number(value)
    except AttacheInvoiceDataError:
        return _clean_text(value)


def _safe_odbc_diagnostics(error):
    try:
        arguments = error.args
    except Exception:
        return None, None
    if not isinstance(arguments, tuple) or not arguments:
        return None, None

    first_argument = arguments[0]
    if isinstance(first_argument, (tuple, list)):
        structured_arguments = tuple(first_argument)
    else:
        structured_arguments = arguments

    sqlstate = None
    if structured_arguments and type(structured_arguments[0]) is str:
        candidate = structured_arguments[0].strip().upper()
        if ODBC_SQLSTATE_PATTERN.fullmatch(candidate):
            sqlstate = candidate

    native_code = next(
        (
            value
            for value in structured_arguments[1:]
            if type(value) is int
        ),
        None,
    )
    return sqlstate, native_code


def _safe_exception_class(error):
    class_name = type(error).__name__
    if SAFE_EXCEPTION_CLASS_PATTERN.fullmatch(class_name):
        return class_name
    return "Exception"


def _safe_odbc_error(error):
    sqlstate, _native_code = _safe_odbc_diagnostics(error)
    if sqlstate in {"HYT00", "HYT01"}:
        return AttacheOdbcTimeoutError("Attaché ODBC query timed out.")
    if sqlstate == "28000":
        return AttacheOdbcAuthenticationError(
            "Attaché ODBC authentication failed."
        )
    if sqlstate == "42501":
        return AttacheOdbcAuthorizationError(
            "Attaché ODBC authorization failed."
        )
    return AttacheOdbcUnavailableError("Attaché ODBC is unavailable.")


def _close_quietly(resource):
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        pass
