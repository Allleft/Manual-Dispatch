import base64
import hmac
import json
import os
import secrets
import time
import warnings
from hashlib import sha256
from fastapi import HTTPException, Request
from backend.schemas import (
    AssignDriverVehicleRequest,
    OperatorAccountIdentity,
    SaveFinalTripSummaryRequest,
)
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationRequiredError


ALLOW_REGISTRATION_ENV = "MANUAL_DISPATCH_ALLOW_REGISTRATION"

REGISTRATION_DISABLED_MESSAGE = "Registration is disabled. Please contact an administrator."

OPERATOR_COOKIE_NAME = "manual_dispatch_operator"

OPERATOR_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 12

OPERATOR_COOKIE_SECRET_ENV = "MANUAL_DISPATCH_AUTH_COOKIE_SECRET"

OPERATOR_COOKIE_SECURE_ENV = "MANUAL_DISPATCH_AUTH_COOKIE_SECURE"

AUTHENTICATION_REQUIRED_MESSAGE = "Authentication required"

_EPHEMERAL_COOKIE_SECRET = secrets.token_bytes(32)
_ephemeral_cookie_secret_warning_emitted = False

def assign_driver_vehicle_request_from_payload(payload):
    payload = payload or {}
    return AssignDriverVehicleRequest(
        dispatch_date=payload.get("dispatch_date"),
        delivery_date=payload.get("delivery_date"),
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id") or None,
    )

def save_final_trip_summary_request_from_payload(payload, identity=None):
    payload = payload or {}
    return SaveFinalTripSummaryRequest(
        dispatch_date=payload.get("dispatch_date"),
        delivery_date=payload.get("delivery_date"),
        driver_id=payload.get("driver_id"),
        driver_name_snapshot=payload.get("driver_name_snapshot")
        or payload.get("driver_name"),
        vehicle_id=payload.get("vehicle_id") or None,
        vehicle_rego_snapshot=payload.get("vehicle_rego_snapshot")
        or payload.get("vehicle_rego"),
        total_pallets=payload.get("total_pallets") or 0,
        total_loose_bags=payload.get("total_loose_bags") or 0,
        generated_at=payload.get("generated_at"),
        trips=payload.get("trips") or [],
        opshop_pickups=payload.get("opshop_pickups") or [],
        saved_by_account_name=(
            identity.account_name if identity else payload.get("saved_by_account_name")
        ),
        saved_by_account_id=(
            identity.account_id if identity else payload.get("saved_by_account_id")
        ),
    )

def with_logbook_actor(service, http_request, callback):
    identity = authenticated_operator_from_request(http_request)
    with service.logbook_actor(identity.account_name):
        return callback()

def current_operator_account_name(service, http_request):
    identity = getattr(getattr(http_request, "state", None), "operator_identity", None)
    if identity:
        return identity.account_name
    try:
        return validate_operator_session(service, http_request).account_name
    except ValueError:
        return None

def require_authenticated_operator(service, http_request: Request):
    try:
        identity = validate_operator_session(service, http_request)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail=AUTHENTICATION_REQUIRED_MESSAGE,
            headers={"WWW-Authenticate": "Cookie"},
        ) from error
    http_request.state.operator_identity = identity
    return identity

def authenticated_operator_from_request(http_request):
    identity = getattr(getattr(http_request, "state", None), "operator_identity", None)
    if not identity:
        raise HTTPException(status_code=401, detail=AUTHENTICATION_REQUIRED_MESSAGE)
    return identity

