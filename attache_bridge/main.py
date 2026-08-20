import logging
import secrets

from fastapi import FastAPI, Header, HTTPException

from .config import AttacheBridgeConfig, AttacheBridgeConfigurationError
from .repository import (
    AttacheInvoiceAmbiguousError,
    AttacheInvoiceDataError,
    AttacheInvoiceNotFoundError,
    AttacheInvoiceRepository,
    AttacheInvoiceTooLargeError,
    AttacheOdbcAuthenticationError,
    AttacheOdbcAuthorizationError,
    AttacheOdbcTimeoutError,
    AttacheOdbcUnavailableError,
    normalize_invoice_number,
)


LOGGER = logging.getLogger(__name__)


def create_app(config_provider=None, repository_factory=None):
    app = FastAPI(
        title="Attaché Read-only Invoice Bridge",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    load_config = config_provider or AttacheBridgeConfig.from_environment
    create_repository = repository_factory or (
        lambda config: AttacheInvoiceRepository(config)
    )

    @app.get("/health")
    def health():
        try:
            configured = load_config().configured
        except AttacheBridgeConfigurationError:
            configured = False
        return {"status": "ok", "configured": configured}

    @app.get("/v1/invoices/{invoice_number}")
    def invoice_lookup(
        invoice_number: str,
        bridge_token: str | None = Header(
            default=None,
            alias="X-Attache-Bridge-Token",
        ),
    ):
        try:
            normalized_invoice_number = normalize_invoice_number(invoice_number)
        except ValueError as error:
            raise _http_error(400, "invalid_invoice_number", str(error)) from error

        try:
            config = load_config().require_configured()
        except AttacheBridgeConfigurationError as error:
            LOGGER.warning("Attaché bridge configuration unavailable")
            raise _http_error(
                503,
                "bridge_not_configured",
                "Attaché bridge is not configured.",
            ) from error

        if not bridge_token or not secrets.compare_digest(
            bridge_token,
            config.api_token,
        ):
            raise _http_error(
                401,
                "bridge_authentication_failed",
                "Attaché bridge authentication failed.",
            )

        LOGGER.info("Attaché lookup started")
        try:
            record = create_repository(config).lookup_invoice(
                normalized_invoice_number
            )
        except AttacheInvoiceNotFoundError as error:
            LOGGER.info("Attaché invoice not found")
            raise _http_error(
                404,
                "invoice_not_found",
                f"Invoice {normalized_invoice_number} was not found in Attaché.",
            ) from error
        except AttacheInvoiceAmbiguousError as error:
            LOGGER.warning("Attaché lookup returned multiple headers")
            raise _http_error(
                409,
                "multiple_invoice_matches",
                "Multiple Attaché invoices matched the supplied invoice number.",
            ) from error
        except AttacheInvoiceTooLargeError as error:
            LOGGER.warning("Attaché invoice exceeds product-line limit")
            raise _http_error(
                422,
                "invoice_too_large",
                "Attaché invoice exceeds the supported product-line limit.",
            ) from error
        except AttacheOdbcTimeoutError as error:
            LOGGER.warning("Attaché ODBC timeout")
            raise _http_error(
                504,
                "odbc_timeout",
                "Attaché lookup timed out.",
            ) from error
        except AttacheOdbcAuthenticationError as error:
            LOGGER.warning("Attaché ODBC authentication failed")
            raise _http_error(
                503,
                "odbc_authentication_failed",
                "Attaché lookup authentication is unavailable.",
            ) from error
        except AttacheOdbcAuthorizationError as error:
            LOGGER.warning("Attaché ODBC authorization failed")
            raise _http_error(
                503,
                "odbc_authorization_failed",
                "Attaché lookup authorization is unavailable.",
            ) from error
        except (
            AttacheInvoiceDataError,
            AttacheOdbcUnavailableError,
            AttacheBridgeConfigurationError,
        ) as error:
            LOGGER.warning("Attaché bridge unavailable")
            raise _http_error(
                503,
                "bridge_unavailable",
                "Attaché lookup is unavailable.",
            ) from error
        except Exception as error:
            LOGGER.warning("Attaché bridge unavailable")
            raise _http_error(
                503,
                "bridge_unavailable",
                "Attaché lookup is unavailable.",
            ) from error

        LOGGER.info("Attaché lookup succeeded")
        return record.to_public_dict()

    return app


def _http_error(status_code, code, message):
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


app = create_app()
