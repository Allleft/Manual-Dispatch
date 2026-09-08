from dataclasses import dataclass, field
from datetime import date
import json
import logging
import math
import os
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)
BRIDGE_URL_ENV = "ATTACHE_BRIDGE_URL"
BRIDGE_API_TOKEN_ENV = "ATTACHE_BRIDGE_API_TOKEN"
BRIDGE_TIMEOUT_ENV = "ATTACHE_BRIDGE_TIMEOUT_SECONDS"
MAX_BRIDGE_RESPONSE_BYTES = 1024 * 1024
MAX_BRIDGE_BATCH_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_CURRENT_FUTURE_INVOICES = 200
INVOICE_NUMBER_PATTERN = re.compile(r"^\d{1,20}$")


class AttacheBridgeError(RuntimeError):
    pass


class AttacheBridgeConfigurationError(AttacheBridgeError):
    pass


class AttacheBridgeInvoiceNotFoundError(AttacheBridgeError):
    pass


class AttacheBridgeAmbiguousInvoiceError(AttacheBridgeError):
    pass


class AttacheBridgeInvoiceTooLargeError(AttacheBridgeError):
    pass


class AttacheBridgeInvoiceBatchTooLargeError(AttacheBridgeError):
    pass


class AttacheBridgeTimeoutError(AttacheBridgeError):
    pass


class AttacheBridgeUnavailableError(AttacheBridgeError):
    pass


class AttacheBridgeMalformedResponseError(AttacheBridgeError):
    pass


@dataclass(frozen=True)
class AttacheBridgeClientConfig:
    base_url: str
    api_token: str = field(repr=False)
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls, environ=None):
        environment = os.environ if environ is None else environ
        base_url = str(environment.get(BRIDGE_URL_ENV, "") or "").strip()
        api_token = str(
            environment.get(BRIDGE_API_TOKEN_ENV, "") or ""
        ).strip()
        timeout_seconds = _bounded_timeout(environment.get(BRIDGE_TIMEOUT_ENV))
        config = cls(
            base_url=base_url,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
        )
        return config.validate()

    def validate(self):
        if not self.base_url or not self.api_token:
            raise AttacheBridgeConfigurationError(
                "Attaché lookup is not configured."
            )
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise AttacheBridgeConfigurationError(
                "Attaché bridge URL configuration is invalid."
            )
        return self


class AttacheBridgeClient:
    def __init__(self, config: AttacheBridgeClientConfig, opener=None):
        self.config = config.validate()
        self.opener = opener or urlopen

    @classmethod
    def from_environment(cls, environ=None, opener=None):
        return cls(
            AttacheBridgeClientConfig.from_environment(environ),
            opener=opener,
        )

    def lookup_invoice(self, invoice_number):
        normalized_invoice_number = normalize_attache_invoice_number(
            invoice_number
        )
        url = (
            f"{self.config.base_url.rstrip('/')}"
            f"/v1/invoices/{quote(normalized_invoice_number, safe='')}"
        )
        payload = self._request_json(
            url,
            max_response_bytes=MAX_BRIDGE_RESPONSE_BYTES,
            map_http_error=lambda error: _map_http_error(
                error,
                normalized_invoice_number,
            ),
            timeout_message=(
                "Attaché lookup timed out. You can still use Import Attaché PDF."
            ),
            unavailable_message=(
                "Attaché lookup is currently unavailable. "
                "You can still use Import Attaché PDF."
            ),
            malformed_message=(
                "Attaché lookup returned an invalid response. "
                "You can still use Import Attaché PDF."
            ),
        )

        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise AttacheBridgeMalformedResponseError(
                "Attaché lookup returned an invalid response. "
                "You can still use Import Attaché PDF."
            )
        returned_invoice_number = str(payload.get("invoice_number") or "").strip()
        if returned_invoice_number != normalized_invoice_number:
            raise AttacheBridgeMalformedResponseError(
                "Attaché lookup returned an invalid response. "
                "You can still use Import Attaché PDF."
            )
        return payload

    def lookup_invoices_from_date(self, from_date):
        normalized_from_date = normalize_attache_from_date(from_date)
        url = (
            f"{self.config.base_url.rstrip('/')}/v1/invoices?"
            f"{urlencode({'from_date': normalized_from_date})}"
        )
        malformed_message = (
            "Attaché current/future invoice lookup returned an invalid response."
        )
        payload = self._request_json(
            url,
            max_response_bytes=MAX_BRIDGE_BATCH_RESPONSE_BYTES,
            map_http_error=_map_batch_http_error,
            timeout_message="Attaché current/future invoice lookup timed out.",
            unavailable_message=(
                "Attaché current/future invoice lookup is currently unavailable."
            ),
            malformed_message=malformed_message,
        )
        if not isinstance(payload, dict):
            raise AttacheBridgeMalformedResponseError(malformed_message)
        if payload.get("from_date") != normalized_from_date:
            raise AttacheBridgeMalformedResponseError(malformed_message)
        invoices = payload.get("invoices")
        if (
            not isinstance(invoices, list)
            or len(invoices) > MAX_CURRENT_FUTURE_INVOICES
        ):
            raise AttacheBridgeMalformedResponseError(malformed_message)

        seen_invoice_numbers = set()
        for invoice in invoices:
            if not isinstance(invoice, dict):
                raise AttacheBridgeMalformedResponseError(malformed_message)
            invoice_number = invoice.get("invoice_number")
            if (
                not isinstance(invoice_number, str)
                or not INVOICE_NUMBER_PATTERN.fullmatch(invoice_number)
                or invoice_number in seen_invoice_numbers
            ):
                raise AttacheBridgeMalformedResponseError(malformed_message)
            seen_invoice_numbers.add(invoice_number)
            try:
                invoice_date = normalize_attache_from_date(
                    invoice.get("invoice_date")
                )
            except ValueError:
                raise AttacheBridgeMalformedResponseError(
                    malformed_message
                ) from None
            if invoice_date < normalized_from_date:
                raise AttacheBridgeMalformedResponseError(malformed_message)
            terms_description = invoice.get("terms_description")
            if terms_description is not None and not isinstance(
                terms_description,
                str,
            ):
                raise AttacheBridgeMalformedResponseError(malformed_message)
            outstanding_balance = invoice.get("outstanding_balance")
            if outstanding_balance is not None and (
                isinstance(outstanding_balance, bool)
                or not isinstance(outstanding_balance, (int, float))
                or not math.isfinite(outstanding_balance)
            ):
                raise AttacheBridgeMalformedResponseError(malformed_message)
            lines = invoice.get("lines")
            if (
                not isinstance(lines, list)
                or not all(isinstance(line, dict) for line in lines)
            ):
                raise AttacheBridgeMalformedResponseError(malformed_message)
        return invoices

    def _request_json(
        self,
        url,
        *,
        max_response_bytes,
        map_http_error,
        timeout_message,
        unavailable_message,
        malformed_message,
    ):
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Attache-Bridge-Token": self.config.api_token,
            },
            method="GET",
        )
        response = None
        try:
            response = self.opener(
                request,
                timeout=self.config.timeout_seconds,
            )
            return _read_json_response(
                response,
                max_response_bytes=max_response_bytes,
                malformed_message=malformed_message,
            )
        except HTTPError as error:
            mapped_error = map_http_error(error)
            try:
                error.close()
            except Exception:
                pass
            raise mapped_error from None
        except (TimeoutError, socket.timeout) as error:
            raise AttacheBridgeTimeoutError(timeout_message) from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise AttacheBridgeTimeoutError(timeout_message) from error
            raise AttacheBridgeUnavailableError(unavailable_message) from error
        except AttacheBridgeMalformedResponseError:
            raise
        except Exception as error:
            LOGGER.warning("Attaché bridge unavailable")
            raise AttacheBridgeUnavailableError(unavailable_message) from error
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass


