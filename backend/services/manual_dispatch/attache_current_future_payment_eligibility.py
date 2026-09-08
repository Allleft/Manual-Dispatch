from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
import re
import time


TERMS_30_DAYS = "30 DAYS"
TERMS_COD = "C.O.D."
PAYMENT_NOT_REQUIRED = "NOT_REQUIRED"
PAYMENT_PAID_IN_FULL = "PAID_IN_FULL"
PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
PAYMENT_UNKNOWN = "UNKNOWN"
PAID_IN_FULL_TOLERANCE = Decimal("0.005")
CURRENT_FUTURE_SOURCE = "attache-current-future"
ELIGIBILITY_PROOF_TTL_SECONDS = 15 * 60
INVALID_PROOF_MESSAGE = (
    "Invoice preview could not be verified. "
    "Refresh Today & Future Invoices before importing."
)


class EligibilitySnapshotError(ValueError):
    pass


def create_eligibility_proof(row, *, from_date, secret):
    snapshot = _eligibility_snapshot(row, from_date)
    return _snapshot_signature(snapshot, secret)


def verify_eligibility_snapshot(row, *, from_date, secret, now=None):
    proof = row.eligibility_proof
    if not isinstance(proof, str) or not re.fullmatch(r"[0-9a-f]{64}", proof):
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)
    snapshot = _eligibility_snapshot(row, from_date)
    if not hmac.compare_digest(proof, _snapshot_signature(snapshot, secret)):
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)

    current_time = int(time.time() if now is None else now)
    if (
        snapshot["issued_at"] > current_time
        or snapshot["expires_at"] - snapshot["issued_at"]
        != ELIGIBILITY_PROOF_TTL_SECONDS
    ):
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)
    if current_time >= snapshot["expires_at"]:
        raise EligibilitySnapshotError(
            "Invoice preview has expired. "
            "Refresh Today & Future Invoices before importing."
        )
    if snapshot["source"] != CURRENT_FUTURE_SOURCE:
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)
    return snapshot


def _eligibility_snapshot(row, from_date):
    if (
        not isinstance(from_date, str)
        or not isinstance(row.invoice_number, str)
        or not row.invoice_number
        or not isinstance(row.source, str)
        or row.customer_code is not None and not isinstance(row.customer_code, str)
        or row.terms_description is not None and not isinstance(row.terms_description, str)
        or type(row.issued_at) is not int
        or type(row.expires_at) is not int
    ):
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)
    try:
        if date.fromisoformat(from_date).isoformat() != from_date:
            raise ValueError
    except ValueError:
        raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE) from None
    balance = None
    if row.outstanding_balance is not None:
        balance = _decimal_balance(row.outstanding_balance)
        if balance is None:
            raise EligibilitySnapshotError(INVALID_PROOF_MESSAGE)
        balance = str(balance.normalize()) if balance else "0"
    return {
        "purpose": "manual-dispatch/current-future-eligibility/v1",
        "source": row.source,
        "invoice_number": row.invoice_number,
        "customer_code": row.customer_code,
        "terms_description": row.terms_description,
        "outstanding_balance": balance,
        "from_date": from_date,
        "issued_at": row.issued_at,
        "expires_at": row.expires_at,
    }


def _snapshot_signature(snapshot, secret):
    # Canonical JSON binds fields without delimiter ambiguity; purpose isolates
    # this proof from other uses of the existing server signing secret.
    message = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hmac.new(secret, message, sha256).hexdigest()


def normalize_terms_description(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if normalized == "COD":
        return TERMS_COD
    return normalized or None


def classify_payment_eligibility(terms_description, outstanding_balance):
    normalized_terms = normalize_terms_description(terms_description)
    if normalized_terms == TERMS_30_DAYS:
        return PAYMENT_NOT_REQUIRED
    if normalized_terms != TERMS_COD:
        return PAYMENT_UNKNOWN

    balance = _decimal_balance(outstanding_balance)
    if balance is None:
        return PAYMENT_UNKNOWN
    if balance <= PAID_IN_FULL_TOLERANCE:
        return PAYMENT_PAID_IN_FULL
    return PAYMENT_REQUIRED


def _decimal_balance(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        balance = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return balance if balance.is_finite() else None
