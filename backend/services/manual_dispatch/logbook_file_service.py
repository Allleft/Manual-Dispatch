from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


LOGGER = logging.getLogger(__name__)
MELBOURNE_TIMEZONE_KEY = "Australia/Melbourne"
DEFAULT_LOGBOOK_DIR = "data/logbook"


def _load_melbourne_timezone():
    try:
        return ZoneInfo(MELBOURNE_TIMEZONE_KEY)
    except ZoneInfoNotFoundError:
        LOGGER.warning(
            "Timezone database is unavailable; using emergency fixed +10:00 "
            "Melbourne offset. Install tzdata so Australia/Melbourne daylight "
            "saving time is applied correctly."
        )
        return timezone(timedelta(hours=10), MELBOURNE_TIMEZONE_KEY)


MELBOURNE_TIMEZONE = _load_melbourne_timezone()


def _melbourne_now() -> datetime:
    return datetime.now(MELBOURNE_TIMEZONE)


class LogbookFileService:
    """Append business audit events to monthly JSON Lines text files."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        configured_dir = base_dir or os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        self.base_dir = Path(configured_dir or DEFAULT_LOGBOOK_DIR)

    def record(
        self,
        *,
        result: str,
        workspace: str,
        actor: str,
        action: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        summary: str,
        dispatch_date: str | None = None,
        delivery_date: str | None = None,
        pickup_date: str | None = None,
        driver: str | None = None,
        vehicle: str | None = None,
        run_sheet_id: str | None = None,
        collection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ) -> None:
        try:
            now = _melbourne_now()
            entry = {
                "time": now.isoformat(timespec="seconds"),
                "result": result,
                "workspace": workspace,
                "actor": actor or "Unknown",
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "summary": summary,
                "dispatch_date": dispatch_date,
                "delivery_date": delivery_date,
                "pickup_date": pickup_date,
                "driver": driver,
                "vehicle": vehicle,
                "run_sheet_id": run_sheet_id,
                "collection_id": collection_id,
                "metadata": metadata or {},
            }
            self.base_dir.mkdir(parents=True, exist_ok=True)
            path = self.base_dir / f"manual_dispatch_logbook_{now:%Y-%m}.txt"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(entry, ensure_ascii=False, sort_keys=True)
                    + "\n"
                )
        except Exception:
            LOGGER.exception("Failed to append Manual Dispatch logbook entry")