def validate_operator_session(service, http_request, now=None):
    if not http_request:
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    cookie_value = http_request.cookies.get(OPERATOR_COOKIE_NAME)
    if not cookie_value:
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    payload_text, submitted_signature = _split_operator_cookie(cookie_value)
    payload = _decode_operator_cookie_payload(payload_text)
    if payload.get("version") != 1:
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    account_id = payload.get("account_id")
    issued_at = payload.get("issued_at")
    account_name = payload.get("account_name")
    if (
        isinstance(account_id, bool)
        or not isinstance(account_id, int)
        or isinstance(issued_at, bool)
        or not isinstance(issued_at, int)
        or not isinstance(account_name, str)
    ):
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    account = service.repository.get_operator_account_by_id(account_id)
    if not account or account.account_name != account_name:
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    expected_signature = operator_cookie_signature(account, payload_text)
    if not hmac.compare_digest(submitted_signature, expected_signature):
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    current_time = int(time.time() if now is None else now)
    if (
        issued_at > current_time + 60
        or current_time - issued_at > OPERATOR_COOKIE_MAX_AGE_SECONDS
    ):
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    return OperatorAccountIdentity(
        account_id=account.account_id,
        account_name=account.account_name,
    )

def set_operator_cookie(service, response, identity):
    account = service.repository.get_operator_account_by_id(identity.account_id)
    if not account:
        return
    issued_at = int(time.time())
    payload_text = _encode_operator_cookie_payload(account, issued_at)
    response.set_cookie(
        OPERATOR_COOKIE_NAME,
        f"{payload_text}.{operator_cookie_signature(account, payload_text)}",
        httponly=True,
        max_age=OPERATOR_COOKIE_MAX_AGE_SECONDS,
        path="/",
        samesite="lax",
        secure=is_env_flag_enabled(OPERATOR_COOKIE_SECURE_ENV, default=False),
    )

def operator_cookie_signature(account, payload_text):
    message = f"{payload_text}:{account.password_hash}".encode("utf-8")
    return hmac.new(operator_cookie_secret(), message, sha256).hexdigest()

def operator_cookie_secret():
    configured_secret = os.environ.get(OPERATOR_COOKIE_SECRET_ENV)
    if configured_secret:
        return configured_secret.encode("utf-8")
    global _ephemeral_cookie_secret_warning_emitted
    if not _ephemeral_cookie_secret_warning_emitted:
        warnings.warn(
            f"{OPERATOR_COOKIE_SECRET_ENV} is not configured; using an ephemeral "
            "process-local cookie secret. Existing sessions will not survive restart.",
            RuntimeWarning,
            stacklevel=2,
        )
        _ephemeral_cookie_secret_warning_emitted = True
    return _EPHEMERAL_COOKIE_SECRET

def _encode_operator_cookie_payload(account, issued_at):
    payload = json.dumps(
        {
            "version": 1,
            "account_id": account.account_id,
            "account_name": account.account_name,
            "issued_at": int(issued_at),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

def _split_operator_cookie(cookie_value):
    parts = str(cookie_value).split(".", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    return parts[0], parts[1]

def _decode_operator_cookie_payload(payload_text):
    try:
        padding = "=" * (-len(payload_text) % 4)
        decoded = base64.urlsafe_b64decode(f"{payload_text}{padding}")
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE) from error
    if not isinstance(payload, dict):
        raise ValueError(AUTHENTICATION_REQUIRED_MESSAGE)
    return payload

def to_http_exception(error):
    message = str(error)
    if isinstance(error, WorkspaceMigrationRequiredError):
        status_code = 409
    else:
        status_code = 404 if "does not exist" in message else 400
    return HTTPException(status_code=status_code, detail=message)

def reject_scoped_fields(payload, forbidden_fields):
    for field_name in forbidden_fields:
        if field_name in (payload or {}):
            raise ValueError(f"Scoped workspace request does not accept {field_name}")

def final_summary_export_filename(summary):
    driver_name = safe_filename_part(summary.driver_name_snapshot or summary.driver_id)
    return (
        f"Final_Trip_Summary_{safe_filename_part(summary.summary_id)}_"
        f"{safe_filename_part(summary.delivery_date)}_{driver_name}.xlsx"
    )

def safe_filename_part(value):
    text = str(value or "").strip() or "Summary"
    safe_characters = []
    for character in text:
        if character.isalnum() or character in {"-", "_"}:
            safe_characters.append(character)
        elif character.isspace():
            safe_characters.append("_")
    safe = "".join(safe_characters).strip("_")
    return safe or "Summary"

def is_env_flag_enabled(name, default=False):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