def create_attache_bridge_client(environ=None, opener=None):
    return AttacheBridgeClient.from_environment(environ, opener=opener)


def normalize_attache_invoice_number(value):
    invoice_number = str(value or "").strip()
    if not INVOICE_NUMBER_PATTERN.fullmatch(invoice_number):
        raise ValueError("Invoice number must contain digits only.")
    return invoice_number


def normalize_attache_from_date(value):
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("from_date must use YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("from_date must use YYYY-MM-DD format.") from None
    if parsed.isoformat() != value:
        raise ValueError("from_date must use YYYY-MM-DD format.")
    return value


def _bounded_timeout(value):
    if value in (None, ""):
        return 5.0
    try:
        timeout = float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise AttacheBridgeConfigurationError(
            f"{BRIDGE_TIMEOUT_ENV} must be between 0.1 and 30 seconds."
        ) from error
    if not 0.1 <= timeout <= 30:
        raise AttacheBridgeConfigurationError(
            f"{BRIDGE_TIMEOUT_ENV} must be between 0.1 and 30 seconds."
        )
    return timeout


def _read_json_response(
    response,
    *,
    max_response_bytes=MAX_BRIDGE_RESPONSE_BYTES,
    malformed_message=(
        "Attaché lookup returned an invalid response. "
        "You can still use Import Attaché PDF."
    ),
):
    payload = response.read(max_response_bytes + 1)
    if len(payload) > max_response_bytes:
        raise AttacheBridgeMalformedResponseError(malformed_message)
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AttacheBridgeMalformedResponseError(malformed_message) from error


def _map_http_error(error, invoice_number):
    code = _read_error_code(error)
    if error.code == 404 or code == "invoice_not_found":
        return AttacheBridgeInvoiceNotFoundError(
            f"Invoice {invoice_number} was not found in Attaché."
        )
    if error.code == 409 or code == "multiple_invoice_matches":
        return AttacheBridgeAmbiguousInvoiceError(
            f"Multiple Attaché invoices matched {invoice_number}. No invoice was selected."
        )
    if error.code == 422 or code == "invoice_too_large":
        return AttacheBridgeInvoiceTooLargeError(
            "Attaché invoice exceeds the supported product-line limit. "
            "No partial preview was created."
        )
    if error.code == 504 or code == "odbc_timeout":
        return AttacheBridgeTimeoutError(
            "Attaché lookup timed out. You can still use Import Attaché PDF."
        )
    return AttacheBridgeUnavailableError(
        "Attaché lookup is currently unavailable. "
        "You can still use Import Attaché PDF."
    )


def _map_batch_http_error(error):
    code = _read_error_code(error)
    if error.code == 413 or code == "invoice_batch_limit_exceeded":
        return AttacheBridgeInvoiceBatchTooLargeError(
            "Too many current/future Attaché invoices were returned. "
            "No partial preview was created."
        )
    if error.code == 422 or code == "invoice_too_large":
        return AttacheBridgeInvoiceTooLargeError(
            "An Attaché invoice exceeds the supported product-line limit. "
            "No partial preview was created."
        )
    if error.code == 504 or code == "odbc_timeout":
        return AttacheBridgeTimeoutError(
            "Attaché current/future invoice lookup timed out."
        )
    return AttacheBridgeUnavailableError(
        "Attaché current/future invoice lookup is currently unavailable."
    )


def _read_error_code(error):
    try:
        payload = error.read(64 * 1024)
        parsed = json.loads(payload.decode("utf-8"))
        detail = parsed.get("detail") if isinstance(parsed, dict) else None
        return detail.get("code") if isinstance(detail, dict) else None
    except Exception:
        return None
