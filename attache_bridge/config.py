from dataclasses import dataclass, field
import os


ODBC_CONNECTION_STRING_ENV = "ATTACHE_ODBC_CONNECTION_STRING"
BRIDGE_API_TOKEN_ENV = "ATTACHE_BRIDGE_API_TOKEN"
CONNECTION_TIMEOUT_ENV = "ATTACHE_BRIDGE_CONNECTION_TIMEOUT_SECONDS"
QUERY_TIMEOUT_ENV = "ATTACHE_BRIDGE_QUERY_TIMEOUT_SECONDS"


class AttacheBridgeConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttacheBridgeConfig:
    connection_string: str = field(repr=False)
    api_token: str = field(repr=False)
    connection_timeout_seconds: int = 5
    query_timeout_seconds: int = 5

    @classmethod
    def from_environment(cls, environ=None):
        environment = os.environ if environ is None else environ
        return cls(
            connection_string=str(
                environment.get(ODBC_CONNECTION_STRING_ENV, "") or ""
            ).strip(),
            api_token=str(environment.get(BRIDGE_API_TOKEN_ENV, "") or "").strip(),
            connection_timeout_seconds=_bounded_timeout(
                environment.get(CONNECTION_TIMEOUT_ENV),
                CONNECTION_TIMEOUT_ENV,
            ),
            query_timeout_seconds=_bounded_timeout(
                environment.get(QUERY_TIMEOUT_ENV),
                QUERY_TIMEOUT_ENV,
            ),
        )

    def require_configured(self):
        missing = []
        if not self.connection_string:
            missing.append(ODBC_CONNECTION_STRING_ENV)
        if not self.api_token:
            missing.append(BRIDGE_API_TOKEN_ENV)
        if missing:
            raise AttacheBridgeConfigurationError(
                "Attaché bridge configuration is incomplete."
            )
        return self

    @property
    def configured(self):
        return bool(self.connection_string and self.api_token)


def _bounded_timeout(value, name):
    if value in (None, ""):
        return 5
    try:
        timeout = int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise AttacheBridgeConfigurationError(
            f"{name} must be an integer between 1 and 30."
        ) from error
    if not 1 <= timeout <= 30:
        raise AttacheBridgeConfigurationError(
            f"{name} must be an integer between 1 and 30."
        )
    return timeout
