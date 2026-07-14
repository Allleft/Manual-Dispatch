"""Shared, privacy-safe System Logbook helpers for maintenance CLIs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from backend.services.manual_dispatch.logbook_file_service import LogbookFileService


MAINTENANCE_ACTOR_ENV = "MANUAL_DISPATCH_MAINTENANCE_ACTOR"


def add_maintenance_logbook_arguments(parser):
    """Add optional maintenance audit arguments without changing existing CLIs."""
    parser.add_argument(
        "--actor",
        help=(
            "Maintenance account name. Defaults to "
            f"{MAINTENANCE_ACTOR_ENV}, then Unknown."
        ),
    )
    parser.add_argument(
        "--logbook-dir",
        help="Optional System Logbook directory override for this invocation.",
    )
    return parser


def resolve_maintenance_actor(
    explicit_actor=None,
    environ: Mapping[str, str] | None = None,
):
    """Resolve a trimmed actor from CLI, environment, then the safe fallback."""
    explicit = str(explicit_actor or "").strip()
    if explicit:
        return explicit
    environment = os.environ if environ is None else environ
    configured = str(environment.get(MAINTENANCE_ACTOR_ENV, "") or "").strip()
    return configured or "Unknown"


def safe_basename(value):
    """Return only a final filename component for Windows or POSIX paths."""
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return None
    return normalized.rsplit("/", 1)[-1]


def sanitized_failure_metadata(error, phase):
    """Describe a failure without including messages, paths, or tracebacks."""
    return {
        "failure_phase": str(phase or "unknown"),
        "error_type": type(error).__name__,
    }


def workbook_import_failure_phase(error, workbook_path):
    """Classify importer failures without inspecting or logging error messages."""
    if not Path(workbook_path).is_file():
        return "workbook_read"
    if type(error).__module__ == "sqlite3":
        return "database_apply"
    if isinstance(error, OSError):
        return "database_backup"
    return "workbook_import"


def workbook_import_metadata(
    summary,
    *,
    workbook_path,
    database_path,
    count_fields,
):
    """Build basename-only aggregate metadata from an importer summary."""
    unresolved = dict(getattr(summary, "unresolved_assigned_to", {}) or {})
    backup_path = getattr(summary, "backup_path", None)
    metadata = {
        "mode": "apply",
        "workbook_filename": safe_basename(workbook_path),
        "database_filename": safe_basename(database_path),
    }
    for field_name in count_fields:
        metadata[field_name] = int(getattr(summary, field_name, 0) or 0)
    metadata.update(
        {
            "unresolved_alias_count": len(unresolved),
            "unresolved_alias_occurrence_count": sum(
                int(count or 0) for count in unresolved.values()
            ),
            "backup_created": bool(backup_path),
            "backup_filename": safe_basename(backup_path),
        }
    )
    return metadata


def record_maintenance_event(
    *,
    action,
    result,
    workspace,
    actor,
    entity_type,
    entity_id,
    summary,
    metadata,
    logbook_dir=None,
):
    """Best-effort event recording through the existing physical JSONL writer."""
    try:
        LogbookFileService(Path(logbook_dir) if logbook_dir else None).record(
            result=result,
            workspace=workspace,
            actor=resolve_maintenance_actor(actor),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            metadata=dict(metadata or {}),
        )
    except Exception:
        return False
    return True
