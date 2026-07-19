import os
import hmac
from hashlib import sha256
from fastapi import HTTPException
from backend.schemas import (
    AssignDriverVehicleRequest,
    SaveFinalTripSummaryRequest,
)
from backend.services.manual_dispatch.workspace_migration_readiness_service import WorkspaceMigrationRequiredError


ALLOW_REGISTRATION_ENV = "MANUAL_DISPATCH_ALLOW_REGISTRATION"

REGISTRATION_DISABLED_MESSAGE = "Registration is disabled. Please contact an administrator."

OPERATOR_COOKIE_NAME = "manual_dispatch_operator"

OPERATOR_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 12

OPERATOR_COOKIE_SECRET_ENV = "MANUAL_DISPATCH_AUTH_COOKIE_SECRET"

def assign_driver_vehicle_request_from_payload(payload):
    payload = payload or {}
    return AssignDriverVehicleRequest(
        dispatch_date=payload.get("dispatch_date"),
        delivery_date=payload.get("delivery_date"),
        driver_id=payload.get("driver_id"),
        vehicle_id=payload.get("vehicle_id") or None,
    )

def save_final_trip_summary_request_from_payload(payload):
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
        saved_by_account_name=payload.get("saved_by_account_name"),
        saved_by_account_id=payload.get("saved_by_account_id"),
    )

def with_logbook_actor(service, http_request, callback):
    with service.logbook_actor(current_operator_account_name(service, http_request)):
        return callback()

def current_operator_account_name(service, http_request):
    if not http_request:
        return None
    cookie_value = http_request.cookies.get(OPERATOR_COOKIE_NAME)
    if not cookie_value:
        # Some legacy/manual API clients still call mutation routes without the
        # browser login cookie; those operations remain valid and log Unknown.
        return None
    parts = str(cookie_value).split(":", 1)
    if len(parts) != 2:
        return None
    account_id_text, submitted_signature = parts
    try:
        account_id = int(account_id_text)
    except (TypeError, ValueError):
        return None
    account = service.repository.get_operator_account_by_id(account_id)
    if not account:
        return None
    expected_signature = operator_cookie_signature(account)
    if not hmac.compare_digest(submitted_signature, expected_signature):
        return None
    return account.account_name

def set_operator_cookie(service, response, identity):
    account = service.repository.get_operator_account_by_id(identity.account_id)
    if not account:
        return
    response.set_cookie(
        OPERATOR_COOKIE_NAME,
        f"{account.account_id}:{operator_cookie_signature(account)}",
        httponly=True,
        max_age=OPERATOR_COOKIE_MAX_AGE_SECONDS,
        samesite="lax",
    )

def operator_cookie_signature(account):
    message = (
        f"{account.account_id}:{account.account_name}:{account.password_hash}"
    ).encode("utf-8")
    return hmac.new(operator_cookie_secret(), message, sha256).hexdigest()

def operator_cookie_secret():
    return os.environ.get(
        OPERATOR_COOKIE_SECRET_ENV,
        "manual-dispatch-local-operator-cookie",
    ).encode("utf-8")

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
