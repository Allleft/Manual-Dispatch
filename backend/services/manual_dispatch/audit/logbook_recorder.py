import logging
from datetime import date
from . import FacadeAuditRecorder


LOGGER = logging.getLogger("backend.services.manual_dispatch_service")

LOGBOOK_DATE_FIELDS = ("dispatch_date", "delivery_date", "pickup_date")

REJECTED_LOGBOOK_DATE_FIELDS_KEY = "rejected_logbook_date_fields"

def _canonical_failed_logbook_date(value):
    """Return a strict optional date without letting audit cleanup raise."""
    try:
        if value is None:
            return None, False
        if not isinstance(value, str):
            return None, True
        text = value.strip()
        if not text:
            return None, False
        if text != value or date.fromisoformat(text).isoformat() != text:
            return None, True
        return text, False
    except Exception:
        return None, True


class LogbookRecorder(FacadeAuditRecorder):
    """Apply existing best-effort Logbook success/failure rules."""

    def _record_logbook(self, **entry):
        try:
            actor = entry.pop("actor", None) or self._current_logbook_actor()
            self.logbook.record(actor=actor, **entry)
        except Exception:
            LOGGER.exception("Failed to record Manual Dispatch logbook entry")

    def _record_failed_logbook(self, **entry):
        metadata = dict(entry.pop("metadata", {}) or {})
        metadata.setdefault("failure_reason", "Operation failed")
        rejected_date_fields = []
        for field_name in LOGBOOK_DATE_FIELDS:
            if field_name not in entry:
                continue
            normalized, rejected = _canonical_failed_logbook_date(entry[field_name])
            entry[field_name] = normalized
            if rejected:
                rejected_date_fields.append(field_name)
        if rejected_date_fields:
            metadata[REJECTED_LOGBOOK_DATE_FIELDS_KEY] = rejected_date_fields
        self._record_logbook(result="FAILED", metadata=metadata, **entry)
